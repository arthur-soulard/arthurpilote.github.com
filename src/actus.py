"""
actus.py — Module « Actus » : la boite Gmail des newsletters, lue dans Pilote.

Pourquoi IMAP et pas Gmail lui-meme : Gmail refuse d'etre affiche dans une
autre page (X-Frame-Options), et Google bloque la connexion a un compte dans
un navigateur integre a une app. Pilote releve donc la boite en IMAP
(imap.gmail.com, port 993, TLS) avec un mot de passe d'application Google,
et affiche les mails a sa facon. Decide avec Arthur le 11/10/2026 : lecture
seule (ouvrir un mail le marque lu, on peut le remettre en non lu), images
des newsletters affichees, une section « Actus » a part.

Emplacement : <app_dir>/users/<slug>/actus.json
              {"adresse": "x@gmail.com", "secret": "dpapi:<base64>"}

Le mot de passe ne repasse jamais par la page : le JS l'envoie une fois
(save_actus), Python le chiffre avec DPAPI (Windows, lie a la session
Windows de l'utilisateur) et le garde pour lui. Un backup ou une archive USB
relue sur un autre PC ne sait donc pas le dechiffrer : il faut le ressaisir.

Une seule connexion IMAP, gardee ouverte et partagee sous verrou : pywebview
appelle chaque methode de l'Api dans son propre fil, et Gmail limite le
nombre de connexions simultanees par compte.
"""
from __future__ import annotations

import base64
import datetime
import email
import email.policy
import email.utils
import html
import imaplib
import re
import socket
import ssl
import sys
import threading
import time
from email.header import decode_header, make_header

import jsonstore
import storage


HOTE     = "imap.gmail.com"
PORT     = 993
DELAI    = 20      # s : au-dela, Gmail est considere injoignable
NB_MAILS = 60      # les plus recents de la boite de reception


