"""Minimalist neutral-graphite stylesheet, crisp vector app/tray icons, and custom Qt style."""

from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QProxyStyle,
    QSpinBox,
    QStyle,
    QStyleOption,
    QWidget,
)

DARK_STYLESHEET = """
QWidget {
    color: #e4e4e7;
    font-family: "Segoe UI Variable", "Segoe UI", "SF Pro Text", "Inter", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}

QToolTip {
    background-color: #202024;
    color: #f4f4f5;
    border: 1px solid #35353d;
    border-radius: 6px;
    padding: 5px 9px;
    font-size: 12px;
}

/* --- System Tray & Context Menus --- */
QMenu {
    background-color: #18181b;
    color: #e4e4e7;
    border: 1px solid #2e2e34;
    border-radius: 9px;
    padding: 5px;
    font-size: 13px;
}

QMenu::item {
    background-color: transparent;
    color: #e4e4e7;
    padding: 7px 24px 7px 10px;
    border-radius: 6px;
    margin: 1px 2px;
}

QMenu::item:selected {
    background-color: #27272c;
    color: #ffffff;
}

QMenu::item:disabled {
    color: #52525b;
}

QMenu::separator {
    height: 1px;
    background-color: #27272c;
    margin: 5px 8px;
}

QMenu::icon {
    padding-left: 4px;
}

/* --- Main Containers --- */
QDialog, QFrame#PopupCard {
    background-color: #18181b;
    border: 1px solid #2b2b31;
    border-radius: 12px;
}

QFrame#HeaderBar {
    background-color: #141417;
    border-top-left-radius: 11px;
    border-top-right-radius: 11px;
    border-bottom: 1px solid #242429;
}

QFrame#UtilityStrip {
    background-color: #141417;
    border-bottom-left-radius: 11px;
    border-bottom-right-radius: 11px;
    border-top: 1px solid #242429;
}

QFrame#TranslatePanel {
    background-color: #141417;
    border: 1px solid #27272d;
    border-radius: 9px;
}

QFrame#PackCard {
    background-color: #141417;
    border: 1px solid #26262c;
    border-radius: 8px;
}

QFrame#PackCard:hover {
    border-color: #3a3a43;
}

/* --- Typography & Subtle Badges --- */
QLabel#TitleLabel {
    font-size: 13px;
    font-weight: 600;
    color: #f4f4f5;
    letter-spacing: -0.1px;
}

QLabel#PackTitle {
    font-size: 13px;
    font-weight: 600;
    color: #f4f4f5;
}

QLabel#PackDesc {
    font-size: 11.5px;
    color: #8e8e98;
}

QLabel#PackStatusInstalled {
    font-size: 11.5px;
    font-weight: 600;
    color: #4ade80;
}

QLabel#PackStatusAvailable {
    font-size: 11.5px;
    color: #71717a;
}

QLabel#LangPill {
    background-color: #232328;
    border: 1px solid #303037;
    color: #f4f4f5;
    border-radius: 6px;
    padding: 2px 8px;
    font-size: 11.5px;
    font-weight: 500;
}

QLabel#EnginePill {
    background-color: transparent;
    border: none;
    color: #8e8e98;
    padding: 2px 4px;
    font-size: 11.5px;
}

QLabel#CopiedPill {
    background-color: rgba(34, 197, 94, 0.14);
    border: 1px solid rgba(74, 222, 128, 0.28);
    color: #4ade80;
    border-radius: 6px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 600;
}

QLabel#WarnPill {
    background-color: rgba(217, 119, 6, 0.12);
    border: 1px solid rgba(245, 158, 11, 0.30);
    color: #fbbf24;
    border-radius: 8px;
    padding: 6px 10px;
    font-size: 12px;
}

QLabel#MutedLabel {
    color: #8e8e98;
    font-size: 11.5px;
}

/* --- Text Inputs & Lists --- */
QPlainTextEdit {
    background-color: #111113;
    border: 1px solid #27272c;
    border-radius: 8px;
    padding: 10px 11px;
    color: #f4f4f5;
    font-size: 13.5px;
    selection-background-color: #3f3f46;
    selection-color: #ffffff;
}

QPlainTextEdit:focus {
    border: 1px solid #52525b;
}

QListWidget {
    background-color: #111113;
    border: 1px solid #27272c;
    border-radius: 8px;
    padding: 4px;
    outline: none;
}

QListWidget::item {
    padding: 8px 10px;
    border-radius: 6px;
    margin-bottom: 2px;
    color: #d4d4d8;
}

QListWidget::item:selected {
    background-color: #27272d;
    color: #ffffff;
}

QListWidget::item:hover:!selected {
    background-color: #1c1c21;
}

QSplitter::handle {
    background-color: transparent;
    width: 8px;
}

/* --- Buttons --- */
QPushButton {
    background-color: #222227;
    border: 1px solid #32323a;
    border-radius: 7px;
    padding: 6px 12px;
    color: #e4e4e7;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #2c2c33;
    border-color: #44444e;
    color: #ffffff;
}

QPushButton:pressed {
    background-color: #1c1c21;
}

QPushButton:disabled {
    color: #52525b;
    background-color: #19191d;
    border-color: #242429;
}

QPushButton#PrimaryButton {
    background-color: #f4f4f5;
    border: 1px solid #f4f4f5;
    color: #09090b;
    font-weight: 600;
    padding: 6px 15px;
}

QPushButton#PrimaryButton:hover {
    background-color: #ffffff;
    border-color: #ffffff;
    color: #09090b;
}

QPushButton#PrimaryButton:pressed {
    background-color: #d4d4d8;
    border-color: #d4d4d8;
}

QPushButton#PrimaryButton:disabled {
    background-color: #27272c;
    border-color: #2e2e34;
    color: #52525b;
}

QPushButton#AIButton, QPushButton#TranslateButton {
    background-color: #222227;
    border: 1px solid #32323a;
    color: #e4e4e7;
    font-weight: 500;
}

QPushButton#AIButton:hover, QPushButton#TranslateButton:hover {
    background-color: #2c2c33;
    border-color: #484852;
    color: #ffffff;
}

QPushButton#IconButton {
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 4px 7px;
    color: #a1a1aa;
    font-size: 12px;
}

QPushButton#IconButton:hover {
    background-color: #26262c;
    color: #f4f4f5;
}

QPushButton#IconButton:checked {
    background-color: #2c2c33;
    border-color: #3f3f48;
    color: #f4f4f5;
}

/* --- Form Controls --- */
QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox {
    background-color: #111113;
    border: 1px solid #2b2b32;
    border-radius: 7px;
    padding: 5px 10px;
    color: #f4f4f5;
}

QComboBox {
    padding-right: 24px;
}

QComboBox#CompactCombo {
    padding: 3px 22px 3px 8px;
    font-size: 11.5px;
    border-radius: 6px;
    background-color: #1b1b20;
    border-color: #292930;
    color: #d4d4d8;
}

QComboBox:hover, QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover {
    border-color: #3f3f48;
}

QComboBox:focus, QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border-color: #71717a;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 24px;
    border: none;
    background: transparent;
}

QComboBox::down-arrow {
    image: none;
    width: 0px;
    height: 0px;
}

QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {
    subcontrol-origin: border;
    width: 20px;
    border: none;
    background: transparent;
}

QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
    background-color: #26262c;
    border-radius: 3px;
}

QSpinBox::up-arrow, QDoubleSpinBox::up-arrow,
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
    image: none;
    width: 0px;
    height: 0px;
}

QComboBox QAbstractItemView {
    background-color: #18181b;
    border: 1px solid #32323a;
    border-radius: 7px;
    selection-background-color: #2c2c34;
    selection-color: #ffffff;
    color: #e4e4e7;
    padding: 4px;
    outline: none;
}

QGroupBox {
    background-color: #141417;
    border: 1px solid #25252b;
    border-radius: 9px;
    margin-top: 14px;
    padding: 14px 12px 12px 12px;
    font-weight: 600;
    color: #d4d4d8;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #a1a1aa;
    font-size: 12px;
    font-weight: 600;
}

QProgressBar {
    background-color: #222227;
    border: none;
    height: 2px;
}

QProgressBar::chunk {
    background-color: #e4e4e7;
}

QCheckBox {
    spacing: 8px;
    color: #e4e4e7;
}

/* --- Minimal Underline Tabs --- */
QTabWidget::pane {
    border: none;
    border-top: 1px solid #26262c;
    background-color: transparent;
    padding-top: 10px;
}

QTabBar::tab {
    background-color: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    padding: 8px 14px;
    margin-right: 4px;
    color: #8e8e98;
    font-weight: 500;
}

QTabBar::tab:hover {
    color: #e4e4e7;
}

QTabBar::tab:selected {
    color: #ffffff;
    border-bottom: 2px solid #f4f4f5;
    font-weight: 600;
}

QScrollArea {
    background-color: transparent;
    border: none;
}

QScrollBar:vertical {
    background: transparent;
    width: 7px;
    margin: 2px 0;
}

QScrollBar::handle:vertical {
    background: #32323a;
    border-radius: 3px;
    min-height: 24px;
}

QScrollBar::handle:vertical:hover {
    background: #4b4b56;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
    height: 0;
}
"""


