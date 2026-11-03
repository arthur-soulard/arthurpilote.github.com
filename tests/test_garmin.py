"""Tests du module Garmin (`python -m unittest discover -s tests`).

Pilote parle a un faux serveur local construit d'apres la documentation de
l'API personnelle de Garmin (Swagger de developer.garmin.com, octobre 2026) et
le client Python officiel (github.com/garmin/connect-personal-api-python) :
jeton = JWT en texte brut, rendu par POST avec « Authorization: ApiKey »,
puis donnees en GET avec « Authorization: Bearer ».
`storage.get_app_dir` est remplace pendant ces tests seulement (setUpClass) :
jamais `Donnees/`, et pas de remplacement au chargement du fichier, qui
prendrait le pas sur celui de test_donnees (charge avant lui par discover).
"""
import base64
import datetime
import json
import sys
import tempfile
import threading
import time
import unittest
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "src"))

import storage  # noqa: E402

_TMP = Path(tempfile.mkdtemp(prefix="pilote_tests_garmin_"))

import actus  # noqa: E402
import garmin  # noqa: E402

if sys.platform != "win32":
    # Trousseau du Mac : hors sujet ici (essayé par le test Mac de l'app)
    actus._chiffrer = lambda mdp, *a: "b64:" + base64.b64encode(mdp.encode()).decode()
    actus._oublier = lambda *a: None

CLE = "gpk_essai-0123456789abcdef"
AUJ = datetime.date.today()


def _iso(n):
    return (AUJ - datetime.timedelta(days=n)).isoformat()


def _jwt():
    tete = base64.urlsafe_b64encode(b'{"alg":"none"}').decode().rstrip("=")
    corps = base64.urlsafe_b64encode(json.dumps({"exp": time.time() + 86400}).encode()).decode().rstrip("=")
    return tete + "." + corps + ".signature"


class _Garmin(BaseHTTPRequestHandler):
    jeton = _jwt()
    requetes = []
    pannes = {}             # morceau de chemin -> statut renvoye
    activites = []
    cycle = None            # resume du cycle menstruel (None : 204, rien de suivi)

    def log_message(self, *a):
        pass

    def _repondre(self, statut, corps=b"", type_="application/json"):
        self.send_response(statut)
        self.send_header("Content-Type", type_)
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)

    def do_POST(self):
        _Garmin.requetes.append(("POST", self.path))
        if self.path != garmin.JETON:
            return self._repondre(404)
        if self.headers.get("Authorization") != "ApiKey " + CLE:
            return self._repondre(401, b'{"message":"invalid key"}')
        self._repondre(200, _Garmin.jeton.encode(), "text/plain")

    def do_GET(self):
        u = urllib.parse.urlsplit(self.path)
        q = dict(urllib.parse.parse_qsl(u.query))
        _Garmin.requetes.append(("GET", self.path))
        if self.headers.get("Authorization") != "Bearer " + _Garmin.jeton:
            return self._repondre(401)
        for morceau, statut in _Garmin.pannes.items():
            if morceau in u.path:
                return self._repondre(statut)
        p = u.path
        if p == "/activitylist-service/activities/search/activities":
            debut, fin = q.get("startDate", "0000"), q.get("endDate", "9999")
            l = [a for a in _Garmin.activites if debut <= a["startTimeLocal"][:10] <= fin]
            s, n = int(q.get("start", 0)), int(q.get("limit", 99))
            return self._repondre(200, json.dumps(l[s:s + n]).encode())
        if p.startswith("/weight-service/weight/all/"):
            return self._repondre(200, json.dumps([
                {"date": _iso(3) + "T07:12:00.000", "calendarDate": _iso(3), "weight": 72.43,
                 "bmi": 23.1, "bodyFat": 17.6, "bodyWater": 58.2, "boneMass": 3100,
                 "timestampGMT": _iso(3) + "T06:12:00.000+0000"},
                {"calendarDate": _iso(1), "weight": 72100, "timestampGMT": _iso(1) + "T06:00:00.000+0000"},
                {"calendarDate": _iso(2), "weight": 4.0},          # hors bornes : ignorée
            ]).encode())
        if p == "/usersummary-service/v2/dailysummaries":
            return self._repondre(200, json.dumps({"data": [
                {"calendarDate": _iso(1), "movement": {"steps": {"value": 8412, "goal": 10000}},
                 "heartRate": {"restingValue": 52}, "stress": {"avgLevel": 31},
                 "bodyBattery": {"maxValue": 88, "minValue": 21, "latestValue": 40},
                 "intensityMinutes": {"moderate": 20, "vigorous": 10, "goal": 150},
                 "pulseOx": {"avgValue": 96}, "respiration": {"avgValue": 14}},
                {"calendarDate": _iso(0), "movement": {"steps": {"value": 1200, "goal": 10000}}},
            ]}).encode())
        if p == "/sleep-service/sleep/dailySleepSummariesByDate":
            return self._repondre(200, json.dumps([
                {"calendarDate": _iso(0), "sleepTimeSeconds": 26100, "deepSleepSeconds": 4800,
                 "remSleepSeconds": 5400, "sleepScores": {"overall": {"value": 82, "qualifierKey": "GOOD"}}},
            ]).encode())
        if p.startswith("/fitnessage-service/fitnessage/v2/"):
            return self._repondre(200, json.dumps([
                {"chronologicalAge": 21, "fitnessAge": 19.43, "achievableFitnessAge": 18.0}]).encode())
        if p.startswith("/periodichealth-service/menstrualcycle/summary/"):
            if _Garmin.cycle is None:
                return self._repondre(204)
            return self._repondre(200, json.dumps(_Garmin.cycle).encode())
        if p.startswith("/hrv-service/hrv/daily/"):
            return self._repondre(200, json.dumps({"hrvSummaries": [
                {"calendarDate": _iso(0), "lastNightAvg": 54, "weeklyAvg": 50, "status": "BALANCED"},
            ]}).encode())
        self._repondre(404)


