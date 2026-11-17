"""ToggleSwitch — 36×20 스위치 (디자인: 작업공간 '숫자·날짜 읽기 변환', 'SRT 자막')."""

from __future__ import annotations

from PySide6.QtCore import Property, QEasingCurve, QPropertyAnimation, QRectF, QSize, Qt
from PySide6.QtGui import QPainter, QPaintEvent
from PySide6.QtWidgets import QAbstractButton, QWidget

from hantts.app.theme import color


class ToggleSwitch(QAbstractButton):
    def __init__(self, parent: QWidget | None = None, accessible_name: str = "") -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        if accessible_name:
            self.setAccessibleName(accessible_name)
        self._pos = 0.0
        self._anim = QPropertyAnimation(self, b"knob", self)
        self._anim.setDuration(140)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.toggled.connect(self._animate)

    def sizeHint(self) -> QSize:
        return QSize(36, 20)

    def _animate(self, on: bool) -> None:
        self._anim.stop()
        self._anim.setEndValue(1.0 if on else 0.0)
        self._anim.start()

    def _get(self) -> float:
        return self._pos

    def _set(self, v: float) -> None:
        self._pos = v
        self.update()

    knob = Property(float, _get, _set)

    def setChecked(self, on: bool) -> None:  # noqa: N802 — Qt API
        super().setChecked(on)
        self._pos = 1.0 if on else 0.0

    def paintEvent(self, _: QPaintEvent) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(0, 0, 36, 20)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color("accent") if self.isChecked() else color("border_strong"))
        p.drawRoundedRect(r, 10, 10)
        x = 2 + self._pos * 16
        p.setBrush(color("on_accent") if self.isChecked() else color("text_muted"))
        p.drawEllipse(QRectF(x, 2, 16, 16))
        if self.hasFocus():
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(color("accent_soft"))
            p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), 10, 10)
