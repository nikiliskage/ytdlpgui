# Getting Started

## Requirements

This app does **not** bundle the binaries — you provide them (keeps the download small and
avoids antivirus/SmartScreen false positives and ffmpeg licensing concerns):

| Binary | Source | Needed for |
| --- | --- | --- |
| **yt-dlp.exe** | <https://github.com/yt-dlp/yt-dlp/releases> | Everything |
| **ffmpeg.exe** | <https://www.gyan.dev/ffmpeg/builds/> | Merging video+audio and audio conversion |
| **deno.exe** | <https://github.com/denoland/deno/releases/latest> | YouTube (JavaScript challenge — without it downloads fail with HTTP 403) |

Put all three **next to the app** (the install folder, by default
`%LocalAppData%\Programs\yt-dlp-gui`), or point to them later in **Settings → Binaries**. The app
looks only in those two places — never in your PATH or any other folder. For ffmpeg and deno,
download the zip and take just the `.exe` (`bin\ffmpeg.exe`, `deno.exe`).

!!! warning "deno is required for YouTube"
    YouTube protects its download links with a JavaScript challenge that yt-dlp solves with deno.
    Without `deno.exe`, YouTube downloads fail with **HTTP 403 Forbidden** even though fetching
    works. Upgrading from an earlier build? Add `deno.exe` next to the app.

The installer shows these steps after installing, lists any file still missing from the install
folder, and offers to open it; the same guide is saved there as `README - binaries.txt`.

## Install

=== "Installer (recommended)"

    Download **`ytdlpgui-setup-0.2.0.exe`** from the
    [Releases page](https://github.com/nikiliskage/ytdlpgui/releases) and run it. It installs
    per-user (no admin) to `%LocalAppData%\Programs\yt-dlp-gui`, with a Start Menu shortcut, and
    asks you to accept a short license/disclaimer.

    !!! note "SmartScreen"
        The unsigned installer may trigger a Windows SmartScreen prompt — choose
        **More info → Run anyway**.

=== "From source (development)"

    ```powershell
    git clone https://github.com/nikiliskage/ytdlpgui.git
    cd ytdlpgui
    pip install -r requirements-dev.txt
    python main.py
    ```

## First run

1. The app opens with a **splash** that checks for `yt-dlp.exe` / `ffmpeg.exe` / `deno.exe`. If a binary is
   missing, a banner tells you and links to **Settings → Binaries**.
2. Paste a video URL into the **omni-bar** and press **Fetch**.
3. Pick a quality chip (or open the advanced format table), then **Add to queue**. A playlist
   link shows a checklist of its videos instead — see [Playlists](user-guide.md#playlists).
4. Watch progress in the **download dock**; manage jobs in the **queue panel**.

Downloads default to `Documents\yt-dlp-gui\video` and `\audio` — change them in
**Settings → Output** (Browse to any folder).

Next: the full [User Guide](user-guide.md).
