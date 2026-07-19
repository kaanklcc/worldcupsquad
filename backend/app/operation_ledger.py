"""Durable, idempotent receipts for user-triggered actions.

The ledger deliberately separates an intent from its final receipt. A retry
with the same key can return the original result; a second external action is
never silently sent while an earlier one is still processing.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any, Literal, Optional
from uuid import uuid4

from fastapi import HTTPException

from .db import get_db_connection


OperationStatus = Literal["processing", "confirmed", "failed"]


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def request_hash(payload: dict[str, Any]) -> str:
    return sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _parse_receipt(raw: Optional[str]) -> Optional[dict[str, Any]]:
    if not raw:
        return None
    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) else None
    except json.JSONDecodeError:
        return None


def serialize_operation(row) -> dict[str, Any]:
    return {
        "operationId": row["operation_id"],
        "idempotencyKey": row["idempotency_key"],
        "actionType": row["action_type"],
        "requestHash": row["request_hash"],
        "status": row["status"],
        "provider": row["provider"],
        "network": row["network"],
        "txHash": row["tx_hash"],
        "receipt": _parse_receipt(row["receipt"]),
        "error": row["error_message"],
        "simulated": bool(row["simulated"]),
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def begin_operation(
    *,
    user_id: int,
    action_type: str,
    provider: str,
    payload: dict[str, Any],
    idempotency_key: Optional[str],
    network: Optional[str] = None,
) -> tuple[dict[str, Any], bool]:
    """Create an intent or return an existing operation for the same key.

    Returns ``(operation, replay)``. A caller must return a confirmed replay
    directly, and must never call an external provider for a processing replay.
    """
    key = (idempotency_key or f"server-{uuid4()}").strip()
    if not re.fullmatch(r"[A-Za-z0-9._:-]{8,160}", key):
        raise HTTPException(status_code=400, detail="Invalid Idempotency-Key")
    digest = request_hash(payload)
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM operation_receipts WHERE idempotency_key = ?", (key,))
        existing = cursor.fetchone()
        if existing:
            operation = serialize_operation(existing)
            if existing["user_id"] != user_id or existing["request_hash"] != digest or existing["action_type"] != action_type:
                raise HTTPException(status_code=409, detail="Idempotency-Key was already used for a different action")
            return operation, True

        operation_id = f"op_{uuid4().hex}"
        now = datetime.now(timezone.utc).isoformat()
        cursor.execute(
            """
            INSERT INTO operation_receipts
                (operation_id, idempotency_key, user_id, action_type, request_hash,
                 status, provider, network, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'processing', ?, ?, ?, ?)
            """,
            (operation_id, key, user_id, action_type, digest, provider, network, now, now),
        )
        conn.commit()
        cursor.execute("SELECT * FROM operation_receipts WHERE operation_id = ?", (operation_id,))
        return serialize_operation(cursor.fetchone()), False
    finally:
        conn.close()


def confirm_operation(
    operation_id: str,
    *,
    receipt: dict[str, Any],
    tx_hash: Optional[str],
    simulated: bool,
) -> dict[str, Any]:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        now = datetime.now(timezone.utc).isoformat()
        cursor.execute(
            """
            UPDATE operation_receipts
            SET status = 'confirmed', tx_hash = ?, receipt = ?, simulated = ?,
                error_message = NULL, updated_at = ?
            WHERE operation_id = ? AND status = 'processing'
            """,
            (tx_hash, _canonical_json(receipt), 1 if simulated else 0, now, operation_id),
        )
        if cursor.rowcount != 1:
            raise HTTPException(status_code=409, detail="Operation could not be confirmed from its current state")
        conn.commit()
        cursor.execute("SELECT * FROM operation_receipts WHERE operation_id = ?", (operation_id,))
        return serialize_operation(cursor.fetchone())
    finally:
        conn.close()


def fail_operation(operation_id: str, message: str) -> None:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE operation_receipts
            SET status = 'failed', error_message = ?, updated_at = ?
            WHERE operation_id = ? AND status = 'processing'
            """,
            (message[:1000], datetime.now(timezone.utc).isoformat(), operation_id),
        )
        conn.commit()
    finally:
        conn.close()


def recent_operations(user_id: int, limit: int = 30) -> list[dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT * FROM operation_receipts WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, max(1, min(limit, 100))),
        )
        return [serialize_operation(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_operation(operation_id: str, user_id: int) -> dict[str, Any]:
    """Load one operation only when it belongs to the authenticated manager."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM operation_receipts WHERE operation_id = ?", (operation_id,))
        row = cursor.fetchone()
        if not row or row["user_id"] != user_id:
            raise HTTPException(status_code=404, detail="Operation was not found for this manager")
        return serialize_operation(row)
    finally:
        conn.close()
