"""
Low-level cryptographic helpers for the NDIC platform.

This module only deals with key objects and PEM strings.
Higher-level operations (sign, verify, hash chain) live in app/security.py.

Key format chosen: RSA-2048 with PSS padding and SHA-256.
RSA was chosen over Ed25519 because:
  - RSA private keys can be password-encrypted (PKCS#8), making external
    key-file management easier for Nigerian field operators.
  - Wider hardware-token support (YubiKey PKCS#11).
  - Ed25519 can be added as an alternative later via the same interface.
"""

from __future__ import annotations

import logging

from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.asymmetric.rsa import (
    RSAPrivateKey,
    RSAPublicKey,
)
from cryptography.hazmat.backends import default_backend

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class InvalidKeyError(ValueError):
    """Raised when a PEM string cannot be parsed as a valid RSA key."""


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def is_valid_rsa_public_key(pem_string: str) -> bool:
    """Return True if *pem_string* is a well-formed RSA public key."""
    try:
        pem_to_public_key(pem_string)
        return True
    except InvalidKeyError:
        return False


def is_valid_rsa_private_key(pem_string: str, password: bytes | None = None) -> bool:
    """Return True if *pem_string* is a well-formed RSA private key."""
    try:
        pem_to_private_key(pem_string, password=password)
        return True
    except InvalidKeyError:
        return False


# ---------------------------------------------------------------------------
# PEM → key object conversion
# ---------------------------------------------------------------------------

def pem_to_public_key(pem_string: str) -> RSAPublicKey:
    """
    Parse a PEM-encoded RSA public key.

    Raises:
        InvalidKeyError: if the PEM is malformed or not an RSA key.
    """
    if not pem_string or not pem_string.strip():
        raise InvalidKeyError("Public key PEM is empty")
    try:
        key = serialization.load_pem_public_key(
            pem_string.strip().encode(),
            backend=default_backend(),
        )
    except (ValueError, UnsupportedAlgorithm, TypeError) as exc:
        raise InvalidKeyError(f"Cannot parse public key PEM: {exc}") from exc

    if not isinstance(key, RSAPublicKey):
        raise InvalidKeyError("Key is not an RSA public key")
    return key


def pem_to_private_key(
    pem_string: str,
    password: bytes | None = None,
) -> RSAPrivateKey:
    """
    Parse a PEM-encoded RSA private key (PKCS#8 or traditional).

    Args:
        pem_string: PEM text of the private key.
        password:   Optional passphrase bytes for encrypted keys.

    Raises:
        InvalidKeyError: if the PEM is malformed or not an RSA key.
    """
    if not pem_string or not pem_string.strip():
        raise InvalidKeyError("Private key PEM is empty")
    try:
        key = serialization.load_pem_private_key(
            pem_string.strip().encode(),
            password=password,
            backend=default_backend(),
        )
    except (ValueError, UnsupportedAlgorithm, TypeError) as exc:
        raise InvalidKeyError(f"Cannot parse private key PEM: {exc}") from exc

    if not isinstance(key, RSAPrivateKey):
        raise InvalidKeyError("Key is not an RSA private key")
    return key


# ---------------------------------------------------------------------------
# Key object → PEM serialisation
# ---------------------------------------------------------------------------

def public_key_to_pem(key: RSAPublicKey) -> str:
    """Serialise an RSA public key to PEM (SubjectPublicKeyInfo)."""
    return key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()


def private_key_to_pem(
    key: RSAPrivateKey,
    password: bytes | None = None,
) -> str:
    """
    Serialise an RSA private key to PEM (PKCS#8).

    If *password* is provided the key is AES-256-CBC encrypted.
    Private keys should NEVER be stored in the database or logged.
    """
    encryption = (
        serialization.BestAvailableEncryption(password)
        if password
        else serialization.NoEncryption()
    )
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=encryption,
    ).decode()


# ---------------------------------------------------------------------------
# PSS padding factory (reused in security.py)
# ---------------------------------------------------------------------------

def pss_padding() -> padding.PSS:
    """Return the standard RSA-PSS padding configuration used platform-wide."""
    return padding.PSS(
        mgf=padding.MGF1(hashes.SHA256()),
        salt_length=padding.PSS.MAX_LENGTH,
    )
