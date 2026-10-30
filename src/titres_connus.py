"""
titres_connus.py — Catalogue des titres les plus détenus sur un PEA ou un
CTO français, pour l'import des relevés (4.4.37).

Un utilisateur important son CSV voyait « à choisir » sur Engie, Saint-Gobain
et d'autres grandes valeurs (30/10/2026). Cause : sans ISIN dans le fichier
(CSV de Fortuneo), Yahoo ne trouve rien sur les noms des banques (« CIE DE
SAINT-GOBAIN », « BNP PARIBAS ACTIONS A ») et rend TotalEnergies ou LVMH
seulement en Allemagne (TOTB.DE, MOH.DE), sans cotation à Paris. Ce
catalogue donne la cotation de référence de chaque titre, retrouvé par son
ISIN ou par son nom ; server.cotations_euro la place en tête des candidats,
toujours vérifiée sur les prix payés comme les autres.

Deux sources :
  * TITRES ci-dessous, écrit à la main : les valeurs les plus courantes,
    avec les noms qu'écrivent les banques. Chaque ligne : (ISIN, ticker
    Yahoo, nom, autres noms séparés par « | »). Vérifié chez Yahoo le
    30/10/2026 (tests/verifier_catalogue.py : cours en euros, et l'ISIN rend
    bien ce titre). Une valeur rachetée ou retirée de la cote se retire
    d'ici ; une nouvelle s'ajoute, puis se vérifie.
  * titres_listes.py, fabriqué par tests/generer_titres.py à partir des
    listes officielles d'Euronext et de Xetra : environ 6 400 titres en
    euros (actions d'Europe et des États-Unis, ETF, ETC, ETN).
"""
import re
import unicodedata

