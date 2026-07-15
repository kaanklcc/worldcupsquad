# Auto-Gaffer

Auto-Gaffer is a World Cup 2026 fantasy football command centre built for the Injective Global Cup Hackathon. A fan builds a squad with a USDC-denominated budget, asks Gemini for tactical help, and approves structured transfer actions through an MCP tool.

The product solves a simple fan problem: World Cup fantasy decisions are spread across player stats, tactical context, and funding actions. Auto-Gaffer brings those decisions into one explainable workflow.

## What the demo does

- Build a squad on an interactive pitch with 4-3-3, 4-2-3-1, 3-5-2, 4-4-2, and 5-3-2 formations.
- Search the 104-player FIFA-announced rosters of the four 2026 semi-finalists (Argentina, England, France, Spain) by position, price, availability, and points.
- Ask a Gemini-powered tactical assistant to search players, rank positions, analyse the squad, read the dated World Cup snapshot, and propose a structured starting XI.
- Confirm an AI lineup in the UI to apply the exact player IDs and formation after server-side budget and position validation.
- Open Matchday to load the dated FIFA fixture snapshot for the two semi-finals; unknown scores and official starting XIs are not invented.
- Gate deep scouting data and executable transfer recommendations behind x402 verification.
- Bridge a one-time 20 USDC budget boost through the CCTP flow. Local development uses a clearly labelled simulation until wallet signing is configured.
- Approve a transfer through the backend MCP client. The default transport starts the standalone MCP server over stdio and returns a structured receipt.
- Persist a validated squad to SQLite, with server-side catalog, position, duplicate, availability, and budget checks.

## Hackathon technology mapping

| Injective technology | How Auto-Gaffer uses it | Current demo status |
| --- | --- | --- |
| x402 | Premium agent access accepts `X-Payment` / `X-Payment-Receipt` and verifies them through a configurable facilitator. | `X402_DEMO_MODE=true` allows a walletless local demo; disable it for a real facilitator. |
| USDC CCTP | The backing flow models source burn → Circle attestation → destination mint and increases the Injective budget by 20 USDC. | The current local flow returns a labelled deterministic simulation; production wallet signing is the next integration step. |
| MCP Server | `backend/app/mcp/server.py` exposes `get_squad`, `apply_transfer`, `apply_lineup`, `set_formation`, and `get_player_details`. Confirmed transfer and lineup APIs call the server through MCP stdio by default. | Real MCP stdio is enabled by default. Set `MCP_SIMULATION=true` for an offline fallback. |
| Agent Skills | Gemini function calling exposes player search, rankings, squad analysis, budget validation, current World Cup snapshot, lineup proposals, transfer suggestions, and premium reports. | Gemini uses `GEMINI_MODEL`; a rule-based fallback remains available without a key. |

Injective is the destination-chain and wallet context for the product. The repo demonstrates the application workflow and protocol boundaries. World Cup data is represented by a dated FIFA roster/fixture snapshot with source URLs; a production deployment should refresh it from an authenticated live feed before each matchday.

## Architecture

```text
Next.js 16 / React 19 UI
  ├─ pitch, squad selection, chat, auth, receipts
  └─ lib/api.ts → authenticated requests

FastAPI backend
  ├─ routers/          auth, players, agent, squad, transfers, CCTP
  ├─ agent/            Gemini client + Agent Skills + fallback logic
  ├─ mcp/              standalone MCP server + stdio client
  ├─ x402.py           payment verification boundary
  ├─ cctp_flow.py      CCTP burn/attest/mint adapter boundary
  └─ data.py / db.py   shared player catalog + SQLite persistence
```

## Stack

- Frontend: Next.js 16.2, React 19, Tailwind CSS 4
- Backend: Python 3.10+, FastAPI, Pydantic, SQLite
- AI: Google Gemini API with function calling
- Protocols: x402, Circle CCTP, Model Context Protocol

## Run locally

### Backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# Add GEMINI_API_KEY when Gemini responses are required.
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

On Windows PowerShell, `Copy-Item .env.example .env` is equivalent to `cp`.

Important local settings:

```env
GEMINI_MODEL=gemini-3.1-flash-lite
X402_DEMO_MODE=true
MCP_SIMULATION=false
```

`MCP_SIMULATION=false` starts `app.mcp.server` as a child process and calls it through the MCP stdio protocol. Use `true` only when running an offline presentation or when the child process cannot be started.

### Frontend

```bash
npm install
npm run dev
```

Open http://localhost:3000. The frontend expects the backend at `http://localhost:8000`; set `NEXT_PUBLIC_API_URL` in `.env.local` to change it.

## Demo walkthrough

1. Register a manager and log in.
2. Add players to the pitch. The picker contains the four semi-finalist FIFA roster snapshots and the backend re-validates catalog, position, availability, duplicates, and budget.
3. Ask the AI about a player, a position, the current matchday, or a starting XI such as “Arjantin–İngiltere için 4-3-3 kadro öner”.
4. Review the structured lineup card and click **Apply AI Lineup**. The exact IDs are validated and persisted only after confirmation.
5. Request Deep Tactical Analytics. In local demo mode, x402 is represented by the explicit `X402_DEMO_MODE` switch.
6. Review the proposed sell/buy action and click **Confirm Tactical Change**.
7. Watch the MCP receipt. It is marked as simulated only when the configured transport is simulated.
8. Use **Acquire Backing** once to run the CCTP flow and expand the budget by 20M.
9. Use **Execute Changes** to persist the final squad snapshot.

## API

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/api/auth/register` | Create a manager |
| `POST` | `/api/auth/login` | Get a JWT session |
| `GET` | `/api/players` | Load the World Cup player catalog |
| `GET` | `/api/players/meta` | Load roster snapshot date and FIFA source URLs |
| `GET` | `/api/worldcup/snapshot` | Load dated FIFA semifinal fixtures and provenance |
| `POST` | `/api/agent` | Chat with Gemini / fallback agent |
| `GET` | `/api/squad/load` | Load the authenticated squad |
| `POST` | `/api/squad/save` | Validate and persist a squad snapshot |
| `POST` | `/api/squad/apply-lineup` | Apply a confirmed structured AI lineup |
| `POST` | `/api/transfers/execute` | Validate and execute an MCP transfer |
| `POST` | `/api/cctp` | Run the one-time CCTP backing flow |
| `GET` | `/docs` | OpenAPI / Swagger documentation |

## Verification

```bash
npm run lint
npm run build

cd backend
python -m compileall -q app
```

The repository intentionally labels simulated CCTP/MCP paths in API responses and the UI. This keeps the hackathon demo usable while making the boundary to live wallet, attestation, and matchday data integrations clear.

Built for the **Injective Global Cup Hackathon 2026**.
