# Agenda iCloud

Fiche détaillée tirée de `CLAUDE.md`, qui garde les règles générales (dont les six choses à ne jamais casser).

## Ce que c'est (agenda.json)

Une section **Agenda** de la barre latérale (Vie perso), deux onglets :

* **Calendrier** (`ag-cal`) : un mois en grille, comme l'agenda de Sports. Il
  **reproduit ce qu'il y a dans iCloud**, comme le téléphone : tous les
  agendas du compte, celui de Pilote compris, en lecture seule. Une séance n'y
  est donc que si elle a été envoyée. S'y ajoutent les **notes**, montrées
  depuis Pilote sans attendre l'aller-retour ;
* **iCloud** (`ag-connexion`) : connexion, agenda où Pilote écrit, cases de ce
  qui part sur l'iPhone.

Demandé par Arthur le 22/10/2026. Ses choix ce jour-là :

* écrire dans l'agenda, et pas seulement le lire ;
* **iCloud d'abord**. Google n'accepte que OAuth (projet Google Cloud à créer,
  écran « application non vérifiée », connexion coupée tous les 7 jours tant
  que l'app reste en mode test : voir `actus.md`) ;
* ce qui part dans l'agenda se choisit dans Pilote ;
* une section à part dans la barre latérale, pas une page des Paramètres (la
  première version, du même jour, y vivait) ;
* le calendrier affiche aussi ses autres agendas iCloud ;
* une note est un événement envoyé à iCloud, comme le reste ;
* puis, après l'essai sur son vrai iCloud : le calendrier doit reproduire
  exactement le téléphone (pas les séances de Pilote collées d'office), les
  notes doivent partir dès qu'elles sont créées, et un bouton « Mettre à jour
  le téléphone ».

Les **notes** partent toujours, dès que l'agenda est connecté. Trois cases
(`agenda.CHOIX`) pour le reste, toutes décochées par défaut :

| Case        | Ce que Pilote écrit                                                        |
|-------------|----------------------------------------------------------------------------|
| `sport`     | chaque séance de Sports. Avec une heure : de l'heure à l'heure + durée (1 h si la durée n'est pas saisie). Sans heure : un événement « toute la journée ». Titre : icône, sport, type, distance ; la note va en description |
| `objectifs` | les objectifs de Sports « Événement à date » (pas les archivés), toute la journée |
| `pret`      | **un seul** événement répété chaque mois (`RRULE:FREQ=MONTHLY;COUNT=durée`), à partir de la date du premier remboursement, avec la mensualité dans le titre |

Les heures sont « flottantes » (sans fuseau) : 18 h 30 reste 18 h 30 là où
se trouve le téléphone.

## Comment Pilote parle à iCloud

CalDAV (HTTPS) sur `caldav.icloud.com`, avec l'**identifiant Apple** et un
**mot de passe pour app** (créé sur account.apple.com › Connexion et sécurité,
double authentification obligatoire). Bibliothèque standard uniquement
(`urllib`, `xml.etree`).

1. `PROPFIND /` → `current-user-principal` → `calendar-home-set` : le dossier
   des agendas, sur un serveur `pXX-caldav.icloud.com` (adresse absolue).
2. `PROPFIND` du dossier, profondeur 1 : les agendas d'événements. La boîte de
   réception et les listes de Rappels (`VTODO` seul) sont écartées.
3. `MKCALENDAR` pour l'agenda « Pilote » (conseillé, choix par défaut), ou un
   agenda existant au choix.
4. `PUT` / `DELETE` d'un fichier `.ics` par événement.

`urllib` ne suit pas une redirection pour `PROPFIND`, `PUT` ou `DELETE` :
`_requete` la suit elle-même (5 au plus).

## Ce qu'il ne faut pas défaire

1. **Pilote ne touche qu'à ses propres événements.** Leur nom de fichier est
   `pilote-<id>-<clé>.ics`, `id` tiré au hasard à la première connexion et
   gardé dans `agenda.json`. Clés : `sport-<id>`, `objectif-<id>`, `pret`. Un
   événement saisi sur l'iPhone dans le même agenda n'est jamais lu ni retiré.
   Deux utilisateurs Pilote sur le même agenda ont deux `id` différents.
2. **La synchronisation part de ce qui est dans l'agenda**, pas d'un journal :
   Pilote liste ses fichiers (`_nos_fichiers`), retire ceux qui ne sont plus
   voulus, envoie les nouveaux et ceux dont l'empreinte a changé
   (`envoyes` : nom → empreinte, sans `DTSTAMP`). Un `agenda.json` restauré
   d'un backup ne crée donc ni doublon ni événement orphelin. Rien de changé →
   aucun envoi.
3. **Le mot de passe suit le chemin de celui d'Actus** : vérifié auprès
   d'iCloud avant d'être gardé (`connecter`), chiffré par DPAPI sous Windows,
   dans le Trousseau sur Mac (service « Pilote Agenda », distinct de « Pilote
   Actus » : `actus._chiffrer` prend le nom du service en paramètre), et jamais
   renvoyé à la page.
4. **Quand l'envoi part.** Trois secondes après chaque `save_sports` ou
   `save_pret` (`agenda.planifier`, un nouvel appel repousse le précédent : dix
   séances d'affilée = un seul envoi), 8 s après le lancement (ce qui a changé
   pendant que Pilote était fermé), et au bouton « Envoyer maintenant ».
   iCloud injoignable : l'erreur s'affiche dans l'onglet Agenda › iCloud, nouvel
   essai 10 min plus tard (`REESSAI`). L'envoi tourne sous un verrou, dans un
   fil à part ; si l'utilisateur change pendant l'envoi, rien n'est écrit dans
   le fichier de l'autre.
5. **Changer d'agenda** retire de l'ancien ce que Pilote y avait mis
   (`aNettoyer`). L'agenda « Pilote » quitté est supprimé en entier
   (`aSupprimer`), comme à la déconnexion. Les autres événements de l'agenda ne
   bougent pas.
6. **Déconnecter** retire les événements de Pilote (ou l'agenda « Pilote »),
   puis oublie le mot de passe. Si iCloud ne répond pas, le mot de passe est
   oublié quand même, et un avertissement dit que les événements sont restés.

## Calendrier et notes

* **Le calendrier, c'est iCloud.** `agenda_icloud` lit tous les agendas, celui
  de Pilote compris. Seules les notes de Pilote (`pilote-<id>-note-…`) sont
  sautées à la lecture : la page les affiche depuis `AG.notes`, donc tout de
  suite et modifiables. Une première version du 22/10 montrait les séances
  depuis les données de Pilote, cochées ou non : Arthur ne voulait pas.
  Sans connexion à iCloud, le calendrier ne montre que les notes.
* **Notes** : `{id, titre, date, heure, duree, texte}` dans `agenda.json`. La
  page les garde (`AG.notes`) ; `save_agenda_notes` les écrit (id nettoyé :
  il finit dans un nom de fichier chez iCloud) et lance l'envoi une demi-seconde
  plus tard. À chaque envoi, les notes partent **avant** les séances. Une note
  sans heure est « toute la journée », sans durée elle dure une heure. Elles
  restent dans Pilote tant qu'iCloud n'est pas connecté, et ne partent pas à
  la déconnexion.
* **Deux verrous** (cas vu sur le vrai iCloud le 22/10) : `_verrou` pour les
  échanges avec iCloud (un premier envoi d'une cinquantaine de séances dure ~30 s),
  `_verrou_fichier` pour lire-modifier-écrire `agenda.json` (`_modifier`, bref).
  Avant, une note créée pendant l'envoi des séances attendait la fin de
  l'envoi pour être seulement enregistrée, puis partait après elles. Chaque
  écriture ne change que ses propres clés : un envoi n'écrase pas une note
  arrivée entre-temps.
* **« Mettre à jour le téléphone »** (en-tête du calendrier) : lance l'envoi
  tout de suite (`agenda_synchroniser`), puis relit iCloud. À côté, l'heure du
  dernier envoi. Un mois déjà lu est relu en y revenant après une minute.
* Un clic sur un jour ouvre son détail (`ov-ag-jour`) : chaque élément avec
  son heure et son agenda, « Modifier » pour une note, « Ajouter une note ».

## Lecture des autres agendas iCloud

`agenda_icloud(debut, fin)` (62 jours au plus) : un `REPORT calendar-query`
par agenda, avec `expand` (iCloud rend alors chaque occurrence d'un événement
répété, en UTC). `lire_ics` lit le strict nécessaire : titre, début, fin ou
durée, toute la journée ou non ; un événement annulé est écarté. Les heures en
UTC sont ramenées à l'heure du PC ; une heure avec `TZID` est prise telle
quelle (juste tant que l'utilisateur vit dans le fuseau de ses événements).
Couleur de chaque agenda : `calendar-color` d'Apple, reprise sur les lignes et
dans la légende (un point par agenda présent dans le mois). La page garde la lecture
d'un mois (`AG.icloud`) jusqu'au bouton « iCloud » (relire) ou à une
reconnexion. **Rien n'est jamais écrit dans ces agendas.**

## Interface (`ag*`, fin d'index.html)

Onglet iCloud (`agOuvrir`, appelée par le patch de `goTab`). Non connecté :
trois étapes et le formulaire (mêmes briques que la connexion d'Actus :
`.ac-etapes`, `.ac-note`, `.ac-btns`, `.ac-err`). Connecté : l'agenda choisi,
les trois cases, l'état du dernier envoi. Changer l'agenda ou une case
enregistre tout de suite (`save_agenda_reglages`) puis envoie
(`agenda_synchroniser`). Rien de coché et aucun agenda encore choisi : rien
n'est créé.

Calendrier : `agRenderCal` (cases `.sp-day` de Sports, une ligne `.ag-ev` par
élément, trois au plus puis « +N »), couleurs par type en variables CSS
(`.ag-t-sport`, `--c`). Le module est dans `MODULES_A_CHARGER` (`agBootstrap` :
réglages et notes) et a son propre patch de `goTab`, après le tableau de bord.

API Python : `load_agenda`, `save_agenda(adresse, code)`,
`save_agenda_reglages(calendrier, choix)` (`calendrier` : adresse d'un agenda,
ou `"nouveau"`), `save_agenda_notes(notes)`, `save_agenda_deconnexion`,
`agenda_calendriers`, `agenda_icloud(debut, fin)`, `agenda_synchroniser`. Les écritures s'appellent `save_*` pour passer
par le gel des enregistrements.

## Tester sans iCloud

`tests/test_agenda.py` : un faux serveur CalDAV local construit comme celui
d'iCloud (première adresse redirigée, dossier des agendas en adresse absolue,
boîte de réception et Rappels à écarter). Il couvre : mauvais mot de passe
(rien d'enregistré), code jamais en clair, contenu des événements, lignes de
75 octets au plus, aucun envoi quand rien ne change, séance modifiée ou
supprimée, case décochée, changement d'agenda, déconnexion, iCloud injoignable,
notes (id nettoyé, envoyées sans case cochée), note enregistrée en moins d'une
seconde pendant un envoi en cours puis envoyée avant les séances, lecture des
agendas (événement sur deux jours, durée, annulé, hors période, objectif
envoyé par Pilote présent, notes de Pilote sautées), heure UTC ramenée à
celle du PC.
Le 22/10/2026, l'écran a aussi tourné sur le banc navigateur (données de
Camille, même faux iCloud) : 36 séances envoyées, une séance ajoutée partie
toute seule 3 s plus tard.

**Essayé contre le vrai iCloud le 22/10/2026** (banc, copie des données
d'Arthur, mot de passe saisi par lui) : découverte par `caldav.icloud.com`
(dossier des agendas sur un serveur `pXX-caldav.icloud.com`), liste des
agendas, `MKCALENDAR` accepté (agenda « Pilote » créé), objectifs à date
envoyés et vus par Arthur sur son iPhone, puis toutes ses séances (aucune
erreur), vues aussi. La case « Séances » décochée les a retirées, et la
déconnexion a supprimé l'agenda « Pilote » (vu sur l'iPhone).
Puis, même jour, le calendrier sur le vrai iCloud : les événements de ses
agendas lus et affichés, une note envoyée, « Mettre à jour le téléphone » en
moins d'une seconde ; Arthur a confirmé que le calendrier de Pilote
correspond à son iPhone, note comprise. Pas encore essayé : les mensualités, les événements
répétés (iCloud rend-il bien chaque occurrence avec `expand` ?), et le tout
sur Mac.

Sur le banc navigateur, `confirm()` répond « Annuler » sans s'afficher : le
bouton Déconnecter n'y fait donc rien (remplacer `window.confirm` le temps de
l'essai). Dans la vraie fenêtre, la question s'affiche.
