#!/usr/bin/env python3
"""Playlist → MP3 — 독립형 macOS GUI (PySide6/Qt).

YouTube 플레이리스트(또는 단일 영상) URL을 넣으면 각 항목을 MP3로 변환해 저장한다.
yt-dlp와 ffmpeg는 앱에 번들된 바이너리를 사용하므로 별도 설치가 필요 없다.
"""

import ctypes
import os
import re
import subprocess
import sys
import threading
import time
import traceback

from PySide6.QtCore import (
    Qt, QEvent, QObject, QSettings, QThread, QTimer, QUrl, Signal,
)
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QCheckBox, QProgressBar, QPlainTextEdit,
    QFileDialog, QFrame, QMessageBox,
)
from PySide6.QtGui import QDesktopServices, QPalette

import yt_dlp

try:
    # 네이티브 타이틀바 통합(프레임리스 글래스 창)용. 없으면 일반 창으로 동작.
    import objc
    from AppKit import NSWindow  # noqa: F401  (PyInstaller 번들 유도)

    _HAS_COCOA = True
except Exception:
    _HAS_COCOA = False


APP_TITLE = "Playlist → MP3"

YOUTUBE_URL_RE = re.compile(
    r"https?://(?:www\.|m\.|music\.)?(?:youtube\.com|youtu\.be)/\S+"
)


def build_qss(dark):
    """macOS 디자인 언어를 따르는 스타일시트 (라이트/다크 모드별)."""
    if dark:
        c = {
            # 배경 그라디언트 위에 반투명 화이트 레이어를 겹쳐 글래스 질감을 낸다
            "bg": "qlineargradient(x1:0, y1:0, x2:0, y2:1,"
                  " stop:0 #1b1b20, stop:1 #101013)",
            "card": "rgba(255,255,255,7%)",
            "solid": "#2c2c2e", "border": "rgba(255,255,255,13%)",
            "text": "#f2f2f7", "sub": "#9a9aa0",
            "field": "rgba(255,255,255,8%)",
            "accent": "#0a84ff", "accent2": "#64d2ff", "accent_h": "#3395ff",
            "primary": "qlineargradient(x1:0, y1:0, x2:0, y2:1,"
                       " stop:0 #2e96ff, stop:1 #0a84ff)",
            "btn": "rgba(255,255,255,10%)", "btn_h": "rgba(255,255,255,16%)",
            "card_h": "rgba(255,255,255,10%)",
            "log": "rgba(0,0,0,35%)",
        }
    else:
        c = {
            "bg": "qlineargradient(x1:0, y1:0, x2:0, y2:1,"
                  " stop:0 #f4f6fa, stop:1 #e7ebf3)",
            "card": "rgba(255,255,255,58%)",
            "solid": "#ffffff", "border": "rgba(255,255,255,90%)",
            "text": "#1d1d1f", "sub": "#6e6e73",
            "field": "rgba(255,255,255,65%)",
            "accent": "#007aff", "accent2": "#32ade6", "accent_h": "#1a8cff",
            "primary": "qlineargradient(x1:0, y1:0, x2:0, y2:1,"
                       " stop:0 #2f95ff, stop:1 #007aff)",
            "btn": "rgba(255,255,255,70%)", "btn_h": "rgba(255,255,255,95%)",
            "card_h": "rgba(255,255,255,72%)",
            "log": "#17171b",
        }
    return f"""
QWidget#window {{ background: {c["bg"]}; }}
QWidget {{
    color: {c["text"]};
    font-size: 13px;
    font-family: 'Pretendard Variable', 'Pretendard', 'Apple SD Gothic Neo';
}}
QLabel {{ background: transparent; }}
QLabel#title {{ font-size: 24px; font-weight: 700; }}
QLabel#section {{ font-size: 12px; font-weight: 600; color: {c["sub"]}; }}
QLabel#subtle {{ color: {c["sub"]}; font-size: 12px; }}
QFrame#card {{
    background: {c["card"]};
    border: 1px solid {c["border"]};
    border-radius: 18px;
}}
QFrame#card:hover {{ background: {c["card_h"]}; }}
QLineEdit {{
    background: {c["field"]};
    border: 1px solid {c["border"]};
    border-radius: 10px;
    padding: 10px 12px;
    selection-background-color: {c["accent"]};
}}
QLineEdit:focus {{ border: 2px solid {c["accent"]}; padding: 9px 11px; }}
QPushButton {{
    background: {c["btn"]};
    border: 1px solid {c["border"]};
    border-radius: 10px;
    padding: 9px 20px;
    font-weight: 500;
}}
QPushButton:hover {{ background: {c["btn_h"]}; }}
QPushButton:pressed {{ background: {c["btn"]}; }}
QPushButton:disabled {{ color: {c["sub"]}; background: {c["field"]}; }}
QPushButton#primary {{
    background: {c["primary"]};
    border: none;
    color: #ffffff;
    font-weight: 600;
    padding: 10px 22px;
}}
QPushButton#primary:hover {{ background: {c["accent_h"]}; }}
QPushButton#primary:pressed {{ background: {c["accent"]}; }}
QPushButton#primary:disabled {{ background: {c["field"]}; color: {c["sub"]}; }}
QComboBox {{
    background: {c["field"]};
    border: 1px solid {c["border"]};
    border-radius: 10px;
    padding: 8px 12px;
    min-width: 56px;
}}
QComboBox QAbstractItemView {{
    background: {c["solid"]};
    border: 1px solid {c["border"]};
    border-radius: 8px;
    selection-background-color: {c["accent"]};
}}
QCheckBox {{ background: transparent; spacing: 7px; }}
QProgressBar {{
    background: {c["field"]};
    border: none;
    border-radius: 3px;
    min-height: 6px;
    max-height: 6px;
}}
QProgressBar::chunk {{
    border-radius: 3px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {c["accent"]}, stop:1 {c["accent2"]});
}}
QPlainTextEdit {{
    background: {c["log"]};
    color: #d4d4d4;
    border: 1px solid {c["border"]};
    border-radius: 14px;
    padding: 10px;
    font-family: 'Pretendard Variable', 'Pretendard', 'Apple SD Gothic Neo';
    font-size: 11px;
}}
QMessageBox {{ background: {c["bg"]}; }}
"""


