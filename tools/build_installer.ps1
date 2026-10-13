<#
.SYNOPSIS
    Build dist\ytdlpgui.exe (PyInstaller) and the setup installer (Inno Setup).

.DESCRIPTION
    Run from anywhere:  powershell -ExecutionPolicy Bypass -File tools\build_installer.ps1

    - The version comes from app\__init__.py (__version__) and is passed to the
      Inno Setup script, so the installer name always matches the app.
    - ISCC.exe is located automatically: -Iscc, the ISCC env var, PATH, the
      registry (per-user and machine-wide installs), then the default folders.
      Install Inno Setup with:  winget install JRSoftware.InnoSetup

    Output: installer\Output\ytdlpgui-setup-<version>.exe

.PARAMETER SkipExe
    Reuse the existing dist\ytdlpgui.exe instead of rebuilding it.

.PARAMETER Python
    Python used to run PyInstaller (default: .venv\Scripts\python.exe if it
    exists, else "python").

.PARAMETER Iscc
    Explicit path to ISCC.exe.
#>
param(
    [switch]$SkipExe,
    [string]$Python = "",
    [string]$Iscc = ""
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

# --- version -------------------------------------------------------------------
$initText = Get-Content (Join-Path $root "app\__init__.py") -Raw
if ($initText -notmatch '__version__\s*=\s*"([^"]+)"') {
    throw "Could not read __version__ from app\__init__.py"
}
$version = $Matches[1]
Write-Host "yt-dlp GUI $version" -ForegroundColor Cyan

# --- 1. exe (PyInstaller) --------------------------------------------------------
$exe = Join-Path $root "dist\ytdlpgui.exe"
if (-not $SkipExe) {
    if (-not $Python) {
        $venvPython = Join-Path $root ".venv\Scripts\python.exe"
        $Python = if (Test-Path $venvPython) { $venvPython } else { "python" }
    }
    Write-Host "Building exe with $Python -m PyInstaller ..." -ForegroundColor Cyan
    & $Python -m PyInstaller --noconfirm --clean ytdlpgui.spec
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed (exit $LASTEXITCODE)" }
}
if (-not (Test-Path $exe)) { throw "Missing $exe - build it first (run without -SkipExe)." }

# --- 2. find ISCC.exe ------------------------------------------------------------
function Find-Iscc {
    param([string]$Explicit)
    $candidates = @()
    if ($Explicit) { $candidates += $Explicit }
    if ($env:ISCC) { $candidates += $env:ISCC }
    $cmd = Get-Command iscc.exe -ErrorAction SilentlyContinue
    if ($cmd) { $candidates += $cmd.Source }
    $uninstallKeys = @(
        "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Inno Setup 6_is1",
        "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Inno Setup 6_is1",
        "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\Inno Setup 6_is1"
    )
    foreach ($key in $uninstallKeys) {
        $item = Get-ItemProperty $key -ErrorAction SilentlyContinue
        if ($item -and $item.InstallLocation) {
            $candidates += (Join-Path $item.InstallLocation "ISCC.exe")
        }
    }
    $candidates += @(
        (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"),
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
    )
    foreach ($c in $candidates) {
        if ($c -and (Test-Path $c)) { return (Resolve-Path $c).Path }
    }
    return $null
}

$isccPath = Find-Iscc -Explicit $Iscc
if (-not $isccPath) {
    throw "ISCC.exe (Inno Setup 6) not found. Install it with 'winget install JRSoftware.InnoSetup' or pass -Iscc <path>."
}

# --- 3. installer (Inno Setup) -----------------------------------------------------
Write-Host "Building installer with $isccPath ..." -ForegroundColor Cyan
& $isccPath "/DMyAppVersion=$version" (Join-Path $root "installer\ytdlpgui.iss")
if ($LASTEXITCODE -ne 0) { throw "ISCC failed (exit $LASTEXITCODE)" }

$setup = Join-Path $root "installer\Output\ytdlpgui-setup-$version.exe"
Write-Host "Done: $setup" -ForegroundColor Green
