"""
sante.py — Module "Sante" : pesees issues de la balance connectee (app FitDays).

Deux facons d'entrer une mesure :
  * en deposant les captures d'ecran FitDays -> lecture automatique (OCR) ;
  * a la main, si l'OCR se trompe ou si on n'a pas de capture.

OCR
───
Le moteur est celui integre a Windows (Windows.Media.Ocr), pilote par
`ocr_win.ps1`. Aucune dependance nouvelle, aucun binaire embarque, aucun acces
reseau : les captures ne quittent jamais le PC. Sur Mac, c'est Vision d'Apple
(plateforme.ocr_mac), lui aussi hors ligne, qui rend les memes mots places.

Le moteur ne voit pas tout du premier coup — le texte colore de FitDays (vert,
orange, rouge, bleu) lui echappe souvent. On lance donc PLUSIEURS passes avec
des pretraitements differents (niveaux de gris, binarisation, echelles) et on
fusionne : chaque passe rattrape ce que les autres ratent.

L'appariement libelle -> valeur se fait par POSITION, jamais par ordre de
lecture : la mise en page est en deux colonnes, le moteur restitue les lignes
dans un ordre imprevisible, et FitDays coupe ses libelles longs sur deux
lignes en intercalant la valeur entre les deux (voir _lire_mots).

Emplacement : <app_dir>/users/<slug>/sante.json
Backup quotidien : <app_dir>/users/<slug>/backups_sante/sante_YYYY-MM-DD.json

Modele de donnees
─────────────────
mesures : {id, date:"YYYY-MM-DD", time:"HH:MM", source:"ocr"|"manuel",
           note:"", + une cle par metrique (voir METRICS)}
goals   : {id, metric:"poids", target:75.0, start:79.6, date:"YYYY-MM-DD"|"",
           status:"active|done|archived", createdAt, doneAt, note}
profil  : {taille_cm, sexe, naissance}
"""
from __future__ import annotations

import os
import re
import sys
import json
import shutil
import zipfile
import datetime
import tempfile
import threading
import subprocess
import unicodedata
from pathlib import Path
from typing import Optional

import jsonstore


# Seuls ces formats sont decodes : Pillow ne tente plus les autres (PSD, etc.),
# ou se trouvaient les failles de securite connues (SUP-05)
_FORMATS_IMAGE = ["PNG", "JPEG", "WEBP", "BMP", "GIF"]

# ─── Catalogue des metriques ──────────────────────────────────────────────────
# "aliases" : ce que l'OCR peut renvoyer pour ce libelle, en minuscules et sans
# accents (voir _norm). On matche par prefixe/inclusion, donc pas besoin d'etre
# exhaustif sur les fins de mots.

METRICS = [
    {"id": "poids",               "label": "Poids",                 "unit": "kg",
     "aliases": ["poids"], "decimals": 1, "key": True, "range": [25, 300]},
    {"id": "imc",                 "label": "IMC",                   "unit": "",
     "aliases": ["imc", "bmi"], "decimals": 1, "range": [8, 70]},
    {"id": "graisse",             "label": "Graisse corporelle",    "unit": "%",
     "aliases": ["graisse corporelle"], "decimals": 1, "key": True, "range": [2, 70]},
    {"id": "taux_musculaire",     "label": "Taux musculaire",       "unit": "%",
     "aliases": ["taux musculaire"], "decimals": 1, "range": [15, 100]},
    {"id": "poids_sans_graisse",  "label": "Poids sans graisse",    "unit": "kg",
     "aliases": ["poids sans graisse"], "decimals": 1, "range": [15, 250]},
    {"id": "graisse_sous_cutanee", "label": "Graisse sous-cutanée", "unit": "%",
     "aliases": ["graisse sous-cutanee", "graisse sous cutanee"], "decimals": 1,
     "range": [1, 60]},
    {"id": "graisse_viscerale",   "label": "Graisse viscérale",     "unit": "",
     "aliases": ["graisse viscerale"], "decimals": 1, "range": [1, 40]},
    {"id": "eau",                 "label": "Eau corporelle",        "unit": "%",
     "aliases": ["eau corporelle"], "decimals": 1, "range": [20, 85]},
    {"id": "muscle_squelettique", "label": "Muscle squelettique",   "unit": "%",
     "aliases": ["muscle squelettique"], "decimals": 1, "range": [10, 80]},
    {"id": "masse_musculaire",    "label": "Masse musculaire",      "unit": "kg",
     "aliases": ["masse musculaire"], "decimals": 1, "key": True, "range": [10, 200]},
    {"id": "masse_osseuse",       "label": "Masse osseuse",         "unit": "kg",
     "aliases": ["masse osseuse"], "decimals": 1, "range": [0.5, 12]},
    {"id": "proteine",            "label": "Protéine",              "unit": "%",
     "aliases": ["proteine"], "decimals": 1, "range": [3, 45]},
    {"id": "metabolisme",         "label": "Métabolisme de base",   "unit": "kcal",
     "aliases": ["taux metabolique basal", "metabolique basal", "metabolisme"],
     "decimals": 0, "range": [500, 6000]},
    {"id": "age_corporel",        "label": "Âge corporel",          "unit": "",
     "aliases": ["age corporel"], "decimals": 0, "range": [5, 120]},
]

METRIC_IDS = [m["id"] for m in METRICS]
_BY_ID = {m["id"]: m for m in METRICS}


def metric(mid: str) -> dict:
    return _BY_ID.get(mid, {})


# ─── Stockage ─────────────────────────────────────────────────────────────────

def default_data() -> dict:
    return {
        "_meta": {
            "version": 1,
            "schema": "sante.v1",
            "createdAt":   datetime.date.today().isoformat(),
            "lastSavedAt": datetime.datetime.now().isoformat(timespec="seconds"),
        },
        "mesures": [],
        "goals":   [],
        "profil":  {"taille_cm": None, "sexe": "", "naissance": ""},
        "_nid":    {"mesure": 1, "goal": 1},
    }


_store = jsonstore.JsonStore(
    filename="sante.json",
    backup_dirname="backups_sante",
    schema="sante.v1",
    default_factory=default_data,
)

def load_data() -> dict:
    return _store.load()


def save_data(data: dict) -> None:
    _store.save(data)


# ─── Outils texte ─────────────────────────────────────────────────────────────

def _norm(s: str) -> str:
    """Minuscules, sans accents, espaces normalises : pour comparer des libelles."""
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.lower().replace(" ", " ")
    return re.sub(r"\s+", " ", s).strip()


# Le moteur rend souvent "%" comme "0/0", "O/O", "9/0"... et la virgule
# decimale comme un point ou l'inverse.
_PCT_GARBLE = re.compile(r"[0oO9]\s*/\s*[0oO]")


