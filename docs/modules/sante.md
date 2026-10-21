# Module Santé

Fiche détaillée tirée de `CLAUDE.md`, qui garde les règles générales (dont les six choses à ne jamais casser).

## Module Santé (sante.json)

Pesées de la balance connectée, saisies depuis les captures d'écran de l'app
**FitDays** — il n'existe pas d'API, la capture est le seul pont praticable.

API Python : `load_sante()` / `save_sante()` (+ le catalogue `METRICS`),
`read_screenshots(paths)`, `ocr_available()`.

### Les 14 mesures

`poids` · `imc` · `graisse` · `taux_musculaire` · `poids_sans_graisse` ·
`graisse_sous_cutanee` · `graisse_viscerale` · `eau` · `muscle_squelettique` ·
`masse_musculaire` · `masse_osseuse` · `proteine` · `metabolisme` · `age_corporel`

Chacune porte son `unit`, ses `decimals`, ses `aliases` OCR et son `range`
(bornes physiologiques).

### OCR — ce qui a été mesuré, ne pas le redécouvrir

Moteur : **Windows.Media.Ocr** via `ocr_win.ps1` (PowerShell + WinRT). Aucune
dépendance nouvelle, hors ligne, les captures ne quittent jamais le PC.
Pillow prépare les images ; `ocr_win.ps1` est dans les `datas` de la spec.

Résultat sur les captures réelles : **14/14 en ~10 s** (3 captures).

Quatre pièges, tous traités — ne pas « simplifier » :

1. **La résolution d'origine bat les agrandissements.** Contre-intuitif, mais
   mesuré : 10 valeurs lues à l'échelle 1 contre 8-9 à l'échelle 3, et deux
   fois plus vite. Les petits nombres isolés (graisse viscérale) disparaissent
   dès qu'on agrandit. L'ordre de `VARIANTS` encode ce résultat.
   **Et le canal le plus sombre bat le gris (4.3.9).** FitDays colore chaque
   valeur selon son niveau (vert pâle, orange, bleu) ; converti en gris, un
   « 7.0 » vert pâle devient presque blanc et aucune passe ne le voit. Les deux
   premières passes (mode `min` de `_preprocess`) gardent pour chaque pixel le
   plus sombre des trois canaux : sur fond blanc, le texte coloré devient aussi
   foncé que du noir. Mesuré le 30/09/2026 sur trois vraies captures : 12 valeurs
   sur 14 en gris (graisse viscérale et âge corporel manquants), **14 sur 14**
   avec `min`, aucune valeur fausse de plus, et plus vite (10 s au lieu de 15 s
   pour les trois). Les quatre anciennes passes restent derrière, en rattrapage.
   **L'arrêt anticipé attend les libellés vus** : une passe qui n'apporte rien
   n'arrête plus la lecture si un libellé de la capture attend encore sa valeur
   (`vus`, rempli à la lecture des blocs de `_label_blocks`). L'âge corporel orange n'apparaissait
   qu'à la 3e passe, et la lecture s'arrêtait à la 2e.
2. **Appariement par COLONNES, jamais par lignes.** FitDays coupe ses libellés
   longs sur deux lignes et place la valeur sur la ligne du milieu :
   `Graisse` / `21.3 %` / `corporelle`. Un appariement ligne à ligne rate la
   moitié des mesures (voir `_label_blocks`).
3. **Comparaison des libellés par ENSEMBLE de mots** (`_match_metric`) : le
   moteur renvoie « Corporelle Eau » et « Graisse sous- cutanee eee ».
   L'alias le plus spécifique gagne, sinon « Poids sans graisse » devient
   « Poids ».
4. **L'écran principal est piégé.** Son bloc « Contraste » affiche les ÉCARTS
   depuis une pesée précédente (+1.2 kg, +0.4 %) avec le libellé SOUS le
   chiffre : sans `_bandes_contraste()`, un écart de 0.4 % est enregistré comme
   une valeur. Jusqu'en 4.4.18, tout ce qui suivait le titre était ignoré, ce
   qui a fait perdre le tableau Détails le 14/10/2026 (voir plus bas). Le gros
   cadran, lui, n'a pas de libellé : `_dial_weight()` le reconnaît à sa taille.

