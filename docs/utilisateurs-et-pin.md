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
