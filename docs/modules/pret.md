# Module Prêt

Fiche détaillée tirée de `CLAUDE.md`, qui garde les règles générales (dont les six choses à ne jamais casser).

## Module Prêt (pret.json)

API Python : `load_pret()` / `save_pret()`. Capitalisation annuelle de l'AV et moteur
événementiel du Livret A repris à l'identique de l'ancienne app standalone (abandonnée).

* pret        : `{nom, montant, date_deblocage, date_premier_remboursement,
                duree_remboursement, mensualite}`

**Un seul prêt, sans échéancier calculé : décision d'Arthur du 14/10/2026.** La
4.4.17 (13/10/2026) avait rendu le module générique : plusieurs prêts, une section
chacun, taux, assurance, différé, in fine, événements, échéancier calculé
(`prEcheancier`), prêt à deux (schéma 7, liste `prets`). Retirée en 4.4.18 :
« on s'est perdu », un prêt est trop personnel pour une appli faite pour tous, et
plus il y a de tâches, plus il y a d'erreurs. Le code est revenu tel qu'en 4.4.16
(`git checkout 3704698`) ; la 4.4.17 vit dans l'historique (`327c5c5` à `06f4253`).
Ne pas la reproposer (`docs/pistes.md`). Un crédit immobilier se suit dans
Patrimoine, saisi à la main (`docs/modules/patrimoine.md`, « Biens immobiliers »).

**Retour du schéma 7 au schéma 6** (`pret._revenir_schema6`, à chaque lecture
d'un fichier qui a une liste `prets`) : le premier prêt reprend sa place à plat,
sa `premiere_echeance` redevient `date_premier_remboursement` (décalée du
différé s'il y en a un), son premier livret redevient `liv`. Ce que le schéma 6
ne connaît pas (taux, assurance, événements, autres prêts et livrets) est laissé
de côté, mais le fichier au schéma 7 est d'abord copié tel quel, une seule fois, en
`pret.plusieurs-prets-4.4.17.json`. Le fichier ne se réécrit qu'à la prochaine
modification du prêt. Vérifié le 14/10/2026 sur une copie du `pret.json`
d'Arthur : le résultat est identique, clé pour clé, à la copie d'avant la 4.4.17
(`pret.avant-plusieurs-prets.json`). Dans Patrimoine, une ligne `auto: "pret:p2"`
(prêt créé après le premier) redevient une ligne manuelle (`patrimoine.load_data`).
Un ordre de CTO marqué « payé avec le prêt » en 4.4.17 garde son badge « Prêt »
dans la liste du CTO, mais le prêt ne le compte pas : il ne lit que les ordres du
PEA (`prPeaOrdres`). Aucun chez Arthur.

**Nom libre (4.3.34).** Le module s'appelait « Prêt étudiant » ; Arthur l'a voulu
général le 11/10/2026, pour qui installe Pilote avec un autre prêt. `pret.nom` se
saisit dans « Configuration du prêt » ; vide, le prêt s'appelle « Prêt » (`prNom()`).
Ce nom s'affiche dans la barre latérale et le fil d'Ariane (`prMajNom()`, appelée
par `prRenderAll`, donc aussi après le bouton Retour), dans la fenêtre Paramètres
(éléments `.pr-nom`), sur la tuile d'accueil et sur la ligne Patrimoine (`paLabel`,
nom de cette ligne en lecture seule dans sa fenêtre). Les textes communs disent
« le prêt » (« Payé avec l'argent du prêt »). **Migration** (`pret.load_data`) :
un `pret.json` sans clé `nom` reçoit « Prêt étudiant » s'il a déjà un montant, un
versement ou un remboursement, sinon un nom vide. Elle lit le fichier **avant** la
fusion avec les défauts, qui donnerait un nom vide à tout le monde. Un vide choisi
ensuite reste vide (la clé existe). Rien d'autre n'est spécifique aux étudiants :
le module suit les versements reçus, les remboursements et l'argent placé.
* pea.achats  : `{id, date, ticker, montant, quantite, cours_achat}`
* pea.ventes  : `{id, date, ticker, quantite, cours_vente, montant (crédité)}`
  → PRU pondéré sur les achats, plus-value réalisée = crédité − qté × PRU,
    plus-value latente sur les parts restantes
  → **ces deux listes ne se remplissent plus** : voir ci-dessous. Elles restent lues
    pour un ordre qui y aurait été saisi avant.
* av.contrats : `[{id, label, frais_versement, taux_annuels:[{annee,taux}], depots:[{id,date,montant,note}]}]`
  → MULTI-CONTRATS, chacun avec ses propres taux
  → **Volontairement simple** (décidé avec Arthur le 08/10/2026, 4.3.29 et 4.3.30) :
    le montant déposé, un taux annuel par année et les frais sur versements, rien
    d'autre. Les prélèvements sociaux et les intérêts bloqués (4.3.27) et le
    simulateur de rachat (4.3.28) ont été retirés à sa demande : « on s'est compliqué
    la tâche ». Ne pas les reproposer (voir `docs/pistes.md`). Un `pret.json` saisi
    entre-temps peut garder `prelevements_sociaux`, `fidelite_fin` et `ouverture` sur
    ses contrats : le code les ignore. Les frais sur versements, retirés avec le reste
    en 4.3.29, sont revenus en 4.3.30 à sa demande : ce n'est pas une taxe, c'est ce
    qui fait coller le compte au relevé.
  → **Frais sur versements** (4.3.26, remis en 4.3.30) : `frais_versement` = % pris sur
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
    tous contrats Afer confondus : rien à compter pour un adhérent. Les
    frais de gestion annuels ne s'ajoutent pas : le taux publié par l'Afer, celui
    qu'on saisit, en est déjà net.
  → Vérifié le 08/10/2026 sur deux contrats réels, avec les taux du communiqué
    de l'assureur et leurs frais sur versements.
* liv         : `{label, taux_history:[{id,date,taux}], mouvements:[{id,date,type,montant,note}]}`
* frais_recurrents : prélevés le MÊME JOUR chaque mois (jour pris sur `date_debut`,
  ramené au dernier jour du mois quand il n'existe pas — voir `prAddMonths`)
* frais_rembourses : `{id, date, montant, label}`, frais que la banque a rendus
  (ex. un mois de carte offert), déduits des frais (4.3.4)

**Les frais se comptent au fil des mois (4.3.4).** Jusque-là, tous les prélèvements
mensuels de la carte comptaient dès le premier jour : des centaines d'euros de frais, et autant en moins
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
Un versement annoncé pour une date future comptait déjà comme reçu.
* `capital_du = prCapitalDu()` (versé − remboursé). `mensualites_restantes` reste
  calculé sur le **montant emprunté** : sur le capital dû, il tomberait à 30 au lieu
  de 60 avant la 2e tranche.
* `prTranchesTxt(o, court)` : « 5 000 € versés sur 10 000 € empruntés, 5 000 €
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
prêt » est cochée (fenêtres `ov-pos` et `ov-tx`, champs `f-pret` / `t-pret`,
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
  par exemple 60 € d'un achat de 150 € → 4 parts sur 10. Cas
  d'origine : des ETF achetés en partie avec l'argent du prêt et en partie avec
  des espèces déjà sur le compte ; tout coché, le prêt comptait plus d'argent placé que reçu.
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
