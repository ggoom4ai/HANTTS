; HanTTS Studio — Inno Setup 6 스크립트 초안 (docs/08_WINDOWS_INSTALLER.md)
; 빌드: ISCC.exe /DAppVersion=0.1.0 installer\hantts.iss

#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif
#define AppName "HanTTS Studio"
#define AppExe  "HanTTS.exe"

[Setup]
AppId={{8C1D7E2A-5B3F-4C9E-9A61-7E0F2D4B6A10}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=HanTTS
DefaultDirName={localappdata}\Programs\HanTTS
DisableDirPage=no
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist\installer
OutputBaseFilename=HanTTS-Setup-{#AppVersion}-x64
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
SetupIconFile=hantts.ico
CloseApplications=yes
UninstallDisplayIcon={app}\{#AppExe}
; SignTool=signtool $f     ; 코드 서명 설정 후 활성화

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; Flags: unchecked
Name: "assochtpack"; Description: "엔진 팩(.htpack) 파일을 HanTTS로 열기"; Flags: unchecked

[Files]
Source: "..\dist\HanTTS\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
Root: HKA; Subkey: "Software\Classes\.htpack"; ValueType: string; ValueData: "HanTTS.EnginePack"; Flags: uninsdeletevalue; Tasks: assochtpack
Root: HKA; Subkey: "Software\Classes\HanTTS.EnginePack\shell\open\command"; ValueType: string; ValueData: """{app}\{#AppExe}"" --import-pack ""%1"""; Flags: uninsdeletekey; Tasks: assochtpack

[Run]
Filename: "{app}\{#AppExe}"; Description: "{#AppName} 실행"; Flags: nowait postinstall skipifsilent
Filename: "{app}\{#AppExe}"; Parameters: "--install-engine supertonic"; Description: "한국어 추천 엔진(Supertonic 3) 바로 설치"; Flags: nowait postinstall skipifsilent unchecked

[Code]
function DataDir(): String;
begin
  Result := ExpandConstant('{localappdata}\HanTTS');
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if (CurUninstallStep = usPostUninstall) and DirExists(DataDir()) then
  begin
    if MsgBox('다운로드한 엔진·모델, 설정, 기록도 모두 삭제할까요?' + #13#10 + DataDir(),
              mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
      DelTree(DataDir(), True, True, True);
  end;
end;
