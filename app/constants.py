"""
Application constants, theme palette, and configuration defaults.
Implements the refined Premium Light Windows Desktop theme and extended codec options.
"""
import os
import sys
import shutil
from pathlib import Path
from typing import Optional

# Application Metadata
APP_NAME = "Downly"
APP_SUBTITLE = "Universal Video Downloader"
APP_VERSION = "1.0.0"
DEFAULT_GITHUB_REPO = "user/Downly"

# Base Application (Installation) Directories
def _resolve_root_dir() -> Path:
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass and (Path(meipass) / "assets").exists():
            return Path(meipass)
        exe_dir = Path(sys.executable).parent
        if (exe_dir / "assets").exists():
            return exe_dir
        if (exe_dir / "_internal" / "assets").exists():
            return exe_dir / "_internal"
        return Path(meipass) if meipass else exe_dir
    return Path(__file__).resolve().parent.parent

ROOT_DIR = _resolve_root_dir()
ASSETS_DIR = ROOT_DIR / "assets"


def find_binary(name: str) -> Optional[str]:
    """Locate binary executable, checking bundled directories before system PATH."""
    exe_name = f"{name}.exe" if sys.platform == "win32" and not name.endswith(".exe") else name

    # 1. Check beside executable (PyInstaller onedir root)
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        if (exe_dir / exe_name).exists():
            return str(exe_dir / exe_name)
        if (exe_dir / "_internal" / exe_name).exists():
            return str(exe_dir / "_internal" / exe_name)
        if (exe_dir / "bin" / exe_name).exists():
            return str(exe_dir / "bin" / exe_name)
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass and (Path(meipass) / exe_name).exists():
            return str(Path(meipass) / exe_name)

    # 2. Check local project bin directory
    project_bin = ROOT_DIR / "bin" / exe_name
    if project_bin.exists():
        return str(project_bin)

    # 3. Fallback to system PATH
    return shutil.which(name)

# Persistent User Data Directories (Outside installation directory)
if sys.platform == "win32":
    LOCAL_APPDATA = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    USER_DATA_DIR = LOCAL_APPDATA / "Downly"
else:
    USER_DATA_DIR = Path.home() / ".downly"

USER_STORAGE_DIR = USER_DATA_DIR / "storage"
USER_UPDATES_DIR = USER_DATA_DIR / "updates"
USER_STAGED_UPDATES_DIR = USER_UPDATES_DIR / "staged"
USER_BACKUP_UPDATES_DIR = USER_UPDATES_DIR / "backups"
USER_LOGS_DIR = USER_DATA_DIR / "logs"
USER_CACHE_DIR = USER_DATA_DIR / "cache"
THUMBNAILS_CACHE_DIR = USER_CACHE_DIR / "thumbnails"

# Default user media directory
USER_DOWNLOADS_DIR = Path.home() / "Downloads" / "Downly"

# Persistent Storage Files
SETTINGS_FILE = USER_STORAGE_DIR / "settings.json"
HISTORY_FILE = USER_STORAGE_DIR / "history.json"
SCHEDULES_FILE = USER_STORAGE_DIR / "schedules.json"
APP_LOG_FILE = USER_LOGS_DIR / "downly.log"

# Legacy paths for migration
LEGACY_STORAGE_DIR = ROOT_DIR / "storage"
LEGACY_SETTINGS_FILE = LEGACY_STORAGE_DIR / "settings.json"
LEGACY_HISTORY_FILE = LEGACY_STORAGE_DIR / "history.json"
LEGACY_DOWNLOADS_DIR = ROOT_DIR / "downloads"

