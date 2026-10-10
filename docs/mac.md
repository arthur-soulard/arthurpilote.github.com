# Pilote sur Mac

Fiche détaillée tirée de `CLAUDE.md`, qui garde les règles générales (dont les cinq choses à ne jamais casser).

## Décisions d'Arthur (11/10/2026)

* **Une seule application pour Windows et Mac**, pas de copie séparée : même code,
  même numéro de version, même format de données. Une archive de sauvegarde faite
  sous Windows se restaure sur un Mac (chemins du zip en `/`, même `_PIN_SALT`).
  Ce qui diffère vit derrière un test `sys.platform` (ou dans `plateforme.py`), et
  le chemin Windows y reste celui d'avant.
* **Tests sur les machines Mac de GitHub** (`.github/workflows/build-mac.yml`) :
  personne n'a de Mac sous la main. Gratuit pour un dépôt public.
* **Pas de compte développeur Apple** (99 $/an) : l'app n'est ni signée ni
  notarisée. Une notice expliquera « Ouvrir quand même » ; la mise à jour sera
  faite par Pilote lui-même, pour ne pas refaire la manipulation à chaque version.
* **Clé USB réglable** (Windows et Mac) : clés autorisées, dossier et contenu,
  moment de la sauvegarde et seuil d'alerte, éjection après copie.
* Cible : Mac à puce Apple. La dernière machine Intel de GitHub (`macos-15-intel`)
  n'est annoncée que jusqu'à l'été 2027 environ.

## Étapes (une version par étape)

| # | Étape | État |
|---|---|---|
| 1 | Socle : dépendances par système, dossier de données, « Ouvrir le dossier », notifications, mise à jour qui ne propose pas le Setup sur Mac, pas de fouille du Bureau sur Mac, build Mac de test | fait, en attente du premier passage sur GitHub |
| 2 | Lire le résultat du build de test, corriger ce qui casse au lancement | |
| 3 | Fenêtre et raccourcis : barre de titre déplaçable, boutons à gauche, Agrandir, taille d'écran, ⌘ au lieu de Ctrl, textes « Windows », ⌘Q qui vide les enregistrements en attente, `private_mode=False` (localStorage gardé, comme sous Windows) | |
| 4 | Clé USB : réglages (les deux systèmes) + détection sur Mac (`/Volumes`, `diskutil info -plist`) | |
| 5 | OCR Santé et Vocabulaire : Vision d'Apple (hors ligne, français en mode « accurate », boîtes par mot) et PDFKit pour les PDF, via pyobjc déjà tiré par pywebview | |
| 6 | Mise à jour Mac (téléchargée et installée par Pilote), asset Mac dans `release.yml` (job séparé, qui ne bloque jamais le Setup), README et notice d'installation | |

## Ce qui est déjà en place (étape 1)

* **Données** : `storage.get_app_dir()` → `~/Library/Application Support/Pilote/Donnees`
  dans l'app Mac compilée. À côté de l'exécutable, elles seraient DANS `Pilote.app`,
  que la mise à jour remplace en entier, et que macOS lance depuis une copie en
  lecture seule tant que l'app n'a pas quitté Téléchargements. En dev, sur Mac
  comme sous Windows, c'est toujours `Donnees/` à la racine du dépôt.
* **`requirements.txt`** : marqueurs `sys_platform`. Windows garde pywebview 4.4.1
  (le filtre du `crash.log` repose sur son comportement) ; le Mac prend la 6.2.1 :
  la 4.4.1 n'y gère pas `prompt()` (10 appels dans l'interface, dont le code PIN
  actuel), et la 6.2 corrige un plantage sur puce Apple. `win10toast` tire
  `pywin32`, qui n'existe pas sur Mac : sans marqueur, l'installation échouait.
