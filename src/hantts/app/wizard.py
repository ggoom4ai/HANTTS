"""첫 실행 마법사 (docs/12_UI_DESIGN.md §7.6)."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from hantts.app.studio import Studio

_USES = (
    ("quality", "또렷한 한국어 내레이션", "supertonic"),
    ("now", "설치 없이 바로 읽기", "windows"),
    ("tone", "억양을 살린 낭독", "melo"),
)


class Wizard(QDialog):
    def __init__(self, studio: Studio, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.studio = studio
        self.choice = "windows"
        self.setMinimumWidth(720)
        self.setWindowTitle(self.tr("HanTTS 시작"))
        self.step = QLabel("1 / 3")
        self.step.setProperty("text_role", "mono")
        self.title = QLabel(self.tr("무엇을 만드시나요?"))
        self.title.setProperty("text_role", "h1")
        self.body = QVBoxLayout()
        self._page = 0
        self._checks: list[QCheckBox] = []
        skip = QPushButton(self.tr("건너뛰기"))
        skip.setProperty("variant", "flat")
        skip.setAccessibleName(self.tr("건너뛰기"))
        skip.clicked.connect(self._finish)
        self.back = QPushButton(self.tr("이전"))
        self.back.setProperty("variant", "ghost")
        self.back.clicked.connect(self._prev)
        self.next = QPushButton(self.tr("다음"))
        self.next.setProperty("variant", "primary")
        self.next.setAccessibleName(self.tr("다음"))
        self.next.clicked.connect(self._next)
        row = QHBoxLayout()
        row.addWidget(skip)
        row.addStretch(1)
        row.addWidget(self.back)
        row.addWidget(self.next)
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 28, 28, 28)
        root.addWidget(self.step)
        root.addWidget(self.title)
        root.addLayout(self.body, 1)
        root.addLayout(row)
        self._render()

    def _clear(self) -> None:
        while self.body.count():
            item = self.body.takeAt(0)
            if item is None:
                break
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _render(self) -> None:
        self._clear()
        self.step.setText(f"{self._page + 1} / 3")
        self.back.setEnabled(self._page > 0)
        if self._page == 0:
            self.title.setText(self.tr("무엇을 만드시나요?"))
            group = QButtonGroup(self)
            group.setExclusive(True)
            for key, label, _engine in _USES:
                button = QPushButton(label)
                button.setCheckable(True)
                button.setProperty("variant", "ghost")
                button.setAccessibleName(label)
                button.setChecked(key == "now")
                button.clicked.connect(lambda _c=False, value=key: self._pick(value))
                group.addButton(button)
                self.body.addWidget(button)
            self.next.setText(self.tr("다음"))
        elif self._page == 1:
            engine = next(item[2] for item in _USES if item[0] == self.choice)
            entry = self.studio.catalog.get(engine)
            name = entry.display_name if entry else engine
            self.title.setText(name)
            self.body.addWidget(QLabel(entry.description_ko if entry else ""))
            self._checks = []
            if entry is not None:
                for lic in entry.licenses:
                    box = QCheckBox(lic.name)
                    box.setAccessibleName(lic.name)
                    box.setChecked(lic.default_checked)
                    if lic.requires_consent:
                        box.setText(lic.name + self.tr(" (필수)"))
                    self._checks.append(box)
                    self.body.addWidget(box)
            self.next.setText(self.tr("이 엔진으로 계속"))
        else:
            self.title.setText(self.tr("데이터는 이 PC에만 있습니다."))
            self.body.addWidget(QLabel(str(self.studio.paths.root)))
            self.body.addWidget(
                QLabel(self.tr("원고는 외부로 전송하지 않습니다. 네트워크는 엔진을 받을 때만 씁니다."))
            )
            self.next.setText(self.tr("설치하고 시작하기") if self.choice != "now" else self.tr("시작하기"))

    def _pick(self, key: str) -> None:
        self.choice = key

    def _next(self) -> None:
        if self._page == 1:
            engine = next(item[2] for item in _USES if item[0] == self.choice)
            entry = self.studio.catalog.get(engine)
            if entry is not None:
                for box, lic in zip(self._checks, entry.licenses, strict=False):
                    if lic.requires_consent and not box.isChecked():
                        return
        if self._page < 2:
            self._page += 1
            self._render()
            return
        engine = next(item[2] for item in _USES if item[0] == self.choice)
        self._finish()
        if engine != "windows":
            from hantts.app.install_dialog import InstallDialog

            InstallDialog(self.studio, engine, self.parentWidget()).exec()

    def _prev(self) -> None:
        if self._page:
            self._page -= 1
            self._render()

    def _finish(self) -> None:
        self.studio.config.wizard_done = True
        self.studio.save_config()
        engine = next(item[2] for item in _USES if item[0] == self.choice)
        self.studio.select_engine(engine)
        self.accept()
