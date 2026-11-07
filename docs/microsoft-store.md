# Microsoft Store

Décidé avec Arthur le 02/11/2026 : Pilote reste **entièrement gratuit** pour
attirer des utilisateurs, et le Microsoft Store est le premier store visé
(inscription gratuite pour un particulier, signature offerte par Microsoft,
plus d'avertissement SmartScreen au premier lancement). Le Setup actuel
(`Pilote_Setup.exe`, auto-update par GitHub) continue à côté : rien ne change
pour les installations existantes.

## Paquet MSIX, pas le Setup

Le Store accepte aussi un `.exe` ou un `.msi`, mais il doit alors être signé
par un certificat acheté (Microsoft ne re-signe que les paquets MSIX). Le
paquet MSIX, lui, est re-signé par le Store : aucun certificat à acheter.

`build/msix.py` le fabrique à partir de `dist/Pilote/` (après PyInstaller) :
copie de l'app, `build/AppxManifest.xml` rempli (identité, éditeur,
version de `src/app.py` au format `4.4.50.0`), logos tirés de
`assets/icon_win.ico`, carrée pleine depuis la 4.4.62 :
Windows pose l'icône sur une plaque à la couleur du système, bleue dans les coins
arrondis de `icon.ico`, que le Mac garde (`icon_512.png` n'est pas dans le dépôt : premier test en
échec le 02/11/2026), puis `makeappx pack` du Windows SDK.

```
python build/msix.py --identite <Nom du paquet> --editeur "CN=<...>" --nom-editeur "<...>"
```

Identité et éditeur viennent de Partner Center (produit > Identité du produit).
Sans eux, des valeurs d'essai (`Pilote.Essai`, `CN=Pilote Essai`) : le paquet
s'installe sur une machine de test, pas dans le Store.

L'app tourne en confiance totale (`runFullTrust`) : serveur local sur
127.0.0.1, PowerShell pour l'OCR, Edge pour le PDF du bilan, comme avec le Setup.

## Ce qui change dans la version Store

`plateforme.version_store()` la reconnaît : un paquet a une identité, que
`GetCurrentPackageFullName` rend (le Setup et le dev rendent 15700,
« pas de paquet »).

* **Données dans `C:\Users\<nom>\Pilote\Donnees`** (`storage.get_app_dir`).
  Le dossier de l'exe (`WindowsApps`) est en lecture seule, et le dossier privé
  du paquet (`AppData\Local\Packages\…`) est **effacé à la désinstallation** :
  la panne d'avant la 4.3.13. Documents était l'autre choix, écarté par Arthur :
  sous Windows 11, OneDrive le synchronise souvent, et les données sortiraient
  du PC.
* **Pas d'auto-update** : le Store met l'app à jour et interdit qu'elle
  s'installe autre chose. `updater.start_check` répond « à jour » avec
  `store: True` sans rien demander à GitHub ; Paramètres affiche « Les mises à
  jour arrivent par le Microsoft Store ».
* **Pas de raccourcis recolorés** (`appicon.apply_to_shortcuts`) : le paquet
  n'a pas de `.lnk`, et ceux trouvés seraient ceux du Setup s'il est aussi
  installé. La fenêtre garde l'icône à l'accent.
* Ce qu'écrit Pilote dans `%APPDATA%` (journal `update.log`, profil WebView2)
  est redirigé par Windows dans le dossier privé du paquet : sans conséquence,
  rien d'irremplaçable n'y vit.

Le Setup et la version Store ne tournent pas en même temps (un seul Pilote à
la fois, `SINGLE_INSTANCE_PORT`), et n'ont pas les mêmes données : passer de
l'un à l'autre se fait par la sauvegarde (restauration), pas automatiquement.

## Test

`build-windows.yml` (branche `mac`), étape « Build and try the Store package » :
fabrique le paquet, le signe avec un certificat d'essai, l'installe, le lance
par le menu Démarrer, attend le serveur, vérifie que l'exe lancé est bien celui
de `WindowsApps`, que `~\Pilote\Donnees` existe et pas `Donnees` dans le paquet,
puis désinstalle et vérifie que les données sont restées.

## Partner Center (02/11/2026)

* Compte de particulier, app « Pilote » réservée : ID Store `9NLZ93TP5HD3`,
  identité `ARSOL.Pilote` (réservée, à ne jamais changer), éditeur affiché
  « Pilote Appli » depuis le 07/11/2026 (« ARSOL » avant ; « Pilote » était déjà
  pris chez Microsoft). Valeurs par défaut de `build/msix.py`.
* Compte Microsoft de connexion : `pilote.appli@gmail.com` (alias principal,
  07/11/2026), même adresse en contact du vendeur.
* `Pilote.msix` est joint à chaque release (`release.yml`), à déposer à la
  main dans Partner Center (28 Mo).
* Politique de confidentialité : https://arthur-soulard.github.io/pilote/confidentialite.html
  (dépôt du site, `pilote/confidentialite.html`).
* Première soumission (v4.4.51) envoyée le 02/11/2026 : gratuite, **lien
  direct seulement** (pas dans les recherches), 3 ans et plus (IARC),
  catégorie Finances personnelles › Banque + investissements, 7 captures
  1366 × 768 au nom de **Brice** (pas Camille dans ce qui est public, demande
  d'Arthur), publication **manuelle** (« Publier maintenant » après la
  certification). Justification de `runFullTrust` limitée à 500 caractères.
* Ensuite : Arthur installe depuis le lien du Store et fait le tour des
  fonctions, puis on passe la visibilité à « détectable ». À chaque nouvelle
  version, nouvelle soumission avec le nouveau `Pilote.msix`.
* État vérifié le 06/11/2026 : fiche **détectable** dans le Store (recherche et
  navigation), public, tous les pays ; soumission n° 4 publiée avec la v4.4.62.0.
