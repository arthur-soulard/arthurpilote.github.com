# Module Vocabulaire

Fiche détaillée tirée de `CLAUDE.md`, qui garde les règles générales (dont les cinq choses à ne jamais casser).

## Module Vocabulaire (vocabulaire.json)

Apprendre des mots par répétition espacée. Quatre boîtes — **1 jour, 1 semaine,
1 mois, 6 mois** — et un principe qui tient en une phrase : un mot su monte
d'une boîte, un mot raté en descend d'une.

API Python : `load_vocabulaire()` / `save_vocabulaire()` — `load_vocabulaire`
renvoie aussi les catalogues (`BOITES`, `MODES`).

Données :

* listes     : `{id, label, icon, color, mode: "trad"|"def"}`
* mots       : `{id, listeId, mot, reponse, exemple, note, boite 1-4,
                prochaine "YYYY-MM-DD", creeLe, derniereRevue, nbVus, nbReussis}`
* historique : `[{date, listeId, vus, ok}]` — un agrégat par jour et par liste,
                purgé au-delà de deux ans. Il ne sert qu'aux courbes.

**Cinq décisions à ne pas défaire :**

1. **Raté = on DESCEND d'une boîte** (et on reste en boîte 1 si on y est déjà),
   su = on monte d'une. Dans les deux cas la prochaine révision tombe à
   l'intervalle de la boîte **d'arrivée** — c'est `voAppliquer()` et rien
   d'autre qui décide. Conséquence voulue : un mot raté en « 6 mois » repasse
   en « 1 mois » et revient donc dans un mois, pas dans six.
2. **Rien n'est corrigé automatiquement.** La saisie sert à s'engager sur une
   réponse avant de la découvrir ; seul le clic sur « Je savais » / « Raté »
   compte. Comparer deux chaînes produirait des faux négatifs sur un accent,
   un synonyme ou un pluriel — et une révision fausse pourrit la boîte d'un
   mot pour des mois. Ne pas « améliorer » ça en comparant les textes.
3. **Les listes ne se mélangent jamais.** La file d'une session est bornée à
   une liste, et chaque liste a ses propres boîtes. C'est la raison d'être de
   `listeId` sur chaque mot, et de listes créables plutôt que deux langues
   codées en dur. Anglais (traduction) et Français (définition) sont livrées
   pour démarrer ; le `mode` ne change que le libellé de la seconde face.
4. **Le sens de la question se choisit au lancement de la session**, pour
   toute la session. Il vit dans `VO_SESS`, jamais dans le fichier : c'est un
   choix du moment, pas une propriété du mot.
5. **Aucun mot n'est livré.** L'intérêt du module est ce qu'Arthur y met.
   `default_data()` ne pose que les deux listes.

Détails qui ont une raison :

* `voBoite()` et `voListe()` retombent explicitement sur la **première** entrée,
  jamais sur la dernière : une boîte inconnue ne doit pas propulser un mot à
  six mois.
* **Chaque validation est écrite sur le disque**, une à la fois (`voSaveQueued`,
  chaînée) : fermer l'app en plein milieu d'une session ne rejoue pas les mots
  déjà tranchés, et deux clics rapides ne s'écrasent pas.
* L'exemple et la note n'apparaissent **qu'après** la révélation : l'exemple
  contient presque toujours le mot, le montrer avant donnerait la solution.
* Les deux boutons de validation affichent **où part le mot** (« passe en
  1 sem », « retombe en 1 j ») : on voit la conséquence avant de trancher.
* Une liste qui contient des mots ne peut pas être supprimée, et il en reste
  toujours au moins une.
* **Supprimer depuis l'onglet Mots (05/10/2026)** : une corbeille par ligne, et
  une case à cocher par ligne (+ « tout cocher » en en-tête) avec un bouton
  « Supprimer N mots » qui n'apparaît qu'une fois des cases cochées
  (`_voSel`, `voCocher`, `voDeleteSelection`, `voSupprimerMots`). Demandé par
  Arthur pour nettoyer un ajout en masse raté : jusque-là, la seule suppression
  était dans la fenêtre du crayon, un mot à la fois. **On ne supprime que ce
  qu'on voit** : un mot coché puis masqué par la recherche ou un filtre sort de
  la sélection. Si l'écriture échoue, la liste en mémoire revient telle qu'elle
  était.
