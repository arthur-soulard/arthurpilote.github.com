# Module Mes comptes

Fiche détaillée tirée de `CLAUDE.md`, qui garde les règles générales (dont les six choses à ne jamais casser).

## Module Mes comptes (finances.json)

Catégories et sous-catégories **portent chacune un emoji** (`icon`), affiché partout :
liste des transactions, sélecteurs, camembert, top de l'année, récurrents.

* `finCatIcon(c)` / `finSubIcon(s)` avec repli (🏷️ dépense, 💰 revenu, • sous-catégorie)
* `finPickIcon(current, titre, callback)` ouvre la modale `ov-fin-icon` (palette + saisie libre)
* `finances.backfill_icons()` côté Python donne un emoji aux fichiers créés avant la 4.1.2,
  en reconnaissant les libellés du jeu par défaut
* **Emoji deviné d'après le libellé (4.2.7)** : `FIN_ICON_GUESS` (mots sans accents ni
  majuscules, première règle qui correspond) via `finGuessIcon(nom)`. Appliqué à la
  création d'une catégorie ou sous-catégorie sans emoji, et au chargement par
  `finBackfillIcons()` sur tout ce qui n'a pas d'emoji ou a gardé le générique 🏷️ / •
  (enregistré ensuite). Une sous-catégorie au libellé inconnu prend l'emoji de sa
  catégorie. 💰 n'est pas considéré comme générique : il peut avoir été choisi.
* **« Autres dépenses » / « Autres revenus » toujours en dernier** : `finCatsOrdered(type)`
  (sélecteurs de la saisie et des récurrents, filtre, liste des catégories, légende du
  camembert). Tri à l'affichage : le fichier garde son ordre, et une catégorie créée
  plus tard se range aussi avant « Autres ». Le top de l'année reste trié par montant.
