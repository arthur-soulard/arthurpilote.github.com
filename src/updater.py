"""
updater.py — Verifieur et installateur de mise a jour avec progression et logs.

Tous les evenements sont logges dans %APPDATA%\\Pilote\\update.log
(Mac : ~/Library/Logs/Pilote/update.log) pour permettre de diagnostiquer
toute panne d'auto-update. Windows installe le Setup ; Mac remplace son
Pilote.app par celui de Pilote_Mac.zip (_installer_mac).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
import traceback
import urllib.error
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path

RELEASES_API = "https://api.github.com/repos/arthur-soulard/arthurpilote.github.com/releases/latest"

# Solution de secours quand l'API refuse de repondre. Sans jeton, elle accepte
# 60 requetes par heure et par adresse IP ; une adresse partagee (box, reseau
# d'ecole) peut epuiser ce quota sans que Pilote y soit pour rien, et l'API
# repond alors 403. Constate le 23/09/2026 : huit verifications refusees de
# suite, l'app se croyait a jour. La page publique n'est pas soumise a ce quota :
# /releases/latest redirige vers /releases/tag/vX.Y.Z, et l'installeur a une URL
# fixe (meme nom que dans release.yml et OutputBaseFilename de installer.iss).
RELEASES_PAGE = "https://github.com/arthur-soulard/arthurpilote.github.com/releases"
SETUP_ASSET   = "Pilote_Setup.exe"
# Mac : l'app zippee, jointe a la meme release par release.yml (job mac). Pas
# d'installeur : Pilote remplace lui-meme son Pilote.app (_installer_mac).
MAC_ASSET     = "Pilote_Mac.zip"
ASSET         = MAC_ASSET if sys.platform == "darwin" else SETUP_ASSET
_UA = "Suivi-PEA-Updater/2"

# Fiche des nouveautes : src/nouveautes.json, livre avec l'app (historique de
# Parametres -> Mises a jour) et relu au tag de la nouvelle version avant de
# l'installer. raw.githubusercontent.com n'a pas le quota de l'API, et le tag
# est connu par les deux chemins de _fetch (API ou page publique).
NOTES_FILE = "nouveautes.json"
NOTES_URL  = ("https://raw.githubusercontent.com/arthur-soulard/arthurpilote.github.com/"
              "{tag}/src/" + NOTES_FILE)
_NOTES_MAX = 512 * 1024   # octets lus au plus : la fiche n'est que du texte

_lock = threading.Lock()

_state: dict = {
    "checked": False,
    "hasUpdate": False,
    "version": None,
    "url": None,
    "downloadUrl": None,
    "notes": None,          # versions entre l'installee et la nouvelle, ou None
}

_progress: dict = {"step": "idle", "pct": 0, "error": None}

# Taille et empreinte SHA-256 annoncees par l'API pour l'installeur retenu
# ({} quand la version vient de la page publique) : un fichier tronque ou
# altere en route n'est pas lance (audit du 20/10/2026, SUP-06)
_attendu: dict = {}


# ── Logs ──────────────────────────────────────────────────────────────────────

def _log_path() -> Path:
    if sys.platform == "darwin":
        # Pas d'APPDATA sur Mac : sans ce cas, un dossier ~/Pilote serait cree
        # a la racine du compte
        p = Path.home() / "Library" / "Logs" / "Pilote"
    else:
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        p = Path(base) / "Pilote"
    try:
        p.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return p / "update.log"


def _log(msg: str) -> None:
    try:
        with open(_log_path(), "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat(timespec='seconds')}] {msg}\n")
    except Exception:
        pass


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_ver(v: str) -> tuple:
    try:
        return tuple(int(x) for x in v.strip().lstrip("v").split("."))
    except Exception:
        return (0, 0, 0)


# Hotes autorises pour le telechargement de l'installeur.
_ALLOWED_HOSTS = ("github.com", "githubusercontent.com")


def _is_github_https(url: str) -> bool:
    """L'URL est-elle une https:// servie par GitHub ?"""
    if not url:
        return False
    try:
        u = urllib.parse.urlparse(url)
    except Exception:
        return False
    if u.scheme != "https" or not u.hostname:
        return False
    host = u.hostname.lower()
    return any(host == h or host.endswith("." + h) for h in _ALLOWED_HOSTS)


