"""
app.py — Point d'entree de Pilote.

Lance :
  - le serveur Yahoo Finance en arriere-plan (server.py)
  - une fenetre native (pywebview) qui charge l'UI HTML
  - un bridge Python <-> JavaScript pour les acces stockage / cours / notifs

Tout s'arrete proprement quand la fenetre se ferme.
Une seule instance autorisee : si l'app est deja lancee, on ramene la fenetre
existante au premier plan et on quitte.
"""
from __future__ import annotations

import os
import sys
import json
import socket
import tempfile
import threading
import traceback
from pathlib import Path
from typing import Optional
import time as _time_lancement

# Instant du lancement, avant les imports lourds (pywebview, modules) : base
# des reperes du diagnostic de demarrage (PILOTE_DIAG, voir _repere)
_T0 = _time_lancement.time()


# Diagnostic (PILOTE_DIAG, tests des builds) dans l'exe Windows, qui n'a pas de
# console (sys.stdout vaut None) : la sortie va dans pilote_diag.log, dossier courant
if os.environ.get("PILOTE_DIAG") and sys.stdout is None:
    sys.stdout = sys.stderr = open("pilote_diag.log", "a", encoding="utf-8", buffering=1)


def _repere(etape: str) -> None:
    """Diagnostic du demarrage (PILOTE_DIAG seulement) : secondes depuis le lancement."""
    if os.environ.get("PILOTE_DIAG"):
        print(f"[t] {_time_lancement.time() - _T0:6.2f} s  {etape}", flush=True)

# Charge le codec idna AVANT que main() ne lance ses fils. Sinon, dans l'exe
# compile, le serveur local (getfqdn) et la verification de mise a jour
# (HTTPS) le chargent en meme temps au demarrage, et l'un des deux recoit
# « LookupError: unknown encoding: idna » : l'app plante avant de s'ouvrir.
# Mesure sur des builds de test : 5 lancements sur 20 sans cette ligne,
# 0 sur 10 avec. Ne pas retirer.
import encodings.idna  # noqa: F401

# Mac : certificats HTTPS avant tout contexte TLS (server en cree un a l'import)
import plateforme
plateforme.certificats_mac()

import webview                        # pywebview

import server
import storage
import finances
import sports
import pret
import cto
import releves
import patrimoine
import sante
import actus
import expositions
import sauvegarde
import notifications
import splash


APP_NAME    = "Pilote"
APP_VERSION = "4.4.20"
SINGLE_INSTANCE_PORT = 50317          # port arbitraire pour le verrou single-instance
WINDOW_DEFAULT_SIZE  = (1280, 800)
WINDOW_MIN_SIZE      = (960, 640)


# ─── Single instance ──────────────────────────────────────────────────────────

_lock_socket = None  # type: Optional[socket.socket]


def acquire_single_instance_lock() -> bool:
    """
    Tente de binder un port localhost. Si reussi -> on est la seule instance.
    Si echoue -> une autre instance tourne deja, on lui dit de remonter au front.
    """
    global _lock_socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", SINGLE_INSTANCE_PORT))
        s.listen(5)
        _lock_socket = s
        # Thread d'ecoute : si une 2eme instance se connecte -> on remonte au front
        threading.Thread(target=_listen_for_focus_pings, args=(s,), daemon=True).start()
        return True
    except OSError:
        # Deja en cours -> on ping pour faire remonter la fenetre existante.
        # Windows ne laisse passer au premier plan que le processus lance par
        # l'utilisateur, c'est-a-dire celui-ci : il cede ce droit a l'autre.
        try:
            import ctypes
            ctypes.windll.user32.AllowSetForegroundWindow(-1)   # ASFW_ANY
        except Exception:
            pass
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as c:
                c.settimeout(2)
                c.connect(("127.0.0.1", SINGLE_INSTANCE_PORT))
                c.sendall(b"focus")
        except Exception:
            pass
        return False


def _listen_for_focus_pings(server_sock: socket.socket) -> None:
    while True:
        try:
            conn, _ = server_sock.accept()
            try:
                conn.recv(64)
            except Exception:
                pass
            conn.close()
            # Encore en chargement : l'ecran de chargement est deja la, et la
            # fenetre s'ouvrira d'elle-meme une fois prete
            if not _revealed:
                continue
            # Ramene la fenetre principale au premier plan
            try:
                w = webview.windows[0] if webview.windows else None
                if w is not None:
                    w.restore()
                    w.show()
                    # Force le focus (Windows). Jusqu'a la 4.3.13, on passait
                    # la fenetre DEJA au premier plan : l'appel ne faisait rien.
                    try:
                        import ctypes
                        hwnd = _hwnd_principale()
                        if hwnd:
                            ctypes.windll.user32.SetForegroundWindow(hwnd)
                    except Exception:
                        pass
            except Exception:
                pass
        except Exception:
            return


def _hwnd_principale() -> int:
    """
    HWND de la fenetre principale de Pilote (0 si introuvable).

    Pas GetForegroundWindow() : la fenetre au premier plan n'est pas forcement
    la notre (fermeture depuis la barre des taches, clic ailleurs pendant
    l'agrandissement) ; la remise au premier plan, elle, visait la fenetre qui
    y etait deja et ne faisait donc rien (essaye le 01/10/2026).
    appicon._main_hwnd() cherche la fenetre de CE processus.
    """
    try:
        import appicon
        return appicon._main_hwnd() or 0
    except Exception:
        return 0


# ─── Bridge JS <-> Python ─────────────────────────────────────────────────────

def _dialogue(genre: str):
    """Type de boite de dialogue : webview.FileDialog.OPEN/FOLDER/SAVE depuis
    pywebview 5, les anciennes constantes OPEN_DIALOG... avant (4.4.1 sous
    Windows) ; elles sont depreciees en 6.2.1 sur Mac (ENV-15)."""
    import webview
    fd = getattr(webview, "FileDialog", None)
    return getattr(fd, genre) if fd is not None else getattr(webview, genre + "_DIALOG")


