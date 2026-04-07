; Inno Setup 6 installer for BSIE.
; Build: ISCC installer\windows\setup.iss
; Prerequisites: Inno Setup 6 (https://jrsoftware.org/isinfo.php)

#define MyAppName "BSIE"
#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif
#define MyAppPublisher "ร้อยตำรวจเอกณัฐวุฒิ สาหร่ายทอง"
#define MyAppComments "Developer: ร้อยตำรวจเอกณัฐวุฒิ สาหร่ายทอง | Contact: ๐๙๖๗๗๖๘๗๕๗"
#define MyAppExeName "BSIE.exe"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppComments={#MyAppComments}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=..\..\dist\installer
OutputBaseFilename=BSIE-Setup-{#MyAppVersion}-windows
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Include the entire PyInstaller output directory
Source: "..\..\dist\BSIE\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
