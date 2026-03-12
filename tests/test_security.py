"""
Tests for NDIC cryptographic security layer.

Run with:
    pip install pytest pytest-asyncio
    pytest tests/test_security.py -v

These are pure unit tests — no database required.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.security import (
    ChainIntegrityError,
    SignatureVerificationError,
    TokenError,
    canonical_payload,
    compute_chain_hash,
    create_access_token,
    create_refresh_token,
    generate_keypair,
    hash_payload,
    sign_data,
    verify_jwt_token,
    verify_signature,
)
from app.utils.crypto_utils import (
    InvalidKeyError,
    is_valid_rsa_public_key,
    is_valid_rsa_private_key,
    pem_to_private_key,
    pem_to_public_key,
    pss_padding,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def keypair() -> tuple[str, str]:
    """Generate a fresh RSA-2048 key pair once for the entire module."""
    pub_pem, priv_pem = generate_keypair(key_size=2048)
    return pub_pem, priv_pem


@pytest.fixture(scope="module")
def keypair_b() -> tuple[str, str]:
    """A second, independent key pair (simulates a different organisation)."""
    pub_pem, priv_pem = generate_keypair(key_size=2048)
    return pub_pem, priv_pem


@pytest.fixture
def sample_record() -> dict:
    return {
        "animal_id": str(uuid.uuid4()),
        "farm_id": str(uuid.uuid4()),
        "record_date": datetime(2026, 3, 11, 8, 0, 0, tzinfo=timezone.utc).isoformat(),
        "temperature_celsius": 38.5,
        "milk_yield_liters": 12.3,
        "behavior_score": 1,
    }


JWT_SECRET = "test-secret-key-that-is-long-enough-for-hmac-sha256-32bytes"


# ===========================================================================
# Key generation
# ===========================================================================

class TestKeypairGeneration:
    def test_generates_valid_pem_strings(self, keypair):
        pub_pem, priv_pem = keypair
        assert pub_pem.startswith("-----BEGIN PUBLIC KEY-----")
        assert priv_pem.startswith("-----BEGIN PRIVATE KEY-----")

    def test_public_key_is_parseable(self, keypair):
        pub_pem, _ = keypair
        key = pem_to_public_key(pub_pem)
        assert key is not None

    def test_private_key_is_parseable(self, keypair):
        _, priv_pem = keypair
        key = pem_to_private_key(priv_pem)
        assert key is not None

    def test_two_keypairs_are_independent(self, keypair, keypair_b):
        assert keypair[0] != keypair_b[0]
        assert keypair[1] != keypair_b[1]

    def test_is_valid_rsa_public_key_true(self, keypair):
        assert is_valid_rsa_public_key(keypair[0]) is True

    def test_is_valid_rsa_private_key_true(self, keypair):
        assert is_valid_rsa_private_key(keypair[1]) is True

    def test_is_valid_rsa_public_key_false_on_garbage(self):
        assert is_valid_rsa_public_key("not a key") is False

    def test_is_valid_rsa_public_key_false_on_private_key(self, keypair):
        # A private key PEM is NOT a valid public key PEM
        assert is_valid_rsa_public_key(keypair[1]) is False

    def test_pem_to_public_key_raises_on_empty(self):
        with pytest.raises(InvalidKeyError):
            pem_to_public_key("")

    def test_pem_to_private_key_raises_on_garbage(self):
        with pytest.raises(InvalidKeyError):
            pem_to_private_key("-----BEGIN PRIVATE KEY-----\nbaddata\n-----END PRIVATE KEY-----")


# ===========================================================================
# Canonical payload & hashing
# ===========================================================================

class TestCanonicalPayload:
    def test_deterministic_for_same_dict(self, sample_record):
        a = canonical_payload(sample_record)
        b = canonical_payload(sample_record)
        assert a == b

    def test_order_independent(self):
        d1 = {"b": 2, "a": 1}
        d2 = {"a": 1, "b": 2}
        assert canonical_payload(d1) == canonical_payload(d2)

    def test_uuid_serialised_as_string(self):
        uid = uuid.uuid4()
        payload = canonical_payload({"id": uid})
        assert str(uid) in payload.decode()

    def test_datetime_serialised_as_iso8601(self):
        dt = datetime(2026, 3, 11, 9, 0, tzinfo=timezone.utc)
        payload = canonical_payload({"ts": dt})
        assert "2026-03-11" in payload.decode()

    def test_different_values_produce_different_hashes(self, sample_record):
        h1 = hash_payload(sample_record)
        modified = {**sample_record, "temperature_celsius": 40.0}
        h2 = hash_payload(modified)
        assert h1 != h2

    def test_hash_is_64_hex_chars(self, sample_record):
        h = hash_payload(sample_record)
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)


# ===========================================================================
# Signing + verification (round-trip)
# ===========================================================================

class TestSigningRoundTrip:
    def test_sign_and_verify_succeeds(self, keypair, sample_record):
        pub_pem, priv_pem = keypair
        sig = sign_data(sample_record, priv_pem)
        assert verify_signature(sample_record, sig, pub_pem) is True

    def test_verify_returns_true_not_truthy(self, keypair, sample_record):
        pub_pem, priv_pem = keypair
        sig = sign_data(sample_record, priv_pem)
        result = verify_signature(sample_record, sig, pub_pem)
        assert result is True

    def test_tampered_payload_raises(self, keypair, sample_record):
        pub_pem, priv_pem = keypair
        sig = sign_data(sample_record, priv_pem)
        tampered = {**sample_record, "temperature_celsius": 42.0}
        with pytest.raises(SignatureVerificationError):
            verify_signature(tampered, sig, pub_pem)

    def test_wrong_public_key_raises(self, keypair, keypair_b, sample_record):
        """Signature made with org A's key should fail verification with org B's key."""
        _, priv_pem_a = keypair
        pub_pem_b, _ = keypair_b
        sig = sign_data(sample_record, priv_pem_a)
        with pytest.raises(SignatureVerificationError):
            verify_signature(sample_record, sig, pub_pem_b)

    def test_garbled_signature_raises(self, keypair, sample_record):
        pub_pem, _ = keypair
        with pytest.raises(SignatureVerificationError):
            verify_signature(sample_record, "notavalidsignature", pub_pem)

    def test_empty_public_key_raises(self, keypair, sample_record):
        _, priv_pem = keypair
        sig = sign_data(sample_record, priv_pem)
        with pytest.raises(SignatureVerificationError):
            verify_signature(sample_record, sig, "")

    def test_signature_is_base64url_string(self, keypair, sample_record):
        _, priv_pem = keypair
        sig = sign_data(sample_record, priv_pem)
        import base64
        # Should not raise — URL-safe base64 with padding restored
        padded = sig + "=" * (-len(sig) % 4)
        decoded = base64.urlsafe_b64decode(padded)
        assert len(decoded) > 0

    def test_different_records_produce_different_signatures(self, keypair):
        _, priv_pem = keypair
        r1 = {"farm_id": "farm-001", "milk_yield_liters": 10.0}
        r2 = {"farm_id": "farm-001", "milk_yield_liters": 11.0}
        sig1 = sign_data(r1, priv_pem)
        sig2 = sign_data(r2, priv_pem)
        assert sig1 != sig2


# ===========================================================================
# Hash chain
# ===========================================================================

class TestHashChain:
    def test_first_entry_uses_genesis(self):
        ph = "a" * 64
        chain_hash = compute_chain_hash(ph, None)
        expected_input = (ph + "GENESIS").encode()
        import hashlib
        assert chain_hash == hashlib.sha256(expected_input).hexdigest()

    def test_subsequent_entry_uses_previous(self):
        ph = "b" * 64
        prev = "c" * 64
        chain_hash = compute_chain_hash(ph, prev)
        import hashlib
        expected_input = (ph + prev).encode()
        assert chain_hash == hashlib.sha256(expected_input).hexdigest()

    def test_chain_is_sensitive_to_payload_change(self):
        prev = "d" * 64
        h1 = compute_chain_hash("e" * 64, prev)
        h2 = compute_chain_hash("f" * 64, prev)
        assert h1 != h2

    def test_chain_is_sensitive_to_previous_change(self):
        ph = "g" * 64
        h1 = compute_chain_hash(ph, "h" * 64)
        h2 = compute_chain_hash(ph, "i" * 64)
        assert h1 != h2

    def test_simulated_three_entry_chain(self):
        """
        Simulate three sequential ledger entries and verify chain links.
        entry_1 → entry_2 → entry_3
        """
        import hashlib

        ph1 = hash_payload({"event": "animal_registered", "idx": 1})
        ph2 = hash_payload({"event": "health_record", "idx": 2})
        ph3 = hash_payload({"event": "health_record", "idx": 3})

        chain1 = compute_chain_hash(ph1, None)       # prev=GENESIS
        chain2 = compute_chain_hash(ph2, chain1)     # prev=chain1
        chain3 = compute_chain_hash(ph3, chain2)     # prev=chain2

        # Verify backward: recompute chain2 from ph2 and chain1
        assert compute_chain_hash(ph2, chain1) == chain2
        # Verify chain3 from ph3 and chain2
        assert compute_chain_hash(ph3, chain2) == chain3

    def test_tampered_payload_breaks_chain(self):
        """If ph2 is tampered, the recomputed chain2 won't match stored chain2."""
        ph1 = hash_payload({"event": "original", "idx": 1})
        ph2_original = hash_payload({"event": "original", "idx": 2})
        ph2_tampered = hash_payload({"event": "TAMPERED", "idx": 2})

        chain1 = compute_chain_hash(ph1, None)
        chain2_original = compute_chain_hash(ph2_original, chain1)
        chain2_tampered = compute_chain_hash(ph2_tampered, chain1)

        assert chain2_original != chain2_tampered


