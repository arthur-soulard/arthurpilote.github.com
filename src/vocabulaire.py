"""
vocabulaire.py — Module "Vocabulaire" : apprendre des mots par repetition espacee.

Le principe tient en quatre boites (Leitner) : 1 jour, 1 semaine, 1 mois,
6 mois. Un mot su monte d'une boite, un mot rate DESCEND d'une boite — et
reste en boite 1 s'il y est deja. Dans les deux cas sa prochaine revision
tombe a la date du jour plus l'intervalle de SA NOUVELLE boite.

Consequence utile de la descente : un mot rate en boite "6 mois" repasse en
"1 mois" et revient donc dans un mois, pas dans six. Un mot qu'on ne sait
plus ne doit pas pouvoir se cacher une demi-annee de plus.

Ce qui n'est PAS fait ici
─────────────────────────
La correction. L'app affiche la reponse et c'est l'utilisateur qui tranche
"je savais" / "rate". Comparer deux chaines donnerait des faux negatifs sur
un accent, un synonyme, un article ou un pluriel — et une revision fausse
pourrit la boite d'un mot pour des mois. La saisie sert a s'engager sur une
reponse avant de la decouvrir, elle n'est jamais notee.

Le sens de la question non plus : il est choisi au debut de chaque session,
vaut pour toute la session, et ne se range donc pas dans le fichier.

Chaque liste a ses PROPRES boites : reviser l'anglais ne touche pas au
francais, les deux piles ne se melangent jamais. C'est la raison d'etre du
champ `listeId` sur chaque mot, et de listes creables plutot que de deux
langues codees en dur.

Aucun mot n'est livre : l'interet du module est ce que l'utilisateur y met.
Seules les deux listes de depart existent, et elles sont modifiables.

Une capture d'ecran, une photo de liste ou un PDF peut pre-remplir l'ajout
en masse (lire_images, en fin de fichier) : l'utilisateur relit toujours
avant d'ajouter.

Emplacement      : <app_dir>/users/<slug>/vocabulaire.json
Backup quotidien : <app_dir>/users/<slug>/backups_vocabulaire/

Modele de donnees
─────────────────
listes     : {id, label, icon, color, mode: "trad"|"def"}
mots       : {id, listeId, mot, reponse, exemple, note, boite 1-4,
              prochaine "YYYY-MM-DD", creeLe, derniereRevue, nbVus, nbReussis}
historique : [{date, listeId, vus, ok}] — un agregat par jour et par liste
"""
from __future__ import annotations

import os
import re
import base64
import bisect
import shutil
import datetime
import tempfile
import statistics

import jsonstore
import sante   # meme moteur OCR que les pesees (ocr_win.ps1)


# ─── Catalogues ───────────────────────────────────────────────────────────────

# `jours` est l'intervalle applique QUAND le mot entre dans la boite. C'est la
# seule source de verite du calendrier : l'UI lit ces valeurs, elle ne les
# recopie pas. 182 jours = six mois, a un jour pres selon l'annee.
BOITES = [
    {"id": 1, "label": "1 jour",    "court": "1 j",   "jours": 1,   "color": "#dc2626"},
    {"id": 2, "label": "1 semaine", "court": "1 sem", "jours": 7,   "color": "#d97706"},
    {"id": 3, "label": "1 mois",    "court": "1 mois", "jours": 30,  "color": "#2563eb"},
    {"id": 4, "label": "6 mois",    "court": "6 mois", "jours": 182, "color": "#16a34a"},
]

BOITE_MIN = BOITES[0]["id"]
BOITE_MAX = BOITES[-1]["id"]

# Le mode d'une liste decide du LIBELLE de la seconde face, rien d'autre : la
# mecanique de revision est identique. Une liste de langue demande une
# traduction, une liste de francais demande une definition.
MODES = [
    {"id": "trad", "label": "Traduction", "reponse": "Traduction", "icon": "🔁"},
    {"id": "def",  "label": "Définition", "reponse": "Définition", "icon": "📖"},
]

# Deux listes pour demarrer, pas deux langues gravees : elles se renomment, se
# suppriment et s'ajoutent depuis Parametres → Vocabulaire.
LISTES_DEFAUT = [
    {"id": "li_en", "label": "Anglais",  "icon": "🇬🇧", "color": "#2563eb", "mode": "trad"},
    {"id": "li_fr", "label": "Français", "icon": "🇫🇷", "color": "#7c3aed", "mode": "def"},
]

