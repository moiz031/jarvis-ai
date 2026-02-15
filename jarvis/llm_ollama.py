# llm_ollama.py – Unified LLM Provider (Ollama + OpenAI/OpenRouter)

import os
import json
import time
import requests
from pathlib import Path
from typing import List, Optional

class OllamaLLM:
    """Unified LLM client.
    Primary strategy: Try Ollama (local) first.
    Fallback strategy: If OpenAI API Key present, try ChatGPT/OpenRouter.
    """

    def __init__(self, config):
        self.config = config
        self.ollama_host = config.OLLAMA_HOST.rstrip('/')
        self.primary_model = config.OLLAMA_MODEL
        self.fallback_model = config.FALLBACK_MODEL
        self.openai_key = getattr(config, 'OPENAI_API_KEY', None)
        self.openai_base = getattr(config, 'OPENAI_BASE_URL', "https://api.openai.com/v1")
        self.timeout = 60
        self.model_cache_ttl = 30
        self._last_model_refresh = 0.0
        self._available_models: List[str] = []
        self.default_error_reply = (
            "Maafi Boss, abhi LLM service unavailable hai. "
            "Ollama start karein ya valid cloud API configure karein."
        )
        
        # Caching
        self.cache_dir = Path(__file__).parent / "data"
        self.cache_dir.mkdir(exist_ok=True)
        self.cache_file = self.cache_dir / "llm_cache.json"
        self.cache: dict = self._load_cache()

    def _load_cache(self):
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {}
        
    def _save_cache(self):
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, indent=2)
        except Exception as e:
            print(f"[LLM] Cache save error: {e}")

    def _get_cache_key(self, model, prompt):
        import hashlib
        return hashlib.md5(f"{model}:{prompt}".encode()).hexdigest()

    def _list_local_models(self) -> List[str]:
        """Return installed Ollama model names with short TTL caching."""
        now = time.time()
        if self._available_models and (now - self._last_model_refresh) < self.model_cache_ttl:
            return self._available_models

        try:
            response = requests.get(f"{self.ollama_host}/api/tags", timeout=5)
            response.raise_for_status()
            models = response.json().get("models", [])
            names = [m.get("name", "") for m in models if m.get("name")]
            self._available_models = names
            self._last_model_refresh = now
            return names
        except Exception:
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
            # We call the internal _request_ollama with stream=True
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
            
            # Save to cache after complete stream
            full_response = "".join(full_response_chunks)
            if full_response.strip():
                key = self._get_cache_key(local_model, prompt)
                self.cache[key] = full_response
                self._save_cache()
                
        except Exception as e:
            print(f"[LLM] Streaming error: {e}")
            # Fallback to non-streaming generation if streaming fails
            yield self.generate(prompt, images)

    def _request_ollama(self, model: str, prompt: str, stream: bool, images: Optional[List[str]] = None):
        """Helper to make the actual request to Ollama."""
        url = f"{self.ollama_host}/api/generate"
        
        payload = {
            "model": model, "prompt": prompt, "stream": stream,
            "options": {"temperature": 0.3, "num_predict": 256, "top_k": 40, "num_ctx": 4096}
        }
        if images:
            payload["images"] = images
            
        try:
            if stream:
                response = requests.post(url, json=payload, timeout=self.timeout, stream=True)
                if response.status_code == 404:
                    print(
                        f"[LLM] Ollama returned 404 for model '{model}'. "
                        "Model may be missing. Run: ollama pull <model>"
                    )
                response.raise_for_status()
                return response
            else:
                print(f"[LLM] Sending request to Ollama: {url}")
                response = requests.post(url, json=payload, timeout=self.timeout)
                if response.status_code == 404:
                    print(
                        f"[LLM] Ollama returned 404 for model '{model}'. "
                        "Model may be missing. Run: ollama pull <model>"
                    )
                response.raise_for_status()
                return response.json().get("response", "")
        except requests.exceptions.RequestException as e:
            print(f"[LLM] Connection Error: {e}")
            raise

    def generate(self, prompt: str, images: Optional[List[str]] = None) -> str:
        """Generate response with caching."""
        local_model = self._select_local_model()
        key = self._get_cache_key(local_model, prompt + (str(images) if images else ""))
        if key in self.cache:
            print(f"[LLM] Cache Hit for: {prompt[:20]}...")
            return self.cache[key]

        try:
            # Try local Ollama first
            response = self._request_ollama(local_model, prompt, stream=False, images=images)
            self.cache[key] = response
            self._save_cache()
            return response
        except Exception as e:
            print(f"[LLM] Local Ollama error: {e}")
            # Fallback to cloud provider if a key is present
            if self.openai_key:
                print("[LLM] Attempting fallback to cloud API...")
                try:
                    return self._call_openai(prompt, images)
                except Exception as fallback_e:
                    print(f"[LLM] Cloud fallback also failed: {fallback_e}")
            
            return self.default_error_reply

    def _call_openai(self, prompt: str, images: Optional[List[str]] = None) -> str:
        """Fallback to call OpenAI/OpenRouter compatible API."""
        if not self.openai_key:
            raise ValueError("OpenAI API key not configured. Cannot use cloud fallback.")
        
        print(f"[LLM] Fallback to: {self.openai_base}")
        headers = {
            "Authorization": f"Bearer {self.openai_key}",
            "Content-Type": "application/json"
        }
        
        content_parts = [{"type": "text", "text": prompt}]
        if images:
            for img_b64 in images:
                content_parts.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}
                })

        payload = {
            "model": self.fallback_model,
            "messages": [{"role": "user", "content": content_parts}],
            "max_tokens": 1500
        }
        
        try:
            response = requests.post(f"{self.openai_base.rstrip('/')}/chat/completions", headers=headers, json=payload, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            return data['choices'][0]['message']['content']
        except requests.exceptions.RequestException as e:
            print(f"[LLM] Cloud API error: {e}")
            if hasattr(e.response, 'status_code') and e.response.status_code == 401:
                raise ValueError("Invalid OpenAI API key. Please check your configuration.")
            raise

    def chat(self, messages: list) -> str:
        prompt = "\n".join([f"{m['role']}: {m['content']}" for m in messages])
        return self.generate(prompt)
