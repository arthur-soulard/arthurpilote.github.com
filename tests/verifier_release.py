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
# En CI, GITHUB_REF_NAME n'est un tag que si GITHUB_REF_TYPE vaut « tag » (sur la
# branche mac, il vaut « mac »)
en_ci = os.environ.get("GITHUB_REF_NAME", "") if os.environ.get("GITHUB_REF_TYPE") == "tag" else ""
tag = (sys.argv[1] if len(sys.argv) > 1 else en_ci).lstrip("v")
if tag:
    versions["tag"] = tag
if len(set(versions.values())) != 1 or None in versions.values():
    erreurs.append("versions differentes : %s" % versions)

# Date de la fiche = jour du tag : la fiche de la 4.4.36, ecrite la veille,
# affichait le 29/10 dans l'historique pour une version sortie le 30/10.
# A la main seulement : la CI tourne a l'heure UTC, un tag pousse apres
# minuit (heure de Paris) y tomberait la veille.
if tag and not en_ci and tete:
    import datetime
    date_fiche = json.loads(lire("src/nouveautes.json"))["versions"][0].get("date")
    if date_fiche != datetime.date.today().isoformat():
        erreurs.append("fiche %s datee du %s, pas d'aujourd'hui (%s)"
                       % (tete, date_fiche, datetime.date.today().isoformat()))

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
