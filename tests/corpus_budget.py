"""Corpus d'entraînement de l'import des relevés dans Mes comptes.

Fabrique des relevés de compte courant aux formats réels des banques
françaises et des néobanques (en-têtes, séparateurs, encodages, lignes de
compte avant l'en-tête, libellés tels que chaque banque les écrit), d'après
les exemples publiés par d'autres projets libres (Carbure, My-PiggyBank,
gleba : voir docs/modules/comptes.md). Chaque opération porte sa bonne
réponse : date, montant signé, notion attendue (ou None : à classer).

Tout est fictif et tiré au sort avec une graine fixe : le même corpus à
chaque lancement, aucun vrai relevé dans le dépôt (il est public).
"""
import base64
import io
import random
import zipfile

# ─── Marchands tels qu'ils apparaissent sur un relevé ───────────────────────
# (nom imprimé par la banque, notion attendue, genres possibles)
C, P, V = "carte", "prelevement", "virement"
MARCHANDS = [
    # Courses
    ("CARREFOUR MARKET", "courses", C), ("CARREFOUR CITY", "courses", C), ("CRF EXPRESS", "courses", C),
    ("CARREFOUR", "courses", C), ("E.LECLERC", "courses", C), ("LECLERC", "courses", C),
    ("SCADIF E LECLERC", "courses", C), ("AUCHAN SUPERMARCHE", "courses", C), ("AUCHAN", "courses", C),
    ("INTERMARCHE", "courses", C), ("ITM ALIMENTAIRE", "courses", C), ("LIDL", "courses", C),
    ("LIDL 1234", "courses", C), ("ALDI MARCHE", "courses", C), ("SUPER U", "courses", C),
    ("HYPER U", "courses", C), ("U EXPRESS", "courses", C), ("MONOPRIX", "courses", C),
    ("MONOP", "courses", C), ("FRANPRIX", "courses", C), ("CASINO SUPERMARCHE", "courses", C),
    ("PICARD SURGELES", "courses", C), ("NETTO", "courses", C), ("BIOCOOP", "courses", C),
    ("NATURALIA", "courses", C), ("GRAND FRAIS", "courses", C), ("LA VIE CLAIRE", "courses", C),
    ("CORA", "courses", C), ("SPAR", "courses", C), ("VIVAL", "courses", C), ("G20", "courses", C),
    ("BOUCHERIE DU MARCHE", "courses", C), ("FROMAGERIE", "courses", C), ("PRIMEUR DES HALLES", "courses", C),
    ("CHRONODRIVE", "courses", C), ("LEADER PRICE", "courses", C), ("COCCINELLE", "courses", C),
    ("BOULANGERIE PAUL", "boulangerie", C), ("BOULANGERIE", "boulangerie", C),
    ("MARIE BLACHERE", "restaurant", C), ("AU PAIN DORE", "boulangerie", C), ("PATISSERIE", "boulangerie", C),
    # Restaurants
    ("MCDONALDS", "restaurant", C), ("MC DONALD S", "restaurant", C), ("BURGER KING", "restaurant", C),
    ("KFC", "restaurant", C), ("SUBWAY", "restaurant", C), ("STARBUCKS", "restaurant", C),
    ("DOMINOS PIZZA", "restaurant", C), ("PIZZA HUT", "restaurant", C), ("O TACOS", "restaurant", C),
    ("SUSHI SHOP", "restaurant", C), ("FIVE GUYS", "restaurant", C), ("BRIOCHE DOREE", "restaurant", C),
    ("COLUMBUS CAFE", "restaurant", C), ("BUFFALO GRILL", "restaurant", C), ("HIPPOPOTAMUS", "restaurant", C),
    ("RESTAURANT LE MARIGNAN", "restaurant", C), ("PIZZERIA NAPOLI", "restaurant", C),
    ("CREPERIE BRETONNE", "restaurant", C), ("IZLY CROUS", "restaurant", C), ("CROUS RESTO U", "restaurant", C),
    ("BRASSERIE DU PORT", "restaurant", C), ("LE PAIN QUOTIDIEN", "restaurant", C), ("KEBAB ISTANBUL", "restaurant", C),
    # Livraison
    ("UBER EATS", "livraison_repas", C), ("UBER * EATS PENDING", "livraison_repas", C),
    ("DELIVEROO", "livraison_repas", C), ("JUST EAT", "livraison_repas", C),
    # Bars
    ("BAR LE CHAT NOIR", "sorties", C), ("PUB O SULLIVANS", "sorties", C), ("V AND B", "sorties", C),
    ("NICOLAS CAVISTE", "sorties", C),
    # Transports
    ("SNCF INTERNET", "transport_commun", C), ("SNCF", "transport_commun", C), ("OUIGO", "transport_commun", C),
    ("TRAINLINE", "transport_commun", C), ("RATP", "transport_commun", C), ("NAVIGO", "transport_commun", C),
    ("COMUTITRES NAVIGO", "transport_commun", P), ("FLIXBUS", "transport_commun", C),
    ("BLABLACAR", "transport_commun", C), ("KEOLIS", "transport_commun", C), ("TCL", "transport_commun", C),
    ("TBM BORDEAUX", "transport_commun", C), ("LIME", "transport_commun", C), ("VELIB", "transport_commun", C),
    ("UBER TRIP", "taxi", C), ("UBR* PENDING.UBER.COM", "taxi", C), ("BOLT.EU", "taxi", C),
    ("G7 TAXI", "taxi", C), ("HEETCH", "taxi", C), ("TAXI PARISIEN", "taxi", C),
    ("TOTALENERGIES", "carburant", C), ("TOTAL ACCESS", "carburant", C), ("ESSO", "carburant", C),
    ("SHELL", "carburant", C), ("STATION LECLERC", "carburant", C), ("INTERMARCHE CARBU", "carburant", C),
    ("AVIA", "carburant", C), ("BP STATION", "carburant", C), ("IONITY", "carburant", C),
    ("VINCI AUTOROUTES", "peage", C), ("SANEF", "peage", C), ("APRR", "peage", C),
    ("BIP&GO", "peage", P), ("INDIGO PARKING", "peage", C), ("SAEMES", "peage", C),
    ("PAYBYPHONE", "peage", C), ("EFFIA", "peage", C), ("FLOWBIRD", "peage", C),
    ("NORAUTO", "entretien_auto", C), ("FEU VERT", "entretien_auto", C), ("SPEEDY", "entretien_auto", C),
    ("MIDAS", "entretien_auto", C), ("DEKRA CONTROLE TECHNIQUE", "entretien_auto", C),
    ("GARAGE DU CENTRE", "entretien_auto", C), ("ELEPHANT BLEU", "entretien_auto", C),
    # Vacances
    ("AIR FRANCE", "vacances", C), ("EASYJET", "vacances", C), ("RYANAIR", "vacances", C),
    ("TRANSAVIA", "vacances", C), ("VOLOTEA", "vacances", C), ("BOOKING.COM", "vacances", C),
    ("AIRBNB", "vacances", C), ("IBIS BUDGET", "vacances", C), ("HOTEL MERCURE", "vacances", C),
    ("CENTER PARCS", "vacances", C), ("PIERRE ET VACANCES", "vacances", C), ("CAMPING LES PINS", "vacances", C),
    ("EXPEDIA", "vacances", C), ("OPODO", "vacances", C),
    # Logement
    ("FONCIA", "loyer", V), ("NEXITY", "loyer", V), ("LOYER", "loyer", V), ("CROUS", "loyer", P),
    ("STUDAPART", "loyer", V), ("SYNDIC COPROPRIETE", "copro", V),
    ("EDF", "energie", P), ("EDF CLIENTS PARTICULIERS", "energie", P), ("ENGIE", "energie", P),
    ("TOTALENERGIES ELECTRICITE ET GAZ", "energie", P), ("EKWATEUR", "energie", P),
    ("MINT ENERGIE", "energie", P), ("OHM ENERGIE", "energie", P), ("ENI GAS POWER", "energie", P),
    ("VEOLIA EAU", "eau", P), ("EAU DE PARIS", "eau", P), ("SAUR", "eau", P), ("SUEZ EAU FRANCE", "eau", P),
    ("FREE HAUTDEBIT", "internet", P), ("ORANGE INTERNET", "internet", P), ("SFR BOX", "internet", P),
    ("BOUYGUES TELECOM BBOX", "internet", P),
    # Téléphone
    ("FREE MOBILE", "telephone", P), ("ORANGE SA", "telephone", P), ("SOSH", "telephone", P),
    ("SFR", "telephone", P), ("RED BY SFR", "telephone", P), ("BOUYGUES TELECOM", "telephone", P),
    ("B AND YOU", "telephone", P), ("LA POSTE MOBILE", "telephone", P), ("PRIXTEL", "telephone", P),
    # Assurances et santé
    ("MAIF", "assurance", P), ("MACIF", "assurance", P), ("MATMUT", "assurance", P), ("AXA FRANCE", "assurance", P),
    ("ALLIANZ IARD", "assurance", P), ("GROUPAMA", "assurance", P), ("DIRECT ASSURANCE", "assurance", P),
    ("LEOCARE", "assurance", P), ("GMF ASSURANCES", "assurance", P),
    ("MGEN", "mutuelle", P), ("HARMONIE MUTUELLE", "mutuelle", P), ("ALAN SA", "mutuelle", P),
    ("MALAKOFF HUMANIS", "mutuelle", P), ("SMEREP", "mutuelle", P), ("HEYME", "mutuelle", P),
    ("PHARMACIE DU CENTRE", "pharmacie", C), ("GRANDE PHARMACIE", "pharmacie", C),
    ("PHARMACIE DE LA GARE", "pharmacie", C), ("DR MARTIN", "medecin", C), ("DOCTOLIB", "medecin", C),
    ("CABINET MEDICAL", "medecin", C), ("LABORATOIRE CERBALLIANCE", "medecin", C), ("KINE DUPUIS", "medecin", C),
    ("OPTIC 2000", "optique", C), ("AFFLELOU", "optique", C), ("KRYS", "optique", C),
    ("CABINET DENTAIRE", "optique", C),
    # Abonnements
    ("NETFLIX.COM", "streaming", P), ("NETFLIX", "streaming", C), ("SPOTIFY", "streaming", C),
    ("SPOTIFY P1234ABCD", "streaming", C), ("DEEZER", "streaming", C), ("DISNEY PLUS", "streaming", C),
    ("CANAL+", "streaming", P), ("AMAZON PRIME", "streaming", C), ("YOUTUBE PREMIUM", "streaming", C),
    ("GOOGLE *YOUTUBE", "streaming", C), ("APPLE.COM/BILL", "logiciels", C), ("GOOGLE STORAGE", "logiciels", C),
    ("MICROSOFT*365", "logiciels", C), ("PLAYSTATION NETWORK", "logiciels", C), ("STEAMPOWERED.COM", "logiciels", C),
    ("DROPBOX", "logiciels", C), ("ADOBE", "logiciels", C), ("OPENAI *CHATGPT", "logiciels", C),
    ("NORDVPN", "logiciels", C), ("DUOLINGO", "logiciels", C), ("OVH SAS", "logiciels", P),
    ("BASIC FIT", "salle_sport", P), ("BASIC-FIT", "salle_sport", C), ("FITNESS PARK", "salle_sport", P),
    ("KEEPCOOL", "salle_sport", P), ("L ORANGE BLEUE", "salle_sport", P), ("NEONESS", "salle_sport", P),
    ("ARKOSE", "salle_sport", C),
    # Shopping
    ("AMAZON PAYMENTS", "shopping", C), ("AMZN MKTP FR", "shopping", C), ("AMAZON.FR", "shopping", C),
    ("ALIEXPRESS", "shopping", C), ("TEMU.COM", "shopping", C), ("VINTED", "vetements", C),
    ("ZARA", "vetements", C), ("H&M", "vetements", C), ("UNIQLO", "vetements", C), ("PRIMARK", "vetements", C),
    ("KIABI", "vetements", C), ("CELIO", "vetements", C), ("JULES", "vetements", C), ("ZALANDO", "vetements", C),
    ("SHEIN", "vetements", C), ("GALERIES LAFAYETTE", "vetements", C), ("PROMOD", "vetements", C),
    ("DECATHLON", "sport", C), ("INTERSPORT", "sport", C), ("GO SPORT", "sport", C), ("COURIR", "sport", C),
    ("FNAC", "culture", C), ("CULTURA", "culture", C), ("LIBRAIRIE GIBERT", "culture", C),
    ("UGC CINE CITE", "culture", C), ("PATHE", "culture", C), ("CINEMA LE GRAND REX", "culture", C),
    ("TICKETMASTER", "culture", C), ("MUSEE DU LOUVRE", "culture", C), ("DISNEYLAND PARIS", "culture", C),
    ("DARTY", "electronique", C), ("BOULANGER", "electronique", C), ("LDLC", "electronique", C),
    ("APPLE STORE", "electronique", C), ("BACK MARKET", "electronique", C), ("CDISCOUNT", "electronique", C),
    ("IKEA", "maison", C), ("LEROY MERLIN", "maison", C), ("CASTORAMA", "maison", C),
    ("MAISONS DU MONDE", "maison", C), ("ACTION", "maison", C), ("GIFI", "maison", C),
    ("BRICO DEPOT", "maison", C), ("LA FOIR FOUILLE", "maison", C),
    ("SEPHORA", "beaute", C), ("NOCIBE", "beaute", C), ("YVES ROCHER", "beaute", C),
    ("COIFFURE BEAUTE", "beaute", C), ("JEAN LOUIS DAVID", "beaute", C), ("BARBER SHOP", "beaute", C),
    ("TABAC DE LA MAIRIE", "tabac", C), ("FDJ", "tabac", C), ("RELAY", "tabac", C),
    ("INTERFLORA", "cadeaux", C), ("WONDERBOX", "cadeaux", C),
    ("MAXI ZOO", "animaux", C), ("CLINIQUE VETERINAIRE", "animaux", C), ("ZOOPLUS", "animaux", C),
    ("CROIX ROUGE FRANCAISE", "dons", P), ("RESTOS DU COEUR", "dons", V), ("HELLOASSO", "dons", C),
    ("UNIVERSITE DE TOULON", "education", C), ("CVEC", "education", C), ("UDEMY", "education", C),
    ("OPENCLASSROOMS", "education", P),
    ("DGFIP IMPOT", "impots", P), ("DIRECTION GENERALE DES FINANCES PUBLIQUES", "impots", P),
    ("TRESOR PUBLIC", "impots", P), ("AMENDES.GOUV", "impots", C), ("ANTS", "impots", C),
    ("COFIDIS", "credit", P), ("CETELEM", "credit", P), ("ONEY", "credit", P), ("KLARNA", "credit", C),
    ("LA POSTE", "shopping", C), ("COLISSIMO", "shopping", C), ("MONDIAL RELAY", "shopping", C),
]

