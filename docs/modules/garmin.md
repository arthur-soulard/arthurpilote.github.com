# Module Garmin

Fiche détaillée tirée de `CLAUDE.md`, qui garde les règles générales (dont les six choses à ne jamais casser).

## Module Garmin (garmin.json)

La montre Garmin, lue dans le compte Garmin Connect de l'utilisateur. Demandé
par Arthur le 03/11/2026 (« est-ce que ça pourrait être possible d'ajouter la
connexion Garmin à Pilote ? »), codé le même jour pendant son absence, essayé
avec sa vraie clé, **publié en 4.4.52** (03/11/2026). Une section « Garmin » dans Vie perso, deux onglets :
**Ma forme** (`ga-forme`) et **Connexion** (`ga-connexion`).

API Python : `load_garmin()` → `{connecte, connecteLe, depuis, choix, derniere,
jours}` ; `save_garmin(cle, depuis)` connecte ; `save_garmin_reglages(choix,
depuis)` ; `save_garmin_deconnexion()` oublie la clé ; `save_garmin_synchro()`
lit Garmin ; `save_garmin_vus(ids)`. Toutes s'appellent `save_*` pour passer par
le gel des enregistrements (`_surveillerEcritures`), la synchronisation comprise :
elle écrit `garmin.json`.

### Pourquoi la clé API personnelle

Recherche du 03/11/2026, quatre voies :

| Voie | Verdict |
|---|---|
| **Clé API personnelle** (Garmin, octobre 2026) | retenue : gratuite, sans approbation, lecture seule, appelée depuis le PC |
| Programme développeurs (Starter, Enterprise) | écartée : Garmin **pousse** les données vers un serveur public qui doit tourner en permanence (Starter : push seul, pas d'historique), contraire au « aucun serveur » de Pilote ; Enterprise payant |
| Bibliothèques non officielles (`python-garminconnect`, `garth`) | écartées : e-mail et mot de passe du compte, cassées par le changement de connexion de Garmin en mars 2026, `garth` abandonnée |
| Export manuel (CSV, archive .FIT) | en secours seulement : rien d'automatique |

Ce qui est sûr, lu sur les pages officielles le 03/11/2026 :

* **FAQ** (`developer.garmin.com/gc-developer-program/personal/personal-faq/`) :
  la clé se crée sur `connect.garmin.com/app/settings/personalApiToken`, n'est
  affichée qu'une fois, dure 30 j, 90 j, 180 j ou 1 an (e-mail une semaine
  avant). Le jeton d'accès vaut **24 h**, sans jeton de renouvellement : on en
  redemande un. « Not intended for commercial applications serving multiple end
  users » : Pilote gratuit, chacun avec sa clé pour ses données, reste dans ce
  cadre. **Un Pilote+ payant poserait la question.**
* **Swagger** (même site, `…/personal/swagger-docs/`, rendu en JavaScript : la
  spec OpenAPI est dans le bundle de la page) : 26 GET, rien en écriture.
* **Client Python officiel** (`github.com/garmin/connect-personal-api-python`,
  Apache-2.0) : le jeton est un **JWT rendu en texte brut** par
  `POST /personalapitoken-service/personal-api/personal-api-key/token` avec
  `Authorization: ApiKey <clé>` ; les données se lisent avec
  `Authorization: Bearer <jeton>`. Pas de dépendance ajoutée : Pilote fait la
  même chose avec `urllib`.

Jamais essayé avec une vraie clé (Arthur absent) : voir « À vérifier ».

### Ce qui est lu

| Case | Endpoint | Devient |
|---|---|---|
| Séances | `/activitylist-service/activities/search/activities` (99 par page, 10 pages au plus) | séances de Sports : date et heure locales, sport, durée (min), distance (km, ou m pour la natation), D+, nom de l'activité en note, FC moyenne, kcal |
| Pesées | `/weight-service/weight/all/{debut}/{fin}` | pesées de Santé : poids, IMC, graisse, eau (`source: "garmin"`) |
| Forme du jour | `/usersummary-service/v2/dailysummaries` (1 an max), `/sleep-service/sleep/dailySleepSummariesByDate` (31 j max), `/hrv-service/hrv/daily/{a}/{b}`, `/fitnessage-service/fitnessage/v2/{jour}` | `jours` de `garmin.json` : pas, objectif, FC au repos, Body Battery (max, min, dernière valeur), stress, minutes intenses et objectif de la semaine, SpO2 et respiration (moyennes du jour), sommeil (min, score, profond, paradoxal), VFC (nuit, statut) ; `ageForme` : âge physique, âge réel, âge atteignable |
| Cycle menstruel (décochée par défaut) | `/periodichealth-service/menstrualcycle/summary/{jour}` | `cycle` : jour du cycle, durée prévue, règles, fenêtre fertile, début de la phase lutéale, grossesse |

