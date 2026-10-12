# Module CTO (comptes-titres ordinaires)

Fiche détaillée tirée de `CLAUDE.md`, qui garde les règles générales (dont les cinq choses à ne jamais casser).

## Ce qui a été décidé avec Arthur (11/10/2026)

Six lots de questions avant d'écrire une ligne. Ses choix :

* **Plusieurs CTO** par utilisateur, chacun avec son courtier. Au départ (4.4.0),
  une seule section « CTO » et une liste déroulante en haut des onglets.
  **Changé le 12/10/2026 (4.4.1), à sa demande** : « un module complet pour un
  CTO », donc **une section par CTO** dans la barre latérale, à son nom
  (« CTO » + nom du compte) ; en créer un agrandit la barre (« + » du titre
  Bourse). La liste déroulante a disparu. Détail : `CLAUDE.md`, « Navigation ».
* Son CTO : **Trade Republic**. ETF en euros, actions européennes, titres américains.
* **Cours en euros** : Trade Republic exécute en euros sur des places
  européennes (LS Exchange, puis « Best Price » depuis la fin du paiement pour
  flux d'ordres en juillet 2026). Pilote suit la cotation en euros d'un titre
  (Apple à Xetra : `APC.DE`), jamais le cours de New York converti.
* **Pas de fiscalité** : montants bruts, comme le PEA (même choix que pour
  l'assurance vie du prêt, 4.3.29).
* **Pas d'espèces** : le compte espèces de Trade Republic sert aussi de compte
  courant (carte). Le CTO ne suit que les titres.
* **Saveback compté à son prix**, comme un achat : le PRU doit être celui de
  Trade Republic (Arthur avait d'abord dit « comme un gain », puis s'est corrigé).
* **Import du CSV Trade Republic** + saisie à la main. Seuls titres et
  dividendes ; carte, virements et intérêts ignorés. Plans programmés non
  paramétrés dans Pilote : le CSV suffit.
* Onglets : vue d'ensemble et courbe, Positions, Expositions, Dividendes,
  Transactions, Wishlist (propre au CTO), Stratégie.
* **Courtiers** : les principaux courtiers français, grilles datées,
  modifiables, alerte quand un ordre réel ne colle pas. Pas de lecture
  automatique de leurs sites (fragile, casserait sans bruit).
* **La Stratégie suit le courtier** : plans gratuits et parts fractionnées
  (Trade Republic) → montants à mettre sur chaque plan ; sinon → les ordres du
  mois, comme le Prochain achat du PEA.
* Liens : Patrimoine (une ligne automatique par CTO) et Accueil (une tuile par
  CTO, à ajouter). Pas de lien avec le Prêt, pas de vue cumulée PEA + CTO.
* **Une seule version** pour tout, choix du courtier sur le PEA compris (4.4.0).

## Architecture : le « compte actif »

Le CTO n'a **aucun écran propre** : il réutilise ceux du PEA (8 000 lignes de
calculs et de rendus mûrs ; les recopier aurait fait deux versions qui
divergent un jour). Ouvrir un onglet `cto-*` appelle `_cptBasculer(id)` :

1. les données du compte affiché sont rangées (`_peaHorsEcran` pour le PEA,
   l'objet du compte dans `CTO.comptes` pour un CTO) ;
2. celles du compte demandé passent dans `S` (mêmes clés, `CPT_CLES`) et `NID` ;
3. les caches propres au compte sont remis (historique Yahoo par compte dans
   `_ctoCaches`, brouillons du simulateur, budget tapé) ; `_cptGen` change ;
4. `renderAll()` : Positions, Transactions et Wishlist ne se redessinent pas à
   l'ouverture et montreraient sinon l'autre compte (bug vu au premier essai).

Tout autre onglet remet le PEA. `goTab` d'origine fait la bascule
(`ctoAvantOnglet` : `cto-pos` → pane `pos`) ; `cto-dash@c2` ouvre un CTO précis
(onglets de sa section, tuile d'accueil). `_navSectionOf` ignore le `@…` ;
`_setActiveSidebar` complète un onglet sans `@` par le CTO affiché.

Créer, renommer ou supprimer un CTO rebâtit la barre latérale
(`_reconstruireSidebar`), comme la lecture de `cto.json` au lancement : la
barre est dessinée avant, avec la seule section « CTO ».

### Ce qu'il ne faut pas défaire

* **`_syncToPythonNow` lit `_etatPea()`, jamais `S`** : une écriture du PEA
  partie 0,4 s avant la bascule déposerait sinon le CTO dans `pea_data.json`.
* **`persist()` d'un CTO n'écrit que `cto.json`** (`ctoPersist`), plus les
  réglages communs (`S.uiPrefs`, dont les corrections d'Expositions) par
  `save_ui_prefs`. Jamais de `localStorage` du PEA.
* **`_cptGen`** : `loadPerfHistory`, `renderPerf` et `perfSeriesAsync` jettent
  une réponse arrivée après une bascule.
* **`dashRender()` ne fait rien pendant qu'un CTO est dans `S`** : les tuiles du
  PEA (Jour, Performance, Prochain achat) le liraient. L'accueil remet le PEA.
* **`renderMetrics()` passe la main à `ctoRenderMetrics()`** pour un CTO : rien
  vers `window._peaPv` (Patrimoine, accueil).
* Réglages propres au compte (Prochain achat, scénarios du simulateur, plans) :
  `_cptPrefs()`. Le courtier d'un CTO vit sur le compte (`courtier`, `tarif`).
* Retour : instantané `{cpt, S, NID}` ; dans la section CTO, seules les actions
  du CTO affiché s'annulent ; `undoLast` réinstalle ses versements déduits.

## Pas d'espèces : les versements se déduisent des ordres

`S.depots` d'un CTO affiché est un accesseur (`ctoInstallerDepots`) qui
recalcule à chaque lecture (`ctoDepotsDeduits`) : un achat est un apport de
son montant frais compris, une vente et un dividende un retrait de ce qu'ils
ont rapporté (mêmes montants que `computeCash` et `buildTwrSeries` :
`brutOrdre`). Les espèces restent donc à zéro, et tout le calcul du PEA
s'applique tel quel : plus-value = valeur − (achats − ventes − dividendes),
courbe des titres, TWR coupé à chaque achat, comparaisons « et si chaque
achat avait acheté l'indice ». Non énumérable : `pushUndo` ne le copie pas.
La ligne pointillée de la courbe devient « Investi net » et descend à une
vente (`buildDepositSeries` garde les retraits pour un CTO seulement).

`ctoResume(id)` est **le seul calcul** des chiffres d'un CTO : ses cartes, sa
tuile d'accueil et sa ligne du Patrimoine le lisent (`computePos(p, txs)` prend
les transactions d'un compte non affiché).

Vérifié sur un relevé d'essai (3 plans, 1 Saveback, 1 achat et 1 vente d'Apple,
1 dividende) : PRU du MSCI World 130,47 € (379,48 € pour 2,908654 parts),
investi net 592,07 €, valeur 681,13 €, plus-value +89,06 €, dernier point de la
courbe = valeur de la carte. PEA d'essai identique au centime avant et après
un passage dans le CTO.

## Courtiers et frais (`COURTIERS`, bloc Prochain achat)

Une grille par courtier : paliers `{max, fixe, pct}`, `min`, `max`, `gratuit`
(1er ordre du mois jusqu'à ce montant), `plan` (frais d'un plan programmé, null
= pas de plans). `courtageOrdre(m, tarif, pea)` ; sur un PEA, plafond légal de
0,5 %. `pacFraisOrdre` remplace l'ancien `montant × taux` dans `pacFrais` et
`soCalcul` (sans grille : l'ancien calcul, d'où les tests inchangés).

Relevés le 11/10/2026 :

| Courtier | Grille | Source |
|---|---|---|
| Trade Republic | 1 € par ordre, plans 0 €, fractions | support.traderepublic.com |
| Fortuneo Starter | 1er ordre du mois ≤ 500 € gratuit, puis 0,35 % | fortuneo.fr/bourse/tarifs |
| Fortuneo Progress | 4,90 € jusqu'à 3 000 €, puis 0,15 % | idem |
| Fortuneo Trader Pro | 9,50 € jusqu'à 10 000 €, puis 0,10 % | idem |
| Bourse Direct | 0,99 / 1,90 / 2,90 / 3,80 € jusqu'à 500 / 1 000 / 2 000 / 4 400 €, puis 0,09 % | conditions du 06/01/2026 |
| BoursoBank Découverte (CTO) | 1,99 € jusqu'à 500 €, puis 0,60 % | tradingboard.boursobank.com |
| DEGIRO (CTO) | 2 € sur Euronext Paris | degiro.fr/tarifs |
| Interactive Brokers Tiered (CTO) | 0,05 %, min 1,25 €, max 29 €, frais de bourse en plus | interactivebrokers.ie |
| Saxo Classic | 0,08 %, min 2 € | moneyvox.fr (la page de Saxo n'affichait pas ses chiffres) |

* **PEA** : « Réglage libre » (seuil + taux) reste le défaut, exactement le
  calcul d'avant. Choisir Fortuneo Starter redonne le même plan au centime
  (vérifié : mêmes ordres, mêmes frais, 496,72 €).
* **Personnalisé** : la grille se modifie palier par palier (Stratégie →
  Réglages / Cibles et courtier).
* **`txFraisBadge`** : un ordre dont les frais réels ne collent pas à la grille
  est marqué « frais ≠ grille » dans Transactions, et compté dans la barre du
  CTO. Un ordre de plan, Saveback ou arrondi attend `tarif.plan`.
* Les tarifs se revérifient à chaque version qui touche aux courtiers.

## Stratégie

* **Plans** (`ctoModePlans` : courtier à fractions et `plan: 0`) : la carte
  « Réglage des plans » remplace Prochain achat. `ctoPlansCalcul` (pur, étapes
  2-3 de `pacCalcul` sans parts entières ni frais) : montant visé, rien pour une
  ligne en surpoids, centimes qui tombent juste sur le budget, plan sous le
  minimum reporté. Colonnes « ce mois-ci » (rattrapage) et « en croisière »
  (cible × budget). **`testsPlans()`** (console, 5 cas).
* Sinon : Prochain achat avec la grille du courtier. Budget du mois saisi et
  retenu (`cfg.budget`) : pas d'espèces à reprendre.
* Simulateur d'ordres : frais du courtier ; « pour 50 € » achète 50 / prix
  parts tronquées au millionième sur un courtier à fractions (`soFractions`).
  Case « ordre gratuit » masquée quand le courtier n'en a pas.

## Import du relevé CSV de Trade Republic

Export dans l'appli depuis avril 2026 : Profil → Relevés → Export des
transactions. Trade Republic ne publie pas ses colonnes : les 23 colonnes
viennent du lecteur open source de broker-to-edavki (ADR 0015). Lecture par
nom de colonne (`cto.lire_csv_tr`), virgule ou point-virgule, décimales au
point ou à la virgule.

* Repris : `BUY`, `SELL`, `SAVINGS_PLAN_EXECUTED` (plan), `BENEFITS_SAVEBACK`
  (Saveback), types `*ROUND_UP` (arrondi), `STOCKPERK`/`BONUS` (offert),
  `DIVIDEND` (montant crédité). Ignorés : espèces (carte, virements, intérêts),
  classes hors actions et fonds. Types inconnus : listés, jamais devinés.
* Le montant d'un ordre peut inclure les frais ou non selon les fichiers :
  un écart jusqu'aux frais est normal (même tolérance que broker-to-edavki).
* **ISIN → cotation en euros** (`/isin`, `server.cotations_euro`) : Yahoo ne
  rend pour un ISIN que la cotation principale (Apple → `AAPL` en dollars,
  MSCI World → `IWDA.L` en dollars). On cherche aussi par symbole et par nom,
  on garde les places européennes, puis on vérifie la **devise réelle** (le
  suffixe ne suffit pas). L'import choisit le cours le plus proche du dernier
  prix payé (à 20 % près) et l'utilisateur valide. Le secteur Yahoo d'une
  action devient celui de la position (`ctoSecteurYahoo`).
* Doublons : même `transaction_id` (`trId` sur la transaction ou le dividende),
  ou même ordre saisi à la main. Ré-importer le même fichier n'ajoute rien.
* Rien n'est enregistré avant « Importer » ; un seul `pushUndo` (Retour annule
  tout l'import).
* **À revérifier sur un vrai export d'Arthur** : les essais du 11/10/2026 ont
  porté sur un fichier construit d'après le format publié (pas de vrai export
  sous la main) : ce que contient une ligne de dividende, le nom exact du type
  des arrondis, et que le PRU affiché par Trade Republic inclut bien les frais
  (comme Pilote ; un témoignage d'utilisateur le laisse penser).

## Expositions

* Pays d'une action d'un CTO : celui de son **ISIN** (`expoPaysIsin`), pas de
  sa place de cotation (Apple suivie à Xetra compterait pour l'Allemagne).
* Un ETF qui suit le même indice qu'un ETF connu reprend sa composition
  (`EXPO_MEME_INDICE`, par ISIN ou ticker : IWDA/SWDA/EUNL → WPEA, CSPX/SXR8 →
  ESE, CNDX/SXRV → PNAS, MEUD → ETZ : ce sont les fonds dont `expositions.py`
  lit déjà les lignes).

## Accueil et Patrimoine

* Une tuile par CTO (`ctoSyncWidgets`, id `cto:<id>`), éteinte tant qu'on ne
  l'ajoute pas ; un clic ouvre ce CTO (`cto-dash@<id>`).
* Une ligne automatique par CTO dans le Patrimoine (`auto: "cto:<id>"`, créée
  par `ctoLignesPatrimoine`), au nom du CTO, valeur de `ctoResume`. Un mois
  passé n'est proposé que si la courbe de ce CTO est chargée ; sinon la ligne
  reprend son dernier relevé. Supprimer un CTO masque sa ligne, sauf si elle a
  des relevés.

## Données (`cto.json`)

`{comptes: [{id, nom, courtier, tarif, cree, _nid, positions, transactions,
divReceived, divFuture, wishlist, closedPositions, strategies, prefs}], actif,
_nid}`. Positions avec `isin` quand elles viennent d'un import ; transactions
avec `origine` (plan, saveback, arrondi, offert) et `trId`. Un état sans aucun
compte n'écrase pas un fichier qui en a (`save_data(…, vide_voulu)`), comme
la défense « PEA vierge ».
