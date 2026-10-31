# Pilote

Application desktop Windows et Mac de suivi personnel : bourse (PEA, comptes-titres), budget, prêt (étudiant ou autre),
sport, santé et patrimoine réunis dans une seule app 100 % locale, multi-utilisateurs.
Aucune donnée ne sort du PC — pas de compte, pas de serveur distant, pas de télémétrie.
Deux exceptions, voulues : le module Actus se connecte à la boîte Gmail de
l'utilisateur pour la lire (`docs/modules/actus.md`) ; il n'y envoie rien de Pilote.
Et la section Agenda (22/10/2026) écrit dans l'agenda iCloud de l'utilisateur ses
notes et ce qu'il a coché, et lit ses autres agendas pour les afficher sans jamais
les modifier (`docs/modules/agenda.md`).
**Aussi sur Mac depuis la 4.4.8** (décidé le 11/10/2026, Mac à puce Apple) : une seule
app pour les deux systèmes, pas de copie séparée ; ce qui diffère passe par
`sys.platform` ou `plateforme.py`, le chemin Windows y reste celui d'avant. Avant de
toucher à ce qui dépend du système, lire `docs/mac.md`.

Stack : Python + pywebview (fenêtre native avec UI HTML/CSS/JS ; 4.4.1 sous Windows,
6.2.1 sur Mac), PyInstaller pour compiler en .exe et en Pilote.app, Inno Setup pour le
Setup.exe, GitHub Actions pour build + release.

