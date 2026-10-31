"""
Clipboard Monitor Service.
Monitors system clipboard for supported video URLs when enabled in preferences.
Strictly non-intrusive: never stores clipboard history, never starts downloads automatically,
and ignores all non-media clipboard content.
"""
from typing import Optional
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

from app.config import config
from app.logger import log_info
from core.url_analyzer import URLAnalyzer


class ClipboardMonitor(QObject):
    """Watches the system clipboard for valid video URLs and emits notification signals."""

    supported_url_detected = Signal(str, str)  # (url, platform)

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(ClipboardMonitor, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        super().__init__()
        self._initialized = True
        self._last_detected_url: str = ""
        self._is_monitoring: bool = False

    def start(self) -> None:
        """Start listening to clipboard dataChanged signal."""
        app = QApplication.instance()
        if not app:
            return

        clipboard = app.clipboard()
        if not self._is_monitoring:
            clipboard.dataChanged.connect(self._on_clipboard_changed)
            self._is_monitoring = True
            log_info("Clipboard monitoring service started.")

    def stop(self) -> None:
        """Stop listening to clipboard events."""
        app = QApplication.instance()
        if not app or not self._is_monitoring:
            return

        try:
            clipboard = app.clipboard()
            clipboard.dataChanged.disconnect(self._on_clipboard_changed)
        except Exception:
            pass
        self._is_monitoring = False
        log_info("Clipboard monitoring service stopped.")

    def update_state(self) -> None:
        """Sync monitoring state with configuration."""
        enabled = config.get("clipboard_monitoring", False)
        if enabled and not self._is_monitoring:
            self.start()
        elif not enabled and self._is_monitoring:
            self.stop()

    def _on_clipboard_changed(self) -> None:
        """Examine clipboard content safely when changed."""
        if not config.get("clipboard_monitoring", False):
            return

        app = QApplication.instance()
        if not app:
            return

        try:
            text = app.clipboard().text()
        except Exception:
            return

        if not text or not isinstance(text, str):
            return

        text = text.strip()
        # Fast sanity check: length and protocol
        if len(text) < 10 or len(text) > 800 or not (text.startswith("http://") or text.startswith("https://")):
            return

        # Avoid repeated popups for identical URL
        if text == self._last_detected_url:
            return

        # Validate URL
        clean_url = URLAnalyzer.normalize_url(text)
        if not URLAnalyzer.is_valid_url(clean_url):
            return

        platform = URLAnalyzer.detect_platform(clean_url)
        self._last_detected_url = clean_url
        log_info(f"Clipboard video link detected: {platform} ({clean_url})")
        self.supported_url_detected.emit(clean_url, platform)


# Global clipboard monitor singleton
clipboard_monitor = ClipboardMonitor()

