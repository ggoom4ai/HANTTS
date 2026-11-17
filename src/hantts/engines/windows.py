"""Windows 음성 엔진 어댑터 (docs/03_ENGINES.md §3).

백엔드 두 가지:
  - onecore : WinRT Windows.Media.SpeechSynthesis (PyWinRT)  — 기본
  - sapi    : SAPI 5 COM (comtypes)                           — 서드파티 SAPI 음성까지 사용

실행: 앱 본체에 번들되어 `HanTTS.exe --worker windows` 로 별도 프로세스에서 돈다(venv 없음).
모든 Windows API 호출은 이 모듈 안의 전용 스레드(_ApiThread) 하나에서만 수행한다:
  - WinRT 비동기 API → 그 스레드의 asyncio 루프
  - SAPI(COM)        → 그 스레드에서 CoInitialize
🔍 표시는 Phase 0 T0.5 에서 PyWinRT 투영 이름을 확인해야 하는 곳이다.
"""

from __future__ import annotations

import asyncio
import io
import queue
import sys
import threading
from collections.abc import Callable
from concurrent.futures import Future
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeVar

import numpy as np

from hantts.core.schema import (
    CapabilitySchema,
    Choice,
    Features,
    LanguageSpec,
    Limits,
    ParamSpec,
    SynthRequest,
    VoiceSpec,
)
from hantts.engines.base import EngineAdapter, EngineError, InvalidParams, UnsupportedLanguage, VoiceNotFound

T = TypeVar("T")

ONECORE = "onecore"
SAPI = "sapi"

# SAPI SpeechAudioFormatType 값 (🔍 SAPI 5.4 문서와 대조)
SAPI_FORMATS: dict[str, tuple[int, int]] = {
    "16k": (18, 16000),
    "22k": (22, 22050),
    "44k": (34, 44100),
    "48k": (38, 48000),
}
SVSF_DEFAULT = 0
SVSF_IS_XML = 8
SSFM_CREATE_FOR_WRITE = 3

LANG_LABELS = {
    "ko": "한국어",
    "en": "영어",
    "ja": "일본어",
    "zh": "중국어",
    "es": "스페인어",
    "fr": "프랑스어",
    "de": "독일어",
    "it": "이탈리아어",
    "pt": "포르투갈어",
    "ru": "러시아어",
    "vi": "베트남어",
    "th": "태국어",
}


@dataclass(slots=True, frozen=True)
class WinVoice:
    id: str  # "onecore:<token id>" | "sapi:<token id>"
    backend: str
    name: str
    lang_tag: str  # "ko-KR"
    gender: str  # "female" | "male" | ""

    @property
    def lang(self) -> str:
        return self.lang_tag.split("-")[0].lower() if self.lang_tag else ""


class _ApiThread:
    """Windows API 전용 단일 스레드. submit(fn) 은 그 스레드에서 fn() 을 실행한다."""

    def __init__(self) -> None:
        self._q: queue.Queue[tuple[Callable[[], Any], Future[Any]] | None] = queue.Queue()
        self.loop: asyncio.AbstractEventLoop | None = None
        self._t = threading.Thread(target=self._main, name="win-tts-api", daemon=True)
        self._ready = threading.Event()
        self._t.start()
        self._ready.wait()

    def _main(self) -> None:
        try:  # COM 초기화 (SAPI 용). comtypes 가 없으면 SAPI 백엔드만 비활성.
            import comtypes

            comtypes.CoInitialize()  # type: ignore[no-untyped-call]
        except Exception:  # noqa: BLE001
            pass
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self._ready.set()
        while (item := self._q.get()) is not None:
            fn, fut = item
            if fut.set_running_or_notify_cancel():
                try:
                    fut.set_result(fn())
                except BaseException as e:  # noqa: BLE001
                    fut.set_exception(e)

    def submit(self, fn: Callable[[], T]) -> T:
        fut: Future[T] = Future()
        self._q.put((fn, fut))
        return fut.result()

    def run_async(self, coro_factory: Callable[[], Any]) -> Any:
        """API 스레드의 루프에서 코루틴 실행."""
        return self.submit(lambda: self.loop.run_until_complete(coro_factory()))  # type: ignore[union-attr]

    def close(self) -> None:
        self._q.put(None)


