# Sauvegarde USB

Fiche détaillée tirée de `CLAUDE.md`, qui garde les règles générales (dont les cinq choses à ne jamais casser).

## Sauvegarde externe sur clé USB (`sauvegarde.py`)

Contrairement à tout le reste, ce module est au niveau de **l'installation**, pas de
l'utilisateur : une sauvegarde embarque le dossier `Donnees/` entier (tous les
espaces, `users.json` compris), pour pouvoir remonter l'installation complète.
Sa config vit donc dans `Donnees/sauvegarde.json`, à côté de `users.json`.

* Une sauvegarde = `Pilote_YYYY-MM-DD_HHhMM.zip` dans la destination. Deux
  sauvegardes dans la même minute portent le même nom et s'écrasent : c'est voulu.
* Écriture en `.zip.part` puis `os.replace()` — une clé débranchée en plein milieu
  ne laisse jamais une archive tronquée sous un nom valide.
* `icones/` et les `.tmp` sont exclus (regénérables). Les `backups_*` sont inclus.
* **La clé est retrouvée par son numéro de série de volume**, pas par sa lettre :
  `E:` qui devient `F:` au rebranchement suivant est suivi automatiquement
  (`_volume_info()` via `GetVolumeInformationW`). Si la clé mémorisée est absente,
  on ne se rabat **pas** sur le chemin brut — il pointerait sur une autre clé ayant
  hérité de la lettre.
* **Un numéro de série nul (`00000000`) est traité comme absent.** Constaté sur une
  vraie clé FAT32 bas de gamme : elle n'en a pas. Le garder reviendrait à « reconnaître »
  n'importe quelle autre clé sans numéro. Repli alors sur le **nom de volume**, puis
  sur le chemin brut. Ne pas « simplifier » en refaisant confiance au numéro.
* Rotation : les `keep` archives les plus récentes (10 par défaut).
* Auto au démarrage dans un thread (`main()`), silencieuse si la clé est absente.
* `restore_from()` : valide l'archive, écrit une archive de sécurité de l'état
  actuel à côté de `Donnees/`, puis **écrase fichier par fichier sans vider le
  dossier** — une archive incomplète ne doit jamais faire disparaître un
  utilisateur qui n'y figure pas. `sauvegarde.json` est volontairement exclu de la
  restauration (sinon on repointerait vers une clé qu'on n'utilise plus).
  Protection zip-slip sur chaque membre.
* Côté page, `svRestore` gèle les enregistrements avant de restaurer
  (`_gelerEnregistrements`, 4.3.14) : une écriture en attente serait sinon passée
  **par-dessus** les fichiers restaurés, avant le rechargement. Même chose pour
  l'import d'un `pea_data.json` et la récupération d'une ancienne installation.
* API : `sauvegarde_status`, `sauvegarde_set_config`, `sauvegarde_pick_folder`,
  `sauvegarde_use_drive`, `sauvegarde_run`, `sauvegarde_list`,
  `sauvegarde_restore`, `sauvegarde_open_folder`, `sauvegarde_push_usb`,
  `sauvegarde_usb_state`.
* UI : Paramètres → **Sauvegarde USB** (`data-sec="sauvegarde"`), fonctions `sv*`.
  `setGoSection()` déclenche `svRefresh()` seulement à l'ouverture de cette
  section — elle interroge le disque.
* Rien n'est chiffré : le zip est aussi lisible que les JSON d'origine.

**Deux mécanismes distincts, volontairement :**

| | Bouton « 🔑 Téléverser » (accueil) | Archives (Paramètres) |
|---|---|---|
| Écrit | `<clé>/Pilote/Donnees/` en miroir | `Pilote_<date>.zip` |
| Historique | aucun, on écrase | rotation des N dernières |
| Pour | récupérer ses fichiers tout de suite | remonter dans le temps |

`push_to_usb()` choisit la clé toute seule s'il n'y en a qu'une, sinon l'UI
demande laquelle. Le miroir **n'efface jamais** de fichier sur la clé : un
dossier Donnees vidé par accident ne doit pas détruire la sauvegarde.

**Sauvegarde trop ancienne : l'accueil le dit en orange (01/10/2026).** Constaté le
30/09 : dernière archive le 23/09, dernier envoi le 24/09, clé débranchée depuis, et
seule une ligne grise « dernier envoi 24 sept. » le disait. Désormais :

* `svDerniereCopie(s)` = la plus récente des deux dates, envoi (`lastPushAt`) ou
  archive (`lastBackupAt`, ajoutée à `usb_state()` pour ça) : l'une comme l'autre
  met les données sur la clé.
* À partir de `SV_ALERTE_JOURS` (7) jours pleins, ou si aucune copie n'a jamais été
  faite, la ligne sous les boutons de l'accueil (`#home-usb-state.vieux`, couleur
  `--a`) écrit « Dernière sauvegarde sur clé il y a N jours » et quoi faire :
  « branche ta clé USB », ou « clique sur Téléverser » si une clé est branchée.
* La tuile « Sauvegarde USB » lit la **même** date (`svDerniereCopie`) et passe en
  orange au même seuil : les deux ne peuvent pas se contredire.
