"""
Reusable Card component for grouping controls with modern Windows styling.
"""
from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel, QWidget
from PySide6.QtCore import Qt

from ui.theme_manager import theme_manager


class Card(QFrame):
    """A clean card container with rounded borders and theme-aware surface."""

    def __init__(self, title: str = "", subtitle: str = "", parent: QWidget = None):
        super().__init__(parent)
        self.setObjectName("cardFrame")

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(18, 18, 18, 18)
        self._layout.setSpacing(12)

        self.title_label = None
        self.subtitle_label = None

        if title:
            header_layout = QVBoxLayout()
            header_layout.setSpacing(2)

            self.title_label = QLabel(title)
            self.title_label.setObjectName("cardTitle")
            header_layout.addWidget(self.title_label)

            if subtitle:
                self.subtitle_label = QLabel(subtitle)
                self.subtitle_label.setObjectName("cardSubtitle")
                header_layout.addWidget(self.subtitle_label)

            self._layout.addLayout(header_layout)

        self._apply_theme()
        theme_manager.theme_changed.connect(self._on_theme_changed)

    def _on_theme_changed(self, _) -> None:
        try:
            self._apply_theme()
        except RuntimeError:
            pass

    def _apply_theme(self) -> None:
        try:
            p = theme_manager.get_palette()
            if self.title_label:
                self.title_label.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {p['main_text']};")
            if self.subtitle_label:
                self.subtitle_label.setStyleSheet(f"font-size: 12px; color: {p['secondary_text']};")
        except RuntimeError:
            pass

    def add_widget(self, widget: QWidget) -> None:
        """Add widget to the card body."""
        self._layout.addWidget(widget)

    def add_layout(self, layout) -> None:
        """Add child layout to the card body."""
        self._layout.addLayout(layout)

    def content_layout(self) -> QVBoxLayout:
        """Return the internal QVBoxLayout for custom configurations."""
        return self._layout
