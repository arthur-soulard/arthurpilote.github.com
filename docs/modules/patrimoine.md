# Module Patrimoine

Fiche détaillée tirée de `CLAUDE.md`, qui garde les règles générales (dont les cinq choses à ne jamais casser).

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
   d'octobre, fait le 02/10 avant la tranche de 15 000 € reçue le 07/10, gardait
   une dette à 0 € tout le mois. Un mois passé garde son relevé ; s'il n'en a
   pas, la ligne auto prend la valeur de la **fin de ce mois-là**
   (`paValeurAuto(compte, iso)`) : prêt via `prCapitalDu(fin du mois)`, PEA via
   le dernier point du mois de la courbe du capital (`_perfFullSeries`), et rien
   tant qu'elle n'est pas chargée (la ligne reprend alors son dernier relevé).
   Jusqu'à la 4.3.24, rouvrir septembre proposait la dette et le PEA d'aujourd'hui.

**Dette du prêt = versements reçus − remboursements** (`PR.versements` et
`PR.remboursements` datés d'aujourd'hui ou avant), et non plus le montant emprunté
moins un échéancier calculé au calendrier. Changé le 28/09/2026 : le prêt d'Arthur
(30 000 €, en deux tranches de 15 000 €) comptait 30 000 € de dette dès sa
configuration, avant tout versement, et le patrimoine baissait d'un argent qui
n'était encore sur aucun compte. Une tranche non reçue n'est ni une dette ni un
avoir. La tuile d'accueil « Prêt étudiant » (capital restant dû) lit la même valeur.
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

Seul le type `dette` compte négativement. Un compte `auto` ne peut pas être
supprimé : il serait recréé au chargement suivant.
