"""엔진 관리자 (docs/12_UI_DESIGN.md §7.2)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from hantts.app.studio import Studio
from hantts.app.theme import set_prop, tokens
from hantts.app.voice_pack import install_korean_voice, open_speech_settings
from hantts.app.widgets.flow_layout import FlowGridLayout
from hantts.core.catalog import EngineEntry
from hantts.core.installer import INSTALLED, NOT_INSTALLED
from hantts.core.schema import CapabilitySchema

_INT_MAX = 2_147_483_647


def disk_bar_units(used_bytes: int) -> int:
    """QProgressBar 범위는 부호 있는 32비트다. 사용량을 메가바이트로 낮춘다."""
    return max(1, min(used_bytes // 1_048_576, _INT_MAX))


class EngineManagerView(QWidget):
    def __init__(self, studio: Studio, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.studio = studio
        self._filter = "all"
        title = QLabel(self.tr("엔진"))
        title.setProperty("text_role", "h1")
        sub = QLabel(self.tr("필요한 엔진만 내려받습니다. Windows 음성은 이미 이 PC에 있습니다."))
        sub.setProperty("text_role", "subtitle")
        pack = QPushButton(self.tr("오프라인 팩 가져오기"))
        pack.setProperty("variant", "ghost")
        pack.setAccessibleName(self.tr("오프라인 팩 가져오기"))
        pack.clicked.connect(self._import_pack)
        self.cache_btn = QPushButton(self.tr("캐시 정리"))
        self.cache_btn.setProperty("variant", "ghost")
        self.cache_btn.setAccessibleName(self.tr("캐시 정리"))
        self.cache_btn.clicked.connect(self._clear_cache)
        head = QHBoxLayout()
        titles = QVBoxLayout()
        titles.addWidget(title)
        titles.addWidget(sub)
        head.addLayout(titles, 1)
        head.addWidget(pack)
        head.addWidget(self.cache_btn)

        self.disk = QProgressBar()
        self.disk.setTextVisible(False)
        self.disk_label = QLabel("")
        self.disk_label.setProperty("text_role", "mono")
        change_dir = QPushButton(self.tr("폴더 변경"))
        change_dir.setProperty("variant", "ghost")
        change_dir.setAccessibleName(self.tr("엔진 폴더 변경"))
        change_dir.clicked.connect(self._pick_engines_dir)
        disk_row = QHBoxLayout()
        disk_row.addWidget(self.disk_label, 1)
        disk_row.addWidget(change_dir)
        self.chips = QWidget()
        chip_row = QHBoxLayout(self.chips)
        chip_row.setContentsMargins(0, 0, 0, 0)
        self._chip_group = QButtonGroup(self)
        self._chip_group.setExclusive(True)
        for key, label in (("all", "전체"), ("korean", "한국어 지원"), ("installed", "설치됨")):
            button = QPushButton(label)
            button.setCheckable(True)
            button.setProperty("variant", "chip")
            button.setAccessibleName(label)
            button.setChecked(key == "all")
            button.clicked.connect(lambda _c=False, value=key: self._set_filter(value))
            self._chip_group.addButton(button)
            chip_row.addWidget(button)
        chip_row.addStretch(1)

        self.grid_host = QWidget()
        self.grid = FlowGridLayout(330, 16, self.grid_host)
        self.grid_host.setLayout(self.grid)

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(16)
        root.addLayout(head)
        root.addWidget(self.disk)
        root.addLayout(disk_row)
        root.addWidget(self.chips)
        root.addWidget(self.grid_host, 1)
        studio.status_changed.connect(lambda *_a: self.reload())
        studio.install_finished.connect(lambda *_a: self.reload())
        studio.paths_changed.connect(self.reload)
        self.reload()

    def reload(self) -> None:
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.deleteLater()
        entries = [e for e in self.studio.catalog.engines if self._match(e)]
        for entry in entries:
            self.grid.addWidget(_card(self, entry))
        used = self.studio.installer.cache_bytes()
        self.cache_btn.setText(self.tr("캐시 정리 · %1 MB").replace("%1", f"{used / 1048576:.0f}"))
        span = disk_bar_units(used)
        self.disk.setRange(0, span)
        self.disk.setValue(span)
        self.disk_label.setText(self.tr("엔진 폴더: %1").replace("%1", str(self.studio.paths.storage)))

    def _match(self, entry: EngineEntry) -> bool:
        if self._filter == "korean":
            return entry.korean_support == "official"
        if self._filter == "installed":
            return self.studio.installer.status(entry.id) == INSTALLED
        return True

    def _set_filter(self, key: str) -> None:
        self._filter = key
        self.reload()

    def _pick_engines_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, self.tr("엔진 폴더"), str(self.studio.paths.storage))
        if path:
            self.studio.set_engines_dir(path)

    def _import_pack(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, self.tr("오프라인 팩"), "", "엔진 팩 (*.htpack *.zip)")
        if not path:
            return
        from pathlib import Path

        from hantts.app.install_dialog import InstallDialog

        InstallDialog(self.studio, "", self, pack=Path(path)).exec()

    def _clear_cache(self) -> None:
        self.studio.installer.clear_cache()
        self.reload()

    def install(self, engine_id: str) -> None:
        from hantts.app.install_dialog import InstallDialog

        InstallDialog(self.studio, engine_id, self).exec()

    def test_engine(self, engine_id: str) -> None:
        self.studio.select_engine(engine_id)
        self.studio.generate("안녕하세요.", {}, preview=True)

    def repair(self, engine_id: str) -> None:
        self.studio.installer.mark_broken(engine_id)
        self.install(engine_id)

    def remove(self, engine_id: str) -> None:
        self.studio.uninstall(engine_id)

    def show_voices(self) -> None:
        """Windows에 설치된 음성을 워커가 열거한 뒤 대화상자에 보여 준다."""
        dialog = QDialog(self)
        dialog.setWindowTitle(self.tr("Windows 음성 목록"))
        dialog.setMinimumWidth(460)
        status = QLabel(self.tr("음성을 확인하고 있습니다."))
        status.setWordWrap(True)
        listing = QListWidget()
        listing.setAccessibleName(self.tr("Windows 음성 목록"))
        close = QPushButton(self.tr("닫기"))
        close.setAccessibleName(self.tr("닫기"))
        close.clicked.connect(lambda _checked=False: dialog.close())
        lay = QVBoxLayout(dialog)
        lay.addWidget(status)
        lay.addWidget(listing, 1)
        lay.addWidget(close)
        loads = {"n": 0}

        def fill(schema: object) -> None:
            if not isinstance(schema, CapabilitySchema) or schema.engine_id != "windows":
                return
            loads["n"] += 1
            if loads["n"] == 1 and not schema.voices:
                return
            listing.clear()
            if not schema.voices:
                status.setText(self.tr("설치된 음성이 없습니다."))
                return
            for voice in schema.voices:
                lang = ", ".join(voice.langs)
                listing.addItem(f"{voice.label} · {lang}")
            status.setText(self.tr("음성 %1개").replace("%1", str(len(schema.voices))))

        def on_fail(message: str) -> None:
            status.setText(message)

        self.studio.schema_changed.connect(fill)
        self.studio.failed.connect(on_fail)

        def cleanup(_result: int = 0) -> None:
            self.studio.schema_changed.disconnect(fill)
            self.studio.failed.disconnect(on_fail)

        dialog.finished.connect(cleanup)
        dialog.show()
        self.studio.select_engine("windows")


def _card(view: EngineManagerView, entry: EngineEntry) -> QFrame:
    status = view.studio.installer.status(entry.id)
    card = QFrame()
    card.setProperty("role", "card")
    if entry.id == "supertonic":
        set_prop(card, selected=True)
    lay = QVBoxLayout(card)
    lay.setContentsMargins(18, 18, 18, 18)
    lay.setSpacing(10)
    mark = tokens()["engine_mark"].get(entry.id, {})
    badge = QLabel(str(mark.get("label") or entry.id[:2]))
    badge.setProperty("variant", "badge")
    badge.setProperty("tone", "accent")
    badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
    badge.setFixedSize(40, 28)
    name = QLabel(entry.display_name)
    name.setProperty("text_role", "title")
    kor = QLabel(_korean_label(entry, status))
    kor.setProperty("variant", "badge")
    kor.setProperty("tone", "warning" if status == "NEEDS_VOICE" else "success")
    head = QHBoxLayout()
    head.addWidget(badge)
    head.addWidget(name, 1)
    head.addWidget(kor)
    desc = QLabel(entry.description_ko)
    desc.setWordWrap(True)
    desc.setProperty("text_role", "caption")
    meta = QLabel(f"{_status_label(status)} · 약 {entry.approx_disk_mb}MB · RAM {entry.approx_ram_mb}MB")
    meta.setProperty("text_role", "mono")
    for note in entry.notices_ko:
        line = QLabel(note)
        line.setWordWrap(True)
        line.setProperty("text_role", "faint")
        lay.addWidget(line)
    actions = QHBoxLayout()
    if entry.runtime == "builtin":
        voice_label = view.tr("음성 목록")
        current = view.studio.schema
        if current is not None and current.engine_id == "windows" and current.voices:
            voice_label = view.tr("음성 목록 · %1").replace("%1", str(len(current.voices)))
        voices = QPushButton(voice_label)
        voices.setProperty("variant", "ghost")
        voices.setAccessibleName(view.tr("음성 목록"))
        voices.clicked.connect(lambda _checked=False: view.show_voices())
        settings = QPushButton(view.tr("Windows 음성 설정"))
        settings.setProperty("variant", "ghost")
        settings.setAccessibleName(view.tr("Windows 음성 설정"))
        settings.clicked.connect(lambda _checked=False: open_speech_settings())
        actions.addWidget(voices)
        actions.addWidget(settings)
        if status == "NEEDS_VOICE":
            auto = QPushButton(view.tr("자동 설치"))
            auto.setProperty("variant", "primary")
            auto.setAccessibleName(view.tr("자동 설치"))
            auto.clicked.connect(lambda _checked=False: install_korean_voice())
            actions.addWidget(auto)
    elif status == NOT_INSTALLED:
        go = QPushButton(view.tr("설치"))
        go.setProperty("variant", "primary")
        go.setAccessibleName(view.tr("설치"))
        go.clicked.connect(lambda _c=False, eid=entry.id: view.install(eid))
        actions.addWidget(go)
    else:
        for label, slot in (
            (view.tr("테스트"), lambda eid=entry.id: view.test_engine(eid)),
            (view.tr("복구"), lambda eid=entry.id: view.repair(eid)),
            (view.tr("제거"), lambda eid=entry.id: view.remove(eid)),
        ):
            button = QPushButton(label)
            button.setProperty("variant", "ghost")
            button.setProperty("size", "sm")
            button.setAccessibleName(label)
            # clicked(bool) 이 첫 인자로 들어가면 엔진 id 기본값이 덮인다.
            button.clicked.connect(lambda _checked=False, fn=slot: fn())
            actions.addWidget(button)
    lay.insertWidget(0, _row_widget(head))
    lay.insertWidget(1, desc)
    lay.insertWidget(2, meta)
    lay.addLayout(actions)
    return card


def _row_widget(layout: QHBoxLayout) -> QWidget:
    host = QWidget()
    host.setLayout(layout)
    return host


def _korean_label(entry: EngineEntry, status: str) -> str:
    if entry.runtime == "builtin" and status == "NEEDS_VOICE":
        return "한국어 음성 설치 필요"
    if entry.runtime == "builtin":
        return "Windows 내장 · 다운로드 없음"
    if entry.korean_support == "official":
        return "한국어 공식 지원"
    return entry.korean_support


def _status_label(status: str) -> str:
    return {
        "INSTALLED": "설치됨",
        "NOT_INSTALLED": "미설치",
        "BROKEN": "오류",
        "UPDATE_AVAILABLE": "업데이트 있음",
        "NEEDS_VOICE": "음성 필요",
        "INSTALLING": "설치 중",
    }.get(status, status)
