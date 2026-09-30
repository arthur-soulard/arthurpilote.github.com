# Pistes d'évolution

Fiche détaillée tirée de `CLAUDE.md`, qui garde les règles générales (dont les cinq choses à ne jamais casser).

## Pistes en attente (proposées, non décidées)

**Les trois qui manquent le plus** — sans elles, Pilote n'est pas « l'app où je fais
tout ». Recommandées dans cet ordre :

- **Module Tâches** (`taches.json`) : échéance, priorité, projet, récurrence
- **Module Agenda** (`agenda.json`) : mois + semaine, fusionnant séances de sport,
  échéances de prêt, relevé de patrimoine, pesée du 1er
- **Écran « Aujourd'hui »** : tâches du jour + événements + séance prévue + échéances.
  Le premier écran à ouvrir le matin.

Autres pistes :

- Objectif d'heures hebdomadaire, avec jauge en haut de l'agenda sport
- Courbe d'heures cumulées année N vs N−1 dans les statistiques sport
- Échéancier prévisionnel du prêt, mois par mois jusqu'à la dernière mensualité
- Simulateur de sortie : « si je vends tout et solde le prêt, il me reste X € »
- Recherche globale (Ctrl+K) sur transactions, séances, pesées, comptes
- Import CSV du relevé bancaire pour « Mes comptes »

**Écartées, ne pas y revenir sans raison nouvelle :**

- **Version mobile / PWA** : écartée par Arthur en 4.1.4 pour la sécurité des données.
  Les JSON sont en clair et le PIN ne chiffre rien ; exposer le serveur local, même
  derrière un VPN, sortait les données du PC. Si la question revient, le prérequis
  serait le chiffrement au repos, pas le réseau.
- **Agrégation bancaire automatique** : contrat pro + validation réglementaire,
  hors de portée d'une app locale. D'où la saisie mensuelle du patrimoine.
- **Passer le dépôt en privé** : écarté par Arthur le 20/09/2026. `updater.py`
  interroge l'API des releases **sans jeton** (en-têtes `User-Agent` + `Accept`
  seulement, `_fetch()` et le téléchargement) ; sur un dépôt privé cet endpoint
  répond 404, indistinguable d'une absence de nouvelle version — l'app se croirait
  à jour pour toujours, et la panne serait silencieuse. Le gain serait par ailleurs
  nul : aucune donnée n'est exposée, `.gitignore` écarte `Donnees/`, `pea_data*.json`,
  `pin.hash` et `profiles.json`, et **aucun fichier de données n'apparaît dans
  l'historique complet** (vérifié sur les 71 commits, pas seulement sur l'état
  courant). Si la question revient, le prérequis serait un second dépôt public dédié
  aux releases — surtout pas un jeton embarqué dans l'exe, il serait extractible.

**Traité depuis** : l'emoji par défaut des catégories créées par l'utilisateur est
deviné d'après le libellé (4.2.7, `finGuessIcon`). L'export de tout l'espace utilisateur, longtemps en attente, est
couvert par la sauvegarde USB (archive zip de tout `Donnees/`). L'import par fichier,
lui, ne couvre toujours que `pea_data.json`.
