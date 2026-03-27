#!/usr/bin/env python3
"""
Build script: creates "MIDI File Examiner.app" in the project directory.

Run once (or after changing Python/deps):
    python3 create_app.py

The .app launches midi_examiner_gui.py from the same folder using the
exact python3 that ran this script, so no PATH juggling is needed.
"""

import os
import sys
import shutil
import subprocess
import tempfile

# Use offscreen rendering — no display needed for icon generation
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtGui import (QPainter, QColor, QLinearGradient,
                              QPainterPath, QPen, QBrush, QImage)
    from PyQt6.QtCore import Qt, QRectF, QPointF
except ImportError:
    print("PyQt6 is required. Install with: pip install PyQt6")
    sys.exit(1)

# One QApplication instance is required before creating any QImage
_qapp = QApplication.instance() or QApplication(sys.argv)

# ── paths ────────────────────────────────────────────────────────────────────
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
APP_NAME    = "MIDI File Examiner"
APP_BUNDLE  = os.path.join(SCRIPT_DIR, f"{APP_NAME}.app")
PYTHON_BIN  = sys.executable   # exact interpreter to embed in launcher

# ── icon drawing ─────────────────────────────────────────────────────────────

def _draw_icon(size: int) -> QImage:
    """Return a QImage of the app icon at *size* × *size* pixels."""
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    s = float(size)

    # Background — macOS-style rounded square with dark navy gradient
    radius = s * 0.18
    bg = QPainterPath()
    bg.addRoundedRect(QRectF(0, 0, s, s), radius, radius)
    grad = QLinearGradient(0, 0, 0, s)
    grad.setColorAt(0.0, QColor(22, 44, 88))
    grad.setColorAt(1.0, QColor( 8, 18, 45))
    p.fillPath(bg, QBrush(grad))
    p.setClipPath(bg)

    # Piano keyboard — lower 47 % of icon
    key_top = s * 0.53
    key_h   = s * 0.43
    n_white = 7
    w_w     = s / n_white
    gap     = max(1.0, s * 0.013)
    corner  = max(1.5, s * 0.025)

    # White keys
    white_color = QColor(232, 237, 255)
    for i in range(n_white):
        x = i * w_w + gap / 2
        w = w_w - gap
        kp = QPainterPath()
        kp.moveTo(x, key_top)
        kp.lineTo(x + w, key_top)
        kp.lineTo(x + w, key_top + key_h - corner)
        kp.quadTo(x + w, key_top + key_h, x + w - corner, key_top + key_h)
        kp.lineTo(x + corner, key_top + key_h)
        kp.quadTo(x, key_top + key_h, x, key_top + key_h - corner)
        kp.closeSubpath()
        p.fillPath(kp, white_color)

    # Black keys — semitone positions C#, D#, F#, G#, A# in one octave
    bk_w = w_w * 0.60
    bk_h = key_h * 0.60
    bk_corner = max(1.0, s * 0.018)
    black_color = QColor(12, 18, 42)
    for pos in (0, 1, 3, 4, 5):
        x = (pos + 1) * w_w - bk_w / 2
        kp = QPainterPath()
        kp.moveTo(x, key_top)
        kp.lineTo(x + bk_w, key_top)
        kp.lineTo(x + bk_w, key_top + bk_h - bk_corner)
        kp.quadTo(x + bk_w, key_top + bk_h, x + bk_w - bk_corner, key_top + bk_h)
        kp.lineTo(x + bk_corner, key_top + bk_h)
        kp.quadTo(x, key_top + bk_h, x, key_top + bk_h - bk_corner)
        kp.closeSubpath()
        p.fillPath(kp, black_color)

    # Beamed eighth notes — upper area
    accent = QColor(110, 190, 255)
    nr     = s * 0.082        # note-head semi-axis
    sw     = max(1.5, s * 0.038)   # stem width
    bw     = max(1.5, s * 0.045)   # beam width

    # Note-head centres
    n1x, n1y = s * 0.305, s * 0.355
    n2x, n2y = s * 0.605, s * 0.295

    # Beam top — horizontal offset of stem from centre of head
    sx_off = nr * 1.08
    beam_y1 = n1y - s * 0.235
    beam_y2 = n2y - s * 0.235

    # Stems
    pen = QPen(accent, sw)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.drawLine(QPointF(n1x + sx_off, n1y), QPointF(n1x + sx_off, beam_y1))
    p.drawLine(QPointF(n2x + sx_off, n2y), QPointF(n2x + sx_off, beam_y2))

    # Beam
    bpen = QPen(accent, bw)
    bpen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(bpen)
    p.drawLine(QPointF(n1x + sx_off, beam_y1), QPointF(n2x + sx_off, beam_y2))

    # Note heads (drawn after stems so they overlap the stem base cleanly)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(accent)
    for cx, cy in ((n1x, n1y), (n2x, n2y)):
        head = QPainterPath()
        head.addEllipse(QRectF(cx - nr * 1.18, cy - nr * 0.80,
                               nr * 2.36, nr * 1.60))
        p.fillPath(head, accent)

    p.end()
    return img