class SleekProxyStyle(QProxyStyle):
    """Draws crisp anti-aliased dropdown chevrons and modern checkboxes natively."""

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
            QColor("#a1a1aa"),
            1.5,
            Qt.PenStyle.SolidLine,
            Qt.PenCapStyle.RoundCap,
            Qt.PenJoinStyle.RoundJoin,
        )
        painter.setPen(pen)
        cx = rect.center().x()
        cy = rect.center().y()
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
        r = QRectF(option.rect).adjusted(1.0, 1.0, -1.0, -1.0)
        checked = bool(option.state & QStyle.StateFlag.State_On)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)

        if checked:
            painter.setBrush(QColor("#f4f4f5"))
            painter.setPen(QPen(QColor("#f4f4f5"), 1.2))
            painter.drawRoundedRect(r, 4.0, 4.0)
            pen = QPen(
                QColor("#09090b"),
                1.8,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
            painter.setPen(pen)
            cx, cy = r.center().x(), r.center().y()
            painter.drawPolyline(
                [QPointF(cx - 3.2, cy + 0.2), QPointF(cx - 0.8, cy + 2.7), QPointF(cx + 3.6, cy - 2.5)]
            )
        else:
            painter.setBrush(QColor("#111113"))
            painter.setPen(QPen(QColor("#52525b" if hovered else "#3a3a43"), 1.2))
            painter.drawRoundedRect(r, 4.0, 4.0)
        painter.restore()


def _paint_down_chevron(widget: QWidget) -> None:
    painter = QPainter(widget)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor("#8e8e98" if widget.isEnabled() else "#52525b")
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
        color = QColor("#8e8e98" if widget.isEnabled() else "#52525b")
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
    """QComboBox that safely draws a crisp anti-aliased chevron inside paintEvent."""

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        _paint_down_chevron(self)


class SleekSpinBox(QSpinBox):
    """QSpinBox that safely draws crisp anti-aliased up/down chevrons inside paintEvent."""

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        _paint_spin_chevrons(self)


class SleekDoubleSpinBox(QDoubleSpinBox):
    """QDoubleSpinBox that safely draws crisp anti-aliased up/down chevrons inside paintEvent."""

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        _paint_spin_chevrons(self)


def apply_sleek_theme(root: QWidget) -> None:
    """Apply the unified minimalist stylesheet to `root`."""
    root.setStyleSheet(DARK_STYLESHEET)


def create_app_icon(size: int = 64) -> QIcon:
    """Render a minimal monochrome graphite & white OCR viewfinder app icon."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Sleek charcoal tile with crisp hairline border (no neon gradients)
    painter.setBrush(QColor("#18181b"))
    painter.setPen(QPen(QColor("#3f3f46"), max(1.2, size * 0.03)))
    radius = size * 0.24
    inset = max(1.5, size * 0.035)
    painter.drawRoundedRect(QRectF(inset, inset, size - inset * 2, size - inset * 2), radius, radius)

    # Crisp white crop viewfinder corners
    pen = QPen(QColor("#f4f4f5"))
    pen.setWidthF(max(2.0, size * 0.065))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)

    m = size * 0.20
    arm = size * 0.16
    painter.drawLine(QPointF(m, m), QPointF(m + arm, m))
    painter.drawLine(QPointF(m, m), QPointF(m, m + arm))
    painter.drawLine(QPointF(size - m, m), QPointF(size - m - arm, m))
    painter.drawLine(QPointF(size - m, m), QPointF(size - m, m + arm))
    painter.drawLine(QPointF(m, size - m), QPointF(m + arm, size - m))
    painter.drawLine(QPointF(m, size - m), QPointF(m, size - m - arm))
    painter.drawLine(QPointF(size - m, size - m), QPointF(size - m - arm, size - m))
    painter.drawLine(QPointF(size - m, size - m), QPointF(size - m, size - m - arm))

    font = QFont("Segoe UI", max(8, int(size * 0.34)), QFont.Weight.DemiBold)
    painter.setFont(font)
    painter.setPen(QColor("#ffffff"))
    painter.drawText(QRectF(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, "A")

    painter.end()
    return QIcon(pixmap)
