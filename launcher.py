"""
Downly Dedicated Command-Line Launcher.
Entry point for CLI and PATH invocation.
Validates environment, enforces single-instance execution, and launches the GUI.
"""
import sys
import os
import shutil
from pathlib import Path

# Add project root to Python module path
if getattr(sys, "frozen", False):
    PROJECT_ROOT = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    exe_dir = Path(sys.executable).parent
    os.environ["PATH"] = (
        str(exe_dir) + os.path.pathsep +
        str(exe_dir / "_internal") + os.path.pathsep +
        str(PROJECT_ROOT) + os.path.pathsep +
        os.environ.get("PATH", "")
    )
else:
    PROJECT_ROOT = Path(__file__).resolve().parent
    bin_dir = PROJECT_ROOT / "bin"
    if bin_dir.exists():
        os.environ["PATH"] = str(bin_dir) + os.path.pathsep + os.environ.get("PATH", "")

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def preflight_check() -> bool:
    """Validate runtime environment and core dependencies."""
    # Check Python version
    if sys.version_info < (3, 9):
        print(f"[Downly Error] Python 3.9 or newer is required. Found Python {sys.version.split()[0]}")
        return False

    # Check PySide6
    try:
        import PySide6
    except ImportError:
        print("[Downly Error] PySide6 is not installed. Please run: pip install -r requirements.txt")
        return False

    # Check yt-dlp
    try:
        import yt_dlp
    except ImportError:
        print("[Downly Error] yt-dlp is not installed. Please run: pip install -r requirements.txt")
        return False

    # Check FFmpeg
    from app.constants import find_binary
    if not find_binary("ffmpeg"):
        print("[Downly Warning] FFmpeg was not detected. Formats requiring separate stream merge may be limited.")

    return True


def run():
    """Main launcher execution function."""
    if not preflight_check():
        sys.exit(1)

    from app.instance_guard import single_instance_guard
    if not single_instance_guard.acquire():
        print("[Downly] Application is already running. Focus shifted to active window.")
        sys.exit(0)

    # Launch GUI
    from main import main
    sys.exit(main())


if __name__ == "__main__":
    run()

