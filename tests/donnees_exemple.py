"""Données d'exemple pour les captures d'écran du test Mac (build-mac.yml,
job « ecrans-mac »).

Tout est FICTIF : le dépôt est public, rien ne vient des données d'un vrai
utilisateur. Les dates sont relatives au jour du test, pour qu'un « prochain
dividende » ou un « versement prévu » le restent quel que soit le jour.

Un utilisateur « Camille » qui a servi chaque module : PEA, un CTO, Mes
comptes, deux prêts (étudiant placé en différé, auto), Sports, Santé,
Patrimoine et un pense-bête, avec toutes les tuiles de l'accueil allumées. Les clés absentes sont complétées par les
valeurs par défaut de chaque module au chargement (jsonstore, storage).

Usage : python3 tests/donnees_exemple.py <dossier Donnees>
"""
import datetime as dt
import json
import os
import sys

AUJ = dt.date.today()


def jour(n):
    """La date d'aujourd'hui + n jours (n négatif : dans le passé)."""
    return (AUJ + dt.timedelta(days=n)).isoformat()


def mois(n, j=1):
    """Le j-ième jour du mois décalé de n mois (borné à la fin du mois)."""
    a, m = AUJ.year, AUJ.month + n
    while m < 1:
        m += 12
        a -= 1
    while m > 12:
        m -= 12
        a += 1
    fin = (dt.date(a + (m == 12), m % 12 + 1, 1) - dt.timedelta(days=1)).day
    return dt.date(a, m, min(j, fin)).isoformat()


def passe(iso):
    return iso <= AUJ.isoformat()


META = {"version": 1, "createdAt": jour(-560), "lastSavedAt": AUJ.isoformat() + "T08:00:00"}


# ── PEA ────────────────────────────────────────────────────────────────────

