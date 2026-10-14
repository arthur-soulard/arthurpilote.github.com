# Import des relevés de banque et de courtier (PEA et CTO)

Fiche tirée de `CLAUDE.md`. Code : `src/releves.py` (lecture), `ctoImport*` dans
`index.html` (aperçu, enregistrement), `server.cotations_euro` (cotation en
euros, voir `docs/modules/cto.md`).

## Ce qui a été décidé avec Arthur (12/10/2026, version 4.4.3)

Demande : lire les relevés d'autres banques que Trade Republic, « en pensant aux
autres utilisateurs » (Crédit Mutuel, Crédit Agricole, Bourse Direct…), et le PEA
aussi. Ses choix :

* **PDF + CSV**, avec la bibliothèque **pypdf** (gratuite, licence BSD, 300 Ko) :
  les banques françaises ne donnent presque jamais de CSV pour la bourse, mais
  des avis d'opéré en PDF (un par ordre), des avis de dividende et des relevés.
  Écartés : CSV seul (inutile pour Fortuneo, BoursoBank, Bourse Direct) et la
  lecture des PDF par l'OCR de Windows (chiffres mal lus, rien sur Mac).
* **PEA compris** : ordres, dividendes, et versements quand le document les
  contient (sinon ils restent saisis à la main).
