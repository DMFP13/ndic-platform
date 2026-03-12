"""
NDIC Ledger Service
────────────────────
Orchestrates the three-step write protocol:

  1. Verify the actor's Ed25519/RSA signature against their registered public key.
  2. Compute the payload hash and chain link.
  3. Append a new row to ledger_log (never update, never delete).

All public functions are async and accept an `AsyncSession`.
They NEVER commit; the calling endpoint owns the transaction boundary,
allowing a domain record insert + ledger insert to share a single atomic commit.

Usage pattern (in an API endpoint)::

    async with get_session_factory()() as session:
        animal = Animal(**payload.model_dump(exclude={"signature"}))
        session.add(animal)
        await session.flush()            # gets animal.id without committing

        entry = await record_submission(
            session       = session,
            actor_user_id = current_user.id,
            actor_org_id  = current_user.organization_id,
            event_type    = LedgerEventType.ANIMAL_REGISTERED,
            target_table  = "animals",
            target_record = animal,
            record_dict   = payload.model_dump(mode="json"),
            signature_b64 = payload.signature,
            public_key_pem= current_user.public_key,
            ip_address    = request.client.host,
            user_agent    = request.headers.get("user-agent"),
        )
        await session.commit()
        return {"id": animal.id, "ledger_entry_id": entry.id}
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.security import (
    ChainIntegrityError,
    SignatureVerificationError,
    compute_chain_hash,
    hash_payload,
    verify_signature,
)
from models.database import LedgerLog
from models.enums import LedgerEventType

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Core write operation
# ---------------------------------------------------------------------------


async def record_submission(
    *,
    session: AsyncSession,
    actor_user_id: uuid.UUID,
    actor_org_id: uuid.UUID | None,
    event_type: LedgerEventType,
    target_table: str,
    target_record_id: uuid.UUID,
    record_dict: dict[str, Any],
    signature_b64: str,
    public_key_pem: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> LedgerLog:
    """
    Verify a submitted record's signature then append a ledger entry.

    Steps:
      1. Verify RSA-PSS signature of record_dict against public_key_pem.
      2. Compute payload_hash = SHA-256(canonical_json(record_dict)).
      3. Query the most recent ledger entry for this actor+table → previous_hash.
      4. Compute chain_link  = SHA-256(payload_hash || previous_hash).
      5. INSERT LedgerLog row (no commit — caller owns the transaction).

    Args:
        session:          Active async SQLAlchemy session.
        actor_user_id:    ID of the user submitting the record.
        actor_org_id:     ID of their organisation (may be None for arpexas_admin).
        event_type:       LedgerEventType variant describing what happened.
        target_table:     Name of the domain table being written to.
        target_record_id: UUID of the domain record being logged.
        record_dict:      Dict representation of the domain record (what was signed).
        signature_b64:    URL-safe base64 RSA-PSS signature provided by the actor.
        public_key_pem:   Actor's registered RSA public key (from users.public_key).
        ip_address:       Client IP for forensic purposes (not exposed via API).
        user_agent:       HTTP User-Agent header (forensic only).

    Returns:
        The newly inserted (but not yet committed) LedgerLog ORM object.

    Raises:
        SignatureVerificationError: signature mismatch.
        ValueError:                 actor has no registered public key.
    """
    # ── Step 1: public key guard ─────────────────────────────────────────────
    if not public_key_pem:
        raise ValueError(
            f"Actor {actor_user_id} has no registered public key. "
            "Register a public key via POST /auth/register-public-key before submitting records."
        )

    # ── Step 2: signature verification ──────────────────────────────────────
    try:
        verify_signature(record_dict, signature_b64, public_key_pem)
    except SignatureVerificationError:
        # Log the attempt for security audit without leaking the signature
        log.warning(
            "Signature verification failed: actor=%s org=%s table=%s record=%s",
            actor_user_id, actor_org_id, target_table, target_record_id,
        )
        raise

    # ── Step 3: payload hash ─────────────────────────────────────────────────
    payload_hash = hash_payload(record_dict)

    # ── Step 4: chain link (previous hash for this actor × table pair) ───────
    previous_hash = await _get_previous_hash(
        session, actor_user_id=actor_user_id, target_table=target_table
    )
    chain_hash = compute_chain_hash(payload_hash, previous_hash)

    # ── Step 5: append ledger entry ──────────────────────────────────────────
    entry = LedgerLog(
        id=uuid.uuid4(),
        event_type=event_type,
        actor_id=actor_user_id,
        actor_org_id=actor_org_id,
        target_table=target_table,
        target_record_id=target_record_id,
        payload_hash=payload_hash,
        signature=signature_b64,
        previous_hash=chain_hash,   # stored so the NEXT entry can link to it
        ip_address=ip_address,
        user_agent=user_agent,
    )
    session.add(entry)
    log.debug(
        "Ledger entry queued: event=%s actor=%s table=%s record=%s chain=%s",
        event_type, actor_user_id, target_table, target_record_id, chain_hash[:12],
    )
    return entry


# ---------------------------------------------------------------------------
# History retrieval
# ---------------------------------------------------------------------------


async def get_ledger_history(
    session: AsyncSession,
    target_record_id: uuid.UUID,
    target_table: str | None = None,
) -> list[LedgerLog]:
    """
    Return all ledger entries for a given domain record, oldest first.

    Args:
        session:          Async SQLAlchemy session.
        target_record_id: UUID of the domain record to look up.
        target_table:     Optional filter by table name (speeds up the query).

    Returns:
        List of LedgerLog objects in ascending created_at order.
    """
    stmt = (
        select(LedgerLog)
        .where(LedgerLog.target_record_id == target_record_id)
        .order_by(LedgerLog.created_at.asc())
    )
    if target_table:
        stmt = stmt.where(LedgerLog.target_table == target_table)

    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_actor_ledger_history(
    session: AsyncSession,
    actor_user_id: uuid.UUID,
    target_table: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[LedgerLog]:
    """
    Return ledger entries submitted by a specific actor, newest first.
    Supports pagination via limit/offset.
    """
    stmt = (
        select(LedgerLog)
        .where(LedgerLog.actor_id == actor_user_id)
        .order_by(LedgerLog.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if target_table:
        stmt = stmt.where(LedgerLog.target_table == target_table)

    result = await session.execute(stmt)
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Chain integrity verification
# ---------------------------------------------------------------------------


async def verify_chain_integrity(
    session: AsyncSession,
    actor_user_id: uuid.UUID | None = None,
    target_table: str | None = None,
    limit: int = 10_000,
) -> dict[str, Any]:
    """
    Walk the ledger chain and verify every hash link.

    This is an O(n) sequential scan and should be run as a background job,
    not on a hot API path.

    Algorithm:
      For each entry (ordered by created_at asc):
        expected_payload_hash = SHA-256(canonical_json(target record))  ← would
          require fetching domain records; here we verify the *chain* links only,
          i.e. that previous_hash[n] == chain_hash(payload_hash[n-1], previous_hash[n-1])
          The payload hash against domain data is a separate audit step.

    Returns::

        {
          "is_valid": bool,
          "entries_checked": int,
          "broken_at": ledger_entry_id or None,
          "errors": [{"entry_id": ..., "message": ...}]
        }

    Args:
        session:        Async SQLAlchemy session.
        actor_user_id:  Narrow to a single actor (optional).
        target_table:   Narrow to a single table (optional).
        limit:          Maximum entries to scan (default 10,000).
    """
    stmt = select(LedgerLog).order_by(LedgerLog.created_at.asc()).limit(limit)
    if actor_user_id:
        stmt = stmt.where(LedgerLog.actor_id == actor_user_id)
    if target_table:
        stmt = stmt.where(LedgerLog.target_table == target_table)

    result = await session.execute(stmt)
    entries: list[LedgerLog] = list(result.scalars().all())

    errors: list[dict[str, Any]] = []
    broken_at: uuid.UUID | None = None

    # Group by (actor_id, target_table) so each actor/table chain is
    # verified independently (chains don't cross actor boundaries).
    chains: dict[tuple[uuid.UUID, str], list[LedgerLog]] = {}
    for entry in entries:
        key = (entry.actor_id, entry.target_table)
        chains.setdefault(key, []).append(entry)

    for (actor_id, table), chain_entries in chains.items():
        running_chain_hash: str | None = None

        for entry in chain_entries:
            expected_previous = running_chain_hash  # what we expect this entry to link back to

            # The first entry in a chain has previous_hash = chain_hash(payload_hash, "GENESIS")
            # We can verify: stored previous_hash == compute_chain_hash(payload_hash, expected_previous)
            recomputed = compute_chain_hash(entry.payload_hash, expected_previous)

            if entry.previous_hash != recomputed:
                msg = (
                    f"Chain broken at entry {entry.id}: "
                    f"expected previous_hash={recomputed[:12]}… "
                    f"got {str(entry.previous_hash)[:12]}…"
                )
                errors.append({"entry_id": str(entry.id), "message": msg})
                if broken_at is None:
                    broken_at = entry.id
                log.error("CHAIN INTEGRITY FAILURE: %s", msg)
                break  # stop checking this chain once broken

            # Advance: the next entry's expected_previous is this entry's previous_hash
            running_chain_hash = entry.previous_hash

    return {
        "is_valid": len(errors) == 0,
        "entries_checked": len(entries),
        "broken_at": str(broken_at) if broken_at else None,
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


async def _get_previous_hash(
    session: AsyncSession,
    actor_user_id: uuid.UUID,
    target_table: str,
) -> str | None:
    """
    Return the `previous_hash` of the most recent ledger entry for this
    actor + table combination, or None if this is the first entry.
    """
    stmt = (
        select(LedgerLog.previous_hash)
        .where(
            LedgerLog.actor_id == actor_user_id,
            LedgerLog.target_table == target_table,
        )
        .order_by(LedgerLog.created_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    return row  # str | None
