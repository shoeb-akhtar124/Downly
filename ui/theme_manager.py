"""
Theme Manager Module for Downly.
Centralized management of Dark Mode (Neon Emerald Dark) and Light Mode (Emerald Light).
Supports dynamic runtime theme switching without application restart and full Qt palette synchronization.
"""
from pathlib import Path
from typing import Dict, Any
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPalette, QColor

from app.config import config
from app.constants import ROOT_DIR

# Chevron Vector Icon Paths
CHEVRON_DARK = (ROOT_DIR / "assets" / "icons" / "chevron_dark.svg").as_posix()
CHEVRON_DARK_HOVER = (ROOT_DIR / "assets" / "icons" / "chevron_dark_hover.svg").as_posix()
CHEVRON_LIGHT = (ROOT_DIR / "assets" / "icons" / "chevron_light.svg").as_posix()
CHEVRON_LIGHT_HOVER = (ROOT_DIR / "assets" / "icons" / "chevron_light_hover.svg").as_posix()
CHECKBOX_CHECK = (ROOT_DIR / "assets" / "icons" / "checkbox_check.svg").as_posix()

# Palette Definitions per User Specification
THEME_PALETTES: Dict[str, Dict[str, str]] = {
    "dark": {
        "name": "dark",
        "bg_main": "#080B0A",
        "sidebar_bg": "#0C110E",
        "card_bg": "#141A16",
        "surface_sec": "#19211C",
        "input_bg": "#101512",
        "table_bg": "#101512",
        "primary_accent": "#00D99A",
        "secondary_accent": "#00B87A",
        "main_text": "#F5F7F6",
        "secondary_text": "#A0AAA4",
        "borders": "#29352E",
        "borders_hover": "#3E4E45",
        "success": "#16C784",
        "warning": "#FFB547",
        "error": "#FF5C68",
        "checkbox_check": CHECKBOX_CHECK,
        # Navigation
        "nav_normal_text": "#A0AAA4",
        "nav_normal_icon": "#84918A",
        "nav_hover_bg": "#111C17",
        "nav_hover_text": "#E8F5EE",
        "nav_sel_bg": "#14251E",
        "nav_sel_text": "#00D99A",
        "nav_sel_indicator": "#00D99A",
        # Specific Buttons (Dark Mode: WHITE text on solid emerald)
        # Analyze Button
        "btn_analyze_bg": "#00875A",
        "btn_analyze_text": "#FFFFFF",
        "btn_analyze_border": "#00A86B",
        "btn_analyze_hover_bg": "#009B70",
        "btn_analyze_hover_text": "#FFFFFF",
        "btn_analyze_hover_border": "#00D99A",
        "btn_analyze_pressed_bg": "#007352",
        # Download Button
        "btn_download_bg": "#00875A",
        "btn_download_text": "#FFFFFF",
        "btn_download_border": "#00A86B",
        "btn_download_hover_bg": "#009B70",
        "btn_download_hover_text": "#FFFFFF",
        "btn_download_pressed_bg": "#007352",
        # Save Preferences Button
        "btn_save_bg": "#00875A",
        "btn_save_text": "#FFFFFF",
        "btn_save_border": "#00A86B",
        "btn_save_hover_bg": "#009B70",
        "btn_save_hover_text": "#FFFFFF",
        "btn_save_pressed_bg": "#007352",
        # Generic Primary Button
        "btn_primary_bg": "#00875A",
        "btn_primary_text": "#FFFFFF",
        "btn_primary_border": "#00A86B",
        "btn_primary_hover": "#009B70",
        "btn_primary_hover_text": "#FFFFFF",
        # Secondary Buttons
        "btn_sec_bg": "#141A16",
        "btn_sec_text": "#F5F7F6",
        "btn_sec_border": "#29352E",
        "btn_sec_hover": "#19211C",
        "btn_sec_hover_text": "#00FFA3",
        # Action Buttons
        "btn_action_bg": "#19211C",
        "btn_action_text": "#00FFA3",
        "btn_action_border": "#29352E",
        "btn_action_hover": "#14251E",
        # Danger Buttons
        "btn_danger_bg": "#2B1417",
        "btn_danger_text": "#FF5C68",
        "btn_danger_border": "#4A2026",
        "btn_danger_hover": "#3B1B20",
        # Dropdowns
        "dropdown_chevron": CHEVRON_DARK,
        "dropdown_chevron_hover": CHEVRON_DARK_HOVER,
        "dropdown_popup_bg": "#141A16",
        "dropdown_popup_sel_bg": "#19251F",
        "dropdown_popup_sel_text": "#00FFA3",
        # Misc
        "progress_bg": "#101512",
        "scrollbar_handle": "#29352E",
        "scrollbar_hover": "#00D99A",
        "badge_bg": "#141A16",
        "badge_text": "#A0AAA4",
        "badge_border": "#29352E",
        "dialog_bg": "#0C110E",
        "menu_bg": "#141A16",
        "menu_hover": "#19211C",
    },
    "light": {
        "name": "light",
        "bg_main": "#F3F5F4",
        "sidebar_bg": "#FFFFFF",
        "card_bg": "#FFFFFF",
        "surface_sec": "#EDF3EF",
        "input_bg": "#FFFFFF",
        "table_bg": "#FFFFFF",
        "primary_accent": "#009B70",
        "secondary_accent": "#00865F",
        "main_text": "#17211B",
        "secondary_text": "#64736A",
        "borders": "#DCE5DF",
        "borders_hover": "#B8CBBE",
        "success": "#159B62",
        "warning": "#D99020",
        "error": "#DC4545",
        "checkbox_check": CHECKBOX_CHECK,
        # Navigation
        "nav_normal_text": "#64736A",
        "nav_normal_icon": "#64736A",
        "nav_hover_bg": "#F0F6F2",
        "nav_hover_text": "#17211B",
        "nav_sel_bg": "#E4F5ED",
        "nav_sel_text": "#008F67",
        "nav_sel_indicator": "#009B70",
        # Specific Buttons (Light Mode: BLACK text on vibrant emerald)
        # Analyze Button
        "btn_analyze_bg": "#00D99A",
        "btn_analyze_text": "#17211B",
        "btn_analyze_border": "#00B87A",
        "btn_analyze_hover_bg": "#00FFAD",
        "btn_analyze_hover_text": "#17211B",
        "btn_analyze_hover_border": "#00D99A",
        "btn_analyze_pressed_bg": "#00B87A",
        # Download Button
        "btn_download_bg": "#00D99A",
        "btn_download_text": "#17211B",
        "btn_download_border": "#00B87A",
        "btn_download_hover_bg": "#00FFAD",
        "btn_download_hover_text": "#17211B",
        "btn_download_pressed_bg": "#00B87A",
        # Save Preferences Button
        "btn_save_bg": "#00D99A",
        "btn_save_text": "#17211B",
        "btn_save_border": "#00B87A",
        "btn_save_hover_bg": "#00FFAD",
        "btn_save_hover_text": "#17211B",
        "btn_save_pressed_bg": "#00B87A",
        # Generic Primary Button
        "btn_primary_bg": "#00D99A",
        "btn_primary_text": "#17211B",
        "btn_primary_border": "#00B87A",
        "btn_primary_hover": "#00FFAD",
        "btn_primary_hover_text": "#17211B",
        # Secondary Buttons
        "btn_sec_bg": "#FFFFFF",
        "btn_sec_text": "#17211B",
        "btn_sec_border": "#DCE5DF",
        "btn_sec_hover": "#EDF3EF",
        "btn_sec_hover_text": "#009B70",
        # Action Buttons
        "btn_action_bg": "#EDF3EF",
        "btn_action_text": "#008F67",
        "btn_action_border": "#DCE5DF",
        "btn_action_hover": "#E4F5ED",
        # Danger Buttons
        "btn_danger_bg": "#FDE8E8",
        "btn_danger_text": "#DC4545",
        "btn_danger_border": "#F8B4B4",
        "btn_danger_hover": "#FCD0D0",
        # Dropdowns
        "dropdown_chevron": CHEVRON_LIGHT,
        "dropdown_chevron_hover": CHEVRON_LIGHT_HOVER,
        "dropdown_popup_bg": "#FFFFFF",
        "dropdown_popup_sel_bg": "#E4F5ED",
        "dropdown_popup_sel_text": "#008F67",
        # Misc
        "progress_bg": "#EDF3EF",
        "scrollbar_handle": "#DCE5DF",
        "scrollbar_hover": "#009B70",
        "badge_bg": "#EDF3EF",
        "badge_text": "#64736A",
        "badge_border": "#DCE5DF",
        "dialog_bg": "#FFFFFF",
        "menu_bg": "#FFFFFF",
        "menu_hover": "#EDF3EF",
    }
}


