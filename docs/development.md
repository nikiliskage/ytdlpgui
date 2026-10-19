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

One command builds both (needs Inno Setup 6: `winget install JRSoftware.InnoSetup`):

```powershell
powershell -ExecutionPolicy Bypass -File tools\build_installer.ps1
# -> dist\ytdlpgui.exe
# -> installer\Output\ytdlpgui-setup-<version>.exe
```

The script takes the version from `app/__init__.py` and finds `ISCC.exe` itself (PATH, the
registry — per-user installs live under `%LocalAppData%\Programs\Inno Setup 6` — or the default
folders). Options: `-SkipExe` reuses an existing `dist\ytdlpgui.exe`, `-Iscc <path>` points at a
specific compiler, `-Python <path>` picks the interpreter that runs PyInstaller (default:
`.venv\Scripts\python.exe` if present).

Manual equivalent:

```powershell
pyinstaller ytdlpgui.spec
& "<Inno Setup 6>\ISCC.exe" /DMyAppVersion=0.2.2 installer\ytdlpgui.iss
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
