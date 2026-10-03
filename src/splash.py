"""
splash.py — Petite fenetre de chargement affichee au lancement de Pilote.

La fenetre principale est creee CACHEE et ne s'ouvre qu'une fois l'accueil
pret : boot() (index.html) appelle Api.app_ready(), qui la montre et ferme
celle-ci. En attendant, animation « Signature » (choisie par Arthur le
03/10/2026 parmi trois maquettes) : le logo arrive en rebondissant, le P
monte dans la tuile, « Pilote » s'ecrit lettre par lettre ; puis, en
boucle, un reflet passe sur la tuile, des ondes en partent et une barre
glisse dessous. Rien que transform et opacity : pendant le chargement, le
processeur est pris par Python et WebView2, ces proprietes-la restent
fluides.

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

SIZE = (340, 260)

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
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  border: 1px solid var(--brd); color: var(--txt);
  font-family: "Onest", system-ui, sans-serif;
}
/* Logo : halo qui respire, deux ondes, tuile qui rebondit, P qui monte, reflet */
.logo { position: relative; width: 72px; height: 72px; }
.halo {
  position: absolute; inset: -80px; border-radius: 50%%;
  background: radial-gradient(closest-side, color-mix(in srgb, var(--accent) 24%%, transparent), transparent);
  animation: halo 3.4s .5s ease-in-out infinite alternate both;
}
@keyframes halo { from { opacity: .35; transform: scale(.8); } to { opacity: 1; transform: scale(1.08); } }
.onde {
  position: absolute; inset: 0; border-radius: 19px; border: 2px solid var(--accent); opacity: 0;
  animation: onde 2.6s .75s cubic-bezier(.15,.6,.3,1) infinite;
}
.onde + .onde { animation-delay: 2.05s; }
@keyframes onde { 0%% { transform: scale(1); opacity: .6; } 100%% { transform: scale(1.85); opacity: 0; } }
.tuile {
  position: relative; width: 72px; height: 72px; border-radius: 19px; overflow: hidden;
  background: var(--accent); color: #fff; display: flex; align-items: center; justify-content: center;
  font-family: "Newsreader", Georgia, serif; font-style: italic; font-weight: 500; font-size: 44px;
  box-shadow: 0 12px 26px -12px color-mix(in srgb, var(--accent) 80%%, transparent);
  animation: pop .8s cubic-bezier(.2,.9,.3,1.25) both;
}
@keyframes pop { 0%% { transform: scale(.25) rotate(-14deg); opacity: 0; } 55%% { opacity: 1; } 100%% { transform: none; opacity: 1; } }
.tuile .p { display: block; line-height: 1; animation: monte .65s .3s cubic-bezier(.2,.8,.2,1) both; }
@keyframes monte { from { transform: translateY(115%%); } to { transform: none; } }
.reflet {
  position: absolute; inset: -30%%; transform: translateX(-130%%);
  background: linear-gradient(105deg, transparent 38%%, rgba(255,255,255,.5) 50%%, transparent 62%%);
  animation: reflet 2.8s 1.1s ease-in-out infinite;
}
@keyframes reflet { 0%% { transform: translateX(-130%%); } 42%%, 100%% { transform: translateX(130%%); } }
/* Nom ecrit lettre par lettre */
.nom {
  display: flex; overflow: hidden; margin-top: 16px; padding: 0 3px .14em;
  font-family: "Newsreader", Georgia, serif; font-style: italic; font-size: 31px; line-height: 1.1;
}
.nom span { display: inline-block; animation: lettre .6s cubic-bezier(.2,.8,.2,1) both; }
.nom span:nth-child(1) { animation-delay: .55s; } .nom span:nth-child(2) { animation-delay: .61s; }
.nom span:nth-child(3) { animation-delay: .67s; } .nom span:nth-child(4) { animation-delay: .73s; }
.nom span:nth-child(5) { animation-delay: .79s; } .nom span:nth-child(6) { animation-delay: .85s; }
@keyframes lettre { from { transform: translateY(105%%) rotate(10deg); opacity: 0; } to { transform: none; opacity: 1; } }
/* Barre de chargement : un trait qui glisse en boucle */
.piste {
  width: 136px; height: 3px; border-radius: 9px; background: var(--brd); overflow: hidden; margin-top: 12px;
  animation: fondu .4s 1.15s both;
}
.piste i {
  display: block; width: 42%%; height: 100%%; border-radius: 9px; background: var(--accent);
  animation: glisse 1.5s 1.15s cubic-bezier(.65,0,.35,1) infinite;
}
@keyframes glisse { from { transform: translateX(-100%%); } to { transform: translateX(240%%); } }
.txt { font-size: 12.5px; color: var(--txt2); margin-top: 10px; animation: fondu .5s 1.3s both; }
@keyframes fondu { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: none; } }
/* Mouvement reduit : tout s'affiche d'emblee, sans rebond ni onde. La barre
   continue de glisser, plus lentement : un indicateur de chargement doit
   rester visible. */
@media (prefers-reduced-motion: reduce) {
  .halo, .onde, .tuile, .tuile .p, .reflet, .nom span, .piste, .txt { animation: none; }
  .halo { opacity: .7; }
  .piste i { animation-duration: 3s; animation-delay: 0s; }
}
</style></head>
<body>
  <div class="logo" aria-hidden="true">
    <div class="halo"></div><i class="onde"></i><i class="onde"></i>
    <div class="tuile"><span class="p">P</span><i class="reflet"></i></div>
  </div>
  <div class="nom" aria-hidden="true"><span>P</span><span>i</span><span>l</span><span>o</span><span>t</span><span>e</span></div>
  <div class="piste" aria-hidden="true"><i></i></div>
  <div class="txt" role="status">Chargement de tes donn&eacute;es&hellip;</div>
</body></html>""" % {"faces": faces, "accent": accent, **t}
