"""
E.V. hero — the homemade HUD.

Design premise, straight from the film's own logic: E.V. isn't Stark tech.
JARVIS, Karen and EDITH were hand-me-downs from a billionaire with a
fabrication lab behind them. E.V. was built from scratch by a kid in a
small apartment with no budget. So this theme is the opposite of the
JARVIS one in every way that matters:

  JARVIS          →  E.V.
  machined arcs   →  hand-drawn lines that wobble
  perfect circles →  organic filaments, no circle anywhere
  cold blue       →  warm crimson and amber, on warm charcoal
  centred, formal →  off-centre, annotated in the margins
  monospace       →  proportional type

The signature trick is the "boiling line": every stroke is drawn as a
jittered polyline that redraws itself a few times a second, the way
hand-drawn animation shivers. Nothing else in this project does that.
"""
from __future__ import annotations

import math
import random

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen, QRadialGradient
from PyQt6.QtWidgets import QHBoxLayout, QLineEdit, QSizePolicy, QVBoxLayout, QWidget

BG      = QColor("#16100e")     # warm charcoal, not black — a dim bedroom
INK     = QColor("#e8503f")     # crimson, the main line colour
AMBER   = QColor("#ffb84d")
CREAM   = QColor("#f2e4d2")
DIM     = QColor("#8a5f52")
FAINT   = QColor("#3a2620")

NOTES = [
    "calibration ok",
    "targeting matrix nominal",
    "recheck servo lag",
    "batt 61% — swap soon",
    "fabricator idle",
    "solder joint 4 = flaky",
    "web pressure stable",
    "TODO: fix the hum",
]


