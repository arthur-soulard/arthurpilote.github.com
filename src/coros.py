"""
coros.py — Montre Coros, lue par le serveur MCP officiel de Coros
(mcp.coros.com/mcp : docs/modules/montres.md).

MCP (Model Context Protocol) est un protocole ouvert : un « client » appelle
les « outils » d'un serveur en JSON-RPC sur HTTP. Coros l'a ouvert pour les
assistants IA, mais n'importe quel client conforme peut s'y connecter :
Pilote en est un, qui ne fait que LIRE (aucun outil d'ecriture n'est appele).

Connexion (lue sur le serveur de Coros le 03/11/2026) : OAuth 2.1 avec
enregistrement dynamique du client (/connect/register), PKCE S256 et jeton de
renouvellement (offline_access). Pilote ouvre la page de connexion de Coros
dans le navigateur ; Coros renvoie vers un petit serveur ouvert un instant sur
127.0.0.1 (port libre, chemin /coros/retour), puis ferme. Le jeton de
renouvellement est chiffre comme la cle Garmin (actus._chiffrer) ; le jeton
d'acces (courte duree) vit en memoire seulement.

Les noms des outils de Coros et la forme de leurs reponses ne sont pas
publies : Pilote les reconnait par leurs mots (activity, sleep, hrv...) et ses
champs par leurs noms usuels. Ce qu'il a vu (noms d'outils et de champs, jamais
de valeurs) est garde dans `apercu`, pour corriger la lecture apres un essai
avec un vrai compte.

Comme pour Garmin, les seances ne sont PAS ecrites ici dans sports.json : la
page les ajoute a SP elle-meme, puis signale ce qu'elle a pris (marquer_vus).

Emplacement : <app_dir>/users/<slug>/coros.json (+ backups_coros/)
"""
from __future__ import annotations

import base64
import datetime
import hashlib
import json
import re
import secrets
import socket
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

import actus
import garmin
import jsonstore

MCP = "https://mcp.coros.com/mcp"     # remplace par les tests
DELAI = 30
ATTENTE_MAX = 300                     # 5 min pour se connecter dans le navigateur
TROUSSEAU = "Pilote Coros"
CHOIX = ("seances", "forme")
CHOIX_DEFAUT = {"seances": True, "forme": True}
PREMIERS_JOURS = 30
RECOUVREMENT = 7
JOURS_GARDES = 400
VERSION_MCP = "2025-06-18"


