# Paramètres

Fiche détaillée tirée de `CLAUDE.md`, qui garde les règles générales (dont les six choses à ne jamais casser).

## Paramètres (`openSettings(section)`)

Modale unique à colonne de sections (`setGoSection(id)`), plus « paramètres du PEA » :

Colonne, dans l'ordre : Général, Utilisateurs, Accueil, Modules, Masqués, puis le
titre « Mes modules » et une entrée par module, puis un trait et les réglages de l'app.

| Section    | Contenu                                                            |
|------------|--------------------------------------------------------------------|
| general    | thème, couleur d'accent, icône de l'app, code PIN de l'utilisateur  |
| users      | liste des utilisateurs, création / édition                          |
| accueil    | tuiles du tableau de bord (idem bouton ✎ de l'accueil)             |
| nav        | « Modules » : modules à cocher                                      |
| masques    | une case par module où quelque chose est caché (4.4.34)             |
| pea        | prénom, banque, date d'ouverture, récap fiscal, rapport annuel      |
| cto        | chaque CTO (nom, courtier) avec « Réglages du compte », « Nouveau CTO » |
| actus      | état de la boîte Gmail, renvoi vers l'onglet `ac-connexion`         |
| agenda     | état d'iCloud, renvois vers `ag-connexion` et `ag-notifs`           |
| comptes    | catégories & emoji, sources, récurrents : les listes, modifiables sur place (4.4.35) |
| pret       | renvoi vers l'onglet `pr-params`                                    |
| sport      | mes sports, types de séance, routines : modifiables sur place (4.4.35) |
| sauvegarde | destination USB, sauvegarde auto, rotation, restauration            |
| donnees    | dossier (chemin en clair + Ouvrir), export/import, réinitialisation, version |
| maj        | version installée, vérification, version proposée, historique       |

**Annuler / Enregistrer (4.4.41, 31/10/2026).** Deux sortes de réglages : ceux
enregistrés dès le clic (thème, taille du texte, modules, masqués, listes de Mes
comptes et Sports, tuiles…) et ceux que seul `saveConfig()` enregistre : prénom,
banque, date d'ouverture, couleur d'accent, PIN. L'accent s'applique à l'écran dès
qu'on clique une pastille (aperçu) : jusqu'à la 4.4.40, « Fermer » le laissait
affiché sans l'enregistrer (il revenait au lancement suivant), et Arthur trouvait que
Fermer et Enregistrer faisaient la même chose. Le bouton s'appelle « Annuler », et
`closeOv("ov-config")` réapplique `S.uiPrefs.accent` : toute fermeture (Annuler, Échap,
clic à côté, renvois vers un onglet) retire l'aperçu ; `saveConfig` pose la nouvelle
couleur dans `S.uiPrefs` avant de fermer. Les champs texte et le PIN sont relus de
`S` / vidés à chaque ouverture (`openConfig`) : rien à défaire. Choix d'Arthur parmi
trois pistes (les deux autres : tout enregistrer au clic, ou demander en fermant).

`openConfig()` reste le point d'entrée historique (ouvre sur `general`). Les onglets
Mes comptes et Sports ont un bouton ⚙ dans leur barre d'actions qui ouvre directement
leur section.

**Une section par module (4.4.34, 29/10/2026).** Choix d'Arthur entre deux pistes :
une entrée par module, plutôt que sortir des onglets les réglages qui y vivent
(Prêt › Paramètres, Actus › Connexion, Agenda › iCloud et Notifications restent des
onglets, la section y renvoie). Les entrées `[data-mod]` de la colonne suivent l'ordre
de la barre latérale et disparaissent avec leur module décoché (`_setNavModules`,
appelée à l'ouverture et par `cfgModule` ; la recherche ignore aussi leur section).
Patrimoine et Santé n'ont rien à régler ici, donc pas d'entrée. Les sections CTO,
Actus et Agenda sont relues à chaque ouverture (`cfgRenderModule`).

* **Mes comptes et Sports réglés sur place (4.4.35)** : Arthur « reste sur sa faim »
  avec des boutons qui ouvrent une fenêtre ; il veut ajouter ou supprimer un sport,
  changer les catégories, directement. Les listes des six fenêtres (Catégories,
  Sources, Récurrents, Mes sports, Types de séance, Routines) sont enveloppées dans un
  `.set-corps` (`corps-fin-cats`…) : **un seul exemplaire**, que `_setCorps(sec)` place
  dans les `[data-corps]` de la section à son ouverture, et que `_corpsDansFenetre`
  remet dans sa fenêtre quand on l'ouvre d'ailleurs (boutons de l'onglet Mes comptes,
  crayons de la fenêtre d'une séance). Les rendus visent leurs id : rien à savoir de
  l'endroit. Ne pas dupliquer les listes (les champs « Ajouter » ont des id). Types de
  séance : un sélecteur des sports qui en ont (`subtype` dans leurs champs) règle
  `_spSport`, sans effet ailleurs (la fenêtre d'une séance le repose à l'ouverture).
  Les sous-fenêtres passent devant (9600) : `ov-sp-sport`, `ov-fin-icon` déjà,
  `ov-fin-rec-edit` depuis la 4.4.35. Listes en entier ici (plus de `max-height`).
* **Fenêtre d'un module ouverte depuis les Paramètres** (`_setParDessus(ouvrir, ovId)`) :
  Réglages du compte d'un CTO (jusqu'à la 4.4.34, aussi les six fenêtres ci-dessus).
  Les Paramètres s'effacent le temps qu'elle est ouverte et reviennent
  sur la même section quand elle se ferme (un `MutationObserver` sur sa classe). Pourquoi
  pas `openOvTop` : ces `.ov` sont plus haut dans la page que `ov-config`, et leurs
  sous-fenêtres (`ov-fin-rec-edit`…) s'ouvrent à 9500 ; monter la première à 9600 les
  aurait fait passer dessous. Une fenêtre qui refuse de s'ouvrir rend la main aussitôt.
  Avant, ces boutons fermaient les Paramètres.
* **Hauteur** : 16 entrées ne tiennent plus à 1366 × 720 (705 px pour 490). Boutons
  resserrés (6 px au lieu de 9) et colonne qui défile seule, à la hauteur du panneau :
  `min(calc(100vh - 232px), 620px)` pour les deux (232 = marges de l'`.ov`, titre,
  boutons du bas). À 232 px rien ne déborde de la fenêtre ; à 230, 1 px.

**Modules (section `nav`, 4.3.37).** L'entrée « Masqué » est devenue « Modules » (même
`data-set`). En tête, une carte à cocher par section de `NAV_SECTIONS`, les mêmes que
l'assistant des premiers pas (`docs/accueil.md`) : `cfgRenderModules()`, `cfgModule()`.
Cocher affiche **tous** les onglets de la section, décocher les masque tous
(`_afficherModule`, dans `S.uiPrefs.hiddenSidebar` comme l'œil) ; la barre latérale est
redessinée (`_reconstruireSidebar`, qui revient à l'accueil si l'onglet ouvert vient
de disparaître) et les tuiles du module quittent l'accueil. Un module décoché n'est
plus chargé aux lancements suivants ; le recocher le charge tout de suite
(`_chargerModule`, voir `docs/accueil.md`, « Sauf les modules masqués »). Un module est « coché »
dès qu'un de ses onglets est visible. Les onglets et blocs cachés, listés sous les
modules jusqu'à la 4.4.33, ont leur propre section, Masqués.

**Masqués (4.4.34, 29/10/2026).** Arthur voyait deux « Dividendes » dans la liste
des onglets masqués, celui du PEA et celui du CTO, sans savoir lequel était lequel.
Il a demandé une entrée « Masqués » où chaque module a sa case ; il a choisi de ne
montrer que les modules où quelque chose est caché (pas tous les onglets à cocher).
`_cfgRenderMasques()`, rien de changé à `hiddenSidebar` ni `hiddenCards` :

* une case par section de `NAV_SECTIONS`, dans l'ordre de la barre (`_setOrdreModules`),
  icône `NAV_ICONS` et nom ; la case CTO porte le nom du CTO s'il n'y en a qu'un,
  sinon « CTO » et « réglage commun à tes N comptes-titres » (les onglets `cto-*`
  masqués le sont dans tous les CTO) ;
* **Module** : « Tout le module » quand il est décoché (Réafficher = `cfgModule(id, true)`,
  qui rend aussi tous ses onglets, d'où aucune ligne Onglets dans ce cas) ;
* **Onglets** : ceux cachés à l'œil ; un onglet retiré de l'app (Formation, `pr-ech`)
  est ignoré ;
* **Blocs** : le module d'un bloc est celui de l'onglet de son pane (`card-strat` dans
  `pane-strat` → Stratégie du PEA, `card-sim-*` → Patrimoine). Les écrans du PEA
  servent aux CTO : un bloc caché sur l'un l'est sur l'autre, il paraît donc dans les
  deux cases, avec « aussi caché sur tes CTO » / « aussi caché sur le PEA » (seulement
  s'il existe un CTO et que l'onglet a son équivalent `cto-*` : pas Versements).

Petits textes en `--txt2` (`--txt3` : 2,8:1 en thème clair). Les messages de l'œil
(`_hideSidebarItem`, `_hideCard`) disent « Pour le réafficher : Paramètres, Masqués ».

**Retrouver ce qui est masqué (4.4.33, 29/10/2026).** Arthur trouvait compliqué de
retrouver un onglet ou un réglage caché. Deux chemins avaient été ajoutés :

* **Barre latérale** : une ligne « 2 masqués » au bas de chaque section, qui listait
  ses onglets cachés. **Retirée en 4.4.34** à la demande d'Arthur : « ça occupe trop
  d'espace pour rien, si on veut masqué c'est pas pour le voir ici ». Ne pas la
  remettre. `_hideSidebarItem` redessine toujours la barre (`_reconstruireSidebar`) :
  l'onglet part de tous les CTO d'un coup.
* **Recherche en haut des Paramètres** (`#set-cherche`, `setChercher`) : chaque mot
  tapé doit se trouver, sans tenir compte des accents ni de la casse, dans le nom d'une
  section, un titre `h3`, un libellé `.fg > label`, un bouton `.btn` ou le nom d'une
  carte de module (`_SET_CHERCHABLES`). Rien n'est indexé à l'avance : les sections
  sont lues telles qu'elles sont (un élément caché en `display:none`, ou `.win-seul`
  sur Mac, est ignoré). Les résultats s'affichent dans la section `data-sec="recherche"` ;
  un clic ouvre la section et fait clignoter le réglage (`_setAllerA`, qui retrouve
  l'élément par son texte si la section l'a redessiné à l'ouverture). Dessous,
  « Masqué » : modules décochés, onglets et blocs cachés, avec « Réafficher » sur place.
  Choisir une section dans la colonne, ou vider le champ, referme la recherche.

**Données & app (section `donnees`).** Depuis la 4.4.20 (19/10/2026), le chemin du dossier
de l'utilisateur actif s'écrit en clair (`#cfg-dossier`, rempli par `setGoSection`
via `_cheminDonnees()`, relu à chaque ouverture : il suit un changement
d'utilisateur), avec « Ouvrir » (`openDataFolder()`). Un clic sur le chemin le
sélectionne en entier. Même ligne dans les Premiers pas (`docs/accueil.md`).

**Mises à jour (section `maj`, 4.3.37).** Le bouton « Vérifier les mises à jour »
quitte « Données & app ». `majRenderSection()` : version installée, la version
proposée s'il y en a une (avec sa fiche et « Installer… », qui ouvre la fenêtre
habituelle), puis l'historique livré avec l'app, la plus récente dépliée. Détail
dans `docs/mise-a-jour.md`, « Fiche des nouveautés ».
