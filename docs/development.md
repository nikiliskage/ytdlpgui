# Development

## Tech stack

- **Python 3.12**, **PySide6** (Qt Widgets) + QSS, Windows-first.
- Drives `yt-dlp.exe` as a subprocess via `QProcess` with a structured `--progress-template`.
- Tooling: **ruff** (lint + format), **mypy** (types), **pytest** + **pytest-qt** (tests),
  GitHub Actions CI (Windows).

## Setup

```powershell
git clone https://github.com/nikiliskage/ytdlpgui.git
cd ytdlpgui
pip install -r requirements-dev.txt
python main.py
```

## Verification

Run the same checks CI runs before calling anything "done":

```powershell
ruff check .
ruff format --check .
mypy app
pytest
```

## Building the executable & installer

A single GUI `.exe` is produced with PyInstaller (binaries stay external), then wrapped into a
per-user Windows installer with [Inno Setup](https://jrsoftware.org/isinfo.php):

```powershell
pyinstaller ytdlpgui.spec
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\ytdlpgui.iss
# -> installer\Output\ytdlpgui-setup-0.1.0.exe
```

## Building these docs

The site is [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/).

```powershell
pip install -r requirements-docs.txt
mkdocs serve   # live preview at http://127.0.0.1:8000
mkdocs build   # static site into ./site
```

See [Architecture](architecture.md) for the module map and design patterns.

## Contributing

1. Branch from `main` using a Conventional-Commits-aligned name
   (`feat/...`, `fix/...`, `docs/...`).
2. Keep commits atomic; messages follow `type: description`.
3. Make sure verification is green, then open a PR.
