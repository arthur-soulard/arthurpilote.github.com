"""
cto.py — Stockage du module « CTO » (compte-titres ordinaire), et lecture de
l'export CSV des transactions de Trade Republic.

Emplacement : <app_dir>/users/<slug>/cto.json
Backup quotidien : <app_dir>/users/<slug>/backups_cto/cto_YYYY-MM-DD.json

Modele
------
comptes : [{id, nom, courtier, tarif, cree, _nid,
            positions, transactions, divReceived, divFuture, wishlist,
            closedPositions, strategies, prefs}]
  -> plusieurs CTO par utilisateur, chacun avec son courtier ;
  -> positions, transactions, dividendes, wishlist ont EXACTEMENT la forme de
     ceux du PEA (pea_data.json) : l'interface du PEA sert aux deux, sur le
     compte affiche (voir « Compte actif » dans index.html) ;
  -> prefs : reglages propres au compte (prochainAchat, simOrdres, plans) ;
  -> pas de depots : le CTO ne suit pas les especes (le compte especes de
     Trade Republic sert aussi de compte courant). L'interface deduit les
     versements des achats, ventes et dividendes, pour que les calculs du PEA
     (valeur, plus-value, courbe) restent justes avec des especes a zero.
actif   : id du compte que montre la section CTO
"""
from __future__ import annotations

import csv
import datetime
import io
import re

import jsonstore


def default_data() -> dict:
    return {
        "_meta": {
            "version": 1,
            "schema": "cto.v1",
            "createdAt":   datetime.date.today().isoformat(),
            "lastSavedAt": datetime.datetime.now().isoformat(timespec="seconds"),
        },
        "comptes": [],
        "actif": "",
        "_nid": {"compte": 1},
    }


_store = jsonstore.JsonStore(
    filename="cto.json",
    backup_dirname="backups_cto",
    schema="cto.v1",
    default_factory=default_data,
)


def load_data() -> dict:
    return _store.load()


def save_data(data: dict, vide_voulu: bool = False) -> None:
    """Un etat sans aucun compte n'ecrase jamais un fichier qui en contient :
    c'est l'etat par defaut d'une lecture ratee, comme le « PEA vierge ».
    Supprimer volontairement son dernier CTO passe vide_voulu."""
    data = data or {}
    if not data.get("comptes") and not vide_voulu:
        actuel = _store.load()
        if actuel.get("comptes"):
            raise ValueError("état vide alors que le fichier contient des comptes : écriture refusée")
    _store.save(data)


# ─── Lecture de l'export CSV de Trade Republic ───────────────────────────────
#
# Export disponible dans l'appli depuis avril 2026 (Profil → Relevés → Export
# des transactions). Trade Republic ne publie aucune definition de ses
# colonnes : celles-ci viennent du lecteur open source de broker-to-edavki
# (ADR 0015, octobre 2026), ecrit d'apres des fichiers d'essai. On lit donc
# par NOM de colonne, et tout type inconnu est rendu a l'interface au lieu
# d'etre devine : l'utilisateur voit ce qui n'a pas ete repris.
#
#   datetime, date, account_type, category, type, asset_class, name, symbol,
#   shares, price, amount, fee, tax, currency, original_amount,
#   original_currency, fx_rate, description, transaction_id, counterparty_name,
#   counterparty_iban, payment_reference, mcc_code
#
# `symbol` est l'ISIN. `shares` est negatif sur une vente, `amount` est le flux
# d'especes (negatif a l'achat), `fee` est negatif. Prix en `currency` (EUR) :
# Trade Republic execute en euros sur des places europeennes.
#
# Constate sur le premier vrai releve d'Arthur (11/10/2026, 732 lignes) :
#   - un plan d'investissement est un `BUY` comme un autre : seule la
#     description le distingue (« Savings plan execution <ISIN> <nom>,
#     quantity: … » ; « Buy trade … » pour un ordre) ;
#   - le Saveback est une ligne d'ESPECES (category CASH, BENEFITS_SAVEBACK,
#     ISIN et montant) suivie de l'achat lui-meme ; une action offerte (« stock
#     perk »), une ligne CASH `GIFT` du montant de l'ordre, frais compris,
#     a la meme seconde que lui. Les lignes CASH ne sont donc jamais des achats :
#     elles servent seulement a reconnaitre l'origine de l'achat ;
#   - `amount` d'un ordre = parts × cours, sans les frais ni la taxe (TTF
#     francaise de 0,4 %, colonne `tax`, sur les actions francaises) ;
#   - une division (category CORPORATE_ACTION, type SPLIT) tient en deux
#     lignes a la meme seconde : l'ancienne ligne sortie (parts negatives) et
#     la nouvelle entree, ici avec un nouvel ISIN (ETP argent x3 de WisdomTree,
#     1 part -> 10). Ni prix ni montant ;
#   - aucun dividende sur la periode : leur ligne reste a voir.

