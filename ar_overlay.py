"""
AR hand-tracking overlay — JARVIS theme only.

This is a toy. It's for messing around, not for real work: gesture control
of a computer is fiddly, needs good lighting, and will misfire sometimes.
It's built to look cool and be fun, and it's off unless you turn it on.

Requirements:
    pip install mediapipe

    Plus the model file (~7 MB), saved next to this file in core/:
    wget -O core/hand_landmarker.task \\
      https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task

IMPORTANT — the API note: mediapipe 0.10.30+ REMOVED the old
`mp.solutions.hands` API that every tutorial online still uses. This file
uses the current Tasks API instead. If you copy code from a YouTube video
and it says `mp.solutions` doesn't exist, that's why.
"""
from __future__ import annotations

import math
import threading
import time
from pathlib import Path

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont, QImage, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

BASE_DIR   = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "core" / "hand_landmarker.task"

# landmark indices — standard MediaPipe hand model
WRIST = 0
TIPS  = {"thumb": 4, "index": 8, "middle": 12, "ring": 16, "pinky": 20}
PIPS  = {"index": 6, "middle": 10, "ring": 14, "pinky": 18}

# How long a pose must be held before it counts. Longer = fewer accidental
# fires, and you get more time to see the charge ring and back out.
GESTURE_HOLD_SECS = 0.9
GESTURE_REFIRE_SECS = 1.5


def deps_status() -> tuple[bool, str]:
    """Returns (ready, message). Checked before opening the overlay so the
    user gets a clear reason instead of a silent black screen."""
    try:
        import mediapipe  # noqa: F401
    except ImportError:
        return False, "mediapipe isn't installed — run: pip install mediapipe"
    try:
        import cv2  # noqa: F401
    except ImportError:
        return False, "opencv isn't installed — run: pip install opencv-python"
    if not MODEL_PATH.exists():
        return False, (
            f"model file missing at core/{MODEL_PATH.name} — see the download "
            "command at the top of ar_overlay.py"
        )
    return True, "ready"


class HandTracker:
    """Runs the camera + MediaPipe on a background thread. Only ever writes
    to plain attributes; the widget reads them on the GUI thread."""

    def __init__(self):
        self.frame_rgb = None      # latest camera frame, as an RGB numpy array
        self.hands: list = []      # list of landmark lists, normalized 0..1
        self.lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self.error = ""

    def start(self) -> None:
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="ar-hands")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread = None

    def _loop(self) -> None:
        try:
            import cv2
            import mediapipe as mp
            import numpy as np
            from mediapipe.tasks.python import BaseOptions
            from mediapipe.tasks.python.vision import (
                HandLandmarker, HandLandmarkerOptions, RunningMode,
            )
        except Exception as e:
            self.error = f"import failed: {e}"
            return

        try:
            options = HandLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=str(MODEL_PATH)),
                running_mode=RunningMode.VIDEO,
                num_hands=2,
                min_hand_detection_confidence=0.6,
                min_tracking_confidence=0.5,
            )
            landmarker = HandLandmarker.create_from_options(options)
        except Exception as e:
            self.error = f"model load failed: {e}"
            return

        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            self.error = "couldn't open the camera"
            return
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        t0 = time.time()
        try:
            while not self._stop.is_set():
                ok, frame = cap.read()
                if not ok:
                    time.sleep(0.03)
                    continue

                frame = cv2.flip(frame, 1)           # mirror, so it feels like a mirror
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                ts_ms = int((time.time() - t0) * 1000)
                try:
                    result = landmarker.detect_for_video(mp_img, ts_ms)
                    found = [
                        [(lm.x, lm.y, lm.z) for lm in hand]
                        for hand in (result.hand_landmarks or [])
                    ]
                except Exception:
                    found = []

                with self.lock:
                    self.frame_rgb = rgb
                    self.hands = found
        finally:
            cap.release()
            try:
                landmarker.close()
            except Exception:
                pass

    def snapshot(self):
        with self.lock:
            return self.frame_rgb, list(self.hands)


def fingers_up(lm) -> dict:
    """Which fingers look extended. Rough but good enough to tell poses
    apart — y grows downward, so a tip above its knuckle means 'up'."""
    out = {}
    for name, pip in PIPS.items():
        out[name] = lm[TIPS[name]][1] < lm[pip][1]
    # thumb: sideways, so compare distance from the wrist instead of height
    d_tip = math.dist(lm[TIPS["thumb"]][:2], lm[WRIST][:2])
    d_ip  = math.dist(lm[3][:2], lm[WRIST][:2])
    out["thumb"] = d_tip > d_ip * 1.15
    return out