class ErreurActus(Exception):
    """Erreur a montrer telle quelle. code : config, saisie, auth, reseau, imap, absent."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


# ─── Fichier ─────────────────────────────────────────────────────────────────

def default_data() -> dict:
    return {
        "_meta": {
            "version": 1,
            "schema": "actus.v1",
            "createdAt":   datetime.date.today().isoformat(),
            "lastSavedAt": datetime.datetime.now().isoformat(timespec="seconds"),
        },
        "adresse": "",
        "secret":  "",
    }


_store = jsonstore.JsonStore(
    filename="actus.json",
    backup_dirname="backups_actus",
    schema="actus.v1",
    default_factory=default_data,
)


# ─── Chiffrement du mot de passe (DPAPI) ─────────────────────────────────────
#
# DPAPI chiffre avec une cle liee a la session Windows : seul ce compte
# Windows, sur ce PC, sait relire le secret. Pas de dependance, pas de cle a
# ranger nous-memes. Hors Windows (chantier Mac), le secret est seulement
# encode : le Trousseau devra prendre le relais.

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    class _Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD),
                    ("pbData", ctypes.POINTER(ctypes.c_char))]

    # Instances privees : poser des argtypes sur ctypes.windll.crypt32 les
    # imposerait a tout le processus.
    _crypt32  = ctypes.WinDLL("crypt32", use_last_error=True)
    _kernel32 = ctypes.WinDLL("kernel32")
    for _fn in (_crypt32.CryptProtectData, _crypt32.CryptUnprotectData):
        _fn.argtypes = [ctypes.POINTER(_Blob), ctypes.c_wchar_p, ctypes.POINTER(_Blob),
                        ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD,
                        ctypes.POINTER(_Blob)]
        _fn.restype = wintypes.BOOL
    _kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    _kernel32.LocalFree.restype  = ctypes.c_void_p

    _CRYPTPROTECT_UI_FORBIDDEN = 0x1

    def _dpapi(donnees: bytes, chiffrer: bool) -> bytes:
        tampon = ctypes.create_string_buffer(donnees, len(donnees))
        entree = _Blob(len(donnees), ctypes.cast(tampon, ctypes.POINTER(ctypes.c_char)))
        sortie = _Blob()
        fn = _crypt32.CryptProtectData if chiffrer else _crypt32.CryptUnprotectData
        if not fn(ctypes.byref(entree), "Pilote Actus" if chiffrer else None, None,
                  None, None, _CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(sortie)):
            raise OSError(ctypes.get_last_error(), "DPAPI a refuse")
        try:
            return ctypes.string_at(sortie.pbData, sortie.cbData)
        finally:
            _kernel32.LocalFree(ctypes.cast(sortie.pbData, ctypes.c_void_p))


def _chiffrer(mdp: str) -> str:
    brut = mdp.encode("utf-8")
    if sys.platform == "win32":
        return "dpapi:" + base64.b64encode(_dpapi(brut, True)).decode("ascii")
    return "b64:" + base64.b64encode(brut).decode("ascii")


def _dechiffrer(secret: str) -> str:
    if secret.startswith("dpapi:") and sys.platform == "win32":
        return _dpapi(base64.b64decode(secret[6:]), False).decode("utf-8")
    if secret.startswith("b64:"):
        return base64.b64decode(secret[4:]).decode("utf-8")
    raise ValueError("secret illisible")


# ─── Connexion IMAP ──────────────────────────────────────────────────────────

class _Imap(imaplib.IMAP4_SSL):
    """IMAP4_SSL avec un delai d'attente : en Python 3.8 (le dev), le
    constructeur n'en accepte pas, et une connexion bloquee figerait le fil
    pour toujours. *args : 3.9+ passe le timeout, 3.8 rien."""

    def _create_socket(self, *args):
        sock = socket.create_connection((self.host, self.port), DELAI)
        return self.ssl_context.wrap_socket(sock, server_hostname=self.host)


def _ouvrir_imap() -> imaplib.IMAP4:
    # Contexte explicite : celui qu'imaplib prend par defaut en 3.8 ne
    # verifie PAS le certificat du serveur, et le mot de passe passe dedans.
    return _Imap(HOTE, PORT, ssl_context=ssl.create_default_context())


_verrou   = threading.RLock()
_conn     = None     # connexion ouverte, boite de reception selectionnee
_conn_cle = None     # (dossier utilisateur, adresse) de cette connexion


def _fermer() -> None:
    global _conn, _conn_cle
    if _conn is not None:
        try:
            _conn.logout()
        except Exception:
            pass
    _conn, _conn_cle = None, None


def _erreur_login(e: Exception) -> ErreurActus:
    txt = str(e)
    if "Application-specific password required" in txt:
        return ErreurActus("auth", "Gmail demande un mot de passe d'application : celui de "
                                   "ton compte Google ne marche pas ici. Suis la fiche "
                                   "« Créer le mot de passe ».")
    if "IMAP" in txt and ("not enabled" in txt or "disabled" in txt):
        return ErreurActus("auth", "L'accès IMAP est coupé sur cette boîte. Dans Gmail : "
                                   "Paramètres › Transfert et POP/IMAP › Activer l'IMAP.")
    return ErreurActus("auth", "Gmail refuse l'adresse ou le mot de passe. Vérifie l'adresse, "
                               "et colle le mot de passe d'application (16 caractères), "
                               "pas celui du compte.")


def _login(adresse: str, mdp: str) -> imaplib.IMAP4:
    """Connexion neuve, identifiee, boite de reception selectionnee."""
    try:
        M = _ouvrir_imap()
    except ssl.SSLError as e:
        raise ErreurActus("reseau", "La connexion sécurisée à Gmail a échoué. "
                                    "Réessaie dans un instant.") from e
    except OSError as e:
        raise ErreurActus("reseau", "Gmail ne répond pas. Vérifie ta connexion "
                                    "internet, puis réessaie.") from e
    try:
        M.login(adresse, mdp)
    except (imaplib.IMAP4.error, UnicodeError) as e:
        try:
            M.logout()
        except Exception:
            pass
        raise _erreur_login(e) from e
    typ, _ = M.select("INBOX")
    if typ != "OK":
        raise ErreurActus("imap", "Gmail n'a pas ouvert la boîte de réception.")
    return M


def _identifiants() -> tuple:
    data = _store.load()
    adresse = (data.get("adresse") or "").strip()
    secret  = data.get("secret") or ""
    if not adresse or not secret:
        raise ErreurActus("config", "Aucune boîte n'est connectée.")
    try:
        return adresse, _dechiffrer(secret)
    except Exception:
        raise ErreurActus("config", "Le mot de passe enregistré ne se relit pas ici (fichier "
                                    "venu d'un autre PC ?). Ressaisis-le dans Actus › Connexion.")


def _avec_imap(fonction):
    """Passe la connexion a `fonction`, en la (re)ouvrant au besoin.
    Gmail ferme les connexions qui dorment, et la veille du PC les coupe :
    une connexion morte est rouverte une fois, sans que l'appelant le voie."""
    global _conn, _conn_cle
    adresse, mdp = _identifiants()
    cle = (str(storage.get_user_dir()), adresse)
    with _verrou:
        for essai in (1, 2):
            neuve = False
            if _conn is None or _conn_cle != cle:
                _fermer()
                _conn, _conn_cle = _login(adresse, mdp), cle
                neuve = True
            try:
                if not neuve:
                    _conn.noop()       # detecte une connexion morte, et fait voir les nouveaux mails
                return fonction(_conn)
            except (imaplib.IMAP4.abort, OSError) as e:
                _fermer()
                if essai == 2:
                    raise ErreurActus("reseau", "La connexion à Gmail a été coupée. "
                                                "Réessaie dans un instant.") from e


