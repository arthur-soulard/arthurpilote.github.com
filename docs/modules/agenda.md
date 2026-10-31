# Agenda iCloud

Fiche détaillée tirée de `CLAUDE.md`, qui garde les règles générales (dont les six choses à ne jamais casser).

## Ce que c'est (agenda.json)

Une section **Agenda** de la barre latérale (Vie perso), trois onglets
(Notifications, `ag-notifs`, ajouté le 22/10/2026 : voir plus bas) :

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
`_requete` la suit elle-même (5 au plus). Le mot de passe part dans chaque
requête : `_redirection_permise` ne suit qu'une adresse `https://…icloud.com`,
ou une adresse du même serveur (le faux iCloud des tests) ; toute autre lève
une erreur sans rien envoyer (4.4.42, audit du 31/10/2026 : avant, une
redirection vers `http://` ou un autre site emportait le mot de passe).

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

## Notifications sur l'iPhone (onglet `ag-notifs`)

Demandé par Arthur le 22/10/2026 (« est-ce que grâce à l'agenda on pourrait
pas envoyer des notifs sur le téléphone ? Si c'est le cas ça doit être un
nouvel onglet »), avec des rappels en plus de ce qui part déjà.

Pilote n'envoie aucune notification lui-même : il pose une **alerte iCalendar**
(`VALARM`, `ACTION:DISPLAY`) dans les événements qu'il écrit chez iCloud, et
c'est l'iPhone qui la sonne, Pilote fermé ou non. Rien de nouveau ne sort du
PC : mêmes événements, même agenda. Sur l'iPhone, Réglages › Notifications ›
Calendrier doit être autorisé.

* **Rangé en pastilles, une par section** (26/10/2026, demande d'Arthur :
  « une liste énorme de propositions, l'utilisateur coche ce qu'il veut ») :
  PEA, CTO, Mes comptes, Prêt (nom libre, `prNom()`), Sports, Patrimoine,
  Santé, Agenda, Pilote. Une section masquée dans la barre latérale masque sa
  pastille, ses réglages restent. Chaque pastille compte ses alertes réglées.
  Catalogue : `AG_NOTIFS` (index.html), `agenda.RAPPELS` (Python).
  `agReglerNotifs` part des réglages en mémoire : seule la pastille ouverte
  est à l'écran, les autres ne doivent pas être remises à zéro.
