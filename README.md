# yt-dlp GUI

A dark-themed **PySide6 desktop GUI for [yt-dlp](https://github.com/yt-dlp/yt-dlp)** (Windows-first).
Paste a link, pick a real available format, and download — with a built-in queue, cookie
support for sign-in/age-restricted content, audio extraction (opus by default), subtitles,
and one-click yt-dlp self-update.

> **Status:** in development (`0.1.0`). See [plans/](plans/) for the architecture and roadmap.

## Why
Using yt-dlp from the command line, two things are annoying:
1. Guessing format strings → *"Requested format is not available"*.
2. Age-restricted / sign-in videos failing.

This GUI fixes both: it **fetches the video's real available formats** into a clickable list,
and offers an **optional cookie module** (read locally, never stored) for sign-in content.

## Requirements
This app does **not** bundle the binaries — you provide them (keeps the download small and
avoids antivirus/SmartScreen false positives and ffmpeg licensing concerns):

- **yt-dlp.exe** — https://github.com/yt-dlp/yt-dlp/releases
- **ffmpeg.exe** — https://www.gyan.dev/ffmpeg/builds/ (needed for merging video+audio and audio conversion)

Put both in `C:\yt-dlp\` (the default the app looks for) or point to them in **Settings → Binaries**.

## Install (from source, during development)
```powershell
pip install -r requirements-dev.txt
python main.py
```

## Packaged build
A single GUI `.exe` is produced with PyInstaller (binaries stay external):
```powershell
pyinstaller ytdlpgui.spec
```
> The unsigned `.exe` may trigger a Windows SmartScreen prompt ("More info → Run anyway").

## Features
- Real-format selector (quality chips + advanced format table)
- Download queue (up to 2 concurrent), cancel / retry, resume (`--continue`)
- Audio extraction (opus / mp3 / m4a), subtitles, thumbnail/metadata embedding
- Optional cookie module (`--cookies-from-browser` or `cookies.txt`)
- One-click "Update yt-dlp" (`yt-dlp -U`)

## FAQ
- **Age-restricted video won't download?** Enable the cookie module (Settings → Cookies) and pick
  your browser. If it still fails, the site may require a PO token — see the
  [yt-dlp wiki](https://github.com/yt-dlp/yt-dlp/wiki).
- **"ffmpeg not found"?** Set its path in Settings → Binaries.
- **Cookies safe?** They are read locally and passed only to yt-dlp for the download — never stored
  or transmitted by this app. See [SECURITY.md](SECURITY.md). Prefer a secondary account.

## Legal
You are responsible for complying with the terms of service of the sites you download from and
with applicable copyright law. This tool is for personal, lawful use.

## License
[MIT](LICENSE).
