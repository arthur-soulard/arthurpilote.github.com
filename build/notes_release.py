"""Texte de la page d'une release GitHub (release.yml).

Écrit pour quelqu'un qui arrive sur la page sans connaître Pilote : quel
fichier prendre selon son ordinateur, comment l'installer, puis la fiche de
la version (src/nouveautes.json). Jusqu'à la 4.4.27, la page ne montrait que
la liste des commits.

Usage : python build/notes_release.py vX.Y.Z fichier_de_sortie.md
"""
import io
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEPOT = "https://github.com/arthur-soulard/arthurpilote.github.com"

INSTALLATION = """\
## Installer Pilote

**Sur Windows 10 ou 11** : télécharge **Pilote_Setup.exe** (en bas de cette page,
rubrique *Assets*) et lance-le. Si Windows affiche « Windows a protégé votre
ordinateur » : *Informations complémentaires*, puis *Exécuter quand même*. Ce
message vient de ce que Pilote n'est pas signé (un certificat est payant).

**Sur Mac à puce Apple (M1 et suivants)** : ouvre le Terminal (Applications ›
Utilitaires › Terminal), colle cette ligne, puis appuie sur Entrée. Elle
télécharge Pilote, le range dans Applications et l'ouvre, sans réglage à faire.

```bash
curl -fL {depot}/releases/latest/download/Pilote_Mac.zip -o /tmp/Pilote_Mac.zip && ditto -x -k /tmp/Pilote_Mac.zip /Applications && open /Applications/Pilote.app
```

Pilote ne fonctionne pas sur un Mac Intel.

**Déjà installé ?** Rien à faire : Pilote te propose cette version au prochain
lancement.

Avant d'installer, ce qu'il faut avoir, les premiers pas et les solutions aux
problèmes courants : [le guide]({depot}#readme).
"""

RUBRIQUES = (("nouveau", "Nouveau"), ("ameliore", "Amélioré"), ("corrige", "Corrigé"))


def fiche(version):
    """La fiche de cette version dans nouveautes.json, ou None."""
    with io.open(os.path.join(RACINE, "src", "nouveautes.json"), encoding="utf-8") as f:
        for v in json.load(f)["versions"]:
            if v.get("version") == version:
                return v
    return None


def texte(tag):
    version = tag.lstrip("v")
    morceaux = [INSTALLATION.format(depot=DEPOT)]
    v = fiche(version)
    if v:
        titre = "## Nouveautés de la %s" % version
        if v.get("titre"):
            titre += " : " + v["titre"]
        morceaux.append(titre + "\n")
        for cle, nom in RUBRIQUES:
            if v.get(cle):
                morceaux.append("**%s**\n\n" % nom + "".join("- %s\n" % l for l in v[cle]))
    return "\n".join(morceaux)


if __name__ == "__main__":
    with io.open(sys.argv[2], "w", encoding="utf-8", newline="\n") as f:
        f.write(texte(sys.argv[1]))
