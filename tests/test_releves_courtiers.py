"""Lecteurs ajoutés en 4.4.37 : Revolut, eToro, XTB (CSV), relevé de compte
Degiro et avis Keytrade (PDF). Données inventées, au format des vrais
documents (exemples d'Export-To-Ghostfolio et de Portfolio Performance).
Sans internet : les conversions passent par un faux cours de change."""
import base64
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import releves  # noqa: E402


def lire(nom, texte):
    return releves.lire([{"nom": nom, "b64": base64.b64encode(texte.encode("utf-8")).decode()}])


def faux_change(montant, devise, date):
    return None if montant is None else (montant if devise == "EUR" else round(montant / 1.10, 2))


@mock.patch.object(releves, "_vers_eur", side_effect=faux_change)
class Tableurs(unittest.TestCase):
    def test_revolut(self, _):
        r = lire("revolut.csv", "Date,Ticker,Type,Quantity,Price per share,Total Amount,Currency,FX Rate\n"
                                "2025-06-05T07:26:04.809Z,TSLA,BUY - MARKET,0.5,€100.00,€50,EUR,1.0000\n"
                                "2025-07-01T09:00:00Z,MSFT,DIVIDEND,,,$2.20,USD,1.1000\n"
                                "2025-07-02T09:00:00Z,,CASH TOP-UP,,,€200,EUR,1\n"
                                "2025-07-03T09:00:00Z,,CASH WITHDRAWAL,,,-$11.00,USD,1.1\n"
                                "2025-07-04T09:00:00Z,TSLA,STOCK SPLIT,1.5,,$0,USD,1\n")
        ops = {o["type"]: o for o in r["operations"]}
        self.assertEqual((ops["Achat"]["nom"], ops["Achat"]["qty"], ops["Achat"]["cours"], ops["Achat"]["montant"]),
                         ("TSLA", 0.5, 100.0, 50.0))
        self.assertEqual(ops["Dividende"]["montant"], 2.0)      # 2,20 $ / 1,10
        self.assertEqual(ops["Versement"]["montant"], 200.0)
        self.assertEqual(ops["Retrait"]["montant"], 10.0)
        self.assertEqual(len(r["inconnues"]), 1)               # la division, à saisir

    def test_un_tableau_en_devise_ne_plante_plus(self, conv):
        conv.side_effect = lambda m, d, date: None             # pas de cours de change
        r = lire("t.csv", "Date;Sens;ISIN;Quantité;Cours;Devise\n03/04/2025;Achat;US0378331005;2;150;USD\n")
        self.assertEqual(r["operations"], [])
        self.assertEqual(r["ignores"].get("conversion"), 1)

    def test_etoro(self, _):
        r = lire("etoro.csv", "Date,Type,Details,Amount,Units,Realized Equity Change,Realized Equity,Balance,"
                              "Position ID,Asset type,NWA\n"
                              "09/01/2024 15:37:16,Open Position,AMD/USD,110.00,0.5,0.00,0,0,1,Stocks,0\n"
                              "10/01/2024 15:37:16,Open Position,BTC,55.00,0.001,0.00,0,0,2,Crypto,0\n"
                              "11/01/2024 00:10:33,Dividend,NKE/USD,0.55,-,0.55,0,0,3,Stocks,0\n")
        ops = r["operations"]
        self.assertEqual([(o["type"], o["nom"], o["montant"]) for o in ops],
                         [("Achat", "AMD", 100.0), ("Dividende", "NKE", 0.5)])
        self.assertEqual(ops[0]["date"], "2024-01-09")

    def test_xtb(self, _):
        r = lire("xtb.csv", "ID;Type;Time;Symbol;Comment;Amount\n"
                            "1;Stocks/ETF purchase;12.04.2024 13:01:45;SPYL.DE;OPEN BUY 34/42.5 @ 11.7480;-399.43\n"
                            "2;Stocks/ETF sale;13.04.2024 11:42:37;GOOGL.US;CLOSE BUY 1 @ 122.34;111.25\n"
                            "3;Dividend;12.07.2024 13:01:17;XRAY.US;XRAY.US USD 0.1600/ SHR;2.56\n"
                            "4;Withholding tax;12.07.2024 13:01:17;XRAY.US;XRAY.US USD WHT 30%;-0.77\n"
                            "5;Deposit;12.04.2024 13:00:22;;deposit;500\n")
        ops = {o["type"]: o for o in r["operations"]}
        self.assertEqual((ops["Achat"]["nom"], ops["Achat"]["qty"], ops["Achat"]["cours"], ops["Achat"]["montant"]),
                         ("SPYL.DE", 34.0, 11.748, 399.43))
        self.assertEqual((ops["Vente"]["nom"], ops["Vente"]["cours"]), ("GOOGL", round(111.25, 6)))
        self.assertEqual(ops["Dividende"]["montant"], 1.79)    # 2,56 − 0,77 de retenue
        self.assertEqual(ops["Versement"]["montant"], 500.0)

    def test_freetrade_reste_au_lecteur_universel(self, _):
        r = lire("f.csv", "Title,Type,Timestamp,Account Currency,Total Amount,Buy / Sell,Ticker,ISIN,"
                          "Price per Share in Account Currency,Quantity,Price per Share,FX Rate\n")
        self.assertNotEqual(r.get("documents", [{}])[0].get("banque"), "Revolut")


