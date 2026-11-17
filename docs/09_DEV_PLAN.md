# 09. 개발 계획 + Cursor 프롬프트

사용법: 각 태스크의 **Cursor 프롬프트** 블록을 Cursor Agent 모드에 그대로 붙여 넣는다.
`@파일`은 Cursor 컨텍스트 참조다. 한 태스크 = 한 커밋(또는 PR) 원칙. 태스크가 끝나면 수용 기준을 직접 확인한다.

```
Phase 0 엔진 스파이크(검증)  ─┐
Phase 1 골격·계약·가짜 엔진    ├─> Phase 2 엔진 매니저 ─> Phase 3 실제 엔진 어댑터 ─> Phase 4 UI 완성
                               │                                                     ─> Phase 5 생산성 기능
                               └────────────────────────────────────────────────────> Phase 6 패키징·배포
```

---

## Phase 0 — 엔진 스파이크 (가장 먼저, 리스크 제거)

목표: 문서의 🔍 항목을 실제 Windows PC에서 확정한다. 코드 품질보다 **사실 확인**이 목적.

### T0.1 엔진별 설치 레시피 확정
```text
@docs/03_ENGINES.md @docs/04_ENGINE_MANAGER.md
Windows 11 x64에서 다운로드형 엔진(supertonic, melo)을 uv로 격리 설치하는 PowerShell 스크립트를
spikes/install_<engine>.ps1 로 작성해줘.
- uv python install <버전> → uv venv spikes\.venv-<engine> → uv pip install
- torch 엔진은 CPU 인덱스(https://download.pytorch.org/whl/cpu) 사용
- 설치 후 pip freeze 결과를 spikes\freeze-<engine>.txt 로 저장
- MeloTTS는 git 커밋을 고정하고, unidic 문제 발생 시 우회 방법을 주석으로 정리
실행 결과(성공/실패, 오류 메시지)를 docs/spike_report.md 에 표로 기록할 템플릿도 만들어줘.
```
**수용:** 2개 엔진 모두 설치 성공 또는 실패 원인·대안이 `spike_report.md`에 기록됨. (Windows 음성은 설치가 없으므로 T0.5에서 검증)

### T0.2 실제 API 시그니처 수집
```text
spikes/introspect.py 를 작성해줘. 엔진 이름을 인자로 받아 해당 venv에서 실행되며,
주요 합성 함수(supertonic.TTS.synthesize, melo.api.TTS.tts_to_file,
winrt.windows.media.speechsynthesis.SpeechSynthesizer 와 options 의 속성 이름, SAPI.SpVoice 의 Rate/Volume/Speak/GetVoices)의
inspect.signature, docstring, 기본값, 샘플레이트, 사용 가능한 음성/화자 목록을 JSON으로 출력한다.
없는 속성은 오류 대신 "missing"으로 기록. 결과는 spikes/introspect-<engine>.json.
```
**수용:** JSON 3개(supertonic, melo, windows) 생성 → `docs/03_ENGINES.md`의 🔍 항목을 실제 값으로 갱신(PR에 포함).

### T0.3 합성·성능 측정
```text
spikes/bench.py: 한국어 문장 10개(tests/fixtures/ko_sentences.txt, 짧은/긴/숫자 포함)와 영어 문장 10개로
각 엔진의 모델 로드 시간, 문장별 합성 시간, RTF, 최대 RSS 메모리(psutil)를 측정해 CSV로 저장하고
결과 wav를 spikes/out/<engine>/ 에 저장해줘. 스레드 수 1/4/물리코어 3가지로 측정.
```
**수용:** CSV + 사람이 들어본 품질 메모 → 기본 엔진/기본 파라미터 결정 기록.

### T0.4 자산 해시 수집
```text
spikes/hash_assets.py: supertonic·melo 모델 파일의 URL(커밋 고정), 크기, SHA256을 수집해 engines/catalog/catalog.json 의 assets 항목을 채워줘.
```

### T0.5 Windows 음성 검증
```text
@docs/03_ENGINES.md#3
spikes/windows_voices.py 를 작성해줘 (Python 3.11, winrt-runtime, winrt-Windows.Foundation, winrt-Windows.Media.SpeechSynthesis,
winrt-Windows.Storage.Streams, comtypes 설치).
1) OneCore(SpeechSynthesizer.all_voices)와 SAPI 5(SAPI.SpVoice.GetVoices) 음성 목록을 각각 id/이름/언어/성별로 JSON 출력
2) 각 한국어 음성으로 "안녕하세요. 2026년 11월 16일입니다." 를 WAV로 저장하고 샘플레이트·비트·채널을 기록
3) OneCore 옵션(speaking_rate, audio_pitch, audio_volume, appended_silence, punctuation_silence)과
   단어 경계 메타데이터(include_word_boundary_metadata → stream.timed_metadata_tracks)가 동작하는지 확인
4) SSML(<break time="500ms"/>, <prosody rate="slow">, <sub alias>)이 한국어 음성에서 적용되는지 확인
5) Windows 11 내레이터 자연스러운 음성(InJoon, SunHi)이 설치된 PC에서 두 목록 중 어디에라도 나타나는지 확인
6) 관리자 PowerShell 에서 Add-WindowsCapability -Online -Name 'Language.TextToSpeech~~~ko-KR~0.0.1.0' 실행 전후 목록 비교
결과를 spike_report.md 'Windows 음성' 절에 기록.
```
**수용:** 한국어 음성 합성 성공, 옵션별 동작 여부 표, 자연스러운 음성 노출 여부 결론.