# Marchands que Pilote ne peut pas connaître : ils doivent rester « à classer »
INCONNUS = [
    "SARL DUMONT ET FILS", "ETS ROBERT", "SC2M", "SAS LEBLANC", "SUMUP *JEAN-PIERRE", "PAYPAL EUROPE",
    "SQ *ATELIER 42", "ZETTLE_*MARIE L.", "SNC GARNIER", "LES JARDINS DE VALERIE", "ABC DIFFUSION",
    "MAISON PERRIN", "STRIPE*KZX", "AU COMPTOIR DE THEO", "LE COIN DE JULIE", "ASSOC 1901 LAMBDA",
    "SPRL MEYER", "GIE MOYENS", "MULTISERVICES 83", "NOMAD SARL", "ETABLISSEMENTS COLIN",
]

# Revenus : (tiers, motif, notion)
REVENUS = [
    ("EMPLOYEUR SA", "SALAIRE {mois}", "salaire"), ("SOCIETE GENERALE DE SERVICES", "PAIE {mois}", "salaire"),
    ("SAS ACME INDUSTRIE", "SALAIRE", "salaire"), ("THALES SERVICES", "VIREMENT DE SALAIRE", "salaire"),
    ("CAF DU VAR", "ALLOCATIONS FAMILIALES", "aides"), ("CAF", "APL {mois}", "aides"),
    ("CPAM DU VAR", "REMBOURSEMENT SOINS", "secu"), ("CPAM PARIS", "PRESTATIONS", "secu"),
    ("MGEN", "REMBOURSEMENT", "mutuelle_remb"), ("HARMONIE MUTUELLE", "REMBT SOINS", "mutuelle_remb"),
    ("FRANCE TRAVAIL", "ALLOCATION ARE", "chomage"), ("CARSAT SUD EST", "PENSION", "retraite"),
    ("DGFIP", "REMBOURSEMENT IMPOT", "remboursement"),
]
PERSONNES = ["M MARTIN DUPONT", "MME CLAIRE PETIT", "LUCAS BERNARD", "M ET MME DURAND", "SOPHIE LAMBERT",
             "PAUL ROUSSEAU", "JULES FONTAINE", "NICOLAS MOREAU"]
