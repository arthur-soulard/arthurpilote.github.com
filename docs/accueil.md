# Accueil

Fiche détaillée tirée de `CLAUDE.md`, qui garde les règles générales (dont les six choses à ne jamais casser).

## Page d'accueil (`pane-home`)

Ouverte au démarrage. `homeGreeting()` renvoie « Bonjour » avant 18 h, « Bonsoir » après ;
`homeDisplayName()` prend le nom de l'utilisateur actif (sinon `S.prenom`).

Mise en page alignée à gauche : grande salutation en serif (`clamp(40px, 5vw, 60px)`),
écrite par `homeRenderGreeting()` avec le prénom dans un `<em>` (italique, couleur
d'accent) ; `renderHomeUsers()` la rappelle quand la liste des utilisateurs arrive.
Puis la date en italique. **À droite de la salutation** (4.3.19), l'un sous l'autre :
les utilisateurs (`#home-users`, cliquables pour basculer + « Nouvel utilisateur »),
les boutons Modifier les tuiles / Paramètres / Téléverser vers clé USB, puis
« Suggérer une amélioration » et l'état de la clé (`#home-usb-state`). Dessous, directement les tuiles,
chacune avec l'icône de son module (`DASH_ICONS`). Sous 1150 px de large, tout s'empile.

Pourquoi (03/10/2026) : en plein écran sur l'écran d'Arthur (1366 × 768, page de
1366 × 720), la 2e rangée de tuiles était coupée et il fallait défiler, alors que la
droite de la salutation restait vide. La salutation occupait toute une bande
(209 px), suivie d'une ligne « Tableau de bord » + crayon (73 px avec ses marges).
Désormais : bandeau de 109 px, ligne « Tableau de bord » supprimée (le crayon a
rejoint les boutons), tuiles un peu moins hautes (marge intérieure 0,9 rem au lieu
de 1,1). Mesuré avec ses vraies tuiles (PEA, Sport, Objectif, Poids, Dépenses) : la
dernière finit à 704 px sur 720. La colonne de la salutation est en `auto` : en
fenêtre plus étroite, ce sont les boutons qui passent à la ligne, pas « Bonjour Arthur ».

`svPushToUsb()` sauve et restaure le libellé du bouton USB en `innerHTML`, pas en
`textContent` : sinon l'icône disparaît après la première copie.

**Suggérer une amélioration** (12/10/2026, demande d'Arthur) : bouton-texte à
l'accent, sur la ligne de l'état de la clé (`.home-row3`), pas avec les cinq
boutons. La ligne des boutons est pleine à 1366 px : un 6e y passait à la ligne
et la dernière tuile finissait à 740 px pour 720 (704 sans lui, 706 avec le
bouton-texte). Il ouvre `ov-suggestion` : l'adresse d'Arthur
(`SUGGESTION_ADRESSE`, arthur.economie@gmail.com) avec un bouton Copier,
« Ouvrir ma messagerie » (lien `mailto:`) et « Écrire avec Gmail » (page de
rédaction de Gmail dans le navigateur), objet « Suggestion pour Pilote » et
version de Pilote déjà remplis, par `Api.open_url`. Rien ne part de Pilote :
c'est la messagerie de l'utilisateur qui envoie. Le bouton Gmail existe parce
qu'un `mailto:` sans messagerie installée n'ouvre rien d'utile (chez Arthur, le
`mailto:` est confié à Brave). Place validée par Arthur : « garde-le comme ça ».

**Exporter et Importer retirés de l'accueil** (4.4.12, demande d'Arthur) : ils
faisaient doublon avec Paramètres → Données & application (`doExport`,
`doImportDialog`), où ils restent, comme les raccourcis Ctrl+E / Ctrl+I (⌘ sur
Mac) et « Importer un fichier » des Premiers pas. Gestes rares, et Importer
remplace toutes les données : pas à un clic de l'accueil.

Depuis la 4.1.4, `homeRender()` ne fait plus que la salutation et la date : **les tuiles
sont déléguées à `dashRender()`** (voir « Accueil : tableau de bord modulaire »). Il n'y
a plus de carte codée en dur.

`homeRender()` est rappelée par `renderMetrics()`, `spBootstrap()`, `saRenderAll()`,
`paRenderAll()`, la fin de `boot()` et à chaque `goTab("home")` — ce dernier
rafraîchit aussi l'état de la clé USB (`svRenderUsbState()`) et sort du mode
édition des tuiles quand on quitte l'accueil.

