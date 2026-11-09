# Utilisateurs et code PIN

Fiche détaillée tirée de `CLAUDE.md`, qui garde les règles générales (dont les six choses à ne jamais casser).

## Multi-utilisateurs

* API Python (`Api` dans app.py) : `get_users`, `add_user(label, emoji, color)`,
  `update_user`, `delete_user`, `set_active_user`.
* `storage.slugify()` fabrique le slug de dossier. `delete_user` retire l'utilisateur
  de la liste mais **conserve son dossier** sur le disque.
* Côté JS : `USERS_STATE`, `_loadUsers(force)`, `renderHomeUsers()`, `switchUser(slug)`
  (bascule + `location.reload()`), `openUserModal(slug|null)`, `renderUsersList()`,
  `_renderUserPill()` (pastille en bas de sidebar), `userAvatarHtml(u, cls)`.
  La pastille de la sidebar prend `var(--accent)` (demande d'Arthur, 27/10/2026) :
  elle suit la couleur d'accent comme l'icône de l'app, sans redessin. La couleur
  propre de chaque utilisateur (`u.color`) reste celle de l'accueil et de la liste.
* `server.with_pin_flags(state)` ajoute `hasPin` à chaque utilisateur — utilisé pour
  afficher le cadenas 🔒.
* **Bascule sans fuite (4.3.14)** : le fichier visé par une écriture est choisi côté
  Python **au moment d'écrire**. Une écriture encore en attente (délai de 0,4 s du
  PEA et de Mes comptes, actualisation des cours) pouvait donc partir après la
  bascule, dans le dossier du nouvel utilisateur (lu dans le code). `switchUser` et la suppression de
  l'utilisateur actif appellent d'abord `_gelerEnregistrements()` : tout ce qui
  attend part chez l'utilisateur actuel, puis plus rien n'est écrit jusqu'au
  rechargement. Essayé : saisie + écriture déclenchée pendant la bascule → la
  saisie chez l'ancien utilisateur, rien chez le nouveau.
* **Isolation** : `storage.scan_orphan_data()` exclut tout ce qui vit sous
  `get_app_dir()`. Sans ça l'écran de bienvenue proposerait d'importer les données
  d'un autre utilisateur de la même installation. Ne pas retirer ce filtre.
  Elle ne descend qu'à 5 niveaux sous Bureau, Documents et Téléchargements
  (`_fichiers_proches`, 4.4.42) : `rglob` parcourait tout avant de filtrer.
* **Pas de copie du PEA dans le `localStorage`** (4.4.42, audit du 31/10/2026).
  Le PEA lu au démarrage passe à `loadState` par la variable `_peaLu`. Avant, il
  transitait par la clé `pea4_v4`, commune à tous les utilisateurs : si les deux
  lectures échouaient, l'écran montrait le PEA du dernier utilisateur ouvert.
  L'ancienne clé est effacée au démarrage. `pea4_v4_var` et `pea4_v4_hist`
  (cours et historiques Yahoo, régénérables) restent.

## Code PIN (un par utilisateur)

* Hash SHA-256 salé dans `users/<slug>/pin.hash`.
* Endpoints `/pin/required`, `/pin/set`, `/pin/check` — tous acceptent `?user=<slug>` ;
  sans ce paramètre ils répondent pour l'utilisateur actif.
* JS : `_isPinRequired(slug)`, `_verifyPin(pin, slug)`, `_setPinServer(pin, slug)`,
  `_checkPinLock()` (écran de verrouillage, awaité dans `boot()` **avant** `renderAll()`).
* L'écran de verrouillage affiche l'avatar + le nom du compte verrouillé et propose
  d'ouvrir un autre compte (chacun reste protégé par son propre code).
* Ça sépare les espaces, ça ne chiffre rien : les JSON restent lisibles sur le disque.

## Audit du 20/10/2026 (4.4.21)

* Un nouvel utilisateur ne retombe jamais sur le dossier d'un utilisateur supprimé :
  `slugify` tient compte des dossiers de `users/`. Les noms réservés de Windows (`nul`,
  `con`…) reçoivent un suffixe, et le dossier est créé avant l'inscription dans `users.json`.
