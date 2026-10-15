"""
releves.py — Lecture des relevés de banque et de courtier, pour l'import
dans le PEA ou un CTO (4.5.0).

Pilote ne « devine » rien : chaque banque a ses règles de lecture, écrites et
vérifiées sur de vrais documents (exemples anonymisés des tests de Portfolio
Performance et d'Export-To-Ghostfolio, voir docs/import-releves.md).

  PDF (texte lu par pypdf) : Fortuneo (avis d'opéré, coupons, taxe sur les
      transactions financières, relevé des liquidités du PEA), BoursoBank
      (opérations de bourse et sur OPC, coupons), Bourse Direct (relevés
      d'opérations), Saxo (rapports de trade, de dividende, de virement, en
      anglais ou en allemand), Degiro (rapport des transactions), Trade
      Republic (avis en français), et l'avis d'opéré d'une autre banque par
      le lecteur universel (_avis_generique : repris seulement si ses
      chiffres tiennent ensemble).
  CSV / Excel (.xlsx, .xls) / LibreOffice (.ods) / HTML / XML : Trade
      Republic (cto.lire_csv_tr), Degiro (relevé de compte), Interactive
      Brokers (Flex Query CSV ou XML), Saxo (transactions), Trading 212, et
      tout autre tableau par le lecteur « universel » : colonnes reconnues
      par leur nom, ou choisies par l'utilisateur.

Sortie : la même que cto.lire_csv_tr, avec en plus les types « Versement »,
« Retrait » (espèces du PEA) et « Taxe » (taxe sur les transactions
financières envoyée à part, rattachée ensuite à son ordre par l'interface).
Montants en euros : un ordre passé dans une autre devise est converti au
cours du relevé quand il le donne, sinon au cours de clôture du jour (Yahoo).
"""
from __future__ import annotations

import base64
import csv
import datetime
import hashlib
import io
import re
import unicodedata
import zipfile
import xml.etree.ElementTree as ET

import cto

_ISIN = r"[A-Z]{2}[A-Z0-9]{9}\d"
# Montant à la française : « 1 234,56 », « 5 058,16 », « +4 973,82 », « -0,50 »
_MT = r"[-+]?\d{1,3}(?:[  .]\d{3})*,\d+"
_MOIS = {"jan": 1, "janv": 1, "janvier": 1, "feb": 2, "fev": 2, "fevr": 2, "fevrier": 2,
         "mar": 3, "mars": 3, "mrz": 3, "apr": 4, "avr": 4, "avril": 4, "may": 5, "mai": 5,
         "jun": 6, "juin": 6, "jul": 7, "juil": 7, "juillet": 7, "aug": 8, "aou": 8, "aout": 8,
         "sep": 9, "sept": 9, "septembre": 9, "oct": 10, "okt": 10, "octobre": 10,
         "nov": 11, "novembre": 11, "dec": 12, "dez": 12, "decembre": 12,
         "maa": 3, "mrt": 3, "mei": 5}
_ETF = re.compile(r"(?i)\b(etf|ucits|tracker|opcvm|fcp|sicav|opc|fund|index|indice|msci|s&p|stoxx)\b")


def _n(txt):
    """Nombre lu dans un relevé (« 1 234,56 », « +7 », « 10.000,00 ») ; None sinon."""
    if txt is None:
        return None
    # « 16'997.84 » : séparateur des milliers suisse (relevés de Saxo CH)
    return cto._nombre(str(txt).replace("€", "").replace("+", "").replace("'", "").replace("’", "").strip())


def _sans_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s or "") if unicodedata.category(c) != "Mn")


