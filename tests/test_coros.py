"""Tests du module Coros (`python -m unittest discover -s tests`).

Faux serveur construit d'apres ce que le vrai annonce (lu le 03/11/2026 sur
mcp.coros.com : /.well-known/oauth-protected-resource, puis
/.well-known/oauth-authorization-server avec registration_endpoint, PKCE S256,
refresh_token) et d'apres le protocole MCP (initialize, tools/list,
tools/call, reponse en JSON ou en flux SSE). Les NOMS des outils et des champs
sont des suppositions : Coros ne les publie pas (docs/modules/montres.md).
"""
import base64
import datetime
import hashlib
import json
import sys
import tempfile
import threading
import time
import unittest
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "src"))

import storage  # noqa: E402

_TMP = Path(tempfile.mkdtemp(prefix="pilote_tests_coros_"))

import actus  # noqa: E402
import coros  # noqa: E402

if sys.platform != "win32":
    actus._chiffrer = lambda mdp, *a: "b64:" + base64.b64encode(mdp.encode()).decode()
    actus._oublier = lambda *a: None

AUJ = datetime.date.today()


def _iso(n):
    return (AUJ - datetime.timedelta(days=n)).isoformat()


def _compact(n):
    return int((AUJ - datetime.timedelta(days=n)).strftime("%Y%m%d"))


