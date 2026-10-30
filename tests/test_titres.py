"""Catalogue des titres de l'import (src/titres_connus.py, 4.4.37) et refus
des PDF (releves.py). Sans internet."""
import base64
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import releves        # noqa: E402
import titres_connus  # noqa: E402


class NomsDesBanques(unittest.TestCase):
    def isin(self, nom):
        r = titres_connus.par_nom(nom)
        return r[0] if len(r) == 1 else r

    def test_noms_que_yahoo_ne_trouvait_pas(self):
        self.assertEqual(self.isin("CIE DE SAINT-GOBAIN"), "FR0000125007")
        self.assertEqual(self.isin("BNP PARIBAS ACTIONS A"), "FR0000131104")
        self.assertEqual(self.isin("BNP PARIBAS ACT.A"), "FR0000131104")
        self.assertEqual(self.isin("ENGIE"), "FR0010208488")
        self.assertEqual(self.isin("TOTALENERGIES SE"), "FR0000120271")
        self.assertEqual(self.isin("LVMH MOET HENNESSY"), "FR0000121014")
        self.assertEqual(self.isin("MICHELIN (CGDE)"), "FR001400AJ45")

    def test_le_nom_le_plus_long_l_emporte(self):
        self.assertEqual(self.isin("DASSAULT SYSTEMES SE"), "FR0014003TT8")
        self.assertEqual(self.isin("DASSAULT AVIATION"), "FR0014004L86")
        self.assertEqual(self.isin("SIEMENS ENERGY AG"), "DE000ENER6Y0")

    def test_actions_americaines(self):
        self.assertEqual(self.isin("NVIDIA CORP"), "US67066G1040")
        self.assertEqual(self.isin("META PLATFORMS INC"), "US30303M1027")
        # Deux titres conviennent autant : les deux, la vérification par les prix tranche
        self.assertEqual(set(titres_connus.par_nom("ALPHABET INC")), {"US02079K3059", "US02079K1079"})

    def test_un_fonds_n_est_jamais_une_action(self):
        self.assertEqual(titres_connus.par_nom("AXA IM NASDAQ 100 UCITS ETF"), [])
        self.assertEqual(titres_connus.par_nom("BNP PARIBAS EASY S&P 500 UCITS ETF"), [])

    def test_inconnu(self):
        self.assertEqual(titres_connus.par_nom("XYZZY TRUC MACHIN"), [])
        self.assertEqual(titres_connus.par_nom(""), [])


class Cotations(unittest.TestCase):
    def test_place_d_origine_puis_xetra(self):
        c = titres_connus.cotations("FR0000125007")
        self.assertEqual(c[0], "SGO.PA")
        self.assertIn("GOB.DE", c)
        self.assertEqual(titres_connus.cotations("US0378331005"), ["APC.DE"])
        self.assertEqual(titres_connus.cotations("fr0010208488")[0], "ENGI.PA")

    def test_listes_fabriquees(self):
        from titres_listes import TITRES
        self.assertGreater(len(TITRES), 5000)
        isins = {t[0] for t in TITRES}
        self.assertGreater(sum(i.startswith("US") for i in isins), 700)
        for isin, sym, nom, genre in TITRES:
            self.assertRegex(isin, r"^[A-Z]{2}[A-Z0-9]{9}\d$")
            self.assertRegex(sym, r"^[A-Z0-9-]+\.(PA|AS|BR|LS|MI|IR|DE)$")
            self.assertIn(genre, ("action", "etf", "etc", "etn"))

    def test_catalogue_a_la_main(self):
        isins = [t[0] for t in titres_connus.TITRES]
        self.assertEqual(len(isins), len(set(isins)), "ISIN en double")


class PlusDePdf(unittest.TestCase):
    def test_pdf_refuse_avec_un_message(self):
        r = releves.lire([{"nom": "avis.pdf", "b64": base64.b64encode(b"%PDF-1.4\n...").decode()}])
        self.assertEqual(r["operations"], [])
        self.assertIn("CSV", r["documents"][0]["erreur"])


if __name__ == "__main__":
    unittest.main()
