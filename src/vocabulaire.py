"""
vocabulaire.py — Module "Vocabulaire" : apprendre des mots par repetition espacee.

Le principe tient en quatre boites (Leitner) : 1 jour, 1 semaine, 1 mois,
6 mois. Un mot su monte d'une boite, un mot rate DESCEND d'une boite — et
reste en boite 1 s'il y est deja. Dans les deux cas sa prochaine revision
tombe a la date du jour plus l'intervalle de SA NOUVELLE boite.

Consequence utile de la descente : un mot rate en boite "6 mois" repasse en
"1 mois" et revient donc dans un mois, pas dans six. Un mot qu'on ne sait
plus ne doit pas pouvoir se cacher une demi-annee de plus.

Ce qui n'est PAS fait ici
─────────────────────────
La correction. L'app affiche la reponse et c'est l'utilisateur qui tranche
"je savais" / "rate". Comparer deux chaines donnerait des faux negatifs sur
un accent, un synonyme, un article ou un pluriel — et une revision fausse
pourrit la boite d'un mot pour des mois. La saisie sert a s'engager sur une
reponse avant de la decouvrir, elle n'est jamais notee.

Le sens de la question non plus : il est choisi au debut de chaque session,
vaut pour toute la session, et ne se range donc pas dans le fichier.

Chaque liste a ses PROPRES boites : reviser l'anglais ne touche pas au
francais, les deux piles ne se melangent jamais. C'est la raison d'etre du
champ `listeId` sur chaque mot, et de listes creables plutot que de deux
langues codees en dur.

Aucun mot n'est livre : l'interet du module est ce que l'utilisateur y met.
Seules les deux listes de depart existent, et elles sont modifiables.

Emplacement      : <app_dir>/users/<slug>/vocabulaire.json
Backup quotidien : <app_dir>/users/<slug>/backups_vocabulaire/

Modele de donnees
─────────────────
listes     : {id, label, icon, color, mode: "trad"|"def"}
mots       : {id, listeId, mot, reponse, exemple, note, boite 1-4,
              prochaine "YYYY-MM-DD", creeLe, derniereRevue, nbVus, nbReussis}
historique : [{date, listeId, vus, ok}] — un agregat par jour et par liste
"""
from __future__ import annotations

import datetime

import jsonstore


# ─── Catalogues ───────────────────────────────────────────────────────────────

# `jours` est l'intervalle applique QUAND le mot entre dans la boite. C'est la
# seule source de verite du calendrier : l'UI lit ces valeurs, elle ne les
# recopie pas. 182 jours = six mois, a un jour pres selon l'annee.
BOITES = [
    {"id": 1, "label": "1 jour",    "court": "1 j",   "jours": 1,   "color": "#dc2626"},
    {"id": 2, "label": "1 semaine", "court": "1 sem", "jours": 7,   "color": "#d97706"},
    {"id": 3, "label": "1 mois",    "court": "1 mois", "jours": 30,  "color": "#2563eb"},
    {"id": 4, "label": "6 mois",    "court": "6 mois", "jours": 182, "color": "#16a34a"},
]

BOITE_MIN = BOITES[0]["id"]
BOITE_MAX = BOITES[-1]["id"]

# Le mode d'une liste decide du LIBELLE de la seconde face, rien d'autre : la
# mecanique de revision est identique. Une liste de langue demande une
# traduction, une liste de francais demande une definition.
MODES = [
    {"id": "trad", "label": "Traduction", "reponse": "Traduction", "icon": "🔁"},
    {"id": "def",  "label": "Définition", "reponse": "Définition", "icon": "📖"},
]

# Deux listes pour demarrer, pas deux langues gravees : elles se renomment, se
# suppriment et s'ajoutent depuis Parametres → Vocabulaire.
LISTES_DEFAUT = [
    {"id": "li_en", "label": "Anglais",  "icon": "🇬🇧", "color": "#2563eb", "mode": "trad"},
    {"id": "li_fr", "label": "Français", "icon": "🇫🇷", "color": "#7c3aed", "mode": "def"},
]

# L'historique ne sert qu'aux statistiques. Deux ans suffisent largement a
# tracer une courbe, et au-dela le fichier grossirait pour rien.
HISTORIQUE_JOURS = 730


# ─── Normalisation ────────────────────────────────────────────────────────────

def _today() -> str:
    return datetime.date.today().isoformat()