VILLES = ["PARIS", "LYON", "TOULON", "MARSEILLE", "NANTES", "LILLE", "BORDEAUX", "PARIS 15", "LA SEYNE SUR M",
          "HYERES", "RENNES", "NICE"]
MOIS = ["JANVIER", "FEVRIER", "MARS", "AVRIL", "MAI", "JUIN", "JUILLET", "AOUT", "SEPTEMBRE", "OCTOBRE",
        "NOVEMBRE", "DECEMBRE"]


class Op:
    def __init__(self, date, montant, notion, genre, nom, interne=False):
        self.date, self.montant, self.notion, self.genre, self.nom, self.interne = date, montant, notion, genre, nom, interne
        self.libelle = ""


def _ops(rng, n, annee=2026):
    """n opérations fictives d'un compte courant, avec leur bonne réponse."""
    ops = []
    mois = rng.randint(1, 12)
    for _ in range(n):
        j = rng.randint(1, 28)
        date = "%04d-%02d-%02d" % (annee, mois, j)
        x = rng.random()
        if x < 0.70:
            nom, notion, genre = rng.choice(MARCHANDS)
            mt = -round(rng.choice([rng.uniform(1.5, 25), rng.uniform(10, 120), rng.uniform(50, 900)]), 2)
            ops.append(Op(date, mt, notion, genre, nom))
        elif x < 0.80:
            ops.append(Op(date, -round(rng.uniform(3, 200), 2), None, rng.choice([C, C, P]), rng.choice(INCONNUS)))
        elif x < 0.86:
            tiers, motif, notion = rng.choice(REVENUS)
            ops.append(Op(date, round(rng.uniform(30, 3500), 2), notion, V, tiers))
            ops[-1].motif = motif.format(mois=MOIS[mois - 1])
        elif x < 0.90:
            ops.append(Op(date, -round(rng.choice([20, 40, 50, 60, 100, 150]), 2), "retrait", "retrait", ""))
        elif x < 0.94:
            p = rng.choice(PERSONNES)
            sens = rng.choice([-1, 1])
            ops.append(Op(date, sens * round(rng.uniform(5, 300), 2), None, V, p))
            ops[-1].motif = rng.choice(["MERCI", "CADEAU", "", "WEEK END", "POUR TOI"])
        elif x < 0.97:
            # Virement vers l'épargne : ni dépense ni revenu
            dest = rng.choice(["LIVRET A", "LDDS", "PEA", "ASSURANCE VIE", "COMPTE EPARGNE", "TRADE REPUBLIC"])
            ops.append(Op(date, -round(rng.choice([50, 100, 200, 300, 500]), 2), None, V, dest, interne=True))
        else:
            frais = rng.choice([("COTISATION CARTE VISA PREMIER", "frais_carte"), ("FRAIS TENUE DE COMPTE", "frais_tenue"),
                                ("COMMISSION D'INTERVENTION", "agios"), ("INTERETS DEBITEURS", "agios"),
                                ("FRAIS PAIEMENT HORS ZONE EURO", "frais")])
            ops.append(Op(date, -round(rng.uniform(1, 45), 2), frais[1], "frais", frais[0]))
    ops.sort(key=lambda o: o.date, reverse=rng.random() < 0.7)
    return ops


