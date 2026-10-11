# Module Actus

Fiche détaillée tirée de `CLAUDE.md`, qui garde les règles générales (dont les cinq choses à ne jamais casser).

## Module Actus (actus.json)

La boîte Gmail qui reçoit les newsletters, lue dans Pilote. Demandé par Arthur
le 11/10/2026 pour sa boîte d'actus bourse. Ses choix ce jour-là : une section
« Actus » à part, les images des newsletters affichées, une fiche dans la
section pour créer le mot de passe, et pas de crainte sur le stockage du code
(la boîte ne sert qu'aux newsletters).

Deux onglets : **Newsletters** (`ac-boite`, liste à gauche, mail à droite) et
**Connexion** (`ac-connexion`, la fiche en quatre étapes et le formulaire).

API Python : `load_actus()` → `{adresse, connecte}` ; `save_actus(adresse, code)`
connecte ; `save_actus_deconnexion()` oublie le code ; `actus_lister()`,
`actus_ouvrir(uid)` → `{ticket}`, `actus_marquer(uid, lu)`. Les deux écritures
s'appellent `save_*` pour passer par le gel des enregistrements (`_surveillerEcritures`).

Données : `{adresse, secret: "dpapi:<base64>"}`. Rien d'autre n'est stocké : la
liste et l'état lu / non lu vivent dans Gmail, Pilote les relit.

### Pourquoi IMAP, et pas Gmail dans un cadre

* Gmail interdit d'être affiché dans une autre page (`X-Frame-Options:
  SAMEORIGIN`, puis `DENY` sur la page de connexion : vérifié le 11/10/2026).
* Google bloque la connexion à un compte dans un navigateur intégré à une app
  (message « This browser or app may not be secure »).
* L'API officielle de Gmail (OAuth) demande un projet Google Cloud, et tant
  que l'app reste en mode « test », Google coupe la connexion tous les 7 jours.

Pilote relève donc la boîte en IMAP (`imap.gmail.com:993`, TLS) avec un
**mot de passe d'application** Google (16 caractères, validation en deux étapes
obligatoire). Point de vigilance : Google a déjà supprimé ces codes pour les
comptes Workspace en 2025 ; s'il les fermait aussi pour les comptes Gmail
personnels, il faudrait passer à OAuth.

Activer la validation en deux étapes est une « action sensible » pour Google.
S'il ne reconnaît ni l'appareil ni le réseau, il répond « Impossible de valider
votre identité » et bloque l'action jusqu'à 7 jours, puis la permet sans
vérification (aide Google, article 7162782). Vu le 11/10/2026 sur la boîte
d'Arthur : l'étape 1 de la fiche le signale depuis.

### Ce qu'il ne faut pas défaire

1. **Le code ne repasse jamais par la page.** Le JS l'envoie une fois
   (`save_actus`), Python le vérifie auprès de Gmail **avant** de l'enregistrer,
   puis le chiffre avec DPAPI (lié à la session Windows : seul ce compte, sur ce
   PC, sait le relire). Aucune méthode ne le renvoie. Corollaire : un
   `actus.json` restauré depuis la clé USB sur un autre PC ne se relit pas, et
   l'onglet demande de ressaisir le code (`code: "config"`). Hors Windows
   (chantier Mac), le secret est seulement encodé en base64 : le Trousseau
   devra prendre le relais.
2. **Le contexte TLS est explicite** (`ssl.create_default_context()`). Celui
   qu'imaplib prend par défaut en Python 3.8 ne vérifie pas le certificat du
   serveur. `_Imap._create_socket` ajoute aussi un délai de 20 s, que le
   constructeur de 3.8 n'accepte pas (le `*args` couvre 3.8 et 3.9+).
3. **Une seule connexion IMAP, sous verrou** (`_avec_imap`). pywebview appelle
   chaque méthode de l'Api dans son propre fil, et Gmail limite les connexions
   simultanées. Une connexion morte (veille du PC, Gmail qui ferme celles qui
   dorment) est rouverte une fois sans que la page le voie ; `NOOP` avant chaque
   usage la détecte, et fait voir les nouveaux mails.
4. **Les en-têtes se lisent avec `email.policy.default`.** L'ancienne politique
   (`compat32`) rendait illisibles les accents écrits en UTF-8 brut dans
   l'objet (« accélère » devenait « acc��l��re »), ce que certaines newsletters
   envoient.
5. **Un mail s'affiche dans une iframe servie par le serveur local, sous ticket**
   (`server.publier_mail`, `GET /actus/mail/<ticket>`). Le navigateur charge
   l'iframe lui-même, sans le jeton de session : le ticket (aléatoire, 10 min,
   20 pages gardées au plus) le remplace, et les verrous Host et Origin
   s'appliquent toujours. La page a sa propre CSP : **aucun script**
   (`default-src 'none'`), mais images, styles et polices de n'importe où (choix
   d'Arthur). `sandbox` (attribut de l'iframe et directive CSP) lui donne une
   origine opaque : elle ne lit rien de Pilote. Ne pas passer par `srcdoc` ni par
   une URL `blob:` : elles héritent de la CSP de Pilote, qui bloque les images
   distantes.
6. **Les liens d'un mail s'ouvrent dans le navigateur du PC.** `actus.page_html`
   ajoute `<base target="_blank">` ; l'iframe a `allow-popups` ; pywebview
   (`on_new_window_request`) envoie toute nouvelle fenêtre à `webbrowser.open`.
   Sans le `_blank`, un lien chargerait le site dans le cadre. Les
   `<meta http-equiv="refresh">` sont retirés pour la même raison.
7. **Fond blanc imposé au mail** (`_TETE`) : un mail sans fond serait du texte
   sombre sur le thème sombre. Gmail fait pareil.
8. **Ouvrir un mail le marque comme lu dans Gmail**, comme Gmail lui-même
   (`BODY.PEEK[]` puis `STORE +FLAGS \Seen`, pour que l'échec éventuel se voie).
   Le bouton « Non lu » / « Lu » de l'en-tête bascule, ici et dans Gmail.

### Relevé

Les 60 derniers mails de la boîte de réception (`NB_MAILS`), relevés au
lancement (3 s après, les cours passent d'abord), à l'ouverture de l'onglet si
le dernier relevé a plus d'une minute, à l'icône à côté de « À jour à … », et
toutes les 3 minutes (`AC_RELEVE_MS`) tant que Pilote est ouvert. Le nombre de
non lus s'affiche sur l'en-tête de la section dans la barre latérale
(`acRenderBadge`). Un relevé raté laisse la liste précédente à l'écran et
affiche l'erreur à la place de « À jour à … » ; s'il n'y a rien à montrer,
« Boîte injoignable » avec Réessayer.

Les filtres : Tout, Non lus, puis les libellés Gmail des mails relevés
(`X-GM-LABELS`, noms en UTF-7 modifié décodés par `_utf7` ; les libellés système
`\Inbox`, `\Important`… sont écartés).

« Ouvrir dans Gmail » ouvre le fil (`X-GM-THRID` en hexadécimal) avec
`?authuser=<adresse>`, pour tomber sur le bon compte quand le navigateur en a
plusieurs. Les deux boutons de la fiche (validation en deux étapes, mots de
passe d'application) ajoutent le même `authuser` dès qu'une adresse est saisie ;
leurs adresses sont celles de l'aide officielle de Google.

### Tester sans Gmail

Les tests du 11/10/2026 ont tourné contre un faux serveur IMAP local au format
de Gmail (`X-GM-LABELS`, `X-GM-THRID`, champs placés avant ou après le
littéral), avec `actus._ouvrir_imap` remplacé et `storage.get_app_dir` pointé
sur un dossier de test, jamais `Donnees/` : 34 vérifications côté Python
(dont connexion coupée, code illisible, Gmail injoignable), puis l'interface
dans une vraie fenêtre pywebview (WebView2). Le navigateur intégré de Claude
refuse les iframes locales (`ERR_BLOCKED_BY_CLIENT`) : le mail ne s'y affiche
pas, ce n'est pas un défaut de Pilote.
