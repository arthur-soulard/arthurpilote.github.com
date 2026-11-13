"""Mesure l'import des relevés de Mes comptes sur le corpus d'entraînement.

    python tests/mesurer_budget.py [nombre de relevés] [--erreurs]

Affiche, par format : opérations bien lues (date et montant exacts), bien
classées, laissées à classer, mal classées ; puis les erreurs si demandé.
"""
import collections
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import budget_releves as br  # noqa: E402
import finances  # noqa: E402
from budget_marchands import CIBLES  # noqa: E402
import corpus_budget as cb  # noqa: E402


def attendu(notion, cats):
    if notion is None:
        return None
    t, c, s = CIBLES[notion]
    r = cats.trouver(t, c, s)
    if notion == "retrait" and r == (None, None):
        r = cats.trouver("expense", "Autres dépenses", "Divers")   # repli voulu pour un retrait
    return r


def mesurer(n=1020, montrer=False, categories=None, validation=False):
    categories = categories or finances._default_categories()
    cats = br.Categories(categories)
    stats = collections.defaultdict(collections.Counter)
    erreurs = []
    t0 = time.time()
    import corpus_budget_validation as cv
    for nom, data, ops, fmt in (cv.corpus(n) if validation else cb.corpus(n)):
        r = br.lire([{"nom": nom, "b64": cb.b64(data)}], categories, [])
        lus = r["operations"]
        st = stats[fmt]
        st["fichiers"] += 1
        st["ops"] += len(ops)
        # Lecture : chaque opération attendue retrouvée (date, montant signé)
        restant = collections.Counter((o.date, round(o.montant, 2)) for o in ops)
        trouves = collections.Counter((o["date"], o["montantSigne"]) for o in lus)
        st["lues"] += sum((restant & trouves).values())
        st["en trop"] += sum((trouves - restant).values())
        if restant != trouves and montrer and len(erreurs) < 400:
            erreurs.append(("LECTURE", fmt, nom, sorted((restant - trouves).elements())[:3],
                            sorted((trouves - restant).elements())[:3]))
        par_cle = collections.defaultdict(list)
        for o in lus:
            par_cle[(o["date"], o["montantSigne"])].append(o)
        for o in ops:
            cand = par_cle.get((o.date, round(o.montant, 2)))
            if not cand:
                continue
            # Même date et même montant : celle dont le libellé porte le nom attendu
            mot = br._norm(o.nom).split()[:1] if o.nom else []
            i = next((k for k, c in enumerate(cand) if mot and mot[0] in br._norm(c["brut"])),
                     next((k for k, c in enumerate(cand) if c["genre"] == o.genre), 0))
            x = cand.pop(i)
            if o.interne:
                st["internes"] += 1
                st["internes vus"] += bool(x["interne"])
                if not x["interne"] and montrer:
                    erreurs.append(("INTERNE", fmt, x["brut"], x["libelle"]))
                continue
            att = attendu(o.notion, cats)
            obt = (x["cat"], x["sub"]) if x["cat"] else None
            if x["interne"]:
                st["faux internes"] += 1
                if montrer:
                    erreurs.append(("FAUX INTERNE", fmt, x["brut"], o.notion))
            if att is None or att == (None, None):
                st["inconnues"] += 1
                if obt and not (o.notion is None and False):
                    st["inconnues classées"] += 1
                    if montrer:
                        erreurs.append(("INCONNU CLASSE", fmt, x["brut"], x["libelle"], obt, x["raison"]))
                continue
            st["connues"] += 1
            if obt == att:
                st["justes"] += 1
            elif obt is None:
                st["à classer"] += 1
                if montrer:
                    erreurs.append(("A CLASSER", fmt, x["brut"], x["libelle"], o.notion, x["genre"]))
            else:
                st["fausses"] += 1
                if montrer:
                    erreurs.append(("FAUX", fmt, x["brut"], x["libelle"], "attendu", att, "obtenu", obt, x["raison"]))
            # Libellé lisible : le nom du marchand y reste
            if o.nom and o.genre == "carte":
                st["cartes"] += 1
                coeur = br._norm(o.nom).split()[0]
                if coeur in br._norm(x["libelle"]):
                    st["libellés propres"] += 1
                elif montrer:
                    erreurs.append(("LIBELLE", fmt, x["brut"], x["libelle"]))
    tot = collections.Counter()
    for fmt, st in sorted(stats.items()):
        tot.update(st)
        _ligne(fmt, st)
    _ligne("TOTAL", tot)
    print("%.1f s" % (time.time() - t0))
    return tot, erreurs


def _ligne(nom, st):
    pc = lambda a, b: "%5.1f %%" % (100.0 * st[a] / st[b]) if st[b] else "   -   "
    print("%-10s %4d fich. %6d ops | lues %s (+%d) | justes %s | à classer %s | fausses %s | inconnues classées %s"
          " | internes %s (faux %d) | libellés %s" % (
              nom, st["fichiers"], st["ops"], pc("lues", "ops"), st["en trop"], pc("justes", "connues"),
              pc("à classer", "connues"), pc("fausses", "connues"), pc("inconnues classées", "inconnues"),
              pc("internes vus", "internes"), st["faux internes"], pc("libellés propres", "cartes")))


if __name__ == "__main__":
    n = int(next((a for a in sys.argv[1:] if a.isdigit()), 1020))
    tot, err = mesurer(n, "--erreurs" in sys.argv, validation="--validation" in sys.argv)
    vus = collections.Counter()
    for e in err:
        k = (e[0], e[1]) if e[0] == "LECTURE" else (e[0], str(e[2])[:50])
        vus[e[0]] += 1
        if vus[e[0]] <= 25:
            print(" | ".join(str(x) for x in e))
