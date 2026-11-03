"""
garmin.py — Module « Garmin » : les donnees de la montre, lues dans le compte
Garmin Connect de l'utilisateur par la cle API personnelle (Personal API,
ouverte par Garmin en octobre 2026 : docs/modules/garmin.md).

Comme pour Actus et Agenda, la cle entre une fois (save_garmin), Python la
verifie aupres de Garmin AVANT de l'enregistrer, puis la chiffre (DPAPI sous
Windows, Trousseau sur Mac : actus._chiffrer). Aucune methode ne la renvoie.

Pilote ne fait que LIRE : l'API personnelle n'a que des GET. Trois choses
sont lues, chacune a cocher :
  * seances : les activites, rendues pretes a entrer dans Sports ;
  * pesees  : les pesees (balance Index ou saisie dans Connect), pour Santé ;
  * forme   : un resume par jour (pas, FC au repos, sommeil, Body Battery,
              stress, VFC, SpO2, respiration, minutes intenses) et l'age
              physique, gardes ici, pour l'onglet « Ma forme » et les tuiles ;
  * cycle   : le cycle menstruel du jour (decoche par defaut : Garmin n'en a
              que si l'utilisateur le suit dans Connect).

Les seances et les pesees ne sont PAS ecrites ici dans sports.json ni
sante.json : la page tient SP et SA en memoire et les reecrit en entier ; une
ecriture de Python par-dessous serait effacee au prochain enregistrement. La
page les ajoute elle-meme, puis signale ce qu'elle a pris (save_garmin_vus) :
une seance supprimee dans Pilote ne revient pas a la synchronisation suivante.

Emplacement : <app_dir>/users/<slug>/garmin.json
Backup quotidien : <app_dir>/users/<slug>/backups_garmin/garmin_YYYY-MM-DD.json
"""
from __future__ import annotations

import base64
import datetime
import json
import re
import socket
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

import actus
import jsonstore
import sante
import sports

BASE  = "https://personal.connectapi.garmin.com"   # remplace par les tests
JETON = "/personalapitoken-service/personal-api/personal-api-key/token"
DELAI = 30
TROUSSEAU = "Pilote Garmin"
CHOIX = ("seances", "pesees", "forme", "cycle")
CHOIX_DEFAUT = {"seances": True, "pesees": True, "forme": True, "cycle": False}
DUREES_CLE = (30, 90, 180, 365)   # durees proposees par Garmin a la creation de la cle
JOURS_GARDES = 400        # resumes de forme gardes (un peu plus d'un an)
PREMIERS_JOURS = 30       # seances et pesees : « depuis » par defaut
RECOUVREMENT = 7          # jours relus a chaque synchronisation (une seance synchronisee en retard)
PAGES_MAX = 10            # 10 x 99 activites au plus par synchronisation
JOURS_AN = 365            # forme lue a la premiere synchronisation (courbe sur un an)
HISTOIRE_DEBUT = "2000-01-01"   # records : tout l'historique, lu une fois
PAGES_HISTOIRE = 30       # 30 x 99 activites au plus pour cette lecture
# Records de course : distances dont Garmin donne le meilleur temps (fastestSplit_<m>)
DISTANCES_RECORD = (1000, 5000, 10000, 21098, 42195)


class ErreurGarmin(Exception):
    """code : saisie, auth, reseau, limite, api, config."""

    def __init__(self, code: str, message: str, statut: int = 0):
        super().__init__(message)
        self.code, self.message, self.statut = code, message, statut


