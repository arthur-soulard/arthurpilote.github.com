"""Garde-fou avant publication (release.yml), aussi lançable à la main.

Vérifie que le numéro de version est le même partout (src/app.py,
build/installer.iss, tête de src/nouveautes.json et, en CI, le tag poussé),
que nouveautes.json se lit, et que chaque fichier Python de src/ compile.
Code de sortie 1 au premier problème : la release n'est alors pas publiée.

Usage : python tests/verifier_release.py [vX.Y.Z]
"""
import io
import json
import os
import py_compile
import re
import sys
import tempfile

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
erreurs = []


def lire(chemin):
    return io.open(os.path.join(RACINE, chemin), encoding="utf-8").read()


app = re.search(r'^APP_VERSION\s*=\s*"([^"]+)"', lire("src/app.py"), re.M)
iss = re.search(r'^#define AppVersion\s+"([^"]+)"', lire("build/installer.iss"), re.M)
try:
    tete = json.loads(lire("src/nouveautes.json"))["versions"][0]["version"]
except Exception as e:
    tete = None
    erreurs.append("src/nouveautes.json illisible : %s" % e)

versions = {"src/app.py": app and app.group(1), "build/installer.iss": iss and iss.group(1),
            "src/nouveautes.json": tete}
tag = (sys.argv[1] if len(sys.argv) > 1 else os.environ.get("GITHUB_REF_NAME", "")).lstrip("v")
if tag:
    versions["tag"] = tag
if len(set(versions.values())) != 1 or None in versions.values():
    erreurs.append("versions differentes : %s" % versions)

with tempfile.TemporaryDirectory() as tmp:
    for nom in sorted(os.listdir(os.path.join(RACINE, "src"))):
        if nom.endswith(".py"):
            try:
                py_compile.compile(os.path.join(RACINE, "src", nom),
                                   cfile=os.path.join(tmp, nom + "c"), doraise=True)
            except py_compile.PyCompileError as e:
                erreurs.append("%s ne compile pas : %s" % (nom, e.msg))

if erreurs:
    for e in erreurs:
        print("::error title=Avant publication::" + e)
    sys.exit(1)
print("OK : version %s partout, nouveautes.json lisible, src/*.py compilent" % versions["src/app.py"])
