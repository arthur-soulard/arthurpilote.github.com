# Module CTO (comptes-titres ordinaires)

Fiche détaillée tirée de `CLAUDE.md`, qui garde les règles générales (dont les cinq choses à ne jamais casser).

## Ce qui a été décidé avec Arthur (11/10/2026)

Six lots de questions avant d'écrire une ligne. Ses choix :

* **Plusieurs CTO** par utilisateur, chacun avec son courtier. Au départ (4.4.0),
  une seule section « CTO » et une liste déroulante en haut des onglets.
  **Changé le 12/10/2026 (4.4.2), à sa demande** : « un module complet pour un
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
  CTO. Un ordre de plan, Saveback ou arrondi attend `tarif.plan` ; une action
  offerte est un ordre ordinaire (1 € chez Trade Republic) ; une division
  n'attend rien. La comparaison porte sur le courtage seul (`txCourtage` :
  frais moins `taxe`).
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
  de la catégorie TRADING (Saveback), types `*ROUND_UP` (arrondi),
  `STOCKPERK`/`BONUS` (offert), `DIVIDEND` (montant crédité), `SPLIT`
  (division). Ignorés : **toute ligne de la catégorie CASH** (carte, virements,
  intérêts, Saveback versé, cadeau), classes hors actions et fonds (le
  Bitcoin : Arthur l'a voulu hors du CTO le 12/10/2026, il n'est pas conservé
  sur le compte-titres). Types inconnus : listés, jamais devinés.
* Ordre des opérations : date, puis heure (`datetime`) : une division passe
  avant la vente du même jour.

### Ce que montre le vrai relevé d'Arthur (12/10/2026)

Premier vrai export (732 lignes, juillet 2025 → octobre 2026, 18 titres) ; les
essais du 11/10 avaient porté sur un fichier construit. Ce qui différait :

* **Plan** : un `BUY` ordinaire ; seule la description le dit (« Savings plan
  execution <ISIN> <nom>, quantity: … », « Buy trade … » pour un ordre).
  Sans ça, 102 achats de plan passaient pour des ordres à 0 € de frais.
* **Saveback** : une ligne CASH `BENEFITS_SAVEBACK` (ISIN, montant) **plus**
  l'achat. L'ancien lecteur prenait la ligne CASH pour un achat sans parts.
  L'achat du même titre et du même montant, à trois jours au plus, devient
  « Saveback ». Depuis décembre 2025, le Saveback d'Arthur va au Bitcoin.
* **Action offerte** (« stock perk ») : une ligne CASH `GIFT` (21 €), puis à la
  même seconde un ordre de 19,99 € + 1 € de frais (Amazon, Tesla) → « offert ».
* **Taxe** : colonne `tax` = TTF française (0,4 %) sur les actions françaises,
  hors `amount`. Elle s'ajoute aux frais de la transaction (PRU, investi,
  carte « Frais cumulés ») et reste aussi dans `taxe` (comparaison à la grille).
* **Ordre en plusieurs morceaux** : même titre, même sens, même instant, même
  cours → fusionnés (5 + 0,94972 parts le 13/05/2026, 1 € de frais en tout).
* **Division** : deux lignes `CORPORATE_ACTION`/`SPLIT` à la même seconde,
  l'ancienne ligne en parts négatives, la nouvelle en positives, sans prix,
  ici avec un **nouvel ISIN** (ETP argent x3 de WisdomTree, IE00B7XD2195 →
  XS3306516876, 1 part → 10). Importée comme une **vente au PRU puis un achat
  du même coût, sans frais** (`origine: "division"`, badge « Division ») :
  plus-value nulle, versements déduits qui s'annulent le jour même. Les deux
  ISIN ont la même cotation (3SIL.MI) : une seule position. Yahoo garde ce
  jour-là le cours d'avant (183 € au lieu de ~21,84 €) : `buildTwrSeries` ne
  trace pas de point le jour d'une division (`jourDivision`).
* `amount` = parts × cours, sans frais ni taxe. Aucun dividende sur la
  période : le contenu d'une ligne de dividende reste à voir.