TITRES = [
    # ── CAC 40 ──
    ("FR0000120404", "AC.PA",    "Accor", ""),
    ("FR0000120073", "AI.PA",    "Air Liquide", "l air liquide"),
    ("NL0000235190", "AIR.PA",   "Airbus", "airbus group"),
    ("LU1598757687", "MT.AS",    "ArcelorMittal", "arcelor mittal|arcelor"),
    ("FR0000120628", "CS.PA",    "AXA", ""),
    ("FR0000131104", "BNP.PA",   "BNP Paribas", ""),
    ("FR0000120503", "EN.PA",    "Bouygues", ""),
    ("FR0006174348", "BVI.PA",   "Bureau Veritas", ""),
    ("FR0000125338", "CAP.PA",   "Capgemini", "cap gemini"),
    ("FR0000120172", "CA.PA",    "Carrefour", ""),
    ("FR0000045072", "ACA.PA",   "Crédit Agricole", "credit agricole sa"),
    ("FR0000120644", "BN.PA",    "Danone", ""),
    ("FR0014003TT8", "DSY.PA",   "Dassault Systèmes", "dassault systemes"),
    ("FR0010908533", "EDEN.PA",  "Edenred", ""),
    ("FR0010208488", "ENGI.PA",  "Engie", "gdf suez"),
    ("FR0000121667", "EL.PA",    "EssilorLuxottica", "essilor luxottica|essilor"),
    ("FR0014000MR3", "ERF.PA",   "Eurofins Scientific", "eurofins"),
    ("NL0006294274", "ENX.PA",   "Euronext", ""),
    ("FR0000052292", "RMS.PA",   "Hermès International", "hermes"),
    ("FR0000121485", "KER.PA",   "Kering", ""),
    ("FR0010307819", "LR.PA",    "Legrand", ""),
    ("FR0000120321", "OR.PA",    "L'Oréal", "loreal|l oreal"),
    ("FR0000121014", "MC.PA",    "LVMH Moët Hennessy Louis Vuitton", "lvmh|moet hennessy"),
    ("FR001400AJ45", "ML.PA",    "Michelin", "cgde michelin"),
    ("FR0000133308", "ORA.PA",   "Orange", "france telecom"),
    ("FR0000120693", "RI.PA",    "Pernod Ricard", ""),
    ("FR0000130577", "PUB.PA",   "Publicis Groupe", "publicis"),
    ("FR0000131906", "RNO.PA",   "Renault", ""),
    ("FR0000073272", "SAF.PA",   "Safran", ""),
    ("FR0000125007", "SGO.PA",   "Saint-Gobain", "saint gobain|st gobain"),
    ("FR0000120578", "SAN.PA",   "Sanofi", ""),
    ("FR0000121972", "SU.PA",    "Schneider Electric", "schneider"),
    ("FR0000130809", "GLE.PA",   "Société Générale", "societe generale|soc gen|socgen"),
    ("NL00150001Q9", "STLAP.PA", "Stellantis", ""),
    ("NL0000226223", "STMPA.PA", "STMicroelectronics", "st microelectronics|stmicro"),
    ("FR0000051807", "TEP.PA",   "Teleperformance", ""),
    ("FR0000121329", "HO.PA",    "Thales", ""),
    ("FR0000120271", "TTE.PA",   "TotalEnergies", "total energies|total"),
    ("FR0013326246", "URW.PA",   "Unibail-Rodamco-Westfield", "unibail rodamco westfield|unibail"),
    ("FR0000124141", "VIE.PA",   "Veolia Environnement", "veolia"),
    ("FR0000125486", "DG.PA",    "Vinci", ""),
    ("FR0000127771", "VIV.PA",   "Vivendi", ""),
    # ── SBF 120 et autres valeurs françaises ──
    ("FR0010340141", "ADP.PA",   "Aéroports de Paris", "aeroports de paris|adp"),
    ("FR001400J770", "AF.PA",    "Air France-KLM", "air france klm|air france"),
    ("FR0010220475", "ALO.PA",   "Alstom", ""),
    ("FR0000071946", "ATE.PA",   "Alten", ""),
    ("FR0004125920", "AMUN.PA",  "Amundi", ""),
    ("FR0010313833", "AKE.PA",   "Arkema", ""),
    ("FR0013258662", "AYV.PA",   "Ayvens", "ald"),
    ("FR0000120966", "BB.PA",    "Société BIC", "bic"),
    ("FR0013280286", "BIM.PA",   "bioMérieux", "biomerieux"),
    ("FR0000039299", "BOL.PA",   "Bolloré", "bollore"),
    ("FR0010828137", "CARM.PA",  "Carmila", ""),
    ("FR0010386334", "CLARI.PA", "Clariane", "korian"),
    ("FR0010667147", "COFA.PA",  "Coface", ""),
    ("FR0000064578", "COV.PA",   "Covivio", ""),
    ("FR0014004L86", "AM.PA",    "Dassault Aviation", ""),
    ("FR0000053381", "DBG.PA",   "Derichebourg", ""),
    ("FR0000130452", "FGR.PA",   "Eiffage", ""),
    ("FR0011950732", "ELIOR.PA", "Elior Group", "elior"),
    ("FR0012435121", "ELIS.PA",  "Elis", ""),
    ("FR0000131757", "ERA.PA",   "Eramet", ""),
    ("FR0010221234", "ETL.PA",   "Eutelsat Communications", "eutelsat"),
    ("FR0000062671", "EXA.PA",   "Exail Technologies", "exail|ecagroupe"),
    ("FR0011476928", "FNAC.PA",  "Fnac Darty", "fnac"),
    ("FR0000121147", "FRVIA.PA", "Forvia", "faurecia"),
    ("FR0013451333", "FDJU.PA",  "FDJ United", "francaise des jeux|fdj"),
    ("FR0011726835", "GTT.PA",   "Gaztransport et Technigaz", "gaztransport technigaz|gtt"),
    ("FR0010040865", "GFC.PA",   "Gecina", ""),
    ("FR0010533075", "GET.PA",   "Getlink", "eurotunnel"),
    ("FR0000035081", "ICAD.PA",  "Icade", ""),
    ("FR0000120859", "NK.PA",    "Imerys", ""),
    ("FR0004024222", "ITP.PA",   "Interparfums", "inter parfums"),
    ("FR0010259150", "IPN.PA",   "Ipsen", ""),
    ("FR0000073298", "IPS.PA",   "Ipsos", ""),
    ("FR0000077919", "DEC.PA",   "JCDecaux", "jc decaux"),
    ("FR0000121964", "LI.PA",    "Klépierre", "klepierre"),
    ("FR0000130213", "MMB.PA",   "Lagardère", "lagardere"),
    ("FR0000065484", "LSS.PA",   "Lectra", ""),
    ("FR0000050353", "FII.PA",   "Lisi", ""),
    ("FR0000053225", "MMT.PA",   "M6 Métropole Télévision", "metropole television|m6"),
    ("FR0000051070", "MAU.PA",   "Maurel et Prom", "maurel prom|maurel"),
    ("FR0010241638", "MERY.PA",  "Mercialys", ""),
    ("FR0000039620", "MRN.PA",   "Mersen", ""),
    ("FR0000044448", "NEX.PA",   "Nexans", ""),
    ("FR0010112524", "NXI.PA",   "Nexity", ""),
    ("FR0014005HJ9", "OVH.PA",   "OVHcloud", "ovh"),
    ("FR0000120560", "QDT.PA",   "Quadient", "neopost"),
    ("FR0000130395", "RCO.PA",   "Rémy Cointreau", "remy cointreau"),
    ("FR0010451203", "RXL.PA",   "Rexel", ""),
    ("FR0013269123", "RUI.PA",   "Rubis", ""),
    ("FR0013154002", "DIM.PA",   "Sartorius Stedim Biotech", "sartorius stedim"),
    ("FR0010411983", "SCR.PA",   "SCOR", ""),
    ("FR0000121709", "SK.PA",    "SEB", "groupe seb"),
    ("FR0000121220", "SW.PA",    "Sodexo", ""),
    ("FR0013227113", "SOI.PA",   "Soitec", ""),
    ("FR0000050809", "SOP.PA",   "Sopra Steria", ""),
    ("FR0012757854", "SPIE.PA",  "Spie", ""),
    ("NL0014559478", "TE.PA",    "Technip Energies", ""),
    ("FR0000054900", "TFI.PA",   "TF1", ""),
    ("FR0005691656", "TRI.PA",   "Trigano", ""),
    ("FR0000054470", "UBI.PA",   "Ubisoft Entertainment", "ubisoft"),
    ("FR0013176526", "FR.PA",    "Valeo", ""),
    ("FR0013506730", "VK.PA",    "Vallourec", ""),
    ("FR0004056851", "VLA.PA",   "Valneva", ""),
    ("FR0013447729", "VRLA.PA",  "Verallia", ""),
    ("FR0000031775", "VCT.PA",   "Vicat", ""),
    ("FR0000031577", "VIRP.PA",  "Virbac", ""),
    ("FR0010282822", "VU.PA",    "VusionGroup", "vusion|ses imagotag"),
    ("FR0013357621", "WAVE.PA",  "Wavestone", ""),
    ("FR0000121204", "MF.PA",    "Wendel", ""),
    ("FR0011981968", "WLN.PA",   "Worldline", ""),
    # ── Pays-Bas ──
    ("NL0011540547", "ABN.AS",   "ABN AMRO", ""),
    ("NL0012969182", "ADYEN.AS", "Adyen", ""),
    ("NL0013267909", "AKZA.AS",  "Akzo Nobel", "akzonobel"),
    ("NL0011794037", "AD.AS",    "Ahold Delhaize", "koninklijke ahold delhaize"),
    ("NL0000334118", "ASM.AS",   "ASM International", ""),
    ("NL0010273215", "ASML.AS",  "ASML Holding", "asml"),
    ("NL0012866412", "BESI.AS",  "BE Semiconductor Industries", "besi"),
    ("NL0012059018", "EXO.AS",   "Exor", ""),
    ("NL0000009165", "HEIA.AS",  "Heineken", ""),
    ("NL0011821202", "INGA.AS",  "ING Groep", ""),
    ("NL0000009082", "KPN.AS",   "KPN", "koninklijke kpn"),
    ("NL0010773842", "NN.AS",    "NN Group", ""),
    ("NL0000009538", "PHIA.AS",  "Philips", "koninklijke philips"),
    ("NL0013654783", "PRX.AS",   "Prosus", ""),
    ("NL0000379121", "RAND.AS",  "Randstad", ""),
    ("NL0015000IY2", "UMG.AS",   "Universal Music Group", ""),
    ("NL0000395903", "WKL.AS",   "Wolters Kluwer", ""),
    ("NL0011585146", "RACE.MI",  "Ferrari", ""),
    # ── Allemagne ──
    ("DE000A1EWWW0", "ADS.DE",   "Adidas", ""),
    ("DE0008404005", "ALV.DE",   "Allianz", ""),
    ("DE000BASF111", "BAS.DE",   "BASF", ""),
    ("DE000BAY0017", "BAYN.DE",  "Bayer", ""),
    ("DE0005200000", "BEI.DE",   "Beiersdorf", ""),
    ("DE0005190003", "BMW.DE",   "BMW", "bayerische motoren werke"),
    ("DE000CBK1001", "CBK.DE",   "Commerzbank", ""),
    ("DE0005439004", "CON.DE",   "Continental", ""),
    ("DE000DTR0CK8", "DTG.DE",   "Daimler Truck", ""),
    ("DE0005140008", "DBK.DE",   "Deutsche Bank", ""),
    ("DE0005810055", "DB1.DE",   "Deutsche Börse", "deutsche borse|deutsche boerse"),
    ("DE0005552004", "DHL.DE",   "DHL Group", "deutsche post"),
    ("DE0005557508", "DTE.DE",   "Deutsche Telekom", ""),
    ("DE000ENAG999", "EOAN.DE",  "E.ON", "eon"),
    ("DE0008402215", "HNR1.DE",  "Hannover Rück", "hannover ruck|hannover rueck|hannover re"),
    ("DE0006047004", "HEI.DE",   "Heidelberg Materials", "heidelbergcement"),
    ("DE0006048432", "HEN3.DE",  "Henkel", ""),
    ("DE000HAG0005", "HAG.DE",   "Hensoldt", ""),
    ("DE0006231004", "IFX.DE",   "Infineon Technologies", "infineon"),
    ("DE0007100000", "MBG.DE",   "Mercedes-Benz Group", "mercedes benz|daimler"),
    ("DE0006599905", "MRK.DE",   "Merck KGaA", ""),
    ("DE000A0D9PT0", "MTX.DE",   "MTU Aero Engines", "mtu aero"),
    ("DE0008430026", "MUV2.DE",  "Münchener Rück", "munich re|munchener ruck|muenchener rueck"),
    ("DE000PAG9113", "P911.DE",  "Porsche AG", "dr ing h c f porsche"),
    ("DE0006969603", "PUM.DE",   "Puma", ""),
    ("DE0007030033", "RHM.DE",   "Rheinmetall", ""),
    ("DE0007037129", "RWE.DE",   "RWE", ""),
    ("DE0007164600", "SAP.DE",   "SAP", ""),
    ("DE0007236101", "SIE.DE",   "Siemens", ""),
    ("DE000ENER6Y0", "ENR.DE",   "Siemens Energy", ""),
    ("DE000SHL1006", "SHL.DE",   "Siemens Healthineers", ""),
    ("DE000SYM9999", "SY1.DE",   "Symrise", ""),
    ("DE0007664039", "VOW3.DE",  "Volkswagen", "vw"),
    ("DE000A1ML7J1", "VNA.DE",   "Vonovia", ""),
    ("DE000ZAL1111", "ZAL.DE",   "Zalando", ""),
    # ── Italie, Espagne, Portugal ──
    ("IT0003128367", "ENEL.MI",  "Enel", ""),
    ("IT0003132476", "ENI.MI",   "Eni", ""),
    ("IT0000062072", "G.MI",     "Generali", "assicurazioni generali"),
    ("IT0000072618", "ISP.MI",   "Intesa Sanpaolo", ""),
    ("IT0003856405", "LDO.MI",   "Leonardo", ""),
    ("IT0004965148", "MONC.MI",  "Moncler", ""),
    ("IT0004176001", "PRY.MI",   "Prysmian", ""),
    ("IT0005239360", "UCG.MI",   "UniCredit", ""),
    ("ES0109067019", "AMS.MC",   "Amadeus IT Group", "amadeus"),
    ("ES0113211835", "BBVA.MC",  "BBVA", "banco bilbao vizcaya argentaria"),
    ("ES0113900J37", "SAN.MC",   "Banco Santander", "santander"),
    ("ES0144580Y14", "IBE.MC",   "Iberdrola", ""),
    ("ES0148396007", "ITX.MC",   "Inditex", "industria de diseno textil"),
    ("ES0173516115", "REP.MC",   "Repsol", ""),
    ("ES0178430E18", "TEF.MC",   "Telefónica", "telefonica"),
    ("PTEDP0AM0009", "EDP.LS",   "EDP Energias de Portugal", ""),
    ("PTGAL0AM0009", "GALP.LS",  "Galp Energia", "galp"),
    ("PTJMT0AE0001", "JMT.LS",   "Jerónimo Martins", "jeronimo martins"),
    # ── Belgique, Finlande, Irlande, Autriche ──
    ("BE0974293251", "ABI.BR",   "Anheuser-Busch InBev", "ab inbev|anheuser busch"),
    ("BE0974264930", "AGS.BR",   "Ageas", ""),
    ("NL0010832176", "ARGX.BR",  "argenx", ""),
    ("BE0974259880", "DIE.BR",   "D'Ieteren", "dieteren"),
    ("BE0003797140", "GBLB.BR",  "Groupe Bruxelles Lambert", "gbl"),
    ("BE0003565737", "KBC.BR",   "KBC Groep", "kbc"),
    ("BE0003717312", "SOF.BR",   "Sofina", ""),
    ("BE0003470755", "SOLB.BR",  "Solvay", ""),
    ("BE0974464977", "SYENS.BR", "Syensqo", ""),
    ("BE0003739530", "UCB.BR",   "UCB", ""),
    ("BE0974320526", "UMI.BR",   "Umicore", ""),
    ("FI0009013403", "KNEBV.HE", "Kone", ""),
    ("FI0009013296", "NESTE.HE", "Neste", ""),
    ("FI0009000681", "NOKIA.HE", "Nokia", ""),
    ("FI0009005987", "UPM.HE",   "UPM-Kymmene", "upm"),
    ("IE0004927939", "KRX.IR",   "Kingspan", ""),
    ("IE00BYTBXV33", "RYA.IR",   "Ryanair", ""),
    ("AT0000652011", "EBS.VI",   "Erste Group Bank", "erste group"),
    ("AT0000743059", "OMV.VI",   "OMV", ""),
    # ── Grandes valeurs américaines, cotation en euros de Xetra (celle des
    #    CTO) : ISIN et ticker repris de titres_listes.py, vrais noms ici
    #    (Xetra les abrège : « META PLATF. », « BERKSH. H.B ») ──
    ("US00287Y1091", "4AB.DE",   "AbbVie", ""),
    ("US00724F1012", "ADB.DE",   "Adobe", ""),
    ("US0090661010", "6Z1.DE",   "Airbnb", ""),
    ("US02079K3059", "ABEA.DE",  "Alphabet Class A", "alphabet|google"),
    ("US02079K1079", "ABEC.DE",  "Alphabet Class C", "alphabet|google"),
    ("US0231351067", "AMZ.DE",   "Amazon.com", "amazon"),
    ("US0378331005", "APC.DE",   "Apple", ""),
    ("US0846707026", "BRYN.DE",  "Berkshire Hathaway B", "berkshire hathaway|berkshire"),
    ("US0970231058", "BCO.DE",   "Boeing", ""),
    ("US11135F1012", "1YD.DE",   "Broadcom", ""),
    ("US1667641005", "CHV.DE",   "Chevron", ""),
    ("US17275R1023", "CIS.DE",   "Cisco Systems", "cisco"),
    ("US1912161007", "CCC3.DE",  "Coca-Cola", "coca cola company"),
    ("US19260Q1076", "1QZ.DE",   "Coinbase Global", "coinbase"),
    ("US22160K1051", "CTO.DE",   "Costco Wholesale", "costco"),
    ("US2546871060", "WDP.DE",   "Walt Disney", "disney"),
    ("US38141G1040", "GOS.DE",   "Goldman Sachs", ""),
    ("US4370761029", "HDI.DE",   "Home Depot", ""),
    ("US4581401001", "INL.DE",   "Intel", ""),
    ("US4592001014", "IBM.DE",   "IBM", "international business machines"),
    ("US46625H1005", "CMC.DE",   "JPMorgan Chase", "jp morgan|jpmorgan"),
    ("US57636Q1040", "M4I.DE",   "Mastercard", ""),
    ("US5801351017", "MDO.DE",   "McDonald's", "mcdonalds|mc donald s"),
    ("US58933Y1055", "6MK.DE",   "Merck & Co", "merck co"),
    ("US30303M1027", "FB2A.DE",  "Meta Platforms", "meta|facebook"),
    ("US5949181045", "MSF.DE",   "Microsoft", ""),
    ("US64110L1061", "NFC.DE",   "Netflix", ""),
    ("US6541061031", "NKE.DE",   "Nike", ""),
    ("DK0062498333", "NOV.DE",   "Novo Nordisk", ""),
    ("US67066G1040", "NVD.DE",   "Nvidia", ""),
    ("US68389X1054", "ORC.DE",   "Oracle", ""),
    ("US69608A1088", "PTX.DE",   "Palantir Technologies", "palantir"),
    ("US70450Y1038", "2PP.DE",   "PayPal", ""),
    ("US7134481081", "PEP.DE",   "PepsiCo", ""),
    ("US7170811035", "PFE.DE",   "Pfizer", ""),
    ("US7427181091", "PRG.DE",   "Procter & Gamble", "procter gamble"),
    ("US7475251036", "QCI.DE",   "Qualcomm", ""),
    ("US79466L3024", "FOO.DE",   "Salesforce", ""),
    ("LU1778762911", "639.DE",   "Spotify Technology", "spotify"),
    ("US8552441094", "SRB.DE",   "Starbucks", ""),
    ("US5949724083", "MIGA.DE",  "Strategy (ex-MicroStrategy)", "microstrategy"),
    ("US88160R1014", "TL0.DE",   "Tesla", ""),
    ("US90353T1007", "UT8.DE",   "Uber Technologies", "uber"),
    ("US91324P1021", "UNH.DE",   "UnitedHealth Group", "unitedhealth"),
    ("US92826C8394", "3V64.DE",  "Visa", ""),
    ("US9311421039", "WMT.DE",   "Walmart", ""),
    # ── ETF éligibles au PEA, cotés à Paris ──
    ("IE0002XZSHO1", "WPEA.PA",  "iShares MSCI World Swap PEA UCITS ETF", ""),
    ("LU1681043599", "CW8.PA",   "Amundi MSCI World Swap UCITS ETF EUR Acc", ""),
    ("FR0011550185", "ESE.PA",   "BNP Paribas Easy S&P 500 UCITS ETF EUR", ""),
    ("FR0011871128", "PSP5.PA",  "Amundi PEA S&P 500 UCITS ETF", ""),
    ("FR0011871110", "PUST.PA",  "Amundi PEA Nasdaq-100 UCITS ETF", ""),
    ("FR0013412020", "PAEEM.PA", "Amundi PEA Emergent MSCI Emerging ESG Transition UCITS ETF", ""),
    ("FR0007052782", "CAC.PA",   "Amundi CAC 40 UCITS ETF Dist", ""),
    ("FR0011550193", "ETZ.PA",   "BNP Paribas Easy STOXX Europe 600 UCITS ETF", ""),
    ("LU0908500753", "MEUD.PA",  "Amundi Core Stoxx Europe 600 UCITS ETF Acc", ""),
    # ── ETF courants sur un CTO ──
    ("IE00B4L5Y983", "IWDA.AS",  "iShares Core MSCI World UCITS ETF USD Acc", ""),
    ("IE00BK5BQT80", "VWCE.DE",  "Vanguard FTSE All-World UCITS ETF USD Acc", ""),
    ("IE00B3RBWM25", "VWRL.AS",  "Vanguard FTSE All-World UCITS ETF USD Dist", ""),
    ("IE00B5BMR087", "SXR8.DE",  "iShares Core S&P 500 UCITS ETF USD Acc", ""),
    ("IE00B3XXRP09", "VUSA.AS",  "Vanguard S&P 500 UCITS ETF", ""),
    ("IE00B6R52259", "IUSQ.DE",  "iShares MSCI ACWI UCITS ETF USD Acc", ""),
    ("IE00BKM4GZ66", "IS3N.DE",  "iShares Core MSCI EM IMI UCITS ETF USD Acc", ""),
    ("IE00BJ0KDQ92", "XDWD.DE",  "Xtrackers MSCI World UCITS ETF 1C", ""),
    ("IE00B4ND3602", "PPFB.DE",  "iShares Physical Gold ETC", ""),
]

