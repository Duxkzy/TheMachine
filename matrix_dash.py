"""
Matrix-mode dashboard widgets.

Used only when the "matrix" theme is active. Everything here reads real
data — psutil for system/process/network stats, the app launcher for the
quick actions. Nothing is faked.

ui.py imports this lazily and swaps these in place of the normal HUD and
side panels.
"""
from __future__ import annotations

import os
import platform
import random
import socket
import subprocess
import threading
import time
from pathlib import Path

import psutil
from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QSizePolicy, QVBoxLayout, QWidget,
)

# katakana + digits, the classic mix
RAIN_CHARS = "ｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜﾝ0123456789"

# ── app_launcher loader ─────────────────────────────────────────────────
# This module gets loaded by path (not as a normal import), so a plain
# `import app_launcher` inside it can't see the project folder. Load it by
# path from right next to this file instead, and cache the result so a
# failure doesn't get retried — and re-logged — on every single click.
_AL_MOD = None
_AL_TRIED = False


def _load_app_launcher():
    global _AL_MOD, _AL_TRIED
    if _AL_TRIED:
        return _AL_MOD
    _AL_TRIED = True
    try:
        import app_launcher as _al          # works if it's already imported
        _AL_MOD = _al
        return _AL_MOD
    except ImportError:
        pass
    path = Path(__file__).resolve().parent / "app_launcher.py"
    if not path.exists():
        return None
    try:
        import importlib.util
        import sys as _sys
        spec = importlib.util.spec_from_file_location("app_launcher", path)
        mod = importlib.util.module_from_spec(spec)
        _sys.modules["app_launcher"] = mod
        spec.loader.exec_module(mod)
        _AL_MOD = mod
    except Exception as e:
        print(f"[Matrix] app_launcher failed to load: {e}")
    return _AL_MOD


# ── shared helpers ──────────────────────────────────────────────────────

def _panel_frame(widget: QWidget, C, title: str) -> QVBoxLayout:
    """Gives a widget the bordered box + header look, returns the layout
    you should add content into."""
    widget.setObjectName("MxPanel")
    widget.setStyleSheet(f"""
        QWidget#MxPanel {{
            background: {C.PANEL};
            border: 1px solid {C.BORDER_B};
            border-radius: 4px;
        }}
    """)
    outer = QVBoxLayout(widget)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(0)

    hdr = QLabel(f"  {title}")
    hdr.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
    hdr.setFixedHeight(26)
    hdr.setStyleSheet(
        f"color: {C.PRI}; background: transparent; "
        f"border-bottom: 1px solid {C.BORDER}; letter-spacing: 1px;"
    )
    outer.addWidget(hdr)

    inner = QVBoxLayout()
    inner.setContentsMargins(12, 8, 12, 10)
    inner.setSpacing(4)
    outer.addLayout(inner)
    return inner


def _row(C, label: str, value: str, label_w: int = 76) -> QWidget:
    w = QWidget()
    w.setStyleSheet("background: transparent;")
    h = QHBoxLayout(w)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(6)
    l = QLabel(label)
    l.setFont(QFont("Courier New", 9))
    l.setFixedWidth(label_w)
    l.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
    v = QLabel(value)
    v.setFont(QFont("Courier New", 9))
    v.setStyleSheet(f"color: {C.TEXT}; background: transparent;")
    v.setWordWrap(False)
    h.addWidget(l)
    h.addWidget(v, stretch=1)
    w._value_label = v          # so callers can update it later
    return w


# ── matrix rain + prompt (centre) ───────────────────────────────────────

