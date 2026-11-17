"""작업공간 (docs/12_UI_DESIGN.md §7.1)."""

from __future__ import annotations

from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QButtonGroup,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from hantts.app.icons import icon
from hantts.app.param_panel import ParamPanel
from hantts.app.studio import Studio
from hantts.app.voice_pack import install_korean_voice, open_speech_settings
from hantts.app.widgets.toggle_switch import ToggleSwitch
from hantts.app.widgets.waveform import WaveformView
from hantts.core.audio.player import Player
from hantts.core.installer import NOT_INSTALLED
from hantts.core.jobs import Rendered
from hantts.core.schema import CapabilitySchema
from hantts.core.text.load_text import read_text_file


class WorkspaceView(QWidget):
    def __init__(self, studio: Studio, player: Player, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.studio = studio
        self.player = player
        self._schema: CapabilitySchema | None = None
        self._build()
        studio.schema_changed.connect(self._on_schema)
        studio.status_changed.connect(self._on_status)
        studio.progress.connect(self._on_progress)
        studio.rendered.connect(self._on_rendered)
        studio.failed.connect(self._on_failed)
        player.position_changed.connect(self._on_position)
        player.state_changed.connect(self._on_play_state)

    def text(self) -> str:
        return self.editor.toPlainText()

    def params(self) -> dict[str, object]:
        return self.panel.values()

    def preview(self) -> None:
        self.studio.generate(self.text(), self.panel.values(), preview=True)

    def generate(self) -> None:
        self.studio.generate(self.text(), self.panel.values(), preview=False)

    def stop(self) -> None:
        self.studio.stop()
        self.player.stop()

    def toggle_play(self) -> None:
        self.player.toggle()

    def open_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, self.tr("파일 열기"), "", "텍스트 (*.txt *.md *.srt *.docx)"
        )
        if path:
            self.editor.setPlainText(read_text_file(path))
            self._refresh_stats()

    def save_preset(self) -> None:
        from PySide6.QtWidgets import QInputDialog

        name, ok = QInputDialog.getText(self, self.tr("프리셋 저장"), self.tr("이름"))
        if ok and name.strip():
            self.studio.store.save_preset(
                name.strip(), self.studio.engine_id, self.studio.voice, self.studio.lang, self.panel.values()
            )
            self._reload_presets()

    def export_as(self) -> None:
        if self._last is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, self.tr("내보내기"), self._last.path, "오디오 (*.wav *.mp3 *.flac *.ogg)"
        )
        if not path:
            return
        from pathlib import Path

        target = Path(path)
        if target.resolve() != Path(self._last.path).resolve():
            target.write_bytes(Path(self._last.path).read_bytes())
        self.status.setText(self.tr("저장했습니다."))

    # ---- 구성 ----------------------------------------------------------
    def _build(self) -> None:
        self._last: Rendered | None = None
        self.engine_btn = self._selector(self.tr("엔진"))
        self.lang_btn = self._selector(self.tr("언어"))
        self.preset_btn = self._selector(self.tr("프리셋"))
        open_btn = QPushButton(self.tr("파일 열기"))
        open_btn.setProperty("variant", "ghost")
        open_btn.setAccessibleName(self.tr("파일 열기"))
        open_btn.clicked.connect(self.open_file)
        preset_btn = QPushButton(self.tr("프리셋 저장"))
        preset_btn.setProperty("variant", "ghost")
        preset_btn.setAccessibleName(self.tr("프리셋 저장"))
        preset_btn.clicked.connect(self.save_preset)

        top = QHBoxLayout()
        top.addWidget(self.engine_btn)
        top.addWidget(self.lang_btn)
        top.addWidget(self.preset_btn)
        top.addStretch(1)
        top.addWidget(open_btn)
        top.addWidget(preset_btn)

        self.editor = QPlainTextEdit()
        self.editor.setPlaceholderText(
            self.tr("여기에 읽을 글을 붙여 넣으세요. 줄 앞에 [F2] 처럼 쓰면 그 줄부터 음성이 바뀝니다.")
        )
        self.editor.setAccessibleName(self.tr("원고"))
        self.editor.textChanged.connect(self._refresh_stats)
        self.stats = QLabel("0")
        self.stats.setProperty("text_role", "mono")
        self.normalize = ToggleSwitch(accessible_name=self.tr("숫자·날짜 읽기 변환"))
        self.normalize.setChecked(self.studio.config.normalize)
        self.normalize.toggled.connect(self._toggle_normalize)
        self.banner = QFrame()
        self.banner.setProperty("role", "banner")
        self.banner.setProperty("tone", "warning")
        banner_row = QHBoxLayout(self.banner)
        self.banner_label = QLabel(self.tr("이 PC에 한국어 Windows 음성이 없습니다."))
        settings_btn = QPushButton(self.tr("Windows 설정에서 설치"))
        settings_btn.setProperty("variant", "ghost")
        settings_btn.setProperty("size", "sm")
        settings_btn.setAccessibleName(self.tr("Windows 설정에서 설치"))
        settings_btn.clicked.connect(open_speech_settings)
        auto_btn = QPushButton(self.tr("자동 설치"))
        auto_btn.setProperty("variant", "primary")
        auto_btn.setProperty("size", "sm")
        auto_btn.setAccessibleName(self.tr("자동 설치"))
        auto_btn.clicked.connect(self._auto_voice)
        banner_row.addWidget(self.banner_label, 1)
        banner_row.addWidget(settings_btn)
        banner_row.addWidget(auto_btn)
        self.banner.hide()

        self.sentences = QListWidget()
        self.sentences.setAccessibleName(self.tr("문장"))
        preview_link = QPushButton(self.tr("변환 결과 미리보기"))
        preview_link.setProperty("variant", "flat")
        preview_link.setAccessibleName(self.tr("변환 결과 미리보기"))
        preview_link.clicked.connect(self._show_preview)

        header = QHBoxLayout()
        title = QLabel(self.tr("원고"))
        title.setProperty("text_role", "section")
        norm_label = QLabel(self.tr("숫자·날짜 읽기 변환"))
        header.addWidget(title)
        header.addWidget(self.stats)
        header.addStretch(1)
        header.addWidget(norm_label)
        header.addWidget(self.normalize)
        header.addWidget(preview_link)

        card = QFrame()
        card.setProperty("role", "card")
        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(18, 16, 18, 16)
        card_lay.setSpacing(10)
        card_lay.addLayout(header)
        card_lay.addWidget(self.banner)
        card_lay.addWidget(self.editor, 3)
        card_lay.addWidget(self.sentences, 2)

        self.wave = WaveformView()
        self.wave.seekRequested.connect(self.player.seek_fraction)
        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setProperty("text_role", "mono")
        self.progress_label = QLabel("")
        self.progress_label.setProperty("text_role", "caption")
        self.play_btn = QToolButton()
        self.play_btn.setProperty("variant", "play")
        self.play_btn.setIcon(icon("play", "on_accent", 20))
        self.play_btn.setAccessibleName(self.tr("재생"))
        self.play_btn.clicked.connect(self.toggle_play)
        prev_btn = self._icon_btn("prev", self.tr("이전 문장"), self._prev_sentence)
        next_btn = self._icon_btn("next", self.tr("다음 문장"), self._next_sentence)
        self.format_box = self._format_bar()
        self.srt_switch = ToggleSwitch(accessible_name=self.tr("SRT 자막"))
        self.srt_switch.setChecked(True)
        self.srt_switch.toggled.connect(self._toggle_srt)
        export_btn = QPushButton(self.tr("내보내기"))
        export_btn.setProperty("variant", "inverse")
        export_btn.setAccessibleName(self.tr("내보내기"))
        export_btn.clicked.connect(self.export_as)
        gen = QPushButton(self.tr("전체 생성"))
        gen.setProperty("variant", "primary")
        gen.setAccessibleName(self.tr("전체 생성"))
        gen.clicked.connect(self.generate)
        pre = QPushButton(self.tr("미리듣기"))
        pre.setProperty("variant", "ghost")
        pre.setAccessibleName(self.tr("미리듣기"))
        pre.clicked.connect(self.preview)
        stop = QPushButton(self.tr("중지"))
        stop.setProperty("variant", "ghost")
        stop.setAccessibleName(self.tr("중지"))
        stop.clicked.connect(self.stop)

        dock = QFrame()
        dock.setProperty("role", "dock")
        dock_lay = QHBoxLayout(dock)
        dock_lay.setContentsMargins(16, 12, 16, 12)
        transport = QVBoxLayout()
        buttons = QHBoxLayout()
        buttons.addWidget(prev_btn)
        buttons.addWidget(self.play_btn)
        buttons.addWidget(next_btn)
        buttons.addWidget(self.wave, 1)
        meta = QVBoxLayout()
        meta.addWidget(self.time_label)
        meta.addWidget(self.progress_label)
        buttons.addLayout(meta)
        actions = QHBoxLayout()
        actions.addWidget(pre)
        actions.addWidget(gen)
        actions.addWidget(stop)
        actions.addStretch(1)
        actions.addWidget(self.format_box)
        srt_label = QLabel(self.tr("SRT 자막"))
        actions.addWidget(srt_label)
        actions.addWidget(self.srt_switch)
        actions.addWidget(export_btn)
        transport.addLayout(buttons)
        transport.addLayout(actions)
        dock_lay.addLayout(transport)

        work = QVBoxLayout()
        work.setContentsMargins(20, 16, 16, 16)
        work.setSpacing(16)
        work.addLayout(top)
        work.addWidget(card, 1)
        work.addWidget(dock)

        self.panel = ParamPanel()
        self.panel.changed.connect(lambda _v: None)
        self.voices = QWidget()
        self.voice_row = QHBoxLayout(self.voices)
        self.voice_row.setContentsMargins(0, 0, 0, 0)
        self.voice_group = QButtonGroup(self)
        self.voice_group.setExclusive(True)
        self.voice_group.idClicked.connect(self._voice_clicked)
        reset = QPushButton(self.tr("기본값 복원"))
        reset.setProperty("variant", "flat")
        reset.setAccessibleName(self.tr("기본값 복원"))
        reset.clicked.connect(self.panel.reset)
        hint = QLabel(self.tr("엔진이 알려준 파라미터로 자동 구성"))
        hint.setProperty("text_role", "faint")
        hint.setWordWrap(True)
        self.install_card = self._install_card()
        voice_title = QLabel(self.tr("음성"))
        voice_title.setProperty("text_role", "section")
        sample = QPushButton(self.tr("샘플 듣기"))
        sample.setProperty("variant", "ghost")
        sample.setProperty("size", "sm")
        sample.setAccessibleName(self.tr("샘플 듣기"))
        sample.clicked.connect(self._sample)

        inspector = QWidget()
        inspector.setProperty("role", "inspector")
        inspector.setMinimumWidth(320)
        inspector.setMaximumWidth(380)
        side = QVBoxLayout(inspector)
        side.setContentsMargins(16, 16, 16, 16)
        side.setSpacing(12)
        side.addWidget(voice_title)
        side.addWidget(self.voices)
        side.addWidget(sample)
        side.addWidget(self.panel, 1)
        side.addWidget(hint)
        side.addWidget(reset)
        side.addWidget(self.install_card)
        self.inspector = inspector
        self.install_card.hide()

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        row.addLayout(work, 1)
        row.addWidget(inspector)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        work.addWidget(self.status)
        self._reload_engines()
        self._reload_presets()
        self._seen_engine = ""

    def _selector(self, name: str) -> QToolButton:
        button = QToolButton()
        button.setText(name)
        button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        button.setProperty("variant", "selector")
        button.setAccessibleName(name)
        button.setMenu(QMenu(button))
        return button

    def _icon_btn(self, name: str, label: str, slot: object) -> QToolButton:
        button = QToolButton()
        button.setProperty("variant", "icon")
        button.setIcon(icon(name, "text_secondary"))
        button.setAccessibleName(label)
        button.clicked.connect(slot)
        return button

    def _format_bar(self) -> QWidget:
        host = QWidget()
        host.setProperty("role", "segmented")
        row = QHBoxLayout(host)
        row.setContentsMargins(4, 4, 4, 4)
        row.setSpacing(0)
        group = QButtonGroup(host)
        group.setExclusive(True)
        for fmt in ("wav", "flac", "ogg", "mp3"):
            button = QPushButton(fmt.upper())
            button.setCheckable(True)
            button.setProperty("variant", "segment")
            button.setAccessibleName(fmt)
            button.setChecked(fmt == self.studio.format)
            button.clicked.connect(lambda _c=False, value=fmt: self._set_format(value))
            group.addButton(button)
            row.addWidget(button)
        return host

    def _install_card(self) -> QFrame:
        card = QFrame()
        card.setProperty("role", "card")
        lay = QVBoxLayout(card)
        self.install_title = QLabel(self.tr("설치가 필요합니다"))
        self.install_title.setProperty("text_role", "title")
        self.install_body = QLabel("")
        self.install_body.setWordWrap(True)
        self.install_body.setProperty("text_role", "caption")
        go = QPushButton(self.tr("설치"))
        go.setProperty("variant", "primary")
        go.setAccessibleName(self.tr("설치"))
        go.clicked.connect(self._ask_install)
        lay.addWidget(self.install_title)
        lay.addWidget(self.install_body)
        lay.addWidget(go)
        return card

    def _reload_engines(self) -> None:
        menu = self.engine_btn.menu()
        assert menu is not None
        menu.clear()
        for entry in self.studio.catalog.engines:
            action = QAction(entry.display_name, self)
            action.triggered.connect(lambda _c=False, eid=entry.id: self.studio.select_engine(eid))
            menu.addAction(action)

    def _reload_presets(self) -> None:
        menu = self.preset_btn.menu()
        assert menu is not None
        menu.clear()
        for preset in self.studio.store.list_presets():
            action = QAction(preset.name, self)
            action.triggered.connect(lambda _c=False, p=preset: self._apply_preset(p))
            menu.addAction(action)

    def _apply_preset(self, preset: object) -> None:
        from hantts.core.store import Preset

        if not isinstance(preset, Preset):
            return
        self.studio.select_engine(preset.engine_id)
        self.studio.set_lang(preset.lang)
        self.studio.set_voice(preset.voice)
        self.panel.set_values(preset.params)

    def _on_schema(self, schema: object) -> None:
        switching = self.studio.engine_id != self._seen_engine
        if switching:
            self._clear_result()
            self._seen_engine = self.studio.engine_id
        if schema is None:
            self.panel.hide()
            self.voices.hide()
            self.install_card.show()
            entry = self.studio.catalog.get(self.studio.engine_id)
            if entry is not None:
                self.install_title.setText(entry.display_name)
                license_name = entry.licenses[0].name if entry.licenses else ""
                self.install_body.setText(
                    f"{entry.description_ko}\n약 {entry.approx_disk_mb}MB · {license_name}"
                )
            self.engine_btn.setText(self.studio.engine_id)
            return
        if not isinstance(schema, CapabilitySchema):
            return
        self._schema = schema
        self.install_card.hide()
        self.panel.show()
        self.voices.show()
        self.panel.set_schema(schema, self.studio.engine_id, reset=switching)
        self._fill_voices(schema)
        self._fill_langs(schema)
        self.engine_btn.setText(schema.display_name)
        supported = {lang.code for lang in schema.languages}
        self.banner.setVisible(self.studio.lang not in supported and self.studio.lang == "ko")

    def _fill_voices(self, schema: CapabilitySchema) -> None:
        while self.voice_row.count():
            item = self.voice_row.takeAt(0)
            if item is None:
                break
            widget = item.widget()
            if widget is not None:
                self.voice_group.removeButton(widget)  # type: ignore[arg-type]
                widget.deleteLater()
        for index, voice in enumerate(schema.voices[:10]):
            button = QPushButton(voice.label)
            button.setCheckable(True)
            button.setProperty("variant", "voice")
            button.setToolTip(voice.id)
            button.setAccessibleName(voice.label)
            button.setChecked(voice.id == self.studio.voice or (not self.studio.voice and index == 0))
            self.voice_group.addButton(button, index)
            self.voice_row.addWidget(button)
        if schema.voices and not self.studio.voice:
            self.studio.set_voice(schema.voices[0].id)

    def _fill_langs(self, schema: CapabilitySchema) -> None:
        menu = self.lang_btn.menu()
        assert menu is not None
        menu.clear()
        for lang in schema.languages:
            action = QAction(lang.label_ko, self)
            action.triggered.connect(
                lambda _c=False, code=lang.code, label=lang.label_ko: self._pick_lang(code, label)
            )
            menu.addAction(action)
        current = next(
            (lang.label_ko for lang in schema.languages if lang.code == self.studio.lang), self.studio.lang
        )
        self.lang_btn.setText(current)

    def _pick_lang(self, code: str, label: str) -> None:
        self.studio.set_lang(code)
        self.lang_btn.setText(label)
        if self._schema is not None:
            self.banner.setVisible(code not in {lang.code for lang in self._schema.languages})

    def _voice_clicked(self, index: int) -> None:
        if self._schema is None or index >= len(self._schema.voices):
            return
        self.studio.set_voice(self._schema.voices[index].id)

    def _on_status(self, engine_id: str, status: str) -> None:
        if engine_id != self.studio.engine_id:
            return
        self.banner.setVisible(status == "NEEDS_VOICE")
        if status == NOT_INSTALLED:
            self._on_schema(None)

    def _on_progress(self, done: int, total: int) -> None:
        self.progress_label.setText(
            self.tr("문장 %1 / %2").replace("%1", str(done)).replace("%2", str(total))
        )
        self._mark_sentences(done, total)

    def _on_rendered(self, rendered: object) -> None:
        if not isinstance(rendered, Rendered):
            return
        self._last = rendered
        self.status.setText("")
        self.player.load_array(rendered.audio, rendered.sample_rate)
        self.wave.set_audio(rendered.audio, sr=rendered.sample_rate)
        self.time_label.setText(f"00:00 / {_clock(rendered.duration)}")
        self.progress_label.setText(self.tr("완료"))
        self.player.play()

    def _clear_result(self) -> None:
        self.studio.stop()
        self.player.clear()
        self.wave.clear()
        self._last = None
        self.time_label.setText("00:00 / 00:00")
        self.progress_label.setText("")
        self.status.setText("")
        self.play_btn.setIcon(icon("play", "on_accent", 20))
        self._show_preview()

    def _on_failed(self, message: str) -> None:
        self.status.setText(message)

    def _on_position(self, seconds: float) -> None:
        if self._last is None:
            return
        self.time_label.setText(f"{_clock(seconds)} / {_clock(self._last.duration)}")
        if self._last.duration:
            self.wave.set_progress(seconds / self._last.duration)

    def _on_play_state(self, state: str) -> None:
        self.play_btn.setIcon(icon("pause" if state == "playing" else "play", "on_accent", 20))

    def _refresh_stats(self) -> None:
        text = self.editor.toPlainText()
        self.stats.setText(f"{len(text)}자")
        self._show_preview(quiet=True)

    def _show_preview(self, quiet: bool = False) -> None:
        del quiet
        spoken = self.studio.preview_text(self.editor.toPlainText())
        self.sentences.clear()
        for line in spoken.splitlines():
            if line.strip():
                self.sentences.addItem(QListWidgetItem(line))

    def _mark_sentences(self, done: int, total: int) -> None:
        for i in range(self.sentences.count()):
            item = self.sentences.item(i)
            if item is None:
                continue
            if i < done:
                item.setIcon(icon("check", "success", 16))
            elif i == done and done < total:
                item.setIcon(icon("wave", "accent", 16))

    def _toggle_normalize(self, on: bool) -> None:
        self.studio.config.normalize = on
        self._show_preview()

    def _toggle_srt(self, on: bool) -> None:
        self.studio.srt = on

    def _set_format(self, fmt: str) -> None:
        self.studio.format = fmt
        self.studio.config.default_format = fmt

    def _sample(self) -> None:
        self.studio.generate("안녕하세요. 반갑습니다.", self.panel.values(), preview=True)

    def _ask_install(self) -> None:
        self.parent()
        from hantts.app.install_dialog import InstallDialog

        dialog = InstallDialog(self.studio, self.studio.engine_id, self)
        dialog.exec()

    def _auto_voice(self) -> None:
        if install_korean_voice():
            self.status.setText(
                self.tr("Windows가 음성 팩을 설치하는 중입니다. 잠시 후 엔진을 다시 선택하세요.")
            )
        else:
            open_speech_settings()

    def _prev_sentence(self) -> None:
        row = max(0, self.sentences.currentRow() - 1)
        self.sentences.setCurrentRow(row)

    def _next_sentence(self) -> None:
        row = min(self.sentences.count() - 1, self.sentences.currentRow() + 1)
        self.sentences.setCurrentRow(row)


def _clock(seconds: float) -> str:
    total = int(seconds)
    return f"{total // 60:02d}:{total % 60:02d}"
