# Auto-Gaffer

**World Cup 2026 Fantasy Football Manager** — built for the Injective Global Cup Hackathon.

Auto-Gaffer is an AI-powered fantasy football management dashboard where you act as the "gaffer" (manager): build your squad within a USDC budget, consult an AI tactical assistant for data-driven transfer recommendations, bridge USDC cross-chain via CCTP, and execute on-chain transfers via MCP.

---

## What It Does

- **Build your squad** on an interactive pitch with 4-3-3, 4-2-3-1, 3-5-2, 4-4-2, and 5-3-2 formations
- **Consult an AI assistant** (Gemini-powered) that analyzes your squad, ranks players by position, and recommends transfers with reasoning
- **Unlock premium analytics** via x402 payment — deep scouting reports with xG data, injury risk, and one-click transfer actions
- **Bridge 20 USDC** from Ethereum to Injective via CCTP to expand your budget from 100M to 120M
- **Execute transfers on-chain** via the MCP server — every swap is processed through Model Context Protocol tools

---

## Architecture

```
worldcupsquad/
├── app/                    # Next.js 16 frontend (React 19, Tailwind 4)
│   ├── page.tsx            # Main dashboard (pitch, chat, sidebar)
│   └── api/                # Legacy TS route handlers (kept as fallback)
├── components/             # UI components (Pitch, ChatPanel, Header, etc.)
├── data/                   # Shared player database (28 World Cup players)
├── types/                  # TypeScript type definitions
└── backend/                # Python FastAPI backend (port 8000)
    └── app/
        ├── routers/        # API endpoints (/api/players, /agent, /cctp, /transfers)
        ├── agent/          # Gemini LLM + function-calling Agent Skills
        ├── mcp/            # MCP server + client for squad tools
        ├── x402.py         # x402 payment verification
        ├── cctp_flow.py    # CCTP burn-attest-mint flow
        └── models.py       # Pydantic models
```

### Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 16, React 19, Tailwind CSS 4 |
| Backend | Python, FastAPI, Pydantic |
| AI Agent | Google Gemini 2.5 Flash with function calling |
| Payments | x402 (HTTP 402 Payment Required) |
| Bridging | CCTP (Circle Cross-Chain Transfer Protocol) |
| Agent Tools | MCP (Model Context Protocol) |

---

## Injective Technologies Used

### 1. x402 — Payment Required Protocol

**Where:** `backend/app/x402.py`, `backend/app/routers/agent.py`

The premium tier (deep scouting reports, xG data, injury risk analysis, AI transfer suggestions) is gated behind x402 payment verification. When a user clicks "Unlock Deep Tactical Analytics", the backend verifies the x402 payment receipt before granting access to premium agent skills.

- Free tier: basic player info, position rankings, general advice
- Premium tier (x402): xG/game, injury risk, scout notes, executable transfer suggestions
- The `X-Payment` header is verified against a facilitator; demo mode trusts the `hasPaidX402` flag

### 2. USDC CCTP — Cross-Chain Transfer Protocol

**Where:** `backend/app/cctp_flow.py`, `backend/app/routers/cctp.py`

Users can bridge 20 USDC from Ethereum to Injective using Circle's CCTP protocol. This expands their squad budget from 100M to 120M USDC. The backend implements the burn → attest → mint flow:

- Burns USDC on the source domain (Ethereum)
- Fetches attestation from Circle's Iris API
- Mints USDC on the destination domain (Injective)
- Returns a transaction hash for verification
- Falls back to a clearly-labeled realistic simulation when no wallet keys are configured

### 3. MCP Server — Model Context Protocol

**Where:** `backend/app/mcp/server.py`, `backend/app/mcp/client.py`, `backend/app/routers/transfers.py`

A standalone MCP server exposes squad management tools that the backend calls to execute transfers. This replaces simulated client-side swaps with real MCP-roundtripped actions:

- `apply_transfer` — Execute a player swap (sell X → buy Y)
- `get_squad` — Retrieve current squad state
- `set_formation` — Change formation
- `get_player_details` — Get detailed player info

Every transfer returns an MCP receipt with a transaction hash, timestamp, and structured data.

### 4. Agent Skills — Function-Calling Tools

**Where:** `backend/app/agent/skills.py`, `backend/app/agent/gemini_client.py`

The AI consultant is powered by Google Gemini 2.5 Flash with native function calling. Six "Agent Skills" are registered as tools the LLM can invoke autonomously:

| Skill | Description |
|-------|-------------|
| `search_player` | Find a player by name/surname with accent-insensitive matching |
| `rank_position` | Get top players at a position sorted by points |
| `analyze_squad` | Calculate total points, budget, xG average, injury risks |
| `suggest_transfer` | AI-powered sell/buy recommendation with reasoning |
| `validate_budget` | Check if squad fits within budget |
| `get_player_report` | Premium scouting report with xG, alternatives, positional rank |

The agent decides which skills to call based on the user's question. Falls back to rule-based logic if no `GEMINI_API_KEY` is configured.

---

## Is Injective Integrated?

**Yes.** The project is built around Injective's ecosystem:

- The wallet system uses Injective addresses (`inj1...`)
- CCTP bridges USDC **to Injective** as the destination chain
- On-chain transfers are simulated on the Injective chain (testnet-ready via `injective-py`)
- The entire budget economy is denominated in USDC on Injective

For full production on-chain integration, set `INJECTIVE_MNEMONIC` in the backend `.env` to enable real wallet signing on Injective testnet.

---

## Getting Started

### Prerequisites

- Node.js 18+ (frontend)
- Python 3.10+ (backend)
- Google Gemini API key (optional — falls back to rule-based agent)

### 1. Start the Python Backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env   # Add your GEMINI_API_KEY (optional)
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API docs available at http://localhost:8000/docs

### 2. Start the Next.js Frontend

```bash
npm install
npm run dev
```

Open http://localhost:3000

### 3. How Users Interact

1. The dashboard loads 28 World Cup players from the backend
2. Click empty slots on the pitch to add players within your 100M budget
3. Chat with the AI assistant (free) or unlock Premium (x402) for deep analytics
4. The AI suggests transfers — click "Confirm Tactical Change" to execute via MCP
5. Click "Acquire Backing" to bridge 20 USDC via CCTP and expand your budget
6. Click "Execute Changes" to sync your squad on-chain

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/players` | Get all 28 World Cup players |
| POST | `/api/agent` | Chat with AI consultant (free + premium via x402) |
| POST | `/api/cctp` | Bridge USDC via CCTP |
| POST | `/api/transfers/execute` | Execute transfer via MCP |
| GET | `/docs` | Interactive API documentation |

---

## Project Structure

- **Frontend:** `app/`, `components/`, `types/` — Next.js dashboard
- **Backend:** `backend/app/` — FastAPI server with Gemini, x402, CCTP, MCP
- **Shared Data:** `data/worldcup_players.json` — 28 players with stats and premium analytics

---

Built for the **Injective Global Cup Hackathon 2026** ⚽
