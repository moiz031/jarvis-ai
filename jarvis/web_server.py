# jarvis/web_server.py - Web server with Super Mode APIs

import asyncio
import json
import logging
import os
import queue
from pathlib import Path
from typing import Dict, List

import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

try:
    from config import BASE_DIR, Config
except ImportError:
    from .config import BASE_DIR, Config

try:
    from memory.db import MemoryDB
except ImportError:
    try:
        from .memory.db import MemoryDB
    except Exception:
        MemoryDB = None

logger = logging.getLogger(__name__)


class JarvisWebServer:
    def __init__(self, input_queue, output_queue):
        self.app = FastAPI(title="Jarvis Neural Command Center")
        self.input_queue = input_queue
        self.output_queue = output_queue
        self.clients = set()
        self.running = True
        self.config = Config()

        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:8080", "http://localhost:8000", "http://127.0.0.1:8080", "http://127.0.0.1:8000"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        static_dir = BASE_DIR / "jarvis" / "static"
        if not static_dir.exists():
            static_dir = BASE_DIR / "static"

        if os.path.exists(static_dir):
            self.app.mount("/static", StaticFiles(directory=static_dir), name="static")
            logger.info("Serving static files from %s", static_dir)
        else:
            logger.warning("Static directory not found at %s", static_dir)

        @self.app.get("/favicon.ico")
        async def favicon():
            return HTMLResponse(content="", status_code=204)

        @self.app.get("/")
        async def get_ui():
            for _name in ("jarvis_ui_fixed.html", "jarvis_ui.html", "index.html"):
                html_path = BASE_DIR / "jarvis" / _name
                if html_path.exists():
                    break
                html_path = BASE_DIR / _name
                if html_path.exists():
                    break

            if not html_path.exists():
                logger.error("UI not found at %s", html_path)
                return HTMLResponse(content="<h1>Error: UI Not Found</h1>", status_code=500)

            try:
                with open(html_path, "r", encoding="utf-8") as fh:
                    return HTMLResponse(content=fh.read())
            except Exception as exc:
                logger.error("Error reading UI: %s", exc)
                return HTMLResponse(content="<h1>Error: Could not load UI</h1>", status_code=500)

        @self.app.get("/health")
        async def health_check():
            return {"status": "healthy", "version": "8.0.0-super"}

        @self.app.post("/api/settings")
        async def update_settings(request: dict):
            try:
                logger.info("Settings update: %s", request)
                return {"status": "success", "message": "Configuration updated"}
            except Exception as exc:
                logger.error("Settings update failed: %s", exc)
                raise HTTPException(status_code=500, detail=str(exc))

        @self.app.get("/api/super/state")
        async def super_state():
            return {
                "state": self._read_json(self.config.SUPER_STATE_PATH, {}),
                "channels": self._read_json(self.config.SUPER_CHANNELS_PATH, {}),
                "directory": self._read_json(self.config.SUPER_DIRECTORY_PATH, {}),
                "policy": self._read_json(self.config.SUPER_POLICY_PATH, {}),
            }

        @self.app.post("/api/super/onboard")
        async def super_onboard(request: dict):
            self.input_queue.put({"type": "super_onboard", "data": request})
            return {"ok": True, "queued": True}

        @self.app.post("/api/super/access")
        async def super_access(request: dict):
            state = self._read_json(self.config.SUPER_STATE_PATH, {})
            system_access = request.get("system_access_granted")
            access_scopes = request.get("access_scopes")

            if system_access is not None:
                granted = bool(system_access)
                state["system_access_granted"] = granted
                state["permission_profile"] = "power" if granted else "basic"

            if isinstance(access_scopes, dict):
                scopes = state.get("access_scopes") or {}
                for key in ("files", "browser", "automation"):
                    if key in access_scopes:
                        scopes[key] = bool(access_scopes[key])
                state["access_scopes"] = scopes

            state["system_access_prompted"] = True
            self._write_json(self.config.SUPER_STATE_PATH, state)
            return {"ok": True, "state": state}

        @self.app.post("/api/super/channel/connect")
        async def super_connect_channel(request: dict):
            self.input_queue.put({"type": "super_connect_channel", "data": request})
            return {"ok": True, "queued": True}

        @self.app.post("/api/super/channel/disconnect")
        async def super_disconnect_channel(request: dict):
            self.input_queue.put({"type": "super_disconnect_channel", "data": request})
            return {"ok": True, "queued": True}

        @self.app.post("/api/super/channel/send")
        async def super_channel_send(request: dict):
            self.input_queue.put({"type": "super_channel_send", "data": request})
            return {"ok": True, "queued": True}

        @self.app.post("/api/super/channel/inbound")
        async def super_channel_inbound(request: dict):
            self.input_queue.put({"type": "super_channel_inbound", "data": request})
            return {"ok": True, "queued": True}

        @self.app.post("/api/super/task")
        async def super_task(request: dict):
            self.input_queue.put({"type": "super_task", "data": request})
            return {"ok": True, "queued": True}

        @self.app.post("/api/super/plugin/reload")
        async def super_plugin_reload():
            self.input_queue.put({"type": "super_plugin_reload", "data": {}})
            return {"ok": True, "queued": True}

        @self.app.post("/api/super/status")
        async def super_status():
            self.input_queue.put({"type": "super_status", "data": {}})
            return {"ok": True, "queued": True}

        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            self.clients.add(websocket)
            logger.info("Client connected. Total clients: %s", len(self.clients))

            try:
                while True:
                    data = await websocket.receive_text()
                    msg = json.loads(data)
                    self.input_queue.put(msg)
            except WebSocketDisconnect:
                self.clients.discard(websocket)
                logger.info("Client disconnected. Total clients: %s", len(self.clients))
            except json.JSONDecodeError:
                logger.error("Invalid JSON received")
                self.clients.discard(websocket)
            except Exception as exc:
                logger.error("WebSocket error: %s", exc)
                self.clients.discard(websocket)

    def _read_json(self, path: Path, default):
        if not path.exists():
            return default
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            return default

    def _write_json(self, path: Path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
        tmp.replace(path)

    async def _metrics_loop(self):
        try:
            import psutil
        except Exception:
            psutil = None

        while self.running:
            try:
                if psutil is None:
                    await asyncio.sleep(2)
                    continue

                metrics = {
                    "type": "metrics",
                    "data": {
                        "cpu": round(psutil.cpu_percent(), 1),
                        "ram": round(psutil.virtual_memory().percent, 1),
                    },
                }
                disconnected = set()
                for client in self.clients:
                    try:
                        await client.send_json(metrics)
                    except Exception:
                        disconnected.add(client)

                for client in disconnected:
                    self.clients.discard(client)

                await asyncio.sleep(2)
            except Exception as exc:
                logger.error("Metrics loop error: %s", exc)
                await asyncio.sleep(2)

    async def _process_loop(self):
        try:
            import psutil
        except Exception:
            psutil = None

        while self.running:
            try:
                if psutil is None:
                    await asyncio.sleep(3)
                    continue

                processes: List[Dict] = []
                for proc in psutil.process_iter(["name", "cpu_percent", "memory_percent"]):
                    try:
                        processes.append(proc.info)
                    except Exception:
                        pass

                processes.sort(key=lambda x: x.get("cpu_percent", 0) or 0, reverse=True)
                top_5 = processes[:5]
                formatted = [
                    {
                        "name": p.get("name"),
                        "cpu": round(p.get("cpu_percent", 0) or 0, 1),
                        "mem": round(p.get("memory_percent", 0) or 0, 1),
                    }
                    for p in top_5
                ]

                msg = {"type": "processes", "data": formatted}
                disconnected = set()
                for client in self.clients:
                    try:
                        await client.send_json(msg)
                    except Exception:
                        disconnected.add(client)

                for client in disconnected:
                    self.clients.discard(client)

                await asyncio.sleep(3)
            except Exception as exc:
                logger.error("Process loop error: %s", exc)
                await asyncio.sleep(3)

    async def _broadcast_loop(self):
        while self.running:
            try:
                msg = self.output_queue.get_nowait()
                if msg:
                    disconnected = set()
                    for client in self.clients:
                        try:
                            await client.send_json(msg)
                        except Exception:
                            disconnected.add(client)

                    for client in disconnected:
                        self.clients.discard(client)
            except queue.Empty:
                await asyncio.sleep(0.05)
            except Exception as exc:
                logger.error("Broadcast error: %s", exc)
                await asyncio.sleep(0.05)

    async def _cockpit_loop(self):
        while self.running:
            try:
                snapshot = {
                    "memory": {"tasks": [], "routines": [], "knowledge_count": 0, "tool_event_count": 0, "recent_actions": []},
                    "super": {
                        "state": self._read_json(self.config.SUPER_STATE_PATH, {}),
                        "channels": self._read_json(self.config.SUPER_CHANNELS_PATH, {}),
                        "directory": self._read_json(self.config.SUPER_DIRECTORY_PATH, {}),
                    },
                }
                if MemoryDB is not None:
                    try:
                        db = MemoryDB()
                        snapshot["memory"] = db.get_dashboard_snapshot()
                    except Exception:
                        pass

                msg = {"type": "cockpit_state", "data": snapshot}
                disconnected = set()
                for client in self.clients:
                    try:
                        await client.send_json(msg)
                    except Exception:
                        disconnected.add(client)

                for client in disconnected:
                    self.clients.discard(client)

                await asyncio.sleep(4)
            except Exception as exc:
                logger.error("Cockpit loop error: %s", exc)
                await asyncio.sleep(4)

    def run(self, host="0.0.0.0", port=8080):
        @self.app.on_event("startup")
        async def startup_event():
            logger.info("Starting background tasks...")
            asyncio.create_task(self._broadcast_loop())
            asyncio.create_task(self._metrics_loop())
            asyncio.create_task(self._process_loop())
            asyncio.create_task(self._cockpit_loop())

        logger.info("Starting Jarvis Web Server on %s:%s", host, port)
        uvicorn.run(self.app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    import multiprocessing

    multiprocessing.freeze_support()
    i_q = queue.Queue()
    o_q = queue.Queue()
    server = JarvisWebServer(i_q, o_q)
    server.run()