# L'historique ne sert qu'aux statistiques. Deux ans suffisent largement a
# tracer une courbe, et au-dela le fichier grossirait pour rien.
HISTORIQUE_JOURS = 730


# ─── Normalisation ────────────────────────────────────────────────────────────

def _today() -> str:
    return datetime.date.today().isoformat()


def _clamp_boite(v) -> int:
    try:
        n = int(v)
    except (TypeError, ValueError):
        n = BOITE_MIN
    return max(BOITE_MIN, min(BOITE_MAX, n))


def _int(v, defaut: int = 0) -> int:
    try:
        return max(0, int(v))
    except (TypeError, ValueError):
        return defaut


def _date(v, defaut: str) -> str:
    """Garde une date "YYYY-MM-DD" plausible, sinon renvoie le defaut."""
    s = (v or "").strip()
    if len(s) == 10 and s[4] == "-" and s[7] == "-":
        try:
            datetime.date.fromisoformat(s)
            return s
        except ValueError:
            pass
    return defaut


def _normalise_liste(l: dict) -> dict:
    l.setdefault("id", "")
    l["label"] = (l.get("label") or "Liste").strip() or "Liste"
    l.setdefault("icon", "📚")
    l.setdefault("color", "#2563eb")
    if l.get("mode") not in [m["id"] for m in MODES]:
        l["mode"] = "trad"
    return l


def _normalise_mot(m: dict) -> dict:
    """Complete un mot avec les cles que le JS attend toujours."""
    m.setdefault("id", "")
    m.setdefault("listeId", "")
    m["mot"]     = (m.get("mot") or "").strip()
    m["reponse"] = (m.get("reponse") or "").strip()
    m.setdefault("exemple", "")
    m.setdefault("note", "")
    m["boite"] = _clamp_boite(m.get("boite"))
    cree = _date(m.get("creeLe"), _today())
    m["creeLe"] = cree
    # Un mot sans date de revision est du tout de suite : c'est le cas d'un
    # mot qu'on vient d'ajouter, et celui d'un fichier bricole a la main.
    m["prochaine"]     = _date(m.get("prochaine"), cree)
    m["derniereRevue"] = _date(m.get("derniereRevue"), "")
    m["nbVus"]    = _int(m.get("nbVus"))
    m["nbReussis"] = _int(m.get("nbReussis"))
    return m


# ─── Fichier ──────────────────────────────────────────────────────────────────

def default_data() -> dict:
    return {
        "_meta": {
            "version": 1,
            "schema": "vocabulaire.v1",
            "createdAt":   datetime.date.today().isoformat(),
            "lastSavedAt": datetime.datetime.now().isoformat(timespec="seconds"),
        },
        "listes":     [dict(l) for l in LISTES_DEFAUT],
        "mots":       [],
        "historique": [],
        "_nid": {"li": 1, "mot": 1},
    }


_store = jsonstore.JsonStore(
    filename="vocabulaire.json",
    backup_dirname="backups_vocabulaire",
    schema="vocabulaire.v1",
    default_factory=default_data,
)


def load_data() -> dict:
    data = _store.load()
    for key in ("listes", "mots", "historique"):
        if not isinstance(data.get(key), list):
            data[key] = []

    # Un fichier dont on aurait supprime toutes les listes laisserait les mots
    # orphelins et l'onglet vide sans moyen d'en recreer une.
    if not data["listes"]:
        data["listes"] = [dict(l) for l in LISTES_DEFAUT]
    data["listes"] = [_normalise_liste(l) for l in data["listes"]]

    # Un mot dont la liste a disparu est rattache a la premiere : mieux vaut
    # une ligne mal rangee qu'une ligne invisible qu'on croit perdue.
    connues = {l["id"] for l in data["listes"]}
    defaut  = data["listes"][0]["id"]
    data["mots"] = [_normalise_mot(m) for m in data["mots"]]
    for m in data["mots"]:
        if m["listeId"] not in connues:
            m["listeId"] = defaut

    if not isinstance(data.get("_nid"), dict):
        data["_nid"] = {"li": 1, "mot": 1}
    return data