class MatrixRain(QWidget):
    """Falling-character background with the title and prompt on top."""

    submitted = pyqtSignal(str)

    def __init__(self, C, parent=None):
        super().__init__(parent)
        self.C = C
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setMinimumHeight(240)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.state = "ONLINE"
        self._cols: list[dict] = []
        self._cell_w = 14
        self._cell_h = 16
        self._tick = 0

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addStretch()

        self._input = QLineEdit()
        self._input.setFont(QFont("Courier New", 12))
        self._input.setFixedHeight(42)
        self._input.setPlaceholderText("")
        self._input.setStyleSheet(f"""
            QLineEdit {{
                background: rgba(0, 0, 0, 170);
                color: {C.WHITE};
                border: 1px solid {C.BORDER_B};
                border-radius: 3px;
                padding: 4px 12px;
            }}
            QLineEdit:focus {{ border: 1px solid {C.PRI}; }}
        """)
        self._input.returnPressed.connect(self._submit)

        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(self._input, stretch=3)
        row.addStretch(1)
        lay.addLayout(row)
        lay.addSpacing(28)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._step)
        self._timer.start(60)      # rain is slower than 60fps on purpose

    def _submit(self):
        txt = self._input.text().strip()
        if txt:
            self._input.clear()
            self.submitted.emit(txt)

    def _rebuild_columns(self):
        n = max(1, self.width() // self._cell_w)
        self._cols = [
            {
                "y": random.uniform(-40, 0),
                "speed": random.uniform(0.4, 1.6),
                "len": random.randint(6, 22),
                "chars": [random.choice(RAIN_CHARS) for _ in range(30)],
            }
            for _ in range(n)
        ]

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._rebuild_columns()

    def _step(self):
        self._tick += 1
        if not self._cols:
            self._rebuild_columns()
        rows = max(1, self.height() // self._cell_h)
        for c in self._cols:
            c["y"] += c["speed"]
            if c["y"] - c["len"] > rows:
                c["y"] = random.uniform(-30, -2)
                c["speed"] = random.uniform(0.4, 1.6)
                c["len"] = random.randint(6, 22)
            if self._tick % 3 == 0:      # churn a character now and then
                i = random.randrange(len(c["chars"]))
                c["chars"][i] = random.choice(RAIN_CHARS)
        self.update()

    def paintEvent(self, _):
        C = self.C
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(C.BG))
        W, H = self.width(), self.height()

        f = QFont("Courier New", 11)
        p.setFont(f)
        head_col = QColor(C.WHITE)
        body_rgb = QColor(C.PRI)

        for ci, c in enumerate(self._cols):
            x = ci * self._cell_w + 2
            head = int(c["y"])
            for k in range(c["len"]):
                ry = head - k
                if ry < 0 or ry * self._cell_h > H:
                    continue
                ch = c["chars"][(ry + ci) % len(c["chars"])]
                if k == 0:
                    p.setPen(QPen(head_col, 1))
                else:
                    fade = 1.0 - (k / c["len"])
                    col = QColor(body_rgb)
                    col.setAlpha(max(12, int(210 * fade * fade)))
                    p.setPen(QPen(col, 1))
                p.drawText(x, ry * self._cell_h + self._cell_h, ch)

        # dark vignette behind the text block so it stays readable
        cy = H * 0.40
        p.fillRect(QRectF(0, cy - 90, W, 200), QColor(0, 0, 0, 165))

        # Scale the title to whatever width we actually have — at a fixed
        # size it gets clipped to "E MACHIN" the moment the window shrinks.
        title_px = max(15, min(40, int(W / 12.5)))
        p.setPen(QPen(QColor(C.PRI), 1))
        title_f = QFont("Courier New", title_px, QFont.Weight.Bold)
        title_f.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 118)
        p.setFont(title_f)
        p.drawText(QRectF(0, cy - 78, W, 56), Qt.AlignmentFlag.AlignCenter,
                   "THE MACHINE")

        sub_px = max(9, min(15, int(W / 34)))
        p.setFont(QFont("Noto Sans CJK JP", sub_px))
        p.setPen(QPen(QColor(C.GREEN_D), 1))
        p.drawText(QRectF(0, cy - 16, W, 26), Qt.AlignmentFlag.AlignCenter,
                   "システム　オンライン")

        p.setFont(QFont("Courier New", max(9, min(13, int(W / 40)))))
        p.setPen(QPen(QColor(C.TEXT), 1))
        p.drawText(QRectF(0, cy + 16, W, 24), Qt.AlignmentFlag.AlignCenter,
                   "How can I help you?")

        # the ">" marker sitting in front of the input box
        ir = self._input.geometry()
        p.setFont(QFont("Courier New", 12, QFont.Weight.Bold))
        p.setPen(QPen(QColor(C.PRI), 1))
        p.drawText(QRectF(ir.x() + 8, ir.y(), 20, ir.height()),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, ">")


