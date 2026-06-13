# User Guide

## The omni-bar

Paste a video URL and press **Fetch**. The app runs `yt-dlp -J` to read the
video's real metadata and available formats, then shows a media card.

## Choosing what to download

The media card has three modes:

- **Video** — quality chips (1080p / 720p / 480p / Best) or an advanced format table listing
  the actual formats. Video downloads prefer **AAC (m4a)** audio so the merged mp4 plays in
  every player.
- **Audio** — extract audio only. **Best audio** keeps the source codec; or convert to
  **opus / mp3 / m4a**.
- **Subtitle** — pick one of your configured languages. A language is selectable only when the
  video has a *manually-uploaded* subtitle for it (auto-translated captions are rate-limited by
  YouTube and unreliable, so they aren't offered). Subtitle downloads skip the media and write
  only the chosen language.

## The download queue

- Up to **2 concurrent** downloads; the rest wait and auto-start as slots free up.
- **Cancel** a job — its partial files (`.part`, `.ytdl`, fragments) are cleaned up, scoped to
  that job so a concurrent download is never touched.
- **Retry** re-runs the job. (Cancelled or failed jobs have their partial files removed, so a
  retry downloads again from the start.)
- Failed downloads show yt-dlp's actual error line (full raw error on hover).

## Cookies (sign-in / age-restricted)

Enable the cookie module in **Settings → Cookies** to fetch and download content that requires
being signed in. A one-time disclaimer is shown the first time you turn it on.

- Choose **Firefox** (`--cookies-from-browser`) or a **cookies.txt** file. Chrome/Edge can't be
  read directly (Chromium app-bound cookie encryption) — export a `cookies.txt` for those.
- Cookies are read locally (at fetch *and* download time) and passed only to yt-dlp — never
  stored, logged, or uploaded. See [Security](security.md).

!!! tip
    Prefer a **secondary account**. Heavy automated use with your main account can occasionally
    trigger temporary rate limits.

## Settings

All path fields below are **read-only — set them with Browse** (you can't mistype or paste a path).

- **Binaries** — `yt-dlp.exe` / `ffmpeg.exe` (the app also finds them next to itself).
- **Output** — separate **Video** and **Audio** folders; default `Documents\yt-dlp-gui\video` /
  `\audio`, Browse to change.
- **Subtitles & embedding** — up to 2 languages; embed subtitles / thumbnail / metadata.
- **Performance** — concurrent fragments + max concurrent downloads (takes effect immediately).
- **Cookies** — enable + choose Firefox or a cookies.txt file.
- **About** — app version, author credit, and a link to the yt-dlp project.

## Updating yt-dlp

Click **Update yt-dlp** to run `yt-dlp -U` in the background. The result (up to date / updated /
failed) is reported inline.

## Troubleshooting

??? question "Age-restricted / sign-in video won't fetch or download"
    Enable the cookie module (Settings → Cookies) and choose **Firefox** or a **cookies.txt** file.
    Chrome/Edge can't be read directly (app-bound cookie encryption) — export a `cookies.txt` for
    those. If it still fails, the site may require a PO token — see the
    [yt-dlp wiki](https://github.com/yt-dlp/yt-dlp/wiki).

??? question "\"ffmpeg not found\""
    Set its path in **Settings → Binaries**.

??? question "Download fails with 403 / format errors"
    Your yt-dlp may be outdated. Click **Update yt-dlp** (or run `yt-dlp -U`) and try again.