def default_data() -> dict:
    return {
        "_meta": {
            "version": 1,
            "schema": "garmin.v1",
            "createdAt":   datetime.date.today().isoformat(),
            "lastSavedAt": datetime.datetime.now().isoformat(timespec="seconds"),
        },
        "secret":   "",
        "connecteLe": "",
        "depuis":   "",          # premiere date importee (seances, pesees)
        "choix":    dict(CHOIX_DEFAUT),
        "expire":   "",          # fin de validite de la cle (AAAA-MM-JJ), donnee a la connexion
        "derniere": "",          # derniere synchronisation reussie (AAAA-MM-JJTHH:MM:SS)
        "vus":      [],          # activites et pesees deja proposees a la page
        "jours":    {},          # "AAAA-MM-JJ" -> resume de forme
        "ageForme": None,        # age physique (fitness age) le plus recent
        "cycle":    None,        # cycle menstruel du jour de la derniere synchronisation
        "records":  {},          # "5000" -> meilleur temps de course {s, date, nom, garminId}
        "historique": False,     # tout l'historique des activites lu pour les records
        "formeAn":  False,       # la forme de l'annee passee lue une fois
    }


_store = jsonstore.JsonStore(
    filename="garmin.json",
    backup_dirname="backups_garmin",
    schema="garmin.v1",
    default_factory=default_data,
)

_verrou = threading.RLock()
_jeton  = {"cle": "", "valeur": "", "fin": 0.0}   # jeton du jour, en memoire seulement


def load_data() -> dict:
    return _store.load()


def _modifier(changer) -> dict:
    with _verrou:
        data = _store.load()
        changer(data)
        _store.save(data)
        return data


def _jour(s, defaut: datetime.date) -> datetime.date:
    try:
        return datetime.date.fromisoformat(str(s)[:10])
    except (TypeError, ValueError):
        return defaut


# ─── HTTP ────────────────────────────────────────────────────────────────────

_ctx = ssl.create_default_context()


def _ouvrir(req: urllib.request.Request) -> tuple:
    """(statut, corps). Les erreurs reseau deviennent ErreurGarmin."""
    try:
        with urllib.request.urlopen(req, timeout=DELAI, context=_ctx) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except (urllib.error.URLError, socket.timeout, ssl.SSLError, OSError) as e:
        raise ErreurGarmin("reseau", "Garmin ne répond pas. Vérifie ta connexion "
                                     "internet, puis réessaie.") from e


def _fin_jwt(jeton: str) -> float:
    """Le champ exp du JWT (sans verifier sa signature : seul Garmin la lit)."""
    try:
        morceau = jeton.split(".")[1]
        return float(json.loads(base64.urlsafe_b64decode(morceau + "=" * (-len(morceau) % 4)))["exp"])
    except (IndexError, KeyError, TypeError, ValueError):
        return time.time() + 3600      # forme inattendue : redemande dans une heure


def _obtenir_jeton(cle: str) -> str:
    """La cle s'echange contre un jeton valable 24 h, sans jeton de
    renouvellement : on en redemande un (FAQ de Garmin)."""
    if _jeton["cle"] == cle and _jeton["fin"] - time.time() > 600:
        return _jeton["valeur"]
    req = urllib.request.Request(BASE + JETON, data=b"", method="POST")
    req.add_header("Authorization", "ApiKey " + cle)
    req.add_header("Accept", "*/*")
    req.add_header("User-Agent", "Pilote")
    statut, corps = _ouvrir(req)
    if statut in (400, 401, 403):
        raise ErreurGarmin("auth", "Garmin refuse cette clé : elle est expirée, supprimée ou mal "
                                   "copiée. Crée-en une nouvelle sur Garmin Connect, puis colle-la.")
    if statut == 429:
        raise ErreurGarmin("limite", "Garmin reçoit trop de demandes : réessaie dans quelques minutes.")
    if statut != 200:
        raise ErreurGarmin("api", f"Garmin a répondu {statut} à la demande de jeton.")
    valeur = corps.decode("utf-8", "replace").strip()
    if not valeur or len(valeur) > 20000 or any(c.isspace() for c in valeur):
        raise ErreurGarmin("api", "Garmin a renvoyé un jeton illisible.")
    _jeton.update(cle=cle, valeur=valeur, fin=_fin_jwt(valeur))
    return valeur


