"""
Sidebar Navigation Component.
Single left vertical navigation sidebar displaying both icons and labels.
Supports Dark Mode and Light Mode with subtle active and hover states.
Cleaned up according to user specifications (theme toggle, version badge, and NAVIGATION heading removed).
"""
from typing import List
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QSpacerItem, QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap

from app.constants import APP_NAME, APP_VERSION, ROOT_DIR
from ui.theme_manager import theme_manager


class Sidebar(QWidget):
    """Single vertical navigation sidebar with icon and readable text label."""

    page_changed = Signal(int)

    NAV_ITEMS = [
        {"index": 0, "title": "Dashboard", "icon": "📊"},
        {"index": 1, "title": "Downloader", "icon": "📥"},
        {"index": 2, "title": "Download Queue", "icon": "⏳"},
        {"index": 3, "title": "History", "icon": "📁"},
        {"index": 4, "title": "Settings", "icon": "⚙️"}
    ]

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setObjectName("sidebarWidget")
        self.setFixedWidth(210)

        self.buttons: List[QPushButton] = []
        self._current_index = 0

        self._setup_ui()
        self._apply_theme_styles()
        theme_manager.theme_changed.connect(self._apply_theme_styles)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 22, 14, 18)
        layout.setSpacing(6)

        # Brand / Header section
        brand_layout = QHBoxLayout()
        brand_layout.setSpacing(10)
        brand_layout.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)

        # App Icon Badge with official brand logo
        self.logo_badge = QLabel()
        self.logo_badge.setFixedSize(36, 36)
        self.logo_badge.setAlignment(Qt.AlignCenter)
        icon_path = ROOT_DIR / "assets" / "icons" / "downly_icon.png"
        if not icon_path.exists():
            icon_path = ROOT_DIR / "assets" / "icons" / "app_icon.png"
        if icon_path.exists():
            pix = QPixmap(str(icon_path)).scaled(36, 36, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.logo_badge.setPixmap(pix)
            self.logo_badge.setStyleSheet("border: none; background: transparent;")
        else:
            self.logo_badge.setText("D")
        brand_layout.addWidget(self.logo_badge)

        self.title_label = QLabel(APP_NAME)
        self.title_label.setObjectName("brandTitle")
        brand_layout.addWidget(self.title_label)

        layout.addLayout(brand_layout)
        layout.addSpacing(16)

        # Navigation Buttons (Both Icon & Text Label)
        for item in self.NAV_ITEMS:
            btn = QPushButton(f" {item['icon']}   {item['title']}")
            btn.setObjectName("navButton")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            idx = item["index"]
            btn.clicked.connect(lambda checked=False, i=idx: self.set_current_index(i))
            layout.addWidget(btn)
            self.buttons.append(btn)

        # Spacer pushing content up
        layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))

        # Bottom-left Application Version Label (Subtle, aligned with sidebar)
        self.version_label = QLabel(f"v{APP_VERSION}")
        self.version_label.setObjectName("versionLabel")
        self.version_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.version_label.setStyleSheet("padding-left: 10px; margin-bottom: 2px;")
        layout.addWidget(self.version_label)

        # Initialize selection
        self.set_current_index(0)

    def _apply_theme_styles(self) -> None:
        """Update logo badge and colors according to active theme."""
        p = theme_manager.get_palette()
        if not self.logo_badge.pixmap() or self.logo_badge.pixmap().isNull():
            self.logo_badge.setStyleSheet(
                f"background: {p['surface_sec']}; color: {p['primary_accent']}; "
                f"border: 1px solid {p['borders']}; font-size: 20px; font-weight: 900; border-radius: 9px;"
            )
        else:
            self.logo_badge.setStyleSheet(
                "border: none; background: transparent;"
            )

        # Re-polish active button to trigger QSS rules
        if 0 <= self._current_index < len(self.buttons):
            btn = self.buttons[self._current_index]
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def set_current_index(self, index: int) -> None:
        """Select active page button and emit change signal."""
        if 0 <= index < len(self.buttons):
            self._current_index = index
            for i, btn in enumerate(self.buttons):
                is_active = (i == index)
                btn.setChecked(is_active)
                btn.setProperty("active", is_active)
                btn.style().unpolish(btn)
                btn.style().polish(btn)
            self.page_changed.emit(index)

    def current_index(self) -> int:
        return self._current_index