def _jjmm(d, sep="/"):
    return d[8:10] + sep + d[5:7]


def _fr(d, sep="/", an4=True):
    return d[8:10] + sep + d[5:7] + sep + (d[:4] if an4 else d[2:4])


def _mt_fr(x, milliers=" ", signe=True):
    s = "%.2f" % (x if signe else abs(x))
    ent, dec = s.split(".")
    neg = ent.startswith("-")
    ent = ent.lstrip("-")
    if milliers and len(ent) > 3:
        ent = ent[:-3] + milliers + ent[-3:]
    return ("-" if neg else "") + ent + "," + dec


def _carte4(rng):
    return "%04d" % rng.randint(0, 9999)


# Libellé « à la manière » d'une banque
def libelle(style, o, rng):
    if o.genre == "retrait":
        return {"sg": "RETRAIT DAB %s %s" % (_jjmm(o.date), rng.choice(VILLES)),
                "bnp": "RETRAIT DAB %s %s CARTE 4974XXXXXXXX%s" % (o.date[8:10] + o.date[5:7] + o.date[2:4], rng.choice(VILLES), _carte4(rng)),
                "neo": "Cash withdrawal",
                }.get(style, "RETRAIT DAB %s %s" % (_fr(o.date, "/", False), rng.choice(VILLES)))
    if o.genre == "frais":
        return o.nom
    if o.genre == V:
        motif = getattr(o, "motif", "")
        if o.interne:
            return rng.choice(["VIR SEPA EMIS VERS %s" % o.nom, "VIREMENT VERS %s" % o.nom, "VIR %s" % o.nom,
                               "VIR INTERNE %s" % o.nom, "VIR PERMANENT %s" % o.nom])
        if o.montant > 0:
            return rng.choice([
                "VIR SEPA RECU /DE %s /MOTIF %s" % (o.nom, motif),
                "VIR RECU %07d DE: %s MOTIF: %s REF: %d" % (rng.randint(0, 9999999), o.nom, motif, rng.randint(1000, 9999)),
                "VIREMENT DE %s %s" % (o.nom, motif),
                "VIR INST RECU DE %s %s" % (o.nom, motif),
            ]).strip()
        if o.notion:
            return rng.choice(["VIR SEPA EMIS VERS %s %s" % (o.nom, rng.choice(MOIS)), "VIREMENT %s" % o.nom,
                               "VIR %s LOYER" % o.nom if o.notion == "loyer" else "VIR %s" % o.nom])
        return rng.choice(["VIR SEPA EMIS /POUR %s /MOTIF %s" % (o.nom, motif), "VIREMENT POUR %s" % o.nom,
                           "VIR INST EMIS VERS %s" % o.nom])
    if o.genre == P:
        ref = "%010d" % rng.randint(0, 9999999999)
        return rng.choice(["PRLV SEPA %s %s" % (o.nom, ref),
                           "PRELEVEMENT EUROPEEN %s ECH/%s ID EMETTEUR/FR12ZZZ%06d" % (o.nom, o.date[8:10] + o.date[5:7] + o.date[2:4], rng.randint(0, 999999)),
                           "PRLV %s" % o.nom,
                           "PRLV SEPA %s REF:%s" % (o.nom, ref)])
    v = rng.choice(VILLES)
    n = o.nom
    return {
        "sg": "CARTE X%s %s %s" % (_carte4(rng), _jjmm(o.date), n),
        "cm": "PAIEMENT CB %s %s %s CARTE 4974XXXXXXXX%s" % (o.date[8:10] + o.date[5:7], v, n, _carte4(rng)),
        "lbp": "ACHAT CB %s %s CARTE NUMERO %03d" % (n, _fr(o.date, ".", False), rng.randint(0, 999)),
        "bnp": "FACTURE CARTE DU %s %s CARTE 4974XXXXXXXX%s" % (o.date[8:10] + o.date[5:7] + o.date[2:4], n, _carte4(rng)),
        "ca": rng.choice(["CB %s %s" % (n, o.date[8:10] + o.date[5:7] + o.date[2:4]),
                          "PAIEMENT PAR CARTE X%s %s %s" % (_carte4(rng), n, _jjmm(o.date))]),
        "bpce": "CB %s FACT %s" % (n, o.date[8:10] + o.date[5:7] + o.date[2:4]),
        "fortuneo": "CARTE %s %s %s" % (_jjmm(o.date), n, v),
        "bourso": "CARTE %s %s CB*%s" % (_fr(o.date, "/", False), n, _carte4(rng)),
        "lcl": "CB  %s  %s" % (n, _fr(o.date, "/", False)),
        "neo": n.title() if rng.random() < 0.6 else n,
    }[style]