# ── icon packaging ────────────────────────────────────────────────────────────

# Required sizes for a full macOS iconset
_ICON_SPECS = [
    ("icon_16x16.png",       16),
    ("icon_16x16@2x.png",    32),
    ("icon_32x32.png",       32),
    ("icon_32x32@2x.png",    64),
    ("icon_128x128.png",    128),
    ("icon_128x128@2x.png", 256),
    ("icon_256x256.png",    256),
    ("icon_256x256@2x.png", 512),
    ("icon_512x512.png",    512),
    ("icon_512x512@2x.png",1024),
]

def build_icns(dest_path: str) -> None:
    """Generate AppIcon.icns at *dest_path*."""
    with tempfile.TemporaryDirectory() as tmp:
        iconset = os.path.join(tmp, "AppIcon.iconset")
        os.makedirs(iconset)
        drawn: dict[int, QImage] = {}
        for filename, px in _ICON_SPECS:
            if px not in drawn:
                drawn[px] = _draw_icon(px)
            drawn[px].save(os.path.join(iconset, filename))
        subprocess.run(
            ["iconutil", "-c", "icns", "-o", dest_path, iconset],
            check=True,
        )
    print(f"  icon  → {dest_path}")


# ── .app bundle assembly ──────────────────────────────────────────────────────

INFO_PLIST = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
    "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>MIDI File Examiner</string>
    <key>CFBundleDisplayName</key>
    <string>MIDI File Examiner</string>
    <key>CFBundleIdentifier</key>
    <string>com.nsheldon.midi-file-examiner</string>
    <key>CFBundleVersion</key>
    <string>{version}</string>
    <key>CFBundleShortVersionString</key>
    <string>{version}</string>
    <key>CFBundleExecutable</key>
    <string>MIDI File Examiner</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.15</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSRequiresAquaSystemAppearance</key>
    <false/>
    <key>CFBundleDocumentTypes</key>
    <array>
        <dict>
            <key>CFBundleTypeName</key>
            <string>MIDI File</string>
            <key>CFBundleTypeExtensions</key>
            <array>
                <string>mid</string>
                <string>midi</string>
            </array>
            <key>CFBundleTypeRole</key>
            <string>Viewer</string>
            <key>LSHandlerRank</key>
            <string>Alternate</string>
        </dict>
    </array>
</dict>
</plist>
"""

LAUNCHER = """\
#!/bin/bash
# Auto-generated launcher — re-run create_app.py to update.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# MacOS/ -> Contents/ -> .app/ -> project dir
PROJECT_DIR="$(dirname "$(dirname "$(dirname "$SCRIPT_DIR")")")"
exec {python} "$PROJECT_DIR/midi_examiner_gui.py" "$@"
"""


def build_app() -> None:
    from midi_examiner import __version__

    # Remove stale bundle
    if os.path.exists(APP_BUNDLE):
        shutil.rmtree(APP_BUNDLE)
        print(f"  removed old {APP_NAME}.app")

    macos_dir     = os.path.join(APP_BUNDLE, "Contents", "MacOS")
    resources_dir = os.path.join(APP_BUNDLE, "Contents", "Resources")
    os.makedirs(macos_dir)
    os.makedirs(resources_dir)

    # Info.plist
    plist_path = os.path.join(APP_BUNDLE, "Contents", "Info.plist")
    with open(plist_path, "w") as f:
        f.write(INFO_PLIST.format(version=__version__))
    print(f"  plist → {plist_path}")

    # Launcher script
    launcher_path = os.path.join(macos_dir, APP_NAME)
    with open(launcher_path, "w") as f:
        f.write(LAUNCHER.format(python=PYTHON_BIN))
    os.chmod(launcher_path, 0o755)
    print(f"  launcher → {launcher_path}")

    # Icon
    icns_path = os.path.join(resources_dir, "AppIcon.icns")
    build_icns(icns_path)

    print(f"\nDone: {APP_BUNDLE}")


if __name__ == "__main__":
    print(f"Building {APP_NAME}.app …")
    build_app()
