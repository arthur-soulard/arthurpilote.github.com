# Sécurité : ce qui est fait, ce qui reste

Plan de lancement du 07/11/2026 : quatre faiblesses connues. Point au 09/11/2026
(branche `maj-explorer-securite`, prochaine version). Les règles du serveur local
restent dans `CLAUDE.md` (« Le serveur local n'est PAS un endroit privé »).

| | Faiblesse | État |
|---|---|---|
| a | Sauvegardes USB et Google Drive en clair | **Fait** : archives chiffrées par mot de passe (`docs/sauvegarde-usb.md`, « Chiffrement par mot de passe ») |
| b | Données en clair sur le disque | **Pas fait**, plan ci-dessous |
| c | Un autre programme du PC lit `/data` pendant que Pilote tourne | **Pas fait**, plan ci-dessous |
| d | Revue du code | **Faite** : une faille corrigée (`/pin/set`, `docs/utilisateurs-et-pin.md`, « Revue du 09/11/2026 ») |

## d. Revue du 09/11/2026

Relu : les trois verrous du serveur (`_guard` : Host, Origin, jeton comparé par
`hmac.compare_digest`), `/vendor/` (liste blanche d'extensions, confinement par
ancêtres), `/recover-data` (seulement un chemin du scan), `/actus/mail/` (ticket
aléatoire, CSP sans script, `sandbox`), `Api.open_url` (http, https, mailto
seulement), l'échappement des noms venus de l'extérieur (positions, comptes,
mails) dans le HTML et dans les attributs `onclick` (seuls des identifiants
internes y passent), le zip-slip de la restauration, les routes PIN.

* **Corrigé** : `/pin/set` vérifiait l'ancien code sans le délai ni le blocage de
  `/pin/check`.
* **Vu, laissé** : le code PIN passe dans l'adresse d'une requête GET locale
  (jamais journalisée) ; `escHtml` n'échappe pas l'apostrophe (aucun attribut entre
  apostrophes ne l'utilise, et dans un `onclick` l'échapper en `&#39;` ne
  protégerait rien : ne jamais y mettre un nom venu de l'extérieur).
* Le code PIN sépare les espaces, il ne protège pas les fichiers : la page lit les
  données avant l'écran de verrouillage. C'est (b) qui changerait ça.

## c. Lecture de `/data` par un autre programme

**Le trou réel.** Les fichiers vivent dans `%LocalAppData%`, que les autres comptes
Windows ne peuvent pas lire. Mais tout programme du PC, même d'un autre compte,
peut demander `http://127.0.0.1:7438/`, y trouver le jeton (injecté dans la page),
puis lire `/data` (PEA de l'utilisateur actif), `/users`, `/scan-orphan-data`.
Un programme du **même** compte, lui, lit déjà les fichiers directement : (c) seul
ne le gêne pas.

**Ce qui existe déjà.** `Api.load_data` (le pont pywebview) rend exactement ce que
rend `/data` ; la page passe par `/data` en **repli**, quand le pont tarde au
démarrage (`_hydrateFromHttp`). Tous les autres modules lisent déjà par le pont.

**Plan conseillé (coût : une demi-journée, risque : démarrage)**

1. Ne plus injecter le jeton dans le HTML servi par `/` : la page le demande au
   pont (`Api.jeton()`) dès l'événement `pywebviewready`, et le wrapper `fetch`
   attend cette promesse. Un programme qui lit `/` n'a plus rien.
2. Retirer le repli `_hydrateFromHttp` (ou l'attendre derrière le jeton) : `/data`
   ne sert plus qu'au pont.
3. Garder les trois verrous (règle de `CLAUDE.md`), le jeton venant seulement
   d'ailleurs.
4. À essayer sur les deux systèmes avant tout : le démarrage à froid sous Windows
   (WebView2, pywebview 4.4.1), sur Mac (pywebview 6.2.1, `adapter_pont_mac`), et le
   test des captures (`tests/lire_tests.py`). Le repli HTTP a été ajouté parce que
   le pont tardait : c'est là que ça peut casser (écran vide au lancement).

**Gain** : ferme l'accès des autres comptes Windows et des programmes qui ne
savent que parler HTTP. **Ne protège pas** d'un programme malveillant du même
compte (il lit les fichiers, et pourrait déchiffrer DPAPI : voir b).

## b. Chiffrement des données sur le disque

**Ce qu'il faudrait.** Une clé de 32 octets par installation, gardée par DPAPI
(Windows) ou le Trousseau (Mac), comme la clé des sauvegardes (`chiffrement.py`).
Chaque JSON écrit chiffré (même format `.pilote`, ou un en-tête court), relu
déchiffré, de façon transparente pour les modules.

**Pourquoi ce n'est pas codé dans cette passe**

* Les écritures ne passent pas toutes par `jsonstore.JsonStore` : `storage.py`
  (PEA, `users.json`, backups du PEA, `avant_import`), `finances.py`, `pin.hash`,
  `sauvegarde.json`, les backups quotidiens de chaque module, les copies
  `corbeille/`, l'archive de sécurité d'une restauration, `scan_orphan_data` et
  `recover_from`, l'import et l'export d'un `pea_data.json`, l'utilisateur Exemple.
  Il faut un point d'entrée unique (lire / écrire un fichier de données) avant de
  chiffrer quoi que ce soit, puis faire passer chacun par lui.
* La migration doit être réversible et sans perte : lire un fichier en clair
  comme chiffré pendant au moins une version, ne chiffrer qu'après une relecture
  réussie, garder un réglage « Déchiffrer mes données » (pour quitter Pilote ou
  changer de compte Windows).
* **Clé perdue = tout perdu** : réinstaller Windows, changer de compte, copier le
  dossier sur un autre PC rend DPAPI incapable de relire la clé. Il faut donc une
  clé de secours (mot de passe, ou phrase à noter), sinon on crée le risque qu'on
  voulait éviter. C'est un choix de produit pour Arthur.
* Le gain est limité : un programme du même compte appelle DPAPI comme Pilote.
  Ça protège surtout un disque volé ou une copie du dossier, ce que BitLocker ou
  FileVault font déjà pour tout le disque.

**Plan si on y va (2 à 3 jours, avec les essais)**

1. `donnees.py` : `lire(chemin)` / `ecrire(chemin, octets)`, seuls à ouvrir un
   fichier de `Donnees/` ; y faire passer `jsonstore`, `storage`, `finances`,
   backups, corbeille, import / export. Aucun chiffrement encore : une version
   publiée ainsi d'abord.
2. Clé d'installation (DPAPI / Trousseau) + clé de secours dérivée d'un mot de
   passe, qui chiffre une copie de la clé (`Donnees/cle.pilote`).
3. Lecture des deux formats ; écriture chiffrée seulement si le réglage est
   coché ; migration fichier par fichier avec relecture, sur une copie des données
   d'exemple (`src/donnees_exemple.py`) puis sur les vraies.
4. Sauvegarde USB : les archives embarquent les fichiers tels quels (chiffrés),
   la restauration sur un autre PC demande la clé de secours.
5. Tests : migration aller-retour, clé illisible (aucune écriture, message clair),
   fichier à moitié migré, Mac.

**Conseil** : faire (c) d'abord (gain réel, coût faible), et (b) seulement si le
lancement payant en fait un argument, avec la clé de secours.
