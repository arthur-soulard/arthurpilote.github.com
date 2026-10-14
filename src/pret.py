"""
pret.py — Stockage du module "Pret" (nom libre, "Pret etudiant" jusqu'a la 4.3.33).

Reprend le modele de l'ancienne application standalone Pret_Etudiant.exe
(localStorage cle "pret_v1", schema 6), mais persiste sur disque comme le
reste de Pilote. Le fichier appartient a l'utilisateur actif.

Emplacement : <app_dir>/users/<slug>/pret.json
Backup quotidien : <app_dir>/users/<slug>/backups_pret/pret_YYYY-MM-DD.json

Modele
------
pret        : {nom, montant, date_deblocage, date_premier_remboursement,
               duree_remboursement, mensualite}
              -> nom : libre (« Pret etudiant », « Pret auto »…), vide = « Pret »
pea.achats  : {id, date, ticker, montant, quantite, cours_achat}
pea.ventes  : {id, date, ticker, quantite, cours_vente, montant} (montant = credite)
av.contrats : [{id, label, frais_versement, taux_annuels:[{annee,taux}], depots:[{id,date,montant,note}]}]
              -> plusieurs contrats possibles, chacun avec ses propres taux
              -> frais_versement : % pris sur chaque depot (Afer : 0,5 sur le fonds euros)
liv         : {label, taux_history:[{id,date,taux}], mouvements:[{id,date,type,montant,note}]}
frais_recurrents : {id, label, montant, date_debut, frequence, nb_occurrences, paliers}
              -> preleve le meme jour de chaque mois (jour pris sur date_debut)
              -> nb_occurrences 0 = sans fin ; paliers [{id, date, montant}] =
                 nouveau montant a partir de cette date (les prelevements
                 passes gardent le leur). Seuls les prelevements dates
                 d'aujourd'hui ou avant comptent dans les frais.
frais_rembourses : {id, date, montant, label}
              -> frais que la banque a rendus (ex. un mois de carte offert),
                 deduits du total des frais

La 4.4.17 avait rendu le module generique (plusieurs prets, schema 7 : liste
"prets"), retiree en 4.4.18 a la demande d'Arthur. Un fichier au schema 7
revient au schema 6 a sa lecture : voir _revenir_schema6.
"""
from __future__ import annotations

import calendar
import datetime
import shutil

import jsonstore


SCHEMA = 6   # aligne sur l'ancienne app standalone


def default_data() -> dict:
    return {
        "_meta": {
            "version": 1,
            "schema": "pret.v1",
            "createdAt":   datetime.date.today().isoformat(),
            "lastSavedAt": datetime.datetime.now().isoformat(timespec="seconds"),
        },
        "schema": SCHEMA,
        "config_locked": False,
        "pret": {
            "nom": "",
            "montant": 0,
            "date_deblocage": "",
            "date_premier_remboursement": "",
            "duree_remboursement": 0,
            "mensualite": 0,
        },
        "pea": {"ticker": "", "achats": [], "ventes": []},
        "av":  {"contrats": []},
        "liv": {"label": "Livret A", "taux_history": [], "mouvements": []},
        "versements":      [],
        "remboursements":  [],
        "frais":           [],
        "frais_recurrents": [],
        "frais_rembourses": [],
    }


_store = jsonstore.JsonStore(
    filename="pret.json",
    backup_dirname="backups_pret",
    schema="pret.v1",
    default_factory=default_data,
)

def load_data() -> dict:
    data = _store.load()
    if isinstance(data.get("prets"), list):
        _revenir_schema6(data)
    # Le module s'appelait « Pret etudiant » jusqu'a la 4.3.33 : un pret deja
    # saisi garde ce nom, un pret jamais saisi prend le nom generique. A lire
    # AVANT la fusion avec les defauts, qui donnerait un nom vide a tous.
    ancien = data.get("pret") or {}
    if "nom" not in ancien:
        deja_saisi = ancien.get("montant") or data.get("versements") or data.get("remboursements")
        data["pret"] = dict(ancien, nom="Prêt étudiant" if deja_saisi else "")
    # Les sous-objets doivent toujours exister avec leurs cles (merge peu profond
    # du JsonStore : une cle "pea" sauvegardee ecrase entierement le defaut).
    defaults = default_data()
    for key in ("pret", "pea", "av", "liv"):
        base = dict(defaults[key])
        base.update(data.get(key) or {})
        data[key] = base
    for key in ("versements", "remboursements", "frais", "frais_recurrents", "frais_rembourses"):
        if not isinstance(data.get(key), list):
            data[key] = []
    for key in ("achats", "ventes"):
        if not isinstance(data["pea"].get(key), list):
            data["pea"][key] = []
    _migrate_av(data)
    if not isinstance(data["liv"].get("taux_history"), list):
        data["liv"]["taux_history"] = []
    if not isinstance(data["liv"].get("mouvements"), list):
        data["liv"]["mouvements"] = []
    return data


def _revenir_schema6(data: dict) -> None:
    """Schema 7 (4.4.17, plusieurs prets) -> schema 6. Le premier pret de la
    liste (« p1 », celui d'avant la 4.4.17) reprend sa place a plat. Ce que le
    schema 6 ne connait pas (taux, assurance, evenements, autres prets, livrets
    apres le premier) est laisse de cote : le fichier au schema 7 est d'abord
    copie a cote, une seule fois, pour ne rien perdre."""
    prets = [p for p in data.pop("prets") if isinstance(p, dict)]
    data.pop("actif", None)
    data.pop("_nid", None)
    data["schema"] = SCHEMA
    try:
        copie = _store.path().with_name("pret.plusieurs-prets-4.4.17.json")
        if _store.path().exists() and not copie.exists():
            shutil.copy2(str(_store.path()), str(copie))
    except Exception as e:
        print(f"[pret] copie avant retour au schema 6 KO: {e}", flush=True)
    if not prets:
        return   # aucun pret saisi : les defauts suffisent
    L = prets[0]
    c = L.get("pret") or {}
    # Au schema 7, la 1re echeance compte le differe ; au schema 6, c'est la
    # date du 1er remboursement de capital.
    premier = c.get("premiere_echeance") or ""
    if premier and c.get("differe") in ("partiel", "total") and c.get("differe_mois"):
        premier = _plus_mois(premier, int(c["differe_mois"]))
    data["pret"] = {
        "nom": c.get("nom", ""),
        "montant": c.get("montant", 0),
        "date_deblocage": c.get("date_deblocage", ""),
        "date_premier_remboursement": premier,
        "duree_remboursement": c.get("duree_remboursement", 0),
        "mensualite": c.get("mensualite", 0),
    }
    data["pea"] = L.get("pea") or {}
    data["av"] = L.get("av") or {}
    livrets = [x for x in (L.get("livrets") or []) if isinstance(x, dict)]
    if livrets:
        data["liv"] = {k: v for k, v in livrets[0].items() if k != "id"}
    for key in ("versements", "remboursements", "frais", "frais_recurrents", "frais_rembourses"):
        data[key] = L.get(key) or []
    data["config_locked"] = False


def _plus_mois(iso: str, n: int) -> str:
    try:
        d = datetime.date.fromisoformat(iso)
    except ValueError:
        return iso
    m = d.month - 1 + n
    annee, mois = d.year + m // 12, m % 12 + 1
    return d.replace(year=annee, month=mois,
                     day=min(d.day, calendar.monthrange(annee, mois)[1])).isoformat()


def _migrate_av(data: dict) -> None:
    """Ancien modele (un seul contrat a plat) -> liste de contrats."""
    av = data["av"]
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
    _store.save(data)
