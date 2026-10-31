"""
Download History Page.
Displays records of completed downloads with quick links to open file and containing folder,
category filtering, and safe entry deletion (preserves media file on disk) styled in Neon Emerald Dark.
"""
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QMenu, QApplication
)
from PySide6.QtCore import Qt, Signal

from storage.history_manager import history_manager
from ui.theme_manager import theme_manager
from ui.components.card import Card
from ui.components.media_details_dialog import MediaDetailsDialog


class HistoryPage(QWidget):
    """View and manage local download history with compact category filters."""

    clear_requested = Signal()

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self._filter_category = "all"
        self._setup_ui()
        self.refresh_history()
        theme_manager.theme_changed.connect(lambda _: self.refresh_history())

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(28, 24, 28, 24)
        main_layout.setSpacing(16)

        # Header Section
        header_layout = QHBoxLayout()
        header_text = QVBoxLayout()
        header_text.setSpacing(2)

        page_title = QLabel("Download History")
        page_title.setObjectName("pageTitle")
        header_text.addWidget(page_title)
        header_layout.addLayout(header_text)
        header_layout.addStretch()

        # Compact category filter pills
        self.filter_all_btn = QPushButton("All")
        self.filter_all_btn.setObjectName("actionButton")
        self.filter_all_btn.setCursor(Qt.PointingHandCursor)
        self.filter_all_btn.clicked.connect(lambda: self.set_filter_category("all"))

        self.filter_video_btn = QPushButton("🎬 Video")
        self.filter_video_btn.setObjectName("actionButton")
        self.filter_video_btn.setCursor(Qt.PointingHandCursor)
        self.filter_video_btn.clicked.connect(lambda: self.set_filter_category("video"))

        self.filter_music_btn = QPushButton("🎵 Music")
        self.filter_music_btn.setObjectName("actionButton")
        self.filter_music_btn.setCursor(Qt.PointingHandCursor)
        self.filter_music_btn.clicked.connect(lambda: self.set_filter_category("music"))

        header_layout.addWidget(self.filter_all_btn)
        header_layout.addWidget(self.filter_video_btn)
        header_layout.addWidget(self.filter_music_btn)
        header_layout.addSpacing(8)

        self.clear_btn = QPushButton("🗑️ Clear History")
        self.clear_btn.setObjectName("secondaryButton")
        self.clear_btn.setCursor(Qt.PointingHandCursor)
        self.clear_btn.clicked.connect(self._on_clear_clicked)
        header_layout.addWidget(self.clear_btn)

        main_layout.addLayout(header_layout)

        # History Table Container Card
        table_card = Card()
        table_layout = QVBoxLayout()
        table_layout.setContentsMargins(0, 0, 0, 0)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "File Name", "Resolution", "Size", "Codec", "Date", "Location", "Actions"
        ])
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)          # File Name
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents) # Resolution
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents) # Size
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents) # Codec
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents) # Date
        header.setSectionResizeMode(5, QHeaderView.Stretch)          # Location
        header.setSectionResizeMode(6, QHeaderView.Fixed)            # Actions
        self.table.setColumnWidth(6, 175)

        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.table.cellDoubleClicked.connect(self._on_cell_double_clicked)

        table_layout.addWidget(self.table)
        table_card.add_layout(table_layout)
        main_layout.addWidget(table_card)

    def set_filter_category(self, cat: str) -> None:
        """Filter displayed records by media category."""
        self._filter_category = cat
        self.refresh_history()

    def refresh_history(self) -> None:
        """Reload records from storage and refresh table."""
        all_records = history_manager.get_all()

        # Apply category filter
        if self._filter_category == "video":
            records = [r for r in all_records if "MP3" not in r.get("codec", "").upper()]
        elif self._filter_category == "music":
            records = [r for r in all_records if "MP3" in r.get("codec", "").upper()]
        else:
            records = all_records

        self.set_history(records)

    def set_history(self, records: List[Dict[str, Any]]) -> None:
        """Populate table with download records."""
        self.table.setRowCount(len(records))
        for row, item in enumerate(records):
            entry_id = item.get("id", "")
            file_name = item.get("file_name", "Untitled")
            resolution = item.get("resolution", "—")
            size = item.get("file_size", "—")
            codec = item.get("codec", "—")
            date = item.get("download_date", "—")
            file_path = item.get("file_location", "")

            # File icon
            is_audio = "MP3" in codec.upper() or file_name.lower().endswith(".mp3")
            icon_str = "🎵" if is_audio else "🎬"

            item_title = QTableWidgetItem(f"{icon_str}  {file_name}")
            item_title.setToolTip(file_path)
            self.table.setItem(row, 0, item_title)

            item_res = QTableWidgetItem(resolution)
            item_res.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 1, item_res)

            item_size = QTableWidgetItem(size)
            item_size.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 2, item_size)

            item_codec = QTableWidgetItem(codec)
            item_codec.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 3, item_codec)

            item_date = QTableWidgetItem(date)
            item_date.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 4, item_date)

            item_loc = QTableWidgetItem(file_path)
            item_loc.setToolTip(file_path)
            self.table.setItem(row, 5, item_loc)

            # Action buttons
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(4, 2, 4, 2)
            actions_layout.setSpacing(6)

            open_btn = QPushButton("Open")
            open_btn.setObjectName("actionButton")
            open_btn.setCursor(Qt.PointingHandCursor)
            open_btn.clicked.connect(lambda _, p=file_path: self._open_file(p))

            folder_btn = QPushButton("Folder")
            folder_btn.setObjectName("actionButton")
            folder_btn.setCursor(Qt.PointingHandCursor)
            folder_btn.clicked.connect(lambda _, p=file_path: self._open_folder(p))

            del_btn = QPushButton("✕")
            del_btn.setObjectName("dangerButton")
            del_btn.setToolTip("Remove record from history (keeps file on disk)")
            del_btn.setCursor(Qt.PointingHandCursor)
            del_btn.clicked.connect(lambda _, eid=entry_id, fp=file_path: self._remove_entry(eid, fp))

            actions_layout.addWidget(open_btn)
            actions_layout.addWidget(folder_btn)
            actions_layout.addWidget(del_btn)
            self.table.setCellWidget(row, 6, actions_widget)

    def _open_file(self, file_path: str) -> None:
        """Launch downloaded file with default OS application."""
        if file_path and os.path.exists(file_path):
            try:
                if sys.platform == "win32":
                    os.startfile(file_path)
                else:
                    subprocess.run(["xdg-open", file_path])
            except Exception as e:
                QMessageBox.warning(self, "Open Error", f"Could not open file: {e}")
        else:
            QMessageBox.warning(self, "File Not Found", f"The file no longer exists at:\n{file_path}")

    def _open_folder(self, file_path: str) -> None:
        """Open containing folder in Windows Explorer and select the file."""
        if file_path and os.path.exists(file_path):
            try:
                if sys.platform == "win32":
                    subprocess.Popen(f'explorer /select,"{os.path.normpath(file_path)}"')
                else:
                    folder = str(Path(file_path).parent)
                    subprocess.Popen(["xdg-open", folder])
            except Exception as e:
                QMessageBox.warning(self, "Folder Error", f"Could not open containing folder: {e}")
        else:
            folder = str(Path(file_path).parent) if file_path else ""
            if folder and os.path.exists(folder):
                if sys.platform == "win32":
                    subprocess.Popen(f'explorer "{os.path.normpath(folder)}"')
                else:
                    subprocess.Popen(["xdg-open", folder])
            else:
                QMessageBox.warning(self, "Folder Not Found", f"The file or destination folder does not exist on disk:\n{file_path}")

    def _remove_entry(self, entry_id: str, file_path: str) -> None:
        """Remove record from history without deleting file on disk."""
        key = entry_id or file_path
        history_manager.remove_entry(key)
        self.refresh_history()

    def _on_cell_double_clicked(self, row: int, col: int) -> None:
        item = self.table.item(row, 5)
        if item:
            self._open_file(item.text())

    def _show_context_menu(self, pos) -> None:
        row = self.table.rowAt(pos.y())
        if row < 0:
            return

        item_path = self.table.item(row, 5)
        item_title = self.table.item(row, 0)
        file_path = item_path.text() if item_path else ""

        menu = QMenu(self)
        act_open = menu.addAction("▶ Open File")
        act_folder = menu.addAction("📂 Open Containing Folder")
        act_details = menu.addAction("📊 View Media Properties (FFprobe)")
        act_copy = menu.addAction("📋 Copy File Path")
        menu.addSeparator()
        act_remove = menu.addAction("✕ Remove from History")

        act_open.triggered.connect(lambda: self._open_file(file_path))
        act_folder.triggered.connect(lambda: self._open_folder(file_path))
        act_details.triggered.connect(lambda: MediaDetailsDialog(file_path, self).exec())
        act_copy.triggered.connect(lambda: QApplication.clipboard().setText(file_path))
        act_remove.triggered.connect(lambda: self._remove_entry("", file_path))

        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _on_clear_clicked(self) -> None:
        """Confirm and clear all download history records."""
        if not history_manager.get_all():
            return
        reply = QMessageBox.question(
            self,
            "Clear History",
            "Are you sure you want to clear all download history records?\n\n(Important: Downloaded media files will NOT be deleted from your disk)",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            history_manager.clear()
            self.refresh_history()
            self.clear_requested.emit()