### T0.6 MeloTTS ONNX 검증 (gnyong 변환본 우선)
```text
@docs/14_MELO_ONNX.md @tools/melo_onnx/compare_gnyong.py @tools/melo_onnx/export_melo_onnx.py
14 문서 §3 의 변환 환경(build\melo-export: Python 3.10 + torch CPU + MeloTTS 0.1.2 커밋 고정)을 만들고,
gnyong/melotts-kr-onnx 의 최신 전체 커밋 해시를 확인해 compare_gnyong.py 를 fp32, int8 로 실행해줘.
오류가 나면(입력 이름·차원·dtype 불일치 등) 스크립트를 고치고 원인을 spike_report.md 에 기록.
summary.csv 와 a/b/c 청취 메모로 §2.3 판정표에 따라 결정을 기록하고:
- BERT 필요 판정이면 export_melo_onnx.py --bert-only --quantize-bert 실행
- 채택 파일의 SHA256·크기로 catalog.json melo assets 확정, 커밋 해시 자리표시자 교체
또 python-mecab-ko 가 Windows/Python 3.11 에서 설치되고 g2pkk 가 동작하는지 확인해줘.
```
**수용:** 노이즈 0 비교 통과 + 청취 판정(BERT 사용 여부, fp32/int8) 기록 → MeloTTS ONNX 구성 확정. gnyong 변환본 불합격 시 §3 직접 변환으로 전환.

---

## Phase 1 — 골격, 계약, 가짜 엔진

### T1.1 프로젝트 초기화
```text
@README.md @docs/02_ARCHITECTURE.md @.cursor/rules
pyproject.toml(uv, Python 3.11, src 레이아웃)을 완성하고 의존성: PySide6, numpy, soundfile, soxr, pyloudnorm,
sounddevice, httpx, truststore, tomli-w, platformdirs. 개발 의존성: pytest, pytest-qt, ruff, mypy, pyinstaller.
worker_pkg/pyproject.toml 은 src/hantts/core/schema.py, src/hantts/engines/, src/hantts/worker/ 만 포함하는
hantts_worker 휠을 빌드하도록 작성(의존성: numpy, soundfile만).
`uv run python -m hantts` 로 빈 메인 창이 뜨게 해줘.
```

### T1.2 Capability Schema & 프로토콜 확정
```text
@docs/06_IPC_PROTOCOL.md @src/hantts/core/schema.py @src/hantts/worker/protocol.py
골격 코드를 문서와 완전히 일치시키고, to_dict/from_dict 왕복 테스트와 ParamSpec 값 검증(validate_params) 테스트를
tests/test_schema.py 에 작성해줘. pydantic 등 외부 의존성 금지(dataclasses만).
```

### T1.3 워커 메인 루프
```text
@src/hantts/worker/main.py @src/hantts/engines/base.py
워커 루프를 완성해줘: stdout을 프로토콜 전용으로 격리, 모든 예외를 ENGINE_ERROR로 변환, cancel 처리(협조적 플래그),
30초 ping 응답.
```

### T1.4 WorkerSupervisor (호스트)
```text
@docs/02_ARCHITECTURE.md#3 @docs/06_IPC_PROTOCOL.md
src/hantts/core/supervisor.py: QProcess 기반으로 엔진별 워커를 지연 시작/유휴 종료/크래시 재시작(지수 백오프, 최대 3회)하고,
요청 id별 Future(또는 Qt 시그널)로 응답을 돌려주는 클래스를 작성해줘. stderr는 logs/worker-<id>.log 로.
동시 워커 상한(설정값) 초과 시 가장 오래 안 쓴 워커 종료.
```

