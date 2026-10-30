# Pilote sur Mac

Fiche détaillée tirée de `CLAUDE.md`, qui garde les règles générales (dont les six choses à ne jamais casser).

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
| 5 | Lecture des captures Santé (Vision), code Gmail dans le Trousseau, rapport annuel | fait (12/10/2026) : voir « Lecture d'images, Trousseau, rapport » (le Vocabulaire est sorti de Pilote en 4.4.0 : pas de PDFKit) |
| 6 | Mise à jour Mac (téléchargée et installée par Pilote), asset Mac dans `release.yml` (job séparé, qui ne bloque jamais le Setup), README et notice d'installation | fait (12/10/2026) : voir « Mise à jour sur Mac » ; publié en **4.4.8** |

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
  propre à Windows (recolorer les raccourcis ; sur Mac, Pilote.app suit l'accent
  toute seule depuis la 4.4.30, voir `docs/demarrage-et-icone.md`).
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

### Captures sur données d'exemple (job `ecrans-mac`, 12/10/2026)

Règle d'Arthur : une fonctionnalité doit être vérifiée sur Mac **et** Windows
avant d'être dite finie. Or le premier job démarre sur un utilisateur vierge :
sa capture ne montre que les Premiers pas, jamais la fonctionnalité.

* **`tests/donnees_exemple.py`** écrit un utilisateur « Camille » entièrement
  **fictif** (le dépôt est public) : PEA, un CTO, Mes comptes, Prêt, Sports,
  Santé, Patrimoine, pense-bête, toutes les tuiles allumées. Dates relatives au
  jour du test (un « prochain dividende » le reste). `nouveautesVues: 999.0.0`
  et `premiersPas` : rien ne s'ouvre par-dessus l'écran.
* **`tests/ecrans.txt`** : les écrans à photographier, une ligne par capture
  (onglet, puis défilement en px). **À mettre à jour à chaque fonctionnalité.**
  Une ligne qui commence par `plein ` est capturée en plein écran, Dock compris
  (27/10/2026, pour voir l'icône à l'accent).
