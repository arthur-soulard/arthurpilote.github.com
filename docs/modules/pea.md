# PEA : Expositions, Wishlist, Stratégie, courbe du capital

Fiche détaillée tirée de `CLAUDE.md`, qui garde les règles générales (dont les cinq choses à ne jamais casser).

## Enregistrement du PEA (4.3.14)

`persist()` → `_syncToPython()` (délai de 0,4 s) → `_syncToPythonNow()` : relit
`pea_data.json`, y recopie `S`, écrit.

* **Défense « PEA vierge »** : un état où positions, transactions, dépôts,
  clôtures, wishlist, dividendes et stratégies sont **tous** vides (`_peaContenu`)
  n'écrase jamais un fichier rempli : c'est l'état par défaut d'une lecture ratée.
  Jusqu'à la 4.3.13 la règle ne regardait que les positions : vendre ou supprimer
  sa dernière ligne bloquait ensuite **tout** enregistrement du PEA, sans rien dire
  (reproduit : trois ventes, le disque gardait une position et une transaction de
  moins). Une vente laisse des transactions, elle passe. Vider volontairement
  (« Réinitialiser les données PEA », Retour sur la toute première saisie) pose
  `_peaVideVoulu`, qui lève la défense pour une écriture.
* **Le badge « ✓ Sauvegardé » suit l'écriture réelle** (avant : affiché au clic,
  même si l'écriture échouait ensuite). Un échec ou un refus s'affiche en rouge
  (`_alerteEnregistrement`, même message au plus une fois toutes les 10 s).
* **Achat daté du futur** (ordre passé pour demain) : `computePos` ne le compte
  qu'à sa date, la quantité vaut donc 0. `_achatAVenir(p)` garde la ligne dans
  les positions, avec « achat prévu le 2 oct. » ; avant la 4.3.14 elle passait
  parmi les positions clôturées à 0 € et disparaissait pour de bon.
* Enregistrements en attente, fermeture, changement d'utilisateur : voir
  « Enregistrements en attente » dans `CLAUDE.md` (conventions de code).

## Cours et courbe hors ligne (4.3.14)

`pea_data.json._cache` (cours et historiques, `dump_cache()`) est rechargé dans le
serveur par `hydrate_cache()` à chaque `GET /data`, donc **avant** les premiers
`/cours` et `/history` de la page. Quand Yahoo ne répond pas (hors ligne, ou
limite de requêtes), `get_prices` / `get_history` rendent ce dernier état connu
et listent les tickers concernés dans `stale` (réponse JSON).

* Jusqu'à la 4.3.13, rien de ce cache ne servait : les cours n'étaient repris
  qu'au format de l'ancien tracker (`cours`, alors que `dump_cache` écrit `prix`),
  l'historique périmé était ignoré, et la page écrasait sa propre copie de secours
  par une réponse vide. Hors ligne, la courbe était vide et le libellé affichait
  « Dernière actualisation » à l'heure du jour.
* `hydrate_cache` ne remplit que les clés **absentes** : `Api.load_data()` la
  rappelle à chaque enregistrement, et écraser un cours frais par sa copie disque
  relançait Yahoo à chaque fois.
* Côté page : `_coursEtat` (`ok` / `perime` / `erreur`). Aucun cours neuf →
  libellé « Yahoo injoignable · derniers cours connus », une seule notification
  par panne (`_yahooDownSignale`), pas de « Mis à jour ». La carte « Évolution du
  capital » affiche la même mention (`showCacheLabel(null)`).
* Essai de référence : serveur isolé, Yahoo coupé, lancement → 178 points de
  courbe depuis le cache ; Yahoo rétabli → « Dernière actualisation ».

## Onglet Expositions (`pane-sector`, `expositions.py`)

Ce que contiennent vraiment les titres : pays, zones, secteurs et entreprises, chaque
ETF étant décomposé selon **l'indice qu'il suit**. Refait le 30/09/2026 : avant, un ETF
comptait pour un seul secteur « ETF / Fonds » et ses zones étaient devinées d'après
son nom (« world » = 70 % Amérique du Nord…). **Aucune limite ni alerte** : choix
d'Arthur, il lit les chiffres et les interprète (les anciens seuils ont disparu).

**Toujours l'indice, jamais le panier détenu.** Les ETF d'un PEA sont synthétiques
(swap) : ils détiennent des actions européennes et reçoivent la performance de
l'indice. L'API Amundi renvoie pour PEMS un panier ASML, Infineon, Nordea… sans
rapport avec son exposition. Sources, par ETF (`ETFS` dans `expositions.py`) :

