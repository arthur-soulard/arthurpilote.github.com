"""
balances.py — Lecture des exports officiels des balances connectees (Sante).

Aucune marque ne publie le format exact de son export (recherche du
09/11/2026, docs/modules/sante.md, « Exports des balances ») : on ne suppose
donc pas une disposition par marque, on reconnait chaque COLONNE par son nom
(francais ou anglais, avec ou sans unite) et on convertit ce qu'il faut :

  * Withings (Health Mate, « Exporter toutes mes donnees ») : un zip dont
    weight.csv donne poids, masse grasse, masse musculaire, masse osseuse et
    hydratation EN KG (ou en livres, selon le compte) ;
  * Zepp Life / Mi Fit (Xiaomi) : BODY_*.csv, en-tete
    timestamp,weight,height,bmi,fatRate,bodyWaterRate,boneMass,metabolism,
    muscleRate,visceralFat,impedance (timestamp en secondes) ;
  * Eufy (EufyLife, « Export All Data ») : Time,WEIGHT (kg),BMI,BODY FAT %…
    date et heure dans une seule colonne ;
  * Renpho, Fitdays, Arboleaf, Beurer… : un CSV par mail, colonnes nommees
    de la meme facon ;
  * Apple Sante (« Exporter toutes les donnees de sante ») : export.zip /
    export.xml, ou toute balance ecrit poids, graisse, IMC et masse maigre.

Rien n'est enregistre ici : la page montre l'apercu et l'utilisateur valide
(meme regle que la lecture des captures : une donnee de sante fausse est pire
qu'une donnee absente).
"""
from __future__ import annotations

import csv
import datetime
import io
import re
import unicodedata
import zipfile
from typing import Optional

import sante

LB = 0.45359237
MAX_FICHIER = 300 * 1024 * 1024     # export.xml d'Apple Sante : souvent > 100 Mo


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return re.sub(r"\s+", " ", s).strip()


# ─── Colonnes reconnues ──────────────────────────────────────────────────────
# (cle, sorte, mots) : la colonne dont le nom, sans son unite, vaut un de ces
# mots (ou les contient tous, pour les noms composes). « sorte » : comment la
# valeur s'interprete (« masse » : en kg ou en livres ; « pct » : en % ou en
# fraction de 1 ; « nombre » : tel quel).
# Les plus precis d'abord : « fat mass » avant « fat », « lean body mass »
# avant « mass »...

_COLONNES = [
    ("date",                "date",   ["date", "datetime", "date time", "date et heure", "timestamp",
                                       "measurement time", "measure time", "heure de mesure", "datum",
                                       "time of measurement", "date/time", "fecha", "data"]),
    ("heure",               "heure",  ["heure", "time", "hour", "uhrzeit"]),
    ("poids_sans_graisse",  "masse",  ["lean body mass", "fat free mass", "fat-free mass", "lbm", "lean mass",
                                       "poids sans graisse", "masse maigre", "masse non grasse", "ffm"]),
    ("graisse_kg",          "masse",  ["fat mass", "masse grasse", "fat mass weight", "body fat mass", "fett masse"]),
    ("graisse_sous_cutanee", "pct",   ["subcutaneous fat", "graisse sous cutanee", "graisse sous-cutanee",
                                       "subcutaneous fat rate"]),
    ("graisse_viscerale",   "nombre", ["visceral fat", "visceralfat", "graisse viscerale", "visceral fat level",
                                       "viszeralfett"]),
    ("graisse",             "pct",    ["fat", "body fat", "fatrate", "fat rate", "body fat rate", "fat %",
                                       "body fat %", "body fat percentage", "graisse", "graisse corporelle",
                                       "masse grasse %", "taux de graisse", "bodyfat", "fat percentage",
                                       "korperfett", "grasa corporal"]),
    ("muscle_squelettique", "pct",    ["skeletal muscle", "skeletal muscle rate", "muscle squelettique",
                                       "skeletal muscle %"]),
    # Pas « musclerate » : chez Zepp Life / Mi Fit, malgre son nom, rien ne dit
    # si c'est un taux ou des kg (les deux tiennent dans les bornes). Laisse de
    # cote plutot que d'inscrire une valeur peut-etre fausse.
    ("taux_musculaire",     "pct",    ["muscle rate", "muscle %", "taux musculaire",
                                       "muscle percentage"]),
    ("masse_musculaire",    "masse",  ["muscle mass", "masse musculaire", "muscle", "musclemass", "muskelmasse"]),
    ("masse_osseuse",       "masse",  ["bone mass", "bonemass", "masse osseuse", "bone", "knochenmasse"]),
    ("eau_kg",              "masse",  ["hydration"]),                       # Withings : en kg
    ("eau",                 "pct",    ["water", "body water", "bodywaterrate", "body water rate", "water %",
                                       "eau", "eau corporelle", "hydratation", "water rate", "korperwasser"]),
    ("proteine",            "pct",    ["protein", "proteine", "protein rate", "protein %", "proteinrate"]),
    ("metabolisme",         "nombre", ["bmr", "metabolism", "basal metabolic rate", "basal metabolism",
                                       "metabolisme", "metabolisme de base", "metabolisme basal", "grundumsatz"]),
    ("age_corporel",        "nombre", ["body age", "metabolic age", "age corporel", "bodyage", "age metabolique"]),
    ("imc",                 "nombre", ["bmi", "imc"]),
    ("poids",               "masse",  ["weight", "poids", "body weight", "gewicht", "peso", "masse corporelle"]),
]