COLONNES_REQUISES = {"date", "category", "type", "symbol", "shares", "price", "amount"}

# Types de la categorie TRADING repris comme achats ou ventes, et leur origine
# (affichee dans Transactions). Un achat offert (Saveback, action offerte) est
# compte a son prix : le PRU reste celui que montre Trade Republic.
ACHATS = {
    "BUY":                   "ordre",
    "SAVINGS_PLAN_EXECUTED": "plan",
    "BENEFITS_SAVEBACK":     "saveback",
    "SAVEBACK":              "saveback",
    "BENEFITS_ROUND_UP":     "arrondi",
    "ROUND_UP":              "arrondi",
    "ROUNDUP":               "arrondi",
    "STOCKPERK":             "offert",
    "BONUS":                 "offert",
}
VENTES = {"SELL": "ordre", "SAVINGS_PLAN_SELL": "plan"}
DIVIDENDES = {"DIVIDEND", "DIVIDEND_PAYMENT", "DISTRIBUTION"}
# Lignes d'especes, ignorees en silence (comptees dans le resume), comme toute
# ligne de la categorie CASH
ESPECES = {
    "CUSTOMER_INBOUND", "CUSTOMER_INPAYMENT", "TRANSFER_INSTANT_INBOUND",
    "CUSTOMER_OUTBOUND_REQUEST", "TRANSFER_INSTANT_OUTBOUND",
    "CARD_TRANSACTION", "CARD_TRANSACTION_INTERNATIONAL", "INTEREST_PAYMENT",
}
# Classes d'actifs suivies : actions et fonds (ETF). Obligations, crypto et
# fonds prives ne sont pas des titres cotes que Yahoo sait valoriser.
CLASSES = {"STOCK": "action", "FUND": "etf", "ETF": "etf", "": None}

_ISIN = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")
# Nom long du titre dans la description : la recherche de sa cotation en a
# besoin (« iShares Physical Gold ETC » quand `name` dit « Physical Gold USD (Acc) »)
_DESCRIPTION = re.compile(r"(?i)^(?:savings plan execution|buy trade|sell trade)\s+"
                          r"[A-Z]{2}[A-Z0-9]{9}[0-9]\s+(.+?),\s*quantity:")


def _nombre(txt: str):
    """« 1.2345 », « -124.97 », « 1 234,56 » -> float ; vide -> None."""
    t = (txt or "").strip().replace(" ", "").replace(" ", "")
    if not t:
        return None
    if "," in t and "." not in t:
        t = t.replace(",", ".")
    elif "," in t and "." in t:          # 1.234,56 (milliers a l'allemande)
        t = t.replace(".", "").replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


def _date(txt: str) -> str:
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", txt or "")
    if m:
        return "-".join(m.groups())
    m = re.search(r"(\d{2})[./](\d{2})[./](\d{4})", txt or "")
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else ""


def _secondes(txt: str):
    """« 2026-01-02T14:09:42.687815Z » -> secondes (UTC) ; sans heure -> None."""
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})", txt or "")
    if not m:
        return None
    return datetime.datetime(*map(int, m.groups()), tzinfo=datetime.timezone.utc).timestamp()


