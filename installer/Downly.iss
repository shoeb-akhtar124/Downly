; Inno Setup Script for Downly - Universal Video Downloader
; Generates Downly-Setup-v1.0.0.exe

#define MyAppName "Downly"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Downly"
#define MyAppExeName "Downly.exe"
#define MyAppIcoName "downly.ico"

[Setup]
AppId={{8A7F2D1E-6C3B-4E5A-9D2F-1B3E5A7C9D2E}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL=https://github.com/user/Downly
AppSupportURL=https://github.com/user/Downly
AppUpdatesURL=https://github.com/user/Downly
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=Downly-Setup-v1.0.0
SetupIconFile=..\assets\icons\{#MyAppIcoName}
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog commandline
ChangesEnvironment=yes
CloseApplications=yes
RestartApplications=no
DisableWelcomePage=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce
Name: "addtopath"; Description: "Add Downly to Windows PATH (launch with 'downly' from terminal)"; GroupDescription: "System Integration:"; Flags: checkedonce

[Files]
Source: "..\dist\Downly\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\_internal\assets\icons\{#MyAppIcoName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\_internal\assets\icons\{#MyAppIcoName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
// Helper to check if directory is already in User PATH
function NeedsAddPath(Param: string): boolean;
var
  OrigPath: string;
begin
  if not RegQueryStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', OrigPath) then
  begin
    Result := True;
    exit;
  end;
  // Look for the path between semicolons or at boundaries
  Result := Pos(';' + UpperCase(Param) + ';', ';' + UpperCase(OrigPath) + ';') = 0;
end;

// Add directory to Windows User PATH without duplicating
procedure AddPathToEnv(Param: string);
var
  OrigPath: string;
begin
  if not RegQueryStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', OrigPath) then
  begin
    RegWriteExpandStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', Param);
  end
  else
  begin
    if NeedsAddPath(Param) then
    begin
      if (Length(OrigPath) > 0) and (OrigPath[Length(OrigPath)] <> ';') then
        OrigPath := OrigPath + ';';
      RegWriteExpandStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', OrigPath + Param);
    end;
  end;
end;

// Remove directory from Windows User PATH during uninstall
procedure RemovePathFromEnv(Param: string);
var
  OrigPath: string;
  P: Integer;
  PParam: string;
begin
  if not RegQueryStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', OrigPath) then
    exit;

  PParam := ';' + UpperCase(Param) + ';';
  OrigPath := ';' + OrigPath + ';';
  P := Pos(PParam, UpperCase(OrigPath));
  if P > 0 then
  begin
    Delete(OrigPath, P, Length(PParam) - 1);
  end;

  // Clean leading semicolon
  while (Length(OrigPath) > 0) and (OrigPath[1] = ';') do
    Delete(OrigPath, 1, 1);

  // Clean trailing semicolon
  while (Length(OrigPath) > 0) and (OrigPath[Length(OrigPath)] = ';') do
    Delete(OrigPath, Length(OrigPath), 1);

  RegWriteExpandStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', OrigPath);
end;

// Handle post-install operations
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    if WizardIsTaskSelected('addtopath') then
    begin
      AddPathToEnv(ExpandConstant('{app}'));
    end;
  end;
end;

// Handle post-uninstall operations
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  UserDataDir: string;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    RemovePathFromEnv(ExpandConstant('{app}'));

    UserDataDir := ExpandConstant('{localappdata}\Downly');
    if DirExists(UserDataDir) then
    begin
      if MsgBox('Do you want to delete your Downly user preferences, settings, and download history?' + #13#10 + #13#10 +
                '(Note: Downloaded media files will NEVER be deleted.)',
                mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
      begin
        DelTree(UserDataDir, True, True, True);
      end;
    end;
  end;
end;

