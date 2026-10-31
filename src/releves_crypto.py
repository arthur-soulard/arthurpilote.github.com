"""
releves_crypto.py — Exports des plateformes crypto, pour le portefeuille
crypto (31/10/2026).

Appelé par releves.lire_tableau, qui reconnaît la plateforme à ses colonnes :
Binance (relevé de compte « Transaction History » et historique des ordres),
Coinbase, Kraken (ledgers et trades), Bitpanda, Crypto.com (application),
Revolut (relevé crypto), Bitvavo et Delta (appli de suivi). Trade Republic
est lu par cto.lire_csv_tr, eToro par releves._etoro.

Colonnes et types d'opérations relevés dans les lecteurs de BittyTax
(github.com/BittyTax/BittyTax, conv/parsers), écrits sur de vrais exports ;
Bitvavo et Delta d'après leur documentation (support.delta.app). Aucun vrai
export n'a été essayé ici (31/10/2026) : à vérifier sur le premier reçu.

Ce que devient chaque ligne :
  achat ou vente contre euros (ou une autre monnaie, convertie au cours du
      jour) -> un achat ou une vente de la crypto ;
  échange d'une crypto contre une autre (BTC -> ETH, achat en USDT) -> une
      vente de l'une et un achat de l'autre, à la valeur en euros que donne
      l'export, sinon au cours de clôture du jour (Yahoo, paire XXX-EUR) ;
  frais payés dans une crypto (BNB chez Binance) -> comptés en euros, et la
      crypto qui les paie diminue d'autant ;
  récompense (staking, intérêts, cashback, parrainage, airdrop) -> un achat
      « offert » à sa valeur du jour, comme une action offerte de Trade
      Republic : la quantité suit celle de la plateforme ;
  envoi ou réception de crypto (vers un portefeuille, une autre plateforme)
      -> ignoré et compté (« transferts ») : la crypto a été achetée ailleurs ;
  dépôt ou retrait d'euros -> versement ou retrait (que le compte déduit
      des ordres, comme un CTO).
Toutes les opérations portent compte « CRYPTO » : un fichier ouvert depuis le
PEA ou un CTO propose de les envoyer dans la section Crypto.
"""
from __future__ import annotations

import re

import cto

FIAT = {"EUR", "USD", "GBP", "CHF", "CAD", "AUD", "JPY", "PLN", "SEK", "NOK", "DKK", "CZK", "HUF", "TRY", "BRL"}
# Symbole Yahoo quand il diffère du symbole courant (même table que
# CRYPTO_CATALOGUE dans index.html)
_YAHOO = {"UNI": "UNI7083"}
# Noms d'usage -> symbole : le lecteur universel reconnaît une crypto à son nom
NOMS = {"bitcoin": "BTC", "ethereum": "ETH", "solana": "SOL", "xrp": "XRP", "ripple": "XRP", "bnb": "BNB",
        "cardano": "ADA", "dogecoin": "DOGE", "tron": "TRX", "chainlink": "LINK", "avalanche": "AVAX",
        "stellar": "XLM", "bitcoin cash": "BCH", "litecoin": "LTC", "polkadot": "DOT", "hedera": "HBAR",
        "uniswap": "UNI", "aave": "AAVE", "ethereum classic": "ETC", "cosmos": "ATOM",
        "internet computer": "ICP", "filecoin": "FIL", "algorand": "ALGO", "tezos": "XTZ",
        "tether": "USDT", "usd coin": "USDC"}
SYMBOLES = set(NOMS.values()) | {"USDT", "USDC", "DAI", "EURC", "SHIB", "PEPE", "POL", "MATIC", "NEAR", "SUI",
                                 "TON", "APT", "ARB", "OP", "CRO", "KAS", "INJ", "RNDR", "RENDER", "MKR"}


def est_crypto(nom: str) -> bool:
    """Un nom de titre qui désigne une crypto (« Bitcoin », « BTC »)."""
    n = (nom or "").strip()
    return n.lower() in NOMS or n.upper() in SYMBOLES


def symbole(s: str) -> str:
    """Symbole d'usage : ceux de Kraken (XXBT, XETH, ZEUR, XBT, XDG), les
    versions « en staking » (ETH2.S, DOT.S, SOL03.S, ADA.M) ramenées à la crypto."""
    s = (s or "").strip().upper()
    s = re.sub(r"(\d\d)?\.(S|M|F|B|P|HOLD|CORE|INK)$", "", s)
    if len(s) == 4 and s[0] in "XZ" and s[1:] in FIAT | {"XBT", "ETH", "LTC", "XRP", "XLM", "XDG", "ETC", "ZEC", "XMR", "MLN", "REP"}:
        s = s[1:]
    s = {"XBT": "BTC", "XDG": "DOGE", "ETH2": "ETH"}.get(s, s)
    return s


