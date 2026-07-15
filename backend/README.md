# Auto-Gaffer Backend

Python FastAPI backend for the Auto-Gaffer World Cup 2026 Fantasy Football Manager.

## Technologies

- **FastAPI** - Modern async web framework
- **Gemini LLM** - AI consultant with function-calling agent skills
- **x402** - Payment Required protocol for premium access
- **CCTP** - Circle Cross-Chain Transfer Protocol for USDC bridging
- **MCP** - Model Context Protocol server for squad management tools

## Features

### API Endpoints

- `GET  /api/players` - Get the 104-player FIFA roster snapshot for Argentina, England, France, and Spain
- `GET  /api/players/meta` - Get roster snapshot date and FIFA source URLs
- `GET  /api/worldcup/snapshot` - Get dated semifinal fixtures and provenance
- `GET  /api/access/status` - Read persistent membership, Match Pass and wallet access
- `POST /api/access/unlock` - Activate Kaan's free judge demo or process x402 access
- `POST /api/access/wallet` - Validate and save an Injective/EVM wallet
- `POST /api/agent` - Chat with the membership/x402-gated AI consultant
- `GET /api/worldcup/matchday-brief` - Build a source-aware pre-match brief from the dated snapshot
- `POST /api/tactical-lab/compare` - Compare all supported formations without mutating the saved squad
- `POST /api/squad/apply-lineup` - Apply a confirmed, budget-validated AI lineup
- `POST /api/cctp` - Bridge USDC from Ethereum to Injective
- `POST /api/transfers/execute` - Execute transfers via MCP

### Agent Skills (Function Calling)

The Gemini LLM has access to these tools:

1. `search_player` - Find player by name/surname
2. `rank_position` - Get top players at a position
3. `analyze_squad` - Analyze squad points, budget, xG, injury risks
4. `suggest_transfer` - Recommend best transfer (sell weakest → buy strongest)
5. `validate_budget` - Check if squad fits within budget
6. `get_player_report` - Premium scouting report with xG and injury data
7. `get_current_world_cup_data` - Read the dated FIFA roster and fixture snapshot
8. `propose_lineup` - Build a position-valid starting XI with stable player IDs

### x402 Payment Verification

All Gemini and Analytics features require a server-side entitlement:

- x402 v2 challenges use `PAYMENT-REQUIRED`; paid retries use `PAYMENT-SIGNATURE`; successful access returns `PAYMENT-RESPONSE`.
- The backend stores membership/pass expiry and an access transaction audit record. It never treats `hasPaidX402` as authoritative in production.
- The `Kaan` account starts locked and may explicitly activate a free `demo_pro` membership. No other account receives that bypass.
- Arbitrary simulated purchases are disabled by default, even when `X402_DEMO_MODE=true`. They additionally require `X402_ALLOW_SIMULATED_PURCHASES=true`.
- Production requires a configured facilitator, `X402_ASSET`, and non-zero `X402_PAY_TO` receiver. The adapter calls facilitator `/verify` and `/settle` before granting access.

### CCTP USDC Bridging

Bridge 20 USDC from Ethereum to Injective to expand squad budget:

- Uses Circle's CCTP protocol
- Burn → Attest → Mint flow
- Returns transaction hash for verification
- Simulated if no real credentials configured

### MCP Server

Standalone MCP server exposing squad tools:

- `apply_transfer` - Execute player swap
- `apply_lineup` - Validate a confirmed starting XI by player ID
- `get_squad` - Get current squad state
- `set_formation` - Change formation
- `get_player_details` - Get player info

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

Required for production:
- `GEMINI_API_KEY` - Get from [Google AI Studio](https://makersuite.google.com/)
- `CIRCLE_API_KEY` - Get from [Circle Developer Portal](https://developers.circle.com/)

Optional for demo/local development:
- Leave empty for simulated behavior (x402, CCTP, Gemini fallback)
- Keep `X402_ALLOW_SIMULATED_PURCHASES=false`; Kaan's scoped demo still works.

### 3. Run the server

Windows (PowerShell):
```bash
.\run.ps1
```

Linux/Mac:
```bash
./run.sh
```

Or manually:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Access API

- API Root: http://localhost:8000
- Interactive Docs: http://localhost:8000/docs
- Health Check: http://localhost:8000/health

## Frontend Integration

The Next.js frontend should be configured to call the Python backend:

1. Add to `.env.local`:
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

2. Update `app/page.tsx` fetch calls:
```typescript
const API_URL = process.env.NEXT_PUBLIC_API_URL || '';

fetch(`${API_URL}/api/players`)
fetch(`${API_URL}/api/agent`, ...)
fetch(`${API_URL}/api/cctp`, ...)
```

## Development

### Running the MCP server standalone

```bash
python -m app.mcp.server
```

### Testing endpoints

```bash
# Get players
curl http://localhost:8000/api/players

# Agent chat (returns the capability/paywall text while locked)
curl -X POST http://localhost:8000/api/agent \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Tell me about Mbappe", "squadPlayerIds": [], "hasPaidX402": false}'

# CCTP bridge
curl -X POST http://localhost:8000/api/cctp \
  -H "Content-Type: application/json" \
  -d '{"walletAddress": "0x123...", "amount": 20, "sourceChain": "Ethereum"}'

# Execute transfer
curl -X POST http://localhost:8000/api/transfers/execute \
  -H "Content-Type: application/json" \
  -d '{"sellPlayerId": "arg_gk_martinez", "buyPlayerId": "fra_gk_maignan", "reasoning": "Need upgrade", "squadPlayerIds": ["arg_gk_martinez"]}'
```

## Troubleshooting

### Gemini not configured

If `GEMINI_API_KEY` is not set, the agent falls back to rule-based logic.
Check server logs for:
```
Warning: GEMINI_API_KEY not configured. Falling back to rule-based logic.
```

### x402 verification failing

If x402 facilitator is not configured, non-Kaan users remain locked. Configure
`X402_FACILITATOR_URL`, `X402_PAY_TO`, `X402_ASSET`, and the correct CAIP-2
`X402_NETWORK` for real verification. The local Kaan demo membership is always
labelled simulated and creates a zero-USDC audit receipt.

### CCTP simulation

Without wallet signing and a live Circle/Injective adapter, CCTP returns a realistic, explicitly labelled simulation. The API never treats a simulated receipt as a real on-chain settlement.

## License

MIT
