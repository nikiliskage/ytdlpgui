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
  #define MyAppVersion "0.2.1"
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
; yt-dlp.exe / ffmpeg.exe / deno.exe). Downloads default to Documents\yt-dlp-gui
; (video\ / audio\), resolved by the app at runtime.
PrivilegesRequired=lowest
DefaultDirName={autopf}\yt-dlp-gui
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
; The license/disclaimer the user must accept to proceed.
LicenseFile=EULA.txt
; Shown after installing: which binaries to download, from where, and where to
; put them (yt-dlp.exe, ffmpeg.exe and deno.exe are not bundled).
InfoAfterFile=BINARIES.txt
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
Source: "BINARIES.txt"; DestDir: "{app}"; DestName: "README - binaries.txt"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; Offered (ticked) only while a required binary is missing from the install folder.
Filename: "{app}"; Description: "Open the install folder (to add yt-dlp.exe, ffmpeg.exe, deno.exe)"; Flags: postinstall shellexec skipifsilent nowait; Check: BinariesMissing
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Messages]
; Extra reminder shown on the "Ready to Install" page.
ReadyLabel2b=yt-dlp GUI does not include yt-dlp.exe, ffmpeg.exe or deno.exe (deno is needed for YouTube). After installing, put them in the install folder (next to the app), or set their paths in Settings -> Binaries. Downloads default to Documents\yt-dlp-gui (video / audio).

[Code]
// Required binaries the app looks for next to ytdlpgui.exe.
function MissingBinaries(): String;
var
  Names: array[0..2] of String;
  I: Integer;
begin
  Names[0] := 'yt-dlp.exe';
  Names[1] := 'ffmpeg.exe';
  Names[2] := 'deno.exe';
  Result := '';
  for I := 0 to 2 do
    if not FileExists(ExpandConstant('{app}\') + Names[I]) then
    begin
      if Result <> '' then
        Result := Result + ', ';
      Result := Result + Names[I];
    end;
end;

function BinariesMissing(): Boolean;
begin
  Result := MissingBinaries() <> '';
end;

// On the last page, say exactly which files are still missing (an upgrade
// that already has them in the folder gets the normal message).
procedure CurPageChanged(CurPageID: Integer);
var
  Missing: String;
begin
  if CurPageID = wpFinished then
  begin
    Missing := MissingBinaries();
    if Missing <> '' then
      WizardForm.FinishedLabel.Caption :=
        'yt-dlp GUI is installed.' + #13#10 + #13#10 +
        'Still missing in the install folder: ' + Missing + '.' + #13#10 +
        'Download them (see "README - binaries.txt" in the install folder) and put them next ' +
        'to ytdlpgui.exe, or pick them in Settings -> Binaries. Without deno.exe, YouTube ' +
        'downloads fail with HTTP 403.';
  end;
end;
