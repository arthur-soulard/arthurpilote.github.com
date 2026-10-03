# Démarrage et icône de la fenêtre

Fiche détaillée tirée de `CLAUDE.md`, qui garde les règles générales (dont les cinq choses à ne jamais casser).

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
