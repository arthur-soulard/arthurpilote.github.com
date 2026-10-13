# Module Prêt

Fiche détaillée tirée de `CLAUDE.md`, qui garde les règles générales (dont les six choses à ne jamais casser).

## Un ou plusieurs prêts, tous les contrats (4.4.17)

Jusqu'à la 4.4.16, le module était taillé pour le prêt d'Arthur : un seul prêt, à
0 %, dont l'argent est placé, et un capital dû calculé « versé − remboursé ».
Faux dès qu'il y a des intérêts (un prêt immobilier de 200 000 € à 3,5 % sur
20 ans : après un an, 192 969 € restent dus, pas 186 081 €), et des onglets PEA,
Assurance vie, Livret A pour qui a un prêt auto. Arthur l'a voulu générique le
13/10/2026, en cochant dans un formulaire ce qu'il fallait couvrir :

* **le contrat** : taux, assurance emprunteur, différé partiel ou total, frais de
  dossier et garantie, taux variable ou renégocié, prêt in fine, échéances
  trimestrielles ou annuelles, taux retrouvé depuis la mensualité ;
* **l'affichage** : tableau d'amortissement, coût total du crédit, courbe du
  capital restant dû, progression et date de fin ;
* **en cours de route** : remboursement anticipé (partiel ou total, indemnités),
  report et modulation d'échéances ;
* **les situations** : plusieurs prêts, prêt à deux (« ma part ») ;
* **les échéances payées** : au choix pour chaque prêt (comptées à leur date par
  défaut ; le sien reste pointé à la main, sa décision du 28/09/2026) ;
* **les placements** : plusieurs livrets, ordres d'un CTO, bilan « gains moins coût
  du crédit ».

**Pas pris** (ne pas reproposer sans raison nouvelle) : simulateur « et si je
remboursais X € » (l'aperçu de la fenêtre d'un remboursement anticipé en tient
lieu), simulateur de sortie, prêt entre proches sans échéancier, argent prêté à
quelqu'un.

## Données (pret.json, schéma 7)

```
{ prets: [{id, pret, versements, remboursements, evenements, frais,
           frais_recurrents, frais_rembourses, pea, av, livrets}],
  actif: "p2", _nid: {pret: 3} }
```

Le détail de chaque clé est en tête de `src/pret.py` (`_PRET_DEFAUT` pour le
contrat). Ids `p1`, `p2`… jamais réutilisés (`_nid`, recalculé au chargement si
le fichier a été retouché).

**Migration** (`pret._migrer_schema6`, à chaque lecture d'un ancien fichier, sans
rien perdre) : l'ancien fichier à plat devient le prêt `p1`. `date_premier_remboursement`
→ `premiere_echeance` (sans différé, c'est la même date) ; `taux` 0 (l'ancien calcul
était celui d'un prêt sans intérêts) ; `remboursements_auto` faux (ils étaient
saisis à la main) ; `placements` vrai s'il avait une assurance vie, un livret ou
des ordres saisis dans le module (et, côté JS, `prAdopterOrdres` si des ordres du
PEA sont cochés `pret: true`) ; `liv` → `livrets[0]`. Le nom « Prêt étudiant »
reste au prêt qui avait déjà un montant (règle de la 4.3.34). Un ancien fichier
jamais rempli ne donne aucun prêt. Le fichier d'origine est copié une fois en
`pret.avant-plusieurs-prets.json`, à côté. Vérifié le 13/10/2026 sur une copie
des données d'Arthur : versements, frais, assurance vie et livret identiques
avant et après, enregistrement puis relecture identiques.

