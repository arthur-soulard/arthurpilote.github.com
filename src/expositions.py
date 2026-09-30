"""
expositions.py — Composition des ETF pour l'onglet Expositions : pays, secteurs
et principales entreprises de l'indice que chaque ETF suit.

Les ETF d'un PEA sont presque tous synthetiques (swap) : ils detiennent un panier
d'actions europeennes et recoivent la performance de leur indice. Ce qui compte
pour l'exposition, c'est donc l'INDICE, jamais le panier detenu. Constate le
30/09/2026 : l'API Amundi renvoie pour PEMS (emergents) un panier ASML, Infineon,
Nordea... qui n'a rien a voir avec l'exposition reelle.

D'ou deux sortes de sources, toutes publiques :

* ``ishares`` : les lignes completes d'un ETF iShares PHYSIQUE qui suit le meme
  indice (MSCI World, S&P 500, Nasdaq-100, MSCI ACWI). Pays, secteurs et
  entreprises se calculent ligne par ligne.
* ``amundi_lignes`` : pareil, avec un ETF Amundi physique (STOXX Europe 600).
* ``amundi_indice`` : la repartition de l'indice publiee par Amundi (pays,
  secteurs, 10 premieres lignes), quand aucun ETF physique ne suit cet indice.

Ces donnees ne sont a personne : elles vivent au niveau de l'installation, dans
``Donnees/etf_compositions.json``, comme ``sauvegarde.json``. Les corrections
qu'un utilisateur fait a la main restent, elles, dans ses ``uiPrefs``.

Tant qu'aucune mise a jour n'a reussi, l'app se sert de ``expositions_base.py``,
releve le 30/09/2026 et livre avec le code : l'onglet marche hors ligne des le
premier lancement. Pour le regenerer : ``python src/expositions.py``.
"""
from __future__ import annotations

import datetime
import json
import os
import re
import tempfile
import threading
import traceback
import urllib.request
from pathlib import Path

import storage

try:
    from expositions_base import BASE      # compositions livrees avec l'app
except Exception:
    BASE = {}

FICHIER = "etf_compositions.json"
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Pilote"

ISHARES_API = ("https://www.ishares.com/varnish-api/uk-retail01-product-data/product-data/"
               "api/v2/get-product-data?appSubType=ISHARES&appType=PRODUCT_PAGE"
               "&component=holdings.all&locale=en_GB&portfolioId={pid}&targetSite=ishares-uk"
               "&userType=individual&excludeContent=true&includeConfig=true")
AMUNDI_API = "https://www.amundietf.fr/mapi/ProductAPI/getProductsData"

# Nombre d'entreprises gardees par ETF quand toutes ses lignes sont connues.
# Au-dela, chacune pese moins de 0,2 % de l'indice : inutile pour l'addition
# d'un ETF a l'autre, et le fichier resterait lourd pour rien.
NB_ENTREPRISES = 60

# ─── Les ETF suivis ──────────────────────────────────────────────────────────
# Cle = mnemonique Euronext (EPA:WPEA -> WPEA). « src » dit ou lire l'indice.
ETFS = {
    "WPEA": {"isin": "IE0002XZSHO1", "nom": "iShares MSCI World Swap PEA",
             "indice": "MSCI World", "src": ("ishares", 251882),
             "via": "iShares Core MSCI World (SWDA), même indice"},
    "PEMS": {"isin": "FR001400ZGO4", "nom": "Amundi PEA Emergent ESG Transition",
             "indice": "MSCI EM ex Egypt ESG Broad CTB Select",
             "src": ("amundi_indice", "FR001400ZGO4"), "via": "Amundi, indice de l'ETF"},
    "PNAS": {"isin": "FR001400ZGR7", "nom": "Amundi PEA Nasdaq-100",
             "indice": "Nasdaq-100", "src": ("ishares", 253741),
             "via": "iShares Nasdaq 100 (CNDX), même indice"},
    "PANX": {"isin": "FR0013412269", "nom": "Amundi PEA US Tech Screened",
             "indice": "Solactive ISS ESG US Tech 100",
             "src": ("amundi_indice", "FR0013412269"), "via": "Amundi, indice de l'ETF"},
    "ESE":  {"isin": "FR0011550185", "nom": "BNP Paribas Easy S&P 500",
             "indice": "S&P 500", "src": ("ishares", 253743),
             "via": "iShares Core S&P 500 (CSPX), même indice"},
    "ETZ":  {"isin": "FR0011550193", "nom": "BNP Paribas Easy STOXX Europe 600",
             "indice": "STOXX Europe 600", "src": ("amundi_lignes", "LU0908500753"),
             "via": "Amundi Core STOXX Europe 600 (MEUD), même indice"},
    # Pas l'iShares MSCI ACWI (SSAC) : il detient l'Inde, le Bresil, la Chine A et
    # l'Arabie saoudite via d'autres ETF, classes « Finance / Irlande » (2,4 %).
    "GPEA": {"isin": "FR0014017NX3", "nom": "Amundi PEA Global (MSCI ACWI)",
             "indice": "MSCI ACWI", "src": ("amundi_indice", "FR0014017NX3"),
             "via": "Amundi, indice de l'ETF"},
}

