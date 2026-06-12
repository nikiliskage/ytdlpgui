# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - Unreleased

### Added
- Project scaffolding: core contracts layer (`app/core/contracts.py`).
- Tooling: pytest + pytest-qt, ruff, mypy, GitHub Actions CI (Windows), shared test
  fixtures/mocks, project documentation (README, SECURITY, ARCHITECTURE).
- **Core (Stream A):** `config.py` (JSON-persisted settings, migration-safe) and `paths.py`
  (yt-dlp/ffmpeg resolution, version detection, console-hiding subprocess helper, `-U` update).
- **yt-dlp layer (Stream B):** `command_builder.py` (Builder), `format_fetcher.py`
  (`-J`/`--flat-playlist` → MediaInfo + formats/playlist), `ytdlp_runner.py` (QProcess +
  progress-template parsing with line buffering), `errors.py` (stderr → friendly AppError).
- **Queue (Stream C):** `queue_manager.py` — up to 2 concurrent downloads (Command + State),
  cancel/retry, playlist add-many.
- **UI (Stream D):** full PySide6 UI per the design handoff — frameless window, splash with
  binary/version checks, omni-bar, media card (segmented modes, quality chips, format table),
  download dock with QPainter progress rings, queue panel, settings slide-over; dark + purple
  theme (`app/resources/theme.qss`).
- **Integration (Faz 2):** `app/main.py` (+ root `main.py`) wires the real `Config`,
  `FormatFetcher`, and `YtDlpRunner` factory into the UI via DI, with a splash that runs
  the real yt-dlp/ffmpeg version checks. Concurrency-limited queue in the main window
  (default max 2, others wait and auto-start). PyInstaller spec (`ytdlpgui.spec`,
  single-file GUI; binaries stay external).
- Subtitle language selection: Settings offers common languages (pick up to 2); the media card
  shows single-select chips built from your configured languages. A language is selectable only
  when the video has a manually-uploaded subtitle in it — the rest are greyed out (auto-translated
  captions are rate-limited by YouTube and unreliable, so they aren't offered). Subtitle downloads
  skip the media (`--skip-download`) and write only the chosen language. `MediaInfo` carries the
  video's available manual subtitle languages.
- Per-folder **Save** buttons for the Videos/Music output folders (changes persist on click —
  or Enter — with a brief purple "Saved" confirmation; unsaved edits are discarded on reopen).
- New widget: `SubtitleChips` (single-select subtitle-language chips).
- Settings "About" section (app name + version, short description, link to the yt-dlp project).
- 152 unit/UI tests; ruff + mypy clean; app launches and resolves binaries (smoke-verified).

### Changed
- Video downloads now prefer AAC (m4a) audio so the merged mp4 plays in all players (avoids the
  silent Opus-in-mp4 case); **Best audio** keeps the source codec instead of always re-encoding
  to Opus.
- Quality presets 1080p/720p/480p now actually apply (the chip ids matched the preset table).
- Settings panel: more vertical spacing; Videos/Music inputs aligned with Base directory; subtitle
  languages are a multi-select (capped at 2) instead of a free-text field.
- The media-card destination label reflects the configured output folder name.
- The media card is a fixed width matching the omni bar, so switching
  Video/Audio/Subtitle modes (different chip counts) no longer shifts the
  centred content. The Audio "Best" chip is relabelled to match the Video one.
- Removed the redundant Settings "Audio format" section — the media-card audio
  chip already chooses the format, and the setting was always overridden by it.
- A fixed Fusion dark theme/palette is applied app-wide so the UI no longer follows the OS
  light/dark setting (native window chrome and disabled controls stay dark).

### Fixed
- Cancelling (or a failed job) now deletes that job's partial files (`.part`, `.ytdl`, fragments)
  from the output folder, scoped to the job so a concurrent download is never touched.
- Queue panel scrolls when the list is long instead of squashing rows on top of each other.
- Format table no longer shows the native Windows accent selection bar or per-cell focus
  rectangle — only the themed purple row highlight (Fusion style + no-focus delegate).
- Failed downloads now show yt-dlp's actual error line (with the full raw error on hover) instead
  of a generic "unexpected error" message.
- "Max concurrent downloads" now takes effect immediately when changed (it was read only at
  startup, so the slider did nothing until a restart).
- Subtitle-only downloads no longer pass `--embed-thumbnail`/`--embed-metadata` (there is no media
  file to embed into).
- The "Update yt-dlp" button now actually runs `yt-dlp -U` in the background and reports the result
  inline (up to date / updated / failed) — previously it was wired to nothing.
