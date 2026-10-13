# Pistes d'évolution

Fiche détaillée tirée de `CLAUDE.md`, qui garde les règles générales (dont les six choses à ne jamais casser).

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
- Simulateur de sortie : « si je vends tout et solde le prêt, il me reste X € »
  (proposé de nouveau le 13/10/2026 avec le prêt générique, pas pris)
- Recherche globale (Ctrl+K) sur transactions, séances, pesées, comptes
- Import CSV du relevé bancaire pour « Mes comptes »
- Onglet Stratégie (brainstorming du 03/10/2026, non retenues ce jour-là) :
  projection sur 12 mois d'un scénario répété (écart à la cible et frais
  cumulés) ; rééquilibrage avec ventes, en calcul affiché seulement ; seuil de
  tolérance (n'acheter une ligne qu'à plus de X points sous sa cible) ; étaler
  un gros versement sur deux mois pour deux ordres gratuits

**Écartées, ne pas y revenir sans raison nouvelle :**

- **Module Formation** (formations, certificats, export CV) : retiré à la demande
  d'Arthur le 11/10/2026, il en avait masqué les quatre onglets. `formation.json` et
  `certificats/` restent sur le disque (et dans les sauvegardes USB), plus lus par
  l'app. Le code et sa fiche vivent dans l'historique git (commit `845a705` et avant).

- **Module Vocabulaire** (listes de mots, quatre boîtes, lecture de photos et de
  PDF) : retiré de Pilote à la demande d'Arthur le 11/10/2026. Il garde l'idée, mais
  à part : une page autonome, `Vocabulaire.html` sur son bureau (mêmes boîtes, mêmes
  règles, mots enregistrés dans le navigateur, export / import au format de
  `vocabulaire.json`), sans la lecture d'images qui demandait l'OCR de Windows.
  `vocabulaire.json` reste sur le disque, plus lu par l'app. Le code, sa fiche et le
  mode PDF d'`ocr_win.ps1` vivent dans l'historique git (commit `bb71143` et avant).

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
- **Prélèvements sociaux et impôt dans l'assurance vie du prêt** : ajoutés en
  4.3.27 et 4.3.28 (intérêts nets, intérêts bloqués, simulateur de rachat), retirés
  en 4.3.29 à la demande d'Arthur le 08/10/2026 : il veut le montant déposé et le
  taux annuel. Seuls les frais sur versements sont revenus (4.3.30). Détail dans
  `docs/modules/pret.md`.
- **Cours du soir pour le CTO (Stuttgart, 8 h - 22 h)** : écarté par Arthur le
  13/10/2026 (« non, prends pas les cours de Stuttgart »). Trade Republic cote
  jusqu'au soir, mais Pilote garde la cotation choisie à l'import (Xetra, Paris :
  clôture de 17 h 30, dernier cours à 17 h 35). Écart mesuré le 12/10 au soir sur
  son CTO : … € sur … €. Francfort (`.F`) ne conviendrait pas non plus
  (D5BL.F à 28,40 € pour 49,75 €).

- **Prêt : simulateur « et si je remboursais X € », prêt entre proches sans
  échéancier, argent prêté à quelqu'un** : proposés le 13/10/2026 avec le prêt
  générique, pas pris par Arthur. L'aperçu de la fenêtre d'un remboursement
  anticipé montre déjà son effet avant de l'enregistrer.

**Traité depuis** : l'échéancier prévisionnel du prêt, mois par mois (4.4.17,
onglet Échéancier, `docs/modules/pret.md`). L'emoji par défaut des catégories créées par l'utilisateur est
deviné d'après le libellé (4.2.7, `finGuessIcon`). L'export de tout l'espace utilisateur, longtemps en attente, est
couvert par la sauvegarde USB (archive zip de tout `Donnees/`). L'import par fichier,
lui, ne couvre toujours que `pea_data.json`.
