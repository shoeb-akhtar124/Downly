"""
Download Queue Page.
Professional Download Manager Table with real-time progress, speed, ETA,
and full context menu / batch controls styled in Neon Emerald Dark.
"""
import os
import sys
import subprocess
from typing import Dict, Any, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QFrame, QTableWidget, QTableWidgetItem, QHeaderView,
    QMenu, QMessageBox, QApplication
)
from PySide6.QtCore import Qt, Signal

from core.download_manager import download_manager, DownloadTask
from ui.theme_manager import theme_manager
from ui.components.card import Card
from ui.components.progress_dialog import DownloadProgressDialog
from ui.components.media_details_dialog import MediaDetailsDialog
from ui.components.schedule_dialog import ScheduleDialog


class QueuePage(QWidget):
    """Manages active and queued download tasks in a professional IDM-style table."""

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.task_rows: Dict[str, int] = {} # task_id -> row_index
        self._progress_bars: Dict[str, QProgressBar] = {}
        self._setup_ui()
        self._connect_signals()
        theme_manager.theme_changed.connect(lambda _: self.refresh_table())

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(16)

        # Header Section
        header_layout = QHBoxLayout()
        header_text = QVBoxLayout()
        header_text.setSpacing(2)

        page_title = QLabel("Download Queue")
        page_title.setObjectName("pageTitle")
        header_text.addWidget(page_title)
        header_layout.addLayout(header_text)
        header_layout.addStretch()

        # Batch Queue Controls
        self.pause_all_btn = QPushButton("⏸ Pause All")
        self.pause_all_btn.setObjectName("secondaryButton")
        self.pause_all_btn.setCursor(Qt.PointingHandCursor)
        self.pause_all_btn.clicked.connect(self._on_pause_all_clicked)

        self.resume_all_btn = QPushButton("▶ Resume All")
        self.resume_all_btn.setObjectName("secondaryButton")
        self.resume_all_btn.setCursor(Qt.PointingHandCursor)
        self.resume_all_btn.clicked.connect(self._on_resume_all_clicked)

        self.clear_finished_btn = QPushButton("🧹 Clear Finished")
        self.clear_finished_btn.setObjectName("secondaryButton")
        self.clear_finished_btn.setCursor(Qt.PointingHandCursor)
        self.clear_finished_btn.clicked.connect(self._on_clear_finished_clicked)

        self.sched_btn = QPushButton("⏰ Scheduler")
        self.sched_btn.setObjectName("secondaryButton")
        self.sched_btn.setCursor(Qt.PointingHandCursor)
        self.sched_btn.clicked.connect(self._on_open_scheduler)

        header_layout.addWidget(self.pause_all_btn)
        header_layout.addWidget(self.resume_all_btn)
        header_layout.addWidget(self.sched_btn)
        header_layout.addWidget(self.clear_finished_btn)
        main_layout.addLayout(header_layout)

        # Table Container Card
        table_card = Card()
        card_layout = QVBoxLayout()
        card_layout.setContentsMargins(0, 0, 0, 0)

        # 6-Column Professional Download Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "File Name", "Size", "Status", "Progress", "Download Speed", "Time Remaining"
        ])
        
        # Column Resizing Behavior
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)          # File Name
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents) # Size
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents) # Status
        header.setSectionResizeMode(3, QHeaderView.Fixed)            # Progress Bar
        self.table.setColumnWidth(3, 160)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents) # Speed
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents) # ETA

        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.table.cellDoubleClicked.connect(self._on_cell_double_clicked)

        card_layout.addWidget(self.table)
        table_card.add_layout(card_layout)
        main_layout.addWidget(table_card)

        self.refresh_table()

    def _connect_signals(self) -> None:
        """Connect download manager events to update queue table in real-time."""
        download_manager.task_added.connect(self._on_task_added)
        download_manager.task_updated.connect(self._on_task_updated)
        download_manager.task_progress.connect(self._on_task_progress)
        download_manager.task_extended_progress.connect(self._on_task_extended_progress)
        download_manager.task_status_changed.connect(self._on_task_status_changed)
        download_manager.task_completed.connect(self._on_task_completed)
        download_manager.task_failed.connect(self._on_task_failed)

    def _on_task_extended_progress(
        self, task_id: str, percent: float, speed: str, avg: str, peak: str, eta: str
    ) -> None:
        self._on_task_progress(task_id, percent, speed, eta)

    def refresh_table(self) -> None:
        """Rebuild entire table from download_manager.tasks."""
        tasks = list(download_manager.tasks.values())
        self.table.setRowCount(len(tasks))
        self.task_rows.clear()
        self._progress_bars.clear()

        for row, task in enumerate(tasks):
            self.task_rows[task.task_id] = row
            self._populate_row(row, task)

    def _populate_row(self, row: int, task: DownloadTask) -> None:
        """Set cell contents for a single row."""
        # Col 0: File Name
        item_title = QTableWidgetItem(f"🎬  {task.title}")
        item_title.setToolTip(task.url)
        self.table.setItem(row, 0, item_title)

        # Col 1: Size
        item_size = QTableWidgetItem(task.file_size_str or "—")
        item_size.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(row, 1, item_size)

        # Col 2: Status Badge Widget
        status_widget = QWidget()
        status_layout = QHBoxLayout(status_widget)
        status_layout.setContentsMargins(6, 4, 6, 4)
        lbl_status = QLabel(task.status)
        lbl_status.setAlignment(Qt.AlignCenter)
        self._style_status_label(lbl_status, task.status)
        status_layout.addWidget(lbl_status)
        self.table.setCellWidget(row, 2, status_widget)

        # Col 3: Progress Bar Widget
        bar_widget = QWidget()
        bar_layout = QHBoxLayout(bar_widget)
        bar_layout.setContentsMargins(6, 4, 6, 4)
        pbar = QProgressBar()
        pbar.setValue(int(task.progress))
        pbar.setFixedHeight(12)
        bar_layout.addWidget(pbar)
        self.table.setCellWidget(row, 3, bar_widget)
        self._progress_bars[task.task_id] = pbar

        # Col 4: Speed
        item_speed = QTableWidgetItem(task.speed_str or "—")
        item_speed.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(row, 4, item_speed)

        # Col 5: ETA
        item_eta = QTableWidgetItem(task.eta_str or "—")
        item_eta.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(row, 5, item_eta)

    def _on_open_scheduler(self) -> None:
        """Open schedule manager dialog."""
        dlg = ScheduleDialog(parent=self)
        dlg.exec()

    def _style_status_label(self, lbl: QLabel, status: str) -> None:
        is_dark = theme_manager.is_dark()
        if status in ("Downloading", "Analyzing"):
            bg = "#14251E" if is_dark else "#E4F5ED"
            fg = "#00D99A" if is_dark else "#008F67"
            bdr = "#1C382C" if is_dark else "#BFE4D3"
        elif status in ("Converting", "Processing"):
            bg = "#26163B" if is_dark else "#F3E8FF"
            fg = "#C084FC" if is_dark else "#7E22CE"
            bdr = "#4A2870" if is_dark else "#D8B4FE"
        elif status in ("Queued", "Pending"):
            bg = "#33230A" if is_dark else "#FEF3C7"
            fg = "#FFB547" if is_dark else "#D97706"
            bdr = "#573E14" if is_dark else "#FCD34D"
        elif status == "Completed":
            bg = "#0F3323" if is_dark else "#DEF7EC"
            fg = "#16C784" if is_dark else "#0E9F6E"
            bdr = "#195239" if is_dark else "#BCF0DA"
        elif status == "Failed":
            bg = "#381418" if is_dark else "#FDE8E8"
            fg = "#FF5C68" if is_dark else "#E02424"
            bdr = "#592027" if is_dark else "#FBD5D5"
        elif status == "Paused":
            bg = "#19211C" if is_dark else "#EDF3EF"
            fg = "#A0AAA4" if is_dark else "#64736A"
            bdr = "#29352E" if is_dark else "#DCE7DF"
        else:
            p = theme_manager.get_palette()
            bg, fg, bdr = p['surface_sec'], p['secondary_text'], p['borders']

        lbl.setStyleSheet(f"background-color: {bg}; color: {fg}; border: 1px solid {bdr}; border-radius: 4px; padding: 2px 8px; font-weight: 600;")

    def _on_task_added(self, task: DownloadTask) -> None:
        self.refresh_table()

    def _on_task_updated(self, task: DownloadTask) -> None:
        row = self.task_rows.get(task.task_id)
        if row is not None and row < self.table.rowCount():
            self._populate_row(row, task)

    def _on_task_progress(self, task_id: str, percent: float, speed: str, eta: str) -> None:
        row = self.task_rows.get(task_id)
        if row is not None and row < self.table.rowCount():
            pbar = self._progress_bars.get(task_id)
            if pbar:
                pbar.setValue(int(percent))
            
            item_speed = self.table.item(row, 4)
            if item_speed:
                item_speed.setText(speed or "—")

            item_eta = self.table.item(row, 5)
            if item_eta:
                item_eta.setText(eta or "—")

    def _on_task_status_changed(self, task_id: str, status: str, message: str) -> None:
        row = self.task_rows.get(task_id)
        if row is not None and row < self.table.rowCount():
            task = download_manager.tasks.get(task_id)
            if task:
                self._populate_row(row, task)

    def _on_task_completed(self, task: DownloadTask) -> None:
        row = self.task_rows.get(task.task_id)
        if row is not None and row < self.table.rowCount():
            self._populate_row(row, task)

    def _on_task_failed(self, task_id: str, error_msg: str) -> None:
        row = self.task_rows.get(task_id)
        if row is not None and row < self.table.rowCount():
            task = download_manager.tasks.get(task_id)
            if task:
                self._populate_row(row, task)

    def _on_cell_double_clicked(self, row: int, col: int) -> None:
        """Open floating progress dialog on row double click."""
        tasks = list(download_manager.tasks.values())
        if 0 <= row < len(tasks):
            task = tasks[row]
            dlg = DownloadProgressDialog(task, self)
            dlg.exec()

    def _show_context_menu(self, pos) -> None:
        """Display context menu for selected task row."""
        row = self.table.rowAt(pos.y())
        if row < 0:
            return

        tasks = list(download_manager.tasks.values())
        if row >= len(tasks):
            return
        task = tasks[row]

        menu = QMenu(self)
        
        act_dialog = menu.addAction("🔍 Open Download Status Window")

        if task.status == "Completed" or (task.final_file_path and os.path.exists(task.final_file_path)):
            act_details = menu.addAction("📊 View Media Properties (FFprobe)")
            act_details.triggered.connect(lambda: MediaDetailsDialog(task.final_file_path, self).exec())

        menu.addSeparator()

        if task.status in ("Downloading", "Queued", "Pending"):
            act_pause = menu.addAction("⏸ Pause Download")
            act_pause.triggered.connect(lambda: download_manager.pause_download(task.task_id))
        elif task.status == "Paused":
            act_resume = menu.addAction("▶ Resume Download")
            act_resume.triggered.connect(lambda: download_manager.resume_download(task.task_id))

        if task.status in ("Downloading", "Queued", "Pending", "Paused"):
            act_cancel = menu.addAction("✕ Cancel Download")
            act_cancel.triggered.connect(lambda: download_manager.cancel_download(task.task_id))

        if task.status in ("Failed", "Cancelled"):
            act_retry = menu.addAction("🔄 Retry Download")
            act_retry.triggered.connect(lambda: download_manager.retry_download(task.task_id))

        menu.addSeparator()
        act_open_folder = menu.addAction("📂 Open Destination Folder")
        act_copy_url = menu.addAction("📋 Copy Media Link")
        act_remove = menu.addAction("🗑 Remove from Queue")

        act_dialog.triggered.connect(lambda: DownloadProgressDialog(task, self).exec())
        act_open_folder.triggered.connect(lambda: self._open_folder(task.download_dir))
        act_copy_url.triggered.connect(lambda: QApplication.clipboard().setText(task.url))
        act_remove.triggered.connect(lambda: self._remove_task(task.task_id))

        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _remove_task(self, task_id: str) -> None:
        if task_id in download_manager.tasks:
            download_manager.cancel_download(task_id)
            download_manager.tasks.pop(task_id, None)
            if task_id in download_manager.queue:
                download_manager.queue.remove(task_id)
            self.refresh_table()

    def _open_folder(self, folder: str) -> None:
        if folder and os.path.exists(folder):
            if sys.platform == "win32":
                os.startfile(folder)
            else:
                subprocess.run(["xdg-open", folder])

    def _on_pause_all_clicked(self) -> None:
        for tid, task in list(download_manager.tasks.items()):
            if task.status in ("Downloading", "Queued"):
                download_manager.pause_download(tid)
        self.refresh_table()

    def _on_resume_all_clicked(self) -> None:
        for tid, task in list(download_manager.tasks.items()):
            if task.status == "Paused":
                download_manager.resume_download(tid)
        self.refresh_table()

    def _on_clear_finished_clicked(self) -> None:
        finished_ids = [
            tid for tid, t in download_manager.tasks.items()
            if t.status in ("Completed", "Cancelled", "Failed")
        ]
        for tid in finished_ids:
            download_manager.tasks.pop(tid, None)
            if tid in download_manager.queue:
                download_manager.queue.remove(tid)
        self.refresh_table()
