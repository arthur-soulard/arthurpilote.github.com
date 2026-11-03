# Module Garmin

Fiche détaillée tirée de `CLAUDE.md`, qui garde les règles générales (dont les six choses à ne jamais casser).

## Module Garmin (garmin.json)

La montre Garmin, lue dans le compte Garmin Connect de l'utilisateur. Demandé
par Arthur le 03/11/2026 (« est-ce que ça pourrait être possible d'ajouter la
connexion Garmin à Pilote ? »), codé le même jour pendant son absence, **pas
encore publié**. Une section « Garmin » dans Vie perso, deux onglets :
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
| Forme du jour | `/usersummary-service/v2/dailysummaries` (1 an max), `/sleep-service/sleep/dailySleepSummariesByDate` (31 j max), `/hrv-service/hrv/daily/{a}/{b}` | `jours` de `garmin.json` : pas, objectif, FC au repos, Body Battery (max, min, dernière valeur), stress, minutes intenses, sommeil (min, score, profond, paradoxal), VFC (nuit, statut) |

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
   écartée. `spSaveSession` garde `garminId`, `fcMoy` et `kcal` d'une séance
   modifiée.
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
plus d'une heure, à l'ouverture de Ma forme dans le même cas, et au bouton
Synchroniser. Pas de minuterie pendant que Pilote reste ouvert (version minimale).

### Écrans et tuiles

* **Ma forme** : cinq chiffres (sommeil de la nuit avec score, Body Battery,
  VFC et son statut, FC au repos et sa moyenne sur 30 j, pas et objectif), une
  courbe des 30 derniers jours au choix (sommeil, Body Battery, VFC, FC au repos,
  pas, stress), puis les 8 dernières séances venues de la montre. Garmin date le
  sommeil du jour du réveil : « nuit du 2 au 3 nov. » (`gaNuit`).
* **Connexion** : la fiche en quatre étapes, la clé, la date de départ, les trois
  cases ; une fois connecté, les cases restent réglables.
* **Tuiles** (`ga-sommeil`, `ga-forme`, `ga-pas`, éteintes par défaut comme toute
  nouvelle tuile) : sommeil de la nuit avec moyenne 7 j et courbe 14 j, Body
  Battery du jour avec VFC et FC au repos, pas du jour avec barre vers l'objectif.
* Sports : badge « Garmin » et FC moyenne dans la liste du jour. Santé : icône de
  montre dans l'historique.
* **Nouveau module** : proposé une fois, décoché (`_demanderNouveauxModules`) ;
  `_modulesConnusDepart` l'exclut aussi pour une installation d'avant la 4.4.47.

### Tests

* `tests/test_garmin.py` : faux serveur construit d'après le Swagger et le client
  officiel (jeton JWT brut, ApiKey puis Bearer), 13 cas (mauvaise clé, clé jamais
  en clair, conversion des séances et pesées, grammes, vus, relecture partielle,
  source en panne, clé expirée, cases, réseau coupé).
* Données de Camille : `garmin.json` avec 30 jours de forme (compte pas
  connecté), quelques séances avec `garminId`, tuiles Garmin en tête.

### À vérifier avec une vraie clé

* Le format exact du jeton et les réponses réelles (seulement d'après la doc et
  le client officiel).
* Le poids (kg d'après la spec, grammes dans l'ancienne API).
* Les noms réels des clés de `sleepScores` (`overall` supposé) et des statuts de
  VFC (`BALANCED`, `UNBALANCED`, `LOW`, `POOR`).
* Les limites de requêtes (non documentées) et les plages de dates refusées.
