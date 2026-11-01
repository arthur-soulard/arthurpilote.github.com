# Section Crypto

Fiche détaillée tirée de `CLAUDE.md`, qui garde les règles générales (dont les six choses à ne jamais casser).

## Ce qui a été décidé avec Arthur (31/10/2026)

* Une section **Crypto** dans « Bourse », sous le PEA et les CTO, **comme un
  CTO** : positions, prix de revient, cours en euros, courbe, plus-value, ligne
  automatique dans le Patrimoine.
* **Import de l'export CSV de Trade Republic** : les lignes de crypto, ignorées
  par le CTO jusque-là (« le Bitcoin hors du CTO », 12/10/2026), vont dans la
  section Crypto.
* **Trois tuiles d'accueil** : valeur (et variation du jour), plus-value, courbe.
* Catalogue d'**une vingtaine de cryptos** ; une autre se tape « XXX-EUR ».

## Architecture : un compte de `cto.json` marqué `crypto: true`

Le portefeuille crypto est un compte de `CTO.comptes` comme les autres, avec
`crypto: true`. Tout le moteur du CTO s'applique tel quel (« compte actif »,
versements déduits des ordres, `ctoResume`, courbe, Retour, écriture de
`cto.json`) : voir `docs/modules/cto.md`. Un seul portefeuille crypto par
utilisateur (`cryptoCompte()`).

Ce qui le distingue :