# ===========================================================================
# Cross-organisation isolation
# ===========================================================================

class TestCrossOrganizationIsolation:
    def test_org_a_signature_rejected_for_org_b_key(self, keypair, keypair_b):
        """Core security property: one org cannot forge another's records."""
        pub_a, priv_a = keypair
        pub_b, priv_b = keypair_b

        record = {"farm_id": "farm-001", "volume_liters": 500.0}

        # Org A signs the record
        sig_a = sign_data(record, priv_a)

        # Platform tries to verify with Org B's public key → must fail
        with pytest.raises(SignatureVerificationError):
            verify_signature(record, sig_a, pub_b)

    def test_org_b_signature_rejected_for_org_a_key(self, keypair, keypair_b):
        pub_a, priv_a = keypair
        pub_b, priv_b = keypair_b

        record = {"disease_type": "brucellosis", "state": "Kaduna"}
        sig_b = sign_data(record, priv_b)

        with pytest.raises(SignatureVerificationError):
            verify_signature(record, sig_b, pub_a)

    def test_each_org_can_verify_its_own_signatures(self, keypair, keypair_b):
        pub_a, priv_a = keypair
        pub_b, priv_b = keypair_b

        record_a = {"org": "A", "data": 1}
        record_b = {"org": "B", "data": 2}

        assert verify_signature(record_a, sign_data(record_a, priv_a), pub_a)
        assert verify_signature(record_b, sign_data(record_b, priv_b), pub_b)


