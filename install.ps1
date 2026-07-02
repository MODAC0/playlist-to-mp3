# Playlist → MP3 원클릭 설치 (Windows)
# 사용(PowerShell): irm https://raw.githubusercontent.com/MODAC0/playlist-to-mp3/main/install.ps1 | iex
$ErrorActionPreference = "Stop"
$Repo = "git+https://github.com/MODAC0/playlist-to-mp3"

# 1) uv 설치 (없을 때만)
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
  Write-Host "▶ uv 설치 중…"
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
}

# 2) 앱 설치 (ffmpeg는 첫 실행 때 자동 다운로드)
Write-Host "▶ playlist-to-mp3 설치 중…"
uv tool install --force $Repo
uv tool update-shell

Write-Host ""
Write-Host "✅ 설치 완료! 새 터미널에서 아래를 실행하세요:"
Write-Host "    playlist-to-mp3"
