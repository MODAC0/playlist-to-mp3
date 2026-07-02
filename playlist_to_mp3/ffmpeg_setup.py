"""크로스 OS ffmpeg/ffprobe 해석기.

우선순위:
  1) 시스템 PATH에 ffmpeg+ffprobe가 있으면 그걸 사용(None 반환 → yt-dlp가 PATH 사용)
  2) 캐시에 이미 받아둔 바이너리가 있으면 그 디렉터리 반환
  3) Windows/Linux: BtbN 정적 빌드를 자동 다운로드해 캐시에 설치
  4) macOS: 정적 빌드 자동설치 대신 `brew install ffmpeg` 안내(가장 신뢰 가능)
"""

import os
import shutil
import stat
import sys
import tarfile
import tempfile
import urllib.request
import zipfile

APP_NAME = "playlist-to-mp3"


def _log(cb, msg):
    if cb:
        cb(msg)


def _cache_dir():
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser(
            r"~\AppData\Local"
        )
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser(
            "~/.local/share"
        )
    d = os.path.join(base, APP_NAME, "ffmpeg")
    os.makedirs(d, exist_ok=True)
    return d


def _exe(name):
    return name + (".exe" if sys.platform == "win32" else "")


def _both_on_path():
    return bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def _cached(cache):
    ff = os.path.join(cache, _exe("ffmpeg"))
    fp = os.path.join(cache, _exe("ffprobe"))
    return ff if os.path.exists(ff) and os.path.exists(fp) else None


# BtbN 정적 빌드는 ffmpeg + ffprobe를 함께 포함한다.
_SOURCES = {
    ("win32", "amd64"): (
        "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/"
        "ffmpeg-master-latest-win64-gpl.zip",
        "zip",
    ),
    ("win32", "arm64"): (
        "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/"
        "ffmpeg-master-latest-winarm64-gpl.zip",
        "zip",
    ),
    ("linux", "x86_64"): (
        "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/"
        "ffmpeg-master-latest-linux64-gpl.tar.xz",
        "tar",
    ),
    ("linux", "aarch64"): (
        "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/"
        "ffmpeg-master-latest-linuxarm64-gpl.tar.xz",
        "tar",
    ),
}


def _machine():
    import platform

    m = platform.machine().lower()
    # 아키텍처 표기 정규화
    if m in ("amd64", "x86_64", "x64"):
        return "amd64" if sys.platform == "win32" else "x86_64"
    if m in ("arm64", "aarch64"):
        return "arm64" if sys.platform == "win32" else "aarch64"
    return m


def _extract_binaries(archive_path, kind, dest):
    """압축을 임시로 풀어 ffmpeg/ffprobe만 dest로 복사한다."""
    wanted = {_exe("ffmpeg"), _exe("ffprobe")}
    found = {}
    with tempfile.TemporaryDirectory() as tmp:
        if kind == "zip":
            with zipfile.ZipFile(archive_path) as z:
                z.extractall(tmp)
        else:
            with tarfile.open(archive_path, "r:xz") as t:
                t.extractall(tmp)
        for root, _dirs, files in os.walk(tmp):
            for f in files:
                if f in wanted and f not in found:
                    found[f] = os.path.join(root, f)
        for name, src in found.items():
            dst = os.path.join(dest, name)
            shutil.copy2(src, dst)
            os.chmod(dst, os.stat(dst).st_mode | stat.S_IEXEC | stat.S_IXGRP)
    missing = wanted - set(found)
    if missing:
        raise RuntimeError(f"압축 안에서 {missing} 를 찾지 못했습니다.")


def _download(url, dest_path, log):
    _log(log, "ffmpeg 다운로드 중… (최초 1회, 수십 MB)")
    req = urllib.request.Request(url, headers={"User-Agent": "playlist-to-mp3"})
    with urllib.request.urlopen(req) as r, open(dest_path, "wb") as out:
        shutil.copyfileobj(r, out)


def ensure_ffmpeg(log=None):
    """ffmpeg/ffprobe가 있는 디렉터리를 반환. PATH로 충분하면 None 반환.

    해석 불가 시 사용자 안내가 담긴 RuntimeError를 던진다.
    """
    if _both_on_path():
        return None  # yt-dlp가 시스템 PATH의 ffmpeg를 사용

    cache = _cache_dir()
    if _cached(cache):
        return cache

    if sys.platform == "darwin":
        raise RuntimeError(
            "ffmpeg가 필요합니다. 터미널에서 다음을 실행해 설치하세요:\n"
            "    brew install ffmpeg\n"
            "(Homebrew가 없다면 https://brew.sh 참고)"
        )

    key = (sys.platform, _machine())
    src = _SOURCES.get(key)
    if not src:
        raise RuntimeError(
            f"이 플랫폼({key})용 ffmpeg 자동 설치를 지원하지 않습니다. "
            "시스템에 ffmpeg/ffprobe를 직접 설치한 뒤 PATH에 추가하세요."
        )

    url, kind = src
    suffix = ".zip" if kind == "zip" else ".tar.xz"
    tmp_archive = os.path.join(cache, "_download" + suffix)
    try:
        _download(url, tmp_archive, log)
        _log(log, "ffmpeg 압축 해제 중…")
        _extract_binaries(tmp_archive, kind, cache)
    finally:
        if os.path.exists(tmp_archive):
            os.remove(tmp_archive)

    if not _cached(cache):
        raise RuntimeError("ffmpeg 설치에 실패했습니다.")
    _log(log, "ffmpeg 준비 완료.")
    return cache