def _lcid_to_tag(lcid_hex: str) -> str:
    """SAPI 'Language' 속성(예: '412' 또는 '412;409') → BCP-47 태그."""
    table = {
        0x412: "ko-KR",
        0x409: "en-US",
        0x809: "en-GB",
        0x411: "ja-JP",
        0x804: "zh-CN",
        0x404: "zh-TW",
        0xC0A: "es-ES",
        0x40C: "fr-FR",
        0x407: "de-DE",
        0x410: "it-IT",
    }
    try:
        return table.get(int(lcid_hex.split(";")[0], 16), "")
    except ValueError:
        return ""


class WindowsAdapter(EngineAdapter):
    engine_id = "windows"

    def __init__(self, ctx: Any) -> None:
        super().__init__(ctx)
        self._api: _ApiThread | None = None
        self._voices: list[WinVoice] = []
        self._onecore_ok = False
        self._sapi_ok = False
        self._last_words: list[dict[str, Any]] | None = None

    def _take_word_timestamps(self) -> list[dict[str, Any]] | None:
        words, self._last_words = self._last_words, None
        return words or None

    # ------------------------------------------------------------------ 스키마
    def _params(self) -> tuple[ParamSpec, ...]:
        on = {"backend": ONECORE}
        sp = {"backend": SAPI}
        silence = (Choice("default", "기본"), Choice("min", "최소"))
        return (
            ParamSpec(
                "backend",
                "enum",
                "음성 API",
                ONECORE,
                "OneCore: Windows 설정의 음성 / SAPI 5: 서드파티 음성 포함",
                choices=(Choice(ONECORE, "OneCore (권장)"), Choice(SAPI, "SAPI 5")),
                group="advanced",
                order=1,
            ),
            ParamSpec(
                "rate",
                "float",
                "속도",
                1.0,
                "1.0 = 기본",
                min=0.5,
                max=3.0,
                step=0.05,
                unit="x",
                order=10,
                visible_if=on,
            ),
            ParamSpec(
                "pitch",
                "float",
                "음높이",
                1.0,
                "1.0 = 기본",
                min=0.0,
                max=2.0,
                step=0.05,
                order=20,
                visible_if=on,
            ),
            ParamSpec("volume", "float", "음량", 1.0, min=0.0, max=1.0, step=0.05, order=30, visible_if=on),
            ParamSpec(
                "appended_silence",
                "enum",
                "발화 끝 쉼",
                "default",
                choices=silence,
                group="advanced",
                order=40,
                visible_if=on,
            ),
            ParamSpec(
                "punctuation_silence",
                "enum",
                "문장부호 뒤 쉼",
                "default",
                choices=silence,
                group="advanced",
                order=41,
                visible_if=on,
            ),
            ParamSpec(
                "sapi_rate",
                "int",
                "속도",
                0,
                "-10(느림) ~ 10(빠름)",
                min=-10,
                max=10,
                step=1,
                order=10,
                visible_if=sp,
            ),
            ParamSpec(
                "sapi_volume", "int", "음량", 100, min=0, max=100, step=1, unit="%", order=30, visible_if=sp
            ),
            ParamSpec(
                "sapi_format",
                "enum",
                "출력 형식",
                "22k",
                choices=tuple(Choice(k, f"{sr / 1000:g}kHz 16bit") for k, (_, sr) in SAPI_FORMATS.items()),
                group="advanced",
                order=50,
                visible_if=sp,
            ),
            ParamSpec(
                "ssml_mode",
                "bool",
                "SSML 모드",
                False,
                "원고를 SSML(OneCore) / SAPI XML 태그로 해석",
                group="advanced",
                order=60,
            ),
        )

    def _build_schema(self, voices: list[WinVoice]) -> CapabilitySchema:
        langs: dict[str, LanguageSpec] = {}
        for v in voices:
            if v.lang and v.lang not in langs:
                langs[v.lang] = LanguageSpec(v.lang, LANG_LABELS.get(v.lang, v.lang_tag), "official")
        if not langs:  # load 전: 한국어를 기본으로 선언 (실제 가능 여부는 load 후 확정)
            langs["ko"] = LanguageSpec("ko", "한국어", "official")
        return CapabilitySchema(
            engine_id="windows",
            display_name="Windows 음성",
            engine_version=f"Windows {sys.getwindowsversion().build}" if sys.platform == "win32" else "n/a",
            sample_rate=0,  # 음성마다 다름 → SynthResult.sample_rate 사용
            languages=tuple(sorted(langs.values(), key=lambda x: (x.code != "ko", x.code))),
            voices=tuple(
                VoiceSpec(
                    v.id,
                    f"{v.name} ({'OneCore' if v.backend == ONECORE else 'SAPI'})",
                    langs=(v.lang,),
                    gender=v.gender,
                    preview_text="안녕하세요. 반갑습니다.",
                )
                for v in voices
            ),
            params=self._params(),
            features=Features(batch=False, streaming=False, word_timestamps=True, builtin_normalization=True),
            limits=Limits(max_chars_per_request=1500, ideal_chunk_seconds=(1.0, 60.0)),
        )

    def describe_static(self) -> CapabilitySchema:
        return self._build_schema([])

    def describe(self) -> CapabilitySchema:
        return self._build_schema(self._voices)

    def korean_voice_available(self) -> bool:
        return any(v.lang == "ko" for v in self._voices)

    # ------------------------------------------------------------------ 로드
    def _load(self) -> None:
        if sys.platform != "win32":
            raise EngineError("Windows 음성 엔진은 Windows에서만 동작합니다.")
        self._api = _ApiThread()
        self._voices = self._api.submit(self._enumerate)

    def _enumerate(self) -> list[WinVoice]:
        out: list[WinVoice] = []
        try:
            from winrt.windows.media.speechsynthesis import SpeechSynthesizer, VoiceGender

            for v in SpeechSynthesizer.all_voices:  # 🔍 IVectorView 반복
                g = "female" if v.gender == VoiceGender.FEMALE else "male"
                out.append(WinVoice(f"onecore:{v.id}", ONECORE, v.display_name, v.language, g))
            self._onecore_ok = True
        except Exception:  # noqa: BLE001 — OneCore 불가(구버전/패키지 없음)
            self._onecore_ok = False
        try:
            import comtypes.client

            sp = comtypes.client.CreateObject("SAPI.SpVoice")
            tokens = sp.GetVoices()
            for i in range(tokens.Count):
                t = tokens.Item(i)
                lang = _lcid_to_tag(str(t.GetAttribute("Language") or ""))
                gender = str(t.GetAttribute("Gender") or "").lower()
                out.append(
                    WinVoice(
                        f"sapi:{t.Id}",
                        SAPI,
                        t.GetDescription(),
                        lang,
                        gender if gender in ("male", "female") else "",
                    )
                )
            self._sapi_ok = True
        except Exception:  # noqa: BLE001
            self._sapi_ok = False
        out.sort(key=lambda v: (v.lang != "ko", v.lang, v.name))
        return out

    # ------------------------------------------------------------------ 합성
    def _synthesize(self, req: SynthRequest, params: dict[str, object]) -> tuple[np.ndarray, int]:
        assert self._api is not None
        voice = next((v for v in self._voices if v.id == req.voice), None)
        if voice is None:
            raise VoiceNotFound(f"voice {req.voice!r} is not installed")
        if voice.lang and req.lang and not _same_lang(voice.lang, req.lang):
            raise UnsupportedLanguage(
                f"{voice.name} 음성은 {req.lang} 를 읽지 못합니다. 같은 언어의 음성을 선택하세요."
            )
        if voice.backend != params["backend"]:
            raise InvalidParams(f"voice {req.voice!r} belongs to backend {voice.backend!r}")
        if voice.backend == ONECORE:
            wav, words = self._api.run_async(lambda: self._onecore(req.text, voice, params))
            self._last_words = words
        else:
            self._last_words = None  # SAPI 단어 이벤트는 v1 범위 밖 (🔍 Word 이벤트 연결 검토)
            wav = self._api.submit(lambda: self._sapi(req.text, voice, params, Path(req.out_path)))
        audio, sr = _decode_wav(wav)
        if len(audio) == 0:
            raise EngineError(f"{voice.name} 음성이 소리를 만들지 못했습니다.")
        return audio, sr

    async def _onecore(
        self, text: str, voice: WinVoice, p: dict[str, object]
    ) -> tuple[bytes, list[dict[str, Any]]]:
        from winrt.windows.media.speechsynthesis import (
            SpeechAppendedSilence,
            SpeechPunctuationSilence,
            SpeechSynthesizer,
        )
        from winrt.windows.storage.streams import DataReader

        s = SpeechSynthesizer()
        s.voice = next(v for v in SpeechSynthesizer.all_voices if f"onecore:{v.id}" == voice.id)
        o = s.options
        o.speaking_rate = float(p["rate"])  # type: ignore[arg-type]
        o.audio_pitch = float(p["pitch"])  # type: ignore[arg-type]
        o.audio_volume = float(p["volume"])  # type: ignore[arg-type]
        o.appended_silence = (
            SpeechAppendedSilence.MIN if p["appended_silence"] == "min" else SpeechAppendedSilence.DEFAULT
        )
        o.punctuation_silence = (
            SpeechPunctuationSilence.MIN
            if p["punctuation_silence"] == "min"
            else SpeechPunctuationSilence.DEFAULT
        )
        o.include_word_boundary_metadata = True

        if p["ssml_mode"]:
            stream = await s.synthesize_ssml_to_stream_async(_ensure_ssml(text, voice.lang_tag))
        else:
            stream = await s.synthesize_text_to_stream_async(text)

        size = int(stream.size)
        reader = DataReader(stream.get_input_stream_at(0))
        await reader.load_async(size)
        buf = bytearray(size)
        reader.read_bytes(buf)  # 🔍 PyWinRT: 쓰기 가능한 버퍼를 채움. 안 되면 bytes(reader.read_buffer(size))
        return bytes(buf), _word_cues(stream)

    def _sapi(self, text: str, voice: WinVoice, p: dict[str, object], out_path: Path) -> bytes:
        import comtypes.client

        sp = comtypes.client.CreateObject("SAPI.SpVoice")
        tokens = sp.GetVoices()
        for i in range(tokens.Count):
            t = tokens.Item(i)
            if f"sapi:{t.Id}" == voice.id:
                sp.Voice = t
                break
        fmt_type, _sr = SAPI_FORMATS[str(p["sapi_format"])]
        fmt = comtypes.client.CreateObject("SAPI.SpAudioFormat")
        fmt.Type = fmt_type
        stream = comtypes.client.CreateObject("SAPI.SpFileStream")
        stream.Format = fmt
        tmp = out_path.with_suffix(".sapi.wav")
        stream.Open(str(tmp), SSFM_CREATE_FOR_WRITE)
        try:
            sp.AudioOutputStream = stream
            sp.Rate = int(p["sapi_rate"])  # type: ignore[call-overload]
            sp.Volume = int(p["sapi_volume"])  # type: ignore[call-overload]
            sp.Speak(text, SVSF_IS_XML if p["ssml_mode"] else SVSF_DEFAULT)
        finally:
            stream.Close()
        data = tmp.read_bytes()
        tmp.unlink(missing_ok=True)
        return data