def lire_csv_tr(texte: str) -> dict:
    """Lit un export CSV de Trade Republic.

    Renvoie {ok, operations, ignores, inconnues, erreur} :
      operations : [{trId, date, quand, type ("Achat"|"Vente"|"Dividende"|"Division"),
                     origine, isin, nom, nomLong, classe ("action"|"etf"), qty,
                     cours, montant, frais, taxe, alerte}], dans l'ordre ou elles
                     ont eu lieu (`quand` : date et heure de la ligne)
        -> montant : le flux d'especes de la ligne, en valeur absolue
           (achat : debite ; vente et dividende : credite) ;
        -> origine : ordre, plan, saveback, arrondi, offert, dividende, division ;
        -> une Division porte aussi isinAvant, nomAvant, qtyAvant, trIdAvant :
           qtyAvant parts de isinAvant deviennent qty parts de isin ;
        -> alerte : texte si les chiffres ne collent pas (montant ≠ qte × cours ± frais).
      ignores    : {"especes": n, "classe": n} lignes laissees de cote, par raison
      inconnues  : [{type, categorie, nom, date}] types que Pilote ne connait pas
    """
    texte = (texte or "").lstrip("﻿")
    if not texte.strip():
        return {"ok": False, "erreur": "Fichier vide."}
    premiere = texte.splitlines()[0]
    sep = ";" if premiere.count(";") > premiere.count(",") else ","
    lecteur = csv.DictReader(io.StringIO(texte), delimiter=sep)
    colonnes = {(c or "").strip().lower() for c in (lecteur.fieldnames or [])}
    manque = COLONNES_REQUISES - colonnes
    if manque:
        return {"ok": False,
                "erreur": "Ce fichier n'a pas les colonnes d'un export Trade Republic "
                          "(il manque : " + ", ".join(sorted(manque)) + ")."}

    operations, inconnues, divisions = [], [], {}
    # Lignes d'especes qui disent d'ou vient un achat (voir plus haut)
    saveback, cadeaux = [], []
    ignores = {"especes": 0, "classe": 0}
    for brut in lecteur:
        row = {(k or "").strip().lower(): (v or "").strip() for k, v in brut.items()}
        typ = row.get("type", "").upper()
        cat = row.get("category", "").upper()
        nom = row.get("name", "")
        date = _date(row.get("date") or row.get("datetime"))
        quand = row.get("datetime") or row.get("date") or ""
        if typ in DIVIDENDES:
            sens, origine = "Dividende", "dividende"
        elif typ in ESPECES or cat == "CASH":
            ignores["especes"] += 1
            if typ == "BENEFITS_SAVEBACK" and row.get("symbol"):
                saveback.append((date, row["symbol"].upper(), abs(_nombre(row.get("amount")) or 0)))
            elif typ == "GIFT":
                cadeaux.append((_secondes(quand), abs(_nombre(row.get("amount")) or 0)))
            continue
        elif typ in ACHATS or typ in VENTES:
            sens = "Achat" if typ in ACHATS else "Vente"
            origine = ACHATS.get(typ) or VENTES.get(typ)
            if origine == "ordre" and row.get("description", "").lower().startswith("savings plan"):
                origine = "plan"
        elif cat == "CORPORATE_ACTION" and typ == "SPLIT":
            divisions.setdefault(quand, []).append(row)
            continue
        else:
            inconnues.append({"type": typ, "categorie": cat, "nom": nom, "date": date})
            continue

        classe = CLASSES.get(row.get("asset_class", "").upper(), False)
        if classe is False:
            ignores["classe"] += 1
            continue
        isin = row.get("symbol", "").upper()
        qty = abs(_nombre(row.get("shares")) or 0)
        cours = _nombre(row.get("price"))
        montant = abs(_nombre(row.get("amount")) or 0)
        frais = abs(_nombre(row.get("fee")) or 0)
        taxe = abs(_nombre(row.get("tax")) or 0)
        devise = (row.get("currency") or "EUR").upper()

        m = _DESCRIPTION.match(row.get("description", ""))
        op = {"trId": row.get("transaction_id", ""), "date": date, "quand": quand, "type": sens,
              "origine": origine, "isin": isin, "nom": nom, "nomLong": m.group(1) if m else "",
              "classe": classe or "etf",
              "qty": qty, "cours": cours, "montant": round(montant, 2),
              "frais": round(frais, 2), "taxe": round(taxe, 2), "alerte": ""}
        alertes = []
        if not _ISIN.match(isin):
            alertes.append("ISIN illisible")
        if devise != "EUR":
            alertes.append("montant en " + devise)
        if sens != "Dividende":
            if not qty:
                alertes.append("quantité absente")
            if cours is None and qty and montant:
                # Prix absent : on le deduit du montant, frais retires (achat) ou ajoutes (vente)
                cours = (montant - frais) / qty if sens == "Achat" else (montant + frais) / qty
                op["cours"] = round(cours, 6)
            # Une part offerte (Saveback, action offerte) n'est pas payee par le
            # compte especes : son montant peut valoir 0, rien a verifier
            # Selon les fichiers, le montant inclut les frais ou non : un ecart
            # jusqu'aux frais est normal (meme tolerance que broker-to-edavki)
            if cours and qty and montant and origine not in ("saveback", "offert"):
                if abs(qty * cours - montant) > frais + 0.02:
                    alertes.append(f"montant {montant:.2f} € pour {qty:g} × {cours:g} €")
        op["alerte"] = ", ".join(alertes)
        operations.append(op)

    # Un ordre execute en plusieurs morceaux (meme titre, meme sens, meme
    # instant, meme cours) n'en fait qu'un : 5 + 0,94972 parts d'argent x3 le
    # 13/05/2026, 1 € de frais sur le premier seulement. Separes, le second
    # passait pour un ordre aux frais differents de la grille. Le plus petit
    # transaction_id reste : un nouvel import du meme ordre le reconnait.
    fusion = {}
    for o in list(operations):
        if o["type"] not in ("Achat", "Vente") or not o["quand"]:
            continue
        cle = (o["isin"], o["type"], o["quand"], o["cours"])
        f = fusion.setdefault(cle, o)
        if f is o:
            continue
        f["qty"] = round(f["qty"] + o["qty"], 10)
        for k in ("montant", "frais", "taxe"):
            f[k] = round(f[k] + o[k], 2)
        f["trId"] = min(f["trId"], o["trId"])
        operations.remove(o)

    achats = [o for o in operations if o["type"] == "Achat"]
    # Saveback : l'achat du meme titre, du meme montant, a trois jours au plus
    for d, isin, m in saveback:
        jour = datetime.date.fromisoformat(d) if d else None
        o = next((o for o in achats if o["origine"] in ("plan", "ordre") and o["isin"] == isin
                  and abs(o["montant"] - m) < 0.005 and jour and o["date"]
                  and abs((datetime.date.fromisoformat(o["date"]) - jour).days) <= 3), None)
        if o:
            o["origine"] = "saveback"
    # Action offerte : l'ordre passe dans les deux minutes, du montant du cadeau
    # frais et taxe compris (21,00 € pour 19,99 € d'Amazon et 1 € de frais)
    for t, m in cadeaux:
        o = next((o for o in achats if o["origine"] == "ordre" and t is not None
                  and _secondes(o["quand"]) is not None and abs(_secondes(o["quand"]) - t) <= 120
                  and abs(o["montant"] + o["frais"] + o["taxe"] - m) <= 0.02), None)
        if o:
            o["origine"] = "offert"

    # Division : l'ancienne ligne sortie et la nouvelle entree, a la meme seconde
    for quand, lignes in divisions.items():
        avant = [r for r in lignes if (_nombre(r.get("shares")) or 0) < 0]
        apres = [r for r in lignes if (_nombre(r.get("shares")) or 0) > 0]
        if len(avant) != 1 or len(apres) != 1:
            inconnues += [{"type": "SPLIT", "categorie": "CORPORATE_ACTION", "nom": r.get("name", ""),
                           "date": _date(r.get("date") or quand)} for r in lignes]
            continue
        a, b = avant[0], apres[0]
        classe = CLASSES.get(b.get("asset_class", "").upper(), False)
        if classe is False:
            ignores["classe"] += len(lignes)
            continue
        operations.append({
            "trId": b.get("transaction_id", ""), "trIdAvant": a.get("transaction_id", ""),
            "date": _date(b.get("date") or quand), "quand": quand, "type": "Division",
            "origine": "division", "isin": b.get("symbol", "").upper(), "nom": b.get("name", ""),
            "nomLong": "", "isinAvant": a.get("symbol", "").upper(), "nomAvant": a.get("name", ""),
            "classe": classe or "etf", "qty": abs(_nombre(b.get("shares"))),
            "qtyAvant": abs(_nombre(a.get("shares"))), "cours": None, "montant": 0,
            "frais": 0, "taxe": 0, "alerte": ""})

    # Dans l'ordre ou elles ont eu lieu : une division avant la vente du meme jour
    operations.sort(key=lambda o: (o["date"], o["quand"], o["trId"]))
    return {"ok": True, "operations": operations, "ignores": ignores, "inconnues": inconnues}
