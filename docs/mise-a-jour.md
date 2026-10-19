# Mise à jour automatique

Fiche détaillée tirée de `CLAUDE.md`, qui garde les règles générales (dont les six choses à ne jamais casser).

## Système d'auto-update (tout est en place, ne pas casser)

* `updater.py` interroge
  `https://api.github.com/repos/arthur-soulard/arthurpilote.github.com/releases/latest`
* Il retient le premier asset dont le nom finit par `Setup.exe`
* Si nouvelle version → modal dans l'UI avec barre de progression
* Téléchargement chunké avec progression réelle (fallback 25 Mo si Content-Length absent)
* Un batch Windows attend la fin du process (nom déduit de `sys.executable`, donc
  résistant à un renommage), puis 5 secondes de plus pour que Windows libère les
  fichiers (le dossier `_MEI*` jusqu'à la 4.2.7, les DLL de `_internal/` depuis),
  puis lance `Setup.exe /VERYSILENT /NORESTART /SUPPRESSMSGBOXES`
* L'app se ferme, l'installeur tourne en silence, puis **rouvre l'app tout seul**
  (4.3.0) : entrée `[Run]` de `installer.iss` avec `Check: WizardSilent`, qui ne
  s'applique qu'en `/VERYSILENT`, donc qu'aux mises à jour. L'installation manuelle
  garde sa case « Lancer Pilote » (`postinstall skipifsilent`) : les deux entrées
  s'excluent, jamais de double lancement. La relance est dans le **Setup** et pas
  dans le batch d'`updater.py` : c'est le Setup de la nouvelle version qui
  s'exécute, alors que le batch est écrit par l'ancienne. Elle vaut donc dès la
  mise à jour qui l'apporte. L'app relancée hérite de l'environnement de l'ancienne
  (`_PYI_ARCHIVE_FILE`, `_PYI_PARENT_PROCESS_LEVEL`) : testé sans conséquence en
  onedir avec PyInstaller 6.11.1. En onefile, il faudrait
  `PYINSTALLER_RESET_ENVIRONMENT=1` (encore une raison de ne pas y revenir).
* Logs : `%APPDATA%\Pilote\update.log` et `%TEMP%\pilote_update\update_bat.log`

**Solution de secours quand l'API refuse (4.2.5).** Sans jeton, l'API accepte
60 requêtes par heure et par adresse IP ; une adresse partagée peut épuiser ce quota
sans que Pilote y soit pour rien, et l'API répond `403 rate limit exceeded`. Constaté
le 23/09/2026 : huit vérifications refusées de suite, l'app se croyait à jour. Désormais
`_fetch()` essaie l'API (`_latest_from_api`) puis, en cas d'échec, la page publique
(`_latest_from_page`) : `/releases/latest` redirige vers `/releases/tag/vX.Y.Z` (lu sans
suivre la redirection, `_redirect_target`), et l'installeur a une URL fixe
`/releases/download/<tag>/Pilote_Setup.exe` (`SETUP_ASSET`, même nom que `release.yml`
et `OutputBaseFilename`). Son existence est vérifiée (302 attendu) avant de proposer
quoi que ce soit, et `hasUpdate` exige maintenant une `downloadUrl` : proposer une
mise à jour sans installeur ne mènerait qu'à un échec.

**Lire le vrai journal depuis une session Claude.** L'app Claude pour Windows est un
paquet MSIX : un terminal lancé depuis elle voit une copie *virtualisée* de
`%APPDATA%` (`...\Packages\Claude_...\LocalCache\Roaming\`). Un `python src/app.py`
lancé depuis Claude y a écrit un `update.log` qui masque le vrai : on croit alors que
l'app installée n'écrit plus rien. Le vrai fichier se lit par
`\\localhost\C$\Users\Arthur\AppData\Roaming\Pilote\update.log`. `%LOCALAPPDATA%\Programs`
(donc `Donnees/`) n'est pas virtualisé.

Points critiques :
* Dans le JS, utiliser `querySelector("#update-modal .upd-btns")` et non
  `getElementById("upd-btns")`
* Le polling JS (`setInterval` 400 ms) doit démarrer **avant** l'appel Python `start_update()`
* `start_update()` côté Python est non-bloquant (lance un thread)
* Ne pas réduire le délai de 5 secondes du batch

## Fiche des nouveautés (4.3.37)

Demandée par Arthur le 11/10/2026 : savoir ce qui change **avant** d'installer, le
retrouver **après**, et un historique. L'historique commence à la 4.3.37 (son choix :
pas de fiches rédigées après coup pour les versions passées).

* **Source unique : `src/nouveautes.json`**, une fiche par version en tête de fichier
  (`version`, `date`, `titre`, listes `nouveau` / `ameliore` / `corrige`). À écrire à
  chaque version, pour l'utilisateur (procédure de `CLAUDE.md`).
* **Avant** : quand `_fetch()` trouve une version plus récente, `_notes_distantes()`
  lit `raw.githubusercontent.com/<dépôt>/v<version>/src/nouveautes.json` (le fichier
  du tag, pas de quota comme l'API, le tag est connu par les deux chemins) et garde
  les fiches entre la version installée (exclue) et la nouvelle (incluse) : qui a
  sauté des versions les lit toutes. Résultat dans `notes` de `check_update()`. Sans
  fiche lisible (`None`), la mise à jour reste proposée, avec une phrase qui le dit.
  La fiche se replie quand l'installation démarre, pour laisser voir la progression.
  **Ne pas déplacer le fichier dans le dépôt** : les versions installées le
  cherchent à ce chemin.
* `_valider_notes()` ne garde que du texte court dans la forme attendue (fiche
  distante relue à chaque vérification) : 140 caractères de titre, 30 points de 600
  caractères par liste, 512 Ko lus au plus. Le JS échappe tout (`escHtml`).
* **Après** : `Api.nouveautes()` renvoie l'historique livré dans l'exe
  (`updater.historique()`, via `sys._MEIPASS`) : **ligne de `datas` dans
  `build/pilote.spec`**, sans laquelle l'historique est vide dans l'exe et plein en
  dev. Au démarrage, `_majFicheApresMiseAJour()` compare la version à
  `S.uiPrefs.nouveautesVues` (propre à chaque utilisateur) : la fiche s'ouvre une
  fois, puis la clé prend la version. Jamais rien lu (clé absente, cas de tout le
  monde à la 4.3.37) : seulement la fiche de la version installée. Pas de fiche
  quand l'assistant des premiers pas s'ouvre, ni si la lecture des données a échoué
  (rien ne pourrait être noté comme lu).
* **Historique** : Paramètres → Mises à jour (`docs/parametres.md`).
* Essais du 11/10/2026 (copie isolée de l'app, données vierges puis inventées) :
  fiche distante filtrée sur un faux serveur local (4.3.38 à 4.3.40 depuis une
  4.3.37), 404 → `None` ; fenêtre de mise à jour avec deux fiches puis sans fiche ;
  `nouveautesVues` à 4.3.36 → la fiche s'ouvre une fois et la clé passe à 4.3.37,
  rien au lancement suivant. Le bouton Installer n'a pas été essayé avec une fausse
  version (il installerait le vrai Setup par-dessus l'app d'Arthur).

## Désinstaller garde les données (4.3.14)

`Donnees/` vit dans le dossier d'installation (`{app}`). Jusqu'à la 4.3.13,
`[UninstallDelete]` effaçait tout `{app}` : **désinstaller supprimait toutes les
données**, tous utilisateurs confondus.

* Retirer la ligne ne suffit pas. Inno ajoute chaque installation au **même**
  journal de désinstallation (`unins*.dat`, mode `append` par défaut), et
  l'ancienne consigne y reste. Essayé le 01/10/2026 avec un installeur de test
  (autre AppId, autre dossier) : version 4.3.13 installée, mise à jour sans la
  ligne, désinstallation → `Donnees` effacé quand même.
* D'où `UninstallLogMode=overwrite` : chaque installation réécrit le journal, la
  mise à jour en 4.3.14 le purge. `[UninstallDelete]` ne vise plus que `_internal`.
  **Ne jamais remettre `{app}` dans `[UninstallDelete]`, ni repasser en `append`.**
* `DefaultDirName={code:DossierParDefaut}` : après une désinstallation, plus de
  trace dans le registre, et une installation neuve irait dans `Programs\Pilote`
  (Pilote s'ouvrirait vide, données à côté). La fonction revient à
  `Programs\Suivi PEA` quand il contient un `Donnees`.
* Désinstallation à la main : un message dit où sont restées les données
  (`CurUninstallStepChanged`, pas en silencieux). Script en ASCII : accents en
  `#$00E9`, commentaires `[Code]` en `//` (une accolade de constante comme `{app}`
  ferme un commentaire `{ }`).
* Essais du 01/10/2026 (installeur de test) : mise à jour 4.3.13 → 4.3.14 puis
  désinstallation → `Donnees` intact, exe et `_internal` retirés ; réinstallation
  sans choisir de dossier → retour dans `Suivi PEA`, données retrouvées ;
  installation neuve sur un PC vierge → `Programs\Pilote`. Seule la mise à jour
  vers la 4.3.14 protège : désinstaller une 4.3.13 efface encore tout.

## Toujours « pour moi seulement » (4.4.20, 19/10/2026)

Jusqu'ici, `PrivilegesRequiredOverridesAllowed=dialog` faisait poser au Setup, en
premier écran d'une installation neuve, la question « Installer seulement pour
moi / pour tous les utilisateurs ». Arthur ne comprenait pas la différence, et un
nouvel utilisateur non plus. Surtout, « pour tous » installe dans
`C:\Program Files\Pilote`, où Pilote, lancé sans droits d'administrateur, ne peut
pas créer `Donnees\` à côté de son exe : `storage.get_app_dir()` se rabat alors sur
`AppData\Roaming\Pilote` (repli jamais essayé), loin du programme, et un dossier par
compte Windows.

* La ligne est retirée : le Setup installe toujours dans
  `%LocalAppData%\Programs\Pilote` (ou `Suivi PEA`, voir `DossierParDefaut`), sans
  mot de passe administrateur. La page « Dossier de destination » reste : on peut
  choisir un autre dossier, et les données suivent le programme.
* Le chemin des données est maintenant écrit dans les Premiers pas et dans
  Paramètres → Données (`docs/accueil.md`, `docs/parametres.md`).
* Essai du 19/10/2026 : deux Setup de test compilés avec l'Inno Setup du PC (autre
  AppId, autre nom, faux fichiers, jamais installés), ouverts puis fermés. Avant :
  premier écran « Choix du Mode d'Installation ». Après : directement le choix de
  la langue, puis « Dossier de destination » sur
  `C:\Users\<nom>\AppData\Local\Programs\<nom de l'app>`.
* Pas essayé : la mise à jour d'une installation déjà faite « pour tous » (aucune
  connue). Le Setup de mise à jour tourne en `/VERYSILENT` sans `/ALLUSERS`, comme
  avant ; si une telle installation existe, ses données sont dans
  `AppData\Roaming\Pilote`. `scan_orphan_data` y regarde, mais ne propose de
  récupérer que le `pea_data.json` (le PEA), pas les autres modules.

