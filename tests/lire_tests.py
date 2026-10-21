"""Relit, sans compte GitHub, les tests Mac et Windows lancés par un push sur la
branche mac (build-mac.yml, build-windows.yml) : résultat de chaque étape,
annotations, et captures d'écran recollées en JPEG.

Les artefacts et les journaux ne se lisent qu'avec un compte ; les annotations,
elles, passent par l'API publique des check-runs (60 lectures par heure sans
compte). Les captures y sortent en base64 découpé : « Capture i/N » (premier
job) et « Ecran n i/N » (job ecrans-mac, un écran de tests/ecrans.txt chacun).

Usage : python tests/lire_tests.py <début du sha du commit> [dossier de sortie]
Écrit resultats-tests.txt, capture-mac.jpg et ecran-<n>.jpg dans le dossier.
"""
import base64
import json
import os
import re
import sys
import urllib.request

DEPOT = "https://api.github.com/repos/arthur-soulard/arthurpilote.github.com"


def api(chemin):
    req = urllib.request.Request(DEPOT + chemin, headers={
        "Accept": "application/vnd.github+json", "User-Agent": "pilote-lire-tests"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def lire(sha, sortie):
    os.makedirs(sortie, exist_ok=True)
    runs = [r for r in api("/actions/runs?branch=mac&per_page=20")["workflow_runs"]
            if r["head_sha"].startswith(sha)]
    if not runs:
        return ["aucun test pour le commit " + sha]
    lignes = []
    for run in runs:
        lignes.append("=== %s : %s / %s" % (run["name"], run["status"], run["conclusion"]))
        for job in api("/actions/runs/%d/jobs" % run["id"])["jobs"]:
            lignes.append("--- job %s : %s / %s" % (job["name"], job["status"], job["conclusion"]))
            for st in job["steps"]:
                lignes.append("  étape %-30s %s" % (st["name"], st["conclusion"]))
            images = {}       # nom du fichier -> {i: morceau}
            for a in api("/check-runs/%d/annotations?per_page=100" % job["id"]):
                titre = a.get("title") or ""
                m = re.match(r"(Capture|Ecran (\d+)) (\d+)/(\d+)$", titre)
                if m:
                    nom = "capture-mac.jpg" if m.group(1) == "Capture" else "ecran-%s.jpg" % m.group(2)
                    images.setdefault(nom, {})[int(m.group(3))] = a["message"]
                else:
                    lignes.append("  [%s] %s : %s" % (a["annotation_level"], titre, a["message"][:2000]))
            for nom, morceaux in sorted(images.items()):
                chemin = os.path.join(sortie, nom)
                with open(chemin, "wb") as f:
                    f.write(base64.b64decode("".join(morceaux[i] for i in sorted(morceaux))))
                lignes.append("  image : %s (%d morceaux)" % (chemin, len(morceaux)))
    with open(os.path.join(sortie, "resultats-tests.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lignes))
    return lignes


if __name__ == "__main__":
    res = lire(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else ".")
    # Console Windows en cp1252 : rien d'exotique à l'écran, tout est dans le fichier
    print("\n".join(res).encode("ascii", "replace").decode())
    # Code de sortie : 1 si un test n'est pas fini et réussi, ou si le journal
    # signale une erreur JavaScript (audit du 20/10/2026, QA-08)
    rate = [l for l in res if l.startswith(("===", "---")) and not l.rstrip().endswith("completed / success")]
    rate += [l for l in res if "ERREUR " in l and "[diag]" in l]
    if rate or (res and res[0].startswith("aucun test")):
        print("ECHEC ou incomplet :", len(rate) or 1, "ligne(s)")
        sys.exit(1)
