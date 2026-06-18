"""Floating recording indicator shown near the bottom of the screen.

A frameless, always-on-top, non-activating pill that never steals focus from
the app you are dictating into. It renders a live waveform while listening, a
pulsing state while transcribing, and a brief confirmation when done.
"""
from __future__ import annotations

import random

from PySide6.QtCore import QPointF, QPropertyAnimation, QRectF, Qt, QTimer, Property, QObject
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

LISTENING, TRANSCRIBING, DONE, ERROR = "listening", "transcribing", "done", "error"
NUM_BARS = 28


class _Fader(QObject):
    """Drives a 0..1 opacity value the widget animates on show/hide."""

    def __init__(self, widget: "Overlay"):
        super().__init__(widget)
        self._w = widget
        self._v = 0.0

    def getv(self) -> float:
        return self._v

    def setv(self, v: float) -> None:
        self._v = v
        self._w.setWindowOpacity(v)

    value = Property(float, getv, setv)


class Overlay(QWidget):
    def __init__(self, recorder, accent: str = "#6C8CFF"):
        super().__init__()
        self.recorder = recorder
        self.accent = QColor(accent)
        self.state = LISTENING
        self.message = ""
        self.partial_text = ""
        self._phase = 0.0
        self._bars = [0.06] * NUM_BARS

        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFixedSize(460, 96)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

        self._fader = _Fader(self)
        self._anim = QPropertyAnimation(self._fader, b"value", self)
        self._anim.setDuration(180)
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._fade_out)

    # --- positioning -----------------------------------------------------
    def _reposition(self) -> None:
        screen = self.screen() or self.windowHandle().screen()
        geo = screen.availableGeometry()
        x = geo.x() + (geo.width() - self.width()) // 2
        y = geo.y() + geo.height() - self.height() - 64
        self.move(x, y)

    # --- public state transitions ---------------------------------------
    def show_listening(self) -> None:
        self.state = LISTENING
        self.message = ""
        self.partial_text = ""
        self._bars = [0.06] * NUM_BARS
        self._hide_timer.stop()
        self._reposition()
        self.show()
        self.raise_()
        self._timer.start(33)
        self._fade_in()

    def set_partial(self, text: str) -> None:
        """Update the live transcript shown while listening."""
        if self.state == LISTENING:
            self.partial_text = text
            self.update()

    def show_transcribing(self) -> None:
        self.state = TRANSCRIBING
        self.message = "Transcribing…"
        self.update()

    def show_done(self, text: str) -> None:
        self.state = DONE
        words = len(text.split())
        self.message = f"Inserted {words} word{'s' if words != 1 else ''}" if words else "Nothing heard"
        self.update()
        self._hide_timer.start(900)

    def show_error(self, msg: str) -> None:
        self.state = ERROR
        self.message = msg
        self.update()
        self._hide_timer.start(2600)

    # --- animation -------------------------------------------------------
    def _tick(self) -> None:
        self._phase += 0.18
        if self.state == LISTENING:
            level = max(0.04, min(1.0, self.recorder.level))
            self._bars.pop(0)
            jitter = level * (0.6 + 0.4 * random.random())
            self._bars.append(jitter)
        self.update()

    def _fade_in(self) -> None:
        self._anim.stop()
        # Drop any leftover finished->hide handler from a previous fade-out,
        # otherwise completing this fade-in would immediately hide the pill.
        try:
            self._anim.finished.disconnect()
        except (RuntimeError, TypeError):
            pass
        self._anim.setStartValue(self.windowOpacity())
        self._anim.setEndValue(1.0)
        self._anim.start()

    def _fade_out(self) -> None:
        self._timer.stop()
        self._anim.stop()
        self._anim.setStartValue(self.windowOpacity())
        self._anim.setEndValue(0.0)
        try:
            self._anim.finished.disconnect()
        except (RuntimeError, TypeError):
            pass
        self._anim.finished.connect(self.hide)
        self._anim.start()

    # --- painting --------------------------------------------------------
    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(2, 2, self.width() - 4, self.height() - 4)

        path = QPainterPath()
        path.addRoundedRect(rect, 22, 22)
        p.fillPath(path, QColor(22, 24, 32, 235))
        p.setPen(QPen(QColor(255, 255, 255, 26), 1))
        p.drawPath(path)

        if self.state == LISTENING:
            if self.partial_text:
                # Compact meter on top, live transcript filling the rest.
                cy = 28
                self._paint_dot(p, self.accent, cy)
                self._paint_waveform(p, cy, scale=0.30)
                self._paint_partial(p)
            else:
                self._paint_dot(p, self.accent, self.height() / 2)
                self._paint_waveform(p, self.height() / 2, scale=0.62)
        elif self.state == TRANSCRIBING:
            self._paint_spinner(p)
            self._paint_label(p, self.message, QColor(220, 224, 235))
        elif self.state == DONE:
            self._paint_check(p)
            self._paint_label(p, self.message, QColor(180, 230, 190))
        else:  # ERROR
            self._paint_dot(p, QColor("#FF6B6B"))
            self._paint_label(p, self.message, QColor(255, 170, 170))
        p.end()

    def _paint_dot(self, p: QPainter, color: QColor, cy: float) -> None:
        pulse = 0.55 + 0.45 * abs((self._phase % 2.0) - 1.0)
        c = QColor(color)
        c.setAlphaF(pulse)
        p.setBrush(c)
        p.setPen(Qt.NoPen)
        p.drawEllipse(24, cy - 5, 10, 10)

    def _paint_waveform(self, p: QPainter, cy: float, scale: float) -> None:
        left = 50
        right = self.width() - 24
        span = right - left
        bw = span / NUM_BARS
        p.setPen(Qt.NoPen)
        for i, v in enumerate(self._bars):
            h = max(3.0, v * (self.height() * scale))
            x = left + i * bw
            c = QColor(self.accent)
            c.setAlphaF(0.45 + 0.55 * v)
            p.setBrush(c)
            p.drawRoundedRect(QRectF(x, cy - h / 2, bw * 0.55, h), bw * 0.27, bw * 0.27)

    def _paint_partial(self, p: QPainter) -> None:
        f = QFont("Segoe UI", 12)
        p.setFont(f)
        fm = p.fontMetrics()
        avail = self.width() - 48
        # Show the tail of the transcript so the newest words stay visible.
        text = self.partial_text
        elided = fm.elidedText(text, Qt.ElideLeft, int(avail))
        p.setPen(QColor(232, 235, 244))
        p.drawText(QRectF(24, 50, avail, 38), Qt.AlignVCenter | Qt.AlignLeft, elided)

    def _paint_spinner(self, p: QPainter) -> None:
        p.save()
        p.translate(34, self.height() / 2)
        n = 8
        for i in range(n):
            p.rotate(360 / n)
            alpha = (i + (self._phase * 2)) % n / n
            c = QColor(self.accent)
            c.setAlphaF(0.25 + 0.75 * alpha)
            p.setBrush(c)
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(QRectF(7, -2, 7, 4), 2, 2)
        p.restore()

    def _paint_check(self, p: QPainter) -> None:
        c = QColor("#7BE38B")
        p.setPen(QPen(c, 3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        y = self.height() / 2
        p.drawPolyline([QPointF(26, y + 1), QPointF(31, y + 6), QPointF(40, y - 6)])

    def _paint_label(self, p: QPainter, text: str, color: QColor) -> None:
        f = QFont("Segoe UI", 11)
        f.setWeight(QFont.Medium)
        p.setFont(f)
        p.setPen(color)
        p.drawText(QRectF(56, 0, self.width() - 70, self.height()),
                   Qt.AlignVCenter | Qt.AlignLeft, text)
