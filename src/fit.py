"""
fit.py — Lecture des fichiers .fit (format des montres : Coros, Garmin, Suunto,
Polar…) pour la section Montres : chaque fichier devient une seance de Sports.

Le format FIT est publie par Garmin (FIT SDK, « Flexible and Interoperable Data
Transfer ») : un en-tete, puis des messages decrits par des « definitions ».
On ne lit que trois messages, sans dependance :
  * file_id (0)   : le fabricant (pour le badge) ;
  * session (18)  : sport, debut, duree, distance, D+, FC moyenne, kcal ;
  * activity (34) : l'heure locale de la montre (decalage avec l'UTC).

Rien n'est enregistre ici : comme pour Garmin, la page ajoute les seances a
SP elle-meme (docs/modules/garmin.md, « Ce qu'il ne faut pas defaire », 1).
"""
from __future__ import annotations

import base64
import datetime
import hashlib
import io
import struct
import zipfile

import garmin

TAILLE_MAX = 50 * 1024 * 1024        # un .fit d'une sortie de 10 h fait ~5 Mo
EPOQUE_FIT = 631065600               # 31/12/1989 00:00 UTC, en secondes Unix

# Types de base : (format struct, valeur « invalide » du SDK)
_TYPES = {
    0x00: ("B", 0xFF), 0x01: ("b", 0x7F), 0x02: ("B", 0xFF),
    0x83: ("h", 0x7FFF), 0x84: ("H", 0xFFFF), 0x85: ("i", 0x7FFFFFFF),
    0x86: ("I", 0xFFFFFFFF), 0x88: ("f", None), 0x89: ("d", None),
    0x0A: ("B", 0), 0x8B: ("H", 0), 0x8C: ("I", 0),
    0x8E: ("q", 0x7FFFFFFFFFFFFFFF), 0x8F: ("Q", 0xFFFFFFFFFFFFFFFF), 0x90: ("Q", 0),
}

# Champs lus : {message: {numero: nom}}
_CHAMPS = {
    0:  {1: "fabricant"},
    18: {253: "fin", 2: "debut", 5: "sport", 6: "sous_sport", 7: "duree_totale",
         8: "duree_chrono", 9: "distance", 11: "kcal", 16: "fc_moy", 22: "denivele",
         44: "bassin"},
    34: {253: "horodatage", 5: "heure_locale"},
}

# Sport du SDK -> sport de Pilote (le reste : « Autre »)
_SPORTS = {1: "course", 2: "velo", 5: "natation", 7: "foot", 16: "rando", 17: "rando"}
_MUSCU = 20                          # sous-sport strength_training (sport training = 10)
FABRICANTS = {1: "Garmin", 23: "Suunto", 123: "Polar", 294: "Coros", 32: "Wahoo"}


class ErreurFit(Exception):
    pass


def _lire(octets: bytes) -> dict:
    """{message: [ {nom: valeur} ]} pour les messages de _CHAMPS. Un fichier
    coupe (copie interrompue) : ce qui precede la coupure est garde."""
    out = {n: [] for n in _CHAMPS}
    try:
        _parcourir(octets, out)
    except (IndexError, struct.error):
        pass
    return out


def _parcourir(octets: bytes, out: dict) -> None:
    if len(octets) < 12:
        raise ErreurFit("Ce fichier est trop court pour être un .fit.")
    taille_entete = octets[0]
    if taille_entete not in (12, 14) or octets[8:12] != b".FIT":
        raise ErreurFit("Ce fichier n'est pas un .fit (export de montre attendu).")
    fin = min(len(octets), taille_entete + struct.unpack_from("<I", octets, 4)[0])
    pos = taille_entete
    definitions = {}
    while pos < fin:
        entete = octets[pos]
        pos += 1
        if entete & 0x80:                       # en-tete compresse (horodatage) : message de donnees
            local, est_def, dev = (entete >> 5) & 0x03, False, False
        else:
            local, est_def, dev = entete & 0x0F, bool(entete & 0x40), bool(entete & 0x20)
        if est_def:
            if pos + 5 > fin:
                break
            ordre = ">" if octets[pos + 1] == 1 else "<"
            numero = struct.unpack_from(ordre + "H", octets, pos + 2)[0]
            nb = octets[pos + 4]
            pos += 5
            champs = []
            for _ in range(nb):
                champs.append((octets[pos], octets[pos + 1], octets[pos + 2]))
                pos += 3
            taille_dev = 0
            if dev:
                nb_dev = octets[pos]
                pos += 1
                taille_dev = sum(octets[pos + 3 * i + 1] for i in range(nb_dev))
                pos += 3 * nb_dev
            definitions[local] = (numero, ordre, champs, taille_dev)
            continue
        d = definitions.get(local)
        if d is None:
            raise ErreurFit("Fichier .fit abîmé : un message sans définition.")
        numero, ordre, champs, taille_dev = d
        noms = _CHAMPS.get(numero)
        valeurs = {}
        for num, taille, base in champs:
            if noms and num in noms and base in _TYPES:
                fmt, invalide = _TYPES[base]
                if struct.calcsize(fmt) <= taille and pos + taille <= fin:
                    v = struct.unpack_from(ordre + fmt, octets, pos)[0]   # tableau : la premiere valeur
                    if v != invalide and v == v:
                        valeurs[noms[num]] = v
            pos += taille
        pos += taille_dev
        if noms is not None and valeurs:
            out[numero].append(valeurs)