def save_data(data: dict) -> None:
    data = data or {}
    if isinstance(data.get("historique"), list):
        data["historique"] = _purge_historique(data["historique"])
    _store.save(data)


def _purge_historique(hist: list) -> list:
    """Coupe l'historique a HISTORIQUE_JOURS — il ne sert qu'aux courbes."""
    limite = (datetime.date.today()
              - datetime.timedelta(days=HISTORIQUE_JOURS)).isoformat()
    out = []
    for h in hist:
        if not isinstance(h, dict):
            continue
        d = _date(h.get("date"), "")
        if d and d >= limite:
            out.append(h)
    out.sort(key=lambda h: h.get("date", ""))
    return out


# ─── Lecture d'images (captures d'ecran, photos de pages) ─────────────────────
#
# Meme moteur que le module Sante : l'OCR integre a Windows, hors ligne, les
# images ne quittent pas le PC. La lecture ne fait que PRE-REMPLIR la zone de
# l'ajout en masse, une ligne "mot = reponse" par mot : rien n'est enregistre
# tant que l'utilisateur n'a pas relu et clique sur Ajouter.
#
# Mesure sur des images de test (29/09/2026) : l'image simplement passee en
# gris se lit mieux que retouchee. Contrastee, une photo penchee n'est plus
# redressee par le moteur et "I'd" devient "Ild". Une passe a la resolution
# d'origine ; une seconde, agrandie, seulement si le texte est minuscule
# (mots de moins de PETIT_TEXTE pixels de haut) : la, l'agrandissement
# corrige tout ("owever", accents perdus, "si" oublie). Au-dessus, il degrade
# ("Ild" revient, un glossaire en deux colonnes se melange).
#
# Mesure le 30/09/2026 sur les photos de deux fiches reduites a la taille
# d'une capture d'ecran, en comptant les paires EXACTEMENT justes (la photo
# pleine resolution servant de reference) : l'agrandissement doit viser un
# texte d'une vingtaine de pixels (x3 pour des mots de 7 px : 19 et 16
# paires justes sur 43 et 41, contre 10 et 12 a x2). Mais en dessous de
# 900 px de haut, AUCUN agrandissement ne rend une page lisible, et une
# image dont la premiere passe ne trouve aucun mot (550 px) ne donne que du
# charabia a x2, x3 ou x4 : 0 paire juste sur 18. On ne l'agrandit pas, on
# conseille de choisir la photo elle-meme.
#
# La page est d'abord coupee en blocs (un titre, un tableau, un paragraphe :
# _blocs), chacun avec sa propre mise en page. Une fiche de cours enchaine
# des tableaux sous des titres qui traversent leurs colonnes ; lue d'un seul
# tenant, aucune colonne n'y apparaissait.
#
# Deux mises en page reconnues dans un bloc :
#   * des colonnes prises deux par deux (mot | traduction, ou mot |
#     traduction | mot | traduction) : le moteur rend chaque colonne en
#     lignes SEPAREES, il faut les reapparier par position (_apparier) ;
#   * "mot : definition" sur une ligne : coupure au premier separateur.
# Le reste arrive tel quel dans la zone, a completer a la main.

IMAGE_MAX_OCTETS = 25 * 1024 * 1024
PETIT_TEXTE = 12   # hauteur mediane des mots, en pixels

# Numero ou puce isoles ("1.", "12)", "•") : du bruit, pas une colonne.
_PUCE_SEULE = re.compile(r"^(?:\d{1,3}[.)]?|[•·▪◦*\-–—])$")
# Numero ou puce en tete de ligne : "1. vehement : ..." -> "vehement : ..."
_PUCE_TETE = re.compile(r"^\s*(?:\d{1,3}\s*[.)]|[•·▪◦*]|[-–—](?=\s))\s*")
# Premier separateur mot / reponse. Un tiret n'en est un qu'entoure d'espaces :
# "well-known" reste entier.
_SEPARATEUR = re.compile(r"\s*(?:=|:|→|->|\s[-–—]\s)\s*")
# Separateur imprime en tete de la colonne des reponses ("TO + verbe | = POUR").
_SEP_TETE = re.compile(r"^\s*(?:=|:|→|->)\s*")
# Le moteur (francais) lit le pronom anglais "I" comme un "l". Un "l" seul
# n'existe pas en francais (c'est toujours "l'"), et "l'd", "l'm"... non plus.
_L_POUR_I = re.compile(r"(?<![\w'’])l(?=['’](?:d|m|ll|ve)\b|(?![\w'’]))")
# Meme confusion sur "In" en debut de ligne ("ln addition", "ln spite of") :
# "ln" n'est un mot ni en francais ni en anglais.
_LN_POUR_IN = re.compile(r"(?<![\w'’])ln(?![\w'’])")


