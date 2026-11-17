# 03. 엔진 명세

> 표기: ✅ 확인됨(공식 문서 기준) · 🔍 **Phase 0 스파이크에서 실제 API 시그니처로 확인 후 확정** · ⚠️ 리스크
> 원칙: 어댑터 구현 전에 반드시 `inspect.signature()`로 실제 인자명을 확인하고, 이 문서를 갱신한다.

## 0. 지원 엔진 (v1 확정: 3종)

| 엔진 | 한국어 | 설치 방식 | 성격 | UI 처리 |
|---|---|---|---|---|
| **Windows 음성** | Windows 한국어 음성 팩(예: Microsoft Heami) | **다운로드 없음**(Windows 내장). 한국어 음성이 없으면 Windows 음성 팩 설치를 안내 | 기본 엔진. 즉시 사용, 가장 가벼움, SSML 지원 | 기본 (`last_engine` = `windows`) |
| **Supertonic 3** | 공식, 프리셋 음성 10종(M1–M5, F1–F5) | 앱이 내려받음 (~0.5GB) | 내려받아 쓰는 고품질 엔진 | 선택 설치 |
| **MeloTTS** | 공식, 화자 1명(`KR`) | 앱이 내려받음 (ONNX fp32, 약 0.3GB) | 자연스러운 억양. ONNX Runtime, BERT 특징은 0 | 선택 설치 |

> **제외한 엔진:** Kokoro v1.0(공식 언어 8개에 한국어 없음), Piper(공식 한국어 음성 없음, 커뮤니티 음성은 비상업 라이선스), Soprano(영어 전용).
> 세 엔진 모두 한국어를 제대로 지원하지 않아 v1 범위에서 뺐다. 엔진 플러그인 구조는 그대로라 나중에 다시 넣을 수 있다.

> "엔진에서 지원하는 모든 기능"은 각 엔진이 실제로 지원하는 **모든 언어·음성·파라미터**를 노출한다는 뜻이다
> (예: Supertonic 3의 다른 언어, Windows에 설치된 모든 음성. MeloTTS ONNX는 한국어만).

---

## 1. Supertonic 3 (Supertone)

| 항목 | 내용 |
|---|---|
| 패키지 | `pip install supertonic` (Python SDK) ✅ |
| 런타임 | ONNX Runtime (CPU) — torch 불필요, 가장 가벼움 |
| 모델 | HF `Supertone/supertonic-3`: `duration_predictor.onnx`, `text_encoder.onnx`, `vector_estimator.onnx`, `vocoder.onnx` + `voice_styles/*.json` (ONNX 합계 약 380MB) |
| 파라미터 규모 | 약 99M |
| 라이선스 | 샘플 코드 MIT / 가중치 BigScience OpenRAIL-M (사용 제한 조항 있음 → 동의 화면) |
| Python 권장 | 3.11 |

**기본 사용 예 (공식):**
```python
from supertonic import TTS
tts = TTS(auto_download=True)          # 우리 앱은 auto_download=False + 로컬 경로 지정 🔍
style = tts.get_voice_style(voice_name="M1")
wav, duration = tts.synthesize(text, voice_style=style, lang="ko")
tts.save_audio(wav, "out.wav")
```

**노출할 기능/파라미터**
| key | 타입 | 기본 | 설명 | 상태 |
|---|---|---|---|---|
| `lang` | enum(31개) | `ko` | 언어 | ✅ |
| `voice` | enum | `F1` | 프리셋 음성 M1–M5 / F1–F5 | ✅ |
| `voice_style_file` | file(.json) | – | 사용자 음성 스타일 JSON 가져오기 (과거 Voice Builder 산출물) | ✅(형식) 🔍(API) |
| `speed` | float 0.7–1.5 | 1.0 (한국어는 0.95 권장) | 말하기 속도 | 🔍 인자명 |
| `total_steps` | int 1–20 | 엔진 기본값 | 생성 스텝(품질↔속도) | 🔍 인자명·범위 |
| `text_normalization` | bool | true | 엔진 내장 정규화(통화·전화번호·단위) 사용 | 🔍 토글 가능 여부 |
| `chunk_silence_ms` | int | 300 | 호스트 측 청크 사이 무음 | 호스트 기능 |