* **Réglage par type** (`agenda.json` : `alertes`, `jours`, `delais`) : `""`
  aucune alerte, `"0"`/`"15"`/`"30"`/`"60"` minutes avant le début, `"matin"`
  9 h le jour même, `"veille"` 18 h la veille, `"semaine"` 9 h une semaine
  avant (`ALERTES_VALEURS`). Un événement « toute la journée » prend `PT9H`
  (9 h) pour les minutes et pour « matin », `-PT6H` pour « veille »,
  `-P6DT15H` pour « semaine ». Avec heure : « matin » = 9 h, ou l'heure même
  si elle est avant 9 h. **Jour et heure au choix** (30/10/2026, demande
  d'Arthur, « comme Gmail quand on programme un mail ») : `"j<N>@HH:MM"`,
  N jours avant (0 à 30) à cette heure (`agenda.alerte_valide`). Dernière
  option de chaque menu (sauf le résumé), « Autre jour et heure… », qui ouvre
  `ov-ag-heure` : suggestions (`AG_H_SUGG`) puis jour + heure exacts. Le
  déclencheur peut être positif (le jour même, 20 h, pour un rendez-vous à 10 h). Déclencheur **relatif au début** : il vaut pour chaque
  mois d'un événement répété. Le résumé de la semaine n'accepte que
  `RESUME_VALEURS` (dimanche 18 h, lundi 8 h).
* **Ce qui part déjà** : notes, séances, objectifs, mensualités. Une case
  décochée dans l'onglet iCloud grise son réglage (« pas envoyées »).
* **Rappels** (`agenda.RAPPELS`), envoyés **seulement** si leur alerte est
  réglée. Un module jamais utilisé n'a rien à rappeler (règle « Pilote
  neutre ») :
  | Pastille | Rappel | Événement |
  |---|---|---|
  | PEA | `versement` | un par versement prévu (`depotsPrevus`) |
  | PEA | `dividende` | un par dividende attendu (`divFuture`), nom de la ligne et montant |
  | PEA | `pea-depot` | « Verser sur le PEA », du mois (rien sans aucun versement) |
  | PEA | `pea-investir` | « Investir ce mois », du mois, fait = un achat ce mois-ci |
  | PEA | `pea-anniv` | prochain anniversaire de `config.ouverture`, « cap des 5 ans » à 5 ans |
  | PEA | `pea-plan` | prochain achat de chaque plan (Plan d'épargne), date `prochaine` écrite par l'UI |
  | CTO | `cto-plan` | idem pour chaque CTO, nom du CTO en fin de titre |
  | CTO | `cto-dividende` | dividendes attendus de chaque CTO, nom du CTO en fin de titre |
  | CTO | `cto-investir` | un rappel du mois par CTO (clé `cto-investir-<id>`) |
  | Mes comptes | `fin-saisie` | du mois, fait = une opération ajoutée (`createdAt`) le jour du rappel ou après |
  | Mes comptes | `fin-recurrent` | prochaine échéance (`nextDue`) de chaque récurrence pas en pause |
  | Prêt | `pret-etapes` | première et dernière mensualité, si elles sont à venir |
  | Sports | `sport-pause` | X jours après la dernière séance |
  | Santé | `pesee` | « Pesée du mois », du mois |
  | Santé | `sante-pause` | X jours après la dernière mesure |
  | Santé | `sante-objectif` | objectifs actifs avec une date à venir |
  | Patrimoine | `releve` | « Relevé du patrimoine », du mois (`patrimoine.mois_saisi`) |
  | Agenda | `resume` | résumé de la semaine (voir plus bas) |
  | Pilote | `sauvegarde` | X jours après la dernière sauvegarde USB (`lastBackupAt`, rien sans) |
  | Pilote | `ouvrir` | aujourd'hui + X jours, recule à chaque envoi, donc à chaque lancement |
  | Pilote | `pense-bete` | pense-bêtes de l'accueil (`uiPrefs.penseBete` du PEA) datés, à venir, pas cochés ; titre « 📌 texte ». `save_ui_prefs` relance l'envoi (27/10/2026) |
* **Rappels du mois** (`MENSUELS`) : le jour choisi (1 à 28), répété chaque
  mois sans fin ; commence au mois suivant dès que le mois est fait.
* **Rappels « depuis X jours »** (`DELAIS`, `DELAIS_VALEURS`) : au plus tôt
  demain. En retard, ils sonnent le lendemain matin et reculent d'un jour à
  chaque envoi tant que rien n'est saisi (`_depuis`).
* **Résumé de la semaine** (`_resume`, appelé par `retenus`) : un événement le
  dimanche 18 h (semaine qui suit) ou le lundi 8 h (semaine qui commence), alerte
  à l'heure. Son titre compte ce que Pilote met dans l'agenda ces sept jours
  (« 🗓️ Ta semaine : 3 séances · 1 mensualité »), le détail jour par jour en
  description. Refait à chaque envoi : chaque module ajoute `"resume"` à son
  `planifier_si`. Les rappels « depuis X jours », l'essai et le résumé
  lui-même ne sont pas comptés.
* **Envoyer un essai** (`save_agenda_essai` → `agenda.tester`, demande
  d'Arthur du 26/10/2026 : « je peux pas envoyer de notif test ») : un
  événement 2 à 3 minutes plus tard, alerte à l'heure, envoyé tout de suite
  (l'erreur s'affiche). `agenda.json` garde l'heure (`test`) ; l'essai est
  retiré au premier envoi après une heure, et un minuteur à part relance un
  envoi une heure après (`planifier()` l'aurait annulé).
* **Notification libre = une note** (26/10/2026, Arthur : « une notif
  personnalisable, où l'utilisateur peut noter ce qu'il veut ») : chaque note
  a sa répétition (`repete` : `semaine`, `mois`, `an` → `RRULE` WEEKLY,
  MONTHLY, YEARLY) et son alerte (`alerte` : `""` = celle de la ligne « Notes
  de l'agenda », `aucune`, ou une valeur d'`ALERTES_VALEURS`). Le calendrier la
  montre à chaque occurrence (`agNoteTombe` ; un mois sans le 31 est sauté,
  comme iCloud), la tuile « Prochaines notes » à la prochaine
  (`agNoteProchaine`). Bouton « Nouvelle notification libre » en haut de
  l'onglet, à côté de l'essai (27/10/2026 : Arthur ne l'avait pas vu dans la
  pastille Agenda) ; ouverte par lui, la note sonne à l'heure par défaut
  (`agOuvrirNote(null, null, true)`).
* **Prochaines notifications** (`agenda.prochaines`, `agenda_prochaines`) :
  les 6 prochaines alertes, calculées avec les mêmes règles que l'envoi
  (`_decalage`, `_occurrences`). Servent à la tuile `ag-alertes`.
* Le PEA est lu par `agenda._pea()` (JSON en lecture seule, sous le verrou du
  fichier), **pas** `storage.load_data()`, qui note son résultat pour toute
  l'app (`get_last_load_info`). Fichier illisible : l'envoi s'arrête avec une
  erreur, rien n'est retiré.
* Envoi : `save_agenda_alertes` enregistre puis envoie dans la seconde.
  `save_data`, `save_cto`, `save_finances`, `save_sante`, `save_patrimoine`
  et la sauvegarde USB appellent `agenda.planifier_si(...)` : l'envoi ne
  repart que si l'un de leurs rappels est réglé (le PEA s'enregistre souvent).
* `_ics` ne cherche la description de l'événement qu'avant `BEGIN:VALARM` :
  celle de l'alerte ne doit pas faire sauter « Ajouté par Pilote. ».

**Pas encore vérifié** : que le vrai iCloud garde l'alerte et que l'iPhone
sonne (ni sur Mac). Banc et tests seulement. Le bouton « Envoyer un essai »
(26/10/2026) sert à le vérifier sur le vrai iPhone.

## Tuiles de l'accueil

Trois tuiles (22/10/2026, choisies par Arthur), éteintes comme toute tuile
nouvelle, module « Agenda » : « Aujourd'hui » (`ag-jour`, disparaît si la
journée est vide), « Cette semaine » (`ag-semaine`, 7 jours, un événement sur
plusieurs jours compté une fois, ceux d'aujourd'hui déjà finis écartés),
« Prochaines notes » (`ag-notes`, toujours là pour son bouton « Ajouter »).
Quatrième tuile le 26/10/2026, choisie par Arthur avec le catalogue :
« Prochaines notifications » (`ag-alertes`, ouvre l'onglet Notifications),
les 4 prochaines alertes de `agenda_prochaines`, relues après 10 min ou un
réglage (`dashAgAlertesRelire`). Rien tant qu'iCloud n'est pas connecté.
Mêmes éléments que le calendrier (`agDuJour(iso, icloud)`). Les événements
iCloud des 7 jours sont lus à part (`_dashAg`, `dashAgIcloud`), seulement si
« Aujourd'hui » ou « Cette semaine » est affichée, relus après 10 min ; un
échec garde la lecture précédente (pas de boucle). Détail : `docs/accueil.md`.

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
