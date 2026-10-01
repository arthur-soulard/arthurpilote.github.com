# Mise à jour automatique

Fiche détaillée tirée de `CLAUDE.md`, qui garde les règles générales (dont les cinq choses à ne jamais casser).

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
