"""
Cyberpunk hero scene — Breach Protocol flavour.

Deliberately unlike the others: no rings (JARVIS), no rain (matrix), no
sunset (synthwave). Instead it's a glitchy hacking/datashard panel —
yellow-on-black with cyan and magenta accents, RGB-split title, drifting
scanlines, a hex code matrix like the Breach Protocol minigame, corner
brackets and the occasional glitch tear.

Colours from the game's UI palette: yellow #FCEE0A, cyan #25E1ED,
magenta #ED1E79.
"""
from __future__ import annotations

import random

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QHBoxLayout, QLineEdit, QSizePolicy, QVBoxLayout, QWidget

YELLOW  = QColor("#fcee0a")
CYAN    = QColor("#25e1ed")
MAGENTA = QColor("#ed1e79")
DIM_Y   = QColor("#8a7d05")
BG0     = QColor("#0a0a02")

HEX_PAIRS = ["1C", "55", "E9", "7A", "BD", "FF", "1F", "A3", "0C", "2D", "88", "E1"]


class CyberpunkHero(QWidget):
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
        self._glitch = 0.0           # 0..1 current glitch intensity
        self._next_glitch = 40       # ticks until the next random tear
        self._scan = 0.0

        # the breach-protocol hex grid — a block of code pairs, some lit
        self._grid_cols = 8
        self._grid_rows = 7
        self._grid = [
            [random.choice(HEX_PAIRS) for _ in range(self._grid_cols)]
            for _ in range(self._grid_rows)
        ]
        self._lit = set()            # (r,c) cells currently highlighted

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addStretch()

        self._input = QLineEdit()
        self._input.setFont(QFont("Courier New", 12))
        self._input.setFixedHeight(42)
        self._input.setPlaceholderText("> INPUT COMMAND SEQUENCE_")
        self._input.setStyleSheet(f"""
            QLineEdit {{
                background: rgba(20, 18, 2, 220);
                color: {YELLOW.name()};
                border: 1px solid {YELLOW.name()};
                border-radius: 0px;
                padding: 4px 14px;
            }}
            QLineEdit:focus {{ border: 1px solid {CYAN.name()}; }}
        """)
        self._input.returnPressed.connect(self._submit)

        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(self._input, stretch=3)
        row.addStretch(1)
        lay.addLayout(row)
        lay.addSpacing(26)

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
        self._scan = (self._scan + 0.9) % 1000

        # random glitch bursts; more frequent while speaking
        self._next_glitch -= 1
        if self._next_glitch <= 0:
            self._glitch = 1.0
            self._next_glitch = random.randint(18, 55) - (10 if self.speaking else 0)
        self._glitch *= 0.82        # decay

        # churn the hex grid + move which cells are lit
        if self._tick % 4 == 0:
            r = random.randrange(self._grid_rows)
            c = random.randrange(self._grid_cols)
            self._grid[r][c] = random.choice(HEX_PAIRS)
        if self._tick % 8 == 0:
            self._lit = {
                (random.randrange(self._grid_rows), random.randrange(self._grid_cols))
                for _ in range(random.randint(2, 5))
            }
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)  # crisp, pixel-y
        W, H = self.width(), self.height()
        p.fillRect(self.rect(), BG0)

        self._draw_grid_bg(p, W, H)
        self._draw_hexblock(p, W, H)
        self._draw_scanlines(p, W, H)
        self._draw_frame(p, W, H)
        self._draw_title(p, W, H)
        self._draw_glitch(p, W, H)

    def _draw_grid_bg(self, p, W, H):
        # faint engineering grid
        c = QColor(YELLOW); c.setAlpha(14)
        p.setPen(QPen(c, 1))
        step = 40
        for x in range(0, W, step):
            p.drawLine(x, 0, x, H)
        for y in range(0, H, step):
            p.drawLine(0, y, W, y)

    def _draw_hexblock(self, p, W, H):
        # breach-protocol style code matrix, upper-right of the scene
        cell = 30
        gw = self._grid_cols * cell
        gh = self._grid_rows * cell
        ox = W - gw - 40
        oy = 46
        if ox < W * 0.42:            # hide on very narrow windows
            return

        p.setFont(QFont("Courier New", 12, QFont.Weight.Bold))
        # header
        p.setPen(QPen(CYAN, 1))
        p.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        p.drawText(QRectF(ox, oy - 18, gw, 14),
                   Qt.AlignmentFlag.AlignLeft, "// BREACH PROTOCOL // BUFFER 8/8")

        p.setFont(QFont("Courier New", 12, QFont.Weight.Bold))
        for r in range(self._grid_rows):
            for c in range(self._grid_cols):
                x = ox + c * cell
                y = oy + r * cell
                lit = (r, c) in self._lit
                if lit:
                    p.fillRect(QRectF(x, y, cell - 4, cell - 4),
                               QColor(252, 238, 10, 40))
                    p.setPen(QPen(YELLOW, 1))
                else:
                    p.setPen(QPen(DIM_Y, 1))
                p.drawText(QRectF(x, y, cell, cell),
                           Qt.AlignmentFlag.AlignCenter, self._grid[r][c])

    def _draw_scanlines(self, p, W, H):
        c = QColor(0, 0, 0, 60)
        p.setPen(Qt.PenStyle.NoPen)
        for y in range(0, H, 3):
            p.fillRect(QRectF(0, y, W, 1), c)
        # one bright moving scanline
        sy = (self._scan / 1000.0) * H
        band = QColor(CYAN); band.setAlpha(28)
        p.fillRect(QRectF(0, sy, W, 2), band)

    def _draw_frame(self, p, W, H):
        m = 12
        # magenta L-brackets at corners
        p.setPen(QPen(MAGENTA, 2))
        b = 26
        for bx, by, dx, dy in [(m,m,1,1),(W-m,m,-1,1),(m,H-m,1,-1),(W-m,H-m,-1,-1)]:
            p.drawLine(QPointF(bx, by), QPointF(bx + dx*b, by))
            p.drawLine(QPointF(bx, by), QPointF(bx, by + dy*b))

        # top-left status stamp
        p.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        p.setPen(QPen(YELLOW, 1))
        label = "MUTED" if self.muted else (
            "//TRANSMITTING" if self.speaking else f"//{self.state}"
        )
        p.drawText(QRectF(m + 8, m + 6, 300, 14), Qt.AlignmentFlag.AlignLeft, label)
        p.setPen(QPen(CYAN, 1))
        p.drawText(QRectF(m + 8, m + 20, 300, 14), Qt.AlignmentFlag.AlignLeft,
                   "NETWATCH::ICE_INACTIVE")

    def _draw_title(self, p, W, H):
        title_px = max(18, min(46, int(W / 11)))
        cy = H * 0.34
        f = QFont("Courier New", title_px, QFont.Weight.Black)
        f.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 108)
        p.setFont(f)
        rect = QRectF(0, cy, W, title_px * 1.5)

        # RGB split — offset cyan + magenta ghosts behind the yellow, with a
        # jitter that jumps during glitches. This is the signature look.
        j = int(self._glitch * 8)
        off = 3 + j
        p.setPen(QPen(QColor(37, 225, 237, 200), 1))
        p.drawText(rect.translated(-off, 0), Qt.AlignmentFlag.AlignCenter, "THE MACHINE")
        p.setPen(QPen(QColor(237, 30, 121, 200), 1))
        p.drawText(rect.translated(off, 0), Qt.AlignmentFlag.AlignCenter, "THE MACHINE")
        p.setPen(QPen(YELLOW, 1))
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, "THE MACHINE")

        # subtitle with a "corrupted" flicker on random characters
        sub = "SYSTEM ONLINE // NETRUNNER READY"
        if self._glitch > 0.3:
            chars = list(sub)
            for _ in range(int(self._glitch * 6)):
                i = random.randrange(len(chars))
                chars[i] = random.choice("!@#$%&/\\|<>_")
            sub = "".join(chars)
        p.setFont(QFont("Courier New", max(8, min(12, int(W / 46))), QFont.Weight.Bold))
        p.setPen(QPen(CYAN, 1))
        p.drawText(QRectF(0, cy + title_px * 1.6, W, 20),
                   Qt.AlignmentFlag.AlignCenter, sub)

        # prompt hint above input
        p.setFont(QFont("Courier New", max(8, min(11, int(W / 52)))))
        p.setPen(QPen(DIM_Y, 1))
        p.drawText(QRectF(0, cy + title_px * 1.6 + 24, W, 18),
                   Qt.AlignmentFlag.AlignCenter, "How can I help you, choom?")

    def _draw_glitch(self, p, W, H):
        if self._glitch < 0.15:
            return
        # horizontal tear bars — slices of the frame shoved sideways with a
        # coloured edge, the classic datamosh artifact
        n = int(self._glitch * 5) + 1
        for _ in range(n):
            y = random.randint(0, H - 6)
            h = random.randint(2, 10)
            dx = random.randint(-18, 18)
            col = random.choice([CYAN, MAGENTA, YELLOW])
            c = QColor(col); c.setAlpha(90)
            p.fillRect(QRectF(dx, y, W, h), QColor(0, 0, 0, 40))
            p.setPen(QPen(c, 1))
            p.drawLine(QPointF(max(0, dx), y), QPointF(W, y))
