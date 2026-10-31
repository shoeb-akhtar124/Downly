"""
Main Application Window.
Coordinates single navigation sidebar, stacked content pages, clipboard monitor,
scheduled download trigger, and responsive toasts.
Completely removes the bottom status bar and categories sidebar.
Supports live dynamic Light and Dark mode switching.
"""
from pathlib import Path
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QStackedWidget, QLabel
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon

from app.constants import APP_NAME, APP_VERSION, ROOT_DIR
from core.download_manager import download_manager, DownloadTask
from core.clipboard_monitor import clipboard_monitor
from core.scheduler_manager import scheduler_manager
from ui.theme_manager import theme_manager
from ui.components.sidebar import Sidebar
from ui.components.clipboard_toast import ClipboardToast
from ui.dashboard_page import DashboardPage
from ui.downloader_page import DownloaderPage
from ui.queue_page import QueuePage
from ui.history_page import HistoryPage
from ui.settings_page import SettingsPage


class MainWindow(QMainWindow):
    """Main desktop application window for Downly with single left navigation sidebar."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1180, 720)
        self.setMinimumSize(940, 600)

        # Set Official Application Icon (downly.ico preferred on Windows)
        ico_path = ROOT_DIR / "assets" / "icons" / "downly.ico"
        png_path = ROOT_DIR / "assets" / "icons" / "downly_icon.png"
        if ico_path.exists():
            self.setWindowIcon(QIcon(str(ico_path)))
        elif png_path.exists():
            self.setWindowIcon(QIcon(str(png_path)))

        self._setup_ui()
        self._connect_signals()

        # Start clipboard monitor if enabled
        clipboard_monitor.update_state()

    def _setup_ui(self) -> None:
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Single Left Vertical Navigation Sidebar (Icon + Label)
        self.sidebar = Sidebar(self)
        main_layout.addWidget(self.sidebar)

        # Right Content Area (Toast Banner + Stacked Pages)
        right_container = QWidget(self)
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # Clipboard Notification Toast (Initially hidden)
        self.clipboard_toast = ClipboardToast(self)
        right_layout.addWidget(self.clipboard_toast)

        # Main Content Pages (StackedWidget with full available width)
        self.pages_stack = QStackedWidget(self)

        self.dashboard_page = DashboardPage(self)
        self.downloader_page = DownloaderPage(self)
        self.queue_page = QueuePage(self)
        self.history_page = HistoryPage(self)
        self.settings_page = SettingsPage(self)

        self.pages_stack.addWidget(self.dashboard_page)    # Index 0
        self.pages_stack.addWidget(self.downloader_page)   # Index 1
        self.pages_stack.addWidget(self.queue_page)        # Index 2
        self.pages_stack.addWidget(self.history_page)      # Index 3
        self.pages_stack.addWidget(self.settings_page)      # Index 4

        right_layout.addWidget(self.pages_stack, stretch=1)
        main_layout.addWidget(right_container, stretch=1)

        # Wire up sidebar navigation
        self.sidebar.page_changed.connect(self._on_navigation_change)

    def _connect_signals(self) -> None:
        """Connect cross-page events and notifications."""
        self.dashboard_page.navigate_requested.connect(self.sidebar.set_current_index)
        self.dashboard_page.quick_analyze_requested.connect(self._on_dashboard_quick_analyze)
        self.settings_page.settings_updated.connect(self.downloader_page.apply_defaults)

        # Download Manager lifecycle
        download_manager.task_added.connect(self._on_task_activity)
        download_manager.task_completed.connect(self._on_global_task_completed)
        download_manager.task_status_changed.connect(self._on_task_activity)

        # Clipboard Monitoring Integration
        clipboard_monitor.supported_url_detected.connect(self._on_clipboard_url_detected)
        self.clipboard_toast.analyze_requested.connect(self._on_toast_analyze_requested)

    def _on_clipboard_url_detected(self, url: str, platform: str) -> None:
        """Show non-intrusive banner when supported link is copied."""
        self.clipboard_toast.show_url(url, platform)

    def _on_toast_analyze_requested(self, url: str) -> None:
        """User confirmed link analysis from clipboard banner."""
        self.sidebar.set_current_index(1)
        self.downloader_page.url_input.setText(url)
        self.downloader_page._on_analyze_clicked()

    def _on_dashboard_quick_analyze(self, url: str) -> None:
        """Receive quick URL from dashboard and analyze in downloader."""
        self.downloader_page.url_input.setText(url)
        self.downloader_page._on_analyze_clicked()

    def _on_task_activity(self, *args) -> None:
        """Refresh dashboard stats on download events."""
        self.dashboard_page.refresh_stats()

    def _on_global_task_completed(self, task: DownloadTask) -> None:
        """Update history and dashboard stats on completion."""
        self.dashboard_page.refresh_stats()
        self.history_page.refresh_history()

    def _on_navigation_change(self, index: int) -> None:
        """Switch active page in stacked widget without any bottom status bar."""
        self.pages_stack.setCurrentIndex(index)

        # Refresh dynamic content when switching
        if index == 0:
            self.dashboard_page.refresh_stats()
        elif index == 2:
            self.queue_page.refresh_table()
        elif index == 3:
            self.history_page.refresh_history()

    def closeEvent(self, event) -> None:
        """Handle application close by cleanly aborting active workers."""
        clipboard_monitor.stop()
        for tid in list(download_manager.active_workers.keys()):
            download_manager.cancel_download(tid)
        for worker in list(download_manager.active_workers.values()):
            worker.wait(1000)
        event.accept()