def _num(v):
    """Nombre d'un export crypto : « 0.00123 », « €1,234.56 », « -$30.93 », « 0,5 »."""
    if v is None:
        return None
    t = re.sub(r"[€$£]", "", str(v)).strip()
    if t in ("", "-", "—"):
        return None
    return cto._nombre(t)


_cours_cache = {}


def cours_eur(sym: str, date: str):
    """Cours de clôture en euros d'une crypto ce jour-là (Yahoo, XXX-EUR), le
    dernier connu avant ; None si introuvable."""
    sym = symbole(sym)
    if sym == "EUR":
        return 1.0
    cle = (sym, date)
    if cle not in _cours_cache:
        import server   # ici et pas en tête : se teste sans le serveur
        tk = _YAHOO.get(sym, sym) + "-EUR"
        val = None
        try:
            h = server.get_history([tk], "max", since=date).get(tk) or {}
            avant = [c for d, c in zip(h.get("dates", []), h.get("closes", [])) if d <= date and c]
            val = avant[-1] if avant else None
        except Exception:
            val = None
        _cours_cache[cle] = val
    return _cours_cache[cle]


def _eur(sym, qty, date):
    """Valeur en euros d'une quantité d'euros, d'une autre monnaie ou d'une crypto."""
    sym = symbole(sym)
    if qty is None:
        return None
    if sym == "EUR":
        return abs(qty)
    if sym in FIAT:
        return releves._vers_eur(abs(qty), sym, date)
    c = cours_eur(sym, date)
    return abs(qty) * c if c else None


def _compte(op):
    if op:
        op["compte"] = "CRYPTO"
    return op


def _compter(lot, cle):
    lot.ignores[cle] = lot.ignores.get(cle, 0) + 1


def _ajoute(lot, type_, date, sym, qty, montant, frais=0.0, quand="", ref="", origine=None):
    return _compte(lot.ajoute(type_, date, "", symbole(sym), qty, None, montant, frais,
                              quand=quand, ref=ref, origine=origine, classe="crypto"))


def echange(lot, date, quand, sortie, entree, frais=None, ref="", valeur=None):
    """Une opération qui fait sortir (sym, qté) et entrer (sym, qté), avec des
    frais éventuels (sym, qté). valeur : sa valeur en euros quand l'export la
    donne. Achat, vente, ou les deux pour un échange entre cryptos."""
    s_sym, s_q = symbole(sortie[0]), abs(sortie[1] or 0)
    e_sym, e_q = symbole(entree[0]), abs(entree[1] or 0)
    f_sym, f_q = (symbole(frais[0]), abs(frais[1] or 0)) if frais and frais[1] else ("", 0.0)
    if not s_q or not e_q or s_sym == e_sym:
        lot.inconnues.append({"date": date, "type": "Échange incomplet", "nom": s_sym + " -> " + e_sym, "compte": "CRYPTO"})
        return
    s_fiat, e_fiat = s_sym in FIAT, e_sym in FIAT
    if s_fiat and e_fiat:   # change entre monnaies : rien à suivre
        _compter(lot, "especes")
        return
    v = valeur if valeur else (_eur(s_sym, s_q, date) if s_fiat else _eur(e_sym, e_q, date) if e_fiat
                               else (_eur(e_sym, e_q, date) or _eur(s_sym, s_q, date)))
    if not v:
        _compter(lot, "conversion")
        return
    f_eur = (_eur(f_sym, f_q, date) or 0) if f_q else 0
    # Frais payés dans une troisième crypto (BNB) : elle diminue d'autant
    tiers = f_q and f_sym not in (s_sym, e_sym) and f_sym not in FIAT
    if tiers:
        _ajoute(lot, "Vente", date, f_sym, f_q, f_eur, 0, quand, (ref + ":f") if ref else "")
    if not e_fiat:   # achat de la crypto qui entre
        q, brut = e_q, v
        if f_q and f_sym == e_sym:      # frais pris sur la crypto reçue
            q, brut = e_q - f_q, v - f_eur
        part = f_eur if (f_sym == e_sym or s_fiat or tiers or f_sym in FIAT) else 0
        if q > 0:
            _ajoute(lot, "Achat", date, e_sym, q, brut, part, quand, (ref + ":a") if ref else "")
    if not s_fiat:   # vente de la crypto qui sort
        q, brut = s_q, v
        if f_q and f_sym == s_sym:      # frais pris sur la crypto vendue
            q, brut = s_q + f_q, v + f_eur
        part = f_eur if (f_sym == s_sym or (e_fiat and (tiers or f_sym in FIAT))) else 0
        _ajoute(lot, "Vente", date, s_sym, q, brut, part, quand, (ref + ":v") if ref else "")