_UNITE = re.compile(r"[\(\[]\s*([^\)\]]*)\s*[\)\]]")


# Meme grandeur, autre unite : « Masse grasse (%) » est un taux, « Body Water (kg) » une masse
_EN_PCT = {"graisse_kg": "graisse", "eau_kg": "eau", "masse_musculaire": "taux_musculaire"}
_EN_KG = {"graisse": "graisse_kg", "eau": "eau_kg"}
_SORTE = {cle: sorte for cle, sorte, _ in _COLONNES}


def _colonne(nom: str):
    """(cle, sorte, unite) d'une colonne, ou None. L'unite vient du nom :
    « Weight (kg) », « Poids [lb] », « BODY FAT % », « weight_lbs »."""
    brut = _norm(nom)
    m = _UNITE.search(brut)
    unite = m.group(1).strip() if m else ""
    base = _UNITE.sub(" ", brut).replace("_", " ").replace("-", " ")
    m = re.search(r"\s*(lbs|lb|kg|%|kcal)\s*$", base)
    if m:
        unite = unite or m.group(1)
        base = base[:m.start()]
    base = re.sub(r"\s+", " ", base).strip(" :.")
    if unite in ("lbs", "livres", "pounds"):
        unite = "lb"
    trouve = None
    for cle, sorte, mots in _COLONNES:
        if base in mots:
            trouve = cle
            break
    if trouve is None:
        # Nom compose (« Body Fat Percentage ») : tous les mots d'un synonyme
        mots_base = set(base.split())
        trouve = next((cle for cle, _, mots in _COLONNES
                       for syn in mots if len(syn.split()) > 1 and set(syn.split()) <= mots_base), None)
    if trouve is None:
        return None
    if unite == "%" and trouve in _EN_PCT:
        trouve = _EN_PCT[trouve]
    elif unite in ("kg", "lb") and trouve in _EN_KG:
        trouve = _EN_KG[trouve]
    return trouve, _SORTE[trouve], unite


# ─── Valeurs ─────────────────────────────────────────────────────────────────

def _nombre(texte) -> Optional[float]:
    if texte is None:
        return None
    t = str(texte).strip().replace(" ", "").replace(" ", "")
    if not t or t in ("-", "--", "null", "none", "nan"):
        return None
    t = re.sub(r"(kg|lbs?|%|kcal)$", "", t, flags=re.I)
    if re.fullmatch(r"-?\d+,\d+", t):
        t = t.replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


_FORMATS_DATE = [
    "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M",
    "%Y-%m-%d", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M", "%Y/%m/%d", "%Y.%m.%d %H:%M", "%Y.%m.%d",
    "%b %d, %Y %I:%M:%S %p", "%b %d, %Y %I:%M %p", "%b %d, %Y", "%d %b %Y %H:%M", "%d %b %Y",
    "%B %d, %Y %I:%M %p", "%B %d, %Y",
]


