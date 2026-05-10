# llm_ollama.py - Unified LLM Provider (Ollama + OpenAI/OpenRouter)

import json
import logging
import os
import time
from pathlib import Path
from typing import List, Optional

import requests

logger = logging.getLogger(__name__)

try:
    from .runtime_support import ensure_ollama_running
except Exception:
    try:
        from runtime_support import ensure_ollama_running
    except Exception:
        ensure_ollama_running = None


class OllamaLLM:
    """Unified LLM client.
    Primary strategy: Cloud-first when configured, otherwise Ollama-first.
    Fallback strategy: Try the other provider on failure.
    """

    def __init__(self, config):
        self.config = config
        self.ollama_host = config.OLLAMA_HOST.rstrip("/")
        self.primary_model = config.OLLAMA_MODEL
        self.fallback_model = config.FALLBACK_MODEL
        self.openai_base = getattr(config, "OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.openai_key = self._resolve_cloud_key()
        self.prefer_cloud = bool(getattr(config, "LLM_PREFER_CLOUD", True))

        self.connect_timeout = float(os.getenv("LLM_CONNECT_TIMEOUT_SECONDS", "5"))
        self.timeout = int(os.getenv("LLM_TIMEOUT_SECONDS", "120"))
        self.num_ctx = int(
            os.getenv(
                "OLLAMA_NUM_CTX",
                "2048" if bool(getattr(config, "LOW_RAM_MODE", False)) else "4096",
            )
        )
        self.num_predict = int(
            os.getenv(
                "OLLAMA_NUM_PREDICT",
                "192" if bool(getattr(config, "LOW_RAM_MODE", False)) else "256",
            )
        )
        self.model_cache_ttl = 30
        self._last_model_refresh = 0.0
        self._available_models: List[str] = []
        self._cloud_unhealthy = False
        self._local_unhealthy = False
        self._attempted_local_boot = False
        self.default_error_reply = (
            "Maafi Boss, abhi LLM service unavailable hai. "
            "Ollama start karein ya valid cloud API configure karein."
        )

        # Caching
        self.cache_dir = Path(__file__).parent / "data"
        self.cache_dir.mkdir(exist_ok=True)
        self.cache_file = self.cache_dir / "llm_cache.json"
        self.cache: dict = self._load_cache()
        self._validate_cloud_config()

    def _detect_cloud_provider(self) -> str:
        base = (self.openai_base or "").lower()
        if "openrouter.ai" in base:
            return "openrouter"
        if "api.x.ai" in base or "x.ai" in base:
            return "xai"
        if "api.groq.com" in base:
            return "groq"
        return "openai"

    def _resolve_cloud_key(self) -> Optional[str]:
        provider = self._detect_cloud_provider()
        if provider == "openrouter":
            return (
                getattr(self.config, "OPENROUTER_API_KEY", None)
                or getattr(self.config, "OPENAI_API_KEY", None)
            )
        if provider == "xai":
            return (
                getattr(self.config, "XAI_API_KEY", None)
                or getattr(self.config, "OPENAI_API_KEY", None)
            )
        if provider == "groq":
            return (
                getattr(self.config, "GROQ_API_KEY", None)
                or getattr(self.config, "OPENAI_API_KEY", None)
            )
        return getattr(self.config, "OPENAI_API_KEY", None)

    def _validate_cloud_config(self) -> None:
        provider = self._detect_cloud_provider()
        if not self.openai_key:
            return
        key = str(self.openai_key)
        if provider == "openrouter" and key.startswith("sk-proj-"):
            logger.warning(
                "[LLM] OPENAI_BASE_URL points to OpenRouter but key looks like OpenAI key. "
                "Set OPENROUTER_API_KEY (or a valid OpenRouter key) to avoid 401 errors."
            )
        if provider == "openai" and key.startswith("sk-or-"):
            logger.warning(
                "[LLM] OPENAI_BASE_URL points to OpenAI but key looks like OpenRouter key."
            )

    def _is_degraded_response(self, text: str) -> bool:
        lowered = (text or "").strip().lower()
        if not lowered:
            return True
        if "llm service unavailable" in lowered:
            return True
        if "ollama start karein" in lowered:
            return True
        if "ji boss, command mil gaya" in lowered:
            return True
        if "processing shuru karta hoon" in lowered:
            return True
        if lowered.startswith("###plan###"):
            return True
        if "my next prompt to you will be:" in lowered:
            return True
        return False

    def _normalize_openrouter_model(self, model: str) -> str:
        """OpenRouter expects namespaced model IDs (e.g., provider/model)."""
        if "openrouter" not in (self.openai_base or "").lower():
            return model
        if "/" in model:
            return model
        return f"openai/{model}"

    def _load_cache(self):
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as fh:
                    return json.load(fh)
            except Exception as exc:
                logger.warning("[LLM] Cache load error: %s", exc)
        return {}

    def _save_cache(self):
        try:
            with open(self.cache_file, "w", encoding="utf-8") as fh:
                json.dump(self.cache, fh, indent=2)
        except Exception as exc:
            logger.warning("[LLM] Cache save error: %s", exc)

    def _get_cache_key(self, model, prompt):
        import hashlib

        return hashlib.md5(f"{model}:{prompt}".encode()).hexdigest()

    def _list_local_models(self) -> List[str]:
        """Return installed Ollama model names with short TTL caching."""
        now = time.time()
        if self._available_models and (now - self._last_model_refresh) < self.model_cache_ttl:
            return self._available_models

        try:
            response = requests.get(
                f"{self.ollama_host}/api/tags",
                timeout=(self.connect_timeout, self.timeout),
            )
            response.raise_for_status()
            models = response.json().get("models", [])
            names = [m.get("name", "") for m in models if m.get("name")]
            self._available_models = names
            self._last_model_refresh = now
            return names
        except Exception as exc:
            logger.warning("[LLM] Could not list local models: %s", exc)
            if (not self._attempted_local_boot) and ensure_ollama_running is not None:
                self._attempted_local_boot = True
                boot = ensure_ollama_running(
                    self.ollama_host,
                    auto_start=bool(getattr(self.config, "OLLAMA_AUTO_START", True)),
                )
                if boot.get("ok"):
                    try:
                        response = requests.get(
                            f"{self.ollama_host}/api/tags",
                            timeout=(self.connect_timeout, self.timeout),
                        )
                        response.raise_for_status()
                        models = response.json().get("models", [])
                        names = [m.get("name", "") for m in models if m.get("name")]
                        self._available_models = names
                        self._last_model_refresh = time.time()
                        return names
                    except Exception as retry_exc:
                        logger.warning("[LLM] Ollama auto-start retry failed: %s", retry_exc)
            return []

    def _select_local_model(self) -> str:
        """
        Pick best available model:
        1) configured primary,
        2) configured fallback,
        3) first installed model,
        4) configured primary (if Ollama unreachable).
        """
        models = self._list_local_models()
        if not models:
            return self.primary_model
        if self.primary_model in models:
            return self.primary_model
        if self.fallback_model in models:
            print(f"[LLM] Using fallback local model: {self.fallback_model}")
            return self.fallback_model
        print(f"[LLM] Configured model missing. Using installed model: {models[0]}")
        return models[0]

    def generate_stream(self, prompt: str, images: Optional[List[str]] = None):
        """Yields response chunks for streaming. Skips cache for now to ensure freshness."""
        local_model = self._select_local_model()
        try:
            full_response_chunks: List[str] = []
            response = self._request_ollama(local_model, prompt, stream=True, images=images)

            for line in response.iter_lines():
                if line:
                    try:
                        chunk = json.loads(line)
                        text: str = str(chunk.get("response", ""))
                        if text:
                            yield text
                            full_response_chunks.append(text)
                        if chunk.get("done"):
                            break
                    except json.JSONDecodeError:
                        continue

            full_response = "".join(full_response_chunks)
            if full_response.strip() and not self._is_degraded_response(full_response):
                key = self._get_cache_key(local_model, prompt)
                self.cache[key] = full_response
                self._save_cache()

        except Exception as exc:
            print(f"[LLM] Streaming error: {exc}")
            yield self.generate(prompt, images)

    def _request_ollama(self, model: str, prompt: str, stream: bool, images: Optional[List[str]] = None):
        """Helper to make the actual request to Ollama."""
        url = f"{self.ollama_host}/api/generate"

        payload = {
            "model": model,
            "prompt": prompt,
            "stream": stream,
            "options": {
                "temperature": 0.25,
                "num_predict": self.num_predict,
                "top_k": 40,
                "num_ctx": self.num_ctx,
            },
        }
        if images:
            payload["images"] = images

        timeout = (self.connect_timeout, self.timeout)
        try:
            if stream:
                response = requests.post(url, json=payload, timeout=timeout, stream=True)
                if response.status_code == 404:
                    print(
                        f"[LLM] Ollama returned 404 for model '{model}'. "
                        "Model may be missing. Run: ollama pull <model>"
                    )
                response.raise_for_status()
                return response

            print(f"[LLM] Sending request to Ollama: {url}")
            response = requests.post(url, json=payload, timeout=timeout)
            if response.status_code == 404:
                print(
                    f"[LLM] Ollama returned 404 for model '{model}'. "
                    "Model may be missing. Run: ollama pull <model>"
                )
            response.raise_for_status()
            return response.json().get("response", "")
        except requests.exceptions.RequestException as exc:
            detail = ""
            if getattr(exc, "response", None) is not None:
                try:
                    detail = f" | body={exc.response.text[:300]}"
                except Exception:
                    detail = ""
            print(f"[LLM] Connection Error: {exc}{detail}")
            raise

    def generate(self, prompt: str, images: Optional[List[str]] = None) -> str:
        """Generate response with caching."""
        local_model = self._select_local_model()
        key = self._get_cache_key(local_model, prompt + (str(images) if images else ""))

        cached = self.cache.get(key)
        if cached and not self._is_degraded_response(cached):
            print(f"[LLM] Cache Hit for: {prompt[:20]}...")
            return cached
        if cached and self._is_degraded_response(cached):
            self.cache.pop(key, None)
            self._save_cache()

        if self.prefer_cloud and self.openai_key and not self._cloud_unhealthy:
            cloud_model = self._normalize_openrouter_model(self.fallback_model)
            cloud_key = self._get_cache_key(f"cloud:{cloud_model}", prompt + (str(images) if images else ""))
            cached_cloud = self.cache.get(cloud_key)
            if cached_cloud and not self._is_degraded_response(cached_cloud):
                print(f"[LLM] Cloud cache hit for: {prompt[:20]}...")
                return cached_cloud
            try:
                response = self._call_openai(prompt, images)
                if response and not self._is_degraded_response(response):
                    self.cache[cloud_key] = response
                    self._save_cache()
                    return response
            except ValueError as exc:
                if "Invalid OpenAI API key" in str(exc):
                    print(f"[LLM] Auth failed. Disabling cloud fallback for this session: {exc}")
                    self._cloud_unhealthy = True
                else:
                    print(f"[LLM] Cloud preferred path failed: {exc}")
            except Exception as exc:
                print(f"[LLM] Cloud preferred path failed, falling back to local: {exc}")

        try:
            response = self._request_ollama(local_model, prompt, stream=False, images=images)
            if response and not self._is_degraded_response(response):
                self.cache[key] = response
                self._save_cache()
            return response
        except Exception as exc:
            print(f"[LLM] Local Ollama error: {exc}")
            if self.openai_key and not self.prefer_cloud and not self._cloud_unhealthy:
                print("[LLM] Attempting fallback to cloud API...")
                try:
                    return self._call_openai(prompt, images)
                except ValueError as exc:
                    if "Invalid OpenAI API key" in str(exc):
                        print(f"[LLM] Auth failed. Disabling cloud fallback: {exc}")
                        self._cloud_unhealthy = True
                    else:
                        print(f"[LLM] Cloud fallback failed: {exc}")
                except Exception as fallback_exc:
                    print(f"[LLM] Cloud fallback also failed: {fallback_exc}")

            return self.default_error_reply

    def _call_openai(self, prompt: str, images: Optional[List[str]] = None) -> str:
        """Fallback to call OpenAI/OpenRouter compatible API."""
        if not self.openai_key:
            raise ValueError("OpenAI API key not configured. Cannot use cloud fallback.")

        print(f"[LLM] Fallback to: {self.openai_base}")
        headers = {
            "Authorization": f"Bearer {self.openai_key}",
            "Content-Type": "application/json",
        }

        model = self._normalize_openrouter_model(self.fallback_model)
        if "openrouter" not in (self.openai_base or "").lower() and "/" in model:
            model = model.split("/", 1)[1]

        if "openrouter" in (self.openai_base or "").lower():
            headers["HTTP-Referer"] = os.getenv("OPENROUTER_SITE_URL", "http://localhost")
            headers["X-Title"] = os.getenv("OPENROUTER_APP_NAME", "JarvisAI")

        content_parts = [{"type": "text", "text": prompt}]
        if images:
            for img_b64 in images:
                content_parts.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"},
                    }
                )

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": content_parts}],
            "max_tokens": 1500,
        }

        try:
            response = requests.post(
                f"{self.openai_base.rstrip('/')}/chat/completions",
                headers=headers,
                json=payload,
                timeout=(self.connect_timeout, self.timeout),
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except requests.exceptions.RequestException as exc:
            print(f"[LLM] Cloud API error: {exc}")
            if hasattr(exc, "response") and exc.response is not None and exc.response.status_code == 401:
                raise ValueError("Invalid OpenAI API key. Please check your configuration.")
            raise

    def chat(self, messages: list) -> str:
        prompt = "\n".join([f"{m['role']}: {m['content']}" for m in messages])
        return self.generate(prompt)
