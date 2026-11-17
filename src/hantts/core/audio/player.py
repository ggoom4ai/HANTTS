"""sounddevice 재생. 콜백 스레드에서 출력하고 UI 는 위치만 폴링한다."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtCore import QObject, QTimer, Signal

from hantts.core.audio.pipeline import read_mono
from hantts.core.errors import AudioError


class Player(QObject):
    position_changed = Signal(float)
    state_changed = Signal(str)
    failed = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._audio = np.zeros(0, dtype=np.float32)
        self._sr = 24000
        self._pos = 0
        self._playing = False
        self._stream: object | None = None
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._emit_pos)

    def load_file(self, path: Path) -> None:
        audio, sr = read_mono(path)
        self.load_array(audio, sr)

    def load_array(self, audio: np.ndarray, sr: int) -> None:
        self.pause()
        self.close()
        self._audio = np.asarray(audio, dtype=np.float32).reshape(-1)
        self._sr = sr
        self._pos = 0
        self.position_changed.emit(0.0)

    @property
    def duration(self) -> float:
        return float(len(self._audio)) / float(self._sr) if self._sr else 0.0

    @property
    def position(self) -> float:
        return float(self._pos) / float(self._sr) if self._sr else 0.0

    @property
    def playing(self) -> bool:
        return self._playing

    def toggle(self) -> None:
        if self._playing:
            self.pause()
        else:
            self.play()

    def play(self) -> None:
        if len(self._audio) == 0:
            return
        if self._pos >= len(self._audio):
            self._pos = 0
        try:
            self._ensure_stream()
        except (OSError, RuntimeError) as e:
            self.failed.emit(f"재생 장치를 열지 못했습니다: {e}")
            return
        self._playing = True
        self._timer.start()
        self.state_changed.emit("playing")

    def pause(self) -> None:
        self._playing = False
        self._timer.stop()
        self.state_changed.emit("paused")

    def stop(self) -> None:
        self.pause()
        self._pos = 0
        self.position_changed.emit(0.0)

    def clear(self) -> None:
        self.stop()
        self.close()
        self._audio = np.zeros(0, dtype=np.float32)
        self._pos = 0

    def seek_fraction(self, fraction: float) -> None:
        if len(self._audio) == 0:
            return
        self._pos = int(min(max(fraction, 0.0), 1.0) * len(self._audio))
        self.position_changed.emit(self.position)

    def close(self) -> None:
        self._playing = False
        self._timer.stop()
        stream = self._stream
        self._stream = None
        if stream is not None:
            try:
                stream.stop()  # type: ignore[attr-defined]
                stream.close()  # type: ignore[attr-defined]
            except (OSError, RuntimeError):
                return

    def _ensure_stream(self) -> None:
        if self._stream is not None:
            return
        import sounddevice as sd

        def callback(outdata: np.ndarray, frames: int, _time: object, _status: object) -> None:
            if not self._playing:
                outdata.fill(0)
                return
            end = self._pos + frames
            chunk = self._audio[self._pos : end]
            self._pos = end
            outdata[: len(chunk), 0] = chunk
            if len(chunk) < frames:
                outdata[len(chunk) :, 0] = 0
                self._playing = False

        stream = sd.OutputStream(
            samplerate=self._sr, channels=1, dtype="float32", callback=callback, blocksize=1024
        )
        try:
            stream.start()
        except (OSError, RuntimeError) as e:
            self._stream = None
            raise AudioError(str(e)) from e
        self._stream = stream

    def _emit_pos(self) -> None:
        self.position_changed.emit(self.position)
        if not self._playing:
            self._timer.stop()
            self.state_changed.emit("paused")