def _get(jeton: str, chemin: str, params: dict = None):
    """JSON decode, ou None quand Garmin n'a rien pour ces dates (204)."""
    url = BASE + chemin + ("?" + urllib.parse.urlencode(params) if params else "")
    req = urllib.request.Request(url, method="GET")
    req.add_header("Authorization", "Bearer " + jeton)
    req.add_header("Accept", "application/json")
    req.add_header("User-Agent", "Pilote")
    statut, corps = _ouvrir(req)
    if statut in (401, 403):
        _jeton.update(cle="", valeur="", fin=0.0)
        raise ErreurGarmin("auth", "Garmin refuse la clé : elle a sans doute expiré. "
                                   "Crée-en une nouvelle sur Garmin Connect, puis colle-la.")
    if statut == 429:
        raise ErreurGarmin("limite", "Garmin reçoit trop de demandes : réessaie dans quelques minutes.")
    if statut == 204 or (statut == 200 and not corps.strip()):
        return None
    if statut != 200:
        raise ErreurGarmin("api", f"Garmin a répondu {statut} ({chemin.split('/')[1]}).", statut)
    try:
        return json.loads(corps.decode("utf-8"))
    except ValueError as e:
        raise ErreurGarmin("api", "Garmin a renvoyé une réponse illisible.") from e


def _cle(data: dict) -> str:
    secret = data.get("secret") or ""
    if not secret:
        raise ErreurGarmin("config", "Aucun compte Garmin n'est connecté.")
    try:
        return actus._dechiffrer(secret, TROUSSEAU)
    except Exception:
        raise ErreurGarmin("config", "La clé enregistrée ne se relit pas ici (fichier venu d'un "
                                     "autre PC ?). Colle-la de nouveau dans Garmin › Connexion.")


# ─── Seances -> Sports ───────────────────────────────────────────────────────

# typeKey de Garmin (running, trail_running, road_biking, lap_swimming...) :
# reconnu par morceau, le plus specifique d'abord. Le reste va dans « Autre ».
_SPORTS_GARMIN = [
    ("swim", "natation"),
    ("run", "course"),
    ("cycl", "velo"), ("bik", "velo"), ("ride", "velo"),
    ("strength", "muscu"),
    ("hik", "rando"), ("mountaineering", "rando"),
    ("soccer", "foot"), ("football", "foot"),
]


def sport_pilote(type_garmin: str) -> str:
    t = (type_garmin or "").lower()
    for morceau, sport in _SPORTS_GARMIN:
        if morceau in t:
            return sport
    return "autre"


def _champs(sport: str) -> list:
    for s in sports.SPORTS:
        if s["id"] == sport:
            return s["fields"]
    return ["duration"]


def _nombre(x) -> float:
    try:
        n = float(x)
        return n if n == n and abs(n) != float("inf") else 0.0
    except (TypeError, ValueError):
        return 0.0


