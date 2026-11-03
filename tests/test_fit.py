"""Tests du lecteur de fichiers .fit (`python -m unittest discover -s tests`).

Les fichiers sont fabriques ici d'apres la description du format dans le FIT
SDK de Garmin (en-tete de 14 octets, definitions, messages file_id, session et
activity), en petit et en grand boutiste, avec un champ developpeur et un
en-tete compresse : ce que les montres ecrivent vraiment.
"""
import struct
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "src"))

import fit  # noqa: E402

# 03/11/2026 18:05:00 UTC en secondes FIT
DEBUT = 1793729100 - fit.EPOQUE_FIT


def _definition(local, numero, champs, gros=False, dev=None):
    o = ">" if gros else "<"
    b = bytes([0x40 | (0x20 if dev else 0) | local, 0, 1 if gros else 0]) + struct.pack(o + "H", numero)
    b += bytes([len(champs)]) + b"".join(bytes([n, struct.calcsize(f), t]) for n, f, t, _ in champs)
    if dev:
        b += bytes([len(dev)]) + b"".join(bytes([n, t, 0]) for n, t in dev)
    return b


def _donnees(local, champs, gros=False, dev=b""):
    o = ">" if gros else "<"
    return bytes([local]) + b"".join(struct.pack(o + f, v) for _, f, _, v in champs) + dev


def _fichier(messages: bytes) -> bytes:
    entete = struct.pack("<BBHI4sH", 14, 0x20, 2100, len(messages), b".FIT", 0)
    return entete + messages + b"\x00\x00"


def _session(sport=1, sous_sport=0, chrono_s=3725.4, metres=10520.7, d_plus=412, fc=151, kcal=812,
             bassin=None, debut=DEBUT):
    c = [(253, "I", 0x86, debut + 4000), (2, "I", 0x86, debut), (5, "B", 0x00, sport), (6, "B", 0x00, sous_sport),
         (7, "I", 0x86, round(chrono_s * 1000) + 30000), (8, "I", 0x86, round(chrono_s * 1000)),
         (9, "I", 0x86, round(metres * 100)), (11, "H", 0x84, kcal), (16, "B", 0x02, fc),
         (22, "H", 0x84, d_plus)]
    if bassin:
        c.append((44, "H", 0x84, bassin * 100))
    return c


class TestFit(unittest.TestCase):

    def test_course_coros(self):
        fid = [(0, "B", 0x00, 4), (1, "H", 0x84, 294)]
        ses = _session()
        act = [(253, "I", 0x86, DEBUT + 4000), (5, "I", 0x86, DEBUT + 4000 + 3600)]   # UTC+1
        b = (_definition(0, 0, fid) + _donnees(0, fid)
             + _definition(1, 18, ses) + _donnees(1, ses)
             + _definition(2, 34, act) + _donnees(2, act))
        [s] = fit.seances(_fichier(b))
        self.assertEqual(s["date"], "2026-11-03")
        self.assertEqual(s["time"], "19:05")                  # heure locale de la montre
        self.assertEqual((s["sport"], s["duration"], s["distance"], s["elevation"]), ("course", 62, 10.52, 412))
        self.assertEqual((s["fcMoy"], s["kcal"], s["marque"]), (151, 812, "Coros"))
        self.assertEqual(len(s["fitId"]), 16)
        # Le même fichier relu donne le même identifiant (pas de doublon)
        self.assertEqual(fit.seances(_fichier(b))[0]["fitId"], s["fitId"])

    def test_gros_boutiste_champ_developpeur_et_entete_compresse(self):
        ses = _session(sport=5, metres=1500, d_plus=0, bassin=25)
        b = (_definition(3, 18, ses, gros=True, dev=[(0, 2)])
             + bytes([0x80 | (3 << 5) | 5]) + _donnees(3, ses, gros=True, dev=b"\x07\x07")[1:])
        [s] = fit.seances(_fichier(b))
        self.assertEqual((s["sport"], s["distance"], s["lieu"]), ("natation", 1500, "25"))

    def test_muscu_et_valeurs_invalides(self):
        ses = _session(sport=10, sous_sport=20, metres=0, d_plus=0xFFFF, fc=0xFF, kcal=0)
        [s] = fit.seances(_fichier(_definition(0, 18, ses) + _donnees(0, ses)))
        self.assertEqual(s["sport"], "muscu")
        self.assertNotIn("fcMoy", s)                          # 0xFF : « pas de mesure » dans le SDK
        self.assertNotIn("kcal", s)

    def test_multisport_et_sport_inconnu(self):
        a, b_ = _session(sport=2, metres=40000), _session(sport=99, debut=DEBUT + 5000)
        b = _definition(0, 18, a) + _donnees(0, a) + _donnees(0, b_)
        l = fit.seances(_fichier(b))
        self.assertEqual([s["sport"] for s in l], ["velo", "autre"])
        self.assertNotEqual(l[0]["fitId"], l[1]["fitId"])

    def test_fichiers_refuses(self):
        for octets in (b"", b"pas un fit du tout", _fichier(b"")):
            with self.assertRaises(fit.ErreurFit):
                fit.seances(octets)
        # Message sans définition : abîmé, pas de plantage
        with self.assertRaises(fit.ErreurFit):
            fit.seances(_fichier(b"\x05\x00\x00"))
        # Coupé au milieu : on lit ce qui est entier, sans plantage
        ses = _session()
        coupe = _fichier(_definition(0, 18, ses) + _donnees(0, ses))[:30]
        with self.assertRaises(fit.ErreurFit):
            fit.seances(coupe)


if __name__ == "__main__":
    unittest.main()