# ─── Formats de fichiers ─────────────────────────────────────────────────────

def _csv(lignes, sep=";"):
    def cell(c):
        c = str(c)
        return '"' + c.replace('"', '""') + '"' if (sep in c or '"' in c or "\n" in c) else c
    return "\r\n".join(sep.join(cell(c) for c in l) for l in lignes) + "\r\n"


def f_sg(ops, rng):
    l = [['="0123400012345678"', "01/01/2026", "31/01/2026", "3", "31/01/2026", "1 234,56 EUR"], [""],
         ["Date de l'opération", "Libellé", "Détail de l'écriture", "Montant de l'opération", "Devise"]]
    for o in ops:
        o.libelle = libelle("sg", o, rng)
        court = " ".join(o.libelle.split()[:3])
        l.append([_fr(o.date), court, o.libelle + " ", _mt_fr(o.montant, ""), "EUR"])
    return _csv(l).encode("cp1252"), "sg.csv"


def f_ca(ops, rng):
    l = [["Téléchargement du 13/10/2026"], [""], ["M. DUPONT MARTIN"], [""],
         ["Compte de Dépôt carte n° 12345678901"], ["Solde au 13/10/2026 1 234,56 €"], [""],
         ["Liste des opérations du compte entre le 01/09/2026 et le 13/10/2026"], [""],
         ["Date", "Libellé", "Débit euros", "Crédit euros", ""]]
    for o in ops:
        o.libelle = libelle("ca", o, rng)
        # Libellé sur plusieurs lignes, comme le Crédit Agricole
        lib = o.libelle if rng.random() < 0.5 else o.libelle.replace(" ", "\n    ", 1)
        l.append([_fr(o.date), lib, _mt_fr(-o.montant) if o.montant < 0 else "",
                  _mt_fr(o.montant) if o.montant > 0 else "", ""])
    return _csv(l).encode("cp1252"), "CA20261013.csv"


def f_bnp(ops, rng):
    sep = rng.choice([";", ","]) if False else ";"
    l = [["Compte de chèques", "Compte de chèques", "****1234", "13/10/2026", "", "1 234,56"], ["", "", "", ""],
         ["Date operation", "Categorie operation", "Sous Categorie operation", "Libelle operation", "Montant operation"]]
    cats = {"courses": ("Alimentation", "Supermarché"), "restaurant": ("Loisirs", "Restaurants"),
            "salaire": ("Revenus", "Salaires"), "carburant": ("Auto & Transports", "Carburant")}
    for o in ops:
        o.libelle = libelle("bnp", o, rng)
        c, s = cats.get(o.notion, ("A catégoriser", "")) if rng.random() < 0.8 else ("Divers", "")
        l.append([_fr(o.date, "-"), c, s, o.libelle, _mt_fr(o.montant)])
    return _csv(l, sep).encode("utf-8-sig"), "E1234567.csv"


