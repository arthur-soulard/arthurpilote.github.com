"""
donnees.py — le seul passage pour lire ou écrire un fichier de données de Pilote.

Étape 1 du chiffrement des données sur le disque (docs/securite.md, « b »,
décidé avec Arthur le 12/11/2026) : chaque lecture et chaque écriture d'un
fichier de Donnees/ (pea_data.json, users.json, fichiers des modules, leurs
backups, sauvegarde.json, pin.hash, utilisateur Exemple) passe par ici.
Rien n'est encore chiffré : ces fonctions lisent et écrivent du texte UTF-8,
exactement comme le faisait chaque module avant. L'étape 2 (case « Chiffrer
mes données », mot de passe de secours) n'aura à changer que ce fichier :
décoder un fichier chiffré à la lecture, chiffrer à l'écriture si la case est
cochée.

Ce qui ne passe PAS par ici, volontairement :
* les copies d'un fichier tel quel (corbeille, copie avant import, archive de
  sauvegarde) : un fichier chiffré copié reste chiffré, c'est voulu ;
* les données publiques ou régénérables (etf_compositions.json, icônes,
  crash.log, journaux) ;
* les fichiers venus de l'utilisateur (relevés, captures, exports d'autres
  applis), qui ne sont jamais écrits dans Donnees/ tels quels.

tests/test_donnees_passage.py vérifie qu'aucun module de données n'ouvre plus
un JSON de Donnees/ sans passer par ici.
"""
from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path


# ─── Lecture ──────────────────────────────────────────────────────────────────

def texte_de(octets: bytes) -> str:
    """Contenu d'un fichier de données (lu sur le disque ou dans une archive)
    -> texte. Étape 2 : déchiffrera un contenu chiffré."""
    return octets.decode("utf-8")


def lire_texte(chemin) -> str:
    with open(chemin, "rb") as f:
        return texte_de(f.read())


def lire_json(chemin):
    return json.loads(lire_texte(chemin))


# ─── Écriture ─────────────────────────────────────────────────────────────────

def octets_de(texte: str) -> bytes:
    """Texte -> contenu à écrire sur le disque. Étape 2 : chiffrera si
    l'utilisateur l'a choisi."""
    return texte.encode("utf-8")


def remplacer(tmp, cible) -> None:
    """os.replace, réessayé 5 fois : sous Windows, il échoue tant qu'un autre
    programme (archive USB, antivirus, indexation, OneDrive) tient le fichier
    ouvert un instant (DAT-05)."""
    for essai in range(5):
        try:
            os.replace(tmp, cible)
            return
        except PermissionError:
            if essai == 4:
                raise
            time.sleep(0.1 * (essai + 1))


def ecrire_texte(chemin, texte: str, prefixe: str = None) -> None:
    """Écriture atomique : fichier temporaire du même dossier, fsync, puis
    renommage. Un fichier n'est jamais à moitié écrit, même si le PC s'éteint."""
    chemin = Path(chemin)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="." + (prefixe or chemin.stem) + "_", suffix=".tmp",
                               dir=str(chemin.parent))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(octets_de(texte))
            f.flush()
            os.fsync(f.fileno())
        remplacer(tmp, chemin)
    except Exception:
        try:
            os.remove(tmp)
        except Exception:
            pass
        raise


def ecrire_json(chemin, data, indent=2, prefixe: str = None) -> None:
    ecrire_texte(chemin, json.dumps(data, ensure_ascii=False, indent=indent), prefixe)
