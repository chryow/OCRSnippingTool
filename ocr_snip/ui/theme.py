"""Cohesive dark-slate glassmorphic stylesheet and vector app icon generator."""

from __future__ import annotations

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QIcon, QLinearGradient, QPainter, QPen, QPixmap

DARK_STYLESHEET = """
QWidget {
    color: #e6e9f2;
    font-family: "Segoe UI", "Inter", "Noto Sans", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}

QToolTip {
    background-color: #1c2132;
    color: #f1f5f9;
    border: 1px solid #353f5e;
    border-radius: 6px;
    padding: 5px 8px;
    font-size: 12px;
}

QDialog, QFrame#PopupCard {
    background-color: #131722;
    border: 1px solid #262d42;
    border-radius: 14px;
}

QFrame#HeaderBar {
    background-color: #181d2b;
    border-top-left-radius: 13px;
    border-top-right-radius: 13px;
    border-bottom: 1px solid #232a3e;
}

QFrame#UtilityStrip {
    background-color: #10131d;
    border-bottom-left-radius: 13px;
    border-bottom-right-radius: 13px;
    border-top: 1px solid #1f2538;
}

QFrame#TranslatePanel {
    background-color: #0f1422;
    border: 1px solid #22304c;
    border-radius: 10px;
}

QFrame#PackCard {
    background-color: #0e111a;
    border: 1px solid #232a3e;
    border-radius: 9px;
}

QFrame#PackCard:hover {
    border-color: #343f5e;
}

QLabel#TitleLabel {
    font-size: 13px;
    font-weight: 600;
    color: #f8fafc;
}

QLabel#PackTitle {
    font-size: 13px;
    font-weight: 600;
    color: #f1f5f9;
}

QLabel#PackDesc {
    font-size: 11.5px;
    color: #8b96b4;
}

QLabel#PackStatusInstalled {
    font-size: 11px;
    font-weight: 600;
    color: #6ee7b7;
}

QLabel#PackStatusAvailable {
    font-size: 11px;
    color: #8b96b4;
}

QLabel#LangPill {
    background-color: rgba(99, 102, 241, 0.20);
    border: 1px solid rgba(129, 140, 248, 0.45);
    color: #c7d2fe;
    border-radius: 10px;
    padding: 3px 10px;
    font-size: 12px;
    font-weight: 600;
}

QLabel#EnginePill {
    background-color: #1b2030;
    border: 1px solid #2b334b;
    color: #9ba6c4;
    border-radius: 10px;
    padding: 3px 9px;
    font-size: 11px;
}

QLabel#CopiedPill {
    background-color: rgba(16, 185, 129, 0.18);
    border: 1px solid rgba(52, 211, 153, 0.45);
    color: #6ee7b7;
    border-radius: 10px;
    padding: 2px 9px;
    font-size: 11px;
    font-weight: 600;
}

QLabel#WarnPill {
    background-color: rgba(245, 158, 11, 0.14);
    border: 1px solid rgba(251, 191, 36, 0.38);
    color: #fcd34d;
    border-radius: 9px;
    padding: 5px 10px;
    font-size: 11.5px;
}

QLabel#MutedLabel {
    color: #8b96b4;
    font-size: 11.5px;
}

QPlainTextEdit {
    background-color: #0d1018;
    border: 1px solid #232a3e;
    border-radius: 10px;
    padding: 10px;
    color: #f1f5f9;
    font-size: 13.5px;
    selection-background-color: #4f46e5;
    selection-color: #ffffff;
}

QPlainTextEdit:focus {
    border: 1px solid #6366f1;
}

QListWidget {
    background-color: #0d1018;
    border: 1px solid #232a3e;
    border-radius: 10px;
    padding: 4px;
    outline: none;
}

QListWidget::item {
    padding: 8px 10px;
    border-radius: 7px;
    margin-bottom: 2px;
    color: #dbe3f4;
}

QListWidget::item:selected {
    background-color: rgba(99, 102, 241, 0.28);
    color: #ffffff;
}

QListWidget::item:hover:!selected {
    background-color: #191f30;
}

QSplitter::handle {
    background-color: transparent;
    width: 6px;
}

QPushButton {
    background-color: #1e2436;
    border: 1px solid #2e3650;
    border-radius: 8px;
    padding: 6px 12px;
    color: #e2e8f0;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #272f46;
    border-color: #445075;
}

QPushButton:pressed {
    background-color: #181d2c;
}

QPushButton:disabled {
    color: #56607a;
    background-color: #151926;
    border-color: #202638;
}

QPushButton#PrimaryButton {
    background-color: #4f46e5;
    border: 1px solid #6366f1;
    color: #ffffff;
    font-weight: 600;
    padding: 6px 15px;
}

QPushButton#PrimaryButton:hover {
    background-color: #5b52f0;
}

QPushButton#PrimaryButton:pressed {
    background-color: #4338ca;
}

QPushButton#AIButton {
    background-color: rgba(139, 92, 246, 0.17);
    border: 1px solid rgba(167, 139, 250, 0.42);
    color: #ddd6fe;
    font-weight: 600;
}

QPushButton#AIButton:hover {
    background-color: rgba(139, 92, 246, 0.28);
}

QPushButton#TranslateButton {
    background-color: rgba(14, 165, 233, 0.16);
    border: 1px solid rgba(56, 189, 248, 0.42);
    color: #bae6fd;
    font-weight: 600;
}

QPushButton#TranslateButton:hover {
    background-color: rgba(14, 165, 233, 0.28);
}

QPushButton#IconButton {
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 4px 7px;
    color: #9ba6c4;
    font-size: 12.5px;
}

QPushButton#IconButton:hover {
    background-color: #242b40;
    color: #f8fafc;
}

QPushButton#IconButton:checked {
    background-color: rgba(99, 102, 241, 0.25);
    border-color: rgba(129, 140, 248, 0.45);
    color: #c7d2fe;
}

QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox {
    background-color: #0d1018;
    border: 1px solid #283047;
    border-radius: 8px;
    padding: 5px 9px;
    color: #f1f5f9;
}

QComboBox#CompactCombo {
    padding: 3px 8px;
    font-size: 11.5px;
    border-radius: 6px;
    background-color: #151a27;
}

QComboBox:focus, QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border-color: #6366f1;
}

QComboBox::drop-down {
    border: none;
    width: 20px;
}

QComboBox QAbstractItemView {
    background-color: #161a26;
    border: 1px solid #2f3750;
    selection-background-color: #4f46e5;
    color: #f1f5f9;
    padding: 3px;
}

QGroupBox {
    border: 1px solid #232a3e;
    border-radius: 10px;
    margin-top: 12px;
    padding: 12px 10px 10px 10px;
    font-weight: 600;
    color: #cbd5e1;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #a5b4fc;
}

QProgressBar {
    background-color: #1a1f2e;
    border: none;
    border-radius: 2px;
    height: 3px;
}

QProgressBar::chunk {
    background-color: #6366f1;
    border-radius: 2px;
}

QCheckBox {
    spacing: 8px;
}

QTabWidget::pane {
    border: 1px solid #232a3e;
    border-radius: 10px;
    background-color: #131722;
    padding: 8px;
}

QTabBar::tab {
    background-color: #181d2b;
    border: 1px solid #232a3e;
    border-bottom: none;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    padding: 7px 14px;
    margin-right: 4px;
    color: #9ba6c4;
}

QTabBar::tab:selected {
    background-color: #21283d;
    color: #ffffff;
    font-weight: 600;
}

QScrollArea {
    background-color: transparent;
    border: none;
}

QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 2px 0;
}

QScrollBar::handle:vertical {
    background: #2d354d;
    border-radius: 4px;
    min-height: 24px;
}

QScrollBar::handle:vertical:hover {
    background: #434f73;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
    height: 0;
}
"""


