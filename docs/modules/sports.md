# Module Sports

Fiche détaillée tirée de `CLAUDE.md`, qui garde les règles générales (dont les cinq choses à ne jamais casser).

## Module Sports (sports.json)

API Python : `load_sports()` / `save_sports()` — `load_sports` renvoie aussi le
catalogue (`SPORTS`) et les champs disponibles (`FIELD_CATALOG`).

Catalogue livré : `course`, `velo`, `natation`, `muscu`, `foot`, `rando`, `autre`.
Chaque sport déclare ses `fields`, ce qui pilote le formulaire côté UI via `spHasField()`.

* course   : distance_km, duration, elevation, subtype
* velo     : distance_km, duration, elevation
* natation : distance_m, duration, lieu (libre / 25 / 50)
* muscu    : duration, groups, routine
* foot     : duration, kind (entrainement / match)
* rando    : distance_km, duration, elevation, subtype
* autre    : duration

**Sports personnalisés** : `SP.customSports` = `[{id, label, icon, color, fields}]`.
L'utilisateur les crée depuis le sélecteur de « Nouvelle séance » (bouton
« + Ajouter un sport ») ou Paramètres → Sports → Mes sports, et coche les informations
à saisir parmi `FIELD_CATALOG` (les mêmes que les sports livrés). Id préfixé `perso_`.
`spRebuildCatalog()` compose `SP_CATALOG` = `SP_BASE_CATALOG` + perso + `autre` en
dernier. `spSportById()` retombe explicitement sur `autre`, jamais sur le dernier
élément du tableau. Un sport utilisé par des séances ne peut pas être supprimé.

Ne pas remettre d'`id` de sport en dur dans le code : c'est `spHasField()` qui décide
(distance en mètres, lieu, routine, groupes, kind…).

Données :
* sessions : `{id, date "YYYY-MM-DD", time, sport, duration (min), distance
  (km, ou mètres si le sport a le champ distance_m), elevation, note, + champs du sport}`
* routines : `{id, name, note}` — de simples libellés de circuits, rattachés aux
  séances de muscu par `routineId`. PAS de liste d'exercices.
* goals    : kind `perf` (validation manuelle) ou `event` (date + compte à rebours)
* subtypes : `{"course": [...], "rando": [...]}` — types de séance modifiables

Ce qui compte le plus pour Arthur : le NOMBRE D'HEURES. C'est le KPI principal
partout (accent, première position). L'agenda affiche une bulle emoji de 30 px par
séance (4 par ligne max) + le total d'heures du jour, détail au clic.

**On ne compare pas avec une période d'avant le suivi (4.2.7).** `spTrackStart()` =
date de la première séance. Avant elle, un mois vide n'est pas « zéro sport » : Pilote
n'était pas encore utilisé. Si le mois (ou l'année) de référence finit avant ce début,
les chiffres clés disent « premier mois suivi » / « première année suivie » (ou « avant
le début du suivi ») au lieu de « −8 h 55 vs août ». Le cumul de l'année dit « depuis
le 11 sept. » et la moyenne hebdo se calcule sur les semaines écoulées **depuis la
première séance** si le suivi a commencé en cours d'année.
