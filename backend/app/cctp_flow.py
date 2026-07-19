"""Verification helpers for a wallet-signed Circle CCTP v2 testnet flow.

The browser performs approve, burn and mint with the manager's own wallet.
This backend never accepts a private key and never creates a synthetic bridge
receipt. It only supplies public CCTP configuration, proxies Iris attestation
status, and verifies both confirmed chain transactions before budget changes.
"""
from __future__ import annotations

from typing import Any
import logging

import httpx
from fastapi import HTTPException

from .config import settings


logger = logging.getLogger(__name__)


IRIS_SANDBOX_URL = "https://iris-api-sandbox.circle.com"
BURN_SELECTOR = "0x8e0250ee"  # depositForBurn(uint256,uint32,bytes32,address,bytes32,uint256,uint32)
MINT_SELECTOR = "0x57ecfd28"  # receiveMessage(bytes,bytes)


def _address(value: str) -> str:
    return value.lower()


def cctp_public_config() -> dict[str, Any]:
    """Return public constants required by an EVM wallet; no secrets included."""
    return {
        "source": {
            "chainId": 11155111,
            "chainName": "Ethereum Sepolia",
            "rpcUrl": settings.cctp_sepolia_rpc_url,
            "usdc": settings.cctp_source_token,
            "domain": settings.cctp_source_domain,
        },
        "destination": {
            "chainId": 1439,
            "chainName": "Injective EVM Testnet",
            "rpcUrl": settings.cctp_injective_rpc_url,
            "usdc": settings.cctp_destination_token,
            "domain": settings.cctp_destination_domain,
        },
        "tokenMessenger": settings.cctp_token_messenger,
        "messageTransmitter": settings.cctp_message_transmitter,
        "irisBaseUrl": IRIS_SANDBOX_URL,
        "explorers": {
            "source": "https://sepolia.etherscan.io/tx/",
            "destination": "https://testnet.blockscout.injective.network/tx/",
        },
    }


async def get_attestation(burn_tx_hash: str) -> dict[str, Any]:
    """Read Circle Iris status. The caller polls until `status == complete`."""
    url = f"{IRIS_SANDBOX_URL}/v2/messages/{settings.cctp_source_domain}?transactionHash={burn_tx_hash}"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url)
            if response.status_code == 404:
                return {"status": "pending", "message": "Burn is not indexed by Iris yet."}
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as error:
        logger.warning("Circle Iris attestation request failed: %s", type(error).__name__)
        raise HTTPException(status_code=502, detail="Circle Iris attestation service is temporarily unavailable") from error

    messages = data.get("messages") or []
    message = messages[0] if messages else {}
    status = str(message.get("status") or "pending").lower()
    complete = status == "complete" and bool(message.get("message")) and bool(message.get("attestation"))
    return {
        "status": "complete" if complete else status,
        "message": message.get("message") if complete else None,
        "attestation": message.get("attestation") if complete else None,
        "burnTxHash": burn_tx_hash,
    }


async def _rpc(url: str, method: str, params: list[Any]) -> Any:
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            body = response.json()
    except httpx.HTTPError as error:
        logger.warning("CCTP RPC request failed: %s", type(error).__name__)
        raise HTTPException(status_code=502, detail="CCTP chain verification service is temporarily unavailable") from error
    if body.get("error"):
        raise HTTPException(status_code=502, detail="CCTP chain verification service rejected the request")
    return body.get("result")


def _decode_word(input_data: str, index: int) -> int:
    # ABI words begin after the four-byte selector. index 0 is the first arg.
    start = 10 + (index * 64)
    word = input_data[start:start + 64]
    if len(word) != 64:
        raise HTTPException(status_code=422, detail="CCTP burn calldata is incomplete")
    return int(word, 16)


def _decode_address_word(input_data: str, index: int) -> str:
    start = 10 + (index * 64)
    word = input_data[start:start + 64]
    if len(word) != 64:
        raise HTTPException(status_code=422, detail="CCTP burn calldata is incomplete")
    return f"0x{word[-40:]}".lower()


