"""
Schedule Download Dialog Component.
Enables users to schedule downloads for future dates/times, view pending schedules,
edit or cancel them, and inspect their status.
"""
from datetime import datetime, timedelta
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QDateTimeEdit, QComboBox, QFileDialog, QTabWidget, QWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox
)
from PySide6.QtCore import Qt, QDateTime

from app.config import config
from app.constants import SUPPORTED_QUALITIES, SUPPORTED_FORMATS
from core.scheduler_manager import scheduler_manager
from core.url_analyzer import URLAnalyzer
from ui.theme_manager import theme_manager


class ScheduleDialog(QDialog):
    """Tabbed modal dialog for scheduling future downloads and managing existing schedules."""

    def __init__(self, initial_url: str = "", initial_title: str = "", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Download Scheduler")
        self.resize(680, 460)
        self.setMinimumSize(540, 380)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self.initial_url = initial_url
        self.initial_title = initial_title
        self._setup_ui()
        self._load_existing_schedules()

    def _setup_ui(self) -> None:
        p = theme_manager.get_palette()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        self.tabs = QTabWidget(self)

        # Tab 1: Schedule New Task
        tab_new = QWidget()
        layout_new = QVBoxLayout(tab_new)
        layout_new.setContentsMargins(16, 16, 16, 16)
        layout_new.setSpacing(12)

        # URL
        lbl_url = QLabel("Media URL:")
        lbl_url.setStyleSheet("font-weight: 600;")
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://...")
        self.url_input.setText(self.initial_url)
        layout_new.addWidget(lbl_url)
        layout_new.addWidget(self.url_input)

        # Title
        lbl_title = QLabel("Task Label / Title (Optional):")
        lbl_title.setStyleSheet("font-weight: 600;")
        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("My Scheduled Download")
        self.title_input.setText(self.initial_title)
        layout_new.addWidget(lbl_title)
        layout_new.addWidget(self.title_input)

        # Date & Time picker
        time_layout = QHBoxLayout()
        time_layout.setSpacing(12)

        lbl_dt = QLabel("Schedule Date & Time:")
        lbl_dt.setStyleSheet("font-weight: 600;")
        self.dt_picker = QDateTimeEdit()
        self.dt_picker.setCalendarPopup(True)
        # Default to 1 hour from now
        default_time = QDateTime.currentDateTime().addSecs(3600)
        self.dt_picker.setDateTime(default_time)
        self.dt_picker.setDisplayFormat("yyyy-MM-dd HH:mm")

        time_layout.addWidget(lbl_dt)
        time_layout.addWidget(self.dt_picker, stretch=1)
        layout_new.addLayout(time_layout)

        # Quality & Format
        opts_layout = QHBoxLayout()
        opts_layout.setSpacing(12)

        lbl_q = QLabel("Quality:")
        lbl_q.setStyleSheet("font-weight: 600;")
        self.combo_q = QComboBox()
        self.combo_q.addItems(SUPPORTED_QUALITIES)

        lbl_f = QLabel("Format:")
        lbl_f.setStyleSheet("font-weight: 600;")
        self.combo_f = QComboBox()
        self.combo_f.addItems(SUPPORTED_FORMATS)

        opts_layout.addWidget(lbl_q)
        opts_layout.addWidget(self.combo_q)
        opts_layout.addWidget(lbl_f)
        opts_layout.addWidget(self.combo_f)
        layout_new.addLayout(opts_layout)

        layout_new.addStretch()

        # Submit button
        btn_sched = QPushButton("⏰ Schedule Download")
        btn_sched.setObjectName("primaryButton")
        btn_sched.setCursor(Qt.PointingHandCursor)
        btn_sched.setFixedHeight(38)
        btn_sched.clicked.connect(self._on_schedule_clicked)
        layout_new.addWidget(btn_sched)

        self.tabs.addTab(tab_new, "⏰ Schedule New Task")

        # Tab 2: Manage Schedules
        tab_list = QWidget()
        layout_list = QVBoxLayout(tab_list)
        layout_list.setContentsMargins(16, 16, 16, 16)
        layout_list.setSpacing(10)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Scheduled Time", "Title / URL", "Quality", "Status"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)

        layout_list.addWidget(self.table)

        list_actions = QHBoxLayout()
        list_actions.setSpacing(10)

        self.btn_cancel_task = QPushButton("Cancel Schedule")
        self.btn_cancel_task.setObjectName("secondaryButton")
        self.btn_cancel_task.setCursor(Qt.PointingHandCursor)
        self.btn_cancel_task.clicked.connect(self._on_cancel_selected)

        self.btn_delete_task = QPushButton("Remove Entry")
        self.btn_delete_task.setObjectName("dangerButton")
        self.btn_delete_task.setCursor(Qt.PointingHandCursor)
        self.btn_delete_task.clicked.connect(self._on_delete_selected)

        btn_refresh = QPushButton("Refresh")
        btn_refresh.setObjectName("secondaryButton")
        btn_refresh.setCursor(Qt.PointingHandCursor)
        btn_refresh.clicked.connect(self._load_existing_schedules)

        list_actions.addWidget(self.btn_cancel_task)
        list_actions.addWidget(self.btn_delete_task)
        list_actions.addStretch()
        list_actions.addWidget(btn_refresh)
        layout_list.addLayout(list_actions)

        self.tabs.addTab(tab_list, "📋 View Schedules")
        layout.addWidget(self.tabs)

        # Footer
        footer = QHBoxLayout()
        close_btn = QPushButton("Close")
        close_btn.setObjectName("secondaryButton")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.accept)
        footer.addStretch()
        footer.addWidget(close_btn)
        layout.addLayout(footer)

    def _on_schedule_clicked(self) -> None:
        url = self.url_input.text().strip()
        if not url or not URLAnalyzer.is_valid_url(url):
            QMessageBox.warning(self, "Invalid URL", "Please enter a valid media URL to schedule.")
            return

        q_dt = self.dt_picker.dateTime()
        target_py_dt = q_dt.toPython()
        if target_py_dt <= datetime.now():
            QMessageBox.warning(self, "Invalid Time", "Scheduled time must be in the future.")
            return

        title = self.title_input.text().strip() or URLAnalyzer.detect_platform(url)
        quality = self.combo_q.currentText()
        output_format = self.combo_f.currentText()

        scheduler_manager.add_schedule(
            url=url,
            title=title,
            scheduled_time=target_py_dt,
            quality=quality,
            output_format=output_format
        )

        QMessageBox.information(
            self,
            "Download Scheduled",
            f"Successfully scheduled '{title}' for {target_py_dt.strftime('%Y-%m-%d %H:%M')}."
        )
        self._load_existing_schedules()
        self.tabs.setCurrentIndex(1)

    def _load_existing_schedules(self) -> None:
        schedules = scheduler_manager.load_schedules()
        self.table.setRowCount(len(schedules))

        for row, s in enumerate(schedules):
            time_str = s.get("scheduled_time_display") or s.get("scheduled_time", "—")
            t_item = QTableWidgetItem(time_str)
            self.table.setItem(row, 0, t_item)

            title_str = s.get("title") or s.get("url", "—")
            self.table.setItem(row, 1, QTableWidgetItem(title_str))

            q_str = s.get("quality", "1080p")
            self.table.setItem(row, 2, QTableWidgetItem(q_str))

            status_str = s.get("status", "pending").capitalize()
            stat_item = QTableWidgetItem(status_str)
            stat_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 3, stat_item)

    def _get_selected_schedule_id(self) -> Optional[str]:
        cur_row = self.table.currentRow()
        if cur_row < 0 or cur_row >= len(scheduler_manager.schedules):
            return None
        return scheduler_manager.schedules[cur_row]["id"]

    def _on_cancel_selected(self) -> None:
        sched_id = self._get_selected_schedule_id()
        if not sched_id:
            QMessageBox.information(self, "No Selection", "Please select a scheduled item to cancel.")
            return

        scheduler_manager.cancel_schedule(sched_id)
        self._load_existing_schedules()

    def _on_delete_selected(self) -> None:
        sched_id = self._get_selected_schedule_id()
        if not sched_id:
            QMessageBox.information(self, "No Selection", "Please select a scheduled item to delete.")
            return

        reply = QMessageBox.question(
            self, "Remove Schedule", "Are you sure you want to remove this scheduled download?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            scheduler_manager.remove_schedule(sched_id)
            self._load_existing_schedules()