def _date_fr(txt: str, ordre: str = "jm") -> str:
    """« 26-03-2024 », « 26/03/2024 », « 2024-03-26 », « 20230522 »,
    « 09-Apr-2025 », « 8 octobre 2021 » -> 2024-03-26 ; sinon "".

    Aussi (4.4.19) : jour et mois sur un chiffre (« 1/3/2024 »), annee sur deux
    (« 26/03/24 »), « Mar 26, 2024 », « 01 juil. 2024 » ; `ordre` « mj » lit
    « 03/26/2024 » a l'americaine (choisi par colonne : _ordre_dates). Une date
    impossible (31/02) est refusee."""
    t = (txt or "").strip()

    def ok(a, m, j):
        try:
            return datetime.date(int(a), int(m), int(j)).isoformat()
        except ValueError:
            return ""

    def an(a):
        a = int(a)
        return a + (2000 if a < 70 else 1900) if a < 100 else a

    m = re.search(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", t)
    if m:
        return ok(m.group(1), m.group(2), m.group(3))
    m = re.search(r"(?<!\d)(\d{1,2})[-/.](\d{1,2})[-/.](\d{4}|\d{2})(?!\d)", t)
    if m:
        j, mo = (m.group(1), m.group(2)) if ordre != "mj" else (m.group(2), m.group(1))
        return ok(an(m.group(3)), mo, j)
    m = re.fullmatch(r"(\d{4})(\d{2})(\d{2})", t)
    if m:
        return ok(*m.groups())

    def mois(nom):
        n = _sans_accents(nom).lower().rstrip(".")
        return _MOIS.get(n[:9]) or _MOIS.get(n[:4]) or _MOIS.get(n[:3])
    m = re.search(r"(?<!\d)(\d{1,2})\.?[- ]([A-Za-zÀ-ÿ]{3,9})\.?[- ,]+(\d{4}|\d{2})(?!\d)", t)
    if m and mois(m.group(2)):
        return ok(an(m.group(3)), mois(m.group(2)), m.group(1))
    m = re.search(r"([A-Za-zÀ-ÿ]{3,9})\.? (\d{1,2}),? (\d{4})", t)
    if m and mois(m.group(1)):
        return ok(m.group(3), mois(m.group(1)), m.group(2))
    return ""


def _ordre_dates(valeurs: list) -> str:
    """« mj » si une colonne de dates est a l'americaine (03/26/2024 : le
    second nombre depasse 12 quelque part, jamais le premier), sinon « jm »."""
    premiers, seconds = [], []
    for v in valeurs:
        m = re.search(r"(?<!\d)(\d{1,2})[-/.](\d{1,2})[-/.](\d{4}|\d{2})(?!\d)", v or "")
        if m:
            premiers.append(int(m.group(1)))
            seconds.append(int(m.group(2)))
    return "mj" if seconds and max(seconds) > 12 and max(premiers) <= 12 else "jm"


def _classe(*textes) -> str:
    return "etf" if any(_ETF.search(t or "") for t in textes) else "action"


class _Lot:
    """Les opérations lues dans un fichier, avec un identifiant stable pour
    chacune : la référence de la banque, sinon une empreinte (deux opérations
    identiques du même fichier restent distinctes ; le même fichier relu donne
    les mêmes identifiants, d'où pas de doublon au second import)."""

    def __init__(self, banque: str):
        self.banque, self.ops, self._vus = banque, [], {}

    def ajoute(self, type_, date, isin="", nom="", qty=0.0, cours=None, montant=0.0,
               frais=0.0, taxe=0.0, quand="", ref="", origine=None, classe=None, alerte=""):
        if not date:
            return None
        cle = f"{self.banque}|{type_}|{date}|{isin}|{qty or 0:.6f}|{montant or 0:.2f}"
        n = self._vus.get(cle, 0)
        self._vus[cle] = n + 1
        trid = ref or ("h:" + hashlib.sha1(f"{cle}#{n}".encode()).hexdigest()[:16])
        op = {"trId": trid, "date": date, "quand": quand or date, "type": type_,
              "origine": origine or {"Dividende": "dividende"}.get(type_, "ordre"),
              "isin": isin, "nom": " ".join((nom or "").split()), "nomLong": "",
              "classe": classe or _classe(nom), "qty": abs(qty or 0),
              "cours": round(cours, 6) if cours else cours,
              "montant": round(abs(montant or 0), 2), "frais": round(abs(frais or 0), 2),
              "taxe": round(abs(taxe or 0), 2), "alerte": alerte, "banque": self.banque}
        if type_ in ("Achat", "Vente") and not op["cours"] and op["qty"] and op["montant"]:
            op["cours"] = round(op["montant"] / op["qty"], 6)
        if type_ in ("Achat", "Vente") and op["cours"] and op["qty"] and not op["montant"]:
            op["montant"] = round(op["cours"] * op["qty"], 2)
        # Les chiffres lus doivent tenir ensemble : parts x cours = montant (a
        # 0,5 % pres : cours arrondi, part de fonds). Sinon un nombre a ete mal
        # decoupe (« 10 250,00 » lu comme un seul nombre) : l'apercu le dit.
        if type_ in ("Achat", "Vente") and op["cours"] and op["qty"] and op["montant"] \
                and abs(op["qty"] * op["cours"] - op["montant"]) > max(0.02, 0.005 * op["montant"]):
            op["alerte"] = ", ".join(x for x in (op["alerte"], "chiffres à vérifier : %g × %g ≠ %.2f"
                                                 % (op["qty"], op["cours"], op["montant"])) if x)
        self.ops.append(op)
        return op


# ─── Conversion en euros ──────────────────────────────────────────────────────

_fx_cache = {}


def _vers_eur(montant, devise, date):
    """Montant dans une autre devise -> euros, au cours de clôture du jour
    (Yahoo, paire EUR<devise>=X). None si le cours est introuvable."""
    devise = (devise or "EUR").upper()
    if montant is None or devise == "EUR":
        return montant
    cle = (devise, date)
    if cle not in _fx_cache:
        import server   # ici et pas en tête : releves se teste sans le serveur
        tk = f"EUR{devise}=X"
        taux = None
        try:
            h = server.get_history([tk], "max", since=date).get(tk) or {}
            avant = [c for d, c in zip(h.get("dates", []), h.get("closes", [])) if d <= date and c]
            taux = avant[-1] if avant else None
        except Exception:
            taux = None
        _fx_cache[cle] = taux
    taux = _fx_cache[cle]
    return montant / taux if taux else None


# ─── PDF ──────────────────────────────────────────────────────────────────────

def texte_pdf(data: bytes, mode: str = "plain") -> str:
    """Texte d'un PDF. `mode` « layout » : pypdf replace chaque mot a sa place
    sur la page (lignes reconstituees d'apres les positions), utile quand le
    document ecrit ses colonnes l'une apres l'autre."""
    from pypdf import PdfReader   # bibliothèque ajoutée en 4.4.3 (requirements.txt)
    lecteur = PdfReader(io.BytesIO(data))
    if lecteur.is_encrypted:
        try:
            if not lecteur.decrypt(""):
                raise ValueError
        except Exception:
            raise ValueError("PDF protégé par un mot de passe : ouvre-le et enregistre-le sans mot de passe")
    pages = []
    for p in lecteur.pages:
        try:
            pages.append(p.extract_text(extraction_mode=mode) or "")
        except Exception:
            pages.append("")
    return _norm_texte("\n".join(pages))


# Ce que les PDF de banque glissent dans leurs nombres et leurs mots : espaces
# insecables ou fines entre les milliers (« 1 234,56 »), signe moins
# typographique (« −12,50 »), apostrophe courbe (« d’opéré »), accents
# decomposes (« e » + accent), ligatures (« ﬁ »), cesures invisibles.
_ESPACES = re.compile("[\u00a0\u202f\u2007\u2009\u2002-\u2006\u2008\u200a]")


def _norm_texte(t: str) -> str:
    t = unicodedata.normalize("NFC", t or "")
    t = _ESPACES.sub(" ", t)
    t = t.replace("\u00ad", "").replace("\u2019", "'").replace("\u2018", "'")
    t = re.sub("[\u2212\u2013](?=\\s?\\d)", "-", t)
    for lig, rem in (("\ufb00", "ff"), ("\ufb01", "fi"), ("\ufb02", "fl"), ("\ufb03", "ffi"), ("\ufb04", "ffl")):
        t = t.replace(lig, rem)
    return t


def _montants(ligne: str) -> list:
    return [_n(x) for x in re.findall(_MT, ligne or "")]


def _ligne_apres(t: str, motif: str) -> str:
    """La ligne qui suit celle où apparaît `motif` (regex), ou ""."""
    m = re.search(motif + r"[^\n]*\n([^\n]*)", t)
    return m.group(1) if m else ""


# Fortuneo (Arkéa Direct Bank) ─────────────────────────────────────────────────

def _fortuneo(t: str, lot: _Lot):
    if re.search(r"AVIS D.OP[ÉE]RATIONS", t):
        # Un bloc par titre (« ACTION : ORANGE (FR0000133308) »), une ou plusieurs
        # exécutions par bloc (« 26-03-2024 Référence 94R6134018440990 »)
        titres = list(re.finditer(r"(ACTION|TRACKER|OPCVM|OBLIGATION|DROIT|CERTIFICAT|WARRANT|[A-Z]{3,})\s*:\s*"
                                  r"(.+?)\s*\((" + _ISIN + r")\)", t))
        for i, b in enumerate(titres):
            fin = titres[i + 1].start() if i + 1 < len(titres) else len(t)
            bloc = t[b.end():fin]
            execs = list(re.finditer(r"(\d{2}-\d{2}-\d{4})\s+Référence\s+(\S+)", bloc))
            for j, e in enumerate(execs):
                seg = bloc[e.start():execs[j + 1].start() if j + 1 < len(execs) else len(bloc)]
                sens = re.search(r"Sens\s+(Achat|Vente|Souscription|Rachat)", seg)
                qte = re.search(r"Quantité\s+([\d  ,.]+?)\s+(?:Cours|Val\.\s*Liquidative)\s+(" + _MT + r"|[\d  ]+)", seg)
                if not (sens and qte):
                    continue
                heure = re.search(r"(\d{2}:\d{2}:\d{2})", seg)
                brut = re.search(r"Montant Brut\s+(" + _MT + ")", seg)
                net = re.search(r"Montant NET\s+(" + _MT + ")", seg)
                frais = sum(_n(x) or 0 for x in re.findall(
                    r"(?:Courtage et Commission|Droits entrée/sortie)\s+(" + _MT + ")", seg))
                date = _date_fr(e.group(1))
                # La référence seule ne suffit pas : deux ordres du même avis la
                # partagent parfois (Crédit Agricole et Orange, 04/07/2023)
                lot.ajoute("Vente" if sens.group(1) in ("Vente", "Rachat") else "Achat", date,
                           b.group(3), b.group(2), _n(qte.group(1)), _n(qte.group(2)),
                           _n(brut.group(1)) if brut else 0, frais,
                           quand=date + ("T" + heure.group(1) if heure else ""),
                           ref=f"fo:{e.group(2)}:{b.group(3)}:{_n(qte.group(1))}",
                           classe=_classe(b.group(1), b.group(2)),
                           alerte="" if net else "montant net illisible")
    elif "ENCAISSEMENT COUPON" in t:
        b = re.search(r"(ACTION|TRACKER|OPCVM|OBLIGATION)\s+(\S.*?)\s*\((" + _ISIN + r")\)", t) \
            or re.search(r"()(\S.*?)\s*\((" + _ISIN + r")\)", t)
        d = re.search(r"(\d{2}/\d{2}/\d{4})", t)
        q = re.search(r"Quantité\s+([\d  ,.]+)", t)
        net = re.search(r"Montant Net\s+(" + _MT + ")", t)
        if b and d and net:
            lot.ajoute("Dividende", _date_fr(d.group(1)), b.group(3), b.group(2),
                       _n(q.group(1)) if q else 0, montant=_n(net.group(1)))
    elif "TAXE SUR LES" in t and "TRANSACTIONS FINANCIERES" in t:
        titres = list(re.finditer(r"(\S.*?)\s*\((" + _ISIN + r")\)", t))
        for i, b in enumerate(titres):
            bloc = t[b.end():titres[i + 1].start() if i + 1 < len(titres) else len(t)]
            d = re.search(r"(\d{2}-\d{2}-\d{4})", bloc)
            m = re.search(r"Montant de la TTF\s*:\s*(" + _MT + ")", bloc) \
                or re.search(r"(" + _MT + r")\s*\n\s*Montant de la TTF", bloc)
            if d and m:
                lot.ajoute("Taxe", _date_fr(d.group(1)), b.group(2), b.group(1), montant=_n(m.group(1)),
                           origine="taxe")
    elif re.search(r"LIQUIDITES sur PEA", t):
        # Relevé annuel des espèces du PEA : seuls les versements et retraits
        # (les ordres n'y ont pas d'ISIN : ils viennent des avis d'opéré)
        an = re.search(r"Ancien solde au \d{2}/\d{2}/(\d{4})", t) or re.search(r"Nouveau Solde au \d{2}/\d{2}/(\d{4})", t)
        if an:
            for m in re.finditer(r"^(\d{2})/(\d{2})\s+(VERSEMENT|RETRAIT|REGULARISATION)\b.*?(" + _MT + r")\s*$", t, re.M):
                date = f"{an.group(1)}-{m.group(2)}-{m.group(1)}"
                if m.group(3) == "REGULARISATION":
                    # Sens inconnu (débit ou crédit ?) : montrée, pas reprise
                    lot.inconnues.append({"type": "REGULARISATION " + m.group(4), "categorie": "Fortuneo",
                                          "nom": "", "date": date})
                    continue
                lot.ajoute("Versement" if m.group(3) == "VERSEMENT" else "Retrait", date,
                           montant=_n(m.group(4)), origine="especes")
    elif "RESULTAT D'OST" in t or "RÉSULTAT D'OST" in t:
        s = re.search(r"souscription de\s+([\d  ,.]+)\s+titre\(s\)\s+(.+?)\s*\((" + _ISIN + r")\)", t, re.S)
        m = re.search(r"montant net de\s*:\s*-?\s*(" + _MT + ")", t)
        d = re.search(r"Au\s+(\d{1,2}\s+\S+\s+\d{4})", t)
        if s and m and d:
            qty = _n(s.group(1))
            lot.ajoute("Achat", _date_fr(d.group(1)), s.group(3), s.group(2), qty,
                       _n(m.group(1)) / qty if qty else None, _n(m.group(1)), origine="ordre")
    else:
        return False
    return True


# BoursoBank ───────────────────────────────────────────────────────────────────

def _boursobank(t: str, lot: _Lot):
    if "COUPONS REMBOURSEMENTS" in t:
        for m in re.finditer(r"^(\d{2}/\d{2}/\d{4})\s+([\d  ,.]+?)\s+(.+?)\s*\((" + _ISIN + r")\)\s*(.*)$", t, re.M):
            mts = _montants(m.group(5))
            if mts:
                lot.ajoute("Dividende", _date_fr(m.group(1)), m.group(4), m.group(3),
                           _n(m.group(2)), montant=mts[-1])
        return True
    if not re.search(r"OPERATION (DE BOURSE|SUR OPC)", t):
        return False
    sens = re.search(r"\b(ACHAT|VENTE)\s+COMPTANT|\b(SOUSCRIPTION|REPRISE|RACHAT)\s+(?:SICAV|F\.C\.P\.|FCP|OPC)", t)
    ligne = re.search(r"^(\d{2}/\d{2}/\d{4})\s+([\d  ,.]+?)\s+(\S.*?)(?:\s+Référence.*)?$", t, re.M)
    isin = re.search(r"Code ISIN\s*:\s*(" + _ISIN + ")", t)
    cours = re.search(r"(?:Cours exécuté|Valeur liquidative)\s*:\s*([\d  ,.]+?)\s*([A-Z]{3})", t)
    if not (sens and ligne and isin and cours):
        return True
    achat = (sens.group(1) or sens.group(2)) in ("ACHAT", "SOUSCRIPTION")
    qty = _n(ligne.group(2))
    net = _montants(_ligne_apres(t, r"Montant net au (?:débit|crédit) de votre compte"))
    entete = re.search(r"^[^\n]*Montant net au (?:débit|crédit) de votre compte", t, re.M).group(0) \
        if net else ""
    cv = re.search(r"Contrevalorisation en EURO\s+[\d,.]+\s+(" + _MT + r")\s*EUR", t)
    taxe = 0.0
    if cv:                                  # titre étranger : contre-valeur en euros
        brut = _n(cv.group(1))
    elif "Montant brut" in entete and net:  # « brut, commission, [frais TTF], net » sur une ligne
        brut = net[0]
        if "Commission Frais" in entete and len(net) == 4:
            taxe = net[2]
    else:                                   # « Montant transaction brut … » puis la ligne des montants
        brut = (_montants(_ligne_apres(t, r"Montant (?:transaction )?brut")) or [None])[0]
    total = net[-1] if net else None
    heure = re.search(r"(\d{2}:\d{2}:\d{2})", t)
    ref = re.search(r"Référence\s*:\s*(\S+)", t)
    date = _date_fr(ligne.group(1))
    frais = abs((total or 0) - (brut or 0)) - taxe if total and brut else 0
    devise = cours.group(2)
    prix = _n(cours.group(1)) if devise == "EUR" else (brut / qty if brut and qty else None)
    lot.ajoute("Achat" if achat else "Vente", date, isin.group(1), ligne.group(3), qty, prix, brut,
               frais, taxe, quand=date + ("T" + heure.group(1) if heure else ""),
               ref="bb:" + ref.group(1) if ref else "",
               classe=_classe(ligne.group(3), "OPC" if "OPC" in t[:200] else ""),
               alerte="" if total else "montant net illisible")
    return True


# Bourse Direct ────────────────────────────────────────────────────────────────

def _boursedirect(t: str, lot: _Lot):
    if "Avis d'Opération" not in t and "relevé d'opérations" not in t:
        return False
    lignes = t.splitlines()
    tete = re.compile(r"^\s*(\d{2}/\d{2}/\d{4})\s+(.+?)\s+(" + _ISIN + r")\s+(.+?)\s+(" + _MT + r")\s*$")
    esp = re.compile(r"^\s*(\d{2}/\d{2}/\d{4})\s+((?:INVESTISSEMENT|VIREMENT|RETRAIT|REMBOURSEMENT)\s+ESPECES)\s+(.*?)\s*(" + _MT + r")\s*$")
    autre = re.compile(r"^\s*(\d{2}/\d{2}/\d{4})\s+(.+?)\s+(" + _MT + r")\s*$")
    i = 0
    while i < len(lignes):
        ln = lignes[i]
        m = tete.match(ln)
        if m:
            date, typ, isin, nom, total = _date_fr(m.group(1)), m.group(2).strip(), m.group(3), m.group(4), _n(m.group(5))
            det = []
            i += 1
            while i < len(lignes) and not re.match(r"^\s*\d{2}/\d{2}/\d{4}\s", lignes[i]) and "Sous réserve" not in lignes[i]:
                det.append(lignes[i])
                i += 1
            d = " ".join(det)
            v = lambda cle: _n((re.search(cle + r"\s*:\s*([-+]?[\d  ,.]+)", d) or [None, None])[1])
            heure = re.search(r"Execution\s*:\s*(\d{2}:\d{2}:\d{2})", d)
            quand = date + ("T" + heure.group(1) if heure else "")
            if typ.startswith(("ACHAT", "VENTE")):
                brut = v("BRUT") or 0
                taxe = v("TAXE ETRANG") or 0
                lot.ajoute("Achat" if typ.startswith("ACHAT") else "Vente", date, isin, nom, v("QUANTITE"),
                           v("COURS"), brut, abs(total - brut) - taxe if brut else 0, taxe, quand=quand)
            elif typ.startswith("COUPON") or "DIVIDENDE" in typ:
                lot.ajoute("Dividende", date, isin, nom, v("QUANTITE"), montant=total)
            elif "TAXE TRANSACT" in typ:
                lot.ajoute("Taxe", date, isin, nom, montant=total, origine="taxe")
            else:
                lot.inconnues.append({"type": typ, "categorie": "Bourse Direct", "nom": nom, "date": date})
            continue
        m = esp.match(ln)
        if m:
            lot.ajoute("Retrait" if m.group(2).startswith("RETRAIT") else "Versement",
                       _date_fr(m.group(1)), montant=_n(m.group(4)), origine="especes")
        else:
            m = autre.match(ln)
            if m and not ln.strip().startswith("Le "):
                lot.inconnues.append({"type": m.group(2).strip()[:40], "categorie": "Bourse Direct",
                                      "nom": "", "date": _date_fr(m.group(1))})
        i += 1
    return True


# Saxo (rapports PDF en anglais ou en allemand) ────────────────────────────────

def _saxo(t: str, lot: _Lot):
    if "Saxo" not in t:
        return False
    dev = re.search(r"(?:Currency|Währung|Devise)\s*:\s*([A-Z]{3})", t)
    devise = dev.group(1) if dev else "EUR"
    # « 1.234,56 » (EU), « 16'997.84 » ou « 19.50 » (Saxo CH), « 49 »
    num = r"-?\d{1,3}(?:[.']\d{3})*,\d+|-?\d{1,3}(?:'\d{3})+(?:\.\d+)?|-?\d+(?:\.\d+)?"
    if re.search(r"Trade Details Report|Bericht zu Trade-Details|Trade details", t):
        blocs = re.split(r"\n(?=Instrument\s)", t)
        for b in blocs[1:]:
            # Le nom est parfois sur la ligne suivante : il reste vide, l'import
            # reprend alors celui de la cotation trouvée par l'ISIN
            nom = re.search(r"Instrument\s*(.*?)\s*(?:Trade time|Handelszeit)\s+(\d{2}-\w{3}-\d{4})\s+(\d{2}:\d{2}:\d{2})", b)
            isin = re.search(r"ISIN\s+(" + _ISIN + ")", b)
            sens = re.search(r"(?:B/S|K/V)\s+(Buy|Sell|Kauf|Verkauf)", b)
            qte = re.search(r"(?:Quantity|Menge)\s+(" + num + ")", b)
            part = re.search(r"^(?:Share Amount|Aktienbetrag)\s.*?(" + num + r")\s*$", b, re.M)
            net = re.search(r"^(?:Net Amount|Nettobetrag)\s.*?(" + num + r")\s*$", b, re.M)
            ref = re.search(r"(?:Trade ID|Trade-ID)\s+(\d+)", b)
            if not (nom and isin and sens and qte and part and net):
                continue
            date = _date_fr(nom.group(2))
            brut = _vers_eur(abs(_n(part.group(1))), devise, date)
            total = _vers_eur(abs(_n(net.group(1))), devise, date)
            if brut is None or total is None:
                lot.inconnues.append({"type": "devise " + devise, "categorie": "Saxo", "nom": nom.group(1), "date": date})
                continue
            achat = sens.group(1) in ("Buy", "Kauf")
            lot.ajoute("Achat" if achat else "Vente", date, isin.group(1), nom.group(1), abs(_n(qte.group(1))),
                       None, brut, abs(total - brut), quand=date + "T" + nom.group(3),
                       ref="sx:" + ref.group(1) if ref else "")
    elif re.search(r"Corporate Action Detail|Kapitalmaßnahme", t):
        isin = re.search(r"ISIN\s+(" + _ISIN + ")", t)
        desc = re.search(r"(?:Description|Beschreibung)\s+(.+?)\s+(?:Dividend per share|Dividende pro Aktie)", t)
        qty = re.search(r"(?:Eligible quantity|Berechtigte Menge|Geeignete Menge)\s+(" + num + ")", t)
        net = re.search(r"^(?:Net Amount|Nettobetrag)\s.*?(" + num + r")\s*$", t, re.M)
        # Lignes « ID, date ex, date d'enregistrement, date de comptabilisation
        # (parfois « - »), date de paiement, montant, taux, montant comptabilisé »
        lignes = re.findall(r"\d{6,}\s+\d{2}-\w{3}-\d{4}\s+\S+\s+\S+\s+(\d{2}-\w{3}-\d{4})\s+(?:" + num + r")\s+(?:"
                            + num + r")\s+(" + num + r")\s*$", t, re.M)
        if isin and lignes:
            date = _date_fr(lignes[0][0])
            # Net : la ligne « Net Amount » si elle est là, sinon dividende + retenue à la source
            mt = abs(_n(net.group(1))) if net else sum(_n(x[1]) for x in lignes)
            mt = _vers_eur(abs(mt), devise, date)
            if mt is not None:
                lot.ajoute("Dividende", date, isin.group(1), desc.group(1) if desc else "",
                           abs(_n(qty.group(1))) if qty else 0, montant=mt)
    elif re.search(r"Cash Transfer|Bargeldtransfer", t):
        for m in re.finditer(r"^(Deposit|Einlage|Withdrawal|Auszahlung)\s+\d+\s+(\d{2}-\w{3}-\d{4})\s.*?(" + num + r")\s*$", t, re.M):
            date = _date_fr(m.group(2))
            mt = _vers_eur(abs(_n(m.group(3))), devise, date)
            if mt is not None:
                lot.ajoute("Versement" if m.group(1) in ("Deposit", "Einlage") else "Retrait", date,
                           montant=mt, origine="especes")
    return True


# Degiro (rapport des transactions en PDF) ─────────────────────────────────────

def _degiro_pdf(t: str, lot: _Lot):
    if "DEGIRO" not in t.upper() or not re.search(r"Transactions du|Transactions from|Transacties van", t):
        return False
    # Trois variantes vues : montants suivis de « EUR » (2022, 2024), sans
    # frais ni lieu d'exécution (échange de titres à 00:00), et le format de
    # 2025 sans devise après les montants, dans la devise du compte (« Montant
    # CHF » dans l'en-tête). Une ligne par exécution ; un nom trop long continue
    # sur la ligne suivante (ignorée).
    Q = r"-?\d{1,3}(?:[ .]\d{3})*(?:,\d+)?"
    P = r"\d{1,3}(?:[ .]\d{3})*(?:,\d+)?"
    A = r"-?\d{1,3}(?:[ .]\d{3})*,\d{2}"
    debut = r"^(\d{2}-\d{2}-\d{4}) (\d{2}:\d{2}) (.+?) (" + _ISIN + r") (?:[A-Z][A-Z0-9]{1,5} ){1,2}(" + Q + r") (" + P + r") ([A-Z]{3}) (" + A + r") [A-Z]{3} "
    ancien = re.compile(debut + r"(" + A + r") EUR(?: (\d+,\d+))?(?: (" + A + r"))?(?: EUR)? (" + A + r") EUR$", re.M)
    nouveau = re.compile(debut + r"(" + A + r")(?: (\d+,\d+))?(?: (" + A + r"))?(?: (" + A + r"))? (" + A + r")$", re.M)
    base = re.search(r"locale\s+([A-Z]{3})\s+change", t)
    base = base.group(1) if base else "EUR"
    for m in list(ancien.finditer(t)) or list(nouveau.finditer(t)):
        date = _date_fr(m.group(1))
        qty = _n(m.group(5))
        # Frais : l'écart entre le montant et le net (« Montant négocié »). En
        # 2025, la colonne « frais AutoFX » n'est pas retirée du net : 898,75 −
        # 4,60 = 894,15 CHF pour ASML, avec −2,25 d'AutoFX à côté.
        valeur, total = _n(m.group(9)), _n(m.group(m.re.groups))
        frais, dev_cpt = abs(abs(valeur) - abs(total)), ("EUR" if m.re is ancien else base)
        # Titre coté en euros : son montant en euros est exact ; sinon conversion
        brut = abs(_n(m.group(8))) if m.group(7) == "EUR" else _vers_eur(abs(valeur), dev_cpt, date)
        frais = _vers_eur(abs(frais), dev_cpt, date) if frais else 0
        if not qty or brut is None:
            continue
        lot.ajoute("Achat" if qty > 0 else "Vente", date, m.group(4), m.group(3), abs(qty), None,
                   brut, frais or 0, quand=f"{date}T{m.group(2)}:00")
    return True


# Trade Republic (avis en français) ───────────────────────────────────────────

# Nombre d'un avis : « 1 234,56 », « 0,3773 », « 53.703679652 », « -1,00 »
_NB = r"-?\d[\d .]*(?:,\d+)?|-?\d+(?:\.\d+)?"


def _traderepublic(t: str, lot: _Lot):
    """Avis de Trade Republic en français (exemples réels anonymisés de
    Portfolio Performance) : relevé de transaction d'un ordre, confirmation
    d'un investissement programmé (plan), confirmation d'exécution d'une
    vente, dividende ou distribution. Le relevé de compte mensuel n'est pas
    lu (ni cours ni frais par ordre) : l'export CSV le remplace."""
    if not re.search(r"RÉCAPITULATIF|RELEVÉ DE TRANSACTION|CONFIRMATION D", t):
        return False
    if "RÈGLEMENT DU VERSEMENT" in t:
        # Versement sur le compte (utile pour un PEA ; ignoré sur un CTO)
        total = re.findall(r"^TOTAL\s+(" + _NB + r")\s+EUR\s*$", t, re.M)
        date = re.search(r"COMPTE-ESPÈCES[^\n]*\n\S+\s+(\d{2}[./]\d{2}[./]\d{4})", t)
        if total and date:
            lot.ajoute("Versement", _date_fr(date.group(1)), montant=abs(_n(total[-1])), origine="especes")
        return True
    isin = re.search(r"(?:ISIN\s*:?\s*)?\b(" + _ISIN + r")\b", t)
    if not isin:
        return False
    # Ligne du titre : « Apple Inc. 0,92086 titre(s) 156,18 EUR 143,82 EUR »,
    # « Nemetschek 0,487012 123,20 EUR 60,00 EUR », ou, pour un dividende sur
    # plusieurs lignes, « US5949181045 0.561914 unit. 0.75 USD »
    ligne = re.search(r"^(.*?)\s*(" + _NB + r")\s*(?:titre\(s\)|unit\.|Stk\.|pc\.)?\s+(" + _NB + r")\s+([A-Z]{3})\s+("
                      + _NB + r")\s+([A-Z]{3})\s*$", t, re.M)
    qte = re.search(r"(" + _NB + r")\s*(?:titre\(s\)|unit\.)", t)
    nom = ""
    if ligne and not re.fullmatch(_ISIN, ligne.group(1).strip()):
        nom = ligne.group(1).strip()
    if not nom:
        avant = re.search(r"(?:POSITION|TITRE) QUANTITÉ[^\n]*\n([^\n]+)", t)
        nom = re.sub(r"\s+" + _NB + r".*$", "", avant.group(1)).strip() if avant else ""
    devise = (ligne.group(6) if ligne else "EUR").upper()
    if re.search(r"\bDIVIDENDE\b|\bDISTRIBUTION\b", t[:1500]) and not re.search(r"-Order (?:Achat|Vente)", t):
        nets = re.findall(r"^TOTAL\s+(" + _NB + r")\s+EUR\s*$", t, re.M)
        date = re.search(r"(?:COMPTE-ESPÈCES|COMPTE DE RÈGLEMENT)[^\n]*\n\S+\s+(\d{2}[./]\d{2}[./]\d{4})", t)
        if nets and date:
            lot.ajoute("Dividende", _date_fr(date.group(1)), isin.group(1), nom,
                       _n(qte.group(1)) if qte else 0, montant=abs(_n(nets[-1])))
        return True
    plan = "INVESTISSEMENT PROGRAMMÉ" in t.upper()
    sens = re.search(r"-Order\s+(Achat|Vente)", t)
    if not (ligne and (plan or sens)):
        return True
    vente = bool(sens and sens.group(1) == "Vente")
    d = re.search(r"(?:le|exécuté le)\s+(\d{2}[./]\d{2}[./]\d{4})(?:\s+à\s+(\d{2}:\d{2}))?", t)
    if not d:
        return True
    date = _date_fr(d.group(1))
    qty, cours, brut = abs(_n(ligne.group(2))), _n(ligne.group(3)), abs(_n(ligne.group(5)))
    frais = sum(abs(_n(x) or 0) for x in re.findall(r"^Frais[^\n]*?\s(" + _NB + r")\s+EUR\s*$", t, re.M))
    taxe = sum(abs(_n(x) or 0) for x in re.findall(r"^Taxe sur les transactions[^\n]*?\s(" + _NB + r")\s+EUR\s*$", t, re.M | re.I))
    if devise != "EUR":
        brut, cours = _vers_eur(brut, devise, date), None
        if brut is None:
            lot.inconnues.append({"type": "devise " + devise, "categorie": "Trade Republic", "nom": nom, "date": date})
            return True
    ref = re.search(r"EXÉCUTION\s+([0-9a-f]{4}-[0-9a-f]{4})", t)
    lot.ajoute("Vente" if vente else "Achat", date, isin.group(1), nom, qty, cours, brut, frais, taxe,
               quand=date + ("T" + d.group(2) + ":00" if d.group(2) else ""),
               ref="tr:" + ref.group(1) if ref else "", origine="plan" if plan else "ordre")
    return True


# Avis d'opéré d'une autre banque : lecteur universel ──────────────────────────

# Rubriques d'un avis d'opéré, sous leurs noms habituels (ordre = priorité)
_RUBRIQUES = [
    ("qty", r"quantit[ée] ex[ée]cut[ée]e|quantit[ée]|qt[ée]|nombre de titres|nombre de parts|nb de titres|nombre"),
    ("cours", r"cours d'ex[ée]cution|cours ex[ée]cut[ée]|prix d'ex[ée]cution|cours moyen|prix moyen|prix unitaire|"
              r"valeur liquidative|cours unitaire|au cours de|cours|prix"),
    ("brut", r"montant brut|montant de la transaction|montant transaction brut|montant n[ée]goci[ée]|"
             r"montant de l'op[ée]ration|brut"),
    ("taxe", r"taxe sur les transactions financi[eè]res|t\.t\.f\.?|ttf"),
    ("frais", r"frais de courtage|frais de bourse|frais de transaction|frais externes|courtage|commissions?|frais"),
    ("net", r"montant net (?:au (?:d[ée]bit|cr[ée]dit) de votre compte|[àa] (?:d[ée]biter|cr[ée]diter)|d[ée]bit[ée]|"
            r"cr[ée]dit[ée])|net [àa] (?:d[ée]biter|cr[ée]diter)|montant net|total net|net|d[ée]bit|cr[ée]dit"),
]
# Dans un en-tete de tableau seulement : « Montant » seul est le brut
_RUBRIQUES_TABLEAU = _RUBRIQUES + [("brut", r"montant")]
_NUM = r"-?\d{1,3}(?:[ .]\d{3})+(?:,\d+)?|-?\d+(?:[.,]\d+)?"
_DEV = r"(?:\s*(?:EUR|€|USD|\$|GBP|£|CHF))?"


def _motif(m: str) -> str:
    """Un nom de rubrique peut etre coupe en fin de ligne (« Taxe sur les
    transactions » / « financières 31,23 EUR ») : une espace vaut toute suite
    d'espaces ou de retours a la ligne."""
    return m.replace(" ", r"\s+")


def _accord(v: dict) -> bool:
    """Les rubriques lues tiennent-elles ensemble ? parts x cours = brut, et
    brut ± frais ± taxe = net (achat ou vente)."""
    q, c, b, n = v.get("qty"), v.get("cours"), v.get("brut"), v.get("net")
    f, tx = abs(v.get("frais") or 0), abs(v.get("taxe") or 0)
    if q and c and b and abs(abs(q) * abs(c) - abs(b)) > max(0.02, 0.005 * abs(b)):
        return False
    if b and n and min(abs(abs(n) - (abs(b) + f + tx)), abs(abs(n) - (abs(b) - f - tx))) > 0.02:
        return False
    return True


def _decoupages(ligne: str, n: int) -> list:
    """Les façons de lire `n` nombres dans une ligne ou l'espace separe a la
    fois les milliers (« 3 986,17 ») et les colonnes : « 12 332,181 3 986,17 »
    est « 12 | 332,181 | 3 986,17 » ou « 12 332,181 | 3 986,17 ». Seul
    l'accord des chiffres (_accord) tranche ensuite."""
    toks = [re.sub(r"(?i)(eur|€|usd|\$)$", "", x) for x in ligne.split()]
    toks = [x for x in toks if x]
    if not toks or not all(re.fullmatch(r"-?\d+(?:[.,]\d+)?", x) for x in toks) or len(toks) > 14:
        return []
    res = []

    def suite(i, groupes):
        if len(groupes) > n:
            return
        if i == len(toks):
            if len(groupes) == n:
                res.append([_n(g) for g in groupes])
            return
        x = toks[i]
        # Collé au nombre precedent comme groupe de milliers ?
        if groupes and re.fullmatch(r"\d{3}(?:[.,]\d+)?", x) and re.fullmatch(r"-?\d{1,3}(?: \d{3})*", groupes[-1]):
            suite(i + 1, groupes[:-1] + [groupes[-1] + " " + x])
        suite(i + 1, groupes + [x])
    suite(0, [])
    return res


def _rubriques_avis(t: str) -> dict:
    """{rubrique: nombre} d'un avis : « Quantité : 10 », « Cours 52,30 EUR »,
    et aussi un tableau dont les noms de colonnes sont sur une ligne et les
    nombres sur une suivante (« Quantité  Cours  Montant brut » / « 10  52,30
    523,00 »), courant chez les banques de réseau."""
    res = {}
    tout = "|".join("(?P<%s%d>%s)" % (k, i, _motif(m)) for i, (k, m) in enumerate(_RUBRIQUES_TABLEAU))
    lignes = t.splitlines()
    for i, l in enumerate(lignes):
        # Tableau : au moins deux rubriques sur la ligne et aucun nombre
        trouves = [m.lastgroup.rstrip("0123456789")
                   for m in re.finditer(r"(?i)(?<![a-zà-ÿ])(?:" + tout + r")(?![a-zà-ÿ])", l)]
        if len(trouves) < 2 or re.search(r"\d", l) or len(set(trouves)) != len(trouves):
            continue
        suite = next((x for x in lignes[i + 1:i + 5] if x.strip()), "")
        bons = [dict(zip(trouves, d)) for d in _decoupages(suite, len(trouves))]
        bons = [v for v in bons if all(x is not None for x in v.values()) and _accord(v)]
        if bons:
            for k, v in bons[0].items():
                res.setdefault(k, v)
    # Ligne du titre : « Acheter iShares Physical Gold ETC 1.002416 pc. 78.61
    # EUR 78.80 EUR » (parts, cours, montant : retenue si parts x cours = montant)
    if not ("qty" in res and ("cours" in res or "brut" in res)):
        for m in re.finditer(r"(?m)^[^\n]*?\s(" + _NUM + r")\s*(?:pc\.|titre\(s\)|titres|parts?|unit\.|actions?)?\s+("
                             + _NUM + r")\s*(?:EUR|€)\s+(" + _NUM + r")\s*(?:EUR|€)\s*$", t):
            q, c, mt = (_n(x) for x in m.groups())
            if q and c and mt and abs(abs(q) * c - abs(mt)) <= max(0.02, 0.005 * abs(mt)):
                res.setdefault("qty", abs(q))
                res.setdefault("cours", c)
                res.setdefault("brut", abs(mt))
                break
    # Rubrique suivie de son nombre (meme ligne, ou ligne suivante)
    for k, motif in _RUBRIQUES:
        if k in res:
            continue
        m = re.search(r"(?im)(?:^|[\s|(])(?:" + _motif(motif) + r")(?![a-zà-ÿ])[^\S\n]*(?:\([^)]{0,40}\))?[^\S\n]*(?::|\.{2,})?\s*("
                      + _NUM + ")" + _DEV + r"(?![\d/])", t)
        if m:
            res[k] = _n(m.group(1))
    # « ACHAT de 25 BNP PARIBAS … au cours de 61,08 EUR »
    if "qty" not in res:
        m = re.search(r"(?:ACHAT|VENTE|SOUSCRIPTION|RACHAT|Achat|Vente|Souscription|Rachat)\s+(?:de\s+)?(" + _NUM
                      + r")\s+(?:titres?\s+|parts?\s+|actions?\s+)?[A-Za-z]", t)
        if m:
            res["qty"] = _n(m.group(1))
    return res


def _avis_generique(t: str, lot: _Lot):
    """Avis d'opéré d'une banque sans règle propre (Crédit Agricole, BNP,
    Société Générale, LCL, Caisse d'Épargne, Banque Populaire, La Banque
    Postale, CIC, Crédit Mutuel… : aucun exemple public). Un seul titre par
    avis ; les rubriques sont cherchées par leur nom habituel
    (_rubriques_avis).

    Rien n'est repris si les chiffres ne tiennent pas ensemble : parts x
    cours = montant brut, et brut ± frais = net quand le net est donné. Un
    avis mal compris est ainsi « non lu » plutôt qu'importé faux."""
    isins = set(re.findall(r"\b(" + _ISIN + r")\b", t))
    if len(isins) != 1:
        return False
    isin = isins.pop()
    # Un avis en français seulement (deux mots du métier au moins) : un avis
    # en néerlandais ou en allemand n'a ni les mêmes rubriques ni les mêmes dates
    francais = {m.lower() for m in re.findall(r"(?i)(?<![a-zà-ÿ])(montant|quantit[ée]|courtage|commission|frais|achat|"
                                              r"vente|dividende|souscription|cours)(?![a-zà-ÿ])", t)}
    if len(francais) < 2:
        return False

    def date_de(motifs):
        for motif in motifs:
            m = re.search(r"(?i)" + motif + r"\s*:?\s*(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}|\d{1,2} [a-zéû]+\.? \d{4})", t)
            if m and _date_fr(m.group(1)):
                return _date_fr(m.group(1))
        return None
    nom = ""
    m = re.search(r"(?im)^\s*(?:valeur|titre|libell[ée]|d[ée]signation|instrument|nom de la valeur)\s*:?\s*([^\n]+)", t)
    if m:
        nom = re.sub(r"(?i)\(?\s*(?:code\s*)?(?:isin\s*:?\s*)?" + isin + r"\s*\)?", "", m.group(1)).strip(" -:")
    if not nom:
        m = re.search(r"(?m)^\s*([^\n:]{3,60}?)\s*[(\[]?\s*(?:ISIN\s*:?\s*)?" + isin, t)
        nom = (m.group(1) if m else "").strip(" -:(")
    nom = re.sub(r"(?i)^(?:code\s*)?isin\s*:?", "", nom).strip()
    r = _rubriques_avis(t)
    haut = t[:3000]
    achat = re.search(r"(?<![A-Za-zà-ÿ])(?:ACHAT|Achat|achat|Acheter|ACHETER|SOUSCRIPTION|Souscription)(?![A-Za-zà-ÿ])", haut)
    vente = re.search(r"(?<![A-Za-zà-ÿ])(?:VENTE|Vente|vente|Vendre|VENDRE|RACHAT|Rachat|CESSION|Cession)(?![A-Za-zà-ÿ])", haut)
    est_div = re.search(r"(?i)(?<![a-zà-ÿ])(dividende|coupon|distribution|acompte sur dividende)(?![a-zà-ÿ])", haut)
    if est_div and not achat and not vente:
        # Date du paiement (pas celle du détachement), net en euros nommé comme tel
        date = date_de((r"date de paiement", r"pay[ée] le", r"cr[ée]dit[ée] le", r"date de r[èe]glement",
                        r"date de valeur", r"date d'op[ée]ration"))
        m = re.search(r"(?i)(?:montant net|net [àa] cr[ée]diter|net cr[ée]dit[ée]|montant cr[ée]dit[ée])[^\S\n]*"
                      r"(?:\([^)]{0,40}\))?[^\S\n]*:?\s*(" + _NUM + r")\s*(EUR|€|[A-Z]{3})?", t)
        net = _n(m.group(1)) if m and (m.group(2) or "EUR") in ("EUR", "€") else None
        brut = r.get("brut")
        if not date or not net or net <= 0 or (brut and net > brut + 0.01):
            return False
        lot.ajoute("Dividende", date, isin, nom, abs(r.get("qty") or 0), montant=net,
                   alerte="lu par le lecteur universel : vérifie les chiffres")
        return True
    # Date de l'exécution de l'ordre (pas celle du règlement, deux jours après)
    date = date_de((r"date d'ex[ée]cution", r"ex[ée]cut[ée]e? le", r"ex[ée]cution", r"date de n[ée]gociation",
                    r"date de l'op[ée]ration", r"date d'op[ée]ration", r"date de l'ordre", r"\ble",
                    r"date(?! de (?:r[èe]glement|valeur|livraison|paiement))"))
    if not date:
        return False
    if bool(achat) == bool(vente):
        m = re.search(r"(?i)(?:sens|nature|type d'op[ée]ration|op[ée]ration)\s*:?\s*(achat|vente|souscription|rachat)", t)
        if not m:
            return False
        est_vente = m.group(1).lower() in ("vente", "rachat")
    else:
        est_vente = bool(vente)
    qty, cours, brut, net = r.get("qty"), r.get("cours"), r.get("brut"), r.get("net")
    frais, taxe = abs(r.get("frais") or 0), abs(r.get("taxe") or 0)
    if not qty:
        return False
    qty = abs(qty)
    cours = abs(cours) if cours else None
    if brut is None and cours:
        brut = round(qty * cours, 2)
    if not brut:
        return False
    brut = abs(brut)
    if cours and abs(qty * cours - brut) > max(0.02, 0.005 * brut):
        return False
    if net:
        attendu = brut + frais + taxe if not est_vente else brut - frais - taxe
        if abs(abs(net) - attendu) > 0.02:
            # Frais lus de travers ou absents : le net les donne
            ecart = abs(net) - brut - taxe if not est_vente else brut - abs(net) - taxe
            # (pas si l'avis parle d'une taxe qui n'a pas ete lue : elle serait
            # comptee dans les frais)
            if 0 <= ecart <= max(50.0, 0.05 * brut) and (taxe or not re.search(
                    r"(?i)taxe\s+sur\s+les\s+transactions|T\.?T\.?F", t)):
                frais = round(ecart, 2)
            else:
                return False
    heure = re.search(r"(?i)(?:heure d'ex[ée]cution|heure)\s*:?\s*(\d{1,2}[:h]\d{2}(?::\d{2})?)", t)
    lot.ajoute("Vente" if est_vente else "Achat", date, isin, nom, qty, cours, brut, frais, taxe,
               quand=date + ("T" + heure.group(1).replace("h", ":") if heure else ""),
               alerte="lu par le lecteur universel : vérifie les chiffres")
    return True


_LECTEURS_PDF = [("Fortuneo", _fortuneo, r"Fortuneo|Arkéa Direct Bank|ARKEA"),
                 # Le nom de la banque est au pied de page ; la forme de l'avis suffit aussi
                 ("BoursoBank", _boursobank, r"Boursorama|BoursoBank|boursobank|OPERATION (?:DE BOURSE|SUR OPC)[\s\S]*Code ISIN :|COUPONS REMBOURSEMENTS"),
                 ("Bourse Direct", _boursedirect, r"Bourse Direct"),
                 ("Saxo", _saxo, r"Saxo Bank"),
                 ("Degiro", _degiro_pdf, r"DEGIRO|flatex"),
                 ("Trade Republic", _traderepublic, r"TRADE REPUBLIC|Trade Republic")]


def lire_pdf(data: bytes, nom: str = "") -> dict:
    """Lu deux fois si besoin : texte dans l'ordre du document, puis texte
    replace d'apres la position des mots (`layout`) quand le premier ne donne
    rien. Certaines banques ecrivent tous les libelles d'un tableau, puis
    toutes les valeurs : « Quantité » et « 10 » ne sont alors plus cote a cote
    dans le premier texte, mais le sont dans le second."""
    t = texte_pdf(data)
    if not t.strip():
        return {"ok": False, "erreur": "aucun texte dans ce PDF (document scanné ou photo) : "
                                       "Pilote ne lit que les PDF téléchargés depuis l'espace client"}
    r = lire_texte_pdf(t)
    if r.get("ok") and r.get("operations"):
        return r
    try:
        r2 = lire_texte_pdf(texte_pdf(data, "layout"))
    except Exception:
        return r
    if r2.get("ok") and (r2.get("operations") or not r.get("ok")):
        return r2
    return r


def lire_texte_pdf(t: str) -> dict:
    """Le texte d'un PDF (séparé pour les essais sur les exemples)."""
    t = _norm_texte(t)
    for banque, lecteur, signe in _LECTEURS_PDF:
        if re.search(signe, t):
            lot = _Lot(banque)
            lot.inconnues = []
            if lecteur(t, lot):
                return {"ok": True, "banque": banque, "operations": lot.ops, "inconnues": lot.inconnues}
    # Aucune banque connue : un avis d'opéré ordinaire, lu s'il tient debout
    lot = _Lot("Autre banque")
    lot.inconnues = []
    if _avis_generique(t, lot) and lot.ops:
        return {"ok": True, "banque": "Autre banque", "operations": lot.ops, "inconnues": lot.inconnues}
    # Documents qui ne sont pas des opérations : dire lesquels plutôt que « non reconnu »
    if re.search(r"SYNTHÈSE DU RELEVÉ DE COMPTE", t) and re.search(r"(?i)trade republic", t):
        return {"ok": False, "erreur": "relevé de compte Trade Republic : il ne donne ni le cours ni les frais "
                                       "de chaque ordre. Importe plutôt l'export CSV (Profil → Relevés → "
                                       "Export des transactions)"}
    if re.search(r"(?i)imprim[ée] fiscal unique|\bIFU\b", t):
        return {"ok": False, "erreur": "imprimé fiscal unique (IFU) : il résume l'année pour les impôts, "
                                       "sans les opérations. Importe les avis d'opéré ou l'historique des opérations"}
    if len(set(re.findall(r"\b(" + _ISIN + r")\b", t))) > 1 and \
            re.search(r"(?i)relev[ée] de portefeuille|[ée]valuation (?:de|du) portefeuille|relev[ée] de titres|"
                      r"inventaire|valorisation", t) and not re.search(r"(?i)\bachat\b|\bvente\b", t):
        return {"ok": False, "erreur": "relevé de portefeuille (positions à une date) : Pilote importe les "
                                       "opérations, pas les positions. Importe les avis d'opéré ou l'historique"}
    return {"ok": False, "erreur": "document non reconnu (banque ou type d'avis que Pilote ne sait pas lire)"}


# ─── Tableaux : CSV, Excel, XML ──────────────────────────────────────────────

def _lignes_csv(texte: str) -> list:
    """Lignes d'un CSV. Le separateur est celui qui decoupe le mieux les 30
    premieres lignes en un meme nombre de colonnes : la premiere ligne seule
    ne suffit pas (titre « Relevé du compte n° … » avant l'en-tete)."""
    debut = [l for l in texte.splitlines()[:30] if l.strip()]

    def score(sep):
        try:
            lignes = list(csv.reader(io.StringIO("\n".join(debut)), delimiter=sep))
        except csv.Error:
            return 0
        nb = [len(r) for r in lignes if len(r) > 1]
        if not nb:
            return 0
        frequent = max(set(nb), key=nb.count)
        return nb.count(frequent) * frequent
    sep = max([";", ",", "\t", "|"], key=score)
    return [r for r in csv.reader(io.StringIO(texte), delimiter=sep) if any(c.strip() for c in r)]


def _lignes_html(texte: str) -> list:
    """Tableau d'une page HTML : beaucoup de banques livrent sous le nom
    « .xls » une page web contenant un tableau."""
    from html.parser import HTMLParser

    class Lecteur(HTMLParser):
        def __init__(self):
            super().__init__()
            self.lignes, self.ligne, self.cell = [], None, None

        def handle_starttag(self, tag, attrs):
            if tag == "tr":
                self.ligne = []
            elif tag in ("td", "th") and self.ligne is not None:
                self.cell = []
            elif tag == "br" and self.cell is not None:
                self.cell.append(" ")

        def handle_endtag(self, tag):
            if tag in ("td", "th") and self.cell is not None and self.ligne is not None:
                self.ligne.append(" ".join("".join(self.cell).split()))
                self.cell = None
            elif tag == "tr" and self.ligne is not None:
                if any(c for c in self.ligne):
                    self.lignes.append(self.ligne)
                self.ligne = None

        def handle_data(self, data):
            if self.cell is not None:
                self.cell.append(data)
    lec = Lecteur()
    lec.feed(texte)
    return lec.lignes


def _lignes_ods(z) -> list:
    """Premiere feuille d'un classeur LibreOffice (.ods) : content.xml. Les
    dates y sont ecrites en clair (office:date-value), les nombres aussi."""
    O = "{urn:oasis:names:tc:opendocument:xmlns:office:1.0}"
    T = "{urn:oasis:names:tc:opendocument:xmlns:table:1.0}"
    racine = ET.fromstring(z.read("content.xml"))
    feuille = next(racine.iter(T + "table"), None)
    lignes = []
    if feuille is None:
        return lignes
    for row in feuille.iter(T + "table-row"):
        cells = []
        for c in row:
            if c.tag not in (T + "table-cell", T + "covered-table-cell"):
                continue
            n = min(int(c.get(T + "number-columns-repeated", "1") or 1), 200)
            typ = c.get(O + "value-type")
            if typ == "date":
                val = (c.get(O + "date-value") or "")[:19]
            elif typ in ("float", "currency", "percentage"):
                val = c.get(O + "value") or ""
            else:
                val = " ".join("".join(p.itertext()) for p in c if p.tag.endswith("}p"))
            cells += [val] * n
        while cells and not cells[-1]:
            cells.pop()
        if cells:
            lignes.append(cells)
        if len(lignes) > 100000:
            break
    return lignes


def _xml_local(el, nom):
    """Elements `nom` sous `el`, quel que soit l'espace de noms (le format
    « strict » d'Excel n'a pas le meme que le format courant)."""
    return [x for x in el.iter() if x.tag.rsplit("}", 1)[-1] == nom]


# Formats de nombre d'Excel qui sont des dates (identifiants predefinis)
_XLSX_DATES = set(range(14, 23)) | set(range(27, 37)) | set(range(45, 48)) | set(range(50, 59))


def _lignes_xlsx(data: bytes) -> list:
    """Première feuille d'un .xlsx, sans bibliothèque : texte partagé + cellules.

    Une date est rangee par Excel en nombre de jours depuis 1900 (« 45377 ») :
    les cellules au format date sont rendues en AAAA-MM-JJ (styles.xml),
    sinon aucune ligne n'avait de date et rien n'etait lu."""
    z = zipfile.ZipFile(io.BytesIO(data))
    noms = z.namelist()
    partages = []
    if "xl/sharedStrings.xml" in noms:
        for si in _xml_local(ET.fromstring(z.read("xl/sharedStrings.xml")), "si"):
            partages.append("".join(x.text or "" for x in _xml_local(si, "t")))
    # Styles « date » : formats predefinis ou personnalises contenant j/m/a
    dates_styles, base1904 = set(), False
    try:
        st = ET.fromstring(z.read("xl/styles.xml"))
        perso = {f.get("numFmtId"): f.get("formatCode", "") for f in _xml_local(st, "numFmt")}
        xfs = _xml_local(st, "cellXfs")
        for i, xf in enumerate(_xml_local(xfs[0], "xf") if xfs else []):
            fid = int(xf.get("numFmtId", "0") or 0)
            code = re.sub(r'"[^"]*"|\[[^\]]*\]', "", perso.get(str(fid), "")).lower()
            if fid in _XLSX_DATES or (str(fid) in perso and re.search(r"[dy]|mm?[-/.]", code)):
                dates_styles.add(i)
    except Exception:
        pass
    try:
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        base1904 = any(x.get("date1904") in ("1", "true") for x in _xml_local(wb, "workbookPr"))
    except Exception:
        wb = None
    # Premiere feuille du classeur (ordre du classeur, pas du nom de fichier)
    feuille = None
    try:
        rid = _xml_local(wb, "sheet")[0].get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
        for rel in _xml_local(ET.fromstring(z.read("xl/_rels/workbook.xml.rels")), "Relationship"):
            if rel.get("Id") == rid:
                cible = rel.get("Target", "").lstrip("/")
                feuille = cible if cible.startswith("xl/") else "xl/" + cible
    except Exception:
        feuille = None
    if feuille not in noms:
        feuilles = sorted((n for n in noms if n.lower().startswith("xl/worksheets/") and n.lower().endswith(".xml")),
                          key=lambda n: (len(n), n.lower()))
        if not feuilles:
            raise ValueError("classeur Excel sans feuille lisible")
        feuille = feuilles[0]
    origine = datetime.date(1904, 1, 1) if base1904 else datetime.date(1899, 12, 30)
    lignes = []
    for row in _xml_local(ET.fromstring(z.read(feuille)), "row"):
        cells = {}
        for n, c in enumerate(_xml_local(row, "c")):
            ref = re.match(r"([A-Z]+)", c.get("r", "") or "")
            if ref:
                col = 0
                for ch in ref.group(1):
                    col = col * 26 + ord(ch) - 64
                col -= 1
            else:
                col = max(cells) + 1 if cells else 0
            v = _xml_local(c, "v")
            val = v[0].text if v else "".join(x.text or "" for x in _xml_local(c, "t"))
            if c.get("t") == "s" and val is not None:
                val = partages[int(val)]
            elif c.get("t") in (None, "n") and val and int(c.get("s", "0") or 0) in dates_styles:
                try:
                    j = float(val)
                    val = (origine + datetime.timedelta(days=int(j))).isoformat()
                    if j % 1:
                        sec = round((j % 1) * 86400)
                        val += "T%02d:%02d:%02d" % (sec // 3600, sec % 3600 // 60, sec % 60)
                except (ValueError, OverflowError):
                    pass
            cells[col] = val or ""
        if cells:
            lignes.append([cells.get(i, "") for i in range(max(cells) + 1)])
    return lignes


def _flux_ole(data: bytes, noms=("Workbook", "Book")) -> bytes:
    """Contenu d'un flux d'un fichier OLE2 (le conteneur des .xls d'Excel 97
    à 2003), sans bibliothèque. None si absent."""
    import struct
    if data[:8] != b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        return None
    taille = 1 << struct.unpack_from("<H", data, 0x1E)[0]
    mini = 1 << struct.unpack_from("<H", data, 0x20)[0]
    nb_fat, rep0 = struct.unpack_from("<II", data, 0x2C)
    seuil, minifat0, nb_minifat, difat0, nb_difat = struct.unpack_from("<IIIII", data, 0x38)

    def secteur(n):
        return data[(n + 1) * taille:(n + 2) * taille]
    difat = list(struct.unpack_from("<109I", data, 0x4C))
    n, vus = difat0, 0
    while n < 0xFFFFFFFA and vus < nb_difat:
        s = secteur(n)
        difat += struct.unpack_from("<%dI" % (taille // 4 - 1), s)
        n = struct.unpack_from("<I", s, taille - 4)[0]
        vus += 1
    fat = []
    for f in difat[:nb_fat]:
        if f < 0xFFFFFFFA:
            fat += struct.unpack_from("<%dI" % (taille // 4), secteur(f))

    def chaine(n, table, lire, limite):
        out, vus = [], set()
        while n < 0xFFFFFFFA and n < len(table) and n not in vus and len(out) < limite:
            vus.add(n)
            out.append(lire(n))
            n = table[n]
        return b"".join(out)
    repertoire = chaine(rep0, fat, secteur, 100000)
    entrees = []
    for i in range(0, len(repertoire) - 127, 128):
        e = repertoire[i:i + 128]
        lg = struct.unpack_from("<H", e, 0x40)[0]
        nom = e[:max(0, lg - 2)].decode("utf-16-le", "replace")
        typ = e[0x42]
        debut, longueur = struct.unpack_from("<II", e, 0x74)
        entrees.append((nom, typ, debut, longueur))
    racine = next((x for x in entrees if x[1] == 5), None)
    minifat = []
    if nb_minifat:
        minifat = list(struct.unpack_from("<%dI" % (nb_minifat * taille // 4), chaine(minifat0, fat, secteur, nb_minifat)))
    flux_mini = chaine(racine[2], fat, secteur, 1000000) if racine else b""
    for voulu in noms:
        for nom, typ, debut, longueur in entrees:
            if typ == 2 and nom == voulu:
                if longueur < seuil:
                    brut = chaine(debut, minifat, lambda k: flux_mini[k * mini:(k + 1) * mini], 1000000)
                else:
                    brut = chaine(debut, fat, secteur, 1000000)
                return brut[:longueur]
    return None


def _lignes_xls(data: bytes) -> list:
    """Première feuille d'un classeur Excel 97-2003 (.xls, BIFF8), sans
    bibliothèque : textes partagés (SST), nombres, dates (formats date des
    cellules), résultats de formules. Une banque le donne parfois tel quel."""
    import struct
    flux = _flux_ole(data)
    if not flux:
        raise ValueError("classeur .xls illisible")
    # Enregistrements : (type, contenu), les CONTINUE recollés à leur parent
    recs, i = [], 0
    while i + 4 <= len(flux):
        typ, lg = struct.unpack_from("<HH", flux, i)
        recs.append((typ, flux[i + 4:i + 4 + lg], i))
        i += 4 + lg

    def chaine_u(b, pos, lg_octets=2):
        """XLUnicodeString : longueur, drapeau, caractères -> (texte, fin)."""
        n = struct.unpack_from("<H" if lg_octets == 2 else "<B", b, pos)[0]
        pos += lg_octets
        f = b[pos]
        pos += 1
        if f & 1:
            return b[pos:pos + 2 * n].decode("utf-16-le", "replace"), pos + 2 * n
        return b[pos:pos + n].decode("latin-1"), pos + n
    formats, xfs, base1904, sst, feuilles = {}, [], False, [], []
    for k, (typ, b, debut) in enumerate(recs):
        if typ == 0x041E and len(b) > 4:          # FORMAT
            formats[struct.unpack_from("<H", b, 0)[0]] = chaine_u(b, 2)[0]
        elif typ == 0x00E0 and len(b) >= 4:       # XF
            xfs.append(struct.unpack_from("<H", b, 2)[0])
        elif typ == 0x0022 and len(b) >= 2:       # DATEMODE
            base1904 = struct.unpack_from("<H", b, 0)[0] == 1
        elif typ == 0x0085 and len(b) >= 8:       # BOUNDSHEET
            feuilles.append((struct.unpack_from("<I", b, 0)[0], b[4], b[5]))
        elif typ == 0x00FC:                       # SST (+ CONTINUE)
            morceaux = [b]
            for t2, b2, _ in recs[k + 1:]:
                if t2 != 0x003C:
                    break
                morceaux.append(b2)
            sst = _sst_xls(morceaux)
    dates = set()
    for i, fid in enumerate(xfs):
        code = re.sub(r'"[^"]*"|\[[^\]]*\]', "", formats.get(fid, "")).lower()
        if fid in _XLSX_DATES or (fid in formats and re.search(r"[dy]|mm?[-/.]", code)):
            dates.add(i)
    origine = datetime.date(1904, 1, 1) if base1904 else datetime.date(1899, 12, 30)

    def valeur(nb, xf):
        if xf in dates:
            try:
                d = (origine + datetime.timedelta(days=int(nb))).isoformat()
                if nb % 1:
                    sec = round((nb % 1) * 86400)
                    d += "T%02d:%02d:%02d" % (sec // 3600, sec % 3600 // 60, sec % 60)
                return d
            except (ValueError, OverflowError):
                pass
        return ("%d" % nb) if float(nb).is_integer() and abs(nb) < 1e15 else repr(nb)

    def rk(v):
        """Nombre compressé d'Excel : entier sur 30 bits, ou haut d'un double ;
        divisé par 100 si le bit 0 le dit."""
        if v & 2:
            nb = float(struct.unpack("<i", struct.pack("<I", v & 0xFFFFFFFC))[0] >> 2)
        else:
            nb = struct.unpack("<d", struct.pack("<Q", (v & 0xFFFFFFFC) << 32))[0]
        return nb / 100 if v & 1 else nb
    debut_feuille = next((o for o, vis, sorte in feuilles if sorte == 0 and vis == 0), feuilles[0][0] if feuilles else None)
    cells, dans, attente = {}, debut_feuille is None, None
    for typ, b, debut in recs:
        if not dans:
            dans = debut == debut_feuille
            continue
        if typ == 0x000A:                          # EOF de la feuille
            break
        if typ in (0x00FD, 0x0203, 0x027E, 0x0204, 0x0006) and len(b) >= 6:
            r, c, xf = struct.unpack_from("<HHH", b, 0)
            if typ == 0x00FD and len(b) >= 10:     # LABELSST
                n = struct.unpack_from("<I", b, 6)[0]
                cells[(r, c)] = sst[n] if n < len(sst) else ""
            elif typ == 0x0203 and len(b) >= 14:   # NUMBER
                cells[(r, c)] = valeur(struct.unpack_from("<d", b, 6)[0], xf)
            elif typ == 0x027E and len(b) >= 10:   # RK
                cells[(r, c)] = valeur(rk(struct.unpack_from("<I", b, 6)[0]), xf)
            elif typ == 0x0204:                    # LABEL
                cells[(r, c)] = chaine_u(b, 6)[0]
            elif typ == 0x0006 and len(b) >= 14:   # FORMULA : résultat gardé
                if b[12:14] == b"\xff\xff":
                    attente = (r, c) if b[6] == 0 else None
                else:
                    cells[(r, c)] = valeur(struct.unpack_from("<d", b, 6)[0], xf)
        elif typ == 0x00BD and len(b) >= 6:        # MULRK
            r, c0 = struct.unpack_from("<HH", b, 0)
            for j in range((len(b) - 6) // 6):
                xf, v = struct.unpack_from("<HI", b, 4 + 6 * j)
                cells[(r, c0 + j)] = valeur(rk(v), xf)
        elif typ == 0x0207 and attente:            # STRING (résultat texte d'une formule)
            cells[attente] = chaine_u(b, 0)[0]
            attente = None
    if not cells:
        return []
    nb_lignes = max(r for r, _ in cells) + 1
    lignes = []
    for r in range(min(nb_lignes, 100000)):
        cols = [c for (rr, c) in cells if rr == r]
        if cols:
            lignes.append([cells.get((r, c), "") for c in range(max(cols) + 1)])
    return lignes


def _sst_xls(morceaux: list) -> list:
    """Table des textes partagés d'un .xls (SST), y compris les textes coupés
    entre deux enregistrements CONTINUE (chaque suite recommence par un octet
    disant si les caractères sont sur un ou deux octets)."""
    import struct
    out = []
    if not morceaux or len(morceaux[0]) < 8:
        return out
    uniques = struct.unpack_from("<I", morceaux[0], 4)[0]
    m, pos = 0, 8

    def octets(n):
        nonlocal m, pos
        res = b""
        while n > 0 and m < len(morceaux):
            dispo = len(morceaux[m]) - pos
            if dispo <= 0:
                m, pos = m + 1, 0
                continue
            pris = min(n, dispo)
            res += morceaux[m][pos:pos + pris]
            pos += pris
            n -= pris
        return res
    for _ in range(uniques):
        if m >= len(morceaux) or (m == len(morceaux) - 1 and pos >= len(morceaux[m])):
            break
        if pos >= len(morceaux[m]):
            m, pos = m + 1, 0
        tete = octets(3)
        if len(tete) < 3:
            break
        cch, f = struct.unpack("<HB", tete)
        runs = struct.unpack("<H", octets(2))[0] if f & 8 else 0
        ext = struct.unpack("<I", octets(4))[0] if f & 4 else 0
        texte, reste, large = "", cch, f & 1
        while reste > 0 and m < len(morceaux):
            dispo = len(morceaux[m]) - pos
            if dispo <= 0:
                # Suite dans le CONTINUE suivant : nouvel octet d'options
                m, pos = m + 1, 0
                if m >= len(morceaux):
                    break
                large = morceaux[m][0] & 1
                pos = 1
                continue
            n = min(reste, dispo // 2 if large else dispo)
            if n == 0:
                m, pos = m + 1, 0
                continue
            b = morceaux[m][pos:pos + n * (2 if large else 1)]
            texte += b.decode("utf-16-le", "replace") if large else b.decode("latin-1")
            pos += len(b)
            reste -= n
        octets(4 * runs + ext)
        out.append(texte)
    return out


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", _sans_accents(s or "").lower().strip())


def _col(entetes: list, *noms) -> int:
    """Indice de la première colonne dont l'en-tête vaut l'un des noms (normalisés)."""
    for nm in noms:
        if nm in entetes:
            return entetes.index(nm)
    return -1


def _sens(texte: str) -> str:
    t = _norm(texte)
    if re.search(r"\b(achat|buy|kauf|koop|acquisition|souscription|bot|purchase)\b", t):
        return "Achat"
    if re.search(r"\b(vente|sell|verkauf|verkoop|cession|rachat|reprise|sld|sale)\b", t):
        return "Vente"
    if re.search(r"(dividend|coupon|distribution|ausschuttung)", t) and not re.search(r"(impot|tax|belasting|steuer|withholding)", t):
        return "Dividende"
    if re.search(r"\b(versement|depot|deposit|einzahlung|einlage|apport)\b", t):
        return "Versement"
    if re.search(r"\b(retrait|withdrawal|auszahlung)\b", t):
        return "Retrait"
    return ""


def _ibkr(entetes, lignes, lot):
    c = {k: entetes.index(k) for k in entetes}
    g = lambda r, k: r[c[k]] if k in c and c[k] < len(r) else ""
    for r in lignes:
        date = _date_fr(g(r, "tradedate") or g(r, "settledate") or g(r, "date/time"))
        dev = (g(r, "currencyprimary") or g(r, "currency") or "EUR").upper()
        # Pas de fxRateToBase ici : le CSV ne dit pas si le compte est en euros
        fx = None
        conv = lambda x: _vers_eur(x, dev, date)
        if "buy/sell" in c:
            qty = abs(_n(g(r, "quantity")) or 0)
            brut = conv(abs(_n(g(r, "trademoney")) or (qty * (_n(g(r, "tradeprice")) or 0))))
            fdev = (g(r, "ibcommissioncurrency") or dev).upper()
            frais = abs(_n(g(r, "ibcommission")) or 0)
            frais = (frais * fx if fx and fdev != "EUR" else _vers_eur(frais, fdev, date)) or 0
            if brut is None:
                lot.inconnues.append({"type": "devise " + dev, "categorie": "IBKR", "nom": g(r, "isin"), "date": date})
                continue
            lot.ajoute("Achat" if g(r, "buy/sell").upper().startswith("B") else "Vente", date, g(r, "isin"),
                       g(r, "description") or g(r, "symbol") or g(r, "isin"), qty, None, brut, frais,
                       ref="ib:" + g(r, "tradeid") if g(r, "tradeid") else "")
        elif "type" in c and "amount" in c:
            typ = g(r, "type").lower()
            if typ.startswith("dividend") or typ.startswith("withholding") or typ.startswith("payment in lieu"):
                mt = conv(_n(g(r, "amount")) or 0)
                op = lot.ajoute("Dividende", date, g(r, "isin"), g(r, "description")[:40], montant=0) \
                    if mt is not None else None
                if op:
                    op["_brut"] = mt
            elif typ.startswith("deposit"):
                mt = conv(_n(g(r, "amount")) or 0)
                if mt:
                    lot.ajoute("Versement" if mt > 0 else "Retrait", date, montant=mt, origine="especes")
    # Dividende et retenue à la source du même titre et du même jour : un seul
    # dividende, net (comme le montant crédité)
    divs = {}
    for o in [o for o in lot.ops if o["type"] == "Dividende" and "_brut" in o]:
        cle = (o["isin"], o["date"])
        if cle in divs:
            divs[cle]["_brut"] += o.pop("_brut")
            lot.ops.remove(o)
        else:
            divs[cle] = o
    for o in divs.values():
        o["montant"] = round(o.pop("_brut"), 2)
        if o["montant"] <= 0:
            lot.ops.remove(o)


def _ibkr_xml(data: bytes, lot: _Lot):
    racine = ET.fromstring(data)
    # fxRateToBase convertit vers la devise du COMPTE : utile seulement si
    # c'est l'euro (exemple réel en dollars canadiens vers une autre devise)
    info = next(racine.iter("AccountInformation"), None)
    base_eur = info is not None and info.get("currency") == "EUR"
    for tr in racine.iter("Trade"):
        a = tr.attrib
        if a.get("assetCategory", "STK") not in ("STK", "FUND", "ETF") or a.get("levelOfDetail", "EXECUTION") not in ("EXECUTION", ""):
            continue
        date = _date_fr(a.get("tradeDate") or a.get("dateTime", "")[:8])
        fx = _n(a.get("fxRateToBase")) if base_eur else None
        dev = a.get("currency", "EUR")
        qty = abs(_n(a.get("quantity")) or 0)
        brut = abs(_n(a.get("tradeMoney")) or qty * (_n(a.get("tradePrice")) or 0))
        brut = brut * fx if fx and dev != "EUR" else _vers_eur(brut, dev, date)
        frais = abs(_n(a.get("ibCommission")) or 0)
        fdev = a.get("ibCommissionCurrency", dev)
        frais = frais * fx if fx and fdev != "EUR" else (_vers_eur(frais, fdev, date) or 0)
        if brut is None or not qty:
            continue
        lot.ajoute("Achat" if (a.get("buySell", "") or "").upper().startswith("B") else "Vente", date,
                   a.get("isin", ""), a.get("description") or a.get("symbol", ""), qty, None, brut, frais,
                   ref="ib:" + a.get("tradeID", "") if a.get("tradeID") else "")
    divs = {}
    for ct in racine.iter("CashTransaction"):
        a = ct.attrib
        typ = (a.get("type") or "").lower()
        date = _date_fr((a.get("dateTime") or a.get("settleDate") or "")[:10].replace(";", ""))
        dev = a.get("currency", "EUR")
        fx = _n(a.get("fxRateToBase")) if base_eur else None
        mt = _n(a.get("amount")) or 0
        mt = mt * fx if fx and dev != "EUR" else _vers_eur(mt, dev, date)
        if mt is None:
            continue
        if "dividend" in typ or "withholding" in typ or "lieu" in typ:
            cle = (a.get("isin", ""), date)
            divs.setdefault(cle, [0.0, a.get("description", "")])[0] += mt
        elif "deposit" in typ:
            lot.ajoute("Versement" if mt > 0 else "Retrait", date, montant=mt, origine="especes")
    for (isin, date), (mt, desc) in divs.items():
        if mt > 0 and isin:
            lot.ajoute("Dividende", date, isin, desc[:40], montant=mt)


def _trading212(entetes, lignes, lot):
    c = {k: i for i, k in enumerate(entetes)}
    g = lambda r, k: r[c[k]] if k in c and c[k] < len(r) else ""
    for r in lignes:
        act, date = g(r, "action").lower(), _date_fr(g(r, "time"))
        tot = _n(g(r, "total"))
        dev_tot = (g(r, "currency (total)") or "EUR").upper()
        tot = _vers_eur(tot, dev_tot, date) if tot is not None else None
        frais = sum(abs(_n(r[i]) or 0) for k, i in c.items()
                    if (k.endswith("fee") or k in ("stamp duty", "stamp duty reserve tax", "french transaction tax",
                                                    "finra fee", "transaction fee")) and i < len(r))
        taxe = abs(_n(g(r, "french transaction tax")) or 0)
        if "buy" in act or "sell" in act:
            if tot is None:
                continue
            achat = "buy" in act
            brut = tot - frais if achat else tot + frais
            lot.ajoute("Achat" if achat else "Vente", date, g(r, "isin"), g(r, "name"), _n(g(r, "no. of shares")),
                       None, brut, frais - taxe, taxe, quand=g(r, "time")[:19].replace(" ", "T"),
                       ref="t2:" + g(r, "id") if g(r, "id") else "")
        elif "dividend" in act and tot:
            lot.ajoute("Dividende", date, g(r, "isin"), g(r, "name"), _n(g(r, "no. of shares")), montant=tot)
        elif act in ("deposit", "withdrawal") and tot:
            lot.ajoute("Versement" if act == "deposit" else "Retrait", date, montant=tot, origine="especes")


def _saxo_csv(entetes, lignes, lot):
    c = {k: i for i, k in enumerate(entetes)}
    g = lambda r, k: r[c[k]] if k in c and c[k] < len(r) else ""
    for r in lignes:
        typ, ev, date = g(r, "type").lower(), g(r, "event"), _date_fr(g(r, "trade date"))
        mt = _n(g(r, "amount"))
        if mt is None:
            continue
        dev = (g(r, "instrument currency") or "EUR").upper()
        if typ == "trade":
            m = re.match(r"(Buy|Sell)\s+([\d.,]+)\s*@\s*([\d.,]+)\s*([A-Z]{3})", ev)
            if not m:
                continue
            taux = _n(g(r, "conversion rate")) or 1
            brut = _vers_eur(abs(mt), dev, date) if dev != "EUR" and taux == 1 else abs(mt)
            if brut is None:
                continue
            lot.ajoute("Achat" if m.group(1) == "Buy" else "Vente", date, g(r, "instrument isin"),
                       g(r, "instrument"), _n(m.group(2)), None, brut, ref="sx:" + g(r, "order id") if g(r, "order id") else "")
        elif "dividend" in ev.lower():
            taux = _n(g(r, "conversion rate"))
            eur = abs(mt) * taux if taux and dev != "EUR" else abs(mt)
            lot.ajoute("Dividende", date, g(r, "instrument isin"), g(r, "instrument"), montant=eur)
        elif typ == "cash amount" and re.search(r"(?i)deposit|withdrawal", ev):
            lot.ajoute("Versement" if mt > 0 else "Retrait", date, montant=mt, origine="especes")


def _fortuneo_csv(entetes, lignes, lot):
    """Historique des opérations de bourse de Fortuneo (CSV dans un .zip,
    12/10/2026) : « libellé;Opération;Place;Date;Qté;Prix d'éx.;Montant brut;
    Courtage/Prélèvement;Montant net;Devise; », en cp1252, décimales au point,
    montants signés. Pas d'ISIN : la cotation se cherche par le nom.
    Ignorés : le transfert de titres depuis une autre banque (0 €, l'achat
    d'origine vient de l'ancienne banque) et le détachement d'un coupon (le
    dividende est sur la ligne « Encaissement coupons », deux jours après)."""
    c = {k: i for i, k in enumerate(entetes)}
    # « Prix d'éxé » dans le vrai fichier : la colonne se repère par son début
    c["prix"] = next((i for i, k in enumerate(entetes) if k.startswith("prix")), -1)
    g = lambda r, k: r[c[k]].strip() if k in c and 0 <= c[k] < len(r) else ""
    for r in lignes:
        op, date, nom = _norm(g(r, "operation")), _date_fr(g(r, "date")), g(r, "libelle")
        qty, prix = _n(g(r, "qte")), _n(g(r, "prix"))
        brut, frais, net = _n(g(r, "montant brut")) or 0, _n(g(r, "courtage/prelevement")) or 0, _n(g(r, "montant net")) or 0
        dev = (g(r, "devise") or "EUR").upper()
        if op.startswith(("achat", "souscription", "vente", "rachat")):
            brut_eur = _vers_eur(abs(brut), dev, date)
            if brut_eur is None or not qty:
                lot.inconnues.append({"type": g(r, "operation"), "categorie": "Fortuneo", "nom": nom, "date": date})
                continue
            lot.ajoute("Achat" if op.startswith(("achat", "souscription")) else "Vente", date, "", nom, abs(qty),
                       prix if dev == "EUR" else None, brut_eur, _vers_eur(abs(frais), dev, date) or 0)
        elif op.startswith("encaissement coupon"):
            lot.ajoute("Dividende", date, "", nom, abs(qty or 0), montant=_vers_eur(abs(net), dev, date) or 0)
        elif "transfert" in op:
            lot.ignores["transferts"] = lot.ignores.get("transferts", 0) + 1
        elif "detachement" in op or op.startswith("ost de creation de coupon"):
            lot.ignores["detachements"] = lot.ignores.get("detachements", 0) + 1
        else:
            lot.inconnues.append({"type": g(r, "operation"), "categorie": "Fortuneo", "nom": nom, "date": date})


def _degiro_compte(entetes, lignes, lot):
    """Relevé de compte Degiro (Account.csv) : dividendes (moins la retenue à
    la source) et versements. Les ordres viennent du rapport des transactions,
    qui donne leur montant en euros."""
    i_date, i_isin, i_desc = 0, _col(entetes, "code isin", "isin"), _col(entetes, "description", "omschrijving", "beschreibung")
    i_prod = _col(entetes, "produit", "product", "produkt")
    i_mvt = _col(entetes, "mouvements", "mutatie", "change", "anderung", "änderung")
    divs = {}
    for r in lignes:
        if max(i_isin, i_desc, i_mvt) >= len(r) or i_mvt < 0:
            continue
        date = _date_fr(r[i_date])
        desc = _norm(r[i_desc])
        dev, mt = (r[i_mvt] or "EUR").upper(), _n(r[i_mvt + 1]) if i_mvt + 1 < len(r) else None
        if mt is None:
            continue
        if re.search(r"dividend", desc):
            cle = (r[i_isin], date, dev)
            divs.setdefault(cle, [0.0, r[i_prod] if i_prod >= 0 else ""])[0] += mt
        elif re.search(r"\b(ideal deposit|versement de fonds|deposit|storting|einzahlung)\b", desc) and "reservation" not in desc:
            eur = _vers_eur(mt, dev, date)
            if eur:
                lot.ajoute("Versement" if eur > 0 else "Retrait", date, montant=eur, origine="especes")
    for (isin, date, dev), (mt, nom) in divs.items():
        eur = _vers_eur(mt, dev, date)
        if eur and eur > 0 and isin:
            lot.ajoute("Dividende", date, isin, nom, montant=eur)


# Lecteur universel : colonnes reconnues par leur nom ──────────────────────────

CHAMPS = ["date", "heure", "sens", "isin", "nom", "qty", "cours", "devise", "montant", "frais", "ref"]
_SYNONYMES = {
    "date": ["date", "datum", "trade date", "date d'execution", "date d'operation", "date operation",
             "date de l'operation", "tradedate", "date execution", "date/time", "date et heure",
             "date de negociation", "date d'ordre", "date de l'ordre", "transaction date", "date de transaction"],
    "heure": ["heure", "time", "tijd", "zeit", "uhrzeit"],
    "sens": ["sens", "type", "type d'operation", "operation", "nature", "buy/sell", "b/s", "action",
             "transaction", "type de transaction", "libelle", "description", "omschrijving"],
    "isin": ["isin", "code isin", "instrument isin", "isin code"],
    "nom": ["produit", "product", "nom", "valeur", "titre", "instrument", "name", "designation",
            "libelle", "nom de la valeur", "description", "libelle valeur", "nom du titre", "support",
            "ticker", "symbol", "symbole", "code valeur", "security", "titre financier"],
    "qty": ["quantite", "quantity", "qty", "nombre", "nb", "aantal", "anzahl", "no. of shares", "parts", "shares",
            "qte", "quantite executee", "nombre de titres", "nombre de parts", "nb titres", "qte executee"],
    "cours": ["cours", "price", "prix", "koers", "kurs", "prix unitaire", "price / share", "tradeprice",
              "cours d'execution", "prix d'execution", "cours execute", "price per share", "prix par action",
              "cours net", "cours brut", "prix moyen", "cours moyen", "prix d'achat", "prix d'exe"],
    "devise": ["devise", "currency", "currencyprimary", "monnaie"],
    "montant": ["montant eur", "value eur", "waarde eur", "total eur", "totaal eur", "montant net", "net",
                "montant", "total", "montant negocie", "amount", "net amount", "valeur eur", "montant brut",
                "total amount", "montant total", "montant de l'operation", "montant operation",
                "montant (eur)", "montant en euros", "montant net (eur)"],
    "frais": ["frais", "frais de courtage", "courtage", "commission", "fees", "fee", "transactiekosten",
              "kosten", "transaction and/or third party fees eur", "frais de courtage et/ou de parties tierces eur",
              "ibcommission", "frais eur", "commissions", "frais de transaction", "frais (eur)", "frais totaux"],
    "ref": ["id ordre", "order id", "reference", "id", "numero d'ordre", "order-id"],
}


def colonnes_auto(entetes: list) -> dict:
    """{champ: indice} pour les colonnes reconnues par leur nom ; une colonne
    ne sert qu'à un champ. « montant » préfère une colonne en euros. Un
    en-tête plus long qu'un nom connu (« Quantité exécutée », « Date de
    valeur ») ne compte qu'en second, et jamais pour un taux de change
    (« Cours de change »)."""
    pris, res = set(), {}
    for champ in CHAMPS:
        for nm in _SYNONYMES[champ]:
            idx = [i for i, e in enumerate(entetes) if i not in pris and (e == nm or (
                champ in ("montant", "frais") and e.startswith(nm + " ") and "local" not in e and "lokale" not in e))]
            if idx:
                res[champ] = idx[0]
                pris.add(idx[0])
                break
    for champ in ("date", "qty", "cours", "isin", "devise"):
        if champ in res:
            continue
        for nm in _SYNONYMES[champ]:
            idx = [i for i, e in enumerate(entetes) if i not in pris and e.startswith(nm + " ")
                   and not re.search(r"change|fx|taux|rate|valeur$", e)]
            if idx:
                res[champ] = idx[0]
                pris.add(idx[0])
                break
    return res


# Noms de colonnes qui font reconnaitre la ligne d'en-tete d'un tableau
_ENTETES_CONNUS = {nm for noms in _SYNONYMES.values() for nm in noms} | {
    "buy/sell", "libelle", "courtage/prelevement", "instrument isin", "event", "no. of shares",
    "settledate", "fx", "mouvements", "mutatie", "change", "solde", "debit", "credit", "qte"}


def _ligne_entetes(lignes: list) -> int:
    """Indice de la ligne d'en-tete : la premiere ne l'est pas toujours (titre,
    numero de compte, periode au-dessus). Celle qui a le plus de noms de
    colonnes connus parmi les 30 premieres, si elle en a au moins deux."""
    meilleur, score = 0, 1
    for i, l in enumerate(lignes[:30]):
        n = sum(1 for c in l if _norm(c) in _ENTETES_CONNUS)
        if n > score:
            meilleur, score = i, n
    return meilleur


def _universel(entetes, lignes, lot, colonnes):
    g = lambda r, k: r[colonnes[k]].strip() if k in colonnes and 0 <= colonnes[k] < len(r) else ""
    ordre = _ordre_dates([g(r, "date") for r in lignes])
    for r in lignes:
        date = _date_fr(g(r, "date"), ordre)
        if not date:
            continue
        qty = _n(g(r, "qty"))
        cours = _n(g(r, "cours"))
        mt = _n(g(r, "montant"))
        frais = abs(_n(g(r, "frais")) or 0)
        sens = _sens(g(r, "sens")) if "sens" in colonnes else ""
        if not sens and qty:
            sens = "Achat" if qty > 0 else "Vente"   # Degiro : quantité négative = vente
        if not sens:
            continue
        # Devise du cours : colonne « devise », ou la colonne sans nom qui suit le cours (Degiro)
        dev = g(r, "devise").upper()
        if not dev and "cours" in colonnes and colonnes["cours"] + 1 < len(r) and re.fullmatch(r"[A-Z]{3}", r[colonnes["cours"] + 1].strip()):
            dev = r[colonnes["cours"] + 1].strip()
        dev = dev if re.fullmatch(r"[A-Z]{3}", dev or "") else "EUR"
        heure = g(r, "heure")
        quand = date + ("T" + heure if re.fullmatch(r"\d{2}:\d{2}(:\d{2})?", heure) else "")
        ref = g(r, "ref")
        if sens in ("Achat", "Vente"):
            qty = abs(qty or 0)
            if not qty:
                continue
            brut = qty * cours if cours else (abs(mt) if mt else None)
            if dev != "EUR":
                # Montant en euros du relevé s'il en a un (« Value EUR », ou « Montant »
                # suivi d'une colonne « EUR » chez Degiro), sinon cours du jour
                im = colonnes.get("montant")
                en_eur = im is not None and (_norm(entetes[im]).endswith("eur")
                                             or (im + 1 < len(r) and r[im + 1].strip().upper() == "EUR"))
                brut = abs(mt) if mt and en_eur else _vers_eur(brut, dev, date)
            if not brut:
                continue
            # Cours du fichier tel quel (au millieme) quand il est en euros
            lot.ajoute(sens, date, g(r, "isin").upper(), g(r, "nom"), qty, cours if dev == "EUR" and cours else None,
                       brut, frais, quand=quand,
                       ref=("u:" + ref) if ref else "", classe=_classe(g(r, "nom")))
        elif sens == "Dividende" and mt:
            lot.ajoute("Dividende", date, g(r, "isin").upper(), g(r, "nom"), abs(qty or 0),
                       montant=_vers_eur(abs(mt), dev, date) or 0)
        elif sens in ("Versement", "Retrait") and mt:
            lot.ajoute(sens, date, montant=_vers_eur(abs(mt), dev, date) or 0, origine="especes")


def _deballer(lignes: list) -> list:
    """Un CSV à virgules ouvert dans Excel en français tient dans UNE colonne
    (« 2025-07-17,BUY,… ») ; réenregistré, chaque ligne devient une seule case
    (CSV, .xlsx). Ces cases sont redécoupées comme le CSV d'origine. Vu sur
    l'export Trade Republic d'Arthur repassé par Excel (14/10/2026)."""
    debut = [l for l in lignes[:20] if any(c.strip() for c in l)]
    if not debut:
        return lignes
    une_case = [l for l in debut if sum(1 for c in l if c.strip()) == 1]
    if len(une_case) < 0.8 * len(debut):
        return lignes
    texte = "\n".join(next(c for c in l if c.strip()) for l in lignes if any(c.strip() for c in l))
    if not any(s in texte[:2000] for s in (",", ";", "\t", "|")):
        return lignes
    relues = _lignes_csv(texte)
    return relues if relues and max(len(l) for l in relues[:20]) > 1 else lignes


def lire_tableau(lignes: list, nom: str = "", colonnes: dict = None) -> dict:
    """Un tableau (lignes de cellules, en-têtes en premier). Renvoie le format
    de lire_texte_pdf, ou {ok: False, besoinColonnes, entetes, apercu, proposition}
    quand les colonnes ne sont pas reconnues."""
    if not lignes:
        return {"ok": False, "erreur": "fichier vide"}
    lignes = _deballer(lignes)
    lignes = lignes[_ligne_entetes(lignes):]
    entetes = [_norm(e) for e in lignes[0]]
    corps = lignes[1:]
    if "transaction_id" in entetes and "asset_class" in entetes:
        # Export Trade Republic passé par un tableur (.xlsx, CSV réenregistré)
        tampon = io.StringIO()
        csv.writer(tampon).writerows(lignes)
        r = cto.lire_csv_tr(tampon.getvalue())
        if r.get("ok"):
            r["banque"] = "Trade Republic"
            for o in r["operations"]:
                o["banque"] = "Trade Republic"
        return r
    if colonnes is None:
        if "buy/sell" in entetes or ("type" in entetes and "settledate" in entetes and "amount" in entetes):
            lot = _Lot("Interactive Brokers")
            lot.inconnues = []
            _ibkr(entetes, corps, lot)
            return {"ok": True, "banque": lot.banque, "operations": lot.ops, "inconnues": lot.inconnues}
        if "action" in entetes and "no. of shares" in entetes:
            lot = _Lot("Trading 212")
            lot.inconnues = []
            _trading212(entetes, corps, lot)
            return {"ok": True, "banque": lot.banque, "operations": lot.ops, "inconnues": lot.inconnues}
        if "libelle" in entetes and "courtage/prelevement" in entetes:
            lot = _Lot("Fortuneo")
            lot.inconnues, lot.ignores = [], {}
            _fortuneo_csv(entetes, corps, lot)
            return {"ok": True, "banque": lot.banque, "operations": lot.ops, "inconnues": lot.inconnues,
                    "ignores": lot.ignores}
        if "instrument isin" in entetes and "event" in entetes:
            lot = _Lot("Saxo")
            lot.inconnues = []
            _saxo_csv(entetes, corps, lot)
            return {"ok": True, "banque": lot.banque, "operations": lot.ops, "inconnues": lot.inconnues}
        if ("fx" in entetes and ("omschrijving" in entetes or "description" in entetes)
                and any(x in entetes for x in ("mutatie", "mouvements", "change", "anderung"))):
            lot = _Lot("Degiro")
            lot.inconnues = []
            _degiro_compte(entetes, corps, lot)
            return {"ok": True, "banque": lot.banque, "operations": lot.ops, "inconnues": lot.inconnues}
        colonnes = colonnes_auto(entetes)
        # En-tête muet : une colonne d'ISIN ou de dates se reconnaît à son contenu
        # (une colonne « Titre » remplie d'ISIN est l'ISIN, pas le nom)
        for champ, motif in (("isin", r"[A-Z]{2}[A-Z0-9]{9}\d"), ("date", r"\d{1,4}[-/.]\d{1,2}[-/.]\d{2,4}.*")):
            if champ not in colonnes:
                for i in range(len(entetes)):
                    vals = [r[i].strip() for r in corps[:10] if i < len(r) and r[i].strip()]
                    libre = i not in colonnes.values() or (champ == "isin" and colonnes.get("nom") == i)
                    if vals and libre and sum(bool(re.fullmatch(motif, v)) for v in vals) >= 0.8 * len(vals):
                        if colonnes.get("nom") == i:
                            del colonnes["nom"]
                        colonnes[champ] = i
                        break
        manque =[c for c in ("date", "qty") if c not in colonnes] + \
                 ([] if "isin" in colonnes or "nom" in colonnes else ["isin ou nom"]) + \
                 ([] if "cours" in colonnes or "montant" in colonnes else ["cours ou montant"])
        if manque:
            return {"ok": False, "besoinColonnes": True, "entetes": lignes[0], "apercu": corps[:5],
                    "proposition": colonnes, "manque": manque,
                    "erreur": "Colonnes à indiquer : " + ", ".join(manque)}
    lot = _Lot("Tableau")
    lot.inconnues = []
    _universel(entetes, corps, lot, {k: int(v) for k, v in colonnes.items() if v is not None and int(v) >= 0})
    return {"ok": True, "banque": "Tableau", "operations": lot.ops, "inconnues": lot.inconnues,
            "colonnes": colonnes, "entetes": lignes[0]}


# ─── Entrée ───────────────────────────────────────────────────────────────────

def _texte(data: bytes) -> str:
    # UTF-16 : « Texte Unicode » d'Excel, avec ou sans marque d'ordre
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        try:
            return data.decode("utf-16")
        except UnicodeDecodeError:
            pass
    debut = data[:2000]
    if len(debut) > 20 and debut.count(b"\x00") > len(debut) // 4:
        for enc in ("utf-16-le", "utf-16-be"):
            try:
                t = data.decode(enc)
                if t[:200].isprintable() or "\n" in t[:2000]:
                    return t
            except UnicodeDecodeError:
                continue
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1", "replace")


def lire_fichier(nom: str, data: bytes, colonnes: dict = None, _niveau: int = 0) -> dict:
    nom_l = (nom or "").lower()
    if not data:
        return {"ok": False, "erreur": "fichier vide"}
    if b"%PDF-" in data[:1024]:
        return lire_pdf(data[data.index(b"%PDF-"):], nom)
    if data[:8] == b"\x89PNG\r\n\x1a\n" or data[:3] == b"\xff\xd8\xff" or data[4:12] in (b"ftypheic", b"ftypmif1") \
            or (data[:4] == b"RIFF" and data[8:12] == b"WEBP"):
        return {"ok": False, "erreur": "c'est une image : Pilote lit les relevés en PDF, CSV ou Excel "
                                       "téléchargés depuis l'espace client"}
    if data[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        # Excel 97-2003 (.xls)
        try:
            lignes = _lignes_xls(data)
        except Exception:
            lignes = None
        if lignes:
            return lire_tableau(lignes, nom, colonnes)
        return {"ok": False, "erreur": "fichier Excel à l'ancien format (.xls) illisible : ouvre-le dans Excel ou "
                                       "LibreOffice et enregistre-le en .xlsx ou en .csv, puis importe ce fichier"}
    if data[:2] == b"PK":
        try:
            z = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile:
            return {"ok": False, "erreur": "archive .zip abîmée ou incomplète (téléchargement interrompu ?)"}
        if any(n.startswith("xl/") for n in z.namelist()):   # un .xlsx est un zip
            return lire_tableau(_lignes_xlsx(data), nom, colonnes)
        if "content.xml" in z.namelist() and b"spreadsheet" in (z.read("mimetype") if "mimetype" in z.namelist() else b""):
            return lire_tableau(_lignes_ods(z), nom, colonnes)   # classeur LibreOffice (.ods)
        if any(n.startswith("Index/") and n.endswith(".iwa") for n in z.namelist()):
            return {"ok": False, "erreur": "fichier Numbers (Mac) : dans Numbers, Fichier → Exporter vers → "
                                           "CSV ou Excel, puis importe ce fichier"}
        # Archive (Fortuneo livre son CSV dans un .zip) : chaque fichier lu
        # comme s'il avait été choisi seul, résultats réunis
        res = {"ok": False, "operations": [], "inconnues": [], "ignores": {},
               "erreur": "aucun relevé dans cette archive (PDF, CSV, Excel ou XML attendu)"}
        for info in z.infolist():
            membre = info.filename
            # 20 Mo au plus par fichier : un relevé n'en fait que quelques Ko
            base = membre.rsplit("/", 1)[-1]
            if membre.endswith("/") or info.file_size > 20_000_000 or membre.startswith("__MACOSX/") \
                    or base.startswith(".") \
                    or not membre.lower().endswith((".csv", ".pdf", ".xlsx", ".xml", ".txt", ".tsv", ".xls", ".ods",
                                                    ".htm", ".html", ".zip")) \
                    or (membre.lower().endswith(".zip") and _niveau >= 2):
                continue
            try:
                contenu = z.read(membre)
            except RuntimeError:      # archive chiffree
                return {"ok": False, "erreur": "archive protégée par un mot de passe : extrais-en les fichiers, puis importe-les"}
            r = lire_fichier(membre, contenu, colonnes, _niveau + 1)
            if not r.get("ok"):
                if r.get("besoinColonnes"):
                    return r
                res["erreur"] = membre + " : " + r.get("erreur", "")
                continue
            res.update(ok=True, banque=r.get("banque", res.get("banque", "")), erreur="")
            res["operations"] += r.get("operations", [])
            res["inconnues"] += r.get("inconnues", [])
            for k, v in (r.get("ignores") or {}).items():
                res["ignores"][k] = res["ignores"].get(k, 0) + v
        return res
    texte = _texte(data).lstrip("\ufeff")
    if texte.lstrip().startswith("<") and re.search(r"(?i)<table", texte[:200000]) and "FlexQueryResponse" not in texte[:2000]:
        return lire_tableau(_lignes_html(texte), nom, colonnes)
    if texte.lstrip().startswith("<") and "FlexQueryResponse" in texte[:2000]:
        lot = _Lot("Interactive Brokers")
        lot.inconnues = []
        _ibkr_xml(data, lot)
        return {"ok": True, "banque": lot.banque, "operations": lot.ops, "inconnues": lot.inconnues}
    premiere = _norm(texte.splitlines()[0] if texte.strip() else "")
    if "transaction_id" in premiere and "asset_class" in premiere:
        r = cto.lire_csv_tr(texte)
        if r.get("ok"):
            r["banque"] = "Trade Republic"
            for o in r["operations"]:
                o["banque"] = "Trade Republic"
            return r
        # Pas lu tel quel : réenregistré par un tableur ? (lire_tableau, _deballer)
        r2 = lire_tableau(_lignes_csv(texte), nom, colonnes)
        return r2 if r2.get("ok") else r
    if nom_l.endswith((".csv", ".txt", ".tsv", ".xls")) or any(c in texte[:5000] for c in ",;\t|"):
        return lire_tableau(_lignes_csv(texte), nom, colonnes)
    return {"ok": False, "erreur": "format non reconnu (PDF, CSV, Excel ou XML attendu)"}


def lire(fichiers: list) -> dict:
    """fichiers : [{nom, b64, colonnes?}] (le contenu en base64, comme
    l'interface le lit). Renvoie {ok, operations, ignores, inconnues, documents,
    colonnes} : les opérations de tous les fichiers, sans doublon (même
    identifiant), dans l'ordre où elles ont eu lieu ; `documents` dit pour
    chaque fichier la banque reconnue, le nombre d'opérations ou l'erreur."""
    _fx_cache.clear()
    ops, inconnues, docs, vus = [], [], [], set()
    ignores = {"especes": 0, "classe": 0}
    a_choisir = None
    for f in fichiers or []:
        nom = f.get("nom", "")
        try:
            r = lire_fichier(nom, base64.b64decode(f.get("b64", "")), f.get("colonnes"))
        except Exception as e:
            r = {"ok": False, "erreur": "lecture impossible : " + str(e)[:200]}
        if not r.get("ok"):
            docs.append({"nom": nom, "erreur": r.get("erreur", "")})
            if r.get("besoinColonnes") and a_choisir is None:
                a_choisir = dict(r, nom=nom)
            continue
        n = 0
        for o in r.get("operations", []):
            if o["trId"] in vus:
                continue
            vus.add(o["trId"])
            o.setdefault("banque", r.get("banque", ""))
            ops.append(o)
            n += 1
        for k, v in (r.get("ignores") or {}).items():
            ignores[k] = ignores.get(k, 0) + v
        inconnues += r.get("inconnues") or []
        docs.append({"nom": nom, "banque": r.get("banque", ""), "operations": n})
    ops.sort(key=lambda o: (o["date"], o.get("quand") or "", o["trId"]))
    res = {"ok": bool(ops) or a_choisir is None, "operations": ops, "ignores": ignores,
           "inconnues": inconnues, "documents": docs}
    if a_choisir:
        res["aChoisir"] = a_choisir
    return res