def pea():
    depots, txs, recus = [], [], []
    depots.append({"id": 1, "date": mois(-18, 4), "amount": 1000, "note": "Ouverture"})
    for n in range(-18, 1):
        if passe(mois(n, 5)):
            depots.append({"id": len(depots) + 1, "date": mois(n, 5), "amount": 250, "note": ""})
        if passe(mois(n, 6)):
            # Un ordre par mois sur le MSCI World, et le S&P 500 tous les trois mois
            txs.append({"date": mois(n, 6), "asset": "EPA:WPEA", "type": "Achat",
                        "cours": round(5.6 + 0.09 * (n + 18), 3), "qty": 25, "frais": 0 if n % 2 else 0.5})
            if n % 3 == 0:
                txs.append({"date": mois(n, 6), "asset": "EPA:ESE", "type": "Achat",
                            "cours": round(25.5 + 0.25 * (n + 18), 3), "qty": 3, "frais": 0.5})
    txs += [
        {"date": mois(-15, 12), "asset": "EPA:TTE", "type": "Achat", "cours": 58.2, "qty": 4, "frais": 1.2},
        {"date": mois(-12, 18), "asset": "EPA:AIR", "type": "Achat", "cours": 161.4, "qty": 1, "frais": 0.8},
        {"date": mois(-6, 18), "asset": "EPA:AIR", "type": "Achat", "cours": 176.9, "qty": 1, "frais": 0.9},
    ]
    txs.sort(key=lambda t: t["date"])
    for i, t in enumerate(txs, 1):
        t["id"] = i
    # TotalEnergies verse un acompte chaque trimestre
    for n in (-12, -9, -6, -3):
        if passe(mois(n, 3)):
            recus.append({"id": len(recus) + 1, "date": mois(n, 3), "ticker": "EPA:TTE", "qty": 4,
                          "ppa": 0.79, "montant": 3.16, "note": ""})
    recus.append({"id": len(recus) + 1, "date": mois(-6, 22), "ticker": "EPA:AIR", "qty": 1,
                  "ppa": 2.0, "montant": 2.0, "note": ""})

    notes = [
        {"id": 1, "texte": "Renouveler la carte d'identité", "date": jour(4), "faite": False},
        {"id": 2, "texte": "Appeler la banque pour le prêt et demander l'échéancier définitif", "date": jour(0), "faite": False},
        {"id": 3, "texte": "Payer la cotisation du club", "date": jour(-2), "faite": False},
        {"id": 4, "texte": "Idée cadeau pour Léa", "date": "", "faite": False},
        {"id": 5, "texte": "Réserver le train des vacances", "date": jour(35), "faite": False},
    ]
    # Les tuiles qui montrent le plus de mise en page d'abord (marchés, listes,
    # barres, sélecteurs) : ce sont elles qu'on veut voir rendues sur Mac
    tuiles = ["pea", "cto-perf:c1", "bourse-perf", "marches", "pense-bete", "pa-repartition", "pa-objectif", "pea-div",
              "sport-annee", "poids", "bourse-totale", "pea-5ans", "pea-plafond", "sport-semaine",
              "fin-solde", "sante-ajout", "sport-ajout", "pret-mensualite", "pea-wish", "pa-an",
              "sport-derniere", "sport-km", "pret-gains", "fin-revenu", "depense", "pea-div-next",
              "pea-versement", "pea-frais", "sante-rappel", "sport", "sport-goal", "sante-goal",
              "patrimoine", "cto:c1", "pea-valeur", "prochain-achat", "pret", "actus", "patri-rappel", "usb"]
    return {
        "_meta": dict(META, app="Suivi PEA", schema="pea_data.v1"),
        "config": {"prenom": "Camille", "banque": "Banque Exemple", "ouverture": mois(-30, 15)},
        "positions": [
            {"id": 1, "ticker": "EPA:WPEA", "name": "iShares MSCI World Swap PEA", "type": "etf",
             "sector": "etf", "cours": 7.2, "dividende": 0, "exdiv": None},
            {"id": 2, "ticker": "EPA:ESE", "name": "BNP Paribas Easy S&P 500", "type": "etf",
             "sector": "etf", "cours": 30.0, "dividende": 0, "exdiv": None},
            {"id": 3, "ticker": "EPA:TTE", "name": "TotalEnergies", "type": "action",
             "sector": "energie", "cours": 57.0, "dividende": 3.2, "exdiv": None},
            {"id": 4, "ticker": "EPA:AIR", "name": "Airbus", "type": "action",
             "sector": "industrie", "cours": 190.0, "dividende": 2.0, "exdiv": None},
        ],
        "transactions": txs,
        "depots": depots,
        "depotsPrevus": [{"id": 1, "date": jour(20), "amount": 250, "note": "Virement du mois"}],
        "divReceived": recus,
        "divFuture": [{"id": 1, "date": jour(12), "ticker": "EPA:TTE", "qty": 4, "ppa": 0.79,
                       "montant": 3.16, "note": ""}],
        "wishlist": [
            {"id": 1, "ticker": "EPA:MC", "name": "LVMH", "stars": 4, "list": "pea", "wtype": "action", "sector": "luxe"},
            {"id": 2, "ticker": "EPA:OR", "name": "L'Oréal", "stars": 3, "list": "pea", "wtype": "action", "sector": "luxe"},
            {"id": 3, "ticker": "EPA:SU", "name": "Schneider Electric", "stars": 4, "list": "pea", "wtype": "action", "sector": "industrie"},
        ],
        "strategies": [],
        "closedPositions": [],
        "_nid": {"pos": 5, "tx": len(txs) + 1, "wish": 4, "dep": len(depots) + 1, "div": len(recus) + 1,
                 "divf": 2, "rule": 1, "depp": 2},
        "ui": {"theme": "light", "windowMaximized": True, "lastTab": "home"},
        "uiPrefs": {
            "premiersPas": True,
            "nouveautesVues": "999.0.0",      # pas de fiche des nouveautés par-dessus l'écran
            "dash": [{"id": t, "on": True} for t in tuiles],
            "dashPeaRange": "MAX",
            "penseBete": notes,
            "dashObjectif": {"montant": 40000, "date": mois(26, 31)},
        },
    }


# ── CTO ────────────────────────────────────────────────────────────────────

