"""
plateforme.py — Ce qui differe entre Windows et Mac, regroupe ici.

Pilote est une seule application pour les deux systemes (decision du
11/10/2026, voir docs/mac.md) : un seul code, un seul format de donnees. Ce
qui ne peut pas s'ecrire pareil sur les deux vit dans ce module, et le chemin
Windows y reste celui d'avant.
"""
from __future__ import annotations

import os
import re
import sys
import subprocess


def certificats_mac() -> None:
    """Mac : donne a Python les certificats fournis avec macOS quand il n'en a pas.

    Pour verifier Yahoo, Gmail et GitHub, le Python compile dans l'app ne lit
    pas le Trousseau du Mac : il cherche un fichier a l'endroit prevu par le
    Python qui a fabrique l'app (/Library/Frameworks/Python.framework/...).
    Sur la machine de GitHub il existe, sur un Mac ordinaire non : sans ce
    repli, aucune connexion HTTPS n'aboutirait (constate le 12/10/2026, voir
    docs/mac.md). /etc/ssl/cert.pem est livre avec macOS. A appeler avant le
    premier contexte TLS (server._SSL_CTX se cree a l'import de server)."""
    if sys.platform != "darwin" or os.environ.get("SSL_CERT_FILE"):
        return
    import ssl
    p = ssl.get_default_verify_paths()     # cafile/capath : None s'ils n'existent pas
    if p.cafile or p.capath:
        return
    if os.path.isfile("/etc/ssl/cert.pem"):
        os.environ["SSL_CERT_FILE"] = "/etc/ssl/cert.pem"


def zone_ecran_mac() -> tuple:
    """Mac : zone utile de l'ecran principal, sans la barre des menus ni le Dock,
    en points et origine en haut a gauche comme pywebview : (x, y, largeur, hauteur)."""
    import AppKit
    AppKit.NSApplication.sharedApplication()     # NSScreen a besoin de l'application
    ecran = AppKit.NSScreen.mainScreen() or AppKit.NSScreen.screens()[0]
    f, v = ecran.frame(), ecran.visibleFrame()
    haut = (f.origin.y + f.size.height) - (v.origin.y + v.size.height)
    return (int(v.origin.x - f.origin.x), int(haut), int(v.size.width), int(v.size.height))


# Mac : menus et boites de dialogue de pywebview en francais (cles de
# webview/localization.py ; le nom de l'app est ajoute a « Quitter », etc.)
LOCALISATION_MAC = {
    "global.quitConfirmation": "Voulez-vous vraiment quitter ?",
    "global.ok": "OK",
    "global.quit": "Quitter",
    "global.cancel": "Annuler",
    "global.saveFile": "Enregistrer le fichier",
    "cocoa.menu.about": "À propos de",
    "cocoa.menu.services": "Services",
    "cocoa.menu.view": "Présentation",
    "cocoa.menu.edit": "Édition",
    "cocoa.menu.hide": "Masquer",
    "cocoa.menu.hideOthers": "Masquer les autres",
    "cocoa.menu.showAll": "Tout afficher",
    "cocoa.menu.quit": "Quitter",
    "cocoa.menu.fullscreen": "Passer en plein écran",
    "cocoa.menu.cut": "Couper",
    "cocoa.menu.copy": "Copier",
    "cocoa.menu.paste": "Coller",
    "cocoa.menu.selectAll": "Tout sélectionner",
}