def seance(a: dict) -> dict:
    """Une activite Garmin (SummarizedActivityDTO) en seance de Sports. None
    si elle n'a ni identifiant ni date lisible."""
    ident = a.get("activityId")
    debut = str(a.get("startTimeLocal") or "")
    m = re.match(r"(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2})", debut)
    if not ident or not m:
        return None
    type_ = (a.get("activityType") or {}).get("typeKey") or ""
    sport = sport_pilote(type_)
    champs = _champs(sport)
    secondes = _nombre(a.get("duration")) or _nombre(a.get("movingDuration"))
    metres = _nombre(a.get("distance"))
    s = {
        "garminId":  str(ident),
        "date":      m.group(1),
        "time":      m.group(2),
        "sport":     sport,
        "duration":  round(secondes / 60),
        "distance":  0,
        "elevation": round(_nombre(a.get("elevationGain"))) if "elevation" in champs else 0,
        "note":      str(a.get("activityName") or "")[:200],
        "garminType": type_,
    }
    if "distance_m" in champs:
        s["distance"] = round(metres)
    elif "distance_km" in champs:
        s["distance"] = round(metres / 1000, 2)
    if "lieu" in champs:
        bassin = round(_nombre(a.get("poolLength")))
        s["lieu"] = str(bassin) if bassin in (25, 50) else "libre"
    fc = round(_nombre(a.get("averageHR")))
    if fc:
        s["fcMoy"] = fc
    kcal = round(_nombre(a.get("calories")))
    if kcal:
        s["kcal"] = kcal
    if a.get("isPR") is True:     # record personnel d'apres Garmin
        s["record"] = True
    # Effet d'entrainement de Garmin (0 a 5) et son libelle (TEMPO, VO2MAX...)
    for cle, nom in (("aerobicTrainingEffect", "effetAero"), ("anaerobicTrainingEffect", "effetAnaero")):
        v = round(_nombre(a.get(cle)), 1)
        if 0 < v <= 5:
            s[nom] = v
    label = a.get("trainingEffectLabel")
    if isinstance(label, str) and re.match(r"[A-Z0-9_]{2,40}$", label):
        s["effetType"] = label
    return s


def records(activites: list, avant: dict) -> dict:
    """Les meilleurs temps de course sur DISTANCES_RECORD : ceux d'`avant`,
    battus par une activite plus rapide."""
    out = {k: v for k, v in (avant or {}).items() if isinstance(v, dict)}
    for a in activites:
        if not isinstance(a, dict) or sport_pilote((a.get("activityType") or {}).get("typeKey") or "") != "course":
            continue
        s = seance(a)
        if not s:
            continue
        for d in DISTANCES_RECORD:
            sec = round(_nombre(a.get(f"fastestSplit_{d}")))
            # Moins de 2:30 au km : une erreur de GPS, pas un record
            if sec < d * 0.15 or (str(d) in out and out[str(d)].get("s", 0) <= sec):
                continue
            out[str(d)] = {"s": sec, "date": s["date"], "nom": s["note"], "garminId": s["garminId"]}
    return out


def _activites(jeton: str, debut: datetime.date, fin: datetime.date, pages: int = PAGES_MAX) -> list:
    tout = []
    for page in range(pages):
        lot = _get(jeton, "/activitylist-service/activities/search/activities",
                   {"start": page * 99, "limit": 99, "startDate": debut.isoformat(),
                    "endDate": fin.isoformat()}) or []
        if not isinstance(lot, list):
            break
        tout += lot
        if len(lot) < 99:
            break
    return tout


# ─── Pesees -> Santé ─────────────────────────────────────────────────────────

def _borne(mid: str, v):
    """La valeur arrondie comme Santé l'affiche, ou None hors des bornes."""
    for m in sante.METRICS:
        if m["id"] == mid:
            if v is None:
                return None
            v = round(_nombre(v), m.get("decimals", 1))
            lo, hi = m.get("range", [None, None])
            return v if v and (lo is None or lo <= v <= hi) else None
    return None


def pesee(p: dict) -> dict:
    """Une pesee Garmin (DateWeightDTO) en mesure de Santé, ou None."""
    jour = str(p.get("calendarDate") or p.get("date") or "")[:10]
    poids = _nombre(p.get("weight"))
    if poids > 1000:          # l'API historique de Connect donnait des grammes
        poids /= 1000
    poids = _borne("poids", poids)
    if not re.match(r"\d{4}-\d{2}-\d{2}$", jour) or poids is None:
        return None
    heure = ""
    m = re.search(r"T(\d{2}:\d{2})", str(p.get("date") or ""))
    if m:
        heure = m.group(1)
    ident = str(p.get("timestampGMT") or p.get("date") or jour) + "|" + str(poids)
    mesure = {"garminId": ident, "date": jour, "time": heure, "poids": poids}
    for cle, mid in (("bmi", "imc"), ("bodyFat", "graisse"), ("bodyWater", "eau")):
        v = _borne(mid, p.get(cle))
        if v is not None:
            mesure[mid] = v
    return mesure