**Premiers pas** (`_showWelcomeIfFirstRun()`, 4.3.37) : un assistant en trois étapes,
demandé par Arthur le 11/10/2026. 1) ce qu'est Pilote (avec, si besoin, de quel
espace il s'agit et la récupération d'une installation **extérieure**, voir
`scan_orphan_data`) ; 2) les modules à cocher, **aucun coché d'office** (au moins un
pour continuer) ; 3) le premier geste de chaque module choisi, en cartes cliquables
qui mènent à leur onglet. `NAV_MODULES` porte pour chaque section sa description, ce
premier geste, l'onglet et les tuiles de l'accueil à allumer : **une nouvelle section
de `NAV_SECTIONS` y ajoute son entrée** (sinon sa carte reste sans texte).

* En fin d'assistant : les modules non cochés sont masqués (tous leurs onglets dans
  `S.uiPrefs.hiddenSidebar`, le mécanisme de l'œil), `S.uiPrefs.dash` ne garde que
  les tuiles des modules choisis, `S.uiPrefs.premiersPas = true` et
  `nouveautesVues` = la version installée (un nouvel utilisateur n'a pas de
  « nouveautés » à lire).
* S'affiche si le PEA est vide **et** `premiersPas` absent : une seule fois par
  utilisateur. Jusqu'à la 4.3.36, l'écran de bienvenue revenait à chaque lancement
  tant que le PEA restait vide, même pour qui ne s'en sert pas. Un utilisateur déjà
  installé (PEA rempli) ne le voit jamais. Importer ou récupérer un fichier ne pose
  pas le drapeau : si l'import échoue, l'assistant revient.
* Tient sans défiler à 1366 × 720 dans les deux cas les plus chargés, mesurés :
  étape 1 avec l'espace d'un 2e utilisateur **et** une installation extérieure
  (644 px pour 646), étape 3 avec les huit modules (620 px, deux colonnes).
* Paramètres → Modules reprend les mêmes cartes (`_modCarteHtml`) : voir
  `docs/parametres.md`. Une tuile dont l'onglet appartient à un module décoché ne
  s'affiche plus (`dashRender`). Un accueil dont les tuiles actives sont toutes vides
  le dit (« Tes tuiles apparaîtront ici… ») au lieu de « Aucune tuile active ».

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
  la main sur les vraies données (… €, … %).
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

Bouton **✎ Modifier les tuiles** (`#dash-edit-btn`, avec les boutons à droite de la
salutation depuis la 4.3.19) →
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

**Sauf les modules masqués** (Paramètres → Modules, 12/10/2026, demande
d'Arthur : « on gagne du temps à l'ouverture et au chargement des données »).
`MODULES_A_CHARGER` (juste avant `boot()`) associe chaque chargement à sa
section de `NAV_SECTIONS` ; `boot()` ne lance que ceux des sections affichées
(`_modulesVisibles`) et écrit les autres au journal (« modules masques, non
charges »). Un module masqué n'a donc ni fichier lu, ni cours demandés (Prêt,
CTO), ni relevé de la boîte (Actus). Le PEA reste toujours lu
(`pea_data.json` porte les réglages de tous les modules) ; masqué, il ne
demande pas son historique au lancement. Cocher un module le charge aussitôt
(`cfgModule` → `_chargerModule`), comme au lancement (ligne du CTO dans le
Patrimoine, cours des CTO). Conséquences voulues :

* les tuiles d'un module masqué ne s'affichaient déjà plus ; « Toute ma
  bourse » sans le module CTO dit « le PEA seul » (sans « aucun CTO » : on ne
  les a pas lus) et n'attend plus `_ctoBootstrapped` (sinon squelette à vie) ;
* `dashSaveConfig` garde les tuiles `cto:<id>` d'un CTO non lu : absentes de
  `DASH_WIDGETS`, `dashConfig` les filtrait et la première tuile modifiée les
  effaçait des réglages ;
* la ligne d'un CTO ou du prêt dans le Patrimoine ne se calcule plus seule
  quand son module est masqué : elle reprend son dernier relevé.

Vérifié au banc d'essai sur une copie de ses données : Santé puis CTO masqués,
`load_sante` et `load_cto` absents au relancement ; PEA masqué, aucun
`/history` ; chaque module recoché se charge (section du CTO, tuile Poids).

De même, `svRenderUsbState()` publie désormais `window._dashUsb` — la tuile
« Sauvegarde USB » lisait cette variable que personne n'écrivait.

### 25 tuiles de plus (12/10/2026)

Choisies par Arthur parmi une quarantaine de propositions. Toutes arrivent
éteintes, comme toute tuile nouvelle. Chacune relit le calcul de son module,
jamais un second calcul :

