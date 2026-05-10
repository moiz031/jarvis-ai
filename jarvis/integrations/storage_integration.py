"""Cloud and local storage integrations used by Jarvis."""

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class CloudStorageIntegration:
    """Base storage integration with safe defaults."""

    def __init__(self):
        self.authenticated = False

    def upload_file(self, local_path: str, remote_path: str = "/"):
        logger.warning("upload_file is not implemented for this provider")
        return "Upload is not supported by this storage provider."

    def download_file(self, remote_path: str, local_path: str):
        logger.warning("download_file is not implemented for this provider")
        return "Download is not supported by this storage provider."

    def list_files(self, folder: str = "/", limit: int = 10):
        logger.warning("list_files is not implemented for this provider")
        return []


class GoogleDriveIntegration(CloudStorageIntegration):
    """Google Drive integration."""

    def __init__(self, credentials_file: str = "jarvis/integrations/credentials.json"):
        super().__init__()
        self.credentials_file = credentials_file
        self.service = None

        try:
            self._authenticate()
        except Exception as e:
            logger.warning(f"Google Drive authentication failed: {e}")

    def _authenticate(self):
        """Authenticate with Google Drive API."""
        import pickle
        from google.auth.transport.requests import Request
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient import discovery

        scopes = ["https://www.googleapis.com/auth/drive.file"]
        creds = None
        token_path = Path("jarvis/integrations/drive_token.pickle")

        if token_path.exists():
            with open(token_path, "rb") as token:
                creds = pickle.load(token)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(self.credentials_file):
                    raise RuntimeError("Google credentials file not found.")
                flow = InstalledAppFlow.from_client_secrets_file(self.credentials_file, scopes)
                creds = flow.run_local_server(port=0)

        token_path.parent.mkdir(parents=True, exist_ok=True)
        with open(token_path, "wb") as token:
            pickle.dump(creds, token)

        self.service = discovery.build("drive", "v3", credentials=creds)
        self.authenticated = True
        logger.info("Google Drive authenticated")

    def upload_file(self, local_path: str, remote_path: str = "/"):
        if not self.authenticated:
            return "Google Drive not authenticated"
        if self.service is None:
            logger.error("Google Drive service is not initialized.")
            return "Google Drive service is not initialized."

        try:
            from googleapiclient.http import MediaFileUpload

            file_metadata = {"name": Path(local_path).name}
            media = MediaFileUpload(local_path)
            uploaded = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields="id",
            ).execute()
            return f"File uploaded successfully (ID: {uploaded.get('id')})"
        except Exception as e:
            logger.error(f"Upload failed: {e}")
            return f"Upload failed: {str(e)}"

    def download_file(self, file_id: str, local_path: str):
        if not self.authenticated:
            return "Google Drive not authenticated"

        try:
            import io
            from googleapiclient.http import MediaIoBaseDownload

            if self.service is None:
                logger.error("Google Drive service is not initialized.")
                return "Google Drive service is not initialized."

            local = Path(local_path)
            local.parent.mkdir(parents=True, exist_ok=True)

            request = self.service.files().get_media(fileId=file_id)
            fh = io.FileIO(str(local), "wb")
            downloader = MediaIoBaseDownload(fh, request)

            done = False
            while not done:
                _, done = downloader.next_chunk()

            return f"File downloaded successfully to {local}"
        except Exception as e:
            logger.error(f"Download failed: {e}")
            return f"Download failed: {str(e)}"

    def list_files(self, folder: str = "/", limit: int = 10):
        if not self.authenticated:
            return []

        try:
            results = self.service.files().list(
                spaces="drive",
                fields="files(id, name, modifiedTime)",
                pageSize=limit,
            ).execute()
            return results.get("files", [])
        except Exception as e:
            logger.error(f"Error listing files: {e}")
            return []


class LocalStorageIntegration(CloudStorageIntegration):
    """Local storage fallback."""

    def __init__(self, base_path: str = "jarvis/data/storage"):
        super().__init__()
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.authenticated = True
        logger.info(f"Local storage initialized: {self.base_path}")

    def upload_file(self, local_path: str, remote_path: str = "/"):
        try:
            import shutil

            source = Path(local_path)
            if not source.exists():
                return f"Local file not found: {source}"

            if remote_path in ("", "/"):
                target_dir = self.base_path
            else:
                target_dir = self.base_path / remote_path.strip("/").strip()
            target_dir.mkdir(parents=True, exist_ok=True)

            dest = target_dir / source.name
            shutil.copy(source, dest)
            return f"File saved to {dest}"
        except Exception as e:
            logger.error(f"Save failed: {e}")
            return f"Save failed: {str(e)}"

    def download_file(self, remote_path: str, local_path: str):
        try:
            import shutil

            src = self.base_path / remote_path.strip("/").strip()
            if not src.exists():
                return f"File not found in storage: {src}"

            dst = Path(local_path)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(src, dst)
            return f"File downloaded successfully to {dst}"
        except Exception as e:
            logger.error(f"Download failed: {e}")
            return f"Download failed: {str(e)}"

    def list_files(self, folder: str = "/", limit: int = 10):
        try:
            if folder in ("", "/"):
                target_dir = self.base_path
            else:
                target_dir = self.base_path / folder.strip("/").strip()
            if not target_dir.exists():
                return []

            files = []
            for i, f in enumerate(target_dir.iterdir()):
                if i >= limit:
                    break
                files.append(
                    {
                        "name": f.name,
                        "size": f.stat().st_size,
                        "modified": f.stat().st_mtime,
                    }
                )
            return files
        except Exception as e:
            logger.error(f"Error listing files: {e}")
            return []
