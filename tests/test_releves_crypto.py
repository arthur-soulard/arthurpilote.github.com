"""Tests des lecteurs d'exports crypto (releves_crypto.py).

Exports fictifs écrits à la main d'après les colonnes de chaque plateforme,
avec leur bonne réponse ; cours des cryptos fixés à l'avance (pas de réseau).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import releves  # noqa: E402
import releves_crypto as rc  # noqa: E402

D = "2024-01-05"
COURS = {"BTC": 50000.0, "ETH": 2000.0, "BNB": 300.0, "USDT": 0.9, "DOT": 6.0, "CRO": 0.08}


def lire(lignes):
    rc._cours_cache.clear()
    for sym, c in COURS.items():
        rc._cours_cache[(sym, D)] = c
    releves._fx_cache[("USD", D)] = 1.1   # 1 € = 1,10 $
    return releves.lire_tableau([[str(x) for x in l] for l in lignes])


def resume(r):
    """(type, nom, quantité, montant, frais, origine) de chaque opération."""
    return [(o["type"], o["nom"], round(o["qty"], 8), o["montant"], o["frais"], o["origine"]) for o in r["operations"]]


class Symboles(unittest.TestCase):
    def test_kraken_et_staking(self):
        for brut, attendu in {"XXBT": "BTC", "ZEUR": "EUR", "XETH": "ETH", "XBT": "BTC", "XDG": "DOGE",
                              "ETH2.S": "ETH", "DOT.S": "DOT", "SOL03.S": "SOL", "ADA.M": "ADA", "btc": "BTC"}.items():
            with self.subTest(brut=brut):
                self.assertEqual(rc.symbole(brut), attendu)

    def test_reconnaitre_une_crypto(self):
        self.assertTrue(rc.est_crypto("Bitcoin"))
        self.assertTrue(rc.est_crypto("ETH"))
        self.assertFalse(rc.est_crypto("Air Liquide"))


class Binance(unittest.TestCase):
    def test_releve_de_compte(self):
        r = lire([
            ["User_ID", "UTC_Time", "Account", "Operation", "Coin", "Change", "Remark"],
            # achat de BTC en euros, frais pris sur le BTC reçu
            ["1", "2024-01-05 10:00:00", "Spot", "Transaction Spend", "EUR", "-100", ""],
            ["1", "2024-01-05 10:00:00", "Spot", "Transaction Buy", "BTC", "0.002", ""],
            ["1", "2024-01-05 10:00:00", "Spot", "Transaction Fee", "BTC", "-0.000002", ""],
            # USDT -> ETH, frais payés en BNB
            ["1", "2024-01-05 11:00:00", "Spot", "Transaction Sold", "USDT", "-200", ""],
            ["1", "2024-01-05 11:00:00", "Spot", "Transaction Revenue", "ETH", "0.09", ""],
            ["1", "2024-01-05 11:00:00", "Spot", "Transaction Fee", "BNB", "-0.001", ""],
            ["1", "2024-01-05 12:00:00", "Earn", "Simple Earn Flexible Interest", "ETH", "0.001", ""],
            ["1", "2024-01-05 12:00:00", "Spot", "Simple Earn Flexible Subscription", "ETH", "-0.05", ""],
            ["1", "2024-01-05 13:00:00", "Spot", "Deposit", "BTC", "0.5", ""],
            ["1", "2024-01-05 13:00:00", "Spot", "Deposit", "EUR", "500", ""],
        ])
        self.assertEqual(r["banque"], "Binance")
        self.assertEqual(resume(r), [
            ("Achat", "BTC", 0.001998, 99.9, 0.1, "ordre"),
            ("Vente", "BNB", 0.001, 0.3, 0.0, "ordre"),
            ("Achat", "ETH", 0.09, 180.0, 0.3, "ordre"),
            ("Vente", "USDT", 200.0, 180.0, 0.0, "ordre"),
            ("Achat", "ETH", 0.001, 2.0, 0.0, "offert"),
            ("Versement", "", 0.0, 500.0, 0.0, "especes"),
        ])
        self.assertTrue(all(o["compte"] == "CRYPTO" and (o["classe"] == "crypto" or o["type"] == "Versement")
                            for o in r["operations"]))
        self.assertEqual(r["ignores"].get("transferts_crypto"), 1)

    def test_historique_des_ordres(self):
        r = lire([
            ["Date(UTC)", "Pair", "Side", "Price", "Executed", "Amount", "Fee"],
            ["2024-01-05 10:00:00", "BTCEUR", "BUY", "50000", "0.00200000BTC", "100.00EUR", "0.10EUR"],
            ["2024-01-05 11:00:00", "BTCEUR", "SELL", "50000", "0.00100000BTC", "50.00EUR", "0.05EUR"],
        ])
        self.assertEqual(resume(r), [("Achat", "BTC", 0.002, 100.0, 0.1, "ordre"),
                                     ("Vente", "BTC", 0.001, 50.0, 0.05, "ordre")])


class Coinbase(unittest.TestCase):
    def test_export_avec_lignes_de_titre(self):
        r = lire([
            ["Transactions"],
            ["User", "Camille", "xxx"],
            ["ID", "Timestamp", "Transaction Type", "Asset", "Quantity Transacted", "Price Currency",
             "Price at Transaction", "Subtotal", "Total (inclusive of fees and/or spread)", "Fees and/or Spread", "Notes"],
            ["a1", "2024-01-05 10:00:00 UTC", "Buy", "BTC", "0.002", "EUR", "€50,000.00", "€100.00", "€101.49", "€1.49",
             "Bought 0.002 BTC for €101.49 EUR"],
            ["a2", "2024-01-05 11:00:00 UTC", "Sell", "BTC", "-0.001", "EUR", "€50,000.00", "€50.00", "€49.25", "€0.75",
             "Sold 0.001 BTC for €49.25 EUR"],
            ["a3", "2024-01-05 12:00:00 UTC", "Convert", "BTC", "-0.0004", "EUR", "€50,000.00", "€20.00", "€20.00", "€0.00",
             "Converted 0.0004 BTC to 0.01 ETH"],
            ["a4", "2024-01-05 13:00:00 UTC", "Staking Income", "ETH", "0.0005", "EUR", "€2,000.00", "€1.00", "€1.00", "€0.00", ""],
            ["a5", "2024-01-05 14:00:00 UTC", "Send", "BTC", "-0.0001", "EUR", "€50,000.00", "€5.00", "€5.00", "€0.00", ""],
        ])
        self.assertEqual(r["banque"], "Coinbase")
        self.assertEqual(resume(r), [
            ("Achat", "BTC", 0.002, 100.0, 1.49, "ordre"),
            ("Vente", "BTC", 0.001, 50.0, 0.75, "ordre"),
            ("Achat", "ETH", 0.01, 20.0, 0.0, "ordre"),
            ("Vente", "BTC", 0.0004, 20.0, 0.0, "ordre"),
            ("Achat", "ETH", 0.0005, 1.0, 0.0, "offert"),
        ])
        self.assertEqual(r["ignores"].get("transferts_crypto"), 1)

    def test_reception_comptee_au_cours_du_jour(self):
        # Un compte qui n'a que des réceptions (export d'un utilisateur, 01/11/2026)
        r = lire([
            ["ID", "Timestamp", "Transaction Type", "Asset", "Quantity Transacted", "Price Currency",
             "Price at Transaction", "Subtotal", "Total (inclusive of fees and/or spread)", "Fees and/or Spread", "Notes"],
            ["r1", "2024-01-05 10:00:00 UTC", "Receive", "SOL", "0.5", "USD", "$110.00", "$55.00", "$55.00", "$0.00",
             "Received 0.5 SOL from an external account"],
        ])
        self.assertEqual(resume(r), [("Achat", "SOL", 0.5, 50.0, 0.0, "recu")])
        self.assertTrue(r["operations"][0]["alerte"])
        self.assertFalse(r["ignores"].get("transferts_crypto"))


class Kraken(unittest.TestCase):
    def test_ledgers(self):
        r = lire([
            ["txid", "refid", "time", "type", "subtype", "aclass", "asset", "amount", "fee", "balance"],
            ["L1", "T1", "2024-01-05 10:00:00", "trade", "", "currency", "ZEUR", "-100.0000", "0.2600", "0"],
            ["L2", "T1", "2024-01-05 10:00:00", "trade", "", "currency", "XXBT", "0.0020000000", "0", "0.002"],
            ["L3", "S1", "2024-01-05 12:00:00", "staking", "", "currency", "DOT.S", "0.5", "0", "0.5"],
            ["L4", "S2", "2024-01-05 12:00:00", "transfer", "spottostaking", "currency", "DOT", "-10", "0", "0"],
            ["L5", "D1", "2024-01-05 09:00:00", "deposit", "", "currency", "ZEUR", "500", "0", "500"],
        ])
        self.assertEqual(r["banque"], "Kraken")
        self.assertEqual(resume(r), [
            ("Versement", "", 0.0, 500.0, 0.0, "especes"),
            ("Achat", "BTC", 0.002, 100.0, 0.26, "ordre"),
            ("Achat", "DOT", 0.5, 3.0, 0.0, "offert"),
        ])

    def test_trades(self):
        r = lire([
            ["txid", "ordertxid", "pair", "time", "type", "ordertype", "price", "cost", "fee", "vol", "margin", "misc", "ledgers"],
            ["T1", "O1", "XXBTZEUR", "2024-01-05 10:00:00", "buy", "market", "50000", "100", "0.4", "0.002", "0", "", ""],
        ])
        self.assertEqual(resume(r), [("Achat", "BTC", 0.002, 100.0, 0.4, "ordre")])


class Bitpanda(unittest.TestCase):
    def test_cryptos_seules(self):
        entete = ["Transaction ID", "Timestamp", "Transaction Type", "In/Out", "Amount Fiat", "Fiat", "Amount Asset",
                  "Asset", "Asset market price", "Asset market price currency", "Asset class", "Product ID", "Fee",
                  "Fee asset", "Spread", "Spread Currency", "Tax Fiat"]
        r = lire([
            ["Disclaimer: All data is without guarantee"], ["Camille"], entete,
            ["b1", "2024-01-05T10:00:00+01:00", "buy", "outgoing", "100.00", "EUR", "0.002", "BTC", "50000", "EUR",
             "Cryptocurrency", "1", "0", "BTC", "-", "-", "0"],
            ["b2", "2024-01-05T11:00:00+01:00", "buy", "outgoing", "50.00", "EUR", "0.25", "AAPL", "200", "EUR",
             "Stock (derivative)", "2", "0", "AAPL", "-", "-", "0"],
            ["b3", "2024-01-05T12:00:00+01:00", "transfer", "incoming", "2.00", "EUR", "0.001", "ETH", "2000", "EUR",
             "Cryptocurrency", "3", "0", "ETH", "-", "-", "0"],
        ])
        self.assertEqual(r["banque"], "Bitpanda")
        self.assertEqual(resume(r), [("Achat", "BTC", 0.002, 100.0, 0.0, "ordre"),
                                     ("Achat", "ETH", 0.001, 2.0, 0.0, "offert")])
        self.assertEqual(r["ignores"].get("classe"), 1)


class CryptoCom(unittest.TestCase):
    def test_application(self):
        entete = ["Timestamp (UTC)", "Transaction Description", "Currency", "Amount", "To Currency", "To Amount",
                  "Native Currency", "Native Amount", "Native Amount (in USD)", "Transaction Kind"]
        r = lire([
            entete,
            ["2024-01-05 10:00:00", "EUR -> BTC", "EUR", "-100", "BTC", "0.002", "EUR", "100", "110", "viban_purchase"],
            ["2024-01-05 11:00:00", "BTC -> ETH", "BTC", "-0.001", "ETH", "0.025", "EUR", "50", "55", "crypto_exchange"],
            ["2024-01-05 12:00:00", "Card Cashback", "CRO", "10", "", "", "EUR", "0.8", "0.88", "referral_card_cashback"],
            ["2024-01-05 13:00:00", "Withdraw BTC", "BTC", "-0.0005", "", "", "EUR", "25", "27.5", "crypto_withdrawal"],
        ])
        self.assertEqual(r["banque"], "Crypto.com")
        self.assertEqual(resume(r), [
            ("Achat", "BTC", 0.002, 100.0, 0.0, "ordre"),
            ("Achat", "ETH", 0.025, 50.0, 0.0, "ordre"),
            ("Vente", "BTC", 0.001, 50.0, 0.0, "ordre"),
            ("Achat", "CRO", 10.0, 0.8, 0.0, "offert"),
        ])
        self.assertEqual(r["ignores"].get("transferts_crypto"), 1)


class Revolut(unittest.TestCase):
    def test_releve_crypto(self):
        r = lire([
            ["Symbol", "Type", "Quantity", "Price", "Value", "Fees", "Date"],
            ["BTC", "Buy", "0.002", "€50,000.00", "€100.00", "€1.49", "Jan 5, 2024, 10:00:00 AM"],
            ["ETH", "Staking reward", "0.001", "€2,000.00", "€2.00", "€0.00", "Jan 5, 2024, 11:00:00 AM"],
        ])
        self.assertEqual(r["banque"], "Revolut")
        self.assertEqual(resume(r), [("Achat", "BTC", 0.002, 100.0, 1.49, "ordre"),
                                     ("Achat", "ETH", 0.001, 2.0, 0.0, "offert")])


class Bitvavo(unittest.TestCase):
    def test_export(self):
        r = lire([
            ["Timezone", "Date", "Time", "Type", "Currency", "Amount", "Quote Currency", "Quote Price",
             "Received / Paid Currency", "Received / Paid Amount", "Fee currency", "Fee amount", "Status", "Transaction ID"],
            ["Europe/Paris", "2024-01-05", "10:00:00", "buy", "BTC", "0.002", "EUR", "50000", "EUR", "100", "EUR", "0.25",
             "Completed", "v1"],
            ["Europe/Paris", "2024-01-05", "11:00:00", "staking", "DOT", "0.5", "EUR", "6", "", "", "", "", "Completed", "v2"],
        ])
        self.assertEqual(r["banque"], "Bitvavo")
        self.assertEqual(resume(r), [("Achat", "BTC", 0.002, 100.0, 0.25, "ordre"),
                                     ("Achat", "DOT", 0.5, 3.0, 0.0, "offert")])


class Delta(unittest.TestCase):
    def test_export(self):
        r = lire([
            ["Date", "Way", "Base amount", "Base currency (name)", "Base type", "Quote amount", "Quote currency",
             "Exchange", "Sent/Received from", "Sent to", "Fee amount", "Fee currency (name)", "Broker", "Notes"],
            ["2024-01-05T10:00:00+01:00", "BUY", "0.002", "BTC", "CRYPTO", "100", "EUR", "Kraken", "", "", "0.4", "EUR", "", ""],
            ["2024-01-05T11:00:00+01:00", "BUY", "2", "AAPL", "STOCK", "400", "USD", "", "", "", "", "", "", ""],
            ["2024-01-05T12:00:00+01:00", "DEPOSIT", "0.1", "ETH", "CRYPTO", "", "", "", "", "", "", "", "", ""],
        ])
        self.assertEqual(r["banque"], "Delta")
        self.assertEqual(resume(r), [("Achat", "BTC", 0.002, 100.0, 0.4, "ordre")])
        self.assertEqual((r["ignores"].get("classe"), r["ignores"].get("transferts_crypto")), (1, 1))

    def test_nom_entre_parentheses(self):
        r = lire([
            ["Date", "Way", "Base amount", "Base currency (name)", "Base type", "Quote amount", "Quote currency",
             "Fee amount", "Fee currency (name)"],
            ["2024-01-05T10:00:00+01:00", "BUY", "1", "SOL (Solana)", "CRYPTO", "100", "EUR", "", ""],
        ])
        self.assertEqual(resume(r), [("Achat", "SOL", 1.0, 100.0, 0.0, "ordre")])


class EtoroEtUniversel(unittest.TestCase):
    def test_etoro_crypto_dans_sa_section(self):
        r = lire([
            ["Date", "Type", "Details", "Amount", "Units", "Realized Equity Change", "Realized Equity", "Balance",
             "Position ID", "Asset type", "NWA"],
            ["05/01/2024 10:00:00", "Open Position", "BTC/USD", "110", "0.002", "0", "0", "0", "p1", "Crypto", "0"],
            ["05/01/2024 11:00:00", "Open Position", "AAPL/USD", "220", "1", "0", "0", "0", "p2", "Stocks", "0"],
        ])
        self.assertEqual(r["banque"], "eToro")
        comptes = {o["nom"]: (o.get("compte"), o["classe"], o["montant"]) for o in r["operations"]}
        self.assertEqual(comptes["BTC"], ("CRYPTO", "crypto", 100.0))
        self.assertIsNone(comptes["AAPL"][0])

    def test_tableau_quelconque(self):
        r = lire([
            ["Date", "Sens", "Nom", "Quantité", "Montant"],
            ["05/01/2024", "Achat", "Bitcoin", "0,002", "100,00"],
            ["05/01/2024", "Achat", "Air Liquide", "1", "160,00"],
        ])
        comptes = {o["nom"]: (o.get("compte"), o["classe"]) for o in r["operations"]}
        self.assertEqual(comptes["Bitcoin"], ("CRYPTO", "crypto"))
        self.assertNotEqual(comptes["Air Liquide"][1], "crypto")


if __name__ == "__main__":
    unittest.main()
