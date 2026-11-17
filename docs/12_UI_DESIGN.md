# 12. UI 디자인 명세 (비주얼 · 컴포넌트 · 화면별 구현 지침)

> `05_UI_SPEC.md`가 **무엇을** 보여줄지(기능·흐름)라면, 이 문서는 **어떻게 보이고 Qt로 어떻게 만드는지**다.
> 시각 기준(원본): 디자인 캔버스 <https://claude.ai/artifact/M5toHYYNPWRLokbebvr4m7>
> 저장소 사본: `design/mockups/*.dc.html` (각 요소의 정확한 색·크기·간격이 inline style로 들어 있음 — Cursor에서 `@design/mockups/Main.dc.html` 로 참조)
> 토큰: `src/hantts/app/resources/tokens.json` · 스타일시트: `src/hantts/app/resources/themes/dark.qss`

---

## 1. 디자인 원칙
1. **스튜디오 다크** — 오디오 편집기처럼 잉크색 배경 위에 콘텐츠(원고·파형)가 가장 밝게 보인다. 크롬(타이틀바·레일)이 가장 어둡고, 카드가 그 위.
2. **강조색은 하나** — 페리윙클 블루 `#7C8CFF`는 "지금 선택/진행 중/주 행동"에만 쓴다. 성공·경고·오류 색은 상태 표시에만.
3. **숫자는 모노** — 시간, 용량, 진행률, 파라미터 값은 JetBrains Mono. 한글 UI는 IBM Plex Sans KR.
4. **넉넉한 터치 영역** — 클릭 가능한 요소 최소 44px(칩 36px 예외), 카드 내부 여백 18–20px.
5. **위계는 밝기로** — 텍스트 4단계(`text` → `text_secondary` → `text_muted` → `text_faint`), 모두 배경 대비 4.5:1 이상.
6. **장식 금지** — 그라데이션, 이모지, 왼쪽 컬러 띠 카드 사용 안 함. 아이콘은 단색 선(stroke 1.8–2.2).

## 2. 색상 토큰 (요약 — 전체는 tokens.json)

| 토큰 | 값 | 용도 |
|---|---|---|
| `chrome` | `#0B0D11` | 타이틀바, 내비게이션 레일 |
| `bg` | `#0E1014` | 앱 배경 |
| `surface_alt` | `#11141A` | 인스펙터, 카드 안 타일 |
| `surface` | `#151820` | 카드, 독, 입력창 |
| `surface_raised` | `#1B1F29` | 값 칩, 음성 버튼(비선택), 툴팁 |
| `track` | `#232835` | 슬라이더/진행 트랙, 선택된 세그먼트 |
| `border` / `border_strong` | `#222734` / `#2E3442` | 카드 테두리 / 버튼·입력 테두리 |
| `text` … `text_faint` | `#E8EAF0` `#C5CBD8` `#9AA3B5` `#7F889B` | 텍스트 4단계 |
| `accent` | `#7C8CFF` | 주 버튼, 선택, 재생된 파형 |
| `accent_bg` / `accent_border` | `#1B2140` / `#3A4680` | 선택된 레일 항목·칩 배경 / 선택 카드 테두리 |
| `success` / `warning` / `danger` | `#3DD68C` / `#F5B544` / `#FF6B6B` | 상태 점·진행 막대 (배지는 `*_bg` + `*_text` 쌍) |

**엔진 배지** (`korean_badge` 토큰): 한국어 공식 = 초록, 내장·다운로드 없음 = 청록, 한국어 음성 설치 필요 = 주황. 엔진 표식(S3/Me/Wi)은 `engine_mark` 토큰의 고유 색.

## 3. 타이포그래피

| 역할 | 크기/굵기 | 예 |
|---|---|---|
| display | 38 / 700, 자간 -0.03em | 첫 실행 마법사 헤드라인 |
| h1 | 28 / 700, -0.02em | 화면 제목 "엔진", "일괄 변환" |
| h2 | 24 / 700 | 마법사 단계 제목 |
| title | 17–19 / 700 | 카드·대화상자 제목 |
| section | 15 / 600 | "원고", "음성", "공통 설정" |
| editor | 16 / 400, 줄높이 1.6 | 원고 문장 |
| base | 14 / 400–500 | 기본 UI |
| body | 13 | 버튼(작은), 표 |
| caption | 12, `text_muted` | 보조 설명 |
| mono | JetBrains Mono 11–13 / 500 | 시간·용량·값 |