def f_bpce(ops, rng):
    l = [["Date de comptabilisation", "Libelle simplifie", "Libelle operation", "Reference",
          "Informations complementaires", "Type operation", "Categorie", "Sous categorie", "Debit", "Credit",
          "Date operation", "Date de valeur", "Pointage operation"]]
    types = {C: "Paiement carte", P: "Prelevement", V: "Virement", "retrait": "Retrait", "frais": "Frais"}
    for o in ops:
        o.libelle = libelle("bpce", o, rng)
        court = o.nom or "RETRAIT"
        l.append([_fr(o.date), court, o.libelle, "XX%09d" % rng.randint(0, 999999999), "",
                  types.get(o.genre, "") + (" recu" if o.genre == V and o.montant > 0 else ""),
                  "", "", _mt_fr(o.montant, "") if o.montant < 0 else "", _mt_fr(o.montant, "") if o.montant > 0 else "",
                  _fr(o.date), _fr(o.date), "0"])
    return _csv(l).encode(rng.choice(["utf-8", "cp1252"])), "telechargement.csv"


def f_cm(ops, rng):
    l = [["Date", "Date de valeur", "Débit", "Crédit", "Libellé", "Solde"]]
    solde = 1500.0
    for o in ops:
        o.libelle = libelle("cm", o, rng)
        solde += o.montant
        l.append([_fr(o.date), _fr(o.date), _mt_fr(o.montant, "") if o.montant < 0 else "",
                  _mt_fr(o.montant, "") if o.montant > 0 else "", o.libelle, _mt_fr(solde, "")])
    return _csv(l).encode("cp1252"), "export.csv"


def f_lbp(ops, rng):
    l = [["Numéro Compte ", "0123456X020"], ["Type ", "CCP"], ["Compte tenu en ", "euros"],
         ["Date ", "13/10/2026"], ["Solde (EUROS) ", "1 234,56"], ["Solde (FRANCS) ", "8 098,51"], [""],
         ["Date", "Libellé", "Montant(EUROS)", "Montant(FRANCS)"]]
    for o in ops:
        o.libelle = libelle("lbp", o, rng)
        l.append([_fr(o.date), '"%s"' % o.libelle if False else o.libelle, _mt_fr(o.montant), _mt_fr(o.montant * 6.55957)])
    return _csv(l).encode("cp1252"), "releve_CCP.csv"


def f_fortuneo(ops, rng):
    l = [["Date opération", "Date valeur", "libellé", "Débit", "Crédit", ""]]
    for o in ops:
        o.libelle = libelle("fortuneo", o, rng)
        d = ("%.2f" % o.montant).replace(".", ",").rstrip("0").rstrip(",")
        l.append([_fr(o.date), _fr(o.date), o.libelle, d if o.montant < 0 else "", d if o.montant > 0 else "", ""])
    return _csv(l).encode("latin-1"), "HistoriqueOperations_123.csv"


def f_bourso(ops, rng):
    l = [["dateOp", "dateVal", "label", "category", "categoryParent", "supplierFound", "amount", "comment",
          "accountNum", "accountLabel", "accountbalance"]]
    for o in ops:
        o.libelle = libelle("bourso", o, rng)
        l.append([o.date, o.date, o.libelle, "Non catégorisé", "Divers", "", _mt_fr(o.montant, " "), "",
                  "00012345678", "BoursoBank", "1234.56"])
    return _csv(l).encode("utf-8"), "export-operations-13-10-2026.csv"


def f_lcl(ops, rng):
    # Sans en-tête : date ; montant ; type ; ; libellé ; ; ;
    l = []
    types = {C: "Carte", P: "Prélèvement", V: "Virement", "retrait": "Carte", "frais": "Frais"}
    for o in ops:
        o.libelle = libelle("lcl", o, rng)
        l.append([_fr(o.date), _mt_fr(o.montant, ""), types.get(o.genre, ""), "", o.libelle, "", "", ""])
    l.append(["13/10/2026", "1234,56", "", "Solde", "", "", "", ""])
    return _csv(l).encode("cp1252"), "CA00012345.csv"


def f_n26(ops, rng):
    l = [["Booking Date", "Value Date", "Partner Name", "Partner Iban", "Type", "Payment Reference",
          "Account Name", "Amount (EUR)", "Original Amount", "Original Currency", "Exchange Rate"]]
    types = {C: "Presentment", P: "Direct Debit", V: "Credit Transfer", "retrait": "Presentment", "frais": "Fee"}
    for o in ops:
        o.libelle = libelle("neo", o, rng) if o.genre in (C, "retrait") else (o.nom or "N26")
        ref = getattr(o, "motif", "")
        l.append([o.date, o.date, o.libelle, "FR7630001007941234567890185" if o.genre == V else "",
                  types.get(o.genre, "") if o.montant < 0 or o.genre != V else "Income", ref, "Compte principal",
                  "%.2f" % o.montant, "", "", ""])
    txt = "\n".join(",".join('"%s"' % c for c in r) for r in l) + "\n"
    return txt.encode("utf-8"), "n26-csv-transactions.csv"


