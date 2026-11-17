"""Capability Schema → 파라미터 위젯 (docs/05_UI_SPEC.md §4)."""

from __future__ import annotations

import re
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from hantts.app.widgets.slider_row import SliderRow
from hantts.app.widgets.toggle_switch import ToggleSwitch
from hantts.core.schema import CapabilitySchema, ParamSpec


class ParamPanel(QWidget):
    """기본/고급 탭, visible_if, 엔진별 값 기억, 값 변경 시그널."""

    changed = Signal(dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._schema: CapabilitySchema | None = None
        self._engine = ""
        self._memory: dict[str, dict[str, Any]] = {}
        self._group = "basic"
        self._editors: dict[str, _Editor] = {}
        self._tabs = _segments(
            self, (("basic", self.tr("기본")), ("advanced", self.tr("고급"))), self._on_group
        )
        self._form = QVBoxLayout()
        self._form.setContentsMargins(0, 0, 0, 0)
        self._form.setSpacing(14)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)
        root.addWidget(self._tabs)
        root.addLayout(self._form)
        root.addStretch(1)

    def set_schema(self, schema: CapabilitySchema, engine_id: str, *, reset: bool = False) -> None:
        if self._schema is not None and self._engine:
            self._memory[self._engine] = self.values()
        if reset:
            self._memory.pop(engine_id, None)
            self._group = "basic"
            for button in self._tabs.findChildren(QPushButton):
                button.setChecked(button.text() == self.tr("기본"))
        self._schema = schema
        self._engine = engine_id
        self._rebuild()

    def values(self) -> dict[str, Any]:
        return {key: editor.value() for key, editor in self._editors.items()}

    def set_values(self, values: dict[str, Any]) -> None:
        for key, value in values.items():
            editor = self._editors.get(key)
            if editor is not None:
                editor.set_value(value)
        self._apply_visibility()

    def reset(self) -> None:
        if self._schema is None:
            return
        self.set_values({p.key: p.default for p in self._schema.params})
        self.changed.emit(self.values())

    def _on_group(self, group: str) -> None:
        self._group = group
        self._apply_visibility()

    def _rebuild(self) -> None:
        while self._form.count():
            item = self._form.takeAt(0)
            if item is None:
                break
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._editors.clear()
        if self._schema is None:
            return
        remembered = self._memory.get(self._engine, {})
        for spec in sorted(self._schema.params, key=lambda p: (p.group, p.order, p.key)):
            value = remembered.get(spec.key, spec.default)
            editor = _Editor(spec, value, self)
            editor.on_change(self._on_edit)
            self._editors[spec.key] = editor
            self._form.addWidget(editor)
        self._apply_visibility()

    def _on_edit(self) -> None:
        self._apply_visibility()
        self.changed.emit(self.values())

    def _apply_visibility(self) -> None:
        current = self.values()
        for _key, editor in self._editors.items():
            spec = editor.spec
            visible = spec.group == self._group and _visible(spec, current)
            editor.setVisible(visible)


def _visible(spec: ParamSpec, current: dict[str, Any]) -> bool:
    return all(current.get(k) == v for k, v in spec.visible_if.items())