* **`PILOTE_ECRANS`** (`app.py`, `_diag_ecrans`) : ouvre chaque écran
  (`goTab`, puis défilement sans l'effet « en douceur » de la page) et écrit
  « [ecran] n pret » ; le job prend alors la capture de la fenêtre (cadre lu
  par System Events, sinon tout l'écran).
* Job à part, qui reprend l'app du premier (artefact `pilote-mac`) : GitHub
  garde **50 annotations au plus par job**, et le premier en émet déjà une
  trentaine. Les captures sortent en morceaux « Ecran n i/N » (45 au plus,
  5 étapes de 9) ; taille et qualité baissent seules pour tenir (1024 px en
  qualité 45 au mieux).
* **`python tests/lire_tests.py <sha> <dossier>`** relit les deux tests sans
  compte (étapes, annotations) et recolle `capture-mac.jpg` et `ecran-<n>.jpg`.
* La fenêtre du Mac de GitHub fait 1024 × 681 : plus étroite que l'écran
  d'Arthur (1366). Premiers constats (12/10/2026), corrigés aussitôt : noms
  d'indices coupés sur la tuile Marchés (« S&P 5… »), libellés du Plafond du
  PEA sur deux lignes. Le reste des tuiles rend sous WebKit comme sous Windows.

## Inventaire de ce qui reste propre à Windows

| Quoi | Où | Sur Mac aujourd'hui |
|---|---|---|
| Déplacement de la fenêtre, Agrandir, taille de l'écran, taille gardée | `index.html`, `app.py` | réglé (étape 3) : barre de titre du système, zone utile de l'écran |
| Remise au premier plan | `app.py` | sans effet (exceptions rattrapées) |
| Icône à l'accent, raccourcis `.lnk` | `appicon.py` | réglé (4.4.29-4.4.31) : Dock pendant que Pilote tourne, Pilote.app recolorée seule au lancement et à l'enregistrement, caches du Dock et d'« Apps » rafraîchis (job `icone-mac`, macOS 26) |
| Coins arrondis de l'écran de chargement (DWM) | `splash.py` | sans effet |
| Détection des clés USB (`GetLogicalDrives`, numéro de série) | `sauvegarde.py` | réglé (étape 4) : `/Volumes` et `diskutil` |
| OCR (`ocr_win.ps1`, Windows.Media.Ocr) | `sante.py` | réglé (étape 5) : Vision d'Apple |
| Installation de la mise à jour (`.bat`, `cmd.exe`, Setup) | `updater.py` | réglé (étape 6) : `Pilote_Mac.zip`, Pilote se remplace lui-même |
| Raccourcis Ctrl, textes « Windows » | `index.html` | réglé (étape 3) : ⌘, « ce Mac » |
| ⌘Q (pywebview) : arrêt sans vider les enregistrements en attente (0,4 s) | pywebview | réglé (étape 3) : voir « Fenêtre Mac » |
| Mot de passe Gmail d'Actus chiffré par DPAPI (session Windows) | `actus.py` | réglé (étape 5) : Trousseau de la session |
| Certificats HTTPS (Yahoo, Gmail, GitHub) : le Python embarqué n'utilise pas forcément ceux du système | `server.py`, `actus.py`, `updater.py` | test du 12/10/2026 (annotation « HTTPS ») : l'app compilée cherche ses certificats dans `/Library/Frameworks/Python.framework/Versions/3.11/etc/openssl/cert.pem`, le Python installé sur la machine de GitHub. Yahoo, Gmail et GitHub y répondent, mais un Mac ordinaire n'a pas ce fichier. Avec `/etc/ssl/cert.pem` (fourni avec macOS), les trois répondent aussi. **Réglé** : `plateforme.certificats_mac()`, en tête d'`app.py` avant tout contexte TLS, pointe `SSL_CERT_FILE` sur ce fichier quand celui du Python manque ; le test cache désormais le fichier de GitHub (`sudo mv`) : Yahoo, Gmail, GitHub OK et cours lu |
| Imprimer / PDF du rapport annuel : `frame.contentWindow.print()` dans une iframe | `index.html` | réglé (étape 5) : pywebview Mac n'imprime que la page principale ; le rapport s'ouvre dans le navigateur (`Api.ouvrir_rapport`), où ⌘P l'imprime |

## Lecture d'images, Trousseau, rapport (étape 5, 12/10/2026)

* **Captures Santé** : `plateforme.ocr_mac` (Vision, mode précis, français puis
  anglais, **sans correction linguistique**, qui « corrigerait » les nombres) rend
  le même JSON qu'`ocr_win.ps1`. Vision donne des lignes : la boîte de chaque mot
  vient de `boundingBoxForRange`, puis est **resserrée sur ses pixels**. Sans ce
  resserrement, les boîtes de Vision ont la hauteur de la ligne, et `sante.py`, qui
  groupe lignes et libellés selon la hauteur des mots, prenait 18,5 % pour l'IMC.
  Vérifié sur une image d'essai à la mise en page FitDays : boîtes identiques au
  pixel près à celles de Windows, même lecture (poids 72,4, IMC 22,1, masse
  musculaire 55,3). Pas encore essayé sur de vraies captures FitDays lues sur Mac.
  Dépendance : `pyobjc-framework-Vision` (Mac seulement), `Vision` dans les
  `hiddenimports`.
  **Depuis la lecture refaite du 14/10/2026** (`docs/modules/sante.md`), l'image
  d'essai d'`_diag_mac_divers` reprend le piège de ce jour-là : bloc
  « Contraste » en haut (écarts, date d'une autre pesée), libellés sur deux
  lignes, valeurs colorées. Sous Windows, elle donne poids 75,9, IMC 24,0,
  graisse 20,3, graisse viscérale 7,0, âge corporel 24, **aucune date** et aucun
  doute : l'annotation « Divers » du test Mac doit dire la même chose.
  `_zoom` passe aussi par `plateforme.ocr_mac` : rien de propre à Windows.
* **Code Gmail d'Actus** : Trousseau de la session, par l'outil `security`
  (`actus.json` : `trousseau:<compte>`, un compte par utilisateur Pilote), retiré à la
  déconnexion. Par `security` plutôt que par l'API Security : l'élément appartient à
  `/usr/bin/security`, signé par Apple et stable, alors que l'app, non signée, change
  d'identité à chaque version et redemanderait l'accès après chaque mise à jour. Le
  code passe en argument de `security` le temps d'un appel (visible des seuls
  processus du même compte).
* **Rapport annuel** : sur Mac, « Imprimer » écrit le rapport dans le dossier
  temporaire de la session et l'ouvre dans le navigateur par défaut.

## Mise à jour sur Mac (étape 6, 12/10/2026)

* `release.yml` : un job `mac` (après le job Windows, `needs: build`) fabrique
  Pilote.app et joint **`Pilote_Mac.zip`** (`ditto`, qui garde les attributs du
  paquet) à la release. S'il échoue, le Setup est déjà publié.
* `updater.py` : sur Mac, la release propose `Pilote_Mac.zip` (`MAC_ASSET`, par
  l'API ou la page publique, comme le Setup). `_installer_mac` le télécharge, le
  décompresse, puis un script `/bin/sh` attend la fin de Pilote, met l'ancienne app
  de côté (`Pilote.app.ancienne`), pose la nouvelle (remet l'ancienne si ça rate), la
  relance par `open` et nettoie. Le fichier téléchargé par Pilote n'a pas la marque
  de quarantaine : pas de nouvel « Ouvrir quand même ». Les données sont hors de
  l'app (Application Support).
* **Pilote doit être dans Applications** (ou un dossier modifiable) : lancée depuis
  Téléchargements sans avoir été déplacée, l'app tourne d'une copie en lecture seule
  (App Translocation). `mac_a_deplacer()` le détecte : message au démarrage, et refus
  clair au moment d'installer.
* Test (`build-mac.yml`, « Update test ») : l'app posée dans /Applications installe
  une fausse version 99.0.0 servie en local (`PILOTE_MAJ_ESSAI`, seulement avec
  `PILOTE_DIAG`) ; vu le 12/10/2026 : fichier témoin en place, ancienne app retirée,
  app relancée. Le script retire `PILOTE_*` de l'environnement avant la relance
  (sinon l'app relancée refaisait la mise à jour d'essai).
* `build-windows.yml` : sur la branche `mac`, le build Windows de `release.yml` sans
  rien publier, lancé et vérifié, avant de fusionner dans main.

## Réseau local (macOS 15, 12/10/2026)

Vu sur le test Mac quand Pilote est ouvert par le Finder (`open`, comme chez un
utilisateur ; lancé depuis le terminal, la question ne se voyait pas) : « Allow
"Pilote" to find devices on local networks? ». Pilote n'a pourtant que deux
connexions, toutes deux sur 127.0.0.1 (`lsof` : 50317 et le port du serveur).

* **Refuser ne casse rien** : essayé le 12/10/2026, « Don't Allow » cliqué, puis
  Pilote relancé par le Finder : page et 7 modules chargés, Yahoo, Gmail et GitHub
  joignables, cours lu, et la question n'est pas reposée. 127.0.0.1 et internet ne
  relèvent pas de cette autorisation. Le README dit de refuser.
* **Cause probable** : `HTTPServer.server_bind` appelle `socket.getfqdn()`, dont la
  recherche du nom passe, sur macOS 15, par le réseau local. Indice : le petit
  serveur web de Python lancé par le test a fait poser la même question
  (« Allow "Python"… »). Le serveur Mac de Pilote s'en passe (`server._ServeurMac`,
  Windows inchangé), et l'Info.plist porte un texte (`NSLocalNetworkUsageDescription`)
  au cas où la question viendrait d'ailleurs. **Non vérifié** que la question a
  disparu : le test suivant n'a remonté aucune annotation.
* Juste après la fermeture d'une app, le port 7438 garde des connexions en attente
  (TIME_WAIT) : l'app relancée prend 7439 (`_find_free_port`), sans conséquence (la
  page lit son port dans `location.port`).

## Installation sans réglage (22/10/2026)

Demande d'Arthur : que Pilote marche sur Mac « avec le moins de paramètres
chiants possible ».

* **Une ligne dans le Terminal** (README) : `curl` télécharge
  `releases/latest/download/Pilote_Mac.zip`, `ditto` le décompresse dans
  /Applications, `open` le lance. Un fichier téléchargé par `curl` ne porte pas
  la marque de quarantaine : pas d'« Ouvrir quand même », pas de copie en lecture
  seule, pas d'« endommagé ». Essayé par `build-mac.yml` (« Install test ») sur
  la vraie dernière release.
* **Par le navigateur** : Gatekeeper reste (sans compte Apple, rien à faire), mais
  Pilote ouvert depuis Téléchargements (App Translocation) propose de se ranger
  lui-même dans Applications (`updater.mac_ranger`) : l'emplacement d'origine vient
  de `SecTranslocateCreateOriginalPathForURL`, un script attend la fin de Pilote,
  déplace l'app (/Applications, ou ~/Applications pour un compte non
  administrateur ; un ancien Pilote y est remplacé), retire la quarantaine et la
  relance. L'ancien message « Glisse Pilote dans Applications » ne reste que si
  macOS ne donne pas l'emplacement d'origine. **Non vérifié** : sur la machine de
  GitHub, Gatekeeper retient l'app avant qu'elle s'ouvre (personne pour « Ouvrir
  quand même »), et `SecTranslocateCreateSecureDirectoryForURL` appelée par un
  script n'y crée pas de copie (« Rangement test » : None).