* **Aide à la saisie (4.2.7)**, dans la fenêtre « Nouvelle dépense / Nouveau revenu » ;
  les deux lisent l'historique du même type (`finTxModels`, un modèle par libellé sans
  accents ni casse, sa saisie la plus récente) et ne font que **pré-remplir** montant,
  catégorie, sous-catégorie et source : la date reste celle du jour, rien n'est
  enregistré sans « Enregistrer », la saisie libre reste entière.
  - « Dépenses fréquentes » (`finRenderFreq`) : les 8 libellés les plus saisis sur
    douze mois, les plus récents d'abord à égalité. Automatique, rien à configurer
    (choix d'Arthur). Masquée en modification.
  - Suggestions sous le libellé (`finAcUpdate`) : ceux qui commencent par la saisie,
    puis ceux dont un mot commence par elle. ↑ ↓ Entrée, Échap ferme la liste sans
    fermer la fenêtre.
  - Après un choix, le montant est sélectionné : il se remplace d'une frappe (courses).

## Changements en lot (demandés par Arthur le 01/11/2026)

Avant, tout se faisait une transaction à la fois, et une catégorie utilisée
ne se supprimait pas (bouton grisé). Bloc « CHANGEMENTS EN LOT » après les
catégories dans index.html. Tout se défait par « Annuler » dans le toast qui
suit (10 s, `finToastAnnuler`) : l'état d'avant (`finSnapshot` : catégories,
transactions, récurrents) est gardé en mémoire seulement.
* **Supprimer une catégorie ou sous-catégorie utilisée** (`finDeleteCat`,
  `finDeleteSub`) : on choisit où vont ses transactions **et récurrents**
  (`finChoisirDest`), puis elle est supprimée. C'est aussi la façon de fusionner.
* **Déplacer une sous-catégorie** dans une autre catégorie du même type
  (`finMoveSub`, flèche ↱). Les numéros de sous-catégorie sont propres à chaque
  catégorie : elle y reçoit le suivant, ou rejoint celle du même nom (sans
  accents ni casse).
* **Cases à cocher** dans la liste (`_finSel`), barre `#fin-selbar` : catégorie
  (dépenses seules ou revenus seuls), source, date (un mois plus tard ou plus tôt,
  même jour ramené au dernier du mois, ou un jour fixe : `finDecalerMois`),
  supprimer. Une case cachée par un filtre ou un autre mois est décochée : une
  action ne touche que ce qu'on voit. Filtre « Tous les mois »
  (`#fin-filter-periode`) pour chercher dans tout l'historique.
* **« Faire pareil pour les autres ? »** (`finProposerPareil`) : après avoir
  changé la catégorie d'une transaction, Pilote propose la même aux autres
  transactions et récurrents du même libellé et du même type. Rien sans « Oui ».
  Pas de règles automatiques (libellé → catégorie) : écartées pour rester simple.

## Importer (JSON ou CSV d'une autre appli, 4.4.40)

Bouton « Importer » de l'en-tête du mois (`finImportLire`). Tout se fait en JS,
rien ne passe par Python avant l'enregistrement habituel (`finPersist`).
* JSON : le premier tableau d'objets (racine, `transactions`, `expenses`…) ; un
  `finances.json` de Pilote garde ses catégories (`categoryId` traduit en nom).
* CSV : séparateur deviné (`;`, `,`, tabulation), colonnes reconnues par leur
  nom (`FIN_IMP_COLS` : date, montant ou débit/crédit, libellé, catégorie,
  sous-catégorie, type, source, note). Dates JJ/MM/AAAA, ISO ou horodatage.
  Depuis la 4.4.61 : une colonne « Mois » sert de date, un mois seul
  (AAAA-MM) est rangé au 1er, et une unité entre parenthèses est ignorée dans
  un nom de colonne (« Montant (€) »). Avant, un tel fichier (export d'un
  tableur de budget par mois) donnait « Aucune transaction reconnue ».
* Sens : la colonne type, sinon le signe ; sans aucun négatif ni colonne
  crédit, tout est une dépense.
* Catégorie, sous-catégorie et source retrouvées par leur nom, sinon créées.
  Doublon (même date, type, montant, libellé) ignoré. Aperçu avant « Importer ».
  Depuis la 4.4.70, ce chemin ne sert plus qu'aux JSON et aux CSV d'une autre
  appli de budget (colonne catégorie, aucune banque reconnue) : tout autre
  fichier passe d'abord par l'import des relevés ci-dessous.

## Import des relevés de banque (4.4.70, demandé par Arthur le 12/11/2026)

« Le top 2 des fonctionnalités après le PEA. » Trois façons de faire, toutes
gardées : importer et laisser Pilote classer ; ranger dans ses propres
catégories (Pilote les retrouve par leur nom et des synonymes) ; continuer à la
main. Bouton « Importer un relevé » de l'en-tête du mois (plusieurs fichiers à
la fois), et tuile d'accueil `fin-releve` (« Relevés de banque » : nombre à
classer, date du dernier import, boutons Importer et Classer).

