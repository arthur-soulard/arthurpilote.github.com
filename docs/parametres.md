# Paramètres

Fiche détaillée tirée de `CLAUDE.md`, qui garde les règles générales (dont les six choses à ne jamais casser).

## Paramètres (`openSettings(section)`)

Modale unique à colonne de sections (`setGoSection(id)`), plus « paramètres du PEA » :

| Section    | Contenu                                                            |
|------------|--------------------------------------------------------------------|
| general    | thème, couleur d'accent, icône de l'app, code PIN de l'utilisateur  |
| users      | liste des utilisateurs, création / édition                          |
| nav        | « Modules » : modules à cocher, puis onglets et blocs masqués       |
| pea        | prénom, banque, date d'ouverture, récap fiscal, rapport annuel      |
| comptes    | catégories & emoji, sources, récurrents                             |
| pret       | renvoi vers l'onglet `pr-params`                                    |
| sport      | mes sports, types de séance, routines                               |
| accueil    | tuiles du tableau de bord (idem bouton ✎ de l'accueil)             |
| sauvegarde | destination USB, sauvegarde auto, rotation, restauration            |
| donnees    | dossier (chemin en clair + Ouvrir), export/import, réinitialisation, version |
| maj        | version installée, vérification, version proposée, historique       |

`openConfig()` reste le point d'entrée historique (ouvre sur `general`). Les onglets
Mes comptes et Sports ont un bouton ⚙ dans leur barre d'actions qui ouvre directement
leur section.

**Modules (section `nav`, 4.3.37).** L'entrée « Masqué » est devenue « Modules » (même
`data-set`). En tête, une carte à cocher par section de `NAV_SECTIONS`, les mêmes que
l'assistant des premiers pas (`docs/accueil.md`) : `cfgRenderModules()`, `cfgModule()`.
Cocher affiche **tous** les onglets de la section, décocher les masque tous
(`_afficherModule`, dans `S.uiPrefs.hiddenSidebar` comme l'œil) ; la barre latérale est
redessinée (`_reconstruireSidebar`, qui revient à l'accueil si l'onglet ouvert vient
de disparaître) et les tuiles du module quittent l'accueil. Un module décoché n'est
plus chargé aux lancements suivants ; le recocher le charge tout de suite
(`_chargerModule`, voir `docs/accueil.md`, « Sauf les modules masqués »). Un module est « coché »
dès qu'un de ses onglets est visible. Dessous, la liste « Onglets masqués » ne montre
plus que les onglets des modules affichés (ceux d'un module décoché reviennent par sa
case). Restaurer un onglet ou un bloc redessine la liste sur place
(`_cfgRenderMasques`) : avant, `openConfig()` renvoyait sur Général.

**Retrouver ce qui est masqué (4.4.33, 29/10/2026).** Arthur trouvait compliqué de
retrouver un onglet ou un réglage caché. Deux chemins de plus, sans rien changer à
`hiddenSidebar` ni `hiddenCards` :

* **Barre latérale** : au bas d'une section, une ligne « 2 masqués » (œil barré) liste
  les onglets de la section cachés à l'œil ; un clic sur l'un le réaffiche
  (`_showSidebarItem`). Écrite par `_injectSidebar`, dépliée ou non selon
  `_navMasquesOuvert` (en mémoire). `_hideSidebarItem` redessine maintenant la barre
  (`_reconstruireSidebar`) au lieu de retirer l'élément, pour que la ligne apparaisse
  tout de suite. Le dernier onglet d'une section masqué emporte la section : il revient
  par Modules (le message le dit).
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
