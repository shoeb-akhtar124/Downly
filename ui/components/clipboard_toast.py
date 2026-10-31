"""
Clipboard Toast Banner Component.
Non-intrusive notification banner displayed when a valid video URL is detected
in the system clipboard while Clipboard Monitoring is enabled.
"""
from typing import Optional

from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QWidget
)
from PySide6.QtCore import Qt, Signal

from ui.theme_manager import theme_manager


class ClipboardToast(QFrame):
    """Clean, non-intrusive notification banner for clipboard URL detection."""

    analyze_requested = Signal(str)
    download_requested = Signal(str)
    dismissed = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.current_url: str = ""
        self.setObjectName("clipboardToast")
        self.setFixedHeight(46)
        self.setVisible(False)
        self._setup_ui()

    def _setup_ui(self) -> None:
        p = theme_manager.get_palette()
        self.setStyleSheet(
            f"QFrame#clipboardToast {{ "
            f"  background-color: {p['card_bg']}; "
            f"  border: 1px solid {p['primary_accent']}; "
            f"  border-radius: 8px; "
            f"}}"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 4, 14, 4)
        layout.setSpacing(10)

        self.lbl_text = QLabel("🔗 Video link detected in clipboard")
        self.lbl_text.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {p['main_text']};")

        btn_analyze = QPushButton("🔍 Analyze")
        btn_analyze.setObjectName("primaryButton")
        btn_analyze.setFixedHeight(28)
        btn_analyze.setCursor(Qt.PointingHandCursor)
        btn_analyze.clicked.connect(self._on_analyze)

        btn_dismiss = QPushButton("✕")
        btn_dismiss.setObjectName("secondaryButton")
        btn_dismiss.setFixedSize(28, 28)
        btn_dismiss.setCursor(Qt.PointingHandCursor)
        btn_dismiss.clicked.connect(self.hide_toast)

        layout.addWidget(self.lbl_text, stretch=1)
        layout.addWidget(btn_analyze)
        layout.addWidget(btn_dismiss)

    def show_url(self, url: str, platform: str) -> None:
        """Display the banner with the detected video URL."""
        self.current_url = url
        short_url = url[:48] + ("..." if len(url) > 48 else "")
        self.lbl_text.setText(f"📋 {platform} link detected: {short_url}")
        self.setVisible(True)

    def hide_toast(self) -> None:
        """Dismiss the banner."""
        self.setVisible(False)
        self.dismissed.emit()

    def _on_analyze(self) -> None:
        url = self.current_url
        self.hide_toast()
        self.analyze_requested.emit(url)