# ─── Forme du jour ───────────────────────────────────────────────────────────

def _tranches(debut: datetime.date, fin: datetime.date, jours: int):
    while debut <= fin:
        bout = min(fin, debut + datetime.timedelta(days=jours - 1))
        yield debut, bout
        debut = bout + datetime.timedelta(days=1)


def _entier(x):
    n = _nombre(x)
    return round(n) if n else None


def _heure_locale(ms):
    """"HH:MM" d'un horodatage du sommeil, ou None. Garmin le donne en ms,
    deja decale a l'heure locale (un nombre, pas une chaine comme dans la spec :
    vu sur une vraie montre le 03/11/2026) : il se lit donc comme de l'UTC."""
    n = _nombre(ms)
    if n < 1e11:          # avant 1973 : pas un horodatage en ms
        return None
    try:
        return datetime.datetime.fromtimestamp(n / 1000, datetime.timezone.utc).strftime("%H:%M")
    except (OverflowError, OSError, ValueError):
        return None


def _forme(jeton: str, debut: datetime.date, fin: datetime.date, erreurs: list) -> dict:
    """{jour: {pas, objectifPas, fcRepos, bbMax, bbMin, bbFin, stress,
    intensite, sommeil, sommeilScore, profond, paradoxal, coucher, lever, vfc, vfcStatut}}.
    Une source qui echoue n'empeche pas les autres (erreurs)."""
    jours = {}

    def jour(d):
        return jours.setdefault(str(d)[:10], {})

    def garder(d: dict, cle: str, v):
        if v is not None:
            d[cle] = v

    try:   # resume du jour : jusqu'a un an par appel
        for a, b in _tranches(debut, fin, 365):
            r = _get(jeton, "/usersummary-service/v2/dailysummaries",
                     {"startDate": a.isoformat(), "endDate": b.isoformat()}) or {}
            for s in (r.get("data") or []) if isinstance(r, dict) else []:
                if not s.get("calendarDate"):
                    continue
                d = jour(s["calendarDate"])
                pas = ((s.get("movement") or {}).get("steps") or {})
                garder(d, "pas", _entier(pas.get("value")))
                garder(d, "objectifPas", _entier(pas.get("goal")))
                garder(d, "fcRepos", _entier((s.get("heartRate") or {}).get("restingValue")))
                bb = s.get("bodyBattery") or {}
                garder(d, "bbMax", _entier(bb.get("maxValue")))
                garder(d, "bbMin", _entier(bb.get("minValue")))
                garder(d, "bbFin", _entier(bb.get("latestValue")))
                garder(d, "stress", _entier((s.get("stress") or {}).get("avgLevel")))
                im = s.get("intensityMinutes") or {}
                if im.get("moderate") is not None or im.get("vigorous") is not None:
                    # Garmin compte une minute intense pour deux
                    d["intensite"] = round(_nombre(im.get("moderate")) + 2 * _nombre(im.get("vigorous")))
                garder(d, "objectifIntensite", _entier(im.get("goal")))   # objectif de la semaine
                garder(d, "spo2", _entier((s.get("pulseOx") or {}).get("avgValue")))
                garder(d, "respiration", _entier((s.get("respiration") or {}).get("avgValue")))
    except ErreurGarmin as e:
        if e.code == "auth":
            raise
        erreurs.append("Résumé du jour : " + e.message)

    try:   # sommeil : 31 jours au plus par appel
        for a, b in _tranches(debut, fin, 31):
            for s in _get(jeton, "/sleep-service/sleep/dailySleepSummariesByDate",
                          {"startDate": a.isoformat(), "endDate": b.isoformat()}) or []:
                if not isinstance(s, dict) or not s.get("calendarDate"):
                    continue
                d = jour(s["calendarDate"])
                sec = _nombre(s.get("sleepTimeSeconds"))
                if sec:
                    d["sommeil"] = round(sec / 60)
                    garder(d, "profond", _entier(_nombre(s.get("deepSleepSeconds")) / 60))
                    garder(d, "paradoxal", _entier(_nombre(s.get("remSleepSeconds")) / 60))
                score = ((s.get("sleepScores") or {}).get("overall") or {}).get("value")
                garder(d, "sommeilScore", _entier(score))
                garder(d, "coucher", _heure_locale(s.get("sleepStartTimestampLocal")))
                garder(d, "lever", _heure_locale(s.get("sleepEndTimestampLocal")))
    except ErreurGarmin as e:
        if e.code == "auth":
            raise
        erreurs.append("Sommeil : " + e.message)

    try:   # VFC (variabilite de la frequence cardiaque) de la nuit
        for a, b in _tranches(debut, fin, 31):
            r = _get(jeton, f"/hrv-service/hrv/daily/{a.isoformat()}/{b.isoformat()}") or {}
            for s in (r.get("hrvSummaries") or []) if isinstance(r, dict) else []:
                if not s.get("calendarDate"):
                    continue
                d = jour(s["calendarDate"])
                garder(d, "vfc", _entier(s.get("lastNightAvg")))
                if s.get("status"):
                    d["vfcStatut"] = str(s["status"])[:20]
    except ErreurGarmin as e:
        if e.code == "auth":
            raise
        erreurs.append("VFC : " + e.message)

    return {k: v for k, v in jours.items() if v}


