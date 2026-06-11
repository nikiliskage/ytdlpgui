# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - Unreleased

### Added
- Project scaffolding: core contracts (`app/core/contracts.py`), plans, and design handoff.
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
- 134 unit/UI tests; ruff + mypy clean.

### Planned (see `plans/`)
- Integration (`app/main.py` wiring real cores via DI) + PyInstaller packaging (Faz 2)
