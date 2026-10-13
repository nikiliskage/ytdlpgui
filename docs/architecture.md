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
    format_fetcher.py  # `-J` metadata/formats; playlist links → PlaylistInfo (async) (B)
    filenames.py       # Windows-safe names, playlist file template, rename_output
    ytdlp_runner.py    # QProcess wrapper + progress/stderr parsing (Facade+Adapter) (B)
    errors.py          # stderr -> AppError mapping (B)
  main_window.py       # UI shell + the download queue (concurrency limit from config)
  splash.py, widgets/, resources/, icons.py, ui_state.py  # UI (Stream D)
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
2. User picks a quality/format → a `DownloadOptions` is built and queued by **MainWindow**.
3. For each free slot (`max_concurrent_downloads`, re-read on every pump so Settings apply
   immediately), the queue uses a **RunnerFactory** to create a **YtDlpRunner**, wires
   `set_callbacks(...)`, and `start()`s it. The runner reports `on_finished` exactly once —
   including when yt-dlp fails to start — so a slot is always freed.
4. The runner parses `--progress-template` lines into `Progress` and reports via callbacks;
   `stderr` is mapped to `AppError` on failure.
5. The UI's **Download Dock** renders progress (QPainter rings); the queue panel lists details.

## Key invariants
- `contracts.py` is the frozen interface layer; modules depend on it, not on each other.
- Binaries are user-provided; subprocess calls hide the console window on Windows.
- Binaries come only from the configured path or the app's own folder — never PATH. Fetch and
  download locate them via `paths.find_ytdlp/find_ffmpeg` (no subprocess); only the splash and
  Settings run `--version` (`resolve_*`). A missing yt-dlp fails the job/fetch with a clear message.
- Playlists are queued as one single-video job per item (`--no-playlist`), with the playlist
  index baked into the output template (`NN - %(title)s.%(ext)s`) under a playlist subfolder.
- The runner asks yt-dlp to `--print-to-file after_move:filepath` (unlike `--print`, this does
  not imply `--quiet`) so `output_files()` knows the final file for Rename.
- Cancel/failure deletes that job's partial files (`.part`/`.ytdl`/fragments), scoped per job.
  (`--continue` is passed but has no effect on retry today, since partials are removed — true
  resume is deferred; see `plans/features/resumable-downloads.md`.)
- Errors are inline bands, never modal dialogs.
