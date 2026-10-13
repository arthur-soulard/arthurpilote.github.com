"""
pret.py — Stockage du module "Pret" : un ou plusieurs prets, chacun a son nom
(un seul pret, "Pret etudiant", jusqu'a la 4.4.16).

Reprend le modele de l'ancienne application standalone Pret_Etudiant.exe
(localStorage cle "pret_v1", schema 6), mais persiste sur disque comme le
reste de Pilote. Le fichier appartient a l'utilisateur actif.

Emplacement : <app_dir>/users/<slug>/pret.json
Backup quotidien : <app_dir>/users/<slug>/backups_pret/pret_YYYY-MM-DD.json

Modele (schema 7, 4.4.17)
------
prets : [{id, pret, versements, remboursements, evenements, frais,
          frais_recurrents, frais_rembourses, pea, av, livrets}]
actif : id du pret affiche en dernier
_nid  : {pret: n} -> le prochain pret cree s'appelle "p<n>"

Un pret :
pret        : le contrat (_PRET_DEFAUT) : nom, montant, taux (% annuel),
              periodicite (mois entre deux echeances : 1, 3, 6 ou 12),
              type ("amortissable" | "in_fine"), date_deblocage,
              premiere_echeance (differe compris), duree_remboursement (mois,
              hors differe), differe ("" | "partiel" | "total"), differe_mois,
              assurance {mode: "" | "initial" | "crd" | "fixe", taux (%/an),
              montant (EUR/mois), incluse (comprise dans l'echeance constante)},
              frais_dossier, frais_garantie, mensualite (celle qu'annonce la
              banque, pour controle), part (% du pret qui revient a
              l'utilisateur : pret a deux), placements (onglets Bourse,
              Assurance vie, Livrets), remboursements_auto (echeances comptees
              a leur date, sinon pointees a la main)
              -> l'echeancier se CALCULE (prEcheancier, index.html) : rien
                 n'est saisi echeance par echeance
versements  : {id, date, montant} — tranches versees par la banque
remboursements : {id, date, montant, echeance} — echeances pointees a la main
              (echeance = sa date dans l'echeancier ; absente pour une
              saisie d'avant la 4.4.17 : du capital rembourse)
evenements  : {id, date, type: "anticipe" | "taux" | "report" | "modulation", ...}
              -> remboursement anticipe {montant, mode: "duree" | "mensualite"
                 | "total", ira}, changement de taux {taux, ajuste: "mensualite"
                 | "duree"}, report {mois, report: "partiel" | "total"},
                 modulation {mensualite}
pea.achats  : {id, date, ticker, montant, quantite, cours_achat}
pea.ventes  : {id, date, ticker, quantite, cours_vente, montant} (montant = credite)
              -> saisies d'avant la lecture des ordres du PEA : ne se remplissent plus
av.contrats : [{id, label, frais_versement, taux_annuels:[{annee,taux}], depots:[{id,date,montant,note}]}]
              -> plusieurs contrats possibles, chacun avec ses propres taux
              -> frais_versement : % pris sur chaque depot (Afer : 0,5 sur le fonds euros)
livrets     : [{id, label, taux_history:[{id,date,taux}], mouvements:[{id,date,type,montant,note}]}]
              (un seul livret, cle "liv", jusqu'a la 4.4.16)
frais_recurrents : {id, label, montant, date_debut, frequence, nb_occurrences, paliers}
              -> preleve le meme jour de chaque mois (jour pris sur date_debut)
              -> nb_occurrences 0 = sans fin ; paliers [{id, date, montant}] =
                 nouveau montant a partir de cette date (les prelevements
                 passes gardent le leur). Seuls les prelevements dates
                 d'aujourd'hui ou avant comptent dans les frais.
frais_rembourses : {id, date, montant, label}
              -> frais que la banque a rendus (ex. un mois de carte offert),
                 deduits du total des frais
"""
from __future__ import annotations

import datetime
import shutil

import jsonstore


SCHEMA = 7   # 6 : un seul pret, a plat (ancienne app standalone, jusqu'a la 4.4.16)

# Le contrat d'un pret, toutes cles presentes
_PRET_DEFAUT = {
    "nom": "", "montant": 0, "taux": 0, "periodicite": 1, "type": "amortissable",
    "date_deblocage": "", "premiere_echeance": "", "duree_remboursement": 0,
    "differe": "", "differe_mois": 0,
    "assurance": {"mode": "", "taux": 0, "montant": 0, "incluse": False},
    "frais_dossier": 0, "frais_garantie": 0, "mensualite": 0,
    "part": 100, "placements": False, "remboursements_auto": True,
}
_LISTES = ("versements", "remboursements", "evenements", "frais",
           "frais_recurrents", "frais_rembourses")
# Cles du schema 6, a plat a la racine du fichier
_ANCIENNES_CLES = ("pret", "pea", "av", "liv", "versements", "remboursements",
                   "frais", "frais_recurrents", "frais_rembourses", "config_locked")


def default_data() -> dict:
    return {
        "_meta": {
            "version": 1,
            "schema": "pret.v1",
            "createdAt":   datetime.date.today().isoformat(),
            "lastSavedAt": datetime.datetime.now().isoformat(timespec="seconds"),
        },
        "schema": SCHEMA,
        "prets": [],
        "actif": "",
        "_nid": {"pret": 1},
    }


_store = jsonstore.JsonStore(
    filename="pret.json",
    backup_dirname="backups_pret",
    schema="pret.v1",
    default_factory=default_data,
)


