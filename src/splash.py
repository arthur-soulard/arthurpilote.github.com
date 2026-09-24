"""
splash.py — Petite fenetre de chargement affichee au lancement de Pilote.

La fenetre principale est creee CACHEE et ne s'ouvre qu'une fois l'accueil
pret : boot() (index.html) appelle Api.app_ready(), qui la montre et ferme
celle-ci. En attendant, on voit le logo a la couleur d'accent, le nom et
trois points qui s'allument tour a tour.

Le HTML est construit ici plutot que dans un fichier a part : un splash.html
devrait etre ajoute aux datas de build/pilote.spec, et l'oublier ne se
verrait que dans l'exe compile (le meme piege que ocr_win.ps1). Les polices
viennent de ui/vendor/fonts, deja embarque, inlinees en data: — la page n'a
pas d'origine et ne peut rien demander au serveur local.
"""
from __future__ import annotations

import base64
import re
from pathlib import Path

SIZE = (300, 230)

# Memes jetons que :root et html[data-theme="dark"] dans index.html
_THEMES = {
    "light": {"bg": "#f1ebe0", "txt": "#2a231b", "txt2": "#6a5e4d", "brd": "rgba(70,45,20,0.17)"},
    "dark":  {"bg": "#191613", "txt": "#efe7d9", "txt2": "#b1a592", "brd": "rgba(255,230,200,0.13)"},
}
_DEFAULT_ACCENT = "#9c4a7a"   # ACCENT_DEFAULT (index.html) / DEFAULT_COLOR (appicon.py)


def background(theme: str) -> str:
    return _THEMES.get(theme, _THEMES["light"])["bg"]


def _font_uri(fonts_dir: Path, name: str) -> str:
    try:
        data = (fonts_dir / name).read_bytes()
        return "data:font/woff2;base64," + base64.b64encode(data).decode("ascii")
    except Exception:
        return ""


def build_html(ui_dir: Path, accent: str, theme: str) -> str:
    t = _THEMES.get(theme, _THEMES["light"])
    # L'accent finit dans du CSS : seul un #rrggbb passe
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", accent or ""):
        accent = _DEFAULT_ACCENT
    fonts = Path(ui_dir) / "vendor" / "fonts"
    serif = _font_uri(fonts, "newsreader-italic-latin.woff2")
    sans = _font_uri(fonts, "onest-latin.woff2")
    faces = ""
    if serif:
        faces += ("@font-face{font-family:'Newsreader';font-style:italic;"
                  "font-weight:400 600;src:url(%s) format('woff2')}" % serif)
    if sans:
        faces += ("@font-face{font-family:'Onest';font-style:normal;"
                  "font-weight:400 600;src:url(%s) format('woff2')}" % sans)

    return """<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8"><title>Pilote</title>
<style>
%(faces)s
:root { --bg:%(bg)s; --txt:%(txt)s; --txt2:%(txt2)s; --brd:%(brd)s; --accent:%(accent)s; }
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body { height: 100%%; background: var(--bg); overflow: hidden; user-select: none; cursor: default; }
body {
  display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 10px;
  border: 1px solid var(--brd); color: var(--txt);
  font-family: "Onest", system-ui, sans-serif;
}
.logo {
  width: 64px; height: 64px; border-radius: 17px; background: var(--accent); color: #fff;
  display: flex; align-items: center; justify-content: center;
  font-family: "Newsreader", Georgia, serif; font-style: italic; font-weight: 500; font-size: 40px;
}
.nom { font-family: "Newsreader", Georgia, serif; font-style: italic; font-size: 24px; margin-top: 4px; }
.dots { display: flex; gap: 7px; margin-top: 8px; }
.dots i { width: 7px; height: 7px; border-radius: 50%%; background: var(--accent); opacity: .25;
          animation: pulse 1.2s ease-in-out infinite; }
.dots i:nth-child(2) { animation-delay: .2s; }
.dots i:nth-child(3) { animation-delay: .4s; }
@keyframes pulse { 0%%, 100%% { opacity: .25; } 40%% { opacity: 1; } }
/* Un indicateur de chargement doit rester visible : sans animation, les
   points s'allument quand meme, plus lentement (opacite seule). */
@media (prefers-reduced-motion: reduce) { .dots i { animation-duration: 2.4s; } }
.txt { font-size: 12.5px; color: var(--txt2); }
</style></head>
<body>
  <div class="logo">P</div>
  <div class="nom">Pilote</div>
  <div class="dots" aria-hidden="true"><i></i><i></i><i></i></div>
  <div class="txt" role="status">Chargement de tes donn&eacute;es&hellip;</div>
</body></html>""" % {"faces": faces, "accent": accent, **t}
