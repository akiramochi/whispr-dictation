"""Programmatically drawn icons so the app ships with no binary assets."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QIcon, QLinearGradient, QPainter, QPen, QPixmap


def mic_pixmap(size: int = 64, accent: str = "#6C8CFF", glyph: str = "#FFFFFF") -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)

    # Rounded gradient background.
    grad = QLinearGradient(0, 0, size, size)
    base = QColor(accent)
    grad.setColorAt(0.0, base.lighter(115))
    grad.setColorAt(1.0, base.darker(120))
    p.setBrush(QBrush(grad))
    p.setPen(Qt.NoPen)
    r = size * 0.16
    p.drawRoundedRect(QRectF(0, 0, size, size), r, r)

    # Microphone glyph.
    c = QColor(glyph)
    p.setPen(QPen(c, max(2.0, size * 0.05), Qt.SolidLine, Qt.RoundCap))
    p.setBrush(QBrush(c))
    body_w = size * 0.26
    body_h = size * 0.40
    cx = size / 2
    top = size * 0.20
    p.drawRoundedRect(
        QRectF(cx - body_w / 2, top, body_w, body_h), body_w / 2, body_w / 2
    )
    # Arc cradle.
    p.setBrush(Qt.NoBrush)
    arc_r = size * 0.22
    arc_rect = QRectF(cx - arc_r, top + body_h * 0.35, arc_r * 2, arc_r * 2)
    p.drawArc(arc_rect, 200 * 16, 140 * 16)
    # Stand.
    stem_top = top + body_h * 0.35 + arc_r * 2 * 0.55
    p.drawLine(QPointF(cx, stem_top), QPointF(cx, size * 0.82))
    p.drawLine(QPointF(cx - size * 0.12, size * 0.82), QPointF(cx + size * 0.12, size * 0.82))
    p.end()
    return pm


def mic_icon(accent: str = "#6C8CFF") -> QIcon:
    icon = QIcon()
    for s in (16, 24, 32, 48, 64, 128):
        icon.addPixmap(mic_pixmap(s, accent))
    return icon