def cto():
    txs = []
    for n in range(-8, 1):
        if passe(mois(n, 2)):
            cours = round(96 + 1.3 * (n + 8), 2)
            txs.append({"date": mois(n, 2), "asset": "AMS:IWDA", "type": "Achat", "cours": cours,
                        "qty": round(50 / cours, 6), "frais": 0, "origine": "plan"})
    txs += [{"date": mois(-7, 14), "asset": "ETR:SAP", "type": "Achat", "cours": 228.5, "qty": 2, "frais": 1},
            {"date": mois(-3, 9), "asset": "ETR:SAP", "type": "Achat", "cours": 241.0, "qty": 1, "frais": 1}]
    txs.sort(key=lambda t: t["date"])
    for i, t in enumerate(txs, 1):
        t["id"] = i
    compte = {
        "id": "c1", "nom": "CTO Exemple", "courtier": "trade-republic",
        "tarif": {"paliers": [{"max": None, "fixe": 1, "pct": 0}], "min": 0, "max": 0, "gratuit": 0, "plan": 0},
        "cree": mois(-8, 1),
        "positions": [
            {"id": 1, "ticker": "AMS:IWDA", "name": "iShares Core MSCI World", "type": "etf",
             "sector": "etf", "cours": 105.0, "dividende": 0, "exdiv": None},
            {"id": 2, "ticker": "ETR:SAP", "name": "SAP", "type": "action",
             "sector": "tech", "cours": 235.0, "dividende": 0, "exdiv": None},
        ],
        "transactions": txs, "divReceived": [], "divFuture": [], "wishlist": [],
        "closedPositions": [], "strategies": [], "prefs": {"plans": {}},
        "_nid": {"pos": 3, "tx": len(txs) + 1, "wish": 1, "dep": 1, "div": 1, "divf": 1, "rule": 1},
    }
    return {"_meta": dict(META, schema="cto.v1"), "comptes": [compte], "actif": "", "_nid": {"compte": 2}}


# ── Mes comptes ────────────────────────────────────────────────────────────

def finances():
    # Catégories et sources par défaut du module (complétées au chargement) :
    # 1 Alimentation, 2 Logement, 3 Transports, 5 Loisirs, 11 Salaire
    modeles = [(1, 1, "Courses", 46.80, "expense", 1), (2, 1, "Loyer", 420, "expense", 2),
               (3, 1, "Carburant", 38.50, "expense", 4), (1, 2, "Restaurant", 24.00, "expense", 9),
               (5, 1, "Cinéma", 11.50, "expense", 12), (1, 1, "Courses", 52.30, "expense", 15),
               (11, 1, "Job étudiant", 640, "income", 1), (1, 1, "Courses", 31.90, "expense", 22)]
    txs = []
    for n in (-1, 0):
        for cat, sub, lib, montant, typ, j in modeles:
            d = mois(n, j)
            if passe(d):
                txs.append({"id": len(txs) + 1, "date": d, "amount": montant, "label": lib, "type": typ,
                            "categoryId": cat, "subcategoryId": sub, "sourceId": 1, "note": "",
                            "createdAt": d + "T12:00:00.000Z"})
    return {"_meta": dict(META, schema="finances.v1"), "transactions": txs, "recurrences": [],
            "_nid": {"tx": len(txs) + 1, "cat": 16, "sub": 100, "src": 8, "rec": 1}}


# ── Sports ─────────────────────────────────────────────────────────────────

