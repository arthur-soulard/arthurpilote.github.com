"""Texte de la page de release (`build/notes_release.py`)."""
import json
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "build"))

import notes_release  # noqa: E402


class NotesRelease(unittest.TestCase):
    def test_version_en_tete(self):
        tete = json.loads((RACINE / "src" / "nouveautes.json").read_text(encoding="utf-8"))["versions"][0]
        t = notes_release.texte("v" + tete["version"])
        # Les deux fichiers que la release publie, et la fiche de la version
        self.assertIn("Pilote_Setup.exe", t)
        self.assertIn("releases/latest/download/Pilote_Mac.zip", t)
        self.assertIn("## Nouveautés de la " + tete["version"], t)

    def test_version_sans_fiche(self):
        # Pas de fiche : la page garde au moins le mode d'emploi
        t = notes_release.texte("v0.0.0")
        self.assertIn("## Installer Pilote", t)
        self.assertNotIn("Nouveautés", t)


if __name__ == "__main__":
    unittest.main()
