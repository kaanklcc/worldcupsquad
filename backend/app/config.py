"""
Configuration from environment variables using pydantic-settings.
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Gemini LLM
    gemini_api_key: str = ""
    # Stable function-calling model. Override with GEMINI_MODEL when needed.
    gemini_model: str = "gemini-3.1-flash-lite"

    # Authentication. Override this in any shared or production environment.
    jwt_secret_key: str = "auto-gaffer-local-development-secret"

    # Injective
    injective_mnemonic: str = ""
    injective_testnet: bool = True

    # x402
    x402_facilitator_url: str = "https://facilitator.x402.co/verify"
    x402_demo_mode: bool = True

    # Use the real stdio MCP transport by default; simulation remains available
    # for offline demos or when a judge only runs the FastAPI process.
    mcp_simulation: bool = False

    # CCTP
    cctp_source_domain: int = 0  # Ethereum
    cctp_destination_domain: int = 3  # Injective
    cctp_source_token: str = "0x07865c6e87b9f70255377e024ace6630c1eaa37f"  # USDC on Ethereum
    circle_api_key: str = ""

    # Server
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