* Banques d'abord : **Fortuneo** (son PEA), **BoursoBank**, **Bourse Direct**,
  **Degiro, Saxo, Interactive Brokers**. Crédit Mutuel, CIC et Crédit Agricole :
  aucun exemple public trouvé, donc le lecteur « universel » (colonnes
  reconnues par leur nom ou choisies par l'utilisateur).

Pilote ne « s'entraîne » pas : une règle de lecture par banque, vérifiée sur de
vrais documents.

## D'où viennent les exemples

* **Portfolio Performance** (logiciel libre, EPL-1.0) : ses tests contiennent le
  texte de vrais documents anonymisés (`name.abuchen.portfolio.tests/.../pdf/<banque>/*.txt`)
  **et le résultat attendu** de chacun (`*PDFExtractorTest.java` : date, parts,
  brut, frais, net). Ce corrigé a servi à vérifier les lecteurs PDF. Banques
  françaises présentes : `arkeadirectbank` (Fortuneo), `boursobank`,
  `boursedirect`, `creditmutuelalliancefederale` (un seul exemple, qui est en
  fait un versement d'assurance vie), `hellobank`, `degiro`, `saxobank`. Pas de
  Crédit Agricole. Exemples XML d'Interactive Brokers : `datatransfer/ibflex/`.
* **Export-To-Ghostfolio** (Apache-2.0) : `samples/` contient de vrais exports
  CSV (Degiro relevé de compte en néerlandais, IBKR, Saxo, Trading 212…).
* **Fortuneo, vrai fichier d'Arthur (12/10/2026, 4.4.5)** : son espace client
  donne en fait un **CSV** de l'historique des opérations de bourse, dans un
  .zip (« HistoriqueOperationsBourse_<compte>.zip », contenant
  « …_du_03_09_2025_au_12_10_2026.csv »). Voir « Fortuneo » plus bas.
* Le texte des exemples PDF est celui de PDFBox ; Pilote lit les PDF avec pypdf,
  dont la mise en page du texte peut différer. **Aucun vrai PDF de banque n'a pu
  être essayé** (12/10/2026) : la chaîne pypdf → lecteur a été vérifiée sur des
  PDF fabriqués à partir du texte des exemples (`fabrique_pdf.py` du banc), pas
  sur la mise en page réelle. À refaire sur les PDF Fortuneo d'Arthur.

## Résultats mesurés (12/10/2026)

| Source | Résultat |
|---|---|
| Fortuneo, BoursoBank, Bourse Direct, Saxo (75 PDF) | 91 opérations conformes au corrigé sur 95 ; les 4 autres sont voulues (ci-dessous) |
| Degiro, rapport des transactions (3 PDF) | 246 lignes sur 246, 6 sur 6, 215 sur 215 ; frais identiques au corrigé |
| IBKR CSV, Trading 212, Saxo CSV, Degiro relevé de compte | contrôlés à la main ligne à ligne |
| IBKR XML (9 exemples) | autant d'ordres que de `<Trade>` d'actions ou de fonds |
| Trade Republic (relevé d'Arthur) | les mêmes 134 opérations qu'en 4.4.1 ; CTO : 939,79 € investis, 27,58 € de frais, 0 « frais ≠ grille » |
| Fortuneo CSV (relevé d'Arthur, .zip) | 13 opérations, chiffres identiques au fichier ; dans son PEA saisi à la main : 13 sur 13 « déjà dans Pilote », 0 à importer, 3 transferts et 1 détachement écartés, chaque titre sur son ticker (PNAS, WPEA, PEMS, EPA:SGO, ESE, PANX) |

Écarts voulus avec Portfolio Performance :

* « REGULARISATION » du relevé des liquidités Fortuneo : montrée (lignes non
  reprises), pas importée : son sens (crédit ou débit) ne se lit pas.
* Obligations (Saxo) : hors du champ du CTO, ignorées.
* Relevé de compte Saxo en allemand (« Kontoauszug ») : pas lu.
* Pilote compte en **euros** : PP garde la devise du compte (CHF, USD).
* Bourse Direct : la taxe sur les transactions et les versements sont des
  opérations à part chez Pilote (rattachée à l'ordre, ou versement du PEA).

## Lecture rendue plus sûre (14/10/2026, demande d'Arthur : « infaillible »)

Banc d'essai de la session du 14/10/2026 : vrais documents anonymisés de
Portfolio Performance (Trade Republic en français, Keytrade, Scalable,
Swissquote, Hello bank, UBS, PostFinance, KBC, Linxea en plus des banques
déjà lues), fichiers fabriqués par **LibreOffice et Excel** (vrais .xlsx,
.xls, .ods, « Texte Unicode », CSV), et 100 avis d'opéré fabriqués en PDF par
LibreOffice (4 mises en page, 9 banques de réseau, 5 polices). Les lectures
d'avant (tous les exemples PDF, le CSV Trade Republic et le .zip Fortuneo
d'Arthur, les CSV et XML de courtiers) sont restées **identiques**.

* **Nombres** (`cto._nombre`) : « 1,234.56 » à l'américaine (le séparateur le
  plus à droite est la décimale ; avant, lu 1,23456 !), « 1.234.567 »,
  « −12,50 » (signe moins typographique), « (12,50) » et « 12,50- »,
  « 12,50 € », « USD 1,234.56 », espaces insécables ou fines.
* **Dates** (`_date_fr`) : jour et mois sur un chiffre, année sur deux
  (« 08/10/24 », c'est ce qu'écrit Excel en « Texte Unicode »), « Mar 26,
  2024 », « 01 juil. 2024 », date impossible refusée. Une colonne de dates à
  l'américaine (03/26/2024) est reconnue (`_ordre_dates`) : avant, ses dates
  étaient lues fausses (2024-26-03) sans rien dire.
* **Texte des PDF** (`_norm_texte`) : espaces insécables et fines, signe
  moins, apostrophe courbe, accents décomposés, ligatures. Un PDF est relu en
  mode `layout` de pypdf (mots replacés d'après leur position) quand le
  premier texte ne donne rien. PDF sans texte (scanné, photo) : message clair.
* **Tableaux** : séparateur choisi sur les 30 premières lignes ; ligne
  d'en-tête cherchée parmi elles (titre, numéro de compte, période au-dessus :
  avant, rien n'était reconnu) ; UTF-16 (« Texte Unicode » d'Excel) ; page
  HTML livrée en « .xls » ; **.xlsx avec de vraies cellules date** (avant,
  « 45377 » au lieu d'une date : aucune ligne lue) ; **.xls d'Excel 97-2003**
  (`_lignes_xls` : conteneur OLE2 et format BIFF8 lus sans bibliothèque,
  textes partagés coupés entre enregistrements compris ; 2 500 lignes avec
  accents, grec et japonais relues à l'identique, fichiers d'Excel et de
  LibreOffice) ; **.ods** de LibreOffice (`_lignes_ods`) ; zip dans un zip,
  zip protégé (message), fichiers cachés de macOS ignorés. Plus de noms de
  colonnes reconnus (« Quantité exécutée », « Ticker », « Prix par action »…),
  jamais « Cours de change » pour un cours. Le cours du fichier est gardé tel
  quel (au millième).
* **Contrôle des chiffres** (`_Lot.ajoute`) : parts × cours doit donner le
  montant (à 0,5 % près) ; sinon l'aperçu affiche « chiffres à vérifier »
  (cas typique : « 10 250,00 » lu comme un seul nombre). Aucun des vrais
  documents ne déclenche ce message.
* **Trade Republic en PDF** (`_traderepublic`) : relevé de transaction d'un
  ordre, investissement programmé (origine « plan »), vente, dividende ou
  distribution (net en euros, date de paiement), versement. 12 avis réels sur
  12 conformes au corrigé. Le relevé de compte mensuel n'est pas lu (ni cours
  ni frais par ordre) : un message renvoie vers l'export CSV.
* **Lecteur universel d'avis d'opéré** (`_avis_generique`), pour une banque
  sans règle propre : un seul ISIN, avis en français, rubriques cherchées par
  leur nom (« Quantité : 10 », tableau dont les noms de colonnes sont sur une
  ligne et les nombres sur la suivante, « ACHAT de 25 … au cours de … »,
  ligne « titre parts cours montant »). Quand les espaces séparent à la fois
  les milliers et les colonnes (« 12 332,181 3 986,17 »), c'est l'accord des
  chiffres qui choisit le découpage (`_decoupages`, `_accord`). **Rien n'est
  repris si parts × cours ≠ brut ou brut ± frais ± taxe ≠ net** ; l'opération
  porte l'alerte « lu par le lecteur universel ». Dividende : date de
  paiement (jamais celle du détachement) et net nommé comme tel, en euros.
  Résultat : 100 avis fabriqués sur 100 justes, Keytrade et Scalable en
  français lus justes, **aucune** lecture fausse sur les documents d'autres
  banques (allemand, néerlandais, assurance vie : « non reconnu »).
* **Documents qui ne sont pas des opérations** : relevé de compte Trade
  Republic, IFU, relevé de portefeuille : un message dit ce que c'est et quoi
  importer à la place.

## Sortie de `releves.lire`

Celle de `cto.lire_csv_tr` (`trId, date, quand, type, origine, isin, nom, nomLong,
classe, qty, cours, montant, frais, taxe, alerte`), plus `banque`, et trois types :

* **Versement / Retrait** (`origine: "especes"`, montant) : versés dans `S.depots`
  sur le PEA ; **ignorés sur un CTO** (ses versements se déduisent des ordres).
* **Taxe** (`origine: "taxe"`, ISIN, montant) : taxe sur les transactions
  financières envoyée à part (avis récapitulatif Fortuneo, ligne « TAXE TRANSACT
  FINANCIERES » de Bourse Direct). L'interface l'ajoute aux frais **et** à `taxe`
  du nouvel ordre du même titre le même jour. Sans ordre importé avec elle (ordre
  déjà saisi, ou absent du lot) : non reprise, pour ne pas la compter deux fois.

`montant` d'un ordre = parts × cours en euros (brut) ; `frais` = courtage et
autres frais ; `taxe` = taxe française (ou étrangère chez Bourse Direct).
`trId` = la référence de la banque quand elle existe, sinon une empreinte des
champs (le même fichier relu donne les mêmes identifiants : pas de doublon).
Les opérations de plusieurs fichiers sont fusionnées sans doublon (même `trId`)
et triées par date puis heure.

Fichiers : PDF (`%PDF-`), Excel `.xlsx` (lu sans bibliothèque : `zipfile` + XML),
Excel `.xls` (OLE2 + BIFF8, sans bibliothèque), LibreOffice `.ods`, page HTML
contenant un tableau, XML Flex d'IBKR, sinon texte (UTF-16, UTF-8, puis cp1252)
lu comme CSV, séparateur deviné. Un .zip est ouvert (deux niveaux au plus).

## Règles par banque, et pièges vus

### Fortuneo (Arkéa Direct Bank)

* **CSV « Historique des opérations de bourse »** (le chemin le plus simple,
  4.4.5) : un .zip, lu tel quel (Pilote ouvre les archives ; un .xlsx, lui
  aussi un zip, se reconnaît à son dossier `xl/`). CSV en cp1252, `;`,
  décimales au point, montants signés : `libellé;Opération;Place;Date;Qté;
  Prix d'éxé;Montant brut;Courtage/Prélèvement;Montant net;Devise;`.
  L'en-tête du prix s'écrit **« Prix d'éxé »** : la colonne se repère par son
  début (« prix »). Opérations : « Achat Comptant », « Vente comptant » (suivi
  d'espaces), « Encaissement coupons intérêt/dividende » (dividende net),
  « OST de création de coupons - Détachement coupon optionnel » (**ignoré** :
  même montant, deux jours avant l'encaissement, ce serait un doublon),
  « Transfert de portefeuille entrant » (**ignoré** : titres arrivés d'une autre
  banque à 0 €, l'achat d'origine vient de l'ancienne banque ; les compter
  ferait un PRU nul). **Pas d'ISIN** : la cotation se cherche par le nom (voir
  « Sans ISIN »). Pas de versements dans ce fichier.
* **Avis d'opérations** : un bloc par titre (« ACTION : ORANGE (FR0000133308) »,
  « TRACKER : … », « OPCVM : … »), une ou plusieurs exécutions par bloc (ordre
  fractionné). **La référence ne suffit pas comme identifiant** : deux ordres du
  même avis la partagent parfois (Crédit Agricole et Orange, 04/07/2023 : le
  second disparaissait) → `fo:<référence>:<ISIN>:<quantité>`. Frais = courtage
  + droits d'entrée/sortie (fonds).
* **Taxe sur les transactions** : avis récapitulatif à part (le montant arrive
  parfois avant le libellé « Montant de la TTF: »).
* **Avis d'encaissement coupon** : dividende net.
* **Relevé « LIQUIDITES sur PEA »** (annuel) : seulement VERSEMENT et RETRAIT,
  année lue sur « Ancien solde au » ; ses lignes ACHAT n'ont pas d'ISIN (elles
  viennent des avis d'opéré).
* **Résultat d'OST** (souscription) : un achat au montant net.

### BoursoBank

* Reconnue au pied de page (Boursorama, BoursoBank) **ou à la forme de l'avis**
  (« OPERATION DE BOURSE … Code ISIN : ») : les exemples anonymisés ont perdu le nom.
* Ligne « date quantité nom », « Code ISIN : », « Cours exécuté : » ou « Valeur
  liquidative : ». Net : dernier montant de la ligne qui suit « Montant net au
  débit/crédit de votre compte ». Ligne « brut, commission, [taxe], net » : la
  3ᵉ valeur sur quatre est la taxe française.
* Titre étranger (« ETR ») : la **contre-valeur en euros** de l'avis donne le
  brut, le cours en euros = brut ÷ parts.
* SOUSCRIPTION / REPRISE de SICAV ou de FCP = achat / vente.
* Coupons : une ligne par titre, le dernier montant est le net client.

### Bourse Direct

* Relevé ligne par ligne : « date TYPE ISIN nom montant », puis QUANTITE, COURS
  (déjà en euros pour un titre étranger), BRUT, COURTAGE, TVA, TAXE ETRANG, Heure.
  Frais = |net − brut| − taxe étrangère.
* COUPONS = dividende net ; INVESTISSEMENT ou VIREMENT ESPECES = versement ;
  TAXE TRANSACT FINANCIERES = taxe ; DROITS DE GARDE et inconnus : listés.

### Saxo (PDF)

* Rapports de trade, de dividende, de virement, en **anglais ou en allemand**
  (pas d'exemple en français). Nom du titre parfois sur la ligne suivante (vide :
  l'import prend celui de Yahoo). Nombres « 1.234,56 », « 16'997.84 » (Suisse),
  « 19.50 ». Frais = |net| − |montant des titres|.
* Montants dans la **devise du compte** (« Currency: CHF ») : convertis en euros.

### Degiro (rapport des transactions en PDF)

* Trois variantes : montants suivis de « EUR » (2022, 2024) ; échanges de titres
  à 00:00 sans frais ni lieu d'exécution ; format 2025 sans devise après les
  montants, dans la devise du compte (« Montant CHF » dans l'en-tête).
* Frais = |montant − montant négocié| : en 2025, la colonne « frais AutoFX »
  **n'est pas retirée** du net (898,75 − 4,60 = 894,15 CHF pour ASML).
* Titre coté en euros : son montant en euros (exact) ; sinon conversion.

### Tableurs

* **Trade Republic** : `cto.lire_csv_tr` (fiche du CTO).
* **Degiro, relevé de compte** (Account.csv) : dividendes moins la retenue à la
  source, versements. Les ordres viennent du rapport des transactions (montants
  en euros). Le CSV « Transactions » de Degiro passe par le lecteur universel :
  **ses colonnes ne sont publiées nulle part, non essayé sur un vrai fichier**.
* **Interactive Brokers** : Flex Query en CSV (colonnes Buy/Sell, TradeDate,
  ISIN, Quantity, TradePrice, TradeMoney, CurrencyPrimary, IBCommission… ; et
  Type/Amount pour les dividendes, nets de la retenue) ou en XML (`<Trade>`,
  `<CashTransaction>`). `fxRateToBase` convertit vers la devise **du compte** :
  utilisé seulement si `<AccountInformation currency="EUR">` (l'exemple 1 est en
  dollars canadiens vers une autre devise) ; sinon cours du jour.
* **Saxo CSV** : « Buy 3 @ 139.74 USD », montant, taux de conversion.
* **Trading 212** : Total en euros frais compris, taxe française à part.
* **Lecteur universel** (`colonnes_auto`) : synonymes d'en-têtes en français,
  anglais, néerlandais, allemand ; une colonne d'ISIN ou de dates se reconnaît
  aussi à son contenu (une colonne « Titre » remplie d'ISIN devient l'ISIN).
  Sans colonne « sens », quantité négative = vente. Il manque la date, la
  quantité, l'ISIN ou le nom, ou le cours ou le montant : l'interface demande
  les colonnes (`aChoisir`, étape « colonnes » de la fenêtre).

### Sans ISIN (CSV de Fortuneo)

* Le titre se repère par son nom dans l'aperçu (`_ctoImpCle` : « NOM:<nom> »,
  colonne ISIN « — »), jamais enregistré comme ISIN de la position.
* `/isin` accepte un nom sans ISIN : Yahoo ne trouve rien sur le nom complet
  (« Amundi PEA Emergent (MSCI Emerging) ESG Transition UCITS ETF - S EUR
  ACC »), d'où `_variantes_nom` (partie avant « - », sans UCITS/ETF/ACC…, 5,
  4 puis 3 mots). Plusieurs parts du même fonds sortent (PNAS.PA et PUST.PA,
  PEMS.PA et PAEEM.PA) : la **vérification par les prix payés** tranche.
* **Un ticker que le compte utilise déjà** (ligne ouverte, vendue, ou ordre)
  passe devant parmi les candidats vérifiés : sans ISIN, pas de place du pays,
  et Saint-Gobain partait sur GOB.DE quand le PEA le suit en EPA:SGO ; ses
  ventes auraient été comptées deux fois. Vaut aussi avec ISIN.

### Autre devise que l'euro

Cours du relevé quand il le donne (BoursoBank, Degiro, Bourse Direct, IBKR sur
compte en euros), sinon **clôture du jour** de la paire `EUR<devise>=X` chez
Yahoo (`_vers_eur`, cache par devise et date le temps d'une lecture).

## Interface

* Bouton **« Importer des relevés »** dans l'onglet Transactions (PEA et CTO) et
  dans la barre du CTO. Fenêtre `ov-cto-import` : choix d'un ou plusieurs
  fichiers, colonnes si besoin, aperçu, « Importer ». Rien n'est écrit avant ;
  un seul `pushUndo` (Retour annule tout l'import).
* **Déjà là** (`ctoImportDeja`) : même `trId` ; ou même opération saisie à la
  main, sur le **ticker normalisé** (un PEA saisi à la main n'a pas d'ISIN) :
  même jour, même sens, même quantité, cours à 0,5 % près (cours tapé arrondi) ;
  même montant pour un dividende ou un versement.
* Une ligne déjà suivie sous le ticker résolu (sans ISIN) est « déjà suivie » :
  sa cotation ne change pas.
* Vérifié le 12/10/2026 sur une copie de ses données (banc d'essai) : PEA, 5 PDF
  Fortuneo fabriqués (achat de 2 titres, taxe, dividende, liquidités, et l'achat
  Saint-Gobain du 10/03/2025 qu'il avait saisi à la main) → 2 ordres frais et
  taxe compris (Crédit Agricole 5 083,45 €), 7 versements (22 000 €), 1 dividende,
  Saint-Gobain « déjà dans Pilote » ; Retour : PEA identique ; second import : 0.

## Dépendance pypdf

`pypdf==5.9.0` dans `requirements.txt` (la 5.9.0 est la dernière qui accepte
Python 3.8, celui du poste de dev ; la CI est en 3.11) et `"pypdf"` dans les
`hiddenimports` de `build/pilote.spec` (import paresseux dans `texte_pdf`).
**Branche mac** : ajouter aussi `"pypdf"` à `pilote-mac.spec` à la fusion.
