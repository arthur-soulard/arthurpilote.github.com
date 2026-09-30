# Accueil

Fiche détaillée tirée de `CLAUDE.md`, qui garde les règles générales (dont les cinq choses à ne jamais casser).

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