def _propre(s: str) -> str:
    s = _L_POUR_I.sub("I", s or "")
    s = _LN_POUR_IN.sub("In", s)
    return re.sub(r"\s+", " ", s).strip()


def _segments(words: list) -> list:
    """
    Morceaux de texte d'un seul tenant, par ligne du moteur.

    Une ligne du moteur est recoupee la ou deux mots sont separes par un grand
    blanc : quand l'ecart entre les colonnes est etroit, il rend parfois le
    mot et sa traduction sur la meme ligne.
    """
    lignes = {}
    for w in words:
        if (w.get("t") or "").strip():
            lignes.setdefault(w.get("l", 0), []).append(w)

    def seg(mots, num):
        return {"t": " ".join(w["t"] for w in mots), "ligne": num,
                "x0": min(w["x"] for w in mots),
                "x1": max(w["x"] + w["w"] for w in mots),
                "cy": sum(w["y"] + w["h"] / 2.0 for w in mots) / len(mots),
                "h": statistics.median(w["h"] for w in mots) or 1}

    out = []
    for num, mots in lignes.items():
        mots.sort(key=lambda w: w["x"])
        h = statistics.median(w["h"] for w in mots) or 1
        courant = [mots[0]]
        for prec, w in zip(mots, mots[1:]):
            if w["x"] - (prec["x"] + prec["w"]) > 1.2 * h:
                out.append(seg(courant, num))
                courant = []
            courant.append(w)
        out.append(seg(courant, num))
    return [s for s in out if not _PUCE_SEULE.match(s["t"].strip())]


def _blocs(segs: list) -> list:
    """
    Coupe la page en bandes horizontales : titre, tableau, paragraphe...

    La coupure tombe sur un blanc nettement plus haut que l'interligne,
    mesure dans les colonnes (entre un morceau et le plus proche en dessous
    qu'il chevauche). Sur une photo un peu tournee, une meme ligne descend
    d'une colonne a l'autre et rogne ce blanc : les hauteurs sont redressees
    de la pente mesuree entre morceaux voisins d'une meme ligne.
    """
    h = statistics.median(s["h"] for s in segs)

    def cx(s):
        return (s["x0"] + s["x1"]) / 2.0

    pentes = [(b["cy"] - a["cy"]) / (cx(b) - cx(a)) for a in segs for b in segs
              if b["x0"] > a["x1"] and abs(b["cy"] - a["cy"]) < 0.8 * h]
    pente = statistics.median(pentes) if len(pentes) >= 3 else 0.0
    for s in segs:
        s["y"] = s["cy"] - pente * cx(s)   # hauteur redressee (sert aussi a _lire_bloc)

    def haut(s):
        return s["y"] - s["h"] / 2.0

    def bas(s):
        return s["y"] + s["h"] / 2.0

    blancs = []
    for s in segs:
        dessous = [haut(t) - bas(s) for t in segs
                   if t["y"] > s["y"] + 0.5 * h
                   and t["x0"] < s["x1"] and t["x1"] > s["x0"]]
        if dessous:
            blancs.append(min(dessous))
    seuil = max(h, 1.6 * statistics.median(blancs)) if blancs else 2 * h

    blocs, fond = [], None
    for s in sorted(segs, key=haut):
        if fond is None or haut(s) - fond > seuil:
            blocs.append([])
            fond = bas(s)
        blocs[-1].append(s)
        fond = max(fond, bas(s))
    return blocs


def _colonne(s: dict, goutt: list):
    """Rang de la colonne d'un morceau, None s'il traverse une gouttiere."""
    i = sum(1 for _, b in goutt if s["x0"] >= b)
    if i < len(goutt) and s["x1"] > goutt[i][0]:
        return None
    return i


