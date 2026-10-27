# Démarrage et icône de la fenêtre

Fiche détaillée tirée de `CLAUDE.md`, qui garde les règles générales (dont les six choses à ne jamais casser).

## Démarrage : écran de chargement (`splash.py`, 4.2.7)

La fenêtre principale est créée **cachée** (`hidden=True`) et ne s'ouvre qu'une fois
l'accueil prêt. En attendant, une fenêtre sans bordure (460 × 350 depuis la 4.3.19 ; 340 × 260 en 4.3.18, contenu grossi
de 35 % par `.scene { zoom }`) montre le
logo « P » à la couleur d'accent et « Pilote », dans le thème de l'utilisateur actif.

* **Animation « Signature »** (03/10/2026). Arthur voulait « un truc plus dynamique,
  plus wahou » que les trois points : il l'a choisie parmi trois maquettes (Signature,
  Orbite des huit sections, Courbe de portefeuille). Le logo arrive en rebondissant,
  le P monte dans la tuile, « Pilote » s'écrit lettre par lettre (1,4 s) ; ensuite, en
  boucle, un reflet passe sur la tuile, des ondes en partent, une barre glisse dessous.
  CSS seul, rien que `transform` et `opacity` : pendant le chargement, le processeur
  est pris par Python et WebView2, ces propriétés restent fluides. En mouvement réduit
  (effets d'animation de Windows coupés), tout s'affiche d'emblée et seule la barre
  glisse, plus lentement. Vérifié dans une vraie fenêtre pywebview (thèmes clair et
  sombre), pas encore dans l'exe compilé.
* **Coins arrondis** (03/10/2026, demande d'Arthur). Les coins sont
  arrondis par Windows 11 lui-même (`splash.arrondir_coins`, DWM :
  `DWMWA_WINDOW_CORNER_PREFERENCE` = arrondi, plus `DWMWA_BORDER_COLOR` = `--brd` rendu
  opaque), appelé sur l'événement `shown` de l'écran de chargement : à cet instant,
  c'est la seule fenêtre visible du processus (pywebview montre puis cache aussitôt la
  fenêtre principale, `hidden=True`), donc `_hwnd_principale()` la trouve. Rayon fixé
  par Windows (8 px), lissé, avec l'ombre du système. Pas de fenêtre transparente avec
  `border-radius` en CSS : pywebview la fait par « couleur clé » (rouge pur rendu
  transparent), ce qui laisse des franges. Sous Windows 10, l'appel échoue sans rien
  casser (coins droits). Fond lisse, à peine plus clair au centre (`haut`).
* **Pas de grain de papier.** Essayé en 4.3.20 (bruit SVG `feTurbulence` en
  surimpression) : Arthur l'a trouvé laid en sombre (« le papier rend moche »), puis
  en clair (« c'est nul »). Retiré en 4.3.21, ne pas le reproposer.

* `boot()` appelle `_appReady()` → `Api.app_ready()` → `reveal_main_window()` (app.py) :
  montre la fenêtre, ferme l'écran de chargement, pose l'icône à l'accent. Une seule
  fois (`_revealed`). Le signal part **après** les modules, le premier chargement
  des cours **et l'historique du PEA** (5 s au plus pour les deux : sans réseau on
  ouvre avec les derniers connus), dans le
  `catch` de `boot()` aussi, et **dès l'écran du code PIN** (`_checkPinLock`) : le
  code se tape dans la fenêtre, elle ne peut pas rester cachée.
* **Historique du PEA attendu (03/10/2026).** Arthur voyait des données se charger
  encore une fois la fenêtre ouverte. Mesuré avec un journal horodaté : l'historique
  (mini-courbe et chiffres 1S, 1M, YTD de la tuile « Performance du PEA ») arrivait
  0,8 s **après** l'ouverture, suivi d'un second appel `range=1mo` : la tuile se
  redessinait 1,6 s après l'ouverture.
  Désormais `boot()` le demande avec les cours (`perfSeriesAsync()`) et attend les
  deux ; le second appel a disparu (historique journalier, voir
  `docs/modules/pea.md`). Délai d'ouverture inchangé : 2,5 s avant comme après, de
  la première requête à l'ouverture (dev, utilisateur de test, 3 titres).
  Les PER, rendements et mini-courbes des tableaux Positions et Wishlist
  (`/keystats`, `/sparkline`, `/analysts`) ne sont toujours **pas** attendus : rien
  ne s'en affiche sur l'accueil.
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
* **La fenêtre de Pilote se trouve par `_hwnd_principale()`** (app.py, qui reprend
  `appicon._main_hwnd()` : la fenêtre visible de CE processus), jamais par
  `GetForegroundWindow()` (4.3.14) : agrandissement, taille mémorisée à la
  fermeture, remise au premier plan. La remise au premier plan passait la fenêtre
  déjà au premier plan à `SetForegroundWindow` et ne faisait rien (reproduit le
  01/10/2026). Windows ne laisse passer devant que le processus lancé par
  l'utilisateur : la 2e instance cède ce droit (`AllowSetForegroundWindow(-1)`)
  avant d'envoyer son ping. Non vérifié en vrai : pendant l'essai, la session
  n'avait aucune fenêtre au premier plan (`GetForegroundWindow()` = 0), et rien ne
  pouvait passer devant. Test à la main : Pilote ouvert derrière une autre
  fenêtre, double-clic sur son raccourci → il doit revenir devant.

## Lenteur du démarrage : mesures du 11/10/2026

**Outils** (rien ne s'active sans `PILOTE_DIAG=1`) :
`PILOTE_DIAG=1 python src/app.py` écrit des repères `[t]` (secondes depuis le
lancement : imports, serveur, fenêtres, écran de chargement, page chargée, page
prête), le journal de la page `[diag]` (`window.__journal`), les mesures du
navigateur `[diag-nav]` (début de la navigation, durée de chaque requête) et, toutes
les 0,5 s pendant 15 s, ce que fait chaque fil Python `[pile]`.

**Où passe le temps** (PC d'Arthur, Pentium Gold 7505, 2 cœurs ; 17 lancements) :

| Étape | Rapide | Lent |
|---|---|---|
| Imports Python (pywebview, modules) | 1,0 s | 3,0 s |
| .NET puis WebView2 jusqu'à l'écran de chargement | 0,6 s | 5,9 s |
| Moteur Edge jusqu'à la page principale chargée | 1,5 s | 5,5 s |
| Page, modules, attente de Yahoo | 1,7 s | 6,0 s |

Les deux étapes du milieu sont du code natif (.NET, processus `msedgewebview2`) :
Python attend pendant ce temps (`[pile]`). Elles varient avec la charge du PC
(23 % du processeur occupés sans Pilote ce jour-là). Total : 6 à 25 s.

* **Corrigé en 4.3.35 : relecture des certificats à chaque requête HTTPS.** `urlopen` sans
  contexte en recrée un par connexion et relit tout le magasin de Windows (~60 ms
  de calcul, les fils l'un après l'autre sous le GIL). `server._SSL_CTX`, créé une
  fois, sert à toutes les requêtes Yahoo. Mesuré : `/cours` 1,6-2,1 s → 0,4 s,
  `/history` 3,9-4,1 s → 1,3 s, `/keystats` 5,5-5,9 s → 2,0 s.
* **Écran de chargement : sans effet mesurable.** 3 paires avec et sans : médianes
  7,97 s et 8,37 s, dans le bruit. Le garder.
* `/sparkline`, `/keystats`, `/analysts` ne servent pas l'accueil (positions,
  liste d'envies, recommandations) mais partent au démarrage ; les différer n'a
  rien montré de net dans le bruit (3 essais).
* Piste non faite, à décider avec Arthur : ouvrir la fenêtre sans attendre les cours
  et l'historique de Yahoo (0,5 à 2,4 s mesurés, jusqu'à 5 s sans réseau). C'est
  un choix délibéré : sans cette attente, la tuile du PEA se remplissait après
  l'ouverture.

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
* **Mac** (27/10/2026) : mêmes fonctions, autre cible. `apply_to_window` change
  l'icône du Dock tant que Pilote tourne (`NSApplication.setApplicationIconImage_`,
  sur le fil principal par `AppHelper.callAfter`), à partir d'un PNG 512 px
  (`png_for`, `Donnees/icones/pilote_<hex>.png`). Dans le même appel, sans bouton
  (demande d'Arthur, 4.4.30 ; le bouton « Recolorer Pilote.app » de la 4.4.29 est
  retiré, le réglage redevient `.win-seul`), `_sync_app_mac` pose l'icône sur le
  paquet par `NSWorkspace.setIcon_forFile_options_` (fichier `Icon\r` vide à sa
  racine, image dans ses attributs étendus : Finder, Launchpad, Dock au repos) et
  note dans `Donnees/icones/app_mac.txt` une empreinte (couleur, `CFBundleVersion`,
  emplacement du paquet, `_empreinte_mac`). Rien n'est réécrit si l'empreinte est
  la même et que `Icon\r` existe ; une mise à jour change la version (et remplace
  le paquet), l'icône revient donc au lancement suivant. La couleur seule ne
  suffisait pas (4.4.30) : une app déjà lancée une fois garde son `Icon\r`.
  Rien dans une copie en lecture seule (`mac_a_deplacer`). Sur plusieurs
  utilisateurs, l'app fermée garde la couleur du dernier qui l'a ouverte.
  Vu sur le Mac de GitHub (27/10/2026) : l'icône que macOS rend pour le paquet
  fermé (`iconForFile`) et le Finder sont à la nouvelle couleur.
* **Caches d'icônes de macOS (4.4.31)**. En 4.4.30, chez Arthur (macOS 26),
  « Apps » restait à l'orange du build et le Dock, app fermée, à la couleur
  d'avant. Le Dock et « Apps » gardent l'icône en cache. Essais du 27/10/2026
  (job `icone-mac`, macOS 26.6, Pilote dans Applications et gardé dans le Dock) :

  | Essai | Dock, app fermée | « Apps » déjà ouvert |
  |---|---|---|
  | rien de plus | orange | orange |
  | `killall Dock` seul | orange | — |
  | paquet relu (date, `lsregister -f`, `mdimport`) | orange | **à jour** |
  | réglage d'apparence resauvé (SkyLight, privé) | orange | — |
  | icône du paquet (`.icns`) remplacée, numéro de build changé | orange | à jour |
  | module de tuile du Dock (`NSDockTilePlugIn`) | orange | — |
  | caches de la session retirés, `killall iconservicesagent` puis `killall Dock` | **à jour** | — |
  | idem avec le cache système (`sudo`) | à jour | — |

  D'où `_rafraichir_mac`, après chaque icône posée : paquet relu, caches
  d'icônes de la session retirés, `iconservicesagent` puis le Dock relancés,
  icône de l'app ouverte reposée 3 s plus tard. Aucun mot de passe. Le Dock
  disparaît une seconde : seulement quand la couleur change ou après une mise à
  jour, jamais à un lancement ordinaire. Remplacer l'`.icns` du paquet
  invaliderait sa signature : écarté. Le job `icone-mac` rejoue le chemin réel
  (Apps ouvert avant, Enregistrer en vert, fermeture, second lancement, mise à
  jour simulée).
  Polices du « P » : Arial Bold du système, sinon Helvetica.
* Pillow est déclaré dans les `hiddenimports` de `build/pilote.spec` (import paresseux).

## Premier lancement lent après un démarrage du PC (4.4.21)

Juste après le démarrage de Windows, le cache disque est froid : la page peut
mettre assez longtemps à charger pour que pywebview lève « Main window failed
to load » (une fois dans le `crash.log` d'Arthur, le 25/09/2026). La fenêtre
s'ouvre ensuite normalement. Ce message est désormais écarté du journal comme
les autres erreurs bénignes (`install_crash_handler`, audit du 20/10/2026).
Pas de correction simple : l'écran de chargement s'affiche déjà avant la page.

WebView2 reçoit un dossier fixe (`%TEMP%\pilote_webview2`, `webview.start(storage_path=...)`),
en mode privé comme avant : sans lui, pywebview en créait un neuf dans `%TEMP%`
à chaque lancement sans jamais l'effacer (112 dossiers sur le PC d'Arthur).
`_menage_webview_temp()` efface en arrière-plan ces anciens dossiers (`tmp*`
contenant seulement `EBWebView`, inchangés depuis 2 jours).
