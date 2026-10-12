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
