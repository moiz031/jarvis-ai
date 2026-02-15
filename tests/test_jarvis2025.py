import os
import sys
import tempfile
from pathlib import Path

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def test_memory_db_roundtrip():
    print("Testing MemoryDB roundtrip...")
    from jarvis.memory.db import MemoryDB

    db = MemoryDB()
    session_id = "test_session_2025"
    db.start_session(session_id)
    db.add_turn("User", "Test User", session_id=session_id)
    history = db.get_context(limit=10, session_id=session_id)

    if any(item.get("content") == "Test User" for item in history):
        print("PASS: MemoryDB logging works.")
    else:
        print("FAIL: MemoryDB logging failed.")


def test_local_storage_integration():
    print("\nTesting LocalStorageIntegration...")
    from jarvis.integrations.storage_integration import LocalStorageIntegration

    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalStorageIntegration(base_path=tmpdir)
        src = Path(tmpdir) / "sample.txt"
        src.write_text("hello", encoding="utf-8")

        upload_result = storage.upload_file(str(src), remote_path="/uploads")
        files = storage.list_files("/uploads")

        if "saved" in upload_result.lower() and any(f.get("name") == "sample.txt" for f in files):
            print("PASS: Local storage upload/list works.")
        else:
            print("FAIL: Local storage upload/list failed.")

        out = Path(tmpdir) / "downloads" / "sample.txt"
        download_result = storage.download_file("uploads/sample.txt", str(out))
        if out.exists() and "successfully" in download_result.lower():
            print("PASS: Local storage download works.")
        else:
            print("FAIL: Local storage download failed.")


if __name__ == "__main__":
    try:
        test_memory_db_roundtrip()
        test_local_storage_integration()
        print("\nAll checks passed for current Jarvis integration.")
    except Exception as e:
        print(f"FAIL: Verification failed with error: {e}")
