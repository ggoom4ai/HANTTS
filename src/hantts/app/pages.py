"""발음 사전, 기록, 설정."""

from __future__ import annotations

import contextlib
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from hantts.app.studio import Studio
from hantts.core.audio.player import Player


class DictionaryView(QWidget):
    def __init__(self, studio: Studio, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.studio = studio
        title = QLabel(self.tr("발음 사전"))
        title.setProperty("text_role", "h1")
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            [self.tr("원문"), self.tr("읽기"), self.tr("범위"), self.tr("정규식")]
        )
        self.table.setAccessibleName(self.tr("발음 사전"))
        self.pattern = QLineEdit()
        self.pattern.setAccessibleName(self.tr("원문"))
        self.replacement = QLineEdit()
        self.replacement.setAccessibleName(self.tr("읽기"))
        self.regex = QCheckBox(self.tr("정규식"))
        self.scope = QComboBox()
        self.scope.addItems([self.tr("전역"), self.tr("이 엔진")])
        add = QPushButton(self.tr("추가"))
        add.setProperty("variant", "primary")
        add.setAccessibleName(self.tr("추가"))
        add.clicked.connect(self._add)
        remove = QPushButton(self.tr("삭제"))
        remove.setAccessibleName(self.tr("삭제"))
        remove.clicked.connect(self._remove)
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.addWidget(title)
        root.addWidget(self.table, 1)
        form = QHBoxLayout()
        form.addWidget(self.pattern)
        form.addWidget(self.replacement)
        form.addWidget(self.scope)
        form.addWidget(self.regex)
        form.addWidget(add)
        form.addWidget(remove)
        root.addLayout(form)
        self.reload()

    def reload(self) -> None:
        self.table.setRowCount(0)
        for entry in self.studio.store.list_dict():
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(entry.pattern))
            self.table.setItem(row, 1, QTableWidgetItem(entry.replacement))
            self.table.setItem(row, 2, QTableWidgetItem(entry.scope))
            self.table.setItem(row, 3, QTableWidgetItem("Y" if entry.is_regex else ""))
            self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, entry.id)  # type: ignore[union-attr]

    def _add(self) -> None:
        if not self.pattern.text().strip():
            return
        scope = "engine" if self.scope.currentIndex() == 1 else "global"
        self.studio.store.add_dict(
            self.pattern.text().strip(),
            self.replacement.text(),
            scope=scope,
            engine_id=self.studio.engine_id if scope == "engine" else "",
            is_regex=self.regex.isChecked(),
        )
        self.pattern.clear()
        self.replacement.clear()
        self.reload()

    def _remove(self) -> None:
        row = self.table.currentRow()
        item = self.table.item(row, 0)
        if item is None:
            return
        entry_id = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(entry_id, int):
            self.studio.store.delete_dict(entry_id)
            self.reload()