def _date_iso(texte: str, ordre: str):
    """(date ISO, heure HH:MM) ou None. ordre : « jm » (31/12) ou « mj »
    (12/31) pour les dates a barres, decide pour tout le fichier."""
    t = str(texte or "").strip()
    if not t:
        return None
    if re.fullmatch(r"\d{10}(\d{3})?(\.\d+)?", t):       # secondes (ou ms) depuis 1970
        s = float(t)
        if s > 1e11:
            s /= 1000
        d = datetime.datetime.fromtimestamp(s)
        return d.date().isoformat(), d.strftime("%H:%M")
    t = re.sub(r"(Z|[+-]\d{2}:?\d{2})$", "", t).strip()     # fuseau : l'heure locale ecrite
    t = re.sub(r"\.\d+$", "", t)
    m = re.match(r"^(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{2,4})(?:[ T,]+(\d{1,2}):(\d{2})(?::\d{2})?\s*([ap]\.?m\.?)?)?$", t, re.I)
    if m:
        a, b, an = int(m.group(1)), int(m.group(2)), int(m.group(3))
        an += 2000 if an < 100 else 0
        j, mo = (a, b) if ordre == "jm" else (b, a)
        try:
            d = datetime.date(an, mo, j)
        except ValueError:
            return None
        heure = ""
        if m.group(4):
            h = int(m.group(4))
            ap = (m.group(6) or "").lower().replace(".", "")
            if ap == "pm" and h < 12:
                h += 12
            if ap == "am" and h == 12:
                h = 0
            heure = "%02d:%s" % (h, m.group(5))
        return d.isoformat(), heure
    for f in _FORMATS_DATE:
        try:
            d = datetime.datetime.strptime(t, f)
        except ValueError:
            continue
        return d.date().isoformat(), (d.strftime("%H:%M") if ("%H" in f or "%I" in f) else "")
    return None


def _ordre_dates(textes) -> tuple:
    """Jour/mois ou mois/jour pour les dates « a/b/aaaa » d'un fichier.
    Rend (ordre, ambigu) : ambigu si aucune date ne permet de trancher
    (jour/mois retenu, l'usage francais, et la page le signale)."""
    textes = list(textes)
    jm = mj = False
    for t in textes:
        m = re.match(r"^\s*(\d{1,2})[/.\-](\d{1,2})[/.\-]\d{2,4}", str(t or ""))
        if not m:
            continue
        a, b = int(m.group(1)), int(m.group(2))
        if a > 12:
            jm = True
        if b > 12:
            mj = True
    if mj and not jm:
        return "mj", False
    vu = any(re.match(r"^\s*\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4}", str(t or "")) for t in textes)
    return "jm", (vu and not jm)


# ─── Lecture d'un tableau ────────────────────────────────────────────────────

def _decoder(octets: bytes) -> str:
    if octets.startswith((b"\xff\xfe", b"\xfe\xff")):
        return octets.decode("utf-16")
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return octets.decode(enc)
        except UnicodeDecodeError:
            continue
    return octets.decode("latin-1")


def _lignes_csv(texte: str) -> list:
    lignes = [l for l in texte.splitlines() if l.strip()]
    # L'en-tete n'est pas toujours la premiere ligne (« Body » pour Garmin,
    # un titre) : la premiere des 10 premieres ou un poids est reconnu
    debut = 0
    for i, l in enumerate(lignes[:10]):
        try:
            sep = csv.Sniffer().sniff(l, delimiters=",;\t").delimiter
        except csv.Error:
            sep = ","
        cols = next(csv.reader([l], delimiter=sep))
        if any((_colonne(c) or ("",))[0] == "poids" for c in cols):
            debut = i
            break
    corps = "\n".join(lignes[debut:])
    try:
        sep = csv.Sniffer().sniff(lignes[debut] if lignes else "", delimiters=",;\t").delimiter
    except csv.Error:
        sep = ","
    return list(csv.reader(io.StringIO(corps), delimiter=sep))


