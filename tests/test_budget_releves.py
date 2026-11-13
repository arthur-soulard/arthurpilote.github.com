"""Tests de l'import des relevés de banque dans Mes comptes (budget_releves.py).

  1. Plus de 1 000 relevés générés aux formats réels de 17 banques et formats
     (corpus_budget.py), puis 340 relevés d'un jeu de validation écrit après
     le réglage (corpus_budget_validation.py) : lecture exacte, classement.
  2. Les exemples publiés par d'autres projets libres (Carbure, My-PiggyBank,
     gleba), recopiés : tous fictifs.
  3. Fichiers difficiles, catégories personnalisées, historique, virements
     internes, carte à débit différé.

Aucun vrai relevé dans le dépôt (il est public).
"""
import base64
import collections
import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import budget_releves as br  # noqa: E402
import finances  # noqa: E402
import mesurer_budget  # noqa: E402

CATS = finances._default_categories()


def lire(texte, nom="releve.csv", enc="utf-8", cats=None, hist=None):
    data = texte if isinstance(texte, bytes) else texte.encode(enc)
    return br.lire([{"nom": nom, "b64": base64.b64encode(data).decode()}], cats or CATS, hist or [])


def resume(r):
    return [(o["date"], o["montantSigne"], o["libelle"], o["cat"], o["sub"]) for o in r["operations"]]


class Corpus(unittest.TestCase):
    """Les 1 020 relevés d'entraînement et les 340 de validation."""

    def test_entrainement_1020_releves(self):
        tot, _ = mesurer_budget.mesurer(1020)
        self.assertGreaterEqual(tot["fichiers"], 1000)
        self.assertEqual(tot["lues"], tot["ops"], "chaque opération lue, date et montant exacts")
        self.assertEqual(tot["en trop"], 0, "aucune ligne inventée (totaux, soldes, attente)")
        self.assertGreaterEqual(tot["justes"] / tot["connues"], 0.98)
        self.assertLessEqual(tot["fausses"] / tot["connues"], 0.005)
        self.assertLessEqual(tot["inconnues classées"] / tot["inconnues"], 0.01)
        self.assertGreaterEqual(tot["internes vus"] / tot["internes"], 0.99)
        self.assertEqual(tot["faux internes"], 0)

    def test_validation_340_releves_jamais_vus(self):
        tot, _ = mesurer_budget.mesurer(340, validation=True)
        self.assertEqual(tot["lues"], tot["ops"])
        self.assertGreaterEqual(tot["justes"] / tot["connues"], 0.97)
        self.assertLessEqual(tot["fausses"] / tot["connues"], 0.01)
        self.assertLessEqual(tot["inconnues classées"] / tot["inconnues"], 0.01)


