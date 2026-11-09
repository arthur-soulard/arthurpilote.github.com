"""
chiffrement.py — Archives de sauvegarde chiffrees par un mot de passe.

Bibliotheque standard seulement (pas de dependance a installer), avec des
briques eprouvees, assemblees de la facon la plus simple possible :

  * cle tiree du mot de passe : PBKDF2-HMAC-SHA256, 600 000 tours, sel
    aleatoire de 16 octets -> 64 octets (32 pour chiffrer, 32 pour signer) ;
  * chiffrement : flux SHAKE-256 (une fonction de la famille SHA-3, sortie de
    longueur libre) tire de la cle, d'un nonce aleatoire de 16 octets propre a
    chaque archive et d'un compteur de bloc, combine aux octets par XOR ;
  * integrite : HMAC-SHA256 sur l'en-tete et tout le chiffre (« chiffrer puis
    signer »). Un mauvais mot de passe ou une archive abimee sont refuses
    AVANT qu'un seul octet dechiffre ne serve.

Format d'un fichier (.pilote) :
    MAGIC (16 octets) | longueur de l'en-tete (4 octets) | en-tete JSON
    | octets chiffres | HMAC (32 octets)

La cle derivee (et jamais le mot de passe) est gardee sur le PC par Windows
(DPAPI) ou par le Trousseau du Mac, comme le code Gmail d'Actus : les
sauvegardes automatiques n'ont pas a le redemander. Sans le mot de passe, une
archive est perdue : il n'existe aucune porte derobee.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import struct
import sys

MAGIC = b"PILOTE-CHIFFRE\x00\x01"
ITERATIONS = 600_000
BLOC = 1 << 20            # 1 Mio : un appel a SHAKE-256 par bloc
_TAG = 32


class MotDePasseIncorrect(ValueError):
    """Le HMAC ne correspond pas : mauvais mot de passe ou archive abimee."""


def deriver(mdp: str, sel: bytes, iterations: int = ITERATIONS) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", mdp.encode("utf-8"), sel, iterations, 64)


def nouveau_sel() -> bytes:
    return os.urandom(16)


def empreinte(cle: bytes) -> str:
    """Identifiant court d'une cle (pas la cle) : dit si une archive a ete
    faite avec le mot de passe actuel, sans rien reveler de celui-ci."""
    return hmac.new(cle, b"pilote-empreinte", hashlib.sha256).hexdigest()[:16]


def _flux(cle_chiffre: bytes, nonce: bytes, i: int, n: int) -> bytes:
    return hashlib.shake_256(b"pilote-flux" + cle_chiffre + nonce + struct.pack(">Q", i)).digest(n)


def _xor(a: bytes, b: bytes) -> bytes:
    n = len(a)
    return (int.from_bytes(a, "little") ^ int.from_bytes(b, "little")).to_bytes(n, "little")


def chiffrer_flux(src, dst, cle: bytes, sel: bytes, iterations: int = ITERATIONS) -> None:
    """Lit src (fichier binaire ouvert) jusqu'au bout et ecrit l'archive
    chiffree dans dst."""
    nonce = os.urandom(16)
    entete = json.dumps({"v": 1, "kdf": "pbkdf2-sha256", "iter": iterations,
                         "sel": sel.hex(), "nonce": nonce.hex(),
                         "flux": "shake256", "mac": "hmac-sha256",
                         "empreinte": empreinte(cle)}).encode("ascii")
    debut = MAGIC + struct.pack(">I", len(entete)) + entete
    mac = hmac.new(cle[32:], debut, hashlib.sha256)
    dst.write(debut)
    i = 0
    while True:
        bloc = src.read(BLOC)
        if not bloc:
            break
        c = _xor(bloc, _flux(cle[:32], nonce, i, len(bloc)))
        mac.update(c)
        dst.write(c)
        i += 1
    dst.write(mac.digest())


def lire_entete(chemin) -> dict:
    """En-tete d'une archive chiffree, ou {} si le fichier n'en est pas une."""
    try:
        with open(chemin, "rb") as f:
            if f.read(len(MAGIC)) != MAGIC:
                return {}
            (n,) = struct.unpack(">I", f.read(4))
            if n > 4096:
                return {}
            return json.loads(f.read(n).decode("ascii"))
    except Exception:
        return {}


def est_chiffre(chemin) -> bool:
    return bool(lire_entete(chemin))


def dechiffrer_flux(chemin, dst, cle: bytes) -> None:
    """Dechiffre le fichier `chemin` dans dst (fichier temporaire : il ne
    doit servir qu'une fois la fonction revenue sans erreur). Leve
    MotDePasseIncorrect si le HMAC ne correspond pas."""
    taille = os.path.getsize(chemin)
    with open(chemin, "rb") as f:
        magic = f.read(len(MAGIC))
        if magic != MAGIC:
            raise ValueError("pas une archive chiffree de Pilote")
        brut_n = f.read(4)
        (n,) = struct.unpack(">I", brut_n)
        entete_brut = f.read(n)
        entete = json.loads(entete_brut.decode("ascii"))
        nonce = bytes.fromhex(entete["nonce"])
        mac = hmac.new(cle[32:], magic + brut_n + entete_brut, hashlib.sha256)
        reste = taille - len(MAGIC) - 4 - n - _TAG
        if reste < 0:
            raise MotDePasseIncorrect("archive tronquee")
        i = 0
        while reste > 0:
            c = f.read(min(BLOC, reste))
            if not c:
                raise MotDePasseIncorrect("archive tronquee")
            reste -= len(c)
            mac.update(c)
            dst.write(_xor(c, _flux(cle[:32], nonce, i, len(c))))
            i += 1
        tag = f.read(_TAG)
    if not hmac.compare_digest(tag, mac.digest()):
        raise MotDePasseIncorrect("mot de passe incorrect ou archive abimee")


# ─── La cle gardee sur le PC ─────────────────────────────────────────────────
# Windows : DPAPI (celle d'Actus), liee a la session Windows. Mac : Trousseau,
# sous un compte fixe (la sauvegarde est au niveau de l'installation, pas d'un
# utilisateur de Pilote ; actus._chiffrer range par utilisateur).

_SERVICE_MAC = "Pilote Sauvegarde"


def _compte_mac() -> str:
    import storage
    return "pilote-sauvegarde-" + hashlib.sha256(str(storage.get_app_dir()).encode("utf-8")).hexdigest()[:16]


def garder_cle(cle: bytes) -> str:
    texte = cle.hex()
    if sys.platform == "win32":
        import actus
        return actus._chiffrer(texte)
    if sys.platform == "darwin":
        import actus
        compte = _compte_mac()
        r = actus._security("add-generic-password", "-U", "-s", _SERVICE_MAC, "-a", compte,
                            "-l", "Pilote : cle des sauvegardes chiffrees", "-w", texte)
        if r.returncode != 0:
            raise OSError((r.stderr or "").strip() or "le Trousseau a refusé la clé")
        return "trousseau:" + compte
    return "b64:" + base64.b64encode(texte.encode("ascii")).decode("ascii")


def relire_cle(secret: str) -> bytes:
    import actus
    if secret.startswith("trousseau:"):
        return bytes.fromhex(actus._dechiffrer(secret, _SERVICE_MAC))
    return bytes.fromhex(actus._dechiffrer(secret))


def oublier_cle(secret: str) -> None:
    if secret.startswith("trousseau:"):
        import actus
        actus._oublier(secret, _SERVICE_MAC)