def _age_forme(jeton: str, jour: datetime.date, erreurs: list):
    """{age, reel, atteignable} : l'age physique (fitness age) le plus recent."""
    try:
        r = _get(jeton, f"/fitnessage-service/fitnessage/v2/{jour.isoformat()}")
    except ErreurGarmin as e:
        if e.code == "auth":
            raise
        # Introuvable : la montre ne calcule pas d'age physique, ce n'est pas une panne
        if e.statut != 404:
            erreurs.append("Âge physique : " + e.message)
        return None
    a = (r[0] if isinstance(r, list) and r else r) if r else None
    if not isinstance(a, dict) or not _nombre(a.get("fitnessAge")):
        return None
    return {"age": round(_nombre(a["fitnessAge"]), 1), "reel": _entier(a.get("chronologicalAge")),
            "atteignable": round(_nombre(a.get("achievableFitnessAge")), 1) or None}


def _cycle(jeton: str, jour: datetime.date, erreurs: list):
    """Le cycle du jour, ou None si Garmin n'en suit pas (204, ou rien de lisible)."""
    try:
        c = _get(jeton, f"/periodichealth-service/menstrualcycle/summary/{jour.isoformat()}")
    except ErreurGarmin as e:
        if e.code == "auth":
            raise
        if e.statut != 404:          # introuvable : pas de cycle suivi dans Connect
            erreurs.append("Cycle : " + e.message)
        return None
    if not isinstance(c, dict) or not _entier(c.get("dayInCycle")):
        return None
    out = {"date": jour.isoformat(), "jour": _entier(c.get("dayInCycle")),
           "duree": _entier(c.get("predictedCycleLength")), "regles": _entier(c.get("periodLength")),
           "fertileDebut": _entier(c.get("fertileWindowStart")), "fertileDuree": _entier(c.get("lengthOfFertileWindow")),
           "luteale": _entier(c.get("lutealPhaseStart")), "prochaine": _entier(c.get("daysUntilNextPhase")),
           "grossesse": c.get("pregnancyCycle") is True}
    return {k: v for k, v in out.items() if v is not None}


# ─── API du module ───────────────────────────────────────────────────────────

def _choix(data: dict) -> dict:
    choix = data.get("choix") if isinstance(data.get("choix"), dict) else {}
    return {c: bool(choix.get(c, CHOIX_DEFAUT[c])) for c in CHOIX}


