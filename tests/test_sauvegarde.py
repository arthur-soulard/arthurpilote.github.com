"""Sauvegarde vers un dossier ordinaire, comme un dossier Google Drive ou OneDrive
(`python -m unittest discover tests`).

Le dossier de Drive pour ordinateur n'est pas une clé : Pilote y écrit par son
chemin, sans numéro de série. On vérifie ici que tout le cycle marche avec un
tel dossier : archive automatique, rotation, puis restauration sur une
installation neuve (l'ordi qui a planté), qui n'a encore aucun réglage.

Toutes les écritures vont dans un dossier temporaire, jamais dans `Donnees/`.
"""
import datetime
import json
import shutil
import sys
import tempfile
import unittest
import zipfile
from unittest import mock
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "src"))

import storage  # noqa: E402

import sauvegarde  # noqa: E402

_TMP = Path(tempfile.mkdtemp(prefix="pilote_sauvegarde_"))
_DONNEES = _TMP / "installation" / "Donnees"


def _ecrire(chemin, texte):
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(texte, encoding="utf-8")


class DossierCommeDrive(unittest.TestCase):
    def setUp(self):
        # Remplacé le temps de chaque test seulement : test_donnees.py remplace
        # le même storage.get_app_dir par son propre dossier
        self._get_app_dir = storage.get_app_dir
        storage.get_app_dir = lambda: _DONNEES      # jamais les vraies données
        self.addCleanup(setattr, storage, "get_app_dir", self._get_app_dir)
        shutil.rmtree(_TMP, ignore_errors=True)
        _DONNEES.mkdir(parents=True)
        self.drive = _TMP / "Mon Drive" / "Pilote"
        _ecrire(_DONNEES / "users.json", json.dumps(
            {"active": "camille", "users": [{"slug": "camille", "label": "Camille"}]}))
        _ecrire(_DONNEES / "users" / "camille" / "pea_data.json", '{"positions": [1, 2]}')
        _ecrire(_DONNEES / "users" / "camille" / "sante.json", '{"pesees": [60]}')

    def test_destination_par_chemin(self):
        st = sauvegarde.set_destination(str(self.drive))
        self.assertTrue(st["ok"])
        self.assertTrue(self.drive.is_dir())             # créé s'il manquait
        self.assertEqual(st["config"]["volumeSerial"], "")   # pas une clé
        self.assertTrue(st["destination"]["ready"])
        self.assertTrue(sauvegarde.usb_state()["dossier"])

    def test_archive_automatique_une_fois_par_jour(self):
        sauvegarde.set_destination(str(self.drive))
        res = sauvegarde.auto_backup_if_due()
        self.assertTrue(res["ok"], res)
        self.assertEqual(len(list(self.drive.glob("Pilote_*.zip"))), 1)
        # Deuxième lancement le même jour : rien de plus
        self.assertEqual(sauvegarde.auto_backup_if_due()["reason"], "not_due")
        # Le lendemain : une nouvelle archive
        cfg = sauvegarde.load_config()
        cfg["lastBackupAt"] = (datetime.datetime.now() - datetime.timedelta(days=1)).isoformat(timespec="seconds")
        sauvegarde.save_config(cfg)
        self.assertTrue(sauvegarde.auto_backup_if_due()["ok"])

    def test_dossier_absent_rien_ecrit(self):
        """Drive pas lancé : son dossier n'existe pas, l'archive attend."""
        sauvegarde.set_destination(str(self.drive))
        shutil.rmtree(self.drive)
        res = sauvegarde.auto_backup_if_due()
        self.assertFalse(res["ok"])
        self.assertEqual(res["reason"], "absent")
        self.assertFalse(self.drive.exists())
        self.assertEqual(sauvegarde.load_config()["lastStatus"], "absent")

    def test_rotation(self):
        sauvegarde.set_destination(str(self.drive))
        sauvegarde.appliquer_reglages({"keep": 3})
        for i in range(5):
            _ecrire(self.drive / f"Pilote_2026-01-0{i + 1}_10h00.zip", "ancienne")
        self.assertTrue(sauvegarde.run_backup()["ok"])
        restantes = sorted(p.name for p in self.drive.glob("Pilote_*.zip"))
        self.assertEqual(len(restantes), 3)
        self.assertNotIn("Pilote_2026-01-01_10h00.zip", restantes)

    def test_restauration_sur_installation_neuve(self):
        sauvegarde.set_destination(str(self.drive))
        archive = sauvegarde.run_backup()["path"]
        with zipfile.ZipFile(archive) as z:
            self.assertIn("Donnees/users/camille/pea_data.json", z.namelist())

        # L'ordi a planté : installation neuve, rien dedans
        shutil.rmtree(_DONNEES)
        _DONNEES.mkdir(parents=True)
        st = sauvegarde.set_destination(str(self.drive))
        self.assertTrue(st["ok"])
        liste = sauvegarde.list_backups()
        self.assertEqual(len(liste["backups"]), 1)

        res = sauvegarde.restore_from(liste["backups"][0]["path"])
        self.assertTrue(res["ok"], res)
        self.assertEqual((_DONNEES / "users" / "camille" / "pea_data.json").read_text(encoding="utf-8"),
                         '{"positions": [1, 2]}')
        self.assertEqual((_DONNEES / "users" / "camille" / "sante.json").read_text(encoding="utf-8"),
                         '{"pesees": [60]}')
        users = json.loads((_DONNEES / "users.json").read_text(encoding="utf-8"))
        self.assertEqual([u["slug"] for u in users["users"]], ["camille"])
        # La destination de la nouvelle installation reste celle choisie
        self.assertEqual(sauvegarde.load_config()["destination"], str(self.drive))


