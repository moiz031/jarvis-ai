import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


def wait_for_health(url: str, timeout: int) -> dict | None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urlopen(url, timeout=3) as response:  # nosec B310 - local health probe
                payload = response.read().decode("utf-8", errors="replace")
                return {"status": response.status, "body": payload}
        except URLError:
            time.sleep(1)
        except Exception:
            time.sleep(1)
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Jarvis backend executable health endpoint.")
    parser.add_argument(
        "--exe",
        default=str(Path("backend") / "JarvisBackend.exe"),
        help="Path to the backend executable to launch.",
    )
    parser.add_argument("--url", default="http://127.0.0.1:8080/health", help="Health endpoint URL.")
    parser.add_argument("--timeout", type=int, default=45, help="Seconds to wait for backend health.")
    args = parser.parse_args()

    exe_path = Path(args.exe).resolve()
    if not exe_path.exists():
        print(f"Backend executable not found: {exe_path}")
        return 1

    proc = subprocess.Popen([str(exe_path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        health = wait_for_health(args.url, args.timeout)
        if not health:
            print("Backend health check timed out.")
            return 1
        print(json.dumps(health, ensure_ascii=False))
        return 0 if health["status"] == 200 else 1
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
