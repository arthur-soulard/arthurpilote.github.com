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
      anglais ou en allemand), Degiro (rapport des transactions).
  CSV / Excel / XML : Trade Republic (cto.lire_csv_tr), Degiro (relevé de
      compte), Interactive Brokers (Flex Query CSV ou XML), Saxo
      (transactions), Trading 212, et tout autre tableau par le lecteur
      « universel » : colonnes reconnues par leur nom, ou choisies par
      l'utilisateur.

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
         "nov": 11, "novembre": 11, "dec": 12, "dez": 12, "decembre": 12}
_ETF = re.compile(r"(?i)\b(etf|ucits|tracker|opcvm|fcp|sicav|opc|fund|index|indice|msci|s&p|stoxx)\b")


def _n(txt):
    """Nombre lu dans un relevé (« 1 234,56 », « +7 », « 10.000,00 ») ; None sinon."""
    if txt is None:
        return None
    # « 16'997.84 » : séparateur des milliers suisse (relevés de Saxo CH)
    return cto._nombre(str(txt).replace("€", "").replace("+", "").replace("'", "").replace("’", "").strip())


def _sans_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s or "") if unicodedata.category(c) != "Mn")


def _date_fr(txt: str) -> str:
    """« 26-03-2024 », « 26/03/2024 », « 2024-03-26 », « 20230522 »,
    « 09-Apr-2025 », « 8 octobre 2021 » -> 2024-03-26 ; sinon ""."""
    t = (txt or "").strip()
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", t)
    if m:
        return "-".join(m.groups())
    m = re.search(r"(\d{2})[-/.](\d{2})[-/.](\d{4})", t)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    m = re.fullmatch(r"(\d{4})(\d{2})(\d{2})", t)
    if m:
        return "-".join(m.groups())
    m = re.search(r"(\d{1,2})[- ]([A-Za-zéûÉÛ]{3,9})\.?[- ](\d{4})", t)
    if m:
        mois = _MOIS.get(_sans_accents(m.group(2)).lower()[:9]) or _MOIS.get(_sans_accents(m.group(2)).lower()[:4]) \
            or _MOIS.get(_sans_accents(m.group(2)).lower()[:3])
        if mois:
            return f"{m.group(3)}-{mois:02d}-{int(m.group(1)):02d}"
    return ""


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

def texte_pdf(data: bytes) -> str:
    from pypdf import PdfReader   # bibliothèque ajoutée en 4.5.0 (requirements.txt)
    lecteur = PdfReader(io.BytesIO(data))
    if lecteur.is_encrypted:
        try:
            lecteur.decrypt("")
        except Exception:
            raise ValueError("PDF protégé par un mot de passe")
    return "\n".join((p.extract_text() or "") for p in lecteur.pages)


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


_LECTEURS_PDF = [("Fortuneo", _fortuneo, r"Fortuneo|Arkéa Direct Bank|ARKEA"),
                 # Le nom de la banque est au pied de page ; la forme de l'avis suffit aussi
                 ("BoursoBank", _boursobank, r"Boursorama|BoursoBank|boursobank|OPERATION (?:DE BOURSE|SUR OPC)[\s\S]*Code ISIN :|COUPONS REMBOURSEMENTS"),
                 ("Bourse Direct", _boursedirect, r"Bourse Direct"),
                 ("Saxo", _saxo, r"Saxo Bank"),
                 ("Degiro", _degiro_pdf, r"DEGIRO|flatex")]


def lire_pdf(data: bytes, nom: str = "") -> dict:
    t = texte_pdf(data)
    if not t.strip():
        return {"ok": False, "erreur": "aucun texte dans ce PDF (document scanné ?)"}
    return lire_texte_pdf(t)


def lire_texte_pdf(t: str) -> dict:
    """Le texte d'un PDF (séparé pour les essais sur les exemples)."""
    for banque, lecteur, signe in _LECTEURS_PDF:
        if re.search(signe, t):
            lot = _Lot(banque)
            lot.inconnues = []
            if lecteur(t, lot):
                return {"ok": True, "banque": banque, "operations": lot.ops, "inconnues": lot.inconnues}
    return {"ok": False, "erreur": "document non reconnu (banque ou type d'avis que Pilote ne sait pas lire)"}


# ─── Tableaux : CSV, Excel, XML ──────────────────────────────────────────────

def _lignes_csv(texte: str) -> list:
    premiere = texte.splitlines()[0] if texte.strip() else ""
    sep = max([",", ";", "\t", "|"], key=premiere.count)
    return [r for r in csv.reader(io.StringIO(texte), delimiter=sep) if any(c.strip() for c in r)]


