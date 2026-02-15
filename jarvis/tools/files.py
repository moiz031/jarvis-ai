# tools/files.py

import os
from pathlib import Path

# Allow access only to specific roots
ALLOWED_ROOTS = [
    Path(os.environ["USERPROFILE"]) / "Desktop",
    Path(os.environ["USERPROFILE"]) / "Documents",
    Path(os.environ["USERPROFILE"]) / "Downloads",
]

def _is_safe_path(path_str):
    try:
        p = Path(path_str).resolve()
        for root in ALLOWED_ROOTS:
            if root in p.parents or root == p:
                return True
        return False
    except:
        return False

def list_dir(path: str) -> list:
    if not _is_safe_path(path):
        return ["Error: Access denied to this path."]
    
    try:
        if not os.path.exists(path):
            return ["Error: Path does not exist."]
        items = os.listdir(path)
        return items[:50]  # limit output
    except Exception as e:
        return [f"Error: {e}"]

def read_file(path: str) -> str:
    if not _is_safe_path(path):
        return "Error: Access denied."
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {e}"

def write_file(path: str, content: str) -> str:
    if not _is_safe_path(path):
        return "Error: Access denied."
    # Note: Overwrite confirmation is handled by the Agent's logic gate
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return "File written successfully."
    except Exception as e:
        return f"Error writing file: {e}"

def search_files(query: str, root_str: str = None) -> list:
    root = Path(root_str) if root_str else ALLOWED_ROOTS[0] # Default to Desktop
    if not _is_safe_path(str(root)):
        return ["Error: Access denied to root."]
    
    matches = []
    try:
        for path in root.rglob(f"*{query}*"):
            matches.append(str(path.name))
            if len(matches) >= 10: break
    except Exception as e:
        return [f"Error searching: {e}"]
    return matches
