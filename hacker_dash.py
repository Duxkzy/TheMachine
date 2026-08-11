"""
Hacker hero — the movie-hacker CRT.

Deliberately not the matrix theme: no falling katakana. This is the *other*
cliche, the one from every 90s hacking scene — a green phosphor monitor
running several panes at once:

  · a live hex dump scrolling past
  · a brute-force key crack, characters locking in one at a time
  · a network node map with pings travelling along the links
  · a rolling status log with progress bars
  · CRT flicker, scanlines, a vignette, and a fat blinking cursor

None of it is a real attack on anything — it's decorative output driven by
random numbers, which is exactly what those movie screens were too.
"""
from __future__ import annotations

import math
import random
import string

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QRadialGradient
from PyQt6.QtWidgets import QHBoxLayout, QLineEdit, QSizePolicy, QVBoxLayout, QWidget

PHOS      = QColor("#33ff66")     # phosphor green
PHOS_DIM  = QColor("#1a8c38")
PHOS_FAINT = QColor("#0d4a1e")
PHOS_HOT  = QColor("#c8ffd8")     # near-white core of a bright glyph
AMBER     = QColor("#ffb000")     # the one warning colour
BG        = QColor("#020703")

HEXCH = "0123456789ABCDEF"
CRACK_CHARS = string.ascii_uppercase + string.digits + "#$%&@!"

STATUS_LINES = [
    "resolving host topology",
    "enumerating open ports",
    "fingerprinting daemon",
    "spoofing MAC address",
    "injecting payload stub",
    "escalating privileges",
    "dumping keyring",
    "patching audit log",
    "tunnelling through relay",
    "rotating session token",
    "scrubbing access trace",
    "mirroring filesystem",
]


