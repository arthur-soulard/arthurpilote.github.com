"""Tests des lecteurs de relevés : nombres et dates (bibliothèque standard).

Cas fictifs, écrits à la main avec leur bonne réponse : aucun vrai relevé dans
le dépôt (il est public).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import cto  # noqa: E402
import releves  # noqa: E402


class Nombres(unittest.TestCase):
    def test_formats_francais_et_anglais(self):
        cas = {"1 234,56": 1234.56, "1.234,56": 1234.56, "1,234.56": 1234.56,
               "12,5": 12.5, "-3,20": -3.2, "(12,50)": -12.5}
        for txt, attendu in cas.items():
            with self.subTest(txt=txt):
                self.assertAlmostEqual(cto._nombre(txt), attendu, places=6)

    def test_vide(self):
        self.assertIsNone(cto._nombre(""))


class Dates(unittest.TestCase):
    def test_jour_mois(self):
        self.assertEqual(releves._date_fr("03/04/2025"), "2025-04-03")

    def test_ordre_americain_detecte(self):
        self.assertEqual(releves._ordre_dates(["03/26/2024", "04/02/2024"]), "mj")
        self.assertEqual(releves._ordre_dates(["26/03/2024", "02/04/2024"]), "jm")

    def test_dates_ambigues(self):
        self.assertTrue(releves._dates_ambigues(["03/04/2025", "05/06/2025"]))
        self.assertFalse(releves._dates_ambigues(["13/04/2025", "05/06/2025"]))

    def test_date_impossible_refusee(self):
        self.assertFalse(releves._date_fr("31/02/2025"))


if __name__ == "__main__":
    unittest.main()
