"""QIcon SVG glyphs recreated from the handoff `icons.jsx` paths.

Each glyph is a 16x16 stroke icon (1.6px stroke, round caps) rendered from an
inline SVG string so no asset files are needed. ``icon(name, color)`` returns a
``QIcon`` tinted to the given color.
"""

from __future__ import annotations

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

# Raw inner SVG markup per glyph (everything inside <svg>), straight from
# icons.jsx. ``sw`` overrides are inlined where the source used them.
_GLYPHS: dict[str, str] = {
    "gear": (
        '<circle cx="8" cy="8" r="2.4"/>'
        '<path d="M8 1.8v2M8 12.2v2M1.8 8h2M12.2 8h2M3.6 3.6l1.4 1.4'
        'M11 11l1.4 1.4M12.4 3.6L11 5M5 11l-1.4 1.4"/>'
    ),
    "close": '<path d="M3.5 3.5l9 9M12.5 3.5l-9 9"/>',
    "min": '<path d="M3 8h10"/>',
    "max": '<rect x="3.5" y="3.5" width="9" height="9" rx="1"/>',
    "link": (
        '<path d="M6.5 9.5l3-3"/>'
        '<path d="M7.5 4.5l1-1a2.5 2.5 0 013.5 3.5l-1 1"/>'
        '<path d="M8.5 11.5l-1 1A2.5 2.5 0 014 9l1-1"/>'
    ),
    "chev_down": '<path d="M4 6.5l4 4 4-4"/>',
    "chev_up": '<path d="M4 9.5l4-4 4 4"/>',
    "chev_right": '<path d="M6 4l4 4-4 4"/>',
    "play": '<path d="M5.5 3.5v9l7-4.5z" fill="currentColor" stroke="none"/>',
    "check": '<path d="M3 8.5l3.2 3.2L13 5"/>',
    "retry": ('<path d="M13 8a5 5 0 11-1.5-3.6"/><path d="M13 2.5V5h-2.5"/>'),
    "pause": '<path d="M5.5 4v8M10.5 4v8" stroke-width="2"/>',
    "trash": '<path d="M3 4.5h10M6.5 4.5V3h3v1.5M4.5 4.5l.7 8h5.6l.7-8"/>',
    "folder": (
        '<path d="M2 4.5A1.5 1.5 0 013.5 3h3l1.5 1.5h4.5A1.5 1.5 0 0114 6v5.5'
        'a1.5 1.5 0 01-1.5 1.5h-9A1.5 1.5 0 012 11.5z"/>'
    ),
    "warn": ('<path d="M8 2.5l6 11H2z"/><path d="M8 6.5v3M8 11.6v.01" stroke-width="1.8"/>'),
    "download": '<path d="M8 2.5v7M5 7l3 3 3-3M3 13h10"/>',
    "cookie": (
        '<circle cx="8" cy="8" r="5.8"/>'
        '<path d="M6 6.2v.01M9.8 7.2v.01M7 10v.01M10 10.4v.01" stroke-width="2"/>'
    ),
}


def svg_markup(name: str, color: str, size: int = 16, stroke: float = 1.6) -> str:
    """Full SVG document string for a glyph, with ``currentColor`` resolved."""
    inner = _GLYPHS[name].replace("currentColor", color)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 16 16" fill="none" stroke="{color}" stroke-width="{stroke}" '
        f'stroke-linecap="round" stroke-linejoin="round">{inner}</svg>'
    )


def pixmap(name: str, color: str = "#e8e8ee", size: int = 16, stroke: float = 1.6) -> QPixmap:
    """Render a glyph to a ``QPixmap`` at the given size and color."""
    renderer = QSvgRenderer(QByteArray(svg_markup(name, color, size, stroke).encode("utf-8")))
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    renderer.render(painter)
    painter.end()
    return pm


def icon(name: str, color: str = "#e8e8ee", size: int = 16, stroke: float = 1.6) -> QIcon:
    """Return a ``QIcon`` for a named glyph tinted to ``color``."""
    return QIcon(pixmap(name, color, size, stroke))
