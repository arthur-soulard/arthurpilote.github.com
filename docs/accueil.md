# Accueil

Fiche détaillée tirée de `CLAUDE.md`, qui garde les règles générales (dont les six choses à ne jamais casser).

## Page d'accueil (`pane-home`)

Ouverte au démarrage. `homeGreeting()` renvoie « Bonjour » avant 18 h, « Bonsoir » après ;
`homeDisplayName()` prend le nom de l'utilisateur actif (sinon `S.prenom`).
Un nom donné d'office (« Moi » au premier lancement, « Mon PEA » ou « default »
d'avant la 4.1.2) ne compte pas : « Bonsoir » seul plutôt que « Bonsoir Moi »
(4.4.16, demande d'Arthur). Même règle pour « Bienvenue sur Pilote » des
premiers pas et le titre du code PIN (« cet utilisateur »).

Mise en page alignée à gauche : grande salutation en serif (`clamp(40px, 5vw, 60px)`),
écrite par `homeRenderGreeting()` avec le prénom dans un `<em>` (italique, couleur
d'accent) ; `renderHomeUsers()` la rappelle quand la liste des utilisateurs arrive.
Pilou (la mascotte, 4.4.67, `docs/design-carnet.md`) salue juste **après**
le prénom, une fois et demie la taille du texte (90 px à 1366 px de large,
marges négatives : le bandeau reste à 108 px) (`#home-pilou`, dessiné une fois par
`homeRenderGreeting()` ; avant « Bonjour » jusqu'au 12/11/2026). C'est lui qui
pose la question : sa bulle de parole **« Une idée, un problème ? »** (voir plus
bas). Puis la date en italique. **À droite de la salutation** (4.3.19), l'un sous l'autre :
les utilisateurs (`#home-users`, cliquables pour basculer + « Nouvel utilisateur »),
les boutons Modifier les tuiles / Paramètres / Téléverser vers clé USB (« Mettre
en place une sauvegarde » tant que rien n'est en place : `docs/sauvegarde-usb.md`), puis
l'état de la clé (`#home-usb-state`). Dessous, directement les tuiles,
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

**Suggérer une amélioration** (12/10/2026, demande d'Arthur) : d'abord un
bouton-texte à l'accent sur la ligne de l'état de la clé (`.home-row3`), pas
avec les cinq boutons d'alors : un 6e passait à la ligne et la dernière tuile
finissait à 740 px pour 720. **Depuis le 13/10/2026** (Arthur : « il faudrait
le mettre plus en avant… à côté du prénom, en mode il a une idée ? ») : une
bulle de pensée **« Une idée ? »** à droite du prénom (`.home-idee`, deux
petits ronds la relient au nom), qui apparaît d'un petit rebond au lancement,
une seule fois (`.vue` après l'animation ; pas d'animation si le système
réduit les mouvements). Elle est hors de `#home-greet` (un `<span>` réécrit à
chaque rendu), sinon elle rebondirait à chaque actualisation des cours. La
place vient d'Exporter et Importer, retirés en 4.4.12 : à 1366 × 720 le
bandeau reste à 109 px et la dernière tuile à 680 px avec ses vraies tuiles.
Mesuré : jusqu'à un prénom de dix lettres (« Bonsoir Christophe ») rien ne
bouge ; au-delà (« Maximilien »), les boutons passent sur deux lignes
(bandeau de 145 px), comme dans une fenêtre étroite.

**Depuis le 12/11/2026** (Arthur : « c'est Pilou qui demande "une idée, un
problème ?" ») : Pilou passe après le prénom et la bulle devient une bulle de
parole qui sort de lui (pointe à gauche, coin bas gauche moins arrondi), texte
**« Une idée, / un problème ? »** sur deux lignes, sans icône. Sur une seule
ligne, « Bonsoir Arthur » faisait passer les boutons de droite à la ligne à
1366 × 720 (mesuré : bandeau de 136 px au lieu de 103) ; sur deux, la bulle et
sa marge prennent 128 px, contre 135 pour l'ancienne « Une idée ? ». Pilou
masqué (Paramètres → Général) : retour à la bulle de pensée et à ses deux petits
ronds (`html.sans-pilou .home-idee`). Au clic, la fenêtre s'ouvre d'abord sur
**deux choix** (`#sug-choix`) : « J'ai une idée » ou « Quelque chose ne marche
pas », qui mènent aux deux écrans d'avant (`homeSuggestion(false|true)`).
`homeSuggestion()` sans argument montre ce choix ; « Signaler un problème » des
Paramètres appelle toujours `homeSuggestion(true)` et va droit au but.

Elle ouvre `ov-suggestion` : l'adresse d'Arthur
(`SUGGESTION_ADRESSE`, pilote.appli+idee@gmail.com depuis le 09/11/2026 :
la boîte de Pilote, plus l'adresse perso d'Arthur) avec un bouton Copier,
« Ouvrir ma messagerie » (lien `mailto:`) et « Écrire avec Gmail » (page de
rédaction de Gmail dans le navigateur), objet « Suggestion pour Pilote » et
version de Pilote déjà remplis, par `Api.open_url`. Rien ne part de Pilote :
c'est la messagerie de l'utilisateur qui envoie. Le bouton Gmail existe parce
qu'un `mailto:` sans messagerie installée n'ouvre rien d'utile (chez Arthur, le
`mailto:` est confié à Brave).

**Exporter et Importer retirés de l'accueil** (4.4.12, demande d'Arthur) : ils
faisaient doublon avec Paramètres → Données & application (`doExport`,
`doImportDialog`), où ils restent, comme les raccourcis Ctrl+E / Ctrl+I (⌘ sur
Mac). Gestes rares, et Importer remplace toutes les données : pas à un clic de
l'accueil. « Importer un fichier » a aussi quitté l'étape 1 des Premiers pas
(27/10/2026) : un nouvel utilisateur le prenait pour l'import d'un relevé.

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
pour continuer) ; 3) la visite avec Pilou, proposée (voir « Pilou guide » plus bas).
Jusqu'au 12/11/2026, l'étape 3 montrait le premier geste de chaque module en cartes
cliquables, plus un encart « Explorer avec des données d'exemple » : Arthur a gardé
la visite, les premiers gestes sont devenus les astuces de premier passage.
`NAV_MODULES` porte pour chaque section sa description, ce premier geste (`pas`,
`besoin`), l'onglet et les tuiles de l'accueil à allumer : **une nouvelle section
de `NAV_SECTIONS` y ajoute son entrée** (sinon sa carte reste sans texte), **ainsi que
ses arrêts dans `PILOU_VISITE` et sa réaction dans `PILOU_REACTIONS`**.

**Pilou guide** (12/11/2026, décidé avec Arthur, bloc « PILOU GUIDE » d'index.html,
juste après le patch de `goTab` de Garmin) :

* **Pilou parle dans les Premiers pas.** Chaque étape est une bulle (`.pp-pl`,
  `.pp-bulle`), sa phrase s'écrit lettre par lettre (`pilouEcrit`, 16 ms par lettre ;
  un clic l'affiche d'un coup ; rien d'animé si le système réduit les mouvements).
  Étape 1 : il se présente et demande le prénom dans sa bulle (« Moi » seulement),
  répond « Enchanté, X ! » dès la frappe ; les quatre points d'avant sont devenus des
  pastilles (détail en infobulle), le chemin des données reste dessous. Étape 2 : il
  réagit au module qu'on coche (`PILOU_REACTIONS`). Étape 3 : « tu veux que je te
  fasse visiter ? », boutons « Visiter avec Pilou » et « Non merci, je commence »
  (accueil). Pilou masqué : la bulle reste, sans pointe ni ourson.
* **Visite avec Pilou** (`pilouVisiter(modules)`) : bascule sur l'utilisateur Exemple
  (`explorerExemple`, qui recharge la page), puis `pilouDemarrage` reprend l'étape
  rangée dans `sessionStorage` (« pilote.visite » : modules et numéro d'arrêt). Arrêts :
  l'accueil, puis **plusieurs écrans par module choisi** (`PILOU_VISITE`, choix
  d'Arthur : « peu de personnes cocheront tout »), puis la fin (« Revenir à mon
  profil » ou « Rester sur l'exemple »). Chaque arrêt ouvre l'onglet, entoure la
  carte dont Pilou parle (`.vis-cible`, la carte nommée ou la première visible) et
  montre une carte flottante en bas à droite (`.pl-flot`) : « n sur N », retour,
  Passer, Suivant ; Échap = Passer. Un arrêt CTO ou Crypto sans compte est sauté.
  Pas de `scrollIntoView` : il faisait glisser toute la fenêtre, barre de titre
  comprise ; seule la zone qui défile bouge. Plus de petits points de progression :
  à 17 arrêts, ils repoussaient Suivant sur une deuxième ligne. La carte est en
  position fixe : elle reste quand on fait défiler la page. Son apparition ne joue
  que sur la position, pas sur l'opacité : une animation bloquée (fenêtre en
  arrière-plan) l'avait laissée invisible. La fin de visite s'affiche **au centre**,
  sur un voile (`.pl-centre`, `.pl-voile`, demande d'Arthur).
* **Astuces de premier passage** (`pilouApresNavigation`, patch de `goTab`, le
  dernier de la chaîne) : la première fois qu'un utilisateur ouvre un module, Pilou
  donne son premier geste (`NAV_MODULES.pas`, et `besoin`), une fois par module
  (`S.uiPrefs.astuces`). Seulement pour qui a fait les nouveaux Premiers pas
  (`terminer()` crée `astuces = {}`) : les utilisateurs d'avant n'ont pas la clé,
  rien ne s'affiche. Jamais sur l'exemple ni pendant la visite.
* **Utilisateurs d'avant** : la visite leur est proposée **une fois** sur l'accueil
  après la mise à jour (`S.uiPrefs.visiteProposee`), puis Paramètres → Général,
  à côté du réglage de Pilou, « Revoir la visite » (`pilouVisiterMesModules` : les
  modules affichés).
* Mesuré à 1366 × 720 : l'étape 1 la plus chargée (prénom, 2e utilisateur, ancienne
  installation, chemin) fait 638 px pour 646 ; l'étape 2 défile dans sa fenêtre
  (760 px), comme avant mais 60 px de plus avec la bulle.

* En fin d'assistant : les modules non cochés sont masqués (tous leurs onglets dans
  `S.uiPrefs.hiddenSidebar`, le mécanisme de l'œil), `S.uiPrefs.dash` ne garde que
  les tuiles des modules choisis, `S.uiPrefs.premiersPas = true` et
  `nouveautesVues` = la version installée (un nouvel utilisateur n'a pas de
  « nouveautés » à lire).
* **Prénom et prérequis** (27/10/2026, Pilote prêt pour d'autres utilisateurs) : si
  l'utilisateur s'appelle encore « Moi » (installation neuve), l'étape 1 demande son
  prénom, enregistré par `Api.update_user` en fin d'assistant (vide : il reste « Moi »).
  Ce qu'il faut avoir pour un module (`besoin` dans `NAV_MODULES` : Gmail en deux
  étapes pour Actus, compte Apple pour l'Agenda) est dit par l'astuce de premier
  passage depuis le 12/11/2026 (sous les cartes de l'étape 3 avant).
* S'affiche si le PEA est vide **et** `premiersPas` absent : une seule fois par
  utilisateur. Jusqu'à la 4.3.36, l'écran de bienvenue revenait à chaque lancement
  tant que le PEA restait vide, même pour qui ne s'en sert pas. Un utilisateur déjà
  installé (PEA rempli) ne le voit jamais. Importer ou récupérer un fichier ne pose
  pas le drapeau : si l'import échoue, l'assistant revient.
* **Chemin des données en clair** (4.4.20, 19/10/2026, demande d'Arthur : un nouvel
  utilisateur ne veut pas que ses données aillent « n'importe où ») : le point
  « Tout reste sur ce PC » donne le chemin du dossier de l'utilisateur
  (`_cheminDonnees()` → `Api.data_folder_path`, le dossier qu'ouvre
  `openDataFolder()`), avec « Ouvrir ». Même ligne dans Paramètres → Données
  (`docs/parametres.md`). Hors de l'app (pas de pont), l'ancienne phrase revient.
* Tient sans défiler à 1366 × 720 dans les deux cas les plus chargés, mesurés :
  étape 1 avec l'espace d'un 2e utilisateur **et** une installation extérieure
  (644 px pour 646 ; 643 px avec le chemin, qui a fait passer la phrase sur une
  ligne et le chemin en ligne fine, sans boîte), étape 3 avec les huit modules
  (620 px, deux colonnes).
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
  la main sur des données réelles, au centime.
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
| Bourse | `bourse-totale`, `marches` | `_peaPv` + `ctoResume` de chaque CTO (sans le portefeuille crypto) ; indices de `/cours` |
| Crypto | `crypto:<id>`, `crypto-pv:<id>`, `crypto-courbe:<id>` | `ctoResume` du portefeuille crypto, `dashPeaDay` et `dashCtoSerie` par `dashAvecCto` (`docs/modules/crypto.md`) |
| Actus | `actus` | `AC.mails` non lus ; `acRenderBadge` redessine l'accueil |
| Patrimoine | `pa-repartition`, `pa-an`, `pa-objectif` | `_paNet.detail` par type (couleurs de `PA_TYPES`), `_paSerie`, `S.uiPrefs.dashObjectif` |
| Sports | `sport-semaine`, `sport-annee`, `sport-derniere`, `sport-km`, `sport-ajout` | `spMoyenneHebdo` (sortie de `spRenderStatsKpis`), `spTotals`, `spTrackStart` |
| Santé | `sante-rappel`, `sante-ajout` | `saMesures`, `saLast` |
| Prêt | `pret-mensualite`, `pret-gains` | configuration du prêt, `prOverview().benefice_net` |
| Comptes | `fin-solde`, `fin-revenu` | `finComputeMonthTotals` |
| Comptes | `fin-releve` (4.4.70) | opérations importées à classer (`finAClasser`), date du dernier import ; boutons « Importer un relevé » (`dashImporterReleve`) et « Classer » (`finVoirAClasser`) : `docs/modules/comptes.md` |
| Pense-bête | `pense-bete` | `S.uiPrefs.penseBete` |
| Bilan | `bilan` (01/11/2026) | total de la bourse sur la semaine passée (`_bilanCache`, calculé 15 s après le lancement si la tuile est affichée), bouton « Voir le bilan » |

### Bilan de la semaine (01/11/2026)

Demande d'Arthur : un bilan de la semaine **passée** (du lundi au dimanche), en
page et pas en texte, avec la performance de la semaine du PEA, de chaque CTO
et de la Crypto, ce qui a le plus monté et baissé, le sport, les dépenses, la
santé et la semaine à venir. Direction artistique validée sur capture
(« parfait pour la DA ») : identité Carnet, page claire imprimable.

* `bilanOuvrir(lundi)` : fenêtre `#ov-bilan` (barre : semaine ‹ ›, « Chaque
  dimanche à HH:MM », Enregistrer en PDF, Fermer), page dans une iframe
  (`bilanPageHtml`), impression par `_rapportImprimer`, commun avec le rapport
  annuel (Mac : ouverte dans le navigateur). La semaine par défaut est celle qui
  s'achève le dimanche, la précédente les autres jours (`bilanLundiDefaut`).
* `bilanCalculer(lundi)` : chaque compte = `computePnl` sur sa courbe, de la
  clôture d'avant le lundi à la dernière de la semaine (comme la pastille 1S) ;
  hausses et baisses = cours des lignes détenues aujourd'hui, à ces deux dates.
  Le PEA doit être dans S : une section CTO ouverte est quittée pour l'accueil.
  Un module masqué n'a pas sa rubrique. « La semaine qui vient » :
  `agenda.a_venir` (ce que Pilote sait dater, iCloud connecté ou non).
* Ouverture du dimanche (`S.uiPrefs.bilan = {auto, heure, vu}`, éteinte par
  défaut) : vérifiée chaque minute ; Pilote fermé à l'heure dite, au premier
  lancement qui suit ; une fois par semaine, jamais par-dessus une autre fenêtre.
* La notification iCloud en reprend les chiffres : `docs/modules/agenda.md`.

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
  **Notes à la ligne** (13/10/2026, demande d'Arthur : « qu'ils retournent à
  la ligne s'ils sont seuls, ou si la place de la case le permet ») : sur la
  tuile, une note coupée gagne des lignes (`-webkit-line-clamp: var(--l)`)
  tant que la tuile ne dépasse pas la hauteur de sa rangée, ou 222 px
  (`DASH_TUILE_HAUT`) si sa rangée est plus basse. `dashNotesAjuster`, appelée
  à la fin de `dashRender` et quand la fenêtre change de taille, donne les
  lignes à tour de rôle (chaque note coupée en gagne une avant qu'une autre en
  gagne deux) et s'arrête dès que la tuile grandirait. Une note seule a toute
  la place (cinq lignes dans une tuile de 222 px). Coche et échéance restent
  sur la première ligne (`align-items: baseline`). Mesuré sur une copie de ses
  données : sa note « Virement Livret A -> Compte courant », coupée jusque-là
  (224 px de texte pour 162), tient sur deux lignes ; trois notes longues en
  1re rangée la font passer de 196 à 220 px, dernière tuile à 704 px.

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

Les tuiles « Performance » (PEA, CTO, toute ma bourse) faisaient 232 px avec
leur mini-courbe : la « Performance du CTO TR » d'Arthur, en 2e rangée, la
faisait finir à 728 px (mesuré le 13/10/2026 avec ses huit tuiles). Courbe
ramenée à 26 px sous les pastilles (`.dash-rng + .dash-spark`) et pastilles
moins espacées : 222 px comme les autres, 2e rangée à 708 px, même avec trois
tuiles Performance dedans (703 px).

### Tuiles de l'Agenda (22/10/2026)

Demandées par Arthur, qui a posé la règle : **toute nouvelle fonctionnalité
vient avec ses tuiles** (`CLAUDE.md`). `ag-jour` (« Aujourd'hui »),
`ag-semaine` (« Cette semaine », 7 jours), `ag-notes` (« Prochaines notes » +
« Ajouter »), et depuis le 26/10/2026 `ag-alertes` (« Prochaines
notifications », ce qui va sonner sur le téléphone, `agenda_prochaines`). Elles relisent `agDuJour` du calendrier et `AG.notes` ; les
événements iCloud sont lus à part (`dashAgIcloud`, 10 min). Détail :
`docs/modules/agenda.md`.

* Mesuré à 1366 × 720 sur le banc : « Cette semaine » faisait 229 px avec son
  lien du bas ; `go: ""` le retire en gardant la tuile cliquable → 199 px, 2e
  rangée à 706 px.
* La liste des notes est en `.dash-agnotes`, pas `.dash-notes` :
  `dashNotesAjuster` prend la première `.dash-notes` de l'accueil, il aurait
  ajusté cette tuile au lieu du pense-bête.

### Tuiles de Garmin (03/11/2026)

`ga-sommeil` (sommeil de la nuit, score, moyenne 7 j, courbe 14 j), `ga-forme`
(Body Battery du jour, VFC et FC au repos, courbe 14 j de la Body Battery),
`ga-pas` (pas du jour, barre vers l'objectif), `ga-intensite` (minutes intenses
depuis lundi, barre vers l'objectif de la semaine), `ga-cycle` (jour du cycle,
seulement s'il est coché et suivi dans Garmin), `ga-record` (dernier record de la
montre, lu dans Sports), `ga-records` (03/11/2026 : record sur 5 km en grand, les
autres distances dessous, lus dans `GA.config.records` ; allumée par Premiers pas
avec le module). Elles lisent `GA.config` (`garmin.json`) et
disparaissent tant que rien n'a été lu. Détail : `docs/modules/garmin.md`.

### Tuiles des montres (03/11/2026, branche `montres`)

`mo-derniere` (dernière séance de Garmin, Coros ou d'un .fit), `mo-synchro`
(heure de synchronisation de chaque montre, rouge s'il faut reconnecter ;
seulement avec une montre connectée), `co-forme` (récupération, sommeil et VFC
de Coros). Module « Montres ». Détail : `docs/modules/montres.md`.

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
* Vérifié sur une copie d'un vrai CTO : les quatre périodes (1S, 1M, YTD, Max), au centime près
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
* Vérifié sur une copie de données réelles : chaque période est la somme du PEA et
  du CTO, et le % tombe entre ceux des deux comptes, comme « Toute ma bourse ».
* Titre court sur la tuile (« Performance de ma bourse ») : le nom complet
  passait sur deux lignes à 1024 px.

* **Achats programmés** (4.4.40, module Bourse) : `plans-attente` (nombre
  d'échéances à valider, PEA et CTO, mène au compte de la plus ancienne) et
  `plans-prochains` (prochain achat programmé). Les deux disparaissent sans plan.
* **Tâches** (12/11/2026) : `tc-jour` (toujours là une fois le module lu, cases à
  cocher et « Ajouter ») et `tc-retard` (s'efface sans retard). Détail :
  `docs/modules/taches.md`.

## Signaler un problème (09/11/2026, prochaine version)

La même fenêtre `ov-suggestion` a un second mode (`homeSuggestion(true)`), ouvert
par « Signaler un problème » sous l'idée, et dans Paramètres › Données &
application (« Un souci ? »). Adresse `PROBLEME_ADRESSE`,
pilote.appli+probleme@gmail.com. Le mail est prérempli avec « Ce que je
faisais / Ce qui s'est passé », la version, le système (`Api.rapport_probleme`)
et les trois derniers plantages de `crash.log` réduits par
`storage.resume_crash_log` : date, fichier:ligne et fonction de chaque étape,
type de l'erreur. **Ni le message de l'erreur, ni les lignes de code, ni les
chemins** : ils peuvent contenir un ticker, un montant ou le nom du compte
Windows (consigne d'Arthur : aucun chiffre). Le texte est montré dans la fenêtre
avant l'envoi, et c'est la messagerie de l'utilisateur qui envoie. Test :
`tests/test_donnees.py`, `SignalerProbleme`.

**C'est l'utilisateur qui décrit le problème (10/11/2026, remarque d'Arthur :
« c'est à l'utilisateur de mettre ce qu'il voit »).** La fenêtre s'ouvre sur
une zone « Ce que tu vois » (`#sug-vu`, curseur dedans) ; les infos techniques
sont pliées en dessous (`details.sug-tech`), toujours jointes et visibles d'un
clic. Le texte tapé ouvre le mail, suivi du rapport après « -- » ; zone vide :
l'ancien modèle « Ce que je faisais / Ce qui s'est passé ». La zone se vide
après « Ouvrir ma messagerie » ou « Écrire avec Gmail », et garde le texte si
l'on referme sans envoyer.

## Recherche globale : Ctrl+K (12/11/2026, 4.4.70)

Bouton « Rechercher » dans la barre du haut, ou Ctrl+K (⌘K sur Mac), partout sauf
sur l'écran du code PIN. Bloc `rg*` d'index.html, fenêtre `ov-recherche` créée à
la première ouverture. Elle cherche **dans ce qui est déjà en mémoire**, rien
n'est relu sur le disque : les onglets des sections affichées, les positions du
PEA (`_etatPea()`, même section CTO ouverte), les transactions de Mes comptes,
les séances, les pesées, les comptes du Patrimoine, les tâches et les notes de
l'Agenda. Un module masqué ou pas encore chargé ne donne rien. Tous les mots
doivent y être, sans accents ni majuscules (`rgNorm`) ; au plus 8 résultats par
groupe, les titres qui commencent par le mot d'abord, puis les plus récents.
↑ ↓ pour choisir, Entrée pour ouvrir : l'onglet s'ouvre, puis la fiche de
l'élément (transaction, séance, pesée, compte, tâche, note).

## Bilan de l'année avec Pilou (12/11/2026, 4.4.70)

Maquette montrée à Arthur le 12/11 : des cartes au format story (1080 × 1920),
présentées par Pilou, **sans aucun montant en euros** (des heures, des % et des
mois), à enregistrer en PNG pour les garder ou les partager. Bloc `an*`
d'index.html (à ne pas confondre avec `bilan*`, le bilan de la semaine).

* **Quand** (choix d'Arthur) : du 1er décembre au 31 janvier, la tuile
  `an-bilan` est mise en tête de l'accueil une fois par an (`S.uiPrefs.anBilanTuile`),
  et Pilou le propose une fois (carte flottante, `anBilanPropose`). Le reste de
  l'année : Paramètres → Général → « Mon année ». En janvier, c'est l'année d'avant
  (`anAnnee`).
* **Cartes** (`anComposer`), une seulement si le module a de quoi dire :
  couverture, Sport (heures, séances, trois sports en %, mois record), Bourse
  (performance du PEA sur l'année, mois avec un versement, ligne de l'année),
  Budget (mois où les revenus dépassent les dépenses, catégorie qui a le plus
  baissé si l'an dernier a au moins 6 mois suivis), Santé (semaines suivies,
  pesées, objectif de poids atteint), Tâches (cochées, récurrentes comprises),
  récap en quatre chiffres. Moins de deux cartes : « pas encore assez de choses
  notées ».
* **Mêmes calculs que les modules** : la performance du PEA est celle de la tuile
  (computePnl sur la courbe, période YTD ; égale à la tuile sur Brice, vérifié le
  12/11), les totaux de Mes comptes sont ceux de `finComputeYearTotals`.
* **Image** : chaque carte est un SVG qui embarque Onest et Newsreader en data URL
  (`anChargerPolices` : une image SVG n'a pas accès aux polices de la page),
  dessiné dans un canvas puis envoyé à `Api.image_enregistrer` (fenêtre
  « Enregistrer sous », en-tête PNG vérifié, rien dans `Donnees/`). Couleurs
  tirées de l'accent choisi. Dans le SVG, la police passe par une classe
  (`an-serif`) : la règle CSS `text {}` l'emporterait sur un attribut `font-family`.