**⚠️ 리스크: 공급 지속성.** Supertone Inc.는 2026-07-15 해산을 결의했고 호스팅 서비스는 2026-08-31 종료,
GitHub 저장소는 아카이브(추가 개발 없음) 공지. 대응:
- 카탈로그에 **다중 미러 URL** 등록(원본 → 검증된 바이트 동일 미러 → 자체 호스팅 GitHub Release/S3)
- 모든 파일 **SHA256 고정**(원본 커밋 `3cadd1ee6394adea1bd021217a0e650ede09a323` 기준 해시를 Phase 0에서 수집)
- `supertonic` PyPI 패키지 버전 고정 + 휠을 자체 저장소에 백업(오프라인 팩에도 포함)

---

## 2. MeloTTS (MyShell)

| 항목 | 내용 |
|---|---|
| 런타임 | **ONNX Runtime** CPU. 모델은 gnyong `melotts_kr_fp32.onnx`(커밋 `c11013196ea7efe6ee06b418ec679212770533f7`, 170,506,511 B). torch 없음 → **[14_MELO_ONNX.md](14_MELO_ONNX.md)** |
| 패키지 | `onnxruntime`, `g2pkk`, `python-mecab-ko`, `jamo`, `anyascii` + `engines/melo_frontend/` |
| 모델 | `melotts_kr.onnx`, `melotts_kr_config.json`, `symbols.json`, `vocab.txt`(어절 정렬). BERT 가중치는 넣지 않고 `bert`·`ja_bert`는 0 |
| 음소 ID | `melotts_kr_config.json`의 `symbols` 인덱스. `symbols.json`의 `symbol_to_id`는 원본 `symbols.py` 순서라 합성에 쓰지 않는다 |
| 출력 | 44,100 Hz |
| 라이선스 | MIT (MeloTTS, gnyong 변환본) |
| Python | 3.11 |

**노출할 기능/파라미터** (ONNX 입력. 언어는 KR만)
| key | 타입 | 기본 | 설명 |
|---|---|---|---|
| `language` | enum | KR | 현재 ONNX는 KR만 |
| `speaker` | enum | KR | 모델 `spk2id`. 현재는 KR |
| `speed` | float 0.5–2.0 | 1.0 | 속도 |
| `sdp_ratio` | float 0–1 | 0.2 | 확률적 길이 예측 비율(억양 다양성) |
| `noise_scale` | float 0–1.5 | 0.6 | 음색 변동 |
| `noise_scale_w` | float 0–1.5 | 0.8 | 길이 변동 |
| `split_sentences` | bool | false | 엔진 내부 분할 사용(기본은 호스트 분할) |

위 파라미터는 ONNX 입력(`length_scale=1/speed`, `sdp_ratio`, `noise_scale`, `noise_scale_w`, `sid`)으로 넣는다. 현재 변환은 **KR만** 대상이다.

PyTorch 런타임과 int8 기본 모델은 현재 구성에 없다. 추론 절차는 14 문서.

---

## 3. Windows 음성 (Windows 내장 TTS)

Windows에 기본으로 들어 있는 음성 합성 기능을 엔진으로 감싼다. **별도 모델 다운로드가 없고**, 앱 설치 직후 바로 쓸 수 있다.
두 가지 API(백엔드)를 하나의 엔진으로 묶고, 사용자가 고급 설정에서 고를 수 있게 한다.

| 항목 | OneCore 백엔드 (기본) | SAPI 5 백엔드 |
|---|---|---|
| API | WinRT `Windows.Media.SpeechSynthesis.SpeechSynthesizer` ✅ | COM `SAPI.SpVoice` (+ `SpFileStream`) |
| Python 바인딩 | PyWinRT: `winrt-runtime`, `winrt-Windows.Foundation`, `winrt-Windows.Media.SpeechSynthesis`, `winrt-Windows.Storage.Streams` ✅ | `comtypes` (또는 `pywin32`) |
| 음성 출처 | 설정 > 시간 및 언어 > 음성 에서 설치한 음성 (레지스트리 `Speech_OneCore`) | 데스크톱 SAPI 음성 + **사용자가 따로 설치한 서드파티 SAPI 음성**(상용 한국어 음성 등) |
| 한국어 기본 음성 | Microsoft Heami (한국어 음성 팩 설치 시) | Microsoft Heami Desktop 🔍 (환경에 따라 없음) |
| 출력 | WAV 스트림 (보통 16kHz/16bit 계열 🔍 — 런타임에 RIFF 헤더에서 읽음) | `SpAudioFormat`으로 지정 (예: 22kHz 16bit mono) 🔍 |
| SSML | `SynthesizeSsmlToStreamAsync` ✅ | `SVSFIsXML` 플래그로 SAPI XML ✅ |
| 타임스탬프 | `IncludeWordBoundaryMetadata`, `IncludeSentenceBoundaryMetadata` → 단어/문장 시작 시각 ✅ | `Word` 이벤트 🔍 |
| 최소 Windows | 옵션별 상이: 속도·피치·볼륨 1709, 문장 끝/문장부호 무음 1803 ✅ | Windows 10/11 모두 |

