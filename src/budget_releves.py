"""
budget_releves.py — Import des relevés de banque dans Mes comptes (4.4.70).

Lit le relevé d'un compte courant (CSV, Excel, OFX, QIF, CAMT.053), nettoie
chaque libellé (« CB CARREFOUR 12/10 CARTE 4974XXXX1234 » -> « Carrefour ») et
propose une catégorie. Rien n'est écrit ici : l'interface montre un aperçu,
l'utilisateur coche, corrige, puis enregistre comme d'habitude (finPersist).

Ordre du classement (le premier qui répond gagne) :
  1. l'historique de l'utilisateur : un libellé déjà classé reprend sa
     catégorie (c'est ainsi que Pilote « apprend » : corriger une fois suffit) ;
  2. les marchands connus (budget_marchands.MARCHANDS) ;
  3. la catégorie que donne la banque elle-même (BoursoBank, BNP, Caisse
     d'Épargne, Qonto…) ;
  4. le code commerçant de la carte (MCC), quand le fichier le donne ;
  5. sinon « À classer ».
Une notion est cherchée dans les catégories de l'utilisateur (noms et
synonymes) ; absente, l'opération reste à classer, avec la catégorie qu'on
pourrait créer (`propose`). Jamais de catégorie forcée ailleurs.

Formats lus et pièges : docs/modules/comptes.md, « Import des relevés ».
Entraînement : tests/test_budget_releves.py (plus de 1 000 relevés générés
aux formats réels des banques, et les exemples publiés par d'autres projets).
"""
from __future__ import annotations

import base64
import collections
import datetime
import hashlib
import re
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
import io

import releves
from budget_marchands import CIBLES, ICONES_PROPOSEES, MARCHANDS, MCC, SYNONYMES

# ─── Texte ───────────────────────────────────────────────────────────────────

def _sans_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s or "") if unicodedata.category(c) != "Mn")


