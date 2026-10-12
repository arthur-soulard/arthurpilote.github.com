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
| 1 | Socle : dépendances par système, dossier de données, « Ouvrir le dossier », notifications, mise à jour qui ne propose pas le Setup sur Mac, pas de fouille du Bureau sur Mac, build Mac de test | fait (11/10/2026) |
| 2 | Lire le résultat du build de test, corriger ce qui casse au lancement | fait (11/10/2026) : icône, pont JS ↔ Python (voir « Pont pywebview et CSP »). Build de test vert, page prête en 0,8 s |
| 2 bis | Certificats HTTPS | fait (12/10/2026) : `plateforme.certificats_mac`, voir l'inventaire. Testé en cachant le fichier de la machine GitHub |
| 3 | Fenêtre et raccourcis | fait (12/10/2026) : voir « Fenêtre Mac » |
| 4 | Clé USB : réglages (les deux systèmes) + détection sur Mac (`/Volumes`, `diskutil info -plist`) | fait (12/10/2026) : `docs/sauvegarde-usb.md`, « Les quatre réglages » et « Sur Mac » |
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

## Pont pywebview et CSP (étape 2, 11/10/2026)

**Le piège.** pywebview fabrique les fonctions de `pywebview.api` avec
`new Function(...)` et renvoie chaque réponse de Python par `evaluate_js`, qui
passe par `eval()`. La CSP de la page (`server._CSP`) n'autorise pas
`'unsafe-eval'`. Sous Windows, WebView2 exempte le script injecté ; WebKit (Mac)
non. Constaté sur le build de test : « EvalError … 'unsafe-eval' », pont vide
(0 fonction), aucun module chargé, fenêtre ouverte seulement par le délai de 20 s.

**La correction** (`plateforme.adapter_pont_mac`, appelée par `main()` sur Mac) :
fermeture à la place de `new Function` dans le script de pywebview, et
`evaluate_js` de la fenêtre principale remplacé par `run_js` (pas d'`eval`).
Vérifiée dans un navigateur sous la même CSP (script d'origine : EvalError ;
adapté : fonctions créées, appel envoyé, réponse reçue), puis sur le build de
test : 61 fonctions, 7 modules chargés, « fenêtre ouverte (page) ».

* **Ne jamais « réparer » en ajoutant `'unsafe-eval'` à la CSP** : c'est
  précisément ce que l'adaptation évite.
* Elle vise le texte de pywebview **6.2.1** (épinglée). En changeant de version,
  relancer le build de test : si le motif a changé, la sortie écrit « pont
  pywebview non adapté » et le journal montre « pont Python false ».
* `_waitForPywebview` attend une vraie fonction (`app_ready`) : pywebview 6 crée
  `pywebview.api` vide puis le remplit. Le croire prêt trop tôt posait
  `_surveillerEcritures()` sur un objet vide.

**Journal de démarrage** (`window.__journal`, index.html) : étapes de `boot()`
et erreurs JS, avec leur instant. `PILOTE_DIAG=1` (test Mac seulement) fait relire
ce journal par `app.py` 30 s après le lancement, via `run_js` (pas
`evaluate_js`, bloqué par la CSP). `build-mac.yml` le publie en annotation
« Diag ». Sous Windows aussi, `PILOTE_DIAG=1 python src/app.py` l'affiche.

Constat annexe sous Windows : sur le PC d'Arthur, la page est prête entre 13 et
16 s, et une fois à 22 s (PC chargé) ; elle s'est alors ouverte par le délai de
secours de 20 s. Rien de cassé, mais la marge est mince.

## Fenêtre Mac (étape 3, 12/10/2026)

* **Barre de titre du système** (`frameless` seulement sous Windows, `app.py`) :
  boutons rouge/jaune/vert à gauche, déplacement, double-clic, plein écran et
  réduction natifs. La page ne crée pas sa barre (`_injectTitlebar` sort sur
  `EST_MAC`) et la marge de 36 px disparaît (`html.os-mac`). Choisi plutôt
  qu'une barre maison déplaçable : rien à réimplémenter, rien qui casse.
* **Taille** : `plateforme.zone_ecran_mac()` (écran sans barre des menus ni Dock,
  `NSScreen.visibleFrame`) donne le « plein écran » d'ouverture et sert à savoir,
  à la fermeture, si la fenêtre l'était (`windowMaximized`).
* **Fermeture** : bouton rouge, ⌘Q et ⌘W arrivent directement à `_on_closing`,
  sans le bouton Fermer de la page qui écrit d'abord ce qui attend. Sur Mac, la
  première fermeture est annulée, la page vide ses enregistrements
  (`_fermerApresVidange`), appelle `Api.fermeture_prete()`, et la fenêtre se
  ferme 0,3 s **après** la réponse : fermer pendant que pywebview renvoie cette
  réponse bloquait un fil pour toujours et l'app ne quittait plus (vu sur le
  test). Filets : 5 s si la page ne répond pas, `os._exit` 3 s après la fin de
  `webview.start()`.
* **⌘ au lieu de Ctrl** pour les raccourcis et dans les bulles d'aide ;
  `.txt-win` / `.txt-mac` pour « ce PC » / « ce Mac », `.win-seul` pour un réglage
  propre à Windows (recolorer les raccourcis).