**라이선스:** 엔진·음성은 Windows 구성요소로 사용자의 Windows 라이선스를 따른다. 앱은 아무것도 재배포하지 않는다.
⚠️ 생성한 음성 파일을 상업적으로 쓰는 조건은 Windows 라이선스 조항 확인이 필요 → 엔진 카드와 11 문서에 안내 문구.

### 3.1 OneCore 사용 예
```python
import asyncio
from winrt.windows.media.speechsynthesis import SpeechSynthesizer
from winrt.windows.storage.streams import DataReader

async def synth(text: str, voice_id: str | None) -> bytes:
    s = SpeechSynthesizer()
    if voice_id:
        s.voice = next(v for v in SpeechSynthesizer.all_voices if v.id == voice_id)
    s.options.speaking_rate = 1.0      # 0.5–6.0
    s.options.audio_pitch = 1.0        # 0.0–2.0
    s.options.audio_volume = 1.0       # 0.0–1.0
    stream = await s.synthesize_text_to_stream_async(text)   # SSML: synthesize_ssml_to_stream_async
    reader = DataReader(stream.get_input_stream_at(0))
    await reader.load_async(stream.size)
    buf = bytearray(stream.size); reader.read_bytes(buf)
    return bytes(buf)                  # RIFF/WAV 바이트
```
(PyWinRT의 속성·메서드 이름은 snake_case 투영. 정확한 이름은 Phase 0 T0.2에서 확인 🔍)

### 3.2 노출할 기능/파라미터
| key | 타입 | 기본 | 설명 | 백엔드 |
|---|---|---|---|---|
| `backend` | enum `onecore`/`sapi` | onecore | 사용할 Windows 음성 API | 공통 (고급) |
| `voice` | enum | 한국어 첫 음성 | **설치된 음성 전체**를 런타임 열거 (`all_voices` / `GetVoices`), 언어·성별 표시 | 공통 |
| `rate` | float 0.5–3.0 | 1.0 | 말하기 속도 (OneCore `SpeakingRate`는 0.5–6.0 허용 → UI는 3.0까지, 고급에서 확장) | OneCore |
| `pitch` | float 0.0–2.0 | 1.0 | 음높이 (`AudioPitch`) | OneCore |
| `volume` | float 0.0–1.0 | 1.0 | 음량 (`AudioVolume`) | OneCore |
| `appended_silence` | enum default/min | default | 발화 끝 무음 (`AppendedSilence`) | OneCore |
| `punctuation_silence` | enum default/min | default | 문장부호 뒤 무음 (`PunctuationSilence`) | OneCore |
| `sapi_rate` | int -10–10 | 0 | 속도 | SAPI |
| `sapi_volume` | int 0–100 | 100 | 음량 | SAPI |
| `sapi_format` | enum | 22kHz 16bit mono | 출력 형식 | SAPI |
| `ssml_mode` | bool | false | 원고를 SSML/SAPI XML로 해석 (편집기에서 태그 하이라이트) | 공통 |
| `word_timestamps` | 기능 플래그 | – | 단어 경계 → 단어 단위 SRT | 공통 |

백엔드에 따라 보이는 파라미터가 달라지므로 `visible_if: {"backend": "onecore"}` 처럼 스키마에 선언한다.

### 3.3 실행 방식 (다른 엔진과 다른 점)
- **venv를 만들지 않는다.** PyWinRT·comtypes 휠(수 MB)을 앱 본체에 함께 번들하고, 워커는 **앱 실행 파일 자신**으로 띄운다:
  `HanTTS.exe --worker windows` (개발 중에는 `python -m hantts.worker.main --engine windows`).
