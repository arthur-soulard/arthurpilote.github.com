"""Exports des balances connectées (src/balances.py).

Fichiers FICTIFS, faits sur le modèle des formats trouvés le 09/11/2026
(docs/modules/sante.md, « Exports des balances ») : aucune marque ne publie le
sien, d'où un lecteur qui reconnaît les colonnes par leur nom. Aucune vraie
pesée dans le dépôt.
"""
import datetime
import os
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "src"))

import balances  # noqa: E402

_TMP = Path(tempfile.mkdtemp(prefix="pilote_balances_"))


def _fichier(nom, texte, enc="utf-8"):
    p = _TMP / nom
    p.write_bytes(texte.encode(enc))
    return str(p)


def _zip(nom, membres):
    p = _TMP / nom
    with zipfile.ZipFile(p, "w") as z:
        for n, t in membres.items():
            z.writestr(n, t)
    return str(p)


class Exports(unittest.TestCase):
    def test_withings_masses_en_kg(self):
        p = _zip("data_CAM_123.zip", {
            "activities.csv": "Date,Steps\n2026-10-01,8000\n",
            "weight.csv": 'Date,"Weight (kg)","Fat mass (kg)","Bone mass (kg)","Muscle mass (kg)","Hydration (kg)",Comments\n'
                          '"2026-10-02 07:45:12",70.0,14.0,2.9,50.1,38.5,\n'
                          '"2026-10-01 07:40:00",70.4,,,,,\n'})
        r = balances.lire_export(p)
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["marque"], "Withings")
        self.assertEqual([m["date"] for m in r["mesures"]], ["2026-10-01", "2026-10-02"])
        m = r["mesures"][1]
        self.assertEqual((m["poids"], m["graisse"], m["eau"], m["masse_osseuse"], m["masse_musculaire"]),
                         (70.0, 20.0, 55.0, 2.9, 50.1))
        self.assertEqual(m["time"], "07:45")

    def test_withings_en_livres(self):
        p = _fichier("weight.csv", 'Date,"Weight (lb)","Fat mass (lb)"\n2026-10-02 07:45:12,154.32,30.86\n')
        m = balances.lire_export(p)["mesures"][0]
        self.assertEqual(m["poids"], 70.0)
        self.assertEqual(m["graisse"], 20.0)

    def test_zepp_life_timestamp(self):
        ts = int(datetime.datetime(2026, 9, 14, 7, 5).timestamp())
        p = _zip("ZeppLife_export.zip", {"20261101_123_MiFitness_data/BODY/BODY_1730000000.csv":
            "timestamp,weight,height,bmi,fatRate,bodyWaterRate,boneMass,metabolism,muscleRate,visceralFat,impedance\n"
            "%d,68.5,172,23.2,21.3,55.2,2.8,1480,52.3,7,480\n" % ts})
        r = balances.lire_export(p)
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["marque"], "Zepp Life / Mi Fit")
        m = r["mesures"][0]
        self.assertEqual((m["date"], m["time"]), ("2026-09-14", "07:05"))
        self.assertEqual((m["poids"], m["imc"], m["graisse"], m["eau"], m["metabolisme"], m["graisse_viscerale"]),
                         (68.5, 23.2, 21.3, 55.2, 1480, 7.0))
        self.assertNotIn("taux_musculaire", m)              # muscleRate : ambigu, laissé de côté
        self.assertNotIn("masse_musculaire", m)

    def test_eufy_date_et_heure_ensemble(self):
        p = _fichier("EufyLife_export.csv", "Time,WEIGHT (kg),BMI,BODY FAT %\n"
                                           "25/10/2026 07:30,69.8,23.1,20.5\n09/11/2026 07:31,69.5,23.0,20.2\n")
        r = balances.lire_export(p)
        self.assertEqual(r["marque"], "Eufy")
        self.assertFalse(r["dateAmbigue"])
        self.assertEqual([(m["date"], m["time"]) for m in r["mesures"]],
                         [("2026-10-25", "07:30"), ("2026-11-09", "07:31")])
        self.assertEqual(r["mesures"][0]["graisse"], 20.5)

    def test_csv_francais_point_virgule(self):
        p = _fichier("renpho.csv",
                     "Date;Heure;Poids(kg);IMC;Graisse corporelle(%);Eau corporelle(%);Masse musculaire(kg);"
                     "Masse osseuse(kg);Graisse viscérale;Métabolisme de base(kcal);Âge corporel;Protéine(%)\n"
                     "03/11/2026;07:12;70,1;23,4;19,8;56,0;53,2;2,9;7;1502;26;17,5\n", enc="cp1252")
        r = balances.lire_export(p)
        self.assertTrue(r["ok"], r)
        m = r["mesures"][0]
        self.assertEqual(m["date"], "2026-11-03")
        self.assertTrue(r["dateAmbigue"])                   # 03/11 ou 11/03 ? Signalé à la page
        self.assertEqual(balances.lire_export(p, "mj")["mesures"][0]["date"], "2026-03-11")
        self.assertEqual((m["poids"], m["eau"], m["masse_musculaire"], m["metabolisme"], m["age_corporel"], m["proteine"]),
                         (70.1, 56.0, 53.2, 1502, 26, 17.5))

    def test_dates_americaines(self):
        p = _fichier("scale.csv", "Date,Weight (lb),Body Fat (%)\n12/31/2025 6:58 AM,155.0,21\n01/02/2026 7:10 PM,154.2,20.8\n")
        r = balances.lire_export(p)
        self.assertEqual([(m["date"], m["time"]) for m in r["mesures"]],
                         [("2025-12-31", "06:58"), ("2026-01-02", "19:10")])

    def test_apple_sante(self):
        xml = ('<?xml version="1.0" encoding="UTF-8"?>\n<HealthData locale="fr_FR">'
               '<Record type="HKQuantityTypeIdentifierBodyMass" sourceName="Balance" unit="kg" '
               'startDate="2026-11-02 07:20:11 +0100" endDate="2026-11-02 07:20:11 +0100" value="69.9"/>'
               '<Record type="HKQuantityTypeIdentifierBodyFatPercentage" sourceName="Balance" unit="%" '
               'startDate="2026-11-02 07:20:11 +0100" endDate="2026-11-02 07:20:11 +0100" value="0.204"/>'
               '<Record type="HKQuantityTypeIdentifierStepCount" sourceName="iPhone" unit="count" '
               'startDate="2026-11-02 08:00:00 +0100" endDate="2026-11-02 08:10:00 +0100" value="900"/>'
               '<Record type="HKQuantityTypeIdentifierBodyMass" sourceName="Balance" unit="lb" '
               'startDate="2026-11-03 07:21:00 +0100" endDate="2026-11-03 07:21:00 +0100" value="154.0"/>'
               '</HealthData>')
        p = _zip("export.zip", {"apple_health_export/export.xml": xml,
                                "apple_health_export/export_cda.xml": "<x/>"})
        r = balances.lire_export(p)
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["marque"], "Apple Santé")
        self.assertEqual(r["mesures"][0], {"date": "2026-11-02", "time": "07:20", "poids": 69.9, "graisse": 20.4})
        self.assertEqual(r["mesures"][1]["poids"], 69.9)

    def test_une_pesee_par_jour_la_plus_complete(self):
        p = _fichier("j.csv", "Date,Weight,Fat\n2026-11-01 20:00,70.5,\n2026-11-01 07:00,70.0,20\n"
                             "2026-11-01 06:00,70.2,\n")
        ms = balances.lire_export(p)["mesures"]
        self.assertEqual(len(ms), 1)
        self.assertEqual((ms[0]["time"], ms[0]["poids"]), ("07:00", 70.0))

    def test_valeurs_hors_bornes_laissees(self):
        p = _fichier("b.csv", "Date,Weight (kg),Body Fat (%)\n2026-11-01,70,95\n2026-11-02,0,20\n")
        r = balances.lire_export(p)
        self.assertEqual(len(r["mesures"]), 1)
        self.assertNotIn("graisse", r["mesures"][0])
        self.assertEqual(r["ignorees"], 1)

    def test_sans_poids_refuse(self):
        r = balances.lire_export(_fichier("c.csv", "Date,Steps\n2026-11-01,9000\n"))
        self.assertFalse(r["ok"])
        self.assertIn("poids", r["error"])

    def test_entete_apres_une_ligne_de_titre(self):
        p = _fichier("g.csv", "Body\nDate,Time,Weight,BMI,Fat\n2026-11-01,07:00,70.0,23.0,20.0\n")
        self.assertEqual(balances.lire_export(p)["mesures"][0]["imc"], 23.0)


def tearDownModule():
    shutil.rmtree(_TMP, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
