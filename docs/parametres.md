# Paramètres

Fiche détaillée tirée de `CLAUDE.md`, qui garde les règles générales (dont les cinq choses à ne jamais casser).

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
| vocabulaire| mes listes, ajout en masse, rappel des quatre boîtes                |
| accueil    | tuiles du tableau de bord (idem bouton ✎ de l'accueil)             |
| sauvegarde | destination USB, sauvegarde auto, rotation, restauration            |
| donnees    | dossier, export/import, réinitialisation, version                   |
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
de disparaître) et les tuiles du module quittent l'accueil. Un module est « coché »
dès qu'un de ses onglets est visible. Dessous, la liste « Onglets masqués » ne montre
plus que les onglets des modules affichés (ceux d'un module décoché reviennent par sa
case). Restaurer un onglet ou un bloc redessine la liste sur place
(`_cfgRenderMasques`) : avant, `openConfig()` renvoyait sur Général.

**Mises à jour (section `maj`, 4.3.37).** Le bouton « Vérifier les mises à jour »
quitte « Données & app ». `majRenderSection()` : version installée, la version
proposée s'il y en a une (avec sa fiche et « Installer… », qui ouvre la fenêtre
habituelle), puis l'historique livré avec l'app, la plus récente dépliée. Détail
dans `docs/mise-a-jour.md`, « Fiche des nouveautés ».