* **« Inverser N mots »** (`voInverserSelection`, même barre, demandé avec) :
  échange mot et réponse des mots cochés **sur place** — boîte, échéance,
  compteurs, exemple et note restent. C'est l'intérêt face à « supprimer puis
  réimporter avec Inverser », qui renverrait chaque mot en boîte 1. Pas de
  confirmation : un second clic rend exactement l'état d'avant.
* **Mot et réponse passent à la ligne** dans les tableaux (`table.tw td.vo-word`,
  `td.vo-rep` : `white-space: normal`). Panne constatée le 05/10/2026 : la règle
  `nowrap` des montants (`.tw td:not(:first-child)`) l'emportait, et une seule
  entrée longue tirée d'un ajout en masse (« First, firstly, first of all… »)
  élargissait le tableau à 1 507 px dans un cadre de 1 092 px qui coupe ce qui
  dépasse : Boîte, Prochaine et le crayon de **tous** les mots sortaient de
  l'écran. Arthur en a conclu qu'on ne pouvait ni modifier ni supprimer un mot.
* L'ajout en masse coupe au **premier** séparateur (tabulation ou `=`) : une
  définition peut donc en contenir d'autres ensuite. Un mot déjà présent dans
  la même liste n'est pas réimporté — sa boîte et son historique sauteraient.
* Les intervalles des boîtes ne se règlent pas : les changer en cours de route
  décalerait toutes les révisions déjà programmées.

Tuiles d'accueil : `voc-jour` (« Liste du jour à faire », qui **disparaît** dès
qu'il n'y a plus rien de dû — c'est tout son intérêt) et `voc-acquis`.

### Lire une capture, une photo de liste ou un PDF (ajout en masse)

