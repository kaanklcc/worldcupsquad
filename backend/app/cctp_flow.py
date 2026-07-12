"""
CCTP (Circle Cross-Chain Transfer Protocol) flow.
Handles burn, attestation, and mint operations for USDC bridging.
"""
import httpx
from typing import Optional, Dict, Any
import hashlib
import time

from .config import settings


class CCTPFlow:
    """Handles CCTP burn → attest → mint flow for USDC bridging."""

    def __init__(self):
        self.source_domain = settings.cctp_source_domain
        self.destination_domain = settings.cctp_destination_domain
        self.source_token = settings.cctp_source_token
        self.circle_api_key = settings.circle_api_key

    def _generate_mock_tx_hash(self, operation: str, details: str) -> str:
        """Generate a realistic-looking mock transaction hash for simulation."""
        data = f"{operation}:{details}:{time.time()}".encode()
        hash_bytes = hashlib.sha256(data).digest()
        return f"0x{hash_bytes[:20].hex()}...{hash_bytes[-4:].hex()}"

    async def simulate_bridge(
        self,
        wallet_address: str,
        amount: int,
        source_chain: str
    ) -> Dict[str, Any]:
        """
        Simulate a CCTP bridge operation (used when no real credentials are configured).

        Returns a realistic simulation response without actual on-chain interaction.

        Args:
            wallet_address: Source wallet address
            amount: Amount to bridge in USDC
            source_chain: Source blockchain name

        Returns:
            dict with success status, tx hash, and details
        """
        burn_tx_hash = self._generate_mock_tx_hash("burn", f"{wallet_address}:{amount}")
        attestation = self._generate_mock_tx_hash("attest", burn_tx_hash)
        mint_tx_hash = self._generate_mock_tx_hash("mint", attestation)

        return {
            "success": True,
            "simulated": True,
            "burn_tx_hash": burn_tx_hash,
            "attestation": attestation,
            "mint_tx_hash": mint_tx_hash,
            "final_tx_hash": f"inj1_cctp_{mint_tx_hash[2:12]}...{mint_tx_hash[-6:]}",
            "amount_bridged": amount,
            "source_chain": source_chain,
            "destination_chain": "Injective",
            "message": f"CCTP bridge simulation successful. {amount} USDC bridged from {source_chain} to Injective."
        }

    async def real_bridge(
        self,
        wallet_address: str,
        amount: int,
        source_chain: str
    ) -> Dict[str, Any]:
        """
        Perform a real CCTP bridge operation.

        This involves:
        1. Burning USDC on source domain via TokenMessenger contract
        2. Fetching attestation from Circle's Attestation API
        3. Minting USDC on destination domain via TokenMessenger contract

        NOTE: This requires wallet signing and contract interaction. For now,
        this returns a realistic simulation as we don't have wallet credentials.

        Args:
            wallet_address: Source wallet address
            amount: Amount to bridge in USDC
            source_chain: Source blockchain name

        Returns:
            dict with success status, tx hash, and details
        """
        # In a production environment, this would:
        # 1. Call TokenMessenger.burn() on source chain
        # 2. Fetch attestation from Circle's API
        # 3. Call TokenMessenger.mint() on destination chain

        # For this implementation, return realistic simulation
        return await self.simulate_bridge(wallet_address, amount, source_chain)

    async def fetch_attestation(self, message_bytes: str) -> Optional[str]:
        """
        Fetch attestation from Circle's API for a burn message.

        Args:
            message_bytes: The message bytes from the burn transaction

        Returns:
            Attestation signature or None if failed
        """
        if not self.circle_api_key:
            print("Warning: CIRCLE_API_KEY not configured. Cannot fetch real attestations.")
            return None

        circle_attestation_url = "https://iris-api-sandbox.circle.com/attestations"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    circle_attestation_url,
                    json={
                        "message": message_bytes,
                        "attestationType": "Attestation"
                    },
                    headers={
                        "Authorization": f"Bearer {self.circle_api_key}"
                    },
                    timeout=30.0
                )
                response.raise_for_status()
                data = response.json()
                return data.get("attestation")
        except httpx.HTTPError as e:
            print(f"Failed to fetch attestation: {e}")
            return None


# Singleton instance
_cctp_flow: Optional[CCTPFlow] = None


def get_cctp_flow() -> CCTPFlow:
    """Get or create the singleton CCTP flow handler."""
    global _cctp_flow
    if _cctp_flow is None:
        _cctp_flow = CCTPFlow()
    return _cctp_flow