# ── system status (left) ────────────────────────────────────────────────

class StatusBar(QWidget):
    """One labelled bar: name on the left, filled track, percent on right."""

    def __init__(self, C, label: str, parent=None):
        super().__init__(parent)
        self.C = C
        self._label = label
        self._detail = ""
        self._pct = 0.0
        self.setFixedHeight(42)
        self.setStyleSheet("background: transparent;")

    def set_state(self, detail: str, pct: float):
        self._detail = detail
        self._pct = max(0.0, min(100.0, pct))
        self.update()

    def paintEvent(self, _):
        C = self.C
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()

        f = QFont("Courier New", 9)
        p.setFont(f)
        p.setPen(QPen(QColor(C.TEXT_DIM), 1))
        p.drawText(QRectF(0, 0, 46, 18), Qt.AlignmentFlag.AlignLeft
                   | Qt.AlignmentFlag.AlignVCenter, self._label + ":")

        # elide instead of clipping — a half-cut CPU model looks broken
        from PyQt6.QtGui import QFontMetrics
        avail = max(20, W - 50)
        detail = QFontMetrics(f).elidedText(
            self._detail, Qt.TextElideMode.ElideRight, int(avail)
        )
        p.setPen(QPen(QColor(C.TEXT), 1))
        p.drawText(QRectF(46, 0, avail, 18), Qt.AlignmentFlag.AlignLeft
                   | Qt.AlignmentFlag.AlignVCenter, detail)

        track_w = max(10, W - 52)
        p.setBrush(QBrush(QColor(C.BAR_BG)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRect(QRectF(0, 26, track_w, 6))

        col = QColor(C.RED if self._pct > 85 else (C.ACC if self._pct > 65 else C.PRI))
        p.setBrush(QBrush(col))
        p.drawRect(QRectF(0, 26, track_w * self._pct / 100.0, 6))

        p.setFont(f)
        p.setPen(QPen(QColor(C.TEXT), 1))
        p.drawText(QRectF(W - 46, 22, 46, 14),
                   Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                   f"{self._pct:.0f}%")


class SystemStatusPanel(QWidget):
    def __init__(self, C, metrics_fn, parent=None):
        super().__init__(parent)
        self.C = C
        self._metrics_fn = metrics_fn      # () -> dict from ui._metrics
        inner = _panel_frame(self, C, "SYSTEM STATUS")

        info = _static_system_info()
        self._rows = {}
        for key, label in (("os", "OS:"), ("kernel", "Kernel:"),
                           ("uptime", "Uptime:"), ("shell", "Shell:"),
                           ("wm", "WM:")):
            r = _row(C, label, info.get(key, "—"))
            self._rows[key] = r
            inner.addWidget(r)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER}; margin: 6px 0;")
        inner.addWidget(sep)

        self._cpu_bar  = StatusBar(C, "CPU")
        self._ram_bar  = StatusBar(C, "RAM")
        self._gpu_bar  = StatusBar(C, "GPU")
        self._disk_bar = StatusBar(C, "DISK")
        for b in (self._cpu_bar, self._ram_bar, self._gpu_bar, self._disk_bar):
            inner.addWidget(b)
        inner.addStretch()

        self._cpu_name = info.get("cpu_name", "CPU")
        self._gpu_name = info.get("gpu_name", "GPU")

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(1500)
        self.refresh()

    def refresh(self):
        snap = self._metrics_fn()

        up = time.time() - psutil.boot_time()
        h, rem = divmod(int(up), 3600)
        m, s = divmod(rem, 60)
        self._rows["uptime"]._value_label.setText(f"{h}h {m}m {s}s")

        self._cpu_bar.set_state(self._cpu_name, snap.get("cpu", 0.0))

        vm = psutil.virtual_memory()
        self._ram_bar.set_state(
            f"{vm.used / 2**30:.1f} GiB / {vm.total / 2**30:.1f} GiB", vm.percent
        )

        gpu = snap.get("gpu", -1.0)
        self._gpu_bar.set_state(self._gpu_name, gpu if gpu >= 0 else 0.0)

        try:
            du = psutil.disk_usage("/" if os.name != "nt" else "C:\\")
            self._disk_bar.set_state(
                f"{du.used / 2**30:.1f} GiB / {du.total / 2**30:.1f} GiB", du.percent
            )
        except Exception:
            self._disk_bar.set_state("—", 0.0)


def _static_system_info() -> dict:
    """Read once at startup — none of this changes while running."""
    info = {}
    try:
        if platform.system() == "Linux":
            pretty = ""
            osr = Path("/etc/os-release")
            if osr.exists():
                for line in osr.read_text(encoding="utf-8").splitlines():
                    if line.startswith("PRETTY_NAME="):
                        pretty = line.split("=", 1)[1].strip().strip('"')
                        break
            de = os.environ.get("XDG_CURRENT_DESKTOP", "")
            info["os"] = f"{pretty or 'Linux'}" + (f" ({de})" if de else "")
            session = os.environ.get("XDG_SESSION_TYPE", "")
            info["wm"] = f"{de or 'unknown'}" + (f" ({session})" if session else "")
        elif platform.system() == "Darwin":
            info["os"] = f"macOS {platform.mac_ver()[0]}"
            info["wm"] = "Quartz"
        else:
            info["os"] = f"{platform.system()} {platform.release()}"
            info["wm"] = "DWM"
    except Exception:
        info["os"] = platform.system()
        info["wm"] = "—"

    info["kernel"] = platform.release()
    info["shell"] = Path(os.environ.get("SHELL", "")).name or os.environ.get(
        "COMSPEC", "—"
    ).split("\\")[-1]

    # CPU model name
    cpu = platform.processor() or ""
    try:
        if platform.system() == "Linux":
            for line in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
                if line.startswith("model name"):
                    cpu = line.split(":", 1)[1].strip()
                    break
    except Exception:
        pass
    info["cpu_name"] = cpu or "CPU"

    # GPU model name — best effort, no subprocess on Windows
    gpu = ""
    try:
        if platform.system() == "Linux":
            out = subprocess.run(["lspci"], capture_output=True, text=True, timeout=2)
            for line in out.stdout.splitlines():
                if "VGA compatible controller" in line or "3D controller" in line:
                    gpu = line.split(":", 2)[-1].strip()
                    break
    except Exception:
        pass
    info["gpu_name"] = gpu or "GPU"
    info["uptime"] = "—"
    return info


# ── network (left) ──────────────────────────────────────────────────────

class NetworkPanel(QWidget):
    def __init__(self, C, metrics_fn, parent=None):
        super().__init__(parent)
        self.C = C
        self._metrics_fn = metrics_fn
        self._history: list[float] = [0.0] * 60

        inner = _panel_frame(self, C, "NETWORK")
        self._local = _row(C, "Local IP:", "—")
        self._down  = _row(C, "Download:", "—")
        self._up    = _row(C, "Upload:", "—")
        for r in (self._local, self._down, self._up):
            inner.addWidget(r)

        self._spark = _Sparkline(C, self._history)
        inner.addWidget(self._spark)

        self._last = psutil.net_io_counters()
        self._last_t = time.time()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(1000)
        self.refresh()

    def refresh(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.2)
            s.connect(("8.8.8.8", 80))       # no packets sent; just picks a route
            self._local._value_label.setText(s.getsockname()[0])
            s.close()
        except Exception:
            self._local._value_label.setText("offline")

        nc = psutil.net_io_counters()
        now = time.time()
        dt = max(0.001, now - self._last_t)
        down = (nc.bytes_recv - self._last.bytes_recv) / dt / 2**20
        up   = (nc.bytes_sent - self._last.bytes_sent) / dt / 2**20
        self._last, self._last_t = nc, now

        self._down._value_label.setText(f"{down:.1f} MiB/s")
        self._up._value_label.setText(f"{up:.1f} MiB/s")

        self._history.pop(0)
        self._history.append(down + up)
        self._spark.update()


class _Sparkline(QWidget):
    def __init__(self, C, data: list[float], parent=None):
        super().__init__(parent)
        self.C = C
        self._data = data
        self.setFixedHeight(46)
        self.setStyleSheet("background: transparent;")

    def paintEvent(self, _):
        C = self.C
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        peak = max(0.25, max(self._data))
        pts = [
            QPointF(i / max(1, len(self._data) - 1) * W, H - (v / peak) * (H - 4) - 2)
            for i, v in enumerate(self._data)
        ]
        p.setPen(QPen(QColor(C.PRI), 1.2))
        for i in range(len(pts) - 1):
            p.drawLine(pts[i], pts[i + 1])


# ── processes (left) ────────────────────────────────────────────────────

class ProcessPanel(QWidget):
    def __init__(self, C, parent=None):
        super().__init__(parent)
        self.C = C
        self._rows_data: list[tuple] = []
        self._totals = (0.0, 0.0)

        inner = _panel_frame(self, C, "ACTIVE PROCESSES")
        self._table = _ProcTable(C, self)
        inner.addWidget(self._table, stretch=1)

        # prime cpu_percent so the first real reading isn't all zeros
        for pr in psutil.process_iter(["cpu_percent"]):
            pass

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh_async)
        self._timer.start(2500)

    def _refresh_async(self):
        threading.Thread(target=self._gather, daemon=True).start()

    def _gather(self):
        procs = []
        for pr in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
            try:
                i = pr.info
                procs.append((
                    i["pid"], (i["name"] or "?")[:18],
                    i["cpu_percent"] or 0.0, i["memory_percent"] or 0.0,
                ))
            except Exception:
                continue
        procs.sort(key=lambda t: t[2], reverse=True)
        self._table.set_rows(
            procs[:6],
            psutil.cpu_percent(interval=None),
            psutil.virtual_memory().percent,
        )


