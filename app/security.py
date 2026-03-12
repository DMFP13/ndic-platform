"""
NDIC Cryptographic Security Layer
──────────────────────────────────
Provides:
  - RSA-2048 key-pair generation
  - RSA-PSS / SHA-256 signing and verification
  - SHA-256 payload hashing and hash-chain computation
  - JWT creation and verification (HS256)

Design principles
-----------------
* Private keys are NEVER stored by this platform. Organisations generate
  their keys externally and register only the public key in the database.
* All signing is performed with `cryptography` (PyCA), not pycryptodome.
* The `canonical_payload` function produces a deterministic JSON
  serialisation (sorted keys, no whitespace) so that the same dict always
  produces the same hash regardless of insertion order.
* JWT sub-claims carry only opaque IDs; no PII is embedded.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa

from app.utils.crypto_utils import (
    InvalidKeyError,
    pem_to_private_key,
    pem_to_public_key,
    private_key_to_pem,
    public_key_to_pem,
    pss_padding,
)

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------


class SignatureVerificationError(ValueError):
    """Raised when a submitted signature does not match the actor's public key."""


class ChainIntegrityError(RuntimeError):
    """Raised when the ledger hash chain contains a broken link (tampering)."""


class TokenError(ValueError):
    """Raised on JWT parse/expiry errors."""


# ---------------------------------------------------------------------------
# Key generation
# ---------------------------------------------------------------------------


def generate_keypair(key_size: int = 2048) -> tuple[str, str]:
    """
    Generate an RSA key pair.

    Returns:
        (public_key_pem, private_key_pem) — both as PEM strings.

    The public key is safe to store in the database (users.public_key).
    The private key MUST be handed to the actor and never stored here.

    Example::

        pub_pem, priv_pem = generate_keypair()
        # Store pub_pem in DB; give priv_pem to the organisation.
    """
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=key_size,
    )
    public_key = private_key.public_key()
    return public_key_to_pem(public_key), private_key_to_pem(private_key)


# ---------------------------------------------------------------------------
# Canonical payload serialisation
# ---------------------------------------------------------------------------


def canonical_payload(data: dict[str, Any]) -> bytes:
    """
    Produce a deterministic UTF-8 byte representation of *data*.

    Rules:
      - Keys are sorted recursively.
      - No extra whitespace.
      - datetime values are serialised as ISO-8601 strings with UTC offset.
      - UUID values are serialised as lowercase hex strings.

    This function is the single source of truth for what bytes are hashed
    and signed; any deviation would break signature verification.
    """

    def _default(obj: Any) -> Any:
        if isinstance(obj, datetime):
            if obj.tzinfo is None:
                obj = obj.replace(tzinfo=timezone.utc)
            return obj.isoformat()
        if isinstance(obj, uuid.UUID):
            return str(obj)
        raise TypeError(f"Object of type {type(obj)} is not JSON serialisable")

    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=_default).encode("utf-8")


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------


def hash_payload(data: dict[str, Any]) -> str:
    """
    Compute the SHA-256 hex digest of the canonical JSON of *data*.

    Returns:
        64-character lowercase hex string.
    """
    return hashlib.sha256(canonical_payload(data)).hexdigest()


def compute_chain_hash(payload_hash: str, previous_hash: str | None) -> str:
    """
    Compute the hash-chain link for a new ledger entry.

    chain_input = payload_hash || (previous_hash OR "GENESIS")
    chain_hash  = SHA-256(chain_input)

    The chain_hash is stored as *previous_hash* of the NEXT entry,
    creating a tamper-evident linked structure.

    Returns:
        64-character lowercase hex string.
    """
    anchor = previous_hash if previous_hash else "GENESIS"
    chain_input = (payload_hash + anchor).encode("utf-8")
    return hashlib.sha256(chain_input).hexdigest()


# ---------------------------------------------------------------------------
# Signing
# ---------------------------------------------------------------------------