- 그래도 **별도 프로세스**로 띄운다 — COM/WinRT 스레드 모델(STA)과 음성 엔진 크래시를 UI에서 분리하기 위해서다.
- 프로토콜·스키마·오류 코드는 다른 엔진과 동일.

### 3.4 "엔진이 없을 때": 한국어 음성 팩 설치 흐름
Windows 음성 엔진 자체는 항상 있다. 대신 **한국어 음성이 없을 수 있다**(영어판 Windows 등).
1. 앱 시작/엔진 선택 시 `all_voices`에서 `language`가 `ko-KR`인 음성을 찾는다.
2. 없으면 엔진 상태 = `NEEDS_VOICE`, 카드에 "한국어 음성 설치 필요" 배지와 두 가지 버튼:
   - **[Windows 설정에서 설치]** — `ms-settings:speech` 열기 (관리자 권한 불필요). 사용자가 "음성 추가 → 한국어"를 고른다.
   - **[자동 설치(관리자)]** — UAC 승인 후 PowerShell로 Windows 기능 설치:
     `Add-WindowsCapability -Online -Name "Language.TextToSpeech~~~ko-KR~0.0.1.0"`
     (Windows 선택적 기능 "Language.TextToSpeech~~~<언어>" 사용 ✅. 인터넷/Windows Update 필요, 수 분 소요)
3. 설치 후 [다시 확인] 또는 앱이 30초 간격으로 재검사 → 음성이 보이면 `INSTALLED`.

### 3.5 Windows 11 "자연스러운 음성"(Narrator Natural Voices)
- Windows 11 22H2 이상의 내레이터는 한국어 자연스러운 음성 **InJoon(남), SunHi(여)** 를 제공한다 ✅.
- ⚠️ 이 음성들은 내레이터용으로 설치되며, 일반 앱용 API(OneCore/SAPI)의 음성 목록에 나타나는지 **Phase 0에서 확인**한다 🔍.
  - 목록에 나타나면: 그대로 `voice` 선택지에 포함("자연스러운 음성" 표시).
  - 나타나지 않으면: v1에서는 지원하지 않고, 엔진 카드에 "내레이터 전용 음성은 사용할 수 없음"을 안내.
    (서드파티 브리지 도구를 쓰면 SAPI에 노출할 수 있으나, 앱이 설치하거나 권하지 않는다 — 사용자가 직접 설치한 경우 SAPI 백엔드에서 자동으로 보임.)

### 3.6 리스크
- ⚠️ Windows 기본 한국어 음성(Heami)은 신경망 음성보다 기계적이다 → 엔진 카드에 "빠르고 가볍지만 음질은 기본 수준" 명시, 품질이 필요하면 Supertonic 3 추천.
- ⚠️ 기업 PC는 그룹 정책으로 선택적 기능 설치가 막혀 있을 수 있다 → 자동 설치 실패 시 IT 관리자 안내 문구 + 설정 열기 대안.
- PyWinRT는 비동기 API → 워커에서 `asyncio.run()`으로 감싸고 요청마다 새 루프 대신 워커 수명 동안 하나의 루프 유지.

---

## 4. 어댑터 구현 규칙 (모든 엔진 공통)

1. `engines/<id>.py`에 `class XxxAdapter(EngineAdapter)` 하나.
2. `describe()`는 **런타임 조회**로 채운다 (화자 목록, 샘플레이트 등 하드코딩 금지).
3. `synthesize(req)`는 float32 mono numpy → `req.out_path`에 WAV 저장 → `SynthResult` 반환.
4. 알 수 없는 파라미터는 무시하지 말고 `InvalidParams` 오류.
5. 요청 언어/음성이 없으면 `UnsupportedLanguage` / `VoiceNotFound` 오류 (Windows 엔진에서 한국어 음성이 없을 때 등 — 호스트가 음성 팩 설치를 안내).
6. `torch.set_num_threads(req.threads)` / onnxruntime `intra_op_num_threads` 적용 (설정의 CPU 스레드 수). Windows 엔진은 해당 없음.
8. Windows 엔진 어댑터만 예외적으로 앱 본체 번들에 포함되어 `HanTTS.exe --worker windows`로 실행된다 (§3.3).
7. 모든 엔진 import는 `load()` 안에서 수행 → `describe_static()`은 모델 로드 없이 즉시 응답 가능해야 함.