## L'ancienne entrée « Suivi PEA 1.0.0 » (piège retiré par le Setup)

Vu le 11/10/2026 sur le PC d'Arthur : les Paramètres de Windows listaient encore
« Suivi PEA 1.0.0 » (installée en mai 2026, **autre AppId** :
`{A7C5D4E2-PEA-4B1A-9F3D-Suivi2026PEA}}_is1`), qui vise **le même dossier** que
Pilote (`Programs\Suivi PEA`). Son désinstalleur, `unins000.exe` (Pilote utilise
`unins001`), et son journal dataient d'avant la 4.3.14 : la désinstaller aurait très
probablement effacé tout le dossier, `Donnees` compris. Non essayé, évidemment.

* `RetirerAncienneEntreeSuiviPEA()` (`[Code]`, appelée en `ssPostInstall`) retire
  à chaque installation toute entrée HKCU dont la clé commence par
  `{A7C5D4E2-PEA-` : son désinstalleur, son `.dat`, puis sa clé.
* **Seulement si son désinstalleur est dans `{app}`.** Sur un PC sans cette vieille
  installation, `unins000` est le désinstalleur de Pilote lui-même : ne jamais
  supprimer `unins000.*` sans cette vérification.
* Testé le 11/10/2026 avec un Setup de test reprenant le même code (préfixe de test) :
  l'entrée qui visait le dossier installé est retirée avec ses deux fichiers,
  `Donnees` intact ; une entrée visant un autre dossier est laissée ; la vraie
  entrée d'Arthur n'a pas été touchée par l'essai. Le journal du Setup (`/LOG`)
  écrit « Ancienne entree … retiree » ou « … laissee : elle vise … ».
