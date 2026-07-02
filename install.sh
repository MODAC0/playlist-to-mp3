#!/usr/bin/env sh
# Playlist → MP3 원클릭 설치 (macOS / Linux)
# 사용: curl -LsSf https://raw.githubusercontent.com/MODAC0/playlist-to-mp3/main/install.sh | sh
set -e

REPO="git+https://github.com/MODAC0/playlist-to-mp3"

# 1) uv 설치 (없을 때만)
if ! command -v uv >/dev/null 2>&1; then
  echo "▶ uv 설치 중…"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

# 2) macOS는 ffmpeg를 brew로 미리 설치(가장 안정적). Linux는 앱이 첫 실행 때 자동 다운로드.
if [ "$(uname)" = "Darwin" ] && ! command -v ffmpeg >/dev/null 2>&1; then
  if command -v brew >/dev/null 2>&1; then
    echo "▶ ffmpeg 설치 중 (brew)…"
    brew install ffmpeg
  else
    echo "⚠  ffmpeg와 Homebrew가 없습니다. https://brew.sh 설치 후 'brew install ffmpeg' 를 실행하세요."
  fi
fi

# 3) 앱 설치
echo "▶ playlist-to-mp3 설치 중…"
uv tool install --force "$REPO"
uv tool update-shell 2>/dev/null || true

echo ""
echo "✅ 설치 완료! 새 터미널을 열고 아래를 실행하세요:"
echo "    playlist-to-mp3"
