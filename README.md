# Playlist → MP3

![Playlist → MP3](docs/hero.png)

YouTube 플레이리스트(또는 단일 영상) URL을 넣으면 각 항목을 **`가수 - 제목.mp3`** 로
변환해 저장하는 크로스 플랫폼(macOS · Windows · Linux) GUI 앱. 태그(아티스트/제목/앨범)와
앨범아트(원본 비율)를 파일에 임베드합니다.

## 설치 (원클릭)

터미널에 아래 한 줄을 붙여넣으면 `uv` 설치 → 앱 설치까지 끝납니다.

**macOS / Linux**
```sh
curl -LsSf https://raw.githubusercontent.com/MODAC0/playlist-to-mp3/main/install.sh | sh
```

**Windows (PowerShell)**
```powershell
irm https://raw.githubusercontent.com/MODAC0/playlist-to-mp3/main/install.ps1 | iex
```

설치 후 새 터미널에서 실행:
```
playlist-to-mp3
```

### 수동 설치 (uv가 이미 있는 경우)
```sh
uv tool install git+https://github.com/MODAC0/playlist-to-mp3
```
업데이트: `uv tool upgrade playlist-to-mp3`

## 사용법
1. `playlist-to-mp3` 실행 → 창이 뜹니다
2. 플레이리스트/영상 URL 붙여넣기
3. 저장 폴더 선택, 음질(128/192/320kbps) 선택
4. **변환 시작**

- **중복 방지**: 저장 폴더의 `.download_archive.txt`에 받은 항목을 기록해, 다시 돌려도 새 곡만 받습니다.

## ffmpeg 처리
- **시스템 PATH에 ffmpeg/ffprobe가 있으면** 그걸 사용합니다.
- **없을 때**:
  - Windows / Linux → 첫 실행 시 정적 빌드를 자동 다운로드해 캐시에 설치
  - macOS → `brew install ffmpeg` 로 설치 (원클릭 스크립트가 자동 시도)

## 기술 메모
- GUI: PySide6(Qt) — 크로스 플랫폼.
- YouTube SABR 강제 회피를 위해 `android_vr` player client 사용 (PO 토큰 불필요).
- 다운로드 작업은 별도 스레드에서 실행, 진행률/로그를 Qt 시그널로 UI에 전달.
- 출력 템플릿: `%(artist,creator,uploader)s - %(title)s`, postprocessor로 메타데이터 +
  썸네일(jpg 변환 후) 임베드, 플레이리스트 자체 썸네일은 저장 안 함(`pl_thumbnail`).

## (선택) macOS .app 로 빌드하기
uv 배포 대신 더블클릭 아이콘이 필요하면 PyInstaller로 번들할 수 있습니다(Apple Silicon 전용,
미서명이라 첫 실행 시 우클릭 → 열기 필요):
```bash
uv run --with pyinstaller pyinstaller --noconfirm "Playlist to MP3.spec"
```
결과물: `dist/Playlist to MP3.app`