def lire_tableau(lignes: list, ordre: str = None) -> dict:
    """Lignes d'un tableau (en-tete d'abord) -> pesees. Le coeur commun a tous
    les CSV."""
    if not lignes:
        return {"mesures": [], "colonnes": {}, "ignorees": 0, "erreur": "Fichier vide."}
    entete = lignes[0]
    cols = {}
    for i, nom in enumerate(entete):
        c = _colonne(nom)
        if c and c[0] not in [v[0] for v in cols.values()]:
            cols[i] = c
    cles = {v[0] for v in cols.values()}
    if "poids" not in cles:
        return {"mesures": [], "colonnes": {}, "ignorees": 0,
                "erreur": "Aucune colonne de poids reconnue dans ce fichier."}
    if "date" not in cles:
        # Eufy : « Time » porte date et heure
        for i, c in cols.items():
            if c[0] == "heure":
                cols[i] = ("date", "date", "")
                break
        else:
            return {"mesures": [], "colonnes": {}, "ignorees": 0,
                    "erreur": "Aucune colonne de date reconnue dans ce fichier."}
    i_date = next(i for i, c in cols.items() if c[0] == "date")
    i_heure = next((i for i, c in cols.items() if c[0] == "heure"), None)
    devine, ambigu = _ordre_dates(l[i_date] for l in lignes[1:] if len(l) > i_date)
    ordre = ordre if ordre in ("jm", "mj") else devine
    # Unites : celle du nom de colonne ; sinon les poids en livres se voient
    # (aucun adulte a plus de 300 kg, des poids > 140 « kg » partout : des livres)
    unite_poids = cols[next(i for i, c in cols.items() if c[0] == "poids")][2]

    mesures, ignorees = [], 0
    for l in lignes[1:]:
        if len(l) <= i_date:
            continue
        d = _date_iso(l[i_date], ordre)
        if not d:
            ignorees += 1
            continue
        date, heure = d
        if i_heure is not None and len(l) > i_heure and not heure:
            h = re.match(r"^\s*(\d{1,2}):(\d{2})", l[i_heure] or "")
            if h:
                heure = "%02d:%s" % (int(h.group(1)), h.group(2))
        brut = {}
        for i, (cle, sorte, unite) in cols.items():
            if cle in ("date", "heure") or i >= len(l):
                continue
            v = _nombre(l[i])
            if v is None:
                continue
            texte = str(l[i]).lower()
            if sorte == "masse" and (unite == "lb" or "lb" in texte):
                v *= LB
            elif sorte == "masse" and not unite and cle == "poids" and unite_poids == "" and v > 300:
                v *= LB
            brut[cle] = (v, sorte, unite)
        m = _vers_mesure(brut)
        if m is None:
            ignorees += 1
            continue
        m["date"], m["time"] = date, heure
        mesures.append(m)
    noms = {entete[i]: c[0] for i, c in cols.items()}
    return {"mesures": mesures, "colonnes": noms, "ignorees": ignorees,
            "dateAmbigue": ambigu}


def _vers_mesure(brut: dict) -> Optional[dict]:
    """Valeurs lues -> mesure de Sante (les 14 metriques), bornes verifiees.
    Une valeur hors bornes est laissee de cote (jamais corrigee)."""
    if "poids" not in brut:
        return None
    poids = brut["poids"][0]
    m = {}

    def poser(mid, v):
        info = sante.metric(mid)
        lo, hi = info.get("range", [None, None])
        if v is None or (lo is not None and not (lo <= v <= hi)):
            return
        m[mid] = round(v, info.get("decimals", 1))

    poser("poids", poids)
    if "poids" not in m:
        return None
    for cle, (v, sorte, unite) in brut.items():
        if cle == "poids":
            continue
        if sorte == "pct" and unite != "%" and 0 < v <= 1:
            v *= 100                       # fraction de 1 (Apple Sante, certains exports)
        if cle == "graisse_kg" and "graisse" not in brut:
            poser("graisse", v / poids * 100)
        elif cle == "eau_kg" and "eau" not in brut:
            poser("eau", v / poids * 100)
        elif cle in sante.METRIC_IDS:
            poser(cle, v)
    return m


# ─── Apple Sante (export.xml) ────────────────────────────────────────────────

_APPLE = {
    "HKQuantityTypeIdentifierBodyMass": "poids",
    "HKQuantityTypeIdentifierBodyFatPercentage": "graisse",
    "HKQuantityTypeIdentifierBodyMassIndex": "imc",
    "HKQuantityTypeIdentifierLeanBodyMass": "poids_sans_graisse",
}


def lire_apple(flux) -> dict:
    """export.xml d'Apple Sante, lu au fil de l'eau (souvent > 100 Mo). Les
    mesures d'une meme minute forment une pesee (la balance ecrit poids,
    graisse, IMC... au meme instant)."""
    import xml.etree.ElementTree as ET
    par_instant = {}
    sources = set()
    for _, el in ET.iterparse(flux, events=("end",)):
        if el.tag != "Record":
            if el.tag not in ("HealthData", "ExportDate", "Me"):
                el.clear()
            continue
        mid = _APPLE.get(el.get("type"))
        if mid:
            debut = (el.get("startDate") or "")[:16]       # « 2026-11-09 08:12 »
            v = _nombre(el.get("value"))
            if debut and v is not None:
                unite = (el.get("unit") or "").lower()
                if mid in ("poids", "poids_sans_graisse") and unite in ("lb", "lbs"):
                    v *= LB
                elif mid in ("poids", "poids_sans_graisse") and unite == "g":
                    v /= 1000
                par_instant.setdefault(debut, {})[mid] = (v, "pct" if mid == "graisse" else "masse",
                                                         "" if mid == "graisse" else "kg")
                sources.add(el.get("sourceName") or "")
        el.clear()
    mesures = []
    for instant, brut in sorted(par_instant.items()):
        m = _vers_mesure(brut)
        if m:
            m["date"], m["time"] = instant[:10], instant[11:16]
            mesures.append(m)
    return {"mesures": mesures, "colonnes": {"Apple Santé": "poids, graisse, IMC, masse maigre"},
            "ignorees": 0, "dateAmbigue": False, "sources": sorted(s for s in sources if s)}


