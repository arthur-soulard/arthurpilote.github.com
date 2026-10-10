"""
notifications.py — Notifications Windows toast natives.

Utilise win10toast si dispo (pip install win10toast). Sur Mac, osascript
(fourni avec macOS) fait l'equivalent sans dependance. Ailleurs, ou si la lib
manque, les fonctions deviennent des no-ops silencieux, pour ne jamais faire
crasher l'app.

Les preferences sont lues depuis storage.load_data()['notifs'] :
  - bigMove   : alerte cours qui bouge > +/- 5%
  - dividend  : dividende prevu aujourd'hui
  - yahooDown : Yahoo injoignable
"""
from __future__ import annotations

import sys
import subprocess
import threading
from pathlib import Path
from typing import Optional

try:
    from win10toast import ToastNotifier  # type: ignore
    _toaster = ToastNotifier()
    _AVAILABLE = True
except Exception:
    _toaster = None
    _AVAILABLE = sys.platform == "darwin"


def _icon_path() -> Optional[str]:
    """Cherche l'icone .ico dans /assets pour les toasts (sinon icone par defaut)."""
    here = Path(__file__).resolve().parent
    for candidate in (here.parent / "assets" / "icon.ico", here / "icon.ico"):
        if candidate.exists():
            return str(candidate)
    return None


def _show_mac(title: str, msg: str) -> None:
    def chaine(s) -> str:   # chaine AppleScript : \ et " echappes
        return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'
    try:
        subprocess.run(["osascript", "-e",
                        f"display notification {chaine(msg)} with title {chaine(title)}"],
                       capture_output=True, timeout=10)
    except Exception as e:
        print(f"[notif] Echec osascript : {e}", flush=True)


def _show(title: str, msg: str, duration: int = 6) -> None:
    if sys.platform == "darwin":
        _show_mac(title, msg)
        return
    if not _AVAILABLE or _toaster is None:
        return
    icon = _icon_path()
    try:
        # threaded=True pour ne pas bloquer l'event loop pywebview
        _toaster.show_toast(
            title, msg,
            icon_path=icon,
            duration=duration,
            threaded=True,
        )
    except Exception as e:
        print(f"[notif] Echec toast : {e}", flush=True)


# ─── API publique ─────────────────────────────────────────────────────────────

def notify(title: str, msg: str, kind: str, prefs: dict) -> None:
    """
    Affiche une notif si l'utilisateur l'a activee.
      kind : 'bigMove' | 'dividend' | 'yahooDown' | 'info'
      prefs : dict de preferences (depuis pea_data.json -> notifs)
    """
    if kind != "info" and not prefs.get(kind, False):
        return
    threading.Thread(target=_show, args=(title, msg), daemon=True).start()


def is_available() -> bool:
    return _AVAILABLE