글꼴 파일은 `src/hantts/app/resources/fonts/`에 동봉(둘 다 SIL OFL 1.1 → 재배포 가능, 라이선스 파일 함께). 없으면 "맑은 고딕"으로 대체.

## 4. 간격 · 모서리 · 크기
- 간격 단위: 4, 6, 8, 10, 12, 14, 16, 18, 20, 24, 28, 32, 40 (tokens `space`)
- 모서리: 입력/작은 버튼 10, 버튼·선택기 12, 카드(작업공간) 16, 엔진 카드 18, 대화상자 22, 마법사 26, 칩·배지 999
- 고정 크기: 타이틀바 48, 레일 84(항목 68×58), 인스펙터 320–380, 컨트롤 44, 재생 버튼 52(원형), 스위치 36×20
- 창: 기본 1440×900, 최소 1100×720. 1280 미만에서는 인스펙터를 접이식 패널(오른쪽 서랍)로 전환.

## 5. 컴포넌트 카탈로그 → Qt 구현

| 컴포넌트 | 디자인 위치 | Qt 구현 | 상태 |
|---|---|---|---|
| 타이틀바 | 모든 화면 상단 | **네이티브 타이틀바 + 다크 모드**(`theme.dark_title_bar`) 권장. 명령 검색은 툴바로 내림. 완전 커스텀이 필요하면 `QWindowKit` 검토 | Phase 4 |
| 내비게이션 레일 | 왼쪽 | `QToolButton[variant="nav"]` (아이콘 위·텍스트 아래 `ToolButtonTextUnderIcon`, `setCheckable`) + `QButtonGroup(exclusive)` | Phase 1 |
| 선택기(엔진/언어/프리셋) | 작업공간 상단 | `QToolButton[variant="selector"]` + `QMenu` 또는 팝업 `QListView`. 엔진 선택기 안에 엔진 표식 + 배지 | Phase 3 |
| 주/보조/반전 버튼 | 곳곳 | `QPushButton[variant="primary|ghost|inverse|flat"]`, `size="sm"` | Phase 1 |
| 세그먼트 | 출력 형식, 기본/고급 탭, 동시 작업 수 | `QWidget[role="segmented"]` 안에 `QPushButton[variant="segment"]` + `QButtonGroup` | Phase 1 |
| 칩 | 엔진 필터, 비교 파라미터 | `QPushButton[variant="chip"]` | Phase 2 |
| 토글 스위치 | 숫자 읽기 변환, SRT 등 | `widgets/toggle_switch.py` ✅ 골격 제공 | Phase 1 |
| 슬라이더 행 | 인스펙터 파라미터 | `widgets/slider_row.py` ✅ (param_panel이 생성) | Phase 1 |
| 음성 그리드 | 인스펙터 | 5열 `QGridLayout` + `QPushButton[variant="voice"]` checkable | Phase 3 |
| 문장 목록 | 원고 편집기 | `QListView` + **커스텀 `QStyledItemDelegate`**: 번호, 상태 아이콘(완료/생성 중 회전/대기), 화자 태그, 사전 단어 점선 밑줄, "엔진 입력 →" 보조 줄, 길이. 편집은 더블클릭 시 인라인 `QPlainTextEdit` | Phase 4 |
| 파형 | 하단 독, 비교 | `widgets/waveform.py` ✅ (재생/생성 완료/대기 3색) | Phase 4 |
| 원형 진행률 | 설치 대화상자 | `widgets/progress_ring.py` ✅ | Phase 2 |
| 엔진 카드 | 엔진 관리자 | `QFrame[role="card"]` 복합 위젯 `EngineCard`(표식, 이름, 추천 배지, 한국어 배지, 설명, 3칸 정보 타일, 공지 배너, 설치 진행 막대, 상태 점+라이선스, 액션 버튼) | Phase 2 |
| 반응형 카드 그리드 | 엔진 관리자, 비교 | 커스텀 `FlowGridLayout`(최소 폭 330/300px, 남는 폭 균등 분배) | Phase 2 |
| 배너 | 지원 종료 안내, 한국어 미지원 경고 | `QFrame[role="banner"][tone=…]` + 아이콘 + 라벨 + (선택) 버튼 | Phase 2 |
| 대기열 표 | 일괄 변환 | `QTableView` + 모델, 진행 열은 델리게이트로 막대+상태 텍스트, 마지막 열 액션 버튼 | Phase 5 |
| 모달 대화상자 | 설치 진행 | `QDialog[role="modal"]` + 배경 딤(부모 위 반투명 오버레이 위젯) | Phase 2 |
| 드롭 영역 | 일괄 변환 | `QFrame` 점선 테두리(`paintEvent`), `setAcceptDrops` | Phase 5 |

