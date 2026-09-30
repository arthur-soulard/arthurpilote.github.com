# Module Mes comptes

Fiche détaillée tirée de `CLAUDE.md`, qui garde les règles générales (dont les cinq choses à ne jamais casser).

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