* Un `users.json` illisible est gardé à côté (`users.illisible-<date>.json`) et la liste est
  refaite à partir des dossiers.
* Les routes `/pin/*` n'acceptent qu'un utilisateur de `users.json`.

## Revue du 09/11/2026

* `/pin/set` vérifiait l'ancien code sans frein : par cette route, les 10 000 codes
  s'essayaient à la chaîne. L'ancien code passe désormais par le même délai (0,25 s)
  et le même blocage (60 s après 10 échecs, compteur partagé avec `/pin/check`) ;
  la page affiche « Trop d'essais » sur un 429. Test : `tests/test_serveur.py`.
* Reste assumé : le code part dans l'adresse de la requête (GET local, jamais
  journalisé : `log_message` ne fait rien).

## Explorer avec des données d'exemple (09/11/2026, prochaine version)

Pour découvrir Pilote sans rien saisir (lancement grand public). Le bouton est à
l'étape 3 des Premiers pas (encart « Envie de voir avant de saisir ? ») et dans
Paramètres › Utilisateurs (« Découvrir Pilote »).

* **Un utilisateur à part**, jamais celui qui explore : `storage.ouvrir_exemple()`
  crée un utilisateur « Exemple » marqué `"exemple": true` dans `users.json`, dans un
  dossier **neuf** (`slugify` écarte les dossiers déjà sur le disque, un ancien
  dossier `exemple` n'est donc jamais réécrit), y écrit les données fictives de
  Camille, puis en fait l'utilisateur actif. Les fichiers de celui qui explore ne
  sont ni lus ni écrits, sauf `ui`, `uiPrefs.theme` et `uiPrefs.accent` de son
  `pea_data.json`, **lus** pour que l'exemple garde son thème et sa fenêtre.
* Le jeu de données est `src/donnees_exemple.py` (déplacé de `tests/` pour être
  livré avec l'exe ; `tests/donnees_exemple.py` n'est plus qu'un lanceur, la
  commande du test Mac ne change pas). Dates relatives au jour de création.
  La fiche des nouveautés de la version installée est tenue pour lue.
* `"retour"` retient qui explorait. **Bandeau** en haut de chaque écran tant que
  l'actif est l'exemple (`#ex-bandeau`, `_renderBandeauExemple()` appelée dans
  `boot()`) : « Revenir à <nom> » (`quitter_exemple(false)`) et « Effacer
  l'exemple » (`quitter_exemple(true)` : retour, puis l'utilisateur et son dossier
  supprimés). Pas de confirmation : ce sont des données fictives, recréées au
  prochain clic.
* Effacer ne supprime définitivement le dossier que s'il porte le témoin
  `exemple-pilote.txt` écrit à la création ; sinon il part à la corbeille, comme
  un utilisateur effacé.
* Bascule comme `switchUser` : `_gelerEnregistrements()` avant, `_degelerEnregistrements()`
  si le pont répond une erreur, puis `location.reload()`. `_hydrationDone` n'est pas
  touché : la page se recharge et relit l'utilisateur actif comme au démarrage.
* Le code PIN n'est pas contourné : l'exemple n'en a pas, mais revenir à un
  utilisateur protégé recharge la page, qui redemande son code.
* Depuis les Premiers pas, les choix de l'assistant (modules, prénom) sont d'abord
  enregistrés pour l'utilisateur qui découvre (`terminer`, qui attend l'écriture
  du prénom dans `users.json` avant la bascule : deux écritures du même fichier
  en parallèle en perdaient une).
* **Pas de tuile d'accueil** : la règle « toute fonctionnalité vient avec ses
  tuiles » ne s'applique pas à un mode de découverte, qui n'a rien à suivre. Le
  bandeau tient ce rôle. L'exemple, lui, a toutes ses tuiles allumées.
* Tests : `tests/test_donnees.py`, classe `Exemple` (aller-retour sans toucher un
  octet du `pea_data.json` de l'utilisateur, un seul exemple, effacer, ancien
  dossier `exemple` intact, sans témoin → corbeille, exemple resté seul → « Moi »).