| Module | Tuiles (id) | Source du chiffre |
|---|---|---|
| PEA | `pea-div`, `pea-div-next`, `pea-plafond`, `pea-versement`, `pea-frais`, `pea-5ans`, `pea-wish` | `dashDivRecus` (mêmes règles que `renderDividends`), `S.divFuture`, `peaTotalVerse`, `depPrevus`, frais des ordres datés d'aujourd'hui ou avant, `peaDateFiscale`, `m1` de `/cours` |
| Bourse | `bourse-totale`, `marches` | `_peaPv` + `ctoResume` de chaque CTO ; indices de `/cours` |
| Actus | `actus` | `AC.mails` non lus ; `acRenderBadge` redessine l'accueil |
| Patrimoine | `pa-repartition`, `pa-an`, `pa-objectif` | `_paNet.detail` par type (couleurs de `PA_TYPES`), `_paSerie`, `S.uiPrefs.dashObjectif` |
| Sports | `sport-semaine`, `sport-annee`, `sport-derniere`, `sport-km`, `sport-ajout` | `spMoyenneHebdo` (sortie de `spRenderStatsKpis`), `spTotals`, `spTrackStart` |
| Santé | `sante-rappel`, `sante-ajout` | `saMesures`, `saLast` |
| Prêt | `pret-mensualite`, `pret-gains` | configuration du prêt, `prOverview().benefice_net` |
| Comptes | `fin-solde`, `fin-revenu` | `finComputeMonthTotals` |
| Pense-bête | `pense-bete` | `S.uiPrefs.penseBete` |

Choix d'Arthur et pièges :

* **Cap des 5 ans** : date d'ouverture saisie dans les réglages du PEA
  (`S.ouverture`). La tuile s'efface une fois l'avantage fiscal atteint.
* **Rappel de pesée** : affiché tant que le mois n'a aucune pesée, comme le
  relevé de patrimoine (choix d'Arthur, plutôt que « 7 jours sans pesée »).
  Rien tant que le module Santé n'a jamais servi.
* **Prochaine mensualité** : échéancier théorique tiré de la configuration
  (1re mensualité, durée, mensualité). Avant la 1re, « Première mensualité »
  avec le délai. Les remboursements restent saisis à la main.
* **Cumul de l'année (sport)** : comparé à l'an dernier *à la même date*, et
  jamais à une période d'avant le suivi. Les barres commencent au mois de la
  première séance : un mois d'avant n'était pas « zéro sport ».
* **Marchés du jour** : CAC 40 `^FCHI`, S&P 500 `^GSPC`, Nasdaq `^IXIC` (le
  Nasdaq demandé par Arthur en plus) et MSCI World `^990100-USD-STRD`, l'indice
  lui-même (en dollars), pas un ETF. Ils ne sont demandés à Yahoo que si la
  tuile est affichée (`dashMarchesTickers`, appelée par `fetchLocalCours`), et
  tout de suite quand on l'ajoute (`dashMarchesCharger`). Une séance qui n'est
  pas celle du jour porte son jour (« ven. ») : New York ouvre à 15 h 30.
  Les quatre lignes partagent une seule grille (`.dash-mkt` en
  `display: contents`) : avec une grille par ligne, les chiffres ne
  s'alignaient pas. Tuile étroite (moins de 215 px utiles, fenêtre de 1024 px
  du test Mac) : les points d'indice disparaissent (requête de conteneur sur
  `.dash-mkts-c`), sinon « S&P 5… » et « MSCI … » étaient coupés.
* **Plafond du PEA** : libellés courts sous la barre (« 3,8 % », « reste
  144 250 € ») : les longs passaient sur deux lignes à 1024 px.
* **Objectif de patrimoine** : montant et date facultative, saisis depuis la
  tuile (`ov-dash-objectif`). Avec une date : ce qu'il reste ÷ les mois
  restants, arrondi à l'euro supérieur.