class EveHero(QWidget):
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
        self._boil = 0            # increments every few frames → lines redraw
        self._breath = 0.0
        self._note_i = 0
        self._note_t = 0

        # organic filaments: each is a strand that sways. Polar-ish but
        # deliberately uneven — no strand shares a radius or a rhythm.
        self._strands = [
            {
                "ang": random.uniform(0, math.tau),
                "len": random.uniform(0.55, 1.45),
                "sway": random.uniform(0.4, 1.5),
                "phase": random.uniform(0, math.tau),
                "kink": random.uniform(-1.15, 1.15),   # strong bend: these
                "bright": random.random() < 0.3,       # should curve, not spike
            }
            for _ in range(44)
        ]
        # drifting motes, like dust in a desk lamp
        self._motes = [
            [random.random(), random.random(),
             random.uniform(0.15, 0.5), random.uniform(0.5, 1.6)]
            for _ in range(34)
        ]

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addStretch()

        self._input = QLineEdit()
        self._input.setFont(QFont("Georgia", 12))
        self._input.setFixedHeight(40)
        self._input.setPlaceholderText("talk to me")
        self._input.setStyleSheet(f"""
            QLineEdit {{
                background: rgba(30, 20, 17, 210);
                color: {CREAM.name()};
                border: 1px solid {DIM.name()};
                border-radius: 20px;
                padding: 4px 18px;
            }}
            QLineEdit:focus {{ border: 1px solid {INK.name()}; }}
        """)
        self._input.returnPressed.connect(self._submit)

        row = QHBoxLayout()
        row.addStretch(2)
        row.addWidget(self._input, stretch=5)
        row.addStretch(1)          # off-centre on purpose
        lay.addLayout(row)
        lay.addSpacing(30)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._step)
        self._timer.start(33)

    def _submit(self):
        txt = self._input.text().strip()
        if txt:
            self._input.clear()
            self.submitted.emit(txt)

    def _step(self):
        self._tick += 1
        if self._tick % 7 == 0:
            self._boil += 1          # ~4 redraws/sec — the hand-drawn shiver
        target = 1.0 if self.speaking else 0.0
        self._breath += (target - self._breath) * 0.05

        for m in self._motes:
            m[1] -= m[2] * 0.0016
            if m[1] < -0.02:
                m[0], m[1] = random.random(), 1.02

        self._note_t += 1
        if self._note_t > 150:
            self._note_t = 0
            self._note_i = (self._note_i + 1) % len(NOTES)
        self.update()

    # ── hand-drawn primitives ───────────────────────────────────────────

    def _jitter(self, seed: int, amp: float) -> float:
        """Deterministic per (seed, boil) wobble, so a line shivers in place
        instead of crawling randomly every single frame."""
        r = math.sin(seed * 12.9898 + self._boil * 78.233) * 43758.5453
        return (r - math.floor(r) - 0.5) * 2 * amp

    def _sketch_line(self, p, x1, y1, x2, y2, seed, amp=1.6, segs=9):
        path = QPainterPath()
        dx, dy = x2 - x1, y2 - y1
        ln = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / ln, dx / ln          # perpendicular
        path.moveTo(x1, y1)
        for i in range(1, segs + 1):
            t = i / segs
            off = self._jitter(seed * 31 + i, amp) * (1 - abs(t - 0.5) * 1.2)
            path.lineTo(x1 + dx * t + nx * off, y1 + dy * t + ny * off)
        p.drawPath(path)

    def _sketch_box(self, p, x, y, w, h, seed, amp=1.5):
        # corners overshoot slightly, the way a pen does
        o = 3
        self._sketch_line(p, x - o, y, x + w, y, seed + 1, amp)
        self._sketch_line(p, x + w, y - o, x + w, y + h, seed + 2, amp)
        self._sketch_line(p, x + w + o, y + h, x, y + h, seed + 3, amp)
        self._sketch_line(p, x, y + h + o, x, y, seed + 4, amp)

    # ── drawing ─────────────────────────────────────────────────────────

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        W, H = self.width(), self.height()
        p.fillRect(self.rect(), BG)

        self._draw_motes(p, W, H)
        self._draw_presence(p, W, H)
        self._draw_frame(p, W, H)
        self._draw_text(p, W, H)
        self._draw_margin_notes(p, W, H)
        self._draw_warmth(p, W, H)

    def _draw_motes(self, p, W, H):
        p.setPen(Qt.PenStyle.NoPen)
        for mx, my, _, size in self._motes:
            c = QColor(AMBER)
            c.setAlpha(38)
            p.setBrush(QBrush(c))
            p.drawEllipse(QPointF(mx * W, my * H), size, size)

    def _draw_presence(self, p, W, H):
        """The 'she's here' element. Not a ring, not a gauge — a loose
        cluster of filaments that leans and breathes, placed off-centre."""
        cx, cy = W * 0.615, H * 0.44
        scale = min(W, H) * 0.20 * (1.0 + 0.07 * self._breath)

        # soft warm bloom behind it
        g = QRadialGradient(cx, cy, scale * 2.4)
        g.setColorAt(0.0, QColor(232, 80, 63, int(46 + 40 * self._breath)))
        g.setColorAt(0.55, QColor(232, 80, 63, 16))
        g.setColorAt(1.0, QColor(232, 80, 63, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(g))
        p.drawEllipse(QPointF(cx, cy), scale * 2.4, scale * 2.4)

        p.setBrush(Qt.BrushStyle.NoBrush)
        for i, s in enumerate(self._strands):
            sway = math.sin(self._tick * 0.02 * s["sway"] + s["phase"]) * 0.28
            a = s["ang"] + sway
            reach = scale * s["len"] * (1.0 + 0.12 * self._breath)

            # each strand is a bent path, not a spoke: mid-point pushed
            # sideways by its own kink value
            ex, ey = cx + math.cos(a) * reach, cy + math.sin(a) * reach
            mx = cx + math.cos(a) * reach * 0.5 - math.sin(a) * reach * s["kink"]
            my = cy + math.sin(a) * reach * 0.5 + math.cos(a) * reach * s["kink"]

            col = QColor(CREAM if s["bright"] else (INK if i % 3 else AMBER))
            base = 120 if s["bright"] else 95
            col.setAlpha(int(base + 95 * (0.5 + 0.5 * math.sin(self._tick * 0.03 + i))))
            p.setPen(QPen(col, 1.5 if s["bright"] else 1.1))
            path = QPainterPath()
            path.moveTo(cx, cy)
            path.quadTo(QPointF(mx, my), QPointF(ex, ey))
            p.drawPath(path)

            # a small node at the tip of some strands
            if i % 4 == 0:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(col))
                p.drawEllipse(QPointF(ex, ey), 1.8, 1.8)
                p.setBrush(Qt.BrushStyle.NoBrush)

        # core: a small irregular blob, hand-drawn, not a circle
        p.setPen(QPen(CREAM, 1.8))
        p.setBrush(Qt.BrushStyle.NoBrush)
        core = QPainterPath()
        n = 11
        for i in range(n + 1):
            a = math.tau * i / n
            rr = scale * 0.26 * (1 + 0.20 * math.sin(a * 3 + self._boil))
            px, py = cx + math.cos(a) * rr, cy + math.sin(a) * rr
            if i == 0:
                core.moveTo(px, py)
            else:
                core.lineTo(px, py)
        core.closeSubpath()
        p.drawPath(core)

    def _draw_frame(self, p, W, H):
        # one hand-drawn bracket, only on the left — asymmetric by design
        p.setPen(QPen(DIM, 1.2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        m = 26
        self._sketch_line(p, m, H * 0.16, m, H * 0.84, 7, 2.0, 14)
        self._sketch_line(p, m, H * 0.16, m + 16, H * 0.16, 8, 1.4, 4)
        self._sketch_line(p, m, H * 0.84, m + 16, H * 0.84, 9, 1.4, 4)

        # a small sketched readout box, tucked bottom-left
        bx, by, bw, bh = m + 22, H * 0.66, 132, 62
        if H > 340:
            p.setPen(QPen(FAINT, 1.2))
            self._sketch_box(p, bx, by, bw, bh, 21, 1.6)
            p.setFont(QFont("Georgia", 8))
            p.setPen(QPen(DIM, 1))
            p.drawText(QRectF(bx + 8, by + 6, bw, 14),
                       Qt.AlignmentFlag.AlignLeft, "diagnostics")
            p.setFont(QFont("Georgia", 9))
            p.setPen(QPen(CREAM, 1))
            lag = 3 + int(2 * abs(math.sin(self._tick * 0.02)))
            p.drawText(QRectF(bx + 8, by + 22, bw, 14),
                       Qt.AlignmentFlag.AlignLeft, f"servo lag   {lag} ms")
            p.drawText(QRectF(bx + 8, by + 38, bw, 14),
                       Qt.AlignmentFlag.AlignLeft,
                       f"link        {'live' if not self.muted else 'muted'}")

    def _draw_text(self, p, W, H):
        # left-aligned into the negative space, never centred
        x = W * 0.075
        size = max(20, min(52, int(W / 15)))
        f = QFont("Georgia", size)
        p.setFont(f)
        p.setPen(QPen(CREAM, 1))
        p.drawText(QRectF(x, H * 0.24, W * 0.5, size * 1.6),
                   Qt.AlignmentFlag.AlignLeft, "E.V.")

        sf = QFont("Georgia", max(9, min(13, int(W / 62))))
        sf.setItalic(True)
        p.setFont(sf)
        p.setPen(QPen(DIM, 1))
        p.drawText(QRectF(x + 3, H * 0.24 + size * 1.35, W * 0.5, 20),
                   Qt.AlignmentFlag.AlignLeft, "built in a bedroom, not a lab")

        label = "muted" if self.muted else (
            "listening…" if not self.speaking else "speaking"
        )
        lf = QFont("Georgia", max(10, min(15, int(W / 52))))
        p.setFont(lf)
        p.setPen(QPen(AMBER if self.speaking else INK, 1))
        p.drawText(QRectF(x + 3, H * 0.24 + size * 1.9, W * 0.5, 22),
                   Qt.AlignmentFlag.AlignLeft, label)

    def _draw_margin_notes(self, p, W, H):
        # scribbled annotations up the right edge, like notes in a margin
        if W < 640:
            return
        p.save()
        p.translate(W - 22, H * 0.52)
        p.rotate(-90)
        f = QFont("Georgia", 9)
        f.setItalic(True)
        p.setFont(f)
        p.setPen(QPen(DIM, 1))
        p.drawText(QRectF(-160, -12, 320, 16),
                   Qt.AlignmentFlag.AlignCenter, NOTES[self._note_i])
        p.restore()

        # a tiny underline scribble beneath it
        p.setPen(QPen(FAINT, 1))
        self._sketch_line(p, W - 14, H * 0.52 - 70, W - 14, H * 0.52 + 70, 44, 1.8, 10)

    def _draw_warmth(self, p, W, H):
        # a warm falloff from the top-left, like a desk lamp just out of frame
        g = QRadialGradient(W * 0.12, H * 0.05, max(W, H) * 0.9)
        g.setColorAt(0.0, QColor(255, 184, 77, 26))
        g.setColorAt(0.45, QColor(255, 140, 60, 8))
        g.setColorAt(1.0, QColor(0, 0, 0, 42))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(g))
        p.drawRect(QRectF(0, 0, W, H))