class _Coros(BaseHTTPRequestHandler):
    base = ""
    requetes = []
    codes = {}           # code -> (client_id, defi)
    acces = "acces-1"
    renouv = "renouv-1"
    sse = False
    refuser = False
    appels = []

    def log_message(self, *a):
        pass

    def _rep(self, statut, obj=None, type_="application/json", entetes=None):
        corps = json.dumps(obj).encode() if obj is not None and type_ == "application/json" else (obj or b"")
        self.send_response(statut)
        self.send_header("Content-Type", type_)
        for k, v in (entetes or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)

    def do_GET(self):
        _Coros.requetes.append(("GET", self.path))
        if self.path in ("/.well-known/oauth-protected-resource/mcp", "/.well-known/oauth-protected-resource"):
            return self._rep(200, {"resource": _Coros.base + "/mcp", "authorization_servers": [_Coros.base]})
        if self.path == "/.well-known/oauth-authorization-server":
            b = _Coros.base
            return self._rep(200, {"issuer": b, "authorization_endpoint": b + "/oauth2/authorize",
                                   "token_endpoint": b + "/oauth2/token", "registration_endpoint": b + "/connect/register",
                                   "revocation_endpoint": b + "/oauth2/revoke", "code_challenge_methods_supported": ["S256"]})
        self._rep(404, {})

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        brut = self.rfile.read(n)
        _Coros.requetes.append(("POST", self.path))
        if self.path == "/connect/register":
            d = json.loads(brut)
            assert d["token_endpoint_auth_method"] == "none" and d["redirect_uris"][0].startswith("http://127.0.0.1:")
            return self._rep(201, {"client_id": "client-pilote", "redirect_uris": d["redirect_uris"]})
        if self.path == "/oauth2/token":
            f = dict(urllib.parse.parse_qsl(brut.decode()))
            if f.get("grant_type") == "authorization_code":
                client, defi = _Coros.codes.get(f.get("code"), (None, None))
                ok = client == f.get("client_id") and defi == base64.urlsafe_b64encode(
                    hashlib.sha256(f.get("code_verifier", "").encode()).digest()).decode().rstrip("=")
                if not ok:
                    return self._rep(400, {"error": "invalid_grant"})
            elif f.get("grant_type") == "refresh_token":
                if _Coros.refuser or f.get("refresh_token") != _Coros.renouv:
                    return self._rep(400, {"error": "invalid_grant"})
                _Coros.renouv = "renouv-2"           # rotation, comme le permet OAuth 2.1
            _Coros.acces = "acces-" + str(len(_Coros.requetes))
            return self._rep(200, {"access_token": _Coros.acces, "expires_in": 3600,
                                   "refresh_token": _Coros.renouv, "token_type": "Bearer"})
        if self.path == "/oauth2/revoke":
            return self._rep(200, {})
        if self.path == "/mcp":
            if self.headers.get("Authorization") != "Bearer " + _Coros.acces:
                return self._rep(401, {})
            msg = json.loads(brut)
            if "id" not in msg:
                return self._rep(202, b"", "text/plain")
            r = self._mcp(msg)
            reponse = {"jsonrpc": "2.0", "id": msg["id"], "result": r}
            if _Coros.sse:
                corps = ("event: message\ndata: " + json.dumps(reponse) + "\n\n").encode()
                return self._rep(200, corps, "text/event-stream", {"Mcp-Session-Id": "s1"})
            return self._rep(200, reponse, entetes={"Mcp-Session-Id": "s1"})
        self._rep(404, {})

    def _mcp(self, msg):
        if msg["method"] == "initialize":
            return {"protocolVersion": coros.VERSION_MCP, "capabilities": {"tools": {}}, "serverInfo": {"name": "coros"}}
        if msg["method"] == "tools/list":
            dates = {"type": "object", "properties": {
                "startDay": {"type": "string", "description": "start date, format yyyyMMdd"},
                "endDay": {"type": "string", "description": "end date, format yyyyMMdd"}}}
            return {"tools": [
                {"name": "query_activity_list", "description": "Query workout records and summary data", "inputSchema": dates},
                {"name": "get_activity_fit_file", "description": "Retrieve .fit files", "inputSchema": dates},
                {"name": "query_daily_sleep", "description": "Query daily sleep data", "inputSchema": dates},
                {"name": "query_daily_health", "description": "daily average heart rate, HRV, resting heart rate, steps",
                 "inputSchema": dates},
                {"name": "create_training_plan", "description": "Create training plans and workouts", "inputSchema": dates},
            ]}
        if msg["method"] == "tools/call":
            nom, args = msg["params"]["name"], msg["params"]["arguments"]
            _Coros.appels.append((nom, args))
            if nom == "query_activity_list":
                debut = int(args["startDay"])
                data = [a for a in _Coros.activites() if a["date"] >= debut]
                return {"content": [{"type": "text", "text": json.dumps({"result": "0000", "data": {"dataList": data}})}]}
            if nom == "query_daily_sleep":
                return {"structuredContent": {"list": [{"date": _compact(0), "totalSleepTime": 452, "score": 80}]}}
            if nom == "query_daily_health":
                return {"content": [{"type": "text", "text": json.dumps([
                    {"happenDay": _compact(1), "rhr": 49, "avgHrv": 61, "steps": 10342, "recoveryPct": 87}])}]}
            raise AssertionError("outil inattendu : " + nom)
        return {}

    @staticmethod
    def activites():
        t = int(time.mktime(datetime.datetime.combine(AUJ - datetime.timedelta(days=1), datetime.time(7, 30)).timetuple()))
        return [
            {"labelId": "4711", "name": "Footing", "sportType": 100, "date": _compact(1), "startTime": t,
             "totalTime": 2710, "distance": 7420.5, "ascent": 35, "avgHr": 148, "calorie": 512000},
            {"labelId": "4712", "name": "Piscine", "sportType": 300, "date": _compact(2), "startTime": t - 86400,
             "totalTime": 1800, "distance": 1500},
            {"labelId": "4713", "name": "Vieux", "sportType": 200, "date": _compact(90), "startTime": t - 89 * 86400,
             "totalTime": 3600, "distance": 30000},
        ]