**Lecture** (`src/budget_releves.py`, pont `Api.budget_lire_releve`) : CSV
(séparateur, encodage, lignes de compte avant l'en-tête, libellés sur
plusieurs lignes, ligne de total, fichier sans en-tête de LCL), Excel .xlsx,
.xls et page HTML nommée .xls, .ods, OFX 1 (SGML) et 2 (XML), QIF, CAMT.053,
zip. Lecteurs de fichiers repris de `releves.py`. Colonnes reconnues par leur
nom (`_COLS`) : date d'opération préférée à la date de comptabilisation (le
jour de l'achat), montant signé ou Débit / Crédit, frais déduits (Revolut),
lignes en attente, refusées ou annulées ignorées (statut), libellé + tiers +
détail réunis sans redite (le libellé abrégé de la Société Générale cède la
place à son détail). Trade Republic : seules les lignes d'espèces du compte
(cartes, virements) ; ses ordres de bourse restent à l'import du PEA ou d'un
CTO. Un PDF est refusé avec la marche à suivre (télécharger le CSV ou l'OFX).

Formats d'après les exemples publiés par d'autres projets libres : Carbure
(PR 116 : Banque Postale, SG, Crédit Mutuel, Fortuneo, Caisse d'Épargne, BNP,
N26 actuel et ancien, Revolut, Qonto), My-PiggyBank (PR 70) et gleba (PR 43).
Pas d'exemple public pour LCL, Shine, Lydia, BforBank, Monabanq : le lecteur
universel et l'OFX les couvrent, à vérifier sur un vrai fichier.

**Libellé lisible** (`nettoyer`) : préfixes bancaires (CB, CARTE X1234,
PRLV SEPA, FACTURE CARTE DU 111026…), dates, numéros de carte, références de
prélèvement (ECH/…, ID EMETTEUR/…), prestataires de paiement (PAYPAL *, SUMUP *)
retirés ; un virement garde son tiers (« VIR SEPA RECU /DE EMPLOYEUR SA /MOTIF
SALAIRE » -> « Employeur SA »). Le libellé de la banque reste dans la
transaction (`libelleBanque`).

**Classement** (`classer`), le premier qui répond :
1. l'historique de l'utilisateur (libellé déjà classé, mêmes mots) : c'est
   ainsi que Pilote apprend, sans écran de règles ;
2. les marchands connus (`src/budget_marchands.py`, quelque 1 700 enseignes
   et mots en motifs, du plus précis au plus général ; un virement vers
   « PAUL » n'est pas la boulangerie Paul : `_PAR_VIREMENT`) ;
3. la catégorie donnée par la banque (BoursoBank, BNP, Caisse d'Épargne, Qonto,
   QIF), retrouvée dans celles de l'utilisateur ;
4. le code commerçant de la carte (MCC), quand le fichier le donne ;
5. sinon « À classer ».
Une notion absente des catégories de l'utilisateur n'est jamais forcée
ailleurs : la ligne reste à classer et l'aperçu propose de créer la catégorie
(« Impôts & taxes », « Aides & allocations »…, `propose`). Un retrait sans
catégorie « Retraits » va dans Autres dépenses › Divers. Un revenu chez un
marchand de dépense (carte, prélèvement) est un remboursement ; un virement
reçu d'une mutuelle aussi ; un virement reçu « MOTIF LOYER » d'un particulier
ne l'est pas.

**Ni dépense ni revenu, pas cochés** : virement vers son épargne ou entre ses
comptes (livret, PEA, Trade Republic, top-up Revolut…, ou deux virements
opposés de même montant dans deux relevés importés ensemble) ; total d'une
carte à débit différé quand ses achats sont aussi dans l'import (sinon
signalé) ; opération déjà saisie à la main (même montant, même sens, à trois
jours près). Une opération déjà importée (empreinte `releve` : date, montant,
libellé de la banque, rang) n'est pas reproposée.

**Aperçu** (`finReleveApercu`) : chaque ligne avec sa catégorie (liste « À
classer » + catégories et sous-catégories), une icône dit d'où elle vient
(historique, marchand, banque, code commerçant, toi ; la raison au survol).
Changer une ligne change aussi les autres lignes du même libellé que
l'utilisateur n'a pas touchées. Filtres Toutes / À classer / Pas cochées.
Rien n'est écrit avant « Importer N opérations » ; « Annuler » dans le toast
(10 s, `finToastAnnuler`) défait tout l'import.

**À classer ensuite** : une opération importée sans catégorie entre dans
« Autres dépenses / revenus » avec `aClasser` = l'id de cette catégorie.
`finAClasser(tx)` est vrai tant qu'elle y est : la ranger ailleurs, par
n'importe quel chemin (modifier, lot, « Faire pareil »), suffit, rien à
remettre à zéro. La modifier et garder « Autres » efface aussi le drapeau.
Filtre « À classer (n) » dans la liste, bandeau au-dessus avec « Les
classer ».

**Entraînement et mesure** : `tests/corpus_budget.py` fabrique des relevés
fictifs aux formats des 17 banques et formats (libellés tels que chaque banque
les écrit, encodages, lignes de compte, totaux, lignes en attente) ;
`python tests/mesurer_budget.py [n] [--validation] [--erreurs]` mesure.
Au 13/11/2026, sur 1 020 relevés (40 179 opérations) : 100 % lues (date et
montant exacts, rien d'inventé), 99,8 % bien classées, 0 % mal classées,
aucun marchand inconnu rangé à tort. **Mesure honnête** : le jeu de
validation (`corpus_budget_validation.py`, 340 relevés, autres marchands et
autres orthographes) écrit après le réglage donnait au premier passage 96,8 %
bien classées, 2,7 % à classer, 0,5 % mal classées ; 99,8 % après des
corrections générales (parapharmacie avant l'enseigne, noms collés,
« supérette »). Ces relevés restent écrits par Claude : aucun vrai relevé
public n'existe. Le premier vrai relevé d'Arthur dira le vrai chiffre.
`tests/test_budget_releves.py` garde ces seuils et les exemples publiés.