def sign_data(data: dict[str, Any], private_key_pem: str) -> str:
    """
    Sign the canonical JSON of *data* with the given RSA private key.

    Algorithm: RSA-PSS with MGF1-SHA-256, maximum salt length.

    Args:
        data:            The dict to be signed (will be canonicalised).
        private_key_pem: PEM-encoded RSA private key (unencrypted).

    Returns:
        URL-safe base64-encoded signature string (no padding).

    Raises:
        InvalidKeyError: if the PEM cannot be parsed.
    """
    private_key = pem_to_private_key(private_key_pem)
    message = canonical_payload(data)
    raw_sig = private_key.sign(message, pss_padding(), hashes.SHA256())
    return base64.urlsafe_b64encode(raw_sig).decode("ascii").rstrip("=")


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------


def verify_signature(
    data: dict[str, Any],
    signature_b64: str,
    public_key_pem: str,
) -> bool:
    """
    Verify that *signature_b64* is a valid RSA-PSS signature of *data*
    using *public_key_pem*.

    Returns:
        True if the signature is valid.

    Raises:
        SignatureVerificationError: if the signature is invalid or the key
            cannot be parsed.  Callers should treat this as a hard failure,
            not just a False return, because an invalid signature indicates
            either tampering or a misconfigured key — both warrant an audit
            trail, not silent failure.
    """
    try:
        public_key = pem_to_public_key(public_key_pem)
    except InvalidKeyError as exc:
        raise SignatureVerificationError(f"Malformed public key: {exc}") from exc

    # Restore base64 padding
    padded = signature_b64 + "=" * (-len(signature_b64) % 4)
    try:
        raw_sig = base64.urlsafe_b64decode(padded)
    except Exception as exc:
        raise SignatureVerificationError(f"Cannot decode signature: {exc}") from exc

    message = canonical_payload(data)
    try:
        public_key.verify(raw_sig, message, pss_padding(), hashes.SHA256())
    except InvalidSignature as exc:
        raise SignatureVerificationError(
            "Signature does not match the payload and public key"
        ) from exc

    return True


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------

_JWT_ALGORITHM = "HS256"
_ACCESS_TOKEN_EXPIRE_MINUTES = 60
_REFRESH_TOKEN_EXPIRE_DAYS = 7


def create_access_token(
    user_id: str | uuid.UUID,
    organization_id: str | uuid.UUID | None,
    role: str,
    secret: str,
    expire_minutes: int = _ACCESS_TOKEN_EXPIRE_MINUTES,
) -> str:
    """
    Create a short-lived HS256 JWT for API authentication.

    Claims:
        sub  : str(user_id)
        org  : str(organization_id) or None
        role : user role string
        type : "access"
        exp  : UTC expiry
        iat  : UTC issue time

    Args:
        user_id:         UUID of the authenticated user.
        organization_id: UUID of the user's organisation (may be None for admins).
        role:            UserRole enum value string.
        secret:          HS256 signing secret from settings.jwt_secret_key.
        expire_minutes:  Token lifetime in minutes (default 60).

    Returns:
        JWT string.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "org": str(organization_id) if organization_id else None,
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=expire_minutes),
    }
    return jwt.encode(payload, secret, algorithm=_JWT_ALGORITHM)


def create_refresh_token(
    user_id: str | uuid.UUID,
    secret: str,
    expire_days: int = _REFRESH_TOKEN_EXPIRE_DAYS,
) -> str:
    """
    Create a long-lived refresh token.  Contains only the user ID and type;
    the access token must be re-issued via /auth/refresh-token.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "iat": now,
        "exp": now + timedelta(days=expire_days),
    }
    return jwt.encode(payload, secret, algorithm=_JWT_ALGORITHM)


def verify_jwt_token(token: str, secret: str) -> dict[str, Any]:
    """
    Decode and validate a JWT.

    Returns:
        Decoded payload dict.

    Raises:
        TokenError: on expiry, bad signature, or malformed token.
    """
    try:
        return jwt.decode(token, secret, algorithms=[_JWT_ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("Token has expired") from exc
    except jwt.InvalidTokenError as exc:
        raise TokenError(f"Invalid token: {exc}") from exc
