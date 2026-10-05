"""Regenerate the raster icons from resources/icons/pvp.svg:
pvp.png (256 px, Linux / docs) and pvp.ico (16-256 px, Windows executable).

    python3 packaging/make_icons.py
"""
import io
import os

from PIL import Image
from PySide6.QtCore import QBuffer, QIODevice, QRectF, Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

ICONS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "resources", "icons")
SIZES = [16, 24, 32, 48, 64, 128, 256]


def render(renderer: QSvgRenderer, size: int) -> Image.Image:
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    renderer.render(p, QRectF(0, 0, size, size))
    p.end()
    buf = QBuffer()
    buf.open(QIODevice.WriteOnly)
    img.save(buf, "PNG")
    return Image.open(io.BytesIO(bytes(buf.data())))


if __name__ == "__main__":
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QGuiApplication([])
    svg = QSvgRenderer(os.path.join(ICONS, "pvp.svg"))
    # render every size from the vector source (sharper than downscaling)
    images = [render(svg, s) for s in SIZES]
    images[-1].save(os.path.join(ICONS, "pvp.png"))
    images[-1].save(os.path.join(ICONS, "pvp.ico"), sizes=[(s, s) for s in SIZES],
                    append_images=images[:-1])
    print("wrote pvp.png, pvp.ico")