def recompense(lot, date, quand, sym, qty, valeur=None, ref=""):
    """Staking, intérêts, cashback, parrainage : un achat offert à sa valeur du jour."""
    sym, qty = symbole(sym), abs(qty or 0)
    if not qty or sym in FIAT:
        _compter(lot, "especes")
        return
    v = valeur or _eur(sym, qty, date)
    if not v:
        _compter(lot, "conversion")
        return
    _ajoute(lot, "Achat", date, sym, qty, v, 0, quand, ref, origine="offert")


def especes(lot, date, quand, sym, montant, ref=""):
    """Dépôt (montant > 0) ou retrait d'une monnaie, ou transfert d'une crypto."""
    sym = symbole(sym)
    if sym not in FIAT:
        _compter(lot, "transferts_crypto")
        return
    eur = _eur(sym, montant, date)
    if eur:
        _compte(lot.ajoute("Versement" if montant > 0 else "Retrait", date, montant=eur,
                           origine="especes", quand=quand, ref=ref))


def _quand(v: str) -> str:
    """« 2024-01-05 10:00:00 », « 2024-01-05T10:00:00Z » -> 2024-01-05T10:00:00."""
    m = re.search(r"(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}(?::\d{2})?)", v or "")
    return m.group(1) + "T" + m.group(2) if m else releves._date_fr(v or "")


_RECOMPENSE = re.compile(r"(?i)reward|interest|staking income|stake reward|cashback|referral|commission|rebate|"
                         r"airdrop|distribution|bonus|learn|earn income|mining|gift|campaign|voucher|kickback|income|dividend")
_INTERNE = re.compile(r"(?i)subscription|redemption|transfer between|transfer funds|lock|unlock|stake$|unstake|"
                      r"allocation|program_created|program_withdrawn|swap_debited|swap_credited|purchase_lock|"
                      r"purchase_unlock|sell_lock|sell_unlock|to_exchange|exchange_to|spottostaking|stakingtospot|"
                      r"spotfromfutures|internal")


# ─── Binance ──────────────────────────────────────────────────────────────────

_BN_ORDRE = {"buy", "sell", "fee", "transaction related", "transaction buy", "transaction fee", "transaction spend",
             "transaction sold", "transaction revenue", "binance convert", "large otc trading",
             "small assets exchange bnb", "buy crypto with card", "buy crypto", "sell crypto", "convert"}


def _binance_releve(c, lignes, lot):
    """Relevé de compte (« Transaction History ») : une ligne par mouvement
    d'une crypto ; un ordre en fait plusieurs à la même seconde (dépense,
    achat, frais), regroupées ici."""
    g = lambda r, k: r[c[k]].strip() if k in c and c[k] < len(r) else ""
    ordres = {}
    for r in lignes:
        quand, op, coin = _quand(g(r, "utc_time")), g(r, "operation"), g(r, "coin")
        compte, chg = g(r, "account").lower(), _num(g(r, "change"))
        date = quand[:10]
        if not date or chg is None or not coin:
            continue
        if compte and compte not in ("spot", "earn", "pool", "savings", "funding", "simple earn"):
            _compter(lot, "classe")   # marge, contrats à terme
            continue
        o = op.lower()
        if o in _BN_ORDRE:
            ordres.setdefault(quand, []).append((o, coin, chg))
        elif o in ("deposit", "withdraw", "fiat deposit", "fiat withdraw", "fiat withdrawal", "send", "receive"):
            especes(lot, date, quand, coin, chg)
        elif _INTERNE.search(o):
            continue
        elif _RECOMPENSE.search(o) and chg > 0:
            recompense(lot, date, quand, coin, chg)
        else:
            lot.inconnues.append({"date": date, "type": op, "nom": coin, "compte": "CRYPTO"})
    for quand, rows in ordres.items():
        mvt, fr = {}, {}
        for o, coin, chg in rows:
            d = fr if "fee" in o else mvt
            d[coin] = d.get(coin, 0) + chg
        sorties = [(k, v) for k, v in mvt.items() if v < 0]
        entrees = [(k, v) for k, v in mvt.items() if v > 0]
        if len(sorties) != 1 or len(entrees) != 1:
            lot.inconnues.append({"date": quand[:10], "type": "Ordre Binance", "nom": " ".join(mvt), "compte": "CRYPTO"})
            continue
        frais = next(iter(fr.items())) if fr else None
        echange(lot, quand[:10], quand, sorties[0], entrees[0], frais, ref="bn:" + quand)


_COTATIONS = ["FDUSD", "USDT", "USDC", "BUSD", "TUSD", "EUR", "USD", "GBP", "TRY", "BTC", "ETH", "BNB", "DAI"]