class ExemplesPublies(unittest.TestCase):
    """Fichiers d'exemple publiés avec les lecteurs de Carbure (PR 116),
    My-PiggyBank (PR 70) et gleba (PR 43), et leurs résultats attendus."""

    def test_banque_postale(self):
        t = ("Numéro Compte ;0123456X020\r\nType ;CCP\r\nCompte tenu en ;euros\r\nDate ;13/10/2026\r\n"
             "Solde (EUROS) ;1 234,56\r\nSolde (FRANCS) ;8 098,51\r\n\r\nDate;Libellé;Montant(EUROS);Montant(FRANCS)\r\n"
             '12/10/2026;"ACHAT CB SUPERMARCHE 11.10.26 CARTE NUMERO 123";-45,60;-299,11\r\n'
             '10/10/2026;"VIREMENT DE M MARTIN DUPONT";1 500,00;9 839,35\r\n')
        r = lire(t, enc="cp1252")
        self.assertEqual(r["documents"][0]["banque"], "La Banque Postale")
        self.assertEqual(resume(r), [
            ("2026-10-10", 1500.0, "Martin Dupont", None, None),
            ("2026-10-12", -45.6, "Supermarche", "Alimentation", "Courses")])

    def test_societe_generale(self):
        t = ('="0123400012345678";01/01/2026;31/01/2026;3;31/01/2026;1 234,56 EUR\n\n'
             "Date de l'opération;Libellé;Détail de l'écriture;Montant de l'opération;Devise\n"
             "19/01/2026;VIR RECU 508160;VIR RECU 1234567834S DE: M MARTIN DUPONT MOTIF: LOYER REF: 1234 ;850,00;EUR\n"
             "18/01/2026;COTISATION JAZZ;COTISATION JAZZ ;-8,10;EUR\n"
             "17/01/2026;CARTE X1234 16/01 BOULANGERIE;CARTE X1234 16/01 BOULANGERIE DU MARCHE ;-3,20;EUR\n")
        r = lire(t, enc="cp1252")
        self.assertEqual(r["documents"][0]["banque"], "Société Générale")
        ops = {o["montantSigne"]: o for o in r["operations"]}
        self.assertEqual(ops[850.0]["libelle"], "Martin Dupont")
        self.assertIsNone(ops[850.0]["cat"], "un loyer reçu d'un particulier n'est pas un remboursement")
        self.assertEqual((ops[-8.1]["cat"], ops[-8.1]["sub"]), ("Frais bancaires", "Frais de tenue de compte"))
        self.assertEqual(ops[-3.2]["libelle"], "Boulangerie Du Marche")
        self.assertEqual(ops[-3.2]["cat"], "Alimentation")

    def test_credit_mutuel(self):
        t = ("Date;Date de valeur;Débit;Crédit;Libellé;Solde\r\n"
             "05/01/2026;05/01/2026;-26,99;;PRLV SEPA OPERATEUR TELECOM;2323,01\r\n"
             "06/01/2026;06/01/2026;;2950,00;VIR SALAIRE EMPLOYEUR SA;5273,01\r\n"
             "07/01/2026;08/01/2026;-12,50;;PAIEMENT CB 0601 PARIS BOULANGERIE CARTE 4974XXXXXXXX1234;5260,51\r\n")
        r = lire(t, enc="cp1252")
        self.assertEqual([(o["date"], o["montantSigne"]) for o in r["operations"]],
                         [("2026-01-05", -26.99), ("2026-01-06", 2950.0), ("2026-01-07", -12.5)])
        self.assertEqual([o["cat"] for o in r["operations"]], ["Abonnements", "Salaire", "Alimentation"])

    def test_fortuneo(self):
        t = ("Date opération;Date valeur;libellé;Débit;Crédit;\r\n"
             "13/12/2025;13/12/2025;CARTE 12/12 LIBRAIRIE METZ;-6,4;\r\n"
             "12/12/2025;12/12/2025;VIR SEPA M MARTIN DUPONT;;150\r\n")
        r = lire(t, enc="latin-1")
        self.assertEqual([(o["montantSigne"], o["libelle"]) for o in r["operations"]],
                         [(150.0, "Martin Dupont"), (-6.4, "Librairie Metz")])
        self.assertEqual(r["operations"][1]["sub"], "Culture")

    def test_caisse_epargne(self):
        t = ("Date de comptabilisation;Libelle simplifie;Libelle operation;Reference;Informations complementaires;"
             "Type operation;Categorie;Sous categorie;Debit;Credit;Date operation;Date de valeur;Pointage operation\n"
             "20/01/2026;FOURNISSEUR ENERGIE;PRLV SEPA FOURNISSEUR ENERGIE;XX123456789;ECH/200126 ID EMETTEUR/FR12ZZZ123456;"
             "Prelevement;Logement;Energie;-125,30;;20/01/2026;20/01/2026;0\n"
             "21/01/2026;EMPLOYEUR SA;VIR SEPA EMPLOYEUR SA;XX123456790;SALAIRE JANVIER;Virement recu;Revenus;Salaires;"
             ";2500,00;21/01/2026;21/01/2026;0\n"
             "22/01/2026;CB SUPERMARCHE;CB SUPERMARCHE FACT 210126;XX123456791;;Paiement carte;Alimentation;Supermarche;"
             "-85,75;;21/01/2026;22/01/2026;0\n")
        r = lire(t)
        ops = {o["montantSigne"]: o for o in r["operations"]}
        # Date d'opération (le jour de l'achat), pas de comptabilisation
        self.assertEqual(ops[-85.75]["date"], "2026-01-21")
        self.assertEqual(ops[-85.75]["libelle"], "Supermarche")
        # Catégorie donnée par la banque : « Energie » retrouvée dans Logement › Électricité
        self.assertEqual((ops[-125.3]["cat"], ops[-125.3]["sub"]), ("Logement", "Électricité"))
        self.assertEqual(ops[-125.3]["comment"], "banque")
        self.assertEqual(ops[2500.0]["cat"], "Salaire")

    def test_bnp(self):
        t = ("Compte de chèques;Compte de chèques;****1234;13/10/2026;;1 234,56\n;;;;\n"
             "Date operation;Categorie operation;Sous Categorie operation;Libelle operation;Montant operation\n"
             "12-10-2026;Alimentation;Supermarché;FACTURE CARTE DU 111026 SUPERMARCHE CARTE 4974XXXXXXXX1234;-54,20\n"
             "10-10-2026;Revenus;Salaires;VIR SEPA RECU /DE EMPLOYEUR SA /MOTIF SALAIRE;2 100,00\n")
        r = lire(t)
        self.assertEqual(r["documents"][0]["banque"], "BNP Paribas")
        self.assertEqual(resume(r), [
            ("2026-10-10", 2100.0, "Employeur SA", "Salaire", "Salaire net"),
            ("2026-10-12", -54.2, "Supermarche", "Alimentation", "Courses")])

    def test_n26_actuel_et_ancien(self):
        t = ('"Booking Date","Value Date","Partner Name","Partner Iban","Type","Payment Reference","Account Name",'
             '"Amount (EUR)","Original Amount","Original Currency","Exchange Rate"\n'
             '"2026-01-05","2026-01-05","BOULANGERIE DU MARCHE","","Presentment","","Compte principal","-4.80","","",""\n'
             '"2026-01-06","2026-01-06","MARTIN DUPONT","FR7630001007941234567890185","Credit Transfer",'
             '"Remboursement restaurant","Compte principal","25.00","","",""\n'
             '"2026-01-08","2026-01-08","LIBRAIRIE EN LIGNE","","Presentment","","Compte principal","-120.50","-140.00","USD","1.1618"\n')
        r = lire(t)
        self.assertEqual([(o["date"], o["montantSigne"], o["libelle"]) for o in r["operations"]], [
            ("2026-01-05", -4.8, "Boulangerie Du Marche"), ("2026-01-06", 25.0, "Martin Dupont"),
            ("2026-01-08", -120.5, "Librairie En Ligne")])
        t2 = ('"Date","Bénéficiaire","Numéro de compte","Type de transaction","Référence de paiement","Montant (EUR)",'
              '"Montant (Devise étrangère)","Sélectionnez la devise étrangère","Taux de conversion"\n'
              '"2025-12-01","SUPERMARCHE BIO","","MasterCard Payment","","-32.40","","",""\n'
              '"2025-12-02","EMPLOYEUR SA","FR7612345678901234567890123","Income","Salaire novembre","2100.00","","",""\n')
        r = lire(t2)
        self.assertEqual([(o["montantSigne"], o["cat"]) for o in r["operations"]],
                         [(-32.4, "Alimentation"), (2100.0, "Salaire")])

    def test_revolut(self):
        t = ("Type,Product,Started Date,Completed Date,Description,Amount,Fee,Currency,State,Balance\n"
             "CARD_PAYMENT,Current,2026-01-03 12:16:54,2026-01-04 08:02:11,Monoprix,-23.45,0.00,EUR,COMPLETED,476.55\n"
             "TOPUP,Current,2026-01-05 09:00:00,2026-01-05 09:00:02,Top-Up by *1234,500.00,0.00,EUR,COMPLETED,976.55\n"
             "EXCHANGE,Current,2026-01-06 10:00:00,2026-01-06 10:00:00,Exchanged to USD,-100.00,0.50,EUR,COMPLETED,876.05\n"
             "CARD_PAYMENT,Current,2026-01-07 15:08:08,2026-01-07 15:08:08,Hotel temporary hold,0.00,0.00,EUR,COMPLETED,876.05\n"
             "CARD_PAYMENT,Current,2026-01-08 19:30:00,,Cinema,-12.00,0.00,EUR,PENDING,\n"
             "TRANSFER,Current,2026-01-09 11:00:00,2026-01-09 11:00:05,To Martin Dupont,-50.00,0.00,EUR,REVERTED,876.05\n")
        r = lire(t)
        self.assertEqual([(o["date"], o["montantSigne"]) for o in r["operations"]],
                         [("2026-01-03", -23.45), ("2026-01-05", 500.0), ("2026-01-06", -100.5)])
        self.assertEqual(r["documents"][0]["ignorees"], {"montant nul": 1, "en attente ou refusée": 2})
        self.assertTrue(r["operations"][1]["interne"] and r["operations"][2]["interne"])

    def test_qonto_anglais_et_francais(self):
        t = ("Status,Settlement date (UTC),Operation date (UTC),Total amount (incl. VAT),Currency,Counterparty name,"
             "Payment method,Transaction ID,IBAN,Reference,Category\n"
             "settled,2026-01-10 09:30:00,2026-01-09 18:12:00,-49.90,EUR,Fournisseur Logiciel,card,txn_0001,,Abonnement,software\n"
             "declined,2026-01-12 10:00:00,2026-01-12 10:00:00,-15.00,EUR,Taxi,card,txn_0003,,,transport\n"
             "settled,2026-01-11 10:00:00,2026-01-11 10:00:00,1200.00,EUR,Client SARL,transfer,txn_0002,"
             "FR7630001007941234567890185,Facture F-2026-001,sales\n")
        r = lire(t)
        self.assertEqual([(o["date"], o["montantSigne"]) for o in r["operations"]],
                         [("2026-01-09", -49.9), ("2026-01-11", 1200.0)])
        t2 = ("Statut;Date de la valeur (UTC);Date de l'opération (UTC);Montant total (TTC);Débit;Crédit;Solde;Devise;"
              "Nom de la contrepartie;IBAN de la contrepartie;Méthode de paiement;Identifiant de transaction;Référence;"
              "Catégorie de trésorerie\n"
              "Exécuté;10-01-2026 09:30:00;09-01-2026 18:12:00;-49,90;-49,90;;950,10;EUR;Fournisseur Logiciel;;Carte;"
              "txn_0001;Abonnement;Logiciels\n"
              "Exécuté;11-01-2026 10:00:00;11-01-2026 10:00:00;1200,00;;1200,00;2150,10;EUR;Client SARL;"
              "FR7630001007941234567890185;Virement;txn_0002;Facture F-2026-001;Ventes\n"
              "Refusé;12-01-2026 10:00:00;12-01-2026 10:00:00;-15,00;-15,00;;2150,10;EUR;Taxi;;Carte;txn_0003;;Transport\n")
        r = lire(t2)
        self.assertEqual([(o["date"], o["montantSigne"]) for o in r["operations"]],
                         [("2026-01-09", -49.9), ("2026-01-11", 1200.0)])
        self.assertEqual(r["operations"][0]["sub"], "Cloud / Logiciels", "catégorie Qonto « Logiciels » reprise")

    def test_ofx_sgml_et_xml(self):
        sgml = ("OFXHEADER:100\nDATA:OFXSGML\nVERSION:102\n\n<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><BANKTRANLIST>\n"
                "<STMTTRN>\n<TRNTYPE>DEBIT\n<DTPOSTED>20260902120000[+1:CET]\n<TRNAMT>-54.20\n<FITID>A1\n"
                "<NAME>CARREFOUR\n<MEMO>CB 01/09\n</STMTTRN>\n"
                "<STMTTRN>\n<TRNTYPE>CREDIT\n<DTPOSTED>20260903\n<TRNAMT>1850.00\n<FITID>A2\n<NAME>VIR SALAIRE\n"
                "</STMTTRN>\n</BANKTRANLIST></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>\n")
        r = lire(sgml, "releve.ofx")
        self.assertEqual(resume(r), [
            ("2026-09-02", -54.2, "Carrefour", "Alimentation", "Courses"),
            ("2026-09-03", 1850.0, "Salaire", "Salaire", "Salaire net")])
        xml = ('<?xml version="1.0" encoding="UTF-8"?>\n<?OFX OFXHEADER="200" VERSION="220"?>\n<OFX><BANKMSGSRSV1>'
               "<STMTTRNRS><STMTRS><BANKTRANLIST><STMTTRN><TRNTYPE>DEBIT</TRNTYPE><DTPOSTED>20260902</DTPOSTED>"
               "<TRNAMT>-54.20</TRNAMT><FITID>A1</FITID><NAME>CARREFOUR</NAME><MEMO>CB 01/09</MEMO></STMTTRN>"
               "</BANKTRANLIST></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>")
        self.assertEqual(len(lire(xml, "releve.ofx")["operations"]), 1)
        vide = ("OFXHEADER:100\nDATA:OFXSGML\n\n<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><BANKTRANLIST>"
                "</BANKTRANLIST></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>")
        self.assertFalse(lire(vide, "vide.ofx")["ok"])

    def test_formats_my_piggybank(self):
        cas = {
            "guillemets": ('"Date";"Libellé";"Montant"\n"02/09/2026";"RESTO; LE COIN";"-23,50"\n'
                           '"04/09/2026";"BOULANGERIE";"-4,30"\n"07/09/2026";"VIREMENT RECU";"100,00"\n',
                           [-23.5, -4.3, 100.0]),
            "debit credit": ("Date;Libellé;Débit;Crédit;Solde\n02/09/2026;CB CARREFOUR;54,20;;1 245,80\n"
                             "03/09/2026;VIR SALAIRE;;1 850,00;3 095,80\n05/09/2026;PRLV EDF;72,00;;3 023,80\n",
                             [-54.2, 1850.0, -72.0]),
            "point décimal": ('Date,Description,Amount\n2026-09-02,GROCERY STORE,"-1,234.56"\n2026-09-03,SALARY,2500.00\n'
                              "2026-09-05,COFFEE,-12.30\n", [-1234.56, 2500.0, -12.3]),
            "sans en-tête": ("02/09/2026;CB CARREFOUR;-54,20\n03/09/2026;VIR SALAIRE;1850,00\n05/09/2026;PRLV EDF;-72,00\n",
                             [-54.2, 1850.0, -72.0]),
            "deux montants": ("Date;Libellé;Montant 1;Montant 2;Solde\n02/09/2026;CB CARREFOUR;;-54,20;1 245,80\n"
                              "03/09/2026;VIR SALAIRE;1 850,00;;3 095,80\n", None),
            "point-virgule final": ("Date;Libellé;Débit;Crédit\n02/09/2026;CB CARREFOUR;54,20;;\n"
                                    "03/09/2026;VIR SALAIRE;;1850,00;\n05/09/2026;PRLV EDF;72,00;;\n",
                                    [-54.2, 1850.0, -72.0]),
            "ligne de total": ("Date;Libellé;Montant\n02/09/2026;CB CARREFOUR;-54,20\n03/09/2026;VIR SALAIRE;1850,00\n"
                               "Total;;-123,45\n", [-54.2, 1850.0]),
            "dates américaines": ("Date;Libellé;Montant\n09/02/2026;CB CARREFOUR;-54,20\n09/13/2026;VIR SALAIRE;1850,00\n",
                                  [-54.2, 1850.0]),
        }
        for nom, (t, attendus) in cas.items():
            with self.subTest(nom):
                r = lire(t)
                if attendus is None:
                    continue    # deux colonnes de montant : lu ou refusé, jamais faux
                self.assertEqual(sorted(o["montantSigne"] for o in r["operations"]), sorted(attendus))
        r = lire(cas["dates américaines"][0])
        self.assertEqual([o["date"] for o in r["operations"]], ["2026-09-02", "2026-09-13"])
        r = lire(cas["guillemets"][0])
        self.assertIn("Resto", [o["libelle"] for o in r["operations"]][0])