| ETF | Indice | Source |
|---|---|---|
| WPEA | MSCI World | lignes d'iShares Core MSCI World (SWDA), même indice |
| PNAS | Nasdaq-100 | lignes d'iShares Nasdaq 100 (CNDX) |
| ESE | S&P 500 | lignes d'iShares Core S&P 500 (CSPX) |
| ETZ | STOXX Europe 600 | lignes d'Amundi Core STOXX Europe 600 (MEUD, physique) |
| PEMS, PANX, GPEA | leur indice | répartition publiée par Amundi (pays, secteurs, 10 premières lignes) |

* iShares ne publie **aucune** répartition pour WPEA lui-même (fiche d'août : « données
  non disponibles ») : d'où SWDA. Pas SSAC pour GPEA : il détient l'Inde, le Brésil, la
  Chine A et l'Arabie saoudite via d'autres ETF, classés « Finance / Irlande » (2,4 %).
* API iShares : `…/product-data/api/v2/get-product-data?component=holdings.all&portfolioId=…`
  (l'ancien lien `.ajax?fileType=csv` renvoie désormais la page HTML). API Amundi :
  POST `https://www.amundietf.fr/mapi/ProductAPI/getProductsData`, champ `breakDown`
  (`INDEX_TOP10` porte son poids dans `adjustedWeight`, pas dans `weight`).
* **Pays = pays du risque (MSCI, S&P, émetteurs)**, pas pays du siège : Linde, Eaton,
  Accenture, Medtronic comptent aux États-Unis. justETF classe au siège : WPEA y montre
  70,0 % d'États-Unis, contre 73,0 % ici. Secteurs GICS ; « Autres secteurs » d'Amundi
  = ses deux plus petits (en général services aux collectivités et immobilier).
* Vérifié le 30/09/2026 : MSCI World et S&P 500 d'iShares contre les indices publiés par
  Amundi (CW8, LU1681048804) → pays à 0,07 point près, secteurs à 0,1 point ; PEMS
  contre la fiche MSCI de son indice, PANX contre celle de Solactive, top 10 contre justETF.
* Une même entreprise sous plusieurs ISIN (Alphabet A/C, Samsung ordinaire/préférentielle,
  ASML d'Amsterdam et son ADR du Nasdaq) est additionnée via `MEME_ENTREPRISE`. Les noms
  d'usage des grosses lignes sont dans `NOMS`, le reste passe par `_joli_nom()`.

**Données.** `expositions_base.py` (généré, livré avec le code) sert tant qu'aucune
mise à jour n'a réussi ; le bouton **« Mettre à jour les données »** relit les sites
dans un thread (`lancer_mise_a_jour`, progression `etat()`, API `load_expositions`,
`expositions_update`, `expositions_status`), le JS suit toutes les 400 ms et affiche le
pourcentage dans le bouton, sans bloquer la navigation. Résultat dans
`Donnees/etf_compositions.json`, **au niveau de l'installation** (données publiques,
comme `sauvegarde.json`). ETF par ETF : un site qui ne répond pas, ou une lecture
incohérente (`_valider` : pays ou secteurs loin de 100 %), laisse l'ancienne composition.
Pour rafraîchir les données livrées avant une version : `python src/expositions.py`.

**Corrections à la main** (« Modifier la composition », fenêtre `ov-expo-edit`) :
`S.uiPrefs.expoPerso[ticker]`, propres à l'utilisateur, prioritaires sur tout le reste.
Une ligne `nom = pourcentage` ; ce qui manque pour 100 % devient « non détaillé » ;
« Autre » (copié de justETF) aussi. Sert aussi à un ETF que Pilote ne suit pas
(« Composition inconnue »).

* Une **action** compte pour son pays de cotation (`EXPO_BOURSE`) et le secteur GICS
  déduit de son secteur de fiche (`EXPO_SECT_ACTION`). Le champ « Zone géographique »
  de la fenêtre Position a disparu (remplacé par la composition).
* Zones au sens de MSCI (Corée, Taïwan, Pologne, Grèce = émergents) : `EXPO_PAYS`.
  Les cinq zones sont **toujours** affichées, même à 0 % (grisées) : avec WPEA seul
  (MSCI World, pays développés), « Pays émergents » disparaissait et Arthur a cru à
  un oubli (« où se retrouve la Chine ? »). La Chine arrive avec PEMS ou GPEA.
* Base = titres hors espèces, comme la répartition de la vue d'ensemble.
* JS : préfixe `expo*`, point d'entrée `renderSectors()` (nom historique, appelé par
  `goTab("sector")` et après une modification de position).

## Wishlist : frais des ETF

Colonne « Frais/an » (TER, frais de gestion annuels) dans le tableau des ETF,
triable ; le premier clic trie du moins cher au plus cher, les frais inconnus
restent en bas.