# ─── Noms des sources -> codes ───────────────────────────────────────────────
PAYS = {
    "United States": "US", "Canada": "CA", "United Kingdom": "GB", "France": "FR",
    "Germany": "DE", "Switzerland": "CH", "Netherlands": "NL", "Sweden": "SE",
    "Denmark": "DK", "Italy": "IT", "Spain": "ES", "Finland": "FI", "Belgium": "BE",
    "Norway": "NO", "Ireland": "IE", "Austria": "AT", "Portugal": "PT",
    "Luxembourg": "LU", "Iceland": "IS", "Malta": "MT", "Jersey": "JE",
    "Guernsey": "GG", "Isle of Man": "IM", "Monaco": "MC", "Gibraltar": "GI",
    "Japan": "JP", "Australia": "AU", "Hong Kong": "HK", "Singapore": "SG",
    "New Zealand": "NZ", "Macau": "MO", "Israel": "IL",
    "China": "CN", "Taiwan": "TW", "India": "IN", "South Korea": "KR",
    "Korea (South)": "KR", "Korea": "KR", "Brazil": "BR", "South Africa": "ZA",
    "Saudi Arabia": "SA", "Mexico": "MX", "United Arab Emirates": "AE", "UAE": "AE",
    "Poland": "PL", "Malaysia": "MY", "Thailand": "TH", "Greece": "GR",
    "Kuwait": "KW", "Peru": "PE", "Indonesia": "ID", "Qatar": "QA", "Chile": "CL",
    "Turkey": "TR", "Hungary": "HU", "Philippines": "PH", "Colombia": "CO",
    "Czech Republic": "CZ", "Egypt": "EG", "Russian Federation": "RU", "Russia": "RU",
    "Argentina": "AR", "Uruguay": "UY", "Vietnam": "VN", "Pakistan": "PK",
    "Kazakhstan": "KZ", "Cyprus": "CY", "Cayman Islands": "KY", "Cayman Island": "KY",
    "Bermuda": "BM", "Panama": "PA", "Puerto Rico": "PR", "Curacao": "CW",
    "Bahamas": "BS", "Liberia": "LR", "Zambia": "ZM", "Virgin Islands (British)": "VG",
}
SECTEURS = {
    "Information Technology": "it", "Financials": "fin", "Industrials": "ind",
    "Health Care": "sante", "Consumer Discretionary": "discr",
    "Communication": "comm", "Communication Services": "comm",
    "Consumer Staples": "base", "Energy": "energie", "Materials": "mat",
    "Utilities": "util", "Real Estate": "immo",
}