def _paire(p: str):
    """« BTCEUR », « BTC/EUR », « BTC-EUR », « XXBTZEUR » -> (BTC, EUR)."""
    p = (p or "").upper().strip()
    for sep in ("/", "-", "_"):
        if sep in p:
            a, b = p.split(sep, 1)
            return symbole(a), symbole(b)
    for q in ["ZEUR", "ZUSD", "ZGBP", "XXBT", "XETH"] + _COTATIONS + ["XBT", "CHF"]:
        if p.endswith(q) and len(p) > len(q):
            return symbole(p[:-len(q)]), symbole(q)
    return None, None


def _qte_sym(v: str):
    """« 0.00100000BTC » -> (0.001, BTC)."""
    m = re.fullmatch(r"\s*([-\d.,]+)\s*([A-Za-z0-9]+)\s*", v or "")
    return (_num(m.group(1)), m.group(2).upper()) if m else (None, "")


def _binance_ordres(c, lignes, lot):
    """Historique des ordres au comptant : Date(UTC), Pair, Side, Price,
    Executed (« 0.001BTC »), Amount (« 40EUR »), Fee (« 0.000001BTC ») ; ou
    l'ancien : Market, Type, Amount, Total, Fee, Fee Coin."""
    g = lambda r, k: r[c[k]].strip() if k in c and c[k] < len(r) else ""
    for r in lignes:
        quand = _quand(g(r, "date(utc)") or g(r, "date"))
        date = quand[:10]
        if "executed" in c:
            q, base = _qte_sym(g(r, "executed"))
            m, quote = _qte_sym(g(r, "amount"))
            f, fsym = _qte_sym(g(r, "fee"))
            sens = g(r, "side").lower()
        else:
            base, quote = _paire(g(r, "market"))
            q, m = _num(g(r, "amount")), _num(g(r, "total"))
            f, fsym = _num(g(r, "fee")), g(r, "fee coin").upper()
            sens = g(r, "type").lower()
        if not date or not q or not m or not base:
            continue
        frais = (fsym, f) if f else None
        if sens == "buy":
            echange(lot, date, quand, (quote, m), (base, q), frais)
        elif sens == "sell":
            echange(lot, date, quand, (base, q), (quote, m), frais)


# ─── Coinbase ─────────────────────────────────────────────────────────────────

def _coinbase(c, lignes, lot):
    """Coinbase : Timestamp, Transaction Type, Asset, Quantity Transacted,
    Price Currency, Price at Transaction, Subtotal, Total (inclusive of fees
    and/or spread), Fees and/or Spread, Notes ; les montants dans la monnaie
    du compte (« €40.00 »), selon la version aussi « EUR Subtotal »…"""
    col = lambda ok: next((i for k, i in c.items() if ok(k)), None)
    i_dev = col(lambda k: k in ("price currency", "spot price currency"))
    i_sub = col(lambda k: k == "subtotal" or k.endswith(" subtotal"))
    i_fee = col(lambda k: k in ("fees and/or spread", "fees") or re.fullmatch(r"[a-z]{3} fees", k))
    i_tot = col(lambda k: "total (inclusive" in k)
    g = lambda r, i: r[i].strip() if i is not None and i < len(r) else ""
    devise_tete = next((k.split(" ")[0].upper() for k in c if re.fullmatch(r"[a-z]{3} subtotal", k)), "")
    for r in lignes:
        quand = _quand(g(r, c.get("timestamp")))
        date = quand[:10]
        typ, sym = g(r, c.get("transaction type")).lower(), g(r, c.get("asset")).upper()
        qty = _num(g(r, c.get("quantity transacted")))
        notes, ref = g(r, c.get("notes")), g(r, c.get("id"))
        if not date or not sym or qty is None:
            continue
        dev = (g(r, i_dev) or devise_tete or "EUR").upper()
        sub, fee, tot = _num(g(r, i_sub)), _num(g(r, i_fee)), _num(g(r, i_tot))
        eur = lambda x: releves._vers_eur(abs(x), dev, date) if x is not None else None
        refx = ("cb:" + ref) if ref else ""
        if typ in ("buy", "advanced trade buy", "advance trade buy", "sell", "advanced trade sell", "advance trade sell"):
            achat = "buy" in typ
            # « Bought 0.01 ETH for 25 USDC on ETH-USDC » : cotation en crypto
            m = re.search(r"(?:Bought|Sold) [\d.,]+ \w+ for [€$£]?([\d.,]+) (\w+)", notes)
            cot = symbole(m.group(2)) if m else dev
            val = eur(sub if sub is not None else (tot or 0))
            if cot not in FIAT:
                qc = _num(m.group(1))
                if achat:
                    echange(lot, date, quand, (cot, qc), (sym, qty), ref=refx, valeur=val)
                else:
                    echange(lot, date, quand, (sym, qty), (cot, qc), ref=refx, valeur=val)
            elif val:
                _ajoute(lot, "Achat" if achat else "Vente", date, sym, abs(qty), val, eur(fee) or 0, quand, refx)
            else:
                _compter(lot, "conversion")
        elif typ == "convert":
            m = re.search(r"to ([\d.,]+) (\w+)", notes)
            if not m:
                lot.inconnues.append({"date": date, "type": "Convert", "nom": sym, "compte": "CRYPTO"})
                continue
            echange(lot, date, quand, (sym, qty), (m.group(2), _num(m.group(1))), ref=refx,
                    valeur=eur(sub if sub is not None else tot))
        elif _RECOMPENSE.search(typ) or typ in ("coinbase earn", "learning reward"):
            recompense(lot, date, quand, sym, qty, eur(tot if tot else sub), refx)
        elif typ in ("send", "receive", "deposit", "withdrawal", "exchange deposit", "exchange withdrawal",
                     "pro deposit", "pro withdrawal"):
            especes(lot, date, quand, sym, -abs(qty) if typ in ("send", "withdrawal") or "withdrawal" in typ else abs(qty), refx)
        else:
            lot.inconnues.append({"date": date, "type": typ, "nom": sym, "compte": "CRYPTO"})


