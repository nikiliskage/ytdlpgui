# yt-dlp GUI

A dark-themed **PySide6 desktop GUI for [yt-dlp](https://github.com/yt-dlp/yt-dlp)** (Windows-first).
Paste a link, pick a real available format, and download — with a built-in queue, playlist
downloads, renaming of finished files, cookie support for sign-in/age-restricted content, audio
extraction, subtitles, and one-click yt-dlp self-update.

> **Status:** in development (`0.2.2`).
>
> 📖 **Documentation:** <https://nikiliskage.github.io/ytdlpgui/>

![yt-dlp GUI — main window](docs/assets/screenshots/app.png)

## Why
Using yt-dlp from the command line, a few things are annoying:
1. Guessing format strings → *"Requested format is not available"*.
2. Age-restricted / sign-in videos failing.
3. Grabbing *part* of a playlist means hand-writing `--playlist-items` ranges.

This GUI fixes these: it **fetches the video's real available formats** into a clickable list,
offers an **optional cookie module** (read locally, never stored) for sign-in content, and lists a
**playlist's videos as a checklist** so you tick exactly the ones you want.

## Requirements
This app does **not** bundle the binaries — you provide them (keeps the download small and
avoids antivirus/SmartScreen false positives and ffmpeg licensing concerns). You need **three**
free programs:

| File | What it does | Where to get it |
| --- | --- | --- |
| **yt-dlp.exe** | The downloader | [yt-dlp releases](https://github.com/yt-dlp/yt-dlp/releases/latest) → `yt-dlp.exe` |
| **ffmpeg.exe** | Merges video + audio, converts audio | [gyan.dev builds](https://www.gyan.dev/ffmpeg/builds/) → `ffmpeg-release-essentials.zip` → `bin\ffmpeg.exe` |
| **deno.exe** | JavaScript runtime yt-dlp needs for **YouTube** | [deno releases](https://github.com/denoland/deno/releases/latest) → `deno-x86_64-pc-windows-msvc.zip` → `deno.exe` |

> [!IMPORTANT]
> **deno is required for YouTube.** YouTube protects its download links with a JavaScript
> challenge that yt-dlp solves with deno. Without `deno.exe`, every YouTube download fails with
> **HTTP 403 Forbidden** (fetching still works, so it looks like the download "just fails").
> Upgrading from an earlier build? Add `deno.exe` next to the app.

### Setting them up
1. Download the three files above (unzip ffmpeg and deno, take just the `.exe`).
2. Put all three **next to the app** — the install folder, by default
   `%LocalAppData%\Programs\yt-dlp-gui` (the installer offers to open it and lists what's
   missing). Or keep them anywhere and pick each one in **Settings → Binaries**.
3. Start the app: the splash shows ✓ for *Checking yt-dlp / ffmpeg / deno*. A ✗ means that file
   isn't where the app looks.

Those are the only two places the app looks — it never picks up a yt-dlp/ffmpeg/deno from your
PATH or another folder. (In a source checkout, the repo root counts as the app's folder.)
Keep yt-dlp current with **Settings → Update yt-dlp**; sites change often.

## Install (from source, during development)
```powershell
pip install -r requirements-dev.txt
# put yt-dlp.exe, ffmpeg.exe and deno.exe in the repo root (or set them in Settings → Binaries)
python main.py
```
Checks (same as CI): `ruff check . ; ruff format --check . ; mypy app ; pytest -m "not network"`.
See the [development guide](docs/development.md) for details.

## Packaged build
A single GUI `.exe` is produced with PyInstaller (binaries stay external):
```powershell
pyinstaller ytdlpgui.spec
```
A Windows **setup installer** (with a license/disclaimer you must accept, a Start Menu
shortcut, an uninstaller, and a closing page that explains the three binaries, lists any that are
missing from the install folder and offers to open it; installs per-user — no admin — under
`%LocalAppData%\Programs\yt-dlp-gui`, with downloads defaulting to `Documents\yt-dlp-gui\video`
and `\audio`) is built from `installer/ytdlpgui.iss` with
[Inno Setup 6](https://jrsoftware.org/isinfo.php) (`winget install JRSoftware.InnoSetup`).
One command builds the exe **and** the installer — it finds `ISCC.exe` itself and takes the
version from `app/__init__.py`:
```powershell
powershell -ExecutionPolicy Bypass -File tools\build_installer.ps1
# -> installer\Output\ytdlpgui-setup-<version>.exe
```
> The unsigned `.exe`/installer may trigger a Windows SmartScreen prompt ("More info → Run anyway").

## Features
- Real-format selector (quality chips + advanced format table); video downloads prefer AAC audio
  so the resulting mp4 plays everywhere
- Download queue — one download at a time, in order (reliable with YouTube); cancel / retry, plus
  **Retry failed** / **Clear failed** for the whole queue; cancelling (or a failed job) cleans up
  the partial files it left behind
- **Playlists** — paste a playlist link (or open the playlist from a video that's part of one),
  tick the videos you want, and each is queued as its own job into
  `<Video|Audio>\<Playlist name>\01 - Title.ext`
- **Rename** a finished download from the queue (its subtitle/thumbnail files follow along)
- Audio extraction — **Best audio** keeps the source codec, or convert to opus / mp3 / m4a
- Subtitles: pick languages (Settings, up to 2); the picker greys out languages a video doesn't offer
- Thumbnail / metadata embedding
- Cookie module for sign-in / age-restricted content — **Firefox** (`--cookies-from-browser`) or a
  **cookies.txt** file; applied at fetch *and* download time (read locally, never stored). A one-time
  disclaimer is shown before it's first enabled.
- Clear, actionable errors (age/sign-in, geo-block, rate-limit, HTTP 403/deno, ffmpeg, outdated
  yt-dlp, network) with an inline
  "Enable cookies" shortcut where relevant
- One-click "Update yt-dlp" (`yt-dlp -U`)

## FAQ
- **Age-restricted / sign-in video won't fetch or download?** Enable the cookie module
  (Settings → Cookies) and choose **Firefox** or a **cookies.txt** file. Chrome/Edge can't be read
  directly (Chromium app-bound cookie encryption) — export a `cookies.txt` for those. If it still
  fails, the site may require a PO token — see the [yt-dlp wiki](https://github.com/yt-dlp/yt-dlp/wiki).
- **YouTube downloads fail with "HTTP 403"?** Put `deno.exe` next to the app (see Requirements)
  and click **Update yt-dlp**. Occasional 403s are temporary — Retry.
- **"yt-dlp not found" / "ffmpeg not found"?** Put the `.exe` next to the app (the install folder),
  or set its path in Settings → Binaries. The app does not look in your PATH or in `C:\yt-dlp`.
- **How do I download only some videos of a playlist?** Paste the playlist link and untick the ones
  you don't want. For a `watch?v=…&list=…` link, the video opens first — click **Open playlist** on
  the media card. Files are numbered in playlist order inside a folder named after the playlist.
  For a channel, paste its *Videos* tab (`youtube.com/@name/videos`).
- **Can I rename a file after it downloaded?** Yes — click the pencil on the finished job in the
  queue (or right-click it in the dock → **Rename…**), type the new name, press Enter. The extension is kept and matching subtitle/thumbnail
  files are renamed too.
- **Cookies safe?** They are read locally and passed only to yt-dlp for the download — never stored
  or transmitted by this app. See [SECURITY.md](SECURITY.md). Prefer a secondary account.

## Legal
You are responsible for complying with the terms of service of the sites you download from and
with applicable copyright law. This tool is for personal, lawful use.

## License
[MIT](LICENSE).
