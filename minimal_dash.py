"""
Minimal hero — the light theme.

Deliberately the opposite of every other theme here. No neon, no glow, no
scanlines, no glitch, no grid. Its own layout too: nothing is boxed in
panels. Instead it borrows from Swiss/editorial print — an off-white
surface, hairline rules, a lot of empty space, one accent colour, and
typography doing the work.

Numbers are real (psutil); they're just presented as a caption strip
rather than as bars in boxes.
"""
from __future__ import annotations

import time

import psutil
from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PyQt6.QtWidgets import QHBoxLayout, QLineEdit, QSizePolicy, QVBoxLayout, QWidget

PAPER   = QColor("#f4f3ef")     # warm off-white, not pure white
INK     = QColor("#16181a")
INK_MID = QColor("#6b7075")
INK_FAI = QColor("#c9c7c1")
RULE    = QColor("#d8d6d0")
ACCENT  = QColor("#d6482f")     # single warm accent, Braun-ish


class MinimalHero(QWidget):
    submitted = pyqtSignal(str)

    def __init__(self, C, parent=None):
        super().__init__(parent)
        self.C = C
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setMinimumHeight(240)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.speaking = False
        self.muted = False
        self.state = "ONLINE"

        self._tick = 0
        self._cpu_hist = [0.0] * 80
        self._stats = {"cpu": 0.0, "mem": 0.0, "disk": 0.0, "up": "0h 00m"}

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addStretch()

        self._input = QLineEdit()
        self._input.setFont(QFont("Helvetica", 13))
        self._input.setFixedHeight(38)
        self._input.setPlaceholderText("Ask anything")
        # borderless with a single underline — a print form field, not a box
        self._input.setStyleSheet(f"""
            QLineEdit {{
                background: transparent;
                color: {INK.name()};
                border: none;
                border-bottom: 1px solid {RULE.name()};
                padding: 2px 2px;
            }}
            QLineEdit:focus {{ border-bottom: 1px solid {ACCENT.name()}; }}
        """)
        self._input.returnPressed.connect(self._submit)

        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(self._input, stretch=4)
        row.addStretch(1)
        lay.addLayout(row)
        lay.addSpacing(74)          # generous space below — the strip sits there

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._step)
        self._timer.start(120)

        self._refresh_stats()

    def _submit(self):
        txt = self._input.text().strip()
        if txt:
            self._input.clear()
            self.submitted.emit(txt)

    def _step(self):
        self._tick += 1
        if self._tick % 8 == 0:
            self._refresh_stats()
        self.update()

    def _refresh_stats(self):
        try:
            cpu = psutil.cpu_percent(interval=None)
            self._cpu_hist.pop(0)
            self._cpu_hist.append(cpu)
            up = int(time.time() - psutil.boot_time())
            self._stats = {
                "cpu": cpu,
                "mem": psutil.virtual_memory().percent,
                "disk": psutil.disk_usage("/").percent,
                "up": f"{up // 3600}h {(up % 3600) // 60:02d}m",
            }
        except Exception:
            pass

    # ── drawing ─────────────────────────────────────────────────────────

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        p.fillRect(self.rect(), PAPER)

        margin = max(28, int(W * 0.07))

        self._draw_masthead(p, W, H, margin)
        self._draw_state(p, W, H, margin)
        self._draw_sparkline(p, W, H, margin)
        self._draw_strip(p, W, H, margin)

    def _draw_masthead(self, p, W, H, m):
        # small caps wordmark, wide tracking, top-left. Rule underneath runs
        # the full measure — the page-header idea from print.
        f = QFont("Helvetica", 10, QFont.Weight.DemiBold)
        f.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 210)
        p.setFont(f)
        p.setPen(QPen(INK, 1))
        p.drawText(QRectF(m, 26, W - m * 2, 18),
                   Qt.AlignmentFlag.AlignLeft, "THE MACHINE")

        f2 = QFont("Helvetica", 9)
        f2.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 118)
        p.setFont(f2)
        p.setPen(QPen(INK_MID, 1))
        p.drawText(QRectF(m, 26, W - m * 2, 18),
                   Qt.AlignmentFlag.AlignRight, time.strftime("%H:%M"))

        p.setPen(QPen(RULE, 1))
        p.drawLine(QPointF(m, 52), QPointF(W - m, 52))

    def _draw_state(self, p, W, H, m):
        # the one big element on the page: current state, set large and light
        label = "Muted" if self.muted else (
            "Speaking" if self.speaking else self.state.capitalize()
        )
        size = max(26, min(64, int(W / 13)))
        f = QFont("Helvetica", size, QFont.Weight.Light)
        f.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 96)
        p.setFont(f)
        p.setPen(QPen(INK, 1))
        base_y = H * 0.26
        p.drawText(QRectF(m, base_y, W - m * 2, size * 1.5),
                   Qt.AlignmentFlag.AlignLeft, label)

        # accent dot, set like a superscript marker after the word
        tw = QFontMetrics(f).horizontalAdvance(label)
        dot_r = max(3.0, size * 0.072)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(ACCENT if not self.muted else INK_FAI)
        p.drawEllipse(
            QPointF(m + tw + dot_r * 2.8, base_y + size * 0.46),
            dot_r, dot_r,
        )

        # caption, clear of the descenders above it
        cf = QFont("Helvetica", 10)
        cf.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 112)
        p.setFont(cf)
        p.setPen(QPen(INK_MID, 1))
        p.drawText(QRectF(m, base_y + size * 1.88, W - m * 2, 18),
                   Qt.AlignmentFlag.AlignLeft,
                   "Local instance · admin access")

    def _draw_sparkline(self, p, W, H, m):
        # a single hairline of CPU history, sitting right on a baseline rule.
        # No fill, no glow — just the trace.
        y0 = H * 0.655
        h = 46
        p.setPen(QPen(RULE, 1))
        p.drawLine(QPointF(m, y0 + h), QPointF(W - m, y0 + h))

        span = (W - m * 2)
        n = len(self._cpu_hist)
        # auto-scale to the data's own range: fixed 0-100 makes a normal
        # idle machine draw an almost flat line with no information in it
        lo, hi = min(self._cpu_hist), max(self._cpu_hist)
        if hi - lo < 6:
            mid = (hi + lo) / 2
            lo, hi = mid - 3, mid + 3
        rng = hi - lo
        pts = [
            QPointF(m + (i / (n - 1)) * span,
                    y0 + h - ((v - lo) / rng) * h)
            for i, v in enumerate(self._cpu_hist)
        ]
        p.setPen(QPen(INK, 1.2))
        for i in range(len(pts) - 1):
            p.drawLine(pts[i], pts[i + 1])

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(ACCENT)
        p.drawEllipse(pts[-1], 2.4, 2.4)

        lf = QFont("Helvetica", 8)
        lf.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 130)
        p.setFont(lf)
        p.setPen(QPen(INK_FAI, 1))
        p.drawText(QRectF(m, y0 - 16, W - m * 2, 14),
                   Qt.AlignmentFlag.AlignLeft, "PROCESSOR LOAD")

    def _draw_strip(self, p, W, H, m):
        # caption strip: four figures with hairline separators between them
        items = [
            (f"{self._stats['cpu']:.0f}%", "CPU"),
            (f"{self._stats['mem']:.0f}%", "MEMORY"),
            (f"{self._stats['disk']:.0f}%", "DISK"),
            (self._stats["up"], "UPTIME"),
        ]
        y = H - 54
        span = W - m * 2
        col = span / len(items)

        num_f = QFont("Helvetica", max(15, min(24, int(W / 42))), QFont.Weight.Light)
        lab_f = QFont("Helvetica", 8)
        lab_f.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 150)

        p.setPen(QPen(RULE, 1))
        p.drawLine(QPointF(m, y - 14), QPointF(W - m, y - 14))

        for i, (value, label) in enumerate(items):
            x = m + i * col
            if i:
                p.setPen(QPen(RULE, 1))
                p.drawLine(QPointF(x - 1, y - 4), QPointF(x - 1, y + 34))
            p.setFont(num_f)
            p.setPen(QPen(INK, 1))
            p.drawText(QRectF(x + 12, y, col - 12, 30),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       value)
            p.setFont(lab_f)
            p.setPen(QPen(INK_MID, 1))
            p.drawText(QRectF(x + 12, y + 26, col - 12, 14),
                       Qt.AlignmentFlag.AlignLeft, label)
