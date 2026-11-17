"""WaveformView — 막대형 파형 (디자인: 작업공간 하단 독).

세 구간을 색으로 구분한다:
  played  (0 ~ playhead)        → color.wave_played
  ready   (playhead ~ generated) → color.wave_ready
  pending (generated ~ end)      → color.wave_pending, 높이 25%
클릭/드래그로 탐색(seekRequested), 마우스 휠은 무시.
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QMouseEvent, QPainter, QPaintEvent
from PySide6.QtWidgets import QSizePolicy, QWidget

from hantts.app.theme import color


class WaveformView(QWidget):
    seekRequested = Signal(float)  # 0..1

    BAR_W = 3.0
    GAP = 2.0

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._peaks = np.zeros(0, dtype=np.float32)
        self._played = 0.0
        self._generated = 0.0
        self.setMinimumHeight(44)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName("파형 탐색")

    def sizeHint(self) -> QSize:
        return QSize(480, 44)

    # ---- 데이터 ----------------------------------------------------------
    def set_audio(self, samples: np.ndarray, expected_seconds: float | None = None, sr: int = 24000) -> None:
        """현재까지 생성된 오디오. expected_seconds 가 있으면 남은 구간을 pending 으로 그린다."""
        a = np.abs(np.asarray(samples, dtype=np.float32).reshape(-1))
        total = max(len(a), int((expected_seconds or 0) * sr))
        bars = max(1, int(self.width() / (self.BAR_W + self.GAP)))
        if total == 0:
            self._peaks = np.zeros(bars, dtype=np.float32)
            self._generated = 0.0
        else:
            padded = np.zeros(total, dtype=np.float32)
            padded[: len(a)] = a
            chunks = np.array_split(padded, bars)
            peaks = np.array([c.max() if len(c) else 0.0 for c in chunks], dtype=np.float32)
            m = float(peaks.max()) or 1.0
            self._peaks = peaks / m
            self._generated = len(a) / total
        self.update()

    def clear(self) -> None:
        self._peaks = np.zeros(0, dtype=np.float32)
        self._played = 0.0
        self._generated = 0.0
        self.update()

    def set_progress(self, played: float) -> None:
        self._played = min(max(played, 0.0), 1.0)
        self.update()

    # ---- 그리기 ----------------------------------------------------------
    def paintEvent(self, _: QPaintEvent) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        n = len(self._peaks)
        if n == 0:
            return
        h = self.height()
        step = self.width() / n
        bw = max(1.0, step - self.GAP)
        c_played, c_ready, c_pend = color("wave_played"), color("wave_ready"), color("wave_pending")
        for i, v in enumerate(self._peaks):
            t = (i + 0.5) / n
            span = float(v) * float(h - 8)
            if t > self._generated:
                bar_h, c = max(3.0, 4.0 + span * 0.25), c_pend
            else:
                bar_h, c = max(3.0, 6.0 + span), (c_played if t <= self._played else c_ready)
            p.setBrush(c)
            p.drawRoundedRect(QRectF(i * step, (h - bar_h) / 2, bw, bar_h), 1.5, 1.5)

    def mousePressEvent(self, e: QMouseEvent) -> None:  # noqa: N802
        self._seek(e)

    def mouseMoveEvent(self, e: QMouseEvent) -> None:  # noqa: N802
        if e.buttons() & Qt.MouseButton.LeftButton:
            self._seek(e)

    def _seek(self, e: QMouseEvent) -> None:
        frac = min(max(e.position().x() / max(1, self.width()), 0.0), self._generated)
        self.seekRequested.emit(frac)