def _activite(ident, jours, type_, secondes, metres=0, d_plus=0, nom="", **autres):
    debut = _iso(jours) + " 18:05:42"
    return {"activityId": ident, "activityName": nom, "startTimeLocal": debut,
            "activityType": {"typeId": 1, "typeKey": type_, "parentTypeId": 17},
            "duration": secondes, "distance": metres, "elevationGain": d_plus, **autres}


class TestGarmin(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app_dir = storage.get_app_dir
        storage.get_app_dir = lambda: _TMP          # jamais les vraies données
        cls.serveur = ThreadingHTTPServer(("127.0.0.1", 0), _Garmin)
        threading.Thread(target=cls.serveur.serve_forever, daemon=True).start()
        garmin.BASE = f"http://127.0.0.1:{cls.serveur.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.serveur.shutdown()
        storage.get_app_dir = cls.app_dir

    def setUp(self):
        _Garmin.requetes.clear()
        _Garmin.pannes.clear()
        _Garmin.cycle = None
        _Garmin.activites = [
            _activite(101, 2, "trail_running", 3725.4, 10520.7, 412.3, "Trail du dimanche",
                      averageHR=151.6, calories=812, isPR=True),
            _activite(102, 1, "lap_swimming", 1800, 1500, poolLength=25),
            _activite(103, 1, "road_biking", 5400, 42195),
            _activite(104, 0, "strength_training", 2700),
            _activite(105, 0, "yoga", 3600),
            _activite(106, 90, "running", 1800, 5000),        # avant « depuis » : jamais lue
        ]
        garmin._jeton.update(cle="", valeur="", fin=0.0)
        for f in storage.get_user_dir().glob("*.json"):
            f.unlink()

    def _connecter(self, depuis=None):
        return garmin.connecter("  " + CLE + "\n", depuis or _iso(30))

    def test_mauvaise_cle(self):
        with self.assertRaises(garmin.ErreurGarmin) as e:
            garmin.connecter("pas-la-bonne", "")
        self.assertEqual(e.exception.code, "auth")
        self.assertFalse(garmin.config()["connecte"])

    def test_saisie_vide_ou_etrange(self):
        for cle in ("", "   ", "é" * 10):
            with self.assertRaises(garmin.ErreurGarmin) as e:
                garmin.connecter(cle, "")
            self.assertEqual(e.exception.code, "saisie")
        self.assertEqual(_Garmin.requetes, [])

    def test_cle_jamais_en_clair(self):
        self._connecter()
        brut = (storage.get_user_dir() / "garmin.json").read_text(encoding="utf-8")
        self.assertNotIn(CLE, brut)
        self.assertNotIn(CLE, json.dumps(garmin.config()))
        self.assertTrue(garmin.config()["connecte"])

    def test_synchronisation(self):
        self._connecter()
        r = garmin.synchroniser()
        self.assertEqual(r["erreurs"], [])
        par_id = {s["garminId"]: s for s in r["seances"]}
        self.assertEqual(sorted(par_id), ["101", "102", "103", "104", "105"])   # 106 : avant « depuis »
        trail = par_id["101"]
        self.assertEqual((trail["sport"], trail["date"], trail["time"]), ("course", _iso(2), "18:05"))
        self.assertEqual((trail["duration"], trail["distance"], trail["elevation"]), (62, 10.52, 412))
        self.assertEqual((trail["note"], trail["fcMoy"], trail["kcal"]), ("Trail du dimanche", 152, 812))
        self.assertTrue(trail["record"])
        self.assertNotIn("record", par_id["103"])
        nage = par_id["102"]
        self.assertEqual((nage["sport"], nage["distance"], nage["lieu"]), ("natation", 1500, "25"))
        self.assertEqual(par_id["103"]["sport"], "velo")
        self.assertEqual((par_id["104"]["sport"], par_id["104"]["distance"]), ("muscu", 0))
        self.assertEqual(par_id["105"]["sport"], "autre")
        # Pesées : kg, grammes ramenés en kg, hors bornes écartée
        self.assertEqual([(m["date"], m["poids"]) for m in r["pesees"]], [(_iso(3), 72.4), (_iso(1), 72.1)])
        p = r["pesees"][0]
        self.assertEqual((p["time"], p["imc"], p["graisse"], p["eau"]), ("07:12", 23.1, 17.6, 58.2))
        # Forme gardée dans garmin.json
        j = garmin.config()["jours"]
        self.assertEqual(j[_iso(1)], {"pas": 8412, "objectifPas": 10000, "fcRepos": 52, "bbMax": 88,
                                      "bbMin": 21, "bbFin": 40, "stress": 31, "intensite": 40,
                                      "objectifIntensite": 150, "spo2": 96, "respiration": 14})
        self.assertEqual(garmin.config()["ageForme"], {"age": 19.4, "reel": 21, "atteignable": 18.0})
        self.assertIsNone(garmin.config()["cycle"])
        self.assertFalse(any("menstrual" in p for _, p in _Garmin.requetes))   # décoché par défaut
        self.assertEqual((j[_iso(0)]["sommeil"], j[_iso(0)]["sommeilScore"], j[_iso(0)]["profond"]), (435, 82, 80))
        self.assertEqual((j[_iso(0)]["vfc"], j[_iso(0)]["vfcStatut"]), (54, "BALANCED"))
        self.assertTrue(garmin.config()["derniere"])

    def test_vus_ne_reviennent_pas(self):
        self._connecter()
        r = garmin.synchroniser()
        garmin.marquer_vus([s["garminId"] for s in r["seances"]] + [m["garminId"] for m in r["pesees"]])
        r2 = garmin.synchroniser()
        self.assertEqual((r2["seances"], r2["pesees"]), ([], []))

    def test_relecture_partielle(self):
        """La seconde synchronisation ne relit que les derniers jours."""
        self._connecter(_iso(300))
        garmin.synchroniser()
        _Garmin.requetes.clear()
        garmin.synchroniser()
        recherches = [urllib.parse.parse_qs(urllib.parse.urlsplit(p).query)
                      for m, p in _Garmin.requetes if "activitylist" in p]
        self.assertEqual(recherches[0]["startDate"], [_iso(garmin.RECOUVREMENT)])
        self.assertFalse(any(m == "POST" for m, _ in _Garmin.requetes))     # jeton du jour réutilisé

    def test_une_source_en_panne(self):
        self._connecter()
        _Garmin.pannes["/sleep-service/"] = 500
        r = garmin.synchroniser()
        self.assertEqual(len(r["erreurs"]), 1)
        self.assertIn("Sommeil", r["erreurs"][0])
        self.assertEqual(len(r["seances"]), 5)
        self.assertEqual(garmin.config()["jours"][_iso(1)]["pas"], 8412)
        self.assertEqual(garmin.config()["derniere"], "")       # tout sera relu la fois suivante

    def test_cle_expiree(self):
        self._connecter()
        _Garmin.pannes["/activitylist-service/"] = 401
        with self.assertRaises(garmin.ErreurGarmin) as e:
            garmin.synchroniser()
        self.assertEqual(e.exception.code, "auth")

    def test_choix(self):
        self._connecter()
        garmin.regler({"seances": False, "pesees": True, "forme": False})
        r = garmin.synchroniser()
        self.assertEqual(r["seances"], [])
        self.assertEqual(len(r["pesees"]), 2)
        self.assertEqual(garmin.config()["jours"], {})
        self.assertFalse(any("activitylist" in p or "sleep" in p for _, p in _Garmin.requetes))

    def test_depuis_plus_tot_relit_tout(self):
        self._connecter(_iso(10))
        garmin.synchroniser()
        garmin.regler({"seances": True, "pesees": True, "forme": True}, _iso(120))
        self.assertEqual(garmin.config()["derniere"], "")
        r = garmin.synchroniser()
        self.assertIn("106", [s["garminId"] for s in r["seances"]])

    def test_deconnexion_garde_la_forme(self):
        self._connecter()
        garmin.synchroniser()
        garmin.deconnecter()
        c = garmin.config()
        self.assertFalse(c["connecte"])
        self.assertTrue(c["jours"])
        with self.assertRaises(garmin.ErreurGarmin) as e:
            garmin.synchroniser()
        self.assertEqual(e.exception.code, "config")

    def test_reseau_coupe(self):
        base, garmin.BASE = garmin.BASE, "http://127.0.0.1:9"
        try:
            with self.assertRaises(garmin.ErreurGarmin) as e:
                garmin.connecter(CLE, "")
            self.assertEqual(e.exception.code, "reseau")
        finally:
            garmin.BASE = base

    def test_cycle(self):
        self._connecter()
        garmin.regler({"seances": False, "pesees": False, "forme": False, "cycle": True})
        r = garmin.synchroniser()                     # rien de suivi dans Connect : 204
        self.assertEqual((r["erreurs"], r["cycle"]), ([], None))
        _Garmin.cycle = {"dayInCycle": 9, "predictedCycleLength": 28, "periodLength": 5,
                         "fertileWindowStart": 10, "lengthOfFertileWindow": 6, "lutealPhaseStart": 16,
                         "daysUntilNextPhase": 1, "pregnancyCycle": False}
        c = garmin.synchroniser()["cycle"]
        self.assertEqual((c["jour"], c["duree"], c["regles"], c["fertileDebut"], c["prochaine"], c["grossesse"]),
                         (9, 28, 5, 10, 1, False))
        garmin.regler({"cycle": False})              # décoché : rien ne reste
        self.assertIsNone(garmin.config()["cycle"])

    def test_age_physique_absent_n_est_pas_une_panne(self):
        self._connecter()
        _Garmin.pannes["/fitnessage-service/"] = 404
        r = garmin.synchroniser()
        self.assertEqual(r["erreurs"], [])
        self.assertIsNone(r["ageForme"])
        self.assertTrue(r["derniere"])

    def test_expiration_de_la_cle(self):
        garmin.connecter(CLE, "", 365)
        fin = (AUJ + datetime.timedelta(days=365)).isoformat()
        self.assertEqual(garmin.config()["expire"], fin)
        garmin.regler(garmin.config()["choix"], "", _iso(-20))      # corrigée à la main
        self.assertEqual(garmin.config()["expire"], _iso(-20))
        garmin.regler(garmin.config()["choix"])                     # None : inchangée
        self.assertEqual(garmin.config()["expire"], _iso(-20))
        garmin.connecter(CLE, "", 12)                               # durée que Garmin ne propose pas
        self.assertEqual(garmin.config()["expire"], "")

    def test_rappel_d_expiration_dans_l_agenda(self):
        import agenda
        garmin.connecter(CLE, "", 30)
        r = agenda.rappels({"garmin-cle": "semaine"}, {})
        self.assertEqual([(e["type"], e["jour"]) for e in r], [("garmin-cle", AUJ + datetime.timedelta(days=30))])
        self.assertEqual(agenda.rappels({}, {}), [])               # alerte pas réglée
        garmin.deconnecter()
        self.assertEqual(agenda.rappels({"garmin-cle": "semaine"}, {}), [])

    def test_sport_pilote(self):
        for t, s in [("running", "course"), ("treadmill_running", "course"), ("open_water_swimming", "natation"),
                     ("mountain_biking", "velo"), ("indoor_cycling", "velo"), ("virtual_ride", "velo"),
                     ("hiking", "rando"), ("soccer", "foot"), ("walking", "autre"), ("", "autre")]:
            self.assertEqual(garmin.sport_pilote(t), s, t)


if __name__ == "__main__":
    unittest.main()
