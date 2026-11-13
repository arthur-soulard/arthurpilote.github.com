"""
budget_marchands.py — Ce que Pilote reconnaît dans un libellé de relevé
bancaire, pour classer une opération importée dans Mes comptes
(budget_releves.py, docs/modules/comptes.md, « Import des relevés »).

Trois tables, toutes sur du texte normalisé (minuscules, sans accents, un
espace entre les mots : budget_releves._norm) :

  CIBLES    : notion -> (type, catégorie, sous-catégorie) aux noms du jeu par
              défaut de Mes comptes (finances._default_categories). Une
              notion sans catégorie par défaut (impôts, éducation…) porte le
              nom proposé si l'utilisateur veut la créer.
  MARCHANDS : (motif, notion[, genres]) — le premier motif trouvé dans le
              libellé gagne : les plus précis d'abord, les mots génériques
              (« restaurant », « pharmacie ») à la fin. `genres` limite la
              règle à certains genres d'opération (carte, prelevement,
              virement, retrait, cheque, frais).
  MCC       : code commerçant de la carte (export Trade Republic, Qonto…)
              -> notion, par tranches de la norme ISO 18245.

Une notion qu'on ne retrouve pas dans les catégories de l'utilisateur n'est
jamais forcée ailleurs : l'opération reste « À classer ».
"""

# ─── Notions ─────────────────────────────────────────────────────────────────
# type, catégorie, sous-catégorie (None : la catégorie seule)
CIBLES = {
    # Alimentation
    "courses":        ("expense", "Alimentation", "Courses"),
    "boulangerie":    ("expense", "Alimentation", "Courses"),
    "restaurant":     ("expense", "Alimentation", "Restaurants"),
    "livraison_repas": ("expense", "Alimentation", "Livraison"),
    # Logement
    "loyer":          ("expense", "Logement", "Loyer"),
    "energie":        ("expense", "Logement", "Électricité"),
    "internet":       ("expense", "Logement", "Internet"),
    "eau":            ("expense", "Logement", "Eau"),
    "assurance_hab":  ("expense", "Logement", "Assurance habitation"),
    "copro":          ("expense", "Logement", "Charges copropriété"),
    # Transports
    "carburant":      ("expense", "Transports", "Carburant"),
    "transport_commun": ("expense", "Transports", "Transports en commun"),
    "taxi":           ("expense", "Transports", "Taxi / VTC"),
    "entretien_auto": ("expense", "Transports", "Entretien véhicule"),
    "assurance_auto": ("expense", "Transports", "Assurance auto"),
    "peage":          ("expense", "Transports", "Péage / Parking"),
    # Santé
    "medecin":        ("expense", "Santé", "Médecin"),
    "pharmacie":      ("expense", "Santé", "Pharmacie"),
    "mutuelle":       ("expense", "Santé", "Mutuelle"),
    "optique":        ("expense", "Santé", "Dentiste / Optique"),
    # Loisirs
    "sorties":        ("expense", "Loisirs", "Sorties"),
    "sport":          ("expense", "Loisirs", "Sport"),
    "vacances":       ("expense", "Loisirs", "Vacances"),
    "culture":        ("expense", "Loisirs", "Culture"),
    # Abonnements
    "streaming":      ("expense", "Abonnements", "Streaming"),
    "telephone":      ("expense", "Abonnements", "Téléphone"),
    "logiciels":      ("expense", "Abonnements", "Cloud / Logiciels"),
    "salle_sport":    ("expense", "Abonnements", "Salle de sport"),
    # Shopping
    "vetements":      ("expense", "Shopping", "Vêtements"),
    "electronique":   ("expense", "Shopping", "Électronique"),
    "maison":         ("expense", "Shopping", "Maison / Déco"),
    "shopping":       ("expense", "Shopping", None),
    # Frais bancaires
    "frais_tenue":    ("expense", "Frais bancaires", "Frais de tenue de compte"),
    "agios":          ("expense", "Frais bancaires", "Agios / Découvert"),
    "frais_carte":    ("expense", "Frais bancaires", "Carte bancaire"),
    "frais":          ("expense", "Frais bancaires", None),
    # Cadeaux & dons
    "cadeaux":        ("expense", "Cadeaux & dons", "Cadeaux"),
    "dons":           ("expense", "Cadeaux & dons", "Dons / Associations"),
    # Sans catégorie par défaut : proposées à la création
    "impots":         ("expense", "Impôts & taxes", None),
    "education":      ("expense", "Éducation", None),
    "retrait":        ("expense", "Retraits d'espèces", None),
    "animaux":        ("expense", "Animaux", None),
    "beaute":         ("expense", "Beauté & soins", None),
    "enfants":        ("expense", "Enfants", None),
    "assurance":      ("expense", "Assurances", None),
    "credit":         ("expense", "Crédits", None),
    "tabac":          ("expense", "Tabac & presse", None),
    # Revenus
    "salaire":        ("income", "Salaire", "Salaire net"),
    "prime":          ("income", "Primes", None),
    "participation":  ("income", "Primes", "Participation"),
    "secu":           ("income", "Remboursements", "Sécurité sociale"),
    "mutuelle_remb":  ("income", "Remboursements", "Mutuelle"),
    "remboursement":  ("income", "Remboursements", None),
    "aides":          ("income", "Aides & allocations", None),
    "interets":       ("income", "Autres revenus", None),
    "chomage":        ("income", "Aides & allocations", None),
    "retraite":       ("income", "Retraite", None),
    "bourse_etudes":  ("income", "Aides & allocations", None),
    "vente_occasion": ("income", "Autres revenus", None),
}