class _Editor(QWidget):
    def __init__(self, spec: ParamSpec, value: Any, parent: QWidget) -> None:
        super().__init__(parent)
        self.spec = spec
        self._cb: Any = None
        self._regex: re.Pattern[str] | None = None
        self._reset = QPushButton("↺")
        self._reset.setProperty("variant", "flat")
        self._reset.setProperty("size", "sm")
        self._reset.setAccessibleName(f"{spec.label_ko} 기본값")
        self._reset.setFixedWidth(36)
        self._reset.clicked.connect(lambda: self.set_value(spec.default))
        self._body = self._build(value)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._body, 1)
        if spec.type not in ("float", "int") or spec.min is None or spec.max is None:
            lay.addWidget(self._reset, 0)
        else:
            self._reset.hide()

    def on_change(self, cb: Any) -> None:
        self._cb = cb

    def _emit(self, *_args: object) -> None:
        if self._cb:
            self._cb()

    def value(self) -> Any:
        return self._read()

    def set_value(self, value: Any) -> None:
        self._write(value)
        self._emit()

    def _build(self, value: Any) -> QWidget:
        spec = self.spec
        if spec.type in ("float", "int") and spec.min is not None and spec.max is not None:
            row = SliderRow(
                spec.label_ko,
                minimum=float(spec.min),
                maximum=float(spec.max),
                step=float(spec.step or (1 if spec.type == "int" else 0.01)),
                value=float(value if value is not None else spec.default or spec.min),
                unit=spec.unit,
                help_text=spec.help_ko,
                decimals=0 if spec.type == "int" else 2,
            )
            row.valueChanged.connect(self._emit)
            self._slider = row
            return row
        if spec.type == "bool":
            return self._bool_row(bool(value))
        if spec.type == "enum" and len(spec.choices) <= 6:
            return self._segments(str(value if value is not None else ""))
        if spec.type == "enum":
            box = QComboBox()
            box.setAccessibleName(spec.label_ko)
            for choice in spec.choices:
                box.addItem(choice.label_ko, choice.value)
            idx = box.findData(value)
            if idx >= 0:
                box.setCurrentIndex(idx)
            box.currentIndexChanged.connect(self._emit)
            self._combo = box
            return self._labeled(spec.label_ko, spec.help_ko, box)
        if spec.type == "file":
            return self._file_row(str(value or ""))
        if spec.type == "voice_blend":
            self._blend = QLineEdit(str(value or ""))
            self._blend.setPlaceholderText("voice=0.5, voice2=0.5")
            self._blend.setAccessibleName(spec.label_ko)
            self._blend.textChanged.connect(self._emit)
            return self._labeled(spec.label_ko, spec.help_ko, self._blend)
        field = QLineEdit(str(value or ""))
        field.setAccessibleName(spec.label_ko)
        field.setPlaceholderText(spec.help_ko)
        field.textChanged.connect(self._emit)
        self._line = field
        self._regex = re.compile(spec.regex) if spec.regex else None
        return self._labeled(spec.label_ko, spec.help_ko, field)

    def _bool_row(self, value: bool) -> QWidget:
        host = QWidget()
        row = QHBoxLayout(host)
        row.setContentsMargins(0, 0, 0, 0)
        label = QLabel(self.spec.label_ko)
        label.setToolTip(self.spec.help_ko)
        switch = ToggleSwitch(accessible_name=self.spec.label_ko)
        switch.setChecked(value)
        switch.toggled.connect(self._emit)
        self._switch = switch
        row.addWidget(label, 1)
        row.addWidget(switch)
        return host

    def _segments(self, value: str) -> QWidget:
        host = QWidget()
        host.setProperty("role", "segmented")
        row = QHBoxLayout(host)
        row.setContentsMargins(4, 4, 4, 4)
        row.setSpacing(0)
        group = QButtonGroup(host)
        group.setExclusive(True)
        self._seg: dict[str, QPushButton] = {}
        for choice in self.spec.choices:
            button = QPushButton(choice.label_ko)
            button.setCheckable(True)
            button.setProperty("variant", "segment")
            button.setAccessibleName(choice.label_ko)
            button.setChecked(choice.value == value)
            group.addButton(button)
            button.clicked.connect(self._emit)
            row.addWidget(button, 1)
            self._seg[choice.value] = button
        return self._labeled(self.spec.label_ko, self.spec.help_ko, host)

    def _file_row(self, value: str) -> QWidget:
        host = QWidget()
        row = QHBoxLayout(host)
        row.setContentsMargins(0, 0, 0, 0)
        field = QLineEdit(value)
        field.setAccessibleName(self.spec.label_ko)
        field.textChanged.connect(self._emit)
        browse = QPushButton(self.tr("찾아보기"))
        browse.setProperty("variant", "ghost")
        browse.setProperty("size", "sm")
        browse.setAccessibleName(f"{self.spec.label_ko} 찾아보기")
        browse.clicked.connect(lambda: self._browse(field))
        self._line = field
        row.addWidget(field, 1)
        row.addWidget(browse)
        return self._labeled(self.spec.label_ko, self.spec.help_ko, host)

    def _browse(self, field: QLineEdit) -> None:
        path, _ = QFileDialog.getOpenFileName(self, self.spec.label_ko, "", self.spec.file_filter)
        if path:
            field.setText(path)

    def _labeled(self, title: str, help_text: str, body: QWidget) -> QWidget:
        host = QWidget()
        col = QVBoxLayout(host)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(6)
        label = QLabel(title)
        label.setProperty("text_role", "body")
        if help_text:
            label.setToolTip(help_text)
        col.addWidget(label)
        col.addWidget(body)
        return host

    def _read(self) -> Any:
        spec = self.spec
        if hasattr(self, "_slider"):
            value = self._slider.value()
            return int(round(value)) if spec.type == "int" else value
        if hasattr(self, "_switch"):
            return self._switch.isChecked()
        if hasattr(self, "_seg"):
            for key, button in self._seg.items():
                if button.isChecked():
                    return key
            return spec.default
        if hasattr(self, "_combo"):
            return self._combo.currentData()
        if hasattr(self, "_line"):
            text = self._line.text()
            if self._regex is not None and text and not self._regex.fullmatch(text):
                return spec.default
            return text
        if hasattr(self, "_blend"):
            return self._blend.text()
        return spec.default

    def _write(self, value: Any) -> None:
        if hasattr(self, "_slider"):
            self._slider.set_value(float(value if value is not None else 0))
        elif hasattr(self, "_switch"):
            self._switch.setChecked(bool(value))
        elif hasattr(self, "_seg"):
            for key, button in self._seg.items():
                button.setChecked(str(key) == str(value))
        elif hasattr(self, "_combo"):
            idx = self._combo.findData(value)
            if idx >= 0:
                self._combo.setCurrentIndex(idx)
        elif hasattr(self, "_line"):
            self._line.setText("" if value is None else str(value))
        elif hasattr(self, "_blend"):
            self._blend.setText("" if value is None else str(value))


def _segments(parent: QWidget, options: tuple[tuple[str, str], ...], on_change: Any) -> QWidget:
    host = QWidget(parent)
    host.setProperty("role", "segmented")
    row = QHBoxLayout(host)
    row.setContentsMargins(4, 4, 4, 4)
    row.setSpacing(0)
    group = QButtonGroup(host)
    group.setExclusive(True)
    buttons: list[QPushButton] = []
    for index, (value, label) in enumerate(options):
        button = QPushButton(label)
        button.setCheckable(True)
        button.setProperty("variant", "segment")
        button.setAccessibleName(label)
        button.setChecked(index == 0)
        group.addButton(button)
        button.clicked.connect(lambda _checked=False, v=value: on_change(v))
        row.addWidget(button, 1)
        buttons.append(button)
    return host
