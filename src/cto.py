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
# Lignes d'especes, ignorees en silence (comptees dans le resume)
ESPECES = {
    "CUSTOMER_INBOUND", "CUSTOMER_INPAYMENT", "TRANSFER_INSTANT_INBOUND",
    "CUSTOMER_OUTBOUND_REQUEST", "TRANSFER_INSTANT_OUTBOUND",
    "CARD_TRANSACTION", "CARD_TRANSACTION_INTERNATIONAL", "INTEREST_PAYMENT",
}
# Classes d'actifs suivies : actions et fonds (ETF). Obligations, crypto et
# fonds prives ne sont pas des titres cotes que Yahoo sait valoriser.
CLASSES = {"STOCK": "action", "FUND": "etf", "ETF": "etf", "": None}

_ISIN = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")


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


def lire_csv_tr(texte: str) -> dict:
    """Lit un export CSV de Trade Republic.

    Renvoie {ok, operations, ignores, inconnues, erreur} :
      operations : [{trId, date, type ("Achat"|"Vente"|"Dividende"), origine,
                     isin, nom, classe ("action"|"etf"), qty, cours, montant,
                     frais, taxe, alerte}]
        -> montant : le flux d'especes de la ligne, en valeur absolue
           (achat : debite ; vente et dividende : credite) ;
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

    operations, inconnues = [], []
    ignores = {"especes": 0, "classe": 0}
    for brut in lecteur:
        row = {(k or "").strip().lower(): (v or "").strip() for k, v in brut.items()}
        typ = row.get("type", "").upper()
        cat = row.get("category", "").upper()
        nom = row.get("name", "")
        date = _date(row.get("date") or row.get("datetime"))
        if typ in ESPECES:
            ignores["especes"] += 1
            continue
        if typ in ACHATS or typ in VENTES:
            sens = "Achat" if typ in ACHATS else "Vente"
            origine = ACHATS.get(typ) or VENTES.get(typ)
        elif typ in DIVIDENDES:
            sens, origine = "Dividende", "dividende"
        else:
            if cat == "CASH" and not row.get("symbol"):
                ignores["especes"] += 1
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

        op = {"trId": row.get("transaction_id", ""), "date": date, "type": sens,
              "origine": origine, "isin": isin, "nom": nom, "classe": classe or "etf",
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

    operations.sort(key=lambda o: (o["date"], o["trId"]))
    return {"ok": True, "operations": operations, "ignores": ignores, "inconnues": inconnues}
