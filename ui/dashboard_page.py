"""
Dashboard Page.
Overview of download statistics, quick URL analysis entry, recent downloads,
and minimal supported media platforms row supporting Dark and Light modes.
"""
import os
import sys
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFrame, QGridLayout, QScrollArea, QApplication
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QPainter
from PySide6.QtSvg import QSvgRenderer

from app.constants import ROOT_DIR
from core.download_manager import download_manager
from storage.history_manager import history_manager
from ui.theme_manager import theme_manager
from ui.components.card import Card


class StatCard(QFrame):
    """Metric stat card supporting both Dark and Light theme styling."""

    def __init__(self, title: str, value: str, icon: str, subtitle: str = "", parent: QWidget = None):
        super().__init__(parent)
        self.setObjectName("cardFrame")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(6)

        top_row = QHBoxLayout()
        self.lbl_title = QLabel(title)
        self.lbl_icon = QLabel(icon)
        self.lbl_icon.setStyleSheet("font-size: 18px;")
        top_row.addWidget(self.lbl_title)
        top_row.addStretch()
        top_row.addWidget(self.lbl_icon)
        layout.addLayout(top_row)

        self.val_label = QLabel(value)
        layout.addWidget(self.val_label)

        self.lbl_sub = None
        if subtitle:
            self.lbl_sub = QLabel(subtitle)
            layout.addWidget(self.lbl_sub)

        self._update_theme()
        theme_manager.theme_changed.connect(self._update_theme)

    def _update_theme(self) -> None:
        p = theme_manager.get_palette()
        self.lbl_title.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {p['secondary_text']}; text-transform: uppercase; letter-spacing: 0.5px;")
        self.val_label.setStyleSheet(f"font-size: 26px; font-weight: 800; color: {p['primary_accent']};")
        if self.lbl_sub:
            self.lbl_sub.setStyleSheet(f"font-size: 11px; color: {p['secondary_text']};")

    def set_value(self, value: str) -> None:
        self.val_label.setText(value)


