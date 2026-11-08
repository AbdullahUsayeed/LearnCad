#define MyAppName "LearnCad"
#ifndef MyAppVersion
  #define MyAppVersion "0.6.5"
#endif
#define MyAppPublisher "Abdullah Usayeed"
#define MyAppURL "https://github.com/AbdullahUsayeed/LearnCad"

[Setup]
AppId={{8F3B2C1A-6D4E-4B7A-9C2F-1A5E7D9B3C60}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={code:GetModRoot}\LearnCad
DefaultGroupName=LearnCad
DisableDirPage=yes
DisableProgramGroupPage=yes
AllowNoIcons=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=LearnCad-Setup-{#MyAppVersion}
SetupIconFile=assets\learncad.ico
UninstallDisplayIcon={app}\launcher\assets\learncad.ico
WizardStyle=modern
Compression=lzma2
SolidCompression=yes
LicenseFile=..\LICENSE
InfoBeforeFile=README.txt
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} installer
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}
SetupLogging=yes
CloseApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut to LearnCad"; GroupDescription: "Shortcuts:"

[Files]
Source: "..\freecad\CADet\*"; DestDir: "{app}\freecad\CADet"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "__pycache__,__pycache__\*,*.pyc,*.pyo"
Source: "..\package.xml"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "assets\learncad.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\launcher\LearnCad.exe"; DestDir: "{app}\launcher"; Flags: ignoreversion
Source: "..\launcher\assets\*"; DestDir: "{app}\launcher\assets"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
Type: filesandordirs; Name: "{app}\freecad\CADet"

[UninstallDelete]
Type: filesandordirs; Name: "{app}\freecad\CADet\__pycache__"

[Icons]
Name: "{group}\LearnCad"; Filename: "{app}\launcher\LearnCad.exe"; WorkingDir: "{app}\launcher"; IconFilename: "{app}\launcher\assets\learncad.ico"
Name: "{group}\Uninstall LearnCad"; Filename: "{uninstallexe}"
Name: "{autodesktop}\LearnCad"; Filename: "{app}\launcher\LearnCad.exe"; WorkingDir: "{app}\launcher"; IconFilename: "{app}\launcher\assets\learncad.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\launcher\LearnCad.exe"; WorkingDir: "{app}\launcher"; Description: "Launch LearnCad"; Flags: postinstall nowait skipifsilent; Check: FreeCADFound

[Code]
function GetModRoot(Param: String): String;
var
  Base: String;
  ModOverride: String;
begin
  ModOverride := ExpandConstant('{param:MODROOT|}');
  if ModOverride <> '' then
  begin
    Result := ModOverride;
    exit;
  end;
  Base := ExpandConstant('{userappdata}\FreeCAD');
  if DirExists(Base + '\v1-1') then
    Result := Base + '\v1-1\Mod'
  else if DirExists(Base + '\v1-2') then
    Result := Base + '\v1-2\Mod'
  else if DirExists(Base + '\v1-0') then
    Result := Base + '\v1-0\Mod'
  else if DirExists(Base + '\Mod') then
    Result := Base + '\Mod'
  else
    Result := Base + '\v1-1\Mod';
end;

function GetFreeCADExe(Param: String): String;
begin
  if FileExists(ExpandConstant('{commonpf64}\FreeCAD 1.1\bin\FreeCAD.exe')) then
    Result := ExpandConstant('{commonpf64}\FreeCAD 1.1\bin\FreeCAD.exe')
  else if FileExists(ExpandConstant('{commonpf64}\FreeCAD 1.2\bin\FreeCAD.exe')) then
    Result := ExpandConstant('{commonpf64}\FreeCAD 1.2\bin\FreeCAD.exe')
  else if FileExists(ExpandConstant('{commonpf64}\FreeCAD 1.0\bin\FreeCAD.exe')) then
    Result := ExpandConstant('{commonpf64}\FreeCAD 1.0\bin\FreeCAD.exe')
  else if FileExists(ExpandConstant('{commonpf64}\FreeCAD\bin\FreeCAD.exe')) then
    Result := ExpandConstant('{commonpf64}\FreeCAD\bin\FreeCAD.exe')
  else if FileExists(ExpandConstant('{commonpf}\FreeCAD 1.1\bin\FreeCAD.exe')) then
    Result := ExpandConstant('{commonpf}\FreeCAD 1.1\bin\FreeCAD.exe')
  else if FileExists(ExpandConstant('{commonpf}\FreeCAD 1.2\bin\FreeCAD.exe')) then
    Result := ExpandConstant('{commonpf}\FreeCAD 1.2\bin\FreeCAD.exe')
  else if FileExists(ExpandConstant('{commonpf}\FreeCAD 1.0\bin\FreeCAD.exe')) then
    Result := ExpandConstant('{commonpf}\FreeCAD 1.0\bin\FreeCAD.exe')
  else if FileExists(ExpandConstant('{commonpf}\FreeCAD\bin\FreeCAD.exe')) then
    Result := ExpandConstant('{commonpf}\FreeCAD\bin\FreeCAD.exe')
  else if FileExists(ExpandConstant('{commonpf32}\FreeCAD 1.1\bin\FreeCAD.exe')) then
    Result := ExpandConstant('{commonpf32}\FreeCAD 1.1\bin\FreeCAD.exe')
  else if FileExists(ExpandConstant('{localappdata}\Programs\FreeCAD 1.1\bin\FreeCAD.exe')) then
    Result := ExpandConstant('{localappdata}\Programs\FreeCAD 1.1\bin\FreeCAD.exe')
  else if FileExists(ExpandConstant('{localappdata}\FreeCAD\bin\FreeCAD.exe')) then
    Result := ExpandConstant('{localappdata}\FreeCAD\bin\FreeCAD.exe')
  else
    Result := '';
end;

function FreeCADFound: Boolean;
begin
  Result := GetFreeCADExe('') <> '';
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = wpFinished then
    WizardForm.FinishedLabel.Caption :=
      'LearnCad is installed.' + #13#10#13#10 +
      'Launch it from the desktop shortcut or the Start Menu.' + #13#10 +
      'Type what you are making, then follow the coach.';
end;

function InitializeSetup(): Boolean;
var
  Target: String;
begin
  Result := True;
  if not FreeCADFound then
  begin
    if not WizardSilent then
      Result := MsgBox(
        'The LearnCad modeling engine was not found in the usual locations.' + #13#10#13#10 +
        'LearnCad can still be installed, but it will not start until its modeling engine is installed and started once.' + #13#10#13#10 +
        'Continue?', mbConfirmation, MB_YESNO) = IDYES;
  end;
  if not Result then
    exit;
  Target := GetModRoot('') + '\LearnCad';
  if DirExists(Target) then
  begin
    if not WizardSilent then
      Result := MsgBox(
        'LearnCad is already installed in your user profile.' + #13#10#13#10 +
        'Setup will update LearnCad. Close LearnCad before continuing.' + #13#10#13#10 +
        'Continue?', mbConfirmation, MB_YESNO) = IDYES;
  end;
end;