def _norm(s) -> str:
    """Minuscules, sans accents, un espace entre les mots ; « & » est gardé (H&M)."""
    t = _sans_accents(str(s or "")).lower().replace("'", " ").replace("’", " ")
    t = re.sub(r"[^a-z0-9&]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


_REGLES = [(re.compile(r"(?<![a-z0-9&])(?:" + m.replace(" |", "|").rstrip() + r")s?(?![a-z0-9&])"), cle,
            (args[0] if args else None)) for m, cle, *args in MARCHANDS]

# Notions qu'un virement peut porter (un virement vers « PAUL » n'est pas la
# boulangerie Paul) ; les autres règles ne valent que pour la carte, le
# prélèvement ou une ligne sans genre
_PAR_VIREMENT = {"impots", "loyer", "copro", "energie", "eau", "internet", "telephone", "assurance",
                 "mutuelle", "credit", "education", "dons", "enfants", "frais", "frais_tenue",
                 "agios", "frais_carte", "salle_sport", "streaming", "logiciels", "assurance_auto",
                 "assurance_hab", "medecin", "optique"}

# ─── Genre d'opération et libellé lisible ────────────────────────────────────

_GENRES = [
    ("retrait", r"^(retrait|ret|retrait dab|retrait gab|ret dab|retrait especes|withdrawal|atm|cash withdrawal)\b"),
    ("cheque", r"^(chq|cheque|remise (de )?(cheque|chq)|rem chq|remise)\b"),
    ("prelevement", r"^(prlv|prelevement|prel|prelev|prlv sepa|ech|echeance|direct debit|debit direct)\b"),
    ("virement", r"^(vir|virement|vrt|vir sepa|vir inst|virement sepa|vir recu|vir emis|transfer|credit transfer|"
                 r"virement instantane|avis de virement|vrmt)\b"),
    ("frais", r"^(frais|cotisation|cotis|commission|com|agios|interets debiteurs|abonnement)\b"),
    ("carte", r"^(cb|carte|paiement cb|paiement par carte|paiement carte|achat cb|facture carte|"
              r"pmt carte|pmt cb|achat|card|achat carte|paiement psc|cb\d*|du \d{6})\b"),
]

# Genre donné par une colonne « type » (Revolut, N26, Caisse d'Épargne, Trade Republic…)
_GENRES_TYPE = [
    ("retrait", r"(atm|retrait|withdraw|cash)"),
    ("carte", r"(card|carte|presentment|mastercard|visa|paiement cb|pos|achat)"),
    ("prelevement", r"(prelev|direct debit|debit direct|directdebit|prlv|sepa debit|repayment)"),
    ("virement", r"(vir|transfer|virement|topup|top up|income|exchange|xfer|credit transfer|outbound|inbound)"),
    ("cheque", r"(cheque|chq|check)"),
    ("frais", r"(fee|frais|commission|cotisation|charge)"),
]

# Préfixes de libellé retirés, dans l'ordre, tant qu'il en reste
_PREFIXES = [
    r"(paiement|achat|pmt|facture|fact|reglement|operation) (par |de |du )?(cb|carte|carte bancaire|psc)( (x|n|no|num|numero)? ?\d{3,4})?",
    r"(cb|carte|card)( (x|n|no)? ?[x\*]?\d{4})?",
    r"x ?\d{4}",
    r"\*\d{4}",
    r"du \d{6}", r"du \d{2} \d{2}( \d{2,4})?", r"le \d{2} \d{2}( \d{2,4})?",
    r"\d{2} \d{2} \d{2,4}", r"\d{2} \d{2}", r"\d{4}(?= [a-z])", r"\d{6}(?= [a-z])",
    r"prlv sepa", r"prelevement( sepa| europeen| europ)?", r"prlv", r"prel", r"prelev",
    r"vir(ement)?( sepa)?( inst(antane)?)?( recu| emis| en votre faveur| permanent| internet| web| eur)?",
    r"payment from", r"payment to", r"transfer (from|to)", r"card transaction", r"card payment",
    r"vrt", r"vrmt", r"de ?:", r"de", r"from", r"pour ?:", r"pour", r"vers", r"to", r"a",
    r"retrait( dab| gab| especes)?", r"ret dab", r"dab", r"gab",
    r"remise( de)? (cheque|chq)s?", r"(chq|cheque)( n| no)?", r"avoir", r"remboursement",
    r"sepa", r"inst", r"recu", r"emis", r"web", r"internet", r"m", r"mme", r"mr", r"mlle", r"ste", r"monsieur", r"madame",
    # Prestataires de paiement : le vrai marchand vient après eux
    r"paypal( europe| \*| pte)?(?= [a-z])", r"sumup( \*)?", r"sq", r"zettle", r"izettle", r"sp", r"lyf", r"stripe",
    r"payplug", r"ppro", r"lydia pro", r"pay", r"ingenico", r"tpe",
]
_PREFIXE_RE = re.compile(r"^(?:" + "|".join(_PREFIXES) + r")(?: |$)")

# Bruit retiré n'importe où
_BRUIT = [
    r"\bdu \d{6}\b", r"\b\d{1,2} \d{1,2}( \d{2,4})?\b(?! ?(rue|av|bd|boulevard|avenue))",
    r"carte ?(n|no|numero)? ?\d{4}[x\*]{4,}\d{4}", r"\d{4,6}[x\*]{4,}\d{2,4}", r"[x\*]{4,}\d{2,4}",
    r"carte (numero|n|no) ?\d+", r"carte x?\d{4}", r"x\d{4}",
    r"\bcb ?\d{4}\b", r"\b\d{1,2}[/.]\d{1,2}([/.]\d{2,4})?\b", r"\b\d{1,2}h\d{2}\b", r"\b\d{2}:\d{2}(:\d{2})?\b",
    r"\bfact(ure)? \d{6}\b", r"\bfact \d{6}\b",
    r"\bech ?/ ?\S+", r"\bid emetteur ?/ ?\S+", r"\bid ?: ?\S+", r"\bref ?[:/.] ?\S+", r"\bref\b \S+",
    r"\bmdt ?/ ?\S+", r"\bmandat ?:? ?\S+", r"\brum ?:? ?\S+", r"\bics ?:? ?\S+",
    r"\b(fr|de|be|lu|es|it|nl)\d{2}[a-z]{3}\w+", r"\b[a-z]{2}\d{2}(?: ?\w{4}){3,7}\b",
    r"\b\d{5,}\b", r"\b[a-z]*\d[a-z\d]{7,}\b",
]
_BRUIT_RE = re.compile("|".join("(?:" + b + ")" for b in _BRUIT), re.I)

_SIGLES = {"edf", "sncf", "sfr", "ratp", "caf", "cpam", "urssaf", "dgfip", "ikea", "h&m", "kfc", "bnp", "lcl",
           "grdf", "mma", "maif", "macif", "maaf", "gmf", "axa", "ugc", "mgen", "cic", "ovh", "tgv", "ter", "ups",
           "dhl", "dpd", "apl", "rsa", "gls", "msa", "cvec", "crous", "tcl", "tbm", "bp", "cgr", "mk2", "fnac",
           "lmde", "smerep", "ag2r", "bhv", "c&a", "dab", "sas", "sa", "sarl", "eurl", "ttc", "ht", "fdj", "pmu",
           "ldlc", "asf", "aprr", "sanef", "esf", "mgel", "ants", "pas", "idf", "cb", "tv", "rmc", "ocs", "adn",
           "ing", "hsbc", "bpce", "lbp", "sg", "ca", "cm", "ce", "bpi", "psg", "om", "ol", "usa", "uk", "eu", "fr",
           "atm", "sepa", "iban", "rib", "emi", "jd", "hp", "lg", "tf1", "m6", "bfm"}


def _jolie(t: str) -> str:
    """« carrefour market » -> « Carrefour Market », sigles en majuscules."""
    mots = []
    for m in t.split():
        if m in _SIGLES or (len(m) <= 4 and not re.search(r"[aeiouy]", m) and m.isalpha()):
            mots.append(m.upper())
        elif m.isdigit():
            mots.append(m)
        else:
            mots.append(m[:1].upper() + m[1:])
    return " ".join(mots)


def genre_de(brut: str, type_col: str = "") -> str:
    """carte, prelevement, virement, retrait, cheque, frais ou autre."""
    n = _norm(brut)
    for g, motif in _GENRES:
        if re.search(motif, n):
            return g
    tc = _norm(type_col)
    if tc:
        for g, motif in _GENRES_TYPE:
            if re.search(motif, tc):
                return g
    # « PAIEMENT CB 0601 », « ACHAT CB » au milieu du libellé
    if re.search(r"\b(cb|carte|paiement cb|facture carte)\b", n):
        return "carte"
    if re.search(r"\b(prlv|prelevement)\b", n):
        return "prelevement"
    if re.search(r"\b(vir|virement)\b", n):
        return "virement"
    return "autre"


def _sans_prefixes(t: str) -> str:
    for _ in range(8):
        t2 = _PREFIXE_RE.sub("", t).strip()
        if t2 == t:
            break
        t = t2
    return t


def nettoyer(brut: str) -> str:
    """Libellé lisible : préfixes bancaires, dates, numéros de carte et
    références retirés. Un virement garde son tiers (« VIR SEPA RECU /DE
    EMPLOYEUR SA /MOTIF SALAIRE » -> « Employeur SA »)."""
    s = str(brut or "")
    # Virement : le tiers est après « DE: », « /DE », « POUR: », « /BEN », et avant « /MOTIF », « REF »
    m = re.search(r"(?i)(?:/de|de ?:|\bde\b|/ben|pour ?:|/pour|beneficiaire ?:?|emetteur ?:?)\s*([^/]+?)(?=\s*(?:/|\bmotif\b|\bref\b|\breference\b|$))", s)
    t = _norm(s)
    if re.match(r"(vir|virement|vrt)\b", t) and m:
        tiers = _norm(m.group(1))
        tiers = _BRUIT_RE.sub(" ", tiers)
        tiers = re.sub(r"^(m|mme|mr|mlle|monsieur|madame|ste|societe)\s+", "", re.sub(r"\s+", " ", tiers).strip())
        if len(tiers) >= 2:
            return _jolie(tiers)
    t = re.sub(r"\s(/?motif|libelle|communication|objet)\b.*$", "", t)   # motif d'un virement
    # Références d'un prélèvement ou d'une facture, toujours en fin de libellé
    t = re.sub(r"(?<=\w)\s(ech|id emetteur|ref|reference|mandat|mdt|rum|ics|fact|facture|numero)\b.*$", "", t)
    t = _sans_prefixes(t)
    t = _BRUIT_RE.sub(" ", t)
    t = _sans_prefixes(re.sub(r"\s+", " ", t).strip())
    # Fin de libellé : ville après un code postal, « fr », « fra », pays
    t = re.sub(r"\s(fr|fra|france|frankreich|eur|com|net|eu|io|cb|carte)$", "", t)
    t = re.sub(r"\s(sas|sa|sarl|eurl|sasu|scs|snc)$", "", t)
    t = re.sub(r"\s+", " ", t).strip(" -*/.")
    if len(t) < 2:
        t = re.sub(r"\s+", " ", _norm(brut))
    return _jolie(t[:60]).strip()


def cle(libelle: str) -> str:
    """Clé de comparaison d'un libellé : nettoyé, sans chiffres ni mots vides."""
    n = _norm(nettoyer(libelle))
    mots = [m for m in n.split() if not m.isdigit() and len(m) > 1 and m not in ("de", "du", "la", "le", "les", "des", "et")]
    return " ".join(mots)

# ─── Montants et dates ───────────────────────────────────────────────────────

def _montant(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if not s or s in ("-", "--"):
        return None
    s = re.sub(r"(?i)\b(eur|euros?)\b", "", s)
    if not re.search(r"\d", s):
        return None
    n = releves._n(s)
    if n is None:
        try:
            n = releves.cto._nombre(s)
        except Exception:
            n = None
    return n


def _date(v, ordre="jm"):
    if v is None:
        return ""
    s = str(v).strip()
    if not s:
        return ""
    if re.fullmatch(r"\d{5}(\.0+)?", s):          # numéro de série Excel resté nombre
        d = datetime.date(1899, 12, 30) + datetime.timedelta(days=int(float(s)))
        return d.isoformat() if 1990 <= d.year <= 2100 else ""
    m = re.fullmatch(r"(\d{4})(\d{2})(\d{2})(\d{6})?.*", s)  # OFX : 20261012120000[+1:CET]
    if m:
        try:
            return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
        except ValueError:
            return ""
    d = releves._date_fr(s, ordre)
    if d and 1990 <= int(d[:4]) <= 2100:
        return d
    return ""

# ─── Colonnes d'un tableau ───────────────────────────────────────────────────
# (champ, motifs sur l'en-tête normalisé : le premier motif trouvé l'emporte)
_COLS = [
    ("statut",  [r"^(status|statut|state|etat)$"]),
    ("date_op", [r"^date (de l |d )?operation", r"^(started date|operation date|transaction date|date de transaction|"
                 r"date d achat|date de la transaction|date operation|dateop|date op|date d operation|booking date|"
                 r"buchungstag|date comptable|date de comptabilisation|date comptabilisation)"]),
    ("date",    [r"^(date|datum|jour|day|completed date|settlement date|date de reglement|datetime|date heure|"
                 r"date et heure|transaction time)$", r"^(date)\b(?!.*valeur)(?!.*value)"]),
    ("date_val", [r"^(date (de )?valeur|value date|dateval|date val|valeur)"]),
    ("libelle", [r"^(libelle operation|libelle de l operation|libelle complet|libelle|label|description|"
                 r"intitule|wording|operation|libelle de l ecriture|nature de l operation|transaction description|"
                 r"buchungstext|verwendungszweck|omschrijving)$", r"^libelle", r"^(description|intitule)"]),
    ("libelle_court", [r"^(libelle (court|simplifie)|short label|libelle abrege)"]),
    ("tiers",   [r"^(partner name|payee|beneficiaire|nom de la contrepartie|counterparty name|counterparty|"
                 r"contrepartie|merchant|marchand|commercant|tiers|nom du tiers|name|nom|destinataire|"
                 r"emetteur|empfanger|auftraggeber|counterparty_name|merchant name)$"]),
    ("detail",  [r"^(detail|detail de l ecriture|details|informations complementaires|info complementaire|"
                 r"payment reference|reference de paiement|motif|reference|communication|memo|notes?|"
                 r"commentaire|comment|payment_reference|libelle complementaire|complement)$"]),
    ("montant", [r"^(montant|amount|montant de l operation|montant operation|montant total|montant eur|"
                 r"montant en euros|amount eur|amount in eur|somme|valeur|betrag|bedrag|total amount|"
                 r"montant euros|montant net)$", r"^(montant|amount|betrag)\b(?!.*(franc|frf|devise|original|"
                 r"foreign|etrangere|local|solde|balance|ht$|tva|vat))"]),
    ("debit",   [r"^(debit|debits|debit euros?|montant debit|sortie|sorties|depense|depenses|withdrawal|"
                 r"paid out|money out|out|outflow|soll)\b"]),
    ("credit",  [r"^(credit|credits|credit euros?|montant credit|entree|entrees|recette|recettes|deposit|"
                 r"paid in|money in|in|inflow|haben)\b"]),
    ("frais",   [r"^(fee|fees|frais|commission)$"]),
    ("devise",  [r"^(devise|currency|monnaie|waehrung|wahrung)$"]),
    ("type",    [r"^(type|type operation|type d operation|type de transaction|transaction type|nature|"
                 r"moyen de paiement|methode de paiement|payment method|mode de paiement|kind|category type)$",
                 r"^type\b"]),
    ("categorie", [r"^(categorie|category|categorie operation|categorie parent|categoryparent|"
                   r"categorie de tresorerie|rubrique|poste)$"]),
    ("sous_categorie", [r"^(sous categorie|sous categorie operation|subcategory|sub category|categorie detaillee)$"]),
    ("mcc",     [r"^(mcc|mcc code|mcc_code|code mcc|merchant category code)$"]),
    ("solde",   [r"^(solde|balance|saldo|accountbalance|solde courant|nouveau solde)"]),
    ("compte_type", [r"^(account type|account_type|product|produit)$"]),
    ("categorie_tr", [r"^(category)$"]),
]


def _entete_norm(h: str) -> str:
    h = _norm(str(h or "").replace("_", " "))
    return re.sub(r"\s(utc|gmt|cet|cest|local|ttc|incl vat|eur|euros|€)$", "", h).strip() if not re.fullmatch(r"(montant|amount) (eur|euros)", h) else h


def _roles(entetes: list) -> dict:
    """{champ: indice} ; une colonne ne sert qu'une fois."""
    noms = [_entete_norm(h) for h in entetes]
    res, pris = {}, set()
    for passe in (0, 1):
        for champ, motifs in _COLS:
            if champ in res or len(motifs) <= passe:
                continue
            rx = re.compile(motifs[passe])
            for i, n in enumerate(noms):
                if i not in pris and n and rx.search(n):
                    if champ == "montant" and re.search(r"(franc|frf)", n):
                        continue
                    res[champ] = i
                    pris.add(i)
                    break
    # Montant : une colonne « Montant(EUROS) » préférée à « Montant(FRANCS) »
    if "montant" in res and "eur" not in noms[res["montant"]]:
        for i, n in enumerate(noms):
            if i not in pris and n.startswith(("montant", "amount")) and "eur" in n and "franc" not in n:
                pris.discard(res["montant"])
                res["montant"], _ = i, pris.add(i)
                break
    return res


def _score_entete(ligne: list) -> int:
    r = _roles(ligne)
    s = len(r)
    if not any(k in r for k in ("date", "date_op")):
        return 0
    if not ("montant" in r or "debit" in r or "credit" in r):
        return 0
    # Une ligne de données ressemble à tout sauf à un en-tête
    if sum(1 for c in ligne if _date(c)) >= 1:
        return 0
    return s


def _ligne_entete(lignes: list) -> int:
    meilleur, score = -1, 0
    for i, l in enumerate(lignes[:40]):
        s = _score_entete(l)
        if s > score:
            meilleur, score = i, s
    return meilleur


def _sans_entete(lignes: list) -> dict:
    """Relevé sans ligne d'en-tête (LCL, certains exports) : colonnes devinées
    à leur contenu — dates, montants, puis le texte le plus long."""
    corps = [l for l in lignes if any(c.strip() for c in l)][:60]
    if not corps:
        return {}
    largeur = max(len(l) for l in corps)
    dates, montants, textes = [], [], []
    for i in range(largeur):
        vals = [l[i].strip() for l in corps if i < len(l) and l[i].strip()]
        if not vals:
            continue
        nd = sum(1 for v in vals if len(v) <= 24 and _date(v))
        nm = sum(1 for v in vals if re.fullmatch(r"[-+]?\s*[\d\s .,']+\s*(€|eur)?", v, re.I) and _montant(v) is not None)
        if nd >= 0.7 * len(corps):
            dates.append(i)
        elif nm >= 0.5 * len(vals) and len(vals) >= 0.3 * len(corps):
            montants.append((i, len(vals)))
        else:
            textes.append((i, sum(len(v) for v in vals) / max(1, len(vals))))
    if not dates or not montants or not textes:
        return {}
    roles = {"date": dates[0], "libelle": max(textes, key=lambda x: x[1])[0]}
    if len(montants) >= 2 and all(n < 0.95 * len(corps) for _, n in montants[:2]):
        # Deux colonnes à moitié vides : débit puis crédit
        roles["debit"], roles["credit"] = montants[0][0], montants[1][0]
    else:
        roles["montant"] = montants[0][0]
    autres = [i for i, _ in textes if i != roles["libelle"]]
    if autres:
        roles["type"] = autres[0]
    return roles


_STATUTS_IGNORES = re.compile(r"^(pending|reverted|declined|failed|cancelled|canceled|reversed|en attente|"
                              r"en cours|refuse|annule|rejete|a venir|autorisation|authorised|authorized|"
                              r"provisoire|non comptabilise)")
_TOTAL = re.compile(r"^((sous )?total|totaux)( (des |de la )?(operations|mouvements|debits?|credits?|general|"
                    r"periode|mois|releve|compte))*$|^(ancien |nouveau )?solde( (initial|final|au|debut|fin|"
                    r"crediteur|debiteur|du compte))?\b|^(report|a reporter|montant total|opening balance|"
                    r"closing balance|balance)$")


def _lire_tableau(lignes: list, banque_auto=True) -> dict:
    lignes = releves._deballer([[str(c if c is not None else "") for c in l] for l in lignes])
    lignes = [l for l in lignes if any(c.strip() for c in l)]
    if not lignes:
        return {"ok": False, "erreur": "fichier vide"}
    i = _ligne_entete(lignes)
    if i >= 0:
        entetes = lignes[i]
        roles = _roles(entetes)
        corps = lignes[i + 1:]
        noms = [_entete_norm(h) for h in entetes]
    else:
        roles = _sans_entete(lignes)
        corps = lignes
        noms = []
        if not roles:
            return {"ok": False, "erreur": "colonnes introuvables : il faut au moins une date, un montant et un "
                                           "libellé par ligne (CSV, Excel, OFX ou QIF téléchargé depuis "
                                           "l'espace client de la banque)"}
    lib_tiers = False
    if "libelle" not in roles:
        for alt in ("tiers", "libelle_court", "detail"):
            if alt in roles:
                roles["libelle"] = roles.pop(alt)
                lib_tiers = alt == "tiers"     # N26 : le nom du tiers est le libellé à montrer
                break
    if "libelle" not in roles:
        return {"ok": False, "erreur": "aucune colonne de libellé reconnue"}
    banque = _banque(noms)
    if banque == "Trade Republic":
        # « category » y dit TRADING ou CASH, « name » est le nom d'un titre :
        # le tiers d'un paiement est dans « counterparty_name »
        roles.pop("categorie", None)
        roles["categorie_tr"] = noms.index("category")
        if "counterparty name" in noms:
            roles["tiers"] = noms.index("counterparty name")
        if "description" in noms:
            roles["libelle"] = noms.index("description")

    def g(r, champ):
        k = roles.get(champ)
        return r[k].strip() if k is not None and k < len(r) else ""

    cle_date = "date_op" if "date_op" in roles else ("date" if "date" in roles else "date_val")
    ordre = releves._ordre_dates([g(r, cle_date) for r in corps])
    ops, ignorees = [], collections.Counter()
    tout_positif = True
    for r in corps:
        brut_lib = re.sub(r"\s+", " ", g(r, "libelle"))
        date = _date(g(r, cle_date), ordre) or _date(g(r, "date"), ordre) or _date(g(r, "date_val"), ordre)
        statut = _norm(g(r, "statut"))
        if statut and _STATUTS_IGNORES.match(statut):
            ignorees["en attente ou refusée"] += 1
            continue
        mt = None
        if "montant" in roles:
            mt = _montant(g(r, "montant"))
        if mt is None and ("debit" in roles or "credit" in roles):
            d, c = _montant(g(r, "debit")), _montant(g(r, "credit"))
            if d:
                mt = -abs(d)
            elif c:
                mt = abs(c)
        if not date or mt is None:
            if brut_lib or any(c.strip() for c in r):
                ignorees["sans date ou sans montant"] += 1 if (date or mt is not None) else 0
            continue
        if _TOTAL.match(_norm(brut_lib)) or (not brut_lib and not g(r, "tiers")):
            ignorees["ligne de total ou de solde"] += 1
            continue
        frais = _montant(g(r, "frais"))
        if frais:
            mt -= abs(frais)
        if abs(mt) < 0.005:
            ignorees["montant nul"] += 1
            continue
        devise = g(r, "devise").upper()
        tiers = re.sub(r"\s+", " ", g(r, "tiers"))
        detail = re.sub(r"\s+", " ", g(r, "detail"))
        # Libellé complet : le libellé, le tiers et le détail s'ils ajoutent quelque chose
        morceaux = []
        for x in (brut_lib, tiers, detail):
            if x and not any(_norm(x) in _norm(y) for y in morceaux):
                morceaux = [y for y in morceaux if _norm(y) not in _norm(x)] + [x]
        # Libellé abrégé repris en entier dans le détail (Société Générale :
        # « PRLV SEPA EDF » puis « PRELEVEMENT EUROPEEN EDF CLIENTS ») : le détail seul
        if len(morceaux) == 2 and brut_lib and detail and morceaux[0] == brut_lib:
            mots = set(cle(brut_lib).split())
            if mots and mots <= set(cle(detail).split()):
                morceaux = [detail]
        brut = " ".join(morceaux) or g(r, "libelle_court")
        if mt < 0:
            tout_positif = False
        ops.append({
            "date": date, "montantSigne": round(mt, 2), "brut": brut,
            "affiche": tiers or (brut_lib if lib_tiers else ""),
            "typeCol": g(r, "type"), "categorieBanque": g(r, "categorie"),
            "sousCategorieBanque": g(r, "sous_categorie"), "mcc": g(r, "mcc"),
            "devise": devise if devise and devise not in ("EUR", "€", "EURO", "EUROS") else "",
            "compteType": g(r, "compte_type"), "categorieTr": g(r, "categorie_tr"),
        })
    # Trade Republic : seules les lignes d'espèces du compte (cartes, virements) sont du budget
    if banque == "Trade Republic":
        ops = [o for o in ops if _norm(o.get("categorieTr")) == "cash"
               and _norm(o.get("compteType")) in ("", "default")]
        for o in ops:
            o["categorieBanque"] = ""
    # Débits sans signe dans une colonne unique « Montant » d'un fichier qui
    # a aussi une colonne Type « Débit / Crédit »
    if tout_positif and "montant" in roles and "type" in roles:
        for o in ops:
            if re.search(r"^(debit|d|sortie|depense|dr)$", _norm(o["typeCol"])):
                o["montantSigne"] = -abs(o["montantSigne"])
    return {"ok": True, "banque": banque, "operations": ops, "ignorees": dict(ignorees),
            "fichierCategories": "categorie" in roles and banque == "Tableau"}


def _banque(noms: list) -> str:
    j = "|".join(noms)
    sig = [
        ("BoursoBank", ["dateop", "dateval", "label", "category", "categoryparent"]),
        ("Caisse d'Épargne / Banque Populaire", ["libelle simplifie", "libelle operation"]),
        ("BNP Paribas", ["libelle operation", "montant operation"]),
        ("Société Générale", ["detail de l ecriture", "montant de l operation"]),
        ("La Banque Postale", ["montant euros", "montant francs"]),
        ("Revolut", ["started date", "completed date", "state"]),
        ("N26", ["partner name", "partner iban"]),
        ("N26", ["beneficiaire", "type de transaction", "montant eur"]),
        ("N26", ["payee", "transaction type", "amount eur"]),
        ("Qonto", ["counterparty name", "settlement date utc"]),
        ("Qonto", ["nom de la contrepartie", "methode de paiement"]),
        ("Trade Republic", ["account type", "asset class", "transaction id"]),
        ("Crédit Mutuel / CIC", ["date de valeur", "debit", "credit", "libelle", "solde"]),
        ("Fortuneo", ["date operation", "date valeur", "libelle", "debit", "credit"]),
        ("Crédit Agricole", ["debit euros", "credit euros"]),
    ]
    for nom, cles in sig:
        if all(any(c == n or n.startswith(c) for n in noms) for c in cles):
            return nom
    return "Tableau"

# ─── OFX, QIF, CAMT ──────────────────────────────────────────────────────────

def _lire_ofx(texte: str) -> dict:
    ops = []
    for bloc in re.findall(r"(?is)<STMTTRN>(.*?)(?=</STMTTRN>|<STMTTRN>|</BANKTRANLIST>)", texte):
        def tag(n, brut=False):
            m = re.search(r"(?is)<" + n + r">([^<\r\n]*)", bloc)
            v = m.group(1) if m else ""
            return v.rstrip() if brut else v.strip()
        import html
        date = _date(tag("DTUSER")[:8]) or _date(tag("DTPOSTED")[:8])
        mt = _montant(tag("TRNAMT").replace(",", ".") if re.fullmatch(r"[-+]?\d+,\d+", tag("TRNAMT")) else tag("TRNAMT"))
        nom, memo = html.unescape(tag("NAME", True)).lstrip(), html.unescape(tag("MEMO", True))
        brut = nom
        if memo.strip() and _norm(memo) not in _norm(nom):
            if _norm(nom) in _norm(memo):
                brut = memo.strip()
            elif len(nom) >= 32:      # NAME coupé à 32 caractères, la suite dans MEMO
                brut = nom + memo
            else:
                brut = nom + " " + memo.strip()
        if not date or mt is None or abs(mt) < 0.005:
            continue
        ops.append({"date": date, "montantSigne": round(mt, 2), "brut": re.sub(r"\s+", " ", brut),
                    "typeCol": tag("TRNTYPE"), "categorieBanque": "", "mcc": tag("SIC")})
    if not ops and "<STMTTRN>" not in texte.upper():
        return {"ok": False, "erreur": "fichier OFX sans opération"}
    return {"ok": True, "banque": "OFX", "operations": ops, "ignorees": {}}


def _lire_qif(texte: str) -> dict:
    ops, cur = [], {}
    dates = re.findall(r"(?m)^D(.+)$", texte)
    ordre = releves._ordre_dates([d.replace("'", "/") for d in dates])
    for ligne in texte.splitlines():
        ligne = ligne.rstrip()
        if not ligne or ligne.startswith("!"):
            continue
        k, v = ligne[0], ligne[1:].strip()
        if k == "^":
            if cur.get("date") and cur.get("mt") is not None and abs(cur["mt"]) >= 0.005:
                brut = cur.get("P", "")
                if cur.get("M") and _norm(cur["M"]) not in _norm(brut):
                    brut = (brut + " " + cur["M"]).strip()
                ops.append({"date": cur["date"], "montantSigne": round(cur["mt"], 2), "brut": brut,
                            "typeCol": "", "categorieBanque": cur.get("L", "").split(":")[0],
                            "sousCategorieBanque": (cur.get("L", "").split(":") + [""])[1], "mcc": ""})
            cur = {}
        elif k == "D":
            cur["date"] = _date(v.replace("'", "/").replace(" ", ""), ordre)
        elif k in "TU" and "mt" not in cur:
            cur["mt"] = _montant(v)
        elif k in "PML":
            cur[k] = re.sub(r"\s+", " ", v)
    if not ops:
        return {"ok": False, "erreur": "fichier QIF sans opération"}
    return {"ok": True, "banque": "QIF", "operations": ops, "ignorees": {}}


def _lire_camt(data: bytes) -> dict:
    try:
        racine = ET.fromstring(re.sub(rb"<!DOCTYPE[^>]*>", b"", data))
    except ET.ParseError:
        return {"ok": False, "erreur": "fichier XML illisible"}
    for el in racine.iter():
        el.tag = el.tag.split("}", 1)[-1]
    ops = []
    for n in racine.iter("Ntry"):
        def t(chemin):
            x = n.find(chemin)
            return (x.text or "").strip() if x is not None and x.text else ""
        mt = _montant(t("Amt"))
        if mt is None:
            continue
        if t("CdtDbtInd") == "DBIT":
            mt = -abs(mt)
        date = _date(t("BookgDt/Dt") or t("BookgDt/DtTm")[:10] or t("ValDt/Dt"))
        brut = t("AddtlNtryInf") or t(".//RmtInf/Ustrd") or t(".//Cdtr/Nm") or t(".//Dbtr/Nm")
        if date and brut:
            ops.append({"date": date, "montantSigne": round(mt, 2), "brut": re.sub(r"\s+", " ", brut),
                        "typeCol": "", "categorieBanque": "", "mcc": ""})
    if not ops:
        return {"ok": False, "erreur": "aucune opération dans ce fichier XML"}
    return {"ok": True, "banque": "CAMT.053", "operations": ops, "ignorees": {}}

# ─── Un fichier ──────────────────────────────────────────────────────────────

def lire_fichier(nom: str, data: bytes) -> dict:
    nom_l = (nom or "").lower()
    if not data:
        return {"ok": False, "erreur": "fichier vide"}
    if b"%PDF-" in data[:1024]:
        return {"ok": False, "erreur": "relevé en PDF : Pilote lit le fichier CSV, Excel, OFX ou QIF que l'espace "
                                       "client de la banque propose au téléchargement (rubrique « Exporter » ou "
                                       "« Télécharger les opérations »)"}
    if data[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        try:
            lignes = releves._lignes_xls(data)
        except Exception:
            lignes = None
        if not lignes:
            return {"ok": False, "erreur": "fichier Excel à l'ancien format (.xls) illisible : enregistre-le en "
                                           ".xlsx ou en .csv, puis importe ce fichier"}
        return _lire_tableau(lignes)
    if data[:2] == b"PK":
        try:
            z = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile:
            return {"ok": False, "erreur": "archive abîmée"}
        if any(n.startswith("xl/") for n in z.namelist()):
            return _lire_tableau(releves._lignes_xlsx(data))
        if "content.xml" in z.namelist():
            return _lire_tableau(releves._lignes_ods(z))
        res = {"ok": False, "erreur": "aucun relevé dans cette archive", "operations": [], "ignorees": {}}
        for info in z.infolist():
            if info.filename.endswith("/") or info.file_size > 20_000_000 or info.filename.startswith("__MACOSX/"):
                continue
            r = lire_fichier(info.filename, z.read(info.filename))
            if r.get("ok"):
                res.update(ok=True, banque=r.get("banque", ""), erreur="")
                res["operations"] += r["operations"]
        return res
    texte = releves._texte(data).lstrip("﻿")
    tete = texte[:4000]
    if "OFXHEADER" in tete or re.search(r"(?i)<OFX>", tete) or nom_l.endswith((".ofx", ".qfx")):
        return _lire_ofx(texte)
    if re.search(r"(?m)^!(Type|Account|Option)", tete) or nom_l.endswith(".qif"):
        return _lire_qif(texte)
    if texte.lstrip().startswith("<") and re.search(r"(?i)<(Document|BkToCstmrStmt)", tete):
        return _lire_camt(texte.encode("utf-8"))
    if texte.lstrip().startswith("<") and re.search(r"(?i)<table", texte[:200000]):
        return _lire_tableau(releves._lignes_html(texte))
    if any(c in tete for c in ",;\t|"):
        return _lire_tableau(releves._lignes_csv(texte))
    return {"ok": False, "erreur": "format non reconnu (CSV, Excel, OFX, QIF ou CAMT attendu)"}

# ─── Catégories de l'utilisateur ─────────────────────────────────────────────

_SYN_NORM = [(_norm(k), {_norm(x) for x in v}) for k, v in SYNONYMES.items()]


class Categories:
    """Les catégories de l'utilisateur, pour y retrouver une notion par son
    nom ou un synonyme. `cats` : [{name, type, subs: [{name}]}]."""

    def __init__(self, cats):
        self.cats = [c for c in (cats or []) if c.get("name")]
        self._trouves = {}

    _cache_noms = {}

    @classmethod
    def _noms(cls, nom):
        """Le nom et ses synonymes, normalisés (gardés en mémoire : appelé souvent)."""
        n = _norm(nom)
        if n not in cls._cache_noms:
            base = {n}
            for k, syn in _SYN_NORM:
                if n == k or n in syn:
                    base |= {k} | syn
            cls._cache_noms[n] = base
        return cls._cache_noms[n]

    def trouver(self, typ, cat, sub=None):
        """(catégorie, sous-catégorie) de l'utilisateur, ou (None, None)."""
        cle_ = (typ, cat, sub)
        if cle_ not in self._trouves:
            self._trouves[cle_] = self._trouver(typ, cat, sub)
        return self._trouves[cle_]

    def _trouver(self, typ, cat, sub=None):
        des_types = [c for c in self.cats if c.get("type", "expense") == typ]
        ncat, nsub = _norm(cat), _norm(sub) if sub else ""
        # 1. Même catégorie (nom exact), sous-catégorie par nom puis synonyme
        for passe in ("exact", "syn"):
            for c in des_types:
                nc = _norm(c["name"])
                if (passe == "exact" and nc == ncat) or (passe == "syn" and nc in self._noms(cat) and nc not in ("autres depenses", "autres revenus")):
                    if not sub:
                        return c["name"], None
                    for s in c.get("subs") or []:
                        if _norm(s.get("name")) == nsub:
                            return c["name"], s["name"]
                    for s in c.get("subs") or []:
                        if _norm(s.get("name")) in self._noms(sub):
                            return c["name"], s["name"]
                    cand = (c["name"], None)
                    # Une sous-catégorie du même nom ailleurs vaut mieux que la catégorie seule
                    autre = self._sub_ailleurs(des_types, sub)
                    return autre or cand
        # 2. La sous-catégorie, rangée ailleurs
        if sub:
            autre = self._sub_ailleurs(des_types, sub)
            if autre:
                return autre
            # 3. Une catégorie qui porte le nom de la sous-catégorie (« Courses »)
            for c in des_types:
                if _norm(c["name"]) in self._noms(sub):
                    return c["name"], None
        return None, None

    def _sub_ailleurs(self, des_types, sub):
        if not sub:
            return None
        for test in (lambda n: n == _norm(sub), lambda n: n in self._noms(sub)):
            for c in des_types:
                for s in c.get("subs") or []:
                    if test(_norm(s.get("name"))):
                        return c["name"], s["name"]
        return None

    def a_classer(self, typ):
        nom = "Autres revenus" if typ == "income" else "Autres dépenses"
        for c in self.cats:
            if c.get("type", "expense") == typ and _norm(c["name"]) == _norm(nom):
                return c["name"]
        return nom

# ─── Classement ──────────────────────────────────────────────────────────────

_REMB = re.compile(r"\b(remboursement|rembt|remb|avoir|refund|retour|annulation|annul|credit carte|reversal)\b")
_INTERNE = re.compile(
    r"\b(livret|livret a|ldds|ldd|lep|pel|cel|epargne|assurance vie|pea|cto|compte titres|virement interne|"
    r"vir interne|vers compte|vir cpte a cpte|cpte a cpte|compte a compte|transfert|top up|topup|rechargement|"
    r"recharge|alimentation compte|approvisionnement|vault|coffre|pocket|tirelire|mes comptes|entre mes comptes|"
    r"exchanged to|exchange|trade republic|boursorama|boursobank|fortuneo|revolut|n26|lydia|sumeria|nickel|"
    r"compte joint|propre compte|own account|epargne salariale|bforbank|hello bank|ma french bank|"
    r"degiro|bourse direct|linxea|yomoni|nalo|ramify|goodvest|placement|versement)\b")
_TOTAL_CARTE = re.compile(r"\b(releve (differe )?(carte|cb)|total (carte|cb)|debit differe|carte differe|"
                          r"differe carte|operations carte|depenses carte|facturette|arrete carte|"
                          r"debit mensuel carte|prlv carte|releve mensuel carte|cb differe|total des factures)\b")


def _mcc_notion(code):
    try:
        c = int(str(code).strip()[:4])
    except (TypeError, ValueError):
        return None
    for de, a, notion in MCC:
        if de <= c <= a:
            return notion
    return None


def _regle(texte: str, genre: str, typ: str):
    """Première notion des marchands connus pour ce texte, ce genre et ce type."""
    for rx, notion, genres in _REGLES:
        if genres is not None:
            if genre not in genres:
                continue
        elif genre == "virement" and notion not in _PAR_VIREMENT:
            continue
        if CIBLES[notion][0] != typ and not (typ == "income" and CIBLES[notion][0] == "expense"):
            continue
        if rx.search(texte):
            return notion
    return None


class Historique:
    """Ce que l'utilisateur a déjà classé : clé du libellé -> (cat, sub) le plus
    fréquent, le plus récent à égalité. `items` : [{label, type, cat, sub, date}]."""

    def __init__(self, items):
        self.par_cle = collections.defaultdict(collections.Counter)
        self.dates = {}
        for it in items or []:
            k = cle(it.get("label", ""))
            if len(k) < 2 or not it.get("cat"):
                continue
            v = (it.get("type", "expense"), it["cat"], it.get("sub") or None)
            self.par_cle[k][v] += 1
            d = it.get("date", "")
            if d > self.dates.get((k, v), ""):
                self.dates[(k, v)] = d
        self.cles = sorted(self.par_cle, key=len, reverse=True)

    def chercher(self, k, typ):
        def meilleur(kk):
            vals = [(n, self.dates.get((kk, v), ""), v) for v, n in self.par_cle[kk].items() if v[0] == typ]
            return max(vals)[2] if vals else None
        if k in self.par_cle:
            v = meilleur(k)
            if v:
                return v, k
        mots = set(k.split())
        if not mots:
            return None, None
        for kk in self.cles:
            mk = set(kk.split())
            fort = [m for m in mk if len(m) >= 3]
            # Tous les mots du libellé connu dans le nouveau (ou l'inverse), avec un mot fort
            if fort and (mk <= mots or (mots <= mk and len(k) >= 4)):
                v = meilleur(kk)
                if v:
                    return v, kk
        return None, None


def classer(op: dict, cats: Categories, hist: Historique) -> dict:
    """Ajoute à l'opération : type, montant, libelle, genre, cat, sub, comment
    (historique | marchand | banque | mcc | aucun), raison, propose, interne,
    totalCarte."""
    mt = op["montantSigne"]
    typ = "expense" if mt < 0 else "income"
    genre = genre_de(op["brut"], op.get("typeCol", ""))
    lib = op.get("affiche") and _jolie(_norm(op["affiche"])) or nettoyer(op["brut"])
    if genre == "retrait" and not _norm(lib).startswith(("retrait", "cash", "atm")):
        lib = ("Retrait " + lib).strip()     # « RETRAIT DAB 10/11 TOULON » -> « Retrait Toulon »
    texte = _norm(op["brut"]) + " " + _norm(op.get("affiche", ""))
    k = cle(op.get("affiche") or op["brut"])
    res = dict(op, type=typ, montant=round(abs(mt), 2), libelle=lib or op["brut"][:60], genre=genre, cle=k,
               cat=None, sub=None, comment="aucun", raison="", propose=None, interne=False, totalCarte=False)

    def poser(cat, sub, comment, raison):
        res.update(cat=cat, sub=sub, comment=comment, raison=raison)
        return res

    # Virement entre ses comptes, épargne : ni dépense ni revenu
    if genre in ("virement", "autre", "prelevement") and _INTERNE.search(texte) and not re.search(
            r"\b(salaire|paie|loyer|caf|cpam|impot|dgfip)\b", texte):
        res["interne"] = True
    if typ == "expense" and _TOTAL_CARTE.search(texte):
        res["totalCarte"] = True
    # 1. Historique
    v, kk = hist.chercher(k, typ)
    if v:
        c, s = cats.trouver(typ, v[1], v[2])
        if c:
            return poser(c, s, "historique", "Comme « " + _jolie(kk) + " », déjà classé ainsi")
    # 2. Marchands connus
    notion = _regle(texte, genre, typ)
    if notion:
        t, c0, s0 = CIBLES[notion]
        if typ == "income" and notion == "mutuelle":
            notion = "mutuelle_remb"
            t, c0, s0 = CIBLES[notion]
        elif typ == "income" and t == "expense" and genre not in ("carte", "prelevement", "autre", "cheque") \
                and not _REMB.search(texte):
            notion = None   # un virement reçu (« MOTIF LOYER ») n'est pas un remboursement de marchand
        elif typ == "income" and t == "expense":
            # Remboursement d'un marchand, de la mutuelle ou de la Sécu
            notion = "mutuelle_remb" if notion == "mutuelle" else ("secu" if notion in ("medecin", "pharmacie") else "remboursement")
            t, c0, s0 = CIBLES[notion]
    if notion:
        t, c0, s0 = CIBLES[notion]
        c, s = cats.trouver(t, c0, s0)
        if c:
            return poser(c, s, "marchand", _raison(notion))
        res["propose"] = {"cat": c0, "sub": s0, "type": t, "icone": ICONES_PROPOSEES.get(c0, ""),
                          "raison": _raison(notion)}
    elif typ == "income" and _REMB.search(texte) and genre == "carte":
        c, s = cats.trouver("income", "Remboursements")
        if c:
            return poser(c, s, "marchand", "Remboursement sur la carte")
    # 3. Catégorie donnée par la banque
    cb, sb = op.get("categorieBanque", ""), op.get("sousCategorieBanque", "")
    if cb and not re.search(r"(?i)a categoriser|non categorise|autres?$|divers|inconnu|uncategori|^other", _norm(cb)):
        for cat_nom, sub_nom in ((sb, None), (cb, sb or None), (cb, None), ("", sb), ("", cb)):
            if not (cat_nom or sub_nom):
                continue
            c, s = cats.trouver(typ, cat_nom, sub_nom)
            if c and _norm(c) not in ("autres depenses", "autres revenus"):
                return poser(c, s, "banque", "Catégorie donnée par la banque : " + cb + (" › " + sb if sb else ""))
    # 4. Code commerçant
    notion = _mcc_notion(op.get("mcc")) if op.get("mcc") else None
    if notion and CIBLES[notion][0] == typ:
        c, s = cats.trouver(*CIBLES[notion])
        if c:
            return poser(c, s, "mcc", "Code commerçant de la carte (" + str(op["mcc"]).strip() + ")")
    # 5. Retrait sans catégorie « Retraits » : dépense diverse, c'est ce qu'il est
    if genre == "retrait" and typ == "expense":
        c, s = cats.trouver("expense", "Autres dépenses", "Divers")
        if c and res["propose"]:
            return poser(c, s, "marchand", "Retrait d'espèces")
    return res


def _raison(notion):
    t, c, s = CIBLES[notion]
    return "Reconnu : " + (s or c).lower() if notion not in ("retrait",) else "Retrait d'espèces"


def _empreinte(op, n):
    base = "|".join([op["date"], "%.2f" % op["montantSigne"], _norm(op["brut"]), str(n)])
    return hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]

# ─── Entrée ──────────────────────────────────────────────────────────────────

def analyser(ops: list, categories=None, historique=None) -> list:
    """Classe des opérations lues (montantSigne, brut, …). Séparé de la lecture
    pour les tests."""
    cats, hist = Categories(categories), Historique(historique)
    vus = collections.Counter()
    sortie = []
    for op in ops:
        r = classer(op, cats, hist)
        base = (r["date"], "%.2f" % r["montantSigne"], _norm(r["brut"]))
        vus[base] += 1
        r["empreinte"] = _empreinte(r, vus[base])
        sortie.append(r)
    _paires_internes(sortie)
    _totaux_carte(sortie)
    return sortie


def _paires_internes(ops):
    """Deux virements de même montant, de sens opposés, à un jour près (deux
    relevés importés ensemble) : un virement entre ses propres comptes."""
    par_mt = collections.defaultdict(list)
    for o in ops:
        if o["genre"] in ("virement", "autre"):
            par_mt[o["montant"]].append(o)
    for groupe in par_mt.values():
        dep = [o for o in groupe if o["type"] == "expense"]
        rev = [o for o in groupe if o["type"] == "income"]
        for d in dep:
            for r in rev:
                if abs((datetime.date.fromisoformat(d["date"]) - datetime.date.fromisoformat(r["date"])).days) <= 1 \
                        and d.get("fichier") != r.get("fichier"):
                    d["interne"] = r["interne"] = True


def _totaux_carte(ops):
    """Carte à débit différé : la ligne du total mensuel double les achats si
    leur détail est aussi dans l'import. Repérée, elle n'est pas cochée."""
    cartes = [o for o in ops if o["genre"] == "carte" and o["type"] == "expense" and not o["totalCarte"]]
    for t in ops:
        if not t["totalCarte"]:
            continue
        mois = t["date"][:7]
        avant = (datetime.date.fromisoformat(t["date"]).replace(day=1) - datetime.timedelta(days=1)).isoformat()[:7]
        for m in (avant, mois):
            somme = sum(o["montant"] for o in cartes if o["date"][:7] == m)
            if somme and abs(somme - t["montant"]) <= max(1.0, 0.01 * t["montant"]):
                t["doubleCarte"] = True
                break


def lire(fichiers: list, categories=None, historique=None) -> dict:
    """fichiers : [{nom, b64}]. Renvoie {ok, operations, documents}. Chaque
    opération : date, type, montant, libelle, brut, genre, cat, sub, comment,
    raison, propose, interne, totalCarte, doubleCarte, empreinte, devise,
    fichier, banque."""
    tout, docs = [], []
    for f in fichiers or []:
        nom = f.get("nom", "")
        try:
            r = lire_fichier(nom, base64.b64decode(f.get("b64", "")))
        except Exception as e:
            r = {"ok": False, "erreur": "lecture impossible : " + str(e)[:200]}
        if not r.get("ok"):
            docs.append({"nom": nom, "erreur": r.get("erreur", "")})
            continue
        for o in r["operations"]:
            o["fichier"] = nom
            o["banque"] = r.get("banque", "")
            o["categorieFichier"] = bool(r.get("fichierCategories"))
        tout += r["operations"]
        docs.append({"nom": nom, "banque": r.get("banque", ""), "operations": len(r["operations"]),
                     "ignorees": r.get("ignorees", {})})
    ops = analyser(tout, categories, historique)
    ops.sort(key=lambda o: (o["date"], o["empreinte"]))
    return {"ok": bool(ops), "operations": ops, "documents": docs,
            "erreur": "" if ops else "; ".join(d["nom"] + " : " + d["erreur"] for d in docs if d.get("erreur"))
                                       or "aucune opération trouvée"}
