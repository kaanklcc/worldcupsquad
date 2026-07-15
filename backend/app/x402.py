"""x402 v2 facilitator verification and settlement boundary."""
from __future__ import annotations

import base64
import json
from typing import Any, Dict, Optional

import httpx

from .config import settings


class X402Verifier:
    """Verify and settle signed x402 payments before access is granted."""

    def __init__(self):
        self.facilitator_url = settings.x402_facilitator_url

    def _endpoint(self, action: str) -> str:
        base = (self.facilitator_url or "").rstrip("/")
        for suffix in ("/verify", "/settle"):
            if base.endswith(suffix):
                base = base[:-len(suffix)]
        return f"{base}/{action}"

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if settings.x402_facilitator_token:
            headers["Authorization"] = f"Bearer {settings.x402_facilitator_token}"
        return headers

    @staticmethod
    def _decode_payment_signature(payment_signature: str) -> Dict[str, Any]:
        try:
            padded = payment_signature + "=" * (-len(payment_signature) % 4)
            decoded = base64.urlsafe_b64decode(padded.encode("ascii"))
            payload = json.loads(decoded.decode("utf-8"))
        except (ValueError, UnicodeError, json.JSONDecodeError) as error:
            raise ValueError(f"Invalid PAYMENT-SIGNATURE payload: {error}") from error
        if not isinstance(payload, dict):
            raise ValueError("PAYMENT-SIGNATURE must decode to a JSON object")
        return payload

    async def verify_and_settle(
        self,
        payment_signature: Optional[str],
        payment_requirements: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Verify and settle one x402 v2 payment before granting access."""
        if not self.facilitator_url:
            return {"verified": False, "error": "x402 facilitator not configured"}
        if not payment_signature:
            return {"verified": False, "error": "PAYMENT-SIGNATURE is missing"}

        try:
            payment_payload = self._decode_payment_signature(payment_signature)
            facilitator_body = {
                "x402Version": 2,
                "paymentPayload": payment_payload,
                "paymentRequirements": payment_requirements,
            }
            async with httpx.AsyncClient(timeout=15.0) as client:
                verify_response = await client.post(
                    self._endpoint("verify"),
                    json=facilitator_body,
                    headers=self._headers(),
                )
                verify_response.raise_for_status()
                verification = verify_response.json()
                if not verification.get("isValid", verification.get("verified", False)):
                    return {
                        "verified": False,
                        "error": verification.get("invalidMessage")
                        or verification.get("invalidReason")
                        or "Payment verification failed",
                    }

                settle_response = await client.post(
                    self._endpoint("settle"),
                    json=facilitator_body,
                    headers=self._headers(),
                )
                settle_response.raise_for_status()
                settlement = settle_response.json()
                if not settlement.get("success", settlement.get("settled", False)):
                    return {
                        "verified": False,
                        "error": settlement.get("errorMessage")
                        or settlement.get("errorReason")
                        or "Payment settlement failed",
                    }

            amount_atomic = float(payment_requirements.get("amount") or 0)
            payment_response = base64.b64encode(
                json.dumps(settlement, separators=(",", ":")).encode("utf-8")
            ).decode("ascii")
            return {
                "verified": True,
                "settled": True,
                "amount": amount_atomic / 1_000_000,
                "currency": "USDC",
                "receipt": settlement.get("transaction"),
                "payer": settlement.get("payer"),
                "paymentResponse": payment_response,
            }
        except (httpx.HTTPError, ValueError, TypeError) as error:
            return {"verified": False, "error": f"x402 verify/settle failed: {error}"}


_verifier: Optional[X402Verifier] = None


def get_x402_verifier() -> X402Verifier:
    """Get or create the singleton x402 verifier."""
    global _verifier
    if _verifier is None:
        _verifier = X402Verifier()
    return _verifier
