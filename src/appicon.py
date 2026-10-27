"""
appicon.py — Icone de l'app recoloree a la volee selon la couleur d'accent.

L'icone embarquee dans le .exe est figee (ressource Windows, choisie au build).
Ce module en regenere une variante a la couleur d'accent choisie dans l'UI,
puis l'applique :

  * a la fenetre en cours (titre + barre des taches) via WM_SETICON  — immediat
  * aux raccourcis .lnk (Bureau, menu Demarrer, barre des taches epinglee)
    via WScript.Shell, uniquement si l'utilisateur le demande explicitement

Sur Mac, apply_to_window agit sur l'icone du Dock pendant que Pilote tourne
(NSApplication) et sur celle de Pilote.app (Finder, Launchpad, Dock au repos)
via NSWorkspace, sans bouton. Une mise a jour remplace Pilote.app et efface
cette icone : elle est remise au lancement suivant (_sync_app_mac).

Le rendu reprend exactement assets/make_icon.py : carre arrondi, lisere
interne, "P" blanc centre, supersampling 4x + LANCZOS, .ico multi-resolution
a PNG embarques (net de 16 a 256 px).
"""
from __future__ import annotations

import os
import sys
import struct
import subprocess
from io import BytesIO
from pathlib import Path
from typing import Optional

import storage


DEFAULT_COLOR = "#9c4a7a"   # prune, accent par defaut du Carnet (ACCENT_DEFAULT dans index.html)
_ICON_SIZES = [16, 20, 24, 32, 40, 48, 64, 96, 128, 256]

# Handles HICON gardes vivants : Windows lit l'icone tant que la fenetre existe
_LIVE_ICONS = []


# ─── Couleurs ─────────────────────────────────────────────────────────────────

def _norm_color(color: Optional[str]) -> str:
    c = (color or "").strip()
    if c.startswith("#"):
        c = c[1:]
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    if len(c) != 6:
        return DEFAULT_COLOR
    try:
        int(c, 16)
    except ValueError:
        return DEFAULT_COLOR
    return "#" + c.lower()


def _rgb(color: str) -> tuple:
    c = _norm_color(color)[1:]
    return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16))


def _darken(rgb: tuple, factor: float = 0.78) -> tuple:
    return tuple(max(0, min(255, int(round(v * factor)))) for v in rgb)


# ─── Rendu (identique a assets/make_icon.py, mais parametre par la couleur) ────