# Emoji d'une catégorie proposée à la création (les autres ont le leur)
ICONES_PROPOSEES = {
    "Impôts & taxes": "🏛️", "Éducation": "🎓", "Retraits d'espèces": "🏧",
    "Animaux": "🐾", "Beauté & soins": "💇", "Enfants": "🧸", "Assurances": "🛡️",
    "Crédits": "🏦", "Tabac & presse": "🚬", "Aides & allocations": "🤝", "Retraite": "👴",
}

# Autres noms qu'un utilisateur donne aux mêmes catégories et sous-catégories
# (normalisés). Sert à retrouver une notion dans des catégories renommées.
SYNONYMES = {
    "alimentation": ["alimentation", "nourriture", "alimentaire", "food", "repas", "bouffe", "manger"],
    "courses": ["courses", "supermarche", "supermarches", "epicerie", "alimentation courante",
                "grande surface", "grandes surfaces", "hypermarche", "groceries", "marche", "course"],
    "restaurants": ["restaurants", "restaurant", "resto", "restos", "restauration", "fast food",
                    "fast-food", "sorties restaurant", "repas dehors", "cafe", "cafes", "bars restaurants",
                    "resto u", "cantine"],
    "livraison": ["livraison", "livraisons", "uber eats", "repas livres", "deliveroo"],
    "logement": ["logement", "maison", "habitation", "habitat", "appartement", "appart", "domicile", "charges"],
    "loyer": ["loyer", "loyers", "location", "pret immobilier", "credit immobilier", "mensualite"],
    "electricite": ["electricite", "energie", "edf", "gaz", "electricite gaz", "energie gaz",
                    "chauffage", "electricite / gaz"],
    "internet": ["internet", "box", "box internet", "fibre", "adsl"],
    "eau": ["eau"],
    "assurance habitation": ["assurance habitation", "assurance logement", "assurance maison", "mrh"],
    "charges copropriete": ["charges copropriete", "copropriete", "syndic", "charges"],
    "transports": ["transports", "transport", "deplacements", "voiture", "vehicule", "auto", "mobilite"],
    "carburant": ["carburant", "essence", "gasoil", "gazole", "plein", "station", "station service"],
    "transports en commun": ["transports en commun", "transport en commun", "train", "metro", "bus",
                             "navigo", "tram", "sncf", "billets de train"],
    "taxi / vtc": ["taxi / vtc", "taxi", "vtc", "uber", "taxis"],
    "entretien vehicule": ["entretien vehicule", "entretien voiture", "garage", "reparation voiture",
                           "entretien", "reparations"],
    "assurance auto": ["assurance auto", "assurance voiture", "assurance vehicule", "assurance moto"],
    "peage / parking": ["peage / parking", "peage", "parking", "peages", "stationnement", "autoroute"],
    "sante": ["sante", "medical", "soins", "medecine"],
    "medecin": ["medecin", "medecins", "docteur", "consultation", "consultations", "generaliste", "specialiste"],
    "pharmacie": ["pharmacie", "medicaments", "parapharmacie"],
    "mutuelle": ["mutuelle", "complementaire sante"],
    "dentiste / optique": ["dentiste / optique", "dentiste", "optique", "opticien", "lunettes", "dentaire"],
    "loisirs": ["loisirs", "loisir", "divertissement", "plaisir", "plaisirs", "sorties loisirs", "hobbies"],
    "sorties": ["sorties", "sortie", "bar", "bars", "soirees", "soiree", "cinema", "concerts"],
    "sport": ["sport", "sports", "activites sportives"],
    "vacances": ["vacances", "voyage", "voyages", "voyages vacances", "hotel", "hotels", "week-end", "weekend",
                 "travel"],
    "culture": ["culture", "livres", "musees", "musique", "jeux video", "jeux"],
    "abonnements": ["abonnements", "abonnement", "souscriptions", "subscriptions", "factures"],
    "streaming": ["streaming", "netflix", "musique", "video", "tv", "spotify"],
    "telephone": ["telephone", "telephonie", "mobile", "forfait", "forfait mobile", "portable",
                  "telephone / internet"],
    "cloud / logiciels": ["cloud / logiciels", "cloud", "logiciels", "logiciel", "applications", "apps",
                          "informatique", "stockage"],
    "salle de sport": ["salle de sport", "fitness", "gym", "musculation", "club de sport"],
    "shopping": ["shopping", "achats", "achats divers", "achat", "magasins"],
    "vetements": ["vetements", "habillement", "mode", "fringues", "vetement", "chaussures"],
    "electronique": ["electronique", "high-tech", "high tech", "informatique", "multimedia"],
    "maison / deco": ["maison / deco", "maison", "deco", "decoration", "bricolage", "ameublement",
                      "meubles", "jardin", "equipement maison"],
    "frais bancaires": ["frais bancaires", "banque", "frais", "frais banque", "services bancaires"],
    "frais de tenue de compte": ["frais de tenue de compte", "tenue de compte", "frais de compte",
                                 "cotisation", "cotisations"],
    "agios / decouvert": ["agios / decouvert", "agios", "decouvert", "interets debiteurs"],
    "carte bancaire": ["carte bancaire", "cotisation carte", "carte"],
    "cadeaux & dons": ["cadeaux & dons", "cadeaux", "dons", "cadeaux et dons"],
    "cadeaux": ["cadeaux", "cadeau"],
    "dons / associations": ["dons / associations", "dons", "associations", "don", "charite"],
    "impots & taxes": ["impots & taxes", "impots", "impot", "taxes", "fiscalite", "impots et taxes",
                       "taxe", "tresor public"],
    "education": ["education", "etudes", "scolarite", "ecole", "formation", "universite", "frais de scolarite"],
    "retraits d'especes": ["retraits d'especes", "retraits", "retrait", "especes", "liquide", "cash",
                           "retraits especes", "dab"],
    "animaux": ["animaux", "animal", "chien", "chat", "veterinaire"],
    "beaute & soins": ["beaute & soins", "beaute", "coiffeur", "soins", "hygiene", "cosmetiques",
                       "hygiene beaute", "soins du corps"],
    "enfants": ["enfants", "enfant", "bebe", "creche", "garde d'enfants", "nounou"],
    "assurances": ["assurances", "assurance"],
    "credits": ["credits", "credit", "emprunts", "emprunt", "prets", "pret", "remboursement pret"],
    "tabac & presse": ["tabac & presse", "tabac", "presse", "cigarettes"],
    # Revenus
    "salaire": ["salaire", "salaires", "paie", "paye", "revenus du travail", "travail", "remuneration"],
    "salaire net": ["salaire net", "salaire"],
    "primes": ["primes", "prime", "bonus"],
    "participation": ["participation", "interessement"],
    "remboursements": ["remboursements", "remboursement", "rembours"],
    "securite sociale": ["securite sociale", "secu", "cpam", "ameli", "assurance maladie"],
    "aides & allocations": ["aides & allocations", "aides", "allocations", "caf", "aide", "apl",
                            "prestations sociales", "allocation", "bourse", "bourses"],
    "autres revenus": ["autres revenus", "divers revenus", "revenus divers"],
    "retraite": ["retraite", "pension", "pensions"],
    "autres depenses": ["autres depenses", "divers", "depenses diverses", "autres"],
}

