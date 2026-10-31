"""
Downly - Universal Video Downloader
Entry point script.
"""
import sys
import os
from pathlib import Path

# Add project root to Python search path and configure environment
if getattr(sys, "frozen", False):
    PROJECT_DIR = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    exe_dir = Path(sys.executable).parent
    os.environ["PATH"] = (
        str(exe_dir) + os.path.pathsep +
        str(exe_dir / "_internal") + os.path.pathsep +
        str(PROJECT_DIR) + os.path.pathsep +
        os.environ.get("PATH", "")
    )
else:
    PROJECT_DIR = Path(__file__).resolve().parent
    bin_dir = PROJECT_DIR / "bin"
    if bin_dir.exists():
        os.environ["PATH"] = str(bin_dir) + os.path.pathsep + os.environ.get("PATH", "")

if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIcon

from app.constants import APP_NAME, ROOT_DIR
from app.config import config
from app.instance_guard import single_instance_guard
from ui.main_window import MainWindow
from ui.theme_manager import theme_manager


def main():
    """Initialize and run Downly desktop application."""
    # Ensure Windows taskbar groups and shows correct application icon
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Downly.UniversalVideoDownloader.1.0")
        except Exception:
            pass

    # Enforce single application instance on Windows
    if not single_instance_guard.acquire():
        print("[Downly] Application is already running. Focus shifted to active window.")
        return 0

    # Ensure High-DPI support on Windows displays
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    # Windows AppUserModelID for taskbar icon grouping and official branding
    if sys.platform == "win32":
        try:
            import ctypes
            app_id = f"downly.desktop.downloader.{APP_VERSION}"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyle("Fusion")

    # Set official application icon (multi-resolution downly.ico preferred on Windows)
    ico_path = ROOT_DIR / "assets" / "icons" / "downly.ico"
    png_path = ROOT_DIR / "assets" / "icons" / "downly_icon.png"
    if ico_path.exists():
        app_icon = QIcon(str(ico_path))
    elif png_path.exists():
        app_icon = QIcon(str(png_path))
    else:
        app_icon = QIcon()

    if not app_icon.isNull():
        app.setWindowIcon(app_icon)

    # Set modern default font
    font = QFont("Segoe UI", 10)
    font.setStyleHint(QFont.SansSerif)
    app.setFont(font)

    # Apply global Windows styling stylesheet and matching palette
    theme_manager.update_application_palette(app)
    app.setStyleSheet(theme_manager.get_stylesheet())

    # Launch main window
    window = MainWindow()
    window.show()
    window.raise_()
    window.activateWindow()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