def _clean_value_text(s: str) -> str:
    s = (s or "").replace(" ", " ").strip()
    s = _PCT_GARBLE.sub("%", s)
    return s


# ─── Pretraitement des images ─────────────────────────────────────────────────
# Chaque variante rattrape ce que les autres ratent. L'ordre compte : la
# premiere qui lit une valeur l'emporte, les suivantes ne font que completer.

# Mesure faite sur des captures reelles : la RESOLUTION D'ORIGINE donne les
# meilleurs resultats (les petits nombres isoles comme la graisse viscerale
# disparaissent des qu'on agrandit), et elle est deux fois plus rapide. Les
# variantes agrandies ne servent que de rattrapage.
#
# Les deux premieres (30/09/2026) gardent le canal le plus SOMBRE de chaque
# pixel ("min") au lieu de la luminance. FitDays colore ses valeurs selon leur
# niveau (vert pale, orange, bleu) : en gris, un "6.0" vert pale devient un
# gris presque blanc que le moteur ne voit a aucune echelle. Mesure sur trois
# vraies captures : 12 valeurs sur 14 en gris, 14 sur 14 avec "min" (graisse
# viscerale lue a toutes les echelles, age corporel orange des x1.5), aucune
# valeur fausse de plus. Les anciennes passes restent en rattrapage.
VARIANTS = [
    {"scale": 1.0, "mode": "min"},    # texte colore compris
    {"scale": 1.5, "mode": "min"},    # age corporel orange
    {"scale": 1.0, "mode": "gray"},   # meilleur rendement sur l'ecran Details
    {"scale": 1.5, "mode": "gray"},   # attrape le gros cadran (blanc sur turquoise)
    {"scale": 2.0, "mode": "bin"},
    {"scale": 3.0, "mode": "gray"},
]

# Au-dela, le moteur Windows decroche (images trop grandes) : on borne.
MAX_SIDE = 8000


def _preprocess(src: str, dst: str, scale: float, mode: str) -> bool:
    try:
        from PIL import Image, ImageOps, ImageEnhance
    except Exception as e:
        print(f"[sante] Pillow indisponible : {e}", flush=True)
        return False
    try:
        im = Image.open(src, formats=_FORMATS_IMAGE)
        # Les captures iPhone peuvent porter une rotation EXIF
        try:
            im = ImageOps.exif_transpose(im)
        except Exception:
            pass
        if mode == "min":
            # Canal le plus sombre : sur fond blanc, un texte vert, orange ou
            # bleu devient aussi fonce que du noir (voir VARIANTS).
            from PIL import ImageChops
            r, g, b = im.convert("RGB").split()
            im = ImageChops.darker(ImageChops.darker(r, g), b)
        else:
            im = im.convert("L")   # la couleur disparait : le texte vert, orange
                                   # ou rouge de FitDays redevient lisible
        if _sombre(im):
            im = ImageOps.invert(im)   # mode sombre : texte fonce sur fond clair
        if mode in ("raw", "min"):
            pass               # aucune retouche : c'est souvent le meilleur
        elif mode == "bin":
            im = ImageOps.autocontrast(im, cutoff=1)
            im = im.point(lambda p: 255 if p > 170 else 0)
        else:
            im = ImageOps.autocontrast(im, cutoff=1)
            im = ImageEnhance.Contrast(im).enhance(1.8)
        w, h = im.size
        f = min(scale, MAX_SIDE / max(w, h))
        if f > 1.0:
            im = im.resize((int(w * f), int(h * f)), Image.LANCZOS)
        # Compression minimale : le fichier ne vit que le temps d'une lecture.
        # Au reglage par defaut, une photo de 12 Mpx prenait 6,5 s a ecrire
        # (mesure le 30/09/2026) ; les pixels sont les memes.
        im.save(dst, compress_level=1)
        return True
    except Exception as e:
        print(f"[sante] pretraitement KO : {e}", flush=True)
        return False


# ─── Appel du moteur OCR ──────────────────────────────────────────────────────

def _ocr_script_path() -> str:
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return str(Path(base) / "ocr_win.ps1")
    return str(Path(__file__).resolve().parent / "ocr_win.ps1")


def ocr_available() -> dict:
    """Le moteur OCR (Windows, ou Vision sur Mac) est-il utilisable sur ce poste ?"""
    if sys.platform == "darwin":
        try:
            import Vision  # noqa: F401
            from PIL import Image  # noqa: F401
        except Exception as e:
            return {"ok": False, "error": f"Lecture d'images indisponible : {e}"}
        return {"ok": True}
    if sys.platform != "win32":
        return {"ok": False, "error": "OCR disponible uniquement sous Windows et sur Mac."}
    if not Path(_ocr_script_path()).exists():
        return {"ok": False, "error": "Script OCR introuvable."}
    try:
        from PIL import Image  # noqa: F401
    except Exception:
        return {"ok": False, "error": "Pillow requis pour préparer les images."}
    return {"ok": True}


def _commande_ocr() -> list:
    return ["powershell.exe", "-NoProfile", "-NonInteractive",
            "-ExecutionPolicy", "Bypass", "-File", _ocr_script_path()]