# ─── Configuration ───────────────────────────────────────────────────────────

def config() -> dict:
    data = _store.load()
    return {"adresse":  data.get("adresse") or "",
            "connecte": bool(data.get("adresse") and data.get("secret"))}


def connecter(adresse: str, mdp: str) -> dict:
    """N'enregistre qu'un mot de passe que Gmail vient d'accepter."""
    global _conn, _conn_cle
    adresse = (adresse or "").strip()
    # Google l'affiche en quatre groupes de quatre : les espaces ne comptent pas
    mdp = re.sub(r"\s+", "", mdp or "")
    if "@" not in adresse:
        raise ErreurActus("saisie", "Saisis l'adresse Gmail complète (…@gmail.com).")
    if not mdp:
        raise ErreurActus("saisie", "Colle le mot de passe d'application.")
    with _verrou:
        _fermer()
        M = _login(adresse, mdp)
        data = _store.load()
        data["adresse"] = adresse
        data["secret"]  = _chiffrer(mdp)
        _store.save(data)
        _conn, _conn_cle = M, (str(storage.get_user_dir()), adresse)
    return config()


def deconnecter() -> dict:
    """Oublie le mot de passe ; l'adresse reste pour la prochaine fois."""
    with _verrou:
        _fermer()
        data = _store.load()
        data["secret"] = ""
        _store.save(data)
    return config()


# ─── Lecture de la boite ─────────────────────────────────────────────────────

_RE_UID     = re.compile(rb"UID (\d+)")
_RE_FLAGS   = re.compile(rb"FLAGS \(([^)]*)\)")
_RE_THRID   = re.compile(rb"X-GM-THRID (\d+)")
_RE_LABELS  = re.compile(rb'X-GM-LABELS \(((?:[^()"]|"(?:[^"\\]|\\.)*")*)\)')
_RE_ATOME   = re.compile(rb'"((?:[^"\\]|\\.)*)"|([^\s()"]+)')
_RE_REPONSE = re.compile(rb"\d+ \(")


def _utf7(s: str) -> str:
    """Nom de libelle IMAP (UTF-7 modifie, RFC 3501) : « March&AOk-s » -> « Marchés »."""
    def _dec(m):
        b64 = m.group(1)
        if not b64:
            return "&"
        b64 = b64.replace(",", "/")
        b64 += "=" * (-len(b64) % 4)
        try:
            return base64.b64decode(b64).decode("utf-16-be")
        except Exception:
            return m.group(0)
    return re.sub(r"&([A-Za-z0-9+,]*)-", _dec, s)