class HistoryView(QWidget):
    def __init__(self, studio: Studio, player: Player, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.studio = studio
        self.player = player
        title = QLabel(self.tr("기록"))
        title.setProperty("text_role", "h1")
        self.list = QListWidget()
        self.list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.list.setAccessibleName(self.tr("생성 기록"))
        play = QPushButton(self.tr("재생"))
        play.setProperty("variant", "primary")
        play.setAccessibleName(self.tr("재생"))
        play.clicked.connect(self._play)
        delete = QPushButton(self.tr("선택삭제"))
        delete.setAccessibleName(self.tr("선택삭제"))
        delete.clicked.connect(self._delete)
        clear = QPushButton(self.tr("전체 삭제"))
        clear.setAccessibleName(self.tr("전체 삭제"))
        clear.clicked.connect(self._delete_all)
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.addWidget(title)
        root.addWidget(self.list, 1)
        row = QHBoxLayout()
        row.addWidget(play)
        row.addWidget(delete)
        row.addWidget(clear)
        root.addLayout(row)
        self.reload()

    def reload(self) -> None:
        self.list.clear()
        for item in self.studio.store.list_history():
            row = QListWidgetItem(
                f"{item.created_at} · {item.engine_id} · {item.duration:.1f}s · {item.text[:40]}"
            )
            row.setData(Qt.ItemDataRole.UserRole, item.id)
            row.setData(Qt.ItemDataRole.UserRole + 1, item.path)
            self.list.addItem(row)

    def _play(self) -> None:
        current = self.list.currentItem()
        if current is None:
            return
        path = current.data(Qt.ItemDataRole.UserRole + 1)
        if isinstance(path, str) and Path(path).exists():
            self.player.load_file(Path(path))
            self.player.play()

    def _delete(self) -> None:
        ids = [
            entry_id
            for item in self.list.selectedItems()
            if isinstance(entry_id := item.data(Qt.ItemDataRole.UserRole), int)
        ]
        if not ids:
            return
        for entry_id in ids:
            self.studio.store.delete_history(entry_id)
        self.reload()

    def _delete_all(self) -> None:
        if self.list.count() == 0:
            return
        box = QMessageBox(self)
        box.setWindowTitle(self.tr("전체 삭제"))
        box.setText(self.tr("생성 기록을 모두 삭제할까요?"))
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        box.setDefaultButton(QMessageBox.StandardButton.No)
        yes = box.button(QMessageBox.StandardButton.Yes)
        no = box.button(QMessageBox.StandardButton.No)
        if yes is not None:
            yes.setText(self.tr("전체 삭제"))
        if no is not None:
            no.setText(self.tr("취소"))
        if box.exec() != QMessageBox.StandardButton.Yes:
            return
        self.studio.store.clear_history()
        self.reload()


class SettingsView(QWidget):
    def __init__(self, studio: Studio, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.studio = studio
        title = QLabel(self.tr("설정"))
        title.setProperty("text_role", "h1")
        cfg = studio.config
        self.language = QComboBox()
        self.language.addItem("한국어", "ko")
        self.language.addItem("English", "en")
        self.language.setCurrentIndex(1 if cfg.language == "en" else 0)
        self.threads = QLineEdit(str(cfg.threads))
        self.threads.setAccessibleName(self.tr("스레드 수"))
        self.workers = QLineEdit(str(cfg.max_workers))
        self.idle = QLineEdit(str(cfg.idle_minutes))
        self.proxy = QLineEdit(cfg.proxy)
        self.proxy.setAccessibleName(self.tr("프록시"))
        self.mirror = QLineEdit(cfg.hf_mirror)
        self.mirror.setAccessibleName(self.tr("Hugging Face 미러"))
        self.lufs = QLineEdit(str(cfg.lufs))
        self.output = QLineEdit(cfg.output_dir or str(studio.paths.output))
        self.output.setProperty("mono", True)
        self.output.setAccessibleName(self.tr("출력 폴더"))
        self.engines = QLineEdit(str(studio.paths.storage))
        self.engines.setProperty("mono", True)
        self.engines.setAccessibleName(self.tr("엔진 폴더"))
        self.commercial = QCheckBox(self.tr("상업적 용도로 사용"))
        self.commercial.setChecked(cfg.commercial_use)
        self.updates = QCheckBox(self.tr("시작 시 업데이트 확인"))
        self.updates.setChecked(cfg.check_updates)
        self.acronyms = QCheckBox(self.tr("영문 약어 읽기"))
        self.acronyms.setChecked(cfg.expand_acronyms)
        save = QPushButton(self.tr("저장"))
        save.setProperty("variant", "primary")
        save.setAccessibleName(self.tr("저장"))
        save.clicked.connect(self._save)
        studio.paths_changed.connect(self._sync_engines)
        browse = QPushButton(self.tr("폴더"))
        browse.setAccessibleName(self.tr("출력 폴더 변경"))
        browse.clicked.connect(self._browse)
        engines_browse = QPushButton(self.tr("폴더"))
        engines_browse.setAccessibleName(self.tr("엔진 폴더 변경"))
        engines_browse.clicked.connect(self._browse_engines)
        form = QFormLayout()
        form.addRow(self.tr("언어"), self.language)
        form.addRow(self.tr("CPU 스레드"), self.threads)
        form.addRow(self.tr("동시 워커"), self.workers)
        form.addRow(self.tr("유휴 종료(분)"), self.idle)
        form.addRow(self.tr("프록시"), self.proxy)
        form.addRow(self.tr("HF 미러"), self.mirror)
        form.addRow(self.tr("LUFS"), self.lufs)
        folder = QHBoxLayout()
        folder.addWidget(self.output, 1)
        folder.addWidget(browse)
        host = QWidget()
        host.setLayout(folder)
        engines_row = QHBoxLayout()
        engines_row.addWidget(self.engines, 1)
        engines_row.addWidget(engines_browse)
        engines_host = QWidget()
        engines_host.setLayout(engines_row)
        form.addRow(self.tr("엔진 폴더"), engines_host)
        form.addRow(self.tr("출력 폴더"), host)
        form.addRow("", self.commercial)
        form.addRow("", self.updates)
        form.addRow("", self.acronyms)
        note = QLabel(
            self.tr(
                "엔진과 모델은 엔진 폴더에 받아지고, 저장하는 즉시 그 폴더의 엔진을 사용합니다. "
                "언어를 바꾸면 다음 실행부터 적용됩니다."
            )
        )
        note.setProperty("text_role", "caption")
        note.setWordWrap(True)
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.addWidget(title)
        root.addLayout(form)
        root.addWidget(note)
        root.addWidget(save)
        root.addStretch(1)

    def _sync_engines(self) -> None:
        self.engines.setText(str(self.studio.paths.storage))

    def _browse(self) -> None:
        path = QFileDialog.getExistingDirectory(self, self.tr("출력 폴더"))
        if path:
            self.output.setText(path)

    def _browse_engines(self) -> None:
        path = QFileDialog.getExistingDirectory(self, self.tr("엔진 폴더"), str(self.studio.paths.storage))
        if path:
            self.engines.setText(path)

    def _save(self) -> None:
        cfg = self.studio.config
        cfg.language = str(self.language.currentData() or "ko")
        cfg.threads = _int(self.threads.text(), cfg.threads)
        cfg.max_workers = _int(self.workers.text(), cfg.max_workers)
        cfg.idle_minutes = _int(self.idle.text(), cfg.idle_minutes)
        cfg.proxy = self.proxy.text().strip()
        cfg.hf_mirror = self.mirror.text().strip()
        with contextlib.suppress(ValueError):
            cfg.lufs = float(self.lufs.text())
        cfg.output_dir = self.output.text().strip()
        self.studio.set_engines_dir(self.engines.text())
        cfg.commercial_use = self.commercial.isChecked()
        cfg.check_updates = self.updates.isChecked()
        cfg.expand_acronyms = self.acronyms.isChecked()
        self.studio.save_config()


def _int(text: str, fallback: int) -> int:
    try:
        return int(text)
    except ValueError:
        return fallback