# ─── Motifs ──────────────────────────────────────────────────────────────────
# Un motif est une expression régulière cherchée entre limites de mots dans le
# libellé normalisé (« \b(motif)\b »). Premier trouvé, premier servi.
_C, _P, _V, _R, _Q = "carte", "prelevement", "virement", "retrait", "cheque"

MARCHANDS = [
    # ── Frais de la banque (avant tout : « cotisation carte visa » n'est pas Visa)
    (r"(cotis(ation)?|abonnement|abon) (carte|cb|visa|mastercard|gold|premier|infinite|ultim|platinum)", "frais_carte", {"frais", "autre", "prelevement"}),
    (r"(cotisation|cotis|frais) (mensuelle |annuelle )?(offre|formule|pack|convention|compte|tenue|esprit libre|sobrio|eko|jazz|essentiel|initiale|globe|cristal)", "frais_tenue", {"frais", "autre", "prelevement"}),
    (r"cotisation jazz|frais tenue (de )?compte|tenue de compte|frais de gestion compte|forfait (des )?services bancaires|offre groupee", "frais_tenue", {"frais", "autre", "prelevement"}),
    (r"agios|interets debiteurs|int debiteurs|frais (de )?decouvert|commission (d )?intervention|commissions d intervention|frais (de )?rejet|rejet prlv|lettre (d )?information prealable|frais irregularite|frais de lettre", "agios", {"frais", "autre", "prelevement"}),
    (r"(frais|commission) (sur )?(paiement|retrait|operation|op|change|carte|cb|internationa\w*|hors zone|devise|tpe)", "frais", {"frais", "autre", "prelevement"}),
    (r"frais (bancaires|banc|virement|vir|opposition|envoi|chequier|fonctionnement)|commission de change|frais pay(ement)? hors|non sepa", "frais", {"frais", "autre", "prelevement"}),
    (r"cotisation (assurance moyens de paiement|securite|protection)|assurance moyens de paiement", "frais", {"frais", "autre", "prelevement"}),
    # ── Impôts et taxes
    (r"dgfip|impot|impots|finances publiques|tresor public|amendes gouv|antai|direction generale des finances|taxe (habitation|fonciere|d habitation)|prelevement a la source|pas dgfip|sip |sie |urssaf|cfe ", "impots"),
    (r"ants|timbre fiscal|timbres fiscaux|redevance audiovisuelle|tresorerie", "impots"),
    # ── Revenus
    (r"salaire|salaires|paie|paye|virement de salaire|remuneration|traitement mensuel|net a payer", "salaire", {_V, "autre"}),
    (r"prime|bonus|13e mois|treizieme mois", "prime", {_V}),
    (r"participation|interessement|amundi ee|natixis interepargne|epargne salariale", "participation", {_V}),
    (r"cpam|ameli|caisse primaire|assurance maladie|cnam|msa ", "secu", {_V, "autre"}),
    (r"caf |caf$|caisse d allocations|allocations familiales|apl |prime d activite|cnaf|rsa ", "aides", {_V, "autre"}),
    (r"pole emploi|france travail|allocation chomage|are pole|assedic", "chomage", {_V, "autre"}),
    (r"crous bourse|bourse (crous|sur criteres|etudiant)|bourse d etudes", "bourse_etudes", {_V, "autre"}),
    (r"carsat|cnav|agirc|arrco|retraite|pension de retraite|caisse de retraite|ircantec", "retraite", {_V, "autre"}),
    (r"interets (crediteurs|annuels|livret|acquis|capitalises)|interet crediteur|remuneration (livret|epargne)|interest (payment|earned)", "interets"),
    (r"vinted|leboncoin paiement|le bon coin|ebay payout|backmarket payout|rakuten payout", "vente_occasion", {_V, "autre"}),
    # ── Retraits
    (r"retrait|ret dab|dab |gab |distributeur|withdrawal|atm|cash withdrawal|retrait especes", "retrait", {_R, _C, "autre"}),
    # ── Crédits
    (r"ech(eance)? pret|echeance (de )?(credit|pret)|remboursement pret|rembt pret|pret immo|credit immo|cofidis|cetelem|sofinco|franfinance|oney|younited|floa|carrefour banque|credit conso|financo|creatis|alma |klarna|scalapay|paypal (paiement|pay) en (3|4)x|en 4x", "credit"),
    # ── Logement
    (r"loyer|loyers|foncia|nexity|century 21|orpi|laforet|citya|sergic|oralia|square habitat|immobiliere|agence immo|gestion locative|bailleur|office (public )?(de l )?habitat|opac|hlm|paris habitat|3f |seqens|cdc habitat|vilogia|action logement|studapart|studelites|nexity studea|les estudines|cardinal campus|logement etudiant", "loyer"),
    (r"crous", "loyer", {_P, _V}),
    (r"syndic|copropriete|copro|charges de copro|syndicat des copro", "copro"),
    (r"edf|engie|totalenergies electricite|total energies gaz|total direct energie|direct energie|eni gaz|ekwateur|mint energie|ohm energie|vattenfall|alpiq|enercoop|planete oui|la bellenergie|happ e|sowee|gaz de bordeaux|es energies|grdf|enedis|gdf suez|mega energie|octopus energy|wekiwi|primeo|iberdrola|elmy|plum energie|ilek|dyneff|butagaz|antargaz|primagaz|vitogaz|fioul", "energie"),
    (r"totalenergies|total energies|total direct|eni|eni plenitude", "energie", {_P, _V}),
    (r"veolia|suez eau|saur |eau de paris|eaux de|eau du|regie des eaux|regie eau|syndicat des eaux|sedif|lyonnaise des eaux|compagnie des eaux|cie des eaux|eau et assainissement|noreade|aquapole|eau 17|siaep", "eau"),
    (r"livebox|freebox|sfr box|box internet|bbox|red box|fibre|orange internet|free telecom|free hautdebit|free haut debit|k net|starlink", "internet"),
    # ── Téléphone (après les box)
    (r"free mobile|freemobile|orange(?! bleue)|sosh|sfr|red by sfr|bouygues telecom|bouygues tel|b and you|byou|la poste mobile|prixtel|nrj mobile|cdiscount mobile|syma|lebara|lyca|coriolis|auchan telecom|youprice|reglo mobile|source mobile|transatel|ubigi|airalo|holafly|telecom|mobile", "telephone"),
    # ── Assurances
    (r"maaf|maif|macif|matmut|gmf|mma |mma$|axa|allianz|groupama|generali|aviva|abeille assurances|direct assurance|leocare|lovys|luko|hiscox|pacifica|amaguiz|olivier assurance|l olivier|april|ag2r|swiss life|cardif|predica|assu2000|assurup|eurofil|acheel|ornikar assurance|assurance auto|assurance moto|assurance habitation|assurance (multirisque|mrh)|mutuelle des motards", "assurance"),
    (r"mutuelle|mgen|harmonie mutuelle|malakoff|humanis|alan |alan$|alan sa|apivia|smerep|lmde|heyme|mgel|mutualite|swisslife sante|april sante|ociane|mutuelle generale|intériale|interiale|mnt |mnh |ag2r sante|vivinter|klesia|uneo|mutuelle bleue|mutuelle familiale|adrea|eovi|aesio|macsf|apicil|identite mutuelle|santiane|netvox|cegema|solimut", "mutuelle", {_P, _V, _C, "autre"}),
    # ── Carburant (avant les supermarchés : « station e leclerc »)
    (r"totalenergies|total energies|total access|total mkt|esso|shell|avia|bp station|station bp|agip|eni station|dyneff station|intermarche carbu|carrefour (station|carbu|energie)|leclerc (station|carbu)|station leclerc|station u|station service|stations services|carburant|essence|gazole|gasoil|super u carbu|auchan carbu|relais total|as24|carrefour market station", "carburant"),
    (r"ionity|tesla supercharger|tesla chargeur|freshmile|chargemap|izivia|electra|fastned|allego|bornes? (de )?recharge|recharge electrique|power dot|shell recharge|totalenergies charging", "carburant"),
    # ── Péage, parking
    (r"peage|vinci autoroute|sanef|aprr|area |asf |cofiroute|escota|bip&go|bip go|ulys|fulli|autoroute|atmb|sftrf|alis |parking|parkings|indigo|saemes|effia|onepark|zenpark|yespark|q park|qpark|interparking|parclick|flowbird|paybyphone|pay by phone|easypark|whoosh|horodateur|stationnement|fps |forfait post stationnement", "peage"),
    # ── Transports en commun et trains
    (r"sncf|ouigo|tgv|ter |ter$|intercites|trainline|sncb|thalys|eurostar|lyria|db bahn|deutsche bahn|trenitalia|renfe|italo|flixbus|flix bus|blablacar bus|blablabus|ratp|navigo|comutitres|transilien|ile de france mobilites|idf mobilites|tcl|keolis|transdev|tisseo|rtm |star rennes|tan nantes|twisto|filibus|ctre|tbm|bordeaux metropole mobilite|cts strasbourg|ilevia|transpole|tag grenoble|lignes d azur|palmbus|zou |zou$|tam montpellier|ginko|fil bleu|stan nancy|astuce|lepilote|car jaune|metro|tramway|bus |ticket t|velib|velov|v3 bordeaux|velo libre service|lime|dott|tier|bird|voi |cooltra|cityscoot|getaround|zity|free2move|share now|leo&go|blablacar|transport", "transport_commun"),
    # ── Taxi, VTC (avant la livraison : « uber eats » est plus bas mais plus précis, donc avant)
    (r"uber eats|ubereats|eats pending", "livraison_repas"),
    (r"deliveroo|just eat|justeat|frichti|glovo|stuart|la belle vie|pop chef|foodles|wolt|getir|flink|gorillas|cajoo|ubereats", "livraison_repas"),
    (r"uber|ubr|bolt|heetch|g7|taxi|taxis|marcel cab|free now|freenow|le cab|lecab|allocab|caocao|chauffeur prive|kapten|vtc", "taxi"),
    # ── Avions, hôtels, voyages
    (r"air france|airfrance|easyjet|ryanair|transavia|volotea|vueling|lufthansa|klm|british airways|iberia|tap portugal|wizz air|wizzair|corsair|air caraibes|french bee|air austral|emirates|qatar airways|turkish airlines|aeroport|airport|duty free|relay aeroport", "vacances"),
    (r"booking com|bkg hotel|airbnb|abritel|homeaway|expedia|hotels com|hotel|hotels|ibis|novotel|mercure|accor|campanile|kyriad|b&b hotel|b b hotels|premiere classe|formule 1|hotelf1|f1 hotel|best western|holiday inn|marriott|hilton|radisson|logis hotel|pierre et vacances|pierre & vacances|center parcs|belambra|odalys|vvf|club med|camping|campings|huttopia|sandaya|capfun|yelloh|gites de france|gite|auberge de jeunesse|hostel|ucpa|lastminute|opodo|edreams|go voyages|govoyages|promovacances|voyage prive|voyages sncf|carrefour voyages|leclerc voyages|tui |fram |look voyages|selectour|havas voyages|thomas cook|skyscanner|kayak|hopper|lodgify|ski pass|forfait ski|remontees mecaniques|compagnie des alpes|esf |esf$|location ski|skiset|sport 2000 location|intersport location", "vacances"),
    # ── Entretien du véhicule
    (r"norauto|feu vert|speedy|midas|point s|euromaster|vulco|carglass|france pare brise|mondial pare brise|roady|garage|carrosserie|controle technique|dekra|autosur|securitest|autovision|cct |pneu|pneus|allopneus|oscaro|mister auto|autodoc|renault (minute|retail)|peugeot|citroen|toyota|volkswagen|dacia|lavage auto|station lavage|eléphant bleu|elephant bleu|hypromat|wash|carwash|auto ecole|ornikar|stych|en voiture simone|permis de conduire", "entretien_auto"),
    # ── Streaming, musique, vidéo
    (r"canal", "streaming", {_P}),
    (r"netflix|youtube|spotify|deezer|disney plus|disneyplus|disney|canal plus|canalplus|mycanal|amazon prime|prime video|primevideo|amzn prime|apple tv|apple music|youtube premium|youtube music|google youtube|youtubepremium|dazn|bein|rmc sport|paramount|crunchyroll|adn |molotov|salto|ocs |tidal|qobuz|audible|twitch|patreon|onlyfans|max com|hbo max|wakanim|napster|soundcloud|kindle unlimited|storytel|kobo plus|youboox", "streaming"),
    # ── Logiciels, cloud, applis
    (r"apple com bill|apple com|itunes|app store|icloud|google storage|google one|google play|google|microsoft|msft|office 365|microsoft 365|xbox|playstation|psn|sony interactive|nintendo|steam|steampowered|epic games|ubisoft|blizzard|riot games|ea games|electronic arts|dropbox|adobe|canva|notion|evernote|openai|chatgpt|anthropic|claude ai|github|ovh|ionos|o2switch|hostinger|godaddy|gandi|nordvpn|expressvpn|surfshark|proton|1password|lastpass|dashlane|duolingo|babbel|headspace|calm |strava|komoot|tinder|bumble|hinge|meetic|happn|linkedin|zoom|slack|figma|jetbrains|setapp|grammarly|deepl|bitdefender|norton|kaspersky|avast|mcafee|aws|amazon web services|cloudflare|digitalocean|scaleway", "logiciels"),
    # ── Salles de sport
    (r"basic fit|basicfit|fitness park|keep cool|keepcool|l orange bleue|orange bleue|neoness|on air fitness|onair|cmg sports|club med gym|episod|gymlib|urban sports|urbansports|magic form|4 m fitness|wellness sport|vita liberte|amazonia|lady fitness|curves|fitness|crossfit|salle de sport|climbing|arkose|block out|vertical art|klifo|hall de bloc", "salle_sport"),
    # ── Sport (matériel, clubs, événements)
    (r"decathlon|intersport|go sport|sport 2000|courir|foot locker|footlocker|snipes|jd sports|alltricks|probikeshop|i run|irun|private sport shop|au vieux campeur|ekosport|glisshop|snowleader|nike|adidas|puma|asics|new balance|salomon|quechua|tennis|padel|golf|piscine|patinoire|bowling|karting|federation francaise|ffr |fft |ffp |licence sportive|club sportif|ussi|association sportive|marathon|trail|semi marathon|njuko|klikego|chronostart|sporkrono|wiclax|protiming|yaka events", "sport"),
    # ── Animaux
    (r"veterinaire|veto|clinique veterinaire|animalis|maxi zoo|maxizoo|tom&co|tom & co|truffaut|jardiland|botanic|zooplus|wanimo|croquetteland|animaux|animalerie|toilettage|pet |pet$|royal canin|purina", "animaux"),
    # ── Pharmacie, santé
    (r"pharmacie|pharma|pharm |parapharmacie|grande pharmacie|pharmacien|newpharma|pharmashopi|cocooncenter|1001pharmacies", "pharmacie"),
    (r"docteur|dr |dr$|medecin|cabinet medical|centre medical|centre de sante|maison de sante|doctolib|kine|kinesitherapeute|osteopathe|osteo|ophtalmo|dermatologue|gynecologue|psychologue|psychiatre|pediatre|radiologie|imagerie|laboratoire|labo |cerballiance|biogroup|eurofins|synlab|unilabs|inovie|bioclinic|hopital|clinique|chu |aphp|sos medecins|infirmier|sage femme|orthophoniste|podologue|dietetique|livi |qare|mesdocteurs", "medecin"),
    (r"dentiste|dentaire|orthodontiste|optique|opticien|optic 2000|optic2000|afflelou|krys|grandoptical|grand optical|generale d optique|atol|lissac|optical center|lynx optic|ecouter voir|audioprothesiste|amplifon|audika|lentilles|lensway|sensee|jimmy fairly", "optique"),
    # ── Culture, sorties
    (r"fnac|cultura|furet du nord|gibert|decitre|mollat|librairie|librairies|la procure|chapitre|momox|recyclivre|cinema|cine|ugc|pathe|gaumont|mk2|cgr|megarama|kinepolis|cineville|le grand rex|theatre|opera|philharmonie|zenith|olympia|accor arena|ticketmaster|fnac spectacles|digitick|see tickets|weezevent|shotgun|billetreduc|dice fm|festicket|musee|musees|louvre|chateau de versailles|centre pompidou|monuments nationaux|exposition|expo |parc asterix|disneyland|futuroscope|puy du fou|zoo|aquarium|jardin d acclimatation|escape game|lasergame|laser game|bowling", "culture"),
    (r"bar |bar$|pub |pub$|biere|bieres|beer|cave a|caviste|nicolas|v and b|v&b|discotheque|boite de nuit|o sullivans|frog|delirium|soiree|apero", "sorties"),
    # ── Tabac, presse
    (r"tabac|bureau de tabac|le narval|(?<!mondial )relay|presse|maison de la presse|journaux|le monde|le figaro|liberation|mediapart|les echos|l equipe|ouest france|la depeche|le parisien|cafe tabac|bar tabac|fdj|francaise des jeux|pmu|betclic|winamax|unibet|parions sport|zebet", "tabac"),
    # ── Boulangeries
    (r"le pain quotidien", "restaurant"),
    (r"boulangerie|patisserie|fournil|au pain|banette|ange|feuillette|sophie lebreuilly|maison kayser|eric kayser|boulang", "boulangerie"),
    # ── Restaurants, cafés (enseignes)
    (r"mcdonald|mc donald|mcdo|burger king|burgerking|quick |quick$|kfc|subway|domino s|dominos|pizza hut|pizzahut|five guys|starbucks|columbus cafe|paul |paul$|brioche doree|la mie caline|marie blachere|pomme de pain|exki|pret a manger|cojean|big fernand|o tacos|otacos|tacos|sushi shop|planet sushi|sushi|kebab|courtepaille|buffalo grill|hippopotamus|del arte|la boucherie|flunch|leon de bruxelles|le relais|bistro|bistrot|brasserie|crêperie|creperie|pizzeria|pizza|burger|restaurant|restau|resto|resto u|cafeteria|cafet|cantine|self |traiteur|wok|ramen|thai|indien|libanais|grill|steakhouse|boulangerie patisserie snack|snack|food truck|foodtruck|cafe de|le cafe|coffee|cafe|izly|sodexo|elior|compass|api restauration|eurest|restaurant d entreprise|ticket restaurant|swile|edenred|bimpli|lunchr|wagamama|nachos|bagel|bagelstein|lina s|la croissanterie|class croute|bert s|le pain quotidien|holly s diner|memphis coffee|tablapizza|signorizza|pitaya|cote sushi|yogurt factory|amorino|haagen dazs|glacier|ladurée|laduree|pierre herme", "restaurant"),
    (r"crous", "restaurant", {_C}),
    # ── Supermarchés, épiceries
    (r"supermarche|supermarches|hypermarche|superette|carrefour\w*|intermarche\w*|auchan\w*|leclerc\w*|monoprix\w*|franprix\w*|crf |crf$|carref|e leclerc|leclerc|eleclerc|e\.leclerc|scadif|auchan|intermarche|itm |itm$|lidl|aldi|super u|hyper u|u express|utile|systeme u|magasins u|casino|geant casino|monoprix|monop|franprix|picard|leader price|netto|match |supermarche match|cora |cora$|simply market|g20|g 20|spar |spar$|vival|proxi|coccinelle|diagonal|naturalia|biocoop|la vie claire|bio c bon|natureo|grand frais|thiriet|promocash|lidl plus|grande epicerie|epicerie|epicier|primeur|fruits et legumes|boucherie|charcuterie|fromagerie|poissonnerie|marche |marche$|halles|la ruche qui dit oui|amap|drive|chronodrive|ooshop|houra|toupargel|cocorico|day by day|o tera|lamarket", "courses"),
    # ── Beauté, soins
    (r"coiffeur|coiffure|salon de coiffure|barbier|barber|jean louis david|franck provost|dessange|tchip|saint algue|camille albane|sephora|nocibe|marionnaud|yves rocher|l occitane|kiko|lush|rituals|body shop|esthetique|institut de beaute|onglerie|nail|spa |spa$|massage|epilation|dermo|aroma zone|aromazone|typology|lookfantastic|notino|birchbox|my little box|beauty|beaute|parfumerie|cosmetique", "beaute"),
    # ── Enfants
    (r"creche|micro creche|nounou|assistante maternelle|garde d enfant|pajemploi|cesu|yoopala|kinougarde|babychou|o2 |o2$|family sphere|aubert|orchestra|vertbaudet|cyrillus|du pareil au meme|dpam|okaidi|jacadi|petit bateau|sergent major|tape a l oeil|natalys|toys r us|king jouet|la grande recre|joueclub|jouets|cantine scolaire|periscolaire|centre de loisirs|accueil de loisirs", "enfants"),
    # ── Éducation
    (r"universite|univ |faculte|ecole|ecoles|lycee|college|campus|scolarite|frais de scolarite|frais d inscription|inscription|cvec|parcoursup|cned|acadomia|complétude|completude|superprof|kartable|studocu|openclassrooms|udemy|coursera|domicours|anacours|cours particuliers|cours de|formation|etudiant|seatech|ensam|insa|polytech|isep|epita|epitech", "education"),
    # ── Dons
    (r"don |dons|donation|croix rouge|restos du coeur|secours populaire|secours catholique|unicef|medecins sans frontieres|msf|fondation|greenpeace|wwf|amnesty|emmaus|action contre la faim|handicap international|ligue contre le cancer|telethon|afm|helloasso|leetchi|ulule|kisskissbankbank|kkbb|gofundme|tipeee|cagnotte|association|asso |paroisse|denier", "dons"),
    # ── Électronique
    (r"apple store|apple retail|boulanger|darty|ldlc|materiel net|materiel\.net|rue du commerce|cdiscount|back market|backmarket|rakuten|grosbill|top achat|topachat|son video|samsung|xiaomi|huawei|dell|lenovo|hp store|asus|logitech|bose|sonos|gopro|dji|electro depot|electrodepot|but |but$|conforama|fnac darty|micromania|game cash|easy cash|cash converters|smartphone|informatique", "electronique"),
    # ── Maison, bricolage, déco
    (r"ikea|leroy merlin|castorama|brico depot|bricodepot|bricomarche|mr bricolage|weldom|point p|lapeyre|maisons du monde|maison du monde|alinea|la redoute interieurs|but |conforama|gifi|la foir fouille|foirfouille|centrakor|action |action$|stokomani|noz |hema|zodio|du bruit dans la cuisine|alice delice|la chaise longue|fly |fly$|cuisinella|schmidt|mobalpa|but cosy|camif|westwing|made com|maison de la literie|la compagnie du lit|emma matelas|tediber|bricolage|quincaillerie|droguerie|jardinerie|gamm vert|truffaut|villaverde|delbard|manomano|bricoprive|leroymerlin|nature et decouvertes|nature & decouvertes|flying tiger|tiger stores|pressing|laverie|blanchisserie|5 a sec", "maison"),
    # ── Vêtements
    (r"zara|h&m|h & m|hm |hennes|uniqlo|primark|kiabi|celio|jules|brice|bershka|pull and bear|pull&bear|stradivarius|mango|promod|camaieu|etam|undiz|darjeeling|orchestra|okaidi|la halle|gemo|chaussea|eram|andre |minelli|besson|san marina|bocage|jonak|bata|zalando|asos|shein|vinted|kiabi|galeries lafayette|printemps|bon marche|bhv|lacoste|levi s|levis|tommy hilfiger|ralph lauren|calvin klein|the kooples|sandro|maje|claudie pierlot|ba&sh|bash|sezane|des petits hauts|petit bateau|aigle|le slip francais|armor lux|saint james|cache cache|bonobo|grain de malice|pimkie|naf naf|kookai|morgan|jennyfer|superdry|jack & jones|vero moda|only |only$|c&a|c & a|tati|lingerie|vetement|vetements|chaussures|textile|tex |tex$|ateliers|cordonnerie|retouche", "vetements"),
    # ── Shopping général (places de marché, grands magasins)
    (r"amazon|amzn|amz |amz$|aliexpress|ali express|temu|wish|ebay|etsy|veepee|vente privee|showroomprive|showroom prive|zalando prive|la redoute|3 suisses|bazarchic|groupon|wish com|vinted|leboncoin|le bon coin|lbc |fnac com|cdiscount|aubert|marionnaud|la poste|laposte|colissimo|chronopost|mondial relay|relais colis|ups |dhl|dpd|gls|fedex", "shopping"),
    (r"cadeau|cadeaux|fleuriste|fleurs|interflora|aquarelle|florajet|bloom s|monceau fleurs|rapid flore|wonderbox|smartbox|bongo|tictactrip cadeau|carte cadeau|e cadeau", "cadeaux"),
]

