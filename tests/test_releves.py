"""Tests des lecteurs de relevés : nombres et dates (bibliothèque standard).

Cas fictifs, écrits à la main avec leur bonne réponse : aucun vrai relevé dans
le dépôt (il est public).
"""
import csv
import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import cto  # noqa: E402
import releves  # noqa: E402


class Nombres(unittest.TestCase):
    def test_formats_francais_et_anglais(self):
        cas = {"1 234,56": 1234.56, "1.234,56": 1234.56, "1,234.56": 1234.56,
               "12,5": 12.5, "-3,20": -3.2, "(12,50)": -12.5}
        for txt, attendu in cas.items():
            with self.subTest(txt=txt):
                self.assertAlmostEqual(cto._nombre(txt), attendu, places=6)

    def test_vide(self):
        self.assertIsNone(cto._nombre(""))


class Dates(unittest.TestCase):
    def test_jour_mois(self):
        self.assertEqual(releves._date_fr("03/04/2025"), "2025-04-03")

    def test_ordre_americain_detecte(self):
        self.assertEqual(releves._ordre_dates(["03/26/2024", "04/02/2024"]), "mj")
        self.assertEqual(releves._ordre_dates(["26/03/2024", "02/04/2024"]), "jm")

    def test_dates_ambigues(self):
        self.assertTrue(releves._dates_ambigues(["03/04/2025", "05/06/2025"]))
        self.assertFalse(releves._dates_ambigues(["13/04/2025", "05/06/2025"]))

    def test_date_impossible_refusee(self):
        self.assertFalse(releves._date_fr("31/02/2025"))


# Export Trade Republic qui mélange le PEA et le compte-titres (colonne
# account_type : « PEA » ou « DEFAULT »), au format d'un vrai export, chiffres
# inventés. Sur le PEA, les frais d'un ordre sont plafonnés à 0,5 % et la taxe
# sur les transactions financières (0,4 %) est à part, comme dans le vrai.
_TR_ENTETE = ('"datetime","date","account_type","category","type","asset_class","name","symbol","shares",'
              '"price","amount","fee","tax","currency","original_amount","original_currency","fx_rate",'
              '"description","transaction_id","counterparty_name","counterparty_iban","payment_reference","mcc_code"')


def _tr(quand, compte, cat, typ, classe="", nom="", isin="", parts="", cours="", montant="", frais="",
        taxe="", desc="", trid=""):
    champs = [quand, quand[:10], compte, cat, typ, classe, nom, isin, parts, cours, montant, frais, taxe,
              "EUR", "", "", "", desc, trid, "", "", "", ""]
    return ",".join('"' + c + '"' for c in champs)


