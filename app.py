#!/usr/bin/env python3
"""Playlist → MP3 — 독립형 macOS GUI (PySide6/Qt).

YouTube 플레이리스트(또는 단일 영상) URL을 넣으면 각 항목을 MP3로 변환해 저장한다.
yt-dlp와 ffmpeg는 앱에 번들된 바이너리를 사용하므로 별도 설치가 필요 없다.
"""

import os
import sys
import traceback

from PySide6.QtCore import Qt, QObject, QThread, Signal
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QCheckBox, QProgressBar, QPlainTextEdit,
    QFileDialog, QMessageBox,
)
from PySide6.QtGui import QFont

import yt_dlp


APP_TITLE = "Playlist → MP3"


def resource_dir():
    """번들된 리소스(ffmpeg 등)가 있는 디렉터리."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return base
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor")


def ffmpeg_location():
    """ffmpeg/ffprobe가 들어있는 디렉터리. 번들 우선, 없으면 시스템 PATH."""
    d = resource_dir()
    if os.path.exists(os.path.join(d, "ffmpeg")):
        return d
    v = os.path.join(d, "vendor")
    if os.path.exists(os.path.join(v, "ffmpeg")):
        return v
    return None


class _YtLogger:
    """yt-dlp 메시지를 워커 시그널로 흘려보낸다."""

    def __init__(self, emit):
        self.emit = emit

    def debug(self, msg):
        if msg and not msg.startswith("[debug]"):
            self.emit(msg)

    def info(self, msg):
        if msg:
            self.emit(msg)

    def warning(self, msg):
        if msg:
            self.emit("⚠ " + msg)

    def error(self, msg):
        if msg:
            self.emit("✖ " + msg)


class Worker(QObject):
    log = Signal(str)
    status = Signal(str)
    progress = Signal(float)
    finished = Signal(bool, str)  # (성공?, 오류텍스트)

    def __init__(self, url, out_dir, bitrate, skip_dupes):
        super().__init__()
        self.url = url
        self.out_dir = out_dir
        self.bitrate = bitrate
        self.skip_dupes = skip_dupes
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def _hook(self, d):
        if self._cancel:
            raise yt_dlp.utils.DownloadCancelled()
        st = d.get("status")
        if st == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            done = d.get("downloaded_bytes") or 0
            pct = (done / total * 100) if total else 0
            self.progress.emit(pct)
            title = d.get("info_dict", {}).get("title", "")
            self.status.emit(f"다운로드 중: {title}  {pct:4.1f}%")
        elif st == "finished":
            self.status.emit("MP3 변환 중…")
            self.progress.emit(100.0)

    def run(self):
        ffloc = ffmpeg_location()
        archive = os.path.join(self.out_dir, ".download_archive.txt")
        opts = {
            "format": "bestaudio/best",
            "outtmpl": os.path.join(
                self.out_dir,
                "%(playlist_index|)s%(playlist_index& - |)s%(title)s.%(ext)s",
            ),
            "ignoreerrors": True,
            "noplaylist": False,
            # YouTube의 SABR 강제로 기본 클라이언트는 audio 포맷을 못 받는 경우가 많다.
            # android_vr 클라이언트는 PO 토큰 없이 직접 다운로드 URL을 제공한다.
            "extractor_args": {"youtube": {"player_client": ["android_vr"]}},
            # 일시적 403/네트워크 오류 자동 복구
            "retries": 10,
            "fragment_retries": 10,
            "extractor_retries": 3,
            "quiet": True,
            "no_warnings": True,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": self.bitrate,
                }
            ],
            "progress_hooks": [self._hook],
            "logger": _YtLogger(self.log.emit),
        }
        if ffloc:
            opts["ffmpeg_location"] = ffloc
        if self.skip_dupes:
            opts["download_archive"] = archive

        try:
            self.log.emit(f"시작: {self.url}")
            self.log.emit(
                f"저장 위치: {self.out_dir}  |  음질: {self.bitrate}kbps  |  "
                f"중복 방지: {'켜짐' if self.skip_dupes else '꺼짐'}"
            )
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([self.url])
            self.finished.emit(True, "")
        except yt_dlp.utils.DownloadCancelled:
            self.finished.emit(False, "사용자가 취소함")
        except Exception:
            self.finished.emit(False, traceback.format_exc())


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(660, 560)
        self.thread = None
        self.worker = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(8)

        title = QLabel("플레이리스트 / 영상 URL")
        f = QFont()
        f.setBold(True)
        f.setPointSize(14)
        title.setFont(f)
        root.addWidget(title)

        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText(
            "https://www.youtube.com/playlist?list=…  또는  영상 URL"
        )
        root.addWidget(self.url_edit)

        # 저장 폴더
        row = QHBoxLayout()
        row.addWidget(QLabel("저장 폴더"))
        self.dir_edit = QLineEdit(
            os.path.join(os.path.expanduser("~"), "Downloads", "MP3")
        )
        row.addWidget(self.dir_edit, 1)
        browse = QPushButton("찾아보기…")
        browse.clicked.connect(self._choose_dir)
        row.addWidget(browse)
        root.addLayout(row)

        # 옵션
        opt = QHBoxLayout()
        opt.addWidget(QLabel("음질(kbps)"))
        self.bitrate = QComboBox()
        self.bitrate.addItems(["128", "192", "320"])
        self.bitrate.setCurrentText("192")
        opt.addWidget(self.bitrate)
        self.skip_dupes = QCheckBox("이미 받은 곡 건너뛰기 (중복 방지)")
        self.skip_dupes.setChecked(True)
        opt.addWidget(self.skip_dupes)
        opt.addStretch(1)
        root.addLayout(opt)

        # 버튼
        btns = QHBoxLayout()
        self.start_btn = QPushButton("변환 시작")
        self.start_btn.clicked.connect(self._start)
        btns.addWidget(self.start_btn)
        self.cancel_btn = QPushButton("취소")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._cancel)
        btns.addWidget(self.cancel_btn)
        btns.addStretch(1)
        root.addLayout(btns)

        # 진행률
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        root.addWidget(self.bar)
        self.status = QLabel("대기 중")
        self.status.setStyleSheet("color:#666;")
        root.addWidget(self.status)

        # 로그
        root.addWidget(QLabel("진행 로그"))
        self.logbox = QPlainTextEdit()
        self.logbox.setReadOnly(True)
        self.logbox.setStyleSheet(
            "background:#1e1e1e; color:#d4d4d4; font-family:Menlo,monospace; font-size:11px;"
        )
        root.addWidget(self.logbox, 1)

    def _choose_dir(self):
        d = QFileDialog.getExistingDirectory(
            self, "저장 폴더 선택", self.dir_edit.text() or os.path.expanduser("~")
        )
        if d:
            self.dir_edit.setText(d)

    def _append(self, text):
        self.logbox.appendPlainText(text)

    def _start(self):
        url = self.url_edit.text().strip()
        if not url:
            QMessageBox.warning(self, APP_TITLE, "URL을 입력하세요.")
            return
        out = self.dir_edit.text().strip()
        if not out:
            QMessageBox.warning(self, APP_TITLE, "저장 폴더를 선택하세요.")
            return
        try:
            os.makedirs(out, exist_ok=True)
        except OSError as e:
            QMessageBox.critical(self, APP_TITLE, f"폴더를 만들 수 없습니다:\n{e}")
            return

        self.start_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.bar.setValue(0)
        self.status.setText("준비 중…")

        self.thread = QThread()
        self.worker = Worker(url, out, self.bitrate.currentText(),
                             self.skip_dupes.isChecked())
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.log.connect(self._append)
        self.worker.status.connect(self.status.setText)
        self.worker.progress.connect(lambda v: self.bar.setValue(int(v)))
        self.worker.finished.connect(self._on_done)
        self.thread.start()

    def _cancel(self):
        if self.worker:
            self.worker.cancel()
            self.status.setText("취소 중… (현재 항목 마무리 후 중단)")

    def _on_done(self, ok, err):
        self.thread.quit()
        self.thread.wait()
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        if ok:
            self.bar.setValue(100)
            self.status.setText("완료 ✅")
            self._append("── 완료 ──")
            QMessageBox.information(self, APP_TITLE, "변환이 완료되었습니다.")
        elif err == "사용자가 취소함":
            self.status.setText("취소됨")
        else:
            self.status.setText("오류 발생 — 로그를 확인하세요")
            self._append("\n[오류]\n" + err)


def _selftest():
    """프로즌 번들 검증용 헤드리스 모드 (P2M_SELFTEST=1 일 때).

    GUI 없이 번들된 yt-dlp + ffmpeg로 1곡을 mp3로 뽑아보고 결과를 출력한다.
    """
    import tempfile
    out = tempfile.mkdtemp()
    url = os.environ.get(
        "P2M_SELFTEST_URL",
        "https://www.youtube.com/playlist?list=PL5jKmsDk2Q4lTrdiBuDB8vBv_fKAd-T3k",
    )
    print("ffmpeg_location ->", ffmpeg_location())
    w = Worker(url, out, "192", False)
    w.url = url
    # playlist_items=1 만 받도록 옵션을 직접 구성
    ffloc = ffmpeg_location()
    opts = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(out, "%(title)s.%(ext)s"),
        "ignoreerrors": True,
        "playlist_items": "1",
        "extractor_args": {"youtube": {"player_client": ["android_vr"]}},
        "quiet": True, "no_warnings": True,
        "postprocessors": [{"key": "FFmpegExtractAudio",
                            "preferredcodec": "mp3", "preferredquality": "192"}],
    }
    if os.environ.get("P2M_VERBOSE"):
        opts["verbose"] = True
        opts["quiet"] = False
    if ffloc:
        opts["ffmpeg_location"] = ffloc
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])
    files = os.listdir(out)
    mp3 = [f for f in files if f.endswith(".mp3")]
    print("SELFTEST FILES:", files)
    print("SELFTEST RESULT:", "OK" if mp3 else "FAIL")
    sys.exit(0 if mp3 else 2)


def main():
    if os.environ.get("P2M_SELFTEST"):
        _selftest()
        return
    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