**QSS 사용 규칙** — 스타일은 objectName/동적 속성으로만 선택한다(`variant`, `role`, `tone`, `text_role`, `selected`). 상태가 바뀌면 `theme.set_prop(widget, selected=True)`로 속성 변경과 재적용을 한 번에. QSS로 안 되는 것(그림자, 원형 진행, 파형, 점선 밑줄, 회전 아이콘)만 `paintEvent`/델리게이트로 그린다.

**아이콘** — 디자인의 아이콘은 24×24 viewBox 선 아이콘이다. `resources/icons/*.svg`로 저장하고 `currentColor` 대신 런타임에 색을 입히는 `icon(name, color_token)` 헬퍼(QSvgRenderer → QPixmap 캐시)를 만든다. 경로 데이터는 목업 파일의 `<path d=…>`에서 그대로 가져온다:

| 이름 | 사용처 | 출처 |
|---|---|---|
| `wave` | 로고, 작업 | Main.dc.html 타이틀바 |
| `engine`, `layers`, `columns`, `book`, `clock`, `sliders` | 레일 메뉴 | Main.dc.html `navDefs` |
| `search`, `chevron-down`, `play`, `pause`, `prev`, `next`, `download`, `upload`, `plus`, `check`, `warning`, `close` | 공통 | 각 목업 |

## 6. 테마 적용 흐름 (`src/hantts/app/theme.py` ✅)
```
QApplication 생성 → theme.apply(app)
  ├ load_fonts()            resources/fonts/*.ttf 등록
  ├ QFont(IBM Plex Sans KR, 14px)
  ├ QPalette(토큰 색)       Fusion 스타일 기반
  └ setStyleSheet(render_qss("dark"))   dark.qss 의 ${color.accent} 등 → tokens.json 값
MainWindow.show() → theme.dark_title_bar(window)
```
- 라이트 테마는 `themes/light.qss` + tokens에 `"light"` 색 세트를 추가하는 방식으로 확장(v1 범위 외, 구조만 유지).
- 커스텀 위젯은 색을 하드코딩하지 말고 `theme.color("accent")`로 조회.

## 7. 화면별 구현 지침

현재 내비게이션은 작업, 엔진, 사전, 기록, 설정이다. 엔진 비교와 일괄 변환은 현재 앱에 없다.

### 7.1 작업공간 (`Main.dc.html`)
```
QMainWindow
└ AppRoot (QHBoxLayout, 0 margin)
   ├ NavRail [role=navrail] 84px
   ├ WorkArea (QVBoxLayout, 20/24 여백, 16 간격)
   │   ├ TopBar: EngineSelector · LanguageSelector · PresetSelector · stretch · [파일 열기] [프리셋 저장]
   │   ├ ScriptCard [role=card] (stretch)
   │   │   ├ 헤더: "원고" · mono 통계 · stretch · Toggle "숫자·날짜 읽기 변환" · 링크 "변환 결과 미리보기"
   │   │   ├ (조건) 한국어 미지원 배너
   │   │   └ SentenceListView + SentenceDelegate
   │   └ TransportDock [role=dock]
   │       ├ 이전 · ▶(52px 원형) · 다음
   │       ├ WaveformView + 시간(mono) + "문장 3/6 생성 중 · 실시간 대비 N배 빠름"
   │       └ 출력 형식 세그먼트 · Toggle SRT · [내보내기](inverse)
   └ Inspector [role=inspector] 320–380px
       ├ "음성" + 음성 그리드(5열) + 샘플 듣기 카드
       ├ 기본/고급 세그먼트 → ParamPanel (SliderRow / ToggleRow / Combo …)
       └ 하단: "엔진이 알려준 파라미터로 자동 구성" · [기본값 복원]
```
- 엔진을 바꾸면 원고만 남긴다. 언어는 한국어(없으면 그 엔진의 첫 언어), 음성·파라미터는 기본값, 파형·재생·진행·상태 문구는 비운다.
- 문장 상태별 표현: 완료 = 초록 체크, 생성 중 = 강조색 회전 원호(QTimer 60fps 회전) + 행 배경 `accent_bg_row` + 1px `accent_border` 테두리, 대기 = 회색 원 + 텍스트 `#AEB5C4`.
- 문장 클릭 → 해당 구간 재생, 우클릭 메뉴: 이 문장만 다시 생성 / 음성 바꾸기 / 사전에 추가.
- 파형: 생성되는 청크가 도착할 때마다 `set_audio()` 갱신, 재생 위치 30fps 갱신.