class TestCoros(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app_dir = storage.get_app_dir
        storage.get_app_dir = lambda: _TMP
        cls.serveur = ThreadingHTTPServer(("127.0.0.1", 0), _Coros)
        threading.Thread(target=cls.serveur.serve_forever, daemon=True).start()
        _Coros.base = f"http://127.0.0.1:{cls.serveur.server_address[1]}"
        coros.MCP = _Coros.base + "/mcp"

    @classmethod
    def tearDownClass(cls):
        cls.serveur.shutdown()
        storage.get_app_dir = cls.app_dir

    def setUp(self):
        _Coros.requetes.clear()
        _Coros.appels.clear()
        _Coros.codes.clear()
        _Coros.renouv, _Coros.sse, _Coros.refuser = "renouv-1", False, False
        coros._acces.update(valeur="", fin=0.0)
        for f in storage.get_user_dir().glob("*.json"):
            f.unlink()

    def _connecter(self):
        """Comme le navigateur : la page de Coros renvoie vers 127.0.0.1 avec le code."""
        url = coros.demarrer_connexion(_iso(30))["url"]
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))
        self.assertEqual((q["code_challenge_method"], q["client_id"]), ("S256", "client-pilote"))
        self.assertIn("offline_access", q["scope"])
        _Coros.codes["code-1"] = (q["client_id"], q["code_challenge"])
        urllib.request.urlopen(q["redirect_uri"] + "?" + urllib.parse.urlencode(
            {"code": "code-1", "state": q["state"]}), timeout=5).read()
        for _ in range(100):
            if coros.etat_connexion()["etat"] != "attente":
                break
            time.sleep(0.05)
        return coros.etat_connexion()

    def test_connexion_et_secret_chiffre(self):
        e = self._connecter()
        self.assertEqual(e["etat"], "ok", e["erreur"])
        self.assertTrue(e["connecte"])
        brut = (storage.get_user_dir() / "coros.json").read_text(encoding="utf-8")
        self.assertNotIn("renouv-1", brut)
        self.assertNotIn("renouv-1", json.dumps(coros.config()))

    def test_mauvais_etat_refuse(self):
        url = coros.demarrer_connexion("")["url"]
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))
        urllib.request.urlopen(q["redirect_uri"] + "?code=x&state=pas-le-bon", timeout=5).read()
        for _ in range(100):
            if coros.etat_connexion()["etat"] != "attente":
                break
            time.sleep(0.05)
        self.assertEqual(coros.etat_connexion()["etat"], "erreur")
        self.assertFalse(coros.config()["connecte"])

    def test_synchro_seances_forme_et_lecture_seule(self):
        self._connecter()
        for sse in (False, True):
            _Coros.sse = sse
            coros._acces.update(valeur="", fin=0.0)          # force le renouvellement
            r = coros.synchroniser()
            self.assertEqual(r["erreurs"], [])
            par_id = {s["corosId"]: s for s in r["seances"]}
            self.assertEqual(set(par_id), {"4711", "4712"})  # 4713 : avant « depuis »
            f = par_id["4711"]
            self.assertEqual((f["sport"], f["date"], f["time"], f["duration"], f["distance"]),
                             ("course", _iso(1), "07:30", 45, 7.42))
            self.assertEqual((f["fcMoy"], f["kcal"], f["elevation"]), (148, 512, 35))
            self.assertEqual(par_id["4712"]["sport"], "natation")
            j = coros.config()["jours"]
            self.assertEqual(j[_iso(0)]["sommeil"], 452)
            self.assertEqual(j[_iso(1)], {"fcRepos": 49, "vfc": 61, "pas": 10342, "recup": 87})
        noms = {n for n, _ in _Coros.appels}
        self.assertNotIn("create_training_plan", noms)        # jamais un outil d'écriture
        self.assertNotIn("get_activity_fit_file", noms)
        self.assertEqual(_Coros.appels[0][1]["startDay"], _iso(30).replace("-", ""))
        apercu = coros.load_data()["apercu"]
        self.assertIn("query_activity_list", apercu["outils"])
        self.assertIn("avgHr", apercu["query_activity_list"])
        self.assertNotIn("7420.5", json.dumps(apercu))        # des noms, jamais de valeurs

    def test_vus_et_acces_retire(self):
        self._connecter()
        r = coros.synchroniser()
        coros.marquer_vus([s["corosId"] for s in r["seances"]])
        self.assertEqual(coros.synchroniser()["seances"], [])
        coros._acces.update(valeur="", fin=0.0)
        _Coros.refuser = True
        with self.assertRaises(coros.ErreurCoros) as e:
            coros.synchroniser()
        self.assertEqual(e.exception.code, "auth")

    def test_deconnexion(self):
        self._connecter()
        coros.deconnecter()
        self.assertFalse(coros.config()["connecte"])
        self.assertIn(("POST", "/oauth2/revoke"), _Coros.requetes)
        with self.assertRaises(coros.ErreurCoros) as e:
            coros.synchroniser()
        self.assertEqual(e.exception.code, "config")

    def test_dates_et_sports(self):
        self.assertEqual(coros._date(20261103), ("2026-11-03", ""))
        self.assertEqual(coros._date("202611031805"), ("2026-11-03", "18:05"))
        self.assertEqual(coros._date("2026-11-03 18:05:00"), ("2026-11-03", "18:05"))
        self.assertEqual(coros._date(None), (None, ""))
        self.assertEqual([coros.sport_pilote(x) for x in (100, 102, 104, 201, 301, 402, 900, "trail_running")],
                         ["course", "course", "rando", "velo", "natation", "muscu", "autre", "course"])


if __name__ == "__main__":
    unittest.main()
