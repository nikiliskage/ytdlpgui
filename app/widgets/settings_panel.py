"""Right-hand settings slide-over with all sections.

Every control writes through to the injected ``config`` (IConfig-like) on change.
Sections: Binaries / Output / Audio / Subtitles & embedding / Performance
(concurrent fragments + max concurrent downloads) / Cookies / Maintenance.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from app import icons
from app.core import contracts as c
from app.widgets.path_field import PathField
from app.widgets.toggle import Toggle


def _as_int(value: object, default: int) -> int:
    """Coerce a config value (object) to int, falling back to default."""
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return default


class _Pills(QWidget):
    """Single-select pill group bound to a config key."""

    selected = Signal(str)

    def __init__(self, options: list[str], current: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self._pills: dict[str, QPushButton] = {}
        for opt in options:
            pill = QPushButton(opt)
            pill.setProperty("class", "pill")
            pill.setCheckable(True)
            pill.setCursor(Qt.CursorShape.PointingHandCursor)
            pill.clicked.connect(lambda _=False, o=opt: self.select(o))
            layout.addWidget(pill)
            self._pills[opt] = pill
        layout.addStretch(1)
        self.select(current, emit=False)

    def select(self, value: str, emit: bool = True) -> None:
        for opt, pill in self._pills.items():
            on = opt == value
            pill.setChecked(on)
            pill.setProperty("selected", "true" if on else "false")
            style = pill.style()
            style.unpolish(pill)
            style.polish(pill)
        if emit:
            self.selected.emit(value)


class SettingsPanel(QWidget):
    """Slide-over settings panel; persists every change to ``config``."""

    close_requested = Signal()
    cookies_enabled = Signal(bool)

    def __init__(
        self,
        config: c.IConfig,
        reduced_motion: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("SettingsPanel")
        self.setFixedWidth(380)
        self._config = config
        self._reduced_motion = reduced_motion
        self._open = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        head = QWidget()
        head.setObjectName("SpHead")
        head_layout = QHBoxLayout(head)
        head_layout.setContentsMargins(20, 16, 20, 14)
        gear = QLabel()
        gear.setPixmap(icons.pixmap("gear", "#9a9aa6", 16))
        head_layout.addWidget(gear)
        title = QLabel("Settings")
        title.setObjectName("SpTitle")
        head_layout.addWidget(title)
        head_layout.addStretch(1)
        close = QPushButton()
        close.setIcon(icons.icon("close", "#9a9aa6"))
        close.setFixedSize(30, 30)
        close.setCursor(Qt.CursorShape.PointingHandCursor)
        close.clicked.connect(self.close_requested.emit)
        head_layout.addWidget(close)
        root.addWidget(head)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        body = QWidget()
        self._body = QVBoxLayout(body)
        self._body.setContentsMargins(20, 6, 20, 24)
        self._body.setSpacing(0)
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        self._build_sections()

    # -- helpers --------------------------------------------------------------
    def _section_label(self, text: str) -> None:
        label = QLabel(text)
        label.setProperty("class", "sp-section-label")
        label.setContentsMargins(0, 18, 0, 8)
        self._body.addWidget(label)

    def _get(self, key: str, default: object = "") -> object:
        try:
            value = self._config.get(key)
        except Exception:
            return default
        return value if value is not None else default

    def _set(self, key: str, value: object) -> None:
        self._config.set(key, value)
        self._config.save()

    # -- sections -------------------------------------------------------------
    def _build_sections(self) -> None:
        # Binaries
        self._section_label("BINARIES")
        self.ytdlp_field = PathField(str(self._get("ytdlp_path")))
        self.ytdlp_field.path_changed.connect(lambda v: self._set("ytdlp_path", v))
        self._body.addWidget(self.ytdlp_field)
        self.ffmpeg_field = PathField(str(self._get("ffmpeg_path")))
        self.ffmpeg_field.path_changed.connect(lambda v: self._set("ffmpeg_path", v))
        self._body.addWidget(self.ffmpeg_field)

        # Output
        self._section_label("OUTPUT")
        self.base_dir = self._labeled_input(
            "Base directory", str(self._get("base_dir")), "base_dir"
        )
        self.video_dir = self._labeled_input(
            "Videos folder", str(self._get("video_subfolder", "videos")), "video_subfolder"
        )
        self.music_dir = self._labeled_input(
            "Music folder", str(self._get("audio_subfolder", "musics")), "audio_subfolder"
        )

        # Audio
        self._section_label("AUDIO")
        self.audio_pills = _Pills(["opus", "mp3", "m4a"], str(self._get("audio_format", "opus")))
        self.audio_pills.selected.connect(lambda v: self._set("audio_format", v))
        self._body.addWidget(self.audio_pills)

        # Subtitles & embedding
        self._section_label("SUBTITLES & EMBEDDING")
        langs = self._get("subtitle_langs", ["en", "tr"])
        langs_str = ",".join(langs) if isinstance(langs, list) else str(langs)
        self.sub_langs = self._labeled_input("Subtitle languages", langs_str, None, mono=True)
        self.sub_langs.textChanged.connect(
            lambda v: self._set("subtitle_langs", [s.strip() for s in v.split(",") if s.strip()])
        )
        self.embed_subs = self._toggle_row("Embed subtitles", "embed_subs")
        self.embed_thumb = self._toggle_row("Embed thumbnail", "embed_thumbnail")
        self.embed_meta = self._toggle_row("Embed metadata", "embed_metadata")

        # Performance
        self._section_label("PERFORMANCE")
        self.fragments = self._slider_row(
            "Concurrent fragments",
            1,
            16,
            _as_int(self._get("concurrent_fragments", 4), 4),
            "concurrent_fragments",
        )
        self.max_downloads = self._slider_row(
            "Max concurrent downloads",
            1,
            6,
            _as_int(self._get("max_concurrent_downloads", 2), 2),
            "max_concurrent_downloads",
        )

        # Cookies
        self._section_label("COOKIES")
        self.cookies_toggle = self._toggle_row(
            "Use cookies for sign-in content", "cookies_enabled", on_change=self._on_cookies
        )
        self.cookie_source = _Pills(
            ["firefox", "chrome", "edge", "file…"], str(self._get("browser_choice", "chrome"))
        )
        self.cookie_source.selected.connect(lambda v: self._set("browser_choice", v))
        self._body.addWidget(self.cookie_source)
        self._note = QWidget()
        self._note.setObjectName("SpNote")
        note_layout = QHBoxLayout(self._note)
        note_layout.setContentsMargins(11, 9, 11, 9)
        note = QLabel(
            "Cookies grant full account access. They are read locally, never stored by "
            "this app, and only passed to yt-dlp for the download session."
        )
        note.setWordWrap(True)
        note_layout.addWidget(note)
        self._body.addWidget(self._note)
        cookies_on = bool(self._get("cookies_enabled", False))
        self.cookie_source.setVisible(cookies_on)
        self._note.setVisible(cookies_on)

        # Maintenance
        self._section_label("MAINTENANCE")
        self.update_btn = QPushButton("Update yt-dlp")
        self.update_btn.setObjectName("SpUpdate")
        self.update_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._body.addWidget(self.update_btn)
        version = QLabel("yt-dlp 2026.05.21 · GUI 0.3.0")
        version.setObjectName("SpVersion")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._body.addWidget(version)
        self._body.addStretch(1)

    def _labeled_input(
        self, label: str, value: str, key: str | None, mono: bool = False
    ) -> QLineEdit:
        lbl = QLabel(label)
        lbl.setProperty("class", "sp-label")
        lbl.setContentsMargins(0, 4, 0, 4)
        self._body.addWidget(lbl)
        field = QLineEdit(value)
        field.setProperty("class", "sp-input sp-input-mono" if mono else "sp-input")
        if key is not None:
            field.textChanged.connect(lambda v, k=key: self._set(k, v))
        self._body.addWidget(field)
        return field

    def _toggle_row(self, label: str, key: str, on_change: object | None = None) -> Toggle:
        row = QHBoxLayout()
        lbl = QLabel(label)
        lbl.setProperty("class", "sp-label")
        row.addWidget(lbl, 1)
        toggle = Toggle(bool(self._get(key, False)), self._reduced_motion)

        def _handler(checked: bool, k: str = key) -> None:
            self._set(k, checked)
            if on_change is not None:
                on_change(checked)  # type: ignore[operator]

        toggle.toggled.connect(_handler)
        row.addWidget(toggle)
        wrapper = QWidget()
        wrapper.setLayout(row)
        self._body.addWidget(wrapper)
        return toggle

    def _slider_row(self, label: str, lo: int, hi: int, value: int, key: str) -> QSlider:
        lbl = QLabel(label)
        lbl.setProperty("class", "sp-label")
        lbl.setContentsMargins(0, 4, 0, 4)
        self._body.addWidget(lbl)
        row = QHBoxLayout()
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(lo, hi)
        slider.setValue(value)
        readout = QLabel(str(value))
        readout.setObjectName("SliderVal")
        slider.valueChanged.connect(lambda v: readout.setText(str(v)))
        slider.valueChanged.connect(lambda v, k=key: self._set(k, v))
        row.addWidget(slider, 1)
        row.addWidget(readout)
        wrapper = QWidget()
        wrapper.setLayout(row)
        self._body.addWidget(wrapper)
        return slider

    def _on_cookies(self, enabled: bool) -> None:
        self.cookie_source.setVisible(enabled)
        self._note.setVisible(enabled)
        self.cookies_enabled.emit(enabled)

    # -- open / close ---------------------------------------------------------
    def is_open(self) -> bool:
        return self._open

    def set_open(self, is_open: bool) -> None:
        self._open = is_open
        self.setVisible(is_open)

    def enable_cookies_module(self) -> None:
        """Open settings with the cookie toggle on (from media card link)."""
        self.cookies_toggle.set_checked(True)
