"""Payment creation with idempotency for Project C."""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Optional

IDEMPOTENCY_TTL_SECONDS = 24 * 60 * 60
MAX_REFUND_WITHOUT_SCOPE = 10_000  # minor units


class PaymentError(Exception):
    def __init__(self, code: str, http_status: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.http_status = http_status


@dataclass
class Payment:
    id: str
    tenant_id: str
    amount: int
    currency: str
    status: str = "pending"
    refunded: int = 0


@dataclass
class IdempotencyRecord:
    body_hash: str
    response: dict
    created_at: float = field(default_factory=time.time)


class PaymentService:
    """In-memory reference implementation used by the unit tests."""

    def __init__(self) -> None:
        self._payments: dict[str, Payment] = {}
        self._idempotency: dict[tuple[str, str], IdempotencyRecord] = {}
        self._counter = 0

    @staticmethod
    def _hash_body(body: dict) -> str:
        return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()

    def create_payment(self, tenant_id: str, idempotency_key: str, body: dict) -> dict:
        """Create a payment, or replay the stored response for a repeated key."""
        key = (tenant_id, idempotency_key)
        body_hash = self._hash_body(body)
        record = self._idempotency.get(key)
        if record is not None:
            if time.time() - record.created_at > IDEMPOTENCY_TTL_SECONDS:
                del self._idempotency[key]
            elif record.body_hash != body_hash:
                raise PaymentError("idempotency_conflict", 409, "Key reused with a different body")
            else:
                return record.response
        if body["amount"] <= 0:
            raise PaymentError("invalid_request", 400, "Amount must be positive")
        self._counter += 1
        payment = Payment(f"pay_{self._counter:06d}", tenant_id, body["amount"], body["currency"])
        payment.status = "authorised"
        self._payments[payment.id] = payment
        response = {"id": payment.id, "status": payment.status, "amount": payment.amount}
        self._idempotency[key] = IdempotencyRecord(body_hash, response)
        return response

    def get_payment(self, tenant_id: str, payment_id: str) -> Payment:
        payment = self._payments.get(payment_id)
        if payment is None or payment.tenant_id != tenant_id:
            # Same error for missing and foreign payments so existence is not leaked.
            raise PaymentError("payment_not_found", 404, "Payment not found")
        return payment

    def refund(self, tenant_id: str, payment_id: str, amount: int, scopes: set[str]) -> dict:
        payment = self.get_payment(tenant_id, payment_id)
        if amount > MAX_REFUND_WITHOUT_SCOPE and "refund:large" not in scopes:
            raise PaymentError("forbidden", 403, "refund:large scope required")
        if payment.refunded + amount > payment.amount:
            raise PaymentError("invalid_request", 400, "Refund exceeds captured amount")
        payment.refunded += amount
        if payment.refunded == payment.amount:
            payment.status = "refunded"
        return {"id": payment.id, "refunded": payment.refunded, "status": payment.status}
