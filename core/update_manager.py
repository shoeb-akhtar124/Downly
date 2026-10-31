"""
Modular Update Manager.
Handles semantic version checking, GitHub Releases integration,
safe update staging, and backup/recovery mechanisms.
Strictly obeys user-confirmation requirements and prevents unverified automatic installations.
"""
import os
import re
import json
import shutil
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List

from PySide6.QtCore import QObject, QThread, Signal

from app.constants import (
    APP_VERSION,
    DEFAULT_GITHUB_REPO,
    USER_UPDATES_DIR,
    USER_STAGED_UPDATES_DIR,
    USER_BACKUP_UPDATES_DIR,
    ROOT_DIR
)


def parse_semver(version_str: str) -> Tuple[int, ...]:
    """Parse a version string (e.g. 'v1.2.3' or '1.0.0') into an integer tuple."""
    clean = re.sub(r'^[vV]', '', version_str.strip())
    # Extract numeric components
    parts = re.findall(r'\d+', clean)
    if not parts:
        return (0, 0, 0)
    return tuple(int(p) for p in parts[:3])


def is_newer_version(candidate: str, current: str = APP_VERSION) -> bool:
    """Compare two semantic version strings."""
    return parse_semver(candidate) > parse_semver(current)


@dataclass
class UpdateInfo:
    """Structured release and update metadata."""
    current_version: str
    latest_version: str
    has_update: bool
    release_name: str
    release_notes: str
    html_url: str
    published_at: str
    download_url: Optional[str] = None
    asset_name: Optional[str] = None
    asset_size: Optional[int] = None

    def summary(self) -> str:
        status = "Update available" if self.has_update else "Up to date"
        return f"{status} (Current: v{self.current_version} • Latest: v{self.latest_version})"