def _ensure_ssml(text: str, lang_tag: str) -> str:
    t = text.strip()
    if t.startswith("<speak"):
        return t
    return (
        f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
        f'xml:lang="{lang_tag or "ko-KR"}">{t}</speak>'
    )


def _same_lang(voice_lang: str, requested: str) -> bool:
    voice = voice_lang.lower()
    ask = requested.lower()
    return voice == ask or ask.startswith(f"{voice}-") or voice.startswith(f"{ask}-")


def _word_cues(stream: Any) -> list[dict[str, Any]]:
    """단어 경계 메타데이터 → [{"text", "start", "end"}] (초). 실패하면 빈 목록."""
    try:
        from winrt.windows.media.core import SpeechCue
    except ImportError:
        return []
    raw: list[tuple[float, float, str]] = []
    try:
        for track in stream.timed_metadata_tracks:
            if str(getattr(track, "id", "")) != "SpeechWord":
                continue
            for cue in track.cues:
                speech = cue.as_(SpeechCue)
                text = str(speech.text or "").strip()
                if not text:
                    continue
                start = float(speech.start_time.total_seconds())
                duration = float(speech.duration.total_seconds())
                raw.append((start, duration, text))
    except Exception:  # noqa: BLE001 — 메타데이터 형식은 Windows 빌드마다 다르다
        return []
    words: list[dict[str, Any]] = []
    for index, (start, duration, text) in enumerate(raw):
        if duration > 0:
            end = start + duration
        elif index + 1 < len(raw):
            end = raw[index + 1][0]
        else:
            end = start + 0.4
        words.append({"text": text, "start": start, "end": end})
    return words


def _decode_wav(data: bytes) -> tuple[np.ndarray, int]:
    import soundfile as sf

    audio, sr = sf.read(io.BytesIO(data), dtype="float32", always_2d=True)
    return audio.mean(axis=1).astype(np.float32), int(sr)
