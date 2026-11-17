# 08. Windows 빌드 · 인스톨러 · 배포

## 1. 산출물
| 파일 | 내용 |
|---|---|
| `HanTTS-Setup-x.y.z-x64.exe` | Inno Setup 인스톨러 (앱 본체 + uv.exe + 워커 휠 + 카탈로그) — 엔진 미포함. 현재 빌드는 `installer\build.ps1`이 `dist\installer\`에 만든다 |
| `HanTTS-x.y.z-portable.zip` | 현재 빌드는 만들지 않는다. 설치 폴더에 `portable.flag`가 있으면 앱은 데이터를 그 옆 `data\`에 둔다 |
| `<engine>-<ver>.htpack` | 오프라인 엔진 팩 (GitHub Release 별도 자산) |

## 2. 빌드 단계 (`installer/build.ps1`)
```powershell
# 0) 버전
$ver = (uv run python -c "import hantts; print(hantts.__version__)")
# 1) 워커 휠
uv build --wheel worker_pkg -o dist\wheels
# 2) 호스트 번들 (onedir)
uv run pyinstaller installer\hantts.spec --noconfirm --clean
# 3) uv.exe 동봉 (버전 고정, SHA256 검증)
#    tools\fetch_uv.ps1 -Version <고정버전> -Dest dist\HanTTS\uv.exe
# 4) 카탈로그·락·워커 휠을 exe 옆에 둔다 (앱은 app_dir()/engines/catalog, app_dir()/wheels 를 읽는다)
Copy-Item engines\catalog dist\HanTTS\engines\catalog -Recurse
Copy-Item dist\wheels dist\HanTTS\wheels -Recurse
# 5) 코드 서명 (exe, dll) — signtool
# 6) 인스톨러
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" /DAppVersion=$ver installer\hantts.iss
# 7) 인스톨러 서명
```

### PyInstaller 주의점
- `onedir` 사용(onefile은 실행마다 압축 해제 → 느림, 백신 오탐 증가)
- PySide6 불필요 모듈 제외(`QtWebEngine`, `Qt3D`, `QtMultimedia` 등) → 용량 절감
- `--windowed`, 아이콘, 버전 리소스(`version_info.txt`) 지정
- 호스트에는 torch/onnxruntime 포함 금지. 다른 conda의 `Library\bin` DLL은 빌드에 쓴 Python의 같은 이름 파일로 바꾸고, 그 환경에 없는 `icu*.dll`과 `api-ms-win-*.dll`은 뺀다. base의 ICU는 Qt6Core와, base OpenSSL은 `_ssl`과 맞지 않는다.
- Windows 음성 엔진용 `winrt.*`, `comtypes` 는 포함 — `hiddenimports`에 `winrt.windows.media.speechsynthesis`, `winrt.windows.storage.streams`, `winrt.windows.foundation`, `comtypes.client` 지정, `comtypes` 생성 캐시(`comtypes.gen`)는 런타임에 데이터 폴더로

## 3. Inno Setup 설계 (`installer/hantts.iss`)
- `PrivilegesRequired=lowest` + `PrivilegesRequiredOverridesAllowed=dialog` → 기본은 사용자 단위 설치. 관리자 설치도 고를 수 있다
- 대상 폴더 페이지는 항상 나온다(`DisableDirPage=no`). 처음 채워지는 경로는 `{localappdata}\Programs\HanTTS`(`%LOCALAPPDATA%\Programs\HanTTS`)이다. 이 상수는 관리자 설치를 골라도 `Program Files`로 바뀌지 않으므로, 다른 디스크나 `Program Files`에 넣으려면 그 페이지에서 경로를 지정한다
- 설정·기록·로그는 설치 폴더와 무관하게 `%LOCALAPPDATA%\HanTTS`에 둔다. 엔진·모델 위치는 `engines_dir`(비우면 같은 데이터 폴더)
- 언어: `Korean.isl` 기본 + English
- 바로가기: 시작 메뉴, (선택) 바탕화면
- 파일 연결(선택): `.htpack` → "HanTTS로 엔진 팩 설치"
- 앱을 켜면 기본 엔진은 Windows 음성이다(`last_engine` 기본값 `windows`).
- 설치 마지막 페이지: [☑ HanTTS 실행], [☐ 한국어 추천 엔진(Supertonic 3) 바로 설치](기본 해제) → 켜면 `--install-engine supertonic`
- **제거 시**: 앱 파일 삭제 후 "다운로드한 엔진·모델, 설정, 기록도 모두 삭제할까요?"를 묻는다. 예를 누르면 `%LOCALAPPDATA%\HanTTS`를 지운다. 기본 버튼은 아니오
- 업그레이드: 같은 `AppId`로 덮어쓰기, 실행 중이면 종료 요청(`CloseApplications=yes`)
- VC++ 재배포 패키지는 설치하지 않는다. 필요한 CRT는 PyInstaller 번들에 들어 있다. Anaconda base의 `icu*.dll`과 `api-ms-win-*.dll`은 빼고, `Library\bin` DLL은 빌드에 쓴 Python 환경의 파일로 바꾼다

## 4. 코드 서명 · SmartScreen
- 현재 산출물은 서명하지 않는다. 서명하지 않으면 SmartScreen "알 수 없는 게시자" 경고가 난다. 상용 배포 시 OV/EV 코드 서명 인증서(또는 Azure Trusted Signing)를 쓴다
- 서명 대상: `HanTTS.exe`, 번들 내 자체 dll, `uv.exe`(재서명 불필요 — 원본 서명 유지), 인스톨러

## 5. CI (GitHub Actions, `windows-latest`)
1. `ci.yml`: `uv sync --frozen` → `ruff` / `mypy` / `pytest -m "not slow"`
2. 태그 `v*`의 `release.yml`: 같은 검사 후 `installer\build.ps1` → `dist\SHA256SUMS.txt` → Release에 인스톨러와 체크섬 업로드. 서명과 포터블 zip은 올리지 않는다.

## 6. 앱 업데이트
현재 앱은 시작 시 버전 확인을 하지 않는다. 새 버전은 같은 `AppId`의 설치 프로그램으로 덮어쓴다.
