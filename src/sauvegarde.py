"""
sauvegarde.py — Sauvegarde externe du dossier Donnees vers une cle USB.

Principe
────────
Une sauvegarde = une archive .zip de TOUT le dossier Donnees (tous les
utilisateurs, users.json compris). C'est volontaire : une cle USB qu'on
rebranche apres un crash disque doit pouvoir remonter l'installation
entiere, pas un seul espace.

La configuration est donc, elle aussi, au niveau de l'installation :
<app_dir>/sauvegarde.json, a cote de users.json — et non dans le dossier
d'un utilisateur.

La lettre d'une cle USB change (E:, F:, G:...). On memorise donc le
NUMERO DE SERIE du volume, et on retrouve la cle quelle que soit la lettre
que Windows lui donne au prochain branchement.

Chiffrement (09/11/2026) : avec un mot de passe choisi dans Parametres, les
archives deviennent des fichiers .pilote chiffres (chiffrement.py) et le
bouton Televerser n'ecrit plus de copie en clair sur la cle. Sans mot de
passe, rien ne change : un .zip lisible, comme avant. Les anciennes archives
.zip se restaurent toujours.
"""
from __future__ import annotations

import os
import re
import sys
import json
import shutil
import zipfile
import datetime
import tempfile
from pathlib import Path
from typing import Optional, Tuple

import storage
import chiffrement


CONFIG_FILE = "sauvegarde.json"
ARCHIVE_PREFIX = "Pilote_"
EXT_ZIP = ".zip"
EXT_CHIFFRE = ".pilote"          # archive chiffree (chiffrement.py)
TELEVERSEMENT = "Pilote_televersement" + EXT_CHIFFRE   # bouton Televerser, chiffre


def _est_archive(nom: str) -> bool:
    return nom.startswith(ARCHIVE_PREFIX) and nom.endswith((EXT_ZIP, EXT_CHIFFRE))

# Dossiers du dossier Donnees qu'on ne sauvegarde pas : regenerables.
EXCLUDED_DIRS = {"icones"}

DRIVE_REMOVABLE = 2
DRIVE_FIXED     = 3


# ─── Configuration ────────────────────────────────────────────────────────────

def default_config() -> dict:
    return {
        "_meta": {
            "version": 1,
            "schema": "sauvegarde.v1",
            "createdAt": datetime.date.today().isoformat(),
        },
        # Destination
        "destination":    "",       # chemin complet, ex. "E:\\Sauvegardes Pilote"
        "volumeSerial":   "",       # numero de serie du volume (retrouve la cle)
        "volumeLabel":    "",       # nom affiche de la cle, pour l'UI
        "relativePath":   "",       # sous-dossier sur la cle, ex. "Sauvegardes Pilote"
        # Comportement
        "auto":           True,     # sauvegarder tout seul quand la cle est la
        "frequence":      "daily",  # daily | weekly | manual
        "keep":           10,       # nombre d'archives conservees (rotation)
        "moment":         "demarrage",  # demarrage | branchement | fermeture
        # Reglages de la cle (docs/sauvegarde-usb.md, « Les quatre reglages »)
        "clesAutorisees": [],       # [{serial, label}] ; vide : toute cle branchee
        "dossierCle":     "Pilote", # dossier du miroir sur la cle (bouton Televerser)
        "avecBackups":    True,     # inclure les backups_* quotidiens des modules
        "alerteJours":    7,        # alerte de l'accueil apres N jours ; 0 : jamais
        "ejecter":        False,    # ejecter la cle une fois la copie finie
        # Chiffrement par mot de passe (chiffrement.py). La cle derivee, jamais
        # le mot de passe, gardee par Windows (DPAPI) ou le Trousseau du Mac
        "chiffrer":       False,
        "cleChiffree":    "",       # « dpapi:… » / « trousseau:… »
        "sel":            "",       # hex, sel du mot de passe actuel
        "iterations":     chiffrement.ITERATIONS,
        "empreinte":      "",       # reconnait les archives du mot de passe actuel
        # Dernier resultat
        "lastBackupAt":   "",
        "lastBackupPath": "",
        "lastStatus":     "",       # ok | error | absent
        "lastError":      "",
        # Dernier televersement direct (bouton de l'accueil)
        "lastPushAt":     "",
        "lastPushPath":   "",
    }


def _config_path() -> Path:
    return storage.get_app_dir() / CONFIG_FILE


def load_config() -> dict:
    p = _config_path()
    cfg = default_config()
    if p.exists():
        try:
            with open(p, "r", encoding="utf-8") as f:
                saved = json.load(f)
            for k, v in (saved or {}).items():
                cfg[k] = v
        except Exception as e:
            print(f"[sauvegarde] config illisible : {e}", flush=True)
    return cfg


