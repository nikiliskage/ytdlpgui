"""Generate ``app/resources/icon.ico`` from the title-bar logo mark.

Renders the purple-gradient rounded square + white download glyph (identical to
``app.widgets.title_bar._LogoMark``) at high resolution via Qt, then writes a
multi-size Windows ``.ico`` with Pillow.

Run:  python tools/make_icon.py
"""

from __future__ import annotations

import io
from pathlib import Path

from app import icons
from PIL import Image
from PySide6.QtCore import QBuffer, QByteArray, Qt
from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter
from PySide6.QtWidgets import QApplication

_OUT = Path(__file__).resolve().parent.parent / "app" / "resources" / "icon.ico"
_SIZES = [256, 128, 64, 48, 32, 16]


def _render(size: int) -> QImage:
    """Draw the logo mark into a transparent ARGB image of the given size."""
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    painter = QPainter(img)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    grad = QLinearGradient(0, 0, size, size)
    grad.setColorAt(0.0, QColor("#a855f7"))
    grad.setColorAt(1.0, QColor("#7437b8"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(grad)
    radius = size // 4
    painter.drawRoundedRect(0, 0, size, size, radius, radius)
    glyph = round(size * 13 / 22)  # same glyph/size ratio as _LogoMark (13/22)
    off = (size - glyph) // 2
    painter.drawPixmap(off, off, icons.pixmap("download", "#ffffff", glyph))
    painter.end()
    return img


def _to_pillow(img: QImage) -> Image.Image:
    data = QByteArray()
    buf = QBuffer(data)
    buf.open(QBuffer.OpenModeFlag.WriteOnly)
    img.save(buf, "PNG")
    buf.close()
    return Image.open(io.BytesIO(bytes(data))).convert("RGBA")


def main() -> None:
    QApplication([])  # required for QPixmap/QPainter
    base = _to_pillow(_render(max(_SIZES)))
    base.save(_OUT, format="ICO", sizes=[(s, s) for s in _SIZES])
    print(f"wrote {_OUT} ({_OUT.stat().st_size} bytes, sizes={_SIZES})")


if __name__ == "__main__":
    main()