def _entete(msg, nom: str) -> str:
    """En-tete decode. msg est lu avec email.policy.default : elle decode les
    « =?utf-8?q?…?= » ET les accents bruts en UTF-8, que l'ancienne politique
    (compat32) rendait illisibles. Si l'en-tete est mal forme, decodage a
    l'ancienne sur la valeur brute."""
    try:
        val = msg.get(nom)
        # Un octet invalide peut laisser un « surrogate », que le JSON vers la page refuserait
        return str(val).encode("utf-8", "replace").decode("utf-8").strip() if val is not None else ""
    except Exception:
        brut = next((v for k, v in msg.raw_items() if k.lower() == nom.lower()), "")
        try:
            brut = str(make_header(decode_header(brut)))
        except Exception:
            pass
        return brut.encode("utf-8", "replace").decode("utf-8").strip()


def _libelles(meta: bytes) -> list:
    m = _RE_LABELS.search(meta)
    if not m:
        return []
    out = []
    for cite, atome in _RE_ATOME.findall(m.group(1)):
        brut = cite.replace(b'\\"', b'"').replace(b"\\\\", b"\\") if cite else atome
        nom = _utf7(brut.decode("ascii", "replace"))
        # Libelles systeme : \Inbox, \Important, \Starred…
        if nom and not nom.startswith("\\"):
            out.append(nom)
    return out


def _analyser_fetch(data: list) -> list:
    """Reponse brute d'imaplib -> un dict par mail.
    Un mail arrive en (debut de reponse + litteral, entetes) puis en octets
    pour la suite de la reponse : on les recolle avant de chercher les champs.
    Un octet qui commence par « N ( » est une autre reponse (mise a jour de
    drapeaux envoyee d'office par le serveur), pas une suite."""
    blocs = []
    for part in data or []:
        if isinstance(part, tuple) and len(part) == 2:
            blocs.append([part[0], part[1]])
        elif isinstance(part, bytes) and blocs and not _RE_REPONSE.match(part):
            blocs[-1][0] += part

    mails = []
    for meta, entetes in blocs:
        m_uid = _RE_UID.search(meta)
        if not m_uid:
            continue
        msg = email.message_from_bytes(entetes or b"", policy=email.policy.default)
        nom, adr = email.utils.parseaddr(_entete(msg, "From"))
        tt = imaplib.Internaldate2tuple(meta)
        if tt:
            date = time.strftime("%Y-%m-%dT%H:%M:%S", tt)
        else:
            try:
                date = email.utils.parsedate_to_datetime(_entete(msg, "Date")) \
                    .astimezone().strftime("%Y-%m-%dT%H:%M:%S")
            except Exception:
                date = ""
        m_flags = _RE_FLAGS.search(meta)
        m_fil   = _RE_THRID.search(meta)
        mails.append({
            "uid":      int(m_uid.group(1)),
            "de":       nom or adr or "(expéditeur inconnu)",
            "adresseDe": adr,
            "objet":    _entete(msg, "Subject") or "(sans objet)",
            "date":     date,
            "lu":       bool(m_flags and b"\\Seen" in m_flags.group(1)),
            "libelles": _libelles(meta),
            # Identifiant du fil en hexadecimal : c'est celui des liens Gmail
            "fil":      format(int(m_fil.group(1)), "x") if m_fil else "",
        })
    return mails


