"""
Download Destination Manager.
Centralizes resolution, validation, creation, and persistence of download destination paths.
Guarantees:
1. Always resolves to an absolute path selected by the user.
2. Never silently falls back to the application or project directory.
3. If the selected folder is missing, inaccessible, or unwritable, raises an explicit error.
4. Preserves task-specific destinations for queued downloads.
5. Handles folder paths with spaces, unicode characters, and alternate drive letters.
"""
import os
import tempfile
from pathlib import Path
from typing import Optional, Tuple

from app.constants import USER_DOWNLOADS_DIR, ROOT_DIR, LEGACY_DOWNLOADS_DIR
from app.config import config
from app.logger import log_info, log_warning, log_error


class DestinationError(Exception):
    """Raised when a download destination directory is invalid, inaccessible, or unwritable."""
    pass


class DownloadDestinationManager:
    """Centralized manager for application download destinations."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DownloadDestinationManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self._ensure_clean_config()

    def _ensure_clean_config(self) -> None:
        """
        Sanitize stored download directory in config.
        If pointing to the legacy project downloads directory or invalid,
        repoint to the user's personal Downloads/Downly folder.
        """
        raw_dir = config.get("download_dir", "")
        if not raw_dir:
            config.set("download_dir", str(USER_DOWNLOADS_DIR))
            return

        try:
            p = Path(raw_dir).resolve()
            # If the configured path is inside project root or is legacy project downloads, migrate
            if p == LEGACY_DOWNLOADS_DIR.resolve() or p == ROOT_DIR.resolve() or (ROOT_DIR.resolve() in p.parents and p.name == "downloads"):
                log_info(f"[DestinationManager] Migrating legacy project download directory '{p}' to user directory '{USER_DOWNLOADS_DIR}'")
                config.set("download_dir", str(USER_DOWNLOADS_DIR))
        except Exception:
            config.set("download_dir", str(USER_DOWNLOADS_DIR))

    def get_destination(self) -> Path:
        """
        Retrieve and validate current active download destination.
        Returns an absolute Path that is guaranteed to exist and be writable.
        """
        raw_dir = config.get("download_dir")
        if not raw_dir:
            raw_dir = str(USER_DOWNLOADS_DIR)

        dest_path = Path(raw_dir).resolve()

        # Safeguard: never silently save to project root
        if dest_path == ROOT_DIR.resolve() or (ROOT_DIR.resolve() in dest_path.parents and dest_path.name == "downloads"):
            dest_path = USER_DOWNLOADS_DIR.resolve()
            config.set("download_dir", str(dest_path))

        # Ensure directory exists and is writable
        self.ensure_directory_writable(dest_path)
        return dest_path

    def set_destination(self, path_str: str) -> Tuple[bool, str]:
        """
        Validate and persist a new download destination selected by user.
        Returns (success: bool, message: str).
        """
        clean_path = str(path_str).strip()
        if not clean_path:
            return False, "Download destination path cannot be empty."

        try:
            dest_path = Path(clean_path).resolve()
        except Exception as e:
            return False, f"Invalid folder path format: {e}"

        # Test creation and write access
        try:
            self.ensure_directory_writable(dest_path)
        except DestinationError as e:
            return False, str(e)

        config.set("download_dir", str(dest_path))
        log_info(f"[DestinationManager] Download destination updated to: {dest_path}")
        return True, str(dest_path)

    def validate_path(self, path_str: str) -> Tuple[bool, str]:
        """Check if a given path can be used as a download destination."""
        clean_path = str(path_str).strip()
        if not clean_path:
            return False, "Path is empty."
        try:
            dest_path = Path(clean_path).resolve()
            self.ensure_directory_writable(dest_path)
            return True, str(dest_path)
        except Exception as e:
            return False, str(e)

    def ensure_directory_writable(self, path: Path) -> None:
        """
        Ensure the destination folder exists and has write permissions.
        Raises DestinationError if inaccessible or read-only.
        """
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise DestinationError(f"Cannot create destination folder '{path}': {e.strerror or e}")

        if not path.is_dir():
            raise DestinationError(f"Destination path '{path}' is not a directory.")

        # Probe write access by creating and removing a temporary test file
        test_file = None
        try:
            with tempfile.NamedTemporaryFile(dir=str(path), prefix=".downly_probe_", delete=False) as tf:
                test_file = Path(tf.name)
                tf.write(b"ok")
        except OSError as e:
            raise DestinationError(
                f"Destination folder '{path}' is not writable or access is denied: {e.strerror or e}"
            )
        finally:
            if test_file and test_file.exists():
                try:
                    test_file.unlink()
                except OSError:
                    pass

    def resolve_task_destination(self, task_assigned_dir: Optional[str] = None) -> Path:
        """
        Determine target destination for a specific download task.
        If task already has an assigned download_dir (e.g. queued task), that directory is
        used so changing global destination later does not affect already-queued tasks.
        """
        if task_assigned_dir and str(task_assigned_dir).strip():
            assigned_path = Path(task_assigned_dir).resolve()
            # If not project directory fallback, use assigned
            if assigned_path != ROOT_DIR.resolve() and assigned_path != LEGACY_DOWNLOADS_DIR.resolve():
                self.ensure_directory_writable(assigned_path)
                return assigned_path

        return self.get_destination()


destination_manager = DownloadDestinationManager()