def _set_progress(step: str, pct: int, error: str | None = None) -> None:
    with _lock:
        _progress.update({"step": step, "pct": pct, "error": error})
    _log(f"PROGRESS step={step} pct={pct} error={error}")


# ── Check update ──────────────────────────────────────────────────────────────

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Ne suit pas les redirections : c'est l'adresse de destination qu'on veut lire."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _redirect_target(url: str) -> str | None:
    """Adresse vers laquelle `url` redirige (en-tete Location), sans la suivre."""
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": _UA})
    try:
        with urllib.request.build_opener(_NoRedirect).open(req, timeout=8):
            return None                     # 200 : pas de redirection
    except urllib.error.HTTPError as e:
        if e.code in (301, 302, 303, 307, 308):
            return e.headers.get("Location")
        raise


def _latest_from_api() -> tuple:
    """(version, page de la release, URL de l'installeur) lus dans l'API GitHub."""
    req = urllib.request.Request(
        RELEASES_API,
        headers={"User-Agent": _UA, "Accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(req, timeout=8) as r:
        data = json.loads(r.read())

    latest = data.get("tag_name", "").lstrip("v")
    html_url = data.get("html_url", "")
    download_url = None
    for asset in data.get("assets", []):
        nom = asset.get("name", "")
        if (nom == MAC_ASSET) if sys.platform == "darwin" else nom.endswith("Setup.exe"):
            url = asset.get("browser_download_url")
            # Ce fichier sera EXECUTE avec les droits de l'utilisateur.
            # On n'accepte qu'une URL https servie par GitHub : une reponse
            # d'API alteree ne doit pas pouvoir rediriger l'auto-update
            # vers un binaire quelconque.
            if _is_github_https(url):
                download_url = url
                _attendu.clear()
                _attendu.update({"size": asset.get("size"), "digest": asset.get("digest")})
            else:
                _log(f"CHECK: asset ignore, URL non GitHub : {url}")
            break
    return latest, html_url, download_url


def _latest_from_page() -> tuple:
    """Meme resultat, lu sur la page publique (pas de quota) : voir RELEASES_PAGE."""
    html_url = _redirect_target(RELEASES_PAGE + "/latest") or ""
    marker = "/releases/tag/"
    if marker not in html_url or not _is_github_https(html_url):
        raise ValueError(f"redirection inattendue : {html_url!r}")
    tag = urllib.parse.unquote(html_url.split(marker, 1)[1].split("?")[0].strip("/"))
    latest = tag.lstrip("v")
    if _parse_ver(latest) == (0, 0, 0):
        raise ValueError(f"tag illisible : {tag!r}")

    # L'installeur doit exister vraiment : une release tout juste creee peut
    # encore attendre ses fichiers. Pas d'installeur -> pas de mise a jour
    # proposee, on reessaiera au prochain lancement.
    download_url = f"{RELEASES_PAGE}/download/{urllib.parse.quote(tag)}/{ASSET}"
    _attendu.clear()
    try:
        present = bool(_redirect_target(download_url))   # 302 vers le stockage GitHub
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
        present = False
    if not present:
        _log(f"CHECK: {ASSET} absent de la release {tag}")
        download_url = None
    return latest, html_url, download_url


def _fetch(current: str) -> None:
    try:
        _log(f"CHECK current_version={current}")
        essai = _essai_mac()
        if essai:
            latest, html_url, download_url = essai
        else:
            try:
                latest, html_url, download_url = _latest_from_api()
            except Exception as e:
                _log(f"CHECK API KO ({e}) -> page publique des releases")
                latest, html_url, download_url = _latest_from_page()
                _log(f"CHECK via page publique : latest={latest}")

        # Ni Windows ni Mac : rien a installer, rien a proposer
        if sys.platform not in ("win32", "darwin"):
            download_url = None

        # Sans installeur telechargeable, proposer la mise a jour ne menerait
        # qu'a un echec au moment d'installer : on attend le prochain lancement.
        has_update = (bool(latest) and bool(download_url)
                      and _parse_ver(latest) > _parse_ver(current))

        # La fiche ne bloque rien : sans elle, la mise a jour reste proposee
        notes = _notes_distantes(latest, current) if has_update else None

        with _lock:
            _state.update({
                "checked": True,
                "erreur": None,
                "hasUpdate": has_update,
                "version": latest,
                "url": html_url,
                "downloadUrl": download_url,
                "notes": notes,
            })
        _log(f"CHECK OK latest={latest} hasUpdate={has_update} downloadUrl={download_url}"
             f" notes={None if notes is None else len(notes)}")
    except Exception as e:
        _log(f"CHECK FAIL: {e}\n{traceback.format_exc()}")
        with _lock:
            _state["checked"] = True
            # Dit a l'ecran : jusqu'a la 4.4.20, un echec s'affichait « A jour »
            _state["erreur"] = "Vérification impossible : pas de connexion à GitHub"


# ── Fiche des nouveautes ─────────────────────────────────────────────────────

def _texte(v, n: int) -> str:
    return v.strip()[:n] if isinstance(v, str) else ""


def _valider_notes(data) -> list:
    """Versions lisibles du fichier, de la plus recente a la plus ancienne.

    La fiche distante est relue a chaque verification : on ne garde que du
    texte court, dans la forme attendue, quoi que contienne le fichier."""
    versions = data.get("versions") if isinstance(data, dict) else None
    out = []
    for v in versions if isinstance(versions, list) else []:
        if not isinstance(v, dict):
            continue
        num = _texte(v.get("version"), 20).lstrip("v")
        if _parse_ver(num) == (0, 0, 0):
            continue
        e = {"version": num,
             "date":    _texte(v.get("date"), 10),
             "titre":   _texte(v.get("titre"), 140)}
        for k in ("nouveau", "ameliore", "corrige"):
            pts = v.get(k)
            pts = pts if isinstance(pts, list) else []
            e[k] = [t for t in (_texte(p, 600) for p in pts) if t][:30]
        out.append(e)
    out.sort(key=lambda e: _parse_ver(e["version"]), reverse=True)
    return out


def historique() -> list:
    """Fiches livrees avec l'app installee (vide si le fichier manque)."""
    base = getattr(sys, "_MEIPASS", None) or Path(__file__).resolve().parent
    try:
        with open(Path(base) / NOTES_FILE, encoding="utf-8") as f:
            return _valider_notes(json.load(f))
    except Exception as e:
        _log(f"NOTES: historique illisible ({e})")
        return []


def _notes_distantes(latest: str, current: str) -> list | None:
    """Fiches des versions entre `current` (exclue) et `latest` (incluse),
    lues dans le fichier du tag de `latest`. None si illisible."""
    url = NOTES_URL.format(tag=urllib.parse.quote("v" + latest))
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read(_NOTES_MAX).decode("utf-8"))
    except Exception as e:
        _log(f"NOTES: fiche de la v{latest} illisible ({e})")
        return None
    cur, new = _parse_ver(current), _parse_ver(latest)
    return [v for v in _valider_notes(data)
            if cur < _parse_ver(v["version"]) <= new]


def start_check(current_version: str) -> None:
    threading.Thread(target=_fetch, args=(current_version,), daemon=True).start()


def get_result() -> dict:
    with _lock:
        return dict(_state)


# ── Install with progress ────────────────────────────────────────────────────

def get_progress() -> dict:
    with _lock:
        return dict(_progress)


def start_install_async() -> None:
    """Lance l'installation dans un thread — retourne immediatement."""
    _log("INSTALL: thread starting")
    _set_progress("downloading", 0)
    threading.Thread(target=_do_install, daemon=True).start()


def _conforme(chemin, size) -> bool:
    """Taille et SHA-256 du fichier telecharge = ce qu'annonce l'API (si connu)."""
    attendu = dict(_attendu)
    if attendu.get("size") and int(attendu["size"]) != size:
        _log(f"INSTALL: taille {size} au lieu de {attendu['size']}")
        return False
    digest = str(attendu.get("digest") or "")
    if digest.startswith("sha256:"):
        import hashlib
        h = hashlib.sha256()
        with open(chemin, "rb") as f:
            for bloc in iter(lambda: f.read(1 << 20), b""):
                h.update(bloc)
        if h.hexdigest() != digest.split(":", 1)[1].lower():
            _log("INSTALL: empreinte SHA-256 differente de celle de l'API")
            return False
    return True


def _do_install() -> None:
    try:
        with _lock:
            download_url = _state.get("downloadUrl")
            version = _state.get("version")

        _log(f"INSTALL: starting v{version} from {download_url}")

        if not download_url:
            _set_progress("error", 0, "URL de téléchargement introuvable (recheck nécessaire)")
            return

        # Revalidation au moment d'executer : _state est partage entre threads
        if not _url_permise(download_url):
            _log(f"INSTALL: URL refusee : {download_url}")
            _set_progress("error", 0, "URL de téléchargement refusée (hors GitHub)")
            return

        if sys.platform == "darwin":
            _installer_mac(download_url, version)
            return

        exe_path = sys.executable
        _log(f"INSTALL: exe_path={exe_path} frozen={getattr(sys, 'frozen', False)}")

        tmp_dir = Path(tempfile.gettempdir()) / "pilote_update"
        tmp_dir.mkdir(exist_ok=True)
        setup_path = tmp_dir / "Pilote_Setup.exe"
        _log(f"INSTALL: setup_path={setup_path}")

        # Supprime un résidu d'une tentative précédente pour éviter Permission denied
        if setup_path.exists():
            try:
                setup_path.unlink()
                _log("INSTALL: removed stale setup file")
            except Exception as e:
                _log(f"INSTALL: could not remove stale setup file: {e}")

        # ── Étape 1 : Téléchargement (0 → 70%) ──────────────────────────────
        _set_progress("downloading", 1)
        req = urllib.request.Request(
            download_url,
            headers={"User-Agent": "Suivi-PEA-Updater/2"},
        )
        with urllib.request.urlopen(req, timeout=300) as r:
            total = int(r.headers.get("Content-Length", 0))
            estimated = total or (25 * 1024 * 1024)  # fallback 25 Mo
            _log(f"INSTALL: download total={total} estimated={estimated}")
            downloaded = 0
            chunk_size = 65536  # 64 Ko
            last_logged_pct = 0
            with open(setup_path, "wb") as f:
                while True:
                    chunk = r.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    pct = min(69, int(downloaded / estimated * 70))
                    pct = max(1, pct)  # toujours montrer >= 1% pour ne pas paraître bloqué
                    _set_progress("downloading", pct)
                    if pct - last_logged_pct >= 10:
                        _log(f"INSTALL: downloaded {downloaded} bytes ({pct}%)")
                        last_logged_pct = pct

        size = setup_path.stat().st_size
        _log(f"INSTALL: download done, file size={size}")

        if size < 1024 * 1024:  # < 1 Mo = corrompu
            _set_progress("error", 0, f"Téléchargement corrompu ({size} octets)")
            return
        if not _conforme(setup_path, size):
            _set_progress("error", 0, "Téléchargement incomplet ou altéré : réessaie plus tard")
            return

        # ── Étape 2 : Préparation batch (70 → 80%) ───────────────────────────
        _set_progress("installing", 75)

        # Nom reel du binaire en cours : survit a un renommage de l'app

        bat_path = tmp_dir / "update.bat"
        # Aucun chemin ecrit dans le batch : %~dp0 (son propre dossier, ou sont
        # aussi le Setup et le journal) est resolu par cmd lui-meme. Le fichier
        # est en ASCII : jusqu'a la 4.4.20, un accent dans %TEMP% (compte
        # « Hélène ») devenait « ? » et la mise a jour echouait, Pilote ferme.
        bat_content = (
            f'@echo off\r\n'
            f'echo [%TIME%] Update batch started >> "%~dp0update_bat.log"\r\n'
            f':wait\r\n'
            f'"%SystemRoot%\\System32\\tasklist.exe" /FI "PID eq %~2" /NH 2>nul'
            f' | "%SystemRoot%\\System32\\find.exe" " %~2 " > nul\r\n'
            f'if not errorlevel 1 ( "%SystemRoot%\\System32\\timeout.exe" /t 1 /nobreak > nul & goto wait )\r\n'
            f'echo [%TIME%] App process gone, waiting 5s for file handle release >> "%~dp0update_bat.log"\r\n'
            f'"%SystemRoot%\\System32\\timeout.exe" /t 5 /nobreak > nul\r\n'
            f'echo [%TIME%] Running installer >> "%~dp0update_bat.log"\r\n'
            f'"%~dp0{setup_path.name}" /VERYSILENT /NORESTART /SUPPRESSMSGBOXES\r\n'
            f'set CODE=%errorlevel%\r\n'
            f'echo [%TIME%] Installer finished (errorlevel=%CODE%) >> "%~dp0update_bat.log"\r\n'
            # Echec : l'ancien Pilote, s'il est encore la, est relance
            f'if not "%CODE%"=="0" if exist "%~1" start "" "%~1"\r\n'
            f'(goto) 2>nul & del "%~f0"\r\n'
        )
        bat_path.write_text(bat_content, encoding="ascii", errors="replace")
        _log(f"INSTALL: batch written to {bat_path}")

        # ── Étape 3 : Lancement batch + fermeture (80 → 100%) ───────────────
        _set_progress("installing", 85)

        # Chemin de l'exe et numero du processus en arguments (%1, %2) : rien de
        # non ASCII dans le batch. /s : cmd ne retire que les guillemets externes
        ancien = exe_path if getattr(sys, "frozen", False) else ""
        subprocess.Popen(
            f'cmd.exe /s /c ""{bat_path}" "{ancien}" {os.getpid()}"',
            creationflags=subprocess.CREATE_NO_WINDOW,
            close_fds=True,
        )
        _log("INSTALL: batch launched")

        _set_progress("launching", 100)

        # Pause pour que le JS puisse lire le message final avant fermeture
        import time as _time
        _time.sleep(3.5)

        _log("INSTALL: closing window")
        try:
            import webview
            if webview.windows:
                webview.windows[0].destroy()
        except Exception as e:
            _log(f"INSTALL: window.destroy() failed: {e}")

    except Exception as e:
        _log(f"INSTALL FATAL: {e}\n{traceback.format_exc()}")
        _set_progress("error", 0, str(e))


# ── Mac : Pilote remplace lui-meme son Pilote.app ───────────────────────────
# Pas de compte developpeur Apple (docs/mac.md) : l'app n'est ni signee ni
# notarisee. Un fichier telecharge par Pilote (et non par un navigateur) ne
# porte pas la marque de quarantaine : la nouvelle version s'ouvre sans
# repasser par « Ouvrir quand meme ». Les donnees vivent dans Application
# Support, hors de l'app : la remplacer ne les touche pas.

def _essai_mac():
    """Test du build Mac seulement (PILOTE_DIAG et PILOTE_MAJ_ESSAI="<url>|<version>") :
    une fausse release servie en local, pour essayer l'installation sans GitHub."""
    v = os.environ.get("PILOTE_MAJ_ESSAI") if os.environ.get("PILOTE_DIAG") else None
    if not v or sys.platform != "darwin":
        return None
    url, _, version = v.partition("|")
    return version, "", url


def _url_permise(url: str) -> bool:
    if _is_github_https(url):
        return True
    return _essai_mac() is not None and str(url).startswith("http://127.0.0.1:")


def _bundle_mac():
    """Le Pilote.app qui tourne (sys.executable : .../Pilote.app/Contents/MacOS/Pilote)."""
    if not getattr(sys, "frozen", False):
        return None
    for parent in Path(sys.executable).resolve().parents:
        if parent.suffix == ".app":
            return parent
    return None


def mac_a_deplacer() -> bool:
    """Mac : l'app tourne-t-elle d'un endroit ou elle ne pourra pas se mettre a
    jour (Telechargements non deplacee, dossier en lecture seule) ?"""
    bundle = _bundle_mac()
    if sys.platform != "darwin" or bundle is None:
        return False
    return "AppTranslocation" in str(bundle) or not os.access(bundle.parent, os.W_OK)


def _installer_mac(download_url: str, version: str) -> None:
    import shlex
    import time as _time
    bundle = _bundle_mac()
    _log(f"INSTALL MAC: bundle={bundle}")
    if bundle is None:
        _set_progress("error", 0, "La mise à jour ne s'installe que dans l'app (pas en développement).")
        return
    # Lancee depuis Telechargements sans avoir ete deplacee, l'app tourne d'une
    # copie en lecture seule (« App Translocation ») : rien a remplacer
    if mac_a_deplacer():
        if "AppTranslocation" in str(bundle):
            _set_progress("error", 0, "Déplace Pilote dans le dossier Applications, puis relance-le : "
                                      "la mise à jour pourra s'installer.")
        else:
            _set_progress("error", 0, "Pilote est dans un dossier que ton compte ne peut pas modifier : "
                                      "mets-le dans le dossier Applications de ton compte "
                                      "(~/Applications), ou installe la mise à jour depuis un compte "
                                      "administrateur.")
        return

    tmp_dir = Path(tempfile.mkdtemp(prefix="pilote_maj_"))
    zip_path = tmp_dir / MAC_ASSET
    # Meme telechargement que sous Windows (0 -> 70 %), garde a part pour ne
    # pas toucher au chemin Windows
    req = urllib.request.Request(download_url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=300) as r:
        total = int(r.headers.get("Content-Length", 0))
        estimated = total or (40 * 1024 * 1024)
        downloaded = 0
        with open(zip_path, "wb") as f:
            while True:
                chunk = r.read(65536)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                _set_progress("downloading", max(1, min(69, int(downloaded / estimated * 70))))
    size = zip_path.stat().st_size
    _log(f"INSTALL MAC: zip {size} octets")
    if size < 1024 * 1024:
        _set_progress("error", 0, f"Téléchargement corrompu ({size} octets)")
        return

    _set_progress("installing", 75)
    neuf_dir = tmp_dir / "neuf"
    r = subprocess.run(["ditto", "-x", "-k", str(zip_path), str(neuf_dir)],
                       capture_output=True, text=True, timeout=300)
    neuf = neuf_dir / "Pilote.app"
    if r.returncode != 0 or not (neuf / "Contents" / "MacOS" / "Pilote").exists():
        _log(f"INSTALL MAC: decompression KO {r.stderr}")
        _set_progress("error", 0, "Archive de la mise à jour illisible")
        return

    # Le script attend la fin de Pilote, met l'ancienne app de cote, pose la
    # nouvelle (remet l'ancienne si ca rate), puis la relance
    q = shlex.quote
    ancienne = str(bundle) + ".ancienne"
    journal = _log_path().parent / "update_sh.log"
    script = tmp_dir / "maj.sh"
    script.write_text(
        "#!/bin/sh\n"
        f"exec >> {q(str(journal))} 2>&1\n"
        f"echo \"[$(date)] mise a jour v{version}\"\n"
        f"while kill -0 {os.getpid()} 2>/dev/null; do sleep 0.5; done\n"
        "sleep 1\n"
        f"rm -rf {q(ancienne)}\n"
        f"mv {q(str(bundle))} {q(ancienne)} || exit 1\n"
        f"if ! mv {q(str(neuf))} {q(str(bundle))}; then mv {q(ancienne)} {q(str(bundle))}; exit 1; fi\n"
        f"xattr -dr com.apple.quarantine {q(str(bundle))} 2>/dev/null\n"
        f"rm -rf {q(ancienne)}\n"
        # La nouvelle app ne doit pas heriter des reglages d'un test (PILOTE_*)
        "unset PILOTE_DIAG PILOTE_MAJ_ESSAI\n"
        f"open {q(str(bundle))}\n"
        "echo \"[$(date)] relancee\"\n"
        f"rm -rf {q(str(tmp_dir))}\n",
        encoding="utf-8")
    subprocess.Popen(["/bin/sh", str(script)], start_new_session=True, close_fds=True,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    _log("INSTALL MAC: script lance")
    _set_progress("launching", 100)
    _time.sleep(3.5)          # le temps pour la page d'afficher le dernier message
    _log("INSTALL MAC: fermeture")
    try:
        import webview
        if webview.windows:
            webview.windows[0].destroy()
    except Exception as e:
        _log(f"INSTALL MAC: destroy KO {e}")
