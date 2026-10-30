"""Tests du module Agenda (`python -m unittest discover -s tests`).

Pilote parle a un faux serveur CalDAV local, construit comme celui d'iCloud
(premiere adresse redirigee, dossier des agendas sur un autre chemin en
adresse absolue, boite de reception et listes de Rappels a ecarter).
`storage.get_app_dir` est remplace AVANT tout appel : jamais `Donnees/`.
"""
import base64
import json
import re
import sys
import tempfile
import threading
import unittest
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "src"))

import storage  # noqa: E402

_TMP = Path(tempfile.mkdtemp(prefix="pilote_tests_agenda_"))
storage.get_app_dir = lambda: _TMP          # jamais les vraies données

import actus  # noqa: E402
import agenda  # noqa: E402
import pret  # noqa: E402
import sports  # noqa: E402

if sys.platform != "win32":
    # Trousseau du Mac : hors sujet ici (essayé par le test Mac de l'app)
    actus._chiffrer = lambda mdp, *a: "b64:" + base64.b64encode(mdp.encode()).decode()
    actus._oublier = lambda *a: None

ID, MDP = "camille@icloud.com", "abcdefghijklmnop"


class _ICloud(BaseHTTPRequestHandler):
    """Agendas : {chemin: {"nom", "comps", "fichiers": {nom: texte}}}."""
    agendas = {}
    requetes = []

    def log_message(self, *a):
        pass

    def _repondre(self, statut, corps=b"", entetes=None):
        self.send_response(statut)
        for k, v in (entetes or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)

    def _xml(self, reponses):
        corps = ('<?xml version="1.0"?><d:multistatus xmlns:d="DAV:" '
                 'xmlns:c="urn:ietf:params:xml:ns:caldav">' + "".join(
                     f"<d:response><d:href>{h}</d:href><d:propstat><d:prop>{p}</d:prop>"
                     "</d:propstat></d:response>" for h, p in reponses) + "</d:multistatus>")
        self._repondre(207, corps.encode("utf-8"))

    def _autorise(self):
        attendu = "Basic " + base64.b64encode(f"{ID}:{MDP}".encode()).decode()
        if self.headers.get("Authorization") != attendu:
            self._repondre(401)
            return False
        return True

    def _corps(self):
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n).decode("utf-8") if n else ""

    def do_PROPFIND(self):
        type(self).requetes.append(("PROPFIND", self.path))
        if not self._autorise():
            return
        self._corps()
        hote = f"http://127.0.0.1:{self.server.server_address[1]}"
        if self.path == "/":
            return self._repondre(301, entetes={"Location": "/racine/"})
        if self.path == "/racine/":
            return self._xml([("/racine/", "<d:current-user-principal><d:href>/123/principal/"
                                           "</d:href></d:current-user-principal>")])
        if self.path == "/123/principal/":
            return self._xml([(self.path, f"<c:calendar-home-set><d:href>{hote}/123/calendars/"
                                          "</d:href></c:calendar-home-set>")])
        if self.path == "/123/calendars/":
            rep = [("/123/calendars/", "<d:resourcetype><d:collection/></d:resourcetype>"),
                   ("/123/calendars/inbox/", "<d:resourcetype><d:collection/>"
                                             "<c:schedule-inbox/></d:resourcetype>")]
            for chemin, a in self.agendas.items():
                comps = "".join(f'<c:comp name="{c}"/>' for c in a["comps"])
                couleur = (f'<x:calendar-color xmlns:x="http://apple.com/ns/ical/">{a["couleur"]}'
                           "</x:calendar-color>") if a.get("couleur") else ""
                rep.append((chemin, f"<d:displayname>{a['nom']}</d:displayname>{couleur}<d:resourcetype>"
                                    "<d:collection/><c:calendar/></d:resourcetype>"
                                    f"<c:supported-calendar-component-set>{comps}"
                                    "</c:supported-calendar-component-set>"))
            return self._xml(rep)
        if self.path in self.agendas:
            return self._xml([(self.path, "<d:resourcetype><c:calendar/></d:resourcetype>")]
                             + [(self.path + urllib.parse.quote(n), '<d:getetag>"1"</d:getetag>')
                                for n in self.agendas[self.path]["fichiers"]])
        self._repondre(404)

    def do_REPORT(self):
        """calendar-query : tout le contenu de l'agenda, sans tri par date (le
        filtre est refait par Pilote), comme un serveur qui ignore expand."""
        type(self).requetes.append(("REPORT", self.path))
        if not self._autorise():
            return
        self._corps()
        a = self.agendas.get(self.path)
        if a is None:
            return self._repondre(404)
        self._xml([(self.path + urllib.parse.quote(n),
                    "<c:calendar-data>" + t.replace("&", "&amp;").replace("<", "&lt;")
                    + "</c:calendar-data>") for n, t in a["fichiers"].items()])

    def do_MKCALENDAR(self):
        type(self).requetes.append(("MKCALENDAR", self.path))
        if not self._autorise():
            return
        nom = re.search(r"<d:displayname>(.*?)</d:displayname>", self._corps()).group(1)
        self.agendas[self.path] = {"nom": nom, "comps": ["VEVENT"], "fichiers": {}}
        self._repondre(201)

    def _fichier(self):
        chemin, _, nom = self.path.rpartition("/")
        return self.agendas.get(chemin + "/"), urllib.parse.unquote(nom)

    def do_PUT(self):
        type(self).requetes.append(("PUT", self.path))
        if not self._autorise():
            return
        a, nom = self._fichier()
        if a is None:
            return self._repondre(404)
        a["fichiers"][nom] = self._corps()
        self._repondre(201)

    def do_DELETE(self):
        type(self).requetes.append(("DELETE", self.path))
        if not self._autorise():
            return
        if self.path in self.agendas:
            del self.agendas[self.path]
            return self._repondre(204)
        a, nom = self._fichier()
        if a is None or nom not in a["fichiers"]:
            return self._repondre(404)
        del a["fichiers"][nom]
        self._repondre(204)