def create_app_icon(size: int = 64) -> QIcon:
    """Render a crisp vector icon (indigo badge with crop corners + 'A' OCR motif)."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    grad = QLinearGradient(0, 0, size, size)
    grad.setColorAt(0.0, QColor("#6366f1"))
    grad.setColorAt(1.0, QColor("#3b82f6"))
    painter.setBrush(grad)
    painter.setPen(Qt.PenStyle.NoPen)
    radius = size * 0.24
    painter.drawRoundedRect(QRectF(2, 2, size - 4, size - 4), radius, radius)

    pen = QPen(QColor("#ffffff"))
    pen.setWidthF(max(2.0, size * 0.065))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)

    m = size * 0.19
    arm = size * 0.16
    painter.drawLine(int(m), int(m), int(m + arm), int(m))
    painter.drawLine(int(m), int(m), int(m), int(m + arm))
    painter.drawLine(int(size - m), int(m), int(size - m - arm), int(m))
    painter.drawLine(int(size - m), int(m), int(size - m), int(m + arm))
    painter.drawLine(int(m), int(size - m), int(m + arm), int(size - m))
    painter.drawLine(int(m), int(size - m), int(m), int(size - m - arm))
    painter.drawLine(int(size - m), int(size - m), int(size - m - arm), int(size - m))
    painter.drawLine(int(size - m), int(size - m), int(size - m), int(size - m - arm))

    font = QFont("Segoe UI", int(size * 0.34), QFont.Weight.Bold)
    painter.setFont(font)
    painter.setPen(QColor("#ffffff"))
    painter.drawText(QRectF(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, "A")

    painter.end()
    return QIcon(pixmap)