TR_PEA_CTO = "\n".join([
    _TR_ENTETE,
    _tr("2026-01-05T09:00:00Z", "PEA", "CASH", "TRANSFER_IN", montant="500.000000", trid="p1"),
    _tr("2026-01-06T10:00:00Z", "PEA", "TRADING", "BUY", "STOCK", "Air Liquide", "FR0000120073",
        "1.0000000000", "160.0000000000", "-160.00", "-0.80", "-0.64",
        "Buy trade FR0000120073 AIR LIQUIDE, quantity: 1", "p2"),
    _tr("2026-01-07T08:00:00Z", "PEA", "TRADING", "BUY", "FUND", "PEA Monde", "FR0011869353",
        "2.0000000000", "50.0000000000", "-100.00", "", "",
        "Savings plan execution FR0011869353 AMUNDI PEA MONDE, quantity: 2", "p3"),
    _tr("2026-01-07T08:30:00Z", "DEFAULT", "CASH", "CARD_TRANSACTION", nom="Boulangerie", montant="-4.20", trid="c1"),
    _tr("2026-01-08T11:00:00Z", "DEFAULT", "TRADING", "BUY", "STOCK", "Apple", "US0378331005",
        "0.5000000000", "200.0000000000", "-100.00", "-1.00", "",
        "Buy trade US0378331005 APPLE INC., quantity: 0.5", "c2"),
    _tr("2026-02-10T12:00:00Z", "PEA", "CASH", "DIVIDEND", "STOCK", "Air Liquide", "FR0000120073",
        "1.0000000000", "", "2.50", "", "", "Cash Dividend for ISIN FR0000120073", "p4"),
    _tr("2026-02-11T12:00:00Z", "PEA", "CASH", "PEA_MARKETING", montant="10.00", trid="p5"),
    _tr("2026-03-02T14:00:00Z", "DEFAULT", "TRADING", "SELL", "STOCK", "Apple", "US0378331005",
        "-0.5000000000", "210.0000000000", "105.00", "-1.00", "",
        "Sell trade US0378331005 APPLE INC., quantity: 0.5", "c3"),
    # Même titre acheté au même instant, au même cours, sur les deux comptes
    _tr("2026-03-05T09:30:00Z", "PEA", "TRADING", "BUY", "STOCK", "Schneider", "FR0000121972",
        "1.0000000000", "250.0000000000", "-250.00", "-1.00", "-1.00", "Buy trade FR0000121972 SCHNEIDER, quantity: 1", "p6"),
    _tr("2026-03-05T09:30:00Z", "DEFAULT", "TRADING", "BUY", "STOCK", "Schneider", "FR0000121972",
        "1.0000000000", "250.0000000000", "-250.00", "-1.00", "-1.00", "Buy trade FR0000121972 SCHNEIDER, quantity: 1", "c4"),
    # Division d'un titre tenu sur les deux comptes : deux paires à la même seconde
    _tr("2026-04-01T06:00:00Z", "PEA", "CORPORATE_ACTION", "SPLIT", "STOCK", "Schneider", "FR0000121972",
        "-1.0000000000", desc="Split", trid="p7"),
    _tr("2026-04-01T06:00:00Z", "PEA", "CORPORATE_ACTION", "SPLIT", "STOCK", "Schneider", "FR0000121972",
        "2.0000000000", desc="Split", trid="p8"),
    _tr("2026-04-01T06:00:00Z", "DEFAULT", "CORPORATE_ACTION", "SPLIT", "STOCK", "Schneider", "FR0000121972",
        "-1.0000000000", desc="Split", trid="c5"),
    _tr("2026-04-01T06:00:00Z", "DEFAULT", "CORPORATE_ACTION", "SPLIT", "STOCK", "Schneider", "FR0000121972",
        "2.0000000000", desc="Split", trid="c6"),
    _tr("2026-05-04T09:00:00Z", "PEA", "CASH", "TRANSFER_OUT", montant="-50.000000", trid="p9"),
]) + "\n"


class TradeRepublicPeaEtCto(unittest.TestCase):
    def setUp(self):
        self.r = cto.lire_csv_tr(TR_PEA_CTO)
        self.ops = {o["trId"]: o for o in self.r["operations"]}

    def test_chaque_operation_porte_son_compte(self):
        self.assertTrue(self.r["ok"])
        pea = sorted(t for t, o in self.ops.items() if o["compte"] == "PEA")
        cto_ = sorted(t for t, o in self.ops.items() if o["compte"] == "CTO")
        self.assertEqual(pea, ["p1", "p2", "p3", "p4", "p6", "p8", "p9"])
        self.assertEqual(cto_, ["c2", "c3", "c4", "c6"])

    def test_ordre_du_pea_frais_et_taxe(self):
        o = self.ops["p2"]
        self.assertEqual((o["type"], o["origine"], o["qty"], o["cours"], o["montant"], o["frais"], o["taxe"]),
                         ("Achat", "ordre", 1.0, 160.0, 160.0, 0.8, 0.64))
        self.assertEqual(self.ops["p3"]["origine"], "plan")
        self.assertEqual((self.ops["p4"]["type"], self.ops["p4"]["montant"]), ("Dividende", 2.5))

    def test_versements_du_pea_seulement(self):
        self.assertEqual((self.ops["p1"]["type"], self.ops["p1"]["montant"]), ("Versement", 500.0))
        self.assertEqual((self.ops["p9"]["type"], self.ops["p9"]["montant"]), ("Retrait", 50.0))
        # La carte du compte-titres reste ignorée, comme avant
        self.assertNotIn("c1", self.ops)
        self.assertEqual(self.r["ignores"]["especes"], 1)
        # Une ligne d'espèces du PEA d'un autre type est montrée, pas devinée
        self.assertEqual([(i["type"], i["compte"]) for i in self.r["inconnues"]], [("PEA_MARKETING", "PEA")])

    def test_meme_ordre_sur_les_deux_comptes_pas_fusionne(self):
        self.assertEqual((self.ops["p6"]["qty"], self.ops["c4"]["qty"]), (1.0, 1.0))

    def test_division_sur_les_deux_comptes(self):
        # Avant : quatre lignes à la même seconde, toutes rendues « inconnues »
        divs = [o for o in self.r["operations"] if o["type"] == "Division"]
        self.assertEqual(sorted((o["compte"], o["trIdAvant"], o["trId"], o["qtyAvant"], o["qty"]) for o in divs),
                         [("CTO", "c5", "c6", 1.0, 2.0), ("PEA", "p7", "p8", 1.0, 2.0)])

    def test_ancien_export_sans_colonne_account_type(self):
        lignes = [l.split('","') for l in TR_PEA_CTO.strip().split("\n")]
        sans = "\n".join('","'.join(c[:2] + c[3:]) for c in lignes) + "\n"
        r = cto.lire_csv_tr(sans)
        self.assertTrue(r["ok"])
        self.assertEqual({o["compte"] for o in r["operations"]}, {""})
        # Sans compte, les espèces restent ignorées : aucun versement deviné
        self.assertFalse([o for o in r["operations"] if o["type"] in ("Versement", "Retrait")])

    def test_via_releves_et_tableur(self):
        # Même lecture par l'entrée commune, et une fois le fichier passé par un tableur
        attendu = sorted((t, o["compte"]) for t, o in self.ops.items())
        r = releves.lire_fichier("Exportation de transactions.csv", TR_PEA_CTO.encode("utf-8"))
        self.assertEqual(sorted((o["trId"], o["compte"]) for o in r["operations"]), attendu)
        r = releves.lire_tableau(list(csv.reader(io.StringIO(TR_PEA_CTO))))
        self.assertEqual(sorted((o["trId"], o["compte"]) for o in r["operations"]), attendu)


