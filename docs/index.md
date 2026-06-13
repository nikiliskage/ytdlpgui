---
hide:
  - navigation
  - toc
---

<div class="ytg-hero" markdown>

<img class="ytg-logo" src="assets/logo.svg" alt="yt-dlp GUI logo" />

# yt-dlp GUI

<span class="ytg-badge">Latest: v0.1.0</span>

<p class="ytg-tagline">
A dark-themed PySide6 desktop GUI for <a href="https://github.com/yt-dlp/yt-dlp">yt-dlp</a> (Windows-first).
Paste a link, pick a <strong>real available format</strong>, and download — with a built-in queue,
cookie support for sign-in / age-restricted content, audio extraction, subtitles, and one-click yt-dlp self-update.
</p>

<div class="ytg-cta" markdown>
[Download :material-download:](https://github.com/nikiliskage/ytdlpgui/releases){ .md-button .md-button--primary }
[Get Started :material-rocket-launch:](getting-started.md){ .md-button }
</div>

</div>

## Why this GUI? { .ytg-section-title }

Using yt-dlp from the command line, two things are annoying:

1. Guessing format strings → *"Requested format is not available"*.
2. Age-restricted / sign-in videos failing.

This GUI fixes both: it **fetches the video's real available formats** into a clickable list,
and offers an **optional cookie module** (read locally, never stored) for sign-in content.

## Features { .ytg-section-title }

<div class="ytg-features" markdown>
<div class="ytg-grid" markdown>

<div class="ytg-card" markdown>
<span class="ytg-icon">:material-format-list-bulleted:</span>
<div class="ytg-body" markdown>
### Real-format selector
Quality chips plus an advanced format table built from the video's actual formats. Video
downloads prefer AAC audio so the resulting mp4 plays everywhere.
</div>
</div>

<div class="ytg-card" markdown>
<span class="ytg-icon">:material-tray-full:</span>
<div class="ytg-body" markdown>
### Download queue
Up to 2 concurrent downloads with cancel and retry. Cancelling (or a failed job) cleans up the
partial files it left behind.
</div>
</div>

<div class="ytg-card" markdown>
<span class="ytg-icon">:material-music:</span>
<div class="ytg-body" markdown>
### Audio extraction
**Best audio** keeps the source codec, or convert to opus / mp3 / m4a — your choice per
download.
</div>
</div>

<div class="ytg-card" markdown>
<span class="ytg-icon">:material-subtitles:</span>
<div class="ytg-body" markdown>
### Subtitles
Pick up to two languages; the picker greys out languages a video doesn't actually offer
as manual subtitles.
</div>
</div>

<div class="ytg-card" markdown>
<span class="ytg-icon">:material-cookie:</span>
<div class="ytg-body" markdown>
### Cookie module
**Firefox** (`--cookies-from-browser`) or a **cookies.txt** file for sign-in / age-restricted
content — read locally, never stored or transmitted.
</div>
</div>

<div class="ytg-card" markdown>
<span class="ytg-icon">:material-update:</span>
<div class="ytg-body" markdown>
### One-click update
Update yt-dlp itself (`yt-dlp -U`) from inside the app and see the result inline.
</div>
</div>

</div>
</div>

---

!!! info "You provide the binaries"
    This app does **not** bundle `yt-dlp.exe` or `ffmpeg.exe` — you supply them. This keeps the
    download small and avoids antivirus/SmartScreen false positives and ffmpeg licensing concerns.
    See [Getting Started](getting-started.md).

!!! warning "Legal"
    You are responsible for complying with the terms of service of the sites you download from and
    with applicable copyright law. This tool is for personal, lawful use.
