"""Donnees d'exemple (Brice) pour le test des builds : le jeu lui-meme vit
dans src/donnees_exemple.py, livre avec l'app pour le bouton « Explorer avec
des donnees d'exemple ».

Usage : python3 tests/donnees_exemple.py <dossier Donnees>
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

import donnees_exemple  # noqa: E402

if __name__ == "__main__":
    donnees_exemple.ecrire(sys.argv[1])
