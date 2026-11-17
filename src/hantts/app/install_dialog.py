"""설치 대화상자 (docs/12_UI_DESIGN.md §7.3)."""

from __future__ import annotations

import zipfile
from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from hantts.app.studio import Studio, is_progress
from hantts.app.widgets.progress_ring import ProgressRing
from hantts.core.catalog import EngineEntry

_STEPS = ("요약", "라이선스 동의", "설치", "완료")
_PIPELINE = ("사전 점검", "Python", "가상환경", "패키지", "모델", "후처리", "검증")


class InstallDialog(QDialog):
    def __init__(
        self, studio: Studio, engine_id: str, parent: QWidget | None = None, pack: Path | None = None
    ) -> None:
        super().__init__(parent)
        self.studio = studio
        self.engine_id = engine_id
        self.pack = pack
        self.setProperty("role", "modal")
        self.setWindowTitle(self.tr("엔진 설치"))
        self.setMinimumWidth(660)
        self.entry: EngineEntry | None = studio.catalog.get(engine_id)
        if pack is not None:
            self.engine_id = _pack_id(pack)
            self.entry = studio.catalog.get(self.engine_id)
        self.stack = QStackedWidget()
        self.stepper = QHBoxLayout()
        self._bars: list[QProgressBar] = []
        for label in _STEPS:
            bar = QProgressBar()
            bar.setRange(0, 1)
            bar.setValue(0)
            bar.setTextVisible(False)
            bar.setAccessibleName(label)
            self._bars.append(bar)
            self.stepper.addWidget(bar)
        self.stack.addWidget(self._summary())
        self.stack.addWidget(self._license())
        self.stack.addWidget(self._progress_page())
        self.stack.addWidget(self._done_page())
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)
        title = QLabel(self.entry.display_name if self.entry else self.tr("엔진 팩"))
        title.setProperty("text_role", "title")
        root.addWidget(title)
        root.addLayout(self.stepper)
        root.addWidget(self.stack, 1)
        self._goto(0)
        studio.install_progress.connect(self._on_progress)
        studio.install_finished.connect(self._on_finished)

    def _goto(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        for i, bar in enumerate(self._bars):
            bar.setValue(1 if i <= index else 0)
            bar.setProperty("tone", "success" if i < index else "accent")

    def _summary(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        entry = self.entry
        text = self.tr("설치를 시작하면 앱이 Python 환경과 모델 파일을 받습니다.")
        if entry is not None:
            text = (
                f"{entry.description_ko}\n\n"
                f"예상 용량 {entry.approx_disk_mb}MB, 메모리 {entry.approx_ram_mb}MB.\n"
                "설치 중에도 앱은 멈추지 않고, 취소하면 이전 상태로 돌아갑니다."
            )
        body = QLabel(text)
        body.setWordWrap(True)
        nxt = QPushButton(self.tr("다음"))
        nxt.setProperty("variant", "primary")
        nxt.setAccessibleName(self.tr("다음"))
        nxt.clicked.connect(lambda: self._goto(1))
        lay.addWidget(body)
        lay.addStretch(1)
        lay.addWidget(nxt, 0)
        return page

    def _license(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        self._checks: list[tuple[QCheckBox, bool]] = []
        entry = self.entry
        if entry is None or not entry.licenses:
            lay.addWidget(QLabel(self.tr("동의가 필요한 라이선스가 없습니다.")))
        else:
            for lic in entry.licenses:
                box = QCheckBox(f"{lic.name}")
                box.setAccessibleName(lic.name)
                box.setChecked(lic.default_checked)
                lay.addWidget(box)
                lay.addWidget(QLabel(lic.url))
                self._checks.append((box, lic.requires_consent))
        row = QHBoxLayout()
        back = QPushButton(self.tr("이전"))
        back.setProperty("variant", "ghost")
        back.clicked.connect(lambda: self._goto(0))
        go = QPushButton(self.tr("설치"))
        go.setProperty("variant", "primary")
        go.setAccessibleName(self.tr("설치"))
        go.clicked.connect(self._begin)
        row.addWidget(back)
        row.addStretch(1)
        row.addWidget(go)
        lay.addStretch(1)
        lay.addLayout(row)
        return page

    def _progress_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        self.ring = ProgressRing()
        self.step_label = QLabel(self.tr("준비하고 있습니다."))
        self.step_label.setProperty("text_role", "section")
        self.checks = QLabel("\n".join(f"○ {name}" for name in _PIPELINE))
        self.checks.setProperty("text_role", "caption")
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setAccessibleName(self.tr("설치 로그"))
        self.log.setMaximumBlockCount(2000)
        cancel = QPushButton(self.tr("취소"))
        cancel.setProperty("variant", "ghost")
        cancel.setAccessibleName(self.tr("취소"))
        cancel.clicked.connect(self.studio.cancel_install)
        lay.addWidget(self.ring, 0)
        lay.addWidget(self.step_label)
        lay.addWidget(self.checks)
        lay.addWidget(self.log, 1)
        lay.addWidget(cancel, 0)
        return page

    def _done_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        self.done_label = QLabel(self.tr("설치가 끝났습니다."))
        self.done_label.setProperty("text_role", "title")
        use = QPushButton(self.tr("바로 사용"))
        use.setProperty("variant", "primary")
        use.setAccessibleName(self.tr("바로 사용"))
        use.clicked.connect(self._use)
        lay.addWidget(self.done_label)
        lay.addStretch(1)
        lay.addWidget(use)
        return page

    def _begin(self) -> None:
        missing = [box.text() for box, required in self._checks if required and not box.isChecked()]
        if missing:
            self.step_label.setText(self.tr("필수 라이선스에 동의해 주세요."))
            return
        self._goto(2)
        if self.pack is not None:
            self._start_pack()
            return
        self.studio.start_install(self.engine_id)

    def _start_pack(self) -> None:
        assert self.pack is not None
        from hantts.app.studio import _InstallThread

        if self.studio._install is not None and self.studio._install.isRunning():
            self.studio.cancel_install()
        links = _extract_wheels(self.pack, self.studio.paths.tmp / "pack-wheels")
        thread = _InstallThread(self.studio.installer, self.engine_id, links)
        thread.progressed.connect(self.studio.install_progress)
        thread.succeeded.connect(self.studio._install_ok)
        thread.failed.connect(self.studio._install_bad)
        self.studio._install = thread
        thread.start()

    def _on_progress(self, event: object) -> None:
        progress = is_progress(event)
        if progress is None:
            return
        self.ring.set_value(progress.fraction)
        self.step_label.setText(progress.message)
        if progress.log:
            self.log.appendPlainText(progress.log)
        done = int(progress.fraction * len(_PIPELINE))
        lines = []
        for i, name in enumerate(_PIPELINE):
            mark = "✓" if i < done else "●" if i == done else "○"
            lines.append(f"{mark} {name}")
        self.checks.setText("\n".join(lines))

    def _on_finished(self, engine_id: str, message: str) -> None:
        if engine_id != self.engine_id:
            return
        self._goto(3)
        self.done_label.setText(message or self.tr("설치가 끝났습니다."))

    def _use(self) -> None:
        self.studio.select_engine(self.engine_id)
        self.accept()


def _pack_id(path: Path) -> str:
    if not zipfile.is_zipfile(path):
        return ""
    with zipfile.ZipFile(path) as zf:
        try:
            raw = zf.read("pack.json")
        except KeyError:
            return ""
    import json

    data = json.loads(raw.decode("utf-8"))
    return str(data.get("engine_id") or "")


def _extract_wheels(pack: Path, dest: Path) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(pack) as zf:
        for name in zf.namelist():
            if name.startswith("wheels/"):
                zf.extract(name, dest.parent)
    wheels = dest.parent / "wheels"
    return wheels if wheels.exists() else dest