def _gouttieres(segs: list) -> list:
    """
    Blancs verticaux entre colonnes : [(debut, fin)] en pixels, de gauche a
    droite ; vide s'il n'y a qu'une colonne.

    On projette les morceaux sur l'axe horizontal et on garde les bandes que
    rien ne traverse, plus larges qu'une espace. Un titre qui court sur
    presque toute la largeur ne compte pas dans la projection : il boucherait
    le blanc. Une colonne doit porter du texte en quantite : un en-tete ou un
    numero de page isole n'en fait pas une, sa gouttiere est retiree.
    """
    if len(segs) < 4:
        return []
    x_min = min(s["x0"] for s in segs)
    largeur = max(s["x1"] for s in segs) - x_min
    if largeur <= 0:
        return []
    h = statistics.median(s["h"] for s in segs)
    couvert = [False] * (largeur + 1)
    for s in segs:
        if s["x1"] - s["x0"] > 0.6 * largeur:
            continue
        for x in range(s["x0"] - x_min, s["x1"] - x_min + 1):
            couvert[x] = True

    goutt, x = [], 0
    while x <= largeur:
        if couvert[x]:
            x += 1
            continue
        debut = x
        while x <= largeur and not couvert[x]:
            x += 1
        if x - debut >= 1.5 * h:
            goutt.append((debut + x_min, x + x_min))

    mini = max(2, 0.15 * len(segs))
    while goutt:
        nb = [0] * (len(goutt) + 1)
        for s in segs:
            i = _colonne(s, goutt)
            if i is not None:
                nb[i] += 1
        i = min(range(len(nb)), key=nb.__getitem__)
        if nb[i] >= mini:
            break
        # La colonne trop maigre rejoint sa voisine la plus proche.
        j = min((j for j in (i - 1, i) if 0 <= j < len(goutt)),
                key=lambda j: goutt[j][1] - goutt[j][0])
        del goutt[j]
    return goutt


def _apparier(gauche: list, droite: list) -> list:
    """
    Reforme les lignes "mot = traduction" d'une liste en deux colonnes.

    Sur une photo penchee que le moteur n'a pas redressee, toute la colonne de
    droite est decalee de la meme hauteur (l'ecart horizontal entre colonnes
    est le meme a chaque ligne). On cherche d'abord ce decalage, celui qui
    aligne le plus de lignes, puis on apparie au plus proche.

    Un morceau sans partenaire juste sous une entree, plus pres d'elle que
    l'ecart habituel entre deux entrees, est la suite d'un texte trop long
    pour tenir sur une ligne. Sinon il sort tel quel : mieux vaut une ligne a
    trier a la main qu'un mot colle a la mauvaise traduction.

    Retourne [(y, texte)].
    """
    h = statistics.median(s["h"] for s in gauche + droite)
    tol = 0.6 * h
    ys_g = sorted(g["cy"] for g in gauche)

    def alignes(dec):
        n = 0
        for d in droite:
            y = d["cy"] - dec
            i = bisect.bisect_left(ys_g, y - tol)
            n += i < len(ys_g) and ys_g[i] <= y + tol
        return n

    candidats = {0.0}
    for g in gauche:
        for d in droite:
            if abs(d["cy"] - g["cy"]) < 3 * h:
                candidats.add(d["cy"] - g["cy"])
    # A egalite, le plus petit decalage : max() garde le premier trouve.
    dec = max(sorted(candidats, key=abs), key=alignes)

    couples = sorted((abs(d["cy"] - dec - g["cy"]), i, j)
                     for i, g in enumerate(gauche) for j, d in enumerate(droite))
    pris_g, pris_d, entrees = set(), set(), []
    for dist, i, j in couples:
        if dist > tol:
            break
        if i in pris_g or j in pris_d:
            continue
        pris_g.add(i)
        pris_d.add(j)
        g, d = gauche[i], droite[j]
        entrees.append({"y": g["cy"], "mot": [g["t"]], "rep": [d["t"]],
                        "fin_g": g["cy"], "fin_d": d["cy"] - dec})
    entrees.sort(key=lambda e: e["y"])

    ecarts = [b["y"] - a["y"] for a, b in zip(entrees, entrees[1:])]
    seuil = 0.85 * statistics.median(ecarts) if ecarts else 1.8 * h

    restes = [(g["cy"], "g", g["t"]) for i, g in enumerate(gauche) if i not in pris_g]
    restes += [(d["cy"] - dec, "d", d["t"]) for j, d in enumerate(droite) if j not in pris_d]
    brut = []
    for y, cote, t in sorted(restes):
        fin = "fin_g" if cote == "g" else "fin_d"
        dessus = [e for e in entrees if e[fin] < y]
        e = max(dessus, key=lambda e: e[fin]) if dessus else None
        if e and y - e[fin] <= seuil:
            e["mot" if cote == "g" else "rep"].append(t)
            e[fin] = y
        else:
            brut.append((y, t))

    out = [(e["y"], _PUCE_TETE.sub("", " ".join(e["mot"])) + " = "
            + _SEP_TETE.sub("", " ".join(e["rep"])))
           for e in entrees]
    return sorted(out + brut)


