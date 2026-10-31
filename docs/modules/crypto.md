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
  frais d'un ordre de crypto).
* Les mini-courbes « 30j » des Positions ne sont demandées qu'au lancement,
  pour le PEA : vides sur un CTO comme sur la Crypto (`fetchSparklines`).
* Pas d'onglet Plan d'épargne (achats programmés) ni Wishlist pour l'instant.