def f_revolut(ops, rng):
    l = [["Type", "Product", "Started Date", "Completed Date", "Description", "Amount", "Fee", "Currency", "State", "Balance"]]
    types = {C: "CARD_PAYMENT", P: "CARD_PAYMENT", V: "TRANSFER", "retrait": "ATM", "frais": "FEE"}
    for o in ops:
        if o.genre == V:
            o.libelle = ("To " if o.montant < 0 else "Payment from ") + (o.nom.title() if o.nom else "")
            if o.interne:
                o.libelle = "To pocket EUR " + o.nom.title()
        else:
            o.libelle = libelle("neo", o, rng)
        l.append([types.get(o.genre, "CARD_PAYMENT"), "Current", o.date + " 12:00:00", o.date + " 14:00:00",
                  o.libelle, "%.2f" % o.montant, "0.00", "EUR", "COMPLETED", "100.00"])
    # Une ligne en attente et une refusée : ignorées
    l.append(["CARD_PAYMENT", "Current", "2026-12-30 10:00:00", "", "Cinema", "-12.00", "0.00", "EUR", "PENDING", ""])
    l.append(["TRANSFER", "Current", "2026-12-30 11:00:00", "2026-12-30 11:00:05", "To X", "-50.00", "0.00", "EUR", "REVERTED", ""])
    return _csv(l, ",").encode("utf-8"), "account-statement_2026.csv"


def f_qonto(ops, rng):
    l = [["Statut", "Date de la valeur (UTC)", "Date de l'opération (UTC)", "Montant total (TTC)", "Débit",
          "Crédit", "Solde", "Devise", "Nom de la contrepartie", "IBAN de la contrepartie", "Méthode de paiement",
          "Identifiant de transaction", "Référence", "Catégorie de trésorerie"]]
    meth = {C: "Carte", P: "Prélèvement", V: "Virement", "retrait": "Carte", "frais": "Frais"}
    for o in ops:
        o.libelle = libelle("neo", o, rng) if o.genre != V else o.nom
        if o.genre == "retrait":
            o.libelle = "Retrait DAB"
        m = _mt_fr(o.montant, "")
        l.append(["Exécuté", _fr(o.date, "-") + " 09:30:00", _fr(o.date, "-") + " 09:00:00", m,
                  m if o.montant < 0 else "", m if o.montant > 0 else "", "950,10", "EUR", o.libelle, "",
                  meth.get(o.genre, ""), "txn_%04d" % rng.randint(0, 9999), getattr(o, "motif", ""), ""])
    l.append(["Refusé", "12-01-2026 10:00:00", "12-01-2026 10:00:00", "-15,00", "-15,00", "", "2150,10", "EUR",
              "Taxi", "", "Carte", "txn_9999", "", "Transport"])
    return _csv(l).encode("utf-8"), "qonto.csv"


def f_tr(ops, rng):
    cols = ["datetime", "date", "account_type", "category", "type", "asset_class", "name", "symbol", "shares",
            "price", "amount", "fee", "tax", "currency", "original_amount", "original_currency", "fx_rate",
            "description", "transaction_id", "counterparty_name", "counterparty_iban", "payment_reference", "mcc_code"]
    l = [cols]
    for o in ops:
        o.libelle = o.nom.title() if o.nom else "ATM"
        typ = {C: "CARD_TRANSACTION", P: "DIRECT_DEBIT", V: "TRANSFER_INSTANT_OUTBOUND" if o.montant < 0 else "TRANSFER_INSTANT_INBOUND",
               "retrait": "CARD_TRANSACTION", "frais": "FEE"}.get(o.genre, "CARD_TRANSACTION")
        desc = ("Card transaction " + o.libelle) if o.genre == C else o.libelle
        if o.genre == "retrait":
            desc = "ATM withdrawal"
        l.append([o.date + "T12:00:00.000Z", o.date, "DEFAULT", "CASH", typ, "", "", "", "", "", "%.2f" % o.montant,
                  "", "", "EUR", "", "", "", desc, "tr-%08d" % rng.randint(0, 99999999),
                  o.libelle if o.genre in (V, C) else "", "", getattr(o, "motif", ""), ""])
    # Une ligne de bourse du même export : pas du budget
    l.append(["2026-03-01T10:00:00.000Z", "2026-03-01", "DEFAULT", "TRADING", "BUY", "STOCK", "Apple",
              "US0378331005", "1", "150", "-150.00", "-1", "", "EUR", "", "", "", "Buy trade", "tr-x", "", "", "", ""])
    return _csv(l, ",").encode("utf-8"), "trade-republic-export.csv"