**Ordres « payés avec l'argent du prêt »** : `t.pret` vaut l'id du prêt (`"p2"`),
ou `true` pour un ordre coché avant la 4.4.17, qui désigne `p1` (`prOrdrePretId`).
**Lignes du Patrimoine** : `auto: "pret"` (créée d'office par patrimoine.py) est le
prêt `p1`, `auto: "pret:p2"` le prêt `p2` (`prDeLigne`, `prLignesPatrimoine`).

## L'échéancier se calcule (prEcheancier)

Rien ne se saisit échéance par échéance : le tableau d'amortissement se déduit du
contrat, des versements de la banque et des événements. Fonctions pures, en tête
du bloc : `prEcheancier(L)`, `prTauxDepuisEcheance`, `prAnnuite`,
`prNbEcheances`, `prAssuranceEch`, `prFluxDeblocage`.

* Les échéances tombent tous les `periodicite` mois, le même jour que la 1re
  (`prAddMonths`, 31 → 30 juin → 30 septembre).
* **Différé** (`differe_mois`, compté depuis la 1re échéance) : partiel, on paie
  intérêts et assurance ; total, l'assurance seule et les intérêts s'ajoutent au
  capital. Puis `duree_remboursement` mois d'amortissement.
* **Échéance constante** : hors assurance, ou assurance comprise quand
  l'assurance est prise sur le restant dû et « comprise » (cas du Crédit Mutuel
  d'Arthur : … %/an du restant dû redonne au centime sa fiche, … €, la
  dernière à … €, … € d'assurance sur 60 mois). **In fine** : intérêts
  seuls, le capital à la dernière.
* **Arrondis de banque** : échéance, intérêts et assurance au centime (`prCts`,
  qui arrondit 4,755 à 4,76 comme une banque, là où un calcul en flottants donnait
  4,75) ; la dernière échéance solde le capital.
* **Tranches** : une tranche versée pendant le différé porte intérêt au prorata des
  jours ; tout le montant emprunté est dû au début de l'amortissement, versements
  saisis ou non (… € dont … € versés : … € par mois sur 60 mois, pas … €).
* **Événements** (`L.evenements`) : changement de taux (échéance recalculée, ou
  même échéance et durée ajustée), remboursement anticipé (après l'échéance du même
  jour ; durée réduite, échéance réduite ou tout solder ; indemnités comptées dans
  le coût), report d'échéances (partiel ou total, la durée s'allonge), modulation
  (nouvelle échéance, la durée suit). Un événement daté après la fin, ou une
  échéance qui ne couvre pas les intérêts, est rendu dans `ignores` ; la fenêtre
  le refuse avant (`prEvErreur`).
* **Retrouver le taux** : bissection sur le taux qui donne la mensualité annoncée,
  assurance comprise telle que saisie. Sans assurance saisie, le taux trouvé
  l'inclut (dit dans le message).

**Vérifié par `testsEcheancier()`** (console) : 28 vérifications, valeurs
attendues calculées à part en Python (boucles écrites cas par cas, intérêts en
décimal exact), plus la fiche de banque d'Arthur. Prêt immobilier, 0 %, différé
total, in fine, trimestriel, anticipé (durée, échéance, total), changement de
taux (deux modes), report partiel et total, modulation, assurance (trois modes),
tranches au prorata, taux retrouvé, contrat incomplet, événement après la fin,
tranche à venir, prêt soldé avant sa 2e tranche.

## Où en est un prêt (prEtat) : le seul calcul du capital restant dû

`prEtat(L, t)` : capital restant dû, capital remboursé, échéances payées,
prochaine échéance, échéances à pointer, coût payé. Les écrans du prêt, le
Patrimoine (`paValeurAuto`, via `prCrdPart`) et l'accueil le lisent tous.

* **Avant le début de l'amortissement**, le capital dû est ce que la banque a
  déjà versé (règle de la 4.3.4 : une tranche pas encore reçue n'est pas une
  dette), plus les intérêts capitalisés d'un différé total. Ensuite, l'échéancier.
* **Échéances comptées à leur date** (`remboursements_auto`, défaut d'un nouveau
  prêt) : celles datées d'aujourd'hui ou avant sont payées.