def config() -> dict:
    data = _store.load()
    jours = data.get("jours") if isinstance(data.get("jours"), dict) else {}
    return {"connecte":   bool(data.get("secret")),
            "connecteLe": data.get("connecteLe") or "",
            "depuis":     data.get("depuis") or "",
            "choix":      _choix(data),
            "derniere":   data.get("derniere") or "",
            "expire":     data.get("expire") or "",
            "jours":      jours,
            "ageForme":   data.get("ageForme") if isinstance(data.get("ageForme"), dict) else None,
            "records":    data.get("records") if isinstance(data.get("records"), dict) else {},
            "cycle":      data.get("cycle") if isinstance(data.get("cycle"), dict) else None}


def _expiration(duree) -> str:
    """Fin de validite d'une cle creee aujourd'hui pour `duree` jours ("" : inconnue)."""
    try:
        n = int(duree)
    except (TypeError, ValueError):
        return ""
    return (datetime.date.today() + datetime.timedelta(days=n)).isoformat() if n in DUREES_CLE else ""


def connecter(cle: str, depuis: str = "", duree=None) -> dict:
    """N'enregistre qu'une cle que Garmin vient d'accepter. duree : jours de
    validite choisis sur Garmin Connect (pour le rappel avant expiration)."""
    cle = re.sub(r"\s+", "", cle or "")
    if not cle:
        raise ErreurGarmin("saisie", "Colle la clé API créée sur Garmin Connect.")
    if len(cle) > 4000 or not re.match(r"^[\x21-\x7e]+$", cle):
        raise ErreurGarmin("saisie", "Ce texte ne ressemble pas à une clé Garmin : recopie-la "
                                     "telle qu'elle est affichée.")
    aujourdhui = datetime.date.today()
    debut = _jour(depuis, aujourdhui - datetime.timedelta(days=PREMIERS_JOURS))
    debut = min(debut, aujourdhui)
    with _verrou:
        _jeton.update(cle="", valeur="", fin=0.0)
        _obtenir_jeton(cle)
        secret = actus._chiffrer(cle, TROUSSEAU, "Pilote : clé API personnelle Garmin")
        _modifier(lambda d: d.update(secret=secret, connecteLe=aujourdhui.isoformat(),
                                     depuis=debut.isoformat(), derniere="", expire=_expiration(duree)))
    return config()


def regler(choix: dict, depuis: str = "", expire: str = None) -> dict:
    """depuis plus tot que l'ancien : la synchronisation suivante remonte jusque-la.
    expire : fin de la cle corrigee a la main ("" l'efface, None n'y touche pas)."""
    def changer(d):
        d["choix"] = {c: bool((choix or {}).get(c)) for c in CHOIX}
        if not d["choix"]["cycle"]:
            d["cycle"] = None          # decoche : rien ne reste du cycle
        if expire is not None:
            fin = _jour(expire, None)
            d["expire"] = fin.isoformat() if fin else ""
        if depuis:
            nouveau = min(_jour(depuis, datetime.date.today()), datetime.date.today()).isoformat()
            if nouveau < (d.get("depuis") or ""):
                d["derniere"] = ""
            d["depuis"] = nouveau
    _modifier(changer)
    return config()


def deconnecter() -> dict:
    """Oublie la cle ; les resumes de forme deja lus restent (ils sont a l'utilisateur)."""
    with _verrou:
        data = _store.load()
        actus._oublier(data.get("secret") or "", TROUSSEAU)
        _jeton.update(cle="", valeur="", fin=0.0)
        _modifier(lambda d: d.update(secret="", derniere="", expire="", cycle=None))
    return config()


def marquer_vus(ids: list) -> dict:
    """Ce que la page a ajoute (ou ecarte) : ne sera plus propose."""
    ids = [str(i)[:200] for i in (ids or []) if i]

    def changer(d):
        d["vus"] = list(dict.fromkeys((d.get("vus") or []) + ids))[-5000:]
    _modifier(changer)
    return {"nb": len(ids)}