class ErreurCoros(Exception):
    """code : saisie, auth, reseau, limite, api, config."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


def default_data() -> dict:
    return {
        "_meta": {
            "version": 1,
            "schema": "coros.v1",
            "createdAt":   datetime.date.today().isoformat(),
            "lastSavedAt": datetime.datetime.now().isoformat(timespec="seconds"),
        },
        "secret":     "",        # jeton de renouvellement, chiffre
        "client":     {},        # client_id donne par Coros, adresses du serveur d'autorisation
        "connecteLe": "",
        "depuis":     "",
        "choix":      dict(CHOIX_DEFAUT),
        "derniere":   "",
        "vus":        [],
        "jours":      {},        # "AAAA-MM-JJ" -> {sommeil, vfc, fcRepos, pas, recup}
        "apercu":     {},        # noms des outils et des champs vus (jamais de valeurs)
    }


_store = jsonstore.JsonStore(
    filename="coros.json",
    backup_dirname="backups_coros",
    schema="coros.v1",
    default_factory=default_data,
)

_verrou = threading.RLock()
_acces = {"valeur": "", "fin": 0.0}                         # memoire seulement
_connexion = {"etat": "", "erreur": "", "jeton": 0}         # suivi de la connexion en cours


def load_data() -> dict:
    return _store.load()


def _modifier(changer) -> dict:
    with _verrou:
        data = _store.load()
        changer(data)
        _store.save(data)
        return data


# ─── HTTP ────────────────────────────────────────────────────────────────────

_ctx = ssl.create_default_context()


def _http(url: str, corps: bytes = None, entetes: dict = None, methode: str = None) -> tuple:
    """(statut, entetes, corps). Les erreurs reseau deviennent ErreurCoros."""
    req = urllib.request.Request(url, data=corps, method=methode or ("POST" if corps is not None else "GET"))
    req.add_header("User-Agent", "Pilote")
    for k, v in (entetes or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=DELAI, context=_ctx) as r:
            return r.status, r.headers, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read()
    except (urllib.error.URLError, socket.timeout, ssl.SSLError, OSError) as e:
        raise ErreurCoros("reseau", "Coros ne répond pas. Vérifie ta connexion internet, puis réessaie.") from e


def _json(url: str, corps=None, entetes=None, formulaire=False) -> tuple:
    h = dict(entetes or {})
    h.setdefault("Accept", "application/json")
    if isinstance(corps, dict):
        if formulaire:
            corps = urllib.parse.urlencode(corps).encode()
            h["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            corps = json.dumps(corps).encode()
            h["Content-Type"] = "application/json"
    statut, _, brut = _http(url, corps, h)
    try:
        return statut, json.loads(brut.decode("utf-8")) if brut.strip() else {}
    except ValueError:
        return statut, {}


def _decouvrir() -> dict:
    """Adresses OAuth annoncees par le serveur MCP (RFC 9728 puis RFC 8414)."""
    u = urllib.parse.urlsplit(MCP)
    origine = f"{u.scheme}://{u.netloc}"
    statut, pr = _json(origine + "/.well-known/oauth-protected-resource" + u.path)
    if statut != 200 or not pr.get("authorization_servers"):
        statut, pr = _json(origine + "/.well-known/oauth-protected-resource")
    if statut != 200 or not pr.get("authorization_servers"):
        raise ErreurCoros("api", "Le serveur de Coros n'indique pas comment se connecter.")
    serveur = str(pr["authorization_servers"][0]).rstrip("/")
    statut, meta = _json(serveur + "/.well-known/oauth-authorization-server")
    if statut != 200 or not meta.get("authorization_endpoint") or not meta.get("token_endpoint"):
        raise ErreurCoros("api", "Le serveur de connexion de Coros ne répond pas comme prévu.")
    return {"ressource": pr.get("resource") or MCP, "autorisation": meta["authorization_endpoint"],
            "jeton": meta["token_endpoint"], "enregistrement": meta.get("registration_endpoint") or "",
            "revocation": meta.get("revocation_endpoint") or ""}


# ─── Connexion (navigateur, puis retour sur 127.0.0.1) ───────────────────────

_PAGE = ("<!doctype html><meta charset='utf-8'><title>Pilote</title>"
         "<body style='font:16px system-ui;margin:3rem;max-width:32rem'><h2>{titre}</h2>"
         "<p>{texte}</p></body>")


def demarrer_connexion(depuis: str = "") -> dict:
    """Prepare la connexion et rend l'adresse de la page de Coros a ouvrir.
    La suite (retour du navigateur, echange du code) se fait dans un fil ;
    etat_connexion() dit ou elle en est."""
    with _verrou:
        meta = _decouvrir()
        if not meta["enregistrement"]:
            raise ErreurCoros("api", "Coros n'accepte pas l'enregistrement d'une application.")
        serveur = HTTPServer(("127.0.0.1", 0), _Retour)
        retour = f"http://127.0.0.1:{serveur.server_address[1]}/coros/retour"
        try:
            statut, client = _json(meta["enregistrement"], {
                "client_name": "Pilote", "redirect_uris": [retour],
                "grant_types": ["authorization_code", "refresh_token"], "response_types": ["code"],
                "token_endpoint_auth_method": "none", "scope": "openid mcp.tools offline_access"})
        except Exception:
            serveur.server_close()
            raise
        if statut not in (200, 201) or not client.get("client_id"):
            serveur.server_close()
            raise ErreurCoros("api", f"Coros a refusé d'enregistrer Pilote ({statut}).")
        verificateur = secrets.token_urlsafe(48)
        defi = base64.urlsafe_b64encode(hashlib.sha256(verificateur.encode()).digest()).decode().rstrip("=")
        etat = secrets.token_urlsafe(24)
        url = meta["autorisation"] + "?" + urllib.parse.urlencode({
            "response_type": "code", "client_id": client["client_id"], "redirect_uri": retour,
            "scope": "openid mcp.tools offline_access", "state": etat, "code_challenge": defi,
            "code_challenge_method": "S256", "resource": meta["ressource"]})
        _connexion.update(etat="attente", erreur="", jeton=_connexion["jeton"] + 1)
        numero = _connexion["jeton"]
        serveur.attendu = {"etat": etat, "code": "", "erreur": ""}
        threading.Thread(target=_attendre, daemon=True,
                         args=(serveur, numero, meta, client["client_id"], retour, verificateur, depuis)).start()
        return {"url": url}


class _Retour(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        u = urllib.parse.urlsplit(self.path)
        if u.path != "/coros/retour":
            self.send_response(404)
            self.end_headers()
            return
        q = dict(urllib.parse.parse_qsl(u.query))
        a = self.server.attendu
        if q.get("state") != a["etat"]:
            a["erreur"] = "Réponse de connexion inattendue : recommence depuis Pilote."
        elif q.get("error"):
            a["erreur"] = "Connexion refusée sur la page de Coros."
        else:
            a["code"] = q.get("code") or ""
        ok = bool(a["code"])
        page = _PAGE.format(titre="Coros est connecté à Pilote" if ok else "Connexion interrompue",
                            texte="Tu peux fermer cet onglet et revenir dans Pilote." if ok else
                            "Reviens dans Pilote pour recommencer.").encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(page)))
        self.end_headers()
        self.wfile.write(page)


def _attendre(serveur, numero, meta, client_id, retour, verificateur, depuis):
    fin = time.time() + ATTENTE_MAX
    serveur.timeout = 1
    try:
        while time.time() < fin and _connexion["jeton"] == numero:
            serveur.handle_request()
            if serveur.attendu["code"] or serveur.attendu["erreur"]:
                break
    finally:
        serveur.server_close()
    if _connexion["jeton"] != numero:          # une autre connexion a ete lancee depuis
        return
    a = serveur.attendu
    if not a["code"]:
        _connexion.update(etat="erreur", erreur=a["erreur"] or "Délai dépassé : la connexion n'a pas été faite sur la page de Coros.")
        return
    try:
        statut, r = _json(meta["jeton"], {"grant_type": "authorization_code", "code": a["code"],
                                          "redirect_uri": retour, "client_id": client_id,
                                          "code_verifier": verificateur, "resource": meta["ressource"]},
                          formulaire=True)
        if statut != 200 or not r.get("access_token"):
            raise ErreurCoros("auth", f"Coros a refusé la connexion ({statut}).")
        _garder_jetons(r, client_id, meta, depuis, nouvelle=True)
        _connexion.update(etat="ok", erreur="")
    except ErreurCoros as e:
        _connexion.update(etat="erreur", erreur=e.message)
    except Exception as e:
        _connexion.update(etat="erreur", erreur="Connexion impossible : " + str(e))


def _garder_jetons(r: dict, client_id: str, meta: dict, depuis: str = "", nouvelle=False):
    _acces.update(valeur=r["access_token"], fin=time.time() + float(r.get("expires_in") or 3600))
    renouv = r.get("refresh_token") or ""
    if not renouv and not nouvelle:
        return                                  # Coros garde le meme jeton de renouvellement
    secret = actus._chiffrer(renouv, TROUSSEAU, "Pilote : connexion Coros") if renouv else ""
    aujourdhui = datetime.date.today()

    def changer(d):
        d["secret"] = secret
        d["client"] = {"id": client_id, **meta}
        if nouvelle:
            debut = garmin._jour(depuis, aujourdhui - datetime.timedelta(days=PREMIERS_JOURS))
            d.update(connecteLe=aujourdhui.isoformat(), depuis=min(debut, aujourdhui).isoformat(), derniere="")
    _modifier(changer)


def etat_connexion() -> dict:
    return {"etat": _connexion["etat"], "erreur": _connexion["erreur"], **config()}


def annuler_connexion() -> dict:
    _connexion.update(etat="", erreur="", jeton=_connexion["jeton"] + 1)
    return config()


def _jeton_acces(data: dict) -> str:
    if _acces["valeur"] and _acces["fin"] - time.time() > 60:
        return _acces["valeur"]
    secret, client = data.get("secret") or "", data.get("client") or {}
    if not secret or not client.get("id"):
        raise ErreurCoros("config", "Aucun compte Coros n'est connecté.")
    try:
        renouv = actus._dechiffrer(secret, TROUSSEAU)
    except Exception:
        raise ErreurCoros("config", "La connexion enregistrée ne se relit pas ici (fichier venu d'un "
                                    "autre PC ?). Reconnecte-toi dans Montres › Coros.")
    statut, r = _json(client["jeton"], {"grant_type": "refresh_token", "refresh_token": renouv,
                                        "client_id": client["id"], "resource": client.get("ressource") or MCP},
                      formulaire=True)
    if statut in (400, 401, 403):
        raise ErreurCoros("auth", "Coros refuse la connexion de Pilote (accès retiré ou expiré) : "
                                  "reconnecte-toi dans Montres › Coros.")
    if statut != 200 or not r.get("access_token"):
        raise ErreurCoros("api", f"Coros a répondu {statut} au renouvellement de la connexion.")
    _garder_jetons(r, client["id"], {k: v for k, v in client.items() if k != "id"})
    return _acces["valeur"]


# ─── MCP (JSON-RPC sur HTTP, réponse en JSON ou en flux SSE) ─────────────────

class _Session:
    def __init__(self, url: str, jeton: str):
        self.url, self.jeton, self.id, self.n = url, jeton, "", 0

    def appeler(self, methode: str, params: dict = None, notification=False):
        self.n += 1
        msg = {"jsonrpc": "2.0", "method": methode}
        if params is not None:
            msg["params"] = params
        if not notification:
            msg["id"] = self.n
        h = {"Authorization": "Bearer " + self.jeton, "Content-Type": "application/json",
             "Accept": "application/json, text/event-stream", "MCP-Protocol-Version": VERSION_MCP}
        if self.id:
            h["Mcp-Session-Id"] = self.id
        statut, entetes, brut = _http(self.url, json.dumps(msg).encode(), h)
        if statut in (401, 403):
            _acces.update(valeur="", fin=0.0)
            raise ErreurCoros("auth", "Coros refuse la connexion de Pilote : reconnecte-toi dans Montres › Coros.")
        if statut == 429:
            raise ErreurCoros("limite", "Coros reçoit trop de demandes : réessaie plus tard.")
        if notification:
            return None
        if statut != 200:
            raise ErreurCoros("api", f"Coros a répondu {statut} ({methode}).")
        self.id = entetes.get("Mcp-Session-Id") or self.id
        texte = brut.decode("utf-8", "replace")
        reponses = []
        if "text/event-stream" in (entetes.get("Content-Type") or ""):
            for bloc in re.split(r"\r?\n\r?\n", texte):
                donnees = "\n".join(l[5:].lstrip() for l in bloc.splitlines() if l.startswith("data:"))
                if donnees:
                    reponses.append(donnees)
        else:
            reponses.append(texte)
        for t in reponses:
            try:
                r = json.loads(t)
            except ValueError:
                continue
            if isinstance(r, dict) and r.get("id") == msg["id"]:
                if r.get("error"):
                    raise ErreurCoros("api", "Coros : " + str((r["error"] or {}).get("message") or r["error"])[:200])
                return r.get("result") or {}
        raise ErreurCoros("api", "Coros a renvoyé une réponse illisible.")

    def ouvrir(self):
        self.appeler("initialize", {"protocolVersion": VERSION_MCP, "capabilities": {},
                                    "clientInfo": {"name": "Pilote", "version": "1"}})
        self.appeler("notifications/initialized", notification=True)


def _contenu(resultat: dict):
    """Le JSON rendu par un outil : structuredContent, ou le texte des blocs."""
    if isinstance(resultat.get("structuredContent"), (dict, list)):
        return resultat["structuredContent"]
    morceaux = []
    for b in resultat.get("content") or []:
        if isinstance(b, dict) and b.get("type") == "text":
            try:
                morceaux.append(json.loads(b.get("text") or ""))
            except ValueError:
                pass
    return morceaux[0] if len(morceaux) == 1 else morceaux


def _listes(x, profondeur=0) -> list:
    """Les listes d'objets trouvees dans une reponse, la plus longue d'abord."""
    out = []
    if profondeur > 5:
        return out
    if isinstance(x, list):
        if x and all(isinstance(e, dict) for e in x):
            out.append(x)
        for e in x:
            out += _listes(e, profondeur + 1)
    elif isinstance(x, dict):
        for v in x.values():
            out += _listes(v, profondeur + 1)
    return sorted(out, key=len, reverse=True)


# Outils : reconnus par les mots de leur nom et de leur description
_ECRITURE = ("create", "update", "delete", "edit", "add", "save", "upload", "set_", "write", "remove")


def _outils_pour(outils: list, mots: tuple, sauf: tuple = ()) -> list:
    out = []
    for o in outils:
        nom = str(o.get("name") or "").lower()
        texte = nom + " " + str(o.get("description") or "").lower()
        if any(m in nom for m in _ECRITURE):
            continue                            # Pilote ne fait que lire
        if any(m in texte for m in mots) and not any(m in nom for m in sauf):
            out.append(o)
    return out


def _arguments(outil: dict, debut: datetime.date, fin: datetime.date) -> dict:
    """Les dates demandees par l'outil, au format qu'il decrit."""
    props = ((outil.get("inputSchema") or {}).get("properties") or {})
    args = {}
    for nom, p in props.items():
        n = nom.lower()
        quoi = debut if re.search(r"start|begin|from|since", n) else fin if re.search(r"end|until|to$|stop", n) else None
        if quoi is None and re.search(r"^date$|^day$", n):
            quoi = fin
        if quoi is None:
            if re.search(r"size|limit|count", n) and (p.get("type") in ("integer", "number")):
                args[nom] = min(int(p.get("maximum") or 100), 100)
            continue
        desc = (str(p.get("description") or "") + " " + str(p.get("pattern") or "") + " " + str(p.get("format") or "")).lower()
        if p.get("type") in ("integer", "number"):
            args[nom] = int(time.mktime(quoi.timetuple())) if "timestamp" in desc or "epoch" in desc \
                else int(quoi.strftime("%Y%m%d"))
        elif "yyyymmdd" in desc or r"\d{8}" in desc:
            args[nom] = quoi.strftime("%Y%m%d")
        else:
            args[nom] = quoi.isoformat()
    return args


def _cle(r: dict, *motifs):
    """La premiere valeur dont le nom de champ correspond a un motif."""
    for motif in motifs:
        for k, v in r.items():
            if v not in (None, "") and re.search(motif, k, re.I):
                return v
    return None


def _date(v):
    """AAAA-MM-JJ et HH:MM depuis 20261103, "2026-11-03 18:05", ou un horodatage."""
    if v is None:
        return None, ""
    s = str(v).strip()
    m = re.match(r"^(\d{4})-?(\d{2})-?(\d{2})(?:[ T]?(\d{2}):?(\d{2}))?", s)
    if m and 1990 < int(m.group(1)) < 2100 and not re.match(r"^\d{13,}$", s):
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}", (f"{m.group(4)}:{m.group(5)}" if m.group(4) else "")
    try:
        n = float(s)
    except ValueError:
        return None, ""
    if n > 1e11:
        n /= 1000                               # millisecondes
    if n < 6e8:
        return None, ""
    d = datetime.datetime.fromtimestamp(n)
    return d.date().isoformat(), d.strftime("%H:%M")


# sportType de Coros (Training Hub) : par centaines, d'apres l'usage courant.
# A VERIFIER avec un vrai compte : Coros ne publie pas la liste.
def sport_pilote(v) -> str:
    try:
        n = int(v)
    except (TypeError, ValueError):
        return garmin.sport_pilote(str(v or ""))
    if n in (104, 105):
        return "rando"
    if n in (402,):
        return "muscu"
    return {1: "course", 2: "velo", 3: "natation"}.get(n // 100, "autre")


def seance(a: dict) -> dict:
    ident = _cle(a, r"^labelId$", r"^activityId$", r"^workoutId$", r"^id$", r"id$")
    jour, heure = _date(_cle(a, r"^startTime", r"^start", r"^date$", r"day$", r"time$"))
    if not ident or not jour:
        return None
    sport = sport_pilote(_cle(a, r"^sportType$", r"^sport", r"^mode$", r"type$"))
    champs = garmin._champs(sport)
    secondes = garmin._nombre(_cle(a, r"^totalTime$", r"^duration", r"workoutTime", r"time$"))
    if secondes > 86400 * 2:
        secondes /= 1000                        # millisecondes
    metres = garmin._nombre(_cle(a, r"^distance"))
    kcal = garmin._nombre(_cle(a, r"calorie"))
    if kcal > 20000:
        kcal /= 1000                            # en calories
    s = {"corosId": str(ident)[:100], "date": jour, "time": heure, "sport": sport,
         "duration": round(secondes / 60), "distance": 0,
         "elevation": round(garmin._nombre(_cle(a, r"ascent", r"elev", r"climb"))) if "elevation" in champs else 0,
         "note": str(_cle(a, r"^name$", r"title") or "")[:200]}
    if "distance_m" in champs:
        s["distance"] = round(metres)
    elif "distance_km" in champs:
        s["distance"] = round(metres / 1000, 2)
    fc = round(garmin._nombre(_cle(a, r"^avgH", r"avg.*heart", r"heart.*avg")))
    if fc:
        s["fcMoy"] = fc
    if kcal:
        s["kcal"] = round(kcal)
    return s


def _jour_forme(r: dict) -> tuple:
    """(jour, {sommeil, vfc, fcRepos, pas, recup}) d'un enregistrement quotidien."""
    jour, _ = _date(_cle(r, r"^date$", r"^happenDay$", r"day$", r"^date", r"time$"))
    if not jour:
        return None, {}
    out = {}
    som = garmin._nombre(_cle(r, r"sleep.*(total|time|dur)", r"^(total)?sleep", r"^duration$"))
    if som:
        out["sommeil"] = round(som / 60) if som > 1440 else round(som)
    for cle, motifs in (("vfc", (r"hrv",)), ("fcRepos", (r"^rhr$", r"resting", r"rest.*h")),
                        ("pas", (r"^steps?$", r"step")), ("recup", (r"recover",))):
        v = garmin._entier(_cle(r, *motifs))
        if v is not None:
            out[cle] = v
    return jour, out


