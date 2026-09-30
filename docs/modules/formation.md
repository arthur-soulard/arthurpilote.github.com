# Module Formation

Fiche détaillée tirée de `CLAUDE.md`, qui garde les règles générales (dont les cinq choses à ne jamais casser).

## Module Formation (formation.json)

Ce qui nourrit le CV. Trois natures d'objets sous le même toit, et c'est ce qui
dicte le découpage en quatre onglets :

* les **formations**, qui progressent (`todo` → `encours` → `fini`) et portent
  un certificat une fois terminées — onglets `fo-todo` et `fo-done` ;
* les **expériences, projets et compétences**, qui ne progressent pas : ils
  existent, on les décrit, ils alimentent l'export — onglet `fo-cv` ;
* les **compteurs**, dans `fo-stats`.

API Python : `load_formation()` / `save_formation()` — `load_formation` renvoie
aussi les catalogues (`STATUTS`, `FORMATS`, `PREUVES`, `PRIORITES`, `NIVEAUX`,
`CATEGORIES_COMPETENCE`) et l'état du dossier des certificats. Plus
`formation_add_certificat`, `formation_open_certificat`,
`formation_remove_certificat`, `formation_certificats_state`,
`formation_clean_orphans`, `formation_open_certificats_folder`.

Données :

* formations  : `{id, titre, organisme, url, description, domaineId, format,
                preuve, ects, cpf, dureeEstimee, statut, dateDebut, dateFin,
                dateEcheance, priorite, note, certificat}`
* experiences : `{id, poste, employeur, lieu, debut, fin, missions[], note}`
* projets     : `{id, nom, url, description, techno[], debut, fin, note}`
* competences : `{id, label, categorie, niveau 1-4}`
* domaines    : `{id, label, icon, color}` — éditables, emoji via `finPickIcon`

**Quatre décisions à ne pas défaire :**

1. **Les certificats sont COPIÉS**, jamais référencés là où ils se trouvent
   (`Donnees/users/<slug>/certificats/`). Un chemin vers Téléchargements casse
   au premier rangement, et surtout la sauvegarde USB ne l'embarquerait pas —
   or un certificat est précisément ce qu'on ne peut pas régénérer. Extensions
   en liste blanche, 25 Mo maximum, nom de fichier confiné au dossier
   (`_resolve()`, même protection que le zip-slip de `sauvegarde.py`).
   Ils ne sont **pas** dans les backups quotidiens : `JsonStore` ne sauvegarde
   que le JSON, rien à faire de particulier.
2. **Pas de champ coût.** L'argent vit dans « Mes comptes » ; un même montant
   saisi à deux endroits finit toujours par diverger. Reste `cpf`, qui est une
   info de repérage et pas un montant.
3. **Pas de compteur d'heures.** Une formation a un statut, pas un chronomètre.
   `dureeEstimee` sert aux totaux « charge à venir » et « heures cumulées », et
   personne n'a à la tenir à jour. Un compteur faux vaut moins que pas de compteur.
4. **Supprimer une formation ne supprime pas son certificat**, comme
   `delete_user` qui conserve le dossier. Le ménage est explicite :
   Paramètres → Formation → « Nettoyer les orphelins ».

Détails qui ont une raison :

* `foDomaine()` retombe explicitement sur `dom_autre`, jamais sur le dernier
  élément du tableau. Et `foRenderChartDom()` regroupe par domaine **résolu**,
  pas par id brut : sinon une formation dont le domaine a disparu s'évapore du
  camembert tout en comptant dans le KPI juste au-dessus.
* `foSaveFormation()` efface `dateEcheance` quand le statut passe à `fini`, et
  `dateFin` quand il n'y est plus : sans ça un badge « J−12 » survit sur une
  formation déjà validée.
* `foSafeUrl()` n'ouvre que du `http(s)` — le champ lien est libre.
* Le `poids` des `PREUVES` (diplôme 5 → aucune 1) ordonne l'export CV et le
  graphique : un diplôme se lit avant un badge de MOOC.
* Un domaine utilisé par des formations ne peut pas être supprimé.
* L'export CV est un **bloc de texte à copier**, généré en JS (`foCvText()`).
  Pas de PDF mis en page : il serait retouché ailleurs de toute façon.
* Le fichier est livré avec huit formations d'exemple (`_seed_formations`) —
  un point de départ à corriger, pas une recommandation gravée.

Tuiles d'accueil : `formation-encours`, `formation-annee`, `formation-todo`.
Les échéances restent dans le module (badge dans la liste `fo-todo`) : elles ne
remontent volontairement pas sur l'accueil.