Bouton « Lire une image ou un PDF » dans `ov-vo-bulk`, ou Ctrl+V d'une capture
(Win+Maj+S) pendant que la fenêtre est ouverte. Le même bouton est dans l'en-tête des onglets
Réviser et Mots (`voLireImage()` : ouvre la fenêtre et le sélecteur d'images) :
en 4.3.5 il n'était que dans Mots → Ajout en masse, et Arthur ne l'a pas trouvé. Même moteur que Santé (`ocr_win.ps1`, hors
ligne) ; `vocabulaire.lire_images()` / `lire_image_collee()`, API
`vocabulaire_pick_images` (son propre filtre « Images et PDF »),
`vocabulaire_read_images`, `vocabulaire_read_pasted`.
JS : `voBulkPickImages`, `voBulkLire`, le gestionnaire `paste`, `voBulkPreview`
(compte sous la zone les mots prêts et les lignes sans « = », qui seront ignorées).

* **Ça ne fait que remplir la fenêtre**, à la suite de son contenu. Rien n'est
  enregistré avant « Ajouter » : même règle que l'import Santé. Ne pas transformer
  ça en ajout direct.
* **Relecture en tableau (30/09/2026, demandée par Arthur : « là c'est pas bon du
  tout »).** Après une lecture, la zone de texte laisse place à un tableau
  Mot | Réponse (`#vo-bulk-rev`, `_voBulkRows` = null en mode texte) : une case à
  cocher par ligne, chaque case modifiable, « Ajouter » ne prend que les lignes
  cochées et complètes. Les lignes sans « = » (titres, consignes, phrases) sont
  **mises de côté** (`_voBulkMis`), repliées sous le tableau, et « + Mot » en
  refait un mot à compléter, qui se coche tout seul une fois complet. En vrac dans
  la zone, elles faisaient croire que la lecture avait raté. Une paire douteuse
  arrive **décochée** avec sa raison (`voBulkDoute` : un seul petit mot comme
  « avec », en-tête en majuscules, liste « a — b — c », caractères suspects).
  « Modifier en texte » / « Relire en tableau » basculent (`voBulkBasculer`),
  « Inverser » marche dans les deux modes. Du texte tapé ou collé reste en mode
  texte, comme avant. La liste prend `calc(100vh - 520px)` : « Ajouter » reste
  visible sur l'écran d'Arthur (768 px).
* **Titres bilingues et listes** (`_titres_et_listes`) : « To express cause /
  pour exprimer la cause » devient une paire ; une liste de connecteurs juste
  dessous (« First, firstly, … ») prend la traduction du titre. Tout autre ligne
  arrête la liste : les phrases d'exemple sous un tableau restent de côté.
* **Cellules sur deux lignes.** Sans traits de tableau : une ligne orpheline se
  recolle à la case du dessus si celle-ci « appelle une suite » (`_SUITE` : virgule,
  « … », article, « pour » ; pas les prépositions, « Because of » est entier). À
  gauche, une 2e ligne en majuscule (« I agree with / I approve of ») devient une
  expression de plus qui **partage** la traduction (même liste Python). Avec traits :
  `_chercheur_traits` repère les bordures horizontales (image cisaillée de la pente
  du texte, bandes seuillées et réduites par Pillow, morceaux de ~150 px à ±2 px :
  100 % sur un trait, 66 % au plus sur du texte), et `_fusion_cases` fusionne deux
  entrées tombées entre les deux mêmes traits (« I disagree with / I disapprove of »
  = « Je ne suis pas d'accord / avec »), **seulement si les traits sont réguliers**
  (un trait manqué ferait une case deux fois plus haute, et deux lignes seraient
  fusionnées à tort).
* **Mesuré** sur les deux photos de connecteurs contre la liste idéale (106 paires) :
  78 justes, 7 fausses avant ; 104 justes, 0 fausse après, en version réduite comme
  d'origine. Les deux manquantes sont illisibles pour le moteur (« = » et « if »).
  Lecture des deux photos dans l'app : 12 s (130 s avant d'accélérer les traits et
  l'écriture du PNG, voir `_preprocess`).
* **.zip (4.3.9)** : `lire_images` remplace un zip par les images et les PDF qu'il
  contient, avec l'extraction de Santé (`sante._images_du_zip(..., exts)` :
  fichiers cachés de macOS/iPhone ignorés, rien ne sort du dossier temporaire).
  Vérifié : le `Gmail.zip` d'Arthur (ses deux photos) donne 84 paires, comme les
  photos seules ; la fiche PDF dans un zip, exactement le même résultat que seule.
* **PDF (30/09/2026)** : `_lire_pdf` fait rendre chaque page en PNG par le moteur
  PDF de Windows (`Windows.Data.Pdf`, hors ligne, rien à installer), via le mode
  `-PdfDir` d'`ocr_win.ps1`, puis lit chaque page comme une photo. Même chemin
  pour un PDF numérique ou scanné. Rendu à 2× la taille nominale (~190 dpi, texte
  d'une vingtaine de pixels), 20 pages au plus (`PDF_PAGES_MAX`, signalé sous la
  zone). Le mode PDF est **dans** `ocr_win.ps1` et pas dans un second script
  exprès : un nouveau fichier devrait entrer dans les `datas` de la spec (le piège
  n° 4). Mesuré sur une fiche de 3 pages : 30 mots sur 30, accents compris, en 9 s.
* **La page est d'abord coupée en blocs** (`_blocs`, 30/09/2026) : titre, tableau,
  paragraphe, chacun lu avec sa propre mise en page. Constaté sur deux photos de
  fiches de connecteurs (tableaux à quatre colonnes sous des titres qui traversent
  leurs colonnes) : lues d'un seul tenant, aucune colonne n'apparaissait, **2 paires
  sur 330 mots lus** ; par blocs, 44 et 41. Même panne sur un PDF à deux colonnes
  sous un titre centré. Coupure sur un blanc de plus de 1,6 interligne (interligne
  mesuré dans les colonnes), hauteurs redressées de la pente des lignes : sur une
  photo tournée d'un degré, la même ligne descend de 14 px d'une colonne à l'autre.
* Dans un bloc : **les colonnes se prennent deux par deux** (mot | traduction |
  mot | traduction), `_gouttieres` trouve tous les blancs verticaux ; une colonne
  restée seule (phrases d'exemple) sort telle quelle, un séparateur imprimé en tête
  de réponse (« = POUR ») est retiré (`_SEP_TETE`). Et **« mot : définition »** sur
  une ligne (`:`, `=`, tiret entouré d'espaces, flèche). Le reste arrive tel quel,
  sans « = » : l'aperçu le signale.
* Une ligne seule dans son bloc (titre, en-tête, pied de page) n'est jamais coupée
  en « mot = réponse » : « Artificial Intelligence — Vocabulary » n'est pas un mot.
  Sauf si c'est toute l'image (capture d'un seul mot).
* **Bouton « Inverser »** (`voBulkInverser`, 4.3.7) : échange mot et réponse sur
  chaque ligne de la zone. Demandé par Arthur pour une fiche PDF qui met le français
  en premier, à l'inverse de ses photos. Coupe au même endroit que `voBulkParse` ;
  si le nouveau mot contient un « = », la ligne prend une tabulation (prioritaire
  à la lecture). Deux clics redonnent exactement le contenu d'origine.
* `_separer` ne rattache une ligne à la définition précédente que si celle-ci était
  **pleine** (son premier mot n'aurait pas tenu avant la marge droite) : sans ça,
  toutes les phrases d'un exercice qui suivent « Words: … » finissaient collées
  en une ligne géante, comptée comme un mot.
* **Le moteur rend chaque colonne en lignes séparées** : l'appariement se fait par
  position (`_gouttieres` trouve les blancs entre colonnes, `_apparier` réassocie).
  Sur une photo penchée que le moteur n'a pas redressée, toute la colonne de droite
  est décalée d'une même hauteur : `_apparier` cherche ce décalage avant d'apparier.
  C'est pour ça que `ocr_win.ps1` renvoie `l` (numéro de ligne du moteur) et `angle`
  depuis ce changement ; Santé ignore ces deux champs.
* Une traduction trop longue pour une ligne est rattachée à son mot si elle est plus
  proche de lui que l'écart habituel entre deux entrées ; sinon elle sort seule :
  mieux vaut une ligne à trier qu'un mot collé à la mauvaise traduction.
* **Image en gris seulement, à la résolution d'origine** (mesuré le 29/09/2026 sur
  des images de test) : contrastée, une photo penchée n'est plus redressée et « I'd »
  devient « Ild ». Relecture agrandie seulement si les mots font moins de 12 px de
  haut (`PETIT_TEXTE`) : là, l'agrandissement corrige tout ; au-dessus, il dégrade.
  L'agrandissement vise un texte d'une vingtaine de pixels (`_passe`, ×2 à ×4).
* **Une capture d'écran de photo se lit mal, quoi qu'on fasse** (mesuré le
  30/09/2026 en comptant les paires EXACTEMENT justes, la photo pleine résolution
  servant de référence) : en dessous de 900 px de haut pour une page A4, moins de
  la moitié des paires sont justes ; à 550 px, la première passe ne trouve rien et
  les agrandissements ×2 à ×4 ne rendent que du charabia (0 paire juste sur 18).
  D'où : rien de lu → message « choisis plutôt la photo elle-même » ; texte de
  8 px ou moins → lu, avec la note « lecture incertaine » sous la zone. Ne pas
  remettre de passe ×4 « au cas où » : le nombre de paires monte, pas leur justesse.
* **Photo couchée** (orientation perdue en route, téléphone tenu de côté) : le
  moteur n'y lit que des lettres isolées (2 mots lisibles sur 36, contre 72 à 100 %
  sur une page droite). `_lire_image` réessaie à 270°, 90° puis 180° et garde le
  sens le plus lisible (`_lisibles`) : 5 → 43 paires. À l'envers, le moteur se
  débrouille déjà seul. Coût : une seconde lecture, seulement quand la première
  est illisible.
* Vérifié le 30/09/2026 dans le Pilote **installé** (4.3.7, piloté par
  l'accessibilité de Windows) : les deux photos d'origine choisies par le
  sélecteur donnent 84 paires, comme en dev. Une plainte « trop peu de mots » vient
  donc de la façon dont l'image arrive (capture collée, photo couchée), pas de l'exe.
* Seul le français est installé comme langue d'OCR chez Arthur ; il lit bien
  l'anglais, sauf le pronom « I » lu « l » : `_L_POUR_I` le corrige (un « l » seul
  ou « l'd », « l'm »… n'existent pas en français). Même chose pour « In » lu « ln »
  (`_LN_POUR_IN`, vu quatre fois sur deux fiches).
* Une cellule sur deux lignes dans un tableau serré (« As a matter of fact, in fact, /
  at all events, in any case ») : la seconde ligne sort seule, car elle tombe à
  l'écart habituel entre deux entrées. Voulu, même règle que la traduction trop
  longue plus haut.
* Un mot isolé très court (« si ») est parfois ignoré par le moteur : la ligne du mot
  reste alors seule, sans « = », donc visible.
* Du texte collé garde son comportement normal : il l'emporte sur une image.