def ocr_mac(image_path: str) -> dict:
    """Mac : lecture du texte d'une image par Vision d'Apple (hors ligne).

    Rend la meme chose qu'ocr_win.ps1 sous Windows, pour que sante.py lise les
    deux pareil : {ok, lang, width, height, angle, words: [{t, l, x, y, w, h}]},
    positions en pixels depuis le coin haut gauche. Vision rend des lignes : la
    boite de chaque mot vient de boundingBoxForRange sur la ligne. Correction
    linguistique coupee : elle « corrige » les nombres (72,4 kg, 18,5 %)."""
    try:
        import Vision
        from Foundation import NSURL
        from PIL import Image
    except Exception as e:
        return {"ok": False, "error": f"Vision indisponible : {e}"}
    try:
        with Image.open(image_path) as im:
            largeur, hauteur = im.size
            gris = im.convert("L")
        url = NSURL.fileURLWithPath_(str(image_path))
        lecteur = Vision.VNImageRequestHandler.alloc().initWithURL_options_(url, None)
        req = Vision.VNRecognizeTextRequest.alloc().init()
        req.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
        req.setRecognitionLanguages_(["fr-FR", "en-US"])
        req.setUsesLanguageCorrection_(False)
        ok, err = lecteur.performRequests_error_([req], None)
        if not ok:
            return {"ok": False, "error": str(err)}

        def boite(r) -> dict:     # CGRect normalise, origine en bas a gauche
            return {"x": int(r.origin.x * largeur),
                    "y": int((1 - r.origin.y - r.size.height) * hauteur),
                    "w": int(r.size.width * largeur),
                    "h": int(r.size.height * hauteur)}

        def serrer(b: dict) -> dict:
            """Boite resserree sur les pixels du mot. Vision rend la hauteur de
            toute la ligne (marges comprises), Windows une boite au ras des
            lettres ; or sante.py regroupe lignes et libelles selon la hauteur
            des mots (essai du 12/10/2026 : 18,5 % pris pour l'IMC sans ce
            resserrement). Fond = teinte la plus frequente de la boite."""
            x0, y0 = max(0, b["x"]), max(0, b["y"])
            x1, y1 = min(largeur, b["x"] + b["w"]), min(hauteur, b["y"] + b["h"])
            if x1 - x0 < 2 or y1 - y0 < 2:
                return b
            zone = gris.crop((x0, y0, x1, y1))
            hist = zone.histogram()
            fond = hist.index(max(hist))
            bb = zone.point(lambda p: 255 if abs(p - fond) > 60 else 0).getbbox()
            if not bb:
                return b
            return {"x": x0 + bb[0], "y": y0 + bb[1], "w": bb[2] - bb[0], "h": bb[3] - bb[1]}

        mots = []
        for li, obs in enumerate(req.results() or [], start=1):
            cands = obs.topCandidates_(1)
            if not cands:
                continue
            cand = cands[0]
            texte = str(cand.string())
            for m in re.finditer(r"\S+", texte):
                rect, _ = cand.boundingBoxForRange_error_((m.start(), m.end() - m.start()), None)
                b = boite(rect.boundingBox()) if rect is not None else boite(obs.boundingBox())
                s = serrer(b)
                mots.append(dict(t=m.group(0), l=li, brut=[b["x"], b["y"], b["w"], b["h"]], **s))
        return {"ok": True, "lang": "fr-FR", "width": largeur, "height": hauteur,
                "angle": 0, "words": mots}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def ouvrir(chemin: str) -> None:
    """Ouvre un fichier ou un dossier avec l'application par defaut du systeme
    (Explorateur sous Windows, Finder sur Mac). Leve une exception en cas d'echec."""
    if sys.platform == "win32":
        os.startfile(chemin)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", chemin])
    else:
        subprocess.Popen(["xdg-open", chemin])


# ─── Mac : pont JS <-> Python de pywebview sans eval ──────────────────────────
# La CSP de la page (server._CSP) interdit d'evaluer du texte comme du code :
# pas de 'unsafe-eval'. Sous Windows, WebView2 exempte le script que pywebview
# injecte ; WebKit (Mac) non. Constate le 11/10/2026 sur le build de test :
# « EvalError ... 'unsafe-eval' », pont vide (0 fonction), page muette, fenetre
# ouverte seulement par le delai de secours.
#
# pywebview 6.2.1 evalue du texte a deux endroits, adaptes ici plutot que
# d'affaiblir la CSP :
#   1. api.js fabrique chaque fonction du pont avec new Function(...) : on la
#      remplace par une fermeture qui fait exactement la meme chose ;
#   2. chaque reponse de Python repart vers la page par Window.evaluate_js,
#      qui enveloppe le code dans eval() : la fenetre principale passe par
#      run_js, qui l'execute tel quel (la valeur rendue n'y sert pas).
# Version de pywebview epinglee (requirements.txt). Si le texte vise change,
# la sortie le dit et le test du build Mac montre « pont Python false ».

_NEW_FUNCTION = re.compile(r"new Function\(\s*sanitize_params\(params\),\s*funcBody\s*\)")

# Meme corps que funcBody dans api.js, sans passer par du texte
_FERMETURE = """(function (nom) {
        return function () {
          var __id = (Math.random() + "").substring(2);
          var promise = new Promise(function (resolve, reject) {
            window.pywebview._checkValue(nom, resolve, reject, __id);
          });
          window.pywebview._jsApiCallback(nom, Array.prototype.slice.call(arguments), __id);
          return promise;
        };
      })(funcName)"""


def adapter_js_pywebview(js: str) -> str:
    """Le script de pywebview, sans new Function (voir plus haut)."""
    js, n = _NEW_FUNCTION.subn(lambda m: _FERMETURE, js)
    if n != 1:
        print(f"[plateforme] pont pywebview non adapte : {n} new Function remplace(s)",
              flush=True)
    return js


def adapter_pont_mac(fenetre) -> None:
    """A appeler sur Mac apres create_window et avant webview.start()."""
    import webview.util as util
    charger = util.load_js_files

    def load_js_files(window, platform):
        js, fin = charger(window, platform)
        return adapter_js_pywebview(js), fin

    util.load_js_files = load_js_files
    fenetre.evaluate_js = lambda script, callback=None: fenetre.run_js(script)