def _separer(lignes: list, droite: float) -> list:
    """
    Lignes "mot : definition" (ou =, tiret, fleche) -> "mot = definition".
    `lignes` : [(y, texte, x0, x1)], de haut en bas.

    Une ligne sans separateur est la suite de la definition precedente si
    elle la suit sans blanc marque ET si la precedente etait pleine : son
    premier mot n'aurait pas tenu avant la marge `droite`. Sans ce second
    test, toutes les phrases d'un exercice qui suivent "Words: ..." se
    collaient a sa "definition".
    """
    ecarts = [b[0] - a[0] for a, b in zip(lignes, lignes[1:])]
    pas = statistics.median(ecarts) if ecarts else 0
    out, prec = [], None
    for y, t, x0, x1 in lignes:
        net = _PUCE_TETE.sub("", t)
        m = _SEPARATEUR.search(net)
        premier_mot = (x1 - x0) * (len(t.split()[0]) + 1) / max(len(t), 1)
        if (m and m.start() > 0 and net[m.end():].strip()
                and len(net[:m.start()].split()) <= 6):
            out.append([net[:m.start()], net[m.end():]])
        elif (out and isinstance(out[-1], list) and prec is not None
              and y - prec[0] <= 1.5 * pas and prec[1] + premier_mot > droite):
            out[-1][1] += " " + t
        else:
            out.append(t)
        prec = (y, x1)
    return [" = ".join(o) if isinstance(o, list) else o for o in out]


def _lignes_depuis_mots(words: list) -> list:
    segs = _segments(words)
    if not segs:
        return []
    droite = max(s["x1"] for s in segs)
    blocs = _blocs(segs)
    return [_propre(t) for bloc in blocs
            for t in _lire_bloc(bloc, droite, len(blocs) > 1)]


def _lignes_de(segs: list) -> list:
    """[(y, texte, x0, x1)] de haut en bas, pour _separer."""
    return sorted((s["cy"], s["t"], s["x0"], s["x1"]) for s in segs)


def _lire_bloc(segs: list, droite: float, plusieurs: bool) -> list:
    """
    Lignes d'un bloc. `droite` : marge droite de la page ; `plusieurs` :
    la page compte d'autres blocs.
    """
    goutt = _gouttieres(segs)
    if goutt:
        colonnes = [[] for _ in range(len(goutt) + 1)]
        traverse = []
        for s in segs:
            i = _colonne(s, goutt)
            if i is None:
                traverse.append((s["cy"], s["t"]))
            else:
                colonnes[i].append(s)
        # Un glossaire mis en page sur deux colonnes ("mot : definition" des
        # deux cotes) n'est pas une liste mot | traduction : on lit les
        # colonnes l'une apres l'autre.
        gauche = colonnes[0]
        avec_sep = sum(1 for s in gauche if _SEPARATEUR.search(_PUCE_TETE.sub("", s["t"])))
        if avec_sep * 2 >= len(gauche):
            return ([t for _, t in sorted(traverse)]
                    + [t for c in colonnes
                       for t in _separer(_lignes_de(c), max(s["x1"] for s in c))])
        # Colonnes prises deux par deux : mot | traduction | mot | traduction.
        # Une colonne restee seule (des phrases d'exemple) se lit a part.
        out = []
        for k in range(0, len(colonnes), 2):
            if k + 1 < len(colonnes):
                lignes = _apparier(colonnes[k], colonnes[k + 1])
                if k == 0:
                    lignes = sorted(lignes + traverse)
                out += [t for _, t in lignes]
            else:
                c = colonnes[k]
                out += _separer(_lignes_de(c), max(s["x1"] for s in c))
        return out

    # Une seule colonne : on reprend les lignes entieres du moteur.
    par_ligne = {}
    for s in sorted(segs, key=lambda s: s["x0"]):
        par_ligne.setdefault(s["ligne"], []).append(s)
    lignes = sorted((sum(s["cy"] for s in ss) / len(ss), " ".join(s["t"] for s in ss),
                     ss[0]["x0"], max(s["x1"] for s in ss))
                    for ss in par_ligne.values())
    # Une ligne isolee entre deux blancs (titre, en-tete, pied de page) reste
    # telle quelle : "Unit 4 — Travel vocabulary" n'est pas un mot. Sauf si
    # c'est toute l'image : la capture d'un seul mot.
    h = statistics.median(s["h"] for s in segs)
    if plusieurs and max(s["y"] for s in segs) - min(s["y"] for s in segs) < h:
        return [t for _, t, _, _ in lignes]
    return _separer(lignes, droite)