* **La saisie l'emporte, Yahoo sert de repli.** `w.ter` (en %, 0.25 = 0,25 %) est
  saisi dans la fenêtre de l'ETF ; vide, la colonne affiche
  `_wsKey[ticker].expenseRatio` (fraction, lue par `/keystats` dans
  `fundProfile.feesExpensesInvestment.annualReportExpenseRatio`), en gris avec la
  mention « Yahoo ». Constaté le 27/09/2026 : Yahoo ne connaît que 3 des 7 ETF de
  la wishlist d'Arthur (rien pour ESE, PANX, PEMS, GPEA). D'où la saisie.
* `_wishTer(w)` décide de la valeur, pour l'affichage comme pour le tri.
* Saisie refusée hors de 0 à 5 % : protège de « 25 » tapé pour 0,25 %.
* `fetchKeystats()` interroge désormais aussi les ETF de la wishlist.
* **Noms des ETF** : choisir un ETF dans la recherche recopie le nom de l'index
  `PEA_ETF_BOOST` (server.py) dans la wishlist. Il donnait de faux émetteurs
  (PEMS noté BNP, etc.) : chaque ligne a été revérifiée sur justETF le
  28/09/2026 (4.3.2). Toute nouvelle ligne se vérifie de la même façon :
  fiche justETF, cotation Euronext Paris sous ce ticker, éligibilité PEA.

## Prochain achat (onglet Stratégie, `#card-pac`)

Chaque mois, les ordres à passer pour atteindre puis garder l'allocation cible
(défaut 70 % WPEA / 20 % PEMS / 10 % PNAS), **sans jamais vendre**, au moindre
courtage (Fortuneo : 1er ordre du mois ≤ 500 € gratuit, sinon 0,35 % sans
minimum, plafonné à 0,5 %, le maximum légal en ligne pour un PEA). Algorithme
en 8 étapes écrit par Arthur, appliqué à la lettre dans `pacCalcul()` (pur : ni
écran ni `S`). **`testsProchainAchat()`** (console) vérifie ses six cas chiffrés :
ne jamais modifier le calcul sans les relancer.

* **Arrondis, piège mesuré** : `pacR2()` arrondit le demi-centime vers le haut
  (13 × 7,675 = 99,775 → 99,78 €) ; `toFixed`/`toLocaleString` partent du binaire
  (99,77499…) et donnent 99,77. Le **reliquat** s'arrondit, le **total** affiché
  = budget − reliquat : les deux font toujours le budget (règle des six cas, T3).
  Les comparaisons au budget se font sur les montants non arrondis.