# Mots des noms de banque ou de bourse qui ne disent rien du titre : forme
# sociale, catégorie d'action, « CIE DE », « ACT. », et ce que Xetra ajoute
# (« INH. O.N. », « DL-,01 », « REG.SHS »). Retirés avant de comparer.
_BRUIT = {"sa", "se", "nv", "ag", "plc", "spa", "sca", "kgaa", "ab", "asa", "oyj", "inc", "ltd",
          "corp", "co", "cie", "compagnie", "ste", "the", "de", "des", "du", "la", "le", "l", "d",
          "et", "and", "act", "actions", "action", "ord", "nom", "port", "reg", "prov", "a", "b",
          "c", "ex", "eo", "s", "nouv", "nouvelles", "cat", "ordinaire", "dl", "on", "o", "n",
          "inh", "nam", "namens", "akt", "vz", "st", "sf", "shs", "adr", "ads", "cl", "class",
          "registered", "ordinary", "shares", "sp", "br", "rc", "dr", "hd", "hld", "hldgs"}
_ETF = re.compile(r"\b(etf|etc|etn|etp|ucits|tracker|opcvm|fcp|sicav|msci|s p|stoxx|ftse|index|fund)\b")


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", (s or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", s).split())


def mots_utiles(nom: str) -> list:
    """Les mots d'un nom de titre sans le bruit des banques ni les nombres :
    « CIE DE SAINT-GOBAIN » -> ["saint", "gobain"]."""
    return [m for m in _norm(nom).split() if m not in _BRUIT and not m.isdigit()]


