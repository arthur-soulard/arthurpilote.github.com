# Module Tâches

Fiche détaillée tirée de `CLAUDE.md`, qui garde les règles générales (dont les six choses à ne jamais casser).

Décidé avec Arthur le 12/11/2026 : une section à part, « Tâches », sous Vie perso
(pas un onglet de l'Agenda). C'était la première des trois pistes « qui manquent le
plus » de `docs/pistes.md`.

## Données (`taches.json`, `src/taches.py`)

Un `jsonstore.JsonStore` comme Sports : backups quotidiens dans `backups_taches/`,
fichier illisible jamais écrasé (`taches.erreur()`). Python ne fait que garder le
fichier (`Api.load_taches` / `Api.save_taches`), tout se calcule dans la page.

* `taches` : `{id, titre, note, echeance "AAAA-MM-JJ"|"", priorite 0|1|2 (normale,
  haute, urgente), projet, recurrence ""|jour|semaine|mois|an, fait "AAAA-MM-JJ"|"",
  cree}`
* `projets` : les noms déjà utilisés, pour la liste de choix et les puces de filtre
* `faites` : `{id: [dates]}`, les jours où une tâche **récurrente** a été cochée
  (elle ne reste pas cochée : le bilan de l'année les compte là)
* `_nid.tache` : prochain identifiant

## Interface (bloc `tc*` d'index.html)

* Onglets `tc-liste` (« À faire ») et `tc-faites` (« Faites »). La liste est rangée
  en cartes : En retard, Aujourd'hui, Les 7 prochains jours, Plus tard, Sans date ;
  dans chaque carte, la plus urgente d'abord, puis la plus proche (`tcTri`).
* Puces de projet en haut (`ac-chip`, les mêmes que les libellés d'Actus).
* Cocher une tâche récurrente la repousse à sa prochaine échéance **après
  aujourd'hui** (`tcDecaler` : le 31 reste en fin de mois), avec un message
  « Faite. Prochaine fois : … ». Une tâche récurrente sans date part d'aujourd'hui.
* `tcChange()` après chaque modification : fichier, section, accueil, calendrier.

## Ailleurs dans Pilote

* **Agenda** : `agDuJour` ajoute les tâches à faire du jour (type `tache`, sans
  heure) : elles sont dans le calendrier, le détail d'un jour (crayon → la tâche)
  et la tuile « Aujourd'hui dans l'agenda ». Elles ne partent **pas** dans iCloud.
* **Tuiles** : « Tâches du jour » (`tc-jour`, toujours là une fois le module lu :
  on coche et on ajoute depuis elle) et « Tâches en retard » (`tc-retard`, s'efface
  quand rien n'est en retard). Elles s'allument quand on accepte le module dans la
  fenêtre « Nouveau module » (`_demanderNouveauxModules` allume désormais les
  `NAV_MODULES.tuiles` des modules pris).
* **Recherche Ctrl+K** et **bilan de l'année** : voir `docs/accueil.md`.
* Brice (`donnees_exemple.taches`) : une tâche en retard, deux du jour (dont une
  récurrente chaque mois), une la semaine, une faite.

## Vérifié (12/11/2026, copie de l'app sur les données de Brice)

Liste, fenêtre d'une tâche, calendrier, thème sombre, et une tâche mensuelle
cochée le 12/11 repartie au 12/12. Tests : `tests/test_taches.py`.
