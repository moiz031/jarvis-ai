"""Shared dataclasses for Super Mode."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class ChannelMessage:
    channel: str
    user_id: str
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=utc_now)


@dataclass(slots=True)
class TaskRequest:
    task_id: str
    source: str
    user_id: str
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)


@dataclass(slots=True)
class TaskResult:
    task_id: str
    ok: bool
    message: str
    payload: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    completed_at: str = field(default_factory=utc_now)


@dataclass(slots=True)
class JobRecord:
    job_id: str
    name: str
    status: str
    attempts: int
    max_retries: int
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    result: Optional[Any] = None
    error: Optional[str] = None
