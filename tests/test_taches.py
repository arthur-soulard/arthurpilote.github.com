"""Tests du module Tâches (taches.py) : fichier propre à l'utilisateur, aller-retour,
fichier illisible jamais écrasé. Les calculs (récurrence, retard) vivent dans
index.html (bloc tc*) et sont vérifiés dans l'app, sur les données de Brice.

Toutes les écritures vont dans un dossier temporaire (comme test_donnees.py).
"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "src"))

import storage  # noqa: E402

_TMP = Path(tempfile.mkdtemp(prefix="pilote_tests_taches_"))
_AVANT = storage.get_app_dir
storage.get_app_dir = lambda: _TMP          # jamais les vraies données, même à l'import

import donnees_exemple  # noqa: E402
import taches  # noqa: E402

storage.get_app_dir = _AVANT                # rendu aux autres fichiers de tests


class Taches(unittest.TestCase):
    # Le dossier temporaire seulement pendant ces tests : test_donnees.py
    # remplace lui aussi storage.get_app_dir, pour les siens
    def setUp(self):
        self._avant = storage.get_app_dir
        storage.get_app_dir = lambda: _TMP
        shutil.rmtree(_TMP, ignore_errors=True)
        _TMP.mkdir(parents=True)

    def tearDown(self):
        storage.get_app_dir = self._avant

    def test_absent_donne_les_valeurs_par_defaut(self):
        d = taches.load_data()
        self.assertEqual(d["taches"], [])
        self.assertEqual(d["_nid"]["tache"], 1)
        self.assertIsNone(taches.erreur())

    def test_aller_retour(self):
        d = taches.load_data()
        d["taches"].append({"id": 1, "titre": "Essai", "echeance": "2026-11-12", "priorite": 1,
                            "projet": "", "recurrence": "mois", "fait": "", "cree": "2026-11-12", "note": ""})
        d["_nid"]["tache"] = 2
        taches.save_data(d)
        self.assertTrue((storage.get_user_dir() / "taches.json").exists())
        relu = taches.load_data()
        self.assertEqual(relu["taches"][0]["titre"], "Essai")
        self.assertEqual(relu["_meta"]["schema"], "taches.v1")

    def test_fichier_illisible_jamais_ecrase(self):
        chemin = storage.get_user_dir() / "taches.json"
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text("{abime", encoding="utf-8")
        d = taches.load_data()
        self.assertIsNotNone(taches.erreur())
        with self.assertRaises(RuntimeError):
            taches.save_data(d)
        self.assertEqual(chemin.read_text(encoding="utf-8"), "{abime")

    def test_brice_a_des_taches(self):
        d = donnees_exemple.taches()
        self.assertTrue(any(t["recurrence"] for t in d["taches"]))
        self.assertTrue(any(t["fait"] for t in d["taches"]))
        self.assertGreater(d["_nid"]["tache"], max(t["id"] for t in d["taches"]))


if __name__ == "__main__":
    unittest.main()