### T1.4b 테마·디자인 기반
```text
@docs/12_UI_DESIGN.md @src/hantts/app/theme.py @src/hantts/app/resources/tokens.json @src/hantts/app/resources/themes/dark.qss
theme.apply() 를 __main__.py 에 연결하고, 메인 창 골격을 목업 @design/mockups/Main.dc.html 과 같은 3단 구조
(NavRail 84px · WorkArea · Inspector 320–380px)로 만들어줘. NavRail 은 QToolButton[variant="nav"] + QButtonGroup,
화면 전환은 QStackedWidget. resources/icons/ 에 목업의 path 데이터로 SVG 아이콘을 만들고
icon(name, color_token) 헬퍼(QSvgRenderer→QPixmap 캐시, 배율 대응)를 app/icons.py 에 작성.
tests/test_theme.py: render_qss() 에 남은 ${...} 가 없는지, 코드에 hex 하드코딩이 없는지 검사.
```

### T1.5 동적 파라미터 패널
```text
@docs/05_UI_SPEC.md#4 @src/hantts/core/schema.py
src/hantts/app/param_panel.py: CapabilitySchema.params 를 받아 기본/고급 탭에 위젯을 자동 생성하고,
visible_if, 기본값 복원, 툴팁(help_ko), 값 변경 시그널, 엔진별 값 기억을 지원해줘.
Windows 음성 스키마로 pytest-qt 테스트를 작성해줘.
```
(T1.5 추가 지시: 숫자 파라미터는 `widgets/slider_row.py`, bool 은 `widgets/toggle_switch.py` 를 사용하고 인스펙터 모양은 목업 Main 의 오른쪽 패널과 맞춘다.)

**Phase 1 수용:** 메인 창에서 Windows 음성 선택 → 파라미터 패널 표시 → [생성] → 재생·WAV 저장.

---

## Phase 2 — 엔진 매니저

### T2.1 카탈로그 로더/검증
```text
@docs/04_ENGINE_MANAGER.md#3 @engines/catalog/catalog.json
src/hantts/core/catalog.py: catalog.json 을 로드하고 스키마 검증(필수 필드, sha256 형식, 커밋 고정 URL 여부 경고)하는 코드와 테스트.
```

### T2.2 다운로더
```text
@docs/04_ENGINE_MANAGER.md#4
src/hantts/core/download.py: httpx 스트리밍 다운로드, Range 이어받기(.part), SHA256 검증, 미러 순회, 재시도, 취소 토큰,
진행률 콜백(bytes, total, speed, eta), truststore 기반 시스템 인증서, 프록시 설정. 로컬 http.server로 테스트 작성.
```

### T2.3 설치 파이프라인
```text
@docs/04_ENGINE_MANAGER.md#1 #2
src/hantts/core/installer.py: 상태 머신과 9단계 파이프라인을 구현해줘. uv.exe 경로는 앱 폴더 기준,
UV_CACHE_DIR/UV_PYTHON_INSTALL_DIR 은 데이터 폴더로. venv.new 에 설치 후 검증 성공 시 원자적 교체,
실패/취소 시 롤백. 각 단계는 QThread(또는 QRunnable)에서 실행되고 진행률을 시그널로 보낸다.
카탈로그의 엔진 한 종으로 end-to-end 테스트.
```

### T2.4 엔진 관리자 UI + 설치 대화상자
```text
@docs/05_UI_SPEC.md#5 @docs/12_UI_DESIGN.md#7.2 @design/mockups/EngineManager.dc.html @design/mockups/InstallDialog.dc.html
EngineCard 복합 위젯, FlowGridLayout(카드 최소 폭 330px), 디스크 사용 누적 막대, 필터 칩을 목업대로 만들고,
설치 대화상자는 widgets/progress_ring.py 와 4단계 스테퍼, 단계 체크리스트, 접이식 로그로 구성해줘.
엔진 관리자 화면(카드 그리드)과 D1 설치 대화상자(요약→라이선스 동의→진행→완료)를 구현해줘.
작업공간에서 미설치 엔진 선택 시 오른쪽 패널에 설치 카드가 뜨도록 연결.
```

### T2.5 오프라인 팩
```text
@docs/04_ENGINE_MANAGER.md#5
tools/make_pack.py(팩 생성)와 installer.py 의 팩 설치 경로(--no-index --find-links)를 구현해줘.
```

---

## Phase 3 — 실제 엔진 어댑터 (엔진별 1태스크, Windows 음성 → Supertonic → Melo 순)

> Windows 음성을 먼저 하는 이유: 다운로드가 없어 가장 빨리 실제 한국어 음성으로 전체 흐름(UI→워커→오디오→내보내기)을 검증할 수 있다.