# ===========================================================================
# JWT
# ===========================================================================

class TestJWT:
    def test_access_token_round_trip(self):
        user_id = uuid.uuid4()
        org_id = uuid.uuid4()
        token = create_access_token(user_id, org_id, "farm", JWT_SECRET)
        payload = verify_jwt_token(token, JWT_SECRET)
        assert payload["sub"] == str(user_id)
        assert payload["org"] == str(org_id)
        assert payload["role"] == "farm"
        assert payload["type"] == "access"

    def test_refresh_token_round_trip(self):
        user_id = uuid.uuid4()
        token = create_refresh_token(user_id, JWT_SECRET)
        payload = verify_jwt_token(token, JWT_SECRET)
        assert payload["sub"] == str(user_id)
        assert payload["type"] == "refresh"

    def test_expired_token_raises(self):
        user_id = uuid.uuid4()
        token = create_access_token(user_id, None, "farm", JWT_SECRET, expire_minutes=-1)
        with pytest.raises(TokenError, match="expired"):
            verify_jwt_token(token, JWT_SECRET)

    def test_wrong_secret_raises(self):
        user_id = uuid.uuid4()
        token = create_access_token(user_id, None, "farm", JWT_SECRET)
        with pytest.raises(TokenError):
            verify_jwt_token(token, "wrong-secret")

    def test_tampered_payload_raises(self):
        """Manually alter the payload bytes — signature should fail."""
        import base64
        user_id = uuid.uuid4()
        token = create_access_token(user_id, None, "farm", JWT_SECRET)

        # JWT is header.payload.signature — corrupt the payload segment
        parts = token.split(".")
        corrupted = parts[0] + "." + parts[1][:-2] + "xx" + "." + parts[2]
        with pytest.raises(TokenError):
            verify_jwt_token(corrupted, JWT_SECRET)

    def test_none_org_id_in_token(self):
        """arpexas_admin has no organisation."""
        user_id = uuid.uuid4()
        token = create_access_token(user_id, None, "arpexas_admin", JWT_SECRET)
        payload = verify_jwt_token(token, JWT_SECRET)
        assert payload["org"] is None

    def test_access_and_refresh_tokens_are_different(self):
        user_id = uuid.uuid4()
        access = create_access_token(user_id, None, "farm", JWT_SECRET)
        refresh = create_refresh_token(user_id, JWT_SECRET)
        assert access != refresh

    def test_token_carries_no_pii_beyond_ids(self):
        """Tokens must not contain email, name, or any PII."""
        user_id = uuid.uuid4()
        token = create_access_token(user_id, None, "processor", JWT_SECRET)
        payload = verify_jwt_token(token, JWT_SECRET)
        forbidden_keys = {"email", "name", "full_name", "password", "phone"}
        assert forbidden_keys.isdisjoint(set(payload.keys()))


