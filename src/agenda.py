"""
agenda.py — Module « Agenda » : Pilote ecrit dans l'agenda iCloud de l'utilisateur.

Demande d'Arthur du 22/10/2026 : que ce qu'il note dans Pilote apparaisse dans
son agenda, donc sur son telephone. iCloud d'abord, parce qu'il accepte un
mot de passe d'application (comme Gmail pour Actus) ; Google n'accepte que
OAuth, avec un projet Google Cloud a creer.

Pilote parle CalDAV a caldav.icloud.com (HTTPS, authentification simple avec
l'identifiant Apple et le mot de passe d'application). Il n'ecrit que dans
UN agenda, choisi par l'utilisateur (de preference « Pilote », cree pour
l'occasion), et n'y touche qu'a ses propres evenements : leur nom de fichier
commence par « pilote-<id>- », id tire au hasard a la connexion.

La section « Agenda » de la barre laterale (demande d'Arthur du meme jour) :
un calendrier du mois qui reproduit ce qu'il y a dans iCloud, comme le
telephone (les autres agendas sont lus, jamais modifies), plus les notes
ajoutees a la main. Ce qui part dans l'agenda iCloud se choisit dans l'onglet iCloud :
  sport     : chaque seance de Sports (heure et duree si elles sont saisies)
  objectifs : les objectifs de Sports « evenement a date »
  pret      : les mensualites du pret (un seul evenement repete chaque mois)
  + les notes, toujours (elles sont ecrites pour l'agenda)

Onglet Notifications (demande d'Arthur du 22/10/2026 : « des notifs sur le
telephone ») : une alerte (VALARM) posee sur ces evenements, que l'iPhone
sonne tout seul, Pilote ferme ou non. Plus un catalogue de rappels qui ne
partent que si leur alerte est reglee (RAPPELS, 26/10/2026) : rappels du mois
(un evenement repete chaque mois, qui saute au mois suivant une fois le mois
fait), dates connues (dividendes, versements, anniversaire du PEA, etapes du
pret), rappels « depuis X jours » (seance, pesee, sauvegarde USB, Pilote pas
ouvert), resume de la semaine, et une notification d'essai.

Synchronisation : Pilote calcule la liste voulue a partir de sports.json et
pret.json, liste ce qui est deja dans l'agenda, puis ajoute, remplace ou
retire. Elle repart quelques secondes apres chaque enregistrement de Sports
ou du Pret (planifier), au lancement, et au bouton « Envoyer maintenant ».

Emplacement : <app_dir>/users/<slug>/agenda.json
  {"adresse", "secret", "id", "calendrier", "calendrierCree",
   "choix": {"sport", "objectifs", "pret"},
   "envoyes": {nom de fichier: empreinte},
   "aNettoyer": [agenda quitte, a vider], "aSupprimer": [agenda « Pilote » quitte],
   "notes": [{id, titre, date, heure, duree (min), texte, repete, alerte}],
   "alertes": {type: valeur de ALERTES_VALEURS}, "jours": {rappel de MENSUELS: jour du mois},
   "delais": {rappel de DELAIS: nombre de jours}, "test": "AAAA-MM-JJTHH:MM" (notification d'essai)}

Le mot de passe suit le chemin de celui d'Actus : verifie aupres d'iCloud
avant d'etre garde, chiffre (DPAPI sous Windows, Trousseau sur Mac), et ne
repasse jamais par la page.
"""
from __future__ import annotations

import base64
import datetime
import hashlib
import json
import re
import socket
import ssl
import threading
import urllib.error
import urllib.parse
import urllib.request
import uuid
import xml.etree.ElementTree as ET

import actus
import cto
import finances
import jsonstore
import patrimoine
import pret
import sante
import sauvegarde
import sports
import storage


BASE      = "https://caldav.icloud.com/"
DELAI     = 20      # s par requete
REESSAI   = 600     # s : iCloud injoignable, on retente 10 min plus tard
TROUSSEAU = "Pilote Agenda"
CHOIX     = ("sport", "objectifs", "pret")
# Rappels de l'onglet Notifications : envoyes seulement si leur alerte est reglee
# (catalogue du 26/10/2026, range par section dans l'onglet)
RAPPELS   = ("pesee", "releve", "versement", "dividende",
             "pea-depot", "pea-investir", "pea-anniv", "cto-investir", "cto-dividende",
             "fin-saisie", "fin-recurrent", "pret-etapes", "sport-pause",
             "sante-pause", "sante-objectif", "resume", "sauvegarde", "ouvrir")
ALERTES   = ("note", "sport", "objectif", "pret") + RAPPELS
# "" : aucune alerte (un rappel n'est alors pas envoye) ; minutes avant le
# debut ; « matin » : 9 h le jour meme ; « veille » : 18 h la veille ;
# « semaine » : 9 h une semaine avant.
# Un evenement sans heure prend 9 h le jour meme pour les minutes.
ALERTES_VALEURS = ("", "0", "15", "30", "60", "matin", "veille", "semaine")
# Resume de la semaine : le dimanche a 18 h ou le lundi a 8 h
RESUME_VALEURS = ("", "dimanche", "lundi")
# Rappels du mois : le jour choisi (1 a 28), passe au mois suivant une fois fait
MENSUELS  = ("pesee", "releve", "pea-depot", "pea-investir", "cto-investir", "fin-saisie")
# Rappels « depuis X jours » : delai par defaut, et delais proposes
DELAIS    = {"sport-pause": 7, "sante-pause": 7, "sauvegarde": 30, "ouvrir": 7}
DELAIS_VALEURS = (2, 3, 4, 5, 7, 10, 14, 21, 30, 45, 60)
# Note de l'agenda : sa repetition, et son alerte (« » : celle de l'onglet
# Notifications, « aucune » : pas d'alerte pour cette note)
REPETITIONS = ("semaine", "mois", "an")
ALERTES_NOTE = ("aucune",) + ALERTES_VALEURS[1:]
# Notification d'essai : sonne 2 min apres le clic, retiree une heure plus tard
TEST_MINUTES = 2

_DAV = "{DAV:}"
_CAL = "{urn:ietf:params:xml:ns:caldav}"