# ─── Kraken ───────────────────────────────────────────────────────────────────

def _kraken_ledgers(c, lignes, lot):
    """Kraken, « ledgers » : txid, refid, time, type, subtype, aclass, asset,
    amount, fee, balance. Un ordre = deux lignes (ou plus) du même refid ;
    le montant n'inclut pas les frais, prélevés à part sur la même ligne."""
    g = lambda r, k: r[c[k]].strip() if k in c and c[k] < len(r) else ""
    groupes = {}
    for r in lignes:
        quand, typ, sub = _quand(g(r, "time")), g(r, "type").lower(), g(r, "subtype").lower()
        asset, mt, fee = g(r, "asset"), _num(g(r, "amount")), _num(g(r, "fee")) or 0
        date, refid = quand[:10], g(r, "refid")
        if not date or mt is None or not asset or not g(r, "txid"):
            continue
        if typ in ("trade", "spend", "receive"):
            groupes.setdefault(refid or quand, []).append((asset, mt, fee, quand))
        elif typ in ("deposit", "withdrawal"):
            especes(lot, date, quand, asset, mt, "kr:" + g(r, "txid"))
        elif typ in ("staking", "earn", "dividend", "invite bonus") and (sub in ("", "reward") or typ != "earn") and mt > 0 \
                and not _INTERNE.search(sub):
            recompense(lot, date, quand, asset, mt - fee, ref="kr:" + g(r, "txid"))
        elif typ in ("transfer", "earn", "staking", "adjustment", "settled", "rollover"):
            continue   # déplacements internes (vers le staking, entre portefeuilles)
        else:
            lot.inconnues.append({"date": date, "type": typ, "nom": asset, "compte": "CRYPTO"})
    for refid, rows in groupes.items():
        sorties = [(a, m) for a, m, f, q in rows if m < 0]
        entrees = [(a, m) for a, m, f, q in rows if m > 0]
        frais = [(a, f) for a, m, f, q in rows if f]
        if len(sorties) != 1 or len(entrees) != 1:
            continue   # moitié d'ordre (fichier coupé) : rien de sûr à écrire
        quand = rows[0][3]
        echange(lot, quand[:10], quand, sorties[0], entrees[0], frais[0] if frais else None, ref="kr:" + refid)


def _kraken_trades(c, lignes, lot):
    """Kraken, « trades » : txid, pair (« XXBTZEUR »), time, type (buy/sell),
    price, cost (sans les frais), fee (dans la monnaie de cotation), vol."""
    g = lambda r, k: r[c[k]].strip() if k in c and c[k] < len(r) else ""
    for r in lignes:
        quand = _quand(g(r, "time"))
        base, quote = _paire(g(r, "pair"))
        vol, cost, fee = _num(g(r, "vol")), _num(g(r, "cost")), _num(g(r, "fee")) or 0
        if not quand or not base or not vol or not cost:
            continue
        frais, ref = (quote, fee) if fee else None, "kr:" + g(r, "txid")
        if g(r, "type").lower() == "buy":
            echange(lot, quand[:10], quand, (quote, cost), (base, vol), frais, ref)
        else:
            echange(lot, quand[:10], quand, (base, vol), (quote, cost), frais, ref)


# ─── Bitpanda ─────────────────────────────────────────────────────────────────

