"""Étape 1 du chiffrement (docs/securite.md, « b ») : tout fichier de données de
Donnees/ se lit et s'écrit par src/donnees.py, le seul endroit que l'étape 2
changera. Ces tests empêchent qu'un module y échappe sans qu'on le voie.
"""
import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "src"))

import donnees  # noqa: E402

# Fichiers qui lisent ou écrivent du JSON, mais pas des données de l'utilisateur
HORS_DONNEES = {
    "donnees.py",       # le passage lui-même
    "expositions.py",   # etf_compositions.json : compositions publiques des ETF
    "sante.py",         # résultat de l'OCR, fichier temporaire hors de Donnees/
    "updater.py",       # nouveautes.json, livré avec l'app
}
MOTIF = re.compile(r"json\.load\(\s*f\s*\)|json\.dump\([^)\n]*\bf\b")


class Passage(unittest.TestCase):
    def test_aucun_module_ne_contourne_donnees(self):
        fautifs = []
        for p in sorted((RACINE / "src").glob("*.py")):
            if p.name in HORS_DONNEES:
                continue
            for n, ligne in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
                if MOTIF.search(ligne):
                    fautifs.append("%s:%d" % (p.name, n))
        self.assertEqual(fautifs, [], "lecture ou écriture de JSON hors de donnees.py "
                                      "(si ce ne sont pas des données de l'utilisateur, "
                                      "ajouter le fichier à HORS_DONNEES)")


class Ecriture(unittest.TestCase):
    def setUp(self):
        self.dossier = Path(tempfile.mkdtemp(prefix="pilote_tests_passage_"))

    def tearDown(self):
        shutil.rmtree(self.dossier, ignore_errors=True)

    def test_aller_retour_json(self):
        c = self.dossier / "sous" / "essai.json"
        donnees.ecrire_json(c, {"é": [1, 2], "n": None})
        self.assertEqual(donnees.lire_json(c), {"é": [1, 2], "n": None})
        # Toujours du JSON lisible tel quel (rien n'est chiffré à l'étape 1)
        self.assertEqual(json.loads(c.read_text(encoding="utf-8"))["é"], [1, 2])

    def test_aucun_temporaire_ne_reste(self):
        c = self.dossier / "essai.json"
        donnees.ecrire_json(c, {"a": 1})
        donnees.ecrire_json(c, {"a": 2})
        self.assertEqual([p.name for p in self.dossier.iterdir()], ["essai.json"])

    def test_echec_ne_touche_pas_l_ancien_fichier(self):
        c = self.dossier / "essai.json"
        donnees.ecrire_json(c, {"a": 1})
        with self.assertRaises(TypeError):
            donnees.ecrire_json(c, {"a": object()})   # pas sérialisable
        self.assertEqual(donnees.lire_json(c), {"a": 1})
        self.assertEqual([p.name for p in self.dossier.iterdir()], ["essai.json"])


if __name__ == "__main__":
    unittest.main()
