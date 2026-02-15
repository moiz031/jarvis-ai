"""Lightweight background worker pool with retries."""

from __future__ import annotations

import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Callable, Dict

try:
    import psutil
except Exception:
    psutil = None

from .schemas import JobRecord


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


class WorkerPool:
    def __init__(self, max_workers: int = 2, low_ram_mode: bool = True):
        self.max_workers = max(1, max_workers)
        self.low_ram_mode = low_ram_mode
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers, thread_name_prefix="jarvis-worker")
        self._lock = threading.Lock()
        self._jobs: Dict[str, JobRecord] = {}

    def _ram_guard(self) -> bool:
        if not self.low_ram_mode or psutil is None:
            return True
        try:
            return psutil.virtual_memory().percent < 90
        except Exception:
            return True

    def submit(self, name: str, fn: Callable[..., Any], *args, retries: int = 1, **kwargs) -> str:
        job_id = str(uuid.uuid4())
        record = JobRecord(
            job_id=job_id,
            name=name,
            status="queued",
            attempts=0,
            max_retries=max(0, retries),
        )
        with self._lock:
            self._jobs[job_id] = record

        self.executor.submit(self._run, job_id, fn, args, kwargs)
        return job_id

    def _run(self, job_id: str, fn: Callable[..., Any], args, kwargs):
        while True:
            with self._lock:
                rec = self._jobs[job_id]
                rec.status = "running"
                rec.updated_at = _ts()
                rec.attempts += 1

            if not self._ram_guard():
                with self._lock:
                    rec = self._jobs[job_id]
                    rec.status = "failed"
                    rec.error = "RAM guard blocked task scheduling."
                    rec.updated_at = _ts()
                return

            try:
                result = fn(*args, **kwargs)
                with self._lock:
                    rec = self._jobs[job_id]
                    rec.status = "completed"
                    rec.result = result
                    rec.updated_at = _ts()
                return
            except Exception as exc:
                with self._lock:
                    rec = self._jobs[job_id]
                    rec.error = str(exc)
                    rec.updated_at = _ts()
                    exhausted = rec.attempts > rec.max_retries
                    if exhausted:
                        rec.status = "failed"
                        return
                    rec.status = "retrying"
                time.sleep(min(4, rec.attempts))

    def status(self, job_id: str):
        with self._lock:
            rec = self._jobs.get(job_id)
            if not rec:
                return None
            return {
                "job_id": rec.job_id,
                "name": rec.name,
                "status": rec.status,
                "attempts": rec.attempts,
                "max_retries": rec.max_retries,
                "created_at": rec.created_at,
                "updated_at": rec.updated_at,
                "result": rec.result,
                "error": rec.error,
            }

    def list_jobs(self, limit: int = 30):
        with self._lock:
            jobs = list(self._jobs.values())
        jobs.sort(key=lambda j: j.updated_at, reverse=True)
        out = []
        for rec in jobs[:limit]:
            out.append(
                {
                    "job_id": rec.job_id,
                    "name": rec.name,
                    "status": rec.status,
                    "attempts": rec.attempts,
                    "max_retries": rec.max_retries,
                    "updated_at": rec.updated_at,
                }
            )
        return out

    def shutdown(self):
        self.executor.shutdown(wait=False, cancel_futures=True)
