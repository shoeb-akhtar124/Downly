"""
Application Stylesheet module.
Delegates to ThemeManager for live runtime Light/Dark theme switching.
"""
from ui.theme_manager import theme_manager

def get_stylesheet() -> str:
    """Return active compiled stylesheet."""
    return theme_manager.get_stylesheet()

APP_STYLESHEET = theme_manager.get_stylesheet()