* **Pense-bête** (une seule tuile, choix d'Arthur) : les trois notes les plus
  proches (dépassées en tête, en rouge), « + N autres », une coche pour
  « c'est fait ». La fenêtre `ov-dash-notes` sert à écrire, modifier,
  supprimer et remettre à faire. Les notes vivent dans `S.uiPrefs`, donc dans
  `pea_data.json` et ses sauvegardes, sans module Python à part.
  **Écritures en file** (`dashSauverPrefs`, `_dashPrefsChaine`) : cinq notes
  ajoutées coup sur coup partaient en même temps et la 4e écrasait la 5e (vu au
  banc d'essai). Jamais d'écriture avant la lecture réussie du PEA
  (`_hydrationDone`).

Mécanique ajoutée à `dashCardHtml` / `dashRender` : `val: null` = pas de grand
chiffre (pense-bête, marchés) ; `vizCls: "dash-viz-haut"` = la liste juste
sous le titre au lieu du bas de la tuile ; `ready()` sur un widget remplace
`dashModuleReady` (squelette des marchés pendant leur chargement). La fenêtre
« Ajouter une tuile » range les tuiles sous un titre par module, dans l'ordre
de `DASH_WIDGETS`. `dashDeMois()` écrit « d'octobre », « de novembre » :
la tuile des dépenses disait « Dépenses de octobre ».

**Hauteur des rangées à 1366 × 720** (4.4.13, demande d'Arthur) : une rangée
prend la hauteur de sa tuile la plus haute, et deux rangées doivent tenir sous
le bandeau (de 250 à 720 px : 228 px chacune au plus). Avec ses tuiles du
12/10 (Performance, Marchés, Dépenses, Sport ; Objectif, Poids, Pense-bête), la
2e rangée faisait 252 px et finissait à 733 px : c'était « Poids », dont
« Comparer avec » prenait une ligne entière au-dessus de la courbe. Il est
monté dans l'en-tête de la tuile, à droite de « Poids » (`coin` du rendu,
placé par `dashCardHtml` dans `.dash-coin`), sous la forme « vs » + liste (le
mot « Comparer avec » reste en infobulle et en `aria-label`). Rangée de
222 px, dernière tuile à 703 px. La liste est bornée à 120 px pour tenir dans
une tuile de 240 px (largeur minimale de la grille). Avant d'ajouter une tuile
haute, la mesurer à 1366 × 720 avec ses vraies tuiles.

### Tuiles des CTO (4.4.0)

Une tuile par CTO (`cto:<id>`), ajoutée à `DASH_WIDGETS` à la lecture de
`cto.json` (`ctoSyncWidgets`), éteinte tant qu'on ne l'ajoute pas : valeur des
titres et plus-value depuis le début, lues dans `ctoResume` (le même calcul que
la vue d'ensemble du CTO). Son onglet `cto-dash@<id>` ouvre ce CTO-là.
`dashRender()` ne fait rien pendant qu'un CTO est dans `S` : les tuiles du PEA
le liraient (voir `docs/modules/cto.md`).

**Performance d'un CTO** (`cto-perf:<id>`, demandée par Arthur le 12/10/2026,
« comme pour le PEA ») : mêmes pastilles Jour · 1S · 1M · YTD · Max, période
retenue par CTO (`S.uiPrefs.dashCtoRange`). Les deux tuiles passent par
`dashPerfTuile` ; aucun calcul n'est recopié :

* `dashAvecCto(id, fn)` met le CTO dans `S` (avec `_compteActif` et ses
  versements déduits des ordres, `ctoDepotsDeduits`) le temps d'un calcul
  **synchrone**, puis remet le PEA. `dashPeaDay`, `buildTwrSeries`,
  `computePnl` et `buildDepositSeries` tournent ainsi tels quels sur le CTO.
  Rien d'asynchrone ni d'écriture dans `fn` : JavaScript ne s'interrompt pas,
  aucun autre code ne voit le CTO dans `S`.
* Max = `ctoResume` (la carte « Plus-value ») ; 1S, 1M, YTD = la série du CTO,
  tirée d'un historique demandé une fois par session (`_dashCtoHist`), à part
  de `_perfHistory` qui est celui du compte affiché ; hors ligne, la copie
  locale de la courbe du CTO.
* Vérifié sur une copie du CTO TR d'Arthur (135 opérations) : 1S … €
  (… %), 1M … €, YTD … €, Max … € (… %), au centime près
  ce qu'affichent sa courbe et sa carte. Tuile du PEA identique avant et après
  `dashPerfTuile` sur les cinq périodes.
* Module CTO masqué : ses tuiles `cto:` et `cto-perf:` sont gardées dans la
  configuration (`dashSaveConfig`) et reviennent avec lui.

**Performance de toute ma bourse** (`bourse-perf`, demandée par Arthur le
12/10/2026) : le PEA et chaque CTO qui a des lignes, additionnés période par
période, mêmes pastilles (`S.uiPrefs.dashBourseRange`). `dashBourseComptes`
donne, pour chaque compte, ce que sa propre tuile calcule ; aucun chiffre
n'est recalculé à part :

* gain de la période = somme des gains de chaque compte ;
* % = somme des gains ÷ somme des capitaux engagés de chaque compte, le
  dénominateur de son propre % : `computePnl` renvoie pour cela `engage`
  (versements nets en historique complet, valeur de départ + flux pondérés
  sur une plage), `dashPeaDay` renvoie `avant` (valeur à la clôture
  précédente), Max prend les versements (PEA) et l'investi net (CTO) ;
* Max = `dashBourseMax`, que la tuile « Toute ma bourse » lit aussi (un seul
  calcul de la plus-value totale) ;
* mini-courbe : la plus-value de chaque compte (`dashPvPoints`) additionnée
  date par date ; un compte sans cotation un jour garde sa dernière valeur.
* Vérifié sur une copie des données d'Arthur : 1S … € (PEA) − … €
  (CTO TR) = … € (… %, entre … % et … %) ; 1M … € ;
  YTD … € ; Max … € (… %), comme « Toute ma bourse ».
* Titre court sur la tuile (« Performance de ma bourse ») : le nom complet
  passait sur deux lignes à 1024 px.