**Version actuelle : 4.4.42**
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
│   ├── pret.py         # Module « Prêt », nom libre (pret.json)
│   ├── cto.py          # Module « CTO »           (cto.json) : comptes-titres + lecture du CSV Trade Republic
│   ├── releves.py      # Import des relevés de banque (PDF, CSV, Excel, XML) pour le PEA et les CTO
│   ├── titres_connus.py # Catalogue des titres (ISIN, nom -> ticker) pour l'import (docs/import-releves.md)
│   ├── titres_listes.py # ~6 400 titres Euronext + Xetra (généré par `python tests/generer_titres.py`)
│   ├── sante.py        # Module « Santé »         (sante.json) + lecture OCR FitDays
│   ├── ocr_win.ps1     # OCR via Windows.Media.Ocr — appelé par sante.py
│   ├── patrimoine.py   # Module « Patrimoine »    (patrimoine.json)
│   ├── actus.py        # Module « Actus »         (actus.json) : boîte Gmail des newsletters, en IMAP
│   ├── agenda.py       # Agenda iCloud            (agenda.json) : séances, objectifs, mensualités, en CalDAV
│   ├── expositions.py  # Onglet Expositions : composition des ETF (iShares, Amundi) + mise à jour
│   ├── expositions_base.py # Compositions livrées avec l'app (généré par `python src/expositions.py`)
│   ├── jsonstore.py    # Socle commun : écriture atomique + backup quotidien 7 j
│   ├── sauvegarde.py   # Sauvegarde externe sur clé USB (miroir + archives zip)
│   ├── appicon.py      # Icône recolorée selon la couleur d'accent
│   ├── splash.py       # Petite fenêtre de chargement affichée au lancement
│   ├── updater.py      # Auto-updater (check + download + install) + fiches des versions
│   ├── nouveautes.json # Fiche de chaque version : avant et après une mise à jour, historique
│   ├── notifications.py
│   ├── plateforme.py   # Ce qui diffère entre Windows et Mac (docs/mac.md)
│   └── ui/
│       ├── index.html  # TOUTE l'UI (HTML + CSS + JS dans un seul fichier, ~24 000 lignes)
│       └── vendor/     # Chart.js, polices woff2 (drapeaux compris), icônes Phosphor : servis en local (aucun CDN)
├── build/
│   ├── installer.iss   # Script Inno Setup utilisé par la CI (AppVersion à bumper)
│   ├── pilote.spec     # Spec PyInstaller → dist/Pilote/ (Pilote.exe + _internal/)
│   ├── pilote-mac.spec # Spec PyInstaller Mac → dist/Pilote.app (fabriqué par build-mac.yml)
│   └── build.bat       # build local
├── assets/             # icon.ico + make_icon.py (générateur d'icône)
├── docs/               # Fiches détaillées par module (voir « Documentation détaillée »)
├── .github/workflows/  # release.yml (publication), build-windows.yml et build-mac.yml (tests de la branche mac)
├── tests/              # donnees_exemple.py (Camille), lire_tests.py, ecrans.txt, verifier_release.py, test_*.py
├── THIRD-PARTY-NOTICES.txt # licences des composants embarques (dans l'exe, l'app Mac et le Setup)
└── requirements.txt    # pywebview, pyinstaller, win10toast + setuptools<81, pillow, pypdf, pyobjc-framework-Vision (Mac)
```

En dev, `Donnees` à la racine du dépôt est un lien symbolique vers le dossier de
données de l'app installée.

## Données sur disque

Tout vit dans `<racine app>/Donnees/` (sur Mac, dans l'app compilée :
`~/Library/Application Support/Pilote/Donnees`, hors de Pilote.app que la mise à jour
remplace). **Chaque utilisateur a son propre dossier**, tous modules confondus :

```
Donnees/
├── users.json                # liste des utilisateurs + utilisateur actif
├── sauvegarde.json           # config de la sauvegarde USB (niveau installation)
├── etf_compositions.json     # compositions des ETF téléchargées (données publiques, niveau installation)
├── users/<slug>/
│   ├── pea_data.json         # PEA              (+ backups/)
│   ├── finances.json         # Mes comptes      (+ backups_finances/)
│   ├── sports.json           # Sports           (+ backups_sports/)
│   ├── pret.json             # Prêt             (+ backups_pret/)
│   ├── cto.json              # CTO, tous les comptes-titres, et le portefeuille Crypto (+ backups_cto/)
│   ├── sante.json            # Santé            (+ backups_sante/)
│   ├── patrimoine.json       # Patrimoine       (+ backups_patrimoine/)
│   ├── actus.json            # Actus : adresse + code d'application chiffré par Windows (+ backups_actus/)
│   ├── agenda.json           # Agenda iCloud : identifiant, code chiffré, agenda, cases (+ backups_agenda/)
│   ├── formation.json, certificats/  # module Formation retiré le 11/10/2026 :
│   │                         #   laissés sur le disque, plus lus par l'app
│   ├── vocabulaire.json      # module Vocabulaire retiré le 11/10/2026, idem
│   │                         #   (devenu une page à part : docs/pistes.md)
│   └── pin.hash              # code PIN de CET utilisateur (si configuré)
├── icones/                   # .ico générés à la couleur d'accent
└── crash.log
```

Rien n'est partagé entre deux utilisateurs — même le thème, la couleur d'accent et
les onglets masqués sont propres à chacun (ils vivent dans `pea_data.json`).

`storage.get_user_dir()` est la racine que `jsonstore.py` et `finances.py` utilisent.

### `_cache` : dans le fichier courant, jamais dans les backups

`pea_data.json` contient une clé `_cache` (cours et historiques Yahoo) qui pèse à
elle seule plus que toutes les données réunies : ~620 Ko contre ~15 Ko chez Arthur (octobre 2026). Elle est
volontairement persistée — c'est ce qui fait vivre l'app **hors ligne** :
`GET /data` la repasse au serveur (`server.hydrate_cache`) avant les premiers cours,
et le serveur la rend quand Yahoo ne répond pas (liste `stale`). Jusqu'à la 4.3.13,
elle ne servait en fait à rien : voir `docs/modules/pea.md`, « Cours et courbe hors ligne ».

Mais `storage._daily_backup()` l'**exclut** : un backup ne doit contenir que
l'irremplaçable. Sans ça, 200 Ko de cache régénérable étaient recopiés sept fois
par utilisateur, puis embarqués dans chaque archive de sauvegarde USB. Backup du
jour : 10 Ko au lieu de 418 Ko. Ne pas « simplifier » en resérialisant `data` tel quel.

### Fichier illisible : rien n'est réécrit par-dessus (4.4.21)

Côté Python aussi : `Api.save_ui_prefs` et l'enregistrement de la fenêtre à la
fermeture n'écrivent rien si `storage.get_last_load_info()["error"]` est posé.
Chaque écriture fait `fsync` avant le renommage, le backup du jour s'écrit par
temporaire, et la lecture essaie les backups du plus récent au plus ancien jusqu'au
premier lisible. Les copies faites avant un import vivent dans
`backups/avant_import/` (hors rotation). Un `users.json` illisible est gardé à côté
(`users.illisible-<date>.json`) et la liste est refaite à partir des dossiers.

### `crash.log` : seulement les vrais plantages

`install_crash_handler()` (app.py) écarte les erreurs connues et sans conséquence des
bibliothèques. Dont, depuis le 01/10/2026, la `KeyError: 'master'` que pywebview lève
à chaque fermeture par la croix (il renvoie la réponse d'`Api.close()` à une fenêtre
déjà détruite) : 286 des 288 entrées du journal au 30/09, qui noyaient les vrais
plantages. Ne pas « corriger » en différant la fermeture : d'après le code de
pywebview 4.4.1 (non essayé), son fil pourrait attendre pour toujours une réponse
de la page disparue, et l'app ne se terminerait plus.

### Migrations automatiques (idempotentes, ne jamais les supprimer)

* `storage.ensure_migrated()` — une installation antérieure à la 4.1.2
  (`profiles.json` + fichiers de modules à la racine) est déplacée vers
  `users/<slug>/` au premier lancement. `profiles.json` devient `profiles.legacy.json`.
* `storage.migrate_legacy_pin()` — le PIN, global jusqu'à la 4.1.3, est attribué au
  **premier** utilisateur. Appelée au démarrage de `main()` et en fin de `ensure_migrated()`.

## ⚠ Six choses à ne JAMAIS casser

1. **`_PIN_SALT`** dans `src/server.py` → sert au hash des codes PIN déjà enregistrés.
2. **L'`AppId` GUID** dans `build/installer.iss` → c'est l'identité de l'installation.
   C'est grâce à lui que le renommage en Pilote n'a pas déplacé les données : le Setup
   reconnaît l'installation existante et réinstalle dans son dossier. Conséquence : le
   dossier d'installation s'appelle toujours `%LocalAppData%\Programs\Suivi PEA\`.
   C'est normal, ne pas « corriger ». Et `Donnees\` vit **dans** ce dossier : jamais
   `{app}` dans `[UninstallDelete]`, jamais `UninstallLogMode` repassé en `append`
   (jusqu'à la 4.3.13, désinstaller effaçait toutes les données ; détail dans
   `docs/mise-a-jour.md`).
3. **La sémantique de `_hydrationDone`** (index.html) → ce drapeau autorise l'écriture
   disque. Il doit suivre la **réussite de la lecture** (`!_debug.load_error`), jamais le
   volume de données : un utilisateur qui vient d'être créé a un PEA vide et doit
   pouvoir enregistrer. Côté Python, un `pea_data.json` absent n'est **pas** une erreur
   de lecture (`storage.load_data()` laisse `error` à `None`).
4. **`ocr_win.ps1` dans les `datas` de `build/pilote.spec`** → sans cette ligne, l'OCR
   du module Santé fonctionne parfaitement en dev et **échoue
   silencieusement dans l'exe compilé** : le script est introuvable, `ocr_available()`
   répond « Script OCR introuvable » et l'import de captures ne marche plus. Une panne invisible tant
   qu'on ne teste pas le binaire. Vérification : `dist/Pilote/_internal/ocr_win.ps1`
   doit exister après le build.

5. **`src/ui/vendor/` dans les `datas` de `build/pilote.spec`** → même piège que
   `ocr_win.ps1` : sans cette ligne, Chart.js, les polices et les icônes sont
   introuvables dans l'exe compilé. Les graphiques disparaissent, la typo retombe sur
   celle du système et les boutons perdent leurs icônes, alors que tout marche
   parfaitement en dev. Vérification : `dist/Pilote/_internal/ui/vendor/` existe.

6. **`BUNDLE_ID` dans `build/pilote-mac.spec`** → l'identité de l'app pour macOS,
   comme l'`AppId` pour Windows : autorisations et préférences y sont attachées. Ne
   jamais la changer, et ne pas renommer `Pilote_Mac.zip` (les Mac installés le
   cherchent sous ce nom dans chaque release, `updater.MAC_ASSET`).

## Documentation détaillée : `docs/`

Le détail de chaque module et de chaque mécanisme vit dans `docs/` : ce qui a été
mesuré, décidé avec Arthur ou corrigé après une panne. **Avant de modifier une
partie, lis sa fiche** : ne redécouvre pas ce qui y est déjà écrit. Quand tu
changes une partie, mets à jour sa fiche plutôt que ce fichier.

| Fiche | Contenu | À lire avant de toucher à |
|---|---|---|
| `docs/sauvegarde-usb.md` | clé USB : envoi en miroir, archives, restauration | `sauvegarde.py`, fonctions `sv*` |
| `docs/utilisateurs-et-pin.md` | multi-utilisateurs, code PIN | utilisateurs dans `storage.py`, `/pin/*`, écran de verrouillage |
| `docs/demarrage-et-icone.md` | écran de chargement, exe en dossier, idna, icône à l'accent | `splash.py`, `main()`, `appicon.py`, `build/pilote.spec` |
| `docs/mise-a-jour.md` | auto-update, repli quand l'API refuse, lire le vrai journal, fiche des nouveautés | `updater.py`, `nouveautes.json`, section `[Run]` d'`installer.iss` |
| `docs/design-carnet.md` | polices, couleurs, formes, icônes, graphiques, vue d'ensemble du PEA | tout changement visuel, `Chart.defaults` |
| `docs/accueil.md` | page d'accueil, tuiles du tableau de bord | `home*`, `dash*`, `DASH_WIDGETS` |
| `docs/parametres.md` | sections de la fenêtre Paramètres | `openSettings`, `setGoSection` |
| `docs/modules/pea.md` | Expositions, frais des ETF, Prochain achat, simulateur d'ordres, courbe du capital | `expositions.py`, `pac*`, `so*`, `renderPerf` |
| `docs/modules/comptes.md` | Mes comptes | `finances.py`, `fin*` |
| `docs/modules/pret.md` | Prêt (nom libre, « Prêt étudiant » jusqu'à la 4.3.33) : un seul prêt, le prêt générique de la 4.4.17 retiré en 4.4.18, retour du schéma 7 au schéma 6 | `pret.py`, `pr*` |
| `docs/modules/sports.md` | Sports | `sports.py`, `sp*` |
| `docs/modules/patrimoine.md` | Patrimoine, biens immobiliers (ligne du bien + ligne de son crédit, 4.4.18) | `patrimoine.py`, `pa*` |
| `docs/modules/sante.md` | Santé, lecture des captures FitDays | `sante.py`, `ocr_win.ps1`, `sa*` |
| `docs/modules/cto.md` | CTO : « compte actif » (écrans du PEA), versements déduits, courtiers et frais, import CSV Trade Republic, plans | `cto.py`, `/isin`, `cto*`, `_cptBasculer`, `COURTIERS`, `pac*` |
| `docs/modules/crypto.md` | Crypto : compte de `cto.json` marqué `crypto`, section à part, catalogue des cotations en euros, import Trade Republic, tuiles | `CRYPTO_CATALOGUE`, `cryptoCompte`, `ctoComptesTitres`, `crypto-*`, `CRYPTO_ISIN` |
| `docs/import-releves.md` | import des relevés de toutes banques (PEA et CTO) : CSV conseillé et PDF, formats, pièges par banque, reconnaissance des titres (catalogue, ticker seul) | `releves.py`, `ctoImport*`, `/isin` |
| `docs/modules/actus.md` | Actus : boîte Gmail en IMAP, code chiffré, mail en iframe sous ticket | `actus.py`, `/actus/mail/`, `ac*` |
| `docs/modules/agenda.md` | Agenda : calendrier, notes, iCloud en CalDAV (écriture et lecture), synchronisation | `agenda.py`, `ag*`, `save_agenda*` |
| `docs/mac.md` | version Mac : décisions, étapes, ce qui reste propre à Windows, build Mac | `plateforme.py`, tout `sys.platform`, `pilote-mac.spec`, `build-mac.yml` |
| `docs/pistes.md` | pistes proposées, et celles écartées (à ne pas reproposer) | toute suggestion de nouveauté |

Rappelés ici parce qu'une erreur ne se voit qu'une fois l'exe installé (détail
dans les fiches) :

* **Exe en dossier (onedir), jamais en exe unique (onefile)**, ni retrait de
  `import encodings.idna` en tête d'`app.py` ou des options
  `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS` de `main()` : `docs/demarrage-et-icone.md`.
* **Mise à jour** : ne pas réduire le délai de 5 s du batch, démarrer le polling JS
  avant `start_update()` : `docs/mise-a-jour.md`. `src/nouveautes.json` doit rester
  dans les `datas` de `build/pilote.spec` (sinon historique vide dans l'exe, même
  piège que `ocr_win.ps1`) et garder son chemin dans le dépôt (lu à cette adresse
  par les versions déjà installées).
* **Une lecture OCR (Santé) ne fait que pré-remplir** : rien n'est
  enregistré sans validation. Fiche du module.

## Pour sortir une nouvelle version

1. Modifier le code
2. Bumper `APP_VERSION` dans `src/app.py`
3. Bumper `AppVersion` dans `build/installer.iss`
4. Écrire la fiche de la version **en tête** de `src/nouveautes.json` (même numéro,
   texte pour l'utilisateur : nouveau / amélioré / corrigé). Elle doit être dans le
   commit du tag : c'est là que les installations existantes la lisent avant de
   proposer la mise à jour (`docs/mise-a-jour.md`, « Fiche des nouveautés »)
5. **Avant le tag, Mac et Windows** (règle d'Arthur) : mettre dans `tests/ecrans.txt`
   les écrans que la version change, pousser sur la branche `mac`, puis lire les deux
   tests et les captures sur données d'exemple : `python tests/lire_tests.py <sha>`
   (`docs/mac.md`, « Captures sur données d'exemple »)
6. `git add … && git commit && git tag vX.Y.Z && git push origin main && git push origin vX.Y.Z`
7. GitHub Actions build `dist/Pilote/` puis `Pilote_Setup.exe`, et crée la release
   avec le Setup (un `Pilote.exe` seul ne tourne pas sans son `_internal/`) ; un
   second job, sur un Mac de GitHub, y joint ensuite `Pilote_Mac.zip` (s'il échoue,
   le Setup est déjà publié). Avant de fusionner du code propre à un système dans
   main, les tests `build-mac.yml` et `build-windows.yml` de la branche `mac`
   montrent s'il démarre des deux côtés (`docs/mac.md`)

Avant le tag : `python tests/verifier_release.py vX.Y.Z` et `python -m unittest discover -s tests`
(la CI les relance de toute façon : un tag qui échoue n'est pas publié). Pas de limite du nombre
de versions par jour (Arthur a retiré la règle « une version par jour au plus » le 21/10/2026).

Règle importante : le numéro de version ne peut qu'augmenter (comparaison sémantique).
Ne jamais descendre sinon l'auto-updater croit que l'app est déjà à jour.

## Navigation

Titlebar custom (fenêtre frameless, 36 px) : logo + « Pilote » + boutons fenêtre.
C'est le seul endroit où « Pilote » est écrit.
Topbar minimale : fil d'Ariane (« Accueil », « PEA › Positions »), indicateur
« Dernière actualisation HH:MM » avec Actualiser (`.refresh-grp`), et Retour (undo).
Retour suit l'onglet ouvert (`_undoModulesOuverts`) : section PEA → ses actions,
section Prêt → les siennes et celles du PEA, ailleurs → grisé.
Le fil d'Ariane est écrit par `_updateCrumb(id)`, appelée à la fin du `goTab`
**d'origine** et pas dans un patch : chaque patch rappelle la version d'origine, le fil
suit donc tous les chemins de navigation (barre latérale, tuiles, Ctrl+1..7).

Sidebar : un onglet **Accueil** seul en tête, puis les sections en accordéon
(`NAV_SECTIONS` dans index.html), réparties sous deux titres, « Bourse » et
« Vie perso » (4.4.2). Une seule section dépliée à la fois, un second clic
sur l'en-tête la referme, aucune section n'est obligatoirement ouverte. Une pastille
marque la section contenant l'onglet actif. En bas : pastille utilisateur, thème,
Paramètres.

* **Une section par CTO** (`_navBlocs`) : « CTO » suivi du nom du compte
  (`ctoNomSection`, « CTO TR » reste « CTO TR »), onglets `cto-pos@c2`. Sans
  aucun CTO, une seule section « CTO » mène à l'écran de création. Le « + » du
  titre Bourse crée un CTO (absent si le module CTO est décoché).
* **Ordre libre** : chaque section se glisse par son en-tête, d'un titre à
  l'autre (`_navBrancherGlisser`). Ordre dans `S.uiPrefs.navOrdre` (clés des
  sections et `@perso`), résolu par `_navOrdre` : un nouveau CTO se range après
  le dernier, une section masquée garde son voisin. Défaut : `NAV_ORDRE_DEFAUT`.
* Rebâtir la barre passe par `_reconstruireSidebar()` (pastille utilisateur et
  non lus d'Actus compris) : après la lecture des CTO, leur création, leur
  renommage ou leur suppression.

| Entrée          | Onglets (ids des panes : `pane-<id>`)                              |
|-----------------|--------------------------------------------------------------------|
| Accueil         | home                                                               |
| PEA             | dash, pos, sector, div, tx, wish, dep, strat (plus de `perf`)      |
| CTO « nom » (un par CTO) | cto-dash, cto-pos, cto-sector, cto-div, cto-tx, cto-wish, cto-strat |
| Crypto          | crypto-dash, crypto-pos, crypto-tx (écrans du PEA, comme un CTO : `docs/modules/crypto.md`) |
| Actus           | ac-boite (« Newsletters »), ac-connexion                           |
| Agenda          | ag-cal (« Calendrier »), ag-notifs (« Notifications »), ag-connexion (« iCloud ») |
| Mes comptes     | fin-month, fin-year                                                |
| Prêt (nom libre) | pr-overview, pr-pea, pr-av, pr-liv, pr-params                     |
| Sports          | sp-agenda, sp-goals, sp-stats                                      |
| Patrimoine      | pa-vue, pa-comptes, sim (Simulateurs, dans le PEA jusqu'à la 4.4.1) |
| Santé           | sa-suivi, sa-mesures, sa-goals                                     |

Fonctions : `_injectSidebar()`, `_setActiveSidebar(id)`, `_navToggleSection(secId)`,
`_navSectionOf(tabId)`. Section dépliée gardée en mémoire seulement (`_navOuverte`,
"" = tout replié) : Pilote s'ouvre toujours sur l'Accueil, toutes sections repliées
(demande d'Arthur, 4.3.18). L'ancienne clé `S.uiPrefs.navOpen` est ignorée.
`SIDEBAR_ITEMS` reste dérivé à plat de `NAV_SECTIONS` pour l'API historique (onglets
masquables via ⊘, Ctrl+1..7, écran Paramètres).

Les onglets `cto-*` n'ont pas de pane : ils montrent ceux du PEA (`cto-pos` → `pane-pos`)
sur le CTO de leur section, que `ctoAvantOnglet` met dans `S` (« compte actif »,
`docs/modules/cto.md`). Tout autre onglet remet le PEA dans `S`. `cto-dash@c2` ouvre un
CTO précis ; `_navSectionOf` ignore le `@…`, `_setActiveSidebar` complète un
`cto-pos` sans `@` par le CTO affiché (`_ongletComplet`). `body.dataset.activeTab`
garde l'onglet sans `@`.

Dix blocs ajoutent leur propre patch de `window.goTab`, dans cet ordre : Mes comptes,
Sports, Prêt, Accueil, Santé, Sauvegarde USB, Patrimoine, Actus, CTO, puis Agenda
après le tableau de bord (`grep -n "window.goTab = function"`). Ils s'enchaînent : ne pas casser l'ordre.

## Serveur local (server.py, port 7438)

* `GET /data` → hydratation initiale de l'UI (+ `_debug.load_error`)
* `GET /cours?tickers=EPA:ESE,WPEA.PA` → cours actuels + variations d1/w1/m1/y1
* `GET /history?tickers=…[&range=max][&since=AAAA-MM-JJ]` → historique journalier
  (`max` n'est jamais demandé tel quel à Yahoo, qui le rend par semaine ou par mois :
  voir `docs/modules/pea.md`, « Courbe au jour près »)
  (ranges : 1mo, 3mo, 6mo, ytd, 1y, 2y, 5y, 10y, max)
* `GET /sparkline`, `/keystats`, `/analysts`, `/search`, `/ping`
* `GET /users` → liste des utilisateurs (+ `hasPin`)
* `GET /pin/required`, `/pin/set`, `/pin/check` — tous avec `?user=<slug>` optionnel
* `GET /scan-orphan-data` → candidats de récupération (installations extérieures)
* `GET /recover-data?from=…` → **le chemin doit figurer dans le scan**, sinon 403 :
  cet endpoint écrase le `pea_data.json` actif, il ne prend pas un chemin libre
* `GET /vendor/<fichier>` → Chart.js, polices et icônes, liste blanche d'extensions
  (`.js`, `.css`, `.woff2`), confiné sous `ui/vendor/`
* `GET /isin?isin=…&nom=…[&nom2=…&points=date:prix,…&depuis=…]` → cotations en euros
  d'un ISIN, devise vérifiée (et historique comparé aux prix payés), et secteur
  (import du CTO : `docs/modules/cto.md`)
* `GET /actus/mail/<ticket>` → la page d'un mail du module Actus, pour son iframe
  (ticket créé par `Api.actus_ouvrir`, 10 min) : voir `docs/modules/actus.md`
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
  C'est elle qui interdit les CDN : d'où `ui/vendor/`. Sur Mac, pywebview y évaluait du
  texte (`new Function`, `eval`) : adapté par `plateforme.adapter_pont_mac`. Ne jamais
  ajouter `'unsafe-eval'` pour « réparer » (`docs/mac.md`). Ne pas rajouter de
  `<script src="https://…>` dans index.html, il sera silencieusement bloqué.
* `/vendor/` est joignable **sans** jeton : le navigateur charge `<script src>` et
  `<link href>` lui-même, ces requêtes ne passent pas par le wrapper `fetch`. Ces
  fichiers ne contiennent aucune donnée utilisateur, et les verrous Host et Origin
  s'appliquent toujours.
* `/actus/mail/<ticket>` est joignable sans jeton pour la même raison (une iframe
  se charge seule) : le ticket aléatoire du chemin le remplace. C'est la seule
  réponse avec `X-Frame-Options: SAMEORIGIN` au lieu de `DENY`, et sa propre CSP
  (aucun script, images distantes permises, `sandbox`).
* `/pin/set` exige l'**ancien** code dès qu'un PIN existe. Poser un premier PIN
  reste libre : il n'y a rien à prouver.
* `/pin/check` est ralenti (0,25 s) et bloqué 60 s après 10 échecs, **côté serveur**.
  Le compteur de l'écran de verrouillage est purement cosmétique et ne protège rien.
  Le paramètre `user` des routes `/pin/*` doit être un utilisateur de `users.json`
  (4.4.21) : sinon « DEMO » ou « ./demo » contournaient le blocage, et `../x` écrivait
  hors de `Donnees/`.
* **Limite assumée** : tant que Pilote tourne, un autre programme du PC (même un autre
  compte Windows) peut demander `/`, y lire le jeton, puis lire `/data`. Les trois verrous
  visent les pages web, pas un programme local ; c'est écrit dans `SECURITY.md`.
* Tout nom venu de l'extérieur (Yahoo, justETF, relevé importé, mail) passe par
  `escHtml` avant d'entrer dans du HTML : la CSP autorise `'unsafe-inline'`, elle
  n'arrêterait pas un `onerror=` injecté, qui aurait tout le pont. `Api.open_url`
  n'ouvre que `http`, `https` et `mailto` (4.4.21).

## Aucune donnée réelle dans le dépôt

Le dépôt est **public**. Jamais un montant, une ligne de portefeuille, un nom de
contrat, une mesure de santé ou un relevé d'Arthur dans un fichier, un commentaire
ou un message de commit : écrire « vérifié sur un vrai relevé, au centime », ou
prendre les données fictives de Camille (`tests/donnees_exemple.py`). Des montants
réels étaient écrits dans `docs/` jusqu'à la 4.4.20 (audit du 20/10/2026) : retirés
des fichiers, puis de tout l'historique git le 21/10/2026 (réécrit et poussé en force,
tags compris). Les numéros de commit d'avant cette date, cités dans d'anciennes notes,
n'existent plus.

## Conventions de code

* Tout l'UI vit dans `index.html` (~24 000 lignes). Les modules annexes sont des blocs
  JS autonomes en fin de fichier, préfixés (`fin*`, `sp*`, `pr*`, `sa*`, `pa*`, `ac*`,
  `cto*`, `dash*`, `sv*`, `home*`, `ag*`), avec leur propre patch de `goTab`. **Ordre des patchs :
  Mes comptes → Sports → Prêt → Accueil → Santé → Sauvegarde USB → Patrimoine → Actus → CTO,
  puis le tableau de bord, Agenda et `boot()`.** Les patches de `goTab` s'enchaînent, ne pas casser l'ordre.
* **HTTP pour lire, pont pour écrire.** Le serveur local (`/data`, `/cours`, `/history`,
  `/isin`…) sert les lectures et Yahoo ; toute écriture passe par une méthode `save_*` du
  pont pywebview (`window.pywebview.api`), enveloppée par `_surveillerEcritures` (gel,
  vidange, alerte d'échec).
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
  `label.sv-check` reste : elle règle aussi la
  taille et l'alignement. Un libellé de texte courant dans un `.fg` se cible toujours
  en `label.ma-classe`.
* Couleurs uniquement via les variables CSS (`--bg2`, `--brd`, `--accent`, `--g`, `--r`,
  `--hover`, `--accent-soft`, `--accent-text`…) et polices via `--font` / `--serif`
  (`--mono` pointe sur Onest) : thème clair ET sombre, plus une couleur d'accent au choix.
  Voir `docs/design-carnet.md`.
* Icônes : Phosphor, `<i class="ph ph-nom"></i>`. Pas de nouvel emoji dans un bouton de
  l'interface. Un libellé qui porte une icône se sauve et se restaure en `innerHTML`.
* Un nouveau module de données = un fichier `src/<nom>.py` basé sur
  `jsonstore.JsonStore` + deux méthodes `load_`/`save_` dans la classe `Api` de `app.py`.
  Il sera automatiquement propre à chaque utilisateur.
* **Toute nouvelle fonctionnalité vient avec ses tuiles d'accueil** (règle d'Arthur,
  22/10/2026) : `DASH_WIDGETS`, `DASH_ICONS`, `NAV_MODULES.tuiles`, `docs/accueil.md`.
  Les proposer à Arthur dès la question de départ ; pas de « fini » sans elles.
* **Enregistrements en attente** (4.3.14, bloc juste après `_syncToPython`) : les
  méthodes `save_*` du pont pywebview sont enveloppées (`_surveillerEcritures`) ;
  un module qui retarde ses écritures ajoute sa fonction « écrire maintenant » à
  `_vidangeurs` (PEA, Mes comptes). La croix vide tout avant de fermer ; changer
  d'utilisateur, restaurer, importer appellent `_gelerEnregistrements()` avant
  d'agir, `_degelerEnregistrements()` en cas d'échec. Une nouvelle méthode
  d'écriture s'appelle donc `save_<module>`, sinon elle échappe au gel. Un échec
  d'écriture s'affiche toujours (`_alerteEnregistrement`), jamais seulement en console.
* Le JS garde l'état en mémoire (`S`, `SP`, `PR`, `SA`, `PA`) et Python ne fait que
  persister. Exception : `load_patrimoine` / `save_patrimoine` renvoient `net`, `serie`
  et `moisSaisi` déjà calculés — l'UI ne refait pas ces calculs.
* Ne jamais recalculer en parallèle un chiffre qu'un autre module produit déjà
  (`window._peaPv` pour le PEA, `ctoResume(id)` pour un CTO). Deux calculs = deux
  résultats divergents un jour.
* **`S` peut contenir un CTO** (section CTO ouverte, `_estCto()`). Ce qui s'écrit
  dans `pea_data.json` passe par `_etatPea()`, jamais par `S` ; un code qui lit le PEA
  hors de sa section (accueil, Patrimoine, Prêt) s'exécute avec le PEA dans `S`, ou
  vérifie `_estCto()`. Réglages propres à un compte : `_cptPrefs()`. Détail :
  `docs/modules/cto.md`.

## Déploiement

* Téléchargement du Setup.exe :
  https://github.com/arthur-soulard/arthurpilote.github.com/releases/latest
* Les mises à jour suivantes sont automatiques depuis l'app
