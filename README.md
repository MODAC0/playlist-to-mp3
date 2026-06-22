# Playlist → MP3

YouTube 플레이리스트(또는 단일 영상) URL을 넣으면 각 항목을 MP3로 변환해 저장하는 macOS 앱.

## 사용법
1. `Playlist to MP3.app` 실행 (처음 실행 시 우클릭 → 열기)
2. 플레이리스트/영상 URL 붙여넣기
3. 저장 폴더 선택, 음질(128/192/320kbps) 선택
4. **변환 시작**

- **중복 방지**: 저장 폴더의 `.download_archive.txt`에 받은 항목을 기록해, 다시 돌려도 새 곡만 받습니다.
- `yt-dlp`와 `ffmpeg`는 앱 안에 번들되어 별도 설치가 필요 없습니다.

## 배포 메모
- 서명/공증(notarize)은 하지 않았습니다. 다른 Mac에서 처음 열 때 Gatekeeper 경고가 나오면
  **우클릭 → 열기**, 또는 시스템 설정 → 개인정보 보호 및 보안에서 허용하세요.
- Apple Silicon(arm64) 전용으로 빌드되었습니다.

## 소스에서 다시 빌드하기
```bash
cd PlaylistToMP3
/usr/bin/python3 -m venv .venv
.venv/bin/python -m pip install PySide6-Essentials yt-dlp pyinstaller
.venv/bin/pyinstaller --noconfirm --clean --windowed \
  --name "Playlist to MP3" --osx-bundle-identifier com.upfall.playlist2mp3 \
  --add-binary "vendor/ffmpeg:." --add-binary "vendor/ffprobe:." \
  --collect-all yt_dlp app.py
```
결과물: `dist/Playlist to MP3.app`

## 기술 메모
- GUI: PySide6(Qt). macOS 26(Tahoe)의 시스템 Tk 8.5가 깨져 Tkinter 대신 Qt 사용.
- YouTube SABR 강제 회피를 위해 `android_vr` player client 사용 (PO 토큰 불필요).
- 다운로드 작업은 별도 스레드에서 실행, 진행률/로그를 Qt 시그널로 UI에 전달.