def _load_fonts():
    """번들된 Pretendard 폰트를 등록한다 (없으면 시스템 폰트 유지)."""
    from PySide6.QtGui import QFontDatabase

    path = os.path.join(resource_dir(), "fonts", "PretendardVariable.ttf")
    if os.path.exists(path):
        QFontDatabase.addApplicationFont(path)


def resource_dir():
    """번들된 리소스(폰트 등)가 있는 디렉터리.

    - PyInstaller 번들: sys._MEIPASS
    - pip/uv 설치: 이 모듈이 위치한 패키지 디렉터리(fonts/ 포함)
    """
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return base
    return os.path.dirname(os.path.abspath(__file__))


_FFMPEG_DIR = None
_FFMPEG_RESOLVED = False


def ffmpeg_location(log=None):
    """ffmpeg/ffprobe가 들어있는 디렉터리. 시스템 PATH로 충분하면 None.

    PyInstaller 번들이면 함께 담긴 바이너리를 우선 사용하고, 그 외에는
    크로스 OS 리졸버(ffmpeg_setup)로 PATH 확인 → 없으면 자동 설치한다.
    결과는 프로세스 내 1회만 계산해 캐시한다.
    """
    global _FFMPEG_DIR, _FFMPEG_RESOLVED

    # PyInstaller 번들에 동봉된 ffmpeg 우선
    meipass = getattr(sys, "_MEIPASS", None)
    _ff = "ffmpeg" + (".exe" if sys.platform == "win32" else "")
    if meipass and os.path.exists(os.path.join(meipass, _ff)):
        return meipass

    if _FFMPEG_RESOLVED:
        return _FFMPEG_DIR

    from .ffmpeg_setup import ensure_ffmpeg

    _FFMPEG_DIR = ensure_ffmpeg(log=log)
    _FFMPEG_RESOLVED = True
    return _FFMPEG_DIR


