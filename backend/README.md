# WCAI backend

FastAPI API for the WCAI World Cup AI Command Centre. The repository-level [README](../README.md) is the source of truth for setup, demo, Injective technology mapping and security boundaries.

## Run

```powershell
py -m pip install -r requirements.txt
Copy-Item .env.example .env
py -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000/docs` for the complete OpenAPI contract.

## Important endpoints

- `POST /api/auth/register`, `POST /api/auth/login` — JWT session.
- `GET /api/players`, `GET /api/players/{player_id}/intel` — sourced roster and player intelligence.
- `POST /api/agent` — membership/x402-gated Gemini Agent Skills.
- `POST /api/access/unlock` — explicit demo grant or x402 v2 402 challenge / settlement.
- `POST /api/squad/apply-lineup`, `POST /api/transfers/execute` — confirmed MCP-backed mutations.
- `POST /api/cctp/intent`, `/attestation`, `/confirm` — wallet-signed CCTP v2 testnet flow.
- `GET /api/operations/recent` — durable receipt ledger.

`JWT_SECRET_KEY` must be at least 32 characters. The API refuses to issue or accept JWTs when it is not configured. Keep `CORS_ORIGINS` explicit in a deployment and never add a wallet seed phrase or facilitator private key to this environment file.
