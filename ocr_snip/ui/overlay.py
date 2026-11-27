"""Fullscreen Win+Shift+S-style snipping selection overlay."""

from __future__ import annotations

import logging

from PIL import Image
from PyQt6.QtCore import QPoint, QPointF, QRect, QRectF, Qt, pyqtSignal
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
from ocr_snip.ui.theme import THEME

logger = logging.getLogger("ocr_snip.overlay")


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
        try:
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
        except Exception:
            logger.exception("Error completing snip capture; closing overlay safely")
            self._cancel()

    def _cancel(self) -> None:
        self._dragging = False
        self.hide()
        self.cancelled.emit()
        self.close()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            # 1. Draw the frozen desktop screenshot scaled cleanly to widget size
            painter.drawPixmap(self.rect(), self._pixmap)

            # 2. Flat understated ink scrim: rgba(26, 26, 24, 0.35)
            dim_color = QColor(*THEME.scrim_rgba)
            rect = self.selection_rect
            if self._dragging and rect.width() > 1 and rect.height() > 1:
                path = QPainterPath()
                path.addRect(QRectF(self.rect()))
                path.addRect(QRectF(rect))
                path.setFillRule(Qt.FillRule.OddEvenFill)
                painter.fillPath(path, dim_color)

                # Sharp 1.5px solid Stamp Vermilion (#C83E2B) selection border
                border_pen = QPen(QColor(THEME.vermilion), 1.5, Qt.PenStyle.SolidLine)
                border_pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
                painter.setPen(border_pen)
                painter.drawRect(QRectF(rect))

                # Crisp hairline corner ticks (drafting/stationery crop marks)
                self._draw_corner_handles(painter, rect)

                # Printed paper dimension tag near cursor
                self._draw_dimensions_pill(painter, rect)
            else:
                painter.fillRect(self.rect(), dim_color)
                # Subtle drafting hairline guides before dragging
                if self._cursor_pos.x() >= 0:
                    guide_pen = QPen(QColor(247, 245, 240, 110), 1.0, Qt.PenStyle.SolidLine)
                    painter.setPen(guide_pen)
                    painter.drawLine(0, self._cursor_pos.y(), self.width(), self._cursor_pos.y())
                    painter.drawLine(self._cursor_pos.x(), 0, self._cursor_pos.x(), self.height())

            # 3. Top-center printed instruction slip
            self._draw_instruction_banner(painter)
        except Exception:
            logger.exception("SnipOverlay paint error; dismissing overlay safely")
            if painter.isActive():
                painter.end()
            self._cancel()
            return
        finally:
            if painter.isActive():
                painter.end()

    def _draw_corner_handles(self, painter: QPainter, rect: QRect) -> None:
        """Draw crisp hairline drafting corner ticks outside the Vermilion selection frame."""
        tick = 7.0
        gap = 3.0
        pen = QPen(QColor(THEME.vermilion), 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.SquareCap)
        painter.setPen(pen)

        left = float(rect.left())
        right = float(rect.right())
        top = float(rect.top())
        bottom = float(rect.bottom())

        # Top-left
        painter.drawLine(QPointF(left - gap, top - gap), QPointF(left - gap + tick, top - gap))
        painter.drawLine(QPointF(left - gap, top - gap), QPointF(left - gap, top - gap + tick))
        # Top-right
        painter.drawLine(QPointF(right + gap, top - gap), QPointF(right + gap - tick, top - gap))
        painter.drawLine(QPointF(right + gap, top - gap), QPointF(right + gap, top - gap + tick))
        # Bottom-left
        painter.drawLine(QPointF(left - gap, bottom + gap), QPointF(left - gap + tick, bottom + gap))
        painter.drawLine(QPointF(left - gap, bottom + gap), QPointF(left - gap, bottom + gap - tick))
        # Bottom-right
        painter.drawLine(QPointF(right + gap, bottom + gap), QPointF(right + gap - tick, bottom + gap))
        painter.drawLine(QPointF(right + gap, bottom + gap), QPointF(right + gap, bottom + gap - tick))

    def _draw_dimensions_pill(self, painter: QPainter, rect: QRect) -> None:
        """Draw a crisp printed paper coordinate/size tag near the selection."""
        label = f"{rect.width()} × {rect.height()} PX"
        font = QFont("Consolas", 9, QFont.Weight.DemiBold)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.8)
        painter.setFont(font)
        fm = painter.fontMetrics()
        tw = fm.horizontalAdvance(label) + 26
        th = fm.height() + 8

        px = float(rect.left())
        py = float(rect.top() - th - 10)
        if py < 56:
            py = float(rect.bottom() + 10)
        px = max(8.0, min(float(self.width() - tw - 8), px))

        tag = QRectF(px, py, float(tw), float(th))
        painter.setPen(QPen(QColor(THEME.ink), 1.0))
        painter.setBrush(QColor(THEME.paper))
        painter.drawRoundedRect(tag, 2.0, 2.0)

        # 5x5px Stamp Vermilion active capture square
        sq_x = px + 8.0
        sq_y = py + (th - 5.0) / 2.0
        painter.fillRect(QRectF(sq_x, sq_y, 5.0, 5.0), QColor(THEME.vermilion))

        text_rect = QRectF(px + 18.0, py, float(tw - 22), float(th))
        painter.setPen(QColor(THEME.ink))
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, label)

    def _draw_instruction_banner(self, painter: QPainter) -> None:
        """Draw a flat printed paper instruction slip at top-center."""
        text = "DRAG TO CAPTURE  ·  ESC OR RIGHT-CLICK TO CANCEL"
        font = QFont("Consolas", 9, QFont.Weight.DemiBold)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.9)
        painter.setFont(font)
        fm = painter.fontMetrics()
        tw = fm.horizontalAdvance(text) + 34
        th = fm.height() + 14

        bx = (self.width() - tw) / 2.0
        by = 18.0
        banner = QRectF(bx, by, float(tw), float(th))
        painter.setPen(QPen(QColor(THEME.ink), 1.0))
        painter.setBrush(QColor(THEME.paper))
        painter.drawRoundedRect(banner, 2.0, 2.0)

        # 5x5px Stamp Vermilion square
        sq_x = bx + 11.0
        sq_y = by + (th - 5.0) / 2.0
        painter.fillRect(QRectF(sq_x, sq_y, 5.0, 5.0), QColor(THEME.vermilion))

        text_rect = QRectF(bx + 22.0, by, float(tw - 28), float(th))
        painter.setPen(QColor(THEME.ink))
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text)
