import json
import sys
from pathlib import Path


def _capture_camera(out_path: str, camera_index: int = 0) -> dict:
    import cv2

    target = Path(out_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        return {"ok": False, "error": "camera_unavailable"}
    ok, frame = cap.read()
    cap.release()
    if not ok:
        return {"ok": False, "error": "frame_capture_failed"}
    cv2.imwrite(str(target), frame)
    return {"ok": True, "path": str(target)}


def _extract_video_frame(video_path: str, out_path: str) -> dict:
    import cv2

    source = Path(video_path)
    target = Path(out_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(source))
    ok, frame = cap.read()
    cap.release()
    if not ok:
        return {"ok": False, "error": "video_frame_read_failed"}
    cv2.imwrite(str(target), frame)
    return {"ok": True, "path": str(target)}


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(json.dumps({"ok": False, "error": "invalid_args"}))
        return 1

    command = argv[1]
    try:
        if command == "capture_camera":
            camera_index = int(argv[3]) if len(argv) > 3 else 0
            payload = _capture_camera(argv[2], camera_index)
        elif command == "extract_video_frame":
            if len(argv) < 4:
                payload = {"ok": False, "error": "missing_video_args"}
            else:
                payload = _extract_video_frame(argv[2], argv[3])
        else:
            payload = {"ok": False, "error": f"unknown_command:{command}"}
    except Exception as exc:
        payload = {"ok": False, "error": str(exc)}

    print(json.dumps(payload))
    return 0 if payload.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