# Une meme entreprise cotee sous plusieurs categories d'actions (Alphabet A et C,
# Samsung ordinaire et preferentielle) : on les additionne sous le premier ISIN.
MEME_ENTREPRISE = {
    "US02079K1079": "US02079K3059",   # Alphabet C -> A
    "KR7005931001": "KR7005930003",   # Samsung preferentielle -> ordinaire
    "US0846701086": "US0846707026",   # Berkshire A -> B
    "USN070592100": "NL0010273215",   # ASML : ADR du Nasdaq-100 -> action d'Amsterdam
}
# Noms d'usage des plus grosses lignes (les sources ecrivent « NVIDIA CORP »,
# « TAIWAN SEMICONDUCTOR MANUFAC »...). Le reste passe par _joli_nom().
NOMS = {
    "US67066G1040": "Nvidia", "US0378331005": "Apple", "US5949181045": "Microsoft",
    "US0231351067": "Amazon", "US02079K3059": "Alphabet (Google)",
    "US30303M1027": "Meta", "US11135F1012": "Broadcom", "US88160R1014": "Tesla",
    "US5951121038": "Micron", "US0079031078": "AMD", "US5324571083": "Eli Lilly",
    "US46625H1005": "JPMorgan Chase", "US0846707026": "Berkshire Hathaway",
    "US30233Q1085": "ExxonMobil", "US92826C8394": "Visa", "US57636Q1040": "Mastercard",
    "US4581401001": "Intel", "US9311421039": "Walmart", "US4781601046": "Johnson & Johnson",
    "US00287Y1091": "AbbVie", "US0382221051": "Applied Materials",
    "US84615Q1031": "SpaceX", "US69608A1088": "Palantir", "US17275R1023": "Cisco",
    "US22160K1051": "Costco", "US5128073062": "Lam Research", "US64110L1061": "Netflix",
    "TW0002330008": "TSMC", "KR7005930003": "Samsung Electronics",
    "KR7000660001": "SK Hynix", "KYG875721634": "Tencent", "KYG017191142": "Alibaba",
    "TW0002454006": "MediaTek", "TW0002308004": "Delta Electronics",
    "TW0002317005": "Hon Hai (Foxconn)", "CNE1000002H1": "China Construction Bank",
    "NL0010273215": "ASML", "GB0005405286": "HSBC", "CH1499059983": "Roche",
    "CH0012005267": "Novartis", "GB00BP6MXD84": "Shell", "GB0009895292": "AstraZeneca",
    "CH0038863350": "Nestlé", "DE0007236101": "Siemens", "ES0113900J37": "Banco Santander",
    "DE0007164600": "SAP", "FR0000120271": "TotalEnergies", "FR0000121972": "Schneider Electric",
    "FR0000121014": "LVMH", "ES0113211835": "BBVA", "DK0062498333": "Novo Nordisk",
    "CH0210483332": "Richemont", "GB00BVZK7T90": "Unilever", "DE0005557508": "Deutsche Telekom",
    "GB0007188757": "Rio Tinto", "US8725901040": "T-Mobile US", "US4592001014": "IBM",
    "US58733R1023": "MercadoLibre", "US25809K1051": "DoorDash", "US91324P1021": "UnitedHealth",
    "US1912161007": "Coca-Cola", "JP3902900004": "Mitsubishi UFJ",
    "US8825081040": "Texas Instruments", "BE0974293251": "AB InBev",
    "SE0015811963": "Investor AB", "DE0008430026": "Munich Re", "FI4000297767": "Nordea",
    "ES0148396007": "Inditex", "IT0003132476": "Eni",
}

# ─── Petits outils ───────────────────────────────────────────────────────────

# Tout ce qui suit la raison sociale : categorie d'action, certificat americain
# (ADR), place de cotation. « NOVO NORDISK A/S-B », « RIO TINTO PLC (GBR) »...
_SUFFIXES = re.compile(
    r"\(.*?\)"
    r"|\s+(ADR|ADS|REPRESENTING|AMERICAN DEPOSITARY|SUBORDINATE|SERIES|NY REG|NAMEN|SHS)\b.*$"
    r"|\s*[-/]\s*(CLASS|CL)\s+[A-Z]\b.*$|\s+(CLASS|CL)\s+[A-Z]\b.*$"
    r"|\s+-\s+.*$|\s*/\s*XETRA.*$|-REG\b.*$|\s+REG\b.*$|\s+A/S\b.*$|-[AB]\b.*$"
)
_MOTS_JURIDIQUES = {"INC", "INC.", "CORP", "CORP.", "CORPORATION", "PLC", "LTD", "LTD.",
                    "LIMITED", "CO", "SA", "SE", "AG", "NV", "N.V.", "ASA", "AB", "OYJ",
                    "SPA", "S.P.A.", "HOLDING", "HOLDINGS", "EUR", "GBP", "CHF", "PARIS",
                    "MADRID", "LONDON", "MILAN", "BRUXELLES", "AMSTERDAM", "SA/NV", "ABP",
                    "PFD", "ADR"}
