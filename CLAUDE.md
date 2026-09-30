# Pilote

Application desktop Windows de suivi personnel : bourse (PEA), budget, prêt étudiant,
sport, santé et patrimoine réunis dans une seule app 100 % locale, multi-utilisateurs.
Aucune donnée ne sort du PC — pas de compte, pas de serveur distant, pas de télémétrie.

Stack : Python + pywebview (fenêtre native avec UI HTML/CSS/JS), PyInstaller pour
compiler en .exe, Inno Setup pour le Setup.exe, GitHub Actions pour build + release.

**Version actuelle : 4.3.10**
(l'app s'appelait « Suivi PEA » jusqu'à la 4.1.0, le dossier du dépôt jusqu'à la 4.1.1)

Dépôt : `C:\Users\Arthur\Desktop\Pilote` — branche `main`, remote
`github.com/arthur-soulard/arthurpilote.github.com` (le nom du dépôt est historique,
il ne suit pas le nom de l'app).

## Structure

```
Pilote/
├── src/
│   ├── app.py          # Point d'entrée, bridge Python↔JS, APP_NAME, APP_VERSION
│   ├── server.py       # Serveur HTTP local (port 7438) + PIN
│   ├── storage.py      # Données PEA + multi-utilisateurs + migrations
│   ├── finances.py     # Module « Mes comptes »   (finances.json)
│   ├── sports.py       # Module « Sports »        (sports.json) + catalogue + champs
│   ├── pret.py         # Module « Prêt étudiant » (pret.json)
│   ├── sante.py        # Module « Santé »         (sante.json) + lecture OCR FitDays
│   ├── ocr_win.ps1     # OCR via Windows.Media.Ocr — appelé par sante.py et vocabulaire.py
│   │                   #   (+ rendu des pages d'un PDF en images, mode -PdfDir)
│   ├── patrimoine.py   # Module « Patrimoine »    (patrimoine.json)
│   ├── formation.py    # Module « Formation »     (formation.json) + certificats
│   ├── vocabulaire.py  # Module « Vocabulaire »   (vocabulaire.json) + 4 boîtes + lecture d'images
│   ├── jsonstore.py    # Socle commun : écriture atomique + backup quotidien 7 j
│   ├── sauvegarde.py   # Sauvegarde externe sur clé USB (miroir + archives zip)
│   ├── appicon.py      # Icône recolorée selon la couleur d'accent
│   ├── splash.py       # Petite fenêtre de chargement affichée au lancement
│   ├── updater.py      # Auto-updater (check + download + install)
│   ├── notifications.py
│   └── ui/
│       ├── index.html  # TOUTE l'UI (HTML + CSS + JS dans un seul fichier, ~18 700 lignes)
│       └── vendor/     # Chart.js, polices woff2, icônes Phosphor : servis en local (aucun CDN)
├── build/
│   ├── installer.iss   # Script Inno Setup utilisé par la CI (AppVersion à bumper)
│   ├── pilote.spec     # Spec PyInstaller → dist/Pilote/ (Pilote.exe + _internal/)
│   └── build.bat       # build local
├── assets/             # icon.ico + make_icon.py (générateur d'icône)
├── .github/workflows/release.yml
└── requirements.txt    # pywebview, pyinstaller, win10toast, pillow
```

En dev, `Donnees` à la racine du dépôt est un lien symbolique vers le dossier de
données de l'app installée.

## Données sur disque

Tout vit dans `<racine app>/Donnees/`. **Chaque utilisateur a son propre dossier**,
tous modules confondus :

```
Donnees/
├── users.json                # liste des utilisateurs + utilisateur actif
├── sauvegarde.json           # config de la sauvegarde USB (niveau installation)
├── users/<slug>/
│   ├── pea_data.json         # PEA              (+ backups/)
│   ├── finances.json         # Mes comptes      (+ backups_finances/)
│   ├── sports.json           # Sports           (+ backups_sports/)
│   ├── pret.json             # Prêt étudiant    (+ backups_pret/)
│   ├── sante.json            # Santé            (+ backups_sante/)
│   ├── patrimoine.json       # Patrimoine       (+ backups_patrimoine/)
│   ├── formation.json        # Formation        (+ backups_formation/)
│   ├── vocabulaire.json      # Vocabulaire      (+ backups_vocabulaire/)
│   ├── certificats/          # PDF et images des formations validées
│   └── pin.hash              # code PIN de CET utilisateur (si configuré)
├── icones/                   # .ico générés à la couleur d'accent
└── crash.log
```

Rien n'est partagé entre deux utilisateurs — même le thème, la couleur d'accent et
les onglets masqués sont propres à chacun (ils vivent dans `pea_data.json`).

`storage.get_user_dir()` est la racine que `jsonstore.py` et `finances.py` utilisent.

### `_cache` : dans le fichier courant, jamais dans les backups

`pea_data.json` contient une clé `_cache` (cours et historiques Yahoo) qui pèse à
elle seule plus que toutes les données réunies : ~200 Ko contre ~6 Ko. Elle est
volontairement persistée — c'est ce qui fait vivre l'app **hors ligne**
(`Api.load_data` la repasse au serveur via `server.hydrate_cache`).

Mais `storage._daily_backup()` l'**exclut** : un backup ne doit contenir que
l'irremplaçable. Sans ça, 200 Ko de cache régénérable étaient recopiés sept fois
par utilisateur, puis embarqués dans chaque archive de sauvegarde USB. Backup du
jour : 10 Ko au lieu de 418 Ko. Ne pas « simplifier » en resérialisant `data` tel quel.

### Migrations automatiques (idempotentes, ne jamais les supprimer)

* `storage.ensure_migrated()` — une installation antérieure à la 4.1.2
  (`profiles.json` + fichiers de modules à la racine) est déplacée vers
  `users/<slug>/` au premier lancement. `profiles.json` devient `profiles.legacy.json`.
* `storage.migrate_legacy_pin()` — le PIN, global jusqu'à la 4.1.3, est attribué au
  **premier** utilisateur. Appelée au démarrage de `main()` et en fin de `ensure_migrated()`.

## ⚠ Cinq choses à ne JAMAIS casser

1. **`_PIN_SALT`** dans `src/server.py` → sert au hash des codes PIN déjà enregistrés.
2. **L'`AppId` GUID** dans `build/installer.iss` → c'est l'identité de l'installation.
   C'est grâce à lui que le renommage en Pilote n'a pas déplacé les données : le Setup
   reconnaît l'installation existante et réinstalle dans son dossier. Conséquence : le
   dossier d'installation s'appelle toujours `%LocalAppData%\Programs\Suivi PEA\`.
   C'est normal, ne pas « corriger ».
3. **La sémantique de `_hydrationDone`** (index.html) → ce drapeau autorise l'écriture
   disque. Il doit suivre la **réussite de la lecture** (`!_debug.load_error`), jamais le
   volume de données : un utilisateur qui vient d'être créé a un PEA vide et doit
   pouvoir enregistrer. Côté Python, un `pea_data.json` absent n'est **pas** une erreur
   de lecture (`storage.load_data()` laisse `error` à `None`).
4. **`ocr_win.ps1` dans les `datas` de `build/pilote.spec`** → sans cette ligne, l'OCR
   des modules Santé et Vocabulaire fonctionne parfaitement en dev et **échoue
   silencieusement dans l'exe compilé** : le script est introuvable, `ocr_available()`
   répond « Script OCR introuvable » et l'import de captures ne marche plus. Une panne invisible tant
   qu'on ne teste pas le binaire. Vérification : `dist/Pilote/_internal/ocr_win.ps1`
   doit exister après le build.

5. **`src/ui/vendor/` dans les `datas` de `build/pilote.spec`** → même piège que
   `ocr_win.ps1` : sans cette ligne, Chart.js, les polices et les icônes sont
   introuvables dans l'exe compilé. Les graphiques disparaissent, la typo retombe sur
   celle du système et les boutons perdent leurs icônes, alors que tout marche
   parfaitement en dev. Vérification : `dist/Pilote/_internal/ui/vendor/` existe.
## Sauvegarde externe sur clé USB (`sauvegarde.py`)

Contrairement à tout le reste, ce module est au niveau de **l'installation**, pas de
l'utilisateur : une sauvegarde embarque le dossier `Donnees/` entier (tous les
espaces, `users.json` compris), pour pouvoir remonter l'installation complète.
Sa config vit donc dans `Donnees/sauvegarde.json`, à côté de `users.json`.

* Une sauvegarde = `Pilote_YYYY-MM-DD_HHhMM.zip` dans la destination. Deux
  sauvegardes dans la même minute portent le même nom et s'écrasent : c'est voulu.
* Écriture en `.zip.part` puis `os.replace()` — une clé débranchée en plein milieu
  ne laisse jamais une archive tronquée sous un nom valide.
* `icones/` et les `.tmp` sont exclus (regénérables). Les `backups_*` sont inclus.
* **La clé est retrouvée par son numéro de série de volume**, pas par sa lettre :
  `E:` qui devient `F:` au rebranchement suivant est suivi automatiquement
  (`_volume_info()` via `GetVolumeInformationW`). Si la clé mémorisée est absente,
  on ne se rabat **pas** sur le chemin brut — il pointerait sur une autre clé ayant
  hérité de la lettre.
* **Un numéro de série nul (`00000000`) est traité comme absent.** Constaté sur une
  vraie clé FAT32 bas de gamme : elle n'en a pas. Le garder reviendrait à « reconnaître »
  n'importe quelle autre clé sans numéro. Repli alors sur le **nom de volume**, puis
  sur le chemin brut. Ne pas « simplifier » en refaisant confiance au numéro.
* Rotation : les `keep` archives les plus récentes (10 par défaut).
* Auto au démarrage dans un thread (`main()`), silencieuse si la clé est absente.
* `restore_from()` : valide l'archive, écrit une archive de sécurité de l'état
  actuel à côté de `Donnees/`, puis **écrase fichier par fichier sans vider le
  dossier** — une archive incomplète ne doit jamais faire disparaître un
  utilisateur qui n'y figure pas. `sauvegarde.json` est volontairement exclu de la
  restauration (sinon on repointerait vers une clé qu'on n'utilise plus).
  Protection zip-slip sur chaque membre.
* API : `sauvegarde_status`, `sauvegarde_set_config`, `sauvegarde_pick_folder`,
  `sauvegarde_use_drive`, `sauvegarde_run`, `sauvegarde_list`,
  `sauvegarde_restore`, `sauvegarde_open_folder`, `sauvegarde_push_usb`,
  `sauvegarde_usb_state`.
* UI : Paramètres → **Sauvegarde USB** (`data-sec="sauvegarde"`), fonctions `sv*`.
  `setGoSection()` déclenche `svRefresh()` seulement à l'ouverture de cette
  section — elle interroge le disque.
* Rien n'est chiffré : le zip est aussi lisible que les JSON d'origine.

**Deux mécanismes distincts, volontairement :**

| | Bouton « 🔑 Téléverser » (accueil) | Archives (Paramètres) |
|---|---|---|
| Écrit | `<clé>/Pilote/Donnees/` en miroir | `Pilote_<date>.zip` |
| Historique | aucun, on écrase | rotation des N dernières |
| Pour | récupérer ses fichiers tout de suite | remonter dans le temps |

`push_to_usb()` choisit la clé toute seule s'il n'y en a qu'une, sinon l'UI
demande laquelle. Le miroir **n'efface jamais** de fichier sur la clé : un
dossier Donnees vidé par accident ne doit pas détruire la sauvegarde.

## Multi-utilisateurs

* API Python (`Api` dans app.py) : `get_users`, `add_user(label, emoji, color)`,
  `update_user`, `delete_user`, `set_active_user`.
* `storage.slugify()` fabrique le slug de dossier. `delete_user` retire l'utilisateur
  de la liste mais **conserve son dossier** sur le disque.
* Côté JS : `USERS_STATE`, `_loadUsers(force)`, `renderHomeUsers()`, `switchUser(slug)`
  (bascule + `location.reload()`), `openUserModal(slug|null)`, `renderUsersList()`,
  `_renderUserPill()` (pastille en bas de sidebar), `userAvatarHtml(u, cls)`.
* `server.with_pin_flags(state)` ajoute `hasPin` à chaque utilisateur — utilisé pour
  afficher le cadenas 🔒.
* **Isolation** : `storage.scan_orphan_data()` exclut tout ce qui vit sous
  `get_app_dir()`. Sans ça l'écran de bienvenue proposerait d'importer les données
  d'un autre utilisateur de la même installation. Ne pas retirer ce filtre.

## Code PIN (un par utilisateur)

* Hash SHA-256 salé dans `users/<slug>/pin.hash`.
* Endpoints `/pin/required`, `/pin/set`, `/pin/check` — tous acceptent `?user=<slug>` ;
  sans ce paramètre ils répondent pour l'utilisateur actif.
* JS : `_isPinRequired(slug)`, `_verifyPin(pin, slug)`, `_setPinServer(pin, slug)`,
  `_checkPinLock()` (écran de verrouillage, awaité dans `boot()` **avant** `renderAll()`).
* L'écran de verrouillage affiche l'avatar + le nom du compte verrouillé et propose
  d'ouvrir un autre compte (chacun reste protégé par son propre code).
* Ça sépare les espaces, ça ne chiffre rien : les JSON restent lisibles sur le disque.

## Démarrage : écran de chargement (`splash.py`, 4.2.7)

La fenêtre principale est créée **cachée** (`hidden=True`) et ne s'ouvre qu'une fois
l'accueil prêt. En attendant, une petite fenêtre sans bordure (300 × 230) montre le
logo « P » à la couleur d'accent, « Pilote » et trois points qui s'allument, dans le
thème de l'utilisateur actif.

* `boot()` appelle `_appReady()` → `Api.app_ready()` → `reveal_main_window()` (app.py) :
  montre la fenêtre, ferme l'écran de chargement, pose l'icône à l'accent. Une seule
  fois (`_revealed`). Le signal part **après** les modules et le premier chargement
  des cours (5 s au plus : sans réseau on ouvre avec les derniers connus), dans le
  `catch` de `boot()` aussi, et **dès l'écran du code PIN** (`_checkPinLock`) : le
  code se tape dans la fenêtre, elle ne peut pas rester cachée.
* **Filet de sécurité** : `REVEAL_TIMEOUT` (20 s), un `threading.Timer` qui ouvre la
  fenêtre quoi qu'il arrive. Un JS en panne ne doit jamais laisser l'app invisible.
* **`WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS`** (posée dans `main()`) : cachée,
  une fenêtre WebView2 freine ses minuteurs JS à un par seconde (mesuré : 20
  `setTimeout` de 10 ms en 2,8 s au lieu de 0,3 s), et c'est cachée qu'elle charge.
  Les options `--disable-background-timer-throttling`, `--disable-renderer-backgrounding`
  et `--disable-backgrounding-occluded-windows` lèvent le frein. Ne pas les retirer.
  `--disable-features=ElasticOverscroll` y est recopiée : c'est l'option que pywebview
  passe lui-même.
* La fenêtre principale est créée **en premier** : `webview.windows[0]` reste elle
  (minimize, close, dialogues, updater).
* Le HTML de l'écran est construit en Python (pas de `splash.html`, qui devrait
  entrer dans les `datas` de la spec : le piège d'`ocr_win.ps1`). Les polices viennent
  de `ui/vendor/fonts`, inlinées en `data:` : la page n'a pas d'origine et ne peut
  rien demander au serveur local.
* Mesuré sur la machine d'Arthur : écran de chargement vers 4 s après le lancement
  (import Python + WebView2), fenêtre complète entre 6,5 et 12,5 s selon la charge.
  Ces chiffres sont ceux du **dev** (`python src/app.py`) : l'exe ajoutait sa
  décompression par-dessus (voir le point suivant).
* **Exe en format dossier (onedir), depuis la 4.2.8.** Jusque-là `Pilote.exe` était un
  exe unique (onefile) qui se décompressait à **chaque** lancement : 217 fichiers,
  36 Mo dans `%TEMP%\_MEI*`, que Defender inspecte un par un. Mesuré sur l'exe
  installé : 4 à 6,5 s avant le moindre affichage, et 39 s le 26/09/2026 au premier
  lancement de la journée. `build/pilote.spec` produit désormais `dist/Pilote/`
  (lanceur `Pilote.exe` + `_internal/`), installé une fois par le Setup. Sur deux
  builds de test identiques, médianes de 6 à 9 lancements : écran de chargement
  7,3 s → 3,0 s, fenêtre complète 15,9 s → 10,3 s. **Ne pas revenir en onefile.**
  Le premier lancement après une mise à jour reste plus lent (16 s mesuré) :
  Defender inspecte les nouveaux fichiers, une seule fois. Le Setup est aussi plus
  léger (21,8 Mo contre 32 Mo sur les mêmes builds de test).
* **`import encodings.idna` en tête d'`app.py` (4.2.8), ne pas retirer.** Au
  démarrage, le serveur local (`getfqdn`) et la vérification de mise à jour (HTTPS)
  chargent le codec idna en même temps dans deux fils ; dans l'exe compilé, l'un des
  deux reçoit `LookupError: unknown encoding: idna` et l'app plante avant de
  s'ouvrir (fenêtre « Unhandled exception in script »). Vu sur des builds de test en
  Python 3.8 : 5 lancements sur 20 ; 0 sur 10 avec l'import anticipé. Jamais observé
  sur la 4.2.7 officielle (Python 3.11), gardé par précaution.
* Un second lancement pendant le chargement ne force pas l'ouverture
  (`_listen_for_focus_pings` attend `_revealed`).

## Icône à la couleur du thème (`appicon.py`)

* Regénère un `.ico` multi-résolution (PNG embarqués, supersampling 4× + LANCZOS,
  même rendu que `assets/make_icon.py`) à la couleur d'accent, mis en cache dans
  `Donnees/icones/pilote_<hex>.ico`.
* Appliqué à la fenêtre + vignette barre des tâches via `WM_SETICON`, sur
  l'écran de chargement puis à l'ouverture de la fenêtre (`_paint_accent_icon`,
  appelée par `reveal_main_window`) et à chaque enregistrement des paramètres
  (`Api.set_app_icon_color`).
* Les raccourcis Windows (.lnk du Bureau, menu Démarrer, barre des tâches épinglée)
  ne se recolorent que sur demande explicite : bouton « 🎨 Recolorer les raccourcis »
  dans Paramètres → Général (`Api.apply_icon_to_shortcuts`, via WScript.Shell).
* L'icône gravée dans le `.exe` reste celle du build : elle ne peut pas changer à chaud.
* Pillow est déclaré dans les `hiddenimports` de `build/pilote.spec` (import paresseux).

## Pour sortir une nouvelle version

1. Modifier le code
2. Bumper `APP_VERSION` dans `src/app.py`
3. Bumper `AppVersion` dans `build/installer.iss`
4. `git add … && git commit && git tag vX.Y.Z && git push origin main && git push origin vX.Y.Z`
5. GitHub Actions build `dist/Pilote/` puis `Pilote_Setup.exe`, et crée la release
   avec le Setup pour seul fichier (un `Pilote.exe` seul ne tourne pas sans son
   `_internal/`)

Règle importante : le numéro de version ne peut qu'augmenter (comparaison sémantique).
Ne jamais descendre sinon l'auto-updater croit que l'app est déjà à jour.

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

## Navigation

Titlebar custom (fenêtre frameless, 36 px) : logo + « Pilote » + boutons fenêtre.
C'est le seul endroit où « Pilote » est écrit.
Topbar minimale : fil d'Ariane (« Accueil », « PEA › Positions »), indicateur
« Dernière actualisation HH:MM » avec Actualiser (`.refresh-grp`), et Retour (undo).
Le fil d'Ariane est écrit par `_updateCrumb(id)`, appelée à la fin du `goTab`
**d'origine** et pas dans un patch : chaque patch rappelle la version d'origine, le fil
suit donc tous les chemins de navigation (barre latérale, tuiles, Ctrl+1..7).

Sidebar : un onglet **Accueil** seul en tête, puis 8 sections en accordéon
(`NAV_SECTIONS` dans index.html). Une seule section dépliée à la fois, un second clic
sur l'en-tête la referme, aucune section n'est obligatoirement ouverte. Une pastille
marque la section contenant l'onglet actif. En bas : pastille utilisateur, thème,
Paramètres.

| Entrée          | Onglets (ids des panes : `pane-<id>`)                              |
|-----------------|--------------------------------------------------------------------|
| Accueil         | home                                                               |
| PEA             | dash, pos, sector, div, tx, wish, dep, strat, sim (plus de `perf`) |
| Mes comptes     | fin-month, fin-year                                                |
| Prêt étudiant   | pr-overview, pr-pea, pr-av, pr-liv, pr-params                      |
| Sports          | sp-agenda, sp-goals, sp-stats                                      |
| Patrimoine      | pa-vue, pa-comptes                                                 |
| Santé           | sa-suivi, sa-mesures, sa-goals                                     |
| Formation       | fo-todo, fo-done, fo-cv, fo-stats                                  |
| Vocabulaire     | vo-reviser, vo-boites, vo-mots, vo-stats                            |

Fonctions : `_injectSidebar()`, `_setActiveSidebar(id)`, `_navToggleSection(secId)`,
`_navSectionOf(tabId)`. Section dépliée persistée dans `S.uiPrefs.navOpen` ("" = tout
replié). `SIDEBAR_ITEMS` reste dérivé à plat de `NAV_SECTIONS` pour l'API historique
(onglets masquables via ⊘, Ctrl+1..7, écran Paramètres).

Chaque module annexe ajoute son propre patch de `window.goTab` en fin de fichier
(finances, sports, prêt, accueil) : ils s'enchaînent, ne pas casser l'ordre.

## Identité visuelle « Carnet » (septembre 2026)

Choisie par Arthur parmi trois maquettes (Net, Carnet, Cockpit) : un carnet de bord
plutôt qu'un logiciel de bureau.

* **Polices** : Newsreader (`--serif`) pour la salutation, les titres de carte et les
  grands chiffres ; Onest (`--font`) pour tout le reste. `--mono` garde son nom
  historique mais pointe sur Onest : les deux polices ont des chiffres de largeur
  fixe, les colonnes restent alignées (vérifié : « 111111 » et « 000000 » ont la même
  largeur). Plus Jakarta Sans et JetBrains Mono restent dans `vendor/fonts/`, gardées
  à la demande d'Arthur, mais plus rien ne les utilise.
* **Couleurs** : fond papier (`--bg #f1ebe0`), cartes crème (`--bg2`), thème sombre
  brun chaud. Le vert et le rouge ne disent que hausse ou baisse : les montants neutres
  (dépôts, valeur, frais, dividendes) restent à la couleur du texte, fini les cartes
  arc-en-ciel. `--accent-soft` et `--accent-text` sont dérivés de l'accent choisi par
  `color-mix()` : lisibles quelle que soit la couleur réglée dans les paramètres.
* **Accent par défaut : prune `#9c4a7a`** (4.2.4), à trois endroits qui doivent rester
  égaux : `--accent` dans `:root`, `ACCENT_DEFAULT` (index.html, aussi ajoutée aux
  pastilles) et `DEFAULT_COLOR` dans `appicon.py`. Choisie parce qu'elle ne ressemble
  ni au vert des gains, ni au rouge des pertes, ni à l'ambre des alertes : la terre
  cuite a été écartée pour cette raison, le bleu encre parce qu'il doublait le bleu
  des badges d'information. Un utilisateur qui a déjà choisi sa couleur la garde ;
  celui qui n'en a jamais choisi passe de l'ambre à la prune.
* **Formes** : cartes sans bordure avec une ombre douce (`--radl` 16 px), boutons et
  entrées de la barre latérale en pilule, un point d'accent sur l'onglet ouvert,
  libellés en casse normale (plus de petites MAJUSCULES espacées).
* **Icônes** : Phosphor regular, servies par `/vendor/phosphor/` (woff2 seul, licence
  MIT). Les emoji des catégories, des sports, des domaines… sont des DONNÉES de
  l'utilisateur et restent. Depuis la 4.2.6, **tous** les boutons en portent une,
  modules compris (+, ✎, ✕, 🗑, ⚙, ←/→… convertis, menu des Paramètres aussi) ;
  `ebtn()`/`dbtn()` (Modifier / Supprimer des tableaux) ont un `title` et un
  `aria-label`, comme tout bouton qui n'a qu'une icône. Les messages d'état
  (« ✓ À jour ») gardent leur caractère : ce ne sont pas des boutons.
* **Où c'est** : les jetons dans `:root` et `html[data-theme="dark"]`, puis un bloc
  « IDENTITÉ CARNET » **en fin de la première feuille de style**, qui surcharge les
  composants plutôt que de réécrire chaque règle. Un nouveau composant réutilise ces
  jetons, jamais une couleur en dur.
* **Graphiques** : un `<canvas>` n'hérite pas du CSS. En tête du premier script :
  `Chart.defaults` (Onest, gris chaud `#8b8072` lisible sur les deux fonds, grille fine
  sans cadre, barres arrondies, légendes en pastilles, infobulle sombre) et trois
  aides : `carnetChartColors()` lit les variables CSS au moment de dessiner,
  `carnetAlpha(hex, a)`, `carnetAreaFill(hex)` donne la surface en dégradé sous une
  courbe. Les courbes du PEA prennent l'accent + cette surface ; gain ou perte se
  lisent dans le résumé (vert/rouge), pas dans la couleur du trait ; les versements
  sont un pointillé gris. `CLRS` (camemberts du PEA) est une palette sourde
  accordée au papier ; les couleurs portées par les données restent celles choisies.
  **Changement de thème ou d'accent** : un `MutationObserver` sur `<html>`
  (`data-theme`, `style`) appelle `carnetRedrawCharts()`, qui redessine la courbe
  « Évolution du capital ».
* **Vue d'ensemble du PEA = ex-onglet Performance (4.2.6).** L'onglet Performance
  n'existe plus : `pane-dash` reçoit, dans cet ordre, le bandeau fiscal, les cinq
  chiffres clés, la carte `#card-twr` (la courbe complète : comparaison CAC 40 /
  S&P 500 / ETF World, pastilles de période, résumé) puis `#dash-duo` =
  « Plus/moins-values réalisées » (2/3) + « Répartition » en barres (1/3). Tout est
  déplacé par `_injectDashboardPane`. Le `goTab` d'origine appelle `renderPerf()` et
  `dashRenderOverview()` sur `"dash"`, et redirige `"perf"` vers `"dash"` (tuile,
  raccourci ou préférence qui viserait encore l'ancien onglet). Les deux camemberts
  et la carte thermique ont été **supprimés à la demande d'Arthur** (avec
  `makePie`, `renderHeatmap`, `_layoutTreemap`, `_hmColor`). La répartition prend la
  même base que la colonne de l'onglet Positions (valeur des titres, hors espèces).
  `perfSeriesAsync()` charge l'historique une seule fois pour les tuiles de l'accueil
  et partage `_perfHistory`/`_perfFullSeries` avec la courbe.
* **Carte « Valeur du PEA » = titres + espèces (4.2.6).** Elle affichait les titres
  seuls (1 464,15 €) quand la courbe, la tuile de l'accueil et le module Patrimoine
  affichaient titres + espèces (1 469,64 €) : 5,49 € d'écart, le solde espèces.
  Calculs revérifiés à la main sur les vraies données, tous justes ; seule la
  définition différait. La bonne est titres + espèces : c'est la valeur à laquelle
  se mesure le rendement (valeur − versements) et celle d'un PEA pour la banque.
  Le détail titres / espèces / investi reste sous le chiffre.
* **Mini-graphiques des tuiles** : un widget peut renvoyer `viz` (HTML) dans
  `render()`. `dashSpark(valeurs, depuis)` (courbe SVG ; `depuis`, facultatif,
  estompe le trait avant cet indice), `dashProgress(pct, g, d)`,
  `dashSportWeeks()` (heures des 4 dernières semaines), `dashPeaSpark("pv"|"val")`
  (6 mois de la série Performance). Colorés par le CSS : ils suivent thème et accent
  sans être redessinés. Seulement là où il y a de vraies données : pas de graphique
  inventé. La progression de l'objectif sportif vient de `spGoalTimeline(g)`,
  partagée avec la carte de l'onglet Objectifs.
* **Tuile raccourci « Ajouter une dépense »** (`depense`, module `Comptes`, 4.2.6) :
  les dépenses du mois (`finComputeMonthTotals`, la même que la carte « Dépenses du
  mois ») et un bouton qui ouvre `finOpenTx("expense")` depuis l'accueil
  (`dashAddExpense()`, qui charge Mes comptes si besoin). Éteinte par défaut comme
  toute nouvelle tuile ; `finSaveTx` rappelle `dashRender()` pour que le total suive.
  En mode édition le bouton est inerte : le clic sert à changer la tuile.
* **Pastilles de période** : classe `.rng` (vue d'ensemble et `#perf-range-btns`),
  l'active porte `aria-pressed="true"` ou `.btn-primary`.
* **Tableaux** : dans un `.tw`, les cellules chiffrées ne passent plus à la ligne
  (« 70,64 » / « € ») : le tableau défile dans son cadre.
* **Cache** : `/vendor/` est servi avec `max-age` d'un jour. Le lien porte
  `fonts.css?v=2` : **incrémenter ce numéro à chaque modification de `fonts.css`**,
  sinon un navigateur garde l'ancienne feuille et les nouvelles polices n'existent pas.

## Page d'accueil (`pane-home`)

Ouverte au démarrage. `homeGreeting()` renvoie « Bonjour » avant 18 h, « Bonsoir » après ;
`homeDisplayName()` prend le nom de l'utilisateur actif (sinon `S.prenom`).

Mise en page alignée à gauche : grande salutation en serif (`clamp(40px, 5vw, 60px)`),
écrite par `homeRenderGreeting()` avec le prénom dans un `<em>` (italique, couleur
d'accent) ; `renderHomeUsers()` la rappelle quand la liste des utilisateurs arrive.
Puis la date en italique, le rang des utilisateurs à gauche (`#home-users`, cliquable
pour basculer + « Nouvel utilisateur ») et à droite les boutons Paramètres / Exporter /
Importer / Téléverser vers clé USB avec l'état de la clé (`#home-usb-state`). Sous
1150 px de large, tout s'empile. Enfin « Tableau de bord » (`.dash-title`), le crayon
et les tuiles, chacune avec l'icône de son module (`DASH_ICONS`).

`svPushToUsb()` sauve et restaure le libellé du bouton USB en `innerHTML`, pas en
`textContent` : sinon l'icône disparaît après la première copie.

Depuis la 4.1.4, `homeRender()` ne fait plus que la salutation et la date : **les tuiles
sont déléguées à `dashRender()`** (voir « Accueil : tableau de bord modulaire »). Il n'y
a plus de carte codée en dur.

`homeRender()` est rappelée par `renderMetrics()`, `spBootstrap()`, `saRenderAll()`,
`paRenderAll()`, la fin de `boot()` et à chaque `goTab("home")` — ce dernier
rafraîchit aussi l'état de la clé USB (`svRenderUsbState()`) et sort du mode
édition des tuiles quand on quitte l'accueil.

**Écran de bienvenue** (`_showWelcomeIfFirstRun()`) : s'affiche quand le PEA est vide,
donc aussi pour chaque utilisateur nouvellement créé. Il présente les suivis,
rappelle de quel espace il s'agit, et ne propose en récupération que des installations
**extérieures** (voir `scan_orphan_data`).

## Paramètres (`openSettings(section)`)

Modale unique à colonne de sections (`setGoSection(id)`), plus « paramètres du PEA » :

| Section    | Contenu                                                            |
|------------|--------------------------------------------------------------------|
| general    | thème, couleur d'accent, icône de l'app, code PIN de l'utilisateur  |
| users      | liste des utilisateurs, création / édition                          |
| nav        | onglets et blocs masqués (restauration)                             |
| pea        | prénom, banque, date d'ouverture, récap fiscal, rapport annuel      |
| comptes    | catégories & emoji, sources, récurrents                             |
| pret       | renvoi vers l'onglet `pr-params`                                    |
| sport      | mes sports, types de séance, routines                               |
| formation  | domaines, dossier des certificats, nettoyage des orphelins          |
| vocabulaire| mes listes, ajout en masse, rappel des quatre boîtes                |
| accueil    | tuiles du tableau de bord (idem bouton ✎ de l'accueil)             |
| sauvegarde | destination USB, sauvegarde auto, rotation, restauration            |
| donnees    | dossier, export/import, mise à jour, réinitialisation, version      |

`openConfig()` reste le point d'entrée historique (ouvre sur `general`). Les onglets
Mes comptes et Sports ont un bouton ⚙ dans leur barre d'actions qui ouvre directement
leur section.

## Serveur local (server.py, port 7438)

* `GET /data` → hydratation initiale de l'UI (+ `_debug.load_error`)
* `GET /cours?tickers=EPA:ESE,WPEA.PA` → cours actuels + variations d1/w1/m1/y1
* `GET /history?tickers=…[&range=max]` → historique journalier
  (ranges : 1mo, 3mo, 6mo, ytd, 1y, 2y, 5y, 10y, max)
* `GET /sparkline`, `/keystats`, `/analysts`, `/search`, `/ping`
* `GET /users` → liste des utilisateurs (+ `hasPin`)
* `GET /pin/required`, `/pin/set`, `/pin/check` — tous avec `?user=<slug>` optionnel
* `GET /scan-orphan-data` → candidats de récupération (installations extérieures)
* `GET /recover-data?from=…` → **le chemin doit figurer dans le scan**, sinon 403 :
  cet endpoint écrase le `pea_data.json` actif, il ne prend pas un chemin libre
* `GET /vendor/<fichier>` → Chart.js, polices et icônes, liste blanche d'extensions
  (`.js`, `.css`, `.woff2`), confiné sous `ui/vendor/`
* Cache serveur : 1 h pour l'historique, 60 s pour les cours
* Tickers : `EPA:XXX` → `XXX.PA` (`AMS:`→`.AS`, `ETR:`→`.DE`, `LON:`→`.L`) ; un ticker
  déjà au format Yahoo (`WPEA.PA`) passe tel quel

### ⚠ Le serveur local n'est PAS un endroit privé

Il écoute sur `127.0.0.1`, mais **tout site ouvert dans n'importe quel navigateur du
PC peut lui parler** pendant que Pilote tourne. Avant la 4.2.0, un simple
`fetch("http://127.0.0.1:7438/data")` depuis une page web suffisait à lire le PEA,
les comptes, le patrimoine et la santé — le serveur répondait avec
`Access-Control-Allow-Origin: *`.

Trois verrous, chacun couvrant ce que les autres ne couvrent pas. **Ne pas en
retirer un en pensant que les deux autres suffisent :**

1. **Jeton de session** (`_SESSION_TOKEN`) — régénéré à chaque lancement, injecté
   dans la page au moment de la servir par `_inject_session_token()`, exigé sur tous
   les endpoints de données. Le bloc injecté enveloppe `window.fetch` une fois pour
   toutes : les appels existants n'ont rien à savoir du jeton. → contre le scan de port.
2. **Refus de tout `Origin` étranger** — notre page n'en envoie pas sur un GET
   same-origin, une page tierce en envoie toujours un. → contre le navigateur complice.
3. **Vérification du `Host`** — un domaine attaquant pointé sur `127.0.0.1` arrive
   avec son propre Host. → contre le DNS rebinding.

Corollaires à ne pas défaire :

* **Aucun en-tête CORS.** Tout est same-origin ; il n'y a rien à autoriser.
* **CSP stricte** (`_CSP`) + `X-Frame-Options: DENY` + `nosniff` + `no-referrer`.
  C'est elle qui interdit les CDN : d'où `ui/vendor/`. Ne pas rajouter de
  `<script src="https://…>` dans index.html, il sera silencieusement bloqué.
* `/vendor/` est joignable **sans** jeton : le navigateur charge `<script src>` et
  `<link href>` lui-même, ces requêtes ne passent pas par le wrapper `fetch`. Ces
  fichiers ne contiennent aucune donnée utilisateur, et les verrous Host et Origin
  s'appliquent toujours.
* `/pin/set` exige l'**ancien** code dès qu'un PIN existe. Poser un premier PIN
  reste libre : il n'y a rien à prouver.
* `/pin/check` est ralenti (0,25 s) et bloqué 60 s après 10 échecs, **côté serveur**.
  Le compteur de l'écran de verrouillage est purement cosmétique et ne protège rien.

## Module Sports (sports.json)

API Python : `load_sports()` / `save_sports()` — `load_sports` renvoie aussi le
catalogue (`SPORTS`) et les champs disponibles (`FIELD_CATALOG`).

Catalogue livré : `course`, `velo`, `natation`, `muscu`, `foot`, `rando`, `autre`.
Chaque sport déclare ses `fields`, ce qui pilote le formulaire côté UI via `spHasField()`.

* course   : distance_km, duration, elevation, subtype
* velo     : distance_km, duration, elevation
* natation : distance_m, duration, lieu (libre / 25 / 50)
* muscu    : duration, groups, routine
* foot     : duration, kind (entrainement / match)
* rando    : distance_km, duration, elevation, subtype
* autre    : duration

**Sports personnalisés** : `SP.customSports` = `[{id, label, icon, color, fields}]`.
L'utilisateur les crée depuis le sélecteur de « Nouvelle séance » (bouton
« + Ajouter un sport ») ou Paramètres → Sports → Mes sports, et coche les informations
à saisir parmi `FIELD_CATALOG` (les mêmes que les sports livrés). Id préfixé `perso_`.
`spRebuildCatalog()` compose `SP_CATALOG` = `SP_BASE_CATALOG` + perso + `autre` en
dernier. `spSportById()` retombe explicitement sur `autre`, jamais sur le dernier
élément du tableau. Un sport utilisé par des séances ne peut pas être supprimé.

Ne pas remettre d'`id` de sport en dur dans le code : c'est `spHasField()` qui décide
(distance en mètres, lieu, routine, groupes, kind…).

Données :
* sessions : `{id, date "YYYY-MM-DD", time, sport, duration (min), distance
  (km, ou mètres si le sport a le champ distance_m), elevation, note, + champs du sport}`
* routines : `{id, name, note}` — de simples libellés de circuits, rattachés aux
  séances de muscu par `routineId`. PAS de liste d'exercices.
* goals    : kind `perf` (validation manuelle) ou `event` (date + compte à rebours)
* subtypes : `{"course": [...], "rando": [...]}` — types de séance modifiables

Ce qui compte le plus pour Arthur : le NOMBRE D'HEURES. C'est le KPI principal
partout (accent, première position). L'agenda affiche une bulle emoji de 30 px par
séance (4 par ligne max) + le total d'heures du jour, détail au clic.

**On ne compare pas avec une période d'avant le suivi (4.2.7).** `spTrackStart()` =
date de la première séance. Avant elle, un mois vide n'est pas « zéro sport » : Pilote
n'était pas encore utilisé. Si le mois (ou l'année) de référence finit avant ce début,
les chiffres clés disent « premier mois suivi » / « première année suivie » (ou « avant
le début du suivi ») au lieu de « −8 h 55 vs août ». Le cumul de l'année dit « depuis
le 11 sept. » et la moyenne hebdo se calcule sur les semaines écoulées **depuis la
première séance** si le suivi a commencé en cours d'année.

## Module Patrimoine (patrimoine.json)

Vue consolidée de ce qu'on possède. **Saisie manuelle une fois par mois** :
l'agrégation bancaire automatique suppose un contrat pro et une validation
réglementaire, hors de portée d'une app locale. Six chiffres par mois suffisent.

API Python : `load_patrimoine()` / `save_patrimoine()` — les deux renvoient
`net`, `serie` et `moisSaisi` déjà calculés, l'UI ne recalcule pas.

* comptes : `{id, label, type, icon, color, auto, archived, note}`
* releves : `{id, compteId, date:"YYYY-MM-01", montant}`

**Trois règles à ne pas casser :**

1. **Tous les relevés sont ancrés au 1er du mois.** C'est ce qui rend la série
   comparable d'un mois à l'autre (`paMoisIso`, `mois_courant`).
2. **Un compte non mis à jour garde sa dernière valeur connue** (`net_worth`
   prend le relevé le plus récent *à cette date ou avant*). Sans ça, oublier
   une ligne ferait s'effondrer le patrimoine ce mois-là.
3. **Le PEA et le prêt ne se saisissent pas** : comptes marqués `auto`,
   pré-remplis par `paValeurAuto()` depuis `window._peaPv.total` et l'onglet Prêt.
   Pas de double saisie. `_peaPv.total` est posé par `renderMetrics()` — ne pas
   recalculer la valorisation du PEA en parallèle.

**Dette du prêt = versements reçus − remboursements** (`PR.versements` et
`PR.remboursements` datés d'aujourd'hui ou avant), et non plus le montant emprunté
moins un échéancier calculé au calendrier. Changé le 28/09/2026 : le prêt d'Arthur
(30 000 €, en deux tranches de 15 000 €) comptait 30 000 € de dette dès sa
configuration, avant tout versement, et le patrimoine baissait d'un argent qui
n'était encore sur aucun compte. Une tranche non reçue n'est ni une dette ni un
avoir. La tuile d'accueil « Prêt étudiant » (capital restant dû) lit la même valeur.
Depuis la 4.3.4, ce calcul n'existe qu'à un endroit, `prCapitalDu()` (onglet Prêt),
que `paValeurAuto` appelle : le « Montant à rembourser » du module donne le même chiffre.

**Pas de doublon avec le prêt.** L'argent du prêt est compté une fois en avoir, là
où il se trouve (ligne PEA = PEA entier, parts du prêt comprises ; Livret A, AV,
compte courant saisis au solde réel de la banque), et une fois en dette. La
« valeur du portefeuille » de l'onglet Prêt n'est ajoutée nulle part. Corollaire :
l'argent du prêt qui attend sur un compte non suivi (compte courant sans ligne)
manque aux avoirs alors que la dette est là.

Seul le type `dette` compte négativement. Un compte `auto` ne peut pas être
supprimé : il serait recréé au chargement suivant.

## Accueil : tableau de bord modulaire

`homeRender()` ne fait plus que la salutation et délègue les tuiles à
`dashRender()`. Chaque tuile est déclarée dans `DASH_WIDGETS`
(`{id, label, module, tab, render()}`).

* `render()` renvoie `null` quand le module n'a rien à dire → la tuile
  **disparaît** au lieu d'afficher un tiret. C'est ce qui garde l'accueil utile
  (ex. le rappel de relevé s'efface une fois le mois saisi).
* Activation et ordre vivent dans `S.uiPrefs.dash`, réglés dans
  Paramètres → **Accueil** (glisser-déposer, `dashRenderConfig`).
* `DASH_DEFAUT` reproduit l'accueil historique (PEA, sport, objectif sportif) :
  une installation existante ne change pas d'aspect après mise à jour.
* Un widget ajouté par une version ultérieure apparaît **éteint** en fin de
  liste, jamais activé d'office.

### Tuile « Performance du PEA » : la période se choisit sur la tuile (4.2.7)

L'ancienne tuile « Rendement du PEA » (id `pea`, inchangé) porte des pastilles
**Jour · 1S · 1M · YTD · Max** (mêmes libellés que la courbe), choix retenu dans
`S.uiPrefs.dashPeaRange`, **Max par défaut** (l'accueil d'avant). `dashPeaPerf()`.
Aucun chiffre recalculé à part :

* **Jour** (`dashPeaDay`) : cours en direct. Titres détenus la veille : quantité ×
  (cours − clôture précédente, déduite de `d1`) ; achetés ou vendus aujourd'hui :
  depuis leur prix d'exécution, frais déduits. Le % se rapporte à la valeur du PEA
  (titres + espèces) à la clôture précédente, versements du jour exclus. Vérifié à
  la main sur les vraies données (−3,68 €, −0,25 %).
* `/cours` renvoie maintenant `t` (= `regularMarketTime`, heure de la séance) :
  le week-end ou avant l'ouverture, `d1` est la variation de la dernière séance, et
  la tuile écrit « séance du ven. 19 sept. » au lieu d'« aujourd'hui ». Une variation
  **sans `t`** vient d'un ancien cache (localStorage) : la tuile attend les cours du jour.
* Le repli de `d1` quand Yahoo ne donne pas `regularMarketChangePercent` prend
  `previousClose`, **plus `chartPreviousClose`** : avec `range=1y` c'est la clôture
  d'il y a un an, et `d1` devenait la variation sur un an.
* **1S, 1M, YTD** : `computePnl(filterByRange(série, r), r)`, exactement le résumé
  de la courbe pour la même plage (vérifié sur les quatre plages). La série est
  partagée via `dashPeaSeries()` (undefined = en cours, null = pas d'historique).
* **Max** : `window._peaPv`, la carte « Plus-value ».
* Les pastilles font `event.stopPropagation()` (un clic ne mène pas à l'onglet) et
  sont inertes en mode édition, comme le bouton de la tuile « Ajouter une dépense ».

### Le crayon : on change les tuiles depuis l'accueil

Bouton **✎ Modifier les tuiles** (`.dash-bar`, au-dessus de la grille) →
`dashToggleEdit()` bascule `_dashEdit` et pose `.dash-editing` sur `#home-cards`.
En mode édition :

* chaque tuile devient cliquable → `dashOpenPick(id)` : la modale `ov-dash-pick`
  liste les widgets et celui qu'on choisit prend **exactement la place** de
  l'ancien (`dashPickApply`) ;
* ✕ retire la tuile, la carte pointillée « + Ajouter une tuile » en ajoute une
  à la fin, le glisser-déposer réordonne (`dashWireHomeDnd` / `dashMove`) ;
* une tuile activée mais sans donnée reste visible en grisé : hors édition elle
  disparaît, mais si elle disparaissait aussi ici on ne pourrait plus la changer.

Paramètres → Accueil reste là et lit la même config : les deux écrans se
resynchronisent (`dashRender()` + `dashRenderConfig()` après chaque écriture).

### Pourquoi les tuiles n'attendent plus

`dashModuleReady(module)` dit si le module a fini de charger. Tant que non, la
tuile affiche un **squelette** au lieu de rien : une tuile absente deux secondes
donnait l'impression que l'accueil ne marchait pas.

Et surtout, `boot()` charge **les six modules en parallèle**
(`Promise.all`), Santé et Patrimoine compris. Avant la 4.2.1 ils n'étaient
bootstrapés qu'à la première visite de leur onglet : leurs quatre tuiles
restaient vides à vie tant qu'on n'y était jamais allé, et cocher la case dans
les paramètres ne faisait visiblement rien. `saBootstrap(discret)` et
`paBootstrap(discret)` chargent alors les **données seules** : le patch de
`goTab` dessine le panneau à la première visite, inutile de le faire au démarrage.

De même, `svRenderUsbState()` publie désormais `window._dashUsb` — la tuile
« Sauvegarde USB » lisait cette variable que personne n'écrivait.

## Module Formation (formation.json)

Ce qui nourrit le CV. Trois natures d'objets sous le même toit, et c'est ce qui
dicte le découpage en quatre onglets :

* les **formations**, qui progressent (`todo` → `encours` → `fini`) et portent
  un certificat une fois terminées — onglets `fo-todo` et `fo-done` ;
* les **expériences, projets et compétences**, qui ne progressent pas : ils
  existent, on les décrit, ils alimentent l'export — onglet `fo-cv` ;
* les **compteurs**, dans `fo-stats`.

API Python : `load_formation()` / `save_formation()` — `load_formation` renvoie
aussi les catalogues (`STATUTS`, `FORMATS`, `PREUVES`, `PRIORITES`, `NIVEAUX`,
`CATEGORIES_COMPETENCE`) et l'état du dossier des certificats. Plus
`formation_add_certificat`, `formation_open_certificat`,
`formation_remove_certificat`, `formation_certificats_state`,
`formation_clean_orphans`, `formation_open_certificats_folder`.

Données :

* formations  : `{id, titre, organisme, url, description, domaineId, format,
                preuve, ects, cpf, dureeEstimee, statut, dateDebut, dateFin,
                dateEcheance, priorite, note, certificat}`
* experiences : `{id, poste, employeur, lieu, debut, fin, missions[], note}`
* projets     : `{id, nom, url, description, techno[], debut, fin, note}`
* competences : `{id, label, categorie, niveau 1-4}`
* domaines    : `{id, label, icon, color}` — éditables, emoji via `finPickIcon`

**Quatre décisions à ne pas défaire :**

1. **Les certificats sont COPIÉS**, jamais référencés là où ils se trouvent
   (`Donnees/users/<slug>/certificats/`). Un chemin vers Téléchargements casse
   au premier rangement, et surtout la sauvegarde USB ne l'embarquerait pas —
   or un certificat est précisément ce qu'on ne peut pas régénérer. Extensions
   en liste blanche, 25 Mo maximum, nom de fichier confiné au dossier
   (`_resolve()`, même protection que le zip-slip de `sauvegarde.py`).
   Ils ne sont **pas** dans les backups quotidiens : `JsonStore` ne sauvegarde
   que le JSON, rien à faire de particulier.
2. **Pas de champ coût.** L'argent vit dans « Mes comptes » ; un même montant
   saisi à deux endroits finit toujours par diverger. Reste `cpf`, qui est une
   info de repérage et pas un montant.
3. **Pas de compteur d'heures.** Une formation a un statut, pas un chronomètre.
   `dureeEstimee` sert aux totaux « charge à venir » et « heures cumulées », et
   personne n'a à la tenir à jour. Un compteur faux vaut moins que pas de compteur.
4. **Supprimer une formation ne supprime pas son certificat**, comme
   `delete_user` qui conserve le dossier. Le ménage est explicite :
   Paramètres → Formation → « Nettoyer les orphelins ».

Détails qui ont une raison :

* `foDomaine()` retombe explicitement sur `dom_autre`, jamais sur le dernier
  élément du tableau. Et `foRenderChartDom()` regroupe par domaine **résolu**,
  pas par id brut : sinon une formation dont le domaine a disparu s'évapore du
  camembert tout en comptant dans le KPI juste au-dessus.
* `foSaveFormation()` efface `dateEcheance` quand le statut passe à `fini`, et
  `dateFin` quand il n'y est plus : sans ça un badge « J−12 » survit sur une
  formation déjà validée.
* `foSafeUrl()` n'ouvre que du `http(s)` — le champ lien est libre.
* Le `poids` des `PREUVES` (diplôme 5 → aucune 1) ordonne l'export CV et le
  graphique : un diplôme se lit avant un badge de MOOC.
* Un domaine utilisé par des formations ne peut pas être supprimé.
* L'export CV est un **bloc de texte à copier**, généré en JS (`foCvText()`).
  Pas de PDF mis en page : il serait retouché ailleurs de toute façon.
* Le fichier est livré avec huit formations d'exemple (`_seed_formations`) —
  un point de départ à corriger, pas une recommandation gravée.

Tuiles d'accueil : `formation-encours`, `formation-annee`, `formation-todo`.
Les échéances restent dans le module (badge dans la liste `fo-todo`) : elles ne
remontent volontairement pas sur l'accueil.

## Module Vocabulaire (vocabulaire.json)

Apprendre des mots par répétition espacée. Quatre boîtes — **1 jour, 1 semaine,
1 mois, 6 mois** — et un principe qui tient en une phrase : un mot su monte
d'une boîte, un mot raté en descend d'une.

API Python : `load_vocabulaire()` / `save_vocabulaire()` — `load_vocabulaire`
renvoie aussi les catalogues (`BOITES`, `MODES`).

Données :

* listes     : `{id, label, icon, color, mode: "trad"|"def"}`
* mots       : `{id, listeId, mot, reponse, exemple, note, boite 1-4,
                prochaine "YYYY-MM-DD", creeLe, derniereRevue, nbVus, nbReussis}`
* historique : `[{date, listeId, vus, ok}]` — un agrégat par jour et par liste,
                purgé au-delà de deux ans. Il ne sert qu'aux courbes.

**Cinq décisions à ne pas défaire :**

1. **Raté = on DESCEND d'une boîte** (et on reste en boîte 1 si on y est déjà),
   su = on monte d'une. Dans les deux cas la prochaine révision tombe à
   l'intervalle de la boîte **d'arrivée** — c'est `voAppliquer()` et rien
   d'autre qui décide. Conséquence voulue : un mot raté en « 6 mois » repasse
   en « 1 mois » et revient donc dans un mois, pas dans six.
2. **Rien n'est corrigé automatiquement.** La saisie sert à s'engager sur une
   réponse avant de la découvrir ; seul le clic sur « Je savais » / « Raté »
   compte. Comparer deux chaînes produirait des faux négatifs sur un accent,
   un synonyme ou un pluriel — et une révision fausse pourrit la boîte d'un
   mot pour des mois. Ne pas « améliorer » ça en comparant les textes.
3. **Les listes ne se mélangent jamais.** La file d'une session est bornée à
   une liste, et chaque liste a ses propres boîtes. C'est la raison d'être de
   `listeId` sur chaque mot, et de listes créables plutôt que deux langues
   codées en dur. Anglais (traduction) et Français (définition) sont livrées
   pour démarrer ; le `mode` ne change que le libellé de la seconde face.
4. **Le sens de la question se choisit au lancement de la session**, pour
   toute la session. Il vit dans `VO_SESS`, jamais dans le fichier : c'est un
   choix du moment, pas une propriété du mot.
5. **Aucun mot n'est livré.** L'intérêt du module est ce qu'Arthur y met.
   `default_data()` ne pose que les deux listes.

Détails qui ont une raison :

* `voBoite()` et `voListe()` retombent explicitement sur la **première** entrée,
  jamais sur la dernière : une boîte inconnue ne doit pas propulser un mot à
  six mois.
* **Chaque validation est écrite sur le disque**, une à la fois (`voSaveQueued`,
  chaînée) : fermer l'app en plein milieu d'une session ne rejoue pas les mots
  déjà tranchés, et deux clics rapides ne s'écrasent pas.
* L'exemple et la note n'apparaissent **qu'après** la révélation : l'exemple
  contient presque toujours le mot, le montrer avant donnerait la solution.
* Les deux boutons de validation affichent **où part le mot** (« passe en
  1 sem », « retombe en 1 j ») : on voit la conséquence avant de trancher.
* Une liste qui contient des mots ne peut pas être supprimée, et il en reste
  toujours au moins une.
* L'ajout en masse coupe au **premier** séparateur (tabulation ou `=`) : une
  définition peut donc en contenir d'autres ensuite. Un mot déjà présent dans
  la même liste n'est pas réimporté — sa boîte et son historique sauteraient.
* Les intervalles des boîtes ne se règlent pas : les changer en cours de route
  décalerait toutes les révisions déjà programmées.

Tuiles d'accueil : `voc-jour` (« Liste du jour à faire », qui **disparaît** dès
qu'il n'y a plus rien de dû — c'est tout son intérêt) et `voc-acquis`.

### Lire une capture, une photo de liste ou un PDF (ajout en masse)

Bouton « Lire une image ou un PDF » dans `ov-vo-bulk`, ou Ctrl+V d'une capture
(Win+Maj+S) pendant que la fenêtre est ouverte. Le même bouton est dans l'en-tête des onglets
Réviser et Mots (`voLireImage()` : ouvre la fenêtre et le sélecteur d'images) :
en 4.3.5 il n'était que dans Mots → Ajout en masse, et Arthur ne l'a pas trouvé. Même moteur que Santé (`ocr_win.ps1`, hors
ligne) ; `vocabulaire.lire_images()` / `lire_image_collee()`, API
`vocabulaire_pick_images` (son propre filtre « Images et PDF »),
`vocabulaire_read_images`, `vocabulaire_read_pasted`.
JS : `voBulkPickImages`, `voBulkLire`, le gestionnaire `paste`, `voBulkPreview`
(compte sous la zone les mots prêts et les lignes sans « = », qui seront ignorées).

* **Ça ne fait que remplir la fenêtre**, à la suite de son contenu. Rien n'est
  enregistré avant « Ajouter » : même règle que l'import Santé. Ne pas transformer
  ça en ajout direct.
* **Relecture en tableau (30/09/2026, demandée par Arthur : « là c'est pas bon du
  tout »).** Après une lecture, la zone de texte laisse place à un tableau
  Mot | Réponse (`#vo-bulk-rev`, `_voBulkRows` = null en mode texte) : une case à
  cocher par ligne, chaque case modifiable, « Ajouter » ne prend que les lignes
  cochées et complètes. Les lignes sans « = » (titres, consignes, phrases) sont
  **mises de côté** (`_voBulkMis`), repliées sous le tableau, et « + Mot » en
  refait un mot à compléter, qui se coche tout seul une fois complet. En vrac dans
  la zone, elles faisaient croire que la lecture avait raté. Une paire douteuse
  arrive **décochée** avec sa raison (`voBulkDoute` : un seul petit mot comme
  « avec », en-tête en majuscules, liste « a — b — c », caractères suspects).
  « Modifier en texte » / « Relire en tableau » basculent (`voBulkBasculer`),
  « Inverser » marche dans les deux modes. Du texte tapé ou collé reste en mode
  texte, comme avant. La liste prend `calc(100vh - 520px)` : « Ajouter » reste
  visible sur l'écran d'Arthur (768 px).
* **Titres bilingues et listes** (`_titres_et_listes`) : « To express cause /
  pour exprimer la cause » devient une paire ; une liste de connecteurs juste
  dessous (« First, firstly, … ») prend la traduction du titre. Tout autre ligne
  arrête la liste : les phrases d'exemple sous un tableau restent de côté.
* **Cellules sur deux lignes.** Sans traits de tableau : une ligne orpheline se
  recolle à la case du dessus si celle-ci « appelle une suite » (`_SUITE` : virgule,
  « … », article, « pour » ; pas les prépositions, « Because of » est entier). À
  gauche, une 2e ligne en majuscule (« I agree with / I approve of ») devient une
  expression de plus qui **partage** la traduction (même liste Python). Avec traits :
  `_chercheur_traits` repère les bordures horizontales (image cisaillée de la pente
  du texte, bandes seuillées et réduites par Pillow, morceaux de ~150 px à ±2 px :
  100 % sur un trait, 66 % au plus sur du texte), et `_fusion_cases` fusionne deux
  entrées tombées entre les deux mêmes traits (« I disagree with / I disapprove of »
  = « Je ne suis pas d'accord / avec »), **seulement si les traits sont réguliers**
  (un trait manqué ferait une case deux fois plus haute, et deux lignes seraient
  fusionnées à tort).
* **Mesuré** sur les deux photos de connecteurs contre la liste idéale (106 paires) :
  78 justes, 7 fausses avant ; 104 justes, 0 fausse après, en version réduite comme
  d'origine. Les deux manquantes sont illisibles pour le moteur (« = » et « if »).
  Lecture des deux photos dans l'app : 12 s (130 s avant d'accélérer les traits et
  l'écriture du PNG, voir `_preprocess`).
* **.zip (4.3.9)** : `lire_images` remplace un zip par les images et les PDF qu'il
  contient, avec l'extraction de Santé (`sante._images_du_zip(..., exts)` :
  fichiers cachés de macOS/iPhone ignorés, rien ne sort du dossier temporaire).
  Vérifié : le `Gmail.zip` d'Arthur (ses deux photos) donne 84 paires, comme les
  photos seules ; la fiche PDF dans un zip, exactement le même résultat que seule.
* **PDF (30/09/2026)** : `_lire_pdf` fait rendre chaque page en PNG par le moteur
  PDF de Windows (`Windows.Data.Pdf`, hors ligne, rien à installer), via le mode
  `-PdfDir` d'`ocr_win.ps1`, puis lit chaque page comme une photo. Même chemin
  pour un PDF numérique ou scanné. Rendu à 2× la taille nominale (~190 dpi, texte
  d'une vingtaine de pixels), 20 pages au plus (`PDF_PAGES_MAX`, signalé sous la
  zone). Le mode PDF est **dans** `ocr_win.ps1` et pas dans un second script
  exprès : un nouveau fichier devrait entrer dans les `datas` de la spec (le piège
  n° 4). Mesuré sur une fiche de 3 pages : 30 mots sur 30, accents compris, en 9 s.
* **La page est d'abord coupée en blocs** (`_blocs`, 30/09/2026) : titre, tableau,
  paragraphe, chacun lu avec sa propre mise en page. Constaté sur deux photos de
  fiches de connecteurs (tableaux à quatre colonnes sous des titres qui traversent
  leurs colonnes) : lues d'un seul tenant, aucune colonne n'apparaissait, **2 paires
  sur 330 mots lus** ; par blocs, 44 et 41. Même panne sur un PDF à deux colonnes
  sous un titre centré. Coupure sur un blanc de plus de 1,6 interligne (interligne
  mesuré dans les colonnes), hauteurs redressées de la pente des lignes : sur une
  photo tournée d'un degré, la même ligne descend de 14 px d'une colonne à l'autre.
* Dans un bloc : **les colonnes se prennent deux par deux** (mot | traduction |
  mot | traduction), `_gouttieres` trouve tous les blancs verticaux ; une colonne
  restée seule (phrases d'exemple) sort telle quelle, un séparateur imprimé en tête
  de réponse (« = POUR ») est retiré (`_SEP_TETE`). Et **« mot : définition »** sur
  une ligne (`:`, `=`, tiret entouré d'espaces, flèche). Le reste arrive tel quel,
  sans « = » : l'aperçu le signale.
* Une ligne seule dans son bloc (titre, en-tête, pied de page) n'est jamais coupée
  en « mot = réponse » : « Artificial Intelligence — Vocabulary » n'est pas un mot.
  Sauf si c'est toute l'image (capture d'un seul mot).
* **Bouton « Inverser »** (`voBulkInverser`, 4.3.7) : échange mot et réponse sur
  chaque ligne de la zone. Demandé par Arthur pour une fiche PDF qui met le français
  en premier, à l'inverse de ses photos. Coupe au même endroit que `voBulkParse` ;
  si le nouveau mot contient un « = », la ligne prend une tabulation (prioritaire
  à la lecture). Deux clics redonnent exactement le contenu d'origine.
* `_separer` ne rattache une ligne à la définition précédente que si celle-ci était
  **pleine** (son premier mot n'aurait pas tenu avant la marge droite) : sans ça,
  toutes les phrases d'un exercice qui suivent « Words: … » finissaient collées
  en une ligne géante, comptée comme un mot.
* **Le moteur rend chaque colonne en lignes séparées** : l'appariement se fait par
  position (`_gouttieres` trouve les blancs entre colonnes, `_apparier` réassocie).
  Sur une photo penchée que le moteur n'a pas redressée, toute la colonne de droite
  est décalée d'une même hauteur : `_apparier` cherche ce décalage avant d'apparier.
  C'est pour ça que `ocr_win.ps1` renvoie `l` (numéro de ligne du moteur) et `angle`
  depuis ce changement ; Santé ignore ces deux champs.
* Une traduction trop longue pour une ligne est rattachée à son mot si elle est plus
  proche de lui que l'écart habituel entre deux entrées ; sinon elle sort seule :
  mieux vaut une ligne à trier qu'un mot collé à la mauvaise traduction.
* **Image en gris seulement, à la résolution d'origine** (mesuré le 29/09/2026 sur
  des images de test) : contrastée, une photo penchée n'est plus redressée et « I'd »
  devient « Ild ». Relecture agrandie seulement si les mots font moins de 12 px de
  haut (`PETIT_TEXTE`) : là, l'agrandissement corrige tout ; au-dessus, il dégrade.
  L'agrandissement vise un texte d'une vingtaine de pixels (`_passe`, ×2 à ×4).
* **Une capture d'écran de photo se lit mal, quoi qu'on fasse** (mesuré le
  30/09/2026 en comptant les paires EXACTEMENT justes, la photo pleine résolution
  servant de référence) : en dessous de 900 px de haut pour une page A4, moins de
  la moitié des paires sont justes ; à 550 px, la première passe ne trouve rien et
  les agrandissements ×2 à ×4 ne rendent que du charabia (0 paire juste sur 18).
  D'où : rien de lu → message « choisis plutôt la photo elle-même » ; texte de
  8 px ou moins → lu, avec la note « lecture incertaine » sous la zone. Ne pas
  remettre de passe ×4 « au cas où » : le nombre de paires monte, pas leur justesse.
* **Photo couchée** (orientation perdue en route, téléphone tenu de côté) : le
  moteur n'y lit que des lettres isolées (2 mots lisibles sur 36, contre 72 à 100 %
  sur une page droite). `_lire_image` réessaie à 270°, 90° puis 180° et garde le
  sens le plus lisible (`_lisibles`) : 5 → 43 paires. À l'envers, le moteur se
  débrouille déjà seul. Coût : une seconde lecture, seulement quand la première
  est illisible.
* Vérifié le 30/09/2026 dans le Pilote **installé** (4.3.7, piloté par
  l'accessibilité de Windows) : les deux photos d'origine choisies par le
  sélecteur donnent 84 paires, comme en dev. Une plainte « trop peu de mots » vient
  donc de la façon dont l'image arrive (capture collée, photo couchée), pas de l'exe.
* Seul le français est installé comme langue d'OCR chez Arthur ; il lit bien
  l'anglais, sauf le pronom « I » lu « l » : `_L_POUR_I` le corrige (un « l » seul
  ou « l'd », « l'm »… n'existent pas en français). Même chose pour « In » lu « ln »
  (`_LN_POUR_IN`, vu quatre fois sur deux fiches).
* Une cellule sur deux lignes dans un tableau serré (« As a matter of fact, in fact, /
  at all events, in any case ») : la seconde ligne sort seule, car elle tombe à
  l'écart habituel entre deux entrées. Voulu, même règle que la traduction trop
  longue plus haut.
* Un mot isolé très court (« si ») est parfois ignoré par le moteur : la ligne du mot
  reste alors seule, sans « = », donc visible.
* Du texte collé garde son comportement normal : il l'emporte sur une image.

## Module Santé (sante.json)

Pesées de la balance connectée, saisies depuis les captures d'écran de l'app
**FitDays** — il n'existe pas d'API, la capture est le seul pont praticable.

API Python : `load_sante()` / `save_sante()` (+ le catalogue `METRICS`),
`read_screenshots(paths)`, `ocr_available()`.

### Les 14 mesures

`poids` · `imc` · `graisse` · `taux_musculaire` · `poids_sans_graisse` ·
`graisse_sous_cutanee` · `graisse_viscerale` · `eau` · `muscle_squelettique` ·
`masse_musculaire` · `masse_osseuse` · `proteine` · `metabolisme` · `age_corporel`

Chacune porte son `unit`, ses `decimals`, ses `aliases` OCR et son `range`
(bornes physiologiques).

### OCR — ce qui a été mesuré, ne pas le redécouvrir

Moteur : **Windows.Media.Ocr** via `ocr_win.ps1` (PowerShell + WinRT). Aucune
dépendance nouvelle, hors ligne, les captures ne quittent jamais le PC.
Pillow prépare les images ; `ocr_win.ps1` est dans les `datas` de la spec.

Résultat sur les captures réelles : **14/14 en ~10 s** (3 captures).

Quatre pièges, tous traités — ne pas « simplifier » :

1. **La résolution d'origine bat les agrandissements.** Contre-intuitif, mais
   mesuré : 10 valeurs lues à l'échelle 1 contre 8-9 à l'échelle 3, et deux
   fois plus vite. Les petits nombres isolés (graisse viscérale) disparaissent
   dès qu'on agrandit. L'ordre de `VARIANTS` encode ce résultat.
   **Et le canal le plus sombre bat le gris (4.3.9).** FitDays colore chaque
   valeur selon son niveau (vert pâle, orange, bleu) ; converti en gris, un
   « 7.0 » vert pâle devient presque blanc et aucune passe ne le voit. Les deux
   premières passes (mode `min` de `_preprocess`) gardent pour chaque pixel le
   plus sombre des trois canaux : sur fond blanc, le texte coloré devient aussi
   foncé que du noir. Mesuré le 30/09/2026 sur trois vraies captures : 12 valeurs
   sur 14 en gris (graisse viscérale et âge corporel manquants), **14 sur 14**
   avec `min`, aucune valeur fausse de plus, et plus vite (10 s au lieu de 15 s
   pour les trois). Les quatre anciennes passes restent derrière, en rattrapage.
   Le Vocabulaire garde son mode `raw` : sur une photo de papier jauni, le canal
   le plus sombre assombrirait le fond.
   **L'arrêt anticipé attend les libellés vus** : une passe qui n'apporte rien
   n'arrête plus la lecture si un libellé de la capture attend encore sa valeur
   (`vus`, rempli par `_extract_values`). L'âge corporel orange n'apparaissait
   qu'à la 3e passe, et la lecture s'arrêtait à la 2e.
2. **Appariement par COLONNES, jamais par lignes.** FitDays coupe ses libellés
   longs sur deux lignes et place la valeur sur la ligne du milieu :
   `Graisse` / `21.3 %` / `corporelle`. Un appariement ligne à ligne rate la
   moitié des mesures (voir `_extract_values` et `_label_blocks`).
3. **Comparaison des libellés par ENSEMBLE de mots** (`_match_metric`) : le
   moteur renvoie « Corporelle Eau » et « Graisse sous- cutanee eee ».
   L'alias le plus spécifique gagne, sinon « Poids sans graisse » devient
   « Poids ».
4. **L'écran principal est piégé.** Son bloc « Contraste » affiche les ÉCARTS
   depuis la pesée précédente (+1.2 kg, +0.4 %) avec le libellé SOUS le
   chiffre : sans `_contraste_cutoff()`, un écart de 0.4 % est enregistré comme
   une valeur. Le gros cadran, lui, n'a pas de libellé : `_dial_weight()` le
   reconnaît à sa taille (repli quand seul cet écran est fourni).

`_preprocess` écrit ses PNG avec `compress_level=1` (30/09/2026) : au réglage par
défaut, une photo de 12 Mpx prenait 6,5 s à écrire, pour un fichier qui ne vit que
le temps d'une lecture. Mêmes pixels, même lecture.

Autres garde-fous : `%` rendu « 0/0 » (`_PCT_GARBLE`), point décimal perdu
(« 152 » → 15.2 via `_validate`, qui REFUSE plutôt que d'inscrire une valeur
hors bornes), dates rejetées comme valeurs (`_NOT_A_VALUE`).

### Captures envoyées en .zip (4.3.8)

Arthur s'envoie ses captures par mail ; Gmail rend les pièces jointes en un seul
`.zip` (« tout télécharger »). Le sélecteur de Santé accepte donc les `.zip`
(`sante_pick_screenshots`), et `read_screenshots` remplace chaque zip par les images
qu'il contient (`_images_du_zip`, PNG / JPG / HEIC, 20 au plus, 25 Mo chacune),
extraites dans un dossier temporaire supprimé à la fin. Ce sont les mêmes règles que
pour plusieurs captures choisies à la main : **toutes sont une seule pesée**.

* Les fichiers cachés que macOS et l'iPhone glissent dans une archive (`__MACOSX/`,
  `._IMG_1234.PNG`) ont une extension d'image sans en être une : ignorés.
* Le chemin d'extraction est choisi par Pilote, jamais repris de l'archive : un
  membre `../../x.png` ne sort pas du dossier temporaire (testé).
* Vérifié le 30/09/2026 sur le vrai zip FitDays d'Arthur (3 captures) : exactement
  le même résultat qu'en choisissant les trois images une à une.
* `_images_du_zip` sert aussi au Vocabulaire (4.3.9), qui y ajoute `.pdf` par
  son paramètre `exts`.

### L'import ne valide jamais tout seul

L'OCR pré-remplit un formulaire, **surligne en rouge** ce qu'il n'a pas su lire
et attend une validation. Une donnée de santé fausse est pire qu'une donnée
absente : ne pas transformer ça en enregistrement direct.

Données :
* mesures : `{id, date, time, source:"ocr"|"manuel", note, + les 14 métriques}`
* goals   : `{id, metric, target, start, date, status, createdAt, note}`
  → avancement = distance parcourue / distance totale ; perte et gain se
    calculent pareil (`saGoalProgress`, côté JS uniquement — il n'y a
    volontairement pas de second calcul en Python)

UI : `sa*` dans index.html. Les métriques où **baisser est bon** (poids, IMC,
graisses, âge corporel) sont listées dans `saDeltaClass` — c'est ce qui décide
de la couleur verte ou rouge.

**Comparer avec une pesée choisie (4.2.6).** L'onglet Suivi a un sélecteur
« Comparer avec » : la pesée précédente (défaut) ou n'importe quelle pesée plus
ancienne. Le choix vit dans `SA.uiCompare` (id de la pesée, mémorisé dans
`sante.json` comme `SA.uiRange`) ; `saRef()` renvoie la pesée de référence et
retombe sur `saPrev()` si le choix ne vaut plus rien (pesée supprimée ou devenue la
dernière). Les chiffres clés et la grille « Dernière pesée » l'utilisent et disent
contre quoi ils comparent (`saRefLabel` : « vs 15 sept. »). La tuile « Poids » de
l'accueil **partage ce choix** et porte son propre sélecteur « Comparer avec »
(4.2.9) : changer d'un côté change l'autre, un seul réglage enregistré. Les options
viennent de `saCompareOptions(court)` pour les deux sélecteurs (libellés courts
sur la tuile). Le sélecteur est inerte en mode édition et absent s'il n'y a
qu'une pesée.

**Choix glissants (4.2.9).** En plus d'une date précise, `SA.uiCompare` accepte
`"w1"` (il y a une semaine), `"m1"` (il y a un mois) et `"first"` (la première
pesée). `saRefChoisie(choix)` résout le choix : pour `w1`/`m1`
(`SA_CMP_GLISSANT`, 7 et 30 jours), la pesée **la plus proche** de N jours avant
la **dernière pesée** (pas avant aujourd'hui : une pesée vieille de trois semaines
ferait tout retomber sur la précédente), la plus ancienne à égalité. Un historique
plus court que la période retombe donc sur la première pesée, et c'est la date
affichée (« vs 15 sept. ») qui le dit. Dans l'onglet Suivi, chaque choix glissant
affiche entre parenthèses la pesée qu'il désigne aujourd'hui.

**Tuile « Poids » (4.2.9).** Sous l'écart de poids, la graisse et la masse
musculaire depuis la même pesée (`dashSanteCompo`, vert ou rouge selon
`saDeltaClass`, une mesure absente est omise) : le poids seul ne dit pas si
c'est du gras ou du muscle qui a bougé. Cette ligne passe par le champ `subHtml`
de `dashCardHtml` (HTML déjà échappé par le widget, sous `sub`). La mini-courbe
(`dashSanteSpark`) couvre au moins les 12 dernières pesées et remonte toujours
jusqu'à la pesée de référence ; le trait prend l'accent à partir d'elle et reste
estompé avant (`dashSpark(vals, depuis)`, classe `.dash-spark-ctx`).

**Nombres à la française (4.2.9).** `saFmt` et `saDelta` passent par
`saNombre()` (`toLocaleString("fr-FR")`) : « 77,5 kg », « −0,4 kg », avec une
espace insécable avant l'unité. Tout le module était en « 77.5 kg ». Ces fonctions
ne servent qu'à l'affichage : les champs de saisie gardent leurs valeurs brutes.

## Module Mes comptes (finances.json)

Catégories et sous-catégories **portent chacune un emoji** (`icon`), affiché partout :
liste des transactions, sélecteurs, camembert, top de l'année, récurrents.

* `finCatIcon(c)` / `finSubIcon(s)` avec repli (🏷️ dépense, 💰 revenu, • sous-catégorie)
* `finPickIcon(current, titre, callback)` ouvre la modale `ov-fin-icon` (palette + saisie libre)
* `finances.backfill_icons()` côté Python donne un emoji aux fichiers créés avant la 4.1.2,
  en reconnaissant les libellés du jeu par défaut
* **Emoji deviné d'après le libellé (4.2.7)** : `FIN_ICON_GUESS` (mots sans accents ni
  majuscules, première règle qui correspond) via `finGuessIcon(nom)`. Appliqué à la
  création d'une catégorie ou sous-catégorie sans emoji, et au chargement par
  `finBackfillIcons()` sur tout ce qui n'a pas d'emoji ou a gardé le générique 🏷️ / •
  (enregistré ensuite). Une sous-catégorie au libellé inconnu prend l'emoji de sa
  catégorie. 💰 n'est pas considéré comme générique : il peut avoir été choisi.
* **« Autres dépenses » / « Autres revenus » toujours en dernier** : `finCatsOrdered(type)`
  (sélecteurs de la saisie et des récurrents, filtre, liste des catégories, légende du
  camembert). Tri à l'affichage : le fichier garde son ordre, et une catégorie créée
  plus tard se range aussi avant « Autres ». Le top de l'année reste trié par montant.
* **Aide à la saisie (4.2.7)**, dans la fenêtre « Nouvelle dépense / Nouveau revenu » ;
  les deux lisent l'historique du même type (`finTxModels`, un modèle par libellé sans
  accents ni casse, sa saisie la plus récente) et ne font que **pré-remplir** montant,
  catégorie, sous-catégorie et source : la date reste celle du jour, rien n'est
  enregistré sans « Enregistrer », la saisie libre reste entière.
  - « Dépenses fréquentes » (`finRenderFreq`) : les 8 libellés les plus saisis sur
    douze mois, les plus récents d'abord à égalité. Automatique, rien à configurer
    (choix d'Arthur). Masquée en modification.
  - Suggestions sous le libellé (`finAcUpdate`) : ceux qui commencent par la saisie,
    puis ceux dont un mot commence par elle. ↑ ↓ Entrée, Échap ferme la liste sans
    fermer la fenêtre.
  - Après un choix, le montant est sélectionné : il se remplace d'une frappe (courses).

## Module Prêt étudiant (pret.json)

API Python : `load_pret()` / `save_pret()`. Capitalisation annuelle de l'AV et moteur
événementiel du Livret A repris à l'identique de l'ancienne app standalone (abandonnée).

* pret        : `{montant, date_deblocage, date_premier_remboursement,
                duree_remboursement, mensualite}`
* pea.achats  : `{id, date, ticker, montant, quantite, cours_achat}`
* pea.ventes  : `{id, date, ticker, quantite, cours_vente, montant (crédité)}`
  → PRU pondéré sur les achats, plus-value réalisée = crédité − qté × PRU,
    plus-value latente sur les parts restantes
  → **ces deux listes ne se remplissent plus** : voir ci-dessous. Elles restent lues
    pour un ordre qui y aurait été saisi avant.
* av.contrats : `[{id, label, taux_annuels:[{annee,taux}], depots:[{id,date,montant,note}]}]`
  → MULTI-CONTRATS, chacun avec ses propres taux
* liv         : `{label, taux_history:[{id,date,taux}], mouvements:[{id,date,type,montant,note}]}`
* frais_recurrents : prélevés le MÊME JOUR chaque mois (jour pris sur `date_debut`,
  ramené au dernier jour du mois quand il n'existe pas — voir `prAddMonths`)
* frais_rembourses : `{id, date, montant, label}`, frais que la banque a rendus
  (ex. un mois de carte offert), déduits des frais (4.3.4)

**Les frais se comptent au fil des mois (4.3.4).** Jusque-là, les 120 prélèvements de
la carte (6,05 €) comptaient dès le premier jour : 726 € de frais, et autant en moins
dans les liquidités et les gains. Désormais `prAllFrais(jusqua)` ne prend que ce qui
est daté d'aujourd'hui ou avant ; le reste s'affiche « à venir » dans Paramètres.
* **Changement de tarif** : `paliers: [{id, date, montant}]` sur le frais récurrent,
  nouveau montant à partir de cette date (`prTarif`). Ne jamais modifier `montant`
  pour un changement de tarif : ce serait réécrire les prélèvements passés.
* `nb_occurrences` 0 ou vide = frais sans fin (`prExpandRecurrent` s'arrête alors à
  la date demandée ; sans date, il ne renvoie rien, jamais une boucle infinie).
* Frais remboursés : même règle, ceux datés d'aujourd'hui ou avant. Le bouton
  « flèche retour » d'un frais récurrent pré-remplit un remboursement (montant du jour).

**Tout au réel, à sa date (4.3.4, audit du module).** Versements, remboursements, dépôts
d'assurance vie, mouvements du Livret A et ordres du PEA ne comptent qu'à partir de
leur date (`prPasse` / `prAVenir`) ; ce qui est daté plus tard s'affiche « à venir ».
Le versement de 15 000 € annoncé pour le 05/10 comptait déjà comme reçu le 28/09.
* `capital_du = prCapitalDu()` (versé − remboursé). `mensualites_restantes` reste
  calculé sur le **montant emprunté** : sur le capital dû, il tomberait à 30 au lieu
  de 60 avant la 2e tranche.
* `prTranchesTxt(o, court)` : « 15 000 € versés sur 30 000 € empruntés, 15 000 €
  attendus le … ». Le champ « Date du 1er déblocage » n'est qu'indicatif : ce sont
  les versements qui comptent (un par tranche).
* **Cours** : `prCours(t)` prend le cours du PEA (`getVar`, rafraîchi toutes les
  3 min), `_prQuotes` ne sert plus qu'aux titres que le PEA ne suit pas. Avant, le
  prêt chargeait ses cours une fois par session : sa valeur vieillissait.
* **Livret A par quinzaines** (`prLivretState`) : un dépôt rapporte à partir de la
  quinzaine qui suit, un retrait cesse dès le début de la sienne, taux / 24 par
  quinzaine terminée, intérêts au capital le 1er janvier. Vérifié : 1 000 € le
  10/01 à 3 % → 23 quinzaines, 28,75 €. Remplace le calcul au jour près.
* **Retour** : `prPushUndo()` met un instantané `{PR}` dans la même pile que le PEA
  (`undoLast` le reconnaît) ; posé par `prSubmit` (retiré si la saisie est refusée)
  et par chaque suppression.
* **Alertes** (`prAlertesHtml`) : versements saisis > montant emprunté ; placé +
  remboursé > versé à ce jour. Les frais bancaires n'y entrent pas : la carte peut
  être prélevée avant l'arrivée du prêt.
* Graphique de répartition aux couleurs du thème (`carnetChartColors`, `CLRS`).

Les cours passent par le serveur local (`/cours`), pas de second proxy Yahoo.

### PEA du prêt = ordres du PEA cochés « argent du prêt »

On n'a qu'un PEA : les achats faits avec le prêt en font partie. Avant, il fallait les
saisir deux fois (onglet PEA et onglet Prêt). Désormais un ordre n'existe **qu'une
fois**, dans `S.transactions`, avec `pret: true` quand la case « Payé avec l'argent du
prêt étudiant » est cochée (fenêtres `ov-pos` et `ov-tx`, champs `f-pret` / `t-pret`,
absente pour un dividende). `prPeaOrdres()` lit ces transactions et les convertit
(`prYahoo` : `EPA:WPEA` → `WPEA.PA` ; montant = qté × cours ± frais, comme
`computeCash`). **Aucune copie dans `pret.json`** : pas de doublon possible, et une
modification, un décochage, une suppression ou le bouton Retour se voient partout.

* Les ordres non cochés n'entrent jamais dans les calculs du prêt.
* « + Achat » / « Vente » de l'onglet Prêt ouvrent les fenêtres du PEA, case cochée
  (`prAchatViaPea`, `prVenteViaPea`) ; le crayon d'un ordre ouvre `editTx`. Pas de
  corbeille côté Prêt : supprimer un ordre du PEA depuis là surprendrait.
* Vente cochée : refusée au-delà des parts achetées avec le prêt (`prVentePretOk`).
* `persist()` appelle `prRefreshIfVisible()` : l'onglet Prêt ouvert suit le PEA.
* Étiquette « Prêt » sur la ligne dans PEA › Transactions.
* Patrimoine : rien ne change et rien ne doit changer. La ligne PEA vaut le PEA
  **entier** (`_peaPv.total`), parts du prêt comprises ; la « valeur du portefeuille »
  du prêt n'est ajoutée nulle part. Ne jamais créer de compte « placements du prêt » :
  PEA, AV et Livret A sont déjà comptés par leurs propres lignes.

## Wishlist : frais des ETF

Colonne « Frais/an » (TER, frais de gestion annuels) dans le tableau des ETF,
triable ; le premier clic trie du moins cher au plus cher, les frais inconnus
restent en bas.

* **La saisie l'emporte, Yahoo sert de repli.** `w.ter` (en %, 0.25 = 0,25 %) est
  saisi dans la fenêtre de l'ETF ; vide, la colonne affiche
  `_wsKey[ticker].expenseRatio` (fraction, lue par `/keystats` dans
  `fundProfile.feesExpensesInvestment.annualReportExpenseRatio`), en gris avec la
  mention « Yahoo ». Constaté le 27/09/2026 : Yahoo ne connaît que 3 des 7 ETF de
  la wishlist d'Arthur (rien pour ESE, PANX, PEMS, GPEA). D'où la saisie.
* `_wishTer(w)` décide de la valeur, pour l'affichage comme pour le tri.
* Saisie refusée hors de 0 à 5 % : protège de « 25 » tapé pour 0,25 %.
* `fetchKeystats()` interroge désormais aussi les ETF de la wishlist.
* **Noms des ETF** : choisir un ETF dans la recherche recopie le nom de l'index
  `PEA_ETF_BOOST` (server.py) dans la wishlist. Il donnait de faux émetteurs
  (PEMS noté BNP, etc.) : chaque ligne a été revérifiée sur justETF le
  28/09/2026 (4.3.2). Toute nouvelle ligne se vérifie de la même façon :
  fiche justETF, cotation Euronext Paris sous ce ticker, éligibilité PEA.

## Prochain achat (onglet Stratégie, `#card-pac`)

Chaque mois, les ordres à passer pour atteindre puis garder l'allocation cible
(défaut 70 % WPEA / 20 % PEMS / 10 % PNAS), **sans jamais vendre**, au moindre
courtage (Fortuneo : 1er ordre du mois ≤ 500 € gratuit, sinon 0,35 % sans
minimum, plafonné à 0,5 %, le maximum légal en ligne pour un PEA). Algorithme
en 8 étapes écrit par Arthur, appliqué à la lettre dans `pacCalcul()` (pur : ni
écran ni `S`). **`testsProchainAchat()`** (console) vérifie ses six cas chiffrés :
ne jamais modifier le calcul sans les relancer.

* **Arrondis, piège mesuré** : `pacR2()` arrondit le demi-centime vers le haut
  (13 × 7,675 = 99,775 → 99,78 €) ; `toFixed`/`toLocaleString` partent du binaire
  (99,77499…) et donnent 99,77. Le **reliquat** s'arrondit, le **total** affiché
  = budget − reliquat : les deux font toujours le budget (règle des six cas, T3).
  Les comparaisons au budget se font sur les montants non arrondis.
* **Quantités** : `computePos(p).qty` (rien n'est stocké). Une ligne cible non
  détenue vaut 0 ; les positions hors allocation sont listées à part.
* **Budget** = `computeCash()` (versement à saisir dans Dépôts avant). Une saisie
  à la main (`_pacBudget`) n'est pas enregistrée.
* **Ordre gratuit** : détecté (`pacGratuitDetecte`) = achat ou vente du mois,
  ≤ seuil, sans frais. Vérifié sur les données d'Arthur le 27/09/2026 : ses ordres
  sans frais font tous < 500 €. La case l'emporte pour le mois **tant que la
  détection ne change pas** (`gratuitForce.vu`) : un ordre gratuit saisi après
  coup compte même si la case avait été décochée.
* **Heure du cours** : Yahoo diffuse Euronext avec 15 min de retard ; pendant
  la séance on affiche donc l'heure du cours, « clôture du JJ/MM » seulement
  hors séance ou si le cours date d'un autre jour (`pacCoursInfo`).
* **Prix limite** arrondi au millième, comme les cours Yahoo de ces ETF.
* Réglages dans `S.uiPrefs.prochainAchat` (comme les simulateurs) : aucune
  clé nouvelle à ajouter aux chemins de sauvegarde et de chargement.
* `fetchLocalCours()` demande aussi le cours des lignes cibles.
* « Saisir » ouvre `ov-pos` pré-rempli (crée la position si besoin) ; rien
  n'est écrit sans « Enregistrer ». Après saisie, le plan se recalcule.
* Tuile d'accueil `prochain-achat` : le premier ordre, disparaît s'il n'y a
  rien à acheter.

## Simulateur d'ordres (onglet Stratégie, `#card-sim-ordres`)

Le pendant manuel de Prochain achat, juste sous sa carte (ajouté dans la Wishlist
en 4.3.5, regroupé dans Stratégie à la demande d'Arthur le 29/09/2026). Arthur compose ses ordres
lui-même (titre parmi cibles, positions et wishlist ; quantité en parts **ou** en
euros, arrondie à la part inférieure ; prix limite modifiable), Pilote calcule
frais, investi, débité, reste et répartition après achat. **Il ne propose rien.**
Fonctions `so*`, bloc juste après Prochain achat.

* **Un seul calcul des frais** : tarif, seuil de l'ordre gratuit, marge du prix
  limite, plafond de 0,5 % et cibles viennent de `pacCfg()`, arrondis de `pacR2`.
  `soCalcul()` (pur) et `testsSimulateurOrdres()` (console, 10 cas) : les six cas de
  Prochain achat, repris comme ordres manuels, doivent redonner les mêmes frais,
  le même débit et le même reste au centime. Relancer les deux séries de tests
  après toute modification.
* **L'ordre des lignes est l'ordre de passage.** Fortuneo écrit « 0 € le 1er ordre
  inférieur ou égal à 500 € chaque mois » (lu sur fortuneo.fr le 29/09/2026) : le
  premier ordre de la liste qui tient sous le seuil est gratuit, même après un
  ordre plus gros. C'est la lecture de `pacGratuitDetecte`. Flèches ↑↓ pour
  réordonner.
* Budget (espèces par défaut) et case « Ordre gratuit du mois disponible »
  (détection de Prochain achat par défaut) : propres au simulateur, en mémoire,
  jamais enregistrés. Ils valent pour l'éditeur **et** toutes les cartes.
* **Scénarios** dans `S.uiPrefs.simOrdres = {scenarios: [{id, nom, lignes:
  [{ticker, mode "parts"|"eur", val, prix|null}]}]}` : recalculés aux cours du jour
  à chaque affichage, sauf un prix saisi à la main. Le brouillon ne vit qu'en
  mémoire (effacé à la fermeture). Aucun ordre n'est jamais saisi dans le PEA.
* **Plan proposé** : carte de référence en pointillés (non supprimable) et bouton
  « Partir du plan proposé ». `pacPlanCourant(opts)` accepte `{budget,
  gratuitUtilise}` pour calculer le plan avec le budget et l'ordre gratuit du
  simulateur : les deux se comparent à armes égales.
* « Comparer » ouvre un tableau des cartes cochées (ordres, frais, débité, reste,
  poids par ligne, écart max à la cible). Badges « frais les plus bas » et « plus
  proche de la cible » seulement s'il y a au moins deux cartes à comparer.
* **`pacRender()` appelle `soRender()`** en tête : arrivée des cours (toutes les
  3 min), ouverture de l'onglet et réglages de Prochain achat passent tous par là. Si le
  focus est dans l'éditeur, on recalcule sans redessiner les champs (sinon le
  curseur sortait en pleine saisie). Les actions qui changent la structure (titre,
  parts/€, flèches, ajout, retrait, chargement) appellent `soRender(true)`.
* Écartés par Arthur le 29/09/2026 : les frais de gestion annuels (TER) dans la
  comparaison, et l'offre Fortuneo × Amundi (achats de 500 € à 100 000 € sans
  courtage sur ~120 ETF Amundi jusqu'au 31/12/2026 ; ni WPEA, ni PEMS
  FR001400ZGO4, ni PNAS FR001400ZGR7 n'y figurent, seulement PAEEM et PUST).

## Graphique « Évolution du capital » (vue d'ensemble du PEA, `#card-twr`)

Était dans l'onglet Performance jusqu'en 4.2.5 ; même code, même carte, rendue par
`renderPerf()` à chaque `goTab("dash")`.

5 plages dans `#perf-range-btns` : 1S (prb-1w), 1M (prb-1m), 6M (prb-6m),
YTD (prb-ytd), Max (prb-max, défaut).

* `setPerfRange(range)`   — change la plage, highlight le bouton, sauvegarde dans
                            `S.uiPrefs.perfRange`, appelle `drawPerfChart()`
* `filterByRange(series, range)` — filtre `_perfFullSeries` par date
                            (ancre = aujourd'hui local, pas le dernier point)
* `buildTwrSeries(history)` — série journalière à partir de l'historique Yahoo
* `drawPerfChart()`       — dessine le Chart.js ; si < 2 points après filtre →
                            bascule sur MAX avec message
* `loadPerfHistory()`     — double fetch : `range=max` + `range=1mo` (30 derniers jours
                            journaliers garantis, fusionnés) pour que 1S/1M aient
                            toujours leurs points récents
* `computePnl(series, allTxs, range)` — P&L sur la plage (TWR pour les plages partielles)

Format labels axe X : 1S, 1M, YTD → « 12 mai » ; 6M, Max → « nov. 25 »

Points critiques :
* `_perfFullSeries` est mis en cache (reconstruit uniquement si null), invalidé à
  chaque `renderPerf()`
* Le fallback < 2 points reset TOUS les boutons (pas seulement YTD/MAX)
* La plage préférée est persistée dans `S.uiPrefs.perfRange` via
  `pywebview.api.save_ui_prefs()`

## Conventions de code

* Tout l'UI vit dans `index.html` (~18 700 lignes). Les modules annexes sont des blocs
  JS autonomes en fin de fichier, préfixés (`fin*`, `sp*`, `pr*`, `sa*`, `pa*`, `vo*`,
  `dash*`, `sv*`, `home*`), avec leur propre patch de `goTab`. **Ordre d'insertion : Sports →
  Prêt → Santé → Patrimoine → Formation → Vocabulaire → Tableau de bord → `boot()`.** Les patches de `goTab`
  s'enchaînent, ne pas casser l'ordre.
* Primitives de DA à réutiliser : `.card/.card-h/.card-t/.card-b`, `.btn/.btn-primary/
  .btn-ghost/.btn-sm`, `table + .tw`, `.ov/.modal/.fg/.fg-row/.mact` + `closeOv(id)`,
  `.mkpis/.mkpi` (KPIs), `.m-tag`, `.m-empty`, `.m-note`, `.m-acts/.m-iconbtn`,
  `.set-layout/.set-nav/.set-sec` (paramètres), `.home-user/.home-user-av` (utilisateurs),
  `.sp-fields/.sp-field` (choix de champs), `.fin-ico` (emoji catégories),
  `.sa-grid/.sa-cell` + `.sa-fields/.sa-field` (santé), `.pa-cpt/.pa-leg` (patrimoine),
  `.dash-cfg-row` (tuiles), `.sv-drive/.sv-row` (clés USB),
  `showToastModern(msg, "ok"|"warn"|"err")`, `escHtml()`.
* Une `.ov` s'ouvre avec `classList.add("open")` — la règle CSS est `.ov.open
  { display: flex }`. Il n'y a pas de classe `show` pour les modales.
* Les `.ov` sont en `z-index: 9500` (au-dessus de la sidebar 9000, sous la titlebar
  10000). Une modale ouverte **depuis** une autre doit passer par `openOvTop(id)`,
  sinon l'ordre du DOM décide qui est devant.
* Attention à la spécificité : `.fg label` (0-1-1) imposait MAJUSCULES + interlettrage
  avant l'identité « Carnet », qui l'a remis en casse normale. Les règles
  `label.sv-check`, `label.fo-check`, `label.vo-check` restent : elles règlent aussi la
  taille et l'alignement. Un libellé de texte courant dans un `.fg` se cible toujours
  en `label.ma-classe`.
* Couleurs uniquement via les variables CSS (`--bg2`, `--brd`, `--accent`, `--g`, `--r`,
  `--hover`, `--accent-soft`, `--accent-text`…) et polices via `--font` / `--serif`
  (`--mono` pointe sur Onest) : thème clair ET sombre, plus une couleur d'accent au choix.
  Voir « Identité visuelle Carnet ».
* Icônes : Phosphor, `<i class="ph ph-nom"></i>`. Pas de nouvel emoji dans un bouton de
  l'interface. Un libellé qui porte une icône se sauve et se restaure en `innerHTML`.
* Un nouveau module de données = un fichier `src/<nom>.py` basé sur
  `jsonstore.JsonStore` + deux méthodes `load_`/`save_` dans la classe `Api` de `app.py`.
  Il sera automatiquement propre à chaque utilisateur. Penser à l'ajouter aussi
  à `DASH_WIDGETS` s'il a un chiffre à montrer sur l'accueil.
* Le JS garde l'état en mémoire (`S`, `SP`, `PR`, `SA`, `PA`) et Python ne fait que
  persister. Exception : `load_patrimoine` / `save_patrimoine` renvoient `net`, `serie`
  et `moisSaisi` déjà calculés — l'UI ne refait pas ces calculs.
* Ne jamais recalculer en parallèle un chiffre qu'un autre module produit déjà
  (`window._peaPv` pour le PEA). Deux calculs = deux résultats divergents un jour.

## Déploiement

* Téléchargement du Setup.exe :
  https://github.com/arthur-soulard/arthurpilote.github.com/releases/latest
* Les mises à jour suivantes sont automatiques depuis l'app

## Pistes en attente (proposées, non décidées)

**Les trois qui manquent le plus** — sans elles, Pilote n'est pas « l'app où je fais
tout ». Recommandées dans cet ordre :

- **Module Tâches** (`taches.json`) : échéance, priorité, projet, récurrence
- **Module Agenda** (`agenda.json`) : mois + semaine, fusionnant séances de sport,
  échéances de prêt, relevé de patrimoine, pesée du 1er
- **Écran « Aujourd'hui »** : tâches du jour + événements + séance prévue + échéances.
  Le premier écran à ouvrir le matin.

Autres pistes :

- Objectif d'heures hebdomadaire, avec jauge en haut de l'agenda sport
- Courbe d'heures cumulées année N vs N−1 dans les statistiques sport
- Échéancier prévisionnel du prêt, mois par mois jusqu'à la dernière mensualité
- Simulateur de sortie : « si je vends tout et solde le prêt, il me reste X € »
- Recherche globale (Ctrl+K) sur transactions, séances, pesées, comptes
- Import CSV du relevé bancaire pour « Mes comptes »

**Écartées, ne pas y revenir sans raison nouvelle :**

- **Version mobile / PWA** : écartée par Arthur en 4.1.4 pour la sécurité des données.
  Les JSON sont en clair et le PIN ne chiffre rien ; exposer le serveur local, même
  derrière un VPN, sortait les données du PC. Si la question revient, le prérequis
  serait le chiffrement au repos, pas le réseau.
- **Agrégation bancaire automatique** : contrat pro + validation réglementaire,
  hors de portée d'une app locale. D'où la saisie mensuelle du patrimoine.
- **Passer le dépôt en privé** : écarté par Arthur le 20/09/2026. `updater.py`
  interroge l'API des releases **sans jeton** (en-têtes `User-Agent` + `Accept`
  seulement, `_fetch()` et le téléchargement) ; sur un dépôt privé cet endpoint
  répond 404, indistinguable d'une absence de nouvelle version — l'app se croirait
  à jour pour toujours, et la panne serait silencieuse. Le gain serait par ailleurs
  nul : aucune donnée n'est exposée, `.gitignore` écarte `Donnees/`, `pea_data*.json`,
  `pin.hash` et `profiles.json`, et **aucun fichier de données n'apparaît dans
  l'historique complet** (vérifié sur les 71 commits, pas seulement sur l'état
  courant). Si la question revient, le prérequis serait un second dépôt public dédié
  aux releases — surtout pas un jeton embarqué dans l'exe, il serait extractible.

**Traité depuis** : l'emoji par défaut des catégories créées par l'utilisateur est
deviné d'après le libellé (4.2.7, `finGuessIcon`). L'export de tout l'espace utilisateur, longtemps en attente, est
couvert par la sauvegarde USB (archive zip de tout `Donnees/`). L'import par fichier,
lui, ne couvre toujours que `pea_data.json`.
