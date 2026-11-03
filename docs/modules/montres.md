# Section Montres : Coros et fichiers .fit

Fiche détaillée tirée de `CLAUDE.md`, qui garde les règles générales (dont les six choses à ne jamais casser).
Garmin a sa propre fiche : `docs/modules/garmin.md`.

Demandé par Arthur le 03/11/2026 (« on peut connecter une coros ? »), codé le
même jour sur la branche `montres`, **pas encore publié**. La section « Garmin »
de la 4.4.52 devient **« Montres »** : même id `sec-garmin` (il est dans les
réglages enregistrés : modules masqués, ordre de la barre), quatre onglets :
**Ma forme** (`ga-forme`), **Garmin** (`ga-connexion`), **Coros**
(`co-connexion`), **Fichiers .fit** (`mo-fit`).

## Pourquoi ces voies (recherche du 03/11/2026)

| Voie | Verdict |
|---|---|
| **Serveur MCP de Coros** (`mcp.coros.com/mcp`) | retenue, à l'essai : seul accès confirmé pour un particulier ; lecture du sommeil, de la VFC, des séances |
| **Fichiers .fit** | retenue : toute montre, sans compte, 100 % local ; manuel |
| API partenaire de Coros | écartée : candidature et examen, pour des entreprises |
| Bibliothèques non officielles (Training Hub par e-mail et mot de passe) | écartées : mot de passe gardé, cassent au moindre changement |
| **Strava** | **écartée avec Arthur** : créer son accès à l'API exige un abonnement payant (« A Strava subscription is required »), et l'API Policy interdit de garder les données plus de 7 jours (« You may not retain Strava Data in your cache for longer than seven (7) days ») alors que Pilote garde les séances. Ne pas reproposer. |