def _bitpanda(c, lignes, lot):
    """Bitpanda : Transaction ID, Timestamp, Transaction Type (buy, sell,
    deposit, withdrawal, transfer), In/Out, Amount Fiat, Fiat, Amount Asset,
    Asset, …, Asset class, …, Fee, Fee asset. Les actions et métaux de
    Bitpanda ne sont pas des cryptos : ignorés."""
    g = lambda r, k: r[c[k]].strip() if k in c and c[k] < len(r) else ""
    for r in lignes:
        quand = _quand(g(r, "timestamp") or g(r, "created at"))
        date = quand[:10]
        typ = (g(r, "transaction type") or g(r, "type")).lower()
        if not date or not typ or ("status" in c and g(r, "status").lower() not in ("", "finished")):
            continue
        fiat, mf = g(r, "fiat").upper() or "EUR", _num(g(r, "amount fiat"))
        asset, ma = g(r, "asset").upper(), _num(g(r, "amount asset"))
        classe = g(r, "asset class").lower()
        ref = "bp:" + (g(r, "transaction id") or g(r, "id")) if (g(r, "transaction id") or g(r, "id")) else ""
        fee, fsym = _num(g(r, "fee")), (g(r, "fee asset") or asset).upper()
        if typ in ("buy", "sell"):
            if classe and "crypto" not in classe:
                _compter(lot, "classe")
                continue
            frais = (fsym, fee) if fee else None
            if typ == "buy":
                echange(lot, date, quand, (fiat, mf), (asset, ma), frais, ref, valeur=_eur(fiat, mf, date))
            else:
                echange(lot, date, quand, (asset, ma), (fiat, mf), frais, ref, valeur=_eur(fiat, mf, date))
        elif typ in ("deposit", "withdrawal"):
            fiat_seul = ma is None or not ma or classe == "fiat" or asset in FIAT
            sgn = 1 if typ == "deposit" else -1
            especes(lot, date, quand, fiat if fiat_seul else asset, sgn * abs((mf if fiat_seul else ma) or 0), ref)
        elif typ == "transfer":
            # Récompense de staking ou bonus, reçue sans contrepartie
            if g(r, "in/out").lower() == "incoming" and ma and "crypto" in classe:
                recompense(lot, date, quand, asset, ma, _eur(fiat, mf, date) if mf else None, ref)
            else:
                _compter(lot, "transferts_crypto")
        else:
            lot.inconnues.append({"date": date, "type": typ, "nom": asset, "compte": "CRYPTO"})


# ─── Crypto.com (application) ─────────────────────────────────────────────────

_CDC_ACHAT = {"viban_purchase", "van_purchase", "recurring_buy_order", "trading.limit_order.cash_account.purchase_commit",
              "crypto_purchase", "trading.crypto_purchase.google_pay"}
_CDC_VENTE = {"crypto_viban_exchange", "crypto_to_van_sell_order", "trading.limit_order.fiat_wallet.sell_commit",
              "crypto_payment", "card_top_up"}
_CDC_ECHANGE = {"crypto_exchange", "trading.limit_order.crypto_wallet.exchange"}
_CDC_TRANSFERT = {"crypto_deposit", "crypto_withdrawal", "crypto_transfer", "exchange_to_crypto_transfer",
                  "crypto_to_exchange_transfer"}


def _cryptocom(c, lignes, lot):
    """Crypto.com : Timestamp (UTC), Transaction Description, Currency,
    Amount, To Currency, To Amount, Native Currency, Native Amount (valeur
    dans la monnaie du compte : l'euro en France), Transaction Kind."""
    g = lambda r, k: r[c[k]].strip() if k in c and c[k] < len(r) else ""
    for r in lignes:
        quand = _quand(g(r, "timestamp (utc)"))
        date, kind = quand[:10], g(r, "transaction kind").lower()
        cur, mt = g(r, "currency").upper(), _num(g(r, "amount"))
        to, mt2 = g(r, "to currency").upper(), _num(g(r, "to amount"))
        nat, mn = g(r, "native currency").upper() or "EUR", _num(g(r, "native amount"))
        ref = "cdc:" + (g(r, "transaction hash") or quand + kind + cur)
        if not date or mt is None or not cur:
            continue
        val = _eur(nat, mn, date) if mn else None
        if kind in _CDC_ACHAT:
            if to and mt2:     # euros -> crypto
                echange(lot, date, quand, (cur, mt), (to, mt2), ref=ref, valeur=val)
            else:              # achat par carte : seule la crypto reçue est écrite
                echange(lot, date, quand, (nat, mn or 0), (cur, mt), ref=ref, valeur=val)
        elif kind in _CDC_VENTE:
            echange(lot, date, quand, (cur, mt), (to or nat, mt2 or mn or 0), ref=ref, valeur=val)
        elif kind in _CDC_ECHANGE:
            echange(lot, date, quand, (cur, mt), (to, mt2), ref=ref, valeur=val)
        elif kind in _CDC_TRANSFERT:
            especes(lot, date, quand, cur, mt, ref)
        elif _INTERNE.search(kind) or kind.startswith("dust_conversion"):
            continue
        elif _RECOMPENSE.search(kind) or kind in ("admin_wallet_credited", "reimbursement"):
            if mt > 0:
                recompense(lot, date, quand, cur, mt, val, ref)
        else:
            lot.inconnues.append({"date": date, "type": kind or g(r, "transaction description"), "nom": cur, "compte": "CRYPTO"})


