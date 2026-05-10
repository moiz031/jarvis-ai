# logger_config.py - Comprehensive logging configuration for Jarvis

import logging
import logging.handlers
import gzip
import json
import os
import re
import shutil
from pathlib import Path
from datetime import datetime
import sys

# Create logs directory
LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

# Log file path
LOG_FILE = LOG_DIR / f"jarvis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
TELEMETRY_FILE = LOG_DIR / "telemetry.jsonl"

_REDACTION_PATTERNS = (
    (re.compile(r"(api[_-]?key\s*[=:]\s*)([^\s,;]+)", re.IGNORECASE), r"\1[REDACTED]"),
    (re.compile(r"(token\s*[=:]\s*)([^\s,;]+)", re.IGNORECASE), r"\1[REDACTED]"),
    (re.compile(r"(authorization\s*:\s*bearer\s+)([^\s,;]+)", re.IGNORECASE), r"\1[REDACTED]"),
    (re.compile(r"(password\s*[=:]\s*)([^\s,;]+)", re.IGNORECASE), r"\1[REDACTED]"),
    (re.compile(r"(secret\s*[=:]\s*)([^\s,;]+)", re.IGNORECASE), r"\1[REDACTED]"),
)


def _redact_text(value: str) -> str:
    text = str(value)
    for pattern, replacement in _REDACTION_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default


class SensitiveDataFilter(logging.Filter):
    def filter(self, record):
        record.msg = _redact_text(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: _redact_text(v) for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(_redact_text(v) for v in record.args)
            else:
                record.args = _redact_text(record.args)
        return True


class GZipRotatingFileHandler(logging.handlers.RotatingFileHandler):
    def doRollover(self):
        super().doRollover()
        for idx in range(self.backupCount, 0, -1):
            rotated_path = Path(f"{self.baseFilename}.{idx}")
            gz_path = Path(f"{self.baseFilename}.{idx}.gz")
            if rotated_path.exists() and not gz_path.exists():
                with rotated_path.open("rb") as src, gzip.open(gz_path, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                rotated_path.unlink()


def _prune_old_logs(log_dir: Path, retention_days: int) -> None:
    if retention_days <= 0:
        return
    cutoff = datetime.now().timestamp() - (retention_days * 86400)
    for path in log_dir.glob("*"):
        try:
            if path.is_file() and path.stat().st_mtime < cutoff:
                path.unlink()
        except Exception:
            continue

class ColoredFormatter(logging.Formatter):
    """Colored log formatter for console output."""
    
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
        'RESET': '\033[0m'        # Reset
    }
    
    def format(self, record):
        if sys.platform != 'win32':  # Colors work on Unix-like systems
            levelname = record.levelname
            if levelname in self.COLORS:
                record.levelname = f"{self.COLORS[levelname]}{levelname}{self.COLORS['RESET']}"
        return super().format(record)

def setup_logging(log_level=logging.INFO):
    """Setup comprehensive logging for the entire application."""
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Clear existing handlers
    root_logger.handlers.clear()
    root_logger.filters.clear()
    root_logger.addFilter(SensitiveDataFilter())
    
    # Format
    log_format = '%(asctime)s | %(name)s | %(levelname)s | %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    
    # Console Handler (colored)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_formatter = ColoredFormatter(log_format, datefmt=date_format)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    class JsonFormatter(logging.Formatter):
        def format(self, record):
            log_record = {
                "timestamp": self.formatTime(record, self.datefmt),
                "name": record.name,
                "level": record.levelname,
                "message": _redact_text(record.getMessage()),
                "module": record.module,
                "lineno": record.lineno
            }
            if record.exc_info:
                log_record["exc_info"] = self.formatException(record.exc_info)
            return json.dumps(log_record)

    _prune_old_logs(LOG_DIR, _int_env("JARVIS_LOG_RETENTION_DAYS", 14))

    file_handler = GZipRotatingFileHandler(
        LOG_FILE,
        maxBytes=_int_env("JARVIS_LOG_MAX_BYTES", 10 * 1024 * 1024),
        backupCount=_int_env("JARVIS_LOG_BACKUP_COUNT", 5),
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_formatter = JsonFormatter(datefmt=date_format)
    file_handler.setFormatter(file_formatter)
    file_handler.addFilter(SensitiveDataFilter())
    root_logger.addHandler(file_handler)
    
    # Suppress noisy third-party loggers
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)
    logging.getLogger('websockets').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('huggingface_hub').setLevel(logging.ERROR)
    logging.getLogger('faster_whisper').setLevel(logging.WARNING)
    
    root_logger.info(f"Logging initialized. JSON Log file: {LOG_FILE}")
    return root_logger

def get_logger(name):
    """Get a logger instance for a module."""
    return logging.getLogger(name)


def log_telemetry_event(event_type: str, payload: dict | None = None):
    """Write local-only telemetry for operational analysis without leaking secrets."""
    if not _bool_env("JARVIS_TELEMETRY_ENABLED", True):
        return

    event = {
        "timestamp": datetime.now().isoformat(),
        "event_type": event_type,
        "payload": payload or {},
    }
    with TELEMETRY_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False, default=str))
        fh.write("\n")