def lister(limite: int = NB_MAILS) -> dict:
    """Les `limite` derniers mails de la boite de reception, du plus recent au plus ancien."""
    def _lire(M):
        typ, data = M.uid("SEARCH", None, "ALL")
        if typ != "OK":
            raise ErreurActus("imap", "Gmail n'a pas donné la liste des mails.")
        uids = sorted((data[0] or b"").split(), key=int)[-limite:]
        if not uids:
            return []
        typ, data = M.uid("FETCH", b",".join(uids).decode("ascii"),
                          "(UID FLAGS X-GM-LABELS X-GM-THRID INTERNALDATE "
                          "BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
        if typ != "OK":
            raise ErreurActus("imap", "Gmail n'a pas donné la liste des mails.")
        return _analyser_fetch(data)

    mails = _avec_imap(_lire)
    mails.sort(key=lambda m: (m["date"], m["uid"]), reverse=True)
    libelles = sorted({l for m in mails for l in m["libelles"]}, key=str.casefold)
    return {"mails": mails, "libelles": libelles,
            "nonLus": sum(1 for m in mails if not m["lu"])}


def ouvrir(uid) -> str:
    """Le mail en page HTML autonome. L'ouvrir le marque comme lu, comme Gmail."""
    uid = str(int(uid))

    def _lire(M):
        typ, data = M.uid("FETCH", uid, "(BODY.PEEK[])")
        brut = next((p[1] for p in (data or []) if isinstance(p, tuple)), None)
        if typ != "OK" or brut is None:
            raise ErreurActus("absent", "Ce mail n'est plus dans la boîte de réception.")
        M.uid("STORE", uid, "+FLAGS", "(\\Seen)")
        return brut

    brut = _avec_imap(_lire)
    return page_html(email.message_from_bytes(brut, policy=email.policy.default))


def marquer(uid, lu: bool) -> None:
    uid = str(int(uid))

    def _ecrire(M):
        typ, _ = M.uid("STORE", uid, "+FLAGS" if lu else "-FLAGS", "(\\Seen)")
        if typ != "OK":
            raise ErreurActus("imap", "Gmail n'a pas pris le changement.")

    _avec_imap(_ecrire)


# ─── Mise en page d'un mail ──────────────────────────────────────────────────
#
# La page part telle quelle dans une iframe isolee (voir server.publier_mail) :
# aucun script ne s'y execute et elle ne peut rien lire de Pilote. On ajoute
# seulement de quoi l'afficher proprement :
#   * fond blanc : un mail sans fond serait du texte sombre sur le thème sombre ;
#   * <base target="_blank"> : un lien s'ouvre dans le navigateur, pas dans le cadre ;
#   * pas de Referer vers les sites des liens et des images.

_TETE = ('<!doctype html><meta charset="utf-8">'
         '<meta name="referrer" content="no-referrer"><base target="_blank">'
         '<style>html{background:#fff;color:#202124;'
         'font:14px/1.5 "Segoe UI",system-ui,Arial,sans-serif}</style>')

_RE_REFRESH = re.compile(r"<meta[^>]+http-equiv\s*=\s*[\"']?refresh[^>]*>", re.I)
_RE_URL     = re.compile(r"(https?://[^\s<>\"']+)")


def _texte(partie) -> str:
    try:
        return partie.get_content()
    except Exception:
        brut = partie.get_payload(decode=True) or b""
        return brut.decode(partie.get_content_charset() or "utf-8", "replace")


def _images_jointes(msg) -> dict:
    """cid -> data URI, pour les images glissees dans le corps du mail."""
    out = {}
    for p in msg.walk():
        cid = (p.get("Content-ID") or "").strip().strip("<>")
        if not cid or p.get_content_maintype() != "image":
            continue
        brut = p.get_payload(decode=True)
        if brut:
            out[cid] = "data:%s;base64,%s" % (p.get_content_type(),
                                              base64.b64encode(brut).decode("ascii"))
    return out


def page_html(msg) -> str:
    try:
        partie = msg.get_body(preferencelist=("html", "plain"))
    except Exception:
        partie = None
    if partie is None:
        return _TETE + "<p>(Ce mail n'a pas de texte.)</p>"
    if partie.get_content_type() == "text/html":
        corps = _RE_REFRESH.sub("", _texte(partie))
        for cid, uri in _images_jointes(msg).items():
            corps = re.sub(r"cid:" + re.escape(cid), lambda _m, u=uri: u, corps, flags=re.I)
        return _TETE + corps
    texte = html.escape(_texte(partie))
    texte = _RE_URL.sub(r'<a href="\1">\1</a>', texte)
    return (_TETE + '<div style="white-space:pre-wrap;overflow-wrap:anywhere;'
                    'max-width:760px;margin:8px auto">' + texte + "</div>")