# ─── Revolut (relevé crypto) ──────────────────────────────────────────────────

def _revolut_crypto(c, lignes, lot):
    """Revolut, relevé crypto : Symbol, Type (Buy, Sell, Send, Receive,
    Staking reward, Learn reward…), Quantity, Price, Value (« €40.00 »,
    hors frais), Fees, Date."""
    g = lambda r, k: r[c[k]].strip() if k in c and c[k] < len(r) else ""
    devise = lambda v: "USD" if "$" in v else "GBP" if "£" in v else "EUR"
    for r in lignes:
        brut_date = g(r, "date")
        quand = _quand(brut_date) if re.search(r"\d{4}-\d{2}-\d{2}", brut_date) else releves._date_fr(brut_date)
        date, typ, sym = quand[:10], g(r, "type").lower(), g(r, "symbol").upper()
        qty, vtxt, ftxt = _num(g(r, "quantity")), g(r, "value"), g(r, "fees")
        if not date or not sym or not qty:
            continue
        val = _eur(devise(vtxt), _num(vtxt), date) if _num(vtxt) else None
        fee = _eur(devise(ftxt), _num(ftxt), date) if _num(ftxt) else 0
        if typ in ("buy", "sell"):
            if val:
                _ajoute(lot, "Achat" if typ == "buy" else "Vente", date, sym, abs(qty), val, fee or 0, quand)
            else:
                _compter(lot, "conversion")
        elif typ in ("send", "receive"):
            _compter(lot, "transferts_crypto")
        elif typ in ("stake", "unstake"):
            continue
        elif _RECOMPENSE.search(typ):
            recompense(lot, date, quand, sym, qty, val)
        else:
            lot.inconnues.append({"date": date, "type": typ, "nom": sym, "compte": "CRYPTO"})


# ─── Bitvavo ──────────────────────────────────────────────────────────────────

def _bitvavo(c, lignes, lot):
    """Bitvavo : Timezone, Date, Time, Type (buy, sell, deposit, withdrawal,
    staking…), Currency, Amount, Quote Currency, Quote Price, Received / Paid
    Currency, Received / Paid Amount, Fee currency, Fee amount, Status,
    Transaction ID."""
    g = lambda r, k: r[c[k]].strip() if k in c and c[k] < len(r) else ""
    for r in lignes:
        date = releves._date_fr(g(r, "date"))
        quand = date + ("T" + g(r, "time")[:8] if re.match(r"\d{2}:\d{2}", g(r, "time")) else "")
        typ, sym, qty = g(r, "type").lower(), g(r, "currency").upper(), _num(g(r, "amount"))
        if not date or not sym or qty is None:
            continue
        if "status" in c and g(r, "status").lower() not in ("", "completed", "success", "finished"):
            continue
        pdev, pmt = g(r, "received / paid currency").upper() or "EUR", _num(g(r, "received / paid amount"))
        fee, fsym = _num(g(r, "fee amount")), g(r, "fee currency").upper()
        ref = "bv:" + g(r, "transaction id") if g(r, "transaction id") else ""
        frais = (fsym, fee) if fee else None
        if typ == "buy" and pmt:
            echange(lot, date, quand, (pdev, pmt), (sym, qty), frais, ref)
        elif typ == "sell" and pmt:
            echange(lot, date, quand, (sym, qty), (pdev, pmt), frais, ref)
        elif typ in ("deposit", "withdrawal"):
            especes(lot, date, quand, sym, abs(qty) if typ == "deposit" else -abs(qty), ref)
        elif _RECOMPENSE.search(typ) or typ in ("staking", "rebate", "affiliate"):
            qp = _num(g(r, "quote price"))
            val = _eur(g(r, "quote currency") or "EUR", qp * abs(qty), date) if qp else None
            recompense(lot, date, quand, sym, qty, val, ref)
        else:
            lot.inconnues.append({"date": date, "type": typ, "nom": sym, "compte": "CRYPTO"})


# ─── Delta (appli de suivi) ───────────────────────────────────────────────────