class Pdf(unittest.TestCase):
    DEGIRO = """flatexDEGIRO Bank www.degiro.fr Account statement
Date Time Value date Product ISIN Description FX Change Balance
08-05-2026 06:31 07-05-2026 Operation de change - Crédit EUR 22,59 EUR 31,73
08-05-2026 06:31 07-05-2026 Opération de change - Débit 10,908 SEK -246,40 SEK 0,00
07-05-2026 07:10 06-05-2026 SOCIETE FICTIVE AB SE0000000001 Dividende SEK 352,00 SEK 246,40
07-05-2026 07:10 06-05-2026 SOCIETE FICTIVE AB SE0000000001 Impôts sur dividende SEK -105,60 SEK -105,60
17-07-2025 07:00 16-07-2025 FONDS FICTIF DE0000000002 Dividende EUR 2,07 EUR 521,41
17-07-2025 07:00 16-07-2025 FONDS FICTIF DE0000000002 Impôts sur dividende EUR -0,55 EUR 519,34
17-07-2025 07:00 16-07-2025 FONDS FICTIF DE0000000002 Dividende EUR 22,64 EUR 519,89
08-10-2025 16:58 08-10-2025 ETF FICTIF IE0000000003 Frais DEGIRO de courtage et/ou de parties tierces EUR -1,00 EUR 9 525,72
08-10-2025 16:58 08-10-2025 ETF FICTIF IE0000000003 Achat 6 ETF Fictif UCITS ETF@53,25 EUR (IE0000000003) EUR -319,50 EUR 9 526,72
08-10-2025 14:50 08-10-2025 Dépôt flatex EUR 9 500,00 EUR 9 525,72
01-08-2025 10:00 01-08-2025 OPTION FICTIVE DE0000000004 Achat 1 OPTION@45,00 EUR (DE0000000004) EUR -225,00 EUR 1,00
"""

    def test_degiro_releve_de_compte(self):
        r = releves.lire_texte_pdf(self.DEGIRO)
        self.assertEqual(r["banque"], "Degiro")
        ops = [(o["type"], o["isin"], o["montant"], o["frais"]) for o in r["operations"]]
        self.assertIn(("Dividende", "SE0000000001", 22.59, 0), ops)   # net en euros : ligne de change
        self.assertIn(("Dividende", "DE0000000002", 1.52, 0), ops)    # l'impôt va au dividende voisin
        self.assertIn(("Dividende", "DE0000000002", 22.64, 0), ops)
        self.assertIn(("Achat", "IE0000000003", 319.5, 1.0), ops)
        self.assertIn(("Versement", "", 9500.0, 0), ops)
        self.assertFalse(any(o[1] == "DE0000000004" for o in ops))      # option : écartée
        self.assertEqual(len(ops), 5)

    def test_keytrade(self):
        t = """Bordereau
Compte titres: 1234567
Numéro de réf. : 0000X0000/01
Achat 20 SOCIETE FICTIVE (BE0000000005) à 74,5 EUR
Type d' instrument: Actions
Date et heure d'exécution: 13/12/2021 16:24:15 CET
Montant brut - 1.490,00 EUR
Taxe boursière - 0,35% - 5,22 EUR
Courtage - 7,50 EUR
Débit 1.502,72 EUR
Keytrade Bank, succursale belge d'Arkéa Direct Bank SA (France)"""
        o = releves.lire_texte_pdf(t)["operations"][0]
        self.assertEqual((o["type"], o["date"], o["isin"], o["qty"], o["cours"], o["montant"], o["frais"], o["taxe"]),
                         ("Achat", "2021-12-13", "BE0000000005", 20.0, 74.5, 1490.0, 7.5, 5.22))


if __name__ == "__main__":
    unittest.main()
