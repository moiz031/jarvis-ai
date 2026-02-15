import os
import requests
from pathlib import Path

def download_model(model_name, onnx_url, json_url, dest_dir):
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    onnx_path = dest_dir / f"{model_name}.onnx"
    json_path = dest_dir / f"{model_name}.onnx.json"
    
    print(f"Downloading {model_name}...")
    
    if not onnx_path.exists():
        print(f"  Fetching ONNX model...")
        r = requests.get(onnx_url, stream=True)
        with open(onnx_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
    else:
        print("  ONNX model already exists.")

    if not json_path.exists():
        print(f"  Fetching JSON config...")
        r = requests.get(json_url, stream=True)
        with open(json_path, 'wb') as f:
            f.write(r.content)
    else:
        print("  JSON config already exists.")
        
    print(f"Finished {model_name}.")

if __name__ == "__main__":
    # English Model
    download_model(
        "en_US-lessac-medium",
        "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx",
        "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json",
        "jarvis/models"
    )
    
    # Urdu Model (Example URL - verifying validity first would be good but using what was in code)
    # The URL in tts_local.py was: https://huggingface.co/rhasspy/piper-voices/resolve/main/ur/ur_PK/dune/medium/ur_PK-dune-medium.onnx
    download_model(
        "ur_PK-dune-medium",
        "https://huggingface.co/rhasspy/piper-voices/resolve/main/ur/ur_PK/dune/medium/ur_PK-dune-medium.onnx",
        "https://huggingface.co/rhasspy/piper-voices/resolve/main/ur/ur_PK/dune/medium/ur_PK-dune-medium.onnx.json",
        "jarvis/models"
    )
    print("All models downloaded.")