class ErreurAgenda(Exception):
    """Erreur a montrer telle quelle. code : config, saisie, auth, reseau, caldav."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


# ─── Fichier ─────────────────────────────────────────────────────────────────

def default_data() -> dict:
    return {
        "_meta": {
            "version": 1,
            "schema": "agenda.v1",
            "createdAt":   datetime.date.today().isoformat(),
            "lastSavedAt": datetime.datetime.now().isoformat(timespec="seconds"),
        },
        "adresse": "",
        "secret":  "",
        "id":      "",
        "calendrier": "",
        "calendrierCree": False,
        "choix":   {c: False for c in CHOIX},
        "envoyes": {},
        "aNettoyer": [],
        "aSupprimer": [],
        "notes":   [],
        "alertes": {},
        "jours":   {t: 1 for t in MENSUELS},
        "delais":  dict(DELAIS),
        "test":    "",
    }


_store = jsonstore.JsonStore(
    filename="agenda.json",
    backup_dirname="backups_agenda",
    schema="agenda.v1",
    default_factory=default_data,
)


def _identifiants(data: dict) -> tuple:
    adresse = (data.get("adresse") or "").strip()
    secret  = data.get("secret") or ""
    if not adresse or not secret:
        raise ErreurAgenda("config", "Aucun agenda iCloud n'est connecté.")
    try:
        return adresse, actus._dechiffrer(secret, TROUSSEAU)
    except Exception:
        raise ErreurAgenda("config", "Le mot de passe enregistré ne se relit pas ici (fichier "
                                     "venu d'un autre PC ?). Ressaisis-le dans Agenda › iCloud.")


# ─── CalDAV ──────────────────────────────────────────────────────────────────

class _SansRedirection(urllib.request.HTTPRedirectHandler):
    """urllib ne suit une redirection que pour GET et HEAD : _requete la suit
    elle-meme, pour PROPFIND, PUT et DELETE aussi."""

    def redirect_request(self, *args, **kwargs):
        return None


_ouvreur = urllib.request.build_opener(
    _SansRedirection, urllib.request.HTTPSHandler(context=ssl.create_default_context()))


def _requete(methode: str, url: str, auth: tuple, corps: bytes = None,
             type_corps: str = "application/xml; charset=utf-8", profondeur: str = None,
             accepte=(200, 201, 204, 207)) -> tuple:
    """(statut, url finale, corps). Un statut hors de `accepte` leve ErreurAgenda."""
    jeton = base64.b64encode(f"{auth[0]}:{auth[1]}".encode("utf-8")).decode("ascii")
    for _ in range(5):
        req = urllib.request.Request(url, data=corps, method=methode)
        req.add_header("Authorization", "Basic " + jeton)
        req.add_header("User-Agent", "Pilote")
        if corps is not None:
            req.add_header("Content-Type", type_corps)
        if profondeur is not None:
            req.add_header("Depth", profondeur)
        try:
            with _ouvreur.open(req, timeout=DELAI) as r:
                statut, contenu = r.status, r.read()
        except urllib.error.HTTPError as e:
            statut, contenu = e.code, e.read()
            if statut in (301, 302, 303, 307, 308) and e.headers.get("Location"):
                url = urllib.parse.urljoin(url, e.headers["Location"])
                continue
        except (urllib.error.URLError, socket.timeout, ssl.SSLError, OSError) as e:
            raise ErreurAgenda("reseau", "iCloud ne répond pas. Vérifie ta connexion "
                                         "internet, puis réessaie.") from e
        if statut == 401:
            raise ErreurAgenda("auth", "iCloud refuse l'identifiant ou le mot de passe. Vérifie "
                                       "l'identifiant Apple, et colle un mot de passe pour app "
                                       "(xxxx-xxxx-xxxx-xxxx), pas celui du compte.")
        if statut not in accepte:
            raise ErreurAgenda("caldav", f"iCloud a répondu {statut} à {methode}.")
        return statut, url, contenu
    raise ErreurAgenda("caldav", "iCloud renvoie d'adresse en adresse.")


def _propfind(url: str, auth: tuple, props: str, profondeur: str) -> tuple:
    corps = ('<?xml version="1.0" encoding="utf-8"?>'
             '<d:propfind xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav"'
             ' xmlns:x="http://apple.com/ns/ical/">'
             f'<d:prop>{props}</d:prop></d:propfind>').encode("utf-8")
    _, final, contenu = _requete("PROPFIND", url, auth, corps, profondeur=profondeur)
    try:
        return final, ET.fromstring(contenu)
    except ET.ParseError as e:
        raise ErreurAgenda("caldav", "Réponse d'iCloud illisible.") from e


def _href(racine, url: str, prop: str) -> str:
    el = racine.find(f".//{_DAV}prop/{prop}/{_DAV}href")
    if el is None or not (el.text or "").strip():
        raise ErreurAgenda("caldav", "iCloud n'a pas donné l'adresse de l'agenda.")
    return urllib.parse.urljoin(url, el.text.strip())


def _maison(auth: tuple) -> str:
    """Dossier des agendas du compte (sur un serveur pXX-caldav.icloud.com)."""
    url, rep = _propfind(BASE, auth, "<d:current-user-principal/>", "0")
    principal = _href(rep, url, f"{_DAV}current-user-principal")
    url, rep = _propfind(principal, auth, "<c:calendar-home-set/>", "0")
    return _href(rep, url, f"{_CAL}calendar-home-set")


def _calendriers(auth: tuple) -> list:
    """Agendas d'evenements du compte (les listes de Rappels sont ecartees)."""
    maison = _maison(auth)
    url, rep = _propfind(maison, auth, "<d:displayname/><d:resourcetype/><x:calendar-color/>"
                                       "<c:supported-calendar-component-set/>", "1")
    out = []
    for r in rep.findall(f"{_DAV}response"):
        href = r.findtext(f"{_DAV}href") or ""
        if r.find(f".//{_DAV}resourcetype/{_CAL}calendar") is None:
            continue
        comps = [c.get("name") for c in r.findall(f".//{_CAL}supported-calendar-component-set/{_CAL}comp")]
        if comps and "VEVENT" not in comps:
            continue
        nom = (r.findtext(f".//{_DAV}displayname") or "").strip() or "Sans nom"
        # Couleur de l'agenda chez Apple (« #RRGGBBAA ») : reprise dans le calendrier de Pilote
        couleur = (r.findtext(".//{http://apple.com/ns/ical/}calendar-color") or "").strip()[:7]
        out.append({"url": urllib.parse.urljoin(url, href).rstrip("/") + "/", "nom": nom,
                    "couleur": couleur if re.fullmatch(r"#[0-9A-Fa-f]{6}", couleur) else ""})
    out.sort(key=lambda c: c["nom"].lower())
    return out


def _creer_calendrier(auth: tuple) -> str:
    url = _maison(auth) + str(uuid.uuid4()).upper() + "/"
    corps = ('<?xml version="1.0" encoding="utf-8"?>'
             '<c:mkcalendar xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">'
             '<d:set><d:prop><d:displayname>Pilote</d:displayname>'
             '<c:supported-calendar-component-set><c:comp name="VEVENT"/>'
             '</c:supported-calendar-component-set></d:prop></d:set></c:mkcalendar>').encode("utf-8")
    _requete("MKCALENDAR", url, auth, corps)
    return url


def _nos_fichiers(cal: str, auth: tuple, prefixe: str) -> set:
    """Noms des fichiers que Pilote a mis dans cet agenda."""
    url, rep = _propfind(cal, auth, "<d:getetag/>", "1")
    out = set()
    for r in rep.findall(f"{_DAV}response"):
        nom = urllib.parse.unquote((r.findtext(f"{_DAV}href") or "").rstrip("/").rsplit("/", 1)[-1])
        if nom.startswith(prefixe) and nom.endswith(".ics"):
            out.add(nom)
    return out


def _retirer(cal: str, auth: tuple, nom: str) -> None:
    _requete("DELETE", cal + urllib.parse.quote(nom), auth, accepte=(200, 204, 404))


# ─── Evenements ──────────────────────────────────────────────────────────────

def _echapper(txt: str) -> str:
    return (str(txt).replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
            .replace("\r\n", "\\n").replace("\n", "\\n"))


def _plier(ligne: str) -> str:
    """Lignes de 75 octets au plus (RFC 5545), sans couper un caractere UTF-8."""
    b = ligne.encode("utf-8")
    morceaux, limite = [], 75
    while len(b) > limite:
        i = limite
        while i > 0 and (b[i] & 0xC0) == 0x80:
            i -= 1
        morceaux.append(b[:i])
        b, limite = b[i:], 74
    morceaux.append(b)
    return "\r\n ".join(m.decode("utf-8") for m in morceaux)


