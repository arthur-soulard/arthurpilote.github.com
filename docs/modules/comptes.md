# Module Mes comptes

Fiche détaillée tirée de `CLAUDE.md`, qui garde les règles générales (dont les six choses à ne jamais casser).

## Module Mes comptes (finances.json)

Catégories et sous-catégories **portent chacune un emoji** (`icon`), affiché partout :
liste des transactions, sélecteurs, camembert, top de l'année, récurrents.

* `finCatIcon(c)` / `finSubIcon(s)` avec repli (🏷️ dépense, 💰 revenu, • sous-catégorie)
* `finPickIcon(current, titre, callback)` ouvre la modale `ov-fin-icon` (palette + saisie libre)
* `finances.backfill_icons()` côté Python donne un emoji aux fichiers créés avant la 4.1.2,
  en reconnaissant les libellés du jeu par défaut
* **Emoji deviné d'après le libellé (4.2.7)** : `FIN_ICON_GUESS` (mots sans accents ni
  majuscules, première règle qui correspond) via `finGuessIcon(nom)`. Appliqué à la
  création d'une catégorie ou sous-catégorie sans emoji, et au chargement par
  `finBackfillIcons()` sur tout ce qui n'a pas d'emoji ou a gardé le générique 🏷️ / •
  (enregistré ensuite). Une sous-catégorie au libellé inconnu prend l'emoji de sa
  catégorie. 💰 n'est pas considéré comme générique : il peut avoir été choisi.
* **« Autres dépenses » / « Autres revenus » toujours en dernier** : `finCatsOrdered(type)`
  (sélecteurs de la saisie et des récurrents, filtre, liste des catégories, légende du
  camembert). Tri à l'affichage : le fichier garde son ordre, et une catégorie créée
  plus tard se range aussi avant « Autres ». Le top de l'année reste trié par montant.
* **Aide à la saisie (4.2.7)**, dans la fenêtre « Nouvelle dépense / Nouveau revenu » ;
  les deux lisent l'historique du même type (`finTxModels`, un modèle par libellé sans
  accents ni casse, sa saisie la plus récente) et ne font que **pré-remplir** montant,
  catégorie, sous-catégorie et source : la date reste celle du jour, rien n'est
  enregistré sans « Enregistrer », la saisie libre reste entière.
  - « Dépenses fréquentes » (`finRenderFreq`) : les 8 libellés les plus saisis sur
    douze mois, les plus récents d'abord à égalité. Automatique, rien à configurer
    (choix d'Arthur). Masquée en modification.
  - Suggestions sous le libellé (`finAcUpdate`) : ceux qui commencent par la saisie,
    puis ceux dont un mot commence par elle. ↑ ↓ Entrée, Échap ferme la liste sans
    fermer la fenêtre.
  - Après un choix, le montant est sélectionné : il se remplace d'une frappe (courses).

## Changements en lot (demandés par Arthur le 01/11/2026)

Avant, tout se faisait une transaction à la fois, et une catégorie utilisée
ne se supprimait pas (bouton grisé). Bloc « CHANGEMENTS EN LOT » après les
catégories dans index.html. Tout se défait par « Annuler » dans le toast qui
suit (10 s, `finToastAnnuler`) : l'état d'avant (`finSnapshot` : catégories,
transactions, récurrents) est gardé en mémoire seulement.
* **Supprimer une catégorie ou sous-catégorie utilisée** (`finDeleteCat`,
  `finDeleteSub`) : on choisit où vont ses transactions **et récurrents**
  (`finChoisirDest`), puis elle est supprimée. C'est aussi la façon de fusionner.
* **Déplacer une sous-catégorie** dans une autre catégorie du même type
  (`finMoveSub`, flèche ↱). Les numéros de sous-catégorie sont propres à chaque
  catégorie : elle y reçoit le suivant, ou rejoint celle du même nom (sans
  accents ni casse).
* **Cases à cocher** dans la liste (`_finSel`), barre `#fin-selbar` : catégorie
  (dépenses seules ou revenus seuls), source, date (un mois plus tard ou plus tôt,
  même jour ramené au dernier du mois, ou un jour fixe : `finDecalerMois`),
  supprimer. Une case cachée par un filtre ou un autre mois est décochée : une
  action ne touche que ce qu'on voit. Filtre « Tous les mois »
  (`#fin-filter-periode`) pour chercher dans tout l'historique.
* **« Faire pareil pour les autres ? »** (`finProposerPareil`) : après avoir
  changé la catégorie d'une transaction, Pilote propose la même aux autres
  transactions et récurrents du même libellé et du même type. Rien sans « Oui ».
  Pas de règles automatiques (libellé → catégorie) : écartées pour rester simple.

## Importer (JSON ou CSV d'une autre appli, 4.4.40)

Bouton « Importer » de l'en-tête du mois (`finImportLire`). Tout se fait en JS,
rien ne passe par Python avant l'enregistrement habituel (`finPersist`).
* JSON : le premier tableau d'objets (racine, `transactions`, `expenses`…) ; un
  `finances.json` de Pilote garde ses catégories (`categoryId` traduit en nom).
* CSV : séparateur deviné (`;`, `,`, tabulation), colonnes reconnues par leur
  nom (`FIN_IMP_COLS` : date, montant ou débit/crédit, libellé, catégorie,
  sous-catégorie, type, source, note). Dates JJ/MM/AAAA, ISO ou horodatage.
* Sens : la colonne type, sinon le signe ; sans aucun négatif ni colonne
  crédit, tout est une dépense.
* Catégorie, sous-catégorie et source retrouvées par leur nom, sinon créées.
  Doublon (même date, type, montant, libellé) ignoré. Aperçu avant « Importer ».
