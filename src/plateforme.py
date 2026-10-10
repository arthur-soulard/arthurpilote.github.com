"""
plateforme.py — Ce qui differe entre Windows et Mac, regroupe ici.

Pilote est une seule application pour les deux systemes (decision du
11/10/2026, voir docs/mac.md) : un seul code, un seul format de donnees. Ce
qui ne peut pas s'ecrire pareil sur les deux vit dans ce module, et le chemin
Windows y reste celui d'avant.
"""
from __future__ import annotations

import os
import sys
import subprocess


def ouvrir(chemin: str) -> None:
    """Ouvre un fichier ou un dossier avec l'application par defaut du systeme
    (Explorateur sous Windows, Finder sur Mac). Leve une exception en cas d'echec."""
    if sys.platform == "win32":
        os.startfile(chemin)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", chemin])
    else:
        subprocess.Popen(["xdg-open", chemin])