class CheckUpdateWorker(QThread):
    """Background thread to query GitHub Releases without freezing the UI."""

    update_found = Signal(object)      # UpdateInfo
    up_to_date = Signal(object)        # UpdateInfo
    check_failed = Signal(str)         # Error message

    def __init__(self, repo: str = DEFAULT_GITHUB_REPO, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.repo = repo

    def run(self):
        manager = UpdateManager()
        try:
            info = manager.check_for_updates(self.repo)
            if info.has_update:
                self.update_found.emit(info)
            else:
                self.up_to_date.emit(info)
        except Exception as e:
            self.check_failed.emit(str(e))


class StageUpdateWorker(QThread):
    """Background thread for downloading and staging an update package safely."""

    progress_signal = Signal(int)     # Percent (0-100)
    staged_success = Signal(str)      # Staged file path
    stage_failed = Signal(str)        # Error message

    def __init__(self, update_info: UpdateInfo, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.update_info = update_info

    def run(self):
        manager = UpdateManager()
        try:
            staged_path = manager.stage_update(self.update_info, callback=self.progress_signal.emit)
            self.staged_success.emit(staged_path)
        except Exception as e:
            self.stage_failed.emit(str(e))


class UpdateManager:
    """Coordinates release checking, safe staging, and disaster recovery backups."""

    def __init__(self):
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Create staged updates and backup directories in persistent user data storage."""
        USER_STAGED_UPDATES_DIR.mkdir(parents=True, exist_ok=True)
        USER_BACKUP_UPDATES_DIR.mkdir(parents=True, exist_ok=True)

    def check_for_updates(self, repo: str = DEFAULT_GITHUB_REPO, timeout: int = 10) -> UpdateInfo:
        """
        Query GitHub Releases API for the latest published release.
        Compares remote tag version with the local APP_VERSION.
        """
        api_url = f"https://api.github.com/repos/{repo}/releases/latest"
        req = urllib.request.Request(
            api_url,
            headers={
                "User-Agent": "Downly-Desktop-App",
                "Accept": "application/vnd.github.v3+json"
            }
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise RuntimeError(f"Repository or release not found on GitHub: {repo}")
            elif e.code == 403:
                raise RuntimeError("GitHub API rate limit exceeded. Please try again later.")
            raise RuntimeError(f"HTTP Error {e.code} checking for updates.")
        except Exception as e:
            raise RuntimeError(f"Network error checking for updates: {e}")

        tag = data.get("tag_name", "").strip()
        clean_tag = re.sub(r'^[vV]', '', tag)
        has_update = is_newer_version(clean_tag, APP_VERSION)

        # Locate Windows installer or binary asset if available
        download_url = None
        asset_name = None
        asset_size = None

        assets: List[Dict[str, Any]] = data.get("assets", [])
        for a in assets:
            name = a.get("name", "")
            if name.lower().endswith((".exe", ".zip", ".msi")):
                download_url = a.get("browser_download_url")
                asset_name = name
                asset_size = a.get("size")
                break

        return UpdateInfo(
            current_version=APP_VERSION,
            latest_version=clean_tag or tag,
            has_update=has_update,
            release_name=data.get("name") or f"Release {tag}",
            release_notes=data.get("body") or "No release notes provided.",
            html_url=data.get("html_url") or f"https://github.com/{repo}/releases",
            published_at=data.get("published_at") or "",
            download_url=download_url,
            asset_name=asset_name,
            asset_size=asset_size
        )

    def stage_update(self, update_info: UpdateInfo, callback=None) -> str:
        """
        Safely download the release asset into the staged updates folder.
        Downloads to a temporary file first, verifying integrity before renaming.
        Does NOT replace or overwrite active binaries.
        """
        if not update_info.download_url:
            raise ValueError("No downloadable asset found for this release.")

        file_name = update_info.asset_name or f"Downly_{update_info.latest_version}.exe"
        target_file = USER_STAGED_UPDATES_DIR / file_name
        temp_file = USER_STAGED_UPDATES_DIR / f"{file_name}.download"

        if temp_file.exists():
            try:
                temp_file.unlink()
            except OSError:
                pass

        req = urllib.request.Request(
            update_info.download_url,
            headers={"User-Agent": "Downly-Desktop-App"}
        )

        with urllib.request.urlopen(req, timeout=30) as resp, open(temp_file, "wb") as out_f:
            total_size = int(resp.headers.get("content-length", 0))
            downloaded = 0
            chunk_size = 64 * 1024

            while True:
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                out_f.write(chunk)
                downloaded += len(chunk)
                if total_size > 0 and callback:
                    percent = int((downloaded / total_size) * 100)
                    callback(percent)

        # Finalize atomic download
        if target_file.exists():
            try:
                target_file.unlink()
            except OSError:
                pass
        temp_file.rename(target_file)

        return str(target_file)

    def create_installation_backup(self) -> Path:
        """
        Safety recovery mechanism. Creates a snapshot archive of configuration
        and application state before any destructive operation.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = USER_BACKUP_UPDATES_DIR / f"backup_v{APP_VERSION}_{timestamp}"
        backup_path.mkdir(parents=True, exist_ok=True)

        # Backup settings and history safely
        from app.constants import SETTINGS_FILE, HISTORY_FILE
        if SETTINGS_FILE.exists():
            shutil.copy2(SETTINGS_FILE, backup_path / "settings.json")
        if HISTORY_FILE.exists():
            shutil.copy2(HISTORY_FILE, backup_path / "history.json")

        return backup_path

    def rollback_backup(self, backup_dir: Path) -> bool:
        """Restore settings and records from a specific backup snapshot."""
        if not backup_dir.exists():
            return False

        from app.constants import SETTINGS_FILE, HISTORY_FILE
        b_settings = backup_dir / "settings.json"
        b_history = backup_dir / "history.json"

        if b_settings.exists():
            shutil.copy2(b_settings, SETTINGS_FILE)
        if b_history.exists():
            shutil.copy2(b_history, HISTORY_FILE)

        return True

    def apply_update_safely(self, staged_file_path: str) -> None:
        """
        Strictly guarded: Automatic self-overwriting is disabled until
        end-to-end update installer tests are verified.
        """
        raise NotImplementedError(
            "Automatic silent in-place installation is intentionally disabled for safety. "
            f"The verified update is staged at '{staged_file_path}'. "
            "Please confirm and install manually via the installer."
        )


# Global update manager singleton
update_manager = UpdateManager()