### Lecture refaite le 14/10/2026 (pesée du jour lue 9 sur 14)

**La panne.** Ce matin-là, la 2ᵉ capture commençait par le bloc « Contraste »
(Arthur avait moins défilé que d'habitude). Or `_contraste_cutoff` ignorait
**tout ce qui était sous le mot « Contraste »** : le tableau Détails entier
disparaissait (Poids, IMC, Graisse, Taux musculaire, Poids sans graisse,
Graisse sous-cutanée). Second défaut trouvé en reproduisant : si les captures
Détails passaient avant l'écran principal, la pesée prenait la date du bloc
Contraste (13/09, la pesée de comparaison), sans rien signaler.

**Ce qui a changé (sante.py), à ne pas « simplifier » :**

1. **Bandes Contraste** (`_bandes_contraste`) : le bloc est ignoré du titre
   « Contraste » jusqu'au titre « Détails » qui le suit, ou jusqu'en bas
   s'il n'y en a pas. Et une valeur n'est rattachée à un libellé que si elle
   occupe sa hauteur (à 0,6 ligne près) : les tuiles du Contraste, où le
   chiffre est AU-DESSUS de son libellé, ne peuvent plus être prises même si
   le titre n'est pas lu.
2. **Date** : seulement une ligne « HH:MM JJ/MM/AAAA » sans aucun mot
   (`_extract_datetime`). La date de l'écran principal (celui du cadran)
   passe devant les autres. FitDays écrit toujours deux chiffres : un « 5:53 »
   (le « 1 » de 15:53 perdu par le moteur) n'est pas retenu, l'heure reste vide.
3. **Chaque valeur lue au moins deux fois** : la pleine page, puis `_zoom`,
   qui découpe la case de chaque valeur, la contraste, l'agrandit et l'empile
   dans une image à part. Mesuré : le chevron « v » à côté d'un nombre isolé
   suffit à ce que Windows ne lise plus « 8.0 » ou « 50 » ; la case s'arrête
   donc au bord droit des valeurs mesuré sur la page. Une capture s'arrête
   quand chaque libellé vu a sa valeur confirmée (deux lectures identiques).
4. **Vote** (`_voter`) : la valeur la plus souvent lue gagne ; à égalité
   entre deux valeurs, la mesure part dans `doutes`.
5. **Relations de FitDays** (`_coherence`, `_RELATIONS`), vérifiées sur les 7
   vraies pesées : poids sans graisse = poids × (1 − graisse) ; taux
   musculaire = masse musculaire ÷ poids ; poids sans graisse = masse
   musculaire + masse osseuse ; graisse + eau + protéine + os = 100 % ;
   métabolisme à 30 % de Katch-McArdle ; IMC avec la taille des pesées déjà
   enregistrées. Quand une mesure a deux lectures, celle qui fait tenir les
   relations l'emporte ; sinon les mesures en cause vont dans `doutes`.
   **Rien n'est corrigé ni calculé d'office.**
6. **Nombres** (`_valeur`) : FitDays écrit toujours le même nombre de
   décimales par mesure. « 20.396 » (le « % » lu comme des chiffres) est
   refusé ; un entier pour une mesure à une décimale n'est accepté que si,
   tel quel, il sort des bornes et, divisé par 10, y rentre (« 759 » → 75,9,
   « 70 » → 7,0) ; « 14 » (1,4 ou 14,0 ?) et « 71 » (71,1 sans sa décimale)
   sont refusés. Une valeur au point recomposé n'est **pas sûre** : en perdant
   le point, le moteur écorche souvent le chiffre voisin (« 17.5 » lu « 173 »,
   deux fois, sur une capture JPEG). Elle compte pour une demi-voix
   (`_choisir`) et ne confirme rien seule : il faut au moins une lecture avec
   son point, sinon la mesure est « à vérifier ». Le zoom commence à ×3 (lu
   juste à ×3 et ×4, faux à ×2). Une unité qui ne va pas avec la mesure
   (« 1.4% » pour l'IMC, « lb ») est refusée (`_unite_ok`).
7. **Libellés écorchés** (`_match_metric`) : un mot long à une ou deux lettres
   près compte (« Coroorelle ») ; une mesure n'est retenue que si aucun mot du
   bloc n'appartient à une autre mesure (« Poids sans graisse » privé de
   « sans » n'est pas le poids).
8. **Un seul PowerShell par import** (`_ServeurOcr`, `ocr_win.ps1 -Serveur`) :
   démarrer PowerShell et charger le moteur coûte environ 3 s, lire une image
   0,3 s, et une pesée demande une dizaine de lectures (30 s sans lui, 10 à
   15 s avec, mesuré le 15/10/2026, y compris dans un programme compilé sans
   console comme Pilote.exe). Au moindre accroc (pas de réponse, PowerShell
   fermé, démarrage raté), chaque lecture relance un PowerShell comme avant :
   essayé en cassant le serveur en cours d'import, même résultat. Sur Mac,
   rien ne change (Vision tourne dans Pilote).
9. Mode sombre inversé, HEIC lu par le moteur de Windows quand Pillow ne sait
   pas l'ouvrir (sinon message « envoie la capture en PNG ou en JPG »),
   `.webp` accepté, chemin absolu donné à `ocr_win.ps1` (un chemin relatif
   faisait échouer `GetFileFromPathAsync`).

**Interface** : `res.doutes` surligne les champs en orange (`.sa-field.doute`,
couleur `--a`) avec « À vérifier sur ta capture : … » ; une date non lue est
signalée (aujourd'hui par défaut). Rouge = non lu, orange = à comparer.

**Banc d'essai** (scratchpad de la session du 14/10/2026) : les 6 vraies
captures (pesées du 08/10 et du 14/10, dans tous les ordres, avec et sans
écran principal) et 110 pesées fabriquées à partir de ces captures (valeurs
repeintes au hasard dans 10 polices et 6 couleurs, défilements variés,
JPEG réduit, largeur Android, demi-taille ; un jeu de 40 jamais vu pendant
les réglages). Résultat : vraies pesées 84 valeurs sur 84 et bonne date dans
tous les cas (avant : 9 sur 14 et date du 13/09) ; jeu neuf, 558 sur 560
justes, **aucune fausse**, 2 laissées vides ; avant, sur 30 pesées, 13 valeurs
fausses non signalées. Les seules valeurs fausses restantes (« 850 » pour
1850 kcal, le « 1 » perdu à chaque lecture) sont surlignées par la relation
du métabolisme. Limite connue : le moteur de Windows lit parfois « 11:44 »
comme « 1:44 » ; l'heure reste alors vide.

`_preprocess` écrit ses PNG avec `compress_level=1` (30/09/2026) : au réglage par
défaut, une photo de 12 Mpx prenait 6,5 s à écrire, pour un fichier qui ne vit que
le temps d'une lecture. Mêmes pixels, même lecture.

Autres garde-fous : `%` rendu « 0/0 » (`_PCT_GARBLE`), point décimal perdu
(« 152 » → 15.2 via `_validate`, qui REFUSE plutôt que d'inscrire une valeur
hors bornes), dates rejetées comme valeurs (`_NOT_A_VALUE`).

### Captures envoyées en .zip (4.3.8)

Arthur s'envoie ses captures par mail ; Gmail rend les pièces jointes en un seul
`.zip` (« tout télécharger »). Le sélecteur de Santé accepte donc les `.zip`
(`sante_pick_screenshots`), et `read_screenshots` remplace chaque zip par les images
qu'il contient (`_images_du_zip`, PNG / JPG / HEIC, 20 au plus, 25 Mo chacune),
extraites dans un dossier temporaire supprimé à la fin. Ce sont les mêmes règles que
pour plusieurs captures choisies à la main : **toutes sont une seule pesée**.

* Les fichiers cachés que macOS et l'iPhone glissent dans une archive (`__MACOSX/`,
  `._IMG_1234.PNG`) ont une extension d'image sans en être une : ignorés.
* Le chemin d'extraction est choisi par Pilote, jamais repris de l'archive : un
  membre `../../x.png` ne sort pas du dossier temporaire (testé).
* Vérifié le 30/09/2026 sur le vrai zip FitDays d'Arthur (3 captures) : exactement
  le même résultat qu'en choisissant les trois images une à une.

### L'import ne valide jamais tout seul

L'OCR pré-remplit un formulaire, **surligne en rouge** ce qu'il n'a pas su lire
et attend une validation. Une donnée de santé fausse est pire qu'une donnée
absente : ne pas transformer ça en enregistrement direct.

Données :
* mesures : `{id, date, time, source:"ocr"|"manuel", note, + les 14 métriques}`
* goals   : `{id, metric, target, start, date, status, createdAt, note}`
  → avancement = distance parcourue / distance totale ; perte et gain se
    calculent pareil (`saGoalProgress`, côté JS uniquement — il n'y a
    volontairement pas de second calcul en Python)

UI : `sa*` dans index.html. Les métriques où **baisser est bon** (poids, IMC,
graisses, âge corporel) sont listées dans `saDeltaClass` — c'est ce qui décide
de la couleur verte ou rouge.

**Comparer avec une pesée choisie (4.2.6).** L'onglet Suivi a un sélecteur
« Comparer avec » : la pesée précédente (défaut) ou n'importe quelle pesée plus
ancienne. Le choix vit dans `SA.uiCompare` (id de la pesée, mémorisé dans
`sante.json` comme `SA.uiRange`) ; `saRef()` renvoie la pesée de référence et
retombe sur `saPrev()` si le choix ne vaut plus rien (pesée supprimée ou devenue la
dernière). Les chiffres clés et la grille « Dernière pesée » l'utilisent et disent
contre quoi ils comparent (`saRefLabel` : « vs 15 sept. »). La tuile « Poids » de
l'accueil **partage ce choix** et porte son propre sélecteur « Comparer avec »
(4.2.9) : changer d'un côté change l'autre, un seul réglage enregistré. Les options
viennent de `saCompareOptions(court)` pour les deux sélecteurs (libellés courts
sur la tuile). Le sélecteur est inerte en mode édition et absent s'il n'y a
qu'une pesée.

**Choix glissants (4.2.9).** En plus d'une date précise, `SA.uiCompare` accepte
`"w1"` (il y a une semaine), `"m1"` (il y a un mois) et `"first"` (la première
pesée). `saRefChoisie(choix)` résout le choix : pour `w1`/`m1`
(`SA_CMP_GLISSANT`, 7 et 30 jours), la pesée **la plus proche** de N jours avant
la **dernière pesée** (pas avant aujourd'hui : une pesée vieille de trois semaines
ferait tout retomber sur la précédente), la plus ancienne à égalité. Un historique
plus court que la période retombe donc sur la première pesée, et c'est la date
affichée (« vs 15 sept. ») qui le dit. Dans l'onglet Suivi, chaque choix glissant
affiche entre parenthèses la pesée qu'il désigne aujourd'hui.

**Tuile « Poids » (4.2.9).** Sous l'écart de poids, la graisse et la masse
musculaire depuis la même pesée (`dashSanteCompo`, vert ou rouge selon
`saDeltaClass`, une mesure absente est omise) : le poids seul ne dit pas si
c'est du gras ou du muscle qui a bougé. Cette ligne passe par le champ `subHtml`
de `dashCardHtml` (HTML déjà échappé par le widget, sous `sub`). La mini-courbe
(`dashSanteSpark`) couvre au moins les 12 dernières pesées et remonte toujours
jusqu'à la pesée de référence ; le trait prend l'accent à partir d'elle et reste
estompé avant (`dashSpark(vals, depuis)`, classe `.dash-spark-ctx`).

**Nombres à la française (4.2.9).** `saFmt` et `saDelta` passent par
`saNombre()` (`toLocaleString("fr-FR")`) : « 77,5 kg », « −0,4 kg », avec une
espace insécable avant l'unité. Tout le module était en « 77.5 kg ». Ces fonctions
ne servent qu'à l'affichage : les champs de saisie gardent leurs valeurs brutes.

## Panne du moteur OCR (4.4.21)

Quand Windows n'a aucune langue de reconnaissance de texte (`no_engine` dans
`ocr_win.ps1`), l'écran d'import le dit en clair (`_cause_ocr`, `_CAUSES_OCR` dans
`sante.py`) au lieu de « Le moteur OCR n'a pas répondu ». Pillow n'ouvre plus que les
formats d'images utiles (`_FORMATS_IMAGE` : PNG, JPEG, WEBP, BMP, GIF) : les failles
connues de Pillow tenaient à d'autres formats.