class _YtLogger:
    """yt-dlp 메시지를 워커 시그널로 흘려보낸다."""

    def __init__(self, emit):
        self.emit = emit

    def debug(self, msg):
        if not msg or msg.startswith("[debug]"):
            return
        # 진행률 스팸([download]  x.x% …)은 로그창에 넣지 않는다.
        # 청크마다 한 줄씩 초당 수백 건이 쌓여 리페인트 폭주 → 크래시 원인.
        # 퍼센트는 상태줄/프로그레스바가 대신 표시한다.
        if msg.startswith("[download]") and "%" in msg:
            return
        self.emit(msg)

    def info(self, msg):
        if msg:
            self.emit(msg)

    def warning(self, msg):
        if msg:
            self.emit("⚠ " + msg)

    def error(self, msg):
        if not msg:
            return
        # yt-dlp가 개발자용 지원중단 예고를 error 채널로 흘린다. 사용자에겐 노이즈.
        if "Deprecated Feature" in msg:
            return
        self.emit("✖ " + msg)


class Worker(QObject):
    log = Signal(str)
    status = Signal(str)
    progress = Signal(float)
    item_progress = Signal(int, int)  # (현재 곡 번호, 전체 곡 수)
    finished = Signal(bool, str, dict)  # (성공?, 오류텍스트, 결과 요약)

    def __init__(self, url, out_dir, bitrate, skip_dupes):
        super().__init__()
        self.url = url
        self.out_dir = out_dir
        self.bitrate = bitrate
        self.skip_dupes = skip_dupes
        self._cancel = False
        self._last_ui_emit = 0.0
        self._completed = set()
        self._n_total = 0
        self.n_skipped = 0
        self.n_failed = 0

    def cancel(self):
        self._cancel = True

    def _summary(self):
        done = len(self._completed)
        if self._n_total:
            # 오류 로그 줄 수로 세면 재시도 후 성공한 곡도 실패로 집계된다.
            # 전체 곡 수를 아는 경우 산술로 계산하는 것이 정확하다.
            failed = max(0, self._n_total - done - self.n_skipped)
        else:
            failed = self.n_failed
        return {
            "done": done,
            "skipped": self.n_skipped,
            "failed": failed,
            "total": self._n_total,
        }

    def _item_info(self, d):
        info = d.get("info_dict") or {}
        idx = info.get("playlist_index") or 1
        total = info.get("n_entries") or 1
        self._n_total = max(self._n_total, total)
        return idx, total

    def _hook(self, d):
        if self._cancel:
            raise yt_dlp.utils.DownloadCancelled()
        st = d.get("status")
        if st == "downloading":
            # UI 갱신 스로틀: 청크마다(초당 수백 회) 시그널을 쏘면 메인 스레드
            # 이벤트 큐가 폭주해 Qt 리페인트 중 세그폴트가 난다. 최대 10회/초로 제한.
            now = time.monotonic()
            if now - self._last_ui_emit < 0.1:
                return
            self._last_ui_emit = now
            idx, total = self._item_info(d)
            total_b = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            done = d.get("downloaded_bytes") or 0
            pct = (done / total_b * 100) if total_b else 0
            self.item_progress.emit(idx, total)
            self.progress.emit(pct)
            title = d.get("info_dict", {}).get("title", "")
            self.status.emit(f"다운로드 중 ({idx}/{total}): {title}  {pct:4.1f}%")
        elif st == "finished":
            idx, total = self._item_info(d)
            self._completed.add(idx)
            self.item_progress.emit(idx, total)
            self.status.emit(f"MP3 변환 중… ({idx}/{total})")
            self.progress.emit(100.0)

    def _log_sniff(self, msg):
        """로그를 UI로 흘리면서 건너뜀/실패 건수를 집계한다."""
        if "already been recorded in the archive" in msg:
            self.n_skipped += 1
        elif msg.startswith("✖ ERROR"):
            self.n_failed += 1
        self.log.emit(msg)

    def run(self):
        ffloc = ffmpeg_location(log=self.log.emit)
        archive = os.path.join(self.out_dir, ".download_archive.txt")
        opts = {
            "format": "bestaudio/best",
            "outtmpl": {
                "default": os.path.join(
                    self.out_dir,
                    "%(artist,creator,uploader)s - %(title)s.%(ext)s",
                ),
                # 플레이리스트 자체 썸네일은 저장하지 않는다(오디오가 없어
                # EmbedThumbnail 정리 단계가 안 돌아 잔여 jpg가 남기 때문).
                "pl_thumbnail": "",
            },
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
            # 앨범 이미지(썸네일)를 임시로 받아 MP3에 심기 위해 필요
            "writethumbnail": True,
            "postprocessors": [
                # 1) 오디오를 MP3로 추출
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": self.bitrate,
                },
                # 2) artist/title/album 등 메타데이터를 태그로 기록
                {
                    "key": "FFmpegMetadata",
                    "add_metadata": True,
                },
                # 3) 썸네일을 jpg로 변환 (webp는 mp3에 임베드 불가·잔여 파일 방지)
                {
                    "key": "FFmpegThumbnailsConvertor",
                    "format": "jpg",
                },
                # 4) 썸네일을 앨범 아트로 임베드 (임베드 후 임시 이미지 정리)
                {
                    "key": "EmbedThumbnail",
                    "already_have_thumbnail": False,
                },
            ],
            "progress_hooks": [self._hook],
            "logger": _YtLogger(self._log_sniff),
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
            self.finished.emit(True, "", self._summary())
        except yt_dlp.utils.DownloadCancelled:
            self.finished.emit(False, "사용자가 취소함", self._summary())
        except Exception:
            self.finished.emit(False, traceback.format_exc(), self._summary())