def _clamp_boite(v) -> int:
    try:
        n = int(v)
    except (TypeError, ValueError):
        n = BOITE_MIN
    return max(BOITE_MIN, min(BOITE_MAX, n))


def _int(v, defaut: int = 0) -> int:
    try:
        return max(0, int(v))
    except (TypeError, ValueError):
        return defaut


def _date(v, defaut: str) -> str:
    """Garde une date "YYYY-MM-DD" plausible, sinon renvoie le defaut."""
    s = (v or "").strip()
    if len(s) == 10 and s[4] == "-" and s[7] == "-":
        try:
            datetime.date.fromisoformat(s)
            return s
        except ValueError:
            pass
    return defaut


def _normalise_liste(l: dict) -> dict:
    l.setdefault("id", "")
    l["label"] = (l.get("label") or "Liste").strip() or "Liste"
    l.setdefault("icon", "📚")
    l.setdefault("color", "#2563eb")
    if l.get("mode") not in [m["id"] for m in MODES]:
        l["mode"] = "trad"
    return l


def _normalise_mot(m: dict) -> dict:
    """Complete un mot avec les cles que le JS attend toujours."""
    m.setdefault("id", "")
    m.setdefault("listeId", "")
    m["mot"]     = (m.get("mot") or "").strip()
    m["reponse"] = (m.get("reponse") or "").strip()
    m.setdefault("exemple", "")
    m.setdefault("note", "")
    m["boite"] = _clamp_boite(m.get("boite"))
    cree = _date(m.get("creeLe"), _today())
    m["creeLe"] = cree
    # Un mot sans date de revision est du tout de suite : c'est le cas d'un
    # mot qu'on vient d'ajouter, et celui d'un fichier bricole a la main.
    m["prochaine"]     = _date(m.get("prochaine"), cree)
    m["derniereRevue"] = _date(m.get("derniereRevue"), "")
    m["nbVus"]    = _int(m.get("nbVus"))
    m["nbReussis"] = _int(m.get("nbReussis"))
    return m


# ─── Fichier ──────────────────────────────────────────────────────────────────

def default_data() -> dict:
    return {
        "_meta": {
            "version": 1,
            "schema": "vocabulaire.v1",
            "createdAt":   datetime.date.today().isoformat(),
            "lastSavedAt": datetime.datetime.now().isoformat(timespec="seconds"),
        },
        "listes":     [dict(l) for l in LISTES_DEFAUT],
        "mots":       [],
        "historique": [],
        "_nid": {"li": 1, "mot": 1},
    }


_store = jsonstore.JsonStore(
    filename="vocabulaire.json",
    backup_dirname="backups_vocabulaire",
    schema="vocabulaire.v1",
    default_factory=default_data,
)


def load_data() -> dict:
    data = _store.load()
    for key in ("listes", "mots", "historique"):
        if not isinstance(data.get(key), list):
            data[key] = []

    # Un fichier dont on aurait supprime toutes les listes laisserait les mots
    # orphelins et l'onglet vide sans moyen d'en recreer une.
    if not data["listes"]:
        data["listes"] = [dict(l) for l in LISTES_DEFAUT]
    data["listes"] = [_normalise_liste(l) for l in data["listes"]]

    # Un mot dont la liste a disparu est rattache a la premiere : mieux vaut
    # une ligne mal rangee qu'une ligne invisible qu'on croit perdue.
    connues = {l["id"] for l in data["listes"]}
    defaut  = data["listes"][0]["id"]
    data["mots"] = [_normalise_mot(m) for m in data["mots"]]
    for m in data["mots"]:
        if m["listeId"] not in connues:
            m["listeId"] = defaut

    if not isinstance(data.get("_nid"), dict):
        data["_nid"] = {"li": 1, "mot": 1}
    return data


def save_data(data: dict) -> None:
    data = data or {}
    if isinstance(data.get("historique"), list):
        data["historique"] = _purge_historique(data["historique"])
    _store.save(data)


def _purge_historique(hist: list) -> list:
    """Coupe l'historique a HISTORIQUE_JOURS — il ne sert qu'aux courbes."""
    limite = (datetime.date.today()
              - datetime.timedelta(days=HISTORIQUE_JOURS)).isoformat()
    out = []
    for h in hist:
        if not isinstance(h, dict):
            continue
        d = _date(h.get("date"), "")
        if d and d >= limite:
            out.append(h)
    out.sort(key=lambda h: h.get("date", ""))
    return out