* **À la main** : une échéance ne compte qu'une fois pointée (`L.remboursements`,
  champ `echeance` = sa date dans l'échéancier, le montant vraiment payé à côté).
  Bouton « Pointer » sur chaque échéance passée (et la prochaine), « Tout pointer »,
  et « + Remboursement » dans Paramètres pointe la prochaine. Une échéance à 0 €
  se règle seule. Les remboursements saisis avant la 4.4.17, sans `echeance`,
  comptent comme du capital rendu (l'ancienne règle).
* **Contrat incomplet** (pas de montant, de durée ou de 1re échéance) : pas
  d'échéancier, et l'ancien calcul versé − remboursé.
* **Prêt à deux** : `pret.part` (%). Les écrans du prêt montrent tout le prêt (« ta
  part : … » sous le restant dû) ; le Patrimoine et l'accueil, la part seule
  (`prCrdPart`).

**Coût du crédit** (`prOverview().cout`) : intérêts, assurance et indemnités de tout
l'échéancier, plus les frais du prêt jusqu'à sa dernière échéance (`prFraisPret` :
dossier et garantie au déblocage, ponctuels, récurrents, moins ceux que la banque
a rendus). « Payé » : ce qui l'est à ce jour.

**Mensualité annoncée par la banque** (`pret.mensualite`, facultative) : sert à
retrouver le taux, et à vérifier le contrat. Un écart d'au moins un centime avec
l'échéance calculée s'affiche en alerte sur la vue d'ensemble et dans l'aperçu de
la fenêtre du contrat. Arthur garde ses … € ici : tant que son assurance n'est
pas saisie (il le fera en décembre 2026, après les premiers prélèvements), Pilote
calcule 500,00 € et signale … € d'écart.

## Écrans

Une section par prêt dans la barre latérale (`_navBlocs`, onglets `pr-ech@p2`),
rangée comme les CTO (`_navOrdre`, familles `sec-cto` et `sec-pret`) ; sans prêt,
une section « Prêt » mène à `pane-pr-vide` (« Créer mon prêt »). `PR` est le prêt
affiché, mis en place par `prAvantOnglet` (appelée par le `goTab` d'origine,
après `ctoAvantOnglet`) ; `PRF` le fichier entier. Le fil d'Ariane prend le nom du
prêt. Le bouton Retour annule les actions du prêt affiché et celles du PEA
(`_undoModulesOuverts` : `["pea", "pret:p2"]`, instantanés `{"PR": id, L}`).

* **Vue d'ensemble** : restant dû, capital remboursé, prochaine (ou première)
  mensualité, coût du crédit, fin du prêt ; barre de progression ; courbe du
  restant dû (trait plein jusqu'à aujourd'hui, pointillé ensuite) et tableau du
  coût (payé, reste, total). Sous 1 180 px de large, courbe et tableau passent
  l'un sous l'autre (`.pr-duo`). Puis, pour un prêt placé, les placements.
  Mesuré à 1366 × 720 : le prêt immobilier de test tient sans défiler.
* **Échéancier** : les changements en cours de route (boutons Remboursement
  anticipé, Nouveau taux, Report, Modulation ; leur fenêtre montre l'effet avant
  d'enregistrer : fin du prêt, intérêts économisés, nouvelle échéance, plafond des
  indemnités d'un prêt immobilier), puis le tableau par année (l'année en cours et
  celle de la prochaine échéance dépliées). Colonnes Intérêts et Assurance cachées
  quand elles sont à zéro.
* **Bourse, Assurance vie, Livrets** : seulement si `pret.placements` (case
  « L'argent du prêt est placé », Paramètres › Suivi dans Pilote). Retirer la case
  n'efface rien.
* **Paramètres** : contrat (fenêtre sur trois colonnes, aperçu en direct, tient
  sans défiler à 1366 × 720 : 635 px pour 646), suivi (placements, pointage à la
  main, ma part), versements, remboursements saisis, frais, « Nouveau prêt »,
  « Supprimer ce prêt » (les ordres du PEA et des CTO restent dans leurs comptes).
* **Paramètres de Pilote › Prêts** : un bouton par prêt (`prRenderReglages`).

## Hors du module

* **Fenêtres d'ordre du PEA et des CTO** : case « Payé avec l'argent du prêt »
  (`prCaseOrdre`, `prChoixPret`), cachée s'il n'existe aucun prêt dont l'argent
  est placé (un nouvel utilisateur ne la voit pas), avec le choix du prêt s'il y
  en a plusieurs. Elle existe aussi dans un CTO depuis la 4.4.17 (plus `pea-seul`).
  Même chose pour « Passer un scénario ». L'étiquette d'un ordre dans
  Transactions prend le nom du prêt s'il y en a plusieurs.
* **Patrimoine** : une ligne de dette par prêt, à son nom, valeur `prCrdPart`.
* **Accueil** : « Capital restant dû des prêts » (`pret`, tous les prêts, « Mes
  prêts » s'il y en a plusieurs), « Prochaine échéance de prêt »
  (`pret-mensualite`, la plus proche, mène à l'échéancier de ce prêt), « Ce que
  rapporte le prêt » (`pret-gains`, gains nets moins intérêts et assurance payés),
  et une tuile par prêt (`pret:p2`, `prSyncWidgets`, éteinte tant qu'on ne
  l'ajoute pas).
* `carnetRedrawCharts` redessine les courbes d'un prêt ouvert au changement de
  thème ou d'accent.

## Placements du prêt (règles reprises de l'ancien module)

API Python : `load_pret()` / `save_pret()`. Capitalisation annuelle de l'AV et moteur
événementiel du Livret A repris à l'identique de l'ancienne app standalone (abandonnée).

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
    tous contrats Afer confondus : rien à compter pour Arthur, déjà adhérent. Les
    frais de gestion annuels ne s'ajoutent pas : le taux publié par l'Afer, celui
    qu'on saisit, en est déjà net.
  → Contrats d'Arthur (08/10/2026) : « Afer Génération » (… % en 2025) et
    « Afer Multisupport » (… % en 2025), taux du communiqué Afer du 19/01/2026,
    0,5 % de frais sur versements sur les deux.
* livrets (4.4.17, un seul « liv » avant) : `[{id, label, taux_history:[{id,date,taux}], mouvements:[{id,date,type,montant,note}]}]`.
  Livret A, LDDS, LEP, livret jeune… : chacun ses taux et ses mouvements, intérêts
  par quinzaines (`prLivretState`) : un dépôt rapporte à partir de la quinzaine
  qui suit, un retrait cesse dès le début de la sienne, taux / 24 par quinzaine
  terminée, intérêts au capital le 1er janvier. Vérifié : 1 000 € le 10/01 à 3 %
  → 23 quinzaines, 28,75 €.
* frais_recurrents : prélevés le MÊME JOUR chaque mois (jour pris sur `date_debut`,
  ramené au dernier jour du mois quand il n'existe pas — voir `prAddMonths`)
* frais_rembourses : `{id, date, montant, label}`, frais que la banque a rendus
  (ex. un mois de carte offert), déduits des frais (4.3.4)

**Les frais se comptent au fil des mois (4.3.4).** Jusque-là, les 120 prélèvements de
la carte (… €) comptaient dès le premier jour : … € de frais, et autant en moins
dans les liquidités et les gains. Désormais `prAllFrais(jusqua, L)` ne prend que ce
qui est daté d'aujourd'hui ou avant ; le reste s'affiche « à venir » dans Paramètres.
* **Changement de tarif** : `paliers: [{id, date, montant}]` sur le frais récurrent,
  nouveau montant à partir de cette date (`prTarif`). Ne jamais modifier `montant`
  pour un changement de tarif : ce serait réécrire les prélèvements passés.
* `nb_occurrences` 0 ou vide = frais sans fin (`prExpandRecurrent` s'arrête alors à
  la date demandée ; sans date, il ne renvoie rien, jamais une boucle infinie).
* Frais remboursés : même règle, ceux datés d'aujourd'hui ou avant. Le bouton
  « flèche retour » d'un frais récurrent pré-remplit un remboursement (montant du jour).

**Tout au réel, à sa date (4.3.4, audit du module).** Versements, dépôts d'assurance
vie, mouvements des livrets et ordres ne comptent qu'à partir de leur date
(`prPasse` / `prAVenir`) ; ce qui est daté plus tard s'affiche « à venir ».
* `prTranchesTxt(o, court)` : « … € versés sur … € empruntés, … €
  attendus le … ». Sans versement saisi, tout le montant compte comme versé au
  déblocage.
* **Cours** : `prCours(t)` prend le cours du PEA (`getVar`, rafraîchi toutes les
  3 min, CTO compris), `_prQuotes` ne sert plus qu'aux titres qu'ils ne suivent pas.
* **Alertes** (`prAlertesHtml`) : versements saisis > montant emprunté ; placé > versé
  à ce jour (prêt placé seulement ; les échéances n'y entrent plus : elles se paient
  souvent avec un salaire, pas avec le prêt) ; mensualité annoncée ≠ calculée ;
  changement qui ne s'applique pas ; échéances à pointer.
* Graphiques aux couleurs du thème (`carnetChartColors`, `CLRS`).

Les cours passent par le serveur local (`/cours`), pas de second proxy Yahoo.

### Bourse du prêt = ordres du PEA et des CTO cochés « argent du prêt »

On n'a qu'un PEA : les achats faits avec le prêt en font partie. Avant la 4.3.x, il
fallait les saisir deux fois. Un ordre n'existe **qu'une fois**, dans les transactions
de son compte, avec `pret` (l'id du prêt) quand la case « Payé avec l'argent du
prêt » est cochée (fenêtres `ov-pos` et `ov-tx`, champs `f-pret` / `t-pret`, choix
du prêt `f-pret-id` / `t-pret-id`, absente pour un dividende). `prPeaOrdres(L)` lit
ces transactions dans le PEA (`_etatPea()`) et dans chaque CTO (`ctoEtat`) et les
convertit (`prYahoo` : `EPA:WPEA` → `WPEA.PA` ; montant = qté × cours ± frais,
comme `computeCash`). **Aucune copie dans `pret.json`** : pas de doublon possible, et
une modification, un décochage, une suppression ou le bouton Retour se voient partout.

* Les ordres non cochés n'entrent jamais dans les calculs du prêt.
* **Ordre payé en partie avec le prêt** (08/10/2026) : sous la case, « dont … €
  pris sur le prêt » (« rendus au prêt » pour une vente), champs `f-pret-mt` /
  `t-pret-mt`, enregistré dans `pretMontant`. Vide ou égal à l'ordre : l'ordre
  entier, pas de `pretMontant`. Le prêt détient alors la même part des parts et
  des frais (`prPartOrdre` = `pretMontant` / montant de l'ordre, `prTotalOrdre`) :
  … € d'un achat de … € → … parts sur 25.
  Fenêtre « Passer un scénario » : un seul montant (`sop-pret-mt`), réparti entre
  les ordres au prorata, le dernier prend le reste (somme juste au centime).
  Le champ n'apparaît que case cochée, en CSS (`label:has(…:not(:checked)) + .pr-part`).
* « + Achat » / « Vente » de l'onglet Bourse ouvrent les fenêtres du PEA, case cochée
  sur ce prêt (`prAchatViaPea`, `prVenteViaPea`) ; le crayon d'un ordre du PEA ouvre
  `editTx`, celui d'un ordre de CTO mène aux transactions du CTO (`prOuvrirCto`).
  Pas de corbeille côté prêt : supprimer un ordre de son compte depuis là surprendrait.
* Vente cochée : refusée au-delà des parts achetées avec ce prêt dans ce compte
  (`prVentePretOk`, qui compte la part du prêt d'une vente partielle).
* `persist()` appelle `prRefreshIfVisible()` : l'onglet du prêt ouvert suit le PEA.
* Patrimoine : la ligne PEA vaut le PEA **entier** (`_peaPv.total`), parts du prêt
  comprises ; la valeur des placements du prêt n'est ajoutée nulle part. Ne jamais
  créer de compte « placements du prêt » : PEA, CTO, AV et livrets sont déjà comptés
  par leurs propres lignes.