class FichiersDifficiles(unittest.TestCase):

    def test_texte_unicode_excel_utf16(self):
        t = "Date\tLibellé\tMontant\r\n12/10/2026\tCB MONOPRIX 11/10\t-12,40\r\n"
        r = lire(t.encode("utf-16"))
        self.assertEqual(resume(r), [("2026-10-12", -12.4, "Monoprix", "Alimentation", "Courses")])

    def test_csv_repasse_par_excel_une_colonne(self):
        # CSV à virgules réenregistré par Excel français : chaque ligne dans une seule case
        t = '"Date,Libelle,Montant"\n"2026-10-12,CB FNAC,-30.00"\n"2026-10-13,PRLV EDF,-60.00"\n'
        r = lire(t)
        self.assertEqual([o["montantSigne"] for o in r["operations"]], [-30.0, -60.0])

    def test_page_html_nommee_xls(self):
        t = ("<html><body><table><tr><td>Date</td><td>Libellé</td><td>Débit</td><td>Crédit</td></tr>"
             "<tr><td>12/10/2026</td><td>CB DECATHLON</td><td>45,00</td><td></td></tr>"
             "<tr><td>13/10/2026</td><td>VIR CAF</td><td></td><td>210,00</td></tr></table></body></html>")
        r = lire(t, "releve.xls")
        self.assertEqual([(o["montantSigne"], o["cat"]) for o in r["operations"]],
                         [(-45.0, "Loisirs"), (210.0, None)])
        self.assertEqual(r["operations"][1]["propose"]["cat"], "Aides & allocations")

    def test_signes_euros_annees_courtes(self):
        t = "Date;Libellé;Montant\n12/10/26;CB LECLERC;-1 234,56 €\n13/10/26;VIR SALAIRE ACME;+2 000,00 €\n"
        r = lire(t)
        self.assertEqual([(o["date"], o["montantSigne"]) for o in r["operations"]],
                         [("2026-10-12", -1234.56), ("2026-10-13", 2000.0)])

    def test_debits_positifs_dans_colonne_debit(self):
        t = "Date;Libellé;Débit euros;Crédit euros;\n12/10/2026;\"CB NETFLIX\n   111026\";15,99;;\n"
        r = lire(t)
        self.assertEqual(resume(r), [("2026-10-12", -15.99, "Netflix", "Abonnements", "Streaming")])

    def test_pdf_refuse_avec_explication(self):
        r = lire(b"%PDF-1.4 ...", "releve.pdf")
        self.assertFalse(r["ok"])
        self.assertIn("CSV", r["erreur"])

    def test_qif(self):
        t = "!Type:Bank\nD12/10/2026\nT-45,60\nPCB CARREFOUR\n^\nD13/10'26\nT1200.00\nPVIR SALAIRE\nLSalaire\n^\n"
        r = lire(t, "r.qif")
        self.assertEqual([(o["date"], o["montantSigne"], o["cat"]) for o in r["operations"]],
                         [("2026-10-12", -45.6, "Alimentation"), ("2026-10-13", 1200.0, "Salaire")])