class DossiersEnLigne(unittest.TestCase):
    """Google Drive et iCloud Drive trouves dans le dossier de l'utilisateur."""

    def setUp(self):
        self.home = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.home, ignore_errors=True)

    def _liste(self, plateforme):
        with mock.patch.object(sys, "platform", plateforme), \
             mock.patch.object(Path, "home", return_value=self.home):
            return sauvegarde.list_cloud_folders()

    def test_mac_google_drive_et_icloud(self):
        self.assertEqual(self._liste("darwin"), [])
        drive = self.home / "Library" / "CloudStorage" / "GoogleDrive-prenom@gmail.com" / "My Drive"
        icloud = self.home / "Library" / "Mobile Documents" / "com~apple~CloudDocs"
        drive.mkdir(parents=True)
        icloud.mkdir(parents=True)
        res = self._liste("darwin")
        self.assertEqual([(d["service"], d["root"]) for d in res],
                         [("Google Drive", str(drive)), ("iCloud", str(icloud))])

    @unittest.skipUnless(sys.platform == "win32", "ctypes.windll")
    def test_windows_miroir_et_icloud(self):
        (self.home / "Mon Drive").mkdir()
        (self.home / "iCloudDrive").mkdir()
        res = [d for d in self._liste("win32") if str(self.home) in d["root"]]
        self.assertEqual([(d["service"], d["label"]) for d in res],
                         [("Google Drive", "Mon Drive"), ("iCloud", "iCloud Drive")])


class RacineDuLecteurDrive(DossierCommeDrive):
    """G:\\ choisi tel quel : Google Drive y refuse tout fichier."""

    def _avec_drive(self):
        mon = self.drive / "Mon Drive"
        mon.mkdir(parents=True, exist_ok=True)
        lettre = str(self.drive)            # le dossier temporaire joue le lecteur G:
        faux = [{"root": str(mon), "letter": lettre, "label": "Mon Drive", "service": "Google Drive",
                 "free": 0, "total": 0}]
        return mon, mock.patch.object(sauvegarde, "list_cloud_folders", return_value=faux), \
            mock.patch.object(sauvegarde.os.path, "splitdrive", side_effect=lambda s: (
                (lettre, s[len(lettre):]) if s.upper().startswith(lettre.upper()) else ("", s)))

    def test_racine_mene_a_mon_drive(self):
        mon, p1, p2 = self._avec_drive()
        with p1, p2:
            res = sauvegarde.set_destination(str(self.drive))
        self.assertTrue(res["ok"], res)
        self.assertEqual(res["config"]["destination"], str(mon / "Sauvegardes Pilote"))

    def test_hors_de_mon_drive_refuse(self):
        mon, p1, p2 = self._avec_drive()
        with p1, p2:
            res = sauvegarde.set_destination(str(self.drive / "Autres ordinateurs"))
            self.assertFalse(res["ok"])
            self.assertIn("Mon Drive", res["error"])
            self.assertTrue(sauvegarde.set_destination(str(mon / "Pilote"))["ok"])


if __name__ == "__main__":
    unittest.main()