* **Quantités** : `computePos(p).qty` (rien n'est stocké). Une ligne cible non
  détenue vaut 0 ; les positions hors allocation sont listées à part.
* **Budget** = `computeCash()` (versement à saisir dans Dépôts avant). Une saisie
  à la main (`_pacBudget`) n'est pas enregistrée.
* **Ordre gratuit** : détecté (`pacGratuitDetecte`) = achat ou vente du mois,
  ≤ seuil, sans frais. Vérifié sur les données d'Arthur le 27/09/2026 : ses ordres
  sans frais font tous < 500 €. La case l'emporte pour le mois **tant que la
  détection ne change pas** (`gratuitForce.vu`) : un ordre gratuit saisi après
  coup compte même si la case avait été décochée.
* **Heure du cours** : Yahoo diffuse Euronext avec 15 min de retard ; pendant
  la séance on affiche donc l'heure du cours, « clôture du JJ/MM » seulement
  hors séance ou si le cours date d'un autre jour (`pacCoursInfo`).
* **Prix limite** arrondi au millième, comme les cours Yahoo de ces ETF.
* Réglages dans `S.uiPrefs.prochainAchat` (comme les simulateurs) : aucune
  clé nouvelle à ajouter aux chemins de sauvegarde et de chargement.
* `fetchLocalCours()` demande aussi le cours des lignes cibles.
* « Saisir » ouvre `ov-pos` pré-rempli (crée la position si besoin) ; rien
  n'est écrit sans « Enregistrer ». Après saisie, le plan se recalcule.
* Tuile d'accueil `prochain-achat` : le premier ordre, disparaît s'il n'y a
  rien à acheter.

## Simulateur d'ordres (onglet Stratégie, `#card-sim-ordres`)

Le pendant manuel de Prochain achat, juste sous sa carte (ajouté dans la Wishlist
en 4.3.5, regroupé dans Stratégie à la demande d'Arthur le 29/09/2026). Arthur compose ses ordres
lui-même (titre parmi cibles, positions et wishlist ; quantité en parts **ou** en
euros, arrondie à la part inférieure ; prix limite modifiable), Pilote calcule
frais, investi, débité, reste et répartition après achat. **Il ne propose rien.**
Fonctions `so*`, bloc juste après Prochain achat.

* **Un seul calcul des frais** : tarif, seuil de l'ordre gratuit, marge du prix
  limite, plafond de 0,5 % et cibles viennent de `pacCfg()`, arrondis de `pacR2`.
  `soCalcul()` (pur) et `testsSimulateurOrdres()` (console, 10 cas) : les six cas de
  Prochain achat, repris comme ordres manuels, doivent redonner les mêmes frais,
  le même débit et le même reste au centime. Relancer les deux séries de tests
  après toute modification.
* **L'ordre des lignes est l'ordre de passage.** Fortuneo écrit « 0 € le 1er ordre
  inférieur ou égal à 500 € chaque mois » (lu sur fortuneo.fr le 29/09/2026) : le
  premier ordre de la liste qui tient sous le seuil est gratuit, même après un
  ordre plus gros. C'est la lecture de `pacGratuitDetecte`. Flèches ↑↓ pour
  réordonner.
* Budget (espèces par défaut) et case « Ordre gratuit du mois disponible »
  (détection de Prochain achat par défaut) : propres au simulateur, en mémoire,
  jamais enregistrés. Ils valent pour l'éditeur **et** toutes les cartes.
* **Scénarios** dans `S.uiPrefs.simOrdres = {scenarios: [{id, nom, lignes:
  [{ticker, mode "parts"|"eur", val, prix|null}]}]}` : recalculés aux cours du jour
  à chaque affichage, sauf un prix saisi à la main. Le brouillon ne vit qu'en
  mémoire (effacé à la fermeture). Aucun ordre n'est jamais saisi dans le PEA.
* **Plan proposé** : carte de référence en pointillés (non supprimable) et bouton
  « Partir du plan proposé ». `pacPlanCourant(opts)` accepte `{budget,
  gratuitUtilise}` pour calculer le plan avec le budget et l'ordre gratuit du
  simulateur : les deux se comparent à armes égales.
* « Comparer » ouvre un tableau des cartes cochées (ordres, frais, débité, reste,
  poids par ligne, écart max à la cible). Badges « frais les plus bas » et « plus
  proche de la cible » seulement s'il y a au moins deux cartes à comparer.
* **`pacRender()` appelle `soRender()`** en tête : arrivée des cours (toutes les
  3 min), ouverture de l'onglet et réglages de Prochain achat passent tous par là. Si le
  focus est dans l'éditeur, on recalcule sans redessiner les champs (sinon le
  curseur sortait en pleine saisie). Les actions qui changent la structure (titre,
  parts/€, flèches, ajout, retrait, chargement) appellent `soRender(true)`.
* Écartés par Arthur le 29/09/2026 : les frais de gestion annuels (TER) dans la
  comparaison, et l'offre Fortuneo × Amundi (achats de 500 € à 100 000 € sans
  courtage sur ~120 ETF Amundi jusqu'au 31/12/2026 ; ni WPEA, ni PEMS
  FR001400ZGO4, ni PNAS FR001400ZGR7 n'y figurent, seulement PAEEM et PUST).

## Graphique « Évolution du capital » (vue d'ensemble du PEA, `#card-twr`)

Était dans l'onglet Performance jusqu'en 4.2.5 ; même code, même carte, rendue par
`renderPerf()` à chaque `goTab("dash")`.

5 plages dans `#perf-range-btns` : 1S (prb-1w), 1M (prb-1m), 6M (prb-6m),
YTD (prb-ytd), Max (prb-max, défaut).

* `setPerfRange(range)`   — change la plage, highlight le bouton, sauvegarde dans
                            `S.uiPrefs.perfRange`, appelle `drawPerfChart()`
* `filterByRange(series, range)` — filtre `_perfFullSeries` par date
                            (ancre = aujourd'hui local, pas le dernier point)
* `buildTwrSeries(history)` — série journalière à partir de l'historique Yahoo
* `drawPerfChart()`       — dessine le Chart.js ; si < 2 points après filtre →
                            bascule sur MAX avec message
* `loadPerfHistory()`     — double fetch : `range=max` + `range=1mo` (30 derniers jours
                            journaliers garantis, fusionnés) pour que 1S/1M aient
                            toujours leurs points récents
* `computePnl(series, allTxs, range)` — P&L sur la plage (TWR pour les plages partielles)

Format labels axe X : 1S, 1M, YTD → « 12 mai » ; 6M, Max → « nov. 25 »

Points critiques :
* `_perfFullSeries` est mis en cache (reconstruit uniquement si null), invalidé à
  chaque `renderPerf()`
* Le fallback < 2 points reset TOUS les boutons (pas seulement YTD/MAX)
* La plage préférée est persistée dans `S.uiPrefs.perfRange` via
  `pywebview.api.save_ui_prefs()`
