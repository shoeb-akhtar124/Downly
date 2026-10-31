"""
Download Scheduler Manager.
Allows users to schedule media downloads for a future date and time.
Stores scheduled tasks persistently in local JSON storage, restores them on startup,
and triggers tasks using a lightweight QTimer.
"""
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from PySide6.QtCore import QObject, QTimer, Signal

from app.constants import SCHEDULES_FILE, USER_STORAGE_DIR
from app.logger import log_info, log_error, log_warning
from core.download_manager import download_manager
from core.download_destination import destination_manager


class SchedulerManager(QObject):
    """Manages persistent scheduled downloads and timer execution."""

    schedule_added = Signal(dict)
    schedule_updated = Signal(dict)
    schedule_removed = Signal(str)
    schedule_triggered = Signal(dict)

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(SchedulerManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        super().__init__()
        self._initialized = True
        self.schedules: List[Dict[str, Any]] = []

        self._ensure_storage()
        self.load_schedules()

        # Check every 15 seconds
        self._timer = QTimer(self)
        self._timer.setInterval(15000)
        self._timer.timeout.connect(self._check_pending_schedules)
        self._timer.start()

    def _ensure_storage(self) -> None:
        """Ensure storage directory exists."""
        USER_STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    def load_schedules(self) -> List[Dict[str, Any]]:
        """Load schedules from persistent JSON file."""
        if SCHEDULES_FILE.exists():
            try:
                with open(SCHEDULES_FILE, "r", encoding="utf-8") as f:
                    self.schedules = json.load(f)
                    log_info(f"Loaded {len(self.schedules)} scheduled task(s) from storage.")
                    return self.schedules
            except Exception as e:
                log_error(f"Failed to load schedules.json: {e}")
                self.schedules = []
        else:
            self.schedules = []
            self.save_schedules()
        return self.schedules

    def save_schedules(self) -> bool:
        """Save schedules to persistent JSON file."""
        try:
            with open(SCHEDULES_FILE, "w", encoding="utf-8") as f:
                json.dump(self.schedules, f, indent=4)
            return True
        except Exception as e:
            log_error(f"Failed to save schedules.json: {e}")
            return False

    def add_schedule(
        self,
        url: str,
        title: str,
        scheduled_time: datetime,
        quality: str = "1080p (Full HD)",
        output_format: str = "MP4",
        codec: str = "Keep Original Codec",
        audio_codec: str = "Keep Original",
        download_dir: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create and persist a new scheduled download."""
        sched_id = str(uuid.uuid4())
        item = {
            "id": sched_id,
            "url": url,
            "title": title or url,
            "scheduled_time": scheduled_time.isoformat(),
            "scheduled_time_display": scheduled_time.strftime("%Y-%m-%d %H:%M"),
            "quality": quality,
            "output_format": output_format,
            "codec": codec,
            "audio_codec": audio_codec,
            "download_dir": download_dir or str(destination_manager.get_destination()),
            "status": "pending",  # "pending", "completed", "cancelled", "missed"
            "created_at": datetime.now().isoformat()
        }
        self.schedules.append(item)
        self.save_schedules()
        log_info(f"Scheduled download added: '{title}' for {item['scheduled_time_display']}")
        self.schedule_added.emit(item)
        return item

    def cancel_schedule(self, sched_id: str) -> bool:
        """Cancel a pending scheduled task."""
        for item in self.schedules:
            if item["id"] == sched_id:
                item["status"] = "cancelled"
                self.save_schedules()
                self.schedule_updated.emit(item)
                return True
        return False

    def remove_schedule(self, sched_id: str) -> bool:
        """Permanently remove a scheduled task."""
        initial_len = len(self.schedules)
        self.schedules = [s for s in self.schedules if s["id"] != sched_id]
        if len(self.schedules) < initial_len:
            self.save_schedules()
            self.schedule_removed.emit(sched_id)
            return True
        return False

    def get_pending_schedules(self) -> List[Dict[str, Any]]:
        """Return all tasks still awaiting execution."""
        return [s for s in self.schedules if s.get("status") == "pending"]

    def _check_pending_schedules(self) -> None:
        """Check if any pending schedule is due for download."""
        now = datetime.now()
        updated = False

        for item in self.schedules:
            if item.get("status") != "pending":
                continue

            try:
                sched_dt = datetime.fromisoformat(item["scheduled_time"])
            except Exception:
                continue

            if now >= sched_dt:
                # If overdue by more than 48 hours, mark as missed safely
                diff_hours = (now - sched_dt).total_seconds() / 3600
                if diff_hours > 48:
                    item["status"] = "missed"
                    updated = True
                    log_warning(f"Scheduled task '{item['title']}' was missed (>48h overdue).")
                    continue

                # Trigger download!
                item["status"] = "completed"
                updated = True
                log_info(f"Executing scheduled download for '{item['title']}' ({item['url']})")

                download_manager.add_download(
                    url=item["url"],
                    title=item["title"],
                    quality=item.get("quality", "1080p (Full HD)"),
                    output_format=item.get("output_format", "MP4"),
                    codec=item.get("codec", "Keep Original Codec"),
                    download_dir=item.get("download_dir") or None,
                    audio_codec=item.get("audio_codec", "Keep Original")
                )
                self.schedule_triggered.emit(item)

        if updated:
            self.save_schedules()


# Global scheduler manager singleton
scheduler_manager = SchedulerManager()