def sports():
    seances = []
    for k in range(70, -1, -1):
        d = AUJ - dt.timedelta(days=k)
        jsem = d.weekday()
        s = None
        if jsem == 1:
            s = {"sport": "course", "duration": 45, "distance": 8.2, "elevation": 60, "time": "18:30"}
        elif jsem == 3:
            s = {"sport": "muscu", "duration": 55, "distance": 0, "elevation": 0, "time": "19:00"}
        elif jsem == 5:
            s = {"sport": "velo", "duration": 95, "distance": 38, "elevation": 320, "time": "09:30"}
        elif jsem == 6 and k % 14 < 7:
            s = {"sport": "natation", "duration": 40, "distance": 1500, "elevation": 0, "time": "11:00", "lieu": "25"}
        if s:
            seances.append(dict(s, id=len(seances) + 1, date=d.isoformat(), note=""))
    return {"_meta": dict(META, schema="sports.v1"), "sessions": seances, "customSports": [], "routines": [],
            "goals": [{"id": 1, "kind": "event", "title": "Semi-marathon de la ville", "sport": "course",
                       "date": jour(24), "note": "21 km", "status": "active", "createdAt": jour(-60), "doneAt": None}],
            "_nid": {"session": len(seances) + 1, "routine": 1, "goal": 2}}


# ── Santé ──────────────────────────────────────────────────────────────────

def sante():
    # Une pesée tous les 5 jours, la dernière à la fin du mois dernier : la
    # tuile « Pesée du mois » a ainsi quelque chose à rappeler
    fin = dt.date(AUJ.year, AUJ.month, 1) - dt.timedelta(days=1)
    mesures = []
    for i in range(12):
        d = fin - dt.timedelta(days=5 * (11 - i))
        poids = round(74.8 - 0.22 * i, 1)
        mesures.append({"id": "mesure%d" % (i + 1), "date": d.isoformat(), "time": "07:45", "source": "manuel",
                        "note": "", "poids": poids, "imc": round(poids / 1.78 ** 2, 1),
                        "graisse": round(19.6 - 0.13 * i, 1), "masse_musculaire": round(55.0 + 0.05 * i, 1),
                        "eau": round(57.0 + 0.1 * i, 1)})
    return {"_meta": dict(META, schema="sante.v1"), "mesures": mesures,
            "goals": [{"id": "goal1", "status": "active", "createdAt": mesures[0]["date"], "metric": "poids",
                       "target": 71, "start": None, "date": jour(90), "note": ""}],
            "_nid": {"mesure": len(mesures) + 1, "goal": 2}}


# ── Prêt ───────────────────────────────────────────────────────────────────

def pret():
    # Deux prets (schema 7, 4.4.17) : un pret etudiant place, en differe, avec
    # une tranche a venir et ses echeances pointees a la main ; un pret auto a
    # interets, echeances comptees a leur date.
    vide = {"frais": [], "frais_recurrents": [], "frais_rembourses": [], "evenements": [],
            "pea": {"achats": [], "ventes": []}}
    etudiant = dict(vide, id="p1", pret={
        "nom": "Prêt étudiant", "montant": 20000, "taux": 0.9, "periodicite": 1, "type": "amortissable",
        "date_deblocage": mois(-6, 10), "premiere_echeance": mois(-5, 10), "duree_remboursement": 60,
        "differe": "partiel", "differe_mois": 36,
        "assurance": {"mode": "crd", "taux": 0.3, "montant": 0, "incluse": True},
        "frais_dossier": 0, "frais_garantie": 0, "mensualite": 0, "part": 100,
        "placements": True, "remboursements_auto": False})
    etudiant["versements"] = [{"id": "v1", "date": mois(-6, 10), "montant": 10000},
                              {"id": "v2", "date": mois(6, 10), "montant": 10000}]
    # Les echeances du differe passees, pointees, sauf la derniere
    etudiant["remboursements"] = [{"id": "r%d" % k, "date": mois(k, 10), "montant": 10.0, "echeance": mois(k, 10)}
                                  for k in range(-5, -1) if passe(mois(k, 10))]
    etudiant["frais_recurrents"] = [{"id": "f1", "label": "Carte", "montant": 2.5, "date_debut": mois(-6, 1),
                                     "frequence": "mensuelle", "nb_occurrences": 0}]
    etudiant["av"] = {"contrats": [{"id": "av1", "label": "Assurance vie", "frais_versement": 0.5,
                                    "taux_annuels": [{"annee": AUJ.year - 1, "taux": 3.2}],
                                    "depots": [{"id": "d1", "date": mois(-5, 15), "montant": 4000, "note": ""}]}]}
    etudiant["livrets"] = [{"id": "l1", "label": "Livret A", "taux_history": [{"id": "t1", "date": mois(-12), "taux": 2.4}],
                            "mouvements": [{"id": "m1", "date": mois(-6, 12), "type": "depot", "montant": 5000, "note": ""}]}]
    auto = dict(vide, id="p2", pret={
        "nom": "Prêt auto", "montant": 12000, "taux": 4.5, "periodicite": 1, "type": "amortissable",
        "date_deblocage": mois(-11, 5), "premiere_echeance": mois(-10, 5), "duree_remboursement": 48,
        "differe": "", "differe_mois": 0, "assurance": {"mode": "fixe", "taux": 0, "montant": 8, "incluse": False},
        "frais_dossier": 150, "frais_garantie": 0, "mensualite": 281.64, "part": 100,
        "placements": False, "remboursements_auto": True})
    auto.update(versements=[], remboursements=[], av={"contrats": []}, livrets=[],
                evenements=[{"id": "e1", "type": "anticipe", "date": mois(14, 20), "montant": 2000,
                             "mode": "duree", "ira": 0, "note": "Prime"}])
    return {"_meta": dict(META, schema="pret.v1"), "schema": 7, "prets": [etudiant, auto],
            "actif": "p1", "_nid": {"pret": 3}}