def _jour(s) -> datetime.date:
    try:
        return datetime.date.fromisoformat(str(s or "")[:10])
    except ValueError:
        return None


def _euros(x) -> str:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return ""
    return f"{v:,.2f}".replace(",", " ").replace(".", ",") + " €"


def _nombre(x) -> float:
    try:
        return float(x or 0)
    except (TypeError, ValueError):
        return 0.0


def _horaire(jour: datetime.date, heure, minutes) -> tuple:
    """(debut, fin) pour une heure « HH:MM » valide, sinon (None, None) : toute la journee."""
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", str(heure or ""))
    if not (m and int(m.group(1)) < 24 and int(m.group(2)) < 60):
        return None, None
    debut = datetime.datetime.combine(jour, datetime.time(int(m.group(1)), int(m.group(2))))
    return debut, debut + datetime.timedelta(minutes=max(int(_nombre(minutes)), 0) or 60)


def _element(cle, type_, titre, jour, debut=None, fin=None, texte="", mois=0, id_=None,
             alerte=None, regle="") -> dict:
    """alerte : reglage impose (resume, essai, note qui a le sien), sinon celui
    du type ; « aucune » : pas d'alerte. mois : repete chaque mois (-1 sans
    fin) ; regle : autre repetition (REPETITIONS), pour une note."""
    return {"cle": cle, "type": type_, "titre": titre, "jour": jour, "debut": debut,
            "fin": fin, "texte": str(texte or ""), "mois": mois, "id": id_, "alerte": alerte,
            "regle": regle}


def elements(sp: dict, pr: dict, notes: list) -> list:
    """Tout ce que Pilote sait dater : seances, objectifs a date, mensualites
    du pret, notes de l'agenda. L'envoi a iCloud ne garde que les cases
    cochees (evenements)."""
    out = []
    catalogue = {x.get("id"): x for x in sports.SPORTS}
    for x in (sp.get("customSports") or []):
        catalogue[x.get("id")] = x
    for s in (sp.get("sessions") or []):
        jour = _jour(s.get("date"))
        if not jour or s.get("id") is None:
            continue
        sport = catalogue.get(s.get("sport")) or catalogue.get("autre") or {}
        titre = " ".join(x for x in (sport.get("icon") or "", sport.get("label") or "Séance") if x)
        if s.get("subtype"):
            titre += " · " + str(s["subtype"])
        dist = _nombre(s.get("distance"))
        if dist > 0:
            en_metres = "distance_m" in (sport.get("fields") or [])
            titre += f" · {dist:g} m" if en_metres else f" · {dist:g} km".replace(".", ",")
        # Heure « flottante » (ni Z ni fuseau) : affichee telle quelle la ou est le telephone
        debut, fin = _horaire(jour, s.get("time"), s.get("duration"))
        out.append(_element(f"sport-{s['id']}", "sport", titre, jour, debut, fin, s.get("note")))
    for g in (sp.get("goals") or []):
        jour = _jour(g.get("date"))
        if g.get("kind") != "event" or not jour or g.get("status") == "archived":
            continue
        out.append(_element(f"objectif-{g.get('id')}", "objectif",
                            "🎯 " + (g.get("title") or "Objectif"), jour, texte=g.get("note")))
    p = pr.get("pret") or {}
    jour = _jour(p.get("date_premier_remboursement"))
    nb = int(_nombre(p.get("duree_remboursement")))
    if jour and nb > 0:
        titre = "Mensualité · " + ((p.get("nom") or "").strip() or "Prêt")
        if _nombre(p.get("mensualite")) > 0:
            titre += " · " + _euros(p["mensualite"])
        out.append(_element("pret", "pret", titre, jour, mois=nb))
    for n in (notes or []):
        jour = _jour(n.get("date"))
        if not jour or not n.get("id"):
            continue
        debut, fin = _horaire(jour, n.get("heure"), n.get("duree"))
        repete = n.get("repete") if n.get("repete") in REPETITIONS else ""
        out.append(_element(f"note-{n['id']}", "note", (n.get("titre") or "").strip() or "Note",
                            jour, debut, fin, n.get("texte"), id_=n["id"],
                            mois=-1 if repete == "mois" else 0,
                            regle={"semaine": "FREQ=WEEKLY", "an": "FREQ=YEARLY"}.get(repete, ""),
                            alerte=n.get("alerte") or None))
    return out


def _pea() -> dict:
    """pea_data.json en lecture seule (versements prevus, dividendes attendus).
    Pas storage.load_data() : elle note son resultat pour toute l'app, et un
    fil d'envoi ne doit pas le changer."""
    chemin = storage.get_data_path()
    if not chemin.exists():
        return {}
    try:
        with storage.verrou(chemin):
            return json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise ErreurAgenda("config", "Le fichier du PEA est illisible : rien n'a été envoyé.")


def _jour_du_mois(jour, fait: bool) -> datetime.date:
    """Le jour choisi (1 a 28) de ce mois, ou du mois suivant si ce mois est fait."""
    auj = datetime.date.today()
    j = min(max(int(_nombre(jour)) or 1, 1), 28)
    if fait:
        return (auj.replace(day=1) + datetime.timedelta(days=32)).replace(day=j)
    return auj.replace(day=j)


def _plus_mois(jour: datetime.date, n: int) -> datetime.date:
    """Le meme jour n mois plus tard, None si ce mois-la ne l'a pas (le 31) :
    iCloud saute aussi ce mois pour un evenement repete."""
    m = jour.month - 1 + n
    try:
        return jour.replace(year=jour.year + m // 12, month=m % 12 + 1)
    except ValueError:
        return None


def _delai(delais: dict, type_: str) -> int:
    v = int(_nombre((delais or {}).get(type_)))
    return v if v in DELAIS_VALEURS else DELAIS[type_]


def _depuis(dernier: datetime.date, delai: int) -> tuple:
    """Rappel « depuis X jours » : (jour, nombre de jours ecoules ce jour-la).
    Au plus tot demain : en retard, il sonne le lendemain matin, et recule
    d'un jour a chaque envoi tant que rien n'est saisi."""
    jour = max(dernier + datetime.timedelta(days=delai),
               datetime.date.today() + datetime.timedelta(days=1))
    return jour, (jour - dernier).days


def _cle(x: dict, jour, i: int) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "", str(x.get("id") or "")) or f"{jour}-{i}"


def _dividendes(compte: dict, prefixe: str, type_: str, suffixe: str = "") -> list:
    """Un evenement par dividende attendu (divFuture) d'un PEA ou d'un CTO."""
    out = []
    noms = {p.get("ticker"): p.get("name") for p in compte.get("positions") or []}
    for i, d in enumerate(compte.get("divFuture") or []):
        jour = _jour(d.get("date"))
        if jour:
            titre = "💶 Dividende · " + str(noms.get(d.get("ticker")) or d.get("ticker") or "")
            if _nombre(d.get("montant")) > 0:
                titre += " · " + _euros(d["montant"])
            out.append(_element(f"{prefixe}-{_cle(d, jour, i)}", type_, titre + suffixe, jour,
                                texte=d.get("note")))
    return out


def _nom_cto(c: dict) -> str:
    """Comme la barre laterale (ctoNomSection) : « CTO » suivi du nom du compte."""
    nom = str(c.get("nom") or "").strip()
    return nom if nom.upper().startswith("CTO") else ("CTO " + nom).strip()