def _delta(c, lignes, lot):
    """Delta : Date, Way (BUY, SELL, DEPOSIT, WITHDRAW, TRANSFER…), Base
    amount, Base currency (name), Base type, Quote amount (prix total),
    Quote currency, Exchange, Fee amount, Fee currency (name), Notes. Les
    actions et fonds suivis dans Delta ne sont pas des cryptos : ignorés."""
    col = lambda d: next((i for k, i in c.items() if k.startswith(d)), None)
    i_bc, i_qc, i_fa, i_fc = col("base currency"), col("quote currency"), col("fee amount"), col("fee currency")
    g = lambda r, i: r[i].strip() if i is not None and i < len(r) else ""
    for r in lignes:
        quand = _quand(g(r, c.get("date")))
        date, way = quand[:10], g(r, c.get("way")).upper()
        sym, qty = g(r, i_bc).upper(), _num(g(r, c.get("base amount")))
        btype = g(r, c.get("base type")).upper()
        qcur, qmt = g(r, i_qc).upper() or "EUR", _num(g(r, c.get("quote amount")))
        fee, fsym = _num(g(r, i_fa)), g(r, i_fc).upper()
        if not date or not sym or not qty:
            continue
        if btype and btype not in ("CRYPTO", "COIN", "CRYPTOCURRENCY", "FIAT"):
            _compter(lot, "classe")
            continue
        frais = (fsym or qcur, fee) if fee else None
        if way in ("BUY", "SELL") and qmt:
            if way == "BUY":
                echange(lot, date, quand, (qcur, qmt), (sym, qty), frais)
            else:
                echange(lot, date, quand, (sym, qty), (qcur, qmt), frais)
        elif way in ("DEPOSIT", "WITHDRAW", "TRANSFER"):
            especes(lot, date, quand, sym, abs(qty) if way == "DEPOSIT" else -abs(qty))
        elif way in ("INCOME", "STAKING", "REWARD", "AIRDROP", "MINING", "INTEREST"):
            recompense(lot, date, quand, sym, qty, _eur(qcur, qmt, date) if qmt else None)
        else:
            lot.inconnues.append({"date": date, "type": way, "nom": sym, "compte": "CRYPTO"})


# ─── Reconnaissance ───────────────────────────────────────────────────────────

# (colonnes qui doivent toutes y être, plateforme, lecteur) ; l'ordre compte
_SIGNES = [
    (("utc_time", "operation", "coin", "change"), "Binance", _binance_releve),
    (("date(utc)", "pair", "side", "executed"), "Binance", _binance_ordres),
    (("date(utc)", "market", "type", "total", "fee coin"), "Binance", _binance_ordres),
    (("timestamp", "transaction type", "asset", "quantity transacted"), "Coinbase", _coinbase),
    (("txid", "refid", "time", "type", "asset", "amount", "fee"), "Kraken", _kraken_ledgers),
    (("txid", "ordertxid", "pair", "time", "type", "cost", "fee", "vol"), "Kraken", _kraken_trades),
    (("transaction type", "in/out", "amount fiat", "fiat", "amount asset", "asset"), "Bitpanda", _bitpanda),
    (("type", "in/out", "amount fiat", "fiat", "amount asset", "asset", "status"), "Bitpanda", _bitpanda),
    (("timestamp (utc)", "currency", "amount", "to currency", "native amount", "transaction kind"), "Crypto.com", _cryptocom),
    (("symbol", "type", "quantity", "price", "value", "fees", "date"), "Revolut", _revolut_crypto),
    (("date", "time", "type", "currency", "amount", "received / paid currency", "received / paid amount"), "Bitvavo", _bitvavo),
    (("date", "way", "base amount", "quote amount"), "Delta", _delta),
]

# Noms de colonnes qui font reconnaître la ligne d'en-tête (Coinbase et
# Bitpanda mettent quelques lignes de titre au-dessus) : releves._ENTETES_CONNUS
ENTETES = {nm for signe, _, _ in _SIGNES for nm in signe} | {"base currency (name)", "notes", "subtotal", "spot price currency"}


def lire(entetes: list, corps: list):
    """Les opérations d'un export de plateforme crypto, ou None si les
    colonnes ne sont celles d'aucune."""
    for signe, banque, lecteur in _SIGNES:
        if all(s in entetes for s in signe):
            lot = releves._Lot(banque)
            lot.inconnues = []
            c = {}
            for i, k in enumerate(entetes):
                c.setdefault(k, i)
            lecteur(c, corps, lot)
            lot.ops.sort(key=lambda o: o["quand"] or o["date"])   # ordres regroupés : à leur heure
            return {"ok": True, "banque": banque, "operations": lot.ops, "inconnues": lot.inconnues,
                    "ignores": lot.ignores}
    return None


# En bas : releves importe ce module à son chargement, et inversement
import releves  # noqa: E402