class Nettoyage(unittest.TestCase):
    def test_libelles(self):
        cas = {
            "CARTE X1234 16/01 BOULANGERIE DU MARCHE": "Boulangerie Du Marche",
            "PAIEMENT CB 0601 PARIS BOULANGERIE CARTE 4974XXXXXXXX1234": "Paris Boulangerie",
            "FACTURE CARTE DU 111026 SUPERMARCHE CARTE 4974XXXXXXXX1234": "Supermarche",
            "ACHAT CB SUPERMARCHE 11.10.26 CARTE NUMERO 123": "Supermarche",
            "PRLV SEPA FREE MOBILE 1234567890": "Free Mobile",
            "PRELEVEMENT EUROPEEN EDF ECH/200126 ID EMETTEUR/FR12ZZZ123456": "EDF",
            "VIR SEPA RECU /DE EMPLOYEUR SA /MOTIF SALAIRE": "Employeur SA",
            "VIR RECU 1234567834S DE: M MARTIN DUPONT MOTIF: LOYER REF: 1234": "Martin Dupont",
            "CARTE 06/01/26 SNCF CB*1234": "SNCF",
            "CB PAYPAL *NETFLIX 120326": "Netflix",
            "PAIEMENT PAR CARTE X1234 AMAZON PAYMENTS 12/03": "Amazon Payments",
            "CB  CARREFOUR  12/10/26": "Carrefour",
        }
        for brut, attendu in cas.items():
            with self.subTest(brut):
                self.assertEqual(br.nettoyer(brut), attendu)

    def test_genres(self):
        cas = {"CB CARREFOUR": "carte", "PRLV SEPA EDF": "prelevement", "VIR SEPA RECU /DE X": "virement",
               "RETRAIT DAB 12/10 PARIS": "retrait", "CHQ 1234567": "cheque", "COTISATION CARTE": "frais",
               "FACTURE CARTE DU 111026 X": "carte"}
        for brut, g in cas.items():
            with self.subTest(brut):
                self.assertEqual(br.genre_de(brut), g)


