"""메인 창. 내비게이션 레일과 화면 스택."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QMainWindow,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from hantts.app.engine_manager_view import EngineManagerView
from hantts.app.icons import app_icon, icon
from hantts.app.pages import DictionaryView, HistoryView, SettingsView
from hantts.app.studio import Studio
from hantts.app.theme import dark_title_bar
from hantts.app.workspace_view import WorkspaceView
from hantts.core.audio.player import Player

_NAV = (
    ("wave", "작업"),
    ("engine", "엔진"),
    ("book", "사전"),
    ("clock", "기록"),
    ("sliders", "설정"),
)


class MainWindow(QMainWindow):
    def __init__(self, studio: Studio, player: Player) -> None:
        super().__init__()
        self.studio = studio
        self.player = player
        self.setWindowTitle("HanTTS Studio")
        self.setWindowIcon(app_icon())
        self.resize(1440, 900)
        self.setMinimumSize(1100, 720)
        self.workspace = WorkspaceView(studio, player)
        self.engines = EngineManagerView(studio)
        self.dictionary = DictionaryView(studio)
        self.history = HistoryView(studio, player)
        self.settings = SettingsView(studio)
        self.stack = QStackedWidget()
        for page in (
            self.workspace,
            self.engines,
            self.dictionary,
            self.history,
            self.settings,
        ):
            self.stack.addWidget(page)
        rail = QWidget()
        rail.setProperty("role", "navrail")
        rail.setFixedWidth(84)
        rail_lay = QVBoxLayout(rail)
        rail_lay.setContentsMargins(8, 12, 8, 12)
        rail_lay.setSpacing(6)
        group = QButtonGroup(self)
        group.setExclusive(True)
        for index, (name, label) in enumerate(_NAV):
            button = QToolButton()
            button.setText(self.tr(label))
            button.setIcon(icon(name, "text_muted"))
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            button.setProperty("variant", "nav")
            button.setCheckable(True)
            button.setAccessibleName(self.tr(label))
            button.setChecked(index == 0)
            group.addButton(button, index)
            rail_lay.addWidget(button)
        rail_lay.addStretch(1)
        group.idClicked.connect(self._go)
        root = QWidget()
        root.setObjectName("AppRoot")
        row = QHBoxLayout(root)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        row.addWidget(rail)
        row.addWidget(self.stack, 1)
        self.setCentralWidget(root)
        self._keys()
        studio.rendered.connect(lambda _r: self.history.reload())
        studio.notice.connect(self.statusBar().showMessage)

    def showEvent(self, event: object) -> None:  # noqa: N802
        super().showEvent(event)  # type: ignore[arg-type]
        dark_title_bar(self)

    def _go(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        if index == 1:
            self.engines.reload()
        elif index == 2:
            self.dictionary.reload()
        elif index == 3:
            self.history.reload()

    def _keys(self) -> None:
        QShortcut(QKeySequence("F5"), self, self.workspace.preview)
        QShortcut(QKeySequence("Ctrl+Return"), self, self.workspace.generate)
        QShortcut(QKeySequence("Esc"), self, self.workspace.stop)
        QShortcut(QKeySequence("Ctrl+S"), self, self.workspace.export_as)
        QShortcut(QKeySequence("Ctrl+O"), self, self.workspace.open_file)
        QShortcut(QKeySequence("Ctrl+,"), self, lambda: self._go(4))
        QShortcut(QKeySequence("Space"), self, self._space)

    def _space(self) -> None:
        focus = self.focusWidget()
        if focus is self.workspace.editor:
            return
        self.workspace.toggle_play()

    def closeEvent(self, event: object) -> None:  # noqa: N802
        self.player.close()
        self.studio.supervisor.shutdown_all()
        self.studio.save_config()
        super().closeEvent(event)  # type: ignore[arg-type]
