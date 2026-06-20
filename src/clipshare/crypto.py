"""Cryptography: Diffie-Hellman key exchange and AES-GCM encryption.

Uses the `cryptography` library for AES-GCM and standard library for DH.
"""

import base64
import hashlib
import logging
import os
from typing import Tuple

logger = logging.getLogger(__name__)

# --- Diffie-Hellman Key Exchange (pure stdlib) ---

# RFC 3526 - Group 14 (2048-bit MODP)
DH_PRIME = int(
    "FFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD1"
    "29024E088A67CC74020BBEA63B139B22514A08798E3404DD"
    "EF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245"
    "E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7ED"
    "EE386BFB5A899FA5AE9F24117C4B1FE649286651ECE45B3D"
    "C2007CB8A163BF0598DA48361C55D39A69163FA8FD24CF5F"
    "83655D23DCA3AD961C62F356208552BB9ED529077096966D"
    "670C354E4ABC9804F1746C08CA18217C32905E462E36CE3B"
    "E39E772C180E86039B2783A2EC07A28FB5C55DF06F4C52C9"
    "DE2BCBF6955817183995497CEA956AE515D2261898FA0510"
    "15728E5A8AACAA68FFFFFFFFFFFFFFFF",
    16,
)

DH_GENERATOR = 2

# DH private key size (256 bits = 32 bytes)
DH_KEY_SIZE = 32


def generate_dh_keypair() -> Tuple[str, str]:
    """Generate a Diffie-Hellman key pair.

    Returns:
        (private_key_b64, public_key_b64): Base64-encoded strings.
    """
    private_key_bytes = os.urandom(DH_KEY_SIZE)
    private_key = int.from_bytes(private_key_bytes, "big") % DH_PRIME
    public_key = pow(DH_GENERATOR, private_key, DH_PRIME)

    private_key_b64 = base64.b64encode(private_key.to_bytes(DH_KEY_SIZE * 8, "big")).decode("utf-8")
    public_key_b64 = base64.b64encode(public_key.to_bytes(256, "big")).decode("utf-8")

    return private_key_b64, public_key_b64


def compute_shared_secret(private_key_b64: str, peer_public_key_b64: str) -> bytes:
    """Compute the shared secret using DH.

    Args:
        private_key_b64: Our base64-encoded private key.
        peer_public_key_b64: Peer's base64-encoded public key.

    Returns:
        32-byte shared secret (SHA-256 of DH result).
    """
    private_key_int = int.from_bytes(base64.b64decode(private_key_b64), "big")
    peer_public_int = int.from_bytes(base64.b64decode(peer_public_key_b64), "big")

    shared_int = pow(peer_public_int, private_key_int, DH_PRIME)
    shared_bytes = shared_int.to_bytes(256, "big")

    # Derive a 32-byte AES key using SHA-256
    aes_key = hashlib.sha256(shared_bytes).digest()
    return aes_key


def aes_key_to_base64(aes_key: bytes) -> str:
    return base64.b64encode(aes_key).decode("utf-8")


def aes_key_from_base64(key_b64: str) -> bytes:
    return base64.b64decode(key_b64)


# --- AES-GCM Encryption (requires `cryptography` library) ---

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    _HAS_AES = True
except ImportError:
    _HAS_AES = False
    logger.warning("cryptography library not available; AES encryption disabled")


def encrypt_data(aes_key: bytes, plaintext: bytes) -> bytes:
    """Encrypt data using AES-256-GCM.

    Args:
        aes_key: 32-byte AES key.
        plaintext: Data to encrypt.

    Returns:
        nonce (12 bytes) + ciphertext + tag (16 bytes).
    """
    if not _HAS_AES:
        raise RuntimeError("cryptography library is required for AES encryption")

    nonce = os.urandom(12)
    aesgcm = AESGCM(aes_key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return nonce + ciphertext


def decrypt_data(aes_key: bytes, encrypted: bytes) -> bytes:
    """Decrypt data using AES-256-GCM.

    Args:
        aes_key: 32-byte AES key.
        encrypted: nonce (12 bytes) + ciphertext + tag (16 bytes).

    Returns:
        Decrypted plaintext.
    """
    if not _HAS_AES:
        raise RuntimeError("cryptography library is required for AES encryption")

    nonce = encrypted[:12]
    ciphertext = encrypted[12:]
    aesgcm = AESGCM(aes_key)
    return aesgcm.decrypt(nonce, ciphertext, None)