def _decode_dynamic_bytes(input_data: str, index: int, *, max_bytes: int = 262_144) -> str:
    """Decode one ABI dynamic-bytes argument from transaction calldata."""
    if not input_data.startswith("0x"):
        raise HTTPException(status_code=422, detail="CCTP mint calldata is malformed")
    try:
        offset = _decode_word(input_data, index)
        length_start = 10 + (offset * 2)
        length_word = input_data[length_start:length_start + 64]
        if len(length_word) != 64:
            raise ValueError("missing dynamic length")
        length = int(length_word, 16)
        if length < 1 or length > max_bytes:
            raise ValueError("dynamic value outside limits")
        data_start = length_start + 64
        data = input_data[data_start:data_start + (length * 2)]
        if len(data) != length * 2:
            raise ValueError("truncated dynamic value")
        return f"0x{data}".lower()
    except (TypeError, ValueError) as error:
        raise HTTPException(status_code=422, detail="CCTP mint calldata is malformed") from error


async def _confirmed_transaction(rpc_url: str, tx_hash: str) -> tuple[dict[str, Any], dict[str, Any]]:
    tx, receipt = await _rpc(rpc_url, "eth_getTransactionByHash", [tx_hash]), await _rpc(rpc_url, "eth_getTransactionReceipt", [tx_hash])
    if not tx or not receipt:
        raise HTTPException(status_code=422, detail="CCTP transaction is not confirmed on the selected chain")
    if str(receipt.get("status", "")).lower() != "0x1":
        raise HTTPException(status_code=422, detail="CCTP transaction reverted on-chain")
    return tx, receipt


async def verify_cctp_receipts(*, wallet_address: str, amount_usdc: int, burn_tx_hash: str, mint_tx_hash: str) -> dict[str, Any]:
    """Verify source burn and destination mint before any database credit.

    This intentionally checks receipt success, sender, destination contracts,
    function selectors, declared USDC amount and Injective destination domain.
    It is conservative: an unavailable RPC or incomplete transaction fails
    closed and does not alter the manager's budget.
    """
    burn_tx, _ = await _confirmed_transaction(settings.cctp_sepolia_rpc_url, burn_tx_hash)
    mint_tx, _ = await _confirmed_transaction(settings.cctp_injective_rpc_url, mint_tx_hash)
    expected_wallet = _address(wallet_address)

    if _address(str(burn_tx.get("from", ""))) != expected_wallet:
        raise HTTPException(status_code=422, detail="CCTP burn transaction was not sent by the saved wallet")
    if _address(str(burn_tx.get("to", ""))) != _address(settings.cctp_token_messenger):
        raise HTTPException(status_code=422, detail="CCTP burn transaction targets an unexpected contract")
    burn_input = str(burn_tx.get("input") or "")
    if not burn_input.startswith(BURN_SELECTOR):
        raise HTTPException(status_code=422, detail="CCTP burn transaction does not call depositForBurn")
    if _decode_word(burn_input, 0) < amount_usdc * 1_000_000:
        raise HTTPException(status_code=422, detail="CCTP burn amount is below the requested USDC amount")
    if _decode_word(burn_input, 1) != settings.cctp_destination_domain:
        raise HTTPException(status_code=422, detail="CCTP burn uses an unexpected destination domain")
    if _decode_address_word(burn_input, 2) != expected_wallet:
        raise HTTPException(status_code=422, detail="CCTP burn recipient does not match the saved wallet")
    if _decode_address_word(burn_input, 3) != _address(settings.cctp_source_token):
        raise HTTPException(status_code=422, detail="CCTP burn uses an unexpected USDC contract")

    if _address(str(mint_tx.get("from", ""))) != expected_wallet:
        raise HTTPException(status_code=422, detail="CCTP mint transaction was not sent by the saved wallet")
    if _address(str(mint_tx.get("to", ""))) != _address(settings.cctp_message_transmitter):
        raise HTTPException(status_code=422, detail="CCTP mint transaction targets an unexpected contract")
    if not str(mint_tx.get("input") or "").startswith(MINT_SELECTOR):
        raise HTTPException(status_code=422, detail="CCTP mint transaction does not call receiveMessage")

    # Link the destination mint to this exact source burn. Merely supplying any
    # successful historical burn and any unrelated mint must not earn credit.
    attestation = await get_attestation(burn_tx_hash)
    if attestation.get("status") != "complete" or not attestation.get("message"):
        raise HTTPException(status_code=422, detail="Circle has not completed attestation for this burn transaction")
    minted_message = _decode_dynamic_bytes(str(mint_tx.get("input") or ""), 0)
    if minted_message != str(attestation["message"]).lower():
        raise HTTPException(status_code=422, detail="CCTP mint is not linked to the supplied burn transaction")

    return {
        "burnTxHash": burn_tx_hash,
        "mintTxHash": mint_tx_hash,
        "sourceNetwork": "eip155:11155111",
        "destinationNetwork": "eip155:1439",
        "simulated": False,
    }
