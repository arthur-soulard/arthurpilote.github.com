; ============================================================
;  Pilote - Inno Setup script
;  Compile avec Inno Setup 6+ (https://jrsoftware.org/isdl.php)
;  Produit : dist\Pilote_Setup.exe
; ============================================================

#define AppName       "Pilote"
#define AppVersion    "4.3.30"
#define AppPublisher  "Arthur"
#define AppExeName    "Pilote.exe"

[Setup]
AppId={{E1B6F4D2-7C8E-4B5A-9D3F-1A2B3C4D5E6F}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
; Voir DossierParDefaut() : une reinstallation retrouve les donnees laissees
; par une desinstallation
DefaultDirName={code:DossierParDefaut}
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
; Les donnees vivent dans {app}\Donnees. Jusqu'a la 4.3.13, [UninstallDelete]
; effacait tout {app} : desinstaller supprimait toutes les donnees. Retirer la
; ligne ne suffit pas : Inno AJOUTE chaque installation au meme journal de
; desinstallation (unins*.dat), et l'ancienne consigne y reste (essaye le
; 01/10/2026 : mise a jour sans la ligne, puis desinstallation -> Donnees
; efface quand meme). overwrite reecrit ce journal a chaque installation : la
; mise a jour suivante le purge. Ne pas repasser en append.
UninstallLogMode=overwrite

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
; Mise a jour automatique (updater.py lance ce Setup en /VERYSILENT apres avoir
; ferme l'app) : on rouvre l'app une fois l'installation terminee. C'est le
; Setup de la NOUVELLE version qui s'execute : la regle vaut des la mise a jour
; qui l'apporte, sans attendre que l'ancienne app sache relancer.
Filename: "{app}\{#AppExeName}"; Flags: nowait; Check: WizardSilent

; Jamais "{app}" ici : Donnees\ vit dedans (voir UninstallLogMode). Le
; desinstalleur retire deja les fichiers qu'il a installes ; Donnees\ reste.
[UninstallDelete]
Type: filesandordirs; Name: "{app}\_internal"

[Code]
// Une desinstallation laisse app\Donnees sur le disque. Une installation
// neuve (plus de trace dans le registre) irait pourtant dans autopf\Pilote,
// et Pilote s'ouvrirait vide alors que les donnees sont a cote. On revient donc
// au dossier qui les contient : "Suivi PEA" est le nom historique, celui de
// toute installation anterieure a la 4.1.0 (voir l'AppId).
// (Commentaires en // : une accolade de constante fermerait un commentaire { }.)
function DossierParDefaut(Param: String): String;
begin
  if DirExists(ExpandConstant('{autopf}\Suivi PEA\Donnees')) then
    Result := ExpandConstant('{autopf}\Suivi PEA')
  else
    Result := ExpandConstant('{autopf}\{#AppName}');
end;

// Desinstallation a la main : dire ou sont restees les donnees.
// Le script reste en ASCII (lu tel quel par le compilateur) : les "e" accentues
// s'ecrivent #$00E9.
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if (CurUninstallStep = usPostUninstall) and not UninstallSilent
     and DirExists(ExpandConstant('{app}\Donnees')) then
    MsgBox('Tes donn' + #$00E9 + 'es Pilote sont conserv' + #$00E9 + 'es dans :' + #13#10
           + ExpandConstant('{app}\Donnees') + #13#10#13#10
           + 'R' + #$00E9 + 'installer Pilote les retrouve. '
           + 'Pour les effacer, supprime ce dossier.',
           mbInformation, MB_OK);
end;