class Api:
    """
    Methodes appelees depuis JavaScript via window.pywebview.api.<methode>(...)
    Toutes retournent des objets JSON-serialisables.
    """

    def __init__(self):
        self._notif_prefs = {}

    # -- Stockage ----------------------------------------------------------

    def load_data(self) -> dict:
        try:
            data = storage.load_data()
            self._notif_prefs = data.get("notifs", {})
            # Hydrate le serveur avec le cache disque -> mode hors-ligne
            cache = data.get("_cache", {})
            server.hydrate_cache(cache.get("prices", {}), cache.get("history", {}))
            # loadError : la page n'ecrit pas apres une lecture ratee (regle n. 3),
            # meme quand elle passe par ce repli au lieu de /data (DAT-15)
            return {"ok": True, "data": data, "loadError": storage.get_last_load_info().get("error")}
        except Exception as e:
            return {"ok": False, "error": str(e), "trace": traceback.format_exc()}

    def save_data(self, data: dict) -> dict:
        try:
            # Met a jour le cache cours avant ecriture, pour le mode hors-ligne
            data.setdefault("_cache", {})
            cache = server.dump_cache()
            data["_cache"]["prices"]  = cache["prices"]  or data["_cache"].get("prices",  {})
            data["_cache"]["history"] = cache["history"] or data["_cache"].get("history", {})
            storage.save_data(data)
            self._notif_prefs = data.get("notifs", {})
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def save_ui_prefs(self, prefs: dict) -> dict:
        """
        Methode dediee : ecrit UNIQUEMENT uiPrefs dans le fichier sans toucher
        au reste. Utilisee pour le PIN, l'accent, etc. Elle relit puis
        reecrit tout le fichier : jamais apres une lecture ratee, sinon un
        pea_data.json illisible serait remplace par un backup ou un PEA vide.
        """
        try:
            # Lecture et ecriture sous le verrou du fichier : une transaction
            # enregistree entre les deux etait perdue (DAT-11)
            with storage.verrou(storage.get_data_path()):
                d = storage.load_data()
                if storage.get_last_load_info().get("error"):
                    return {"ok": False, "error": "pea_data.json illisible : rien n'est ecrit"}
                d["uiPrefs"] = prefs or {}
                storage.save_data(d)
            return {"ok": True, "uiPrefs": d["uiPrefs"]}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # -- Finances perso (propre a l'utilisateur actif) --------------------

    def load_finances(self) -> dict:
        try:
            return {"ok": True, "data": finances.load_data()}
        except Exception as e:
            return {"ok": False, "error": str(e), "trace": traceback.format_exc()}

    def save_finances(self, data: dict) -> dict:
        try:
            finances.save_data(data or {})
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # -- Sports (propre a l'utilisateur actif) ----------------------------

    def load_sports(self) -> dict:
        try:
            return {"ok": True, "data": sports.load_data(),
                    "catalog": sports.SPORTS, "fieldCatalog": sports.FIELD_CATALOG}
        except Exception as e:
            return {"ok": False, "error": str(e), "trace": traceback.format_exc()}

    def save_sports(self, data: dict) -> dict:
        try:
            sports.save_data(data or {})
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # -- Pret etudiant (propre a l'utilisateur actif) ----------------------

    def load_pret(self) -> dict:
        try:
            return {"ok": True, "data": pret.load_data()}
        except Exception as e:
            return {"ok": False, "error": str(e), "trace": traceback.format_exc()}

    def save_pret(self, data: dict) -> dict:
        try:
            pret.save_data(data or {})
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # -- CTO (propre a l'utilisateur actif) --------------------------------

    def load_cto(self) -> dict:
        try:
            return {"ok": True, "data": cto.load_data()}
        except Exception as e:
            return {"ok": False, "error": str(e), "trace": traceback.format_exc()}

    def save_cto(self, data: dict, vide_voulu: bool = False) -> dict:
        try:
            cto.save_data(data or {}, bool(vide_voulu))
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def releves_lire(self, fichiers: list) -> dict:
        """Releves de banque ou de courtier (PDF, CSV, Excel, XML, en base64)
        -> operations a valider dans le PEA ou un CTO (rien n'est ecrit).
        Voir releves.py et docs/import-releves.md."""
        try:
            return releves.lire(fichiers or [])
        except Exception as e:
            return {"ok": False, "erreur": "Lecture impossible : " + str(e)}

    # -- Patrimoine (propre a l'utilisateur actif) -------------------------

    def load_patrimoine(self) -> dict:
        try:
            data = patrimoine.load_data()
            return {"ok": True, "data": data, "types": patrimoine.TYPES,
                    "moisCourant": patrimoine.mois_courant(),
                    "moisSaisi":   patrimoine.mois_saisi(data),
                    "net":         patrimoine.net_worth(data),
                    "serie":       patrimoine.serie_mensuelle(data)}
        except Exception as e:
            return {"ok": False, "error": str(e), "trace": traceback.format_exc()}

    def save_patrimoine(self, data: dict) -> dict:
        try:
            patrimoine.save_data(data or {})
            d = patrimoine.load_data()
            return {"ok": True, "net": patrimoine.net_worth(d),
                    "serie": patrimoine.serie_mensuelle(d),
                    "moisSaisi": patrimoine.mois_saisi(d)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # -- Sante (propre a l'utilisateur actif) ------------------------------

    def load_sante(self) -> dict:
        try:
            return {"ok": True, "data": sante.load_data(),
                    "metrics": sante.METRICS}
        except Exception as e:
            return {"ok": False, "error": str(e), "trace": traceback.format_exc()}

    def save_sante(self, data: dict) -> dict:
        try:
            sante.save_data(data or {})
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def sante_ocr_available(self) -> dict:
        try:
            return sante.ocr_available()
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def sante_pick_screenshots(self) -> dict:
        """Selecteur de captures FitDays (plusieurs a la fois, ou un .zip)."""
        try:
            win = webview.windows[0]
            result = win.create_file_dialog(
                _dialogue("OPEN"),
                allow_multiple=True,
                file_types=("Captures ou zip (*.png;*.jpg;*.jpeg;*.heic;*.webp;*.zip)",
                            "All files (*.*)"),
            )
            if not result:
                return {"ok": False, "cancelled": True}
            paths = list(result) if isinstance(result, (list, tuple)) else [result]
            return {"ok": True, "paths": paths}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def sante_read_screenshots(self, paths: list) -> dict:
        """
        Lecture OCR des captures. Peut prendre plusieurs secondes : l'UI
        affiche un indicateur pendant ce temps.
        """
        try:
            return sante.read_screenshots(list(paths or []))
        except Exception as e:
            return {"ok": False, "error": str(e), "values": {},
                    "trace": traceback.format_exc()}

    # -- Sauvegarde externe (cle USB) --------------------------------------
    # Au niveau de l'installation, pas de l'utilisateur : une sauvegarde
    # embarque TOUT le dossier Donnees, tous les espaces confondus.

    def sauvegarde_status(self) -> dict:
        try:
            return sauvegarde.status()
        except Exception as e:
            return {"ok": False, "error": str(e), "trace": traceback.format_exc()}

    def sauvegarde_set_config(self, patch: dict) -> dict:
        """Met a jour les reglages (comportement et reglages de la cle), sans
        jamais toucher a la destination ni aux derniers resultats."""
        try:
            return sauvegarde.appliquer_reglages(patch)
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def sauvegarde_pick_folder(self) -> dict:
        """Ouvre le selecteur de dossier et retient la cle choisie."""
        try:
            win = webview.windows[0]
            result = win.create_file_dialog(_dialogue("FOLDER"))
            if not result:
                return {"ok": False, "cancelled": True}
            path = result[0] if isinstance(result, (list, tuple)) else result
            res = sauvegarde.set_destination(path)
            if not res.get("ok"):
                return res
            return sauvegarde.status()
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def sauvegarde_use_drive(self, root: str) -> dict:
        """Choisit une cle detectee, avec un sous-dossier dedie."""
        try:
            target = os.path.join(root, "Sauvegardes Pilote")
            res = sauvegarde.set_destination(target)
            if not res.get("ok"):
                return res
            return sauvegarde.status()
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def sauvegarde_push_usb(self, root: str = None) -> dict:
        """Miroir immediat du dossier Donnees sur la cle (bouton de l'accueil)."""
        try:
            return sauvegarde.push_to_usb(root)
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def sauvegarde_usb_state(self) -> dict:
        try:
            return sauvegarde.usb_state()
        except Exception as e:
            return {"ok": False, "error": str(e), "drives": [], "count": 0}

    def sauvegarde_run(self) -> dict:
        try:
            return sauvegarde.run_backup(reason="manuel")
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def sauvegarde_list(self) -> dict:
        try:
            return sauvegarde.list_backups()
        except Exception as e:
            return {"ok": False, "error": str(e), "backups": []}

    def sauvegarde_restore(self, path: str) -> dict:
        try:
            return sauvegarde.restore_from(path)
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def sauvegarde_open_folder(self) -> dict:
        try:
            dest = sauvegarde.resolve_destination()
            if not dest.get("ready"):
                return {"ok": False, "error": dest.get("message") or "Destination absente."}
            plateforme.ouvrir(dest["path"])
            return {"ok": True, "path": dest["path"]}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def open_data_folder(self) -> dict:
        """Ouvre le dossier de donnees de l'utilisateur actif."""
        try:
            path = str(storage.get_user_dir())
            plateforme.ouvrir(path)
            return {"ok": True, "path": path}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def data_folder_path(self) -> dict:
        """Chemin du dossier ouvert par open_data_folder, sans l'ouvrir : les
        Premiers pas et Parametres -> Donnees l'ecrivent en clair."""
        try:
            return {"ok": True, "path": str(storage.get_user_dir())}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # -- Cours / historique ------------------------------------------------

    # -- Actus : boite Gmail des newsletters (propre a l'utilisateur actif) --
    # Le mot de passe d'application entre par save_actus et ne ressort jamais.

    def load_actus(self) -> dict:
        try:
            return {"ok": True, **actus.config()}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def save_actus(self, adresse: str, mot_de_passe: str) -> dict:
        """Connecte la boite : rien n'est enregistre tant que Gmail n'a pas accepte."""
        try:
            return {"ok": True, **actus.connecter(adresse, mot_de_passe)}
        except actus.ErreurActus as e:
            return {"ok": False, "code": e.code, "error": e.message}
        except Exception as e:
            return {"ok": False, "code": "imap", "error": str(e)}

    def save_actus_deconnexion(self) -> dict:
        try:
            return {"ok": True, **actus.deconnecter()}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def actus_lister(self) -> dict:
        try:
            return {"ok": True, **actus.lister()}
        except actus.ErreurActus as e:
            return {"ok": False, "code": e.code, "error": e.message}
        except Exception as e:
            return {"ok": False, "code": "imap", "error": "Gmail a répondu : " + str(e),
                    "trace": traceback.format_exc()}

    def actus_ouvrir(self, uid) -> dict:
        """La page du mail est servie par le serveur local (iframe), sous ticket."""
        try:
            return {"ok": True, "ticket": server.publier_mail(actus.ouvrir(uid))}
        except actus.ErreurActus as e:
            return {"ok": False, "code": e.code, "error": e.message}
        except Exception as e:
            return {"ok": False, "code": "imap", "error": "Gmail a répondu : " + str(e),
                    "trace": traceback.format_exc()}

    def actus_marquer(self, uid, lu: bool) -> dict:
        try:
            actus.marquer(uid, bool(lu))
            return {"ok": True}
        except actus.ErreurActus as e:
            return {"ok": False, "code": e.code, "error": e.message}
        except Exception as e:
            return {"ok": False, "code": "imap", "error": "Gmail a répondu : " + str(e)}

    # -- Expositions : composition des ETF (donnees publiques, niveau installation)

    def load_expositions(self) -> dict:
        try:
            return {"ok": True, **expositions.charger()}
        except Exception as e:
            return {"ok": False, "error": str(e), "trace": traceback.format_exc()}

    def expositions_update(self) -> dict:
        """Bouton « Mettre a jour les donnees » : non bloquant, progression via
        expositions_status()."""
        try:
            return {"ok": True, "lance": expositions.lancer_mise_a_jour()}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def expositions_status(self) -> dict:
        try:
            return {"ok": True, **expositions.etat()}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def expositions_chercher(self, cle: str, isin: str = "") -> dict:
        """ETF que Pilote ne suit pas : cherche sa composition sur internet
        (quelques secondes, dans le thread de l'appel) et la garde."""
        try:
            return {"ok": True, "composition": expositions.chercher(cle, isin)}
        except expositions.Introuvable as e:
            return {"ok": False, "error": str(e), "isin": e.isin}
        except Exception as e:
            traceback.print_exc()
            return {"ok": False, "error": "recherche impossible : " + str(e)[:150]}

    # -- Export / import (boutons UI) -------------------------------------

    def export_dialog(self) -> dict:
        win = webview.windows[0]
        result = win.create_file_dialog(
            _dialogue("SAVE"),
            save_filename="pea_data.json",
            file_types=("JSON (*.json)",),
        )
        if not result:
            return {"ok": False, "cancelled": True}
        target = result if isinstance(result, str) else result[0]
        ok = storage.export_to(target)
        return {"ok": ok, "path": target}

    def import_dialog(self) -> dict:
        win = webview.windows[0]
        result = win.create_file_dialog(
            _dialogue("OPEN"),
            allow_multiple=False,
            file_types=("JSON (*.json)", "All files (*.*)"),
        )
        if not result:
            return {"ok": False, "cancelled": True}
        path = result[0] if isinstance(result, (list, tuple)) else result
        ok, msg = storage.import_from(path)
        return {"ok": ok, "message": msg}

    # -- Fenetre / divers --------------------------------------------------

    def app_ready(self) -> dict:
        """Appele par boot() (index.html) quand l'accueil est pret : ouvre
        la fenetre principale et ferme l'ecran de chargement."""
        _repere("page prete (app_ready)")
        reveal_main_window("page")
        return {"ok": True}

    def mac_emplacement(self) -> dict:
        """Mac : Pilote doit etre dans Applications pour se mettre a jour."""
        try:
            import updater
            return {"ok": True, "aDeplacer": updater.mac_a_deplacer()}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def ouvrir_rapport(self, html: str, nom: str = "Pilote_rapport") -> dict:
        """Mac : le rapport annuel s'ouvre dans le navigateur, qui sait l'imprimer
        (pywebview n'imprime pas l'iframe du rapport). Fichier du dossier
        temporaire de la session, lisible par ce seul compte."""
        try:
            import re as _re
            import tempfile
            nom = _re.sub(r"[^A-Za-z0-9_-]", "", str(nom))[:60] or "Pilote_rapport"
            chemin = Path(tempfile.gettempdir()) / f"{nom}.html"
            chemin.write_text(str(html), encoding="utf-8")
            plateforme.ouvrir(str(chemin))
            return {"ok": True, "path": str(chemin)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def fermeture_prete(self) -> dict:
        """Mac : la page a ecrit ce qui attendait, la fenetre peut se fermer
        (voir _on_closing dans main)."""
        if _fermeture_prete is not None:
            # Apres la reponse a la page, pas pendant : pywebview la renverrait a
            # une fenetre deja fermee, et ce fil du pont attendrait pour toujours
            # (vu le 12/10/2026 sur le test Mac : l'app ne quittait plus)
            t = threading.Timer(0.3, _fermeture_prete)
            t.daemon = True
            t.start()
        return {"ok": True}

    def minimize(self):
        try:
            webview.windows[0].minimize()
        except Exception:
            pass

    def maximize_toggle(self):
        """
        Maximisation 'a la Windows' (respecte la barre des taches), meme
        sur fenetre frameless et ecran HiDPI.
        On utilise SetWindowPos directement (pixels physiques, DPI-aware) plutot
        que pywebview.resize qui peut mal gerer le scaling.
        """
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            # Force la conscience DPI au niveau process (per-monitor v2)
            try:
                ctypes.windll.user32.SetProcessDpiAwarenessContext(-4)  # PER_MONITOR_AWARE_V2
            except Exception:
                try:
                    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
                except Exception:
                    pass

            hwnd = _hwnd_principale()
            if not hwnd:
                return

            # Si deja "maximise", on restaure
            if getattr(self, "_is_max", False):
                r = getattr(self, "_pre_max_rect", None)
                if r:
                    SWP_NOZORDER   = 0x0004
                    SWP_SHOWWINDOW = 0x0040
                    user32.SetWindowPos(
                        hwnd, 0,
                        int(r[0]), int(r[1]), int(r[2]), int(r[3]),
                        SWP_NOZORDER | SWP_SHOWWINDOW
                    )
                self._is_max = False
                return

            # Memorise la position/taille actuelle (pixels reels via GetWindowRect)
            class RECT(ctypes.Structure):
                _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG),
                            ("right", wintypes.LONG), ("bottom", wintypes.LONG)]
            cur = RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(cur))
            self._pre_max_rect = (
                cur.left, cur.top,
                cur.right - cur.left, cur.bottom - cur.top
            )

            # Trouve le moniteur et sa work area
            class MONITORINFO(ctypes.Structure):
                _fields_ = [
                    ("cbSize",    wintypes.DWORD),
                    ("rcMonitor", RECT),
                    ("rcWork",    RECT),
                    ("dwFlags",   wintypes.DWORD),
                ]

            MONITOR_DEFAULTTONEAREST = 2
            monitor = user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
            mi = MONITORINFO()
            mi.cbSize = ctypes.sizeof(MONITORINFO)
            user32.GetMonitorInfoW(monitor, ctypes.byref(mi))

            wa = mi.rcWork
            wa_l, wa_t = wa.left, wa.top
            wa_w, wa_h = wa.right - wa.left, wa.bottom - wa.top

            # SetWindowPos en pixels physiques (DPI-aware)
            SWP_NOZORDER   = 0x0004
            SWP_SHOWWINDOW = 0x0040
            user32.SetWindowPos(
                hwnd, 0,
                wa_l, wa_t, wa_w, wa_h,
                SWP_NOZORDER | SWP_SHOWWINDOW
            )

            self._is_max = True
        except Exception as e:
            print(f"[maximize_toggle] {e}", flush=True)

    def close(self):
        try:
            webview.windows[0].destroy()
        except Exception:
            pass

    def notify(self, title: str, msg: str, kind: str = "info") -> dict:
        notifications.notify(title, msg, kind, self._notif_prefs)
        return {"ok": True}

    # ─── Multi-utilisateurs ────────────────────────────────
    # Un utilisateur = un dossier complet (PEA + comptes + sport + pret).

    def get_users(self) -> dict:
        try:
            return {"ok": True, "state": server.with_pin_flags(storage.get_users_state())}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def add_user(self, label: str, emoji: str = "", color: str = "") -> dict:
        try:
            label = (label or "").strip() or "Nouvel utilisateur"
            state = storage.get_users_state()
            slug = storage.slugify(label, [u["slug"] for u in state["users"]])
            # Le dossier d'abord : s'il ne peut pas etre cree, l'utilisateur
            # n'est pas inscrit dans users.json (DAT-16)
            storage.get_user_dir(slug)
            state["users"].append({"slug": slug, "label": label,
                                   "emoji": (emoji or "").strip(),
                                   "color": (color or "").strip()})
            storage.save_users_state(state)
            return {"ok": True, "slug": slug, "state": state}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def update_user(self, slug: str, label: str = None,
                    emoji: str = None, color: str = None) -> dict:
        try:
            state = storage.get_users_state()
            for u in state["users"]:
                if u["slug"] == slug:
                    if label is not None and label.strip():
                        u["label"] = label.strip()
                    if emoji is not None:
                        u["emoji"] = emoji.strip()
                    if color is not None:
                        u["color"] = color.strip()
                    storage.save_users_state(state)
                    return {"ok": True, "state": state}
            return {"ok": False, "error": "utilisateur introuvable"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def delete_user(self, slug: str) -> dict:
        """Retire l'utilisateur de la liste. Son dossier reste sur le disque."""
        try:
            state = storage.get_users_state()
            if len(state["users"]) <= 1:
                return {"ok": False, "error": "Impossible de supprimer le dernier utilisateur"}
            state["users"] = [u for u in state["users"] if u["slug"] != slug]
            if state["active"] == slug:
                state["active"] = state["users"][0]["slug"]
            storage.save_users_state(state)
            return {"ok": True, "active": state["active"], "state": state,
                    "folder": str(storage.get_app_dir() / storage.USERS_DIRNAME / slug)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def set_active_user(self, slug: str) -> dict:
        try:
            state = storage.get_users_state()
            if not any(u["slug"] == slug for u in state["users"]):
                return {"ok": False, "error": "utilisateur inconnu"}
            state["active"] = slug
            storage.save_users_state(state)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ─── Icone de l'app a la couleur du theme ──────────────────────

    def set_app_icon_color(self, color: str) -> dict:
        """Recolore l'icone de la fenetre + barre des taches (effet immediat)."""
        try:
            import appicon
            return {"ok": appicon.apply_to_window(color)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def apply_icon_to_shortcuts(self, color: str) -> dict:
        """Repointe aussi les raccourcis Bureau / Demarrer / barre des taches."""
        try:
            import appicon
            return appicon.apply_to_shortcuts(color)
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def check_update(self) -> dict:
        try:
            import updater
            return {"ok": True, **updater.get_result()}
        except Exception as e:
            return {"ok": False, "error": str(e), "checked": True, "hasUpdate": False}

    def recheck_update(self) -> dict:
        """Relance une verification de mise a jour (utilise par le bouton manuel)."""
        try:
            import updater
            updater.start_check(APP_VERSION)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def nouveautes(self) -> dict:
        """Fiches des versions livrees avec l'app (src/nouveautes.json)."""
        try:
            import updater
            return {"ok": True, "version": APP_VERSION, "versions": updater.historique()}
        except Exception as e:
            return {"ok": False, "error": str(e), "version": APP_VERSION, "versions": []}

    def start_update(self) -> dict:
        try:
            import updater
            updater.start_install_async()   # non-bloquant, progression via get_install_progress()
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def get_install_progress(self) -> dict:
        try:
            import updater
            return {"ok": True, **updater.get_progress()}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def open_url(self, url: str) -> dict:
        try:
            # Seulement des adresses web ou mail : sous Windows, webbrowser.open
            # passe par os.startfile, qui lancerait aussi un programme ou un
            # chemin reseau (audit du 20/10/2026, SEC-02)
            import urllib.parse
            if urllib.parse.urlparse(str(url)).scheme.lower() not in ("http", "https", "mailto"):
                return {"ok": False, "error": "Adresse refusee"}
            import webbrowser
            webbrowser.open(url)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def app_info(self) -> dict:
        try:
            active = storage.get_active_user()
        except Exception:
            active = {}
        return {
            "appName":  APP_NAME,
            "version":  APP_VERSION,
            "user":     active,
            "appDir":   str(storage.get_app_dir()),
            "dataPath": str(storage.get_data_path()),
            "logPath":  str(storage.get_log_path()),
            "port":     server.get_port(),
            "notifAvailable": notifications.is_available(),
        }


# ─── Localisation des assets (fonctionne dev + PyInstaller) ───────────────────

def resource_path(rel: str) -> str:
    """
    Sert pour PyInstaller : en mode 'frozen', les fichiers sont extraits dans
    sys._MEIPASS. En dev, on prend le dossier du fichier app.py.
    """
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return str(Path(base) / rel)
    return str(Path(__file__).resolve().parent / rel)


# ─── Crash log silencieux ─────────────────────────────────────────────────────

CRASH_LOG_MAX = 256 * 1024   # 256 Ko


def _rotate_crash_log() -> None:
    """
    Un crash.log qui grossit sans fin finit par peser plus lourd que les
    donnees elles-memes et par partir dans chaque sauvegarde USB. On garde la
    generation precedente sous crash.log.1 et on repart a zero au-dela de
    CRASH_LOG_MAX.
    """
    try:
        path = storage.get_log_path()
        if path.exists() and path.stat().st_size > CRASH_LOG_MAX:
            prev = path.with_name(path.name + ".1")
            try:
                if prev.exists():
                    prev.unlink()
            except Exception:
                pass
            path.replace(prev)
    except Exception:
        pass



def install_crash_handler() -> None:
    """
    Installe un crash handler silencieux qui n'ecrit que les VRAIS crashes.
    Filtre les erreurs benignes connues (ex: bug WPARAM de win10toast).
    """
    # « Main window failed to load » : pywebview le leve quand la page met trop
    # de temps au tout premier lancement apres un demarrage du PC (cache disque
    # froid) ; la fenetre s'ouvre ensuite normalement (ENV-11, docs/demarrage-et-icone.md)
    BENIGN = ("WPARAM is simple", "win10toast", "Main window failed to load")

    def _is_benign(exc) -> bool:
        try:
            return any(b in str(exc) for b in BENIGN)
        except Exception:
            return False

    def _is_closed_window(exc_type, tb) -> bool:
        """
        pywebview renvoie le resultat de chaque appel JS -> Python a la page
        qui l'a lance. Quand cet appel est Api.close() (la croix de la barre
        de titre), la fenetre n'existe deja plus : KeyError: 'master' dans
        evaluate_js, une fois par fermeture (286 entrees sur 288 du crash.log
        au 30/09/2026). Rien n'est perdu, la fonction appelee a fini avant.
        Differer la fermeture serait risque : evaluate_js attend la reponse
        de la page, et si la fenetre fermait entre-temps, ce fil (non daemon)
        pourrait attendre pour toujours et empecher l'app de se terminer
        (d'apres le code de pywebview 4.4.1, pas essaye).
        """
        try:
            if not issubclass(exc_type, KeyError):
                return False
            import traceback as _tb
            last = _tb.extract_tb(tb)[-1]
            return last.name == "evaluate_js" and "webview" in last.filename
        except Exception:
            return False

    def _hook(exc_type, exc, tb):
        if _is_benign(exc) or _is_closed_window(exc_type, tb):
            return  # ignore silencieusement les bugs connus de libs tierces
        try:
            _rotate_crash_log()
            with open(storage.get_log_path(), "a", encoding="utf-8") as f:
                f.write("\n=== CRASH ===\n")
                import datetime as _dt
                f.write(_dt.datetime.now().isoformat() + "\n")
                import traceback as _tb
                _tb.print_exception(exc_type, exc, tb, file=f)
        except Exception:
            pass
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = _hook

    # Filtre aussi les exceptions levees dans des threads (toast tourne dans un thread)
    try:
        def _thread_hook(args):
            if _is_benign(args.exc_value):
                return
            sys.excepthook(args.exc_type, args.exc_value, args.exc_traceback)
        threading.excepthook = _thread_hook
    except Exception:
        pass


# ─── Ouverture differee de la fenetre ─────────────────────────────────────────
# La fenetre principale nait cachee, derriere l'ecran de chargement
# (splash.py), et ne s'ouvre qu'une fois l'accueil pret, sur signal de boot()
# (Api.app_ready). Filet de securite : elle s'ouvre de toute facon au bout de
# REVEAL_TIMEOUT secondes, pour qu'un JS en panne ne laisse jamais l'app
# invisible.

REVEAL_TIMEOUT = 20

_main_window = None
_splash_window = None
_revealed = False
_reveal_lock = threading.Lock()
_fermeture_prete = None     # Mac : ferme pour de bon une fois la page videe (main)


def _paint_accent_icon() -> None:
    """Icone recoloree selon l'accent choisi, sur la fenetre visible."""
    try:
        import appicon
        accent = (storage.load_data().get("uiPrefs") or {}).get("accent")
        appicon.apply_to_window(accent or appicon.DEFAULT_COLOR)
    except Exception as e:
        print(f"[app] icone accent KO : {e}", flush=True)


def reveal_main_window(origine: str = "delai") -> None:
    """origine : "page" quand boot() a fini, "delai" pour le filet de securite.
    Ecrit dans la sortie : le test du build Mac (build-mac.yml) la lit pour
    savoir si l'interface a vraiment demarre."""
    global _revealed
    with _reveal_lock:
        if _revealed or _main_window is None:
            return
        _revealed = True
    print(f"[app] fenetre ouverte ({origine})", flush=True)
    _repere("fenetre ouverte")
    try:
        _main_window.show()
    except Exception as e:
        print(f"[app] ouverture fenetre KO : {e}", flush=True)
    if _splash_window is not None:
        try:
            _splash_window.destroy()
        except Exception:
            pass
    # L'ecran de chargement ferme, la vraie fenetre est la seule visible
    _paint_accent_icon()


# ─── Cycle de vie ─────────────────────────────────────────────────────────────


def _menage_webview_temp() -> None:
    """Efface, en arriere-plan, les dossiers WebView2 laisses dans %TEMP% par
    les versions d'avant la 4.4.21 : un dossier tmp* qui ne contient que
    EBWebView et n'a pas bouge depuis 2 jours."""
    def menage():
        import shutil, time as _t
        racine = tempfile.gettempdir()
        try:
            for nom in os.listdir(racine):
                d = os.path.join(racine, nom)
                try:
                    if (nom.startswith("tmp") and os.path.isdir(d)
                            and os.listdir(d) == ["EBWebView"]
                            and _t.time() - os.path.getmtime(d) > 2 * 86400):
                        shutil.rmtree(d, ignore_errors=True)
                except Exception:
                    continue
        except Exception:
            pass
    threading.Thread(target=menage, daemon=True).start()


def main() -> int:
    _repere("imports termines")
    install_crash_handler()

    # Single instance : si une autre tourne, on quitte (elle a deja remonte au
    # front). En tete de main depuis la 4.4.21 : un double-clic lancait sinon
    # la migration du PIN et une seconde archive USB, tuee en route (DAT-17)
    if not acquire_single_instance_lock():
        print("[app] Une autre instance tourne deja. Sortie.", flush=True)
        return 0

    # Le PIN, global jusqu'a la v4.1.3, devient propre a chaque utilisateur
    try:
        storage.migrate_legacy_pin()
    except Exception as e:
        print(f"[app] migration PIN KO : {e}", flush=True)

    # Lance la verification de mise a jour en arriere-plan (silencieux)
    try:
        import updater
        updater.start_check(APP_VERSION)
    except Exception:
        pass

    # Sauvegarde externe automatique, en arriere-plan et sans rien bloquer :
    # si la cle USB n'est pas branchee, on note le statut et on n'insiste pas.
    # Reglage « moment », relu a chaque tour (un changement vaut tout de suite) :
    # au demarrage (une fois), des que la cle est branchee (toutes les 20 s tant
    # que Pilote est ouvert) ou a la fermeture (fin de main).
    def _sauvegarde_auto_une() -> dict:
        try:
            res = sauvegarde.auto_backup_if_due()
            if res.get("ok"):
                print(f"[app] sauvegarde externe : {res.get('path')}", flush=True)
            return res
        except Exception as e:
            print(f"[app] sauvegarde auto KO : {e}", flush=True)
            return {"ok": False, "reason": "error"}

    def _auto_sauvegarde():
        premier = True
        while True:
            try:
                moment = sauvegarde.load_config().get("moment") or "demarrage"
            except Exception:
                moment = "demarrage"
            attente = 20
            if moment == "branchement" or (premier and moment == "demarrage"):
                # Ecriture ratee (cle pleine, protegee) : pas un essai toutes les 20 s
                if _sauvegarde_auto_une().get("reason") == "error":
                    attente = 600
            premier = False
            _time_lancement.sleep(attente)

    try:
        threading.Thread(target=_auto_sauvegarde, daemon=True).start()
    except Exception:
        pass

    # Active la conscience DPI au plus tot (avant de creer la fenetre).
    # Ca evite les soucis de tailles sur ecran HiDPI (laptops 4K, etc.).
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.user32.SetProcessDpiAwarenessContext(-4)  # PER_MONITOR_AWARE_V2
        except Exception:
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PER_MONITOR
            except Exception:
                try:
                    ctypes.windll.user32.SetProcessDPIAware()  # legacy
                except Exception:
                    pass

    # Charge les preferences UI pour decider taille/position fenetre
    data = storage.load_data()
    ui_prefs = data.get("ui", {})
    saved_size      = ui_prefs.get("windowSize")
    saved_maximized = ui_prefs.get("windowMaximized", True)   # True = defaut = plein ecran
    pos             = ui_prefs.get("windowPos")  # [x, y] ou None

    # Recupere la work area du moniteur principal (ecran moins barre des taches)
    screen_w, screen_h = 1280, 720  # fallback
    zone_mac = None                 # Mac : (x, y, largeur, hauteur) sans menus ni Dock
    try:
        if sys.platform == "darwin":
            zone_mac = plateforme.zone_ecran_mac()
            screen_w, screen_h = zone_mac[2], zone_mac[3]
        elif sys.platform == "win32":
            import ctypes
            user32 = ctypes.windll.user32
            class _RECT(ctypes.Structure):
                _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                            ("right", ctypes.c_long), ("bottom", ctypes.c_long)]
            wa = _RECT()
            if user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(wa), 0):
                screen_w = wa.right - wa.left
                screen_h = wa.bottom - wa.top
    except Exception:
        pass

    # Strategie d'ouverture :
    # - windowMaximized == True (defaut 1er lancement) → plein ecran work-area exacte
    # - Sinon → taille sauvegardee (clampee)
    if saved_maximized or not (saved_size and isinstance(saved_size, (list, tuple)) and len(saved_size) == 2):
        w_, h_ = screen_w, screen_h
        pos = None  # pas de position sauvegardee en mode plein ecran
        if zone_mac:
            pos = list(zone_mac[:2])    # Mac : coin haut gauche, sous la barre des menus
    else:
        try:
            w_, h_ = int(saved_size[0]), int(saved_size[1])
            if not (200 <= w_ <= 8000 and 200 <= h_ <= 8000):
                w_, h_ = screen_w, screen_h
        except Exception:
            w_, h_ = screen_w, screen_h
        # Clamp final
        w_ = min(w_, max(960, screen_w))
        h_ = min(h_, max(640, screen_h))
        # Validation position
        if pos and isinstance(pos, (list, tuple)) and len(pos) == 2:
            try:
                x_, y_ = int(pos[0]), int(pos[1])
                if not (-16000 < x_ < 16000 and -16000 < y_ < 16000):
                    pos = None
                elif x_ + w_ < 100 or y_ < -10 or x_ > screen_w - 100 or y_ > screen_h - 50:
                    pos = None   # au moins 100 px visibles, barre de titre comprise
                elif sys.platform == "win32":
                    # Le haut de la fenetre doit tomber sur un ecran branche : un
                    # second ecran retire laissait Pilote s'ouvrir hors de vue (ENV-02)
                    import ctypes
                    from ctypes import wintypes
                    _MFP = ctypes.windll.user32.MonitorFromPoint
                    _MFP.restype = wintypes.HMONITOR
                    _MFP.argtypes = [wintypes.POINT, wintypes.DWORD]
                    if not _MFP(wintypes.POINT(x_ + 100, y_ + 10), 0):   # 0 : MONITOR_DEFAULTTONULL
                        pos = None
            except Exception:
                pos = None
        else:
            pos = None

    size = (w_, h_)

    api = Api()
    html_path = resource_path(os.path.join("ui", "index.html"))

    # Demarre le serveur Yahoo + sert le HTML
    port = server.start_server(html_path=html_path)

    # Attend que le serveur reponde vraiment avant d'ouvrir la fenetre
    import time as _time
    for _ in range(40):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as _probe:
                _probe.settimeout(0.2)
                if _probe.connect_ex(("127.0.0.1", port)) == 0:
                    break
        except Exception:
            pass
        _time.sleep(0.05)

    _repere("serveur local pret")

    # L'UI est servie par le serveur local : pas de file://, pas de query string,
    # le port se lit naturellement via location.port.
    url = f"http://127.0.0.1:{port}/"

    # Cachee, une fenetre WebView2 voit ses minuteurs JS freines a un par
    # seconde (mesure : 20 setTimeout de 10 ms en 2,8 s au lieu de 0,3 s). Or
    # c'est cachee qu'elle charge, derriere l'ecran de chargement : ces options
    # levent le frein. ElasticOverscroll reprend l'option que pywebview passe
    # lui-meme, au cas ou la variable la remplacerait.
    os.environ.setdefault(
        "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS",
        "--disable-features=ElasticOverscroll --disable-background-timer-throttling"
        " --disable-renderer-backgrounding --disable-backgrounding-occluded-windows")

    window_kwargs = dict(
        title=APP_NAME,
        url=url,
        js_api=api,
        width=size[0],
        height=size[1],
        min_size=WINDOW_MIN_SIZE,
        resizable=True,
        text_select=True,
        confirm_close=False,
        # Windows : titlebar custom dans l'UI. Mac : celle du systeme (boutons a
        # gauche, deplacement, plein ecran), l'UI cache la sienne (html.os-mac)
        frameless=sys.platform != "darwin",
        easy_drag=False,        # le drag est gere via -webkit-app-region: drag
        hidden=True,            # ouverte par reveal_main_window() une fois prete
    )
    if pos and isinstance(pos, (list, tuple)) and len(pos) == 2:
        window_kwargs["x"] = int(pos[0])
        window_kwargs["y"] = int(pos[1])

    # Creee la premiere : webview.windows[0] reste la fenetre principale
    window = webview.create_window(**window_kwargs)
    # Mac : le pont JS <-> Python ne doit pas evaluer de texte, la CSP de la
    # page l'interdit (voir plateforme.adapter_pont_mac)
    if sys.platform == "darwin":
        plateforme.adapter_pont_mac(window)

    global _main_window, _splash_window
    _main_window = window
    try:
        prefs = data.get("uiPrefs") or {}
        theme = "dark" if prefs.get("theme") == "dark" else "light"
        _splash_window = webview.create_window(
            APP_NAME,
            html=splash.build_html(os.path.dirname(html_path), prefs.get("accent"), theme),
            width=splash.SIZE[0], height=splash.SIZE[1],
            resizable=False, frameless=True,
            background_color=splash.background(theme),
        )
        _splash_window.events.shown += _paint_accent_icon

        def _arrondir_splash():
            # A cet instant la fenetre principale est encore cachee : la seule
            # fenetre visible de Pilote est l'ecran de chargement
            splash.arrondir_coins(_hwnd_principale(), theme)
        _splash_window.events.shown += _arrondir_splash
    except Exception as e:
        print(f"[app] ecran de chargement KO : {e}", flush=True)
        _splash_window = None

    _reveal_timer = threading.Timer(REVEAL_TIMEOUT, reveal_main_window)
    _reveal_timer.daemon = True
    _reveal_timer.start()

    # Test du build Mac, mise a jour (build-mac.yml, PILOTE_MAJ_ESSAI) : la
    # fausse release est trouvee au demarrage ; on clique « Installer » a la
    # place de l'utilisateur, l'app doit se remplacer et se relancer seule.
    if os.environ.get("PILOTE_DIAG") and os.environ.get("PILOTE_MAJ_ESSAI"):
        def _diag_maj():
            import time as _t
            import updater
            for _ in range(60):
                _t.sleep(1)
                res = updater.get_result()
                if res.get("checked"):
                    break
            print(f"[maj] verification : {json.dumps({k: res.get(k) for k in ('hasUpdate', 'version', 'downloadUrl')})}",
                  flush=True)
            if res.get("hasUpdate"):
                _t.sleep(8)               # que la page ait fini de s'ouvrir
                updater.start_install_async()
                print("[maj] installation demandee", flush=True)
                for _ in range(60):
                    _t.sleep(1)
                    p = updater.get_progress()
                    if p.get("step") in ("launching", "error"):
                        print(f"[maj] progression : {p}", flush=True)
                        break
        threading.Thread(target=_diag_maj, daemon=True).start()

    # Test du build Mac (build-mac.yml) seulement : relit le journal de
    # demarrage de la page (window.__journal, index.html) et l'ecrit dans la
    # sortie, faute d'outils de developpement sur la machine de GitHub.
    if os.environ.get("PILOTE_DIAG") and not os.environ.get("PILOTE_MAJ_ESSAI"):
        def _diag():
            import time as _t
            _t.sleep(30)
            # run_js et non evaluate_js : pywebview 6 (Mac) passe evaluate_js
            # par eval(), que la CSP de la page interdit. 4.4.1 n'a pas run_js.
            lire = getattr(window, "run_js", None) or window.evaluate_js
            try:
                res = lire(
                    "JSON.stringify({journal: window.__journal || 'absent',"
                    " fonctions: window.pywebview && window.pywebview.api"
                    " ? Object.keys(window.pywebview.api).length : -1,"
                    " prete: !!window._appShown,"
                    " coque: document.body.classList.contains('has-shell')})")
                print(f"[diag] {res}", flush=True)
                # Mesures du navigateur : debut de la navigation (ramene au
                # lancement), HTML, et chaque requete (debut+duree en ms)
                mes = json.loads(lire(
                    "JSON.stringify((function () {"
                    " var n = performance.getEntriesByType('navigation')[0] || {};"
                    " return {origine: performance.timeOrigin,"
                    "  html: [n.requestStart, n.responseStart, n.responseEnd].map(Math.round),"
                    "  domInteractive: Math.round(n.domInteractive),"
                    "  domContentLoaded: Math.round(n.domContentLoadedEventEnd),"
                    "  ressources: performance.getEntriesByType('resource').map(function (e) {"
                    "   return Math.round(e.startTime) + '+' + Math.round(e.duration) + ' '"
                    "    + e.name.replace(location.origin, '').split('?')[0]; }).slice(0, 25)};"
                    "})())"))
                print(f"[t] {mes['origine'] / 1000 - _T0:6.2f} s  debut de la navigation"
                      f" (les ms de la page partent d'ici)", flush=True)
                print(f"[diag-nav] {json.dumps(mes, ensure_ascii=False)}", flush=True)
            except Exception as e:
                print(f"[diag] lecture KO : {e}", flush=True)
        threading.Thread(target=_diag, daemon=True).start()

        # Certificats HTTPS (docs/mac.md) : le Python compile ne lit pas le
        # Trousseau du Mac. Ecrit ou il cherche ses certificats, puis essaie
        # Yahoo, Gmail et GitHub comme Pilote aujourd'hui, et avec le fichier
        # fourni avec macOS. Poignee de main TLS seulement : rien n'est envoye.
        def _diag_https():
            import ssl
            import socket
            import time as _t
            _t.sleep(16)                  # apres l'echantillonneur du demarrage
            # D'abord les bibliotheques importees a la demande : bien embarquees
            # dans l'app ? (meme piege qu'ocr_win.ps1 : tout marche en dev)
            for mod in ("pypdf", "PIL.Image"):
                try:
                    __import__(mod)
                    print(f"[module] {mod} OK", flush=True)
                except Exception as e:
                    print(f"[module] {mod} KO : {e}", flush=True)
            p = ssl.get_default_verify_paths()
            print(f"[https] {ssl.OPENSSL_VERSION} ; cherche {p.openssl_cafile}"
                  f" (existe : {os.path.isfile(p.openssl_cafile)}) et {p.openssl_capath}"
                  f" (existe : {os.path.isdir(p.openssl_capath)}) ;"
                  f" SSL_CERT_FILE={os.environ.get('SSL_CERT_FILE')}", flush=True)

            def essais(ctx) -> str:
                res = []
                for nom, hote, port in (("Yahoo", "query1.finance.yahoo.com", 443),
                                        ("Gmail", "imap.gmail.com", 993),
                                        ("GitHub", "api.github.com", 443)):
                    try:
                        with socket.create_connection((hote, port), timeout=10) as s:
                            with ctx.wrap_socket(s, server_hostname=hote):
                                pass
                        res.append(f"{nom} OK")
                    except Exception as e:
                        res.append(f"{nom} KO ({type(e).__name__} : {str(e)[:90]})")
                return ", ".join(res)

            print(f"[https] reglages de Pilote : {essais(ssl.create_default_context())}",
                  flush=True)
            if os.path.isfile("/etc/ssl/cert.pem"):
                ctx_mac = ssl.create_default_context(cafile="/etc/ssl/cert.pem")
                print(f"[https] avec /etc/ssl/cert.pem (fourni avec macOS) : {essais(ctx_mac)}",
                      flush=True)
            cours = server.fetch_yahoo("WPEA.PA")
            print(f"[https] cours WPEA.PA lu par Pilote : {cours and cours.get('prix')}",
                  flush=True)
        threading.Thread(target=_diag_https, daemon=True).start()

        # Mac : cles USB (docs/mac.md, etape 4). build-mac.yml monte une image
        # disque CLETEST : ecartee comme toute image, puis presentee comme une
        # cle USB pour essayer le televersement et l'ejection par diskutil.
        def _diag_usb():
            import time as _t
            _t.sleep(25)
            if sys.platform != "darwin":
                return
            try:
                for p in sorted(Path("/Volumes").iterdir()):
                    info = sauvegarde._mac_disque(str(p))
                    champs = {k: info.get(k) for k in (
                        "BusProtocol", "Internal", "Ejectable", "RemovableMedia",
                        "RemovableMediaOrExternalDevice", "VolumeName", "FilesystemName")}
                    champs["uuid"] = bool(info.get("VolumeUUID"))
                    print(f"[usb] {p.name} : {json.dumps(champs, default=str)}", flush=True)
                print(f"[usb] cles vues : {[d['label'] for d in sauvegarde.list_removable_drives()]}",
                      flush=True)
                vrai = sauvegarde._mac_disque
                sauvegarde._mac_disque = lambda point: (dict(vrai(point), BusProtocol="USB")
                                                        if point.endswith("/CLETEST") else vrai(point))
                cles = sauvegarde.list_removable_drives()
                print(f"[usb] CLETEST en USB : {[(d['label'], bool(d['serial'])) for d in cles]}",
                      flush=True)
                cle = next((d for d in cles if d["label"] == "CLETEST"), None)
                if cle:
                    r = sauvegarde.push_to_usb(cle["root"])
                    miroir = os.path.exists("/Volumes/CLETEST/Pilote/Donnees/users.json")
                    print(f"[usb] televersement : ok={r.get('ok')} fichiers={r.get('files')}"
                          f" users.json sur la cle={miroir} {r.get('error', '')}", flush=True)
                    e = sauvegarde.ejecter(cle["root"])
                    print(f"[usb] ejection : {e} ; encore montee : "
                          f"{os.path.exists('/Volumes/CLETEST')}", flush=True)
                sauvegarde._mac_disque = vrai
            except Exception as ex:
                print(f"[usb] KO : {ex}", flush=True)
        threading.Thread(target=_diag_usb, daemon=True).start()

        # Mac : lecture d'images (Vision), code Gmail dans le Trousseau, rapport
        # annuel (docs/mac.md, etape 5). Une capture fabriquee, un code d'essai.
        def _diag_mac_divers():
            import time as _t
            import tempfile
            _t.sleep(30)
            if sys.platform != "darwin":
                return
            try:
                from PIL import Image, ImageDraw, ImageFont
                img = Path(tempfile.gettempdir()) / "pilote_essai_ocr.png"
                # Ecran Details de FitDays comme celui d'Arthur le 14/10/2026 :
                # bloc « Contraste » EN HAUT (ecarts, libelle sous le chiffre,
                # date d'une autre pesee), libelles sur deux lignes, valeurs
                # colorees. Attendu (14/10/2026) : poids 75.9, imc 24.0, graisse
                # 20.3, graisse_viscerale 7.0, age_corporel 24, pas de date.
                im = Image.new("RGB", (1170, 1500), "white")
                d = ImageDraw.Draw(im)
                police = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 46)
                turq, gris, vert, pale, orange = (102, 204, 204), (120, 120, 120), (55, 142, 40), (80, 212, 58), (255, 144, 0)
                for xy, t, c in (((98, 40), "Contraste 08:48 13/09/2026", turq),
                                 ((150, 150), "3.4 kg", turq), ((470, 150), "1.4%", turq), ((900, 150), "1.0", turq),
                                 ((180, 250), "Poids", gris), ((480, 230), "Graisse", gris),
                                 ((480, 280), "corporelle", gris), ((900, 250), "IMC", gris),
                                 ((225, 420), "Détails", turq),
                                 ((242, 560), "Poids", gris), ((780, 560), "75.9 kg", vert),
                                 ((242, 740), "IMC", gris), ((850, 740), "24.0", vert),
                                 ((242, 895), "Graisse", gris), ((800, 925), "20.3 %", vert),
                                 ((242, 955), "corporelle", gris),
                                 ((242, 1075), "Graisse", gris), ((880, 1105), "7.0", pale),
                                 ((242, 1135), "Viscérale", gris),
                                 ((242, 1290), "Âge corporel", gris), ((900, 1290), "24", orange)):
                    d.text(xy, t, fill=c, font=police)
                im.save(img)
                print(f"[ocr] disponible : {sante.ocr_available()}", flush=True)
                r = plateforme.ocr_mac(str(img))
                mots = " ".join(w["t"] for w in r.get("words", []))
                # Boites resserrees (x y w h) et brutes de Vision, a comparer a
                # celles de Windows sur la meme image (docs/mac.md, etape 5)
                boites = [f"{w['t']} {w['x']} {w['y']} {w['w']} {w['h']} (brut {w.get('brut')})"
                          for w in r.get("words", [])]
                print(f"[ocr] ok={r.get('ok')} {r.get('error', '')} mots : {mots}", flush=True)
                print(f"[ocr] boites : {' | '.join(boites)}", flush=True)
                lu = sante.read_screenshots([str(img)])
                print(f"[ocr] lecture Sante : {lu.get('values')} date={lu.get('date')!r} "
                      f"doutes={lu.get('doutes')} manquent={len(lu.get('missing') or [])}", flush=True)
            except Exception as e:
                print(f"[ocr] KO : {e}", flush=True)
            try:
                s = actus._chiffrer("abcd efgh ijkl mnop")
                relu = actus._dechiffrer(s)
                actus._oublier(s)
                parti = True
                try:
                    actus._dechiffrer(s)
                    parti = False
                except Exception:
                    pass
                print(f"[trousseau] range : {s.split(':')[0]} ; relu identique : "
                      f"{relu == 'abcd efgh ijkl mnop'} ; retire a la deconnexion : {parti}", flush=True)
            except Exception as e:
                print(f"[trousseau] KO : {e}", flush=True)
            try:
                r = Api().ouvrir_rapport("<!DOCTYPE html><p>Rapport d'essai</p>", "Pilote_rapport_essai")
                print(f"[rapport] {r.get('ok')} {r.get('error', '')} fichier present : "
                      f"{os.path.exists(r.get('path', ''))}", flush=True)
            except Exception as e:
                print(f"[rapport] KO : {e}", flush=True)
        threading.Thread(target=_diag_mac_divers, daemon=True).start()

        # Mac : fenetre et fermeture (docs/mac.md, etape 3). 45 s apres le
        # lancement : barre de titre, ⌘2, taille ; puis une ecriture laissee en
        # attente et « Quitter » comme ⌘Q. Le test verifie ensuite qu'elle est
        # sur le disque et que l'app s'est fermee seule.
        def _diag_fenetre():
            import time as _t
            _t.sleep(45)
            try:
                lire = getattr(window, "run_js", None) or window.evaluate_js
                print("[fenetre] " + str(lire(
                    "JSON.stringify({mac: document.documentElement.classList.contains('os-mac'),"
                    " barrePilote: !!document.getElementById('app-titlebar'),"
                    " margeHaut: getComputedStyle(document.body).paddingTop,"
                    " ongletApresCmd2: (function () { document.dispatchEvent(new KeyboardEvent("
                    "'keydown', {key: '2', metaKey: true, bubbles: true}));"
                    " return document.body.dataset.activeTab; })(),"
                    " bulle: (document.querySelector('[title*=\"Actualiser\"]') || {}).title})")),
                    flush=True)
                print(f"[fenetre] {window.width}x{window.height} en ({window.x}, {window.y}),"
                      f" zone utile {zone_mac}", flush=True)
                if sys.platform == "darwin":
                    lire("S.uiPrefs = S.uiPrefs || {}; S.uiPrefs.essaiMac = 'ecrit avant de quitter';"
                         " persist(); 1")
                    import AppKit
                    from PyObjCTools import AppHelper
                    AppHelper.callAfter(AppKit.NSApplication.sharedApplication().terminate_, None)
                    print("[fenetre] Quitter demande (comme Cmd+Q)", flush=True)
            except Exception as e:
                print(f"[fenetre] KO : {e}", flush=True)
        threading.Thread(target=_diag_fenetre, daemon=True).start()

        # Echantillonneur : toutes les 0,5 s pendant 15 s, ce que fait chaque fil
        # Python (fonction en cours la plus profonde du code de Pilote ou de ses
        # bibliotheques). Montre qui occupe Python quand le demarrage traine.
        def _echantillons():
            import time as _t
            moi = threading.get_ident()
            noms = {}
            for _ in range(30):
                _t.sleep(0.5)
                noms.update({th.ident: th.name for th in threading.enumerate()})
                vus = []
                for ident, cadre in sys._current_frames().items():
                    if ident == moi:
                        continue
                    pile = traceback.extract_stack(cadre)
                    utiles = [f for f in pile if "threading.py" not in f.filename
                              and "socketserver.py" not in f.filename
                              and "selectors.py" not in f.filename]
                    f = (utiles or pile)[-1]
                    if f.name in ("wait", "acquire", "select", "accept", "_wait_for_tstate_lock",
                                  "sleep", "serve_forever", "readinto", "recv_into", "get"):
                        continue          # fil en attente : ne consomme rien
                    vus.append(f"{noms.get(ident, ident)}:{Path(f.filename).name}:{f.name}:{f.lineno}")
                if vus:
                    print(f"[pile] {_time_lancement.time() - _T0:6.2f} s  " + " | ".join(vus), flush=True)
        threading.Thread(target=_echantillons, daemon=True).start()

    # Test des builds (build-mac.yml, job « ecrans-mac ») : sur les donnees
    # d'exemple (tests/donnees_exemple.py), ouvre un a un les ecrans de
    # PILOTE_ECRANS (« home ; home 640 ; pa-vue » : onglet, puis defilement en
    # px) et ecrit « [ecran] <n> pret » quand chacun est affiche. Le test prend
    # alors la capture d'ecran, puis ferme l'app apres « [ecran] fin ».
    if os.environ.get("PILOTE_ECRANS"):
        def _diag_ecrans():
            import time as _t
            lire = getattr(window, "run_js", None) or window.evaluate_js
            for _ in range(90):              # la page et ses modules
                _t.sleep(1)
                try:
                    if str(lire("JSON.stringify(!!window._appShown)")) == "true":
                        break
                except Exception:
                    pass
            _t.sleep(10)                     # cours, historiques et graphiques
            ecrans = [e.split() for e in os.environ["PILOTE_ECRANS"].split(";") if e.strip()]
            for n, e in enumerate(ecrans, 1):
                onglet = e[0]
                defil = int(e[1]) if len(e) > 1 and e[1].isdigit() else 0
                try:
                    # « js:openSettings('donnees') » : un ecran qui n'est pas un onglet (QA-09)
                    if onglet.startswith("js:"):
                        lire(onglet[3:] + "; 1")
                    else:
                        lire("goTab(%s); _setActiveSidebar(%s); 1" % (json.dumps(onglet), json.dumps(onglet)))
                    _t.sleep(3)
                    # Le premier parent qui defile (la page, ou la zone du
                    # contenu), sans le defilement en douceur de la page
                    lire("(function (y) { var el = document.querySelector('.pane.active');"
                         " while (el && !(el.scrollHeight > el.clientHeight + 5"
                         "   && /(auto|scroll)/.test(getComputedStyle(el).overflowY))) el = el.parentElement;"
                         " el = el || document.scrollingElement; var b = el.style.scrollBehavior;"
                         " el.style.scrollBehavior = 'auto'; el.scrollTop = y; el.style.scrollBehavior = b;"
                         " return 1; })(%d)" % defil)
                    _t.sleep(1)
                    print(f"[ecran] {n} pret {onglet} {defil}", flush=True)
                except Exception as ex:
                    print(f"[ecran] {n} KO {onglet} : {ex}", flush=True)
                _t.sleep(5)                  # le temps de la capture
            print("[ecran] fin", flush=True)
        threading.Thread(target=_diag_ecrans, daemon=True).start()

    # Sauvegarde de la taille/position avant fermeture
    def _sauver_fenetre():
        try:
            d = storage.load_data()
            if storage.get_last_load_info().get("error"):
                # Fichier illisible : on n'ecrit rien par-dessus (regle n. 3)
                return
            d.setdefault("ui", {})

            # Taille reelle via ctypes (gere le maximize ctypes qui bypass window.width)
            actual_w = actual_h = actual_x = actual_y = None
            try:
                import ctypes as _ct
                from ctypes import wintypes as _wt
                _u32 = _ct.windll.user32
                _hwnd = _hwnd_principale()
                class _R(_ct.Structure):
                    _fields_ = [("left", _wt.LONG), ("top", _wt.LONG),
                                ("right", _wt.LONG), ("bottom", _wt.LONG)]
                _wr = _R()
                if _u32.GetWindowRect(_hwnd, _ct.byref(_wr)):
                    actual_w = _wr.right - _wr.left
                    actual_h = _wr.bottom - _wr.top
                    actual_x = _wr.left
                    actual_y = _wr.top
            except Exception:
                pass

            # Fallback pywebview si ctypes echoue
            if actual_w is None:
                try:
                    actual_w, actual_h = int(window.width), int(window.height)
                    actual_x, actual_y = int(window.x), int(window.y)
                except Exception:
                    pass

            # Detecte si la fenetre couvre >= 95 % de la work area → maximisee
            maximized = False
            try:
                import ctypes as _ct2
                from ctypes import wintypes as _wt2
                class _R2(_ct2.Structure):
                    _fields_ = [("left", _wt2.LONG), ("top", _wt2.LONG),
                                ("right", _wt2.LONG), ("bottom", _wt2.LONG)]
                _wa = _R2()
                if _ct2.windll.user32.SystemParametersInfoW(0x0030, 0, _ct2.byref(_wa), 0):
                    wa_w = _wa.right - _wa.left
                    wa_h = _wa.bottom - _wa.top
                    if actual_w and actual_h and wa_w > 0 and wa_h > 0:
                        maximized = (actual_w >= wa_w * 0.95 and actual_h >= wa_h * 0.95)
            except Exception:
                pass
            # Mac : pas de ctypes, la zone utile vient de plateforme.zone_ecran_mac
            if zone_mac and actual_w and actual_h:
                maximized = (actual_w >= zone_mac[2] * 0.95 and actual_h >= zone_mac[3] * 0.95)

            d["ui"]["windowMaximized"] = maximized
            if maximized:
                d["ui"]["windowSize"] = None
                d["ui"]["windowPos"]  = None
            else:
                if actual_w and 200 <= actual_w <= 8000 and \
                   actual_h and 200 <= actual_h <= 8000:
                    d["ui"]["windowSize"] = [actual_w, actual_h]
                if actual_x is not None and -16000 < actual_x < 16000 and \
                   actual_y is not None and -16000 < actual_y < 16000:
                    d["ui"]["windowPos"] = [actual_x, actual_y]
                else:
                    d["ui"]["windowPos"] = None

            storage.save_data(d)
        except Exception as e:
            print(f"[app] Echec sauvegarde UI prefs : {e}", flush=True)

    # Mac : bouton rouge, ⌘Q et ⌘W arrivent ici directement, sans passer par le
    # bouton Fermer de la page, qui ecrit d'abord ce qui attend (0,4 s). La
    # premiere fois, la fermeture est donc annulee : la page ecrit, rappelle
    # Api.fermeture_prete(), et _fermer_mac() ferme pour de bon. Filet de 5 s.
    # NSWindow.close (destroy) ne repasse pas par cet evenement.
    fermeture_mac = {"demandee": False, "faite": False}

    def _fermer_mac(origine: str = "page"):
        if fermeture_mac["faite"]:
            return
        fermeture_mac["faite"] = True
        print(f"[app] fermeture ({origine})", flush=True)   # lu par le test Mac
        _sauver_fenetre()
        try:
            window.destroy()
        except Exception as e:
            print(f"[app] fermeture KO : {e}", flush=True)

    def _vider_puis_fermer_mac():
        try:
            window.run_js("window._fermerApresVidange ? window._fermerApresVidange()"
                          " : window.pywebview.api.fermeture_prete()")
        except Exception as e:
            print(f"[app] vidange avant fermeture KO : {e}", flush=True)
        filet = threading.Timer(5.0, _fermer_mac, args=("delai",))
        filet.daemon = True
        filet.start()

    def _on_closing():
        if sys.platform == "darwin" and not fermeture_mac["faite"]:
            if not fermeture_mac["demandee"]:
                fermeture_mac["demandee"] = True
                threading.Thread(target=_vider_puis_fermer_mac, daemon=True).start()
            return False
        _sauver_fenetre()

    global _fermeture_prete
    _fermeture_prete = lambda: _fermer_mac("page")

    # L'icone a la couleur d'accent est posee par reveal_main_window(), quand
    # la fenetre apparait vraiment (et sur l'ecran de chargement avant elle)
    window.events.closing += _on_closing
    if os.environ.get("PILOTE_DIAG"):
        window.events.loaded += lambda: _repere("page principale chargee (pywebview)")
        if _splash_window is not None:
            _splash_window.events.shown += lambda: _repere("ecran de chargement affiche")
    _repere("fenetres creees, lancement de pywebview")

    try:
        # debug=False pour la prod ; True pour ouvrir les devtools
        if sys.platform == "darwin":
            # Menus et boites de dialogue de pywebview en francais
            webview.start(debug=False, localization=plateforme.LOCALISATION_MAC)
        else:
            # Dossier WebView2 fixe : sans lui, pywebview en cree un neuf dans
            # %TEMP% a chaque lancement et ne l'efface jamais (119 dossiers,
            # 694 Mo sur le PC d'Arthur, ENV-06). Le mode prive reste actif :
            # rien n'y est garde d'une session a l'autre.
            _menage_webview_temp()
            webview.start(debug=False,
                          storage_path=os.path.join(tempfile.gettempdir(), "pilote_webview2"))
    finally:
        # Apres fermeture de la fenetre : on coupe le serveur, on libere le port
        server.stop_server()
        try:
            if _lock_socket is not None:
                _lock_socket.close()
        except Exception:
            pass
        # Reglage « moment » de la sauvegarde USB : a la fermeture de Pilote
        try:
            if sauvegarde.load_config().get("moment") == "fermeture":
                _sauvegarde_auto_une()
        except Exception as e:
            print(f"[app] sauvegarde a la fermeture KO : {e}", flush=True)
        if sys.platform == "darwin":
            # Filet : un fil de pywebview encore en attente d'une page fermee
            # garderait l'app ouverte (icone dans le Dock) ; 3 s apres, on sort
            fin = threading.Timer(3.0, lambda: os._exit(0))
            fin.daemon = True
            fin.start()

    return 0


if __name__ == "__main__":
    sys.exit(main())
