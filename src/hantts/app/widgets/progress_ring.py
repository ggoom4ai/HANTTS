"""ProgressRing — 84px 원형 진행률 (디자인: 엔진 설치 진행 대화상자)."""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QFont, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QWidget

from hantts.app.theme import color, tokens


class ProgressRing(QWidget):
    def __init__(self, parent: QWidget | None = None, size: int = 84, thickness: int = 8) -> None:
        super().__init__(parent)
        self._value = 0.0
        self._size = size
        self._thick = thickness
        self.setFixedSize(size, size)

    def sizeHint(self) -> QSize:
        return QSize(self._size, self._size)

    def set_value(self, fraction: float) -> None:
        self._value = min(max(fraction, 0.0), 1.0)
        self.setAccessibleName(f"전체 진행률 {round(self._value * 100)}퍼센트")
        self.update()

    def paintEvent(self, _: QPaintEvent) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        m = self._thick / 2 + 1
        r = QRectF(m, m, self._size - 2 * m, self._size - 2 * m)
        pen = QPen(color("track"), self._thick)
        p.setPen(pen)
        p.drawEllipse(r)
        pen.setColor(color("accent"))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawArc(r, 90 * 16, int(-self._value * 360 * 16))
        f = QFont(tokens()["font"]["family_mono"])
        f.setPixelSize(18)
        p.setFont(f)
        p.setPen(color("text"))
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, f"{round(self._value * 100)}%")
