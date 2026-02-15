# jarvis/tools/coach_rules.py
import re

ERROR_PATTERNS = [
    (re.compile(r"Traceback \(most recent call last\):", re.I), "python_traceback"),
    (re.compile(r"ModuleNotFoundError:", re.I), "python_module_missing"),
    (re.compile(r"ImportError:", re.I), "python_import_error"),
    (re.compile(r"SyntaxError:", re.I), "python_syntax_error"),
    (re.compile(r"PermissionError:", re.I), "permission_error"),
    (re.compile(r"CommandNotFound", re.I), "command_not_found"),
]

def detect_issue(screen_text: str) -> dict | None:
    t = (screen_text or "").strip()
    if not t:
        return None
    for rx, tag in ERROR_PATTERNS:
        if rx.search(t):
            return {"tag": tag, "evidence": rx.pattern}
    return None        