### 7.2 엔진 관리자 (`EngineManager.dc.html`)
- 상단: h1 "엔진" + 설명, 오른쪽 [오프라인 팩 가져오기] [캐시 정리 · N GB]
- 디스크 사용 카드: 엔진별 색 누적 막대(엔진 표식 색 사용) + 범례 + 데이터 폴더 경로 + "변경"
- 필터 칩: 전체 / 한국어 지원 / 설치됨 (개수 표시)
- `FlowGridLayout`에 `EngineCard` 3개(Windows 음성, Supertonic 3, MeloTTS). 기본으로 선택된 엔진은 Windows 음성이다.
- 카드 상태별 액션: 미설치 → [설치](primary)+[자세히] / 설치됨 → [테스트][복구][제거] / 설치 중 → 진행 막대 + [진행 보기][취소] / Windows 음성 → 다운로드 없음: [음성 목록](음성 수 표시) [Windows 음성 설정], 한국어 음성이 없으면 경고 배너 + [자동 설치] [Windows 설정에서 설치]

### 7.3 엔진 설치 진행 (`InstallDialog.dc.html`)
- 660px 모달, 부모 화면은 어둡게(오버레이 `#07080B` 65%)
- 헤더: 엔진 표식 + "OOO 설치" + 메타 + 닫기(=백그라운드 전환)
- 4단계 스테퍼(요약 / 라이선스 동의 / 설치 / 완료): 4px 막대 — 완료 초록, 현재 강조색, 남음 트랙색
- 본문: ProgressRing + 현재 단계 제목 + "torch 내려받는 중 · 속도 · 남은 시간" + 안심 문구
- 단계 체크리스트 2열(설치 파이프라인 단계와 1:1, `04_ENGINE_MANAGER.md §2`)
- "자세히 보기(설치 로그)" 접이식 `QPlainTextEdit`(읽기 전용, mono 11.5px, 최대 2,000줄 유지)
- 바닥: "취소하면 설치 전 상태로 되돌립니다." · [취소] · [백그라운드에서 계속](primary)

### 7.4 엔진 비교 (`Compare.dc.html`, 현재 앱에 없음)
- 비교 문장 `QPlainTextEdit`(17px) → 슬롯 카드 2–4개 + [슬롯 추가] 점선 카드
- 슬롯: 문자(A/B/C) 배지 · 엔진 · 음성 · 파라미터 칩 · 미니 파형+재생 · 길이/생성 시간/숫자 읽기 · [이게 좋아요](토글) · [프리셋으로 저장]
- 재생 중 슬롯은 `selected=true`. 한 번에 하나만 재생.

### 7.5 일괄 변환 (`Batch.dc.html`, 현재 앱에 없음)
- 왼쪽: h1 + 설명 · 드롭 영역(92px, 점선) · 대기열 표 · 전체 진행 카드([중지] [일시정지])
- 오른쪽 인스펙터: 공통 설정(엔진, 음성, 프리셋, 출력 형식, 출력 폴더(mono), 파일 이름 규칙(mono)) · 동시 작업 수 세그먼트 1–4 + 안내
- 행 상태: 완료(초록, [열기]) · 생성 중(강조, [중지]) · 오류(빨강, 오류 사유를 결과 열에, [다시 시도]) · 대기(회색, [제거])