class DashboardPage(QWidget):
    """Application Dashboard view with clean spacing and minimal supported platforms."""

    navigate_requested = Signal(int)       # Page index to switch to
    quick_analyze_requested = Signal(str)  # URL to analyze on Downloader page

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self._setup_ui()
        self.refresh_stats()
        theme_manager.theme_changed.connect(self._on_theme_changed)

    def _setup_ui(self) -> None:
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background: transparent;")

        container = QWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(28, 24, 28, 24)
        main_layout.setSpacing(18)

        # Header Section
        header_layout = QVBoxLayout()
        header_layout.setSpacing(2)
        page_title = QLabel("Dashboard")
        page_title.setObjectName("pageTitle")
        header_layout.addWidget(page_title)
        main_layout.addLayout(header_layout)

        # 1. Metrics Grid (2 balanced stat cards)
        metrics_layout = QHBoxLayout()
        metrics_layout.setSpacing(16)

        self.card_total = StatCard("Total Downloads", "0", "📁")
        self.card_active = StatCard("Active Queue", "0", "⏳")

        metrics_layout.addWidget(self.card_total)
        metrics_layout.addWidget(self.card_active)
        main_layout.addLayout(metrics_layout)

        # 2. Quick Download Bar
        quick_card = Card(title="Quick Download / Analyze")
        quick_layout = QHBoxLayout()
        quick_layout.setSpacing(8)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://www.youtube.com/watch?v=...")
        self.url_input.setClearButtonEnabled(True)
        self.url_input.returnPressed.connect(self._on_quick_inspect)

        paste_btn = QPushButton("📋 Paste")
        paste_btn.setObjectName("secondaryButton")
        paste_btn.setCursor(Qt.PointingHandCursor)
        paste_btn.clicked.connect(self._on_paste_clicked)

        inspect_btn = QPushButton("🚀 Inspect & Download")
        inspect_btn.setObjectName("primaryButton")
        inspect_btn.setCursor(Qt.PointingHandCursor)
        inspect_btn.clicked.connect(self._on_quick_inspect)

        quick_layout.addWidget(self.url_input, stretch=1)
        quick_layout.addWidget(paste_btn)
        quick_layout.addWidget(inspect_btn)
        quick_card.add_layout(quick_layout)
        main_layout.addWidget(quick_card)

        # 3. Recent Downloads Card
        self.recent_card = Card(title="Recent Downloads")
        self.recent_layout = QVBoxLayout()
        self.recent_layout.setSpacing(10)

        self.recent_items_container = QWidget()
        self.recent_items_layout = QVBoxLayout(self.recent_items_container)
        self.recent_items_layout.setContentsMargins(0, 0, 0, 0)
        self.recent_items_layout.setSpacing(8)

        self.recent_layout.addWidget(self.recent_items_container)

        view_all_btn = QPushButton("View Full History →")
        view_all_btn.setObjectName("secondaryButton")
        view_all_btn.setCursor(Qt.PointingHandCursor)
        view_all_btn.clicked.connect(lambda: self.navigate_requested.emit(3)) # Index 3 is History
        self.recent_layout.addWidget(view_all_btn, alignment=Qt.AlignRight)

        self.recent_card.add_layout(self.recent_layout)
        main_layout.addWidget(self.recent_card)

        # 4. Completely Redesigned Minimal Supported Platforms Section
        platform_card = Card(title="Supported Platforms")

        platforms_container = QHBoxLayout()
        platforms_container.setSpacing(10)
        platforms_container.setAlignment(Qt.AlignLeft)

        # Verified supported platforms: real brand vector logos and names, compact appearance
        platforms_data = [
            ("youtube", "YouTube"),
            ("instagram", "Instagram"),
            ("facebook", "Facebook"),
            ("tiktok", "TikTok"),
            ("vimeo", "Vimeo"),
            ("x", "X"),
            ("reddit", "Reddit"),
        ]

        self.platform_frames = []
        for slug, name in platforms_data:
            p_frame = QFrame()
            p_frame.setObjectName("platformBadge")
            p_layout = QHBoxLayout(p_frame)
            p_layout.setContentsMargins(12, 8, 12, 8)
            p_layout.setSpacing(8)

            lbl_icon = QLabel()
            lbl_icon.setFixedSize(18, 18)
            svg_path = ROOT_DIR / "assets" / "icons" / "platforms" / f"{slug}.svg"
            if svg_path.exists():
                pix = QPixmap(18, 18)
                pix.fill(Qt.transparent)
                painter = QPainter(pix)
                renderer = QSvgRenderer(str(svg_path))
                renderer.render(painter)
                painter.end()
                lbl_icon.setPixmap(pix)

            lbl_name = QLabel(name)
            lbl_name.setStyleSheet("font-size: 12px; font-weight: 600;")

            p_layout.addWidget(lbl_icon)
            p_layout.addWidget(lbl_name)
            platforms_container.addWidget(p_frame)
            self.platform_frames.append(p_frame)

        platforms_container.addStretch()
        platform_card.add_layout(platforms_container)
        main_layout.addWidget(platform_card)

        main_layout.addStretch()
        scroll.setWidget(container)

        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.addWidget(scroll)

        self._style_platform_badges()

    def _style_platform_badges(self) -> None:
        p = theme_manager.get_palette()
        for f in self.platform_frames:
            f.setStyleSheet(
                f"QFrame#platformBadge {{"
                f"  background-color: {p['input_bg']}; "
                f"  border: 1px solid {p['borders']}; "
                f"  border-radius: 6px;"
                f"}}"
                f"QFrame#platformBadge:hover {{"
                f"  background-color: {p['surface_sec']}; "
                f"  border-color: {p['primary_accent']};"
                f"}}"
            )

    def _on_theme_changed(self, theme_name: str) -> None:
        self._style_platform_badges()
        self.refresh_stats()

    def refresh_stats(self) -> None:
        """Update metrics and recent items from storage and download manager."""
        records = history_manager.get_all()
        self.card_total.set_value(str(len(records)))

        active_count = len(download_manager.active_workers) + len(
            [t for t in download_manager.tasks.values() if t.status in ("Queued", "Downloading")]
        )
        self.card_active.set_value(str(active_count))

        p = theme_manager.get_palette()

        # Clear and rebuild recent items
        while self.recent_items_layout.count():
            item = self.recent_items_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not records:
            empty_lbl = QLabel("No downloads recorded yet. Paste a video URL above to get started!")
            empty_lbl.setStyleSheet(f"font-size: 13px; color: {p['secondary_text']}; padding: 12px 0;")
            self.recent_items_layout.addWidget(empty_lbl)
        else:
            for r in records[:4]:
                row = QFrame()
                row.setStyleSheet(
                    f"background-color: {p['surface_sec']}; "
                    f"border: 1px solid {p['borders']}; "
                    f"border-radius: 6px; padding: 6px;"
                )
                row_layout = QHBoxLayout(row)
                row_layout.setContentsMargins(10, 6, 10, 6)

                icon = QLabel("🎬" if "MP3" not in r.get("codec", "").upper() else "🎵")
                icon.setStyleSheet("font-size: 16px;")

                info_col = QVBoxLayout()
                info_col.setSpacing(2)
                t_lbl = QLabel(r.get("file_name", "Untitled"))
                t_lbl.setStyleSheet(f"font-weight: 600; font-size: 13px; color: {p['main_text']};")
                sub_lbl = QLabel(f"{r.get('website', 'Web')} • {r.get('resolution', '—')} • {r.get('file_size', '—')} • {r.get('download_date', '')}")
                sub_lbl.setStyleSheet(f"font-size: 11px; color: {p['secondary_text']};")
                info_col.addWidget(t_lbl)
                info_col.addWidget(sub_lbl)

                open_btn = QPushButton("Open")
                open_btn.setObjectName("actionButton")
                open_btn.setCursor(Qt.PointingHandCursor)
                file_path = r.get("file_location", "")
                open_btn.clicked.connect(lambda _, fp=file_path: self._open_file(fp))

                row_layout.addWidget(icon)
                row_layout.addLayout(info_col, stretch=1)
                row_layout.addWidget(open_btn)
                self.recent_items_layout.addWidget(row)

    def _open_file(self, file_path: str) -> None:
        if file_path and os.path.exists(file_path):
            if sys.platform == "win32":
                os.startfile(file_path)
            else:
                subprocess.run(["xdg-open", file_path])

    def _on_paste_clicked(self) -> None:
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if text:
            self.url_input.setText(text.strip())

    def _on_quick_inspect(self) -> None:
        url = self.url_input.text().strip()
        if url:
            self.quick_analyze_requested.emit(url)
            self.navigate_requested.emit(1) # Navigate to Downloader page