def _find_bold_font(size: int):
    from PIL import ImageFont
    for c in ("C:/Windows/Fonts/segoeuib.ttf",
              "C:/Windows/Fonts/arialbd.ttf",
              "C:/Windows/Fonts/calibrib.ttf",
              "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
              "/Library/Fonts/Arial Bold.ttf",
              "/System/Library/Fonts/Helvetica.ttc",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        if Path(c).exists():
            try:
                return ImageFont.truetype(c, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _render_tile(target_size: int, base: tuple, dark: tuple):
    from PIL import Image, ImageDraw
    SS = 4
    size = target_size * SS
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    radius = int(size * 0.18)
    d.rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=base)

    if target_size > 32:
        inset = max(2, size // 64)
        d.rounded_rectangle((inset, inset, size - 1 - inset, size - 1 - inset),
                            radius=radius - inset, outline=dark,
                            width=max(2, size // 96))

    p_ratio = 0.62 if target_size >= 64 else 0.72
    font = _find_bold_font(int(size * p_ratio))
    bbox = d.textbbox((0, 0), "P", font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    d.text(((size - w) / 2 - bbox[0], (size - h) / 2 - bbox[1] - size * 0.02),
           "P", font=font, fill=(255, 255, 255))

    return img.resize((target_size, target_size), Image.Resampling.LANCZOS)


def _build_ico(images_by_size: dict, out_path: Path) -> None:
    """ICONDIR + ICONDIRENTRY[N] + flux PNG (format moderne, net en petit)."""
    sizes = sorted(images_by_size.keys())
    blobs = {}
    for s in sizes:
        buf = BytesIO()
        images_by_size[s].save(buf, format="PNG", optimize=True)
        blobs[s] = buf.getvalue()

    out = bytearray()
    out += struct.pack("<HHH", 0, 1, len(sizes))
    offset = 6 + 16 * len(sizes)
    for s in sizes:
        png = blobs[s]
        b = 0 if s >= 256 else s
        out += struct.pack("<BBBBHHII", b, b, 0, 0, 1, 32, len(png), offset)
        offset += len(png)
    for s in sizes:
        out += blobs[s]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(".ico.tmp")
    tmp.write_bytes(bytes(out))
    os.replace(tmp, out_path)


# ─── Cache disque ─────────────────────────────────────────────────────────────

def icons_dir() -> Path:
    d = storage.get_app_dir() / "icones"
    d.mkdir(parents=True, exist_ok=True)
    return d


def ico_for(color: str) -> Optional[Path]:
    """
    Retourne le .ico correspondant a la couleur (le genere si absent).
    Retourne None si Pillow n'est pas disponible.
    """
    color = _norm_color(color)
    path = icons_dir() / ("pilote_" + color[1:] + ".ico")
    if path.exists() and path.stat().st_size > 0:
        return path
    try:
        base = _rgb(color)
        imgs = {s: _render_tile(s, base, _darken(base)) for s in _ICON_SIZES}
        _build_ico(imgs, path)
        return path
    except Exception as e:
        print(f"[appicon] generation KO ({color}) : {e}", flush=True)
        return None


def png_for(color: str) -> Optional[Path]:
    """Mac : meme icone en un seul PNG 512 px (NSImage le met a l'echelle)."""
    color = _norm_color(color)
    path = icons_dir() / ("pilote_" + color[1:] + ".png")
    if path.exists() and path.stat().st_size > 0:
        return path
    try:
        base = _rgb(color)
        tmp = path.with_suffix(".png.tmp")
        _render_tile(512, base, _darken(base)).save(tmp, format="PNG")
        os.replace(tmp, path)
        return path
    except Exception as e:
        print(f"[appicon] generation KO ({color}) : {e}", flush=True)
        return None


# ─── Mac : Dock et Pilote.app ─────────────────────────────────────────────────

_MAC_MARQUE = "app_mac.txt"     # couleur posee sur Pilote.app, pour la remettre apres une mise a jour


def _apply_dock_mac(color: str) -> bool:
    path = png_for(color)
    if not path:
        return False
    try:
        from AppKit import NSApplication, NSImage
        from PyObjCTools import AppHelper
        image = NSImage.alloc().initWithContentsOfFile_(str(path))
        if image is None:
            return False
        # AppKit veut le fil principal ; on est appele depuis le pont ou un evenement
        AppHelper.callAfter(NSApplication.sharedApplication().setApplicationIconImage_, image)
        return True
    except Exception as e:
        print(f"[appicon] Dock KO : {e}", flush=True)
        return False


def _apply_app_mac(color: str) -> dict:
    import updater
    bundle = updater._bundle_mac()
    if bundle is None:
        return {"ok": False, "error": "seulement dans l'app compilée", "count": 0}
    if updater.mac_a_deplacer():
        return {"ok": False, "error": "rangez d'abord Pilote dans Applications", "count": 0}
    path = png_for(color)
    if not path:
        return {"ok": False, "error": "Pillow indisponible", "count": 0}
    try:
        from AppKit import NSImage, NSWorkspace
        image = NSImage.alloc().initWithContentsOfFile_(str(path))
        if image is None or not NSWorkspace.sharedWorkspace().setIcon_forFile_options_(image, str(bundle), 0):
            return {"ok": False, "error": "macOS a refusé de changer l'icône", "count": 0}
        (icons_dir() / _MAC_MARQUE).write_text(_norm_color(color), encoding="utf-8")
        return {"ok": True, "count": 1, "paths": [str(bundle)], "ico": str(path)}
    except Exception as e:
        return {"ok": False, "error": str(e), "count": 0}


def _sync_app_mac(color: str) -> None:
    """Pilote.app suit la couleur toute seule : au lancement et a chaque
    changement d'accent. Rien a faire si elle l'a deja (meme couleur notee et
    fichier « Icon\\r » present ; une mise a jour remplace le paquet et l'efface)."""
    try:
        import updater
        bundle = updater._bundle_mac()
        if bundle is None or updater.mac_a_deplacer():
            return
        marque = icons_dir() / _MAC_MARQUE
        deja = marque.read_text(encoding="utf-8").strip() if marque.exists() else ""
        if deja == _norm_color(color) and (bundle / "Icon\r").exists():
            return
        r = _apply_app_mac(color)
        print(f"[appicon] icone de Pilote.app : {r.get('ok')} {r.get('error') or ''}", flush=True)
    except Exception as e:
        print(f"[appicon] icone de Pilote.app KO : {e}", flush=True)


# ─── Application a la fenetre en cours ────────────────────────────────────────

def _main_hwnd() -> int:
    """HWND de la fenetre principale de CE process."""
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    found = []
    pid_here = os.getpid()

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def _cb(hwnd, _lparam):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == pid_here and user32.IsWindowVisible(hwnd):
            if not user32.GetWindow(hwnd, 4):        # GW_OWNER = 4 -> fenetre racine
                found.append(hwnd)
        return True

    try:
        user32.EnumWindows(_cb, 0)
    except Exception:
        pass
    if found:
        return found[0]
    return user32.FindWindowW(None, "Pilote") or 0


def apply_to_window(color: str) -> bool:
    """Change l'icone de la fenetre + de la vignette barre des taches (Mac : du Dock)."""
    if sys.platform == "darwin":
        ok = _apply_dock_mac(color)
        _sync_app_mac(color)
        return ok
    if sys.platform != "win32":
        return False
    path = ico_for(color)
    if not path:
        return False
    try:
        import ctypes
        user32 = ctypes.windll.user32
        hwnd = _main_hwnd()
        if not hwnd:
            return False

        IMAGE_ICON, LR_LOADFROMFILE, LR_DEFAULTSIZE = 1, 0x0010, 0x0040
        WM_SETICON, ICON_SMALL, ICON_BIG = 0x0080, 0, 1

        ok = False
        for which, cx, cy in ((ICON_SMALL, 16, 16), (ICON_BIG, 32, 32)):
            h = user32.LoadImageW(None, str(path), IMAGE_ICON, cx, cy,
                                  LR_LOADFROMFILE | LR_DEFAULTSIZE)
            if h:
                _LIVE_ICONS.append(h)
                user32.SendMessageW(hwnd, WM_SETICON, which, h)
                ok = True
        return ok
    except Exception as e:
        print(f"[appicon] application fenetre KO : {e}", flush=True)
        return False


# ─── Application aux raccourcis (Bureau / Demarrer / barre des taches) ────────

def _shortcut_candidates() -> list:
    """Raccourcis .lnk susceptibles de pointer sur Pilote."""
    if sys.platform != "win32":
        return []
    home = Path.home()
    appdata = Path(os.environ.get("APPDATA", home / "AppData" / "Roaming"))
    spots = [
        home / "Desktop",
        Path(os.environ.get("PUBLIC", "C:/Users/Public")) / "Desktop",
        appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs",
        appdata / "Microsoft" / "Internet Explorer" / "Quick Launch" / "User Pinned" / "TaskBar",
    ]
    out = []
    for spot in spots:
        if not spot.exists():
            continue
        try:
            for lnk in spot.rglob("*.lnk"):
                name = lnk.stem.lower()
                # Le raccourci de desinstallation garde l'icone d'origine
                if any(x in name for x in ("desinstall", "désinstall", "uninstall")):
                    continue
                if "pilote" in name or "suivi pea" in name or "suivi_pea" in name:
                    out.append(lnk)
        except Exception:
            continue
    return out


def apply_to_shortcuts(color: str) -> dict:
    """
    Repointe l'icone des raccourcis Pilote vers le .ico recolore.
    Passe par WScript.Shell (aucune dependance supplementaire).
    """
    if sys.platform != "win32":
        return {"ok": False, "error": "Windows uniquement", "count": 0}
    path = ico_for(color)
    if not path:
        return {"ok": False, "error": "Pillow indisponible", "count": 0}

    links = _shortcut_candidates()
    if not links:
        return {"ok": False, "error": "aucun raccourci Pilote trouve", "count": 0}

    ps_lines = ["$sh = New-Object -ComObject WScript.Shell"]
    for lnk in links:
        p = str(lnk).replace("'", "''")
        i = str(path).replace("'", "''")
        ps_lines.append(f"$s = $sh.CreateShortcut('{p}'); $s.IconLocation = '{i},0'; $s.Save()")
    # Force Windows a relire le cache d'icones
    ps_lines.append(
        "Add-Type -Namespace W -Name S -MemberDefinition "
        "'[DllImport(\"shell32.dll\")] public static extern void "
        "SHChangeNotify(int e, uint f, IntPtr a, IntPtr b);'; "
        "[W.S]::SHChangeNotify(0x8000000, 0, [IntPtr]::Zero, [IntPtr]::Zero)"
    )

    try:
        flags = 0
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            flags = subprocess.CREATE_NO_WINDOW
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", "; ".join(ps_lines)],
            capture_output=True, text=True, timeout=30, creationflags=flags,
        )
        if r.returncode != 0:
            return {"ok": False, "error": (r.stderr or "powershell KO").strip()[:300], "count": 0}
        return {"ok": True, "count": len(links),
                "paths": [str(l) for l in links], "ico": str(path)}
    except Exception as e:
        return {"ok": False, "error": str(e), "count": 0}
