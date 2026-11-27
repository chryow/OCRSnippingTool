"""Modern dark slate theme stylesheet and vector app icon generator."""

from __future__ import annotations

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QIcon, QLinearGradient, QPainter, QPen, QPixmap

DARK_STYLESHEET = """
QWidget {
    color: #e6e9f2;
    font-family: "Segoe UI", "Inter", "Noto Sans", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}

QDialog, QFrame#PopupCard {
    background-color: #131620;
    border: 1px solid #282e42;
    border-radius: 14px;
}

QFrame#HeaderBar {
    background-color: #191d2b;
    border-top-left-radius: 13px;
    border-top-right-radius: 13px;
    border-bottom: 1px solid #252b3d;
}

QLabel#TitleLabel {
    font-size: 13px;
    font-weight: 600;
    color: #f3f5fc;
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
    background-color: #1d2233;
    border: 1px solid #2e354d;
    color: #9ca7c4;
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
    background-color: rgba(245, 158, 11, 0.16);
    border: 1px solid rgba(251, 191, 36, 0.4);
    color: #fcd34d;
    border-radius: 10px;
    padding: 3px 9px;
    font-size: 11px;
}

QLabel#MutedLabel {
    color: #8892b0;
    font-size: 11px;
}

QPlainTextEdit {
    background-color: #0e1018;
    border: 1px solid #252b3d;
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

QPushButton {
    background-color: #202536;
    border: 1px solid #2f364d;
    border-radius: 8px;
    padding: 6px 12px;
    color: #e2e8f0;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #293047;
    border-color: #444f73;
}

QPushButton:pressed {
    background-color: #1a1f2e;
}

QPushButton:disabled {
    color: #5b647d;
    background-color: #171b27;
    border-color: #222738;
}

QPushButton#PrimaryButton {
    background-color: #4f46e5;
    border: 1px solid #6366f1;
    color: #ffffff;
    font-weight: 600;
}

QPushButton#PrimaryButton:hover {
    background-color: #5b52f0;
}

QPushButton#PrimaryButton:pressed {
    background-color: #4338ca;
}

QPushButton#AIButton {
    background-color: rgba(139, 92, 246, 0.18);
    border: 1px solid rgba(167, 139, 250, 0.45);
    color: #ddd6fe;
    font-weight: 600;
}

QPushButton#AIButton:hover {
    background-color: rgba(139, 92, 246, 0.30);
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

QFrame#TranslatePanel {
    background-color: #111522;
    border: 1px solid #26314a;
    border-radius: 10px;
}

QPushButton#IconButton {
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 4px 7px;
    color: #9ca7c4;
    font-size: 13px;
}

QPushButton#IconButton:hover {
    background-color: #252b3d;
    color: #f8fafc;
}

QPushButton#IconButton:checked {
    background-color: rgba(99, 102, 241, 0.25);
    border-color: rgba(129, 140, 248, 0.45);
    color: #c7d2fe;
}

QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox {
    background-color: #0e1018;
    border: 1px solid #2b3248;
    border-radius: 8px;
    padding: 5px 10px;
    color: #f1f5f9;
}

QComboBox:focus, QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border-color: #6366f1;
}

QComboBox::drop-down {
    border: none;
    width: 22px;
}

QComboBox QAbstractItemView {
    background-color: #161a26;
    border: 1px solid #2f364d;
    selection-background-color: #4f46e5;
    color: #f1f5f9;
}

QGroupBox {
    border: 1px solid #252b3d;
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
    background-color: #1b2030;
    border: none;
    border-radius: 3px;
    height: 4px;
}

QProgressBar::chunk {
    background-color: #6366f1;
    border-radius: 3px;
}

QCheckBox {
    spacing: 8px;
}

QTabWidget::pane {
    border: 1px solid #252b3d;
    border-radius: 10px;
    background-color: #131620;
    padding: 8px;
}

QTabBar::tab {
    background-color: #191d2b;
    border: 1px solid #252b3d;
    border-bottom: none;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    padding: 7px 14px;
    margin-right: 4px;
    color: #9ca7c4;
}

QTabBar::tab:selected {
    background-color: #22283c;
    color: #ffffff;
    font-weight: 600;
}
"""


def create_app_icon(size: int = 64) -> QIcon:
    """Render a crisp vector icon (indigo badge with crop corners + 'A' OCR motif)."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Rounded gradient background
    grad = QLinearGradient(0, 0, size, size)
    grad.setColorAt(0.0, QColor("#6366f1"))
    grad.setColorAt(1.0, QColor("#3b82f6"))
    painter.setBrush(grad)
    painter.setPen(Qt.PenStyle.NoPen)
    radius = size * 0.24
    painter.drawRoundedRect(QRectF(2, 2, size - 4, size - 4), radius, radius)

    # Crisp white snipping corner brackets
    pen = QPen(QColor("#ffffff"))
    pen.setWidthF(max(2.0, size * 0.065))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)

    m = size * 0.19
    arm = size * 0.16
    # Top-left
    painter.drawLine(int(m), int(m), int(m + arm), int(m))
    painter.drawLine(int(m), int(m), int(m), int(m + arm))
    # Top-right
    painter.drawLine(int(size - m), int(m), int(size - m - arm), int(m))
    painter.drawLine(int(size - m), int(m), int(size - m), int(m + arm))
    # Bottom-left
    painter.drawLine(int(m), int(size - m), int(m + arm), int(size - m))
    painter.drawLine(int(m), int(size - m), int(m), int(size - m - arm))
    # Bottom-right
    painter.drawLine(int(size - m), int(size - m), int(size - m - arm), int(size - m))
    painter.drawLine(int(size - m), int(size - m), int(size - m), int(size - m - arm))

    # Center "A" glyph representing text extraction
    font = QFont("Segoe UI", int(size * 0.34), QFont.Weight.Bold)
    painter.setFont(font)
    painter.setPen(QColor("#ffffff"))
    painter.drawText(QRectF(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, "A")

    painter.end()
    return QIcon(pixmap)
