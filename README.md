# Pilote

Application Windows et Mac de suivi personnel : bourse (PEA et comptes-titres), budget,
prêt, sport, patrimoine, santé et newsletters réunis dans une seule app, sans compte ni
serveur. Les cours sont actualisés automatiquement depuis Yahoo Finance.

▶ [Vidéo de présentation](https://drive.google.com/file/d/1jA8N2ddIVyI6T9nbTnmhDlv6lp5w70gn/view?usp=drive_link)

## ✨ Les huit modules

**PEA** : positions, transactions, versements, dividendes, wishlist, expositions sectorielle
et géographique, courbe du capital comparée à des indices, prochain achat et simulateur
d'ordres, règles de stratégie vérifiées automatiquement, rapport annuel imprimable.

**CTO** (comptes-titres) : une section par compte, avec les mêmes écrans que le PEA, le
courtier et sa grille de frais, et l'import des relevés (Trade Republic, Fortuneo et
d'autres banques).

**Mes comptes** : budget mois par mois, dépenses et revenus catégorisés, échéances
récurrentes, récapitulatif annuel.

**Prêt** (nom libre) : suivi d'un prêt, par exemple un prêt étudiant placé : versements et
remboursements, PEA dédié, assurance vie, livret, frais.

**Sports** : agenda des séances, sports personnalisés, objectifs, statistiques d'heures.

**Patrimoine** : tous tes comptes relevés une fois par mois (le PEA, les CTO et le prêt se
remplissent seuls), biens immobiliers et leur crédit, valeur nette et son évolution.

**Santé** : pesées et mesures saisies à la main ou lues sur des captures de l'app FitDays.

**Actus** : la boîte Gmail qui reçoit tes newsletters, lue dans Pilote, avec un mot de passe
d'application Google gardé chiffré par Windows, ou dans le Trousseau sur Mac.

Chaque module se masque s'il ne sert pas.

## ⚙ Transverse

- **Accueil** avec les chiffres qui comptent, en tuiles à choisir
- **Multi-utilisateurs** : chaque utilisateur a tous ses modules à lui, rien n'est partagé
- **Code PIN** à 4 chiffres par utilisateur. Il sépare les espaces dans Pilote ; il ne
  chiffre pas les fichiers, lisibles par quiconque ouvre ta session Windows ou macOS
- **Thèmes** clair et sombre, couleur d'accent au choix
- **Sauvegarde** sur clé USB ou dans un dossier, avec restauration
- **Mise à jour automatique** depuis les releases GitHub

## 📦 Installation

### Sur Windows

1. Télécharger la dernière version : [Releases](../../releases/latest)
2. Lancer **`Pilote_Setup.exe`**
3. Si Windows SmartScreen affiche un avertissement : « Informations complémentaires »,
   puis « Exécuter quand même » (Pilote n'est pas signé : un certificat est payant)
4. Suivre l'assistant, puis lancer Pilote depuis le menu Démarrer ou le raccourci du bureau

Si Pilote ne démarre plus après une mise à jour, relance le Setup de la dernière version :
tes données sont conservées.

### Sur Mac (puce Apple uniquement, M1 et suivants)

**Le plus simple : une ligne dans le Terminal** (Applications → Utilitaires → Terminal).
La copier, la coller, puis Entrée :

```bash
curl -fL https://github.com/arthur-soulard/arthurpilote.github.com/releases/latest/download/Pilote_Mac.zip -o /tmp/Pilote_Mac.zip && ditto -x -k /tmp/Pilote_Mac.zip /Applications && open /Applications/Pilote.app
```

Elle télécharge Pilote, le range dans Applications et l'ouvre. Aucun réglage à faire :
l'avertissement de macOS sur les apps non signées ne vise que les fichiers téléchargés
par un navigateur.

**Ou par le navigateur :**

1. Télécharger **`Pilote_Mac.zip`** depuis la dernière version : [Releases](../../releases/latest).
   Le Mac le décompresse tout seul en **Pilote**. Il ne fonctionne pas sur un Mac Intel.
2. Ouvrir Pilote. Il n'est pas signé par Apple (pas de compte développeur payant) :
   macOS refuse de l'ouvrir. Fermer le message.
3. Ouvrir **Réglages Système → Confidentialité et sécurité**, descendre jusqu'au message
   sur Pilote et cliquer sur **Ouvrir quand même**, puis confirmer avec le mot de passe
   du Mac. Ce n'est à faire qu'une fois.
4. Ouvert depuis Téléchargements, Pilote propose de se ranger lui-même dans le dossier
   Applications : accepter (sans ça, il ne pourrait pas se mettre à jour).

Les mises à jour suivantes sont faites par Pilote lui-même. Les données vivent dans
`~/Library/Application Support/Pilote/Donnees`, hors de l'app : la remplacer ne les touche pas.

### Compatibilité

- **Windows 10 / 11 x64**, avec Microsoft Edge WebView2 Runtime (préinstallé sur Windows 11
  et sur Windows 10 à jour). Windows sur processeur ARM : non essayé.
- **Mac à puce Apple** (M1 et suivants), essayé sur macOS 15 Sequoia
- Connexion internet pour les cours ; sans elle, Pilote montre les derniers cours connus

## 🔒 Confidentialité

Tes données restent sur ton ordinateur, en fichiers JSON **non chiffrés**. Pilote n'a ni
compte, ni serveur, ni mesure d'audience. Il contacte seulement :

| Site | Quand | Ce qui part |
|---|---|---|
| Yahoo Finance | au lancement, puis toutes les 3 min ; recherche d'un titre | la liste de tes titres (tickers), jamais les quantités ni les montants, et ton adresse IP |
| GitHub | au lancement, et pour une mise à jour | ton adresse IP et la version installée |
| justETF, Euronext, iShares, Amundi | quand un ETF détenu n'a pas encore de composition connue, ou sur « Mettre à jour les données » | l'identifiant public de l'ETF (ISIN) |
| Gmail | si tu actives Actus | ton adresse et ton mot de passe d'application, pour lire ta boîte |
| Expéditeurs des newsletters | à l'ouverture d'un mail, si tu affiches ses images | ton adresse IP et l'heure d'ouverture |

Sources des données : cours de Yahoo Finance ; compositions d'ETF d'iShares, d'Amundi et de
justETF. Ce sont des sources non officielles, utilisées sans garantie.

Pilote calcule à partir de tes saisies et de tes règles. Il ne donne pas de conseil en
investissement.

Pour signaler une faille de sécurité : voir [SECURITY.md](SECURITY.md).

## 🛠 Développement

- Python 3.8 sur le poste de développement, 3.11 pour l'app fabriquée par GitHub Actions
- `pip install -r requirements.txt`, puis `python src/app.py`
- Build Windows : `python -m PyInstaller build/pilote.spec --clean --noconfirm`, puis
  `ISCC.exe build/installer.iss` (Inno Setup 6) ; build Mac : `build/pilote-mac.spec`
- Avant une version : `python tests/verifier_release.py vX.Y.Z` et `python -m unittest discover tests`

L'architecture, les données sur disque et les règles du projet sont décrites dans
[CLAUDE.md](CLAUDE.md) et les fiches de [docs/](docs/).

## 📂 Où sont les données

- Windows : `%LocalAppData%\Programs\Suivi PEA\Donnees\` (nom historique du dossier
  d'installation), un dossier par utilisateur dans `users/`
- Mac : `~/Library/Application Support/Pilote/Donnees/`

Le chemin exact s'affiche aussi dans Pilote : Paramètres → Données.

## 📜 Licence

Pilote est sous licence MIT : voir [LICENSE](LICENSE). Les licences des composants
embarqués (Python, pywebview, Pillow, pypdf, Chart.js, Phosphor, polices…) sont dans
[THIRD-PARTY-NOTICES.txt](THIRD-PARTY-NOTICES.txt), aussi installé avec l'app.