_PETITS_MOTS = {"OF", "AND", "THE", "DE", "LA", "DU", "DES"}
_SIGLES = {"ASML", "SAP", "HSBC", "AMD", "UBS", "BNP", "AXA", "LVMH", "ABB", "RELX",
           "BHP", "IBM", "GE", "BBVA", "ING", "DBS", "AIA", "BYD", "CATL", "ICICI",
           "HDFC", "TSMC", "KLA", "NXP", "ARM", "PDD", "3M", "AT&T", "CME", "S&P",
           "RTX", "UBER", "BAE", "GSK", "BP", "RWE", "EON", "E.ON", "SK", "LG", "JD",
           "UFJ", "CSX", "US", "DHL", "HCA", "AIG", "CVS", "PNC", "MSCI", "EOG", "NTT",
           "KDDI", "SMC", "TDK", "ANZ", "CIBC", "DSV", "KBC", "SEB", "OMV", "EDP", "ENI"}


def _joli_nom(brut: str) -> str:
    """« TOTALENERGIES SE PARIS » -> « Totalenergies »... a peu pres : les
    noms qui comptent sont dans NOMS."""
    s = _SUFFIXES.sub(" ", (brut or "").strip().upper()).strip()
    mots = [m for m in s.split() if m not in _MOTS_JURIDIQUES]
    while mots and mots[-1] == "&":           # « JPMORGAN CHASE & CO » sans le CO
        mots.pop()
    if not mots:
        mots = s.split() or [brut or ""]
    def mot(m, i):
        if m in _SIGLES:
            return m
        if i and m in _PETITS_MOTS:
            return m.lower()
        return "-".join(p.capitalize() for p in m.split("-"))
    return " ".join(mot(m, i) for i, m in enumerate(mots))


def _get_json(url: str, body: dict = None, timeout: int = 45) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"User-Agent": _UA, "Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers,
                                 method="POST" if data is not None else "GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _r(x: float, n: int = 3) -> float:
    return round(float(x), n)


# ─── Lecture des sources ─────────────────────────────────────────────────────
# Chacune rend une liste de lignes {nom, isin, pct, pays, secteur} (actions
# seulement), ou directement une repartition deja agregee (amundi_indice).

def _lignes_ishares(pid: int) -> tuple:
    d = _get_json(ISHARES_API.format(pid=pid))
    dp = d["componentsByNameMap"]["holdings"]["containersByNameMap"]["all"]["dataPointsByNameMap"]
    col = lambda k: dp[k]["value"]
    lignes = []
    for nom, isin, pct, pays, sect, classe in zip(col("issueName"), col("isin"),
                                                  col("holdingPercent"), col("countryOfRisk"),
                                                  col("sectorName"), col("assetClass")):
        if classe != "Equity" or not pct:
            continue
        lignes.append({"nom": nom or "", "isin": isin or "", "pct": float(pct),
                       "pays": pays or "", "secteur": sect or ""})
    return lignes, str(dp["asOfDate"]["value"])


def _lignes_amundi(isin: str) -> tuple:
    body = {"context": {"countryCode": "FRA", "languageCode": "fr", "userProfileName": "RETAIL"},
            "productIds": [isin], "productType": "PRODUCT",
            "composition": {"compositionFields": ["date", "type", "isin", "name", "weight",
                                                  "sector", "countryOfRisk"]}}
    rows = _get_json(AMUNDI_API, body)["products"][0]["composition"]["compositionData"]
    lignes, date = [], ""
    for r in rows:
        c = r.get("compositionCharacteristics") or {}
        if c.get("type") not in ("EQUITY_ORDINARY", "PREFERENCE_SHARES") or not r.get("weight"):
            continue
        date = date or (c.get("date") or "")
        lignes.append({"nom": c.get("name") or "", "isin": c.get("isin") or "",
                       "pct": float(r["weight"]) * 100, "pays": c.get("countryOfRisk") or "",
                       "secteur": c.get("sector") or ""})
    return lignes, date