* **`plateforme.ouvrir()`** : Explorateur sous Windows (`os.startfile`, comme avant),
  Finder sur Mac (`open`). Utilisée par les 3 boutons « Ouvrir » (destination de
  la sauvegarde USB, dossier de l'utilisateur, dossier Donnees).
* **Notifications** : `osascript` sur Mac (fourni avec macOS). Non essayé sur un
  vrai Mac : macOS peut les attribuer à l'Éditeur de script et demander une
  autorisation.
* **Mise à jour** : sur Mac, `downloadUrl` est vidé, donc jamais de « nouvelle
  version » qui mènerait au Setup Windows ; le journal va dans `~/Library/Logs/Pilote/`.
* **`scan_orphan_data()`** rend `[]` sur Mac : les données n'y suivent jamais l'app,
  et lire Bureau, Documents ou Téléchargements déclenche une demande d'autorisation
  du système pour chacun, dès le premier lancement.
* **`reveal_main_window(origine)`** écrit « fenêtre ouverte (page) » ou « (delai) » :
  le test du build Mac sait ainsi si l'interface a vraiment démarré.

## Build Mac

* `build/pilote-mac.spec` : à part de `pilote.spec` pour que le build Windows ne
  bouge pas. Même piège : `ui/vendor` doit rester dans les `datas`. L'icône est
  `assets/icon.ico` (la même que Windows ; `icon_512.png` est exclue de git), convertie en `.icns` par PyInstaller.
* **`BUNDLE_ID = "io.github.arthur-soulard.pilote"`** : l'identité de l'app pour
  macOS (autorisations, préférences). Comme l'`AppId` de `installer.iss`, ne
  JAMAIS la changer une fois l'app distribuée.
* `build-mac.yml` ne se déclenche que sur la branche `mac` (et à la main). Il
  fabrique l'app, la lance, attend `/ping` et la ligne « fenêtre ouverte », prend
  une capture d'écran, vérifie que `Donnees` est dans Application Support et pas
  dans l'app. Les constats sortent en annotations (lisibles sans compte via
  l'API publique des check-runs) ; capture, journal et app zippée sont en artefact.

## Inventaire de ce qui reste propre à Windows

| Quoi | Où | Sur Mac aujourd'hui |
|---|---|---|
| Déplacement de la fenêtre (`-webkit-app-region`, propre au moteur de Windows) | `index.html` `.titlebar` | fenêtre immobile ; pywebview veut la classe `pywebview-drag-region` |
| Agrandir, taille de l'écran, taille gardée à la fermeture | `app.py` `maximize_toggle`, `main()`, `_on_closing` | rien / 1280×720 / repli sur `window.width` |
| Remise au premier plan, icône à l'accent, raccourcis `.lnk` | `app.py`, `appicon.py` | sans effet (exceptions rattrapées) |
| Coins arrondis de l'écran de chargement (DWM) | `splash.py` | sans effet |
| Détection des clés USB (`GetLogicalDrives`, numéro de série) | `sauvegarde.py` | « Aucune clé USB détectée » |
| OCR (`ocr_win.ps1`, Windows.Media.Ocr) | `sante.py`, `vocabulaire.py` | « OCR disponible uniquement sous Windows » |
| Installation de la mise à jour (`.bat`, `cmd.exe`, Setup) | `updater.py` | jamais proposée (étape 1) |
| Raccourcis Ctrl, textes « Windows », « Win+Maj+S » | `index.html` | Ctrl au lieu de ⌘ |
| ⌘Q (pywebview) : arrêt sans vider les enregistrements en attente (0,4 s) | pywebview | à gérer côté Python |

## Gatekeeper (app non signée)

Depuis macOS Sequoia, le clic droit → Ouvrir ne contourne plus le blocage : lancer
l'app une fois, fermer l'avertissement, puis Réglages Système → Confidentialité et
sécurité → **Ouvrir quand même**. Une app non signée change d'identité à chaque
version : macOS peut redemander ses autorisations (accès à la clé USB) après une
mise à jour. À vérifier sur un vrai Mac : un fichier téléchargé par Pilote lui-même
(et non par le navigateur) ne porte pas la marque de quarantaine qui déclenche le
blocage.
