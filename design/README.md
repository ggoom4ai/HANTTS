# design/

| 경로 | 내용 |
|---|---|
| `mockups/*.dc.html` | 디자인 캔버스의 화면 원본 사본. 각 요소의 정확한 색·크기·간격이 inline style로 들어 있다. **Cursor에 참조용으로 제공**하며, 디자인 런타임(`support.js`) 전용 문법이라 브라우저에서 단독 실행되지는 않는다. |
| 원본 캔버스 | https://claude.ai/artifact/M5toHYYNPWRLokbebvr4m7 (화면 보기·수정·PNG/PDF 내보내기) |

토큰과 스타일시트는 앱 리소스에 있다:
- `src/hantts/app/resources/tokens.json`
- `src/hantts/app/resources/themes/dark.qss`

## 목업 읽는 법 (Qt로 옮길 때)
- `style="display:flex; flex-direction:column; gap:16px; padding:20px 24px"` → `QVBoxLayout`, `setSpacing(16)`, `setContentsMargins(24, 20, 24, 20)`
- `flex: 1` → `addWidget(w, stretch=1)` / `flex-wrap` 카드 그리드 → `FlowGridLayout`
- `<sc-for list="{{rows}}">` → 모델/반복 생성, 반복 데이터는 스크립트 블록의 `renderVals()` 안에 샘플로 있다
- `<sc-if>` → 상태에 따른 `setVisible()`
- 색 hex → `tokens.json`에서 같은 값의 토큰 이름으로 치환
- `border-radius`, `border`, 배경 → `dark.qss`의 해당 `variant`/`role` 규칙 (없으면 추가)

## 화면 캡처
캔버스에서 각 아트보드를 PNG로 내보내 `design/screens/01_main.png` 등으로 넣어 두면 Cursor 채팅에 이미지로 첨부해 비교 작업을 시킬 수 있다.
