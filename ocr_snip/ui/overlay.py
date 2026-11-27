"""Fullscreen Win+Shift+S-style snipping selection overlay."""

from __future__ import annotations

from PIL import Image
from PyQt6.QtCore import QPoint, QRect, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QFont,
    QGuiApplication,
    QImage,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PyQt6.QtWidgets import QWidget

from ocr_snip.capture.screenshot import ScreenCapture


def _logical_virtual_geometry(capture: ScreenCapture) -> QRect:
    """Return the Qt logical virtual-desktop bounding box across all screens.

    On HiDPI displays (e.g. Windows 150%/200% scaling), `mss` reports physical
    pixels whereas Qt window geometry uses logical coordinates. Computing the
    union of `QScreen.geometry()` keeps the overlay aligned across all monitors.
    """
    screens = QGuiApplication.screens()
    if screens:
        virtual = QRect()
        for screen in screens:
            virtual = virtual.united(screen.geometry())
        if virtual.isValid() and virtual.width() > 0 and virtual.height() > 0:
            return virtual
    return QRect(capture.left, capture.top, capture.width, capture.height)


def pil_to_qpixmap(image: Image.Image) -> QPixmap:
    """Convert a PIL RGB Image to a QPixmap safely."""
    rgb = image.convert("RGB")
    data = rgb.tobytes("raw", "RGB")
    qimg = QImage(data, rgb.width, rgb.height, rgb.width * 3, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(qimg.copy())


class SnipOverlay(QWidget):
    """Frozen fullscreen overlay allowing rectangular snip selection for OCR."""

    region_captured = pyqtSignal(object, QPoint)  # (PIL.Image.Image, release_global_pos)
    cancelled = pyqtSignal()

    MIN_SELECTION_PX = 8

    def __init__(self, capture: ScreenCapture, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._capture = capture
        self._pixmap = pil_to_qpixmap(capture.image)

        self._dragging = False
        self._origin = QPoint()
        self._current = QPoint()
        self._cursor_pos = QPoint(-1, -1)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setMouseTracking(True)

        # Span the full logical virtual desktop across all monitors (HiDPI-safe)
        self.setGeometry(_logical_virtual_geometry(capture))

    @property
    def selection_rect(self) -> QRect:
        if not self._dragging and self._origin == self._current:
            return QRect()
        return QRect(self._origin, self._current).normalized()

    def keyPressEvent(self, event: QKeyEvent | None) -> None:
        if event and event.key() == Qt.Key.Key_Escape:
            self._cancel()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        if event is None:
            return
        if event.button() == Qt.MouseButton.RightButton:
            self._cancel()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._origin = event.position().toPoint()
            self._current = self._origin
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent | None) -> None:
        if event is None:
            return
        pos = event.position().toPoint()
        self._cursor_pos = pos
        if self._dragging:
            self._current = pos
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent | None) -> None:
        if event is None or event.button() != Qt.MouseButton.LeftButton or not self._dragging:
            return
        self._dragging = False
        self._current = event.position().toPoint()
        rect = self.selection_rect
        global_pos = event.globalPosition().toPoint()

        if rect.width() < self.MIN_SELECTION_PX or rect.height() < self.MIN_SELECTION_PX:
            self._cancel()
            return

        cropped = self._capture.crop_from_overlay_rect(
            rect.x(),
            rect.y(),
            rect.width(),
            rect.height(),
            self.width(),
            self.height(),
        )
        self.hide()
        self.region_captured.emit(cropped, global_pos)
        self.close()

    def _cancel(self) -> None:
        self.hide()
        self.cancelled.emit()
        self.close()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 1. Draw the frozen desktop screenshot scaled cleanly to widget size
        painter.drawPixmap(self.rect(), self._pixmap)

        # 2. Dim the entire screen EXCEPT the selected rectangle
        dim_color = QColor(9, 9, 11, 138)
        rect = self.selection_rect
        if self._dragging and rect.width() > 1 and rect.height() > 1:
            path = QPainterPath()
            path.addRect(QRectF(self.rect()))
            path.addRect(QRectF(rect))
            path.setFillRule(Qt.FillRule.OddEvenFill)
            painter.fillPath(path, dim_color)

            # Subtle dark outer contrast stroke + crisp pure-white selection frame
            painter.setPen(QPen(QColor(0, 0, 0, 140), 3))
            painter.drawRect(rect)
            painter.setPen(QPen(QColor("#ffffff"), 1.5))
            painter.drawRect(rect)

            # Minimal corner handles
            self._draw_corner_handles(painter, rect)

            # Floating dimensions pill
            self._draw_dimensions_pill(painter, rect)
        else:
            painter.fillRect(self.rect(), dim_color)
            # Subtle hairline crosshair guides before dragging
            if self._cursor_pos.x() >= 0:
                guide_pen = QPen(QColor(255, 255, 255, 38), 1, Qt.PenStyle.SolidLine)
                painter.setPen(guide_pen)
                painter.drawLine(0, self._cursor_pos.y(), self.width(), self._cursor_pos.y())
                painter.drawLine(self._cursor_pos.x(), 0, self._cursor_pos.x(), self.height())

        # 3. Top-center instruction pill
        self._draw_instruction_banner(painter)
        painter.end()

    def _draw_corner_handles(self, painter: QPainter, rect: QRect) -> None:
        painter.setBrush(QColor("#ffffff"))
        painter.setPen(QPen(QColor("#18181b"), 1.2))
        r = 3.5
        for pt in (rect.topLeft(), rect.topRight(), rect.bottomLeft(), rect.bottomRight()):
            painter.drawEllipse(pt, r, r)

    def _draw_dimensions_pill(self, painter: QPainter, rect: QRect) -> None:
        label = f"{rect.width()} × {rect.height()}"
        font = QFont("Segoe UI", 9, QFont.Weight.DemiBold)
        painter.setFont(font)
        fm = painter.fontMetrics()
        tw = fm.horizontalAdvance(label) + 16
        th = fm.height() + 8

        px = rect.left()
        py = rect.top() - th - 8
        if py < 56:
            py = rect.bottom() + 8
        px = max(8, min(self.width() - tw - 8, px))

        pill = QRectF(px, py, tw, th)
        painter.setPen(QPen(QColor(255, 255, 255, 38), 1))
        painter.setBrush(QColor(20, 20, 23, 230))
        painter.drawRoundedRect(pill, 6, 6)
        painter.setPen(QColor("#f4f4f5"))
        painter.drawText(pill, Qt.AlignmentFlag.AlignCenter, label)

    def _draw_instruction_banner(self, painter: QPainter) -> None:
        text = "Drag to capture text  ·  Esc or Right-Click to cancel"
        font = QFont("Segoe UI", 10, QFont.Weight.Medium)
        painter.setFont(font)
        fm = painter.fontMetrics()
        tw = fm.horizontalAdvance(text) + 32
        th = fm.height() + 14

        bx = (self.width() - tw) / 2
        by = 20
        banner = QRectF(bx, by, tw, th)
        painter.setPen(QPen(QColor(255, 255, 255, 34), 1))
        painter.setBrush(QColor(20, 20, 23, 230))
        painter.drawRoundedRect(banner, th / 2, th / 2)
        painter.setPen(QColor("#f4f4f5"))
        painter.drawText(banner, Qt.AlignmentFlag.AlignCenter, text)