* **Sa propre section** `sec-crypto` dans `NAV_SECTIONS`, onglets
  `crypto-dash`, `crypto-pos`, `crypto-tx` (pas d'`@id`). `ctoAvantOnglet` met
  le compte crypto dans `S` et montre `pane-dash`, `pane-pos`, `pane-tx` ; sans
  portefeuille, `pane-crypto-vide` (bouton « Créer mon portefeuille crypto »,
  `ctoOuvrirCompte(null, true)`).
* **Jamais parmi les CTO** : `ctoComptesTitres()` (les comptes sans `crypto`)
  remplace `ctoComptes()` partout où il s'agit des comptes-titres : blocs de la
  barre (`_navBlocs`), `ctoActifId`, `_ongletComplet`, cibles de l'import,
  Paramètres › CTO, Plan d'épargne (`peComptes`), « Toute ma bourse »
  (`dashBourseComptes`, dont la tuile dit « PEA + n CTO »). `ctoComptes()`
  reste là où tous les comptes comptent : cours, écriture, Patrimoine.
* `body.cpt-crypto` (en plus de `cpt-cto`) : `.pas-crypto` masque le type, le
  secteur et les dividendes de « Ajouter une position », la carte « Dividendes
  reçus » et la colonne Secteur des Positions. `data-crypto` donne à un libellé
  `data-cto` son texte crypto (« Valeur des cryptos », `ctoLibelles`).
* Position de type `crypto` (badge « Crypto »), `sector: null`.
* Ordre de la barre : `sec-crypto` suit `sec-cto` dans `NAV_ORDRE_DEFAUT` ; dans
  une barre déjà réordonnée, elle se range après le dernier CTO (`_navOrdre`).
* Module à part (`NAV_MODULES`, `MODULES_A_CHARGER`) : masquable seul. Les deux
  sections lisent le même `cto.json`, une seule fois (`ctoBootstrap` garde sa
  promesse en cours).

## Cours en euros

Yahoo cote les cryptos en paires `BTC-EUR`. `normalizeTicker` laisse passer
`XXX-EUR` tel quel (il en faisait « EPA:BTC-EUR »). `CRYPTO_CATALOGUE` : 23
cryptos dont la paire en euros a été vérifiée chez Yahoo le 31/10/2026
(Uniswap : `UNI7083-EUR`). Écartés : Polygon, Near, Pepe, Sui, Toncoin, Aptos,
Arbitrum, Optimism (pas de paire en euros chez Yahoo), Shiba Inu (cours de
0,00001 € arrondi à 0 par le serveur, quatre décimales). « Ajouter une
position » cherche dans ce catalogue, pas chez Yahoo (qui rend d'abord les
paires en dollars).

## Import Trade Republic

`cto.lire_csv_tr` : `asset_class` `CRYPTO`, ou un faux ISIN `XF000…`
(XF000BTC0017 : « XF000 » + symbole) quand la classe manque → `classe:
"crypto"`, `compte: "CRYPTO"` quel que soit `account_type` (Trade Republic ne
range pas la crypto sur le compte-titres). L'import sépare les opérations par
compte (`_ctoImpSeparer`, `_ctoImpCompteIci`) et propose d'envoyer chaque autre
groupe (PEA, compte-titres, cryptos) dans son compte. La cotation d'une crypto
vient de `cryptoTickerDe(isin, nom)` (symbole du faux ISIN, sinon nom du
catalogue), sans appel à `/isin`. Tests : `tests/test_releves.py`,
`TradeRepublicCrypto` (lignes inventées : aucune vraie ligne de crypto d'Arthur
n'a encore été essayée).

## Plateformes crypto et leurs exports (31/10/2026, demande d'Arthur)

« Tu as mis les mêmes courtiers que les CTO, or c'est différent » : le
portefeuille crypto propose ses **plateformes**, celles de `COURTIERS` dont
`comptes` contient `"crypto"` : Binance, Bitpanda, Bitstack, Bitvavo,
Coinbase, Coinhouse, Crypto.com, Delta (appli de suivi, ajoutée à sa demande),
eToro, Kraken, Revolut, Trade Republic, et « Autre plateforme ». Le champ
s'appelle « Plateforme » (`cto-cpt-courtier-lbl`). Un portefeuille créé en
4.4.43 avec un courtier de CTO voit la liste vide jusqu'à ce qu'il en
rechoisisse une (`dispo`).

* **Tarifs** : relevés le 31/10/2026 dans plusieurs comparatifs (les pages des
  plateformes se contredisent souvent : écart de cours caché dans le prix,
  paliers). Ils servent d'indication dans la barre du compte.
* **Pas d'alerte « frais ≠ grille »** sur la crypto (`txFraisAttendus` rend
  null) : le vrai coût est un écart de cours que les exports ne montrent pas,
  l'alerte sonnerait à tort.
* Binance : arrêt de ses services en France au 1er juillet 2026 selon plusieurs
  sources (non confirmé sur son site) ; gardé pour importer son historique.

**Lecteur** : `src/releves_crypto.py`, appelé en tête de
`releves.lire_tableau` (reconnaissance par les colonnes, `_SIGNES`). Formats :
Binance (relevé de compte « Transaction History », lignes d'un même ordre
regroupées par seconde ; historique des ordres, ancien et nouveau), Coinbase
(lignes de titre au-dessus de l'en-tête, montants « €1,234.56 »), Kraken
(ledgers regroupés par `refid`, trades), Bitpanda (actions et métaux ignorés),
Crypto.com (application, `Native Amount` = valeur en euros), Revolut (relevé
crypto), Bitvavo, Delta. eToro (`releves._etoro`) et le lecteur universel
envoient aussi leurs cryptos dans la section (nom reconnu : `est_crypto`).
Colonnes et types relevés dans les lecteurs de BittyTax (sur de vrais
exports) ; Bitvavo et Delta d'après leur documentation.

Règles (en tête de `releves_crypto.py`) :
* échange entre cryptos (BTC → ETH, achat en USDT) = une vente et un achat, à
  la valeur en euros de l'export, sinon au cours de clôture du jour (Yahoo,
  `cours_eur`) ;
* frais pris sur la crypto reçue : quantité nette, frais en euros ; payés dans
  une troisième crypto (BNB) : celle-ci est vendue d'autant ;
* **récompense** (staking, intérêts, cashback, parrainage) = achat « offert »
  (`origine: "offert"`) à sa valeur du jour : les quantités suivent la
  plateforme, comme les actions offertes de Trade Republic ;
* envoi ou réception de crypto : ignoré, compté (`transferts_crypto`, dit à
  l'écran : « importe aussi l'export de cette plateforme ») ;
* **sauf « Receive » chez Coinbase** (01/11/2026, décidé avec Arthur) : un
  utilisateur dont l'export Coinbase n'avait que des réceptions voyait un
  portefeuille vide. Une réception devient un achat `origine: "recu"` (badge
  « Reçu ») à la valeur que donne l'export (`Subtotal`, converti en euros),
  sinon au cours du jour. L'aperçu de l'import prévient : si l'export d'où
  vient la crypto est aussi importé, son achat y est déjà (compté deux fois).
  Les envois restent ignorés ;
* Delta écrit `SOL (Solana)` : seul le symbole avant la parenthèse est gardé
  (jusqu'au 01/11/2026, « SOL (SOLANA) » restait sans cotation) ;
* toute opération porte `compte: "CRYPTO"`. Depuis le PEA ou un CTO, l'import
  propose de l'envoyer dans la section Crypto ; depuis la Crypto, les actions
  d'un relevé de banque restent dehors (`titres_hors_crypto`).

Tests : `tests/test_releves_crypto.py` (exports fictifs, cours fixés). Vérifié
au banc : un export Coinbase importé dans la section (achat, staking en
« offert », envoi ignoré, Solana reconnu). Le 01/11/2026, deux fichiers
d'un autre utilisateur : un vrai export Coinbase (5 réceptions : BTC, ETH,
SOL, DOGE importés au banc avec leur cours) et le modèle d'exemple de Delta
(pas un vrai historique). Les autres plateformes : aucun vrai export essayé.

## Tuiles et Patrimoine

* `cryptoWidgets(id)` (appelée par `ctoSyncWidgets`) : `crypto:<id>` (valeur,
  variation du jour par `dashPeaDay`), `crypto-pv:<id>` (plus-value et % de
  `ctoResume`), `crypto-courbe:<id>` (valeur et mini-courbe sur 6 mois,
  `dashCtoSerie`). Éteintes tant qu'on ne les ajoute pas ; module « Crypto »
  (icône `currency-btc`).
* Ligne du Patrimoine : `auto: "cto:<id>"` comme un CTO, de type `crypto`
  (« Cryptomonnaies », type qui existait déjà).

## Vérifié au banc (31/10/2026, données de Camille)

Création, ajout d'un Bitcoin à la main (0,01 à 60 000 € + 1 € : valeur et
plus-value justes au cours du jour), courbe, import d'un export mêlant crypto et
compte-titres dans les deux sens (rien dans le PEA ni le CTO, `cto.json`
relu sur le disque), trois tuiles, ligne du Patrimoine, thèmes clair et sombre.

## Reste à voir

* Un vrai export Trade Republic avec des cryptos (nom exact de `asset_class`,
  frais d'un ordre de crypto), et un vrai export de chaque plateforme.
* Les mini-courbes « 30j » des Positions ne sont demandées qu'au lancement,
  pour le PEA : vides sur un CTO comme sur la Crypto (`fetchSparklines`).
* Pas d'onglet Plan d'épargne (achats programmés) ni Wishlist pour l'instant.