class _ServeurOcr:
    """
    Un seul PowerShell pour toutes les lectures d'un import (ocr_win.ps1
    -Serveur). Lancer PowerShell et charger le moteur coute environ 3 s, lire
    une image 0,3 s : une pesee demande une dizaine de lectures (passes et
    zooms), d'ou 30 s au lieu de 6 sans lui (mesure du 14/10/2026). Au moindre
    accroc (pas de reponse, PowerShell ferme), il s'arrete et chaque lecture
    relance un PowerShell, comme avant.
    """

    def __init__(self):
        import queue
        self.p = subprocess.Popen(_commande_ocr() + ["-Serveur"], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                  creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.q = queue.Queue()
        self.vide = queue.Empty

        def lire():
            for ligne in self.p.stdout:
                self.q.put(ligne.decode("utf-8", "replace").strip())
            self.q.put(None)
        threading.Thread(target=lire, daemon=True).start()
        rep = self._reponse(60)
        if rep != "pret":
            _noter_cause(rep)
            self.fermer()
            raise RuntimeError("serveur OCR indisponible")

    def _reponse(self, delai):
        try:
            return self.q.get(timeout=delai)
        except self.vide:
            return None

    def lire(self, image: str, sortie: str, delai: int = 90) -> bool:
        try:
            self.p.stdin.write((image + "\t" + sortie + "\n").encode("utf-8"))
            self.p.stdin.flush()
        except OSError:
            return False
        return self._reponse(delai) == "fait"

    def fermer(self):
        try:
            self.p.stdin.write(b"\n")
            self.p.stdin.close()
            self.p.wait(timeout=5)
        except Exception:
            try:
                self.p.kill()
            except Exception:
                pass


_serveur = None   # le PowerShell de l'import en cours (read_screenshots)
_cause_ocr = ""   # derniere panne du moteur, en clair, pour l'ecran (ENV-03)

_CAUSES_OCR = {
    "no_engine": "Windows n'a aucune langue de reconnaissance de texte installée : "
                 "Paramètres › Heure et langue › Langue, ajoute le français (ou l'anglais) "
                 "avec la reconnaissance optique de caractères.",
}


def _noter_cause(texte) -> None:
    global _cause_ocr
    texte = str(texte or "")
    for code, phrase in _CAUSES_OCR.items():
        if code in texte:
            _cause_ocr = phrase
            return
    if texte and texte not in ("None", "ko"):
        _cause_ocr = "Le moteur de lecture de Windows a répondu : " + texte


def _run_ocr(image_path: str, timeout: int = 90) -> dict:
    """
    Lance ocr_win.ps1 et retourne {ok, words:[{t,x,y,w,h}], ...}.
    Sur Mac : Vision d'Apple, meme resultat (plateforme.ocr_mac).
    """
    global _serveur
    if sys.platform == "darwin":
        import plateforme
        return plateforme.ocr_mac(image_path)
    out_fd, out_path = tempfile.mkstemp(prefix="pilote_ocr_", suffix=".json")
    os.close(out_fd)
    try:
        image = os.path.abspath(str(image_path))
        if _serveur is not None:
            if _serveur.lire(image, out_path, timeout):
                with open(out_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            _serveur.fermer()      # accroc : retour a un PowerShell par lecture
            _serveur = None
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
        subprocess.run(_commande_ocr() + ["-ImagePath", image, "-JsonPath", out_path],
                       timeout=timeout, capture_output=True, creationflags=flags)
        with open(out_path, "r", encoding="utf-8") as f:
            res = json.load(f)
        if not res.get("ok"):
            _noter_cause(res.get("error"))
        return res
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "OCR trop long (image trop grande ?)"}
    except Exception as e:
        return {"ok": False, "error": str(e)}
    finally:
        try:
            os.remove(out_path)
        except Exception:
            pass


# ─── Lecture d'une capture ────────────────────────────────────────────────────

def _rows_from_words(words: list) -> list:
    """
    Regroupe les mots en lignes horizontales.

    Deux mots appartiennent a la meme ligne si leurs centres verticaux sont
    distants de moins de 60 % de la hauteur du plus grand des deux. Ca tolere
    les libelles sur deux lignes tout en separant deux metriques voisines.
    """
    items = sorted(words, key=lambda w: (w.get("y", 0), w.get("x", 0)))
    rows = []
    for w in items:
        cy = w.get("y", 0) + w.get("h", 0) / 2.0
        placed = False
        for row in rows:
            tol = max(row["h"], w.get("h", 0)) * 0.6
            if abs(cy - row["cy"]) <= tol:
                row["words"].append(w)
                row["cy"] = sum(x.get("y", 0) + x.get("h", 0) / 2.0
                                for x in row["words"]) / len(row["words"])
                row["h"] = max(row["h"], w.get("h", 0))
                placed = True
                break
        if not placed:
            rows.append({"cy": cy, "h": w.get("h", 0), "words": [w]})
    for row in rows:
        row["words"].sort(key=lambda w: w.get("x", 0))
    rows.sort(key=lambda r: r["cy"])
    return rows


def _tokens(s: str) -> set:
    """Mots significatifs d'un libelle, sans accents ni ponctuation."""
    return {t for t in re.split(r"[^a-z0-9]+", _norm(s)) if len(t) > 1}


# Mots des libelles -> metriques qui les emploient. « graisse » sert a quatre
# mesures, « viscerale » a une seule : un mot qui n'appartient qu'a une mesure
# suffit a la reconnaitre quand l'autre ligne du libelle manque (capture coupee).
_VOCAB = {}
for _m in METRICS:
    for _a in _m["aliases"]:
        for _t in _tokens(_a):
            _VOCAB.setdefault(_t, set()).add(_m["id"])


def _distance(a: str, b: str) -> int:
    """Nombre de lettres a changer, ajouter ou retirer pour passer de a a b."""
    prec = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cour = [i]
        for j, cb in enumerate(b, 1):
            cour.append(min(prec[j] + 1, cour[j - 1] + 1, prec[j - 1] + (ca != cb)))
        prec = cour
    return prec[-1]


def _proche(mot: str, ref: str) -> bool:
    """Le moteur ecorche les mots longs (« Coroorelle », « musculalre ») :
    une lettre de travers jusqu'a 7 lettres, deux au-dela ; un mot court
    (« eau », « imc », « sans ») doit etre exact."""
    if mot == ref:
        return True
    tol = 0 if len(ref) <= 4 else (1 if len(ref) <= 7 else 2)
    return bool(tol) and abs(len(mot) - len(ref)) <= tol and _distance(mot, ref) <= tol


def _vocab_de(mot: str) -> set:
    if mot in _VOCAB:
        return {mot}
    return {v for v in _VOCAB if _proche(mot, v)}


def _match_metric(label_text: str) -> Optional[str]:
    """
    Reconnait une metrique a partir du texte OCR d'un bloc de libelle.

    Comparaison par ENSEMBLE de mots, pas par sous-chaine : le moteur rend les
    mots d'un libelle sur deux lignes dans un ordre imprevisible ("Corporelle
    Eau") et y ajoute parfois du bruit ("Graisse sous- cutanee eee"). Un mot
    ecorche compte s'il est proche (_proche).

    Une mesure n'est retenue que si :
      * aucun mot du bloc n'appartient a une AUTRE mesure : « Poids sans
        graisse » dont le moteur aurait perdu « sans » ({poids, graisse}) n'est
        ni le poids ni rien d'autre ;
      * un de ses libelles est complet, ou le bloc contient un mot qui n'est qu'a
        elle (« viscerale », « cutanee »).
    L'alias complet le plus long gagne ; deux mesures a egalite : rien.
    """
    vus = {}
    for t in _tokens(label_text):
        v = _vocab_de(t)
        if v:
            vus[t] = v
    if not vus:
        return None
    presents = set().union(*vus.values())
    best, best_score, egalite = None, None, False
    for m in METRICS:
        alias = [_tokens(a) for a in m["aliases"]]
        siens = set().union(*alias)
        if any(not (v & siens) for v in vus.values()):
            continue
        complet = max((len(a) for a in alias if a <= presents), default=0)
        propre = any(len(_VOCAB[t]) == 1 for t in presents & siens)
        if not complet and not propre:
            continue
        score = (complet, len(presents & siens))
        if best_score is None or score > best_score:
            best, best_score, egalite = m["id"], score, False
        elif score == best_score:
            egalite = True
    return None if egalite else best


# Un libelle a gauche, sa valeur a droite. Mais FitDays coupe ses libelles
# longs sur DEUX lignes, et la valeur se retrouve alors sur la ligne du
# milieu :
#
#     Graisse            <- ligne 1 du libelle
#                21.3 %  <- la valeur, seule sur sa ligne
#     corporelle         <- ligne 2 du libelle
#
# Un appariement ligne a ligne rate donc la moitie des mesures. On raisonne
# en COLONNES : on reconstitue les blocs de libelle a gauche, puis on rattache
# chaque nombre de droite au bloc dont il occupe la hauteur.

_VALUE_TOKEN = re.compile(r"^[-+]?\d")

# "15/09/2026" ou "08:37" commencent par un chiffre mais ne sont pas des
# valeurs : sans ce filtre, une date se retrouve enregistree comme mesure.
_NOT_A_VALUE = re.compile(r"[/:]")

# Frontiere entre la colonne des libelles et celle des valeurs.
_SPLIT_X = 0.45


def _label_blocks(words: list) -> list:
    """Regroupe les mots de gauche en blocs de libelle (1 a 3 lignes)."""
    blocks = []
    for w in sorted(words, key=lambda w: (w.get("y", 0), w.get("x", 0))):
        top = w.get("y", 0)
        bot = top + w.get("h", 0)
        if blocks:
            b = blocks[-1]
            # Meme mot-ligne (chevauchement) ou ligne suivante tres proche :
            # c'est la suite du meme libelle.
            if top - b["bot"] < max(w.get("h", 0), b["h"]) * 0.75:
                b["words"].append(w)
                b["top"] = min(b["top"], top)
                b["bot"] = max(b["bot"], bot)
                b["h"]   = max(b["h"], w.get("h", 0))
                continue
        blocks.append({"top": top, "bot": bot, "h": w.get("h", 0), "words": [w]})
    for b in blocks:
        b["words"].sort(key=lambda w: (w.get("y", 0), w.get("x", 0)))
        b["text"] = " ".join(w.get("t", "") for w in b["words"])
    return blocks


def _validate(mid: str, val: float) -> Optional[float]:
    """
    Garde-fou : une valeur hors des bornes physiologiques est refusee.

    Le cas courant est le point decimal perdu par l'OCR ("152" pour 15.2) :
    on retente en divisant par 10. Si ca ne rentre toujours pas, on prefere
    ne rien ecrire plutot qu'inscrire une donnee de sante fausse.
    """
    rng = metric(mid).get("range")
    if not rng:
        return val
    lo, hi = rng
    if lo <= val <= hi:
        return val
    for factor in (10.0, 100.0):
        if lo <= val / factor <= hi:
            return round(val / factor, 2)
    return None


def _valeur(mid: str, texte: str):
    """
    Le nombre d'un mot de la colonne des valeurs, pour la mesure `mid` :
    (valeur, sure) ou None.

    FitDays ecrit toujours le meme nombre de decimales par mesure (« 6.0 »,
    « 23.1 », « 1650 ») : un nombre qui en a PLUS est un « % » ou un « kg »
    pris pour des chiffres (« 17.696 » pour « 17.6 % ») et il est refuse ; un
    nombre a une decimale attendue qui n'en a AUCUNE a perdu son point
    (« 726 » pour 72.6, « 60 » pour 6.0). Une valeur ainsi recomposee n'est
    pas « sure » : en perdant le point, le moteur ecorche souvent le chiffre
    voisin (« 173 » pour 17.5, 14/10/2026) ; elle ne suffit pas a confirmer.
    """
    s = _clean_value_text(texte)
    m = re.match(r"[-+]?(\d{1,5})(?:[.,](\d+))?", s)
    if not m:
        return None
    dec = metric(mid).get("decimals", 1)
    entier, frac = m.group(1), m.group(2) or ""
    val = float(entier + ("." + frac if frac else ""))
    if len(frac) > dec and frac.strip("0"):
        return None
    if dec and not frac:
        # Point perdu (« 726 » pour 72.6, « 60 » pour 6.0) ou decimale perdue
        # (« 71 » pour 71.1) ? Seul le nombre hors bornes tel quel, et dans les
        # bornes divise par 10, est sur : « 14 » (1.4 ou 14.0 ?) est refuse.
        lo, hi = metric(mid).get("range") or (float("-inf"), float("inf"))
        if not lo <= val <= hi and lo <= val / 10 ** dec <= hi:
            return round(val / 10 ** dec, dec), False
        return None
    v = _validate(mid, val)
    return None if v is None else (v, v == val)


# Unite ecrite a cote de la valeur : « kg », « % » (souvent lu « 0/0 »),
# « kcal » ; « lb » si FitDays est regle en livres (jamais pris pour des kg).
_UNITE_MOT = re.compile(r"(kg|k9|kcal|kca[l1|i]|lbs?|%)$", re.I)


def _unite(w: dict, voisins: list):
    """Unite collee au nombre (« 72.6kg ») ou ecrite juste apres sur la ligne
    -> (unite ou None, bord droit du groupe nombre + unite)."""
    def norm(t):
        t = _clean_value_text(t).lower()
        m = _UNITE_MOT.search(t)
        if not m:
            return None
        u = m.group(1)
        return {"%": "%", "kg": "kg", "k9": "kg"}.get(u, "lb" if u.startswith("lb") else "kcal")
    fin = w.get("x", 0) + w.get("w", 0)
    u = norm(re.sub(r"^[-+]?[\d.,]+\s*", "", _clean_value_text(w.get("t", ""))) or "_")
    if u:
        return u, fin
    cy = w.get("y", 0) + w.get("h", 0) / 2.0
    h = max(w.get("h", 1), 1)
    for v in voisins:
        if v is w:
            continue
        vcy = v.get("y", 0) + v.get("h", 0) / 2.0
        if abs(vcy - cy) <= 0.6 * h and fin - h * 0.2 <= v.get("x", 0) <= fin + 2.5 * h:
            u = norm(v.get("t", ""))
            if u:
                return u, v.get("x", 0) + v.get("w", 0)
    return None, fin


def _unite_ok(mid: str, unite: Optional[str]) -> bool:
    """« 0.8% » ne peut pas etre l'IMC, ni « 60.5 kg » la graisse."""
    if unite is None:
        return True
    return unite == (metric(mid).get("unit") or None)


def _bandes_contraste(words: list, hauteur: int) -> list:
    """
    Bandes horizontales du bloc « Contraste » de FitDays, a ignorer.

    Ce bloc affiche les ECARTS depuis une pesee precedente (2.1 kg, 0.8 %,
    0.6), avec le libelle SOUS le chiffre, et la date de CETTE pesee-la. Il
    va du titre « Contraste » au titre « Details » qui le suit, ou jusqu'en bas
    de la capture. Jusqu'en 4.4.18, TOUT ce qui etait sous le titre etait
    ignore : sur une capture ou le bloc Contraste est en haut (14/10/2026),
    le tableau des Details disparaissait avec lui (9 mesures sur 14).
    """
    bandes = []
    for w in words:
        if not any(_proche(t, "contraste") for t in _tokens(w.get("t", ""))):
            continue
        haut = w.get("y", 0) - w.get("h", 0) * 0.5
        fins = [x.get("y", 0) for x in words
                if x.get("y", 0) > w.get("y", 0) + w.get("h", 0)
                and any(_proche(t, "details") or _proche(t, "reduire") for t in _tokens(x.get("t", "")))]
        bandes.append((haut, min(fins) - 1 if fins else hauteur + 1))
    return bandes


def _hors_bandes(words: list, bandes: list) -> list:
    def dedans(w):
        cy = w.get("y", 0) + w.get("h", 0) / 2.0
        return any(a <= cy <= b for a, b in bandes)
    return [w for w in words if not dedans(w)]


def _dial_weight(words: list):
    """
    Poids affiche dans le grand cadran de l'ecran principal : (valeur, sure)
    ou None.

    Il n'a pas de libelle a cote : on le reconnait a sa taille, tres superieure
    au reste de la page.
    """
    cands = [w for w in words
             if not _NOT_A_VALUE.search(w.get("t", ""))
             and _VALUE_TOKEN.match(_clean_value_text(w.get("t", "")))]
    if not cands:
        return None
    hauteurs = sorted(w.get("h", 0) for w in words if w.get("h", 0) > 0)
    if not hauteurs:
        return None
    mediane = hauteurs[len(hauteurs) // 2]
    plus_gros = max(cands, key=lambda w: w.get("h", 0))
    if plus_gros.get("h", 0) < mediane * 1.8:
        return None
    return _valeur("poids", plus_gros.get("t", ""))


# "08:37 15/09/2026" sur l'ecran principal, ou "13/09/2026" ailleurs.
# FitDays ecrit toujours deux chiffres (« 06:59 », « 08/10/2026 ») : un
# chiffre seul est un chiffre perdu par le moteur (« 5:53 » pour 15:53),
# la date ou l'heure n'est alors pas retenue plutot que fausse.
_DATE_RE = re.compile(r"(?<!\d)(\d{2})[/.](\d{2})[/.](\d{4})")
_TIME_RE = re.compile(r"^([0-2]\d)[:h]([0-5]\d)$")


def _extract_datetime(rows: list) -> dict:
    """
    Date et heure de la pesee : la ligne « 06:59 14/10/2026 » de l'ecran
    principal, seule sur sa ligne. Une date accompagnee d'un mot (« Contraste
    08:48 13/09/2026 ») est celle d'une AUTRE pesee : jamais retenue, meme si
    le moteur a ecorche le mot.
    """
    out = {"date": "", "time": ""}
    for row in rows:
        line = " ".join(w.get("t", "") for w in row["words"])
        m = _DATE_RE.search(line)
        if not m:
            continue
        if re.search(r"[A-Za-zÀ-ÿ]{2,}", _DATE_RE.sub(" ", line)):
            continue
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            out["date"] = datetime.date(y, mo, d).isoformat()
        except ValueError:
            continue
        # L'heure est le mot juste avant, sur la meme ligne
        for w in row["words"]:
            tm = _TIME_RE.match((w.get("t") or "").strip())
            if tm and int(tm.group(1)) < 24:
                out["time"] = f"{int(tm.group(1)):02d}:{tm.group(2)}"
                break
        break
    return out


def _lire_mots(words: list, width: int, height: int) -> dict:
    """
    Ce que dit UNE lecture OCR d'une capture : {lectures: [(metrique,
    (valeur, sure))], blocs: [(metrique, haut, bas, h)], bords, date, time,
    cadran} ; `bords` : bord droit de chaque valeur lue avec son unite (_zoom
    s'en sert) ; `sure` : voir _valeur.
    """
    out = {"lectures": [], "blocs": [], "bords": [], "date": "", "time": "", "cadran": False}
    if not words:
        return out
    words = _hors_bandes(words, _bandes_contraste(words, height))
    out.update(_extract_datetime(_rows_from_words(words)))
    split = (width or 1) * _SPLIT_X
    left  = [w for w in words if w.get("x", 0) < split]
    right = [w for w in words if w.get("x", 0) >= split]

    labelled = []
    for b in _label_blocks(left):
        mid = _match_metric(b["text"])
        if mid:
            labelled.append((mid, b))
            out["blocs"].append((mid, b["top"], b["bot"], b["h"]))

    for w in sorted(right, key=lambda w: (w.get("y", 0), w.get("x", 0))):
        txt = _clean_value_text(w.get("t", ""))
        if not _VALUE_TOKEN.match(txt) or _NOT_A_VALUE.search(txt):
            continue          # "%", "kg" seuls, date ou heure : pas une valeur
        cy = w.get("y", 0) + w.get("h", 0) / 2.0
        # Le libelle dont le nombre occupe la hauteur (a un peu plus d'une
        # demi-ligne pres) : une valeur au-dessus ou au-dessous de son libelle
        # (tuiles du Contraste, graduations) n'est pas a lui.
        cands = []
        for mid, b in labelled:
            tol = 0.6 * max(b["h"], 1)
            if b["top"] - tol <= cy <= b["bot"] + tol:
                cands.append((abs(cy - (b["top"] + b["bot"]) / 2.0), mid))
        if not cands:
            continue
        mid = min(cands)[1]
        unite, bord = _unite(w, right)
        if not _unite_ok(mid, unite):
            continue
        val = _valeur(mid, txt)
        if val is not None:
            out["lectures"].append((mid, val))
            out["bords"].append(bord)

    if not any(mid == "poids" for mid, _ in out["lectures"]):
        # Ecran principal : pas de tableau, mais le poids du grand cadran
        # (reconnu a sa taille : un ecran Details n'a pas de si gros nombre)
        dial = _dial_weight(words)
        if dial is not None:
            out["lectures"].append(("poids", dial))
            out["cadran"] = True
    return out


def _zoom(src: str, blocs: list, tmpdir: str, n: int, bord=None, echelle: float = 2) -> list:
    """
    Seconde lecture des valeurs : la case de la valeur de chaque ligne
    reconnue, decoupee, contrastee, agrandie et empilee dans une image a part.
    Isole de la page, un petit nombre (« 27 » orange, « 6.0 » vert pale)
    est mieux lu ; et chaque valeur l'est une deuxieme fois, independamment
    de la premiere : deux lectures d'accord valent confirmation.

    La case s'arrete juste apres les valeurs (`bord`, mesure sur la page) :
    le chevron « v » de FitDays a cote d'un nombre isole suffit a ce que le
    moteur de Windows ne rende plus rien (« 8.0 », « 50 » : essai du
    14/10/2026).
    """
    if not blocs:
        return []
    try:
        from PIL import Image, ImageChops, ImageOps
        im = Image.open(src, formats=_FORMATS_IMAGE)
        try:
            im = ImageOps.exif_transpose(im)
        except Exception:
            pass
        r, g, b = im.convert("RGB").split()
        im = ImageChops.darker(ImageChops.darker(r, g), b)
        if _sombre(im):
            im = ImageOps.invert(im)
        W, H = im.size
        x1 = int(min(W, bord + 0.02 * W)) if bord else int(0.86 * W)
        x0 = max(int(W * _SPLIT_X), int(x1 - 0.32 * W))
        morceaux, larg, haut = [], 0, 40
        for mid, top, bot, h in blocs:
            m = 0.5 * h
            c = im.crop((x0, int(max(0, top - m)), x1, int(min(H, bot + m))))
            if c.height < 4 or c.width < 4:
                continue
            c = ImageOps.autocontrast(c, cutoff=1)
            c = c.resize((int(c.width * echelle), int(c.height * echelle)), Image.LANCZOS)
            morceaux.append((mid, c, haut))
            larg = max(larg, c.width)
            haut += c.height + 60
        if not morceaux:
            return []
        planche = Image.new("L", (larg + 80, haut), 255)
        for mid, c, y in morceaux:
            planche.paste(c, (40, y))
        chemin = os.path.join(tmpdir, f"z{n}.png")
        planche.save(chemin, compress_level=1)
    except Exception as e:
        print(f"[sante] zoom KO : {e}", flush=True)
        return []
    res = _run_ocr(chemin)
    if not res.get("ok"):
        return []
    mots = res.get("words") or []
    lectures = []
    for mid, c, y in morceaux:
        dedans = [w for w in mots if y <= w.get("y", 0) + w.get("h", 0) / 2.0 <= y + c.height]
        for w in sorted(dedans, key=lambda w: w.get("x", 0)):
            txt = _clean_value_text(w.get("t", ""))
            if not _VALUE_TOKEN.match(txt) or _NOT_A_VALUE.search(txt):
                continue
            if not _unite_ok(mid, _unite(w, dedans)[0]):
                continue
            val = _valeur(mid, txt)
            if val is not None:
                lectures.append((mid, val))
                break
    return lectures


# Echelle de _zoom a chaque tour : une valeur ratee a 2 est souvent lue a 3
# (« 17.5 » lu « 173 » a 2, juste a 3 et 4 : essai du 14/10/2026)
_ECHELLES_ZOOM = [3, 2, 4, 2.5, 3, 2]


def _sombre(im) -> bool:
    """Capture en mode sombre (texte clair sur fond fonce) ?"""
    try:
        from PIL import ImageStat
        return ImageStat.Stat(im.convert("L")).mean[0] < 100
    except Exception:
        return False


def _confirmees(lectures: dict) -> set:
    """Mesures lues au moins deux fois a l'identique, dont une fois « sure »
    (lectures : {metrique: [(valeur, sure)]}, voir _valeur)."""
    out = set()
    for mid, lus in lectures.items():
        for v in {v for v, _ in lus}:
            memes = [s for x, s in lus if x == v]
            if len(memes) >= 2 and any(memes):
                out.add(mid)
    return out


def _choisir(lus: list):
    """La valeur d'une mesure parmi ses lectures [(valeur, sure)] : une
    lecture sure compte une voix, une valeur au point recompose une demi.
    -> (valeur, a_verifier) : a verifier si deux valeurs sont a egalite, ou
    si la gagnante n'a jamais ete lue avec son point."""
    voix = {}
    for v, s in lus:
        voix[v] = voix.get(v, 0) + (1 if s else 0.5)
    ordre = [v for v, _ in lus]
    best = max(voix, key=lambda v: (voix[v], -ordre.index(v)))
    egalite = any(v != best and voix[v] == voix[best] for v in voix)
    return best, egalite or not any(s for v, s in lus if v == best)


def read_screenshot(path: str, cumul: Optional[dict] = None) -> dict:
    """
    Lit UNE capture : plusieurs passes OCR, chaque valeur lue au moins deux
    fois si possible (pleine page, puis valeurs agrandies : _zoom).

    `cumul` : lectures deja faites sur les autres captures de la meme pesee
    ({metrique: [(valeur, sure)]}), pour savoir quand s'arreter.

    Retourne {ok, values:{metrique: valeur}, lectures:{metrique: [(valeur,
    sure)]}, date, time, cadran, passes, engine}.
    """
    chk = ocr_available()
    if not chk["ok"]:
        return {"ok": False, "error": chk["error"], "values": {}}

    src = Path(path)
    if not src.exists():
        return {"ok": False, "error": "Image introuvable.", "values": {}}

    lect = {}                      # {metrique: [valeurs lues sur CETTE capture]}
    dates = []                     # [(date, heure)] lues a chaque passe
    blocs, bords = {}, []          # {metrique: (haut, bas, h)} ; bords droits des valeurs
    cadran, passes, lang, prepare = False, 0, "", 0
    autres = cumul or {}
    largeur = _largeur(str(src))
    tmpdir = tempfile.mkdtemp(prefix="pilote_ocr_")

    def confirmees():
        tout = {k: list(v) + list(autres.get(k, [])) for k, v in lect.items()}
        return _confirmees(tout)

    # Format que Pillow ne sait pas ouvrir (HEIC d'un iPhone) : le moteur de
    # Windows lit peut-etre l'original lui-meme, en une seule passe.
    variantes = VARIANTS if largeur else [None]
    try:
        for i, var in enumerate(variantes):
            if var is None:
                prepped = str(src)
            else:
                prepped = os.path.join(tmpdir, f"p{i}.png")
                if not _preprocess(str(src), prepped, var["scale"], var["mode"]):
                    continue
            prepare += 1
            res = _run_ocr(prepped)
            if not res.get("ok"):
                continue
            passes += 1
            lang = lang or res.get("lang", "")
            # Positions ramenees a l'echelle de la capture d'origine
            f = (res.get("width") or 1) / float(largeur or res.get("width") or 1)
            mots = [dict(w, x=w.get("x", 0) / f, y=w.get("y", 0) / f,
                         w=w.get("w", 0) / f, h=w.get("h", 0) / f)
                    for w in (res.get("words") or [])]
            lu = _lire_mots(mots, (res.get("width") or 1) / f, (res.get("height") or 1) / f)
            for mid, val in lu["lectures"]:
                lect.setdefault(mid, []).append(val)
            cadran = cadran or lu["cadran"]
            if lu["date"]:
                dates.append((lu["date"], lu["time"]))
            for mid, top, bot, h in lu["blocs"]:
                blocs[mid] = (mid, top, bot, h)
            bords += lu["bords"]
            # Valeurs agrandies (_zoom) des lignes dont la valeur n'est pas
            # encore confirmee, a une autre echelle a chaque tour
            a_relire = [b for mid, b in blocs.items() if mid not in confirmees()]
            if a_relire and largeur:
                bord = sorted(bords)[len(bords) // 2] if bords else None
                for mid, val in _zoom(str(src), a_relire, tmpdir, i, bord, _ECHELLES_ZOOM[i % len(_ECHELLES_ZOOM)]):
                    lect.setdefault(mid, []).append(val)
                passes += 1
            # Assez lu : chaque libelle de la capture a sa valeur confirmee
            # (deux lectures d'accord), et sur l'ecran principal le cadran et
            # la date aussi. Une capture ou rien n'est lu essaie toutes les
            # variantes : une capture difficile ne cede parfois qu'a la derniere.
            attendues = set(blocs) | ({"poids"} if cadran else set())
            date_sure = any(dates.count(d) >= 2 for d in dates)
            if attendues and not (attendues - confirmees()) and (date_sure or not cadran):
                break
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    if passes == 0:
        if prepare == 0 or not largeur:
            return {"ok": False, "values": {},
                    "error": "Image illisible (format non pris en charge ?). "
                             "Envoie la capture en PNG ou en JPG."}
        return {"ok": False, "values": {},
                "error": _cause_ocr or "Le moteur OCR n'a pas répondu."}
    values = {mid: _choisir(lus)[0] for mid, lus in lect.items()}
    # Date et heure : les plus souvent lues
    jours = [d for d, _ in dates]
    date = max(jours, key=lambda d: (jours.count(d), -jours.index(d))) if jours else ""
    heures = [t for d, t in dates if d == date and t]
    heure = max(heures, key=lambda t: (heures.count(t), -heures.index(t))) if heures else ""
    return {"ok": True, "values": values, "lectures": lect, "vus": sorted(blocs),
            "date": date, "time": heure, "cadran": cadran, "passes": passes, "engine": lang}


def _largeur(path: str) -> int:
    try:
        from PIL import Image, ImageOps
        with Image.open(path, formats=_FORMATS_IMAGE) as im:
            try:
                im = ImageOps.exif_transpose(im)
            except Exception:
                pass
            return im.size[0]
    except Exception:
        return 0


# ─── Captures envoyees en .zip ────────────────────────────────────────────────
# Arthur s'envoie ses captures par mail, et Gmail rend les pieces jointes en
# un seul .zip ("tout telecharger"). Chaque image de l'archive est lue comme
# si elle avait ete choisie a la main. Les fichiers caches que macOS et
# l'iPhone glissent dans une archive (__MACOSX/, "._IMG_1234.PNG") portent
# une extension d'image sans en etre une : ils sont ignores.

ZIP_EXTS = (".png", ".jpg", ".jpeg", ".heic", ".webp")
ZIP_IMAGES_MAX = 20
ZIP_IMAGE_OCTETS_MAX = 25 * 1024 * 1024


def _images_du_zip(chemin: str, dossier: str):
    """
    Extrait les images d'une archive dans `dossier` -> (chemins, erreur).
    """
    out = []
    try:
        with zipfile.ZipFile(chemin) as zf:
            membres = sorted((i for i in zf.infolist()
                              if not i.is_dir()
                              and not i.filename.startswith("__MACOSX/")
                              and not os.path.basename(i.filename).startswith(".")
                              and os.path.splitext(i.filename)[1].lower() in ZIP_EXTS
                              and i.file_size <= ZIP_IMAGE_OCTETS_MAX),
                             key=lambda i: i.filename.lower())
            for n, info in enumerate(membres[:ZIP_IMAGES_MAX]):
                # Le chemin est choisi ici, jamais repris de l'archive : rien
                # ne peut en sortir ("../../x.png"). Un sous-dossier par image
                # garde son nom d'origine, meme si deux portent le meme.
                sous = os.path.join(dossier, str(n))
                os.makedirs(sous, exist_ok=True)
                cible = os.path.join(sous, os.path.basename(info.filename))
                with zf.open(info) as src, open(cible, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                out.append(cible)
    except RuntimeError:     # archive chiffree
        return [], "Fichier zip protégé par un mot de passe."
    except (zipfile.BadZipFile, OSError, ValueError):
        return [], "Fichier zip illisible."
    if not out:
        return [], "Ce fichier zip ne contient aucune image (PNG ou JPG)."
    return out, ""


def read_screenshots(paths: list) -> dict:
    """
    Lit PLUSIEURS captures du meme instant (ecran principal + details).
    Un .zip compte pour les images qu'il contient.

    Les valeurs se completent d'une capture a l'autre, et chaque lecture
    compte comme une voix (_voter) : une valeur lue de deux facons a egalite,
    ou qui ne colle pas avec les autres mesures (_coherence), est rendue dans
    `doutes` et surlignee « a verifier » par l'interface.
    """
    global _serveur, _cause_ocr
    with _verrou_import:
        _cause_ocr = ""
        if sys.platform == "win32" and _serveur is None:
            try:
                _serveur = _ServeurOcr()
            except Exception as e:
                print(f"[sante] serveur OCR indisponible : {e}", flush=True)
                _serveur = None
        try:
            return _read_screenshots(paths)
        finally:
            if _serveur is not None:
                _serveur.fermer()
                _serveur = None


_verrou_import = threading.Lock()   # un import de captures a la fois


def _read_screenshots(paths: list) -> dict:
    tmpdir = tempfile.mkdtemp(prefix="pilote_zip_")
    try:
        images, erreurs_zip = [], []
        for k, p in enumerate(paths or []):
            if os.path.splitext(p)[1].lower() == ".zip":
                lues, err = _images_du_zip(p, os.path.join(tmpdir, str(k)))
                images += lues
                if err:
                    erreurs_zip.append({"file": os.path.basename(p), "ok": False,
                                        "found": 0, "error": err})
            else:
                images.append(p)
        if not images and erreurs_zip:
            return {"ok": False, "values": {}, "files": erreurs_zip,
                    "missing": [m["id"] for m in METRICS],
                    "error": erreurs_zip[0]["error"]}
        res = _read_images(images)
        res["files"] = erreurs_zip + res["files"]
        return res
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _read_images(paths: list) -> dict:
    lectures, date_, time_, date_cadran, details = {}, "", "", None, []
    for p in paths or []:
        if len(_confirmees(lectures)) >= len(METRICS) and (date_ or date_cadran):
            details.append({"file": os.path.basename(p), "ok": True,
                            "found": 0, "error": "", "skipped": True})
            continue
        r = read_screenshot(p, cumul=lectures)
        details.append({"file": os.path.basename(p), "ok": r.get("ok"),
                        "found": len(r.get("values") or {}),
                        "error": r.get("error", "")})
        if not r.get("ok"):
            continue
        for mid, vals in (r.get("lectures") or {}).items():
            lectures.setdefault(mid, []).extend(vals)
        # La date de l'ecran principal (celui du cadran) passe devant
        if r.get("date"):
            if r.get("cadran") and not date_cadran:
                date_cadran = (r["date"], r.get("time", ""))
            if not date_:
                date_, time_ = r["date"], r.get("time", "")
    if date_cadran:
        date_, time_ = date_cadran

    values, doutes, conflicts = _voter(lectures)
    incoherentes, repris = _coherence(values, lectures)
    doutes = (doutes - repris) | incoherentes
    manquants = [m["id"] for m in METRICS if m["id"] not in values]
    return {"ok": bool(values), "values": values, "date": date_, "time": time_,
            "missing": manquants, "conflicts": conflicts,
            "doutes": [m["id"] for m in METRICS if m["id"] in doutes],
            "files": details,
            "error": "" if values else "Aucune valeur reconnue sur ces captures."}


def _voter(lectures: dict):
    """
    Une valeur par mesure : la plus souvent lue (deux passes, deux captures),
    voir _choisir. A egalite entre deux valeurs, ou jamais lue avec son
    point, la mesure est « a verifier ». Retourne (valeurs, doutes, conflits).
    """
    values, doutes, conflicts = {}, set(), {}
    for mid, lus in lectures.items():
        if not lus:
            continue
        best, a_voir = _choisir(lus)
        values[mid] = best
        autres = sorted({v for v, _ in lus} - {best})
        if autres:
            conflicts[mid] = autres
        if a_voir:
            doutes.add(mid)
    return values, doutes, conflicts


# Relations entre les mesures de FitDays, verifiees sur les vraies pesees
# d'Arthur (sept. a oct. 2026, ecart maximal entre parentheses) ; la tolerance
# couvre les arrondis a une decimale de chaque mesure :
#   poids sans graisse = poids x (1 - graisse)            (0,04 kg)
#   taux musculaire    = masse musculaire / poids         (0,06 point)
#   poids sans graisse = masse musculaire + masse osseuse (0,1 kg)
#   graisse + eau + proteine + masse osseuse = 100 %      (0,06 point)
# et, plus lache, le metabolisme a 30 % pres de la formule de Katch-McArdle
# (370 + 21,6 x poids sans graisse) : un « 1 » perdu
# (« 850 » pour 1850 kcal) n'y tient pas.
# Un chiffre mal lu (7 pris pour 1) les fait mentir : les mesures en cause
# sont surlignees « a verifier ». Rien n'est corrige d'office.
_RELATIONS = [
    (("poids", "graisse", "poids_sans_graisse"), 0.2,
     lambda v: v["poids"] * (1 - v["graisse"] / 100) - v["poids_sans_graisse"]),
    (("poids", "masse_musculaire", "taux_musculaire"), 0.3,
     lambda v: v["masse_musculaire"] / v["poids"] * 100 - v["taux_musculaire"]),
    (("masse_musculaire", "masse_osseuse", "poids_sans_graisse"), 0.2,
     lambda v: v["masse_musculaire"] + v["masse_osseuse"] - v["poids_sans_graisse"]),
    (("poids", "graisse", "eau", "proteine", "masse_osseuse"), 0.3,
     lambda v: v["graisse"] + v["eau"] + v["proteine"] + v["masse_osseuse"] / v["poids"] * 100 - 100),
    (("poids_sans_graisse", "metabolisme"), 0.3,
     lambda v: v["metabolisme"] / (370 + 21.6 * v["poids_sans_graisse"]) - 1),
]


def _taille_habituelle() -> Optional[float]:
    """Taille (m) que FitDays utilise pour l'IMC, retrouvee sur les pesees
    deja enregistrees (racine de poids / IMC), ou None."""
    try:
        mes = [m for m in (load_data().get("mesures") or [])
               if m.get("poids") and m.get("imc")]
    except Exception:
        return None
    tailles = sorted((m["poids"] / m["imc"]) ** 0.5 for m in mes[-5:])
    return tailles[len(tailles) // 2] if tailles else None


def _coherence(values: dict, lectures: dict):
    """
    Mesures qui ne collent pas avec les autres (_RELATIONS, et l'IMC avec la
    taille des pesees precedentes). Quand une mesure a ete lue de deux facons,
    la lecture qui fait tenir les relations l'emporte (values est modifie).
    -> (doutes, repris) : `repris`, la mesure ainsi departagee, que les
    relations confirment (elle n'est plus « a verifier »).
    """
    relations = list(_RELATIONS)
    taille = _taille_habituelle()
    if taille:
        relations.append((("poids", "imc"), 0.2, lambda v: v["poids"] / taille ** 2 - v["imc"]))

    def fausses(v):
        out = []
        for ids, tol, f in relations:
            if all(v.get(i) for i in ids):
                try:
                    if abs(f(v)) > tol:
                        out.append(ids)
                except ZeroDivisionError:
                    out.append(ids)
        return out

    ko = fausses(values)
    change = None
    if ko:
        # Une autre lecture d'une mesure en cause remet-elle tout d'aplomb ?
        en_cause = {i for ids in ko for i in ids}
        meilleur = (len(ko), None, None)
        for mid in sorted(en_cause):
            for alt in sorted({v for v, _ in lectures.get(mid, [])} - {values.get(mid)}):
                n = len(fausses(dict(values, **{mid: alt})))
                if n < meilleur[0]:
                    meilleur = (n, mid, alt)
        if meilleur[1]:
            change = meilleur[1]
            values[change] = meilleur[2]
            ko = fausses(values)
    tenues = {i for ids, tol, f in relations if all(values.get(x) for x in ids)
              and ids not in ko for i in ids}
    en_cause = {i for ids in ko for i in ids}
    repris = {change} if change and change in tenues and change not in en_cause else set()
    return en_cause - tenues, repris


# ─── Objectifs ────────────────────────────────────────────────────────────────
