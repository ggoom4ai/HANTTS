# HanTTS Studio — CPU 기반 Windows 한국어 TTS 데스크톱 앱

설치형 Windows GUI 프로그램이다. 엔진은 **Windows 음성**(기본), **Supertonic 3**, **MeloTTS(ONNX fp32)** 세 가지다. Windows 음성은 내려받지 않고, 나머지 둘은 앱이 필요할 때 받아 엔진별 가상환경에 설치한다. GPU 없이 CPU만으로 동작한다.

화면은 **작업, 엔진, 사전, 기록, 설정**이다. 설계의 기준은 `docs/`다. 구현이 문서와 달라지면 문서도 함께 고친다.

## 엔진

| 엔진 | 한국어 | 런타임 | 라이선스 | 비고 |
|---|---|---|---|---|
| **Windows 음성** | Windows 한국어 음성 팩(Microsoft Heami 등) | OneCore WinRT / SAPI 5 | Windows 구성요소 | **기본 엔진**. 다운로드 없음. 한국어 음성이 없으면 음성 팩 설치 안내 |
| **Supertonic 3** | 공식 (31개 언어) | ONNX Runtime (워커 venv) | 코드 MIT / 가중치 OpenRAIL-M | 필요할 때 설치. 저장소가 아카이브되어 미러 URL과 SHA256을 고정한다 |
| **MeloTTS** | 공식 (KR, 화자 1명) | ONNX Runtime fp32 (워커 venv) | MIT | torch 없음. BERT 특징은 0. 음소 ID는 체크포인트 `symbols` 순서 |

Kokoro·Piper·Soprano는 한국어를 제대로 지원하지 않아 제외했다. 엔진별 파라미터는 [`docs/03_ENGINES.md`](docs/03_ENGINES.md), Melo 변환은 [`docs/14_MELO_ONNX.md`](docs/14_MELO_ONNX.md).

호스트(PySide6)는 torch, onnxruntime, 엔진 패키지를 import하지 않는다. Supertonic과 Melo는 각자 venv의 워커 프로세스에서 JSON-RPC(stdio)로 합성하고, Windows 음성만 `HanTTS.exe --worker windows`로 앱 자신이 실행한다. 각 엔진은 Capability Schema를 내고, 작업 화면의 파라미터 패널은 그 스키마로 만들어진다.

## 설치

`installer\build.ps1`이 `dist\installer\HanTTS-Setup-0.1.0-x64.exe`를 만든다. 마법사에서 설치 폴더를 고른다. 처음 채워지는 경로는 `%LOCALAPPDATA%\Programs\HanTTS`다. 관리자 설치를 골라도 이 기본 경로는 `Program Files`로 바뀌지 않으므로, 다른 위치를 쓰려면 그 페이지에서 지정한다.

