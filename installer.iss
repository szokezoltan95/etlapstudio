#ifndef AppVersion
#define AppVersion "1.1.0"
#endif

#define AppName "ÉtlapStúdió"
#define AppExe "EtlapStudio.exe"

[Setup]
AppId={{7B8A16BB-A074-4DAB-9CF5-70E58C51D151}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Szőke Zoltán
DefaultDirName={autopf}\EtlapStúdió
DefaultGroupName={#AppName}
OutputDir=dist\installer
OutputBaseFilename=EtlapStudio-Setup-{#AppVersion}
SetupIconFile=design_assets\megyehaza_emblem.ico
UninstallDisplayIcon={app}\{#AppExe}
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=lowest
CloseApplications=force
RestartApplications=no
WizardStyle=modern
Compression=lzma2
SolidCompression=yes

[Languages]
Name: "hungarian"; MessagesFile: "compiler:Languages\Hungarian.isl"

[Tasks]
Name: "desktopicon"; Description: "Asztali ikon létrehozása"; GroupDescription: "További ikonok:"; Flags: unchecked

[Files]
Source: "dist\EtlapStudio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "LICENSE"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{#AppName} indítása"; Flags: nowait postinstall skipifsilent