def _ocr(chemin: str, tmpdir: str, scale: float, angle: int = 0) -> dict:
    prep = os.path.join(tmpdir, "p%s_%d.png" % (scale, angle))
    # Gris seulement ("raw") : voir la mesure en tete de section. Si Pillow ne
    # sait pas ouvrir l'image, le decodeur de Windows tente l'original.
    pret = sante._preprocess(chemin, prep, scale, "raw")
    if angle:
        if not pret:
            return {"ok": False, "error": "rotation impossible"}
        from PIL import Image
        with Image.open(prep) as im:
            tournee = im.rotate(angle, expand=True)
        tournee.save(prep)
    return sante._run_ocr(prep if pret else chemin)


def _lisibles(res: dict) -> int:
    """Mots d'au moins deux lettres : le reste est du bruit ("o", "c", "1.")."""
    return sum(1 for w in res.get("words") or []
               if len(re.findall(r"[^\W\d_]", w["t"])) >= 2)


def _passe(chemin: str, tmpdir: str, angle: int) -> dict:
    """Une orientation : resolution d'origine, puis agrandie si le texte est petit."""
    res = _ocr(chemin, tmpdir, 1.0, angle)
    mots = res.get("words") or []
    # Rien de lu du tout : agrandir n'y change rien (voir la mesure en tete
    # de section), _lire_image le dit a l'utilisateur.
    h = statistics.median(w["h"] for w in mots) if mots else 0
    if res.get("ok") and mots and h < PETIT_TEXTE:
        # Viser un texte d'une vingtaine de pixels.
        f = max(2, min(4, round(21.0 / h)))
        agrandi = _ocr(chemin, tmpdir, float(f), angle)
        if agrandi.get("ok") and agrandi.get("words"):
            res = agrandi
            res["minuscule"] = f >= 3
    return res


def _lire_image(chemin: str) -> dict:
    tmpdir = tempfile.mkdtemp(prefix="pilote_voc_")
    try:
        res = _passe(chemin, tmpdir, 0)
        # Photo couchee (telephone tenu de cote, orientation perdue en
        # route) : le moteur n'y voit que des lettres isolees, 2 mots lisibles
        # sur 36 mesure le 30/09/2026, contre 72 a 100 % sur une page droite.
        # On essaie les autres sens et on garde le plus lisible. A l'envers,
        # le moteur se debrouille seul : 180 degres vient en dernier.
        mots = res.get("words") or []
        if res.get("ok") and mots and _lisibles(res) < 0.5 * len(mots):
            for angle in (270, 90, 180):
                essai = _passe(chemin, tmpdir, angle)
                if essai.get("ok") and _lisibles(essai) > _lisibles(res):
                    res = essai
                if _lisibles(res) >= 0.5 * len(res.get("words") or []):
                    break
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    if not res.get("ok"):
        # Le reste des erreurs est un message brut de PowerShell : illisible.
        err = res.get("error") or ""
        if err == "no_engine":
            err = ("Aucune langue de reconnaissance de texte n'est installée "
                   "dans Windows.")
        elif not err.startswith("OCR trop long"):
            err = "Image illisible (format non reconnu ?)."
        return {"ok": False, "error": err}
    if not res.get("words"):
        return {"ok": False,
                "error": ("Aucun texte lisible. Si c'est une capture d'écran d'une "
                          "photo, choisis plutôt la photo elle-même : son texte est "
                          "bien plus net.")}
    out = {"ok": True, "lignes": _lignes_depuis_mots(res.get("words") or [])}
    if res.get("minuscule"):
        out["note"] = ("texte très petit, lecture incertaine (la photo elle-même "
                       "se lit mieux qu'une capture d'écran)")
    return out


