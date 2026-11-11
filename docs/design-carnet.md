# Identité visuelle « Carnet »

Fiche détaillée tirée de `CLAUDE.md`, qui garde les règles générales (dont les six choses à ne jamais casser).

## Pilou, la mascotte (4.4.67, 11/11/2026)

Choisi avec Arthur : un **ourson** (« c'est affectueux »), à la couleur d'accent,
**lunettes d'aviateur sur les yeux** (verres teintés transparents : l'humeur se
voit au travers). Essayés puis écartés par Arthur : l'écharpe d'aviateur, les
lunettes relevées sur le front, « Pilou » écrit sur le ventre. Planche des
essais (trois styles, quatre humeurs) : artifact privé d'Arthur.

* **Dessin** : `pilouSvg(humeur)` dans index.html (à côté d'`applyDesign`), SVG
  fait main dont les couleurs sont des classes `pl-*` tirées de `--accent` par
  `color-mix()` : il suit l'accent et les deux thèmes sans être redessiné.
  Humeurs : `content`, `salut` (bras qui fait trois signes), `joyeux`, `pensif`,
  `endormi` (deux « z »). Les yeux clignent ; rien ne bouge avec
  `prefers-reduced-motion`.
* **Où il est** (choix d'Arthur) : à côté de « Bonjour » sur l'Accueil
  (`.pilou-accueil`, 1,05 em : n'agrandit pas la salutation), dans le titre de
  l'étape 1 des Premiers pas (`.pilou-pp`, même hauteur de ligne : l'étape tient
  toujours à 1366 × 720), et au-dessus du texte des écrans vides de premier
  usage (`pilouVide(humeur)`, 84 px) : Positions, Santé (suivi, objectifs),
  Patrimoine, Mes comptes (transactions), objectifs de Sports, achats
  programmés. Pas dans les petits vides (« — », lignes d'un tableau, jour sans séance).
* **Réglage** : Paramètres → Général → « Pilou, la mascotte », Afficher /
  Masquer, par utilisateur (`S.uiPrefs.pilou`, absent = visible). Masquer pose
  `html.sans-pilou`, qui cache tout `.pilou` : rien n'est redessiné.
* Pas de tuile d'accueil : ce n'est pas une donnée à suivre.

## Style « Verre », par défaut depuis la 4.4.56 (03/11/2026)

Demandé par Arthur : « un nouveau design comme Apple avec le Liquid Glass ».
Validé sur captures (données de Brice), Carnet à gauche, Verre à droite.

* **Deux styles, une feuille.** Le Carnet reste le style de base de toute la
  feuille de style. Verre s'y ajoute par le bloc « STYLE VERRE », en fin de la
  première feuille, actif seulement avec `<html class="verre">`. La classe est
  posée dans la balise même (pas de clignotement au démarrage), puis
  `applyDesign()` la retire si l'utilisateur a choisi le Carnet.
* **Choix par utilisateur** : `S.uiPrefs.design` (`"verre"` ou `"carnet"`, absent
  = Verre), Paramètres › Général › Style, appliqué sans relancer l'app
  (`setDesignPref`). La police des graphiques suit (`Chart.defaults.font.family`
  relu dans `--font`) et la courbe du PEA est redessinée.
* **Choix provisoire** : Arthur sonde son entourage pendant au moins une semaine
  (à partir du 03/11/2026) pour savoir quel style garder. Ensuite, soit on retire
  le bloc Verre (retour au Carnet), soit on retire le choix et le Carnet devient
  du code mort à nettoyer. Ne pas retirer le choix avant sa décision.
* **Le verre** : un fond fixe (`body::before`) à la seule couleur d'accent de
  l'utilisateur, mêlée au fond (`--fond-1..3`, 34/22/13 % en clair, 30/19/11 % en
  sombre, plus doux à sa demande) : un voile en diagonale sur toute la fenêtre et sept taches douces
  réparties partout, aucune qui domine. Choisi par Arthur en 4.4.57 après trois
  essais : la 4.4.56 avait trois sources (l'accent, un bleu, une pêche), jugées
  « bizarres » ; un fond presque uni a été refusé (« celui d'avant je préfère ») ;
  couleurs renforcées à sa demande, puis un peu adoucies. Le texte reste lisible sur les cartes. Des surfaces translucides (`--verre`, liseré clair
  `--verre-lum`), de grands arrondis (22 et 28 px), la barre latérale en panneau
  flottant (200 px, décalée de 10 px ; sur Mac, collée en haut), la police du
  système (Segoe UI Variable sous Windows, SF Pro sur Mac). Les couleurs gain /
  perte / alerte suivent celles d'Apple, foncées en clair pour le contraste.
* **Carte graphique modeste (Intel UHD)** : les cartes qui défilent n'ont PAS de
  `backdrop-filter`. Le fond étant déjà un dégradé flou, un fond translucide
  suffit et le rendu est le même. Le vrai flou est réservé aux surfaces fixes :
  barre de titre, barre latérale, fenêtres, notifications. Ne pas « améliorer »
  en floutant les cartes.
* **Écrans hors des pages, au même style (4.4.58)** : écran de lancement
  (`splash.py`, voir `docs/demarrage-et-icone.md`), fenêtre de mise à jour et sa
  progression (`#update-overlay`, `#update-modal` : verre, icône dans une pastille),
  écran de verrouillage (`.lock-ecran` : le même fond que l'app, opaque, pour ne rien
  laisser voir derrière ; cases du code en verre), fond flouté du rapport annuel. Les
  emojis de ces écrans et des titres de fenêtres (🚀, ⬇, 🔧, ✅, ❌, ⚠, 🔒, 📄, ⚙, 🏅,
  ▦, ⊳, 📚) sont devenus des icônes Phosphor, dans les deux styles. Le fond Verre est
  écrit une fois pour `body::before` et `.lock-ecran`.
* **Repères communs aux deux styles** (bloc « REPÈRES », juste avant) : espacements
  sur une grille de 4 et 8 px (`--space-*`), quatre durées (`--dur-*`), une courbe
  douce (`--ease`) et un léger rebond (`--ease-spring`) pour ce qui répond à un
  geste. Un onglet qui s'ouvre glisse de 4 px, une fenêtre arrive en 0,3 s. Tout
  s'arrête sous `prefers-reduced-motion`.

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
  seuls quand la courbe, la tuile de l'accueil et le module Patrimoine
  affichaient titres + espèces : l'écart était le solde espèces.
  Calculs revérifiés à la main sur les vraies données, tous justes ; seule la
  définition différait. La bonne est titres + espèces : c'est la valeur à laquelle
  se mesure le rendement (valeur − versements) et celle d'un PEA pour la banque.
  Le détail titres / espèces reste sous le chiffre.
* **Carte « Plus-value latente » (4.4.60, demande d'Arthur).** Sur le PEA, la
  première carte n'est plus « Total versé », déjà dans le bandeau du haut (où il
  a maintenant son propre gros chiffre, `#f-verse`), mais la plus-value latente :
  titres − prix de revient des lignes, en % de ce prix de revient, en vert ou
  rouge, « — » tant qu'un cours manque. La ligne « Prix de revient des lignes »
  de la carte Valeur est retirée (PEA et CTO), `ligneRevient` avec. Un CTO
  (pas de bandeau) garde « Investi net » dans cette première carte ; le latent y
  est déjà le mode « Lignes actuelles » de la carte Rendement.
  En 4.4.61, à la demande d'Arthur, la carte Valeur repasse en premier et la
  plus-value latente (ou « Investi net » d'un CTO) vient en deuxième.
* **Historique, 4.4.6 à 4.4.59 : « Prix de revient des lignes », pas « Investi ».** La 3e ligne de la
  carte Valeur (PEA et CTO, `ligneRevient`) était le coût des lignes détenues, frais
  compris (somme des `computePos().inv`). Appelée « Investi » jusqu'en 4.4.5, elle
  a été lue comme l'argent versé, alors que l'écart avec le « Total déposé » est le
  réalisé des lignes vendues et les dividendes, réinvestis (vérifié au centime le 12/10/2026).
  Le latent (titres − prix de revient) suit entre parenthèses, absent tant qu'un
  cours manque. Montant et latent sont insécables : à 147 px (fenêtre de 1 280 px)
  la ligne passe sur trois lignes propres. La colonne « Investi » des Positions
  garde son nom : ligne par ligne, rien ne prête à confusion.
* **PRU et cours au millième (4.4.7)**, demandés par Arthur : `eur3`
  (3 décimales) pour le PRU et le cours dans les Positions (PEA et CTO), le
  cours de chaque ordre dans Transactions et l'aperçu d'import, l'onglet PEA du
  Prêt et le bilan annuel. Les ETF du PEA cotent au millième (7,297 €) :
  6,9657 € s'affichait 6,97 €, et un ordre à 6,789 € se lisait 6,79 €, ce qui
  cachait une erreur de saisie de 0,003 €. Les montants restent au centime (`eur`).
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