# ─── Code commerçant (MCC, ISO 18245) ────────────────────────────────────────
# (de, à, notion) : premier intervalle qui contient le code
MCC = [
    (3000, 3350, "vacances"),       # compagnies aériennes
    (3351, 3500, "transport_commun"),  # location de voitures
    (3501, 3999, "vacances"),       # hôtels
    (4011, 4131, "transport_commun"),
    (4111, 4111, "transport_commun"),
    (4121, 4121, "taxi"),
    (4131, 4131, "transport_commun"),
    (4511, 4511, "vacances"),
    (4722, 4722, "vacances"),
    (4784, 4784, "peage"),
    (4812, 4814, "telephone"),
    (4899, 4899, "streaming"),
    (4900, 4900, "energie"),
    (5045, 5045, "electronique"),
    (5200, 5261, "maison"),
    (5300, 5300, "courses"),
    (5310, 5311, "shopping"),
    (5331, 5331, "shopping"),
    (5399, 5399, "shopping"),
    (5411, 5411, "courses"),
    (5422, 5422, "courses"),
    (5441, 5441, "courses"),
    (5451, 5451, "courses"),
    (5462, 5462, "boulangerie"),
    (5499, 5499, "courses"),
    (5511, 5599, "entretien_auto"),
    (5541, 5542, "carburant"),
    (5551, 5599, "entretien_auto"),
    (5611, 5699, "vetements"),
    (5712, 5719, "maison"),
    (5722, 5722, "electronique"),
    (5732, 5735, "electronique"),
    (5811, 5811, "restaurant"),
    (5812, 5812, "restaurant"),
    (5813, 5813, "sorties"),
    (5814, 5814, "restaurant"),
    (5912, 5912, "pharmacie"),
    (5921, 5921, "sorties"),
    (5940, 5941, "sport"),
    (5942, 5942, "culture"),
    (5945, 5945, "enfants"),
    (5977, 5977, "beaute"),
    (5992, 5992, "cadeaux"),
    (5993, 5993, "tabac"),
    (5995, 5995, "animaux"),
    (5999, 5999, "shopping"),
    (7011, 7011, "vacances"),
    (7230, 7230, "beaute"),
    (7298, 7298, "beaute"),
    (7523, 7523, "peage"),
    (7531, 7549, "entretien_auto"),
    (7832, 7832, "culture"),
    (7922, 7922, "culture"),
    (7991, 7991, "culture"),
    (7997, 7997, "salle_sport"),
    (7941, 7941, "sport"),
    (8011, 8099, "medecin"),
    (8021, 8021, "optique"),
    (8043, 8043, "optique"),
    (8211, 8299, "education"),
    (8398, 8398, "dons"),
    (9311, 9311, "impots"),
]