* **Menus en français** : `plateforme.LOCALISATION_MAC`, passée à `webview.start`.
* **`private_mode` reste à sa valeur par défaut**, comme sous Windows : l'idée
  d'origine (`private_mode=False` « comme sous Windows ») reposait sur une erreur,
  pywebview 4.4.1 ouvre lui aussi WebView2 en navigation privée
  (`IsInPrivateModeEnabled`), donc le localStorage n'y survit pas non plus.
* Test (`_diag_fenetre`, 45 s) : barre, ⌘2, taille, puis une écriture laissée en
  attente et « Quitter » ; vu le 12/10/2026 : fermée seule en 2 s, écriture sur le
  disque, `windowMaximized` vrai.

## Build Mac

* `build/pilote-mac.spec` : à part de `pilote.spec` pour que le build Windows ne
  bouge pas. Même piège : `ui/vendor` doit rester dans les `datas`, et `pypdf`
  dans les `hiddenimports` (import des relevés PDF, comme `pilote.spec`). L'icône est
  `assets/icon.ico` (la même que Windows ; `icon_512.png` est exclue de git), convertie en `.icns` par PyInstaller.
* **`BUNDLE_ID = "io.github.arthur-soulard.pilote"`** : l'identité de l'app pour
  macOS (autorisations, préférences). Comme l'`AppId` de `installer.iss`, ne
  JAMAIS la changer une fois l'app distribuée.
* `build-mac.yml` ne se déclenche que sur la branche `mac` (et à la main). Il
  fabrique l'app, la lance, attend `/ping` et la ligne « fenêtre ouverte », prend
  une capture d'écran, vérifie que `Donnees` est dans Application Support et pas
  dans l'app. Depuis le 12/10/2026, `PILOTE_DIAG` essaie aussi Yahoo, Gmail et
  GitHub en HTTPS (annotation « HTTPS », voir l'inventaire). Les constats sortent en annotations (lisibles sans compte via
  l'API publique des check-runs) ; capture, journal et app zippée sont en artefact.

## Inventaire de ce qui reste propre à Windows

| Quoi | Où | Sur Mac aujourd'hui |
|---|---|---|
| Déplacement de la fenêtre, Agrandir, taille de l'écran, taille gardée | `index.html`, `app.py` | réglé (étape 3) : barre de titre du système, zone utile de l'écran |
| Remise au premier plan, icône à l'accent, raccourcis `.lnk` | `app.py`, `appicon.py` | sans effet (exceptions rattrapées) |
| Coins arrondis de l'écran de chargement (DWM) | `splash.py` | sans effet |
| Détection des clés USB (`GetLogicalDrives`, numéro de série) | `sauvegarde.py` | réglé (étape 4) : `/Volumes` et `diskutil` |
| OCR (`ocr_win.ps1`, Windows.Media.Ocr) | `sante.py`, `vocabulaire.py` | « OCR disponible uniquement sous Windows » |
| Installation de la mise à jour (`.bat`, `cmd.exe`, Setup) | `updater.py` | jamais proposée (étape 1) ; Paramètres affiche pourtant « À jour (dernière : vX) » même en retard : à corriger avant de distribuer |
| Raccourcis Ctrl, textes « Windows » | `index.html` | réglé (étape 3) : ⌘, « ce Mac » |
| ⌘Q (pywebview) : arrêt sans vider les enregistrements en attente (0,4 s) | pywebview | réglé (étape 3) : voir « Fenêtre Mac » |
| Mot de passe Gmail d'Actus chiffré par DPAPI (session Windows) | `actus.py` | seulement encodé en base64 (« b64: »), donc lisible dans `actus.json` et dans les sauvegardes : passer au Trousseau de macOS |
| Certificats HTTPS (Yahoo, Gmail, GitHub) : le Python embarqué n'utilise pas forcément ceux du système | `server.py`, `actus.py`, `updater.py` | test du 12/10/2026 (annotation « HTTPS ») : l'app compilée cherche ses certificats dans `/Library/Frameworks/Python.framework/Versions/3.11/etc/openssl/cert.pem`, le Python installé sur la machine de GitHub. Yahoo, Gmail et GitHub y répondent, mais un Mac ordinaire n'a pas ce fichier. Avec `/etc/ssl/cert.pem` (fourni avec macOS), les trois répondent aussi. **Réglé** : `plateforme.certificats_mac()`, en tête d'`app.py` avant tout contexte TLS, pointe `SSL_CERT_FILE` sur ce fichier quand celui du Python manque ; le test cache désormais le fichier de GitHub (`sudo mv`) : Yahoo, Gmail, GitHub OK et cours lu |
| Imprimer / PDF du rapport annuel : `frame.contentWindow.print()` dans une iframe | `index.html` | probablement sans effet : pywebview Mac ne remplace que le `window.print` de la page principale (`customize.js`), pas celui de l'iframe (vu le 12/10/2026, non essayé) |

## Gatekeeper (app non signée)

Depuis macOS Sequoia, le clic droit → Ouvrir ne contourne plus le blocage : lancer
l'app une fois, fermer l'avertissement, puis Réglages Système → Confidentialité et
sécurité → **Ouvrir quand même**. Une app non signée change d'identité à chaque
version : macOS peut redemander ses autorisations (accès à la clé USB) après une
mise à jour. À vérifier sur un vrai Mac : un fichier téléchargé par Pilote lui-même
(et non par le navigateur) ne porte pas la marque de quarantaine qui déclenche le
blocage.
