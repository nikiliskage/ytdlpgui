"""Right-hand settings slide-over with all sections.

Every control writes through to the injected ``config`` (IConfig-like) on change.
Sections: Binaries / Output / Subtitles & embedding / Performance (concurrent
fragments + max concurrent downloads) / Cookies / Maintenance / About.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QProcess, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from app import __version__, icons
from app.core import contracts as c
from app.ui_state import SUBTITLE_LANGS
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


class _MultiPills(QWidget):
    """Multi-select pill grid (capped) bound to a list config value.

    Toggling a pill flips it in/out of the selection and emits the full ordered
    list; selection is discrete so it persists immediately (no Save button). At
    most ``max_selected`` pills can be active at once.
    """

    changed = Signal(list)  # emits list[str] of selected codes, in option order

    def __init__(
        self,
        options: list[tuple[str, str]],
        selected: list[str],
        max_selected: int = 2,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        columns = 3
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(6)
        self._order = [code for code, _ in options]
        self._max = max_selected
        # Keep at most _max, preserving option order.
        kept = [code for code in self._order if code in selected][:max_selected]
        self._selected: set[str] = set(kept)
        self._pills: dict[str, QPushButton] = {}
        for i, (code, label) in enumerate(options):
            pill = QPushButton(label)
            pill.setProperty("class", "pill")
            pill.setCheckable(True)
            pill.setCursor(Qt.CursorShape.PointingHandCursor)
            pill.clicked.connect(lambda _=False, code=code: self._toggle(code))
            grid.addWidget(pill, i // columns, i % columns, Qt.AlignmentFlag.AlignLeft)
            self._pills[code] = pill
        grid.setColumnStretch(columns, 1)  # trailing spacer keeps the grid left-packed
        self._refresh()

    def selected(self) -> list[str]:
        """Selected codes in the original option order."""
        return [code for code in self._order if code in self._selected]

    def _toggle(self, code: str) -> None:
        if code in self._selected:
            self._selected.discard(code)
        elif len(self._selected) < self._max:
            self._selected.add(code)
        # else: at the cap — leave selection unchanged; _refresh unchecks the pill.
        self._refresh()
        self.changed.emit(self.selected())

    def _refresh(self) -> None:
        for code, pill in self._pills.items():
            on = code in self._selected
            pill.setChecked(on)
            pill.setProperty("selected", "true" if on else "false")
            style = pill.style()
            style.unpolish(pill)
            style.polish(pill)


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
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedWidth(380)
        self._config = config
        self._reduced_motion = reduced_motion
        self._open = False
        # Per-field "discard unsaved edits" resetters, run when the panel opens.
        self._reset_fns: list[Callable[[], None]] = []
        # yt-dlp self-update process + captured output (None when idle).
        self._update_proc: QProcess | None = None
        self._update_out: list[str] = []

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
        scroll.setObjectName("SpScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body = QWidget()
        body.setObjectName("SpBody")
        self._body = QVBoxLayout(body)
        self._body.setContentsMargins(20, 10, 20, 28)
        self._body.setSpacing(7)
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        self._build_sections()

    # -- helpers --------------------------------------------------------------
    def _section_label(self, text: str) -> None:
        label = QLabel(text)
        label.setProperty("class", "sp-section-label")
        label.setContentsMargins(0, 16, 0, 6)
        self._body.addWidget(label)

    def _field_label(self, text: str) -> None:
        label = QLabel(text)
        label.setProperty("class", "sp-label")
        label.setContentsMargins(0, 6, 0, 4)
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
        self._field_label("yt-dlp")
        self.ytdlp_field = PathField(str(self._get("ytdlp_path")))
        self.ytdlp_field.path_changed.connect(lambda v: self._set("ytdlp_path", v))
        self._body.addWidget(self.ytdlp_field)
        self._field_label("ffmpeg")
        self.ffmpeg_field = PathField(str(self._get("ffmpeg_path")))
        self.ffmpeg_field.path_changed.connect(lambda v: self._set("ffmpeg_path", v))
        self._body.addWidget(self.ffmpeg_field)

        # Output
        self._section_label("OUTPUT")
        self._field_label("Base directory")
        self.base_dir = PathField(str(self._get("base_dir")), show_status=False, pick_dir=True)
        self.base_dir.path_changed.connect(lambda v: self._set("base_dir", v))
        self._body.addWidget(self.base_dir)
        self.video_dir = self._saved_input(
            "Videos folder", str(self._get("video_subfolder", "videos")), "video_subfolder"
        )
        self.music_dir = self._saved_input(
            "Music folder", str(self._get("audio_subfolder", "musics")), "audio_subfolder"
        )

        # Subtitles & embedding
        self._section_label("SUBTITLES & EMBEDDING")
        self._field_label("Subtitle languages (up to 2)")
        langs = self._get("subtitle_langs", ["en", "tr"])
        selected = [str(x) for x in langs] if isinstance(langs, list) else []
        self.sub_langs = _MultiPills(SUBTITLE_LANGS, selected)
        self.sub_langs.changed.connect(lambda v: self._set("subtitle_langs", v))
        self._body.addWidget(self.sub_langs)
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
        self.update_btn.clicked.connect(self._on_update)
        self._body.addWidget(self.update_btn)
        self._update_status = QLabel("")
        self._update_status.setProperty("class", "sp-sublabel")
        self._update_status.setWordWrap(True)
        self._update_status.setContentsMargins(0, 6, 0, 0)
        self._update_status.setVisible(False)
        self._body.addWidget(self._update_status)

        # About
        self._section_label("ABOUT")
        about_name = QLabel(f"yt-dlp GUI · v{__version__}")
        about_name.setProperty("class", "sp-label")
        self._body.addWidget(about_name)
        about_desc = QLabel("A desktop GUI for yt-dlp — paste a link, pick a format, download.")
        about_desc.setProperty("class", "sp-sublabel")
        about_desc.setWordWrap(True)
        self._body.addWidget(about_desc)
        about_links = QLabel(
            "MIT License · powered by "
            '<a style="color:#a855f7; text-decoration:none;" '
            'href="https://github.com/yt-dlp/yt-dlp">yt-dlp</a>'
        )
        about_links.setProperty("class", "sp-sublabel")
        about_links.setOpenExternalLinks(True)
        self._body.addWidget(about_links)
        self._body.addStretch(1)

    def _saved_input(self, label: str, value: str, key: str) -> QLineEdit:
        """Input + explicit Save button (same row layout/width as Base directory).

        The value is *not* written on every keystroke; it only persists when Save
        is clicked (or Enter pressed). So if the user types and walks away without
        saving, the previously stored location stays in effect.
        """
        lbl = QLabel(label)
        lbl.setProperty("class", "sp-label")
        lbl.setContentsMargins(0, 4, 0, 4)
        self._body.addWidget(lbl)

        row = QHBoxLayout()
        # Zero margins so the input's left edge lines up with the Base directory
        # box; without this the layout inherits the style's default insets and
        # the box drifts slightly to the right.
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        field = QLineEdit(value)
        field.setProperty("class", "sp-input")
        row.addWidget(field, 1)
        save = QPushButton("Save")
        save.setProperty("class", "sp-browse")
        save.setCursor(Qt.CursorShape.PointingHandCursor)
        # Match the Browse button width so the folder inputs align with Base
        # directory; fixed width also stops the box jumping on the "Saved" flash.
        save.setFixedWidth(82)

        def _set_saved(on: bool) -> None:
            save.setText("Saved" if on else "Save")
            save.setProperty("saved", "true" if on else "false")
            style = save.style()
            style.unpolish(save)
            style.polish(save)

        def _commit() -> None:
            text = field.text().strip()
            if not text:
                return  # never persist an empty folder name; keep the old one
            self._set(key, text)
            _set_saved(True)  # flash purple
            QTimer.singleShot(1200, lambda: _set_saved(False))  # back to gray

        save.clicked.connect(_commit)
        field.returnPressed.connect(_commit)  # Enter also saves
        row.addWidget(save)
        wrapper = QWidget()
        wrapper.setLayout(row)
        self._body.addWidget(wrapper)

        # Discard unsaved edits when the panel re-opens: snap back to whatever
        # is currently stored in config (the last saved value).
        def _reset() -> None:
            field.setText(str(self._get(key, value)))
            _set_saved(False)

        self._reset_fns.append(_reset)
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

    # -- yt-dlp self-update ---------------------------------------------------
    def _resolve_ytdlp_path(self) -> str:
        """Locate yt-dlp: configured path → paths.resolve_ytdlp() → PATH."""
        configured = str(self._get("ytdlp_path", "") or "")
        if configured:
            return configured
        try:
            from app.core.paths import resolve_ytdlp

            result = resolve_ytdlp()
            if result.found and result.path:
                return str(result.path)
        except Exception:
            pass
        import shutil

        return shutil.which("yt-dlp") or ""

    def _on_update(self) -> None:
        """Run ``yt-dlp -U`` in the background and report the result inline."""
        if self._update_proc is not None:
            return  # already running
        ytdlp = self._resolve_ytdlp_path()
        if not ytdlp:
            self._set_update_status("yt-dlp not found — set its path under Binaries.", ok=False)
            return
        self.update_btn.setEnabled(False)
        self.update_btn.setText("Updating…")
        self._set_update_status("Checking for updates…", ok=None)

        proc = QProcess(self)
        self._update_proc = proc
        self._update_out = []
        proc.readyReadStandardOutput.connect(
            lambda: self._update_out.append(
                bytes(proc.readAllStandardOutput().data()).decode("utf-8", "replace")
            )
        )
        proc.readyReadStandardError.connect(
            lambda: self._update_out.append(
                bytes(proc.readAllStandardError().data()).decode("utf-8", "replace")
            )
        )
        proc.finished.connect(self._on_update_done)
        proc.start(ytdlp, ["-U"])

    def _on_update_done(self, exit_code: int, _status: object) -> None:
        output = "".join(self._update_out)
        self._update_proc = None
        self.update_btn.setEnabled(True)
        self.update_btn.setText("Update yt-dlp")
        message, ok = self._update_message(exit_code, output)
        self._set_update_status(message, ok=ok)

    @staticmethod
    def _update_message(exit_code: int, output: str) -> tuple[str, bool]:
        """Classify ``yt-dlp -U`` output into a friendly (message, success) pair."""
        last = next((ln.strip() for ln in reversed(output.splitlines()) if ln.strip()), "")
        if exit_code == 0 and "up to date" in output.lower():
            return "yt-dlp is already up to date.", True
        if exit_code == 0:
            return last or "yt-dlp updated.", True
        return last or "Update failed.", False

    def _set_update_status(self, message: str, ok: bool | None) -> None:
        if ok is True:
            cls = "sp-status-ok"
        elif ok is False:
            cls = "sp-status-bad"
        else:
            cls = "sp-sublabel"
        self._update_status.setText(message)
        self._update_status.setProperty("class", cls)
        style = self._update_status.style()
        style.unpolish(self._update_status)
        style.polish(self._update_status)
        self._update_status.setVisible(True)

    def _on_cookies(self, enabled: bool) -> None:
        self.cookie_source.setVisible(enabled)
        self._note.setVisible(enabled)
        self.cookies_enabled.emit(enabled)

    # -- open / close ---------------------------------------------------------
    def is_open(self) -> bool:
        return self._open

    def set_open(self, is_open: bool) -> None:
        if is_open:
            # Re-opening shows the saved state; any edit left unsaved is dropped.
            for reset in self._reset_fns:
                reset()
        self._open = is_open
        self.setVisible(is_open)

    def enable_cookies_module(self) -> None:
        """Open settings with the cookie toggle on (from media card link)."""
        self.cookies_toggle.set_checked(True)
