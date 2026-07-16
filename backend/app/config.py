"""
Configuration from environment variables using pydantic-settings.
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Gemini LLM
    gemini_api_key: str = ""
    # Stable function-calling model. Override with GEMINI_MODEL when needed.
    gemini_model: str = "gemini-3.1-flash-lite"

    # Authentication secret is always supplied by the operator. There is no
    # hardcoded fallback because an accidental default would make every
    # deployment sign tokens with the same key.
    jwt_secret_key: str = ""

    # Injective
    injective_mnemonic: str = ""
    injective_testnet: bool = True

    # x402
    x402_facilitator_url: str = ""
    x402_demo_mode: bool = True
    # Optional presentation-only switch. Kaan's demo membership does not need
    # this; other accounts remain payment-gated by default.
    x402_allow_simulated_purchases: bool = False
    # x402 v2 uses CAIP-2 network identifiers. Injective EVM testnet is 1439.
    x402_network: str = "eip155:1439"
    # Operator-owned receiver address; intentionally has no default.
    x402_pay_to: str = ""
    x402_asset: str = "0x0000000000000000000000000000000000000000"
    x402_facilitator_token: str = ""
    x402_resource_base_url: str = "http://localhost:8000"

    # Use the real stdio MCP transport by default; simulation remains available
    # for offline demos or when a judge only runs the FastAPI process.
    mcp_simulation: bool = False

    # CCTP v2 testnet: browser wallets sign each transaction; this service only
    # verifies confirmed receipts before granting a fantasy-budget credit.
    cctp_source_domain: int = 0  # Ethereum / Sepolia
    cctp_destination_domain: int = 29  # Injective EVM testnet
    cctp_source_token: str = "0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238"  # Circle USDC on Sepolia
    cctp_destination_token: str = "0x0C382e685bbeeFE5d3d9C29e29E341fEE8E84C5d"  # Circle USDC on Injective testnet
    cctp_token_messenger: str = "0x8FE6B999Dc680CcFDD5Bf7EB0974218be2542DAA"
    cctp_message_transmitter: str = "0xE737e5cEBEEBa77EFE34D4aa090756590b1CE275"
    cctp_sepolia_rpc_url: str = "https://ethereum-sepolia-rpc.publicnode.com"
    cctp_injective_rpc_url: str = "https://k8s.testnet.json-rpc.injective.network/"
    circle_api_key: str = ""

    # Public World Cup event refresh. Tests can disable this to stay fully
    # deterministic and offline.
    live_stats_enabled: bool = True
    live_event_feed_enabled: bool = True

    # Server
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
