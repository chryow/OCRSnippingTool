"""Editorial E-Ink design system — centralized color/font tokens, QSS, and crisp native widgets.

Aesthetic: printed ledger / Japanese stationery / tactile e-reader.
- Zero gradients, zero blur/glassmorphism, zero heavy drop shadows, zero pill buttons.
- Crisp 2px–3px corners, hairline 1px dividers, high-contrast ink on unbleached paper.
"""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProxyStyle,
    QSizeGrip,
    QSpinBox,
    QStyle,
    QStyleOption,
    QWidget,
)


@dataclass(frozen=True)
class EditorialThemeTokens:
    """Centralized Editorial E-Ink color, border, and typography tokens."""

    # Core paper & ink palette
    paper: str = "#F7F5F0"           # Window Background (Unbleached Paper)
    sheet: str = "#FFFFFF"           # Text Box / Card Surface (Crisp Sheet)
    pressed: str = "#EFECE4"         # Hover / Subtle Tint (Pressed Paper)
    ink: str = "#1A1A18"             # Primary Text / Strong Active Border (Rich Ink)
    graphite: str = "#6B6963"        # Muted Text / Metadata (Graphite)
    hairline: str = "#D8D4CA"        # Hairline Borders & Dividers
    vermilion: str = "#C83E2B"       # Primary Accent (Stamp Vermilion)
    vermilion_hover: str = "#AE3423" # Hover deepen for solid Vermilion CTA
    vermilion_tint: str = "#FBF2EF"  # Flat paper tint for warning/error slips
    green: str = "#234E3D"           # Success Accent (Fountain Pen Green)
    green_tint: str = "#EFF5F2"      # Flat subtle tint for confirmed states
    disabled_ink: str = "#A8A49B"    # Disabled text on paper

    # Scrim (rgba(26, 26, 24, 0.35))
    scrim_rgba: tuple[int, int, int, int] = (26, 26, 24, 89)

    # Typography stacks
    font_serif: str = '"Newsreader", "Georgia", "Times New Roman", serif'
    font_sans: str = (
        '"Inter", "Segoe UI Variable", "Segoe UI", "Noto Sans", '
        '"PingFang SC", "Yu Gothic UI", "Malgun Gothic", "Helvetica Neue", Arial, sans-serif'
    )
    font_mono: str = '"JetBrains Mono", "Cascadia Mono", "Consolas", "SF Mono", monospace'

    # Editorial colophon credit
    colophon_credit: str = "CRAFTED BY WILSON"


THEME = EditorialThemeTokens()


