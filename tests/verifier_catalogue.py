"""
Vérifie le catalogue des titres (src/titres_connus.py) chez Yahoo : chaque
ticker doit avoir un cours en euros, et la recherche de son ISIN doit rendre
ce titre (même racine de ticker, ou un nom en commun). Demande internet :
à lancer à la main après avoir modifié le catalogue, pas dans les tests.

    python tests/verifier_catalogue.py
"""
import concurrent.futures
import json
import os
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import server            # noqa: E402
import titres_connus     # noqa: E402


def _meta(sym):
    url = ("https://query2.finance.yahoo.com/v8/finance/chart/" + urllib.parse.quote(sym)
           + "?interval=1d&range=5d")
    req = urllib.request.Request(url, headers={"User-Agent": server.USER_AGENT, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10, context=server._SSL_CTX) as r:
            res = json.loads(r.read().decode())["chart"]["result"]
        return res[0]["meta"] if res else {}
    except Exception:
        return {}


# Écarts vus le 30/10/2026 et acceptés : la recherche de Yahoo ne connaît pas
# l'ISIN de Rheinmetall (le ticker, lui, est juste), et rend l'ETF ACWI
# d'iShares sous son ticker de Londres (ISAC.L, même fonds)
ACCEPTES = {"DE0007030033", "IE00B6R52259"}


def verifier(ligne):
    isin, sym, nom, _ = ligne
    m = _meta(sym)
    pb = []
    if not m.get("regularMarketPrice"):
        pb.append("pas de cours")
    elif m.get("currency") != "EUR":
        pb.append("cours en " + str(m.get("currency")))
    try:
        quotes = server._yahoo_search_brut(isin)
    except Exception as e:
        quotes, pb = [], pb + ["recherche KO " + str(e)]
    racines = {(q.get("symbol") or "").split(".")[0] for q in quotes}
    noms = set()
    for q in quotes:
        noms |= server._mots(q.get("shortname") or q.get("longname") or "")
    ref = server._mots(nom) | server._mots(m.get("longName") or "")
    if isin in ACCEPTES:
        return isin, sym, nom, m.get("longName") or "", pb
    if not quotes:
        pb.append("ISIN inconnu de Yahoo")
    elif sym.split(".")[0] not in racines and not (ref & noms):
        pb.append("l'ISIN rend " + ", ".join(sorted(q.get("symbol", "") for q in quotes)[:4]))
    return isin, sym, nom, m.get("longName") or m.get("shortName") or "", pb


def main():
    with concurrent.futures.ThreadPoolExecutor(6) as ex:
        res = list(ex.map(verifier, titres_connus.TITRES))
    ko = [r for r in res if r[4]]
    for isin, sym, nom, yn, pb in ko:
        print(f"KO {isin} {sym:10} {nom} (Yahoo : {yn}) : {' ; '.join(pb)}")
    isins = [t[0] for t in titres_connus.TITRES]
    doubles = {i for i in isins if isins.count(i) > 1}
    for i in doubles:
        print("KO ISIN en double :", i)
    print(f"{len(res) - len(ko)} titres sur {len(res)} conformes")
    return 1 if ko or doubles else 0


if __name__ == "__main__":
    sys.exit(main())
