"""Serveur local (src/server.py) : le changement de code PIN est freiné comme
la vérification (revue de sécurité du 09/11/2026). Un vrai serveur sur un
port libre, des données dans un dossier temporaire."""
import http.client
import json
import shutil
import sys
import tempfile
import threading
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "src"))

import storage  # noqa: E402
import server  # noqa: E402

_TMP = Path(tempfile.mkdtemp(prefix="pilote_serveur_"))


class PinFreine(unittest.TestCase):
    def setUp(self):
        self._get_app_dir = storage.get_app_dir
        storage.get_app_dir = lambda: _TMP           # jamais les vraies données
        self.addCleanup(setattr, storage, "get_app_dir", self._get_app_dir)
        shutil.rmtree(_TMP, ignore_errors=True)
        _TMP.mkdir(parents=True)
        storage.save_users_state({"active": "brice", "users": [
            {"slug": "brice", "label": "Brice", "emoji": "", "color": ""}]})
        server.pin_set("1234", "brice")
        self._delai = server.PIN_DELAY_SEC
        server.PIN_DELAY_SEC = 0
        self.addCleanup(setattr, server, "PIN_DELAY_SEC", self._delai)
        server._pin_fails.clear()
        self.httpd = server.http.server.ThreadingHTTPServer(("127.0.0.1", 0), server._Handler)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)

    def _get(self, chemin, jeton=True):
        c = http.client.HTTPConnection("127.0.0.1", self.httpd.server_address[1], timeout=10)
        h = {"Host": "127.0.0.1"}
        if jeton:
            h[server.TOKEN_HEADER] = server._SESSION_TOKEN
        c.request("GET", chemin, headers=h)
        r = c.getresponse()
        corps = json.loads(r.read() or b"{}")
        c.close()
        return r.status, corps

    def test_ancien_code_freine_puis_bloque(self):
        for i in range(server.PIN_MAX_TRIES):
            st, _ = self._get("/pin/set?pin=0000&old=%04d" % i)
            self.assertEqual(st, 403)
        st, d = self._get("/pin/set?pin=0000&old=1234")      # même le bon : bloqué
        self.assertEqual(st, 429)
        self.assertTrue(server.pin_check("1234", "brice"))  # code inchangé

    def test_bon_ancien_code_change(self):
        st, d = self._get("/pin/set?pin=5678&old=1234")
        self.assertEqual(st, 200, d)
        self.assertTrue(server.pin_check("5678", "brice"))

    def test_sans_jeton_refuse(self):
        st, _ = self._get("/pin/set?pin=0000&old=1234", jeton=False)
        self.assertNotEqual(st, 200)
        self.assertTrue(server.pin_check("1234", "brice"))

    def test_page_servie_sans_le_jeton(self):
        """docs/securite.md, « c » : un programme qui lit `/` n'y trouve plus
        le jeton (la page le demande au pont, Api.jeton)."""
        page_ui = Path(__file__).resolve().parent.parent / "src" / "ui" / "index.html"
        self.addCleanup(setattr, server, "_html_file_path", server._html_file_path)
        server._html_file_path = str(page_ui)
        c = http.client.HTTPConnection("127.0.0.1", self.httpd.server_address[1], timeout=10)
        c.request("GET", "/", headers={"Host": "127.0.0.1"})
        r = c.getresponse()
        page = r.read().decode("utf-8", "replace")
        c.close()
        self.assertEqual(r.status, 200)
        self.assertIn("api.jeton", page)
        self.assertNotIn(server._SESSION_TOKEN, page)


def tearDownModule():
    shutil.rmtree(_TMP, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