def _build_editorial_stylesheet(t: EditorialThemeTokens = THEME) -> str:
    return f"""
QWidget {{
    color: {t.ink};
    font-family: {t.font_sans};
    font-size: 13.5px;
}}

QToolTip {{
    background-color: {t.paper};
    color: {t.ink};
    border: 1px solid {t.ink};
    border-radius: 2px;
    padding: 5px 8px;
    font-family: {t.font_mono};
    font-size: 11px;
}}

/* --- System Tray & Context Menus --- */
QMenu {{
    background-color: {t.paper};
    color: {t.ink};
    border: 1px solid {t.ink};
    border-radius: 3px;
    padding: 4px;
    font-family: {t.font_sans};
    font-size: 13px;
}}

QMenu::item {{
    background-color: transparent;
    color: {t.ink};
    padding: 7px 26px 7px 10px;
    border-radius: 2px;
    margin: 1px 0px;
}}

QMenu::item:selected {{
    background-color: {t.pressed};
    color: {t.ink};
}}

QMenu::item:disabled {{
    color: {t.disabled_ink};
}}

QMenu::separator {{
    height: 1px;
    background-color: {t.hairline};
    margin: 4px 6px;
}}

QMenu::icon {{
    padding-left: 4px;
}}

/* --- Main Containers --- */
QDialog {{
    background-color: {t.paper};
    color: {t.ink};
}}

QFrame#PopupCard {{
    background-color: {t.paper};
    border: 1px solid {t.ink};
    border-radius: 3px;
}}

QFrame#HeaderBar {{
    background-color: {t.paper};
    border-bottom: 1px solid {t.hairline};
    border-top-left-radius: 2px;
    border-top-right-radius: 2px;
}}

QFrame#LangBar {{
    background-color: {t.paper};
    border-bottom: 1px solid {t.hairline};
}}

QFrame#UtilityStrip, QFrame#ColophonBar {{
    background-color: {t.paper};
    border-top: 1px solid {t.hairline};
    border-bottom-left-radius: 2px;
    border-bottom-right-radius: 2px;
}}

QFrame#SheetPane, QFrame#TranslatePanel {{
    background-color: {t.sheet};
    border: 1px solid {t.hairline};
    border-radius: 2px;
}}

QFrame#PaneHeader {{
    background-color: {t.paper};
    border-bottom: 1px solid {t.hairline};
}}

QFrame#StatusSlip {{
    background-color: {t.paper};
    border: 1px solid {t.ink};
    border-radius: 2px;
}}

QFrame#PackCard {{
    background-color: {t.sheet};
    border: 1px solid {t.hairline};
    border-radius: 3px;
}}

QFrame#PackCard:hover {{
    border-color: {t.ink};
}}

QWidget#ScrollBody {{
    background-color: transparent;
}}

/* --- Editorial Typography --- */
QLabel#TitleLabel {{
    font-family: {t.font_serif};
    font-size: 16px;
    font-weight: 700;
    color: {t.ink};
    letter-spacing: 0.2px;
}}

QLabel#SectionSerif {{
    font-family: {t.font_serif};
    font-size: 15px;
    font-weight: 700;
    color: {t.ink};
}}

QLabel#MonoLabel {{
    font-family: {t.font_mono};
    font-size: 10.5px;
    font-weight: 600;
    color: {t.ink};
    letter-spacing: 0.9px;
}}

QLabel#MonoMuted {{
    font-family: {t.font_mono};
    font-size: 10.5px;
    font-weight: 500;
    color: {t.graphite};
    letter-spacing: 0.7px;
}}

QLabel#PackTitle {{
    font-family: {t.font_serif};
    font-size: 14px;
    font-weight: 700;
    color: {t.ink};
}}

QLabel#PackDesc {{
    font-size: 12.5px;
    color: {t.graphite};
}}

QLabel#PackStatusInstalled {{
    font-family: {t.font_mono};
    font-size: 10.5px;
    font-weight: 700;
    color: {t.green};
    letter-spacing: 0.7px;
}}

QLabel#PackStatusAvailable {{
    font-family: {t.font_mono};
    font-size: 10.5px;
    color: {t.graphite};
    letter-spacing: 0.6px;
}}

QLabel#LangPill {{
    background-color: {t.sheet};
    border: 1px solid {t.hairline};
    color: {t.ink};
    border-radius: 2px;
    padding: 4px 9px;
    font-family: {t.font_mono};
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.6px;
}}

QLabel#EnginePill {{
    background-color: transparent;
    border: none;
    color: {t.graphite};
    padding: 2px 4px;
    font-family: {t.font_mono};
    font-size: 10.5px;
    letter-spacing: 0.5px;
}}

QLabel#CopiedPill {{
    background-color: {t.paper};
    border: 1px solid {t.ink};
    color: {t.green};
    border-radius: 2px;
    padding: 2px 8px;
    font-family: {t.font_mono};
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.9px;
}}

QLabel#WarnPill {{
    background-color: {t.vermilion_tint};
    border: 1px solid {t.vermilion};
    color: {t.vermilion};
    border-radius: 2px;
    padding: 6px 10px;
    font-family: {t.font_mono};
    font-size: 11px;
    letter-spacing: 0.3px;
}}

QLabel#MutedLabel {{
    color: {t.graphite};
    font-size: 12px;
}}

/* --- Text Inputs & Sheets --- */
QPlainTextEdit {{
    background-color: {t.sheet};
    border: 1px solid {t.hairline};
    border-radius: 2px;
    padding: 11px 12px;
    color: {t.ink};
    font-family: {t.font_sans};
    font-size: 14.5px;
    selection-background-color: {t.pressed};
    selection-color: {t.ink};
}}

QPlainTextEdit:focus {{
    border: 1px solid {t.ink};
}}

QPlainTextEdit#SheetEdit {{
    background-color: {t.sheet};
    border: none;
    border-radius: 0px;
    padding: 12px 14px;
    color: {t.ink};
    font-family: {t.font_sans};
    font-size: 14.5px;
    selection-background-color: {t.pressed};
    selection-color: {t.ink};
}}

QListWidget {{
    background-color: {t.sheet};
    border: 1px solid {t.hairline};
    border-radius: 2px;
    padding: 4px;
    outline: none;
    font-size: 13px;
}}

QListWidget::item {{
    padding: 9px 10px;
    border-bottom: 1px solid {t.hairline};
    border-radius: 2px;
    color: {t.ink};
}}

QListWidget::item:selected {{
    background-color: {t.pressed};
    color: {t.ink};
    border-left: 2px solid {t.vermilion};
}}

QListWidget::item:hover:!selected {{
    background-color: {t.paper};
}}

QSplitter::handle {{
    background-color: transparent;
    width: 8px;
    height: 8px;
}}

/* --- Buttons (Crisp 2px–3px Rectangular Ledger Style) --- */
QPushButton {{
    background-color: {t.sheet};
    border: 1px solid {t.ink};
    border-radius: 2px;
    padding: 6px 12px;
    color: {t.ink};
    font-family: {t.font_sans};
    font-weight: 500;
    font-size: 13px;
}}

QPushButton:hover {{
    background-color: {t.pressed};
    color: {t.ink};
}}

QPushButton:pressed {{
    background-color: {t.hairline};
}}

QPushButton:disabled {{
    color: {t.disabled_ink};
    background-color: {t.paper};
    border-color: {t.hairline};
}}

/* Primary Ink CTA (Translate / Save Settings) */
QPushButton#PrimaryButton, QPushButton#TranslateButton {{
    background-color: {t.ink};
    border: 1px solid {t.ink};
    border-radius: 2px;
    color: {t.paper};
    font-family: {t.font_mono};
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.8px;
    padding: 7px 14px;
}}

QPushButton#PrimaryButton:hover, QPushButton#TranslateButton:hover {{
    background-color: #2E2E2B;
    border-color: #2E2E2B;
    color: {t.paper};
}}

QPushButton#PrimaryButton:pressed, QPushButton#TranslateButton:pressed {{
    background-color: #0E0E0D;
}}

QPushButton#PrimaryButton:disabled, QPushButton#TranslateButton:disabled {{
    background-color: {t.hairline};
    border-color: {t.hairline};
    color: {t.graphite};
}}

/* Stamp Vermilion Primary Capture CTA (Re-Snip) */
QPushButton#CaptureButton {{
    background-color: {t.vermilion};
    border: 1px solid {t.vermilion};
    border-radius: 2px;
    color: {t.paper};
    font-family: {t.font_mono};
    font-size: 10.5px;
    font-weight: 700;
    letter-spacing: 0.9px;
    padding: 5px 11px;
}}

QPushButton#CaptureButton:hover {{
    background-color: {t.vermilion_hover};
    border-color: {t.vermilion_hover};
    color: {t.paper};
}}

QPushButton#CaptureButton:pressed {{
    background-color: #932B1C;
}}

/* Secondary bordered action (Enhance / Copy / Swap) */
QPushButton#AIButton, QPushButton#SwapButton {{
    background-color: {t.sheet};
    border: 1px solid {t.ink};
    border-radius: 2px;
    color: {t.ink};
    font-family: {t.font_mono};
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.7px;
    padding: 6px 11px;
}}

QPushButton#AIButton:hover, QPushButton#SwapButton:hover {{
    background-color: {t.pressed};
}}

QPushButton#SwapButton {{
    padding: 4px 8px;
    font-size: 13px;
}}

/* Inline Pane [ COPY ] button */
QPushButton#PaneCopyButton {{
    background-color: {t.sheet};
    border: 1px solid {t.ink};
    border-radius: 2px;
    color: {t.ink};
    font-family: {t.font_mono};
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.8px;
    padding: 3px 9px;
}}

QPushButton#PaneCopyButton:hover {{
    background-color: {t.pressed};
}}

QPushButton#PaneCopyButton:disabled {{
    background-color: {t.paper};
    border-color: {t.hairline};
    color: {t.disabled_ink};
}}

/* Quiet utility header buttons */
QPushButton#IconButton {{
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 2px;
    padding: 4px 7px;
    color: {t.ink};
    font-family: {t.font_mono};
    font-size: 10.5px;
    font-weight: 600;
    letter-spacing: 0.6px;
}}

QPushButton#IconButton:hover {{
    background-color: {t.pressed};
    border-color: {t.hairline};
    color: {t.ink};
}}

QPushButton#IconButton:checked {{
    background-color: {t.pressed};
    border-color: {t.ink};
    color: {t.ink};
}}

/* --- Form Controls --- */
QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox {{
    background-color: {t.sheet};
    border: 1px solid {t.hairline};
    border-radius: 2px;
    padding: 5px 10px;
    color: {t.ink};
    font-size: 13px;
}}

QComboBox {{
    padding-right: 26px;
    margin-right: 2px;
}}

QComboBox#CompactCombo {{
    padding: 3px 22px 3px 8px;
    font-family: {t.font_mono};
    font-size: 10.5px;
    border-radius: 2px;
    background-color: {t.sheet};
    border: 1px solid {t.hairline};
    color: {t.ink};
}}

QComboBox:hover, QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover {{
    border-color: {t.graphite};
}}

QComboBox:focus, QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {t.ink};
}}

QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 24px;
    border: none;
    background: transparent;
}}

QComboBox::down-arrow {{
    image: none;
    width: 0px;
    height: 0px;
}}

QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    subcontrol-origin: border;
    width: 22px;
    border: none;
    background: transparent;
}}

QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
    background-color: {t.pressed};
}}

QSpinBox::up-arrow, QDoubleSpinBox::up-arrow,
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
    image: none;
    width: 0px;
    height: 0px;
}}

QComboBox QAbstractItemView {{
    background-color: {t.sheet};
    border: 1px solid {t.ink};
    border-radius: 2px;
    selection-background-color: {t.pressed};
    selection-color: {t.ink};
    color: {t.ink};
    padding: 3px;
    outline: none;
    font-size: 13px;
}}

QComboBox QAbstractItemView::item {{
    min-height: 26px;
    padding: 4px 10px;
    border-radius: 2px;
}}

/* --- Ledger Section Cards (QGroupBox) --- */
QGroupBox {{
    background-color: {t.sheet};
    border: 1px solid {t.hairline};
    border-radius: 3px;
    margin-top: 16px;
    padding: 16px 14px 14px 14px;
    font-family: {t.font_serif};
    font-size: 14px;
    font-weight: 700;
    color: {t.ink};
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    top: 2px;
    padding: 0 6px;
    background-color: {t.paper};
    color: {t.ink};
    font-family: {t.font_serif};
    font-size: 14px;
    font-weight: 700;
}}

QProgressBar {{
    background-color: {t.hairline};
    border: none;
    height: 2px;
}}

QProgressBar::chunk {{
    background-color: {t.vermilion};
}}

QCheckBox {{
    spacing: 9px;
    color: {t.ink};
    font-size: 13px;
}}

/* --- Editorial Underline Tabs --- */
QTabWidget::pane {{
    border: none;
    border-top: 1px solid {t.hairline};
    background-color: transparent;
    padding-top: 10px;
}}

QTabBar::tab {{
    background-color: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    padding: 8px 16px;
    margin-right: 4px;
    color: {t.graphite};
    font-family: {t.font_mono};
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.7px;
}}

QTabBar::tab:hover {{
    color: {t.ink};
}}

QTabBar::tab:selected {{
    color: {t.ink};
    border-bottom: 2px solid {t.vermilion};
    font-weight: 700;
}}

QScrollArea {{
    background-color: transparent;
    border: none;
}}

QScrollArea > QWidget > QWidget {{
    background-color: transparent;
}}

QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 2px 0;
}}

QScrollBar::handle:vertical {{
    background: {t.hairline};
    border-radius: 2px;
    min-height: 28px;
}}

QScrollBar::handle:vertical:hover {{
    background: {t.graphite};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: transparent;
    height: 0;
}}

QScrollBar:horizontal {{
    background: transparent;
    height: 8px;
    margin: 0 2px;
}}

QScrollBar::handle:horizontal {{
    background: {t.hairline};
    border-radius: 2px;
    min-width: 28px;
}}

QScrollBar::handle:horizontal:hover {{
    background: {t.graphite};
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    background: transparent;
    width: 0;
}}

QSizeGrip {{
    background: transparent;
    width: 14px;
    height: 14px;
}}
"""