### 7.6 첫 실행 마법사 (`Onboarding.dc.html`)
- 1040px 카드, 왼쪽 브랜드 패널(`accent_bg` 배경, 헤드라인 38px, 장식 파형) / 오른쪽 단계 내용
- 상단 진행 "1 / 3" + 막대
- 1단계 용도 선택(라디오형 큰 버튼 3개) → 2단계 추천 엔진 카드 + 라이선스 동의 체크 → 3단계 데이터 폴더·여유 공간·안심 항목
- 추천 규칙: 고품질 한국어 → Supertonic 3 / 설치 없이 바로 → Windows 음성 / 억양 중시 → MeloTTS. 처음 선택된 용도는 "설치 없이 바로 읽기"(Windows 음성).
- 버튼: [건너뛰기](flat) · [이전] · [다음 → 이 엔진으로 계속]. Windows 음성은 [시작하기]로 끝내고, 다른 엔진은 [설치하고 시작하기]가 설치 대화상자를 연다.

### 7.7 디자인이 아직 없는 화면 (같은 언어로 구현)
- **발음 사전**: 표(원문 · 읽기 · 범위 · 정규식)와 하단 입력. [추가] [삭제].
- **기록**: 카드 대신 행 목록(제목, 엔진 표식, 길이, 시각, ▶, 폴더 열기). 아래 [재생] [선택삭제] [전체 삭제]. 선택삭제는 고른 행만 지우고, 전체 삭제는 확인 후 기록 전부를 지운다.
- **설정**: 왼쪽 섹션 목록 + 오른쪽 폼, 폼 행 = 라벨/설명(왼쪽) + 컨트롤(오른쪽), 구분선 `divider`.

## 7.8 앱 아이콘
- 잉크색 둥근 타일(`#141821`) + 가운데가 가장 밝은 파형 막대(`#6F80FF` → `#8E9CFF` → `#C9D0FF`).
- 크기별 별도 디자인: 16–20px 막대 3개, 24–40px 4개, 48px 이상 5개 + 테두리. 원본 생성기 `tools/make_icon.py`(rsvg-convert + Pillow).
- 파일: `installer/hantts.ico`(16·20·24·32·40·48·64·96·128·256 포함 — PyInstaller `icon=`, Inno `SetupIconFile`), `src/hantts/app/resources/icons/app.svg`, `app_256.png`, `app_512.png`.
- 앱에서 `QApplication.setWindowIcon(QIcon(".../icons/app.svg"))` — 작업 표시줄 아이콘은 exe에 박힌 .ico가 쓰인다.

## 8. 상호작용 · 모션
- 호버: 배경 한 단계 밝게(`surface` → `surface_raised`), 120ms
- 선택 변화·스위치: 140–180ms OutCubic (`QPropertyAnimation`)
- 생성 중 아이콘 회전 1회전/0.9초, 진행 막대는 값 변화 시 180ms 보간
- 토스트(설치 완료 등): 오른쪽 아래, 4초, `surface_raised` + 상태 점
- 포커스: 모든 컨트롤 1–2px `accent` 테두리(QSS `:focus`), Tab 순서 = 시각적 순서
- 접근성: 모든 아이콘 버튼 `setAccessibleName`, 상태 색은 아이콘/텍스트와 함께 표시(색만으로 구분하지 않음)

## 9. 수용 기준 (UI)
- [ ] 6개 화면을 목업과 나란히 놓고 비교했을 때 색·간격·크기 차이가 눈에 띄지 않는다(픽셀 단위 일치는 요구하지 않음)
- [ ] 코드에 색상 hex 하드코딩 없음(`tokens.json`/`theme.color()`만) — `rg "#[0-9A-Fa-f]{6}" src/hantts/app --glob '!resources/**'` 결과 0건
- [ ] 125%/150% 디스플레이 배율에서 글자·아이콘이 흐리지 않다(`QT_ENABLE_HIGHDPI_SCALING` 기본, SVG 아이콘)
- [ ] 1100×720 최소 창에서 잘림 없이 동작(인스펙터 서랍 전환)
- [ ] 키보드만으로 작업공간 전체 조작 가능
