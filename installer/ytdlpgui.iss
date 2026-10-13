; Inno Setup script for yt-dlp GUI.
; Easiest: build the exe and this installer in one go (finds ISCC.exe itself and
; takes the version from app\__init__.py):
;
;   powershell -ExecutionPolicy Bypass -File tools\build_installer.ps1
;
; Manually: pyinstaller ytdlpgui.spec, then
;   ISCC.exe /DMyAppVersion=<version> installer\ytdlpgui.iss
;
; Output: installer\Output\ytdlpgui-setup-<version>.exe

#define MyAppName "yt-dlp GUI"
; Overridable from the command line (/DMyAppVersion=...); keep in sync with
; app\__init__.py when compiling by hand.
#ifndef MyAppVersion
  #define MyAppVersion "0.1.0"
#endif
#define MyAppPublisher "nikiliskage"
#define MyAppURL "https://github.com/nikiliskage/ytdlpgui"
#define MyAppExeName "ytdlpgui.exe"

[Setup]
AppId={{9E4D6F2A-8B1C-4E3D-9A77-1F2B3C4D5E6F}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
; Per-user install (no admin/UAC): the app + its binaries go directly in
; %LocalAppData%\Programs\yt-dlp-gui (the app searches its own folder for
; yt-dlp.exe/ffmpeg.exe). Downloads default to Documents\yt-dlp-gui
; (video\ / audio\), resolved by the app at runtime.
PrivilegesRequired=lowest
DefaultDirName={autopf}\yt-dlp-gui
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
; The license/disclaimer the user must accept to proceed.
LicenseFile=EULA.txt
SetupIconFile=..\app\resources\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
OutputDir=Output
OutputBaseFilename=ytdlpgui-setup-{#MyAppVersion}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "EULA.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Messages]
; Extra reminder shown on the "Ready to Install" page.
ReadyLabel2b=yt-dlp GUI does not include yt-dlp.exe or ffmpeg.exe. After installing, put both in the install folder (next to the app), or set their paths in Settings -> Binaries. Downloads default to Documents\yt-dlp-gui (video / audio).
