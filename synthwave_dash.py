"""
Synthwave hero scene.

The animated retrowave picture that replaces the HUD when the synthwave
theme is on: gradient sun with slits, a perspective grid scrolling toward
you, mountain silhouettes with neon edges, and a starfield.

The side panels are the same ones matrix mode uses — they take the colour
class as a parameter, so they re-skin themselves for free.
"""
from __future__ import annotations

import math
import random

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen,
    QRadialGradient,
)
from PyQt6.QtWidgets import QHBoxLayout, QLineEdit, QSizePolicy, QVBoxLayout, QWidget

# Fixed scene colours. These don't come from the theme class because the
# whole point of this picture is a specific sunset palette — the panels
# around it still follow the theme.
SKY_TOP    = QColor("#0d0221")
SKY_MID    = QColor("#2b0a4a")
SKY_LOW    = QColor("#7a1b62")
SUN_TOP    = QColor("#ffe66d")
SUN_MID    = QColor("#ff8c42")
SUN_LOW    = QColor("#ff2e97")
GRID_NEAR  = QColor("#ff5cd6")
GRID_FAR   = QColor("#8a4fff")
MTN_FILL   = QColor("#160a2e")
MTN_EDGE   = QColor("#b06bff")
STAR       = QColor("#ffffff")


class SynthwaveHero(QWidget):
    """The scene, plus the title and prompt drawn over it."""

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
        self._scroll = 0.0          # grid movement, 0..1 loops
        self._pulse = 0.0
        self._stars = [
            (random.random(), random.random(), random.uniform(0.6, 1.8),
             random.uniform(0, 6.283))
            for _ in range(90)
        ]
        # mountain ridge: (centre x as 0..1, height as 0..1, half-width)
        self._peaks = []
        x = -0.05
        while x < 1.1:
            self._peaks.append((x, random.uniform(0.22, 0.72), random.uniform(0.06, 0.13)))
            x += random.uniform(0.07, 0.14)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addStretch()

        self._input = QLineEdit()
        self._input.setFont(QFont("Courier New", 12))
        self._input.setFixedHeight(42)
        self._input.setStyleSheet(f"""
            QLineEdit {{
                background: rgba(20, 4, 40, 200);
                color: #ffe9ff;
                border: 1px solid {GRID_NEAR.name()};
                border-radius: 21px;
                padding: 4px 18px;
            }}
            QLineEdit:focus {{ border: 2px solid {SUN_TOP.name()}; }}
        """)
        self._input.setPlaceholderText("type a command…")
        self._input.returnPressed.connect(self._submit)

        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(self._input, stretch=3)
        row.addStretch(1)
        lay.addLayout(row)
        lay.addSpacing(26)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._step)
        self._timer.start(33)          # ~30 fps

    def _submit(self):
        txt = self._input.text().strip()
        if txt:
            self._input.clear()
            self.submitted.emit(txt)

    def _step(self):
        self._tick += 1
        # grid rolls faster while it's talking, so the scene reacts
        self._scroll = (self._scroll + (0.028 if self.speaking else 0.012)) % 1.0
        target = 1.0 if self.speaking else 0.0
        self._pulse += (target - self._pulse) * 0.06
        self.update()

    # ── drawing ─────────────────────────────────────────────────────────

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        horizon = H * 0.56

        self._draw_sky(p, W, H, horizon)
        self._draw_stars(p, W, horizon)
        self._draw_sun(p, W, horizon)
        self._draw_mountains(p, W, horizon)
        self._draw_grid(p, W, H, horizon)
        self._draw_text(p, W, H, horizon)

    def _draw_sky(self, p, W, H, horizon):
        g = QLinearGradient(0, 0, 0, horizon)
        g.setColorAt(0.0, SKY_TOP)
        g.setColorAt(0.62, SKY_MID)
        g.setColorAt(1.0, SKY_LOW)
        p.fillRect(QRectF(0, 0, W, horizon), QBrush(g))
        # ground is near-black so the neon grid pops off it
        p.fillRect(QRectF(0, horizon, W, H - horizon), QColor("#0a0118"))

    def _draw_stars(self, p, W, horizon):
        p.setPen(Qt.PenStyle.NoPen)
        for sx, sy, size, phase in self._stars:
            y = sy * horizon * 0.86
            # clamp: sin() dips below zero here and a negative alpha is a
            # Qt warning per star, per frame
            twinkle = max(0.05, 0.45 + 0.55 * math.sin(self._tick * 0.05 + phase))
            c = QColor(STAR)
            c.setAlpha(max(0, min(255, int(200 * twinkle))))
            p.setBrush(QBrush(c))
            p.drawEllipse(QPointF(sx * W, y), size, size)

    def _draw_sun(self, p, W, horizon):
        # sits mostly above the horizon, its lower part hidden behind it
        r = min(W, horizon) * (0.34 + 0.02 * self._pulse)
        cx = W / 2
        cy = horizon - r * 0.42

        # outer glow
        glow = QRadialGradient(cx, cy, r * 2.1)
        glow.setColorAt(0.0, QColor(255, 90, 190, 90))
        glow.setColorAt(0.5, QColor(255, 60, 160, 34))
        glow.setColorAt(1.0, QColor(255, 60, 160, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(glow))
        p.drawEllipse(QPointF(cx, cy), r * 2.1, r * 2.1)

        # the disc itself, clipped so nothing spills below the horizon
        p.save()
        clip = QPainterPath()
        clip.addRect(QRectF(0, 0, W, horizon))
        p.setClipPath(clip)

        g = QLinearGradient(0, cy - r, 0, cy + r)
        g.setColorAt(0.0, SUN_TOP)
        g.setColorAt(0.48, SUN_MID)
        g.setColorAt(1.0, SUN_LOW)
        p.setBrush(QBrush(g))
        p.drawEllipse(QPointF(cx, cy), r, r)

        # horizontal slits across the lower half — they get thicker and
        # closer together toward the bottom, which is what makes it read
        # as retrowave rather than just a circle
        p.setBrush(QBrush(QColor("#0a0118")))
        y = cy + r * 0.06
        gap = r * 0.20
        thick = r * 0.020
        while y < cy + r:
            p.drawRect(QRectF(cx - r, y, r * 2, thick))
            y += gap
            gap *= 0.86
            thick *= 1.20
        p.restore()

    def _draw_mountains(self, p, W, horizon):
        base = horizon + 1
        peak_h = horizon * 0.34
        path = QPainterPath()
        path.moveTo(-10, base)
        for cx01, h01, hw01 in self._peaks:
            cx = cx01 * W
            hw = hw01 * W
            path.lineTo(cx - hw, base)
            path.lineTo(cx, base - peak_h * h01)
            path.lineTo(cx + hw, base)
        path.lineTo(W + 10, base)
        path.lineTo(W + 10, base + 6)
        path.lineTo(-10, base + 6)
        path.closeSubpath()

        p.setBrush(QBrush(MTN_FILL))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawPath(path)

        # neon rim — a soft wide pass under a bright thin one
        glow_pen = QPen(QColor(MTN_EDGE.red(), MTN_EDGE.green(), MTN_EDGE.blue(), 70), 5)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(glow_pen)
        p.drawPath(path)
        p.setPen(QPen(QColor("#d9b3ff"), 1.4))
        p.drawPath(path)

    def _draw_grid(self, p, W, H, horizon):
        vp_x = W / 2                      # vanishing point
        depth = H - horizon
        if depth <= 2:
            return

        # horizontal lines: perspective spacing, scrolled toward the viewer
        n = 22
        focal = depth * 0.34
        p.setBrush(Qt.BrushStyle.NoBrush)
        for i in range(n):
            z = i + 1 - self._scroll
            y = horizon + focal / z
            if y > H + 4:
                continue
            t = min(1.0, (y - horizon) / depth)     # 0 far, 1 near
            col = QColor(
                int(GRID_FAR.red()   + (GRID_NEAR.red()   - GRID_FAR.red())   * t),
                int(GRID_FAR.green() + (GRID_NEAR.green() - GRID_FAR.green()) * t),
                int(GRID_FAR.blue()  + (GRID_NEAR.blue()  - GRID_FAR.blue())  * t),
                int(60 + 195 * t),
            )
            p.setPen(QPen(col, 0.8 + 1.8 * t))
            p.drawLine(QPointF(0, y), QPointF(W, y))

        # vertical lines converging on the vanishing point
        spread = W * 1.9
        for k in range(-14, 15):
            x_bottom = vp_x + (k / 14.0) * spread
            t = abs(k) / 14.0
            col = QColor(GRID_NEAR)
            col.setAlpha(int(210 - 90 * t))
            p.setPen(QPen(col, 1.2))
            p.drawLine(QPointF(vp_x, horizon), QPointF(x_bottom, H))

        # bright horizon line with a bloom above it
        hl = QLinearGradient(0, horizon - 26, 0, horizon)
        hl.setColorAt(0.0, QColor(255, 92, 214, 0))
        hl.setColorAt(1.0, QColor(255, 92, 214, 110))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(hl))
        p.drawRect(QRectF(0, horizon - 26, W, 26))
        p.setPen(QPen(QColor("#ffd9f5"), 1.6))
        p.drawLine(QPointF(0, horizon), QPointF(W, horizon))

    def _draw_text(self, p, W, H, horizon):
        C = self.C
        title_px = max(16, min(44, int(W / 11.5)))
        ty = horizon * 0.30

        f = QFont("Courier New", title_px, QFont.Weight.Bold)
        f.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 122)
        p.setFont(f)

        rect = QRectF(0, ty, W, title_px * 1.7)
        # chunky drop shadow, then a magenta offset, then the bright face —
        # cheap way to get that layered chrome look
        p.setPen(QPen(QColor(80, 0, 90, 200), 1))
        p.drawText(rect.translated(3, 3), Qt.AlignmentFlag.AlignCenter, "THE MACHINE")
        p.setPen(QPen(QColor("#ff2e97"), 1))
        p.drawText(rect.translated(-2, -2), Qt.AlignmentFlag.AlignCenter, "THE MACHINE")
        p.setPen(QPen(QColor("#fff2ff"), 1))
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, "THE MACHINE")

        sub_px = max(8, min(12, int(W / 44)))
        p.setFont(QFont("Courier New", sub_px, QFont.Weight.Bold))
        p.setPen(QPen(QColor("#8be9ff"), 1))
        label = "MUTED" if self.muted else (
            "TRANSMITTING" if self.speaking else self.state
        )
        p.drawText(QRectF(0, ty + title_px * 1.8, W, 20),
                   Qt.AlignmentFlag.AlignCenter,
                   f"·  {label}  ·")