Les records : `isPR` de l'activité devient `record: true` sur la séance de Sports.

**Cycle menstruel, pour qui ?** Pilote ne connaît pas le sexe de l'utilisateur
(Garmin ne le donne pas dans l'API, et le profil de Santé ne le demande pas).
La case est décochée pour tout le monde, et même cochée rien ne s'affiche tant
que Garmin ne renvoie pas de cycle : Garmin n'en a que si l'utilisateur le suit
dans Connect (204 sinon). Décocher efface le cycle gardé. Âge physique ou cycle
introuvable (404) : pas de donnée, pas une panne (la synchronisation avance).

**Expiration de la clé** : Garmin ne la donne pas. La durée choisie à la
création (30 j, 90 j, 180 j, 1 an : `DUREES_CLE`) est demandée à la connexion et
devient `expire` ; elle se corrige dans Connexion. Rappels : bandeau de Ma forme
14 jours avant (`GA_RAPPEL_JOURS`), notification Agenda « Clé Garmin à
renouveler » (`agenda.RAPPELS`, type `garmin-cle`, pastille Garmin) le jour
de l'expiration, avec l'alerte choisie (une semaine avant, par exemple).

Le sport vient du `typeKey` de Garmin, reconnu par morceau (`sport_pilote`) :
`swim` → natation, `run` → course, `cycl`/`bik`/`ride` → vélo, `strength` →
muscu, `hik` → rando, `soccer` → foot, le reste → Autre (yoga, marche…).

Unités d'après la spec : durées en secondes, distances en mètres, poids en kg.
L'ancienne API de Connect donnait le poids en **grammes** : une valeur au-dessus
de 1 000 est divisée par 1 000. Une pesée hors des bornes de Santé est ignorée.

### Ce qu'il ne faut pas défaire

1. **Python n'écrit ni `sports.json` ni `sante.json`.** La page tient SP et SA en
   mémoire et les réécrit en entier : une écriture de Python par-dessous serait
   effacée au prochain enregistrement. `save_garmin_synchro` renvoie séances et
   pesées ; `gaAjouter` (index.html) les ajoute, enregistre le module, puis
   seulement appelle `save_garmin_vus`. Échec d'enregistrement : rien n'est
   marqué vu, ce sera reproposé.
2. **`vus`** (5 000 derniers identifiants) : une séance supprimée dans Pilote ne
   revient pas. Les séances déjà dans Sports se reconnaissent aussi par leur
   `garminId`.
3. **Doublons avec la saisie à la main** : même jour, même sport, durée à
   15 min ou 25 % près → la séance saisie est gardée et reçoit le `garminId`.
   Une pesée existe déjà ce jour-là (FitDays, à la main) → celle de Garmin est
   écartée. `spSaveSession` garde `garminId`, `fcMoy`, `kcal` et `record` d'une
   séance modifiée. Un record reconnu sur une séance saisie à la main lui est
   reporté.
4. **La clé ne repasse jamais par la page** : vérifiée auprès de Garmin (jeton
   obtenu) avant d'être enregistrée, chiffrée par `actus._chiffrer` (DPAPI sous
   Windows, Trousseau sur Mac, service « Pilote Garmin »). Le jeton du jour vit
   en mémoire seulement (`_jeton`).
5. **Relecture partielle** : la synchronisation relit depuis la dernière réussie
   moins 7 jours (`RECOUVREMENT` : une séance synchronisée en retard), la forme
   depuis 2 jours avant. Une source en panne n'empêche pas les autres
   (`erreurs`), mais `derniere` n'avance pas : tout sera relu la fois suivante.
   Clé refusée (401) : tout s'arrête, message « crée une nouvelle clé ».
