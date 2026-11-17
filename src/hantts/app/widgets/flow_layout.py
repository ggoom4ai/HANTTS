"""남는 폭을 카드 최소 너비로 나눠 채우는 그리드."""

from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtWidgets import QLayout, QLayoutItem, QWidget


class FlowGridLayout(QLayout):
    def __init__(self, min_width: int = 330, spacing: int = 16, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._min = min_width
        self._gap = spacing
        self._items: list[QLayoutItem] = []

    def addItem(self, item: QLayoutItem) -> None:  # noqa: N802
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int) -> QLayoutItem | None:  # noqa: N802
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int) -> QLayoutItem | None:  # noqa: N802
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self) -> Qt.Orientation:  # noqa: N802
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        return self._place(QRect(0, 0, width, 0), apply=False)

    def setGeometry(self, rect: QRect) -> None:  # noqa: N802
        super().setGeometry(rect)
        self._place(rect, apply=True)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(self._min * 2 + self._gap, self.heightForWidth(self._min * 2 + self._gap))

    def minimumSize(self) -> QSize:  # noqa: N802
        return QSize(self._min, 120)

    def _place(self, rect: QRect, *, apply: bool) -> int:
        if not self._items:
            return 0
        width = max(rect.width(), self._min)
        cols = max(1, (width + self._gap) // (self._min + self._gap))
        col_w = (width - self._gap * (cols - 1)) // cols
        row_h = max(item.sizeHint().height() for item in self._items)
        x0, y0 = rect.x(), rect.y()
        for i, item in enumerate(self._items):
            col, row = i % cols, i // cols
            box = QRect(x0 + col * (col_w + self._gap), y0 + row * (row_h + self._gap), col_w, row_h)
            if apply:
                item.setGeometry(box)
        rows = (len(self._items) + cols - 1) // cols
        return rows * row_h + max(0, rows - 1) * self._gap