def _indice_amundi(isin: str) -> dict:
    body = {"context": {"countryCode": "FRA", "languageCode": "fr", "userProfileName": "RETAIL"},
            "productIds": [isin], "productType": "PRODUCT",
            "characteristics": ["INDEX_BREAKDOWNS_AS_OF_DATE"],
            "breakDown": {"aggregationFields": ["INDEX_TOP10", "INDEX_SECTORS", "INDEX_COUNTRIES"]}}
    p = _get_json(AMUNDI_API, body)["products"][0]
    bd = {b.get("aggregationField"): b.get("breakDownData") or [] for b in p.get("breakDowns") or []}
    pays, secteurs, inconnus = {}, {}, []
    for x in bd.get("INDEX_COUNTRIES", []):
        code = PAYS.get(x.get("aggregationName"))
        if not code:
            inconnus.append(x.get("aggregationName"))
            code = x.get("aggregationName") or "?"
        pays[code] = pays.get(code, 0) + float(x.get("weight") or 0) * 100
    for x in bd.get("INDEX_SECTORS", []):
        sid = SECTEURS.get(x.get("aggregationName"), "autres")
        secteurs[sid] = secteurs.get(sid, 0) + float(x.get("weight") or 0) * 100
    # Les 10 premieres lignes portent leur poids dans « adjustedWeight »
    lignes = []
    for x in bd.get("INDEX_TOP10", []):
        a = x.get("additionalProperties") or {}
        lignes.append({"nom": x.get("aggregationName") or "", "isin": a.get("isin") or "",
                       "pct": float(x.get("adjustedWeight") or x.get("weight") or 0) * 100,
                       "pays": a.get("countryOfRisk") or "", "secteur": a.get("sector") or ""})
    return {"pays": pays, "secteurs": secteurs, "entreprises": _entreprises(lignes),
            "lignes": None, "date": (p.get("characteristics") or {}).get("INDEX_BREAKDOWNS_AS_OF_DATE", ""),
            "inconnus": inconnus}


# ─── Agregation ──────────────────────────────────────────────────────────────

def _entreprises(lignes: list, nb: int = NB_ENTREPRISES) -> list:
    """Additionne les categories d'une meme entreprise, trie, garde les nb premieres."""
    par = {}
    for l in lignes:
        if l["pct"] <= 0:
            continue
        isin = MEME_ENTREPRISE.get(l["isin"], l["isin"]) or l["nom"]
        e = par.get(isin)
        if e is None:
            e = par[isin] = {"id": isin, "nom": NOMS.get(isin) or _joli_nom(l["nom"]),
                             "pct": 0.0, "pays": PAYS.get(l["pays"], ""),
                             "secteur": SECTEURS.get(l["secteur"], "autres")}
        e["pct"] += l["pct"]
    out = sorted(par.values(), key=lambda e: -e["pct"])[:nb]
    for e in out:
        e["pct"] = _r(e["pct"])
    return out


def _depuis_lignes(lignes: list) -> dict:
    """Pays, secteurs et entreprises calcules ligne par ligne, ramenes a 100 %."""
    total = sum(l["pct"] for l in lignes) or 1.0
    for l in lignes:
        l["pct"] = l["pct"] * 100.0 / total
    pays, secteurs, inconnus = {}, {}, []
    for l in lignes:
        code = PAYS.get(l["pays"])
        if not code:
            if l["pays"] and l["pays"] not in inconnus:
                inconnus.append(l["pays"])
            code = l["pays"] or "?"
        pays[code] = pays.get(code, 0) + l["pct"]
        sid = SECTEURS.get(l["secteur"], "autres")
        secteurs[sid] = secteurs.get(sid, 0) + l["pct"]
    return {"pays": pays, "secteurs": secteurs, "entreprises": _entreprises(lignes),
            "lignes": len(lignes), "inconnus": inconnus}


def _valider(c: dict) -> None:
    """Refuse une lecture incoherente : mieux vaut garder l'ancienne composition."""
    for cle in ("pays", "secteurs"):
        s = sum(c[cle].values())
        if not c[cle] or not (97.0 <= s <= 101.5):
            raise ValueError(f"{cle} : total {s:.1f} % au lieu de 100 %")
    if not c["entreprises"]:
        raise ValueError("aucune entreprise lue")


def recuperer(ticker: str) -> dict:
    """Telecharge et calcule la composition d'un ETF de ETFS."""
    info = ETFS[ticker]
    genre, ref = info["src"]
    if genre == "ishares":
        lignes, date = _lignes_ishares(ref)
        c = _depuis_lignes(lignes)
    elif genre == "amundi_lignes":
        lignes, date = _lignes_amundi(ref)
        c = _depuis_lignes(lignes)
    else:
        c = _indice_amundi(ref)
        date = c.pop("date", "")
    if len(date) == 8 and date.isdigit():             # 20260929 -> 2026-09-29
        date = f"{date[:4]}-{date[4:6]}-{date[6:]}"
    _valider(c)
    for cle in ("pays", "secteurs"):
        c[cle] = {k: _r(v) for k, v in sorted(c[cle].items(), key=lambda kv: -kv[1])
                  if _r(v) > 0}
    c.update({"isin": info["isin"], "nom": info["nom"], "indice": info["indice"],
              "source": info["via"], "date": date,
              "releve": datetime.date.today().isoformat()})
    return c