6. **Déconnexion** : la clé est oubliée (et retirée du Trousseau), la forme déjà
   lue reste (`jours`, à l'utilisateur).

### Quand Pilote synchronise

Au lancement (4 s après, une fois Sports et Santé lus) si la dernière date de
plus d'une heure, à l'ouverture de Ma forme dans le même cas, au bouton
Synchroniser, et, Pilote resté ouvert, toutes les 2 heures (`GA_PERIODE_MS`,
vérifié toutes les 10 min) : discrètement, un message seulement s'il y a du
nouveau ou une panne.

### Écrans et tuiles

* **Ma forme** : jusqu'à neuf chiffres (sommeil de la nuit avec score, Body
  Battery, VFC et son statut, FC au repos et sa moyenne sur 30 j, pas et
  objectif, minutes intenses de la semaine, SpO2, respiration, âge physique :
  chacun n'apparaît que si la montre le mesure), une courbe des 30 derniers
  jours au choix (sommeil, Body Battery, VFC, FC au repos, pas, stress, minutes
  intenses, SpO2, respiration), la carte du cycle (jour, phase, prochaines
  règles, barre règles / fenêtre fertile / aujourd'hui), puis les 8 dernières
  séances venues de la montre, records marqués. Garmin date le sommeil du jour
  du réveil : « nuit du 2 au 3 nov. » (`gaNuit`). La phase du cycle se déduit
  des jours donnés par Garmin (`gaPhase`), pas de son `currentPhase`, dont la
  doc ne donne pas les valeurs ; le jour avance seul depuis la dernière
  synchronisation (`gaCycleDuJour`).
* **Connexion** : la fiche en quatre étapes, la clé, la durée choisie sur Garmin
  Connect, la date de départ, les quatre cases ; une fois connecté, les cases,
  la date de départ et la date d'expiration restent réglables.
* **Tuiles** (éteintes par défaut comme toute nouvelle tuile) : `ga-sommeil`
  (sommeil de la nuit, moyenne 7 j, courbe 14 j), `ga-forme` (Body Battery du
  jour, VFC, FC au repos), `ga-pas` (pas du jour, barre vers l'objectif),
  `ga-intensite` (minutes intenses depuis lundi, barre vers l'objectif de la
  semaine), `ga-cycle` (jour du cycle, phase, prochaines règles), `ga-record`
  (dernier record : distance ou durée en grand).
* Sports : badges « Garmin » et « Record », FC moyenne dans la liste du jour.
  Objectifs de performance : un record de la montre depuis la création de
  l'objectif, du même sport, propose « Valider » (`gaRecordPour`) ; rien ne se
  valide seul (Pilote ne lit pas « 10 km en 45 min »). Santé : icône de montre
  dans l'historique.
* **Bilan de la semaine** : section « Forme » (sommeil moyen, pas par jour, FC au
  repos, minutes intenses, sommeil nuit par nuit, records de la semaine) et une
  ligne « Forme : … » dans la notification.
* **Nouveau module** : proposé une fois, décoché (`_demanderNouveauxModules`) ;
  `_modulesConnusDepart` l'exclut aussi pour une installation d'avant la 4.4.47.

### Tests

* `tests/test_garmin.py` : faux serveur construit d'après le Swagger et le client
  officiel (jeton JWT brut, ApiKey puis Bearer), 17 cas (mauvaise clé, clé jamais
  en clair, conversion des séances, records et pesées, grammes, SpO2,
  respiration, âge physique, vus, relecture partielle, source en panne, âge
  physique absent, clé expirée, cases, cycle suivi ou non, date d'expiration,
  rappel dans l'Agenda, réseau coupé).
* Données de Camille : `garmin.json` avec 30 jours de forme (compte pas
  connecté), le cycle coché, quelques séances avec `garminId` dont un record, un
  objectif de performance à valider, les six tuiles Garmin en tête.

### Essai avec une vraie clé (03/11/2026)

Sur un banc isolé (copie de la branche, données temporaires effacées après),
avec la clé d'Arthur et sa montre, journal de la seule forme des réponses :

* **Jeton** : JWT de 1 141 caractères en texte brut, 3 parties, `exp` à 24 h.
  Conforme au client officiel.
* **Activités** : `isPR`, `activityType.typeKey`, `duration` (s), `distance` (m),
  `elevationGain`, `averageHR`, `calories` présents ; 8 séances lues
  (randonnée, course), distances et durées cohérentes.
* **Résumé du jour (v2)** : 30 jours ; `intensityMinutes.goal` présent ;
  `respiration.avgValue` présent ; **`pulseOx` ne contient que l'altitude** sur
  cette montre : pas de SpO2, la case n'apparaît pas (prévu).
* **Sommeil** : `sleepScores.overall.value` présent (supposition juste) ;
  les horodatages du sommeil sont des **nombres** (ms), pas des chaînes comme
  dans la spec : Pilote ne les lit pas.
* **VFC** : statut `BALANCED` vu.
* **Âge physique** : la réponse est un **objet** `{"invalidReason": …}` (pas une
  liste) quand Garmin n'en a pas : lu comme « pas de donnée », sans erreur.
* Aucune erreur, aucune limite de requêtes rencontrée (5 appels, moins de 3 s).

Reste à vérifier : **le poids** (la case Pesées était décochée : kg d'après la
spec, grammes dans l'ancienne API, Pilote accepte les deux), un vrai record
(`isPR` à `true`), les autres statuts de VFC, le cycle d'un compte qui le suit,
et la réponse de Garmin à une clé expirée.
