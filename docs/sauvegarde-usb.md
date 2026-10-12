# Sauvegarde USB

Fiche détaillée tirée de `CLAUDE.md`, qui garde les règles générales (dont les six choses à ne jamais casser).

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

## Les quatre réglages de la clé (12/10/2026, Windows et Mac)

Demandés par Arthur le 11/10 avec le chantier Mac (`docs/mac.md`). Tous dans
`sauvegarde.json`, validés par `appliquer_reglages()` (seule porte d'écriture
depuis l'UI : `Api.sauvegarde_set_config`). Paramètres → Sauvegarde USB.

| Réglage | Clés de `sauvegarde.json` | Effet |
|---|---|---|
| Mes clés autorisées | `clesAutorisees` : `[{serial, label}]` | Vide (défaut) : toute clé branchée convient, comme avant. Sinon le bouton Téléverser et l'accueil ne voient que ces clés (par numéro de série / UUID ; une clé sans numéro, par son nom). `status()` marque chaque clé branchée `autorisee`. Les archives vont toujours à la destination choisie |
| Dossier et contenu | `dossierCle` (« Pilote »), `avecBackups` (oui) | Dossier du miroir à la racine de la clé, nettoyé (`_dossier_cle` : un seul nom, ni `/` ni `..`) ; `avecBackups=False` écarte les `backups*` des modules du miroir **et** des archives. L'archive de sécurité d'une restauration garde tout |
| Moment et alerte | `moment` (`demarrage` / `branchement` / `fermeture`), `alerteJours` (7, 0 = jamais) | `app.py` : un fil relit `moment` toutes les 20 s ; « dès que la clé est branchée » tente `auto_backup_if_due()` à chaque tour (10 min après un échec d'écriture), « à la fermeture » la lance en fin de `main()`. Clé absente : le statut n'est réécrit que s'il change (pas une écriture toutes les 20 s). L'accueil et la tuile lisent `alerteJours` par `svAlerteJours()` |
| Éjecter après copie | `ejecter` (non) | Après un téléversement ou une archive sur une clé détectée (`_cle_de`) : `ejecter(root)`. Windows : verbe `Eject` de l'Explorateur par PowerShell, puis vérifie que la clé a disparu ; Mac : `diskutil eject`. Le résultat (`ejection`) donne un message « Clé éjectée : tu peux la retirer », ou la raison |

Essais du 12/10/2026 : 16 vérifications sous Windows sur une copie, un dossier
temporaire jouant la clé (autorisées, nom de la clé sans numéro, dossier nettoyé,
miroir sans backups, rien sur la clé non autorisée, éjection demandée, archive
avec backups, valeurs refusées, pas de réécriture quand la clé manque), et
l'écran dans un banc navigateur (enregistrement de chaque réglage, Autoriser /
Retirer avec un nom à apostrophe). **L'éjection sous Windows n'a pas été
essayée avec une vraie clé.**

Corrigé au passage : les boutons « Restaurer » et des clés détectées mettaient le
chemin dans le code du `onclick` ; un nom avec une apostrophe (« Clé d'Arthur »,
courant sur Mac) cassait le clic. Chemin désormais en `data-path` / `data-root`.

## Sur Mac (`_mac_cles`)

Pas de lettre : la clé est son point de montage (`/Volumes/CLE`, `letter` vide,
le nom dans `label`), retrouvée par l'UUID de son volume (`diskutil info -plist`,
`VolumeUUID`) au lieu du numéro de série de Windows. Écartés : le disque du Mac
(lien vers `/`), les images disque (`BusProtocol` « Disk Image ») et les partages
réseau (inconnus de diskutil). Retenu : ce qui n'est pas interne, ou interne mais
amovible (lecteur de carte SD). `set_destination` reconnaît un dossier choisi
sous `/Volumes/<clé>/…`. Une config faite sous Windows ne suit pas sur Mac
(`sauvegarde.json` n'est jamais restauré, et l'UUID n'est pas le numéro de série).

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
* À partir de `svAlerteJours()` jours pleins (réglage `alerteJours`, 7 par
  défaut, 0 = jamais ; c'était la constante `SV_ALERTE_JOURS`), la ligne sous les boutons de
  l'accueil (`#home-usb-state.vieux`, couleur `--a`) écrit « Dernière sauvegarde
  sur clé il y a N jours » et quoi faire : « branche ta clé USB », ou « clique sur
  Téléverser » si une clé est branchée.
* Aucune copie jamais faite : en gris, sans alerte (« aucune sauvegarde sur clé
  pour l'instant »), et la tuile écrit « Jamais » sans orange (11/10/2026). Jusque-là
  c'était l'alerte orange : tout nouvel utilisateur la voyait dès le premier
  lancement, et pour toujours s'il n'avait pas de clé.
* La tuile « Sauvegarde USB » lit la **même** date (`svDerniereCopie`) et passe en
  orange au même seuil : les deux ne peuvent pas se contredire.