# ─── API du module ───────────────────────────────────────────────────────────

def _choix(data: dict) -> dict:
    choix = data.get("choix") if isinstance(data.get("choix"), dict) else {}
    return {c: bool(choix.get(c, CHOIX_DEFAUT[c])) for c in CHOIX}


def config() -> dict:
    data = _store.load()
    return {"connecte": bool(data.get("secret")), "connecteLe": data.get("connecteLe") or "",
            "depuis": data.get("depuis") or "", "choix": _choix(data), "derniere": data.get("derniere") or "",
            "jours": data.get("jours") if isinstance(data.get("jours"), dict) else {}}


def regler(choix: dict, depuis: str = "") -> dict:
    def changer(d):
        d["choix"] = {c: bool((choix or {}).get(c)) for c in CHOIX}
        if depuis:
            nouveau = min(garmin._jour(depuis, datetime.date.today()), datetime.date.today()).isoformat()
            if nouveau < (d.get("depuis") or ""):
                d["derniere"] = ""
            d["depuis"] = nouveau
    _modifier(changer)
    return config()


def deconnecter() -> dict:
    """Oublie la connexion (et la retire chez Coros si possible) ; la forme lue reste."""
    with _verrou:
        data = _store.load()
        client = data.get("client") or {}
        try:
            if data.get("secret") and client.get("revocation"):
                renouv = actus._dechiffrer(data["secret"], TROUSSEAU)
                _json(client["revocation"], {"token": renouv, "client_id": client.get("id", ""),
                                             "token_type_hint": "refresh_token"}, formulaire=True)
        except Exception:
            pass                                 # hors ligne : Pilote oublie quand meme
        actus._oublier(data.get("secret") or "", TROUSSEAU)
        _acces.update(valeur="", fin=0.0)
        _modifier(lambda d: d.update(secret="", client={}, derniere=""))
    return config()


