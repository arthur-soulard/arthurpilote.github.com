# Identité visuelle « Carnet »

Fiche détaillée tirée de `CLAUDE.md`, qui garde les règles générales (dont les cinq choses à ne jamais casser).

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
* **Chiffres des cinq cartes du PEA (`.mc-val`), 4.3.16** : 30 px au plus, sinon
  17,5 % de la largeur de la carte (`container-type: inline-size` sur `.mc`, unité
  `cqw`). En fenêtre de 1 280 px (taille par défaut), 30 px coupaient tout montant
  à 5 chiffres : « 10 700,0… » (156 px de texte pour 147 disponibles). Mesuré :
  25,7 px à 1 280 px, 30 px à 960 px (les cartes passent sur deux lignes) et à
  1 600 px, rien de coupé. Un `font-size: 30px` précède la règle en `cqw`, en
  repli pour un moteur qui ne la connaîtrait pas.
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