def f_ofx(ops, rng):
    xml = rng.random() < 0.4
    corps = []
    types = {C: "POS", P: "DIRECTDEBIT", V: "XFER", "retrait": "ATM", "frais": "FEE"}
    for i, o in enumerate(ops):
        o.libelle = libelle(rng.choice(["sg", "cm", "bpce", "ca"]), o, rng)
        nom, memo = o.libelle[:32], o.libelle[32:]
        d = o.date.replace("-", "")
        if xml:
            corps.append("<STMTTRN><TRNTYPE>%s</TRNTYPE><DTPOSTED>%s</DTPOSTED><TRNAMT>%.2f</TRNAMT><FITID>%d</FITID>"
                         "<NAME>%s</NAME>%s</STMTTRN>" % (types.get(o.genre, "OTHER"), d, o.montant, i,
                                                          nom.replace("&", "&amp;"), "<MEMO>%s</MEMO>" % memo.replace("&", "&amp;") if memo else ""))
        else:
            corps.append("<STMTTRN>\r\n<TRNTYPE>%s\r\n<DTPOSTED>%s120000[+1:CET]\r\n<TRNAMT>%s\r\n<FITID>%d\r\n<NAME>%s\r\n%s</STMTTRN>"
                         % (types.get(o.genre, "OTHER"), d, ("%.2f" % o.montant).replace(".", rng.choice([".", ","])),
                            i, nom.replace("&", "&amp;"), ("<MEMO>%s\r\n" % memo.replace("&", "&amp;")) if memo else ""))
    if xml:
        txt = ('<?xml version="1.0" encoding="UTF-8"?>\n<?OFX OFXHEADER="200" VERSION="220"?>\n<OFX><BANKMSGSRSV1>'
               "<STMTTRNRS><STMTRS><CURDEF>EUR</CURDEF><BANKTRANLIST>" + "".join(corps) +
               "</BANKTRANLIST></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>")
        return txt.encode("utf-8"), "releve.ofx"
    txt = ("OFXHEADER:100\r\nDATA:OFXSGML\r\nVERSION:102\r\nSECURITY:NONE\r\nENCODING:USASCII\r\nCHARSET:1252\r\n"
           "COMPRESSION:NONE\r\nOLDFILEUID:NONE\r\nNEWFILEUID:NONE\r\n\r\n<OFX>\r\n<BANKMSGSRSV1>\r\n<STMTTRNRS>\r\n"
           "<STMTRS>\r\n<CURDEF>EUR\r\n<BANKTRANLIST>\r\n" + "\r\n".join(corps) + "\r\n</BANKTRANLIST>\r\n</STMTRS>\r\n"
           "</STMTTRNRS>\r\n</BANKMSGSRSV1>\r\n</OFX>\r\n")
    return txt.encode("cp1252"), "CA_releve.ofx"


def f_qif(ops, rng):
    l = ["!Type:Bank"]
    for o in ops:
        o.libelle = libelle(rng.choice(["sg", "lbp", "bnp", "fortuneo"]), o, rng)
        l += ["D" + _fr(o.date), "T" + ("%.2f" % o.montant).replace(".", rng.choice([".", ","])), "P" + o.libelle, "^"]
    return ("\r\n".join(l) + "\r\n").encode("cp1252"), "releve.qif"


def f_camt(ops, rng):
    nt = []
    for o in ops:
        o.libelle = libelle(rng.choice(["sg", "bpce"]), o, rng)
        nt.append("<Ntry><Amt Ccy=\"EUR\">%.2f</Amt><CdtDbtInd>%s</CdtDbtInd><BookgDt><Dt>%s</Dt></BookgDt>"
                  "<AddtlNtryInf>%s</AddtlNtryInf></Ntry>" % (abs(o.montant), "DBIT" if o.montant < 0 else "CRDT",
                                                              o.date, o.libelle.replace("&", "&amp;")))
    txt = ('<?xml version="1.0" encoding="UTF-8"?><Document xmlns="urn:iso:std:iso:20022:tech:xsd:camt.053.001.02">'
           "<BkToCstmrStmt><Stmt>" + "".join(nt) + "</Stmt></BkToCstmrStmt></Document>")
    return txt.encode("utf-8"), "camt053.xml"


def _xlsx(lignes):
    """Classeur .xlsx minimal (texte en ligne, nombres), sans bibliothèque."""
    def col(i):
        s = ""
        i += 1
        while i:
            i, r = divmod(i - 1, 26)
            s = chr(65 + r) + s
        return s
    rows = []
    for ri, l in enumerate(lignes, 1):
        cells = []
        for ci, v in enumerate(l):
            ref = col(ci) + str(ri)
            if isinstance(v, (int, float)):
                cells.append('<c r="%s"><v>%s</v></c>' % (ref, v))
            elif v != "":
                t = str(v).replace("&", "&amp;").replace("<", "&lt;")
                cells.append('<c r="%s" t="inlineStr"><is><t>%s</t></is></c>' % (ref, t))
        rows.append('<row r="%d">%s</row>' % (ri, "".join(cells)))
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                   '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')
        z.writestr("xl/workbook.xml", '<?xml version="1.0"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                   'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Operations" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels", '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
        z.writestr("xl/worksheets/sheet1.xml", '<?xml version="1.0"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
                   + "".join(rows) + "</sheetData></worksheet>")
    return b.getvalue()


def f_xlsx(ops, rng):
    """Export Excel (BNP, Crédit Agricole…) : dates en texte ou en nombre de jours, montants en nombres."""
    import datetime
    l = [["Relevé de compte"], ["Compte courant", "****1234"], [],
         ["Date", "Libellé", "Débit", "Crédit"]]
    serie = rng.random() < 0.5
    for o in ops:
        o.libelle = libelle(rng.choice(["bnp", "ca", "sg"]), o, rng)
        d = (datetime.date.fromisoformat(o.date) - datetime.date(1899, 12, 30)).days if serie else _fr(o.date)
        l.append([d, o.libelle, -o.montant if o.montant < 0 else "", o.montant if o.montant > 0 else ""])
    return _xlsx(l), "operations.xlsx"


FORMATS = [f_sg, f_ca, f_bnp, f_bpce, f_cm, f_lbp, f_fortuneo, f_bourso, f_lcl, f_n26, f_revolut, f_qonto,
           f_tr, f_ofx, f_qif, f_camt, f_xlsx]


def corpus(n=1020, graine=2026):
    """n relevés : [(nom, octets, [Op…])]."""
    rng = random.Random(graine)
    res = []
    for i in range(n):
        fmt = FORMATS[i % len(FORMATS)]
        ops = _ops(rng, rng.randint(8, 70))
        data, nom = fmt(ops, rng)
        res.append((nom, data, ops, fmt.__name__[2:]))
    return res


def b64(data):
    return base64.b64encode(data).decode()
