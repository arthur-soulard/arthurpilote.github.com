# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec Mac : Pilote -> dist/Pilote.app (application macOS).

Pendant de build/pilote.spec (Windows), garde a part pour que le build
Windows ne bouge pas d'une ligne. Fabrique sur une machine Mac de GitHub
(.github/workflows/build-mac.yml) : PyInstaller ne sait pas fabriquer une app
Mac depuis Windows. Voir docs/mac.md.

Meme piege que sous Windows : sans ui/vendor dans les datas, graphiques,
polices et icones disparaissent dans l'app compilee alors que tout marche en
dev. Pas d'ocr_win.ps1 : le moteur OCR de Windows n'existe pas sur Mac.

Usage (sur un Mac) :
    pyinstaller build/pilote-mac.spec --clean --noconfirm
"""

import re
from pathlib import Path

# Le .spec s'execute avec son repertoire courant = racine du projet
ROOT   = Path.cwd()
SRC    = ROOT / "src"
ASSETS = ROOT / "assets"
# La meme icone que Windows : PyInstaller la convertit lui-meme en .icns (avec
# Pillow). Pas icon_512.png : .gitignore l'ecarte, elle n'existe pas sur GitHub.
ICON   = ASSETS / "icon.ico"

# Version lue dans app.py : un seul endroit a augmenter, comme sous Windows
VERSION = re.search(r'^APP_VERSION\s*=\s*"([^"]+)"',
                    (SRC / "app.py").read_text(encoding="utf-8"), re.M).group(1)

# Identite de l'app pour macOS (autorisations accordees, preferences). Comme
# l'AppId de installer.iss : ne JAMAIS la changer une fois l'app distribuee.
BUNDLE_ID = "io.github.arthur-soulard.pilote"


a = Analysis(
    [str(SRC / "app.py")],
    pathex=[str(SRC)],
    binaries=[],
    datas=[
        (str(SRC / "ui" / "index.html"), "ui"),
        (str(SRC / "ui" / "vendor"),     "ui/vendor"),
    ],
    hiddenimports=[
        "webview.platforms.cocoa",
        # Pillow : import paresseux (appicon.py, sante.py)
        "PIL.Image",
        "PIL.ImageDraw",
        "PIL.ImageFont",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Pilote",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,     # pas de compte developpeur Apple : signature ad hoc
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="Pilote",
)

app = BUNDLE(
    coll,
    name="Pilote.app",
    icon=str(ICON),
    bundle_identifier=BUNDLE_ID,
    version=VERSION,
    info_plist={
        "CFBundleName": "Pilote",
        "CFBundleDisplayName": "Pilote",
        "CFBundleVersion": VERSION,
        "NSHighResolutionCapable": True,
        "LSApplicationCategoryType": "public.app-category.finance",
    },
)
