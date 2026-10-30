"""
Fabrique src/titres_listes.py : les titres négociés en euros sur Euronext et
sur Xetra, avec leur ticker Yahoo vérifié. Complète le catalogue écrit à la
main (src/titres_connus.py) pour l'import des relevés (4.4.37).

Sources, données publiques :
  * Euronext, liste des actions (live.euronext.com, Produits, Actions,
    « Télécharger », CSV) : actions de Paris, Amsterdam, Bruxelles,
    Lisbonne, Milan et Dublin, sur leur place d'origine ;
  * Xetra, « All tradable instruments » (cashmarket.deutsche-boerse.com,
    t7-xetr-allTradableInstruments.csv) : actions allemandes, américaines
    et du monde entier, ETF, ETC et ETN, cotés en euros à Francfort (la
    cotation que suivent les CTO, Trade Republic en tête).

Chaque ticker est vérifié chez Yahoo : un cours en euros, échangé dans les 60
derniers jours ; sinon (Euronext), la recherche de l'ISIN donne le bon ticker
sur la même place, ou le titre n'est pas gardé. Demande internet, une
vingtaine de minutes :

    python tests/generer_titres.py <actions Euronext.csv> <Xetra.csv>
"""
import concurrent.futures
import csv
import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ICI, "..", "src"))
import server            # noqa: E402

# Place d'Euronext -> suffixe Yahoo (la première place citée quand le titre
# est coté sur plusieurs : « Euronext Paris, Brussels » -> Paris)
PLACES = {"Paris": ".PA", "Amsterdam": ".AS", "Brussels": ".BR", "Lisbon": ".LS",
          "Milan": ".MI", "Dublin": ".IR"}
# Marchés de cotation des sociétés (pas les titres étrangers recotés :
# Global Equity Market, EuroTLX, Trading After Hours, Expert Market)
MARCHES = ("Euronext ", "Euronext Growth ", "Euronext Access ")
GENRES_XETRA = {"CS": "action", "ETF": "etf", "ETC": "etc", "ETN": "etn"}


def lire_euronext(chemin):
    titres = {}
    with open(chemin, encoding="utf-8-sig") as f:
        for r in csv.reader(f, delimiter=";"):
            if len(r) < 5 or r[4] != "EUR" or not r[2] or r[2] == "-":
                continue
            nom, isin, sym, marche = r[0].strip(), r[1].strip(), r[2].strip(), r[3].strip()
            premier = marche.split(",")[0].strip()
            for m in MARCHES:
                if premier.startswith(m) and premier[len(m):] in PLACES:
                    titres.setdefault(isin, (isin, sym + PLACES[premier[len(m):]], nom, "action"))
    return list(titres.values())


def lire_xetra(chemin):
    with open(chemin, encoding="utf-8", errors="replace") as f:
        lignes = list(csv.reader(f, delimiter=";"))
    i = next(k for k, l in enumerate(lignes) if "ISIN" in l and "Mnemonic" in l)
    h = lignes[i]
    c = {n: h.index(n) for n in ("Instrument", "ISIN", "Mnemonic", "Instrument Type", "Currency",
                                  "Instrument Status")}
    titres = {}
    for r in lignes[i + 1:]:
        if len(r) <= max(c.values()) or r[c["Currency"]] != "EUR" or r[c["Instrument Status"]] != "Active":
            continue
        genre = GENRES_XETRA.get(r[c["Instrument Type"]])
        if genre and r[c["Mnemonic"]].strip():
            isin = r[c["ISIN"]].strip()
            # « MICROSOFT    DL-,00000625 » : le nominal suit le nom, après des espaces
            nom = r[c["Instrument"]].split("   ")[0].strip()
            titres.setdefault(isin, (isin, r[c["Mnemonic"]].strip() + ".DE", nom, genre))
    return list(titres.values())


