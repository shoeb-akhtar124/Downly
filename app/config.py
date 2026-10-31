"""
Local settings manager using JSON storage.
All configurations are stored locally in the persistent user data directory
outside the application installation directory.
"""
import json
import os
import shutil
from pathlib import Path
from typing import Any, Dict

from app.constants import (
    DEFAULT_SETTINGS,
    USER_DOWNLOADS_DIR,
    SETTINGS_FILE,
    USER_STORAGE_DIR,
    USER_LOGS_DIR,
    THUMBNAILS_CACHE_DIR,
    LEGACY_SETTINGS_FILE,
    ROOT_DIR,
    LEGACY_DOWNLOADS_DIR
)


class ConfigManager:
    """Manages application settings stored in the persistent local JSON file."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self._settings: Dict[str, Any] = {}
        self._ensure_directories()
        self.load()

    def _ensure_directories(self) -> None:
        """Create persistent user storage and default download directories."""
        USER_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        USER_LOGS_DIR.mkdir(parents=True, exist_ok=True)
        THUMBNAILS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        try:
            USER_DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass

        # Automatic migration from legacy project storage directory if present
        if not SETTINGS_FILE.exists() and LEGACY_SETTINGS_FILE.exists():
            try:
                shutil.copy2(LEGACY_SETTINGS_FILE, SETTINGS_FILE)
                print(f"[ConfigManager] Migrated existing settings to {SETTINGS_FILE}")
            except OSError as e:
                print(f"[ConfigManager] Migration notice: {e}")

    def load(self) -> Dict[str, Any]:
        """Load settings from persistent JSON file or create with defaults."""
        if SETTINGS_FILE.exists():
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._settings = {**DEFAULT_SETTINGS, **data}
                    
                    # Prevent project directory from ever being used as download destination
                    raw_dir = self._settings.get("download_dir", "")
                    if raw_dir:
                        try:
                            p = Path(raw_dir).resolve()
                            if p == ROOT_DIR.resolve() or p == LEGACY_DOWNLOADS_DIR.resolve() or (ROOT_DIR.resolve() in p.parents and p.name == "downloads"):
                                self._settings["download_dir"] = str(USER_DOWNLOADS_DIR)
                                self.save()
                        except Exception:
                            self._settings["download_dir"] = str(USER_DOWNLOADS_DIR)
                    else:
                        self._settings["download_dir"] = str(USER_DOWNLOADS_DIR)

                    return self._settings
            except (json.JSONDecodeError, OSError) as e:
                print(f"[ConfigManager] Error reading settings.json: {e}. Reverting to defaults.")

        self._settings = dict(DEFAULT_SETTINGS)
        self.save()
        return self._settings

    def save(self) -> bool:
        """Persist current settings to settings.json."""
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(self._settings, f, indent=4)
            return True
        except OSError as e:
            print(f"[ConfigManager] Failed to save settings: {e}")
            return False

    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting by key."""
        return self._settings.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a setting and automatically persist it."""
        self._settings[key] = value
        self.save()

    def get_all(self) -> Dict[str, Any]:
        """Return a copy of all settings."""
        return dict(self._settings)

    def reset_to_defaults(self) -> None:
        """Reset all configurations to factory defaults."""
        self._settings = dict(DEFAULT_SETTINGS)
        self.save()


# Global singleton helper
config = ConfigManager()