class Categories(unittest.TestCase):
    PERSO = [  # utilisateur « ordonné » : ses propres noms
        {"name": "Nourriture", "type": "expense", "subs": [{"name": "Supermarché"}, {"name": "Resto"}]},
        {"name": "Maison", "type": "expense", "subs": [{"name": "Loyer"}, {"name": "Énergie"}, {"name": "Box"}]},
        {"name": "Voiture", "type": "expense", "subs": [{"name": "Essence"}, {"name": "Péage"}]},
        {"name": "Impôts", "type": "expense", "subs": []},
        {"name": "Divers", "type": "expense", "subs": []},
        {"name": "Paie", "type": "income", "subs": []},
    ]

    def test_noms_personnels_retrouves(self):
        t = ("Date;Libellé;Montant\n01/10/2026;CB CARREFOUR MARKET;-30,00\n02/10/2026;CB MCDONALDS;-9,90\n"
             "03/10/2026;PRLV SEPA EDF;-60,00\n04/10/2026;CB TOTALENERGIES;-50,00\n05/10/2026;PRLV DGFIP IMPOT;-100,00\n"
             "06/10/2026;PRLV FREEBOX;-29,99\n07/10/2026;VIR SEPA RECU /DE ACME /MOTIF SALAIRE;2000,00\n"
             "08/10/2026;CB VINCI AUTOROUTES;-12,00\n")
        r = lire(t, cats=self.PERSO)
        self.assertEqual([(o["cat"], o["sub"]) for o in r["operations"]], [
            ("Nourriture", "Supermarché"), ("Nourriture", "Resto"), ("Maison", "Énergie"), ("Voiture", "Essence"),
            ("Impôts", None), ("Maison", "Box"), ("Paie", None), ("Voiture", "Péage")])

    def test_jamais_force_ailleurs(self):
        minimal = [{"name": "Courses", "type": "expense", "subs": []},
                   {"name": "Autres dépenses", "type": "expense", "subs": []}]
        t = "Date;Libellé;Montant\n01/10/2026;CB NETFLIX;-13,49\n02/10/2026;CB LIDL;-20,00\n"
        r = lire(t, cats=minimal)
        self.assertEqual([o["cat"] for o in r["operations"]], [None, "Courses"])
        self.assertEqual(r["operations"][0]["propose"]["cat"], "Abonnements")

    def test_historique_apprend(self):
        hist = [{"label": "Chez Gégé", "type": "expense", "cat": "Loisirs", "sub": "Sorties", "date": "2026-09-01"},
                # Un libellé connu du dictionnaire mais que l'utilisateur classe autrement : il gagne
                {"label": "Amazon", "type": "expense", "cat": "Loisirs", "sub": "Culture", "date": "2026-09-02"},
                {"label": "Amazon", "type": "expense", "cat": "Loisirs", "sub": "Culture", "date": "2026-09-03"}]
        t = ("Date;Libellé;Montant\n01/10/2026;CB CHEZ GEGE 30/09;-25,00\n02/10/2026;CB AMAZON PAYMENTS;-18,00\n"
             "03/10/2026;CB CHEZ ROBERT;-8,00\n")
        r = lire(t, hist=hist)
        ops = r["operations"]
        self.assertEqual((ops[0]["cat"], ops[0]["sub"], ops[0]["comment"]), ("Loisirs", "Sorties", "historique"))
        self.assertEqual((ops[1]["sub"], ops[1]["comment"]), ("Culture", "historique"))
        self.assertIsNone(ops[2]["cat"])


