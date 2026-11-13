"""Jeu de validation de l'import des relevés (Mes comptes).

Écrit APRÈS le réglage du dictionnaire, sans le relire : d'autres marchands,
d'autres façons de les écrire (tronqués, collés, avec un numéro de magasin
ou la forme juridique). Sa mesure dit ce que Pilote fera sur des libellés
qu'il n'a jamais vus. Même fabrique que corpus_budget, autre graine.
"""
import corpus_budget as cb

C, P = cb.C, cb.P

VALIDATION = [
    ("CARREFOUR DAC", "courses", C), ("CARREFOURMARKET", "courses", C), ("LECLERC DRIVE", "courses", C),
    ("AUCHAN DIRECT", "courses", C), ("INTERMARCHE SUPER", "courses", C), ("PROXI SUPER", "courses", C),
    ("SUPERETTE DU PORT", "courses", C), ("EPICERIE FINE MAISON", "courses", C), ("MONOPRIX 7765", "courses", C),
    ("CASINO SHOP", "courses", C), ("ALDI 0123", "courses", C), ("LIDL FRANCE", "courses", C),
    ("SUPER U SAS", "courses", C), ("U EXPRESS VERDUN", "courses", C), ("MARCHE U", "courses", C),
    ("BIO C BON", "courses", C), ("FRANPRIX 5212", "courses", C), ("CARREF MARKET", "courses", C),
    ("HYPERMARCHE CORA", "courses", C), ("LECLERC EXPRESS", "courses", C), ("SPAR SUPERMARCHE", "courses", C),
    ("BOULANGERIE LA FOURNEE", "boulangerie", C), ("LA MIE CALINE", "restaurant", C),
    ("BOULANG PATISS", "boulangerie", C), ("PATISSERIE GOURMANDE", "boulangerie", C),
    ("MAISON KAYSER", "boulangerie", C),
    ("MCDONALDS FRANCE", "restaurant", C), ("MC DONALDS 1245", "restaurant", C),
    ("BURGER KING FRANCE", "restaurant", C), ("KFC TOULON", "restaurant", C), ("STARBUCKS COFFEE", "restaurant", C),
    ("RESTAURANT CHEZ MARCEL", "restaurant", C), ("BISTROT DU COIN", "restaurant", C),
    ("PIZZA DEL ARTE", "restaurant", C), ("SUSHI KYO", "restaurant", C), ("LA CREPERIE", "restaurant", C),
    ("CAFE DE LA PAIX", "restaurant", C), ("BRASSERIE LIPP", "restaurant", C), ("POMME DE PAIN", "restaurant", C),
    ("COTE SUSHI", "restaurant", C), ("O TACOS TOULON", "restaurant", C),
    ("UBEREATS", "livraison_repas", C), ("DELIVEROO FR", "livraison_repas", C), ("JUSTEAT", "livraison_repas", C),
    ("SNCF VOYAGEURS", "transport_commun", C), ("SNCF CONNECT", "transport_commun", C),
    ("RATP 4567", "transport_commun", C), ("TER PACA", "transport_commun", C), ("RESEAU MISTRAL", None, C),
    ("TRAINLINE.FR", "transport_commun", C),
    ("UBER *TRIP", "taxi", C), ("UBER BV", "taxi", C), ("BOLT", "taxi", C), ("TAXI G7", "taxi", C),
    ("TOTAL MARKETING FRANCE", None, C), ("TOTALENERGIES RELAIS", "carburant", C), ("ESSO EXPRESS", "carburant", C),
    ("STATION ESSO", "carburant", C), ("CARREFOUR STATION", "carburant", C), ("AGIP", "carburant", C),
    ("STATION U", "carburant", C), ("AUCHAN CARBURANT", "carburant", C),
    ("VINCI AUTOROUTE ASF", "peage", C), ("PEAGE APRR", "peage", C), ("PARKING INDIGO", "peage", C),
    ("Q-PARK FRANCE", "peage", C), ("PARKING GARE", "peage", C), ("EASYPARK", "peage", C),
    ("NORAUTO FRANCE", "entretien_auto", C), ("CONTROLE TECHNIQUE AUTOSUR", "entretien_auto", C),
    ("CARGLASS", "entretien_auto", C), ("POINT S", "entretien_auto", C),
    ("EASYJET AIRLINE", "vacances", C), ("RYANAIR LTD", "vacances", C), ("AIRBNB * HMXX", "vacances", C),
    ("BOOKING.COM HOTEL", "vacances", C), ("HOTEL IBIS STYLES", "vacances", C), ("ACCOR HOTELS", "vacances", C),
    ("CAMPING MUNICIPAL", "vacances", C), ("AIR FRANCE KLM", "vacances", C),
    ("EDF ELECTRICITE", "energie", P), ("ENGIE PARTICULIERS", "energie", P), ("TOTALENERGIES ELEC", "energie", P),
    ("EKWATEUR SAS", "energie", P), ("VEOLIA", "eau", P), ("SAUR SAS", "eau", P),
    ("FREE MOBILE SAS", "telephone", P), ("ORANGE", "telephone", P), ("SFR SA", "telephone", P),
    ("BOUYGUES TELECOM SA", "telephone", P), ("SOSH MOBILE", "telephone", P), ("FREE TELECOM", "internet", P),
    ("MAIF ASSURANCE", "assurance", P), ("MACIF SAM", "assurance", P), ("ALLIANZ", "assurance", P),
    ("AXA ASSURANCES IARD", "assurance", P), ("MATMUT SAM", "assurance", P),
    ("MGEN MUTUELLE", "mutuelle", P), ("ALAN", "mutuelle", P), ("HARMONIE MUTUELLE SA", "mutuelle", P),
    ("PHARMACIE CENTRALE", "pharmacie", C), ("PHARM DU PORT", "pharmacie", C),
    ("PARAPHARMACIE LECLERC", "pharmacie", C), ("DOCTEUR DUPONT", "medecin", C), ("CENTRE MEDICAL", "medecin", C),
    ("LABO BIOGROUP", "medecin", C), ("OPTICIEN KRYS", "optique", C), ("GRANDOPTICAL", "optique", C),
    ("NETFLIX INTERNATIONAL", "streaming", C), ("SPOTIFY AB", "streaming", C), ("DISNEY+", "streaming", C),
    ("AMAZON PRIME FR", "streaming", C), ("DEEZER SA", "streaming", C), ("CANAL PLUS", "streaming", P),
    ("APPLE.COM", "logiciels", C), ("ITUNES.COM", "logiciels", C), ("GOOGLE PLAY", "logiciels", C),
    ("MICROSOFT", "logiciels", C), ("PAYPAL *STEAM", "logiciels", C), ("NINTENDO", "logiciels", C),
    ("BASIC FIT FRANCE", "salle_sport", P), ("FITNESS PARK TOULON", "salle_sport", P),
    ("ON AIR FITNESS", "salle_sport", P),
    ("AMAZON EU SARL", "shopping", C), ("AMAZON MKTPLACE", "shopping", C), ("AMZN DIGITAL", "shopping", C),
    ("ZARA FRANCE", "vetements", C), ("H & M", "vetements", C), ("KIABI EUROPE", "vetements", C),
    ("ZALANDO SE", "vetements", C), ("CELIO FRANCE", "vetements", C), ("UNIQLO EUROPE", "vetements", C),
    ("DECATHLON FRANCE", "sport", C), ("INTERSPORT TOULON", "sport", C),
    ("FNAC DARTY", "culture", C), ("FNAC.COM", "culture", C), ("CULTURA SAS", "culture", C),
    ("UGC", "culture", C), ("PATHE CINEMAS", "culture", C), ("CINEMA PATHE", "culture", C),
    ("DARTY FRANCE", "electronique", C), ("BOULANGER SA", "electronique", C), ("LDLC.COM", "electronique", C),
    ("IKEA FRANCE", "maison", C), ("LEROY MERLIN FRANCE", "maison", C), ("CASTORAMA FRANCE", "maison", C),
    ("ACTION FRANCE", "maison", C), ("BRICOMARCHE", "maison", C),
    ("SEPHORA FRANCE", "beaute", C), ("COIFFEUR SALON ANNE", "beaute", C), ("NOCIBE FRANCE", "beaute", C),
    ("DGFIP FINANCES PUBLIQUES", "impots", P), ("IMPOTS.GOUV", "impots", C), ("TAXE FONCIERE", "impots", P),
    ("COFIDIS SA", "credit", P), ("CETELEM BNP", "credit", P),
    ("TABAC PRESSE", "tabac", C), ("LE BALTO TABAC", "tabac", C),
    ("VETERINAIRE DU PARC", "animaux", C), ("ANIMALIS", "animaux", C),
    ("CROIX-ROUGE", "dons", P), ("UNICEF FRANCE", "dons", P),
    ("UNIVERSITE AIX MARSEILLE", "education", C),
]
INCONNUS = [
    "SARL LE ZINC", "BOUTIQUE ELISE", "MAISON BLANCHE SAS", "LES DELICES D ANNA", "ETS MARTIN", "SC IMMO 2",
    "SAS HORIZON", "L ATELIER", "SUMUP *MARC", "SQ *LA CABANE", "PAYPAL *KIWI", "GLOBAL SERVICES", "SARL BLEU",
    "MULTI COMMERCE", "LA BOUTIQUE", "EURL FERRAND", "SNC DU MIDI", "ALPHA DISTRIBUTION",
]
REVENUS = [
    ("SAS DUPONT INDUSTRIE", "SALAIRE {mois}", "salaire"), ("NAVAL GROUP", "PAIE", "salaire"),
    ("CAF DES BOUCHES DU RHONE", "PRESTATIONS", "aides"), ("CPAM DES BOUCHES", "REMB", "secu"),
    ("ALAN SA", "REMBOURSEMENT SOINS", "mutuelle_remb"), ("POLE EMPLOI", "ARE", "chomage"),
]


def corpus(n=340, graine=777):
    sauve = cb.MARCHANDS, cb.INCONNUS, cb.REVENUS
    cb.MARCHANDS, cb.INCONNUS, cb.REVENUS = VALIDATION, INCONNUS, REVENUS
    try:
        return cb.corpus(n, graine)
    finally:
        cb.MARCHANDS, cb.INCONNUS, cb.REVENUS = sauve
