# Pilote

Application Windows et Mac de suivi personnel : bourse (PEA et comptes-titres), budget,
prêt, sport, patrimoine, santé et newsletters réunis dans une seule app, sans compte ni
serveur. Les cours sont actualisés automatiquement depuis Yahoo Finance.

▶ [Vidéo de présentation](https://drive.google.com/file/d/1jA8N2ddIVyI6T9nbTnmhDlv6lp5w70gn/view?usp=drive_link)

## Installer Pilote

### Ce qu'il faut avoir

| | Windows | Mac |
|---|---|---|
| Ordinateur | Windows 10 ou 11, 64 bits | Mac à puce Apple (M1 et suivants). **Pas un Mac Intel** |
| Système essayé | Windows 11 (Windows sur processeur ARM : pas essayé) | macOS 15 Sequoia (un macOS plus ancien n'a pas été essayé) |
| Composant | Microsoft Edge WebView2, qui dessine la fenêtre. Déjà là sur Windows 11 et sur un Windows 10 à jour ; sinon, le programme d'installation l'ajoute | rien |
| Internet | pour l'installation, les cours de bourse et les mises à jour. Sans connexion, Pilote s'ouvre et montre les derniers cours connus | pareil |

Pilote n'a pas besoin de compte. Seuls trois modules, facultatifs, demandent quelque chose
de plus :

- **Actus** : un compte Gmail avec la validation en deux étapes activée (Pilote s'y
  connecte avec un mot de passe d'application, que l'onglet Connexion t'aide à créer) ;
- **Agenda**, pour le voir et le faire sonner sur ton iPhone : un compte Apple avec la
  double authentification (l'onglet iCloud explique comment créer un mot de passe pour
  app). Sans iPhone, le calendrier marche quand même ;
- **Santé**, pour lire des captures de l'app FitDays : sur Windows, le français ou
  l'anglais parmi les langues de Windows (c'est le cas d'un Windows en français). La
  saisie à la main marche partout.

### Sur Windows

1. Télécharger **`Pilote_Setup.exe`** depuis la [dernière version](../../releases/latest)
   (rubrique *Assets*, en bas de la page).
2. Le lancer. Si Windows affiche « Windows a protégé votre ordinateur » : *Informations
   complémentaires*, puis *Exécuter quand même*. Ce message vient de ce que Pilote n'est
   pas signé (un certificat est payant).
3. Suivre l'assistant. Il ne demande pas de mot de passe administrateur : Pilote
   s'installe pour toi seul, dans ton dossier `AppData`.
4. Lancer Pilote depuis le menu Démarrer ou le raccourci du bureau.

### Sur Mac

**Le plus simple : une ligne dans le Terminal** (Applications → Utilitaires → Terminal).
La copier, la coller, puis Entrée :

```bash
curl -fL https://github.com/arthur-soulard/arthurpilote.github.com/releases/latest/download/Pilote_Mac.zip -o /tmp/Pilote_Mac.zip && ditto -x -k /tmp/Pilote_Mac.zip /Applications && open /Applications/Pilote.app
```

Elle télécharge Pilote, le range dans Applications et l'ouvre. Aucun réglage à faire :
l'avertissement de macOS sur les apps non signées ne vise que les fichiers téléchargés
par un navigateur.

**Ou par le navigateur :**

1. Télécharger **`Pilote_Mac.zip`** depuis la [dernière version](../../releases/latest).
   Le Mac le décompresse tout seul en **Pilote**.
2. Ouvrir Pilote. Il n'est pas signé par Apple (pas de compte développeur payant) :
   macOS refuse de l'ouvrir. Fermer le message.
3. Ouvrir **Réglages Système → Confidentialité et sécurité**, descendre jusqu'au message
   sur Pilote et cliquer sur **Ouvrir quand même**, puis confirmer avec le mot de passe
   du Mac. Ce n'est à faire qu'une fois.
4. Ouvert depuis Téléchargements, Pilote propose de se ranger lui-même dans le dossier
   Applications : accepter (sans ça, il ne pourrait pas se mettre à jour).

### Ensuite

Les mises à jour se font depuis Pilote : au lancement, il te montre ce que change la
nouvelle version et l'installe si tu le veux. Tes données restent en place.

## Premier lancement

Un assistant en trois étapes s'ouvre :

1. **Bienvenue** : ton prénom (il nomme ton espace) et l'endroit où vivent tes données ;
2. **Tes modules** : coche ce que tu veux suivre, le reste est masqué (Paramètres →
   Modules le remet) ;
3. **Par où commencer** : le premier geste de chaque module, et ce qu'il faut avoir pour
   ceux qui en demandent.

Plusieurs personnes peuvent partager l'ordinateur : chacune a son espace (Paramètres →
Utilisateurs), et peut le protéger par un code PIN.

## En cas de souci

**Windows : « Windows a protégé votre ordinateur ».** Normal pour une app non signée :
*Informations complémentaires*, puis *Exécuter quand même*.

**Windows : Pilote s'ouvre sur une fenêtre vide.** WebView2 manque, en général parce que
le PC n'avait pas internet pendant l'installation. Relance `Pilote_Setup.exe` avec une
connexion : il l'ajoute, tes données restent en place.

**Windows : « Pilote est déjà installé pour tous les utilisateurs ».** Une très ancienne
installation est dans Program Files. Désinstalle-la depuis les Paramètres de Windows (tes
données restent dans son dossier), puis relance le programme d'installation.

**Windows : Pilote ne démarre plus après une mise à jour.** Relance le `Pilote_Setup.exe`
de la dernière version : tes données sont conservées.

**Mac : macOS refuse d'ouvrir Pilote.** Passe par la ligne du Terminal ci-dessus, ou par
*Ouvrir quand même* dans Réglages Système → Confidentialité et sécurité. Sur un Mac Intel,
Pilote ne peut pas fonctionner.

**Les cours ne bougent pas.** Pilote a besoin d'internet pour les actualiser ; sans
connexion, il garde les derniers connus. Le bouton Actualiser est en haut de la fenêtre.

**Santé : la lecture des captures FitDays échoue sur Windows.** Ajoute le français ou
l'anglais dans Paramètres de Windows → Heure et langue → Langue, puis réessaie.

**Désinstaller.** Windows : Paramètres → Applications. Mac : glisser Pilote d'Applications
à la Corbeille. Dans les deux cas, tes données restent sur le disque (voir « Où sont les
données ») : réinstaller Pilote les retrouve.

## ✨ Les modules

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

**Agenda** : un calendrier de tout ce que Pilote sait dater, tes notes, et ton agenda
iCloud, qui fait sonner ton iPhone.

Chaque module se masque s'il ne sert pas.

## ⚙ Transverse

- **Accueil** avec les chiffres qui comptent, en tuiles à choisir
- **Multi-utilisateurs** : chaque utilisateur a tous ses modules à lui, rien n'est partagé
- **Code PIN** à 4 chiffres par utilisateur. Il sépare les espaces dans Pilote ; il ne
  chiffre pas les fichiers, lisibles par quiconque ouvre ta session Windows ou macOS
- **Thèmes** clair et sombre, couleur d'accent au choix
- **Sauvegarde** sur clé USB ou dans un dossier, avec restauration
- **Mise à jour automatique** depuis les releases GitHub

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
| iCloud | si tu connectes l'Agenda | ton identifiant Apple et ton mot de passe pour app ; tes notes et ce que tu coches |
| Microsoft | à l'installation sur Windows, seulement si WebView2 manque | ton adresse IP, pour télécharger WebView2 |

Sources des données : cours de Yahoo Finance ; compositions d'ETF d'iShares, d'Amundi et de
justETF. Ce sont des sources non officielles, utilisées sans garantie.

Pilote calcule à partir de tes saisies et de tes règles. Il ne donne pas de conseil en
investissement.

Pour signaler une faille de sécurité : voir [SECURITY.md](SECURITY.md).

## 📂 Où sont les données

- Windows : `%LocalAppData%\Programs\Suivi PEA\Donnees\` (nom historique du dossier
  d'installation), un dossier par utilisateur dans `users/`
- Mac : `~/Library/Application Support/Pilote/Donnees/`

Le chemin exact s'affiche aussi dans Pilote : Paramètres → Données.

## 🛠 Développement

- Python 3.8 sur le poste de développement, 3.11 pour l'app fabriquée par GitHub Actions
- `pip install -r requirements.txt`, puis `python src/app.py`
- Build Windows : `python -m PyInstaller build/pilote.spec --clean --noconfirm`, puis
  `ISCC.exe build/installer.iss` (Inno Setup 6) ; build Mac : `build/pilote-mac.spec`
- Avant une version : `python tests/verifier_release.py vX.Y.Z` et `python -m unittest discover tests`

L'architecture, les données sur disque et les règles du projet sont décrites dans
[CLAUDE.md](CLAUDE.md) et les fiches de [docs/](docs/).

## 📜 Licence

Pilote est sous licence MIT : voir [LICENSE](LICENSE). Les licences des composants
embarqués (Python, pywebview, Pillow, Chart.js, Phosphor, polices…) sont dans
[THIRD-PARTY-NOTICES.txt](THIRD-PARTY-NOTICES.txt), aussi installé avec l'app.