def classify(lm) -> str:
    """Map a hand's landmarks to one of a few named poses."""
    up = fingers_up(lm)
    n = sum(up.values())

    pinch_d = math.dist(lm[TIPS["thumb"]][:2], lm[TIPS["index"]][:2])
    hand_sz = math.dist(lm[WRIST][:2], lm[9][:2]) or 0.001
    if pinch_d / hand_sz < 0.35:
        return "PINCH"

    if n == 0:
        return "FIST"
    if n >= 5:
        return "OPEN PALM"
    if up["index"] and up["middle"] and not up["ring"] and not up["pinky"]:
        return "PEACE"
    if up["index"] and n == 1:
        return "POINT"
    return "—"


class ARHudOverlay(QWidget):
    """Camera feed + hand skeleton + JARVIS-flavoured readouts."""

    closed = pyqtSignal()

    def __init__(self, colors, parent=None):
        super().__init__(parent)
        self.C = colors                 # the theme's colour class from ui.py
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            ARHudOverlay {{
                background: rgba(0, 6, 10, 250);
                border: 1px solid {colors.PRI};
                border-radius: 6px;
            }}
        """)

        self.tracker = HandTracker()
        self.on_gesture = None      # set by ui.py: callable(gesture_name)
        self.control_enabled = False
        self._gesture = "—"
        self._last_fired = ""
        self._last_fire_t = 0.0
        self._hold_since = 0.0
        self._tick = 0

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 8)
        lay.setSpacing(4)

        hdr = QHBoxLayout()
        title = QLabel("◈  AUGMENTED VIEW  ·  HAND TRACKING")
        title.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {colors.PRI}; background: transparent;")
        hdr.addWidget(title)
        hdr.addStretch()

        self._ctrl_btn = QPushButton("CONTROL: OFF")
        self._ctrl_btn.setFixedHeight(22)
        self._ctrl_btn.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        self._ctrl_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._style_ctrl_btn()
        self._ctrl_btn.clicked.connect(self._toggle_control)
        hdr.addWidget(self._ctrl_btn)

        close_btn = QPushButton("✕  CLOSE")
        close_btn.setFixedHeight(22)
        close_btn.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(
            f"color: {colors.TEXT_DIM}; background: transparent; border: none;"
        )
        close_btn.clicked.connect(self.stop)
        hdr.addWidget(close_btn)
        lay.addLayout(hdr)

        self._canvas = _ARCanvas(self)
        lay.addWidget(self._canvas, stretch=1)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._step)

    def _style_ctrl_btn(self) -> None:
        on = self.control_enabled
        col = self.C.GREEN if on else self.C.TEXT_DIM
        self._ctrl_btn.setText(f"CONTROL: {'ON' if on else 'OFF'}")
        self._ctrl_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {col};
                border: 1px solid {col}; border-radius: 3px; padding: 0 6px;
            }}
        """)

    def _toggle_control(self) -> None:
        self.control_enabled = not self.control_enabled
        self._style_ctrl_btn()

    def charge(self) -> float:
        """0..1 — how far along the current pose is toward firing. Drives
        the ring on the pointer so you can see it coming and back off if
        it's the wrong one."""
        if self._gesture in ("—", "PINCH"):
            return 0.0
        if self._hold_since > time.time():      # already fired, waiting for change
            return 1.0
        held = time.time() - self._hold_since
        return max(0.0, min(1.0, held / GESTURE_HOLD_SECS))

    def start(self) -> None:
        self.tracker.start()
        self._timer.start(33)      # ~30 fps repaint
        self.show()
        self.raise_()

    def stop(self) -> None:
        self._timer.stop()
        self.tracker.stop()
        self.hide()
        self.closed.emit()

    def _step(self) -> None:
        self._tick += 1
        _, hands = self.tracker.snapshot()

        gesture = classify(hands[0]) if hands else "—"
        now = time.time()

        # a pose has to be held ~0.4s before it counts, and the same one
        # can't re-fire for 1.5s — otherwise one wave spams a dozen actions
        if gesture != self._gesture:
            self._gesture = gesture
            self._hold_since = now
        elif (
            gesture not in ("—", "PINCH")
            and now - self._hold_since > GESTURE_HOLD_SECS
            and (gesture != self._last_fired or now - self._last_fire_t > GESTURE_REFIRE_SECS)
        ):
            self._last_fired = gesture
            self._last_fire_t = now
            self._hold_since = now + 999   # don't refire until the pose changes
            if self.on_gesture:
                self.on_gesture(gesture)

        self._canvas.update()


