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
`assets/icon.ico` (`icon_512.png` n'est pas dans le dépôt : premier test en
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

## Reste à faire (02/11/2026)

1. **Arthur** : compte Partner Center de particulier (gratuit, pièce
   d'identité et selfie), puis réserver le nom de l'app (« Pilote » s'il est
   libre). Ça donne l'identité et l'éditeur à passer à `build/msix.py`.
2. Politique de confidentialité en ligne (site GitHub Pages) : aucune donnée
   collectée, deux exceptions voulues (Gmail d'Actus, iCloud d'Agenda).
3. Fiche du store : description, captures sur les données d'exemple de Camille,
   classification par âge.
4. Joindre `Pilote.msix` à la release (`release.yml`), puis première soumission.
