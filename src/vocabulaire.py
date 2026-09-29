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

Une capture d'ecran ou une photo de liste peut pre-remplir l'ajout en masse
(lire_images, en fin de fichier) : l'utilisateur relit toujours avant
d'ajouter.

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
# d'origine ; une seconde, agrandie x2, seulement si le texte est minuscule
# (mots de moins de PETIT_TEXTE pixels de haut) : la, l'agrandissement
# corrige tout ("owever", accents perdus, "si" oublie). Au-dessus, il degrade
# ("Ild" revient, un glossaire en deux colonnes se melange).
#
# Deux mises en page reconnues :
#   * deux colonnes (mot | traduction) : le moteur rend chaque colonne en
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
# Le moteur (francais) lit le pronom anglais "I" comme un "l". Un "l" seul
# n'existe pas en francais (c'est toujours "l'"), et "l'd", "l'm"... non plus.
_L_POUR_I = re.compile(r"(?<![\w'’])l(?=['’](?:d|m|ll|ve)\b|(?![\w'’]))")


def _propre(s: str) -> str:
    s = _L_POUR_I.sub("I", s or "")
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


def _gouttiere(segs: list):
    """
    Blanc vertical entre deux colonnes : (debut, fin) en pixels, ou None.

    On projette les morceaux sur l'axe horizontal et on cherche une bande que
    rien ne traverse, plus large qu'une espace, avec du texte en quantite des
    deux cotes. Un titre qui court sur presque toute la largeur ne compte pas
    dans la projection : il boucherait le blanc.
    """
    if len(segs) < 4:
        return None
    x_min = min(s["x0"] for s in segs)
    largeur = max(s["x1"] for s in segs) - x_min
    if largeur <= 0:
        return None
    h = statistics.median(s["h"] for s in segs)
    couvert = [False] * (largeur + 1)
    for s in segs:
        if s["x1"] - s["x0"] > 0.6 * largeur:
            continue
        for x in range(s["x0"] - x_min, s["x1"] - x_min + 1):
            couvert[x] = True

    meilleure, score_max = None, 0
    x = 0
    while x <= largeur:
        if couvert[x]:
            x += 1
            continue
        debut = x
        while x <= largeur and not couvert[x]:
            x += 1
        a, b = debut + x_min, x + x_min
        if b - a < 1.5 * h:
            continue
        score = min(sum(1 for s in segs if s["x1"] <= a),
                    sum(1 for s in segs if s["x0"] >= b))
        if score < 2 or score < 0.25 * len(segs):
            continue
        if score > score_max or (score == score_max
                                 and b - a > meilleure[1] - meilleure[0]):
            meilleure, score_max = (a, b), score
    return meilleure


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

    out = [(e["y"], _PUCE_TETE.sub("", " ".join(e["mot"])) + " = " + " ".join(e["rep"]))
           for e in entrees]
    return sorted(out + brut)


def _separer(lignes: list) -> list:
    """
    Lignes "mot : definition" (ou =, tiret, fleche) -> "mot = definition".

    Une ligne sans separateur qui suit une entree, sans blanc marque entre
    les deux, est la suite de sa definition.
    """
    ecarts = [b[0] - a[0] for a, b in zip(lignes, lignes[1:])]
    pas = statistics.median(ecarts) if ecarts else 0
    out, y_prec = [], None
    for y, t in lignes:
        net = _PUCE_TETE.sub("", t)
        m = _SEPARATEUR.search(net)
        if (m and m.start() > 0 and net[m.end():].strip()
                and len(net[:m.start()].split()) <= 6):
            out.append([net[:m.start()], net[m.end():]])
        elif (out and isinstance(out[-1], list) and y_prec is not None
              and y - y_prec <= 1.5 * pas):
            out[-1][1] += " " + t
        else:
            out.append(t)
        y_prec = y
    return [" = ".join(o) if isinstance(o, list) else o for o in out]


def _lignes_depuis_mots(words: list) -> list:
    segs = _segments(words)
    if not segs:
        return []
    goutt = _gouttiere(segs)
    if goutt:
        a, b = goutt
        gauche = [s for s in segs if s["x1"] <= a]
        droite = [s for s in segs if s["x0"] >= b]
        traverse = [(s["cy"], s["t"]) for s in segs if s["x1"] > a and s["x0"] < b]
        # Un glossaire mis en page sur deux colonnes ("mot : definition" des
        # deux cotes) n'est pas une liste mot | traduction : on lit la
        # colonne de gauche, puis celle de droite.
        avec_sep = sum(1 for s in gauche if _SEPARATEUR.search(_PUCE_TETE.sub("", s["t"])))
        if avec_sep * 2 < len(gauche):
            lignes = sorted(_apparier(gauche, droite) + traverse)
            return [_propre(t) for _, t in lignes]
        colonnes = [sorted((s["cy"], s["t"]) for s in c) for c in (gauche, droite)]
        return [_propre(t) for c in colonnes for t in _separer(c)]

    # Une seule colonne : on reprend les lignes entieres du moteur.
    par_ligne = {}
    for s in sorted(segs, key=lambda s: s["x0"]):
        par_ligne.setdefault(s["ligne"], []).append(s)
    lignes = sorted((sum(s["cy"] for s in ss) / len(ss), " ".join(s["t"] for s in ss))
                    for ss in par_ligne.values())
    return [_propre(t) for t in _separer(lignes)]


def _ocr(chemin: str, tmpdir: str, scale: float) -> dict:
    prep = os.path.join(tmpdir, "p%s.png" % scale)
    # Gris seulement ("raw") : voir la mesure en tete de section. Si Pillow ne
    # sait pas ouvrir l'image, le decodeur de Windows tente l'original.
    source = prep if sante._preprocess(chemin, prep, scale, "raw") else chemin
    return sante._run_ocr(source)


def _lire_image(chemin: str) -> dict:
    tmpdir = tempfile.mkdtemp(prefix="pilote_voc_")
    try:
        res = _ocr(chemin, tmpdir, 1.0)
        mots = res.get("words") or []
        if (res.get("ok") and mots
                and statistics.median(w["h"] for w in mots) < PETIT_TEXTE):
            agrandi = _ocr(chemin, tmpdir, 2.0)
            if agrandi.get("ok") and agrandi.get("words"):
                res = agrandi
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
    return {"ok": True, "lignes": _lignes_depuis_mots(res.get("words") or [])}


def lire_images(chemins: list) -> dict:
    """
    Lit des captures ou des photos de listes de mots.

    Retourne {ok, lignes:[str], details:[{file, ok, lignes, error}]}, les
    lignes au format de l'ajout en masse. `ok` n'est faux que si AUCUNE image
    n'a pu etre lue.
    """
    chk = sante.ocr_available()
    if not chk["ok"]:
        return {"ok": False, "error": chk["error"], "lignes": []}
    lignes, details = [], []
    for p in chemins or []:
        nom = os.path.basename(p)
        if not os.path.isfile(p):
            details.append({"file": nom, "ok": False, "lignes": 0,
                            "error": "Image introuvable."})
            continue
        r = _lire_image(p)
        lues = r.get("lignes") or []
        lignes += lues
        details.append({"file": nom, "ok": r["ok"], "lignes": len(lues),
                        "error": r.get("error", "")})
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
        return lire_images([chemin])
    finally:
        try:
            os.remove(chemin)
        except OSError:
            pass