class HackerHero(QWidget):
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
        self._flicker = 1.0

        # hex dump — a rolling window of fake memory
        self._dump_addr = random.randrange(0x40000000, 0x7FFFFFFF) & ~0xF
        self._dump: list[tuple[int, list[int]]] = []
        for i in range(26):
            self._dump.append(
                (self._dump_addr + i * 16, [random.randrange(256) for _ in range(8)])
            )

        # brute-force crack
        self._target = "".join(random.choice(CRACK_CHARS) for _ in range(12))
        self._locked = 0
        self._scramble = list(self._target)

        # node map
        self._nodes = [
            (random.uniform(0.12, 0.88), random.uniform(0.15, 0.85))
            for _ in range(11)
        ]
        self._links = []
        for i in range(len(self._nodes)):
            for _ in range(2):
                j = random.randrange(len(self._nodes))
                if j != i and (i, j) not in self._links and (j, i) not in self._links:
                    self._links.append((i, j))
        self._pings = []      # (link_index, progress 0..1, speed)

        # status log
        self._log: list[tuple[str, float, bool]] = []   # text, progress, done
        for _ in range(5):
            self._push_log()

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addStretch()

        self._input = QLineEdit()
        self._input.setFont(QFont("Courier New", 12, QFont.Weight.Bold))
        self._input.setFixedHeight(38)
        self._input.setPlaceholderText("root@themachine:~#")
        self._input.setStyleSheet(f"""
            QLineEdit {{
                background: rgba(2, 12, 5, 235);
                color: {PHOS.name()};
                border: 1px solid {PHOS_DIM.name()};
                border-radius: 0px;
                padding: 4px 12px;
            }}
            QLineEdit:focus {{ border: 1px solid {PHOS.name()}; }}
        """)
        self._input.returnPressed.connect(self._submit)

        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(self._input, stretch=4)
        row.addStretch(1)
        lay.addLayout(row)
        lay.addSpacing(20)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._step)
        self._timer.start(50)

    def _submit(self):
        txt = self._input.text().strip()
        if txt:
            self._input.clear()
            self.submitted.emit(txt)

    def _push_log(self):
        # avoid repeating the line that's already on screen — two identical
        # rows next to each other reads as a bug, not as output
        recent = {e[0] for e in self._log[-3:]}
        choices = [s for s in STATUS_LINES if s not in recent] or STATUS_LINES
        self._log.append([random.choice(choices), 0.0, False])
        if len(self._log) > 6:
            self._log.pop(0)

    def _step(self):
        self._tick += 1
        speed = 2 if self.speaking else 1

        # CRT flicker — mostly steady with the occasional dip
        self._flicker = 0.94 + random.random() * 0.06
        if random.random() < 0.02:
            self._flicker = 0.72

        # scroll the hex dump
        if self._tick % max(1, 3 // speed) == 0:
            last = self._dump[-1][0] + 16
            self._dump.append((last, [random.randrange(256) for _ in range(8)]))
            self._dump.pop(0)

        # brute force: lock a character in now and then, then reset
        if self._tick % max(1, 9 // speed) == 0:
            if self._locked < len(self._target):
                self._locked += 1
            else:
                if self._tick % 60 == 0:
                    self._target = "".join(
                        random.choice(CRACK_CHARS) for _ in range(12)
                    )
                    self._locked = 0
        self._scramble = [
            self._target[i] if i < self._locked else random.choice(CRACK_CHARS)
            for i in range(len(self._target))
        ]

        # pings along links
        if random.random() < 0.25 * speed and self._links:
            self._pings.append([random.randrange(len(self._links)), 0.0,
                                random.uniform(0.02, 0.06)])
        for pg in self._pings:
            pg[1] += pg[2]
        self._pings = [pg for pg in self._pings if pg[1] < 1.0]

        # status log progress
        for entry in self._log:
            if not entry[2]:
                entry[1] += random.uniform(0.01, 0.07) * speed
                if entry[1] >= 1.0:
                    entry[1] = 1.0
                    entry[2] = True
        if all(e[2] for e in self._log) and self._tick % 10 == 0:
            self._push_log()

        self.update()

    # ── drawing ─────────────────────────────────────────────────────────

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        W, H = self.width(), self.height()
        p.fillRect(self.rect(), BG)

        # panes only appear when there's room; on a small window it falls
        # back to just the banner so nothing overlaps into mush
        wide = W > 720
        tall = H > 380

        if wide and tall:
            self._draw_hexdump(p, 14, 14, int(W * 0.34), int(H * 0.56))
            self._draw_nodemap(p, int(W * 0.36), 14, int(W * 0.30), int(H * 0.40))
            self._draw_crack(p, int(W * 0.68), 14, int(W * 0.30), int(H * 0.24))
            self._draw_statuslog(p, int(W * 0.68), int(H * 0.28),
                                 int(W * 0.30), int(H * 0.42))

        self._draw_banner(p, W, H, compact=not (wide and tall))
        self._draw_crt(p, W, H)

    def _pane(self, p, x, y, w, h, title):
        # explicit NoBrush: whatever was drawn before (the node map sets a
        # green fill) would otherwise flood the whole pane
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(PHOS_FAINT, 1))
        p.drawRect(QRectF(x, y, w, h))
        p.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        p.setPen(QPen(PHOS_DIM, 1))
        p.fillRect(QRectF(x + 6, y - 6, len(title) * 6 + 8, 11), BG)
        p.drawText(QRectF(x + 10, y - 7, 400, 12),
                   Qt.AlignmentFlag.AlignLeft, title)

    def _draw_hexdump(self, p, x, y, w, h):
        self._pane(p, x, y, w, h, "0x MEMORY DUMP")
        p.setFont(QFont("Courier New", 8))
        line_h = 12
        rows = int((h - 14) / line_h)
        for i, (addr, data) in enumerate(self._dump[-rows:]):
            ly = y + 10 + i * line_h
            fade = 0.35 + 0.65 * (i / max(1, rows - 1))
            col = QColor(PHOS)
            col.setAlpha(int(255 * fade * self._flicker))
            p.setPen(QPen(col, 1))
            hexpart = " ".join(f"{b:02X}" for b in data)
            asciipart = "".join(
                chr(b) if 32 <= b < 127 else "." for b in data
            )
            p.drawText(QRectF(x + 8, ly, w - 12, line_h),
                       Qt.AlignmentFlag.AlignLeft,
                       f"{addr:08X}  {hexpart}  |{asciipart}|")

    def _draw_nodemap(self, p, x, y, w, h):
        self._pane(p, x, y, w, h, "NET TOPOLOGY")
        pad = 14
        ix, iy = x + pad, y + pad
        iw, ih = w - pad * 2, h - pad * 2

        def pos(n):
            return QPointF(ix + self._nodes[n][0] * iw, iy + self._nodes[n][1] * ih)

        p.setPen(QPen(PHOS_FAINT, 1))
        for a, b in self._links:
            p.drawLine(pos(a), pos(b))

        # pings sliding along a link
        for li, prog, _ in self._pings:
            a, b = self._links[li]
            pa, pb = pos(a), pos(b)
            pt = QPointF(pa.x() + (pb.x() - pa.x()) * prog,
                         pa.y() + (pb.y() - pa.y()) * prog)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(PHOS_HOT))
            p.drawEllipse(pt, 2.2, 2.2)

        p.setPen(Qt.PenStyle.NoPen)
        for i in range(len(self._nodes)):
            pulse = 0.5 + 0.5 * math.sin(self._tick * 0.08 + i)
            c = QColor(PHOS)
            c.setAlpha(int(120 + 135 * pulse))
            p.setBrush(QBrush(c))
            r = 2.5 + pulse * 1.5
            p.drawEllipse(pos(i), r, r)

    def _draw_crack(self, p, x, y, w, h):
        self._pane(p, x, y, w, h, "BRUTE FORCE")
        p.setFont(QFont("Courier New", 13, QFont.Weight.Bold))
        cw = max(9, (w - 22) // len(self._scramble))
        for i, ch in enumerate(self._scramble):
            locked = i < self._locked
            p.setPen(QPen(PHOS_HOT if locked else PHOS_DIM, 1))
            p.drawText(QRectF(x + 11 + i * cw, y + h * 0.30, cw, 20),
                       Qt.AlignmentFlag.AlignCenter, ch)

        pct = self._locked / len(self._target)
        bar_y = y + h * 0.66
        p.setPen(QPen(PHOS_FAINT, 1))
        p.drawRect(QRectF(x + 11, bar_y, w - 22, 8))
        p.fillRect(QRectF(x + 12, bar_y + 1, (w - 24) * pct, 6), PHOS)

        p.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        done = self._locked >= len(self._target)
        p.setPen(QPen(AMBER if done else PHOS_DIM, 1))
        p.drawText(QRectF(x + 11, bar_y + 12, w - 22, 14),
                   Qt.AlignmentFlag.AlignLeft,
                   "*** ACCESS GRANTED ***" if done else f"KEYSPACE {pct*100:5.1f}%")

    def _draw_statuslog(self, p, x, y, w, h):
        self._pane(p, x, y, w, h, "TASK QUEUE")
        p.setFont(QFont("Courier New", 8))
        line_h = max(20, int((h - 16) / max(1, len(self._log))))
        for i, (text, prog, done) in enumerate(self._log):
            ly = y + 10 + i * line_h
            p.setPen(QPen(PHOS if done else PHOS_DIM, 1))
            mark = "[OK]" if done else "[..]"
            p.drawText(QRectF(x + 9, ly, w - 16, 12),
                       Qt.AlignmentFlag.AlignLeft, f"{mark} {text[:26]}")
            bw = w - 20
            p.setPen(QPen(PHOS_FAINT, 1))
            p.drawLine(QPointF(x + 10, ly + 14), QPointF(x + 10 + bw, ly + 14))
            p.setPen(QPen(PHOS if done else AMBER, 2))
            p.drawLine(QPointF(x + 10, ly + 14),
                       QPointF(x + 10 + bw * prog, ly + 14))

    def _draw_banner(self, p, W, H, compact: bool):
        cy = H * (0.44 if compact else 0.70)
        size = max(18, min(44, int(W / 13)))
        f = QFont("Courier New", size, QFont.Weight.Black)
        f.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 112)
        p.setFont(f)

        label = "THE MACHINE"
        # phosphor bloom: a dim wide pass under the bright one
        c = QColor(PHOS); c.setAlpha(int(70 * self._flicker))
        p.setPen(QPen(c, 1))
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            p.drawText(QRectF(dx, cy + dy, W, size * 1.5),
                       Qt.AlignmentFlag.AlignCenter, label)
        c2 = QColor(PHOS_HOT); c2.setAlpha(int(255 * self._flicker))
        p.setPen(QPen(c2, 1))
        p.drawText(QRectF(0, cy, W, size * 1.5),
                   Qt.AlignmentFlag.AlignCenter, label)

        sub = "MUTED" if self.muted else (
            "TRANSMITTING…" if self.speaking else f"{self.state} — awaiting instruction"
        )
        blink = "█" if (self._tick // 8) % 2 == 0 else " "
        p.setFont(QFont("Courier New", max(8, min(12, int(W / 48))), QFont.Weight.Bold))
        p.setPen(QPen(PHOS, 1))
        p.drawText(QRectF(0, cy + size * 1.45, W, 18),
                   Qt.AlignmentFlag.AlignCenter, f"> {sub} {blink}")

    def _draw_crt(self, p, W, H):
        # scanlines
        p.setPen(Qt.PenStyle.NoPen)
        dark = QColor(0, 0, 0, 70)
        for y in range(0, H, 3):
            p.fillRect(QRectF(0, y, W, 1), dark)

        # rolling brightness band, like a badly synced monitor
        band_y = (self._tick * 3) % (H + 160) - 80
        g = QColor(PHOS); g.setAlpha(10)
        p.fillRect(QRectF(0, band_y, W, 70), g)

        # vignette — corners fall off, the way a curved tube does
        v = QRadialGradient(W / 2, H / 2, max(W, H) * 0.72)
        v.setColorAt(0.0, QColor(0, 0, 0, 0))
        v.setColorAt(0.72, QColor(0, 0, 0, 40))
        v.setColorAt(1.0, QColor(0, 0, 0, 165))
        p.setBrush(QBrush(v))
        p.drawRect(QRectF(0, 0, W, H))

        # overall flicker
        if self._flicker < 0.85:
            p.fillRect(self.rect(), QColor(0, 0, 0, int((1 - self._flicker) * 90)))
