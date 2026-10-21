"""Tests de la couche de données (bibliothèque standard, `python -m unittest discover tests`).

Toutes les écritures vont dans un dossier temporaire : `storage.get_app_dir` est
remplacé AVANT tout appel, pour que jamais ces tests ne touchent `Donnees/`, qui
est, sur le PC d'Arthur, un lien vers ses vraies données.
"""
import datetime
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "src"))

import storage  # noqa: E402

_TMP = Path(tempfile.mkdtemp(prefix="pilote_tests_"))
storage.get_app_dir = lambda: _TMP          # jamais les vraies données

import finances  # noqa: E402
import jsonstore  # noqa: E402


def _ecrire(chemin, texte):
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(texte, encoding="utf-8")


class Socle(unittest.TestCase):
    def setUp(self):
        shutil.rmtree(_TMP, ignore_errors=True)
        _TMP.mkdir(parents=True)

    def test_dossier_isole(self):
        self.assertTrue(str(storage.get_user_dir()).startswith(str(_TMP)))

    def test_fichier_absent_n_est_pas_une_erreur(self):
        storage.load_data()
        self.assertIsNone(storage.get_last_load_info()["error"])

    def test_ecriture_puis_relecture(self):
        d = storage.load_data()
        d["positions"] = [{"id": 1, "ticker": "EPA:X", "name": "X"}]
        storage.save_data(d)
        self.assertEqual(storage.load_data()["positions"][0]["ticker"], "EPA:X")
        self.assertFalse(list(storage.get_data_path().parent.glob(".pea_*.tmp")))

    def test_backup_lisible_le_plus_recent(self):
        storage.save_data(storage.load_data())
        bdir = storage.get_backup_dir()
        hier = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
        _ecrire(bdir / ("pea_data_%s.json" % hier), json.dumps({"positions": [{}, {}]}))
        _ecrire(bdir / ("pea_data_%s.json" % datetime.date.today().isoformat()), "{abime")
        _ecrire(bdir / "pea_data_avant_import_20260801-101010.json", json.dumps({"positions": []}))
        _ecrire(storage.get_data_path(), '{"positions": [tronque')
        d = storage.load_data()
        self.assertEqual(len(d["positions"]), 2)                 # le backup d'hier
        self.assertTrue(storage.get_last_load_info()["error"])

    def test_rotation_ignore_les_copies_d_import(self):
        bdir = storage.get_backup_dir()
        for j in range(1, 12):
            jour = (datetime.date.today() - datetime.timedelta(days=j)).isoformat()
            _ecrire(bdir / ("pea_data_%s.json" % jour), "{}")
        _ecrire(bdir / "pea_data_avant_import_20260801-101010.json", "{}")
        storage.save_data(storage.load_data())
        dates = sorted(x.name for x in bdir.glob("pea_data_????-??-??.json"))
        self.assertEqual(len(dates), storage.BACKUP_KEEP_DAYS)
        self.assertTrue(dates[-1].endswith(datetime.date.today().isoformat() + ".json"))

    def test_version_plus_recente_bloque_l_ecriture(self):
        _ecrire(storage.get_data_path(), json.dumps({"_meta": {"version": storage.DATA_VERSION + 1}}))
        storage.load_data()
        self.assertTrue(storage.get_last_load_info()["error"])

    def test_users_illisible_reconstruit(self):
        for slug, prenom in (("default", "A"), ("lou", "Lou")):
            _ecrire(_TMP / "users" / slug / "pea_data.json", json.dumps({"config": {"prenom": prenom}}))
        _ecrire(_TMP / "users.json", '{"users": [{"slug": "def')
        st = storage.get_users_state()
        self.assertEqual(sorted(u["slug"] for u in st["users"]), ["default", "lou"])
        self.assertTrue(list(_TMP.glob("users.illisible-*.json")))

    def test_slug_sans_collision_ni_nom_reserve(self):
        (_TMP / "users" / "paul").mkdir(parents=True)
        self.assertEqual(storage.slugify("Paul", []), "paul_2")
        self.assertNotEqual(storage.slugify("Nul", []), "nul")


class Modules(unittest.TestCase):
    def setUp(self):
        shutil.rmtree(_TMP, ignore_errors=True)
        _TMP.mkdir(parents=True)
        self.store = jsonstore.JsonStore("essai.json", "backups_essai", "essai.v1",
                                         lambda: {"_meta": {}, "items": []})

    def test_illisible_sans_backup_bloque(self):
        _ecrire(self.store.path(), "{abime")
        self.store.load()
        with self.assertRaises(RuntimeError):
            self.store.save({"items": [1]})

    def test_etat_vide_refuse(self):
        with self.assertRaises(ValueError):
            self.store.save({})

    def test_finances_illisible_bloque(self):
        _ecrire(finances.get_finances_path(), "{abime")
        finances.load_data()
        with self.assertRaises(RuntimeError):
            finances.save_data({"transactions": []})


def tearDownModule():
    shutil.rmtree(_TMP, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