_index = None   # construit au premier import d'un relevé (les listes pèsent ~6 000 lignes)


def _construire():
    """{isin: [tickers]} (catalogue à la main d'abord, puis Euronext, puis
    Xetra) et [(mots, isin)] des noms d'actions."""
    global _index
    if _index is not None:
        return _index
    try:
        from titres_listes import TITRES as LISTES   # fabriqué par tests/generer_titres.py
    except ImportError:
        LISTES = []
    par_isin, noms = {}, []
    for isin, sym, nom, autres in TITRES:
        par_isin.setdefault(isin, []).append(sym)
        # Noms d'actions seulement : le nom d'un ETF ne se compare pas mot à
        # mot (« Amundi MSCI World » ressemble à dix autres fonds)
        if not _ETF.search(_norm(nom)):
            noms += [(frozenset(mots_utiles(n)), isin, 0) for n in [nom] + [a for a in autres.split("|") if a]]
    for isin, sym, nom, genre in LISTES:
        if sym not in par_isin.setdefault(isin, []):
            par_isin[isin].append(sym)
        if genre == "action" and not _ETF.search(_norm(nom)):
            noms.append((frozenset(mots_utiles(nom)), isin, 1))
    _index = (par_isin, [n for n in noms if n[0]])
    return _index


def cotations(isin: str) -> list:
    """Les tickers Yahoo connus d'un ISIN (sa place d'origine, Xetra…), ou []."""
    return list(_construire()[0].get((isin or "").strip().upper(), []))


def par_nom(nom: str) -> list:
    """Les ISIN des actions dont tous les mots d'un des noms se retrouvent dans
    `nom` : le nom le plus long l'emporte (« Dassault Systèmes » plutôt que
    « Dassault »), le catalogue écrit à la main avant les listes des bourses.
    Plusieurs ISIN quand plusieurs titres conviennent autant (Alphabet A et
    C) : la vérification par les prix payés tranche. Un nom de fonds (ETF,
    OPCVM) n'est jamais rapproché d'une action : « AXA IM Nasdaq 100 UCITS
    ETF » n'est pas AXA."""
    n = _norm(nom)
    if not n or _ETF.search(n):
        return []
    mots = set(mots_utiles(nom))
    trouves = [(len(m), -src, isin) for m, isin, src in _construire()[1] if m <= mots]
    if not trouves:
        return []
    best = max(t[0] for t in trouves)
    out = []
    for _, _, isin in sorted(t for t in trouves if t[0] == best)[::-1]:
        if isin not in out:
            out.append(isin)
    return out[:4]
