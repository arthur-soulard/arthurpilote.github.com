; ============================================================
;  Pilote - Inno Setup script
;  Compile avec Inno Setup 6+ (https://jrsoftware.org/isdl.php)
;  Produit : dist\Pilote_Setup.exe
; ============================================================

#define AppName       "Pilote"
#define AppVersion    "4.4.43"
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
; Toujours "pour moi seulement", sans la question "pour moi / pour tous" : dans
; Program Files, Pilote ne peut pas ecrire Donnees a cote de son exe et les
; rangeait ailleurs (repli de storage.get_app_dir, AppData\Roaming). Retiree en
; 4.4.20 (19/10/2026) : PrivilegesRequiredOverridesAllowed=dialog.
PrivilegesRequired=lowest
; 64 bits exige (l'exe est en x64) : refus clair sur un Windows 32 bits, et un
; Windows sur processeur ARM l'accepte (emulation x64), SUP-12
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
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
; Licences des composants embarques (LEG-03)
Source: "..\THIRD-PARTY-NOTICES.txt";  DestDir: "{app}"; Flags: ignoreversion

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
; WebView2 absent du PC : installe a partir du programme telecharge par
; NextButtonClick (voir WebView2Present)
Filename: "{tmp}\MicrosoftEdgeWebview2Setup.exe"; Parameters: "/silent /install"; StatusMsg: "Installation de Microsoft Edge WebView2..."; Flags: waituntilterminated; Check: WebView2Telecharge
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

// L'ancienne entree "Suivi PEA 1.0.0" (autre AppId, mai 2026) visait le meme
// dossier que Pilote. Son desinstalleur (unins000 sur le PC d'Arthur) datait
// d'avant la 4.3.13 : lance depuis les Parametres de Windows, il aurait efface
// tout {app}, Donnees compris (vu le 11/10/2026). On la retire a chaque
// installation : son desinstalleur et son journal (.exe et .dat), puis sa cle.
// Seulement si elle vise CE dossier : ailleurs, unins000 peut etre le
// desinstalleur de Pilote lui-meme, auquel on ne touche pas.
const
  CLE_DESINSTALLATION = 'Software\Microsoft\Windows\CurrentVersion\Uninstall';
  ANCIEN_APPID        = '{A7C5D4E2-PEA-';

procedure RetirerAncienneEntreeSuiviPEA();
var
  Noms: TArrayOfString;
  I: Integer;
  Cle, Desinstalleur, Dossier: String;
begin
  if not RegGetSubkeyNames(HKCU, CLE_DESINSTALLATION, Noms) then
    Exit;
  for I := 0 to GetArrayLength(Noms) - 1 do
  begin
    if Pos(ANCIEN_APPID, Noms[I]) <> 1 then
      Continue;
    Cle := CLE_DESINSTALLATION + '\' + Noms[I];
    if not RegQueryStringValue(HKCU, Cle, 'UninstallString', Desinstalleur) then
      Continue;
    Desinstalleur := RemoveQuotes(Desinstalleur);
    Dossier := ExtractFilePath(Desinstalleur);
    if CompareText(AddBackslash(Dossier), AddBackslash(ExpandConstant('{app}'))) <> 0 then
    begin
      Log('Ancienne entree ' + Noms[I] + ' laissee : elle vise ' + Dossier);
      Continue;
    end;
    DeleteFile(Desinstalleur);
    DeleteFile(ChangeFileExt(Desinstalleur, '.dat'));
    if RegDeleteKeyIncludingSubkeys(HKCU, Cle) then
      Log('Ancienne entree ' + Noms[I] + ' retiree');
  end;
end;

// Avant la 4.4.20, le Setup proposait « pour tous » (Program Files, registre
// HKLM). L'installeur actuel, « pour moi », ne la voit pas : une mise a jour
// poserait une seconde copie, et Pilote se rouvrirait vide (SUP-10). On
// s'arrete en disant ou sont les donnees ; en mise a jour silencieuse, le
// batch d'updater.py relance alors l'ancien Pilote.
function InitializeSetup(): Boolean;
var
  Cle: String;
begin
  Result := True;
  Cle := CLE_DESINSTALLATION + '\' + ExpandConstant('{#SetupSetting("AppId")}') + '_is1';
  if RegKeyExists(HKLM32, Cle) or RegKeyExists(HKLM64, Cle) then
  begin
    MsgBox('Pilote est d' + #$00E9 + 'j' + #$00E0 + ' install' + #$00E9 + ' pour tous les utilisateurs '
           + '(dossier Program Files). Pour garder tes donn' + #$00E9 + 'es, d' + #$00E9 + 'sinstalle '
           + 'cette version depuis les Param' + #$00E8 + 'tres de Windows (tes donn' + #$00E9 + 'es restent '
           + 'dans son dossier Donnees), puis relance ce programme d''installation.',
           mbError, MB_OK);
    Result := False;
  end;
end;

// WebView2 dessine la fenetre de Pilote. Sans lui, pywebview se rabat sur
// Internet Explorer et Pilote s'ouvre sur une page vide. Il est fourni avec
// Windows 11 et un Windows 10 a jour, mais peut manquer sur un Windows 10
// ancien. Meme lecture du registre que pywebview (_is_chromium dans
// winforms.py) : version "pv", cote utilisateur ou cote machine.
const
  WEBVIEW2_CLE = 'SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';
  WEBVIEW2_URL = 'https://go.microsoft.com/fwlink/p/?LinkId=2124703';
  WEBVIEW2_EXE = 'MicrosoftEdgeWebview2Setup.exe';

var
  PageWebView2: TDownloadWizardPage;

function WebView2Present(): Boolean;
var
  V: String;
begin
  Result := True;
  if RegQueryStringValue(HKCU, WEBVIEW2_CLE, 'pv', V) and (V <> '') and (V <> '0.0.0.0') then
    Exit;
  if RegQueryStringValue(HKLM32, WEBVIEW2_CLE, 'pv', V) and (V <> '') and (V <> '0.0.0.0') then
    Exit;
  Result := False;
end;

function WebView2Telecharge(): Boolean;
begin
  Result := FileExists(ExpandConstant('{tmp}\' + WEBVIEW2_EXE));
end;

procedure InitializeWizard();
begin
  PageWebView2 := CreateDownloadPage(SetupMessage(msgWizardPreparing), SetupMessage(msgPreparingDesc), nil);
end;

// Au clic sur Installer : si WebView2 manque, on telecharge son installateur
// officiel (lien de Microsoft), lance par [Run]. Une mise a jour silencieuse n'est pas
// concernee : Pilote tournait, donc WebView2 est la. Sans connexion, on
// installe quand meme et on dit quoi faire.
function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if (CurPageID <> wpReady) or WizardSilent or WebView2Present() then
    Exit;
  PageWebView2.Clear;
  PageWebView2.Add(WEBVIEW2_URL, WEBVIEW2_EXE, '');
  PageWebView2.Show;
  try
    try
      PageWebView2.Download;
    except
      MsgBox('Pilote a besoin de Microsoft Edge WebView2, absent de ce PC, et son '
             + 'installation n''a pas pu ' + #$00EA + 'tre t' + #$00E9 + 'l' + #$00E9 + 'charg' + #$00E9 + 'e.' + #13#10#13#10
             + 'Pilote s''installe quand m' + #$00EA + 'me. Ensuite, connecte-toi ' + #$00E0 + ' internet et '
             + 'relance ce programme d''installation : il ajoutera WebView2. '
             + 'Sans lui, Pilote s''ouvre sur une fen' + #$00EA + 'tre vide.',
             mbInformation, MB_OK);
    end;
  finally
    PageWebView2.Hide;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    RetirerAncienneEntreeSuiviPEA();
end;