* **Réseau local** : plus de question depuis `server._ServeurMac` (test du
  21/10/2026 : aucun bouton « Ne pas autoriser » trouvé après une ouverture par
  le Finder). Retiré du README.

## Sélecteur de fichiers (22/10/2026)

pywebview 6.2.1 (`runOpenPanelWithParameters`) ne filtre la fenêtre du Finder
que par les **types MIME** d'`accept` (`_acceptedMIMETypes`) et ignore les
extensions. L'import des relevés déclarait `text/csv, application/pdf,
application/zip` : un .xlsx, .xls, .ods, .xml, .txt ou .html y était grisé sur
Mac. `ctoOuvrirImport` n'y garde que les extensions : aucun filtre, tout se
choisit, et Pilote dit lui-même ce qu'il ne sait pas lire. Windows inchangé.
Le test (`_diag_fichiers`, annotation « Modules ») note ce que pywebview reçoit,
avant et après.

## Tour complet (22/10/2026)

`tests/ecrans-tour.txt` : tous les onglets, les sections des Paramètres,
quelques fenêtres et une notification. Le job `ecrans-mac` est découpé en lots
de 3 captures (job `lots`, puis une matrice) : chaque lot a ses 50
annotations, les captures restent nettes. Chaque écran relève aussi les erreurs
JavaScript du journal de la page (« [ecran] n erreurs JS »).

## Gatekeeper (app non signée)

Depuis macOS Sequoia, le clic droit → Ouvrir ne contourne plus le blocage : lancer
l'app une fois, fermer l'avertissement, puis Réglages Système → Confidentialité et
sécurité → **Ouvrir quand même**. Une app non signée change d'identité à chaque
version : macOS peut redemander ses autorisations (accès à la clé USB) après une
mise à jour. À vérifier sur un vrai Mac : un fichier téléchargé par Pilote lui-même
(et non par le navigateur) ne porte pas la marque de quarantaine qui déclenche le
blocage.
