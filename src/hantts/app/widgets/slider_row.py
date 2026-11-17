"""SliderRow — 라벨 + 도움말 + 값 칩 + 슬라이더 한 줄 (디자인: 인스펙터 '속도', '문장 사이 쉼' …).

param_panel.py 가 ParamSpec(type=float|int, min/max 있음) 마다 하나씩 만든다.
float 는 내부적으로 정수 슬라이더(step 단위)로 변환한다.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSlider, QVBoxLayout, QWidget


class SliderRow(QWidget):
    valueChanged = Signal(float)

    def __init__(
        self,
        label: str,
        *,
        minimum: float,
        maximum: float,
        step: float,
        value: float,
        unit: str = "",
        help_text: str = "",
        decimals: int = 2,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._min, self._step, self._unit, self._dec = minimum, step or 1.0, unit, decimals

        title = QLabel(label)
        title.setProperty("text_role", "body")
        hint = QLabel(help_text)
        hint.setProperty("text_role", "faint")
        self._chip = QLabel()
        self._chip.setProperty("text_role", "value")

        head = QHBoxLayout()
        head.setSpacing(6)
        head.addWidget(title)
        head.addWidget(hint)
        head.addStretch(1)
        head.addWidget(self._chip)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, round((maximum - minimum) / self._step))
        self._slider.setAccessibleName(label)
        self._slider.valueChanged.connect(self._on_change)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        lay.addLayout(head)
        lay.addWidget(self._slider)
        self.set_value(value)

    def value(self) -> float:
        return self._min + self._slider.value() * self._step

    def set_value(self, v: float) -> None:
        self._slider.setValue(round((v - self._min) / self._step))
        self._update_chip()

    def _on_change(self, _: int) -> None:
        self._update_chip()
        self.valueChanged.emit(self.value())

    def _update_chip(self) -> None:
        v = self.value()
        txt = f"{v:.{self._dec}f}".rstrip("0").rstrip(".") if self._dec else str(int(v))
        self._chip.setText(f"{txt}{self._unit}")