### T3.x 어댑터 공통 프롬프트 (엔진 이름만 바꿔 사용)
```text
@docs/03_ENGINES.md @spikes/introspect-<engine>.json @src/hantts/engines/base.py
src/hantts/engines/<engine>.py 에 <Engine>Adapter 를 구현해줘.
- describe_static(): 모델 로드 없이 언어/파라미터 스키마 반환 (03 문서의 '노출할 기능/파라미터' 표 전부 포함)
- load(): 엔진 import 와 모델 로드 (models_dir 에서만 로드, 네트워크 금지)
- describe(): load 후 화자/음성 등 동적 항목 갱신
- synthesize(): float32 mono 로 out_path 에 WAV 저장, SynthResult 반환
- 지원하지 않는 언어는 UnsupportedLanguage, 알 수 없는 파라미터는 InvalidParams
- 스레드 수 적용, seed 적용(가능한 경우)
catalog.json 에 해당 엔진 항목과 잠금 파일(engines/catalog/locks/<engine>-win_amd64.txt, uv pip compile --generate-hashes)을 추가.
tests/engines/test_<engine>.py: @pytest.mark.slow 스모크 테스트(한국어 지원 엔진은 한국어, 아니면 영어 문장).
```
엔진별 추가 지시:
- **supertonic**: 사용자 voice style JSON 가져오기(`import_voice`), 미러 URL 2개 이상
- **melo** (ONNX, @docs/14_MELO_ONNX.md §4): 프런트엔드를 `engines/melo_frontend/`로 이식한다. 합성은 `melotts_kr.onnx` 만 쓰고 PyTorch 경로는 없다.
- **windows** (@src/hantts/engines/windows.py 골격 완성): venv/카탈로그 잠금 파일 없음 — 대신 PyWinRT·comtypes를 호스트 pyproject 에
  `sys_platform == 'win32'` 마커로 추가하고 PyInstaller 번들에 포함. `HanTTS.exe --worker windows` 실행 경로(__main__.py 에서 인자 분기),
  OneCore/SAPI 백엔드 전환, 설치된 음성 전체 열거, SSML 모드, 단어 타임스탬프 → SRT, NEEDS_VOICE 상태와 음성 팩 설치 흐름(04 문서 §8)

**Phase 3 수용:** 3개 엔진 모두 엔진 관리자에서 설치 → 작업공간에서 합성 → 모든 파라미터가 결과에 영향을 주는지 수동 확인 체크리스트 통과.

---

## Phase 4 — 텍스트 프런트엔드 & 오디오 파이프라인 & 작업공간 완성
- T4.1 `normalize_ko.py` TDD: "@docs/07_TEXT_FRONTEND.md 의 표를 tests/text/cases_normalize.tsv(200케이스 이상)로 먼저 만들고, 통과하는 구현을 작성해줘"
- T4.2 `splitter.py` + offset 매핑 + 청크화
- T4.3 사용자 사전(SQLite) + S5 화면
- T4.4 AudioPipeline: 무음 삽입·병합·soxr 리샘플·pyloudnorm LUFS·soundfile 인코딩(WAV/FLAC/OGG/MP3)·SRT
- T4.5 작업공간 (목업 @design/mockups/Main.dc.html, @docs/12_UI_DESIGN.md §7.1): SentenceDelegate(상태 아이콘·화자 태그·사전 밑줄·'엔진 입력 →' 보조 줄), TransportDock + WaveformView, 엔진/언어/프리셋 선택기, 문장 하이라이트, 문장 단위 재생성(청크 캐시), 미지원 언어 배너, 변환 미리보기, 플레이어/파형

## Phase 5 — 생산성
- T5.3 프리셋 · T5.4 히스토리(S6) · T5.5 화자 태그 대화체 · T5.6 `hantts-cli` · T5.7 첫 실행 마법사(S0, 목업 Onboarding) · T5.8 설정(S7) · T5.9 영어 UI 번역

## Phase 6 — 패키징·배포
```text
@docs/08_WINDOWS_INSTALLER.md @installer/hantts.iss
installer/hantts.spec(PyInstaller onedir, 불필요 Qt 모듈 제외, torch/onnxruntime 포함 시 빌드 실패하도록 검사),
installer/build.ps1, tools/fetch_uv.ps1(버전·SHA256 고정)을 작성하고 hantts.iss 를 완성해줘.
GitHub Actions 워크플로 .github/workflows/ci.yml(테스트)과 release.yml(태그 시 빌드·업로드)도 작성.
```
**수용:** 깨끗한 Windows VM(사용자 계정, 관리자 아님)에서 설치 → Supertonic 설치 → 한국어 MP3 생성 → 제거 시 데이터 삭제 선택 동작.

---

## 일정 가이드 (1인 + Cursor 기준, 대략)
| Phase | 기간 |
|---|---|
| 0 | 3–5일 |
| 1 | 1주 |
| 2 | 1–1.5주 |
| 3 | 2주 (MeloTTS Windows 이슈에 따라 변동) |
| 4 | 1.5주 |
| 5 | 1.5주 |
| 6 | 3–5일 |