class _ARCanvas(QWidget):
    """The actual drawing surface — camera frame underneath, HUD on top."""

    def __init__(self, host: ARHudOverlay):
        super().__init__(host)
        self._host = host

    def paintEvent(self, _):
        host = self._host
        C = host.C
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        p.fillRect(self.rect(), QColor(C.BG))

        frame, hands = host.tracker.snapshot()

        # ── camera feed, dimmed so the overlay reads on top of it ──────────
        fx = fy = 0.0
        fw = fh = 0.0
        if frame is not None:
            h, w, _ = frame.shape
            img = QImage(frame.data, w, h, 3 * w, QImage.Format.Format_RGB888)
            px = QPixmap.fromImage(img).scaled(
                W, H, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            fw, fh = px.width(), px.height()
            fx, fy = (W - fw) / 2, (H - fh) / 2
            p.setOpacity(0.55)
            p.drawPixmap(int(fx), int(fy), px)
            p.setOpacity(1.0)
            # scanline texture over the video, for the HUD-feed feel
            p.setPen(QPen(QColor(C.PRI), 1))
            p.setOpacity(0.06)
            for y in range(int(fy), int(fy + fh), 3):
                p.drawLine(int(fx), y, int(fx + fw), y)
            p.setOpacity(1.0)
        elif host.tracker.error:
            p.setPen(QPen(QColor(C.RED), 1))
            p.setFont(QFont("Courier New", 9))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                       f"Camera error:\n{host.tracker.error}")
            return
        else:
            p.setPen(QPen(QColor(C.TEXT_DIM), 1))
            p.setFont(QFont("Courier New", 9))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "starting camera…")
            return

        from mediapipe.tasks.python.vision import HandLandmarksConnections as HC

        def to_px(lm):
            return QPointF(fx + lm[0] * fw, fy + lm[1] * fh)

        # ── hand skeletons ─────────────────────────────────────────────────
        for lm in hands:
            p.setPen(QPen(QColor(C.PRI), 1.6))
            for conn in HC.HAND_CONNECTIONS:
                p.drawLine(to_px(lm[conn.start]), to_px(lm[conn.end]))

            for i, point in enumerate(lm):
                is_tip = i in TIPS.values()
                r = 4.0 if is_tip else 2.2
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(QColor(C.ACC if is_tip else C.PRI)))
                p.drawEllipse(to_px(point), r, r)

            # arc-reactor style rings on the palm centre
            palm = to_px(lm[9])
            span = math.dist((lm[0][0], lm[0][1]), (lm[9][0], lm[9][1])) * fh
            for k in range(3):
                rr = span * (0.55 + k * 0.32)
                spin = (host._tick * (2.2 - k * 0.6)) % 360
                col = QColor(C.PRI); col.setAlpha(190 - k * 45)
                p.setPen(QPen(col, 1.4)); p.setBrush(Qt.BrushStyle.NoBrush)
                rect = QRectF(palm.x() - rr, palm.y() - rr, rr * 2, rr * 2)
                for seg in range(3):
                    p.drawArc(rect, int((spin + seg * 120) * 16), int(64 * 16))

            # bracket around the whole hand, like a target lock
            xs = [fx + q[0] * fw for q in lm]
            ys = [fy + q[1] * fh for q in lm]
            pad = 14
            x0, x1 = min(xs) - pad, max(xs) + pad
            y0, y1 = min(ys) - pad, max(ys) + pad
            bl = 16
            col = QColor(C.ACC2); col.setAlpha(200)
            p.setPen(QPen(col, 1.6))
            for bx, by, dx, dy in [(x0,y0,1,1),(x1,y0,-1,1),(x0,y1,1,-1),(x1,y1,-1,-1)]:
                p.drawLine(QPointF(bx, by), QPointF(bx + dx*bl, by))
                p.drawLine(QPointF(bx, by), QPointF(bx, by + dy*bl))

            # pinch indicator — line between thumb and index when they're close
            t, i8 = to_px(lm[4]), to_px(lm[8])
            pinch_d = math.dist((lm[4][0], lm[4][1]), (lm[8][0], lm[8][1]))
            hand_sz = math.dist((lm[0][0], lm[0][1]), (lm[9][0], lm[9][1])) or 0.001
            if pinch_d / hand_sz < 0.6:
                col = QColor(C.GREEN); col.setAlpha(220)
                p.setPen(QPen(col, 1.4, Qt.PenStyle.DashLine))
                p.drawLine(t, i8)
                mid = QPointF((t.x()+i8.x())/2, (t.y()+i8.y())/2)
                p.setPen(QPen(col, 1))
                p.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
                p.drawText(QRectF(mid.x()-30, mid.y()-16, 60, 12),
                           Qt.AlignmentFlag.AlignCenter, f"{pinch_d/hand_sz:.2f}")

        # ── pointer + gesture charge ───────────────────────────────────────
        # A visible cursor at the index fingertip, with a ring that fills as
        # the pose is held. You can see what's about to fire before it does,
        # instead of guessing.
        if hands:
            lm = hands[0]
            tip = to_px(lm[8])
            charged = host.charge()          # 0..1

            # crosshair cursor
            col = QColor(C.GREEN if charged >= 1.0 else C.ACC2)
            p.setPen(QPen(col, 1.6)); p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawLine(QPointF(tip.x() - 14, tip.y()), QPointF(tip.x() - 5, tip.y()))
            p.drawLine(QPointF(tip.x() + 5, tip.y()), QPointF(tip.x() + 14, tip.y()))
            p.drawLine(QPointF(tip.x(), tip.y() - 14), QPointF(tip.x(), tip.y() - 5))
            p.drawLine(QPointF(tip.x(), tip.y() + 5), QPointF(tip.x(), tip.y() + 14))
            p.drawEllipse(tip, 3.0, 3.0)

            # charge ring — fills clockwise while a pose is held
            if charged > 0:
                rr = 22.0
                rect = QRectF(tip.x() - rr, tip.y() - rr, rr * 2, rr * 2)
                p.setPen(QPen(QColor(C.PRI_DIM), 2))
                p.drawArc(rect, 0, 360 * 16)
                p.setPen(QPen(col, 3))
                p.drawArc(rect, 90 * 16, -int(360 * charged * 16))

                if charged >= 1.0:
                    p.setPen(QPen(QColor(C.GREEN), 1))
                    p.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
                    p.drawText(QRectF(tip.x() - 60, tip.y() + rr + 4, 120, 14),
                               Qt.AlignmentFlag.AlignCenter, "▸ FIRED")
                elif host._gesture not in ("—", "PINCH"):
                    p.setPen(QPen(QColor(C.ACC2), 1))
                    p.setFont(QFont("Courier New", 7))
                    p.drawText(QRectF(tip.x() - 70, tip.y() + rr + 4, 140, 14),
                               Qt.AlignmentFlag.AlignCenter,
                               f"HOLD… {host._gesture}")

        # ── readouts ───────────────────────────────────────────────────────
        p.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
        p.setPen(QPen(QColor(C.PRI), 1))
        p.drawText(QRectF(10, 8, 260, 16), Qt.AlignmentFlag.AlignLeft,
                   f"HANDS TRACKED: {len(hands)}")

        gcol = C.ACC if host._gesture not in ("—",) else C.TEXT_DIM
        p.setPen(QPen(QColor(gcol), 1))
        p.setFont(QFont("Courier New", 14, QFont.Weight.Bold))
        p.drawText(QRectF(10, 26, 320, 22), Qt.AlignmentFlag.AlignLeft,
                   f"POSE: {host._gesture}")

        p.setFont(QFont("Courier New", 7))
        p.setPen(QPen(QColor(C.TEXT_DIM), 1))
        hint = (
            "OPEN PALM = mute · FIST = interrupt · PEACE = next tab · POINT = prev tab"
            if host.control_enabled else
            "OPEN PALM = mute · FIST = interrupt   (CONTROL off: tab gestures ignored)"
        )
        p.drawText(QRectF(10, H - 20, W - 20, 14), Qt.AlignmentFlag.AlignLeft, hint)