class _ProcTable(QWidget):
    def __init__(self, C, parent=None):
        super().__init__(parent)
        self.C = C
        self._rows = []
        self._cpu_total = 0.0
        self._mem_total = 0.0
        self.setMinimumHeight(150)
        self.setStyleSheet("background: transparent;")

    def set_rows(self, rows, cpu_total, mem_total):
        self._rows = rows
        self._cpu_total = cpu_total
        self._mem_total = mem_total
        self.update()

    def paintEvent(self, _):
        C = self.C
        p = QPainter(self)
        W = self.width()
        p.setFont(QFont("Courier New", 9))

        cols = [(0, "PID"), (58, "NAME"), (W - 96, "CPU%"), (W - 44, "MEM%")]
        p.setPen(QPen(QColor(C.TEXT_DIM), 1))
        for x, label in cols:
            p.drawText(QRectF(x, 0, 90, 16),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, label)

        y = 22
        p.setPen(QPen(QColor(C.TEXT), 1))
        for pid, name, cpu, mem in self._rows:
            p.setPen(QPen(QColor(C.TEXT_DIM), 1))
            p.drawText(QRectF(0, y, 56, 16), Qt.AlignmentFlag.AlignLeft, str(pid))
            p.setPen(QPen(QColor(C.TEXT), 1))
            p.drawText(QRectF(58, y, W - 160, 16), Qt.AlignmentFlag.AlignLeft, name)
            p.drawText(QRectF(W - 96, y, 44, 16), Qt.AlignmentFlag.AlignLeft, f"{cpu:.1f}")
            p.drawText(QRectF(W - 44, y, 44, 16), Qt.AlignmentFlag.AlignLeft, f"{mem:.1f}")
            y += 20

        y += 6
        p.setPen(QPen(QColor(C.BORDER), 1))
        p.drawLine(QPointF(0, y), QPointF(W, y))
        y += 6
        p.setPen(QPen(QColor(C.PRI), 1))
        p.drawText(QRectF(0, y, W // 2, 16), Qt.AlignmentFlag.AlignLeft,
                   f"TOTAL CPU: {self._cpu_total:.0f}%")
        p.drawText(QRectF(W // 2, y, W // 2, 16), Qt.AlignmentFlag.AlignLeft,
                   f"TOTAL MEM: {self._mem_total:.0f}%")


# ── quick actions (right) ───────────────────────────────────────────────

class QuickActionsPanel(QWidget):
    """Each row runs something real: the app ones go through the fuzzy
    launcher, so they work regardless of what the app is actually called."""

    action_logged = pyqtSignal(str)

    def __init__(self, C, on_exit=None, parent=None):
        super().__init__(parent)
        self.C = C
        inner = _panel_frame(self, C, "QUICK ACTIONS")

        items = [
            (">_", "Open Terminal",   lambda: self._launch("terminal")),
            ("/\\", "System Monitor", lambda: self._launch("system monitor")),
            ("<>", "Code Editor",     lambda: self._launch("vscode")),
            ("[]", "File Manager",    lambda: self._launch("files")),
            ("()", "Web Browser",     lambda: self._launch("firefox")),
            ("**", "Settings",        lambda: self._launch("settings")),
        ]
        if on_exit:
            items.append(("X", "Exit The Machine", on_exit))

        for icon, label, fn in items:
            inner.addWidget(self._make_row(icon, label, fn))
        inner.addStretch()

    def _make_row(self, icon: str, label: str, fn) -> QWidget:
        C = self.C
        w = QWidget()
        w.setCursor(Qt.CursorShape.PointingHandCursor)
        w.setFixedHeight(34)
        w.setStyleSheet(f"""
            QWidget {{ background: transparent; }}
            QWidget:hover {{ background: {C.PRI_GHO}; }}
        """)
        h = QHBoxLayout(w)
        h.setContentsMargins(6, 0, 6, 0)
        h.setSpacing(10)

        ic = QLabel(icon)
        ic.setFixedSize(26, 22)
        ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ic.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
        ic.setStyleSheet(
            f"color: {C.PRI}; background: transparent; "
            f"border: 1px solid {C.BORDER_B}; border-radius: 3px;"
        )
        h.addWidget(ic)

        tx = QLabel(f"> {label}")
        tx.setFont(QFont("Courier New", 10))
        tx.setStyleSheet(f"color: {C.TEXT}; background: transparent;")
        h.addWidget(tx, stretch=1)

        w.mousePressEvent = lambda _e, f=fn: f()
        return w

    def _launch(self, query: str):
        al = _load_app_launcher()
        if al is None:
            self.action_logged.emit(
                "ERR: app_launcher.py is missing from the project folder — "
                "quick actions need it. (Download it and drop it next to main.py.)"
            )
            return
        try:
            msg = al.open_app_smart(query)
        except Exception as e:
            msg = f"Launch failed: {e}"
        self.action_logged.emit(f"SYS: {msg}")