# ─── Fichier de l'installation ───────────────────────────────────────────────

def _path() -> Path:
    return storage.get_app_dir() / FICHIER


def _lire_fichier() -> dict:
    try:
        with open(_path(), "r", encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _ecrire_fichier(d: dict) -> None:
    path = _path()
    fd, tmp = tempfile.mkstemp(prefix=".etf_compositions_", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
    except Exception:
        try:
            os.remove(tmp)
        except Exception:
            pass
        raise


def charger() -> dict:
    """Compositions a utiliser : celles livrees avec l'app, remplacees ETF par ETF
    par la derniere mise a jour reussie."""
    etfs = {k: dict(v, origine="integre") for k, v in BASE.items()}
    f = _lire_fichier()
    for k, v in (f.get("etfs") or {}).items():
        # Une mise a jour plus ancienne que les donnees livrees ne les ecrase pas
        if k not in etfs or (v.get("date") or "") >= (etfs[k].get("date") or ""):
            etfs[k] = dict(v, origine="maj")
    return {"etfs": etfs, "maj": f.get("maj"), "suivis": list(ETFS.keys())}


# ─── Mise a jour en arriere-plan (bouton de l'onglet) ────────────────────────

_lock = threading.Lock()
_etat = {"enCours": False, "pct": 0, "etape": "", "fini": False,
         "ok": [], "erreurs": [], "maj": None}


def etat() -> dict:
    with _lock:
        return json.loads(json.dumps(_etat))


def _set(**kw) -> None:
    with _lock:
        _etat.update(kw)


def lancer_mise_a_jour() -> bool:
    """Demarre la mise a jour dans un thread. False si elle tourne deja."""
    with _lock:
        if _etat["enCours"]:
            return False
        _etat.update({"enCours": True, "pct": 1, "etape": "Connexion…", "fini": False,
                      "ok": [], "erreurs": []})
    threading.Thread(target=_mettre_a_jour, daemon=True).start()
    return True


def _mettre_a_jour() -> None:
    ok, erreurs, nouveaux = [], [], {}
    tickers = list(ETFS.keys())
    try:
        for i, t in enumerate(tickers):
            _set(etape=f"{t} ({i + 1}/{len(tickers)})", pct=int(2 + i * 94 / len(tickers)))
            try:
                nouveaux[t] = recuperer(t)
                ok.append(t)
            except Exception as e:
                erreurs.append({"etf": t, "erreur": str(e)[:200]})
                print(f"[expositions] {t} KO : {e}", flush=True)
        _set(etape="Enregistrement…", pct=97)
        if nouveaux:
            f = _lire_fichier()
            f.setdefault("etfs", {}).update(nouveaux)
            f["maj"] = datetime.datetime.now().isoformat(timespec="seconds")
            _ecrire_fichier(f)
        _set(enCours=False, fini=True, pct=100, etape="", ok=ok, erreurs=erreurs,
             maj=datetime.datetime.now().isoformat(timespec="seconds") if nouveaux else None)
    except Exception as e:
        traceback.print_exc()
        _set(enCours=False, fini=True, pct=100, etape="", ok=ok,
             erreurs=erreurs + [{"etf": "", "erreur": str(e)[:200]}])


# ─── Regenerer les donnees livrees avec l'app ────────────────────────────────

if __name__ == "__main__":
    import pprint
    base = {}
    for t in ETFS:
        c = recuperer(t)
        c.pop("inconnus", None)
        base[t] = c
        print(t, c["date"], len(c["pays"]), "pays", len(c["secteurs"]), "secteurs",
              len(c["entreprises"]), "entreprises")
    cible = Path(__file__).resolve().parent / "expositions_base.py"
    with open(cible, "w", encoding="utf-8", newline="\n") as f:
        f.write('"""Compositions livrees avec l\'app (voir expositions.py).\n'
                "Fichier genere par `python src/expositions.py` : ne pas modifier a la main.\n"
                f'Releve du {datetime.date.today().isoformat()}."""\n\n')
        f.write("BASE = " + pprint.pformat(base, width=100, sort_dicts=False) + "\n")
    print("ecrit :", cible)
