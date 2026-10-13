# User Guide

## The omni-bar

Paste a video URL and press **Fetch**. The app runs `yt-dlp -J` to read the
video's real metadata and available formats, then shows a media card. A playlist link opens the
playlist card instead (see [Playlists](#playlists)).

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

## Playlists

- Paste a **playlist link** (e.g. `youtube.com/playlist?list=…`) and press **Fetch**: the playlist
  card lists every video with a checkbox (all ticked; **Select all** toggles them).
- A **video link that is part of a playlist** (`watch?v=…&list=…`) opens just that video; the
  media card then offers **Open playlist**. (Not for YouTube *mixes* — `list=RD…` — which are
  endless, auto-generated lists.)
- For a **channel**, paste its *Videos* tab (`youtube.com/@name/videos`); the channel's home link
  lists tabs, not videos, so it shows "no downloadable videos".
- Pick one mode and quality for the whole selection, then **Add N to queue**. Each video becomes
  its own queue job (cancel / retry individually) and is saved as
  `<Video|Audio folder>\<Playlist name>\01 - <title>.<ext>` — numbered in playlist order.

## The download queue

- Up to **2 concurrent** downloads; the rest wait and auto-start as slots free up.
- **Cancel** a job — its partial files (`.part`, `.ytdl`, fragments) are cleaned up, scoped to
  that job so a concurrent download is never touched.
- **Retry** re-runs the job. (Cancelled or failed jobs have their partial files removed, so a
  retry downloads again from the start.)
- Failed downloads show yt-dlp's actual error line (full raw error on hover).
- The queue header has bulk actions: **Retry failed** (re-queue every failed job — e.g. a
  playlist's temporary HTTP 403s), **Clear failed** (failed and canceled jobs) and
  **Clear completed**.
- **Rename** (pencil icon on a finished job) edits the file name in place — **Enter** saves,
  **Esc** cancels. The extension is kept, invalid characters are replaced, and subtitle /
  thumbnail files with the same name are renamed too. If the name is taken, nothing is renamed
  and the row says so.
- **Right-click a dock item** for **Rename…**, **Open folder** (the folder the file is in) and
  **Show in queue**.

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

- **Binaries** — `yt-dlp.exe` / `ffmpeg.exe` / `deno.exe` (YouTube needs deno). Leave empty to use the ones next to the app; the
  app never searches your PATH.
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

??? question "\"yt-dlp not found\" / \"ffmpeg not found\""
    Put the `.exe` next to the app (the install folder) or set its path in
    **Settings → Binaries**. The app does not look in your PATH.

??? question "\"This yt-dlp is too old for the app\""
    Your `yt-dlp.exe` predates the option the app uses to hand it deno. Click
    **Update yt-dlp** (or replace the file with the latest release).

??? question "Download fails with 403 / format errors"
    For YouTube, yt-dlp needs **deno** to solve a JavaScript challenge — put `deno.exe` next to the
    app (or set it in **Settings → Binaries**). Your yt-dlp may also be outdated: click
    **Update yt-dlp** (or run `yt-dlp -U`). An occasional 403 is temporary — **Retry**.

??? question "Subtitle downloads show \"No subtitles in …\""
    The video has no manually-uploaded subtitle in that language (common for music). The job is
    marked failed instead of "done" so nothing is silently skipped.