def synchroniser() -> dict:
    """Lit ce qui est nouveau depuis la derniere synchronisation (avec
    RECOUVREMENT jours relus), garde la forme, renvoie seances et pesees a
    ajouter par la page."""
    with _verrou:
        data = _store.load()
        cle = _cle(data)
        choix = _choix(data)
        aujourdhui = datetime.date.today()
        depuis = _jour(data.get("depuis"), aujourdhui - datetime.timedelta(days=PREMIERS_JOURS))
        derniere = data.get("derniere") or ""
        debut = depuis
        if derniere:
            debut = max(depuis, _jour(derniere, depuis) - datetime.timedelta(days=RECOUVREMENT))
        vus = set(data.get("vus") or [])
        erreurs = []
        jeton = _obtenir_jeton(cle)

        seances, recs, histoire = [], None, False
        if choix["seances"]:
            try:
                # Une fois, tout l'historique pour les records : les seances
                # d'avant « depuis » n'entrent pas dans Sports pour autant
                histoire = not data.get("historique")
                lues = (_activites(jeton, datetime.date.fromisoformat(HISTOIRE_DEBUT), aujourdhui, PAGES_HISTOIRE)
                        if histoire else _activites(jeton, debut, aujourdhui))
                recs = records(lues, data.get("records") if isinstance(data.get("records"), dict) else {})
                for a in lues:
                    s = seance(a) if isinstance(a, dict) else None
                    if s and s["garminId"] not in vus and s["date"] >= debut.isoformat():
                        seances.append(s)
            except ErreurGarmin as e:
                histoire = False
                if e.code == "auth":
                    raise
                erreurs.append("Séances : " + e.message)
            seances.sort(key=lambda s: (s["date"], s["time"]))

        pesees = []
        if choix["pesees"]:
            try:
                for a, b in _tranches(debut, aujourdhui, 365):
                    for p in _get(jeton, f"/weight-service/weight/all/{a.isoformat()}/{b.isoformat()}") or []:
                        m = pesee(p) if isinstance(p, dict) else None
                        if m and m["garminId"] not in vus:
                            pesees.append(m)
            except ErreurGarmin as e:
                if e.code == "auth":
                    raise
                erreurs.append("Pesées : " + e.message)
            pesees.sort(key=lambda m: (m["date"], m["time"]))

        forme, age = {}, None
        if choix["forme"]:
            jours = data.get("jours") if isinstance(data.get("jours"), dict) else {}
            # Une fois l'annee passee (courbe sur un an), puis les derniers jours
            debut_forme = aujourdhui - datetime.timedelta(days=JOURS_AN - 1)
            if jours and derniere and data.get("formeAn"):
                debut_forme = max(debut_forme, _jour(derniere, aujourdhui) - datetime.timedelta(days=2))
            forme = _forme(jeton, debut_forme, aujourdhui, erreurs)
            age = _age_forme(jeton, aujourdhui, erreurs)
        cycle = _cycle(jeton, aujourdhui, erreurs) if choix["cycle"] else None

        def changer(d):
            if recs is not None:
                d["records"] = recs
            if histoire:
                d["historique"] = True
            if choix["forme"] and not erreurs:
                d["formeAn"] = True
            if choix["forme"] and age:
                d["ageForme"] = age
            if choix["cycle"]:
                d["cycle"] = cycle
            jours = d.get("jours") if isinstance(d.get("jours"), dict) else {}
            for k, v in forme.items():
                jours[k] = {**jours.get(k, {}), **v}
            limite = (aujourdhui - datetime.timedelta(days=JOURS_GARDES)).isoformat()
            d["jours"] = {k: jours[k] for k in sorted(jours) if k >= limite}
            if not erreurs:
                d["derniere"] = datetime.datetime.now().isoformat(timespec="seconds")
        _modifier(changer)

    return {**config(), "seances": seances, "pesees": pesees, "erreurs": erreurs}