def build_stylesheet(p: Dict[str, str]) -> str:
    """Generate complete application QSS from a palette definition."""
    return f"""
/* Base Application Typography & Window Colors */
QWidget {{
    font-family: "Segoe UI Variable Text", "Segoe UI", -apple-system, BlinkMacSystemFont, "Roboto", sans-serif;
    font-size: 13px;
    color: {p['main_text']};
    background-color: transparent;
}}

QMainWindow {{
    background-color: {p['bg_main']};
}}

QDialog {{
    background-color: {p['dialog_bg']};
    color: {p['main_text']};
}}

/* Scroll Area Base */
QScrollArea {{
    background: transparent;
    border: none;
}}

QScrollArea > QWidget > QWidget {{
    background: transparent;
}}

/* Redesigned Single Left Navigation Sidebar */
#sidebarWidget {{
    background-color: {p['sidebar_bg']};
    border-right: 1px solid {p['borders']};
}}

#brandTitle {{
    font-size: 19px;
    font-weight: 800;
    color: {p['main_text']};
    letter-spacing: -0.3px;
}}

#navButton {{
    background-color: transparent;
    color: {p['nav_normal_text']};
    border: none;
    border-left: 3px solid transparent;
    border-radius: 6px;
    padding: 10px 14px;
    text-align: left;
    font-size: 13px;
    font-weight: 600;
}}

#navButton:hover {{
    background-color: {p['nav_hover_bg']};
    color: {p['nav_hover_text']};
    border-left: 3px solid transparent;
}}

#navButton:checked, #navButton[active="true"] {{
    background-color: {p['nav_sel_bg']};
    color: {p['nav_sel_text']};
    border-left: 3px solid {p['nav_sel_indicator']};
    font-weight: 700;
}}

#versionLabel {{
    font-size: 11px;
    font-weight: 600;
    color: {p['secondary_text']};
    padding: 0px 4px;
}}

/* Page Headers */
#pageTitle {{
    font-size: 22px;
    font-weight: 800;
    color: {p['main_text']};
    letter-spacing: -0.3px;
}}

#pageSubtitle {{
    font-size: 13px;
    color: {p['secondary_text']};
}}

/* Cards & Surfaces */
QFrame#cardFrame {{
    background-color: {p['card_bg']};
    border: 1px solid {p['borders']};
    border-radius: 10px;
}}

QFrame#surfaceCard {{
    background-color: {p['surface_sec']};
    border: 1px solid {p['borders']};
    border-radius: 8px;
}}

#cardTitle {{
    font-size: 15px;
    font-weight: 700;
    color: {p['main_text']};
}}

#cardSubtitle {{
    font-size: 12px;
    color: {p['secondary_text']};
}}

/* Input Fields */
QLineEdit {{
    background-color: {p['input_bg']};
    border: 1px solid {p['borders']};
    border-radius: 8px;
    padding: 8px 12px;
    color: {p['main_text']};
    font-size: 13px;
    selection-background-color: {p['primary_accent']};
    selection-color: {p['btn_primary_text']};
}}

QLineEdit:hover {{
    border-color: {p['borders_hover']};
}}

QLineEdit:focus {{
    border: 1.5px solid {p['primary_accent']};
}}

QLineEdit:disabled, QLineEdit:read-only {{
    background-color: {p['surface_sec']};
    color: {p['secondary_text']};
    border-color: {p['borders']};
}}

QTextEdit {{
    background-color: {p['input_bg']};
    border: 1px solid {p['borders']};
    border-radius: 8px;
    padding: 8px 12px;
    color: {p['main_text']};
    font-size: 12px;
    selection-background-color: {p['primary_accent']};
    selection-color: {p['btn_primary_text']};
}}

QTextEdit:focus {{
    border: 1.5px solid {p['primary_accent']};
}}

/* Dropdown Comboboxes */
QComboBox {{
    background-color: {p['input_bg']};
    border: 1px solid {p['borders']};
    border-radius: 8px;
    padding: 7px 32px 7px 12px;
    color: {p['main_text']};
    font-size: 13px;
    min-height: 22px;
}}

QComboBox:hover {{
    border-color: {p['borders_hover']};
}}

QComboBox:focus {{
    border: 1.5px solid {p['primary_accent']};
}}

QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 28px;
    border-left: none;
    background: transparent;
}}

/* Clear Downward-facing Chevron Indicator */
QComboBox::down-arrow {{
    image: url({p['dropdown_chevron']});
    width: 10px;
    height: 6px;
    margin-right: 10px;
}}

QComboBox::down-arrow:hover {{
    image: url({p['dropdown_chevron_hover']});
}}

/* Dropdown popup container & item views */
QComboBoxPrivateContainer {{
    background-color: {p['dropdown_popup_bg']};
    border: 1px solid {p['borders']};
    border-radius: 8px;
}}

QComboBox QAbstractItemView,
QComboBox QListView {{
    background-color: {p['dropdown_popup_bg']};
    border: 1px solid {p['borders']};
    border-radius: 8px;
    selection-background-color: {p['dropdown_popup_sel_bg']};
    selection-color: {p['dropdown_popup_sel_text']};
    color: {p['main_text']};
    outline: none;
    padding: 4px;
}}

QComboBox QAbstractItemView::item,
QComboBox QListView::item {{
    background-color: transparent;
    color: {p['main_text']};
    padding: 6px 10px;
    border-radius: 4px;
    min-height: 22px;
}}

QComboBox QAbstractItemView::item:selected,
QComboBox QListView::item:selected,
QComboBox QAbstractItemView::item:hover,
QComboBox QListView::item:hover {{
    background-color: {p['dropdown_popup_sel_bg']};
    color: {p['dropdown_popup_sel_text']};
}}

/* SpinBoxes */
QSpinBox {{
    background-color: {p['input_bg']};
    border: 1px solid {p['borders']};
    border-radius: 8px;
    padding: 7px 12px;
    color: {p['main_text']};
    font-size: 13px;
    min-height: 22px;
}}

QSpinBox:hover {{
    border-color: {p['borders_hover']};
}}

QSpinBox:focus {{
    border: 1.5px solid {p['primary_accent']};
}}

/* Checkboxes */
QCheckBox {{
    spacing: 8px;
    color: {p['main_text']};
    font-size: 13px;
}}

QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border: 1px solid {p['borders']};
    border-radius: 4px;
    background-color: {p['input_bg']};
}}

QCheckBox::indicator:hover {{
    border-color: {p['primary_accent']};
}}

QCheckBox::indicator:checked {{
    background-color: {p['primary_accent']};
    border-color: {p['primary_accent']};
    image: url({p['checkbox_check']});
}}

QCheckBox::indicator:checked:hover {{
    background-color: {p['secondary_accent']};
    border-color: {p['secondary_accent']};
    image: url({p['checkbox_check']});
}}

/* Base PushButton */
QPushButton {{
    font-family: "Segoe UI Variable Text", "Segoe UI", -apple-system, BlinkMacSystemFont, "Roboto", sans-serif;
    font-size: 13px;
    font-weight: 600;
    border-radius: 8px;
    padding: 8px 16px;
    outline: none;
}}

/* 1. ANALYZE URL BUTTON (#analyzeButton) */
QPushButton#analyzeButton {{
    background-color: {p['btn_analyze_bg']};
    color: {p['btn_analyze_text']};
    border: 1.5px solid {p['btn_analyze_border']};
    border-radius: 8px;
    padding: 9px 18px;
    font-size: 13px;
    font-weight: 700;
}}

QPushButton#analyzeButton:hover {{
    background-color: {p['btn_analyze_hover_bg']};
    color: {p['btn_analyze_hover_text']};
    border-color: {p['btn_analyze_hover_border']};
}}

QPushButton#analyzeButton:pressed {{
    background-color: {p['btn_analyze_pressed_bg']};
    color: {p['btn_analyze_text']};
    border-color: {p['secondary_accent']};
}}

QPushButton#analyzeButton:disabled {{
    background-color: {p['surface_sec']};
    color: {p['secondary_text']};
    border: 1px solid {p['borders']};
}}

/* 2. DOWNLOAD BUTTON (#downloadButton) */
QPushButton#downloadButton {{
    background-color: {p['btn_download_bg']};
    color: {p['btn_download_text']};
    border: 1.5px solid {p['btn_download_border']};
    border-radius: 8px;
    padding: 10px 20px;
    font-size: 14px;
    font-weight: 700;
}}

QPushButton#downloadButton:hover {{
    background-color: {p['btn_download_hover_bg']};
    color: {p['btn_download_hover_text']};
    border-color: {p['btn_download_border']};
}}

QPushButton#downloadButton:pressed {{
    background-color: {p['btn_download_pressed_bg']};
    color: {p['btn_download_text']};
    border-color: {p['secondary_accent']};
}}

QPushButton#downloadButton:disabled {{
    background-color: {p['surface_sec']};
    color: {p['secondary_text']};
    border: 1px solid {p['borders']};
}}

/* 3. SAVE PREFERENCES BUTTON (#saveButton) */
QPushButton#saveButton {{
    background-color: {p['btn_save_bg']};
    color: {p['btn_save_text']};
    border: 1.5px solid {p['btn_save_border']};
    border-radius: 8px;
    padding: 9px 18px;
    font-size: 13px;
    font-weight: 700;
}}

QPushButton#saveButton:hover {{
    background-color: {p['btn_save_hover_bg']};
    color: {p['btn_save_hover_text']};
    border-color: {p['btn_save_border']};
}}

QPushButton#saveButton:pressed {{
    background-color: {p['btn_save_pressed_bg']};
    color: {p['btn_save_text']};
    border-color: {p['secondary_accent']};
}}

QPushButton#saveButton:disabled {{
    background-color: {p['surface_sec']};
    color: {p['secondary_text']};
    border: 1px solid {p['borders']};
}}

/* 4. GENERIC PRIMARY BUTTON (#primaryButton) */
QPushButton#primaryButton {{
    background-color: {p['btn_primary_bg']};
    color: {p['btn_primary_text']};
    border: 1.5px solid {p['btn_primary_border']};
    border-radius: 8px;
    padding: 9px 18px;
    font-size: 13px;
    font-weight: 700;
}}

QPushButton#primaryButton:hover {{
    background-color: {p['btn_primary_hover']};
    border-color: {p['primary_accent']};
    color: {p['btn_primary_hover_text']};
}}

QPushButton#primaryButton:pressed {{
    background-color: {p['secondary_accent']};
    border-color: {p['secondary_accent']};
    color: {p['btn_primary_text']};
}}

QPushButton#primaryButton:disabled {{
    background-color: {p['surface_sec']};
    color: {p['secondary_text']};
    border: 1px solid {p['borders']};
}}

/* 5. SECONDARY BUTTONS (#secondaryButton, pasteButton, clearButton, batchButton, scheduleButton, resetButton) */
QPushButton#secondaryButton, QPushButton#pasteButton, QPushButton#clearButton, QPushButton#batchButton, QPushButton#scheduleButton, QPushButton#resetButton {{
    background-color: {p['btn_sec_bg']};
    color: {p['btn_sec_text']};
    border: 1px solid {p['btn_sec_border']};
    border-radius: 8px;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 600;
}}

QPushButton#secondaryButton:hover, QPushButton#pasteButton:hover, QPushButton#clearButton:hover, QPushButton#batchButton:hover, QPushButton#scheduleButton:hover, QPushButton#resetButton:hover {{
    background-color: {p['btn_sec_hover']};
    color: {p['btn_sec_hover_text']};
    border-color: {p['primary_accent']};
}}

QPushButton#secondaryButton:pressed, QPushButton#pasteButton:pressed, QPushButton#clearButton:pressed, QPushButton#batchButton:pressed, QPushButton#scheduleButton:pressed, QPushButton#resetButton:pressed {{
    background-color: {p['surface_sec']};
}}

QPushButton#secondaryButton:disabled, QPushButton#pasteButton:disabled, QPushButton#clearButton:disabled, QPushButton#batchButton:disabled, QPushButton#scheduleButton:disabled, QPushButton#resetButton:disabled {{
    background-color: {p['surface_sec']};
    color: {p['secondary_text']};
    border-color: {p['borders']};
}}

/* 6. ACTION BUTTONS (#actionButton, Open, Folder, Table pills) */
QPushButton#actionButton {{
    background-color: {p['btn_action_bg']};
    color: {p['btn_action_text']};
    border: 1px solid {p['btn_action_border']};
    border-radius: 6px;
    padding: 5px 12px;
    font-size: 12px;
    font-weight: 600;
}}

QPushButton#actionButton:hover {{
    background-color: {p['btn_action_hover']};
    border-color: {p['primary_accent']};
}}

QPushButton#actionButton:pressed {{
    background-color: {p['surface_sec']};
}}

QPushButton#actionButton:disabled {{
    background-color: {p['surface_sec']};
    color: {p['secondary_text']};
    border-color: {p['borders']};
}}

/* 7. THEME TOGGLE BUTTON (#themeToggleButton) */
QPushButton#themeToggleButton {{
    background-color: {p['btn_sec_bg']};
    color: {p['main_text']};
    border: 1px solid {p['btn_sec_border']};
    border-radius: 8px;
    padding: 7px 14px;
    font-size: 13px;
    font-weight: 600;
}}

QPushButton#themeToggleButton:hover {{
    background-color: {p['btn_sec_hover']};
    color: {p['primary_accent']};
    border-color: {p['primary_accent']};
}}

/* 8. DANGER BUTTONS (#dangerButton) */
QPushButton#dangerButton {{
    background-color: {p['btn_danger_bg']};
    color: {p['btn_danger_text']};
    border: 1px solid {p['btn_danger_border']};
    border-radius: 6px;
    padding: 5px 12px;
    font-size: 12px;
    font-weight: 600;
}}

QPushButton#dangerButton:hover {{
    background-color: {p['btn_danger_hover']};
}}

/* Tables */
QTableWidget {{
    background-color: {p['table_bg']};
    alternate-background-color: {p['surface_sec']};
    border: 1px solid {p['borders']};
    border-radius: 8px;
    gridline-color: {p['borders']};
    color: {p['main_text']};
    font-size: 12px;
    selection-background-color: {p['nav_sel_bg']};
    selection-color: {p['nav_sel_text']};
}}

QHeaderView::section {{
    background-color: {p['surface_sec']};
    color: {p['secondary_text']};
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    padding: 8px 10px;
    border: none;
    border-bottom: 1px solid {p['borders']};
    border-right: 1px solid {p['borders']};
}}

QTableCornerButton::section {{
    background-color: {p['surface_sec']};
    border: none;
}}

/* Progress Bars */
QProgressBar {{
    background-color: {p['progress_bg']};
    border: 1px solid {p['borders']};
    border-radius: 6px;
    height: 12px;
    text-align: center;
    color: {p['main_text']};
    font-size: 10px;
    font-weight: 700;
}}

QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {p['secondary_accent']}, stop:1 {p['primary_accent']});
    border-radius: 5px;
}}

/* ScrollBars */
QScrollBar:vertical {{
    background-color: {p['bg_main']};
    width: 8px;
    margin: 0px;
    border-radius: 4px;
}}

QScrollBar::handle:vertical {{
    background-color: {p['scrollbar_handle']};
    min-height: 24px;
    border-radius: 4px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {p['scrollbar_hover']};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QScrollBar:horizontal {{
    background-color: {p['bg_main']};
    height: 8px;
    margin: 0px;
    border-radius: 4px;
}}

QScrollBar::handle:horizontal {{
    background-color: {p['scrollbar_handle']};
    min-width: 24px;
    border-radius: 4px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: {p['scrollbar_hover']};
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
}}

/* Context Menus */
QMenu {{
    background-color: {p['menu_bg']};
    border: 1px solid {p['borders']};
    border-radius: 8px;
    padding: 6px;
    color: {p['main_text']};
}}

QMenu::item {{
    background-color: transparent;
    color: {p['main_text']};
    padding: 7px 22px 7px 14px;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 500;
}}

QMenu::item:selected {{
    background-color: {p['menu_hover']};
    color: {p['primary_accent']};
}}

QMenu::item:disabled {{
    background-color: transparent;
    color: {p['secondary_text']};
}}

QMenu::separator {{
    height: 1px;
    background-color: {p['borders']};
    margin: 4px 6px;
}}

/* Tooltips */
QToolTip {{
    background-color: {p['card_bg']};
    color: {p['main_text']};
    border: 1px solid {p['borders']};
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 12px;
}}

/* Dialog & Message Boxes */
QMessageBox {{
    background-color: {p['dialog_bg']};
    color: {p['main_text']};
}}

QMessageBox QLabel {{
    color: {p['main_text']};
}}
"""


