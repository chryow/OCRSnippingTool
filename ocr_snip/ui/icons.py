"""Crisp, HiDPI-aware monochrome vector icons rendered via QPainter.

Eliminates inconsistent OS color emojis (Segoe UI Emoji / Apple Color Emoji) and
requires zero external asset files when bundled with PyInstaller.
"""

from __future__ import annotations

from functools import lru_cache

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap


def _render_icon_pixmap(name: str, size: int, color: str, scale: int = 2) -> QPixmap:
    px = size * scale
    pixmap = QPixmap(px, px)
    pixmap.fill(Qt.GlobalColor.transparent)
    pixmap.setDevicePixelRatio(float(scale))

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    c = QColor(color)
    stroke = max(1.4, size * 0.095)
    pen = QPen(c, stroke, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    # Draw in a normalized 16x16 logical coordinate space scaled to `size`
    s = size / 16.0
    painter.scale(s, s)
    pen.setWidthF(1.5)
    painter.setPen(pen)

    if name == "snip":
        # Clean viewfinder crop corners
        painter.drawPolyline([QPointF(2.5, 5.5), QPointF(2.5, 2.5), QPointF(5.5, 2.5)])
        painter.drawPolyline([QPointF(10.5, 2.5), QPointF(13.5, 2.5), QPointF(13.5, 5.5)])
        painter.drawPolyline([QPointF(2.5, 10.5), QPointF(2.5, 13.5), QPointF(5.5, 13.5)])
        painter.drawPolyline([QPointF(10.5, 13.5), QPointF(13.5, 13.5), QPointF(13.5, 10.5)])
        painter.drawLine(QPointF(8.0, 5.5), QPointF(8.0, 10.5))
        painter.drawLine(QPointF(5.5, 8.0), QPointF(10.5, 8.0))

    elif name == "history":
        painter.drawEllipse(QRectF(2.5, 2.5, 11.0, 11.0))
        painter.drawPolyline([QPointF(8.0, 5.0), QPointF(8.0, 8.2), QPointF(10.4, 9.6)])

    elif name in ("pin", "pin_filled"):
        path = QPainterPath()
        path.moveTo(9.8, 2.4)
        path.lineTo(13.6, 6.2)
        path.lineTo(11.6, 8.2)
        path.lineTo(11.0, 10.4)
        path.lineTo(5.6, 5.0)
        path.lineTo(7.8, 4.4)
        path.closeSubpath()
        if name == "pin_filled":
            painter.setBrush(c)
        painter.drawPath(path)
        painter.drawLine(QPointF(8.2, 7.8), QPointF(3.0, 13.0))

    elif name == "settings":
        # Minimal 3-row horizontal sliders (cleaner than chunky gear at 16px)
        for y, knob_x in ((4.0, 10.2), (8.0, 5.8), (12.0, 9.5)):
            painter.drawLine(QPointF(2.5, y), QPointF(knob_x - 1.6, y))
            painter.drawLine(QPointF(knob_x + 1.6, y), QPointF(13.5, y))
            painter.drawEllipse(QPointF(knob_x, y), 1.5, 1.5)

    elif name == "close":
        painter.drawLine(QPointF(4.0, 4.0), QPointF(12.0, 12.0))
        painter.drawLine(QPointF(12.0, 4.0), QPointF(4.0, 12.0))

    elif name == "copy":
        painter.drawRoundedRect(QRectF(5.5, 5.5, 8.0, 8.0), 1.6, 1.6)
        path = QPainterPath()
        path.moveTo(5.5, 10.5)
        path.lineTo(4.0, 10.5)
        path.quadTo(2.5, 10.5, 2.5, 9.0)
        path.lineTo(2.5, 4.0)
        path.quadTo(2.5, 2.5, 4.0, 2.5)
        path.lineTo(9.0, 2.5)
        path.quadTo(10.5, 2.5, 10.5, 4.0)
        path.lineTo(10.5, 5.5)
        painter.drawPath(path)

    elif name == "check":
        painter.drawPolyline([QPointF(3.0, 8.4), QPointF(6.5, 11.8), QPointF(13.0, 4.5)])

    elif name == "translate":
        painter.drawEllipse(QRectF(2.3, 2.3, 11.4, 11.4))
        painter.drawLine(QPointF(2.5, 8.0), QPointF(13.5, 8.0))
        painter.drawEllipse(QRectF(5.4, 2.3, 5.2, 11.4))

    elif name == "enhance":
        # Subtle monochrome 4-point star
        path = QPainterPath()
        path.moveTo(8.0, 2.0)
        path.quadTo(8.3, 7.7, 14.0, 8.0)
        path.quadTo(8.3, 8.3, 8.0, 14.0)
        path.quadTo(7.7, 8.3, 2.0, 8.0)
        path.quadTo(7.7, 7.7, 8.0, 2.0)
        painter.drawPath(path)

    elif name == "unwrap":
        painter.drawLine(QPointF(2.5, 4.0), QPointF(13.5, 4.0))
        painter.drawLine(QPointF(2.5, 8.0), QPointF(13.5, 8.0))
        painter.drawLine(QPointF(2.5, 12.0), QPointF(9.5, 12.0))

    elif name == "clipboard":
        painter.drawRoundedRect(QRectF(3.2, 3.8, 9.6, 10.2), 1.6, 1.6)
        painter.drawRoundedRect(QRectF(5.8, 2.2, 4.4, 2.6), 0.9, 0.9)

    elif name == "image":
        painter.drawRoundedRect(QRectF(2.3, 3.0, 11.4, 10.0), 1.6, 1.6)
        painter.drawEllipse(QPointF(5.7, 6.2), 1.0, 1.0)
        painter.drawPolyline([QPointF(3.0, 12.0), QPointF(6.5, 8.8), QPointF(9.0, 11.0), QPointF(11.0, 9.2), QPointF(13.2, 11.8)])

    elif name == "timer":
        painter.drawLine(QPointF(6.2, 2.2), QPointF(9.8, 2.2))
        painter.drawEllipse(QRectF(3.0, 4.0, 10.0, 10.0))
        painter.drawLine(QPointF(8.0, 9.0), QPointF(10.5, 6.8))

    elif name == "folder":
        path = QPainterPath()
        path.moveTo(2.3, 4.2)
        path.lineTo(6.4, 4.2)
        path.lineTo(7.8, 5.8)
        path.lineTo(13.7, 5.8)
        path.lineTo(13.7, 12.6)
        path.lineTo(2.3, 12.6)
        path.closeSubpath()
        painter.drawPath(path)

    elif name == "quit":
        painter.drawArc(QRectF(3.0, 3.5, 10.0, 10.0), 130 * 16, 280 * 16)
        painter.drawLine(QPointF(8.0, 2.2), QPointF(8.0, 7.6))

    elif name in ("star", "star_filled"):
        pts = [
            QPointF(8.0, 2.2),
            QPointF(9.8, 5.8),
            QPointF(13.8, 6.4),
            QPointF(10.9, 9.2),
            QPointF(11.6, 13.2),
            QPointF(8.0, 11.3),
            QPointF(4.4, 13.2),
            QPointF(5.1, 9.2),
            QPointF(2.2, 6.4),
            QPointF(6.2, 5.8),
        ]
        path = QPainterPath()
        path.moveTo(pts[0])
        for p in pts[1:]:
            path.lineTo(p)
        path.closeSubpath()
        if name == "star_filled":
            painter.setBrush(c)
        painter.drawPath(path)

    elif name == "trash":
        painter.drawLine(QPointF(2.8, 4.5), QPointF(13.2, 4.5))
        painter.drawLine(QPointF(6.0, 4.5), QPointF(6.5, 2.6))
        painter.drawLine(QPointF(10.0, 4.5), QPointF(9.5, 2.6))
        painter.drawLine(QPointF(6.5, 2.6), QPointF(9.5, 2.6))
        painter.drawPolyline([QPointF(4.0, 4.5), QPointF(4.7, 13.2), QPointF(11.3, 13.2), QPointF(12.0, 4.5)])

    elif name == "eye":
        path = QPainterPath()
        path.moveTo(2.0, 8.0)
        path.quadTo(8.0, 3.0, 14.0, 8.0)
        path.quadTo(8.0, 13.0, 2.0, 8.0)
        painter.drawPath(path)
        painter.drawEllipse(QPointF(8.0, 8.0), 1.8, 1.8)

    elif name == "chevron_down":
        painter.drawPolyline([QPointF(4.2, 6.2), QPointF(8.0, 10.0), QPointF(11.8, 6.2)])

    elif name == "swap":
        # Crisp horizontal swap arrows (⇄)
        painter.drawLine(QPointF(3.0, 5.5), QPointF(13.0, 5.5))
        painter.drawPolyline([QPointF(10.5, 3.2), QPointF(13.0, 5.5), QPointF(10.5, 7.8)])
        painter.drawLine(QPointF(13.0, 10.5), QPointF(3.0, 10.5))
        painter.drawPolyline([QPointF(5.5, 8.2), QPointF(3.0, 10.5), QPointF(5.5, 12.8)])

    painter.end()
    return pixmap


@lru_cache(maxsize=128)
def svg_icon(name: str, size: int = 16, color: str = "#1A1A18") -> QIcon:
    """Return a cached crisp monochrome vector QIcon tuned for Editorial E-Ink surfaces."""
    icon = QIcon()
    icon.addPixmap(_render_icon_pixmap(name, size, color), QIcon.Mode.Normal, QIcon.State.Off)
    icon.addPixmap(_render_icon_pixmap(name, size, color), QIcon.Mode.Active, QIcon.State.Off)
    icon.addPixmap(_render_icon_pixmap(name, size, "#B5B1A7"), QIcon.Mode.Disabled, QIcon.State.Off)
    return icon
