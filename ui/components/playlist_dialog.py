"""
Playlist Selection Dialog Component.
Displays parsed playlist entries with checkboxes, selection tools,
format/quality choices, and batch enqueueing into Downly's download manager.
"""
from typing import Dict, Any, List, Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox,
    QComboBox, QFrame, QMessageBox, QWidget
)
from PySide6.QtCore import Qt

from app.constants import SUPPORTED_QUALITIES, SUPPORTED_FORMATS, SUPPORTED_VIDEO_CODECS, SUPPORTED_AUDIO_CODECS
from core.download_manager import download_manager
from core.download_destination import destination_manager
from ui.theme_manager import theme_manager


class PlaylistDialog(QDialog):
    """Modal dialog presenting playlist videos for selective or full batch downloading."""

    def __init__(self, playlist_info: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.playlist_info = playlist_info
        self.entries: List[Dict[str, Any]] = playlist_info.get("entries", [])
        self.checkboxes: List[QCheckBox] = []

        self.setWindowTitle(f"Playlist - {playlist_info.get('title', 'Video Playlist')}")
        self.resize(760, 520)
        self.setMinimumSize(600, 400)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self._setup_ui()

    def _setup_ui(self) -> None:
        p = theme_manager.get_palette()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(14)

        # Header
        head_layout = QHBoxLayout()
        head_text = QVBoxLayout()
        head_text.setSpacing(2)

        title = self.playlist_info.get("title", "Untitled Playlist")
        count = len(self.entries)
        uploader = self.playlist_info.get("uploader", "Unknown Channel")

        title_lbl = QLabel(f"📋 {title}")
        title_lbl.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {p['main_text']};")
        title_lbl.setWordWrap(True)

        meta_lbl = QLabel(f"{count} items detected  •  Channel: {uploader}")
        meta_lbl.setStyleSheet(f"font-size: 12px; color: {p['secondary_text']};")

        head_text.addWidget(title_lbl)
        head_text.addWidget(meta_lbl)
        head_layout.addLayout(head_text)
        head_layout.addStretch()

        # Selection shortcuts
        btn_select_all = QPushButton("Select All")
        btn_select_all.setObjectName("secondaryButton")
        btn_select_all.setCursor(Qt.PointingHandCursor)
        btn_select_all.clicked.connect(self._select_all)

        btn_deselect_all = QPushButton("Deselect All")
        btn_deselect_all.setObjectName("secondaryButton")
        btn_deselect_all.setCursor(Qt.PointingHandCursor)
        btn_deselect_all.clicked.connect(self._deselect_all)

        head_layout.addWidget(btn_select_all)
        head_layout.addWidget(btn_deselect_all)
        layout.addLayout(head_layout)

        # Table of playlist items
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["", "#", "Title", "Duration"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 40)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        self.table.setColumnWidth(1, 40)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)

        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)

        self._populate_table()
        layout.addWidget(self.table)

        # Output options bar
        opts_frame = QFrame()
        opts_frame.setStyleSheet(
            f"background-color: {p['card_bg']}; border: 1px solid {p['borders']}; border-radius: 8px;"
        )
        opts_layout = QHBoxLayout(opts_frame)
        opts_layout.setContentsMargins(14, 10, 14, 10)
        opts_layout.setSpacing(12)

        lbl_q = QLabel("Quality:")
        lbl_q.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {p['secondary_text']};")
        self.combo_quality = QComboBox()
        self.combo_quality.addItems(SUPPORTED_QUALITIES)

        lbl_fmt = QLabel("Format:")
        lbl_fmt.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {p['secondary_text']};")
        self.combo_format = QComboBox()
        self.combo_format.addItems(SUPPORTED_FORMATS)

        opts_layout.addWidget(lbl_q)
        opts_layout.addWidget(self.combo_quality)
        opts_layout.addWidget(lbl_fmt)
        opts_layout.addWidget(self.combo_format)
        opts_layout.addStretch()

        layout.addWidget(opts_frame)

        # Footer actions
        footer = QHBoxLayout()
        footer.setSpacing(10)

        self.lbl_selected_count = QLabel(f"Selected: {len(self.entries)} of {len(self.entries)}")
        self.lbl_selected_count.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {p['main_text']};")

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("secondaryButton")
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)

        self.add_btn = QPushButton(f"⬇️ Add Selected ({len(self.entries)}) to Queue")
        self.add_btn.setObjectName("primaryButton")
        self.add_btn.setCursor(Qt.PointingHandCursor)
        self.add_btn.setFixedHeight(36)
        self.add_btn.clicked.connect(self._on_add_clicked)

        footer.addWidget(self.lbl_selected_count)
        footer.addStretch()
        footer.addWidget(cancel_btn)
        footer.addWidget(self.add_btn)
        layout.addLayout(footer)

    def _populate_table(self) -> None:
        p = theme_manager.get_palette()
        self.table.setRowCount(len(self.entries))
        self.checkboxes.clear()

        for row, item in enumerate(self.entries):
            # Checkbox cell
            cb = QCheckBox()
            cb.setChecked(True)
            cb.stateChanged.connect(self._update_selected_count)
            self.checkboxes.append(cb)

            cb_widget = QWidget()
            cb_layout = QHBoxLayout(cb_widget)
            cb_layout.setContentsMargins(8, 0, 0, 0)
            cb_layout.setAlignment(Qt.AlignCenter)
            cb_layout.addWidget(cb)
            self.table.setCellWidget(row, 0, cb_widget)

            # Index cell
            idx_item = QTableWidgetItem(str(item.get("index", row + 1)))
            idx_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 1, idx_item)

            # Title cell
            title_item = QTableWidgetItem(item.get("title", f"Video {row+1}"))
            self.table.setItem(row, 2, title_item)

            # Duration cell
            dur_item = QTableWidgetItem(item.get("duration_str", "—"))
            dur_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 3, dur_item)

    def _select_all(self) -> None:
        for cb in self.checkboxes:
            cb.setChecked(True)
        self._update_selected_count()

    def _deselect_all(self) -> None:
        for cb in self.checkboxes:
            cb.setChecked(False)
        self._update_selected_count()

    def _update_selected_count(self) -> None:
        selected = sum(1 for cb in self.checkboxes if cb.isChecked())
        total = len(self.checkboxes)
        self.lbl_selected_count.setText(f"Selected: {selected} of {total}")
        self.add_btn.setText(f"⬇️ Add Selected ({selected}) to Queue")
        self.add_btn.setEnabled(selected > 0)

    def _on_add_clicked(self) -> None:
        quality = self.combo_quality.currentText()
        output_format = self.combo_format.currentText()
        codec = "Keep Original Codec"
        audio_codec = "Keep Original"
        dest_dir = str(destination_manager.get_destination())

        added_count = 0
        for i, cb in enumerate(self.checkboxes):
            if cb.isChecked():
                entry = self.entries[i]
                url = entry.get("url")
                title = entry.get("title") or f"Item {i+1}"
                thumb = entry.get("thumbnail") or ""

                download_manager.add_download(
                    url=url,
                    title=title,
                    quality=quality,
                    output_format=output_format,
                    codec=codec,
                    thumbnail=thumb,
                    platform=self.playlist_info.get("platform", "Playlist"),
                    download_dir=dest_dir,
                    audio_codec=audio_codec
                )
                added_count += 1

        QMessageBox.information(
            self,
            "Playlist Queued",
            f"Successfully queued {added_count} video(s) into the Download Queue."
        )
        self.accept()
