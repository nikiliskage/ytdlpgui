# Security & Privacy

## No telemetry
This application does not collect, transmit, or phone home any usage data. Everything runs
locally on your machine.

## Cookies
The optional cookie module exists to download sign-in / age-restricted content.

- Cookies are **read locally** at download time (via `--cookies-from-browser` or a `cookies.txt`
  you select) and passed **only to yt-dlp**, which sends them only to the target site — exactly
  as your browser would.
- This app **never stores cookies on disk, never logs them, and never uploads them anywhere**.
- A cookie equals a live session token: **do not share** your `cookies.txt`. Anyone with it can
  access your account.
- Recommendation: use a **secondary account** for downloading. Heavy automated use with your main
  account can occasionally trigger temporary rate limits from the provider.

Because this project is open source, you can verify the above in the code (search for
`--cookies-from-browser` / `--cookies`).

## Binaries
`yt-dlp.exe` and `ffmpeg.exe` are **not bundled**; you supply them from their official sources.
The app only executes the binaries you point it to.

## Reporting an issue
This is a personal/hobby project. To report a security concern, open a private issue on the
repository or contact the maintainer.