class CasParticuliers(unittest.TestCase):
    def test_virement_entre_deux_releves(self):
        a = "Date;Libellé;Montant\n05/10/2026;VIR SEPA EMIS VERS M DUPONT;-300,00\n"
        b = "Date;Libellé;Montant\n05/10/2026;VIR SEPA RECU /DE M DUPONT;300,00\n"
        r = br.lire([{"nom": "a.csv", "b64": base64.b64encode(a.encode()).decode()},
                     {"nom": "b.csv", "b64": base64.b64encode(b.encode()).decode()}], CATS, [])
        self.assertTrue(all(o["interne"] for o in r["operations"]))

    def test_carte_a_debit_differe(self):
        t = ("Date;Libellé;Montant\n03/10/2026;CB LIDL;-40,00\n10/10/2026;CB FNAC;-60,00\n"
             "31/10/2026;RELEVE DIFFERE CARTE X1234;-100,00\n")
        r = lire(t)
        total = [o for o in r["operations"] if o["totalCarte"]]
        self.assertEqual(len(total), 1)
        self.assertTrue(total[0].get("doubleCarte"))

    def test_empreinte_stable_et_distincte(self):
        t = "Date;Libellé;Montant\n01/10/2026;CB CAFE;-2,00\n01/10/2026;CB CAFE;-2,00\n"
        e1 = [o["empreinte"] for o in lire(t)["operations"]]
        e2 = [o["empreinte"] for o in lire(t)["operations"]]
        self.assertEqual(e1, e2)
        self.assertEqual(len(set(e1)), 2, "deux cafés le même jour restent deux opérations")


if __name__ == "__main__":
    unittest.main()
