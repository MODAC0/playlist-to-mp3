# playlist-to-mp3 다운로드 중 강제종료(SIGSEGV) 수정 보고서

- 날짜: 2026-07-02
- 대상: `playlist-to-mp3` (macOS PySide6 GUI, PyInstaller 번들)
- 증상: 플레이리스트 다운로드 도중 앱이 강제종료됨 (11:30~11:33 사이 크래시 4회)

## 원인

`~/Library/Logs/DiagnosticReports/`의 크래시 리포트 4건 모두 EXC_BAD_ACCESS(SIGSEGV)이며, 죽는 지점이 매번 다른 Qt 페인트 코드였음. 재현 후 확보한 리포트에서 결정적 증거 확인: **faulting thread가 QThread(워커 스레드)이고 그 스택에 `QProgressBar::paintEvent`가 존재**.

근본 원인은 `app.py`의 시그널 연결 방식:

```python
self.worker.progress.connect(lambda v: self.bar.setValue(int(v)))
```

PySide6에서 시그널을 QObject 바운드 메서드가 아닌 **람다/일반 함수에 연결하면 큐잉 없이 발신(워커) 스레드에서 직접 실행**된다(실험으로 확정: bound method는 MainThread, lambda·plain function은 워커 스레드에서 실행). 그 결과 `QProgressBar.setValue()` → 동기 리페인트가 워커 스레드에서 일어나 GUI 자료구조가 오염되고, 메인 스레드의 임의 페인트 지점에서 세그폴트 발생.

## 수정 내용 (app.py)

1. **크래시 근본 수정**: `progress` 시그널을 람다 대신 `MainWindow._on_progress` 바운드 메서드 슬롯으로 연결 (메인 스레드로 큐잉됨)
2. **진행률 로그 스팸 차단**: `_YtLogger.debug`에서 `[download] x.x%` 진행률 라인 필터링 (청크마다 초당 수백 건 appendPlainText 방지, 퍼센트는 상태줄·프로그레스바가 표시)
3. **UI 갱신 스로틀**: `Worker._hook`에서 progress/status 시그널을 최대 10회/초로 제한
4. **로그창 상한**: `logbox.setMaximumBlockCount(2000)`으로 문서 무한 성장 방지

## 검증

| 테스트 | 결과 |
|---|---|
| 수정 전 GUI 프로그래매틱 구동 재현 (실제 플레이리스트 7곡) | SIGSEGV(exit 139) 재현 |
| 수정 후 동일 재현 (앱 코드 무수정 플로우, 완료 폴링 감지) | 7/7곡 mp3 생성, exit 0, 경고 없음 |
| PyInstaller 재빌드 후 번들 셀프테스트 (`P2M_SELFTEST=1`) | OK (mp3 생성 확인) |

재빌드된 배포본: `dist/Playlist to MP3.app` (2026-07-02).

## 남은 참고사항 (미수정)

- **ad-hoc 서명**: 다른 맥에 배포 시 Gatekeeper 차단됨. 배포하려면 Developer ID 서명·공증 필요
- **중복 방지 아카이브**: 같은 저장 폴더 재사용 시 `.download_archive.txt` 때문에 파일이 없어도 전부 건너뜀 (의도된 동작이지만 "안 받아짐"으로 오인 가능)
- **번들 yt-dlp 2025.10.14 + Python 3.9**: yt-dlp가 3.9 지원 중단 예고 중, YouTube 변경 시 취약. 주기적 재빌드 권장
- `Desktop/playground/playlist-to-mp3`의 구사본은 이번 수정 미반영 (upfall 사본이 최신)

## 검증 프로토콜 기록

feature-verifier(Playwright MCP)는 브라우저 앱 대상이라 네이티브 Qt 앱에는 적용 불가. 대신 실제 GUI를 프로그래매틱으로 구동해 다운로드 전 과정을 검증하는 방식으로 대체함.