def _achat_ce_mois(compte: dict, mois: str) -> bool:
    return any(t.get("type") == "Achat" and str(t.get("date") or "").startswith(mois)
               for t in compte.get("transactions") or [])


def _anniversaire(ouverture: datetime.date) -> tuple:
    """(prochain anniversaire, aujourd'hui compris ; nombre d'annees ce jour-la)."""
    auj = datetime.date.today()
    for annee in (auj.year, auj.year + 1):
        try:
            jour = ouverture.replace(year=annee)
        except ValueError:   # ouvert un 29 fevrier
            jour = datetime.date(annee, 2, 28)
        if jour >= auj:
            return jour, annee - ouverture.year
    return None, 0


def rappels(alertes: dict, jours: dict, delais: dict = None) -> list:
    """Les rappels de l'onglet Notifications dont l'alerte est reglee. Les
    rappels du mois (MENSUELS) sont un evenement repete chaque mois (mois=-1)
    qui commence au mois suivant une fois celui-ci fait : la notification ne
    sonne pas pour rien. Un module jamais utilise n'a rien a rappeler."""
    out = []
    auj = datetime.date.today()
    mois = auj.strftime("%Y-%m")
    if alertes.get("pesee") or alertes.get("sante-pause") or alertes.get("sante-objectif"):
        sa = sante.load_data()
        mesures = sa.get("mesures") or []
        if alertes.get("pesee") and mesures:
            fait = any(str(m.get("date") or "").startswith(mois) for m in mesures)
            out.append(_element("pesee", "pesee", "⚖️ Pesée du mois",
                                _jour_du_mois(jours.get("pesee"), fait), mois=-1))
        dates = [d for d in (_jour(m.get("date")) for m in mesures) if d and d <= auj]
        if alertes.get("sante-pause") and dates:
            jour, n = _depuis(max(dates), _delai(delais, "sante-pause"))
            out.append(_element("sante-pause", "sante-pause", f"⚖️ Pas de pesée depuis {n} jours", jour))
        if alertes.get("sante-objectif"):
            metriques = {m["id"]: m for m in sante.METRICS}
            for i, g in enumerate(sa.get("goals") or []):
                jour = _jour(g.get("date"))
                if jour and jour >= auj and g.get("status", "active") == "active":
                    m = metriques.get(g.get("metric")) or {"label": "Objectif", "unit": ""}
                    cible = f"{_nombre(g.get('target')):g}".replace(".", ",")
                    titre = f"🎯 {m['label']} · objectif {cible} {m['unit']}".rstrip()
                    out.append(_element(f"sante-objectif-{_cle(g, jour, i)}", "sante-objectif",
                                        titre, jour, texte=g.get("note")))
    if alertes.get("releve"):
        pa = patrimoine.load_data()
        # Seules les lignes saisies a la main se relevent chaque mois
        if any(not c.get("archived") and not c.get("auto") for c in pa.get("comptes") or []):
            out.append(_element("releve", "releve", "📋 Relevé du patrimoine",
                                _jour_du_mois(jours.get("releve"), patrimoine.mois_saisi(pa)), mois=-1))
    if any(alertes.get(t) for t in ("versement", "dividende", "pea-depot", "pea-investir", "pea-anniv")):
        pea = _pea()
        if alertes.get("versement"):
            for i, v in enumerate(pea.get("depotsPrevus") or []):
                jour = _jour(v.get("date"))
                if jour:
                    out.append(_element(f"versement-{_cle(v, jour, i)}", "versement",
                                        "💶 Versement PEA prévu · " + _euros(v.get("amount")),
                                        jour, texte=v.get("note")))
        if alertes.get("dividende"):
            out += _dividendes(pea, "dividende", "dividende")
        depots = pea.get("depots") or []
        if alertes.get("pea-depot") and depots:
            fait = any(str(d.get("date") or "").startswith(mois) for d in depots)
            out.append(_element("pea-depot", "pea-depot", "💶 Verser sur le PEA",
                                _jour_du_mois(jours.get("pea-depot"), fait), mois=-1))
        if alertes.get("pea-investir") and (pea.get("positions") or pea.get("transactions")):
            out.append(_element("pea-investir", "pea-investir", "📈 Investir ce mois sur le PEA",
                                _jour_du_mois(jours.get("pea-investir"), _achat_ce_mois(pea, mois)), mois=-1))
        ouverture = _jour((pea.get("config") or {}).get("ouverture"))
        if alertes.get("pea-anniv") and ouverture:
            jour, n = _anniversaire(ouverture)
            if jour and n >= 1:
                titre = f"🎂 Le PEA a {n} an{'s' if n > 1 else ''}" + (" · cap des 5 ans" if n == 5 else "")
                out.append(_element("pea-anniv", "pea-anniv", titre, jour))
    if alertes.get("cto-investir") or alertes.get("cto-dividende"):
        for c in cto.load_data().get("comptes") or []:
            cid = re.sub(r"[^A-Za-z0-9_-]", "", str(c.get("id") or ""))
            if not cid:
                continue
            if alertes.get("cto-dividende"):
                out += _dividendes(c, f"cto-dividende-{cid}", "cto-dividende", " · " + _nom_cto(c))
            if alertes.get("cto-investir") and (c.get("positions") or c.get("transactions")):
                out.append(_element(f"cto-investir-{cid}", "cto-investir",
                                    "📈 Investir ce mois · " + _nom_cto(c),
                                    _jour_du_mois(jours.get("cto-investir"), _achat_ce_mois(c, mois)),
                                    mois=-1))
    if alertes.get("fin-saisie") or alertes.get("fin-recurrent"):
        fi = finances.load_data()
        tx = fi.get("transactions") or []
        if alertes.get("fin-saisie") and tx:
            # Fait : une operation ajoutee ce mois-ci, le jour du rappel ou apres
            limite = _jour_du_mois(jours.get("fin-saisie"), False).isoformat()
            fait = any(str(t.get("createdAt") or "")[:10] >= limite for t in tx)
            out.append(_element("fin-saisie", "fin-saisie", "🧾 Saisir les dépenses du mois",
                                _jour_du_mois(jours.get("fin-saisie"), fait), mois=-1))
        if alertes.get("fin-recurrent"):
            for i, r in enumerate(fi.get("recurrences") or []):
                jour = _jour(r.get("nextDue"))
                if jour and jour >= auj and r.get("status") != "paused":
                    signe = "+" if r.get("type") == "income" else "−"
                    titre = f"🔁 {str(r.get('label') or 'Récurrent').strip()} · {signe}{_euros(r.get('amount'))}"
                    out.append(_element(f"fin-recurrent-{_cle(r, jour, i)}", "fin-recurrent", titre,
                                        jour, texte=r.get("note")))
    if alertes.get("pret-etapes"):
        p = pret.load_data().get("pret") or {}
        premier = _jour(p.get("date_premier_remboursement"))
        nb = int(_nombre(p.get("duree_remboursement")))
        if premier and nb > 0:
            nom = (p.get("nom") or "").strip() or "Prêt"
            for cle, titre, jour in (("pret-premiere", "🏁 Première mensualité · ", premier),
                                     ("pret-derniere", "🎉 Dernière mensualité · ", _plus_mois(premier, nb - 1))):
                if jour and jour >= auj:
                    out.append(_element(cle, "pret-etapes", titre + nom, jour))
    if alertes.get("sport-pause"):
        dates = [d for d in (_jour(s.get("date")) for s in sports.load_data().get("sessions") or [])
                 if d and d <= auj]
        if dates:
            jour, n = _depuis(max(dates), _delai(delais, "sport-pause"))
            out.append(_element("sport-pause", "sport-pause", f"🏃 Pas de séance depuis {n} jours", jour))
    if alertes.get("sauvegarde"):
        derniere = _jour(sauvegarde.load_config().get("lastBackupAt"))
        if derniere:   # jamais de sauvegarde USB : rien a rappeler
            jour, n = _depuis(derniere, _delai(delais, "sauvegarde"))
            out.append(_element("sauvegarde", "sauvegarde", f"💾 Pas de sauvegarde USB depuis {n} jours", jour))
    if alertes.get("ouvrir"):
        # Recule a chaque envoi, donc a chaque lancement de Pilote
        n = _delai(delais, "ouvrir")
        out.append(_element("ouvrir", "ouvrir", f"🧭 Pilote n'a pas été ouvert depuis {n} jours",
                            auj + datetime.timedelta(days=n)))
    return out