def _lignes_xlsx(data: bytes) -> list:
    """Première feuille d'un .xlsx, sans bibliothèque : texte partagé + cellules."""
    z = zipfile.ZipFile(io.BytesIO(data))
    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    partages = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).iter(ns + "si"):
            partages.append("".join(x.text or "" for x in si.iter(ns + "t")))
    feuille = sorted(n for n in z.namelist() if n.startswith("xl/worksheets/sheet"))[0]
    lignes = []
    for row in ET.fromstring(z.read(feuille)).iter(ns + "row"):
        cells = {}
        for c in row.iter(ns + "c"):
            ref = re.match(r"([A-Z]+)", c.get("r", "A"))
            col = 0
            for ch in ref.group(1):
                col = col * 26 + ord(ch) - 64
            v = c.find(ns + "v")
            val = v.text if v is not None else "".join(x.text or "" for x in c.iter(ns + "t"))
            if c.get("t") == "s" and val is not None:
                val = partages[int(val)]
            cells[col - 1] = val or ""
        if cells:
            lignes.append([cells.get(i, "") for i in range(max(cells) + 1)])
    return lignes


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
             "date de l'operation", "tradedate", "date execution", "date/time", "date et heure"],
    "heure": ["heure", "time", "tijd", "zeit", "uhrzeit"],
    "sens": ["sens", "type", "type d'operation", "operation", "nature", "buy/sell", "b/s", "action",
             "transaction", "type de transaction", "libelle", "description", "omschrijving"],
    "isin": ["isin", "code isin", "instrument isin", "isin code"],
    "nom": ["produit", "product", "nom", "valeur", "titre", "instrument", "name", "designation",
            "libelle", "nom de la valeur", "description"],
    "qty": ["quantite", "quantity", "qty", "nombre", "nb", "aantal", "anzahl", "no. of shares", "parts", "shares"],
    "cours": ["cours", "price", "prix", "koers", "kurs", "prix unitaire", "price / share", "tradeprice",
              "cours d'execution", "prix d'execution"],
    "devise": ["devise", "currency", "currencyprimary", "monnaie"],
    "montant": ["montant eur", "value eur", "waarde eur", "total eur", "totaal eur", "montant net", "net",
                "montant", "total", "montant negocie", "amount", "net amount", "valeur eur", "montant brut"],
    "frais": ["frais", "frais de courtage", "courtage", "commission", "fees", "fee", "transactiekosten",
              "kosten", "transaction and/or third party fees eur", "frais de courtage et/ou de parties tierces eur",
              "ibcommission", "frais eur"],
    "ref": ["id ordre", "order id", "reference", "id", "numero d'ordre", "order-id"],
}


def colonnes_auto(entetes: list) -> dict:
    """{champ: indice} pour les colonnes reconnues par leur nom ; une colonne
    ne sert qu'à un champ. « montant » préfère une colonne en euros."""
    pris, res = set(), {}
    for champ in CHAMPS:
        for nm in _SYNONYMES[champ]:
            idx = [i for i, e in enumerate(entetes) if i not in pris and (e == nm or (
                champ in ("montant", "frais") and e.startswith(nm + " ") and "local" not in e and "lokale" not in e))]
            if idx:
                res[champ] = idx[0]
                pris.add(idx[0])
                break
    return res


def _universel(entetes, lignes, lot, colonnes):
    g = lambda r, k: r[colonnes[k]].strip() if k in colonnes and 0 <= colonnes[k] < len(r) else ""
    for r in lignes:
        date = _date_fr(g(r, "date"))
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
            lot.ajoute(sens, date, g(r, "isin").upper(), g(r, "nom"), qty, None, brut, frais, quand=quand,
                       ref=("u:" + ref) if ref else "", classe=_classe(g(r, "nom")))
        elif sens == "Dividende" and mt:
            lot.ajoute("Dividende", date, g(r, "isin").upper(), g(r, "nom"), abs(qty or 0),
                       montant=_vers_eur(abs(mt), dev, date) or 0)
        elif sens in ("Versement", "Retrait") and mt:
            lot.ajoute(sens, date, montant=_vers_eur(abs(mt), dev, date) or 0, origine="especes")


def lire_tableau(lignes: list, nom: str = "", colonnes: dict = None) -> dict:
    """Un tableau (lignes de cellules, en-têtes en premier). Renvoie le format
    de lire_texte_pdf, ou {ok: False, besoinColonnes, entetes, apercu, proposition}
    quand les colonnes ne sont pas reconnues."""
    if not lignes:
        return {"ok": False, "erreur": "fichier vide"}
    entetes = [_norm(e) for e in lignes[0]]
    corps = lignes[1:]
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
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1", "replace")


def lire_fichier(nom: str, data: bytes, colonnes: dict = None) -> dict:
    nom_l = (nom or "").lower()
    if data[:5] == b"%PDF-":
        return lire_pdf(data, nom)
    if data[:2] == b"PK":
        z = zipfile.ZipFile(io.BytesIO(data))
        if any(n.startswith("xl/") for n in z.namelist()):   # un .xlsx est un zip
            return lire_tableau(_lignes_xlsx(data), nom, colonnes)
        # Archive (Fortuneo livre son CSV dans un .zip) : chaque fichier lu
        # comme s'il avait été choisi seul, résultats réunis
        res = {"ok": False, "operations": [], "inconnues": [], "ignores": {}, "erreur": "archive vide"}
        for info in z.infolist():
            membre = info.filename
            # 20 Mo au plus par fichier : un relevé n'en fait que quelques Ko
            if membre.endswith("/") or info.file_size > 20_000_000 \
                    or not membre.lower().endswith((".csv", ".pdf", ".xlsx", ".xml", ".txt")):
                continue
            r = lire_fichier(membre, z.read(membre), colonnes)
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
    texte = _texte(data)
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
    if nom_l.endswith((".csv", ".txt", ".tsv")) or "," in premiere or ";" in premiere:
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