# Cryptos du compte Trade Republic (section Crypto, 31/10/2026) : faux ISIN
# « XF000 » + symbole, chiffres inventés
TR_CRYPTO = "\n".join([
    _TR_ENTETE,
    _tr("2026-02-02T10:00:00Z", "DEFAULT", "TRADING", "BUY", "CRYPTO", "Bitcoin", "XF000BTC0017",
        "0.0020000000", "50000.0000000000", "-100.00", "-1.00", "", "Buy trade XF000BTC0017 Bitcoin, quantity: 0.002", "k1"),
    # Plan d'épargne sur l'Ethereum, sans asset_class : reconnu à son ISIN
    _tr("2026-02-16T08:00:00Z", "DEFAULT", "TRADING", "BUY", "", "Ethereum", "XF000ETH0019",
        "0.0100000000", "2500.0000000000", "-25.00", "", "",
        "Savings plan execution XF000ETH0019 Ethereum, quantity: 0.01", "k2"),
    _tr("2026-03-02T14:00:00Z", "DEFAULT", "TRADING", "SELL", "CRYPTO", "Bitcoin", "XF000BTC0017",
        "-0.0010000000", "60000.0000000000", "60.00", "-1.00", "", "Sell trade XF000BTC0017 Bitcoin, quantity: 0.001", "k3"),
    _tr("2026-03-05T09:30:00Z", "DEFAULT", "TRADING", "BUY", "STOCK", "Apple", "US0378331005",
        "0.5000000000", "200.0000000000", "-100.00", "-1.00", "", "Buy trade US0378331005 APPLE INC., quantity: 0.5", "c1"),
]) + "\n"


class TradeRepublicCrypto(unittest.TestCase):
    def setUp(self):
        self.r = cto.lire_csv_tr(TR_CRYPTO)
        self.ops = {o["trId"]: o for o in self.r["operations"]}

    def test_cryptos_reprises_dans_leur_compte(self):
        self.assertTrue(self.r["ok"])
        self.assertEqual(self.r["ignores"]["classe"], 0)
        self.assertEqual({t: (o["compte"], o["classe"]) for t, o in self.ops.items()},
                         {"k1": ("CRYPTO", "crypto"), "k2": ("CRYPTO", "crypto"),
                          "k3": ("CRYPTO", "crypto"), "c1": ("CTO", "action")})

    def test_chiffres_et_origine(self):
        o = self.ops["k1"]
        self.assertEqual((o["type"], o["qty"], o["cours"], o["montant"], o["frais"], o["alerte"]),
                         ("Achat", 0.002, 50000.0, 100.0, 1.0, ""))
        self.assertEqual(self.ops["k2"]["origine"], "plan")
        self.assertEqual((self.ops["k3"]["type"], self.ops["k3"]["qty"]), ("Vente", 0.001))


if __name__ == "__main__":
    unittest.main()