def save_config(cfg: dict) -> None:
    p = _config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".sauvegarde_", suffix=".tmp", dir=str(p.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        os.replace(tmp, p)
    except Exception:
        try:
            os.remove(tmp)
        except Exception:
            pass
        raise


# ─── Detection des volumes amovibles (Windows) ────────────────────────────────

def _volume_info(root: str) -> dict:
    """Nom, numero de serie et systeme de fichiers d'un volume ("E:\\")."""
    info = {"label": "", "serial": "", "fs": ""}
    if sys.platform != "win32":
        return info
    try:
        import ctypes
        name_buf   = ctypes.create_unicode_buffer(261)
        fs_buf     = ctypes.create_unicode_buffer(261)
        serial     = ctypes.c_ulong(0)
        max_comp   = ctypes.c_ulong(0)
        flags      = ctypes.c_ulong(0)
        ok = ctypes.windll.kernel32.GetVolumeInformationW(
            ctypes.c_wchar_p(root),
            name_buf, ctypes.sizeof(name_buf),
            ctypes.byref(serial), ctypes.byref(max_comp), ctypes.byref(flags),
            fs_buf, ctypes.sizeof(fs_buf),
        )
        if ok:
            info["label"]  = name_buf.value or ""
            info["fs"]     = fs_buf.value or ""
            # Certaines cles (FAT32 bas de gamme, cartes SD) rendent un numero
            # de serie nul : il n'identifie alors rien du tout. On le traite
            # comme absent plutot que de croire reconnaitre la bonne cle.
            info["serial"] = "" if serial.value == 0 else f"{serial.value:08X}"
    except Exception:
        pass
    return info


def _disk_space(root: str) -> Tuple[int, int]:
    """(libre, total) en octets, (0, 0) si indisponible."""
    try:
        usage = shutil.disk_usage(root)
        return usage.free, usage.total
    except Exception:
        return 0, 0


def _mac_disque(point: str) -> dict:
    """Mac : ce que diskutil dit d'un volume monte ({} si illisible)."""
    import plistlib
    import subprocess
    try:
        r = subprocess.run(["diskutil", "info", "-plist", point],
                           capture_output=True, timeout=10)
        return plistlib.loads(r.stdout) if r.returncode == 0 and r.stdout else {}
    except Exception:
        return {}


def _mac_cles() -> list:
    """Mac : cles USB, cartes SD et disques externes montes sous /Volumes.

    Pas de lettre : la cle est la par son point de montage (/Volumes/CLE) et
    retrouvee par l'UUID de son volume, l'equivalent du numero de serie de
    Windows. Le disque du Mac (lien vers /), les images disque (.dmg) et les
    partages reseau (diskutil ne les connait pas) sont ecartes."""
    cles = []
    try:
        points = sorted(Path("/Volumes").iterdir())
    except Exception:
        return cles
    for p in points:
        try:
            if p.is_symlink() or not p.is_dir() or os.path.realpath(str(p)) == "/":
                continue
        except Exception:
            continue
        info = _mac_disque(str(p))
        if not info or info.get("BusProtocol") == "Disk Image":
            continue
        amovible = (info.get("RemovableMediaOrExternalDevice") or info.get("Ejectable")
                    or info.get("RemovableMedia") or info.get("Removable"))
        if info.get("Internal", True) and not amovible:
            continue
        free, total = _disk_space(str(p))
        if not total:
            continue
        cles.append({
            "root":   str(p),
            "letter": "",
            "label":  info.get("VolumeName") or p.name,
            "serial": info.get("VolumeUUID") or info.get("DiskUUID") or "",
            "fs":     info.get("FilesystemName") or info.get("FilesystemType") or "",
            "free":   free,
            "total":  total,
        })
    return cles


def list_removable_drives() -> list:
    """Cles USB et disques externes actuellement branches."""
    drives = []
    if sys.platform == "darwin":
        return _mac_cles()
    if sys.platform != "win32":
        return drives
    try:
        import ctypes
        mask = ctypes.windll.kernel32.GetLogicalDrives()
    except Exception:
        return drives

    for i in range(26):
        if not (mask >> i) & 1:
            continue
        root = f"{chr(65 + i)}:\\"
        try:
            dtype = ctypes.windll.kernel32.GetDriveTypeW(ctypes.c_wchar_p(root))
        except Exception:
            continue
        if dtype != DRIVE_REMOVABLE:
            continue
        info = _volume_info(root)
        free, total = _disk_space(root)
        if not total:
            continue  # lecteur declare mais sans media (lecteur de carte vide)
        drives.append({
            "root":   root,
            "letter": root[:2],
            "label":  info["label"] or "Volume amovible",
            "serial": info["serial"],
            "fs":     info["fs"],
            "free":   free,
            "total":  total,
        })
    return drives


# Dossier principal de Google Drive pour ordinateur, selon la langue du logiciel
_NOMS_MON_DRIVE = ("Mon Drive", "My Drive")


def list_cloud_folders() -> list:
    """Dossiers synchronises en ligne : « Mon Drive » de Google Drive pour
    ordinateur, et iCloud Drive.

    Sous Windows, Drive monte un lecteur fixe (G: en general) nomme « Google
    Drive » : list_removable_drives ne le voit pas (GetDriveTypeW = 3, verifie
    sur le vrai Drive le 01/11/2026). En mode « mise en miroir », le dossier
    est dans le profil. Sur Mac : ~/Library/CloudStorage/GoogleDrive-<compte>.
    iCloud Drive : ~/Library/Mobile Documents/com~apple~CloudDocs sur Mac,
    %USERPROFILE%\\iCloudDrive avec iCloud pour Windows."""
    bases = []
    icloud = []
    if sys.platform == "win32":
        try:
            import ctypes
            mask = ctypes.windll.kernel32.GetLogicalDrives()
        except Exception:
            mask = 0
        for i in range(26):
            if not (mask >> i) & 1:
                continue
            root = f"{chr(65 + i)}:\\"
            try:
                if ctypes.windll.kernel32.GetDriveTypeW(ctypes.c_wchar_p(root)) != DRIVE_FIXED:
                    continue
            except Exception:
                continue
            if _volume_info(root)["label"] == "Google Drive":
                bases.append((Path(root), root[:2]))
        bases.append((Path.home(), ""))
        icloud = [Path.home() / "iCloudDrive"]
    elif sys.platform == "darwin":
        try:
            bases = [(p, "") for p in sorted((Path.home() / "Library" / "CloudStorage").glob("GoogleDrive-*"))]
        except Exception:
            bases = []
        icloud = [Path.home() / "Library" / "Mobile Documents" / "com~apple~CloudDocs"]
    dossiers = []
    for base, letter in bases:
        for nom in _NOMS_MON_DRIVE:
            p = base / nom
            try:
                if not p.is_dir():
                    continue
            except Exception:
                continue
            free, total = _disk_space(str(p))
            dossiers.append({"root": str(p), "letter": letter, "label": nom,
                             "service": "Google Drive", "free": free, "total": total})
            break
    for p in icloud:
        try:
            if not p.is_dir():
                continue
        except Exception:
            continue
        free, total = _disk_space(str(p))
        dossiers.append({"root": str(p), "letter": "", "label": "iCloud Drive",
                         "service": "iCloud", "free": free, "total": total})
    return dossiers


def _find_drive_by_serial(serial: str) -> Optional[str]:
    """Retrouve la racine ("E:\\") du volume portant ce numero de serie."""
    if not serial:
        return None
    for d in list_removable_drives():
        if d["serial"] and d["serial"] == serial:
            return d["root"]
    return None


# ─── Resolution de la destination ─────────────────────────────────────────────

def resolve_destination(cfg: dict = None) -> dict:
    """
    Ou ecrire, maintenant ?

    Retourne {ready, path, reason, drive}. La cle est cherchee par numero de
    serie en priorite : si Windows lui a donne une autre lettre depuis la
    derniere fois, on la suit.
    """
    cfg = cfg or load_config()
    dest = (cfg.get("destination") or "").strip()
    serial = (cfg.get("volumeSerial") or "").strip()
    rel = (cfg.get("relativePath") or "").strip().strip("\\/")

    if not dest and not serial:
        return {"ready": False, "path": "", "reason": "unset",
                "message": "Aucune destination choisie.", "drive": None}

    # 1. Par numero de serie — resiste au changement de lettre
    if serial:
        root = _find_drive_by_serial(serial)
        if root:
            path = Path(root) / rel if rel else Path(root)
            return {"ready": True, "path": str(path), "reason": "ok",
                    "message": "", "drive": root[:2]}
        # La cle memorisee n'est pas branchee : on ne se rabat PAS sur le
        # chemin brut, il pointerait sur une autre cle qui a herite la lettre.
        return {"ready": False, "path": dest, "reason": "absent",
                "message": f"La clé « {cfg.get('volumeLabel') or 'de sauvegarde'} » "
                           f"n'est pas branchée.",
                "drive": None}

    # 2. Pas de numero de serie utilisable : on suit le NOM de volume, qui
    #    reste un indice correct, et a defaut le chemin brut.
    label = (cfg.get("volumeLabel") or "").strip()
    if label:
        for d in list_removable_drives():
            if d["label"] and d["label"].lower() == label.lower():
                path = Path(d["root"]) / rel if rel else Path(d["root"])
                return {"ready": True, "path": str(path), "reason": "ok",
                        "message": "", "drive": d["letter"]}

    p = Path(dest)
    if p.exists():
        return {"ready": True, "path": str(p), "reason": "ok", "message": "", "drive": None}
    return {"ready": False, "path": dest, "reason": "absent",
            "message": (f"La clé « {label} » n'est pas branchée.") if label
                       else "Destination introuvable.",
            "drive": None}


def set_destination(path: str) -> dict:
    """
    Enregistre une destination choisie par l'utilisateur.

    Si le chemin est sur un volume amovible, on retient son numero de serie
    et le sous-dossier, de facon a retrouver la cle plus tard.
    """
    cfg = load_config()
    p = Path(path)
    # Une destination dans Donnees/ s'archivait elle-meme a chaque fois et
    # remplissait le disque (2,7 Go en 2 minutes au banc d'essai, DAT-10)
    try:
        app_r = storage.get_app_dir().resolve()
        if p.resolve() == app_r or app_r in p.resolve().parents:
            return {"ok": False, "error": "Choisis un dossier en dehors du dossier des données de Pilote."}
    except Exception:
        pass
    # Le lecteur de Google Drive (G:) refuse tout fichier hors de « Mon Drive » :
    # G:\ choisi tel quel donnait « [Errno 2] ... G:\Pilote_....zip.part »
    # (vu chez Arthur le 01/11/2026). La racine mene a Mon Drive, le reste est refuse.
    for d in list_cloud_folders():
        if not d["letter"] or os.path.splitdrive(str(p))[0].upper() != d["letter"].upper():
            continue
        mon = Path(d["root"])
        if str(p).rstrip("\\/").upper() == d["letter"].upper():
            p = mon / "Sauvegardes Pilote"
        elif os.path.normcase(str(mon)) not in [os.path.normcase(str(x)) for x in [p, *p.parents]]:
            return {"ok": False, "error": f"Google Drive n'accepte des fichiers que dans « {d['label']} » : "
                                          f"choisis un dossier dans {mon}."}
    try:
        p.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return {"ok": False, "error": f"Dossier inaccessible : {e}"}

    cfg["destination"]  = str(p)
    cfg["volumeSerial"] = ""
    cfg["volumeLabel"]  = ""
    cfg["relativePath"] = ""

    if sys.platform == "win32":
        try:
            root = os.path.splitdrive(str(p.resolve()))[0] + "\\"
            import ctypes
            dtype = ctypes.windll.kernel32.GetDriveTypeW(ctypes.c_wchar_p(root))
            if dtype == DRIVE_REMOVABLE:
                info = _volume_info(root)
                cfg["volumeSerial"] = info["serial"]       # "" si illisible
                cfg["volumeLabel"]  = info["label"] or ""
                rel = str(p.resolve())[len(root):]
                cfg["relativePath"] = rel.strip("\\/")
        except Exception:
            pass
    elif sys.platform == "darwin":
        # /Volumes/CLE/... : la cle est retenue par l'UUID de son volume
        parts = p.resolve().parts
        if len(parts) >= 3 and parts[1] == "Volumes":
            point = os.path.join("/", "Volumes", parts[2])
            cle = next((d for d in _mac_cles() if d["root"] == point), None)
            if cle:
                cfg["volumeSerial"] = cle["serial"]
                cfg["volumeLabel"]  = cle["label"]
                cfg["relativePath"] = "/".join(parts[3:])

    save_config(cfg)
    return {"ok": True, "config": cfg, "destination": resolve_destination(cfg)}


# ─── Fabrication de l'archive ─────────────────────────────────────────────────

def _iter_files(app_dir: Path, avec_backups: bool = True):
    """Tous les fichiers a sauvegarder, en ignorant le regenerable.
    avec_backups=False ecarte aussi les backups quotidiens des modules
    (users/<slug>/backups*), reglage « Dossier et contenu »."""
    for root, dirs, files in os.walk(app_dir):
        rel_root = Path(root).relative_to(app_dir)
        # Elague les dossiers exclus (comparaison sur le premier segment)
        dirs[:] = [d for d in dirs
                   if not (rel_root == Path(".") and d in EXCLUDED_DIRS)
                   and (avec_backups or not d.startswith("backups"))]
        for name in files:
            if (name.endswith((".tmp", ".part")) or name.startswith(".sauvegarde_")
                    or _est_archive(name)):
                continue
            full = Path(root) / name
            yield full, str(rel_root / name) if str(rel_root) != "." else name


def _archive_name(chiffre: bool = False) -> str:
    stamp = datetime.datetime.now().strftime("%Y-%m-%d_%Hh%M")
    return f"{ARCHIVE_PREFIX}{stamp}{EXT_CHIFFRE if chiffre else EXT_ZIP}"


class CleIllisible(Exception):
    """Le chiffrement est demande mais la cle gardee sur le PC ne se relit
    pas : on n'ecrit RIEN plutot qu'une archive en clair."""


def _cle(cfg: dict) -> Optional[bytes]:
    """Cle des archives, ou None si le chiffrement n'est pas active."""
    if not cfg.get("chiffrer"):
        return None
    try:
        cle = chiffrement.relire_cle(cfg.get("cleChiffree") or "")
        if len(cle) != 64:
            raise ValueError("taille")
        return cle
    except Exception as e:
        raise CleIllisible("Mot de passe des sauvegardes à ressaisir (Paramètres › Sauvegarde) : "
                           f"la clé gardée sur cet ordinateur est illisible ({e}).")


def _ecrire_zip(fichier, app_dir: Path, avec_backups: bool, reason: str) -> int:
    count = 0
    with zipfile.ZipFile(fichier, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for full, arc in _iter_files(app_dir, avec_backups):
            try:
                z.write(full, arcname=str(Path("Donnees") / arc))
                count += 1
            except Exception as e:
                print(f"[sauvegarde] fichier ignore {full}: {e}", flush=True)
        z.writestr("Donnees/_sauvegarde.txt", _manifest(count, reason))
    return count


def _ecrire_archive(tmp_target: Path, app_dir: Path, cfg: dict, cle: Optional[bytes],
                    reason: str) -> int:
    """Ecrit l'archive dans tmp_target : un zip, ou, avec une cle, le zip
    chiffre. Le zip en clair passe alors par un fichier temporaire du PC
    (efface a la fermeture), jamais par la destination : une cle retiree en
    route ne doit pas garder une copie lisible."""
    avec = bool(cfg.get("avecBackups", True))
    if cle is None:
        return _ecrire_zip(tmp_target, app_dir, avec, reason)
    with tempfile.TemporaryFile() as clair:
        count = _ecrire_zip(clair, app_dir, avec, reason)
        clair.seek(0)
        with open(tmp_target, "wb") as out:
            chiffrement.chiffrer_flux(clair, out, cle, bytes.fromhex(cfg["sel"]),
                                      int(cfg.get("iterations") or chiffrement.ITERATIONS))
    return count


def run_backup(reason: str = "manuel") -> dict:
    """Ecrit une archive dans la destination, puis applique la rotation."""
    cfg  = load_config()
    dest = resolve_destination(cfg)

    if not dest["ready"]:
        cfg["lastStatus"] = "absent"
        cfg["lastError"]  = dest["message"]
        save_config(cfg)
        return {"ok": False, "reason": dest["reason"], "error": dest["message"]}

    app_dir = storage.get_app_dir()
    out_dir = Path(dest["path"])
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return {"ok": False, "reason": "error", "error": f"Dossier inaccessible : {e}"}

    try:
        cle = _cle(cfg)
    except CleIllisible as e:
        cfg["lastStatus"] = "error"
        cfg["lastError"]  = str(e)
        save_config(cfg)
        return {"ok": False, "reason": "cle", "error": str(e)}

    target = out_dir / _archive_name(cle is not None)
    # On ecrit d'abord a cote, puis on renomme : une cle debranchee en plein
    # milieu ne laisse pas une archive tronquee portant un nom valide.
    tmp_target = out_dir / (target.name + ".part")

    count = 0
    try:
        count = _ecrire_archive(tmp_target, app_dir, cfg, cle, reason)
        os.replace(tmp_target, target)
    except Exception as e:
        for leftover in (tmp_target,):
            try:
                leftover.unlink()
            except Exception:
                pass
        cfg["lastStatus"] = "error"
        cfg["lastError"]  = str(e)
        save_config(cfg)
        return {"ok": False, "reason": "error", "error": str(e)}

    size = target.stat().st_size
    removed = _rotate(out_dir, int(cfg.get("keep") or 10))

    # Un reglage change pendant l'archive (quelques secondes) n'est pas annule
    cfg = load_config()
    cfg["lastBackupAt"]   = datetime.datetime.now().isoformat(timespec="seconds")
    cfg["lastBackupPath"] = str(target)
    cfg["lastStatus"]     = "ok"
    cfg["lastError"]      = ""
    save_config(cfg)

    res = {"ok": True, "path": str(target), "files": count, "chiffre": cle is not None,
           "size": size, "removed": removed, "reason": reason}
    if cfg.get("ejecter"):
        cle = _cle_de(str(out_dir))
        if cle:
            res["ejection"] = ejecter(cle["root"])
    return res


def _manifest(count: int, reason: str) -> str:
    users = storage.get_users_state()
    lignes = [
        "Sauvegarde Pilote",
        f"Date       : {datetime.datetime.now().isoformat(timespec='seconds')}",
        f"Origine    : {storage.get_app_dir()}",
        f"Fichiers   : {count}",
        f"Declencheur: {reason}",
        f"Utilisateurs : " + ", ".join(u.get("label", u.get("slug", "?"))
                                       for u in users.get("users", [])),
        "",
        "Pour restaurer : Pilote > Parametres > Sauvegarde > Restaurer,",
        "ou (archive .zip non chiffree) decompresser ce zip par-dessus le",
        "dossier Donnees, app fermee.",
    ]
    return "\n".join(lignes)


def _rotate(out_dir: Path, keep: int) -> int:
    """Ne garde que les `keep` archives les plus recentes."""
    if keep <= 0:
        return 0
    try:
        # Par nom, donc par date, .zip et .pilote melanges ; jamais le
        # fichier du bouton Televerser
        archives = sorted(p for p in out_dir.glob(f"{ARCHIVE_PREFIX}*")
                          if _est_archive(p.name) and p.name != TELEVERSEMENT)
    except Exception:
        return 0
    removed = 0
    while len(archives) > keep:
        old = archives.pop(0)
        try:
            old.unlink()
            removed += 1
        except Exception:
            pass
    return removed


# ─── Reglages de la cle : cles autorisees, dossier, ejection ─────────────────

def _dans_liste(d: dict, autorisees: list) -> bool:
    """La cle `d` figure-t-elle dans « Mes cles autorisees » ? Par son numero
    de serie (UUID sur Mac) ; une cle sans numero, par son nom."""
    for a in autorisees or []:
        s = (a.get("serial") or "").strip()
        if s:
            if d.get("serial") and s == d["serial"]:
                return True
        elif a.get("label") and (d.get("label") or "").lower() == a["label"].lower():
            return True
    return False


def _est_autorisee(d: dict, cfg: dict) -> bool:
    """Liste vide (reglage par defaut) : toute cle branchee convient."""
    autorisees = cfg.get("clesAutorisees") or []
    return not autorisees or _dans_liste(d, autorisees)


def _dossier_cle(cfg: dict) -> str:
    """Dossier du miroir sur la cle (« Dossier et contenu »), Pilote par defaut.
    Un seul nom, sans separateur ni caractere interdit : il reste a la racine
    de la cle."""
    nom = re.sub(r'[\\/:*?"<>|]', "", str(cfg.get("dossierCle") or "")).strip().strip(".").strip()
    return nom[:60] or "Pilote"


def _cle_de(chemin: str) -> Optional[dict]:
    """La cle branchee qui porte ce chemin, None pour un dossier du disque."""
    try:
        c = os.path.normcase(os.path.abspath(chemin))
    except Exception:
        return None
    for d in list_removable_drives():
        r = os.path.normcase(os.path.abspath(d["root"])).rstrip("\\/")
        if c == r or c.startswith(r + os.sep):
            return d
    return None


def ejecter(root: str) -> dict:
    """Ejecte une cle detectee (reglage « Ejecter apres copie »).
    Windows : verbe Ejecter de l'Explorateur ; Mac : diskutil eject."""
    import subprocess
    try:
        if sys.platform == "darwin":
            r = subprocess.run(["diskutil", "eject", root],
                               capture_output=True, text=True, timeout=30)
            if r.returncode == 0:
                return {"ok": True}
            return {"ok": False, "error": (r.stderr or r.stdout or "").strip()[:200]
                                          or "Éjection impossible"}
        if sys.platform == "win32":
            lecteur = os.path.splitdrive(root)[0].upper()
            if not re.fullmatch(r"[A-Z]:", lecteur):
                return {"ok": False, "error": "Lecteur inconnu"}
            ps = ("(New-Object -ComObject Shell.Application).Namespace(17)"
                  f".ParseName('{lecteur}').InvokeVerb('Eject')")
            subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                           capture_output=True, timeout=30,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            # Le verbe ne rend rien : la cle a-t-elle disparu de la liste ?
            import time
            for _ in range(10):
                if not any(d["root"].upper().startswith(lecteur) for d in list_removable_drives()):
                    return {"ok": True}
                time.sleep(0.5)
            return {"ok": False, "error": "La clé est encore utilisée : retire-la après "
                                          "l'avoir éjectée depuis l'Explorateur."}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}
    return {"ok": False, "error": "Éjection non prise en charge"}


# ─── Televersement direct (bouton de l'accueil) ───────────────────────────────
# Different des archives : ici on ecrit un MIROIR du dossier Donnees dans
# <cle>/Pilote/Donnees (« Pilote » : reglage dossierCle). Pas d'historique, pas
# de rotation — on ecrase, c'est une actualisation. Les deux mecanismes
# coexistent : le miroir pour recuperer ses fichiers tout de suite, les
# archives pour pouvoir remonter dans le temps.

def push_to_usb(root: str = None) -> dict:
    """
    Copie tout le dossier Donnees vers <cle>/Pilote/Donnees, en ecrasant.

    Sans `root`, la cle est choisie automatiquement s'il n'y en a qu'une ;
    s'il y en a plusieurs, on rend la liste pour que l'UI demande laquelle.
    Seules les cles autorisees comptent (liste vide : toutes).
    """
    cfg = load_config()
    toutes = list_removable_drives()
    drives = [d for d in toutes if _est_autorisee(d, cfg)]
    if not drives:
        if toutes:
            return {"ok": False, "reason": "no_drive",
                    "error": "Aucune de tes clés autorisées n'est branchée "
                             "(Paramètres → Sauvegarde)."}
        return {"ok": False, "reason": "no_drive",
                "error": "Aucune clé USB détectée. Branche-la puis réessaie."}

    if root:
        chosen = next((d for d in drives if d["root"].lower() == root.lower()), None)
        if not chosen:
            return {"ok": False, "reason": "no_drive",
                    "error": "Cette clé n'est plus branchée."}
    elif len(drives) == 1:
        chosen = drives[0]
    else:
        # Si une cle est deja configuree pour les archives, on la privilegie
        chosen = next((d for d in drives
                       if d["serial"] and d["serial"] == cfg.get("volumeSerial")), None)
        if not chosen:
            return {"ok": False, "reason": "choose", "drives": drives,
                    "error": "Plusieurs clés sont branchées."}

    app_dir = storage.get_app_dir()
    nom = chosen["letter"] or chosen["label"]      # Mac : pas de lettre
    try:
        cle = _cle(cfg)
    except CleIllisible as e:
        return {"ok": False, "reason": "cle", "error": str(e)}
    if cle is not None:
        return _televerser_chiffre(chosen, nom, cfg, cle, app_dir)
    dest = Path(chosen["root"]) / _dossier_cle(cfg) / "Donnees"
    try:
        dest.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return {"ok": False, "reason": "error",
                "error": f"Écriture impossible sur {nom} : {e}"}

    copies, octets, echecs = 0, 0, []
    for full, rel in _iter_files(app_dir, bool(cfg.get("avecBackups", True))):
        target = dest / rel
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            # copy2 preserve la date : un fichier inchange reste identique.
            # A cote puis renomme : une cle retiree en route ne laisse pas un
            # fichier tronque a la place du bon (DAT-18)
            partiel = target.with_name(target.name + ".part")
            shutil.copy2(full, partiel)
            os.replace(partiel, target)
            copies += 1
            octets += target.stat().st_size
        except Exception as e:
            echecs.append(f"{rel} ({e})")

    try:
        (dest / "_sauvegarde.txt").write_text(_manifest(copies, "téléversement"),
                                              encoding="utf-8")
    except Exception:
        pass

    cfg = load_config()
    cfg["lastPushAt"]   = datetime.datetime.now().isoformat(timespec="seconds")
    cfg["lastPushPath"] = str(dest)
    try:
        save_config(cfg)
    except Exception:
        pass

    res = {"ok": True, "path": str(dest), "files": copies, "size": octets,
           "drive": nom, "label": chosen["label"],
           "failed": echecs[:5], "failedCount": len(echecs)}
    if cfg.get("ejecter"):
        res["ejection"] = ejecter(chosen["root"])
    return res


def _televerser_chiffre(chosen: dict, nom: str, cfg: dict, cle: bytes, app_dir: Path) -> dict:
    """Bouton Televerser avec le chiffrement actif : une seule archive chiffree
    <cle>/<dossier>/Pilote_televersement.pilote, remplacee a chaque envoi, au
    lieu des fichiers en clair. Une ancienne copie en clair (Donnees/) n'est
    jamais effacee par Pilote : l'UI le signale (ancienMiroir)."""
    dossier = Path(chosen["root"]) / _dossier_cle(cfg)
    target = dossier / TELEVERSEMENT
    partiel = dossier / (TELEVERSEMENT + ".part")
    try:
        dossier.mkdir(parents=True, exist_ok=True)
        count = _ecrire_archive(partiel, app_dir, cfg, cle, "téléversement")
        os.replace(partiel, target)
    except Exception as e:
        try:
            partiel.unlink()
        except Exception:
            pass
        return {"ok": False, "reason": "error", "error": f"Écriture impossible sur {nom} : {e}"}
    cfg = load_config()
    cfg["lastPushAt"]   = datetime.datetime.now().isoformat(timespec="seconds")
    cfg["lastPushPath"] = str(target)
    try:
        save_config(cfg)
    except Exception:
        pass
    res = {"ok": True, "path": str(target), "files": count, "size": target.stat().st_size,
           "drive": nom, "label": chosen["label"], "chiffre": True,
           "ancienMiroir": (dossier / "Donnees").is_dir(),
           "failed": [], "failedCount": 0}
    if cfg.get("ejecter"):
        res["ejection"] = ejecter(chosen["root"])
    return res


def usb_state() -> dict:
    """Etat rapide pour l'accueil : y a-t-il une cle, et de quand date l'envoi ?
    Seules les cles autorisees sont comptees ; « autres » : les autres cles."""
    cfg = load_config()
    toutes = list_removable_drives()
    drives = [d for d in toutes if _est_autorisee(d, cfg)]
    # Destination dans un dossier (Google Drive, OneDrive...) et non sur une
    # cle : l'accueil parle alors de sauvegarde, pas de cle a brancher
    dossier = bool((cfg.get("destination") or "").strip()) and not (
        (cfg.get("volumeSerial") or "").strip() or (cfg.get("volumeLabel") or "").strip())
    return {"ok": True, "drives": drives, "count": len(drives), "dossier": dossier,
            "autres": len(toutes) - len(drives),
            "alerteJours": int(cfg.get("alerteJours", 7) or 0),
            "lastPushAt": cfg.get("lastPushAt", ""),
            "lastPushPath": cfg.get("lastPushPath", ""),
            "lastBackupAt": cfg.get("lastBackupAt", "")}


# ─── Inventaire ───────────────────────────────────────────────────────────────

def list_backups() -> dict:
    """Archives presentes dans la destination, la plus recente en tete."""
    dest = resolve_destination()
    if not dest["ready"]:
        return {"ok": False, "reason": dest["reason"], "error": dest["message"],
                "backups": []}
    out = []
    try:
        cfg = load_config()
        for p in sorted((x for x in Path(dest["path"]).glob(f"{ARCHIVE_PREFIX}*")
                         if _est_archive(x.name)), reverse=True):
            try:
                st = p.stat()
                ent = chiffrement.lire_entete(p) if p.name.endswith(EXT_CHIFFRE) else {}
                out.append({
                    "name": p.name,
                    "path": str(p),
                    "size": st.st_size,
                    "chiffre": bool(ent),
                    # Faite avec le mot de passe actuel : restaurable sans le taper
                    "cleConnue": bool(ent) and bool(cfg.get("chiffrer"))
                                 and ent.get("empreinte") == cfg.get("empreinte"),
                    "date": datetime.datetime.fromtimestamp(st.st_mtime)
                                    .isoformat(timespec="seconds"),
                })
            except Exception:
                pass
    except Exception as e:
        return {"ok": False, "reason": "error", "error": str(e), "backups": []}
    free, total = _disk_space(dest["path"])
    return {"ok": True, "backups": out, "path": dest["path"],
            "free": free, "total": total}


# ─── Sauvegarde automatique ───────────────────────────────────────────────────

def is_due(cfg: dict = None) -> bool:
    """La sauvegarde automatique doit-elle tourner maintenant ?"""
    cfg = cfg or load_config()
    if not cfg.get("auto"):
        return False
    freq = cfg.get("frequence") or "daily"
    if freq == "manual":
        return False
    last = cfg.get("lastBackupAt") or ""
    if not last:
        return True
    try:
        last_dt = datetime.datetime.fromisoformat(last)
    except Exception:
        return True
    # Jours de calendrier : avec 24 h glissantes, un lancement un peu plus tot
    # que la veille sautait la journee (une archive un jour sur deux, DAT-12)
    auj = datetime.date.today()
    if freq == "weekly":
        return auj.isocalendar()[:2] != last_dt.date().isocalendar()[:2]
    return last_dt.date() < auj


def auto_backup_if_due() -> dict:
    """
    Appelee au demarrage, a la fermeture ou toutes les 20 s selon le reglage
    « moment » (app.py). Silencieuse : si la cle n'est pas la, on ne derange
    pas l'utilisateur, on note juste le statut (une fois, pas a chaque essai).
    """
    cfg = load_config()
    if not is_due(cfg):
        return {"ok": False, "reason": "not_due"}
    dest = resolve_destination(cfg)
    if not dest["ready"]:
        if cfg.get("lastStatus") != "absent" or cfg.get("lastError") != dest["message"]:
            cfg["lastStatus"] = "absent"
            cfg["lastError"]  = dest["message"]
            save_config(cfg)
        return {"ok": False, "reason": dest["reason"]}
    return run_backup(reason="automatique")


def appliquer_reglages(patch: dict) -> dict:
    """Reglages modifiables depuis Parametres → Sauvegarde, valides un par un."""
    cfg = load_config()
    patch = patch or {}
    for k in ("auto", "avecBackups", "ejecter"):
        if k in patch:
            cfg[k] = bool(patch[k])
    if patch.get("frequence") in ("daily", "weekly", "manual"):
        cfg["frequence"] = patch["frequence"]
    if patch.get("moment") in ("demarrage", "branchement", "fermeture"):
        cfg["moment"] = patch["moment"]
    if "keep" in patch:
        try:
            cfg["keep"] = max(1, min(100, int(patch["keep"] or 10)))
        except (TypeError, ValueError):
            pass
    if "alerteJours" in patch:
        try:
            cfg["alerteJours"] = max(0, min(365, int(patch["alerteJours"] or 0)))
        except (TypeError, ValueError):
            pass
    if "dossierCle" in patch:
        cfg["dossierCle"] = _dossier_cle({"dossierCle": patch["dossierCle"]})
    if isinstance(patch.get("clesAutorisees"), list):
        cfg["clesAutorisees"] = [
            {"serial": str(a.get("serial") or "")[:64], "label": str(a.get("label") or "")[:64]}
            for a in patch["clesAutorisees"][:20]
            if isinstance(a, dict) and (a.get("serial") or a.get("label"))]
    save_config(cfg)
    return status()


# ─── Mot de passe des archives ───────────────────────────────────────────────

MDP_MIN = 8


def definir_mot_de_passe(mdp: str) -> dict:
    """Active le chiffrement (ou change de mot de passe). Les archives deja
    faites gardent leur ancien mot de passe (ou restent en clair)."""
    mdp = mdp or ""
    if len(mdp) < MDP_MIN:
        return {"ok": False, "error": f"Au moins {MDP_MIN} caractères."}
    sel = chiffrement.nouveau_sel()
    iterations = chiffrement.ITERATIONS
    cle = chiffrement.deriver(mdp, sel, iterations)
    secret = chiffrement.garder_cle(cle)
    if chiffrement.relire_cle(secret) != cle:
        return {"ok": False, "error": "La clé n'a pas pu être gardée sur cet ordinateur."}
    cfg = load_config()
    ancien = cfg.get("cleChiffree") or ""
    cfg.update({"chiffrer": True, "cleChiffree": secret, "sel": sel.hex(),
                "iterations": iterations, "empreinte": chiffrement.empreinte(cle)})
    save_config(cfg)
    if ancien and ancien != secret:
        try:
            chiffrement.oublier_cle(ancien)
        except Exception:
            pass
    return status()


def retirer_chiffrement() -> dict:
    """Les prochaines archives seront de nouveau des .zip lisibles."""
    cfg = load_config()
    ancien = cfg.get("cleChiffree") or ""
    cfg.update({"chiffrer": False, "cleChiffree": "", "sel": "", "empreinte": ""})
    save_config(cfg)
    if ancien:
        try:
            chiffrement.oublier_cle(ancien)
        except Exception:
            pass
    return status()


# ─── Restauration ─────────────────────────────────────────────────────────────

def _fusionner_users(contenu: bytes, cible: Path) -> None:
    """users.json de l'archive + utilisateurs actuels absents de l'archive :
    un utilisateur cree apres l'archive ne disparait pas de la liste (la fiche
    docs/sauvegarde-usb.md le promettait, le code le remplacait, DAT-09)."""
    import json as _json
    archive = _json.loads(contenu.decode("utf-8"))
    try:
        actuel = _json.loads(cible.read_text(encoding="utf-8"))
    except Exception:
        actuel = {"users": []}
    slugs = {u.get("slug") for u in archive.get("users", [])}
    for u in actuel.get("users", []):
        if u.get("slug") not in slugs:
            archive.setdefault("users", []).append(u)
    storage.save_users_state(archive)


def restore_from(zip_path: str, mdp: str = None) -> dict:
    """
    Restaure une archive par-dessus le dossier Donnees.

    Deux garde-fous :
      * l'archive est validee avant d'ecrire quoi que ce soit ;
      * une archive de securite de l'etat ACTUEL est ecrite a cote, pour
        pouvoir revenir en arriere si la restauration ne donne pas ce qu'on
        attendait.

    On ecrase fichier par fichier, sans vider le dossier au prealable : une
    archive incomplete ne doit jamais faire disparaitre un utilisateur qui
    n'y figure pas.
    """
    src = Path(zip_path)
    if not src.exists():
        return {"ok": False, "error": "Archive introuvable."}

    # Archive chiffree : dechiffree (et verifiee) dans un temporaire du PC
    # avant tout le reste. Sans mot de passe, celle du mot de passe actuel se
    # dechiffre avec la cle gardee ; une autre demande le sien (reason).
    source = src
    clair = None
    entete = chiffrement.lire_entete(src)
    if entete:
        cfg = load_config()
        cle = None
        if mdp:
            try:
                cle = chiffrement.deriver(mdp, bytes.fromhex(entete["sel"]), int(entete["iter"]))
            except Exception:
                return {"ok": False, "error": "En-tête de l'archive illisible."}
        elif cfg.get("chiffrer") and entete.get("empreinte") == cfg.get("empreinte"):
            try:
                cle = _cle(cfg)
            except CleIllisible:
                cle = None
        if cle is None:
            return {"ok": False, "reason": "mot_de_passe",
                    "error": "Cette archive est chiffrée : tape son mot de passe."}
        clair = tempfile.TemporaryFile()
        try:
            chiffrement.dechiffrer_flux(src, clair, cle)
        except chiffrement.MotDePasseIncorrect:
            clair.close()
            return {"ok": False, "reason": "mot_de_passe",
                    "error": "Mot de passe incorrect (ou archive abîmée)."}
        except Exception as e:
            clair.close()
            return {"ok": False, "error": f"Archive illisible : {e}"}
        source = clair
    try:
        return _restaurer(source, clair)
    finally:
        if clair is not None:
            clair.close()


def _restaurer(source, clair) -> dict:
    """Suite de restore_from : source est le chemin du zip, ou le fichier
    temporaire dechiffre (clair, remis au debut avant chaque lecture)."""
    def ouvrir():
        if clair is not None:
            clair.seek(0)
        return zipfile.ZipFile(source)

    try:
        with ouvrir() as z:
            bad = z.testzip()
            if bad:
                return {"ok": False, "error": f"Archive corrompue ({bad})."}
            members = [m for m in z.namelist() if m.startswith("Donnees/")]
            if not members:
                return {"ok": False,
                        "error": "Ce zip n'est pas une sauvegarde Pilote."}
    except zipfile.BadZipFile:
        return {"ok": False, "error": "Fichier illisible (zip invalide)."}
    except Exception as e:
        return {"ok": False, "error": str(e)}

    app_dir = storage.get_app_dir()

    # Filet de securite : l'etat actuel, avant d'ecraser
    safety = ""
    try:
        stamp = datetime.datetime.now().strftime("%Y-%m-%d_%Hh%M%S")
        safety_path = app_dir.parent / f"Pilote_avant-restauration_{stamp}.zip"
        with zipfile.ZipFile(safety_path, "w", zipfile.ZIP_DEFLATED) as z:
            for full, arc in _iter_files(app_dir):
                try:
                    z.write(full, arcname=str(Path("Donnees") / arc))
                except Exception:
                    pass
        safety = str(safety_path)
    except Exception as e:
        print(f"[sauvegarde] archive de securite KO : {e}", flush=True)
        # Promise par la confirmation : sans elle, on ne touche a rien (DAT-09)
        return {"ok": False, "error": f"Archive de sécurité impossible ({e}) : rien n'a été restauré."}

    written = 0
    try:
        with ouvrir() as z:
            for member in members:
                if member.endswith("/"):
                    continue
                rel = member[len("Donnees/"):]
                # Le manifeste est documentaire ; la config de sauvegarde
                # decrit la cle ACTUELLE et ne doit pas revenir en arriere
                # (sinon restaurer une vieille archive repointerait vers une
                # cle qu'on n'utilise peut-etre plus).
                if not rel or rel in ("_sauvegarde.txt", CONFIG_FILE):
                    continue
                # Refuse toute sortie du dossier (zip slip). Comparaison par
                # ancetres et non par prefixe de chaine : un dossier voisin
                # nomme "DonneesX" passait le test startswith et laissait une
                # archive piegee ecrire en dehors de Donnees/.
                app_r  = app_dir.resolve()
                target = (app_dir / rel).resolve()
                if app_r not in target.parents:
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                if rel == "users.json":
                    _fusionner_users(z.read(member), target)
                    written += 1
                    continue
                # Temporaire puis renommage : une cle retiree au milieu ne
                # laisse jamais un fichier tronque (DAT-09)
                partiel = target.with_name(target.name + ".restauration.tmp")
                with z.open(member) as fsrc, open(partiel, "wb") as fdst:
                    shutil.copyfileobj(fsrc, fdst)
                storage.remplacer(partiel, target)
                written += 1
    except Exception as e:
        return {"ok": False, "error": str(e), "safety": safety}

    return {"ok": True, "files": written, "safety": safety,
            "path": str(app_dir)}


# ─── Etat complet pour l'UI ───────────────────────────────────────────────────

def status() -> dict:
    """Tout ce dont l'ecran Parametres a besoin, en un appel."""
    cfg  = load_config()
    dest = resolve_destination(cfg)
    drives = list_removable_drives()
    for d in drives:     # « Mes cles autorisees » : la cle y figure-t-elle ?
        d["autorisee"] = _dans_liste(d, cfg.get("clesAutorisees") or [])
    cfg = dict(cfg)
    cfg.pop("cleChiffree", None)       # inutile a la page
    return {
        "ok": True,
        "config":      cfg,
        "destination": dest,
        "drives":      drives,
        "dossiers":    list_cloud_folders(),
        "due":       is_due(cfg),
        "appDir":      str(storage.get_app_dir()),
    }
