# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec : Pilote -> dossier dist/Pilote/ (onedir, sans console) :
Pilote.exe + _internal/ (Python, bibliotheques, UI). Le Setup installe le tout.

Pourquoi pas un seul .exe (onefile, jusqu'a la 4.2.7) : il se decompressait a
CHAQUE lancement (217 fichiers, 36 Mo dans %TEMP%\\_MEI*), et Defender
inspectait chaque DLL au passage. Mesure sur la machine d'Arthur : 4 a 6,5 s
avant le moindre affichage, 39 s un matin a froid. En onedir les fichiers sont
installes une fois, il n'y a plus rien a decompresser. Ne pas revenir en onefile.

Usage :
    pyinstaller build/pilote.spec --clean --noconfirm
"""

import sys
from pathlib import Path

# Le .spec s'execute avec son repertoire courant = racine du projet
ROOT     = Path.cwd()
SRC      = ROOT / "src"


def _fiche_version():
    """Ecrit build/version_info.txt (format de PyInstaller) depuis APP_VERSION."""
    import re
    v = re.search(r'^APP_VERSION\s*=\s*"([^"]+)"', (SRC / "app.py").read_text(encoding="utf-8"), re.M).group(1)
    t = tuple(int(x) for x in (v.split(".") + ["0", "0", "0"])[:4])
    texte = (
        "VSVersionInfo(ffi=FixedFileInfo(filevers=%r, prodvers=%r, mask=0x3f, flags=0x0, OS=0x40004,\n"
        "  fileType=0x1, subtype=0x0, date=(0, 0)), kids=[StringFileInfo([StringTable('040C04B0', [\n"
        "  StringStruct('CompanyName', 'Arthur Soulard'), StringStruct('FileDescription', 'Pilote'),\n"
        "  StringStruct('FileVersion', %r), StringStruct('InternalName', 'Pilote'),\n"
        "  StringStruct('LegalCopyright', 'Licence MIT'), StringStruct('OriginalFilename', 'Pilote.exe'),\n"
        "  StringStruct('ProductName', 'Pilote'), StringStruct('ProductVersion', %r)])]),\n"
        "  VarFileInfo([VarStruct('Translation', [1036, 1200])])])\n" % (t, t, v, v))
    chemin = ROOT / "build" / "version_info.txt"
    chemin.write_text(texte, encoding="utf-8")
    return str(chemin)
ASSETS   = ROOT / "assets"
ICON     = ASSETS / "icon.ico"


block_cipher = None


a = Analysis(
    [str(SRC / "app.py")],
    pathex=[str(SRC)],
    binaries=[],
    datas=[
        # Embarque l'UI HTML et l'icone dans l'exe
        (str(SRC / "ui" / "index.html"), "ui"),
        # Chart.js + polices, servis par server.py sur /vendor/. Sans cette
        # ligne les graphiques disparaissent et la typo retombe sur celle du
        # systeme dans l'exe compile, alors que tout marche en dev : la meme
        # panne invisible que ocr_win.ps1 ci-dessous.
        (str(SRC / "ui" / "vendor"),      "ui/vendor"),
        # Script OCR (module Sante) : lu a l'execution via sys._MEIPASS
        (str(SRC / "ocr_win.ps1"),      "."),
        # Licences des composants embarques (audit du 20/10/2026, LEG-03)
        (str(ROOT / "THIRD-PARTY-NOTICES.txt"), "."),
        # Fiches des versions (Parametres -> Mises a jour, fiche apres une mise
        # a jour), lues par updater.historique() : sans cette ligne l'historique
        # est vide dans l'exe, alors qu'il s'affiche en dev
        (str(SRC / "nouveautes.json"),  "."),
        (str(ICON),                       "."),
    ],
    hiddenimports=[
        # pywebview backends Windows
        "webview.platforms.edgechromium",
        "webview.platforms.mshtml",
        "clr_loader",
        # win10toast deps
        "win10toast",
        # Pillow : icone recoloree a la volee (appicon.py, import paresseux)
        "PIL.Image",
        "PIL.ImageDraw",
        "PIL.ImageFont",
        # Catalogue des titres de l'import (server.cotations_euro, import paresseux)
        "titres_connus",
        "titres_listes",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter", "unittest", "pydoc", "doctest",
    ],
    noarchive=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,   # onedir : les DLL et les datas vont dans COLLECT
    name="Pilote",
    icon=str(ICON),
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,           # pas de cmd noir
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # Fiche de version de l'exe (Proprietes > Details de Windows), lue dans
    # app.py : un exe sans elle passe plus mal les antivirus (SUP-11)
    version=_fiche_version(),
    uac_admin=False,
)

# dist/Pilote/Pilote.exe + dist/Pilote/_internal/ : sys._MEIPASS pointe sur
# _internal, resource_path() et sante._ocr_script_path() n'ont rien a changer
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Pilote",
)
