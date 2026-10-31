"""
History Manager Module.
Maintains persistent local download history in user data storage.
Outside installation folder so application updates never delete or reset history.
"""
import json
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from app.constants import HISTORY_FILE, USER_STORAGE_DIR, LEGACY_HISTORY_FILE


class HistoryManager:
    """Manages persistent local JSON download history."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(HistoryManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self._history: List[Dict[str, Any]] = []
        self._ensure_storage()
        self.load()

    def _ensure_storage(self) -> None:
        """Ensure persistent user data directory exists and migrate legacy records."""
        USER_STORAGE_DIR.mkdir(parents=True, exist_ok=True)

        # Automatic migration from legacy project storage directory if present
        if not HISTORY_FILE.exists() and LEGACY_HISTORY_FILE.exists():
            try:
                shutil.copy2(LEGACY_HISTORY_FILE, HISTORY_FILE)
                print(f"[HistoryManager] Migrated existing history to {HISTORY_FILE}")
            except OSError as e:
                print(f"[HistoryManager] Migration notice: {e}")

    def load(self) -> List[Dict[str, Any]]:
        """Load history records from persistent history.json."""
        if HISTORY_FILE.exists():
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self._history = data
                        return self._history
            except (json.JSONDecodeError, OSError) as e:
                print(f"[HistoryManager] Error reading history.json: {e}")
        self._history = []
        self.save()
        return self._history

    def save(self) -> bool:
        """Persist history list to history.json."""
        try:
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(self._history, f, indent=4)
            return True
        except OSError as e:
            print(f"[HistoryManager] Failed to save history: {e}")
            return False

    def get_all(self) -> List[Dict[str, Any]]:
        """Return a copy of all history records."""
        return list(self._history)

    def add_entry(
        self,
        file_name: str,
        file_location: str,
        website: str,
        resolution: str,
        codec: str,
        file_size: str,
        download_date: Optional[str] = None,
        entry_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Record a completed download entry."""
        if not download_date:
            download_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        record = {
            "id": entry_id or str(uuid.uuid4()),
            "file_name": file_name,
            "file_location": str(file_location),
            "website": website,
            "resolution": resolution,
            "codec": codec,
            "file_size": file_size,
            "download_date": download_date
        }
        self._history.insert(0, record)
        self.save()
        return record

    def remove_entry(self, entry_id: str) -> bool:
        """Remove a record by its unique ID or file_location."""
        initial_len = len(self._history)
        self._history = [
            item for item in self._history
            if item.get("id") != entry_id and item.get("file_location") != entry_id
        ]
        if len(self._history) != initial_len:
            self.save()
            return True
        return False

    def clear(self) -> None:
        """Clear all history records."""
        self._history.clear()
        self.save()


# Singleton instance
history_manager = HistoryManager()