Résultat vérifié au centime contre un calcul indépendant fait sur le CSV :
5 positions (or physique 1,991035 parts pour 145,72 €, HSBC Emerging 23,598439
pour 353,87 €, Xtrackers Europe Value 5,722762 pour 277,34 €, Amazon 20,99 €,
Tesla 31,00 €), investi net 939,79 €, frais 27,58 € dont 0,58 € de taxe,
offert 61,99 €, aucun « frais ≠ grille », 12 lignes clôturées, second import
du même fichier : rien de nouveau, PEA identique avant et après. Les
plus-values réalisées par ligne diffèrent de quelques centimes du relevé
(−110,83 € contre −110,87 €) : `computePos` multiplie parts × cours sans
arrondir, comme pour le PEA ; l'investi net, lui, part de `brutOrdre`.

### ISIN → cotation en euros (`/isin`, `server.cotations_euro`)

Yahoo ne rend pour un ISIN que la cotation principale (Apple → `AAPL` en
dollars, MSCI World → `IWDA.L` en dollars). On cherche aussi par symbole et
par nom, on garde les places européennes, on vérifie la **devise réelle** (le
suffixe ne suffit pas). Depuis le vrai relevé :

* recherche aussi par le **nom long** de la description, entier puis raccourci
  (`_nom_court`) : « iShares Physical Gold ETC » trouve l'or physique, que
  l'ISIN et « Physical Gold USD (Acc) » ne trouvaient pas ;
* **second saut** par la racine des cotations trouvées (PPFB.SG → PPFB.DE),
  puis **essai direct sur Xetra** de chaque racine (AMZ.SG → AMZ.DE) : la
  recherche de Yahoo ne rend pas la même liste d'un appel à l'autre ;
* tri : même racine que la cotation principale, puis **place du pays de
  l'ISIN** (`_PLACE_DU_PAYS` : SGO.PA plutôt que SGO.VI), puis les places dans
  l'ordre de `_PLACES_EUR` ;
* **vérification par l'historique** : l'import envoie les prix payés
  (`points=date:prix`, 40 derniers) et le premier ordre (`depuis`). Pour les 4
  premiers candidats qui ont un cours, écart médian entre prix payés et
  clôtures (`_ecart_historique`) ; un historique qui ne remonte pas au premier
  ordre est écarté (la courbe aurait un trou). Passe devant : la place
  préférée parmi celles à moins d'un point du meilleur écart (Xetra plutôt
  que le parquet de Francfort). Le cours du jour ne suffit pas : IGLD.DE (or
  couvert en euros, un autre produit) cotait comme PPFB.DE, mais s'écartait de
  4,7 % des prix payés, contre 0,7 %. Seuil `ISIN_ECART_MAX` 10 % (un ETP à
  levier x3 s'écarte de 5 % : cours très mobile dans la journée).
* L'import prend le candidat vérifié (`ecart`), sinon le premier dont le cours
  est à 20 % du dernier prix payé, sinon le premier. « vérifiée » s'affiche
  dans la liste ; l'utilisateur peut toujours changer.
* Mesuré sur les 18 titres d'Arthur (8 s) : SGO.PA, RHM.DE, EL.PA, LRC.DE,
  HEI.DE, RRU.DE, MTE.DE, 1KTOS.MI, PPFB.DE, HEMA.PA, AMZ.DE, TL0.DE, 3GOL.MI,
  NUCL.PA, TDIV.AS, 3SIL.MI (deux ISIN), D5BL.DE. Le secteur Yahoo d'une
  action devient celui de la position (`ctoSecteurYahoo`).

### Le reste

* Doublons : même `transaction_id` (`trId` sur la transaction ou le dividende),
  ou même ordre saisi à la main. Ré-importer le même fichier n'ajoute rien.
* Rien n'est enregistré avant « Importer » ; un seul `pushUndo` (Retour annule
  tout l'import).
* **Reste à voir** : une ligne de dividende réelle, le nom exact du type des
  arrondis, et que le PRU affiché par Trade Republic inclut bien les frais et
  la taxe (comme Pilote).

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
