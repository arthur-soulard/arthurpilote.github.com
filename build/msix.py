"""
msix.py — Paquet Microsoft Store de Pilote (Pilote.msix), a partir de dist/Pilote/.

A lancer apres PyInstaller (build/pilote.spec) :
    python build/msix.py [--identite ...] [--editeur "CN=..."] [--nom-editeur ...]

Par defaut, l'identite de Pilote dans Partner Center (Gestion du produit >
Identite du produit, relevee le 02/11/2026) : c'est le paquet a envoyer au
Store, qui le re-signe (pas de certificat a acheter). Le test de
build-windows.yml passe une identite d'essai, celle de son certificat.
Detail et decisions : docs/microsoft-store.md.
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
DIST = RACINE / "dist" / "Pilote"
SORTIE = RACINE / "dist" / "msix"
PAQUET = RACINE / "dist" / "Pilote.msix"

# Taille de chaque logo demande par le manifeste (en pixels)
LOGOS = {"StoreLogo.png": 50, "Square44x44Logo.png": 44, "Square150x150Logo.png": 150}


def version_app() -> str:
    """APP_VERSION de src/app.py, au format du Store (4 nombres, le dernier a 0)."""
    texte = (RACINE / "src" / "app.py").read_text(encoding="utf-8")
    v = re.search(r'^APP_VERSION = "(\d+)\.(\d+)\.(\d+)"', texte, re.M)
    if not v:
        sys.exit("APP_VERSION introuvable dans src/app.py")
    return ".".join(v.groups()) + ".0"


def makeappx() -> str:
    """makeappx.exe du Windows SDK le plus recent."""
    kits = os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), "Windows Kits", "10")
    trouves = sorted(glob.glob(os.path.join(kits, "bin", "*", "x64", "makeappx.exe")))
    trouves += glob.glob(os.path.join(kits, "App Certification Kit", "makeappx.exe"))
    if not trouves:
        sys.exit("makeappx.exe introuvable : installer le Windows SDK")
    return trouves[-1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--identite", default="ARSOL.Pilote")
    ap.add_argument("--editeur", default="CN=EA040BB3-FE8B-4FEE-9E20-3D788F376B39")
    ap.add_argument("--nom-editeur", default="ARSOL")
    args = ap.parse_args()

    if not (DIST / "Pilote.exe").is_file():
        sys.exit("dist/Pilote/Pilote.exe absent : lancer PyInstaller d'abord")

    # Le dossier du paquet : l'app telle que PyInstaller l'a faite, plus le
    # manifeste et les logos
    if SORTIE.exists():
        shutil.rmtree(SORTIE)
    shutil.copytree(DIST, SORTIE)

    manifeste = (RACINE / "build" / "AppxManifest.xml").read_text(encoding="utf-8")
    for champ, valeur in (("__IDENTITE__", args.identite), ("__EDITEUR__", args.editeur),
                          ("__NOM_EDITEUR__", args.nom_editeur), ("__VERSION__", version_app())):
        manifeste = manifeste.replace(champ, valeur)
    (SORTIE / "AppxManifest.xml").write_text(manifeste, encoding="utf-8")

    from PIL import Image
    images = SORTIE / "Images"
    images.mkdir()
    with Image.open(RACINE / "assets" / "icon_512.png") as icone:
        icone = icone.convert("RGBA")
        for nom, cote in LOGOS.items():
            icone.resize((cote, cote), Image.LANCZOS).save(images / nom)

    if PAQUET.exists():
        PAQUET.unlink()
    r = subprocess.run([makeappx(), "pack", "/d", str(SORTIE), "/p", str(PAQUET), "/o"],
                       capture_output=True, text=True)
    print(r.stdout[-2000:])
    if r.returncode != 0 or not PAQUET.is_file():
        print(r.stderr[-2000:])
        sys.exit("makeappx a echoue")
    print(f"OK {PAQUET} ({PAQUET.stat().st_size // (1024 * 1024)} Mo), version {version_app()}")


if __name__ == "__main__":
    main()