| 위치 | 내용 |
|---|---|
| 설치 폴더 | `HanTTS.exe`, `_internal\`, `uv.exe`, `wheels\hantts_worker-*.whl`, `engines\catalog\` |
| `%LOCALAPPDATA%\HanTTS` | `config.toml`, `hantts.db`, 로그, 기본 출력. 설치 폴더를 바꿔도 여기 유지 |
| 엔진 폴더 | 설정·엔진 화면의 `engines_dir`. 비우면 `%LOCALAPPDATA%\HanTTS` |

설치 마지막에 앱 실행은 켜져 있고, Supertonic 3 바로 설치는 꺼져 있다. 제거 때 앱 파일을 지운 뒤, 엔진·모델·설정·기록을 같이 지울지 묻는다. 기본은 아니오. 자세한 빌드 규칙은 [`docs/08_WINDOWS_INSTALLER.md`](docs/08_WINDOWS_INSTALLER.md).

## 개발

Windows, Python 3.11, [uv](https://docs.astral.sh/uv/)가 필요하다. 설치 프로그램을 만들 때는 Inno Setup 6도 필요하다.

```powershell
uv sync
uv run hantts
```

검사:

```powershell
uv run ruff check .
uv run mypy src
uv run pytest -m "not slow"
```

설치 프로그램:

```powershell
powershell -ExecutionPolicy Bypass -File installer\build.ps1
```

## 문서

| 문서 | 내용 |
|---|---|
| [docs/01_PRD.md](docs/01_PRD.md) | 제품 요구사항, 범위, 비기능 요구사항 |
| [docs/02_ARCHITECTURE.md](docs/02_ARCHITECTURE.md) | 프로세스 모델, 폴더 구조, 데이터 흐름 |
| [docs/03_ENGINES.md](docs/03_ENGINES.md) | 엔진별 기능·파라미터·설치 레시피 |
| [docs/04_ENGINE_MANAGER.md](docs/04_ENGINE_MANAGER.md) | 다운로드, 설치, 오프라인 팩, 카탈로그 |
| [docs/05_UI_SPEC.md](docs/05_UI_SPEC.md) | 화면 구성, 동적 파라미터 패널 |
| [docs/06_IPC_PROTOCOL.md](docs/06_IPC_PROTOCOL.md) | 호스트↔워커 JSON-RPC, Capability Schema |
| [docs/07_TEXT_FRONTEND.md](docs/07_TEXT_FRONTEND.md) | 한국어 정규화, 문장 분할, 발음 사전 |
| [docs/08_WINDOWS_INSTALLER.md](docs/08_WINDOWS_INSTALLER.md) | PyInstaller + Inno Setup, CI |
| [docs/09_DEV_PLAN.md](docs/09_DEV_PLAN.md) | 단계별 개발 계획 |
| [docs/10_TESTING.md](docs/10_TESTING.md) | 테스트, 엔진 스모크, 수용 기준 |
| [docs/11_LICENSES.md](docs/11_LICENSES.md) | 라이선스와 사용자 동의 |
| [docs/12_UI_DESIGN.md](docs/12_UI_DESIGN.md) | 토큰, Qt 매핑, 화면별 구현 |
| [docs/14_MELO_ONNX.md](docs/14_MELO_ONNX.md) | MeloTTS ONNX: fp32, 심볼 ID, BERT 0 |
| [design/](design/README.md) | 화면 목업 |

## 코드

호스트(`src/hantts/app`, `src/hantts/core`에서 `schema.py`·`errors.py`를 뺀 나머지)는 화면과 설치만 담당한다. 워커 휠(`worker_pkg`)에는 `schema.py`, `errors.py`, `engines/`, `worker/`만 들어가고 PySide6는 넣지 않는다. 엔진 패키지 import는 각 어댑터 안에서, 워커 프로세스가 실행될 때만 한다.

```
src/hantts/
  __main__.py                      # GUI 진입점. 카탈로그·설정·마법사 후 MainWindow
  cli.py                           # hantts-cli synth|engines. 같은 워커로 한 문장 합성
  app/
    main_window.py                 # 레일: 작업, 엔진, 사전, 기록, 설정
    studio.py                      # 화면이 부르는 상태. 설치, 합성 큐, 워커, 엔진 폴더
    workspace_view.py              # 작업. 원고, 엔진·음성, 스키마 파라미터, 파형
    engine_manager_view.py         # 엔진 카드, 설치·제거, 엔진 폴더, 오프라인 팩
    install_dialog.py              # 설치 진행
    wizard.py                      # 첫 실행. 기본 선택은 Windows 음성
    pages.py                       # 사전, 기록(선택삭제·전체 삭제), 설정
    param_panel.py                 # Capability Schema → 기본/고급 위젯
    voice_pack.py                  # 한국어 음성 팩이 없을 때 설정 앱·기능 설치
    theme.py  icons.py  i18n.py    # 다크 테마, 아이콘, 영문 문자열
    widgets/                       # waveform, slider_row, toggle_switch, progress_ring, flow_layout
    resources/                     # tokens.json, themes/dark.qss, hantts.ico
  core/                            # 호스트 전용. UI 스레드에서 블로킹 I/O 금지
    paths.py                       # 설치 폴더는 exe 옆. 데이터는 %LOCALAPPDATA%\HanTTS
    config.py                      # config.toml. last_engine 기본 windows, engines_dir
    catalog.py                     # engines/catalog/catalog.json 로드
    installer.py                   # uv venv, 잠금 파일 설치, SHA256, 롤백
    download.py                    # 커밋 고정 URL 다운로드. truststore
    supervisor.py                  # QProcess 워커. 유휴 종료, 재시작
    jobs.py                        # 문장 단위 합성 큐. 실패 문장부터 재개
    store.py                       # SQLite. 기록, 사전, 프리셋. clear_history
    schema.py                      # Capability Schema. 호스트·워커 공용 (워커 휠)
    errors.py                      # 도메인 예외 (워커 휠)
    text/
      frontend.py                  # [화자] 태그 → 사전 → 정규화 → 문장 → 청크
      normalize_ko.py              # 숫자·날짜·시간·단위·약어
      splitter.py  dictionary.py   # 문장 분할, 발음 사전 적용
      load_text.py  detect.py      # txt/md/docx/srt 읽기, 언어 감지
    audio/
      pipeline.py                  # 무음 삽입, 리샘플, LUFS, WAV/MP3/FLAC/OGG, SRT
      player.py                    # sounddevice 재생
  engines/                         # 워커 휠. 호스트는 이 패키지의 런타임을 import하지 않음
    base.py                        # 어댑터 인터페이스, EngineError
    windows.py                     # WinRT/SAPI. --worker windows 에서만 import
    supertonic.py                  # ONNX. 워커 venv의 onnxruntime
    melo.py                        # ONNX 전용. melotts_kr.onnx 가 없으면 실패
    melo_onnx.py                   # 세션, 심볼 ID(config symbols 순서), 합성
    melo_frontend/                 # 한국어 g2p, 어절 wordpiece. BERT는 0
  worker/
    protocol.py                    # NDJSON JSON-RPC. stdout은 프로토콜만
    main.py                        # python -m hantts.worker.main --engine <id>

engines/catalog/
  catalog.json                     # 설치 레시피. 앱은 설치 폴더의 engines/catalog 를 읽음
  locks/*-win_amd64.txt            # uv 잠금. 현재 엔진에 torch 없음

worker_pkg/pyproject.toml          # hantts-worker 휠. numpy, soundfile만 의존
installer/
  hantts.spec                      # PyInstaller onedir. 다른 conda의 Library\bin DLL 교체
  hantts.iss                       # Inno Setup. DisableDirPage=no
  build.ps1                        # 휠 → 번들 → uv.exe → 카탈로그 → ISCC
tools/
  fetch_uv.ps1                     # 고정 버전 uv.exe, SHA256
  make_pack.py                     # .htpack
  melo_onnx/                       # ONNX 재내보내기·검증. 앱 런타임은 이 스크립트를 쓰지 않음
tests/                             # pytest -m "not slow"
```