def _date(secondes_fit: int, decalage: int) -> datetime.datetime:
    return datetime.datetime.utcfromtimestamp(secondes_fit + EPOQUE_FIT + decalage)


def seances(octets: bytes) -> list:
    """Les seances d'un .fit, au format de garmin.seance (avec fitId au lieu
    de garminId). Un fichier multisport donne une seance par sport."""
    if len(octets) > TAILLE_MAX:
        raise ErreurFit("Ce fichier est trop gros pour un .fit de séance.")
    m = _lire(octets)
    if not m[18]:
        raise ErreurFit("Ce .fit ne contient pas de séance (un parcours ou un réglage ?).")
    fab = next((f["fabricant"] for f in m[0] if "fabricant" in f), None)
    # Decalage heure locale - UTC, donne par la montre (sinon celui du PC)
    decalage = None
    for a in m[34]:
        if "heure_locale" in a and "horodatage" in a:
            decalage = int(a["heure_locale"]) - int(a["horodatage"])
    out = []
    for s in m[18]:
        debut = s.get("debut") or s.get("fin")
        if not debut:
            continue
        if decalage is None:
            utc = datetime.datetime.utcfromtimestamp(debut + EPOQUE_FIT).replace(tzinfo=datetime.timezone.utc)
            dec = int(utc.astimezone().utcoffset().total_seconds())
        else:
            dec = decalage
        quand = _date(int(debut), dec)
        sport = _SPORTS.get(s.get("sport"), "autre")
        if s.get("sport") == 10 and s.get("sous_sport") == _MUSCU:
            sport = "muscu"
        champs = garmin._champs(sport)
        secondes = (s.get("duree_chrono") or s.get("duree_totale") or 0) / 1000
        metres = (s.get("distance") or 0) / 100
        ident = hashlib.sha1(f"{int(debut)}|{s.get('sport')}|{round(secondes)}".encode()).hexdigest()[:16]
        r = {
            "fitId":     ident,
            "date":      quand.date().isoformat(),
            "time":      quand.strftime("%H:%M"),
            "sport":     sport,
            "duration":  round(secondes / 60),
            "distance":  0,
            "elevation": round(s.get("denivele") or 0) if "elevation" in champs else 0,
            "note":      "",
            "marque":    FABRICANTS.get(fab, ""),
        }
        if "distance_m" in champs:
            r["distance"] = round(metres)
        elif "distance_km" in champs:
            r["distance"] = round(metres / 1000, 2)
        if "lieu" in champs:
            bassin = round((s.get("bassin") or 0) / 100)
            r["lieu"] = str(bassin) if bassin in (25, 50) else "libre"
        if s.get("fc_moy"):
            r["fcMoy"] = int(s["fc_moy"])
        if s.get("kcal"):
            r["kcal"] = int(s["kcal"])
        out.append(r)
    return out


def lire(fichiers: list) -> dict:
    """[{nom, b64}] choisis dans la page (.fit, ou .zip d'un export complet)
    -> {seances, erreurs: [{nom, erreur}]}. Rien n'est enregistre."""
    seances_, erreurs = [], []

    def un(nom, octets):
        try:
            seances_.extend(seances(octets))
        except ErreurFit as e:
            erreurs.append({"nom": nom, "erreur": str(e)})

    for f in fichiers or []:
        nom = str((f or {}).get("nom") or "fichier")[:200]
        try:
            octets = base64.b64decode((f or {}).get("b64") or "")
        except (ValueError, TypeError):
            erreurs.append({"nom": nom, "erreur": "Fichier illisible."})
            continue
        if octets[:2] == b"PK":
            try:
                with zipfile.ZipFile(io.BytesIO(octets)) as z:
                    noms = [i for i in z.infolist() if i.filename.lower().endswith(".fit")
                            and i.file_size <= TAILLE_MAX][:2000]
                    if not noms:
                        erreurs.append({"nom": nom, "erreur": "Aucun fichier .fit dans ce .zip."})
                    for i in noms:
                        un(i.filename.rsplit("/", 1)[-1], z.read(i))
            except zipfile.BadZipFile:
                erreurs.append({"nom": nom, "erreur": "Ce .zip est abîmé."})
            continue
        un(nom, octets)
    # Un même fichier choisi deux fois : une seule séance
    vus, uniques = set(), []
    for s in sorted(seances_, key=lambda s: (s["date"], s["time"])):
        if s["fitId"] not in vus:
            vus.add(s["fitId"])
            uniques.append(s)
    return {"seances": uniques, "erreurs": erreurs}