def marquer_vus(ids: list) -> dict:
    ids = [str(i)[:200] for i in (ids or []) if i]

    def changer(d):
        d["vus"] = list(dict.fromkeys((d.get("vus") or []) + ids))[-5000:]
    _modifier(changer)
    return {"nb": len(ids)}


def synchroniser() -> dict:
    with _verrou:
        data = _store.load()
        jeton = _jeton_acces(data)
        choix = _choix(data)
        aujourdhui = datetime.date.today()
        depuis = garmin._jour(data.get("depuis"), aujourdhui - datetime.timedelta(days=PREMIERS_JOURS))
        derniere = data.get("derniere") or ""
        debut = max(depuis, garmin._jour(derniere, depuis) - datetime.timedelta(days=RECOUVREMENT)) if derniere else depuis
        vus = set(data.get("vus") or [])
        erreurs, apercu = [], {}
        mcp = _Session((data.get("client") or {}).get("ressource") or MCP, jeton)
        mcp.ouvrir()
        outils = (mcp.appeler("tools/list", {}) or {}).get("tools") or []
        apercu["outils"] = sorted(str(o.get("name") or "")[:80] for o in outils)[:100]

        def lire(outil, de, a):
            r = _contenu(mcp.appeler("tools/call", {"name": outil["name"], "arguments": _arguments(outil, de, a)}))
            listes = _listes(r)
            l = listes[0] if listes else ([r] if isinstance(r, dict) else [])
            apercu[str(outil["name"])[:80]] = sorted({str(k)[:60] for e in l[:5] for k in e})[:80]
            return l

        seances = []
        if choix["seances"]:
            a_lire = _outils_pour(outils, ("activit", "workout", "sport record"),
                                  ("fit", "file", "plan", "schedule", "lap", "split", "detail", "feedback"))
            if not a_lire:
                erreurs.append("Séances : Coros ne propose pas d'outil de liste des séances.")
            for o in a_lire[:1]:
                try:
                    for a in lire(o, debut, aujourdhui):
                        s = seance(a)
                        if s and s["corosId"] not in vus and s["date"] >= depuis.isoformat():
                            seances.append(s)
                except ErreurCoros as e:
                    if e.code == "auth":
                        raise
                    erreurs.append("Séances : " + e.message)
            seances.sort(key=lambda s: (s["date"], s["time"]))

        forme = {}
        if choix["forme"]:
            debut_forme = aujourdhui - datetime.timedelta(days=PREMIERS_JOURS - 1)
            if data.get("jours") and derniere:
                debut_forme = max(debut_forme, garmin._jour(derniere, aujourdhui) - datetime.timedelta(days=2))
            for o in _outils_pour(outils, ("sleep", "hrv", "resting", "daily", "step", "recover"),
                                  ("series", "fit", "plan", "schedule", "activit", "workout")):
                try:
                    for r in lire(o, debut_forme, aujourdhui):
                        jour, v = _jour_forme(r)
                        if jour and v:
                            forme[jour] = {**forme.get(jour, {}), **v}
                except ErreurCoros as e:
                    if e.code == "auth":
                        raise
                    erreurs.append(str(o.get("name"))[:40] + " : " + e.message)

        def changer(d):
            jours = d.get("jours") if isinstance(d.get("jours"), dict) else {}
            for k, v in forme.items():
                jours[k] = {**jours.get(k, {}), **v}
            limite = (aujourdhui - datetime.timedelta(days=JOURS_GARDES)).isoformat()
            d["jours"] = {k: jours[k] for k in sorted(jours) if k >= limite}
            d["apercu"] = apercu
            if not erreurs:
                d["derniere"] = datetime.datetime.now().isoformat(timespec="seconds")
        _modifier(changer)

    return {**config(), "seances": seances, "erreurs": erreurs}