class ThemeManager(QObject):
    """Central singleton managing application themes and dynamic live updates."""

    theme_changed = Signal(str)  # Emits "dark" or "light"

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ThemeManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        super().__init__()
        self._initialized = True
        
        # Load saved theme or default to "dark"
        saved_theme = config.get("theme", "dark")
        self._current_theme = "light" if saved_theme == "light" else "dark"

    @property
    def current_theme(self) -> str:
        return self._current_theme

    def is_dark(self) -> bool:
        return self._current_theme == "dark"

    def get_palette(self) -> Dict[str, str]:
        """Return color dictionary for active theme."""
        return THEME_PALETTES.get(self._current_theme, THEME_PALETTES["dark"])

    def get_stylesheet(self) -> str:
        """Return compiled QSS string for active theme."""
        return build_stylesheet(self.get_palette())

    def update_application_palette(self, app: QApplication) -> None:
        """Synchronize native QApplication QPalette so native views and containers match theme."""
        if not app:
            return
        p = self.get_palette()
        is_dark = self.is_dark()

        palette = QPalette()
        bg = QColor(p["bg_main"])
        card = QColor(p["card_bg"])
        text = QColor(p["main_text"])
        sec_text = QColor(p["secondary_text"])
        accent = QColor(p["primary_accent"])
        btn_bg = QColor(p["btn_sec_bg"])

        palette.setColor(QPalette.Window, bg)
        palette.setColor(QPalette.WindowText, text)
        palette.setColor(QPalette.Base, card)
        palette.setColor(QPalette.AlternateBase, QColor(p["surface_sec"]))
        palette.setColor(QPalette.ToolTipBase, card)
        palette.setColor(QPalette.ToolTipText, text)
        palette.setColor(QPalette.Text, text)
        palette.setColor(QPalette.Button, btn_bg)
        palette.setColor(QPalette.ButtonText, text)
        palette.setColor(QPalette.BrightText, QColor("#FFFFFF"))
        palette.setColor(QPalette.Highlight, accent)
        palette.setColor(QPalette.HighlightedText, QColor("#FFFFFF" if is_dark else "#17211B"))
        palette.setColor(QPalette.PlaceholderText, sec_text)

        app.setPalette(palette)

    def set_theme(self, theme_name: str) -> None:
        """Switch active theme dynamically across the entire application."""
        theme_clean = "light" if theme_name.lower().startswith("light") else "dark"
        if theme_clean == self._current_theme:
            return

        self._current_theme = theme_clean
        config.set("theme", self._current_theme)

        # Apply global stylesheet and synchronized palette immediately to QApplication
        app = QApplication.instance()
        if app:
            self.update_application_palette(app)
            app.setStyleSheet(self.get_stylesheet())

        self.theme_changed.emit(self._current_theme)

    def toggle_theme(self) -> str:
        """Toggle between Dark and Light mode and return new theme name."""
        new_theme = "light" if self._current_theme == "dark" else "dark"
        self.set_theme(new_theme)
        return new_theme


# Global singleton instance
theme_manager = ThemeManager()