# ─── Point d'entree ──────────────────────────────────────────────────────────

def _marque(nom_fichier: str, colonnes: dict) -> str:
    n = _norm(nom_fichier)
    c = " ".join(_norm(k) for k in colonnes)
    if "fatrate" in c or "bodywaterrate" in c or n.startswith("body_") or "mifit" in n or "zepp" in n:
        return "Zepp Life / Mi Fit"
    if "hydration" in c or n.endswith("weight.csv") and "fat mass" in c:
        return "Withings"
    if "eufy" in n:
        return "Eufy"
    if "renpho" in n:
        return "Renpho"
    if "fitdays" in n:
        return "FitDays"
    return ""


def _choisir_dans_zip(z: zipfile.ZipFile) -> Optional[str]:
    noms = [n for n in z.namelist() if not n.endswith("/") and "__MACOSX" not in n
            and not n.split("/")[-1].startswith("._")]
    for n in noms:
        if n.lower().endswith("export.xml") and "cda" not in n.lower():
            return n
    for n in noms:
        if n.lower().split("/")[-1] == "weight.csv":
            return n
    for n in noms:
        if re.match(r"body.*\.csv$", n.lower().split("/")[-1]):
            return n
    # Sinon le premier CSV ou un poids est reconnu
    for n in noms:
        if n.lower().endswith(".csv") and z.getinfo(n).file_size < 50 * 1024 * 1024:
            try:
                tete = _decoder(z.read(n)[:4096])
            except Exception:
                continue
            if lire_tableau(_lignes_csv(tete)[:2]).get("colonnes"):
                return n
    return None


def lire_export(chemin: str, ordre: str = None) -> dict:
    """Un export (CSV, zip ou export.xml) -> apercu des pesees, sans rien
    enregistrer. {ok, marque, fichier, mesures, colonnes, ignorees,
    dateAmbigue, debut, fin} ou {ok: False, error}. ordre : « jm » ou « mj »
    pour forcer la lecture des dates a barres (choix de la page)."""
    import os
    nom = os.path.basename(chemin)
    try:
        if os.path.getsize(chemin) > MAX_FICHIER:
            return {"ok": False, "error": "Fichier trop gros (plus de 300 Mo)."}
        bas = nom.lower()
        if bas.endswith(".zip"):
            with zipfile.ZipFile(chemin) as z:
                membre = _choisir_dans_zip(z)
                if not membre:
                    return {"ok": False, "error": "Aucune pesée trouvée dans ce zip."}
                if z.getinfo(membre).file_size > MAX_FICHIER:
                    return {"ok": False, "error": "Fichier trop gros dans le zip."}
                if membre.lower().endswith(".xml"):
                    with z.open(membre) as f:
                        res = lire_apple(f)
                    res["marque"] = "Apple Santé"
                else:
                    res = lire_tableau(_lignes_csv(_decoder(z.read(membre))), ordre)
                    res["marque"] = _marque(membre, res.get("colonnes") or {})
                res["fichier"] = nom + " › " + membre.split("/")[-1]
        elif bas.endswith(".xml"):
            with open(chemin, "rb") as f:
                res = lire_apple(f)
            res["marque"], res["fichier"] = "Apple Santé", nom
        else:
            with open(chemin, "rb") as f:
                res = lire_tableau(_lignes_csv(_decoder(f.read())), ordre)
            res["marque"], res["fichier"] = _marque(nom, res.get("colonnes") or {}), nom
    except zipfile.BadZipFile:
        return {"ok": False, "error": "Zip illisible."}
    except Exception as e:
        return {"ok": False, "error": "Fichier illisible : %s" % e}
    if res.get("erreur"):
        return {"ok": False, "error": res["erreur"]}
    mesures = _une_par_jour(res["mesures"])
    if not mesures:
        return {"ok": False, "error": "Aucune pesée lisible dans ce fichier."}
    res["mesures"] = mesures
    res["debut"], res["fin"] = mesures[0]["date"], mesures[-1]["date"]
    res["ok"] = True
    return res


def _une_par_jour(mesures: list) -> list:
    """Une pesee par jour, comme dans Sante : la plus complete, et a egalite
    la plus matinale (la pesee de reference se fait le matin)."""
    par_jour = {}
    for m in mesures:
        d = m["date"]
        cle = (-len(m), m.get("time") or "99:99")
        if d not in par_jour or cle < par_jour[d][0]:
            par_jour[d] = (cle, m)
    return [par_jour[d][1] for d in sorted(par_jour)]
