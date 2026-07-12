"""
x402 payment verification middleware.
Verifies HTTP 402 payment receipts before granting premium access.
"""
import httpx
from typing import Optional, Dict, Any

from .config import settings


class X402Verifier:
    """Verifies x402 payment receipts for premium access."""

    def __init__(self):
        self.facilitator_url = settings.x402_facilitator_url

    async def verify_receipt(self, receipt: Optional[str] = None, payment_header: Optional[str] = None) -> Dict[str, Any]:
        """
        Verify an x402 payment receipt or payment header.

        Args:
            receipt: Payment receipt string (from body or query params)
            payment_header: X-Payment header value

        Returns:
            dict with 'verified' (bool), 'amount' (float), 'currency' (str), and optional error
        """
        # If no facilitator URL configured, we can't verify
        if not self.facilitator_url or self.facilitator_url == "https://facilitator.x402.co/verify":
            return {
                "verified": False,
                "error": "x402 facilitator not configured - payment verification unavailable"
            }

        # If no receipt or header provided, not verified
        if not receipt and not payment_header:
            return {
                "verified": False,
                "error": "No payment receipt or X-Payment header provided"
            }

        # Prepare verification payload
        payload = {}
        if receipt:
            payload["receipt"] = receipt
        if payment_header:
            payload["payment_header"] = payment_header

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.facilitator_url,
                    json=payload,
                    timeout=10.0
                )
                response.raise_for_status()
                data = response.json()
                
                return {
                    "verified": data.get("verified", False),
                    "amount": data.get("amount", 0.0),
                    "currency": data.get("currency", "USDC"),
                    "error": None
                }
        except httpx.HTTPError as e:
            return {
                "verified": False,
                "error": f"Failed to verify payment: {str(e)}"
            }
        except Exception as e:
            return {
                "verified": False,
                "error": f"Payment verification error: {str(e)}"
            }

    async def verify_premium_access(
        self,
        has_paid_x402: bool,
        receipt: Optional[str] = None,
        payment_header: Optional[str] = None
    ) -> bool:
        """
        Verify premium access. This combines the client's claim with x402 verification.

        For demo/simulation purposes, if has_paid_x402 is True and we can't verify
        (no facilitator configured), we'll return True to allow the demo to work.

        Args:
            has_paid_x402: Client's claim that they've paid (from frontend)
            receipt: Optional payment receipt
            payment_header: Optional X-Payment header

        Returns:
            True if premium access is verified, False otherwise
        """
        # If facilitator is not configured (local dev/demo), trust the client's claim
        if not self.facilitator_url or self.facilitator_url == "https://facilitator.x402.co/verify":
            if has_paid_x402:
                return True
            return False

        # If client claims payment but no receipt/header, need to verify
        if has_paid_x402 and not receipt and not payment_header:
            return False

        # Verify the receipt
        verification = await self.verify_receipt(receipt, payment_header)
        return verification["verified"]


# Singleton instance
_verifier: Optional[X402Verifier] = None


def get_x402_verifier() -> X402Verifier:
    """Get or create the singleton x402 verifier."""
    global _verifier
    if _verifier is None:
        _verifier = X402Verifier()
    return _verifier