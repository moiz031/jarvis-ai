
import os
import shutil
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_EXE = os.path.join(BASE_DIR, "dist", "JarvisAI.exe")
RELEASE_DIR = os.path.join(BASE_DIR, "Jarvis_Desktop_App")

if not os.path.exists(DIST_EXE):
    print(f"Error: {DIST_EXE} not found. Build failed?")
    sys.exit(1)

print(f"Creating Release in {RELEASE_DIR}...")

# 1. Create Release Dir
if os.path.exists(RELEASE_DIR):
    shutil.rmtree(RELEASE_DIR)
os.makedirs(RELEASE_DIR)

# 2. Copy Executable
shutil.copy(DIST_EXE, RELEASE_DIR)

# 3. Create Data Structure
os.makedirs(os.path.join(RELEASE_DIR, "data"), exist_ok=True)
os.makedirs(os.path.join(RELEASE_DIR, "logs"), exist_ok=True)

# 4. Copy .env if exists (Check root and jarvis/.env)
env_src = os.path.join(BASE_DIR, ".env")
if not os.path.exists(env_src):
    env_src = os.path.join(BASE_DIR, "jarvis", ".env")

if os.path.exists(env_src):
    shutil.copy(env_src, os.path.join(RELEASE_DIR, ".env"))
    print("Copied .env configuration.")
else:
    print("Warning: .env not found. Please create one in the Release folder.")

print(f"Success! Jarvis Desktop App is ready in '{RELEASE_DIR}'")
