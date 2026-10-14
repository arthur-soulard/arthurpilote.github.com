# Module Patrimoine

Fiche détaillée tirée de `CLAUDE.md`, qui garde les règles générales (dont les six choses à ne jamais casser).

## Module Patrimoine (patrimoine.json)

Vue consolidée de ce qu'on possède. **Saisie manuelle une fois par mois** :
l'agrégation bancaire automatique suppose un contrat pro et une validation
réglementaire, hors de portée d'une app locale. Six chiffres par mois suffisent.

API Python : `load_patrimoine()` / `save_patrimoine()` — les deux renvoient
`net`, `serie` et `moisSaisi` déjà calculés, l'UI ne recalcule pas.

* comptes : `{id, label, type, icon, color, auto, archived, note}`
* releves : `{id, compteId, date:"YYYY-MM-01", montant}`

**Trois règles à ne pas casser :**

1. **Tous les relevés sont ancrés au 1er du mois.** C'est ce qui rend la série
   comparable d'un mois à l'autre (`paMoisIso`, `mois_courant`).
2. **Un compte non mis à jour garde sa dernière valeur connue** (`net_worth`
   prend le relevé le plus récent *à cette date ou avant*). Sans ça, oublier
   une ligne ferait s'effondrer le patrimoine ce mois-là.
3. **Le PEA et le prêt ne se saisissent pas** : comptes marqués `auto`,
   pré-remplis par `paValeurAuto()` depuis `window._peaPv.total` et l'onglet Prêt.
   Pas de double saisie. `_peaPv.total` est posé par `renderMetrics()` — ne pas
   recalculer la valorisation du PEA en parallèle.
   Sur le **mois en cours**, la valeur actuelle d'une ligne auto passe avant le
   relevé déjà saisi ce mois-là (`paBuildSaisie`) : refaire le relevé suffit à la
   remettre à jour, rien n'est réécrit sans lui. Corrigé le 08/10/2026 : le relevé
   d'octobre, fait le 02/10 avant la tranche de … € reçue le 07/10, gardait
   une dette à 0 € tout le mois. Un mois passé garde son relevé ; s'il n'en a
   pas, la ligne auto prend la valeur de la **fin de ce mois-là**
   (`paValeurAuto(compte, iso)`) : prêt via `prCapitalDu(fin du mois)`, PEA via
   le dernier point du mois de la courbe du capital (`_perfFullSeries`), et rien
   tant qu'elle n'est pas chargée (la ligne reprend alors son dernier relevé).
   Jusqu'à la 4.3.24, rouvrir septembre proposait la dette et le PEA d'aujourd'hui.

**Dette du prêt = versements reçus − remboursements** (`PR.versements` et
`PR.remboursements` datés d'aujourd'hui ou avant), et non plus le montant emprunté
moins un échéancier calculé au calendrier. Changé le 28/09/2026 : le prêt d'Arthur
(… €, en deux tranches de … €) comptait … € de dette dès sa
configuration, avant tout versement, et le patrimoine baissait d'un argent qui
n'était encore sur aucun compte. Une tranche non reçue n'est ni une dette ni un
avoir. La tuile d'accueil du prêt (capital restant dû) lit la même valeur.
Depuis la 4.3.4, ce calcul n'existe qu'à un endroit, `prCapitalDu()` (onglet Prêt),
que `paValeurAuto` appelle : le « Montant à rembourser » du module donne le même chiffre.

**Pas de doublon avec le prêt.** L'argent du prêt est compté une fois en avoir, là
où il se trouve (ligne PEA = PEA entier, parts du prêt comprises ; Livret A, AV,
compte courant saisis au solde réel de la banque), et une fois en dette. La
« valeur du portefeuille » de l'onglet Prêt n'est ajoutée nulle part. Corollaire :
l'argent du prêt qui attend sur un compte non suivi (compte courant sans ligne)
manque aux avoirs alors que la dette est là.

**La courbe couvre tout l'historique** (`serie_mensuelle`), du premier relevé
au mois en cours ; elle nourrit aussi la colonne « Net » du tableau des relevés.
Jusqu'à la 4.3.13, la boucle s'arrêtait 37 points après le **premier** relevé :
au-delà de trois ans, la courbe se figeait (essayé sur 58 mois : arrêt en
janvier 2025, tuile à 6 700 €, dernier point à 4 600 €).

**La ligne du prêt n'apparaît qu'une fois le prêt paramétré** (montant
emprunté saisi dans Prêt › Paramètres, même règle que la tuile d'accueil), ou si
elle a déjà des relevés : `paCompteVisible`, appliquée par `paComptes()`, donc
partout (comptes, tableau, relevé du mois). Demandé par Arthur le 11/10/2026 :
quelqu'un qui installe Pilote sans prêt étudiant n'a pas à voir une dette à 0 €.
Le compte existe toujours dans `patrimoine.json` : il réapparaît seul dès que le
prêt est saisi. Un compte qui a des relevés reste visible pour que le tableau
corresponde au total, calculé côté Python sur tous les comptes non archivés.
**Même règle pour la ligne du PEA** (13/10/2026) : absente tant que le PEA est
vide (ni position, ni ordre, ni dépôt, ni espèces) et sans relevé. Elle
apparaissait d'office, à « — », chez qui ne se sert pas du PEA ; le premier
dépôt la fait apparaître (vérifié sur le banc d'essai, données vierges).
Depuis la 4.3.34, la ligne du prêt **porte le nom donné au prêt** (`paLabel`) : son `label`
enregistré ne sert plus que de repli, et son nom se change dans les paramètres du
prêt (champ en lecture seule dans la fenêtre du compte).

Seul le type `dette` compte négativement. Un compte `auto` ne peut pas être
supprimé : il serait recréé au chargement suivant.

## Lignes des CTO (4.4.0)

Une ligne automatique par CTO (`auto: "cto:<id>"`, type `cto`), créée par
`ctoLignesPatrimoine` au démarrage et à la création d'un CTO. Elle porte le nom
du CTO (`paLabel`, à renommer dans ses réglages) et se pré-remplit avec la valeur
de ses titres (`ctoValeurAuto` → `ctoResume`). Un mois passé n'est proposé que si
la courbe de ce CTO est chargée ; sinon la ligne reprend son dernier relevé. Un
CTO supprimé masque sa ligne, sauf si elle a des relevés. Détail :
`docs/modules/cto.md`.

## Onglet Simulateurs (4.4.2)

Projection de versements, objectifs et comparateur d'actifs (`pane-sim`,
`_initSimulateurs`) : dans le PEA jusqu'à la 4.4.1, déplacés ici à la demande
d'Arthur (12/10/2026). Ils ne lisent aucun compte ; leurs saisies restent dans
`S.uiPrefs.simulators`, et l'onglet garde son id `sim` (onglet masqué, cartes
`card-sim-*`). Le PEA est dans `S` quand ils s'ouvrent (onglet hors CTO).