class TestAgenda(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.serveur = ThreadingHTTPServer(("127.0.0.1", 0), _ICloud)
        threading.Thread(target=cls.serveur.serve_forever, daemon=True).start()
        agenda.BASE = f"http://127.0.0.1:{cls.serveur.server_address[1]}/"
        agenda.planifier = lambda delai=3: None   # les tests synchronisent eux-mêmes

    @classmethod
    def tearDownClass(cls):
        cls.serveur.shutdown()

    def setUp(self):
        _ICloud.agendas.clear()
        _ICloud.agendas["/123/calendars/perso/"] = {
            "nom": "Perso", "comps": ["VEVENT"],
            "fichiers": {"evenement-a-moi.ics": "BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n"}}
        _ICloud.agendas["/123/calendars/rappels/"] = {"nom": "Rappels", "comps": ["VTODO"],
                                                      "fichiers": {}}
        _ICloud.requetes.clear()
        for f in storage.get_user_dir().glob("*.json"):
            f.unlink()
        sports.save_data({
            "sessions": [
                {"id": 1, "date": "2026-10-20", "time": "18:30", "sport": "course",
                 "duration": 45, "distance": 8.5, "subtype": "Footing", "note": "Parc, 3 tours"},
                {"id": 2, "date": "2026-10-21", "time": "", "sport": "natation",
                 "duration": 30, "distance": 1500},
            ],
            "goals": [
                {"id": 1, "kind": "event", "title": "Semi-marathon", "date": "2026-11-15",
                 "status": "active"},
                {"id": 2, "kind": "perf", "title": "10 km en 45 min", "status": "active"},
            ]})
        p = pret.load_data()
        p["pret"].update(nom="Prêt étudiant", date_premier_remboursement="2027-01-05",
                         duree_remboursement=60, mensualite=250)
        pret.save_data(p)

    def _fichiers(self, chemin):
        return _ICloud.agendas[chemin]["fichiers"]

    def test_mauvais_mot_de_passe(self):
        with self.assertRaises(agenda.ErreurAgenda) as e:
            agenda.connecter(ID, "faux")
        self.assertEqual(e.exception.code, "auth")
        self.assertFalse(agenda.config()["connecte"])   # rien d'enregistré

    def test_connexion_et_envoi(self):
        r = agenda.connecter(ID, "abcd-efgh ijkl mnop".replace("-", " "))
        self.assertTrue(r["connecte"])
        # Les Rappels et la boîte de réception ne sont pas des agendas d'événements
        self.assertEqual([c["nom"] for c in r["calendriers"]], ["Perso"])
        brut = json.loads((storage.get_user_dir() / "agenda.json").read_text("utf-8"))
        self.assertNotIn(MDP, json.dumps(brut))         # le code n'est jamais en clair

        agenda.regler("nouveau", {"sport": True, "objectifs": True, "pret": True})
        cal = agenda.config()["calendrier"]
        self.assertEqual(_ICloud.agendas[urllib.parse.urlparse(cal).path]["nom"], "Pilote")
        etat = agenda.synchroniser()
        self.assertEqual(etat["nb"], 4)
        f = self._fichiers(urllib.parse.urlparse(cal).path)
        self.assertEqual(len(f), 4)
        seance = next(t for n, t in f.items() if n.endswith("-sport-1.ics"))
        self.assertIn("DTSTART:20261020T183000", seance)
        self.assertIn("DTEND:20261020T191500", seance)
        self.assertIn("Footing · 8\\,5 km", seance)     # virgule échappée (RFC 5545)
        self.assertIn("DESCRIPTION:Parc\\, 3 tours", seance)
        nage = next(t for n, t in f.items() if n.endswith("-sport-2.ics"))
        self.assertIn("DTSTART;VALUE=DATE:20261021", nage)
        self.assertIn("1500 m", nage)
        mens = next(t for n, t in f.items() if n.endswith("-pret.ics"))
        self.assertIn("RRULE:FREQ=MONTHLY;COUNT=60", mens)
        self.assertIn("250\\,00 €", mens)
        self.assertTrue(all(len(l.encode()) <= 75 for t in f.values() for l in t.split("\r\n")))

        # Rien de changé : aucun envoi
        _ICloud.requetes.clear()
        agenda.synchroniser()
        self.assertEqual([m for m, _ in _ICloud.requetes if m in ("PUT", "DELETE")], [])

        # Une séance supprimée, une modifiée, le prêt décoché
        sp = sports.load_data()
        sp["sessions"] = [dict(sp["sessions"][0], duration=60)]
        sports.save_data(sp)
        agenda.regler(cal, {"sport": True, "objectifs": True, "pret": False})
        _ICloud.requetes.clear()
        agenda.synchroniser()
        self.assertEqual(sorted(n.split("-", 2)[2] for n in f), ["objectif-1.ics", "sport-1.ics"])
        self.assertEqual(sum(1 for m, _ in _ICloud.requetes if m == "PUT"), 1)
        self.assertIn("DTEND:20261020T193000", next(iter(t for n, t in f.items() if "sport-1" in n)))

        # Changement d'agenda : l'agenda « Pilote » quitté est supprimé, tout
        # arrive dans le nouveau ; l'événement qui n'est pas de Pilote reste
        perso = r["calendriers"][0]["url"]
        agenda.regler(perso, {"sport": True, "objectifs": True, "pret": False})
        agenda.synchroniser()
        self.assertNotIn(urllib.parse.urlparse(cal).path, _ICloud.agendas)
        self.assertEqual(len(self._fichiers("/123/calendars/perso/")), 3)

        # Puis vers un autre agenda à soi : Perso est vidé de ce que Pilote y a mis
        _ICloud.agendas["/123/calendars/sport/"] = {"nom": "Sport", "comps": ["VEVENT"], "fichiers": {}}
        agenda.regler(agenda.calendriers()[-1]["url"], {"sport": True, "objectifs": True})
        agenda.synchroniser()
        self.assertEqual(list(self._fichiers("/123/calendars/perso/")), ["evenement-a-moi.ics"])
        self.assertEqual(len(self._fichiers("/123/calendars/sport/")), 2)
        agenda.regler(perso, {"sport": True, "objectifs": True})
        agenda.synchroniser()

        # Déconnexion : ce que Pilote a mis repart, le reste ne bouge pas
        r = agenda.deconnecter()
        self.assertFalse(r["connecte"])
        self.assertEqual(r["avertissement"], "")
        self.assertEqual(list(self._fichiers("/123/calendars/perso/")), ["evenement-a-moi.ics"])

    def test_deconnexion_supprime_agenda_pilote(self):
        agenda.connecter(ID, MDP)
        agenda.regler("nouveau", {"sport": True})
        agenda.synchroniser()
        chemin = urllib.parse.urlparse(agenda.config()["calendrier"]).path
        agenda.deconnecter()
        self.assertNotIn(chemin, _ICloud.agendas)
        self.assertIn("/123/calendars/perso/", _ICloud.agendas)

    def test_notes_et_calendrier(self):
        agenda.enregistrer_notes([
            {"id": "n1", "titre": "Dentiste", "date": "2026-10-28", "heure": "14:00", "duree": 30,
             "texte": "Cabinet, 2e étage"},
            {"id": "../x", "titre": "Rendre le livre", "date": "2026-10-30"},
            {"id": "n3", "titre": "sans date"},
        ])
        notes = agenda.config()["notes"]
        self.assertEqual([n["id"] for n in notes], ["n1", "x"])   # id nettoyé, note sans date écartée

        # Les notes partent dans l'agenda, même sans aucune case cochée
        agenda.connecter(ID, MDP)
        agenda.regler("nouveau", {})
        self.assertEqual(agenda.synchroniser()["nb"], 2)
        f = self._fichiers(urllib.parse.urlparse(agenda.config()["calendrier"]).path)
        dent = next(t for n, t in f.items() if n.endswith("-note-n1.ics"))
        self.assertIn("DTSTART:20261028T140000", dent)
        self.assertIn("DTEND:20261028T143000", dent)

    def test_note_sans_attendre_un_envoi_en_cours(self):
        """Cas vu le 22/10/2026 : la note attendait la fin de l'envoi des séances."""
        import time
        tenu, lacher = threading.Event(), threading.Event()

        def envoi_long():   # un envoi en cours tient le verrou des échanges avec iCloud
            with agenda._verrou:
                tenu.set()
                lacher.wait(10)
        threading.Thread(target=envoi_long, daemon=True).start()
        tenu.wait(5)
        t = time.time()
        agenda.enregistrer_notes([{"id": "n1", "titre": "Vite", "date": "2026-10-28"}])
        duree = time.time() - t
        lacher.set()
        self.assertLess(duree, 1)
        self.assertEqual(agenda.config()["notes"][0]["titre"], "Vite")

        # Et à l'envoi, la note passe avant les séances ; l'envoi ne l'écrase pas
        agenda.connecter(ID, MDP)
        agenda.regler("nouveau", {"sport": True})
        _ICloud.requetes.clear()
        agenda.synchroniser()
        puts = [p for m, p in _ICloud.requetes if m == "PUT"]
        self.assertTrue(puts[0].endswith("-note-n1.ics"))
        self.assertEqual(len(agenda.config()["notes"]), 1)

    def test_lire_les_autres_agendas(self):
        perso = self._fichiers("/123/calendars/perso/")
        perso["anniv.ics"] = ("BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nUID:a\r\nSUMMARY:Anniversaire\\, Léa\r\n"
                              "DTSTART;VALUE=DATE:20261024\r\nDTEND;VALUE=DATE:20261026\r\nEND:VEVENT\r\n"
                              "END:VCALENDAR\r\n")
        perso["reunion.ics"] = ("BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nUID:b\r\nSUMMARY:Réunion du pro\r\n"
                                " jet\r\nDTSTART;TZID=Europe/Paris:20261027T090000\r\nDURATION:PT1H30M\r\n"
                                "END:VEVENT\r\nEND:VCALENDAR\r\n")
        perso["annule.ics"] = ("BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nUID:c\r\nSUMMARY:Annulé\r\nSTATUS:CANCELLED\r\n"
                               "DTSTART:20261027T100000\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n")
        perso["loin.ics"] = ("BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nUID:d\r\nSUMMARY:Plus tard\r\n"
                             "DTSTART:20270101T100000\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n")
        agenda.connecter(ID, MDP)
        agenda.regler(agenda.calendriers()[0]["url"], {"objectifs": True})   # Pilote écrit dans Perso
        agenda.enregistrer_notes([{"id": "n1", "titre": "Ma note", "date": "2026-10-20"}])
        agenda.synchroniser()
        ev = agenda.icloud("2026-10-01", "2026-11-30")
        # Ce que montre le téléphone, objectif envoyé par Pilote compris ; la
        # note de Pilote est sautée (la page l'affiche elle-même)
        self.assertEqual([e["titre"] for e in ev], ["Anniversaire, Léa", "Réunion du projet",
                                                    "🎯 Semi-marathon"])
        self.assertEqual((ev[0]["debut"], ev[0]["fin"], ev[0]["heure"]), ("2026-10-24", "2026-10-25", ""))
        self.assertEqual((ev[1]["heure"], ev[1]["heureFin"], ev[1]["agenda"]), ("09:00", "10:30", "Perso"))
        with self.assertRaises(agenda.ErreurAgenda):
            agenda.icloud("2026-01-01", "2026-12-31")   # une année d'un coup : refusé

    def test_heure_utc_ramenee_au_pc(self):
        ev = agenda.lire_ics("BEGIN:VEVENT\r\nSUMMARY:x\r\nDTSTART:20260715T080000Z\r\n"
                             "DTEND:20260715T090000Z\r\nEND:VEVENT\r\n")[0]
        import datetime
        attendu = datetime.datetime(2026, 7, 15, 8, tzinfo=datetime.timezone.utc).astimezone()
        self.assertEqual(ev["heure"], attendu.strftime("%H:%M"))

    def test_icloud_injoignable(self):
        agenda.connecter(ID, MDP)
        agenda.regler("nouveau", {"sport": True})
        base, agenda.BASE = agenda.BASE, "http://127.0.0.1:9/"
        # L'agenda est déjà connu : l'envoi va droit au serveur des agendas,
        # on coupe donc le serveur lui-même
        cal = agenda.config()["calendrier"]
        data = agenda._store.load()
        data["calendrier"] = cal.replace(str(self.serveur.server_address[1]), "9")
        agenda._store.save(data)
        with self.assertRaises(agenda.ErreurAgenda) as e:
            agenda.synchroniser()
        agenda.BASE = base
        self.assertEqual(e.exception.code, "reseau")
        self.assertIn("ne répond pas", agenda.config()["etat"]["erreur"])

    def test_alertes_sur_les_evenements(self):
        agenda.connecter(ID, MDP)
        agenda.regler("nouveau", {"sport": True, "objectifs": True, "pret": True})
        agenda.enregistrer_notes([{"id": "n1", "titre": "Dentiste", "date": "2026-10-30", "heure": "08:00"}])
        r = agenda.regler_alertes({"sport": "30", "objectif": "veille", "pret": "matin",
                                   "note": "matin", "inconnu": "15"}, {"pesee": 40})
        self.assertNotIn("inconnu", r["alertes"])
        self.assertEqual(r["jours"]["pesee"], 28)                 # borné au 28
        self.assertEqual(agenda.regler_alertes({"sport": "999"}, {})["alertes"]["sport"], "")
        agenda.regler_alertes({"sport": "30", "objectif": "veille", "pret": "matin", "note": "matin"}, {})
        agenda.synchroniser()
        f = self._fichiers(urllib.parse.urlparse(agenda.config()["calendrier"]).path)
        t = {n.split("-", 2)[2][:-4]: v for n, v in f.items()}
        self.assertIn("BEGIN:VALARM\r\nACTION:DISPLAY\r\n", t["sport-1"])
        self.assertIn("TRIGGER:-PT30M", t["sport-1"])            # 18 h 30 : 30 min avant
        self.assertIn("TRIGGER:PT9H", t["sport-2"])              # sans heure : 9 h le jour même
        self.assertIn("TRIGGER:-PT6H", t["objectif-1"])          # la veille à 18 h
        self.assertIn("TRIGGER:PT9H", t["pret"])                 # chaque mois, relatif au début
        self.assertIn("TRIGGER:PT0S", t["note-n1"])              # 8 h : avant 9 h, à l'heure
        # La description de l'alerte ne remplace pas celle de l'événement
        self.assertIn("DESCRIPTION:Ajouté par Pilote.", t["objectif-1"])
        self.assertEqual(agenda.lire_ics(t["objectif-1"])[0]["titre"], "🎯 Semi-marathon")
        # Alerte changée : seul l'événement concerné repart
        _ICloud.requetes.clear()
        agenda.regler_alertes({"sport": "30", "objectif": "veille", "pret": "matin", "note": "60"}, {})
        agenda.synchroniser()
        self.assertEqual(sum(1 for m, _ in _ICloud.requetes if m == "PUT"), 1)
        self.assertNotIn("VALARM", agenda._ics("x", ["SUMMARY:x"]).decode())

    def test_rappels_du_mois_et_du_pea(self):
        import datetime
        import patrimoine
        import sante
        auj = datetime.date.today()
        mois_suivant = (auj.replace(day=1) + datetime.timedelta(days=32)).replace(day=5)
        alertes = {"pesee": "matin", "releve": "veille", "versement": "matin", "dividende": "veille"}
        jours = {"pesee": 5, "releve": 1}
        # Rien de saisi : pas de pesée ni de relevé à rappeler, PEA absent
        self.assertEqual(agenda.rappels(alertes, jours), [])

        sante.save_data({"mesures": [{"id": 1, "date": "2025-01-10", "poids": 70}]})
        patrimoine.save_data({"comptes": [{"id": "c1", "label": "Livret A", "type": "livret"}],
                              "releves": []})
        (storage.get_user_dir() / "pea_data.json").write_text(json.dumps({
            "positions": [{"ticker": "EPA:CW8", "name": "Amundi MSCI World"}],
            "depotsPrevus": [{"id": 7, "date": "2026-11-02", "amount": 300}],
            "divFuture": [{"id": "d1", "date": "2026-12-10", "ticker": "EPA:CW8", "montant": 12.5}],
        }), "utf-8")
        ev = agenda.evenements({}, {}, {}, [], alertes, agenda.rappels(alertes, jours))
        self.assertEqual(sorted(ev), ["dividende-d1", "pesee", "releve", "versement-7"])
        self.assertIn("DTSTART;VALUE=DATE:" + auj.replace(day=5).strftime("%Y%m%d"), ev["pesee"])
        self.assertIn("RRULE:FREQ=MONTHLY", ev["pesee"])
        self.assertIn("TRIGGER:-PT6H", ev["releve"])
        self.assertIn("SUMMARY:💶 Versement PEA prévu · 300\\,00 €", ev["versement-7"])
        self.assertIn("SUMMARY:💶 Dividende · Amundi MSCI World · 12\\,50 €", ev["dividende-d1"])

        # Pesée et relevé faits ce mois-ci : le rappel passe au mois suivant
        sante.save_data({"mesures": [{"id": 1, "date": auj.isoformat(), "poids": 70}]})
        patrimoine.save_data({"comptes": [{"id": "c1", "label": "Livret A", "type": "livret"}],
                              "releves": [{"id": 1, "compteId": "c1", "date": patrimoine.mois_courant(),
                                           "montant": 100}]})
        ev = agenda.evenements({}, {}, {}, [], alertes, agenda.rappels(alertes, jours))
        self.assertIn("DTSTART;VALUE=DATE:" + mois_suivant.strftime("%Y%m%d"), ev["pesee"])
        self.assertIn("DTSTART;VALUE=DATE:" + mois_suivant.replace(day=1).strftime("%Y%m%d"), ev["releve"])
        # Sans alerte, un rappel ne part pas
        self.assertEqual(agenda.rappels({}, jours), [])

    def test_planifier_seulement_si_un_rappel_part(self):
        appels = []
        avant, agenda.planifier = agenda.planifier, lambda delai=3: appels.append(delai)
        try:
            agenda.planifier_si("versement", "dividende")
            self.assertEqual(appels, [])
            agenda.regler_alertes({"dividende": "matin"}, {})
            appels.clear()
            agenda.planifier_si("versement", "dividende")
            agenda.planifier_si("pesee")
            self.assertEqual(appels, [3])
        finally:
            agenda.planifier = avant

    def test_catalogue_des_rappels(self):
        import datetime
        import cto
        import finances
        import sante
        import sauvegarde
        auj = datetime.date.today()
        j = lambda n: (auj + datetime.timedelta(days=n)).isoformat()
        dem = auj + datetime.timedelta(days=1)
        mois_suivant = (auj.replace(day=1) + datetime.timedelta(days=32)).replace(day=5)
        sante.save_data({"mesures": [{"id": 1, "date": j(-20), "poids": 70}],
                         "goals": [{"id": 3, "metric": "poids", "target": 68.5, "date": j(30), "status": "active"},
                                   {"id": 4, "metric": "poids", "target": 60, "date": j(-3), "status": "active"}]})
        (storage.get_user_dir() / "pea_data.json").write_text(json.dumps({
            "config": {"ouverture": dem.replace(year=dem.year - 5).isoformat()},
            "positions": [{"ticker": "EPA:CW8", "name": "Amundi MSCI World"}],
            "transactions": [{"id": 1, "type": "Achat", "date": auj.isoformat()}],
            "depots": [{"id": 1, "date": (auj.replace(day=1) - datetime.timedelta(days=1)).isoformat()}],
            "plansProg": [{"id": 1, "ticker": "EPA:CW8", "montant": 100, "prochaine": j(3)},
                          {"id": 2, "ticker": "EPA:CW8", "montant": 50, "prochaine": j(-1)}],
        }), "utf-8")
        cto.save_data({"comptes": [{"id": "c2", "nom": "TR", "transactions": [],
                                    "positions": [{"ticker": "AAPL", "name": "Apple"}],
                                    "plansProg": [{"id": 7, "ticker": "AAPL", "montant": 25, "prochaine": j(4)}],
                                    "divFuture": [{"id": "x", "date": j(10), "ticker": "AAPL", "montant": 1.2}]}]})
        finances.save_data({"transactions": [{"id": 1, "createdAt": j(-40) + "T10:00:00"}],
                            "recurrences": [{"id": 5, "label": "Loyer", "type": "expense", "amount": 450,
                                             "nextDue": j(5), "status": "active"},
                                            {"id": 6, "label": "En pause", "type": "expense", "amount": 9,
                                             "nextDue": j(5), "status": "paused"}]})
        sauvegarde.save_config(dict(sauvegarde.load_config(), lastBackupAt=j(-40) + "T10:00:00"))
        sports.save_data({"sessions": [{"id": 1, "date": j(-2), "sport": "course"}]})
        p = pret.load_data()
        p["pret"].update(date_premier_remboursement=j(10), duree_remboursement=12)
        pret.save_data(p)

        tout = {t: "matin" for t in agenda.RAPPELS if t != "resume"}
        r = {e["cle"]: e for e in agenda.rappels(tout, {"pea-investir": 5},
                                                 {"sport-pause": 3, "ouvrir": 10, "sauvegarde": 999})}
        self.assertEqual(r["sante-pause"]["jour"], dem)                     # en retard : demain
        self.assertEqual(r["sante-pause"]["titre"], "⚖️ Pas de pesée depuis 21 jours")
        self.assertEqual(r["sante-objectif-3"]["titre"], "🎯 Poids · objectif 68,5 kg")
        self.assertNotIn("sante-objectif-4", r)                              # date passée
        self.assertEqual((r["pea-anniv"]["jour"], r["pea-anniv"]["titre"]), (dem, "🎂 Le PEA a 5 ans · cap des 5 ans"))
        self.assertEqual(r["pea-investir"]["jour"], mois_suivant)             # achat ce mois-ci
        self.assertEqual(r["pea-depot"]["jour"], auj.replace(day=1))          # pas de versement ce mois-ci
        self.assertEqual(r["cto-dividende-c2-x"]["titre"], "💶 Dividende · Apple · 1,20 € · CTO TR")
        self.assertEqual(r["cto-investir-c2"]["titre"], "📈 Investir ce mois · CTO TR")
        # Achats programmés : le prochain de chaque plan, pas une date passée
        self.assertEqual((r["pea-plan-1"]["jour"].isoformat(), r["pea-plan-1"]["titre"]),
                         (j(3), "🔁 Achat programmé · Amundi MSCI World · 100,00 €"))
        self.assertNotIn("pea-plan-2", r)
        self.assertEqual(r["cto-plan-c2-7"]["titre"], "🔁 Achat programmé · Apple · 25,00 € · CTO TR")
        self.assertEqual(r["fin-saisie"]["jour"], auj.replace(day=1))
        self.assertEqual(r["fin-recurrent-5"]["titre"], "🔁 Loyer · −450,00 €")
        self.assertNotIn("fin-recurrent-6", r)                               # en pause
        self.assertEqual(r["pret-premiere"]["jour"].isoformat(), j(10))
        self.assertEqual(r["pret-derniere"]["jour"], agenda._plus_mois(r["pret-premiere"]["jour"], 11))
        self.assertEqual((r["sport-pause"]["jour"], r["sport-pause"]["titre"]), (dem, "🏃 Pas de séance depuis 3 jours"))
        self.assertEqual(r["sauvegarde"]["titre"], "💾 Pas de sauvegarde depuis 41 jours")   # 999 → 30
        self.assertEqual(r["ouvrir"]["jour"].isoformat(), j(10))
        # Chaque rappel part dans l'agenda avec son alerte ; « semaine » sur une date
        ev = agenda.evenements({}, {}, {}, [], dict(tout, dividende="semaine", **{"cto-dividende": "semaine"}),
                               list(r.values()))
        self.assertIn("TRIGGER:-P6DT15H", ev["cto-dividende-c2-x"])
        self.assertIn("RRULE:FREQ=MONTHLY", ev["pea-investir"])
        self.assertEqual(len(ev), len(r))
        # Rien de réglé : rien ne part
        self.assertEqual(agenda.rappels({}, {}, {}), [])

    def test_resume_essai_et_prochaines(self):
        import datetime
        maintenant = datetime.datetime.now()
        auj = maintenant.date()
        notes = [{"id": f"n{i}", "titre": f"Note {i}", "date": (auj + datetime.timedelta(days=i)).isoformat()}
                 for i in range(15)]
        ev = agenda.evenements({}, {}, {}, notes, {"resume": "dimanche"}, [])
        self.assertIn("SUMMARY:🗓️ Ta semaine : 7 notes", ev["resume"])
        self.assertIn("TRIGGER:PT0S", ev["resume"])
        self.assertTrue(re.search(r"DTSTART:\d{8}T180000", "\n".join(ev["resume"])))
        e = agenda.retenus({}, {}, {}, [], {"resume": "lundi"})[0]
        self.assertEqual((e["debut"].weekday(), e["debut"].hour), (0, 8))
        self.assertGreater(e["debut"], maintenant)
        self.assertEqual(e["titre"], "🗓️ Ta semaine : rien de prévu dans Pilote")
        # Réglages acceptés par type
        propres = agenda._alertes_propres({"resume": "matin", "sport": "dimanche", "objectif": "semaine"})
        self.assertEqual((propres["resume"], propres["sport"], propres["objectif"]), ("", "", "semaine"))
        self.assertIn("TRIGGER:-PT10650M", agenda.evenements(           # 18 h 30, 9 h une semaine avant
            sports.load_data(), {}, {"sport": True}, [], {"sport": "semaine"})["sport-1"])
        # Essai : rien sans date ou après une heure
        self.assertEqual(agenda.essai(""), [])
        self.assertEqual(agenda.essai((maintenant - datetime.timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M")), [])
        agenda.connecter(ID, MDP)
        agenda.regler("nouveau", {})
        r = agenda.tester()
        f = self._fichiers(urllib.parse.urlparse(agenda.config()["calendrier"]).path)
        essai = next(v for n, v in f.items() if n.endswith("-essai.ics"))
        self.assertIn("TRIGGER:PT0S", essai)
        self.assertIn("T" + r["heure"].replace(":", "") + "00", essai)
        # Prochaines notifications : l'essai d'abord, puis la note de demain à 10 h
        demain = (auj + datetime.timedelta(days=1)).isoformat()
        agenda.enregistrer_notes([{"id": "n1", "titre": "Dentiste", "date": demain, "heure": "10:00"}])
        agenda.regler_alertes({"note": "0"}, {})
        p = agenda.prochaines()
        self.assertEqual([x["type"] for x in p], ["essai", "note"])
        self.assertEqual(p[1]["quand"], demain + "T10:00")

    def test_pense_betes_dates(self):
        import datetime
        auj = datetime.date.today()
        j = lambda n: (auj + datetime.timedelta(days=n)).isoformat()
        (storage.get_user_dir() / "pea_data.json").write_text(json.dumps({"uiPrefs": {"penseBete": [
            {"id": 1, "texte": "Appeler la banque", "date": j(3), "faite": False},
            {"id": 2, "texte": "Déjà fait", "date": j(3), "faite": True},
            {"id": 3, "texte": "Sans date", "date": "", "faite": False},
            {"id": 4, "texte": "Dépassé", "date": j(-1), "faite": False}]}}), "utf-8")
        r = agenda.rappels({"pense-bete": "veille"}, {})
        self.assertEqual([(e["cle"], e["titre"], e["jour"].isoformat()) for e in r],
                         [("pense-bete-1", "📌 Appeler la banque", j(3))])
        self.assertIn("TRIGGER:-PT6H", agenda.evenements({}, {}, {}, [], {"pense-bete": "veille"}, r)["pense-bete-1"])
        self.assertEqual(agenda.rappels({}, {}), [])

    def test_note_personnalisee(self):
        import datetime
        auj = datetime.date.today()
        il_y_a_3_semaines = (auj - datetime.timedelta(days=21)).isoformat()
        r = agenda.enregistrer_notes([
            {"id": "h", "titre": "Sport en salle", "date": il_y_a_3_semaines, "heure": "07:30",
             "repete": "semaine", "alerte": "15"},
            {"id": "m", "titre": "Loyer", "date": "2026-01-05", "repete": "mois", "alerte": "aucune"},
            {"id": "a", "titre": "Fête des mères", "date": "2026-05-31", "repete": "an", "alerte": "semaine"},
            {"id": "x", "titre": "Bizarre", "date": "2026-11-01", "repete": "jour", "alerte": "999"}])
        notes = {n["id"]: n for n in r["notes"]}
        self.assertEqual((notes["x"]["repete"], notes["x"]["alerte"]), ("", ""))   # valeurs inconnues écartées
        ev = agenda.evenements({}, {}, {}, r["notes"], {"note": "matin"})
        self.assertIn("RRULE:FREQ=WEEKLY", ev["note-h"])
        self.assertIn("TRIGGER:-PT15M", ev["note-h"])                 # son alerte, pas celle des notes
        self.assertIn("RRULE:FREQ=MONTHLY", ev["note-m"])
        self.assertFalse(any(l.startswith("TRIGGER") for l in ev["note-m"]))   # « aucune »
        self.assertIn("RRULE:FREQ=YEARLY", ev["note-a"])
        self.assertIn("TRIGGER:-P6DT15H", ev["note-a"])
        self.assertIn("TRIGGER:PT9H", ev["note-x"])                   # réglage général des notes
        # Occurrences : la note hebdomadaire tombe encore cette semaine
        e = next(x for x in agenda.elements({}, {}, r["notes"]) if x["cle"] == "note-h")
        jours = agenda._occurrences(e, auj, auj + datetime.timedelta(days=6))
        self.assertEqual(len(jours), 1)
        self.assertEqual(jours[0].weekday(), datetime.date.fromisoformat(il_y_a_3_semaines).weekday())
        a = next(x for x in agenda.elements({}, {}, r["notes"]) if x["cle"] == "note-a")
        self.assertEqual(agenda._occurrences(a, datetime.date(2028, 1, 1), datetime.date(2028, 12, 31)),
                         [datetime.date(2028, 5, 31)])


if __name__ == "__main__":
    unittest.main()