Lu directement sur le serveur de Coros (lecture seule, sans compte) :
`/.well-known/oauth-protected-resource/mcp` renvoie la ressource
`https://mcpeu.coros.com/mcp` et le serveur d'autorisation
`https://mcpeu.coros.com` ; `/.well-known/oauth-authorization-server` annonce
`registration_endpoint` (`/connect/register`, enregistrement dynamique), PKCE
`S256`, `refresh_token`, le flux par code d'appareil, et les scopes `openid
mcp.tools offline_access`. Un POST sur `/mcp` sans jeton répond 401 avec
`WWW-Authenticate: Bearer resource_metadata=…`, comme le veut le protocole.

**Pas essayé** : l'enregistrement de Pilote chez Coros (il crée un client sur
leur serveur : refusé pendant le développement, il se fera au premier clic
d'Arthur sur « Connecter »), et donc toute la suite avec un vrai compte.

## Coros (coros.py, coros.json)

API Python : `load_coros()` → `{connecte, connecteLe, depuis, choix, derniere,
jours}` ; `save_coros_connexion(depuis)` rend l'adresse de la page de Coros ;
`load_coros_etat()` suit la connexion (`etat` : `attente`, `ok`, `erreur`) ;
`save_coros_annuler()` ; `save_coros_reglages(choix, depuis)` ;
`save_coros_deconnexion()` ; `save_coros_synchro()` ; `save_coros_vus(ids)`.

### Connexion

1. `_decouvrir` lit les adresses OAuth sur le serveur MCP (RFC 9728, puis RFC 8414).
2. Un petit serveur s'ouvre sur `127.0.0.1`, port libre, chemin `/coros/retour`
   (pas le serveur de Pilote : ses trois verrous restent intacts).
3. Pilote s'enregistre (`client_name` « Pilote », client public, sans secret),
   puis la page ouvre l'adresse de connexion de Coros dans le navigateur, avec
   PKCE et un `state` aléatoire. Un retour avec un autre `state` est refusé.
4. Le code est échangé contre les jetons ; le **jeton de renouvellement** est
   chiffré comme la clé Garmin (`actus._chiffrer`, service « Pilote Coros ») ;
   le jeton d'accès vit en mémoire (`_acces`). Coros peut renouveler le jeton à
   chaque usage : le nouveau remplace l'ancien.
5. 5 minutes au plus (`ATTENTE_MAX`) ; « Annuler » arrête l'attente.

Déconnecter retire le jeton chez Coros (`revocation_endpoint`, si en ligne),
puis l'oublie ; la forme déjà lue reste.

### Lecture (MCP)

JSON-RPC sur HTTP : `initialize`, `notifications/initialized`, `tools/list`,
`tools/call` ; réponse en JSON ou en flux SSE (les deux sont lus), en-tête
`Mcp-Session-Id` repris. **Coros ne publie ni les noms de ses outils ni la
forme de leurs réponses** : Pilote les reconnaît par leurs mots.

* Séances : le premier outil dont le nom ou la description parle d'`activit`,
  `workout`, `sport record`, sauf `fit`, `file`, `plan`, `schedule`, `lap`,
  `split`, `detail`, `feedback`.
* Forme : chaque outil qui parle de `sleep`, `hrv`, `resting`, `daily`, `step`,
  `recover`, sauf les séries (`series`) et les séances.
* **Aucun outil d'écriture n'est appelé** (`create`, `update`, `delete`,
  `edit`, `add`, `save`, `upload`, `set_`, `write`, `remove` dans le nom) :
  depuis le 21/09/2026, le serveur sait créer des plans d'entraînement.
* Dates : d'après le schéma de l'outil (`start…`/`end…`, `yyyyMMdd` si la
  description le dit, entier `20261103`, horodatage si « timestamp »).
* Champs, par leurs noms usuels : identifiant (`labelId`, `activityId`…),
  début (`startTime`, `date`), sport (`sportType`, par centaines : 1xx course
  sauf 104/105 rando, 2xx vélo, 3xx natation, 402 muscu ; **à vérifier**),
  durée en s (ms au-delà de 2 jours), distance en m, kcal (divisées par 1 000
  au-delà de 20 000 : Coros les donne parfois en calories), D+, FC moyenne ;
  forme : sommeil (min, s au-delà de 1 440), VFC, FC au repos, pas,
  récupération (%).
* `apercu` dans `coros.json` : les noms des outils et des champs vus, **jamais
  de valeurs**. C'est ce qu'il faut lire après le premier essai réel pour
  corriger la reconnaissance.

Comme Garmin : Python n'écrit pas `sports.json` (la page ajoute par
`gaAjouter` avec `{cle: "corosId"}`), `vus` empêche une séance supprimée de
revenir, relecture depuis la dernière synchronisation moins 7 jours, une
source en panne n'arrête pas les autres mais `derniere` n'avance pas.
Synchronisation au lancement (6 s après) si la dernière date de plus d'une
heure, à l'ouverture de Ma forme, toutes les 2 heures, au bouton.

## Fichiers .fit (fit.py)

Lecteur du format FIT (FIT SDK de Garmin) écrit sans dépendance : en-tête,
définitions (petit et grand boutiste, champs développeur sautés), en-têtes
compressés. Trois messages lus : `file_id` (fabricant, pour le badge),
`session` (une séance par session : un fichier multisport en donne plusieurs),
`activity` (décalage de l'heure locale de la montre ; sinon celui du PC).
Valeurs « invalides » du SDK (0xFF…) ignorées ; fichier coupé : ce qui précède
la coupure est gardé. Un `.zip` (export complet) est ouvert, 2 000 fichiers au
plus, 50 Mo par fichier.

`fit_lire(fichiers)` (pont, lecture seule) rend les séances avec un `fitId`
(empreinte du début, du sport et de la durée : le même fichier relu donne le
même). La page les montre cochées ; celles déjà dans Sports (même `fitId`, ou
même séance d'après `gaMemeSeance`) sont grisées. Rien n'entre dans Sports
avant « Ajouter ». Pas de `vus` : réimporter un fichier dont on a supprimé la
séance la remet, c'est voulu (geste explicite).

## Ce qu'il ne faut pas défaire

1. **Une seule séance par sortie** : `gaMemeSeance(s, g, cle)` — une séance déjà
   venue d'une montre ou d'un .fit n'est la même qu'à 10 min près (même jour,
   même sport) ; une séance saisie à la main garde la règle de Garmin (durée à
   15 min ou 25 % près). Une séance qui a déjà son identifiant pour cette source
   n'en reçoit pas un second.
2. **`gaJours()` mêle Garmin et Coros** : Garmin l'emporte un jour où les deux
   ont mesuré. Ma forme, ses tuiles et le bilan de la semaine en dépendent.
3. `spSaveSession` garde `garminId`, `corosId`, `fitId`, `marque`, `fcMoy`,
   `kcal`, `record` d'une séance modifiée.
4. La section garde l'id `sec-garmin` et le module de chargement lit les deux
   (`MODULES_A_CHARGER`, « montres »).
5. **Reproposée une fois** (demande d'Arthur, 03/11/2026) à qui avait refusé
   Garmin en 4.4.52 : `S.uiPrefs.montresProposees`, posé par
   `_demanderNouveauxModules` (qui retire alors `sec-garmin` de `modulesConnus`
   si la section est masquée) et par les Premiers pas. Essayé sur le banc :
   proposée après un refus, pas après un « oui », pas une seconde fois.

## Tuiles

* `mo-derniere` « Séance de la montre » : la dernière venue de Garmin, Coros
  ou d'un .fit (distance ou durée en grand, d'où elle vient).
* `mo-synchro` « Synchro des montres » : seulement avec une montre connectée ;
  heure de la dernière synchronisation de chacune, rouge « À reconnecter » si
  l'accès est refusé ou la clé Garmin expirée, jours restants de la clé dans
  les deux semaines.
* `co-forme` « Forme Coros » : récupération du jour (barre), sommeil, VFC.

Module « Montres » dans `DASH_WIDGETS`, prêtes quand Garmin et Coros sont lus.

## Tests

* `tests/test_fit.py` (5 cas) : fichiers fabriqués d'après le SDK (petit et
  grand boutiste, champ développeur, en-tête compressé, multisport, valeurs
  invalides, fichiers refusés ou coupés).
* `tests/test_coros.py` (6 cas) : faux serveur d'après ce que le vrai annonce
  (découverte, enregistrement, PKCE vérifié, rotation du jeton) et le
  protocole MCP (JSON et SSE). Les noms d'outils et de champs y sont des
  **suppositions**.
* Banc navigateur du 03/11/2026 (données de Camille) : import d'un .fit,
  réimport grisé, fichier abîmé signalé, écrans Coros (sans connexion et
  connecté, simulé), Ma forme avec la récupération, tuiles, aucune erreur en
  console. Le bouton « Connecter » n'a pas été cliqué (il aurait enregistré
  Pilote chez Coros).

## À vérifier avec un vrai compte Coros

Tout ce qui suit la découverte : l'enregistrement accepté, la page de
connexion, la durée des jetons, les **noms des outils et des champs**
(`apercu`), les codes `sportType`, les unités (distance, kcal, sommeil), et un
vrai .fit exporté de l'app Coros.
