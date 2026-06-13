# Getting Started

## Requirements

This app does **not** bundle the binaries — you provide them (keeps the download small and
avoids antivirus/SmartScreen false positives and ffmpeg licensing concerns):

| Binary | Source | Needed for |
| --- | --- | --- |
| **yt-dlp.exe** | <https://github.com/yt-dlp/yt-dlp/releases> | Everything |
| **ffmpeg.exe** | <https://www.gyan.dev/ffmpeg/builds/> | Merging video+audio and audio conversion |

Put both **next to the app** — the app searches its own folder first — or point to them later in
**Settings → Binaries**. (`C:\yt-dlp` and your PATH are also checked as fallbacks.)

## Install

=== "Installer (recommended)"

    Download **`ytdlpgui-setup-0.1.0.exe`** from the
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

1. The app opens with a **splash** that checks for `yt-dlp.exe` / `ffmpeg.exe`. If a binary is
   missing, a banner tells you and links to **Settings → Binaries**.
2. Paste a video URL into the **omni-bar** and press **Fetch**.
3. Pick a quality chip (or open the advanced format table), then **Download**.
4. Watch progress in the **download dock**; manage jobs in the **queue panel**.

Downloads default to `Documents\yt-dlp-gui\video` and `\audio` — change them in
**Settings → Output** (Browse to any folder).

Next: the full [User Guide](user-guide.md).