def essai(quand: str) -> list:
    """La notification d'essai (bouton de l'onglet), tant qu'elle n'a pas plus d'une heure."""
    try:
        debut = datetime.datetime.strptime(str(quand or ""), "%Y-%m-%dT%H:%M")
    except ValueError:
        return []
    if debut < datetime.datetime.now() - datetime.timedelta(hours=1):
        return []
    return [_element("essai", "essai", "🔔 Essai de Pilote : les notifications arrivent bien",
                     debut.date(), debut, debut + datetime.timedelta(minutes=15), alerte="0")]


# Resume de la semaine : ce qui est compte, au singulier et au pluriel
_RESUME_NOMS = {"sport": ("séance", "séances"), "note": ("note", "notes"),
                "objectif": ("objectif", "objectifs"), "pret": ("mensualité", "mensualités"),
                "dividende": ("dividende", "dividendes"), "cto-dividende": ("dividende", "dividendes"),
                "versement": ("versement", "versements"), "fin-recurrent": ("opération récurrente", "opérations récurrentes")}
_RESUME_ECARTES = ("sport-pause", "sante-pause", "sauvegarde", "ouvrir", "essai", "resume")


def _occurrences(e: dict, debut: datetime.date, fin: datetime.date) -> list:
    """Les jours de `e` entre debut et fin compris (evenement repete compris)."""
    if e["regle"] == "FREQ=WEEKLY":
        jour = e["jour"] + datetime.timedelta(days=7 * max((debut - e["jour"]).days // 7, 0))
        out = []
        while jour <= fin:
            if jour >= debut:
                out.append(jour)
            jour += datetime.timedelta(days=7)
        return out
    if e["regle"] == "FREQ=YEARLY":
        return [j for j in (_plus_mois(e["jour"], 12 * k) for k in range(max(debut.year - e["jour"].year, 0),
                                                                          max(fin.year - e["jour"].year, -1) + 1))
                if j and debut <= j <= fin]
    if not e["mois"]:
        return [e["jour"]] if debut <= e["jour"] <= fin else []
    out = []
    for k in range(e["mois"] if e["mois"] > 0 else 1200):
        jour = _plus_mois(e["jour"], k)
        if jour is None:
            continue
        if jour > fin:
            break
        if jour >= debut:
            out.append(jour)
    return out


def _resume(retenus: list, valeur: str) -> list:
    """Le resume de la semaine : le dimanche 18 h (la semaine qui suit) ou le
    lundi 8 h (celle qui commence). Son titre compte ce que Pilote met dans
    l'agenda ces sept jours-la ; il est refait a chaque envoi."""
    if valeur not in RESUME_VALEURS[1:]:
        return []
    maintenant = datetime.datetime.now()
    jour_sem, heure = (6, 18) if valeur == "dimanche" else (0, 8)
    jour = maintenant.date() + datetime.timedelta(days=(jour_sem - maintenant.weekday()) % 7)
    debut = datetime.datetime.combine(jour, datetime.time(heure))
    if debut <= maintenant:
        debut += datetime.timedelta(days=7)
    lundi = debut.date() + datetime.timedelta(days=1 if valeur == "dimanche" else 0)
    dimanche = lundi + datetime.timedelta(days=6)
    compte, lignes = {}, []
    for e in retenus:
        if e["type"] in _RESUME_ECARTES:
            continue
        noms = _RESUME_NOMS.get(e["type"], ("rappel", "rappels"))
        for j in _occurrences(e, lundi, dimanche):
            compte[noms] = compte.get(noms, 0) + 1
            lignes.append((j, e["debut"].strftime("%H:%M") if e["debut"] else "", e["titre"]))
    if compte:
        titre = "🗓️ Ta semaine : " + " · ".join(f"{n} {noms[n > 1]}" for noms, n in compte.items())
    else:
        titre = "🗓️ Ta semaine : rien de prévu dans Pilote"
    jours_fr = ("lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim.")
    texte = "\n".join(f"{jours_fr[j.weekday()]} {j.day} {h} {t}".replace("  ", " ")
                      for j, h, t in sorted(lignes))
    return [_element("resume", "resume", titre, debut.date(), debut,
                     debut + datetime.timedelta(minutes=15), texte, alerte="0")]


def _decalage(e: dict, valeur: str) -> datetime.timedelta:
    """Moment de l'alerte par rapport au debut (minuit pour un evenement sans
    heure), None sans alerte."""
    if not valeur or valeur not in ALERTES_VALEURS:
        return None
    if e["debut"]:
        minute = e["debut"].hour * 60 + e["debut"].minute
        matin = max(minute - 9 * 60, 0)
        avant = {"matin": matin, "veille": minute + 6 * 60, "semaine": matin + 7 * 1440}.get(valeur)
        return -datetime.timedelta(minutes=int(valeur) if avant is None else avant)
    return {"veille": -datetime.timedelta(hours=6),
            "semaine": -datetime.timedelta(days=6, hours=15)}.get(valeur, datetime.timedelta(hours=9))


def _alarme(e: dict, valeur: str) -> list:
    """Bloc VALARM : l'iPhone affiche la notification tout seul, Pilote ferme
    ou non. Declenchement relatif au debut, donc valable pour chaque mois
    d'un evenement repete."""
    d = _decalage(e, valeur)
    if d is None:
        return []
    if e["debut"]:
        avant = int(-d.total_seconds()) // 60
        declencheur = f"-PT{avant}M" if avant else "PT0S"
    else:
        # Toute la journee : le debut est minuit
        declencheur = {"veille": "-PT6H", "semaine": "-P6DT15H"}.get(valeur, "PT9H")
    return ["BEGIN:VALARM", "ACTION:DISPLAY", "DESCRIPTION:" + _echapper(e["titre"]),
            "TRIGGER:" + declencheur, "END:VALARM"]


_CASES = {"sport": "sport", "objectif": "objectifs", "pret": "pret"}


def evenements(sp: dict, pr: dict, choix: dict, notes: list = (),
               alertes: dict = None, en_plus: list = ()) -> dict:
    """{cle: lignes iCalendar de l'evenement, sans UID ni DTSTAMP}. Les notes
    partent toujours : elles sont ecrites pour l'agenda. `en_plus` : les
    rappels (rappels()), deja tries selon leur alerte."""
    out = {}
    alertes = alertes or {}
    for e in retenus(sp, pr, choix, notes, alertes, en_plus):
        lignes = ["SUMMARY:" + _echapper(e["titre"])]
        if e["debut"]:
            lignes += ["DTSTART:" + e["debut"].strftime("%Y%m%dT%H%M%S"),
                       "DTEND:" + e["fin"].strftime("%Y%m%dT%H%M%S")]
        else:
            lignes += ["DTSTART;VALUE=DATE:" + e["jour"].strftime("%Y%m%d"),
                       "DTEND;VALUE=DATE:" + (e["jour"] + datetime.timedelta(days=1)).strftime("%Y%m%d")]
        if e["mois"]:   # -1 : chaque mois, sans fin
            lignes.append(f"RRULE:FREQ=MONTHLY;COUNT={e['mois']}" if e["mois"] > 0 else "RRULE:FREQ=MONTHLY")
        elif e["regle"]:
            lignes.append("RRULE:" + e["regle"])
        if e["texte"]:
            lignes.append("DESCRIPTION:" + _echapper(e["texte"]))
        out[e["cle"]] = lignes + _alarme(e, e["alerte"] or alertes.get(e["type"]))
    return out


def retenus(sp: dict, pr: dict, choix: dict, notes: list = (),
            alertes: dict = None, en_plus: list = ()) -> list:
    """Ce qui part dans l'agenda : les cases cochees, les rappels, puis le
    resume de la semaine, qui les compte."""
    alertes = alertes or {}
    out = [e for e in list(elements(sp, pr, notes)) + list(en_plus)
           if not (e["type"] in _CASES and not choix.get(_CASES[e["type"]]))]
    return out + _resume(out, alertes.get("resume"))


def prochaines(n: int = 6) -> list:
    """Les prochaines notifications qui sonneront sur le telephone (tuile de
    l'accueil) : [{quand "AAAA-MM-JJTHH:MM", titre, type}], dans l'ordre."""
    data = _store.load()
    if not data.get("secret") or not data.get("calendrier"):
        return []
    alertes = _alertes_propres(data.get("alertes"))
    maintenant = datetime.datetime.now()
    out = []
    for e in retenus(sports.load_data(), pret.load_data(), data.get("choix") or {},
                     data.get("notes") or [], alertes,
                     rappels(alertes, data.get("jours") or {}, data.get("delais"))
                     + essai(data.get("test"))):
        d = _decalage(e, e["alerte"] or alertes.get(e["type"]))
        if d is None:
            continue
        for jour in _occurrences(e, (maintenant - datetime.timedelta(days=8)).date(),
                                 (maintenant + datetime.timedelta(days=400)).date()):
            debut = (datetime.datetime.combine(jour, e["debut"].time()) if e["debut"]
                     else datetime.datetime.combine(jour, datetime.time()))
            if debut + d >= maintenant:
                out.append({"quand": (debut + d).strftime("%Y-%m-%dT%H:%M"),
                            "titre": e["titre"], "type": e["type"]})
                break
    return sorted(out, key=lambda x: x["quand"])[:n]


# ─── Lecture des agendas iCloud (le calendrier de Pilote) ────────────────────

def _deplier_ics(texte: str) -> list:
    return re.sub(r"\r?\n[ \t]", "", texte or "").splitlines()


def _desechapper(v: str) -> str:
    return re.sub(r"\\([\\;,nN])", lambda m: "\n" if m.group(1) in "nN" else m.group(1), v)


def _quand(params: str, valeur: str):
    """(date ou datetime local, toute_la_journee)."""
    valeur = valeur.strip()
    if "VALUE=DATE" in params.upper() and "DATE-TIME" not in params.upper() or len(valeur) == 8:
        return datetime.datetime.strptime(valeur[:8], "%Y%m%d").date(), True
    t = datetime.datetime.strptime(valeur[:15], "%Y%m%dT%H%M%S")
    if valeur.endswith("Z"):
        # UTC (iCloud rend ainsi les occurrences d'un evenement repete) : heure du PC
        t = t.replace(tzinfo=datetime.timezone.utc).astimezone().replace(tzinfo=None)
    return t, False   # TZID : pris comme l'heure du PC (simple, juste en France)


def _duree(v: str) -> datetime.timedelta:
    m = re.fullmatch(r"[+]?P(?:(\d+)W)?(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?", v.strip())
    if not m:
        return datetime.timedelta(0)
    s, j, h, mi, se = (int(x or 0) for x in m.groups())
    return datetime.timedelta(weeks=s, days=j, hours=h, minutes=mi, seconds=se)


def lire_ics(texte: str) -> list:
    """Les VEVENT d'un fichier iCalendar : {debut, fin (dates incluses), heure, heureFin, titre}."""
    out, ev = [], None
    for ligne in _deplier_ics(texte):
        if ligne == "BEGIN:VEVENT":
            ev = {}
        elif ligne == "END:VEVENT" and ev is not None:
            out.append(ev)
            ev = None
        elif ev is not None and ":" in ligne:
            tete, valeur = ligne.split(":", 1)
            nom, _, params = tete.partition(";")
            ev.setdefault(nom.upper(), (params, valeur))
    res = []
    for ev in out:
        if "DTSTART" not in ev or ev.get("STATUS", ("", ""))[1].upper() == "CANCELLED":
            continue
        try:
            debut, journee = _quand(*ev["DTSTART"])
            if "DTEND" in ev:
                fin = _quand(*ev["DTEND"])[0]
            else:
                fin = debut + (_duree(ev["DURATION"][1]) if "DURATION" in ev
                               else datetime.timedelta(days=1 if journee else 0))
            if journee:
                jour_fin = max(fin - datetime.timedelta(days=1), debut)
            else:
                # Fin a minuit pile : l'evenement s'arrete la veille
                jour_fin = (fin - datetime.timedelta(seconds=1)).date() if fin > debut else debut.date()
        except (ValueError, KeyError, TypeError, AttributeError):
            continue   # date illisible ou melange date / date-heure : evenement ignore
        res.append({"debut": (debut if journee else debut.date()).isoformat(),
                    "fin": jour_fin.isoformat(),
                    "heure": "" if journee else debut.strftime("%H:%M"),
                    "heureFin": "" if journee else fin.strftime("%H:%M"),
                    "titre": _desechapper(ev.get("SUMMARY", ("", "Sans titre"))[1]) or "Sans titre"})
    return res


def _lire_calendrier(cal: str, auth: tuple, debut: datetime.date, fin: datetime.date,
                     a_sauter: str) -> list:
    a = debut.strftime("%Y%m%dT000000Z")
    b = (fin + datetime.timedelta(days=1)).strftime("%Y%m%dT000000Z")
    corps = ('<?xml version="1.0" encoding="utf-8"?>'
             '<c:calendar-query xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">'
             f'<d:prop><c:calendar-data><c:expand start="{a}" end="{b}"/></c:calendar-data></d:prop>'
             '<c:filter><c:comp-filter name="VCALENDAR"><c:comp-filter name="VEVENT">'
             f'<c:time-range start="{a}" end="{b}"/></c:comp-filter></c:comp-filter></c:filter>'
             '</c:calendar-query>').encode("utf-8")
    _, _, contenu = _requete("REPORT", cal, auth, corps, profondeur="1")
    try:
        rep = ET.fromstring(contenu)
    except ET.ParseError as e:
        raise ErreurAgenda("caldav", "Réponse d'iCloud illisible.") from e
    out = []
    for r in rep.findall(f"{_DAV}response"):
        nom = urllib.parse.unquote((r.findtext(f"{_DAV}href") or "").rsplit("/", 1)[-1])
        if nom.startswith(a_sauter):
            continue   # les notes : la page les montre depuis Pilote, sans attendre l'envoi
        for ev in lire_ics(r.findtext(f".//{_CAL}calendar-data") or ""):
            if ev["fin"] >= debut.isoformat() and ev["debut"] <= fin.isoformat():
                out.append(ev)
    return out


def icloud(debut: str, fin: str) -> list:
    """Tout ce qu'il y a dans les agendas iCloud du compte entre deux dates,
    agenda « Pilote » compris : le calendrier de Pilote montre ce que montre
    le telephone (demande d'Arthur du 22/10/2026). Seules les notes de Pilote
    sont sautees, la page les affiche elle-meme."""
    d0, d1 = _jour(debut), _jour(fin)
    if not d0 or not d1 or d1 < d0 or (d1 - d0).days > 62:
        raise ErreurAgenda("saisie", "Période illisible.")
    data = _store.load()
    auth = _identifiants(data)
    a_sauter = f"pilote-{data.get('id')}-note-"
    out = []
    for c in _calendriers(auth):
        for ev in _lire_calendrier(c["url"], auth, d0, d1, a_sauter):
            out.append(dict(ev, agenda=c["nom"], couleur=c.get("couleur") or ""))
    out.sort(key=lambda x: (x["debut"], x["heure"], x["titre"]))
    return out


def _ics(uid: str, lignes: list) -> bytes:
    maintenant = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    # La description de l'alerte (VALARM) n'est pas celle de l'evenement
    propres = lignes[:lignes.index("BEGIN:VALARM")] if "BEGIN:VALARM" in lignes else lignes
    tout = (["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Pilote//Agenda//FR", "BEGIN:VEVENT",
             "UID:" + uid, "DTSTAMP:" + maintenant] + lignes
            + ["DESCRIPTION:Ajouté par Pilote." if not any(l.startswith("DESCRIPTION:") for l in propres) else "",
               "END:VEVENT", "END:VCALENDAR"])
    return ("\r\n".join(_plier(l) for l in tout if l) + "\r\n").encode("utf-8")


def _empreinte(lignes: list) -> str:
    return hashlib.sha256("\n".join(lignes).encode("utf-8")).hexdigest()[:16]


# ─── Synchronisation ─────────────────────────────────────────────────────────

# Deux verrous. _verrou : un seul echange avec iCloud a la fois (envoi,
# reglages, deconnexion), il peut durer 30 s (premier envoi de 50 seances).
# _verrou_fichier : la lecture-modification-ecriture d'agenda.json, toujours
# breve. Une note s'enregistre donc sans attendre la fin d'un envoi en cours
# (jusqu'au 22/10/2026, elle l'attendait, puis passait derriere les seances).
_verrou = threading.RLock()
_verrou_fichier = threading.Lock()
_minuteur = None


def _modifier(changer) -> None:
    """Relit agenda.json, applique `changer(data)`, reecrit : les cles que
    `changer` ne touche pas (les notes, pour un envoi) restent celles du disque."""
    with _verrou_fichier:
        data = _store.load()
        changer(data)
        _store.save(data)
_etat = {"dossier": "", "enCours": False, "quand": "", "erreur": "", "nb": 0}


def _etat_public() -> dict:
    if _etat["dossier"] != str(storage.get_user_dir()):
        return {"enCours": False, "quand": "", "erreur": "", "nb": 0}
    return {k: _etat[k] for k in ("enCours", "quand", "erreur", "nb")}


def planifier(delai: float = 3) -> None:
    """Synchronise dans `delai` secondes ; un nouvel appel repousse le precedent
    (dix seances enregistrees d'affilee = un seul envoi)."""
    global _minuteur
    if _minuteur is not None:
        _minuteur.cancel()
    _minuteur = threading.Timer(delai, _synchroniser_en_fond)
    _minuteur.daemon = True
    _minuteur.start()


def _synchroniser_en_fond() -> None:
    try:
        synchroniser()
    except Exception:
        pass   # l'erreur est dans _etat, affichee par l'onglet Agenda › iCloud


def synchroniser() -> dict:
    with _verrou:
        dossier = str(storage.get_user_dir())
        data = _store.load()
        if not data.get("secret") or not data.get("calendrier"):
            return _etat_public()
        _etat.update(dossier=dossier, enCours=True, erreur="")
        try:
            nb = _envoyer(data, dossier)
            _etat.update(quand=datetime.datetime.now().strftime("%H:%M"), nb=nb)
        except ErreurAgenda as e:
            _etat["erreur"] = e.message
            if e.code == "reseau":
                planifier(REESSAI)
            raise
        except Exception as e:
            _etat["erreur"] = "Envoi interrompu : " + str(e)
            raise
        finally:
            _etat["enCours"] = False
        return _etat_public()


def _envoyer(data: dict, dossier: str) -> int:
    auth = _identifiants(data)
    prefixe = f"pilote-{data['id']}-"
    cal = data["calendrier"]
    # Agendas quittes (changement d'agenda) : on y retire ce que Pilote y avait
    # mis ; celui que Pilote avait cree part en entier
    for ancien in list(data.get("aSupprimer") or []):
        _requete("DELETE", ancien, auth, accepte=(200, 204, 404))
    for ancien in list(data.get("aNettoyer") or []):
        try:
            for nom in _nos_fichiers(ancien, auth, prefixe):
                _retirer(ancien, auth, nom)
        except ErreurAgenda as e:
            if e.code != "caldav":   # agenda supprime entre-temps : rien a retirer
                raise
    alertes = data.get("alertes") or {}
    tous = evenements(sports.load_data(), pret.load_data(),
                      data.get("choix") or {}, data.get("notes") or [],
                      alertes, rappels(alertes, data.get("jours") or {}, data.get("delais"))
                      + essai(data.get("test")))
    # Les notes d'abord : ecrites a la main pour l'agenda, elles n'attendent
    # pas derriere cinquante seances
    voulus = {prefixe + cle + ".ics": tous[cle]
              for cle in sorted(tous, key=lambda c: not c.startswith("note-"))}
    presents = _nos_fichiers(cal, auth, prefixe)
    faits = dict(data.get("envoyes") or {})
    for nom in presents - set(voulus):
        _retirer(cal, auth, nom)
        faits.pop(nom, None)
    for nom, lignes in voulus.items():
        emp = _empreinte(lignes)
        if nom in presents and faits.get(nom) == emp:
            continue
        _requete("PUT", cal + urllib.parse.quote(nom), auth, _ics(nom[:-4], lignes),
                 type_corps="text/calendar; charset=utf-8")
        faits[nom] = emp
    # Utilisateur change pendant l'envoi : ne pas ecrire dans le fichier de l'autre
    if str(storage.get_user_dir()) == dossier:
        _modifier(lambda d: d.update(envoyes={n: e for n, e in faits.items() if n in voulus},
                                     aNettoyer=[], aSupprimer=[]))
    return len(voulus)


# ─── API appelee par app.py ──────────────────────────────────────────────────

def config() -> dict:
    data = _store.load()
    choix = data.get("choix") or {}
    return {"adresse":    data.get("adresse") or "",
            "connecte":   bool(data.get("secret")),
            "calendrier": data.get("calendrier") or "",
            "calendrierCree": bool(data.get("calendrierCree")),
            "choix":      {c: bool(choix.get(c)) for c in CHOIX},
            "notes":      data.get("notes") or [],
            "alertes":    _alertes_propres(data.get("alertes")),
            "jours":      _jours_propres(data.get("jours")),
            "delais":     {t: _delai(data.get("delais"), t) for t in DELAIS},
            "etat":       _etat_public()}


def _alertes_propres(alertes) -> dict:
    alertes = alertes if isinstance(alertes, dict) else {}
    return {t: alertes.get(t) if alertes.get(t) in (RESUME_VALEURS if t == "resume" else ALERTES_VALEURS)
            else "" for t in ALERTES}


def _jours_propres(jours) -> dict:
    jours = jours if isinstance(jours, dict) else {}
    return {t: min(max(int(_nombre(jours.get(t))) or 1, 1), 28) for t in MENSUELS}


def regler_alertes(alertes: dict, jours: dict, delais: dict = None) -> dict:
    """Onglet Notifications : enregistre, puis envoie dans la seconde."""
    _modifier(lambda d: d.update(alertes=_alertes_propres(alertes), jours=_jours_propres(jours),
                                 delais={t: _delai(delais, t) for t in DELAIS}))
    planifier(0.5)
    return config()


def tester() -> dict:
    """Bouton « Envoyer un essai » : un evenement dans TEST_MINUTES minutes,
    alerte a l'heure, envoye tout de suite (l'erreur s'affiche). Retire au
    premier envoi apres une heure."""
    data = _store.load()
    if not data.get("secret") or not data.get("calendrier"):
        raise ErreurAgenda("config", "Connecte d'abord ton agenda iCloud.")
    quand = (datetime.datetime.now() + datetime.timedelta(minutes=TEST_MINUTES + 1)).replace(second=0, microsecond=0)
    _modifier(lambda d: d.update(test=quand.strftime("%Y-%m-%dT%H:%M")))
    synchroniser()
    # Retire l'essai une heure apres, meme si rien d'autre ne relance d'envoi
    # (Pilote ferme avant : au lancement suivant). Minuteur a part : planifier()
    # l'annulerait au prochain enregistrement.
    menage = threading.Timer(TEST_MINUTES * 60 + 3720, _synchroniser_en_fond)
    menage.daemon = True
    menage.start()
    return {"heure": quand.strftime("%H:%M")}


def planifier_si(*types) -> None:
    """planifier(), seulement si l'un de ces rappels part : le PEA, la Sante et
    le Patrimoine s'enregistrent souvent, sans rien changer a l'agenda sinon."""
    try:
        alertes = _store.load().get("alertes") or {}
    except Exception:
        return
    if any(alertes.get(t) for t in types):
        planifier()


def enregistrer_notes(notes: list) -> dict:
    """Les notes de l'agenda, ecrites par la page (elle garde l'etat, Python persiste)."""
    propres = []
    for n in (notes if isinstance(notes, list) else []):
        # L'id finit dans un nom de fichier chez iCloud : lettres, chiffres, - et _
        id_ = re.sub(r"[^A-Za-z0-9_-]", "", str(n.get("id") or ""))[:40] if isinstance(n, dict) else ""
        if not id_ or not _jour(n.get("date")):
            continue
        heure = str(n.get("heure") or "")
        propres.append({
            "id":    id_,
            "titre": str(n.get("titre") or "").strip()[:200],
            "date":  _jour(n["date"]).isoformat(),
            "heure": heure if re.fullmatch(r"\d{2}:\d{2}", heure) else "",
            "duree": max(int(_nombre(n.get("duree"))), 0),
            "texte": str(n.get("texte") or "")[:2000],
            # Notification propre a la note (26/10/2026) : sa repetition, son alerte
            "repete": n.get("repete") if n.get("repete") in REPETITIONS else "",
            "alerte": n.get("alerte") if n.get("alerte") in ALERTES_NOTE else "",
        })
    _modifier(lambda d: d.update(notes=propres))   # sans attendre un envoi en cours
    planifier(0.5)
    return config()


def connecter(adresse: str, mdp: str) -> dict:
    """N'enregistre qu'un mot de passe qu'iCloud vient d'accepter."""
    adresse = (adresse or "").strip()
    mdp = re.sub(r"\s+", "", mdp or "")
    if "@" not in adresse:
        raise ErreurAgenda("saisie", "Saisis ton identifiant Apple complet (son adresse e-mail).")
    if not mdp:
        raise ErreurAgenda("saisie", "Colle le mot de passe pour app.")
    with _verrou:
        cals = _calendriers((adresse, mdp))
        secret = actus._chiffrer(mdp, TROUSSEAU, "Pilote : mot de passe pour app iCloud (Agenda)")
        _modifier(lambda d: d.update(adresse=adresse, secret=secret,
                                     id=d.get("id") or uuid.uuid4().hex[:10]))
    return {**config(), "calendriers": cals}


def calendriers() -> list:
    return _calendriers(_identifiants(_store.load()))


def regler(calendrier: str, choix: dict) -> dict:
    """calendrier : url d'un agenda du compte, ou « nouveau » pour en creer un nomme Pilote."""
    with _verrou:
        data = _store.load()
        auth = _identifiants(data)
        ancien = data.get("calendrier") or ""
        if calendrier == "nouveau":
            calendrier, cree = _creer_calendrier(auth), True
        elif calendrier == ancien:
            cree = bool(data.get("calendrierCree"))
        else:
            if calendrier not in [c["url"] for c in _calendriers(auth)]:
                raise ErreurAgenda("saisie", "Cet agenda n'existe plus dans iCloud.")
            cree = False
        maj = {"calendrier": calendrier, "calendrierCree": cree,
               "choix": {c: bool((choix or {}).get(c)) for c in CHOIX}}
        if ancien and ancien != calendrier:
            liste = "aSupprimer" if data.get("calendrierCree") else "aNettoyer"
            maj[liste] = list(dict.fromkeys((data.get(liste) or []) + [ancien]))
            maj["envoyes"] = {}
        _modifier(lambda d: d.update(maj))
    return config()   # la page lance l'envoi elle-meme (synchroniser), pour l'afficher


def deconnecter() -> dict:
    """Retire de l'agenda ce que Pilote y a mis, puis oublie le mot de passe.
    L'agenda « Pilote » cree par Pilote est supprime en entier."""
    avertissement = ""
    with _verrou:
        data = _store.load()
        cal = data.get("calendrier") or ""
        try:
            auth = _identifiants(data) if data.get("secret") and cal else None
            if auth and data.get("calendrierCree"):
                _requete("DELETE", cal, auth, accepte=(200, 204, 404))
            elif auth:
                for nom in _nos_fichiers(cal, auth, f"pilote-{data.get('id')}-"):
                    _retirer(cal, auth, nom)
        except ErreurAgenda as e:
            avertissement = ("Les événements de Pilote sont restés dans l'agenda (" + e.message
                             + "). Tu peux les supprimer depuis ton iPhone.")
        actus._oublier(data.get("secret") or "", TROUSSEAU)
        _modifier(lambda d: d.update(secret="", calendrier="", calendrierCree=False, envoyes={},
                                     aNettoyer=[], aSupprimer=[]))
    return {**config(), "avertissement": avertissement}