def _meta(sym):
    url = ("https://query2.finance.yahoo.com/v8/finance/chart/" + urllib.parse.quote(sym)
           + "?interval=1d&range=3mo")
    req = urllib.request.Request(url, headers={"User-Agent": server.USER_AGENT, "Accept": "application/json"})
    for essai in range(4):
        try:
            with urllib.request.urlopen(req, timeout=10, context=server._SSL_CTX) as r:
                res = json.loads(r.read().decode())["chart"]["result"]
            return res[0]["meta"] if res else {}
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return {}
            time.sleep(3 + essai * 5)
        except Exception:
            time.sleep(3 + essai * 5)
    return None   # Yahoo injoignable : ni gardé ni écarté sans le dire


def _vivant(m):
    t = m.get("regularMarketTime") or 0
    return bool(m.get("regularMarketPrice") and m.get("currency") == "EUR"
                and time.time() - t < 60 * 86400)


def verifier(t):
    isin, sym = t[0], t[1]
    m = _meta(sym)
    if m is None:
        return t, None, "Yahoo injoignable"
    if m and _vivant(m):
        return t, sym, ""
    # Autre ticker chez Yahoo sur la même place : celui que rend son ISIN
    suf = "." + sym.rsplit(".", 1)[1]
    try:
        quotes = server._yahoo_search_brut(isin)
    except Exception:
        quotes = []
    for q in quotes:
        s = q.get("symbol") or ""
        if s.endswith(suf) and s != sym:
            m2 = _meta(s)
            if m2 and _vivant(m2):
                return t, s, ""
    return t, None, "pas de cours en euros récent chez Yahoo"


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    euronext, xetra = lire_euronext(sys.argv[1]), lire_xetra(sys.argv[2])
    print(len(euronext), "actions Euronext,", len(xetra), "titres Xetra", flush=True)
    titres = euronext + xetra
    res = []
    with concurrent.futures.ThreadPoolExecutor(8) as ex:
        for k, r in enumerate(ex.map(verifier, titres), 1):
            res.append(r)
            if k % 500 == 0:
                print(k, "vérifiés", flush=True)
    injoignables = [t for t, s, why in res if why == "Yahoo injoignable"]
    if injoignables:
        print(len(injoignables), "titres sans réponse de Yahoo : relance plus tard, rien n'est écrit")
        return 1
    gardes = sorted(((t[0], s, t[2], t[3]) for t, s, _ in res if s), key=lambda x: (x[2].lower(), x[1]))
    corriges = sum(1 for t, s, _ in res if s and s != t[1])
    par_genre = {}
    for g in gardes:
        par_genre[g[3]] = par_genre.get(g[3], 0) + 1
    jour = datetime.date.today().strftime("%d/%m/%Y")
    lignes = ['"""',
              "titres_listes.py — FICHIER FABRIQUÉ par tests/generer_titres.py, ne pas le",
              "modifier à la main (le relancer). Titres négociés en euros : actions",
              "d'Euronext sur leur place, et titres de Xetra (actions, ETF, ETC, ETN), listes",
              "officielles du " + jour + ", ticker Yahoo vérifié ce jour-là.",
              "Lu par titres_connus.py ; voir docs/import-releves.md.",
              '"""',
              "",
              "# (ISIN, ticker Yahoo, nom chez la bourse, genre : action, etf, etc, etn)",
              "TITRES = ["]
    lignes += [f"    ({isin!r}, {sym!r}, {nom!r}, {genre!r})," for isin, sym, nom, genre in gardes]
    lignes += ["]", ""]
    with open(os.path.join(ICI, "..", "src", "titres_listes.py"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lignes))
    print(f"{len(gardes)} gardés {par_genre} (dont {corriges} sous un autre ticker que celui de la "
          f"bourse), {len(res) - len(gardes)} écartés : pas de cours en euros récent chez Yahoo")
    return 0


if __name__ == "__main__":
    sys.exit(main())
