; ============================================================
;  Pilote - Inno Setup script
;  Compile avec Inno Setup 6+ (https://jrsoftware.org/isdl.php)
;  Produit : dist\Pilote_Setup.exe
; ============================================================

#define AppName       "Pilote"
#define AppVersion    "4.2.8"
#define AppPublisher  "Arthur"
#define AppExeName    "Pilote.exe"

[Setup]
AppId={{E1B6F4D2-7C8E-4B5A-9D3F-1A2B3C4D5E6F}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=Pilote_Setup
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesInstallIn64BitMode=x64
MinVersion=10.0
LanguageDetectionMethod=uilanguage

[Languages]
Name: "french";  MessagesFile: "compiler:Languages\French.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon";  Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Build onedir (build/pilote.spec) : Pilote.exe n'est qu'un lanceur, Python,
; les bibliotheques et l'UI vivent dans _internal\ a cote de lui
Source: "..\dist\Pilote\Pilote.exe";    DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\Pilote\_internal\*";   DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\assets\icon.ico";           DestDir: "{app}"; Flags: ignoreversion

; L'AppId est un GUID fixe : une installation "Suivi PEA" existante est
; reconnue et mise a jour dans son dossier actuel (Donnees/ est conserve).
; On y efface simplement les traces de l'ancien nom.
[InstallDelete]
Type: files; Name: "{app}\Suivi_PEA.exe"
Type: files; Name: "{autoprograms}\Suivi PEA.lnk"
Type: files; Name: "{autodesktop}\Suivi PEA.lnk"
Type: files; Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\Suivi PEA.lnk"
; _internal\ est entierement regenere a chaque version : on le vide avant de
; le reinstaller, pour qu'une bibliotheque retiree du build ne traine pas.
; Donnees\ n'est jamais touche.
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{autoprograms}\{#AppName}";          Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\icon.ico"
Name: "{autodesktop}\{#AppName}";           Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\icon.ico"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#AppName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\icon.ico"; Tasks: quicklaunchicon

[Run]
; Lancement normal apres installation manuelle (case a cocher)
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