class _PreviewBridge(QObject):
    """미리보기 백그라운드 스레드 → 메인 스레드 전달용.

    바운드 메서드 슬롯에만 연결할 것(람다는 발신 스레드에서 직접 실행됨).
    """

    ready = Signal(int, str, int)  # (요청 세대, 제목, 곡 수)
    failed = Signal(int)


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(720, 760)
        self.setAcceptDrops(True)
        self.thread = None
        self.worker = None
        self.settings = QSettings("upfall", "playlist-to-mp3")
        self._cur_idx = 0
        self._cur_total = 0
        self._last_clip_fill = ""
        self._preview_gen = 0
        self._preview_bridge = _PreviewBridge()
        self._preview_bridge.ready.connect(self._on_preview_ready)
        self._preview_bridge.failed.connect(self._on_preview_failed)
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(800)
        self._preview_timer.timeout.connect(self._request_preview)
        self._style_dark = None
        self._titlebar_done = False
        self._build_ui()
        self._apply_style()
        self._maybe_fill_from_clipboard()

    def showEvent(self, e):
        super().showEvent(e)
        self._integrate_titlebar()

    def _integrate_titlebar(self):
        """타이틀바를 투명하게 만들고 콘텐츠를 창 최상단까지 확장한다.

        신호등 버튼은 네이티브로 유지되고, 글래스 배경이 타이틀바 영역까지
        이어져 프레임리스 글래스 창처럼 보인다. pyobjc가 없으면 일반 창 유지.
        """
        if not _HAS_COCOA or self._titlebar_done:
            return
        try:
            view = objc.objc_object(c_void_p=ctypes.c_void_p(int(self.winId())))
            win = view.window()
            if win is None:
                return
            win.setTitlebarAppearsTransparent_(True)
            win.setTitleVisibility_(1)  # NSWindowTitleHidden
            # NSWindowStyleMaskFullSizeContentView = 1 << 15
            win.setStyleMask_(win.styleMask() | (1 << 15))
            win.setMovableByWindowBackground_(True)
            self._titlebar_done = True
        except Exception:
            pass

    def mousePressEvent(self, e):
        # 타이틀바가 투명해진 상단 영역을 잡고 창을 이동할 수 있게 한다
        if (
            self._titlebar_done
            and e.button() == Qt.MouseButton.LeftButton
            and e.position().y() < 44
        ):
            handle = self.windowHandle()
            if handle is not None:
                handle.startSystemMove()
                e.accept()
                return
        super().mousePressEvent(e)

    def _apply_style(self):
        """시스템 라이트/다크 모드에 맞는 스타일 적용 (변화 있을 때만)."""
        dark = self.palette().color(QPalette.ColorRole.Window).lightness() < 128
        if self._style_dark == dark:
            return
        self._style_dark = dark
        self.setStyleSheet(build_qss(dark))

    def _build_ui(self):
        self.setObjectName("window")
        root = QVBoxLayout(self)
        # 타이틀바 통합 시 신호등 버튼 아래로 콘텐츠가 시작되도록 상단 여백 확보
        root.setContentsMargins(28, 48 if _HAS_COCOA else 28, 28, 28)
        root.setSpacing(16)

        # 헤더
        title = QLabel(APP_TITLE)
        title.setObjectName("title")
        root.addWidget(title)
        subtitle = QLabel("YouTube 재생목록·영상을 MP3로 변환해 저장합니다")
        subtitle.setObjectName("subtle")
        root.addWidget(subtitle)

        # ── 카드 1: URL + 미리보기 ──
        url_card = QFrame()
        url_card.setObjectName("card")
        uc = QVBoxLayout(url_card)
        uc.setContentsMargins(20, 20, 20, 20)
        uc.setSpacing(10)
        url_label = QLabel("플레이리스트 / 영상 URL")
        url_label.setObjectName("section")
        uc.addWidget(url_label)
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText(
            "https://www.youtube.com/playlist?list=…  또는  영상 URL"
        )
        self.url_edit.returnPressed.connect(self._start)
        self.url_edit.textChanged.connect(self._on_url_changed)
        uc.addWidget(self.url_edit)
        self.preview = QLabel("")
        self.preview.setObjectName("subtle")
        uc.addWidget(self.preview)
        root.addWidget(url_card)

        # ── 카드 2: 저장 폴더 + 옵션 ──
        opt_card = QFrame()
        opt_card.setObjectName("card")
        oc = QVBoxLayout(opt_card)
        oc.setContentsMargins(20, 20, 20, 20)
        oc.setSpacing(12)

        row = QHBoxLayout()
        dir_label = QLabel("저장 폴더")
        dir_label.setObjectName("section")
        row.addWidget(dir_label)
        default_dir = os.path.join(os.path.expanduser("~"), "Downloads", "MP3")
        self.dir_edit = QLineEdit(
            str(self.settings.value("out_dir", default_dir))
        )
        row.addWidget(self.dir_edit, 1)
        browse = QPushButton("찾아보기…")
        browse.clicked.connect(self._choose_dir)
        row.addWidget(browse)
        open_btn = QPushButton("폴더 열기")
        open_btn.clicked.connect(self._open_dir)
        row.addWidget(open_btn)
        oc.addLayout(row)

        opt = QHBoxLayout()
        q_label = QLabel("음질(kbps)")
        q_label.setObjectName("section")
        opt.addWidget(q_label)
        self.bitrate = QComboBox()
        self.bitrate.addItems(["128", "192", "320"])
        self.bitrate.setCurrentText(str(self.settings.value("bitrate", "192")))
        opt.addWidget(self.bitrate)
        self.skip_dupes = QCheckBox("이미 받은 곡 건너뛰기 (중복 방지)")
        self.skip_dupes.setChecked(
            self.settings.value("skip_dupes", True, type=bool)
        )
        opt.addWidget(self.skip_dupes)
        opt.addStretch(1)
        oc.addLayout(opt)
        root.addWidget(opt_card)

        # ── 카드 3: 진행률 (전체 n/m곡 + 현재 곡) ──
        prog_card = QFrame()
        prog_card.setObjectName("card")
        pc = QVBoxLayout(prog_card)
        pc.setContentsMargins(20, 20, 20, 20)
        pc.setSpacing(12)

        total_row = QHBoxLayout()
        self.total_label = QLabel("전체 0/0곡")
        self.total_label.setObjectName("section")
        self.total_label.setFixedWidth(84)
        total_row.addWidget(self.total_label)
        self.total_bar = QProgressBar()
        self.total_bar.setRange(0, 100)
        self.total_bar.setTextVisible(False)
        total_row.addWidget(self.total_bar, 1)
        pc.addLayout(total_row)

        cur_row = QHBoxLayout()
        cur_label = QLabel("현재 곡")
        cur_label.setObjectName("section")
        cur_label.setFixedWidth(84)
        cur_row.addWidget(cur_label)
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setTextVisible(False)
        cur_row.addWidget(self.bar, 1)
        pc.addLayout(cur_row)

        self.status = QLabel("대기 중")
        self.status.setObjectName("subtle")
        pc.addWidget(self.status)
        root.addWidget(prog_card)

        # ── 실행 버튼 (macOS 관례: 주 동작이 오른쪽 끝) ──
        btns = QHBoxLayout()
        btns.addStretch(1)
        self.cancel_btn = QPushButton("취소")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._cancel)
        btns.addWidget(self.cancel_btn)
        self.start_btn = QPushButton("변환 시작")
        self.start_btn.setObjectName("primary")
        self.start_btn.clicked.connect(self._start)
        btns.addWidget(self.start_btn)
        root.addLayout(btns)

        # ── 로그 ──
        log_label = QLabel("진행 로그")
        log_label.setObjectName("section")
        root.addWidget(log_label)
        self.logbox = QPlainTextEdit()
        self.logbox.setReadOnly(True)
        # 로그 문서가 무한히 커지면 레이아웃·리페인트 비용이 누적된다. 상한 고정.
        self.logbox.setMaximumBlockCount(2000)
        root.addWidget(self.logbox, 1)

    def _choose_dir(self):
        d = QFileDialog.getExistingDirectory(
            self, "저장 폴더 선택", self.dir_edit.text() or os.path.expanduser("~")
        )
        if d:
            self.dir_edit.setText(d)

    def _open_dir(self):
        d = self.dir_edit.text().strip()
        if d and os.path.isdir(d):
            QDesktopServices.openUrl(QUrl.fromLocalFile(d))
        else:
            QMessageBox.information(self, APP_TITLE, "폴더가 아직 없습니다.")

    def _append(self, text):
        self.logbox.appendPlainText(text)

    # ── 클립보드 자동 인식 ──────────────────────────────────────────
    def _maybe_fill_from_clipboard(self):
        """URL 칸이 비어 있으면 클립보드의 YouTube URL을 자동으로 채운다."""
        current = self.url_edit.text().strip()
        if current and current != self._last_clip_fill:
            return  # 사용자가 직접 입력한 값은 덮어쓰지 않는다
        m = YOUTUBE_URL_RE.search(QApplication.clipboard().text() or "")
        if m and m.group(0) != self._last_clip_fill:
            self._last_clip_fill = m.group(0)
            self.url_edit.setText(m.group(0))
            self._append(f"클립보드에서 URL을 가져왔습니다: {m.group(0)}")

    def changeEvent(self, e):
        if e.type() == QEvent.Type.ActivationChange and self.isActiveWindow():
            self._maybe_fill_from_clipboard()
        elif e.type() == QEvent.Type.PaletteChange:
            # 팔레트 변경 이벤트 처리 도중 setStyleSheet 재진입을 피하려고 지연 호출
            QTimer.singleShot(0, self._apply_style)
        super().changeEvent(e)

    # ── 드래그앤드롭 ────────────────────────────────────────────────
    def dragEnterEvent(self, e):
        md = e.mimeData()
        text = md.urls()[0].toString() if md.hasUrls() else md.text()
        if text and YOUTUBE_URL_RE.search(text):
            e.acceptProposedAction()

    def dropEvent(self, e):
        md = e.mimeData()
        text = md.urls()[0].toString() if md.hasUrls() else md.text()
        m = YOUTUBE_URL_RE.search(text or "")
        if m:
            self.url_edit.setText(m.group(0))

    # ── URL 미리보기 ────────────────────────────────────────────────
    def _on_url_changed(self, _text):
        self.preview.setText("")
        self._preview_timer.start()

    def _request_preview(self):
        url = self.url_edit.text().strip()
        if not YOUTUBE_URL_RE.search(url):
            self.preview.setText("")
            return
        self._preview_gen += 1
        self.preview.setText("재생목록 확인 중…")
        threading.Thread(
            target=self._preview_fetch,
            args=(self._preview_gen, url),
            daemon=True,
        ).start()

    def _preview_fetch(self, gen, url):
        """백그라운드에서 제목·곡 수만 가볍게 조회 (flat extraction)."""
        try:
            opts = {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "extract_flat": "in_playlist",
                "extractor_args": {"youtube": {"player_client": ["android_vr"]}},
            }
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
            entries = info.get("entries")
            count = len(list(entries)) if entries is not None else 1
            title = info.get("title") or "(제목 없음)"
            self._preview_bridge.ready.emit(gen, title, count)
        except Exception:
            self._preview_bridge.failed.emit(gen)

    def _on_preview_ready(self, gen, title, count):
        if gen != self._preview_gen:
            return  # 이미 다른 URL로 바뀐 이전 요청의 응답
        self.preview.setText(f"✔ {title} · {count}곡")

    def _on_preview_failed(self, gen):
        if gen != self._preview_gen:
            return
        self.preview.setText("✖ 재생목록/영상을 찾지 못했습니다. URL을 확인하세요.")

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

        # 다음 실행을 위해 현재 설정을 기억
        self.settings.setValue("out_dir", out)
        self.settings.setValue("bitrate", self.bitrate.currentText())
        self.settings.setValue("skip_dupes", self.skip_dupes.isChecked())

        self.start_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.bar.setValue(0)
        self.total_bar.setValue(0)
        self.total_label.setText("전체 0/0곡")
        self._cur_idx = 0
        self._cur_total = 0
        self.status.setText("준비 중…")

        self.thread = QThread()
        self.worker = Worker(url, out, self.bitrate.currentText(),
                             self.skip_dupes.isChecked())
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.log.connect(self._append)
        self.worker.status.connect(self.status.setText)
        # 주의: 람다로 연결하면 PySide6가 큐잉 없이 워커 스레드에서 직접 실행해
        # QProgressBar 리페인트가 워커 스레드에서 일어나 세그폴트가 난다.
        # 반드시 QObject(MainWindow) 바운드 메서드로 연결해 메인 스레드로 큐잉시킬 것.
        self.worker.progress.connect(self._on_progress)
        self.worker.item_progress.connect(self._on_item_progress)
        self.worker.finished.connect(self._on_done)
        self.thread.start()

    def _on_progress(self, v):
        self.bar.setValue(int(v))
        if self._cur_total > 0:
            overall = ((self._cur_idx - 1) * 100 + v) / self._cur_total
            self.total_bar.setValue(int(overall))

    def _on_item_progress(self, idx, total):
        self._cur_idx = idx
        self._cur_total = total
        self.total_label.setText(f"전체 {idx}/{total}곡")

    def _cancel(self):
        if self.worker:
            self.worker.cancel()
            self.status.setText("취소 중… (현재 항목 마무리 후 중단)")

    def _on_done(self, ok, err, summary):
        self.thread.quit()
        self.thread.wait()
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        done = summary.get("done", 0)
        skipped = summary.get("skipped", 0)
        failed = summary.get("failed", 0)
        result_line = f"성공 {done}곡 · 건너뜀 {skipped}곡 · 실패 {failed}곡"
        if ok:
            self.bar.setValue(100)
            self.total_bar.setValue(100)
            self.status.setText(f"완료 ✅  {result_line}")
            self._append(f"── 완료: {result_line} ──")
            msg = f"변환이 완료되었습니다.\n{result_line}"
            if done == 0 and skipped > 0:
                msg += (
                    "\n\n모든 곡이 이전에 받은 기록이 있어 건너뛰었습니다."
                    "\n다시 받으려면 '이미 받은 곡 건너뛰기'를 끄고 실행하세요."
                )
            if failed > 0:
                msg += "\n\n실패한 곡은 진행 로그에서 ✖ 표시를 확인하세요."
            box = QMessageBox(self)
            box.setWindowTitle(APP_TITLE)
            box.setText(msg)
            open_btn = box.addButton("폴더 열기", QMessageBox.ActionRole)
            box.addButton("닫기", QMessageBox.AcceptRole)
            self._notify(APP_TITLE, f"변환 완료: {result_line}")
            box.exec()
            if box.clickedButton() is open_btn:
                self._open_dir()
        elif err == "사용자가 취소함":
            self.status.setText(f"취소됨  ({result_line})")
        else:
            self.status.setText("오류 발생: 로그를 확인하세요")
            self._append("\n[오류]\n" + err)

    def _notify(self, title, message):
        """macOS 알림 센터로 완료를 알린다 (실패해도 앱 흐름에 영향 없음)."""
        try:
            safe_t = title.replace('"', "'")
            safe_m = message.replace('"', "'")
            subprocess.run(
                [
                    "/usr/bin/osascript", "-e",
                    f'display notification "{safe_m}" with title "{safe_t}"',
                ],
                check=False, capture_output=True, timeout=5,
            )
        except Exception:
            pass

    def closeEvent(self, e):
        self.settings.setValue("out_dir", self.dir_edit.text().strip())
        self.settings.setValue("bitrate", self.bitrate.currentText())
        self.settings.setValue("skip_dupes", self.skip_dupes.isChecked())
        super().closeEvent(e)


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
    _load_fonts()
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