# ── Patrimoine ─────────────────────────────────────────────────────────────

def patrimoine():
    comptes = [
        ("cpt_pea", "PEA", "pea", "pea"), ("cpt_pret", "Prêt étudiant", "dette", "pret"),
        ("compte1", "Livret A", "livret", ""), ("compte2", "Assurance vie", "av", ""),
        ("compte3", "Compte courant", "courant", ""), ("compte4", "CTO Exemple", "cto", "cto:c1"),
    ]
    releves = []
    for n in range(-12, 1):
        k = n + 12
        valeurs = {
            "cpt_pea": 1000 + 430 * k, "cpt_pret": 10000 if n >= -6 else 0,   # 1re tranche du pret etudiant
            "compte1": 3000 + 60 * k + (9000 if n >= -6 else 0),
            "compte2": (8000 + 25 * (n + 5)) if n >= -5 else 0, "compte3": 900 + (70 * k) % 400,
            "compte4": (60 + 150 * (n + 8)) if n >= -8 else 0,
        }
        for cid, v in valeurs.items():
            if v:
                releves.append({"id": "releve%d" % (len(releves) + 1), "compteId": cid,
                                "date": mois(n), "montant": float(v)})
    return {"_meta": dict(META, schema="patrimoine.v1"),
            "comptes": [{"id": c, "label": l, "type": t, "auto": a, "icon": "", "color": "",
                         "archived": False, "note": ""} for c, l, t, a in comptes],
            "releves": releves, "_seeded": True, "_nid": {"compte": 5, "releve": len(releves) + 1}}


def ecrire(dossier):
    utilisateur = os.path.join(dossier, "users", "demo")
    os.makedirs(utilisateur, exist_ok=True)
    fichiers = {
        os.path.join(dossier, "users.json"): {"active": "demo", "users": [
            {"slug": "demo", "label": "Camille", "emoji": "", "color": ""}]},
        os.path.join(utilisateur, "pea_data.json"): pea(),
        os.path.join(utilisateur, "cto.json"): cto(),
        os.path.join(utilisateur, "finances.json"): finances(),
        os.path.join(utilisateur, "sports.json"): sports(),
        os.path.join(utilisateur, "sante.json"): sante(),
        os.path.join(utilisateur, "pret.json"): pret(),
        os.path.join(utilisateur, "patrimoine.json"): patrimoine(),
    }
    for chemin, contenu in fichiers.items():
        with open(chemin, "w", encoding="utf-8") as f:
            json.dump(contenu, f, ensure_ascii=False, indent=1)
    print("donnees d'exemple ecrites dans %s (%d fichiers)" % (dossier, len(fichiers)))


if __name__ == "__main__":
    ecrire(sys.argv[1])
