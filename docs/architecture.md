# Architecture

> Forward-looking developer reference for the ytdlpgui codebase.

## Overview
A PySide6 (Qt Widgets) desktop GUI that drives `yt-dlp.exe` as a subprocess (`QProcess`).
Progress is parsed from a structured `--progress-template`. The UI follows an
"Omni-bar · Media Card · Download Dock" layout (no tabs/sidebar) with a frameless window
and a startup splash that verifies the yt-dlp/ffmpeg binaries.

## Module map
```
app/
  core/
    contracts.py       # Shared data models + interfaces (Protocols). Single source of truth.
    config.py          # JSON-persisted settings (Stream A)
    paths.py           # yt-dlp/ffmpeg resolution + versions + CREATE_NO_WINDOW + -U update (A)
    command_builder.py # Builds yt-dlp arg lists (Builder) (Stream B)
    format_fetcher.py  # `-J` metadata/formats + `--flat-playlist` (async) (B)
    ytdlp_runner.py    # QProcess wrapper + progress/stderr parsing (Facade+Adapter) (B)
    errors.py          # stderr -> AppError mapping (B)
    queue_manager.py   # Up to 2 concurrent jobs (Command + State) (Stream C)
  main_window.py, splash.py, widgets/, resources/, icons.py, ui_state.py  # UI (Stream D)
tests/                 # pytest (unit / integration[@network] / ui[pytest-qt]) + fixtures (Stream T)
```

## Design patterns (per refactoring.guru)
- **Builder** — `YtDlpCommandBuilder` assembles argument lists step by step.
- **Strategy** — download mode (video/audio/subtitle) and cookie source.
- **Command + State** — each `DownloadJob` in the queue; lifecycle `JobState`.
- **Facade + Adapter** — `ytdlp_runner` hides QProcess + arg building + parsing behind a clean
  interface; adapts the yt-dlp CLI to a typed Python surface.
- **Observer** — progress/state via callbacks (bridged to Qt signals).
- **Parameter Object** — `DownloadOptions` carries all per-download settings.
- **Singleton (careful)** — `Config`, passed via dependency injection, not global access.

## Data flow
1. User pastes a URL → **FormatFetcher** runs `yt-dlp -J` → `(MediaInfo, list[FormatInfo])`.
2. User picks a quality/format → a `DownloadOptions` is built and added to the **QueueManager**.
3. For each free slot (max 2), the queue uses a **RunnerFactory** to create a **YtDlpRunner**,
   wires `set_callbacks(...)`, and `start()`s it.
4. The runner parses `--progress-template` lines into `Progress` and reports via callbacks;
   `stderr` is mapped to `AppError` on failure.
5. The UI's **Download Dock** renders progress (QPainter rings); the queue panel lists details.

## Key invariants
- `contracts.py` is the frozen interface layer; modules depend on it, not on each other.
- Binaries are user-provided; subprocess calls hide the console window on Windows.
- Cancel/failure deletes that job's partial files (`.part`/`.ytdl`/fragments), scoped per job.
  (`--continue` is passed but has no effect on retry today, since partials are removed — true
  resume is deferred; see `plans/features/resumable-downloads.md`.)
- Errors are inline bands, never modal dialogs.
