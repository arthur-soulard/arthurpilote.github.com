"""
taches.py — Module "Taches" : ce qu'il y a a faire, avec une echeance.

Emplacement : <app_dir>/users/<slug>/taches.json
Backup quotidien : <app_dir>/users/<slug>/backups_taches/

Modele de donnees
─────────────────
taches : {id, titre, note, echeance:"YYYY-MM-DD"|"", priorite:0|1|2 (normale, haute,
          urgente), projet:"", recurrence:""|"jour"|"semaine"|"mois"|"an",
          fait:"YYYY-MM-DD"|"" (date ou elle a ete cochee), cree:"YYYY-MM-DD"}
projets : liste de noms, dans l'ordre choisi

Une tache recurrente cochee n'est pas gardee cochee : l'interface la repousse a
sa prochaine echeance (et note la date dans `faites`, pour le bilan annuel).
Tout le calcul vit dans la page (bloc `tc*` d'index.html) ; Python ne fait que
persister, comme pour Sports.
"""
from __future__ import annotations

import datetime

import jsonstore


def default_data() -> dict:
    return {
        "_meta": {
            "schema":      "taches.v1",
            "version":     1,
            "createdAt":   datetime.date.today().isoformat(),
            "lastSavedAt": datetime.datetime.now().isoformat(timespec="seconds"),
        },
        "taches":  [],
        "projets": [],
        # Dates ou une tache recurrente a ete faite : {id de la tache: [dates]}
        "faites":  {},
        "_nid":    {"tache": 1},
    }


_store = jsonstore.JsonStore(
    filename="taches.json",
    backup_dirname="backups_taches",
    schema="taches.v1",
    default_factory=default_data,
)


def load_data() -> dict:
    return _store.load()


def save_data(data: dict) -> None:
    _store.save(data)


def erreur():
    return _store.erreur()
