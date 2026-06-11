# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for ytdlpgui — single-file, GUI-only.

yt-dlp.exe and ffmpeg.exe are NOT bundled; the user provides them (the app
resolves them from config / C:\\yt-dlp / PATH at runtime). Only the GUI and its
QSS theme are packaged.

Build:  pyinstaller ytdlpgui.spec
"""

block_cipher = None


a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("app/resources/theme.qss", "app/resources"),
    ],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="ytdlpgui",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # windowed app (no console flash)
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