EDITORIAL_STYLESHEET = _build_editorial_stylesheet(THEME)
# Backwards-compatible alias for existing imports/tests
DARK_STYLESHEET = EDITORIAL_STYLESHEET


class SleekProxyStyle(QProxyStyle):
    """Draws crisp ink chevrons and tactile square checkboxes natively."""

    def drawPrimitive(
        self,
        element: QStyle.PrimitiveElement,
        option: QStyleOption | None,
        painter: QPainter | None,
        widget: QWidget | None = None,
    ) -> None:
        if option is not None and painter is not None:
            if element == QStyle.PrimitiveElement.PE_IndicatorArrowDown:
                self._draw_chevron(painter, option.rect, direction="down")
                return
            if element == QStyle.PrimitiveElement.PE_IndicatorArrowUp:
                self._draw_chevron(painter, option.rect, direction="up")
                return
            if element == QStyle.PrimitiveElement.PE_IndicatorArrowRight:
                self._draw_chevron(painter, option.rect, direction="right")
                return
            if element == QStyle.PrimitiveElement.PE_IndicatorCheckBox:
                self._draw_checkbox(painter, option)
                return
        super().drawPrimitive(element, option, painter, widget)

    @staticmethod
    def _draw_chevron(painter: QPainter, rect, direction: str) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(
            QColor(THEME.ink),
            1.4,
            Qt.PenStyle.SolidLine,
            Qt.PenCapStyle.RoundCap,
            Qt.PenJoinStyle.RoundJoin,
        )
        painter.setPen(pen)
        cx = float(rect.center().x())
        cy = float(rect.center().y())
        if direction == "down":
            painter.drawPolyline([QPointF(cx - 3.5, cy - 1.5), QPointF(cx, cy + 2.0), QPointF(cx + 3.5, cy - 1.5)])
        elif direction == "up":
            painter.drawPolyline([QPointF(cx - 3.5, cy + 1.5), QPointF(cx, cy - 2.0), QPointF(cx + 3.5, cy + 1.5)])
        else:
            painter.drawPolyline([QPointF(cx - 1.5, cy - 3.5), QPointF(cx + 2.0, cy), QPointF(cx - 1.5, cy + 3.5)])
        painter.restore()

    @staticmethod
    def _draw_checkbox(painter: QPainter, option: QStyleOption) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(option.rect).adjusted(1.5, 1.5, -1.5, -1.5)
        checked = bool(option.state & QStyle.StateFlag.State_On)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)

        if checked:
            painter.setBrush(QColor(THEME.ink))
            painter.setPen(QPen(QColor(THEME.ink), 1.2))
            painter.drawRoundedRect(r, 2.0, 2.0)
            pen = QPen(
                QColor(THEME.paper),
                1.7,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
            painter.setPen(pen)
            cx, cy = r.center().x(), r.center().y()
            painter.drawPolyline(
                [QPointF(cx - 3.0, cy + 0.2), QPointF(cx - 0.8, cy + 2.6), QPointF(cx + 3.4, cy - 2.4)]
            )
        else:
            painter.setBrush(QColor(THEME.pressed if hovered else THEME.sheet))
            painter.setPen(QPen(QColor(THEME.ink), 1.1))
            painter.drawRoundedRect(r, 2.0, 2.0)
        painter.restore()


def _paint_down_chevron(widget: QWidget) -> None:
    painter = QPainter(widget)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(THEME.ink if widget.isEnabled() else THEME.disabled_ink)
        pen = QPen(color, 1.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        cx = widget.width() - 12.5
        cy = widget.height() / 2.0
        painter.drawPolyline(
            [QPointF(cx - 3.3, cy - 1.4), QPointF(cx, cy + 2.0), QPointF(cx + 3.3, cy - 1.4)]
        )
    finally:
        if painter.isActive():
            painter.end()


def _paint_spin_chevrons(widget: QWidget) -> None:
    painter = QPainter(widget)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(THEME.ink if widget.isEnabled() else THEME.disabled_ink)
        pen = QPen(color, 1.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        cx = widget.width() - 10.5
        cy_up = widget.height() * 0.33
        cy_dn = widget.height() * 0.67
        painter.drawPolyline(
            [QPointF(cx - 2.8, cy_up + 1.2), QPointF(cx, cy_up - 1.5), QPointF(cx + 2.8, cy_up + 1.2)]
        )
        painter.drawPolyline(
            [QPointF(cx - 2.8, cy_dn - 1.2), QPointF(cx, cy_dn + 1.5), QPointF(cx + 2.8, cy_dn - 1.2)]
        )
    finally:
        if painter.isActive():
            painter.end()


class SleekComboBox(QComboBox):
    """QComboBox that safely draws a crisp ink chevron inside paintEvent."""

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        _paint_down_chevron(self)


class SleekSpinBox(QSpinBox):
    """QSpinBox that safely draws crisp ink up/down chevrons inside paintEvent."""

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        _paint_spin_chevrons(self)


class SleekDoubleSpinBox(QDoubleSpinBox):
    """QDoubleSpinBox that safely draws crisp ink up/down chevrons inside paintEvent."""

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        _paint_spin_chevrons(self)


class SleekSizeGrip(QSizeGrip):
    """Minimalist bottom-right resize grip with two crisp graphite diagonal ticks."""

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            pen = QPen(QColor(THEME.graphite), 1.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.SquareCap)
            painter.setPen(pen)
            w, h = float(self.width()), float(self.height())
            painter.drawLine(QPointF(w - 3.5, h - 9.5), QPointF(w - 9.5, h - 3.5))
            painter.drawLine(QPointF(w - 3.5, h - 5.5), QPointF(w - 5.5, h - 3.5))
        finally:
            if painter.isActive():
                painter.end()


def make_accent_square(color: str = THEME.vermilion, size: int = 5) -> QFrame:
    """Create a crisp 5x5px flat square status/colophon mark."""
    sq = QFrame()
    sq.setFixedSize(size, size)
    sq.setStyleSheet(f"background-color: {color}; border: none; border-radius: 0px;")
    return sq


class StatusSlip(QFrame):
    """Compact printed slip toast/badge with a 5x5px colored square indicator."""

    def __init__(self, text: str = "", accent: str = THEME.green, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("StatusSlip")
        row = QHBoxLayout(self)
        row.setContentsMargins(7, 3, 8, 3)
        row.setSpacing(6)

        self._square = make_accent_square(accent, 5)
        row.addWidget(self._square)

        self._label = QLabel(text)
        self._label.setObjectName("MonoLabel")
        row.addWidget(self._label)

    def set_status(self, text: str, accent: str = THEME.green) -> None:
        self._square.setStyleSheet(f"background-color: {accent}; border: none; border-radius: 0px;")
        self._label.setText(text)
        self._label.setStyleSheet(f"color: {THEME.ink};")

    def text(self) -> str:
        return self._label.text()

    def setText(self, text: str) -> None:  # noqa: N802 (Qt compatibility)
        self._label.setText(text)


def create_colophon_bar(
    left_widget: QWidget | None = None,
    *,
    left_text: str = "",
    parent: QWidget | None = None,
    include_size_grip: bool = False,
) -> tuple[QFrame, QLabel | None]:
    """Build the slim editorial footer strip with left hint and right author colophon."""
    bar = QFrame(parent)
    bar.setObjectName("ColophonBar")
    layout = QHBoxLayout(bar)
    layout.setContentsMargins(14, 7, 10 if include_size_grip else 14, 7)
    layout.setSpacing(8)

    left_label: QLabel | None = None
    if left_widget is not None:
        layout.addWidget(left_widget)
    if left_text:
        left_label = QLabel(left_text)
        left_label.setObjectName("MonoMuted")
        layout.addWidget(left_label)

    layout.addStretch()

    credit = QLabel(THEME.colophon_credit)
    credit.setObjectName("MonoMuted")
    layout.addWidget(credit)

    layout.addWidget(make_accent_square(THEME.vermilion, 5))

    if include_size_grip and parent is not None:
        grip = SleekSizeGrip(parent)
        grip.setToolTip("Drag corner or any window edge to resize")
        layout.addWidget(grip, alignment=Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)

    return bar, left_label


def apply_sleek_theme(root: QWidget) -> None:
    """Apply the unified Editorial E-Ink stylesheet to `root`."""
    root.setStyleSheet(EDITORIAL_STYLESHEET)


def create_app_icon(size: int = 64) -> QIcon:
    """Render an Editorial E-Ink stationery stamp icon (paper tile, ink serif 'A', vermilion crop ticks)."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Unbleached paper stamp tile with crisp ink outline
    inset = max(1.5, size * 0.04)
    painter.setBrush(QColor(THEME.paper))
    painter.setPen(QPen(QColor(THEME.ink), max(1.5, size * 0.045)))
    radius = max(2.0, size * 0.08)
    painter.drawRoundedRect(QRectF(inset, inset, size - inset * 2, size - inset * 2), radius, radius)

    # Stamp Vermilion corner crop ticks
    pen = QPen(QColor(THEME.vermilion))
    pen.setWidthF(max(1.8, size * 0.06))
    pen.setCapStyle(Qt.PenCapStyle.SquareCap)
    painter.setPen(pen)

    m = size * 0.18
    arm = size * 0.15
    painter.drawLine(QPointF(m, m), QPointF(m + arm, m))
    painter.drawLine(QPointF(m, m), QPointF(m, m + arm))
    painter.drawLine(QPointF(size - m, m), QPointF(size - m - arm, m))
    painter.drawLine(QPointF(size - m, m), QPointF(size - m, m + arm))
    painter.drawLine(QPointF(m, size - m), QPointF(m + arm, size - m))
    painter.drawLine(QPointF(m, size - m), QPointF(m, size - m - arm))
    painter.drawLine(QPointF(size - m, size - m), QPointF(size - m - arm, size - m))
    painter.drawLine(QPointF(size - m, size - m), QPointF(size - m, size - m - arm))

    # Rich ink serif letter 'A'
    font = QFont("Georgia", max(9, int(size * 0.36)), QFont.Weight.Bold)
    painter.setFont(font)
    painter.setPen(QColor(THEME.ink))
    painter.drawText(QRectF(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, "A")

    painter.end()
    return QIcon(pixmap)