def load_data() -> dict:
    data = _store.load()
    if any(k in data for k in _ANCIENNES_CLES):
        _migrer_schema6(data)
    if not isinstance(data.get("prets"), list):
        data["prets"] = []
    for p in data["prets"]:
        _normaliser(p)
    ids = [p.get("id") for p in data["prets"]]
    # Le prochain id libre, meme si le fichier a ete retouche a la main
    nums = [int(i[1:]) for i in ids if isinstance(i, str) and i[1:].isdigit()]
    data["_nid"]["pret"] = max([int(data["_nid"].get("pret") or 1)] + [n + 1 for n in nums])
    if data.get("actif") not in ids:
        data["actif"] = ids[0] if ids else ""
    data["schema"] = SCHEMA
    return data


def _num(v) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _migrer_schema6(data: dict) -> None:
    """Schema 6 (un seul pret, a plat) -> schema 7 : l'ancien pret devient le
    pret "p1", avec tout ce qu'il contient. Un pret jamais saisi ne devient
    rien. Le fichier d'origine est d'abord copie a cote (une seule fois)."""
    ancien = {k: data.pop(k) for k in _ANCIENNES_CLES if k in data}
    if data.get("prets"):
        return   # deja au schema 7 : des restes, sans valeur
    p = dict(ancien.get("pret") or {})
    pea = ancien.get("pea") if isinstance(ancien.get("pea"), dict) else {}
    av = ancien.get("av") if isinstance(ancien.get("av"), dict) else {}
    liv = ancien.get("liv") if isinstance(ancien.get("liv"), dict) else {}
    listes = {k: (ancien.get(k) if isinstance(ancien.get(k), list) else []) for k in _LISTES}
    place = bool(av.get("contrats") or av.get("depots") or av.get("taux_annuels")
                 or liv.get("mouvements") or liv.get("taux_history")
                 or pea.get("achats") or pea.get("ventes"))
    if not (_num(p.get("montant")) or any(listes.values()) or place):
        return
    try:
        copie = _store.path().with_name("pret.avant-plusieurs-prets.json")
        if _store.path().exists() and not copie.exists():
            shutil.copy2(str(_store.path()), str(copie))
    except Exception as e:
        print(f"[pret] copie avant migration KO: {e}", flush=True)
    # Le module s'appelait « Pret etudiant » jusqu'a la 4.3.33 : un pret deja
    # saisi garde ce nom, un pret jamais nomme garde un nom vide.
    if "nom" not in p:
        deja_saisi = p.get("montant") or listes["versements"] or listes["remboursements"]
        p["nom"] = "Prêt étudiant" if deja_saisi else ""
    # Sa date de 1er remboursement (sans differe) est sa 1re echeance
    p["premiere_echeance"] = p.pop("date_premier_remboursement", "") or p.get("premiere_echeance", "")
    p.setdefault("taux", 0)                       # pas de taux avant : capital du = verse - rembourse
    p.setdefault("placements", place)             # le pret dont l'argent est place garde ses onglets
    p.setdefault("remboursements_auto", False)    # remboursements saisis a la main jusqu'ici
    livrets = []
    if liv.get("mouvements") or liv.get("taux_history"):
        livrets.append(dict(liv, id="l1"))
    pret = {"id": "p1", "pret": p, "pea": pea, "av": av, "livrets": livrets}
    pret.update(listes)
    data["prets"] = [pret]
    data["actif"] = "p1"
    data.setdefault("_nid", {})["pret"] = 2


def _normaliser(L: dict) -> None:
    """Un pret avec toutes ses cles (le JS ne verifie rien)."""
    contrat = dict(_PRET_DEFAUT)
    contrat.update(L.get("pret") or {})
    ass = dict(_PRET_DEFAUT["assurance"])
    if isinstance(contrat.get("assurance"), dict):
        ass.update(contrat["assurance"])
    contrat["assurance"] = ass
    L["pret"] = contrat
    for k in _LISTES:
        if not isinstance(L.get(k), list):
            L[k] = []
    pea = L.get("pea") if isinstance(L.get("pea"), dict) else {}
    for k in ("achats", "ventes"):
        if not isinstance(pea.get(k), list):
            pea[k] = []
    L["pea"] = pea
    av = L.get("av") if isinstance(L.get("av"), dict) else {}
    _migrate_av(av)
    L["av"] = av
    if not isinstance(L.get("livrets"), list):
        L["livrets"] = []
    for i, liv in enumerate(L["livrets"]):
        liv.setdefault("id", "l%d" % (i + 1))
        liv.setdefault("label", "Livret A")
        for k in ("taux_history", "mouvements"):
            if not isinstance(liv.get(k), list):
                liv[k] = []


def _migrate_av(av: dict) -> None:
    """Ancien modele (un seul contrat a plat) -> liste de contrats."""
    if not isinstance(av.get("contrats"), list):
        av["contrats"] = []
    legacy_depots = av.pop("depots", None)
    legacy_taux   = av.pop("taux_annuels", None)
    legacy_label  = av.pop("label", None)
    if (legacy_depots or legacy_taux) and not av["contrats"]:
        av["contrats"].append({
            "id":    "av1",
            "label": legacy_label or "Assurance Vie Fonds Euros",
            "taux_annuels": legacy_taux or [],
            "depots":       legacy_depots or [],
        })
    for c in av["contrats"]:
        if not isinstance(c.get("taux_annuels"), list):
            c["taux_annuels"] = []
        if not isinstance(c.get("depots"), list):
            c["depots"] = []
        c.setdefault("label", "Assurance vie")


def save_data(data: dict) -> None:
    data = dict(data or {})
    # Ces deux cles n'ont de sens que dans l'ancienne app localStorage.
    data.pop("undo_stack", None)
    data.pop("cours_cache", None)
    data["schema"] = SCHEMA
    _store.save(data)
