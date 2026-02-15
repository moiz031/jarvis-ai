# tools/commands.py

import subprocess
import shlex

# Strict allowlist of commands
ALLOWED_COMMANDS = {
    "ping": ["ping", "-n", "4"], # Default to 4 pings
    "dir": ["cmd", "/c", "dir"],
    "ipconfig": ["ipconfig"],
    "echo": ["cmd", "/c", "echo"],
    "mkdir": ["cmd", "/c", "mkdir"],
    "type": ["cmd", "/c", "type"],
    "whoami": ["whoami"],
    "date": ["cmd", "/c", "date", "/t"],
    "time": ["cmd", "/c", "time", "/t"],
}

def run_command(command_str: str) -> str:
    """Run a system command if it is in the allowlist."""
    parts = shlex.split(command_str)
    if not parts:
        return "Empty command."
    
    base_cmd = parts[0].lower()
    
    if base_cmd not in ALLOWED_COMMANDS:
        return f"Command '{base_cmd}' is not allowed for safety reasons."
        
    # Construct the actual command to run
    # For some like 'ping', we might want to allow arguments but sanitizing is hard.
    # For safety, we'll only allow appending arguments for specific commands, or valid flags.
    # Simple approach: If it's a known safe binary (ping, ipconfig), we allow limited args.
    # If it's a shell built-in (dir, echo), we construct it carefully.
    
    full_cmd = []
    
    if base_cmd in ["ping", "ipconfig", "whoami"]:
         full_cmd = [base_cmd] + parts[1:]
    elif base_cmd in ["dir", "mkdir", "echo", "type", "date", "time"]:
        # Use cmd /c for shell built-ins
        # security risk with chaining like "echo hello && del *"
        # basic sanitization: check for dangerous characters
        if any(c in command_str for c in ["&", "|", ">", "<", ";"]):
             return "Command contains blocked characters (&, |, >, <, ;)."
        full_cmd = ["cmd", "/c"] + parts
    
    try:
        # Capture output
        result = subprocess.run(full_cmd, capture_output=True, text=True, check=False)
        output = result.stdout.strip()
        if result.stderr:
            output += f"\nError: {result.stderr.strip()}"
        return output
    except Exception as e:
        return f"Failed to run command: {e}"
