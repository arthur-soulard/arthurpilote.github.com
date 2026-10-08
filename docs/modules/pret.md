# Module Prêt étudiant

Fiche détaillée tirée de `CLAUDE.md`, qui garde les règles générales (dont les cinq choses à ne jamais casser).

## Module Prêt étudiant (pret.json)

API Python : `load_pret()` / `save_pret()`. Capitalisation annuelle de l'AV et moteur
événementiel du Livret A repris à l'identique de l'ancienne app standalone (abandonnée).

* pret        : `{montant, date_deblocage, date_premier_remboursement,
                duree_remboursement, mensualite}`
* pea.achats  : `{id, date, ticker, montant, quantite, cours_achat}`
* pea.ventes  : `{id, date, ticker, quantite, cours_vente, montant (crédité)}`
  → PRU pondéré sur les achats, plus-value réalisée = crédité − qté × PRU,
    plus-value latente sur les parts restantes
  → **ces deux listes ne se remplissent plus** : voir ci-dessous. Elles restent lues
    pour un ordre qui y aurait été saisi avant.
* av.contrats : `[{id, label, frais_versement, taux_annuels:[{annee,taux}], depots:[{id,date,montant,note}]}]`
  → MULTI-CONTRATS, chacun avec ses propres taux
  → **Frais sur versements** (08/10/2026, 4.3.26) : `frais_versement` = % pris sur
    chaque dépôt avant placement, réglé dans la fenêtre du contrat (crayon).
    `prAvFraisDepot` (arrondi au centime par dépôt), `prAvDepotInvesti` : les
    intérêts courent sur l'**investi**, pas sur le versé. `depose` = argent sorti du
    prêt (frais compris, c'est lui qui compte dans les liquidités), `investi` =
    versé − frais, `valeur` = investi + intérêts. Les frais vont dans `frais_total`
    (« Frais payés », « Gains nets »), comme les frais d'ordre du PEA ; la colonne
    « Investi » de « Performance par enveloppe » est nette de frais, comme celle du PEA.
    Afer (vérifié sur afer.fr/frais et la notice Afer Génération de janvier 2025,
    tableau des frais Multisupport de juin 2025) : 0,5 % sur un versement en fonds
    euros (EuroGénération, Fonds Garanti), 0 % en unités de compte ; 20 000 € versés
    → 19 900 € investis. Droit d'adhésion de 20 € payé une seule fois par adhérent,
    tous contrats Afer confondus : rien à compter pour Arthur, déjà adhérent. Les
    frais de gestion annuels ne s'ajoutent pas : le taux publié par l'Afer, celui
    qu'on saisit, en est déjà net.
* liv         : `{label, taux_history:[{id,date,taux}], mouvements:[{id,date,type,montant,note}]}`
* frais_recurrents : prélevés le MÊME JOUR chaque mois (jour pris sur `date_debut`,
  ramené au dernier jour du mois quand il n'existe pas — voir `prAddMonths`)
* frais_rembourses : `{id, date, montant, label}`, frais que la banque a rendus
  (ex. un mois de carte offert), déduits des frais (4.3.4)

**Les frais se comptent au fil des mois (4.3.4).** Jusque-là, les 120 prélèvements de
la carte (6,05 €) comptaient dès le premier jour : 726 € de frais, et autant en moins
dans les liquidités et les gains. Désormais `prAllFrais(jusqua)` ne prend que ce qui
est daté d'aujourd'hui ou avant ; le reste s'affiche « à venir » dans Paramètres.
* **Changement de tarif** : `paliers: [{id, date, montant}]` sur le frais récurrent,
  nouveau montant à partir de cette date (`prTarif`). Ne jamais modifier `montant`
  pour un changement de tarif : ce serait réécrire les prélèvements passés.
* `nb_occurrences` 0 ou vide = frais sans fin (`prExpandRecurrent` s'arrête alors à
  la date demandée ; sans date, il ne renvoie rien, jamais une boucle infinie).
* Frais remboursés : même règle, ceux datés d'aujourd'hui ou avant. Le bouton
  « flèche retour » d'un frais récurrent pré-remplit un remboursement (montant du jour).

**Tout au réel, à sa date (4.3.4, audit du module).** Versements, remboursements, dépôts
d'assurance vie, mouvements du Livret A et ordres du PEA ne comptent qu'à partir de
leur date (`prPasse` / `prAVenir`) ; ce qui est daté plus tard s'affiche « à venir ».
Le versement de 15 000 € annoncé pour le 05/10 comptait déjà comme reçu le 28/09.
* `capital_du = prCapitalDu()` (versé − remboursé). `mensualites_restantes` reste
  calculé sur le **montant emprunté** : sur le capital dû, il tomberait à 30 au lieu
  de 60 avant la 2e tranche.
* `prTranchesTxt(o, court)` : « 15 000 € versés sur 30 000 € empruntés, 15 000 €
  attendus le … ». Le champ « Date du 1er déblocage » n'est qu'indicatif : ce sont
  les versements qui comptent (un par tranche).
* **Cours** : `prCours(t)` prend le cours du PEA (`getVar`, rafraîchi toutes les
  3 min), `_prQuotes` ne sert plus qu'aux titres que le PEA ne suit pas. Avant, le
  prêt chargeait ses cours une fois par session : sa valeur vieillissait.
* **Livret A par quinzaines** (`prLivretState`) : un dépôt rapporte à partir de la
  quinzaine qui suit, un retrait cesse dès le début de la sienne, taux / 24 par
  quinzaine terminée, intérêts au capital le 1er janvier. Vérifié : 1 000 € le
  10/01 à 3 % → 23 quinzaines, 28,75 €. Remplace le calcul au jour près.
* **Retour** : `prPushUndo()` met un instantané `{PR}` dans la même pile que le PEA
  (`undoLast` le reconnaît) ; posé par `prSubmit` (retiré si la saisie est refusée)
  et par chaque suppression.
* **Alertes** (`prAlertesHtml`) : versements saisis > montant emprunté ; placé +
  remboursé > versé à ce jour. Les frais bancaires n'y entrent pas : la carte peut
  être prélevée avant l'arrivée du prêt.
* Graphique de répartition aux couleurs du thème (`carnetChartColors`, `CLRS`).

Les cours passent par le serveur local (`/cours`), pas de second proxy Yahoo.

### PEA du prêt = ordres du PEA cochés « argent du prêt »

On n'a qu'un PEA : les achats faits avec le prêt en font partie. Avant, il fallait les
saisir deux fois (onglet PEA et onglet Prêt). Désormais un ordre n'existe **qu'une
fois**, dans `S.transactions`, avec `pret: true` quand la case « Payé avec l'argent du
prêt étudiant » est cochée (fenêtres `ov-pos` et `ov-tx`, champs `f-pret` / `t-pret`,
absente pour un dividende). `prPeaOrdres()` lit ces transactions et les convertit
(`prYahoo` : `EPA:WPEA` → `WPEA.PA` ; montant = qté × cours ± frais, comme
`computeCash`). **Aucune copie dans `pret.json`** : pas de doublon possible, et une
modification, un décochage, une suppression ou le bouton Retour se voient partout.

* Les ordres non cochés n'entrent jamais dans les calculs du prêt.
* **Ordre payé en partie avec le prêt** (08/10/2026) : sous la case, « dont … €
  pris sur le prêt » (« rendus au prêt » pour une vente), champs `f-pret-mt` /
  `t-pret-mt`, enregistré dans `pretMontant`. Vide ou égal à l'ordre : l'ordre
  entier, pas de `pretMontant`. Le prêt détient alors la même part des parts et
  des frais (`prPartOrdre` = `pretMontant` / montant de l'ordre, `prTotalOrdre`) :
  117,28 € d'un achat de 183,07 € → 16,0157 parts sur 25. Cas d'origine : le
  07/10, 573,02 € d'ETF achetés avec 500 € du prêt et 73,02 € déjà en espèces ;
  tout coché, le prêt comptait 15 073,02 € placés pour 15 000 € reçus.
  Fenêtre « Passer un scénario » : un seul montant (`sop-pret-mt`), réparti entre
  les ordres au prorata, le dernier prend le reste (somme juste au centime).
  Le champ n'apparaît que case cochée, en CSS (`label:has(…:not(:checked)) + .pr-part`),
  parce que la case est aussi cochée par programme (`prAchatViaPea`, `editTx`).
* « + Achat » / « Vente » de l'onglet Prêt ouvrent les fenêtres du PEA, case cochée
  (`prAchatViaPea`, `prVenteViaPea`) ; le crayon d'un ordre ouvre `editTx`. Pas de
  corbeille côté Prêt : supprimer un ordre du PEA depuis là surprendrait.
* Vente cochée : refusée au-delà des parts achetées avec le prêt (`prVentePretOk`,
  qui compte la part du prêt d'une vente partielle).
* `persist()` appelle `prRefreshIfVisible()` : l'onglet Prêt ouvert suit le PEA.
* Étiquette « Prêt » sur la ligne dans PEA › Transactions.
* Patrimoine : rien ne change et rien ne doit changer. La ligne PEA vaut le PEA
  **entier** (`_peaPv.total`), parts du prêt comprises ; la « valeur du portefeuille »
  du prêt n'est ajoutée nulle part. Ne jamais créer de compte « placements du prêt » :
  PEA, AV et Livret A sont déjà comptés par leurs propres lignes.
