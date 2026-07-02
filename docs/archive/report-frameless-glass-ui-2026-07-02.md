# playlist-to-mp3 프레임리스 글래스 창·알림·Pretendard 적용 보고서

- 날짜: 2026-07-02
- 대상: `playlist-to-mp3` (macOS PySide6 GUI)
- 요청 4건: 타이틀바 통합 프레임리스 글래스 창 / 카드 호버 밝기 변화 / 완료 시 시스템 알림 / 전체(진행 로그 포함) Pretendard 폰트

## 적용 내용

### 1. 타이틀바 통합 프레임리스 글래스 창 (app.py `_integrate_titlebar`)

- pyobjc(11.1)로 NSWindow에 접근해 `titlebarAppearsTransparent` + `NSWindowStyleMaskFullSizeContentView`(1<<15) + 타이틀 텍스트 숨김 적용
- 신호등 버튼은 네이티브 그대로 유지, 글래스 그라디언트 배경이 창 최상단까지 이어짐
- 상단 여백 48px로 신호등 아래에서 콘텐츠 시작, 상단 44px 영역 드래그 시 `startSystemMove()`로 창 이동
- pyobjc 임포트 실패 시 일반 창으로 폴백 (`_HAS_COCOA`)

### 2. 카드 호버 밝기 (build_qss)

- `QFrame#card:hover` 배경 알파 상승 (다크 7%→10%, 라이트 58%→72%)

### 3. 완료 시 시스템 알림 (`_notify`)

- `/usr/bin/osascript`의 `display notification`으로 알림 센터 발송 ("변환 완료: 성공 x곡 · …")
- 실패해도 앱 흐름에 영향 없도록 예외 무시, timeout 5초

### 4. Pretendard 폰트 전체 적용

- `vendor/fonts/PretendardVariable.ttf` 번들 (공식 v1.3.9, SIL OFL 라이선스라 재배포 가능)
- 실행 시 `QFontDatabase.addApplicationFont` 등록, QSS 전역 + 진행 로그까지 `'Pretendard Variable'` 지정
- spec `datas`에 `('vendor/fonts', 'fonts')` 추가 → 프로즌 번들에서 `_MEIPASS/fonts`로 로드

## 검증

| 항목 | 결과 |
|---|---|
| Pretendard 등록 (`QFontDatabase.families()`에 'Pretendard Variable') | OK |
| 타이틀바 통합 플래그 + 실제 창 스크린샷(신호등+글래스 상단, `docs/ui-frameless-dark.png`) | OK |
| 알림 발송 (osascript) | OK |
| 재빌드 번들에 fonts/AppKit/objc 포함 확인 | OK |
| 번들 셀프테스트 + 프로즌 GUI 기동 유지 | OK |

## 주의점

- venv pip 21.x로는 pyobjc 휠 설치 실패 → pip 업그레이드 후 설치됨 (Python 3.9 환경)
- 전체 창 캡처(`screencapture -l`)는 화면 기록 권한에 따라 실패할 수 있음 (검증 시 1회 실패 후 성공)

재빌드된 배포본: `dist/Playlist to MP3.app` (2026-07-02).

## 검증 프로토콜 기록

feature-verifier(Playwright MCP)는 네이티브 Qt 앱에 적용 불가. 실제 GUI 구동 + 네이티브 창 스크린샷 육안 검증으로 대체.