# Neon Emerald Dark Theme Palette
COLOR_BG_MAIN = "#080B0A"          # Main dark background
COLOR_SIDEBAR = "#00C98B"          # Emerald green sidebar
COLOR_BG_SECONDARY = "#111513"     # Secondary background / categories panel
COLOR_BG_CARD = "#171C19"          # Dark card surface
COLOR_BG_TABLE = "#101411"         # Table background
COLOR_PRIMARY_ACCENT = "#00E69A"   # Primary neon emerald accent
COLOR_SECONDARY_ACCENT = "#00B87A" # Secondary emerald accent
COLOR_TEXT_MAIN = "#F5F7F6"        # Main light text
COLOR_TEXT_SECONDARY = "#A0AAA4"   # Secondary text / labels
COLOR_BORDER = "#29332E"           # Subtle dark border
COLOR_BORDER_FOCUS = "#00E69A"     # Active focus border
COLOR_SUCCESS = "#16C784"          # Emerald success
COLOR_WARNING = "#FFB547"          # Amber warning
COLOR_ERROR = "#FF5C68"            # Red error

# Backward compatibility aliases
COLOR_BG_WINDOW = COLOR_BG_MAIN
COLOR_BG_SIDEBAR = COLOR_SIDEBAR
COLOR_SURFACE_LIGHT = COLOR_BG_SECONDARY
COLOR_SURFACE_HOVER = "#1B221E"
COLOR_TEXT_PRIMARY = COLOR_TEXT_MAIN
COLOR_TEXT_MUTED = "#6C7A73"
COLOR_PRIMARY_BLUE = COLOR_PRIMARY_ACCENT
COLOR_PRIMARY_HOVER = COLOR_SECONDARY_ACCENT
COLOR_PRIMARY_LIGHT = "#0D2B20"
COLOR_PRIMARY_BORDER = COLOR_PRIMARY_ACCENT
COLOR_DANGER = COLOR_ERROR

# Supported Options
SUPPORTED_QUALITIES = [
    "Best Available",
    "2160p (4K)",
    "1440p (2K)",
    "1080p (Full HD)",
    "720p (HD)",
    "480p (SD)",
    "360p (Low)"
]

SUPPORTED_FORMATS = [
    "MP4",
    "MKV",
    "WebM",
    "MOV",
    "MP3 (Audio Only)"
]

SUPPORTED_VIDEO_CODECS = [
    "Keep Original Codec",
    "H.264 (AVC)",
    "H.265 (HEVC)",
    "AV1",
    "VP9"
]

SUPPORTED_AUDIO_CODECS = [
    "Keep Original",
    "AAC",
    "MP3",
    "Opus",
    "FLAC"
]

# Legacy alias for backward compatibility
SUPPORTED_CODECS = SUPPORTED_VIDEO_CODECS

SUPPORTED_SUBTITLE_LANGUAGES = [
    ("English", "en"),
    ("Spanish", "es"),
    ("French", "fr"),
    ("German", "de"),
    ("Italian", "it"),
    ("Portuguese", "pt"),
    ("Russian", "ru"),
    ("Japanese", "ja"),
    ("Korean", "ko"),
    ("Chinese", "zh"),
    ("Arabic", "ar"),
    ("Hindi", "hi")
]

# Default Application Preferences
DEFAULT_SETTINGS = {
    "download_dir": str(USER_DOWNLOADS_DIR),
    "default_quality": "1080p (Full HD)",
    "default_format": "MP4",
    "default_video_codec": "Keep Original Codec",
    "default_audio_codec": "Keep Original",
    "max_concurrent_downloads": "Automatic",
    "retry_attempts": "Automatic",
    "auto_retry": True,
    "retry_delay": "Automatic",
    "clipboard_monitoring": False,
    "connection_timeout": 30,
    "concurrent_fragments": "Automatic",
    "auto_hevc_conversion": False,
    "auto_conversion_enabled": True,
    "preserve_original_video": False,
    "hardware_acceleration": "Auto / Software",
    "max_concurrent_conversions": 2,
    "subtitles_enabled": False,
    "subtitle_language": "en",
    "subtitle_format": "srt",
    "embed_subtitles": False,
    "check_updates_on_startup": True,
    "github_repo": DEFAULT_GITHUB_REPO,
    "theme": "dark"
}