# ===========================================================================
# Ledger service (unit — mocked DB session)
# ===========================================================================

class TestLedgerServiceUnit:
    """
    Unit tests for ledger_service.record_submission using a mocked async session.
    These tests do not require a real database.
    """

    @pytest.fixture
    def mock_session(self):
        """Minimal async session mock that accepts session.add() and flush()."""
        session = AsyncMock()
        session.add = MagicMock()

        # Simulate _get_previous_hash returning None (first entry in chain)
        async def execute_side_effect(stmt):
            result = MagicMock()
            result.scalar_one_or_none.return_value = None
            return result

        session.execute = execute_side_effect
        return session

    @pytest.mark.asyncio
    async def test_valid_submission_returns_ledger_entry(self, keypair, sample_record, mock_session):
        from app.services.ledger_service import record_submission
        from models.enums import LedgerEventType

        pub_pem, priv_pem = keypair
        sig = sign_data(sample_record, priv_pem)
        record_id = uuid.uuid4()
        user_id = uuid.uuid4()
        org_id = uuid.uuid4()

        entry = await record_submission(
            session=mock_session,
            actor_user_id=user_id,
            actor_org_id=org_id,
            event_type=LedgerEventType.HEALTH_RECORD_SUBMITTED,
            target_table="health_records",
            target_record_id=record_id,
            record_dict=sample_record,
            signature_b64=sig,
            public_key_pem=pub_pem,
        )

        assert entry.actor_id == user_id
        assert entry.target_table == "health_records"
        assert entry.target_record_id == record_id
        assert len(entry.payload_hash) == 64
        mock_session.add.assert_called_once_with(entry)

    @pytest.mark.asyncio
    async def test_bad_signature_raises(self, keypair, sample_record, mock_session):
        from app.services.ledger_service import record_submission
        from models.enums import LedgerEventType

        pub_pem, _ = keypair

        with pytest.raises(SignatureVerificationError):
            await record_submission(
                session=mock_session,
                actor_user_id=uuid.uuid4(),
                actor_org_id=uuid.uuid4(),
                event_type=LedgerEventType.HEALTH_RECORD_SUBMITTED,
                target_table="health_records",
                target_record_id=uuid.uuid4(),
                record_dict=sample_record,
                signature_b64="invalidsignature",
                public_key_pem=pub_pem,
            )

    @pytest.mark.asyncio
    async def test_missing_public_key_raises(self, sample_record, mock_session):
        from app.services.ledger_service import record_submission
        from models.enums import LedgerEventType

        with pytest.raises(ValueError, match="no registered public key"):
            await record_submission(
                session=mock_session,
                actor_user_id=uuid.uuid4(),
                actor_org_id=uuid.uuid4(),
                event_type=LedgerEventType.HEALTH_RECORD_SUBMITTED,
                target_table="health_records",
                target_record_id=uuid.uuid4(),
                record_dict=sample_record,
                signature_b64="sig",
                public_key_pem="",
            )