# Chaque page coute quelques secondes de lecture, sans barre de progression :
# un manuel entier bloquerait la fenetre de longues minutes.
PDF_PAGES_MAX = 20


def _lire_pdf(chemin: str) -> dict:
    """
    Un PDF, page par page : Windows rend chaque page en image (ocr_win.ps1,
    mode PDF), puis elle est lue comme une photo. Un PDF numerique ou scanne,
    c'est le meme chemin.
    """
    tmpdir = tempfile.mkdtemp(prefix="pilote_pdf_")
    try:
        rendu = sante._run_ocr(chemin, extra=("-PdfDir", tmpdir,
                                              "-PdfMaxPages", str(PDF_PAGES_MAX)))
        if not rendu.get("ok"):
            return {"ok": False,
                    "error": "PDF illisible (abîmé ou protégé par un mot de passe ?)."}
        pages = rendu.get("pages") or []
        lignes, erreurs = [], []
        for page in pages:
            r = _lire_image(page)
            if r["ok"]:
                lignes += r["lignes"]
            else:
                erreurs.append(r["error"])
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    if pages and len(erreurs) == len(pages):
        return {"ok": False, "error": erreurs[0]}
    out = {"ok": True, "lignes": lignes}
    if (rendu.get("total") or 0) > PDF_PAGES_MAX:
        out["note"] = "seules les %d premières pages ont été lues" % PDF_PAGES_MAX
    return out


def lire_images(chemins: list) -> dict:
    """
    Lit des captures, des photos de listes de mots ou des PDF.

    Retourne {ok, lignes:[str], details:[{file, ok, lignes, error, note}]},
    les lignes au format de l'ajout en masse. `ok` n'est faux que si AUCUN
    fichier n'a pu etre lu.
    """
    chk = sante.ocr_available()
    if not chk["ok"]:
        return {"ok": False, "error": chk["error"], "lignes": []}
    lignes, details = [], []
    for p in chemins or []:
        nom = os.path.basename(p)
        if not os.path.isfile(p):
            details.append({"file": nom, "ok": False, "lignes": 0,
                            "error": "Fichier introuvable."})
            continue
        if os.path.splitext(p)[1].lower() == ".pdf":
            r = _lire_pdf(p)
        else:
            r = _lire_image(p)
        lues = r.get("lignes") or []
        lignes += lues
        details.append({"file": nom, "ok": r["ok"], "lignes": len(lues),
                        "error": r.get("error", ""), "note": r.get("note", "")})
    if not any(d["ok"] for d in details):
        err = details[0]["error"] if details else "Aucune image."
        return {"ok": False, "error": err, "lignes": [], "details": details}
    return {"ok": True, "lignes": lignes, "details": details}


def lire_image_collee(data_url: str) -> dict:
    """Image collee depuis le presse-papiers (Win+Maj+S, puis Ctrl+V)."""
    entete, _, b64 = (data_url or "").partition(",")
    if not entete.startswith("data:image/") or ";base64" not in entete:
        return {"ok": False, "error": "Le presse-papiers ne contient pas d'image.",
                "lignes": []}
    if len(b64) * 3 // 4 > IMAGE_MAX_OCTETS:
        return {"ok": False, "error": "Image trop lourde (25 Mo au plus).",
                "lignes": []}
    try:
        octets = base64.b64decode(b64, validate=True)
    except ValueError:
        octets = b""
    if not octets:
        return {"ok": False, "error": "Image illisible.", "lignes": []}
    fd, chemin = tempfile.mkstemp(prefix="pilote_voc_", suffix=".png")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(octets)
        r = lire_images([chemin])
        # Le nom du fichier temporaire ne dit rien a l'utilisateur.
        for d in r.get("details") or []:
            d["file"] = "capture collée"
        return r
    finally:
        try:
            os.remove(chemin)
        except OSError:
            pass
