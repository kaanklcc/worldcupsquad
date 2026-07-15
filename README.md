# Auto-Gaffer

Auto-Gaffer is a membership-first World Cup 2026 fantasy football command centre built for the Injective Global Cup Hackathon. A fan builds a squad with a USDC-denominated budget, unlocks Gemini and Deep Tactical Analytics through membership or x402, and approves structured lineup/transfer actions through an MCP tool.

The product solves a simple fan problem: World Cup fantasy decisions are spread across player stats, tactical context, and funding actions. Auto-Gaffer brings those decisions into one explainable workflow.

## What the demo does

- Build a squad on an interactive pitch with 4-3-3, 4-2-3-1, 3-5-2, 4-4-2, and 5-3-2 formations.
- Search the 104-player FIFA-announced rosters of the four 2026 semi-finalists (Argentina, England, France, Spain) by position, price, availability, and points.
- Unlock every Gemini conversation and Analytics request through a server-side Pro membership or a 15-minute x402 Match Pass. Locked prompts never reach Gemini and instead return a complete feature/access explanation.
- Ask the entitled Gemini-powered tactical assistant to search players, rank positions, analyse the squad, read the dated World Cup snapshot, and propose a structured starting XI.
- Confirm an AI lineup in the UI to apply the exact player IDs and formation after server-side budget and position validation.
- Open Matchday to load the dated FIFA fixture snapshot for the two semi-finals; unknown scores and official starting XIs are not invented.
- Open **Tournament HQ** for a 48-team World Cup directory: group overview, knockout bracket, filterable fixtures, and squad-scoped Scout Cards. The schedule is clearly marked as a community live feed; player-level data remains limited to dated FIFA roster snapshots.
- Compare players in the original **Scout Card** view: price, verified goals/assists where available, model xG, points, readiness and source status are kept distinct.
- Click any selected player on the main pitch to open an individual **Player Intel Card**. It fetches player-specific source metadata plus a clearly labelled Auto-Gaffer model layer: radar, five-point signal trend, tactical attributes and scout brief. The small left swap control preserves replacement; the red control removes the player.
- Run one unified Deep Tactical Analytics flow from the sidebar or chat panel. It evaluates formation balance, authenticated budget, verified World Cup contributions, model xG, availability, injury risk and price efficiency before producing an executable action.
- Open **Gaffer Matchday Brief** for a source-aware pre-match cockpit: fixture context, budget-valid XI, captain/vice-captain signals, risk flags and two tactical scenarios.
- Use the premium **What-if Tactical Lab** to compare all supported formations against the same server-side budget without mutating the saved squad; only a separate explicit apply action can change the pitch.
- Confirm or explicitly reject every AI lineup/transfer proposal. Rejection leaves the persisted squad unchanged.
- Use the `Kaan` judge/demo account in a deliberately locked initial state, then activate all Pro features for free from the membership dialog. This branch is username-scoped, labelled simulated and never charges money.
- Bridge a one-time 20 USDC budget boost through the CCTP flow. Local development uses a clearly labelled simulation until wallet signing is configured.
- Approve a transfer through the backend MCP client. The default transport starts the standalone MCP server over stdio and returns a structured receipt.
- Open **Action Ledger** to inspect a durable intent and receipt for every membership unlock, lineup application, transfer and CCTP attempt. The same `Idempotency-Key` returns its original receipt and cannot silently replay a provider mutation.
- The redesigned **Manager Ledger** is also the x402 access console: it explains what Pro / Match Pass unlocks, opens the wallet + membership dialog, filters access/tactical/funding receipts, and exposes receipt details without describing demo transport as a real settlement.
- Persist a validated squad to SQLite, with server-side catalog, position, duplicate, availability, and budget checks.

## Hackathon technology mapping

| Injective technology | How Auto-Gaffer uses it | Current demo status |
| --- | --- | --- |
| x402 | Membership and Match Pass purchases expose an HTTP 402 challenge with the x402 v2 `PAYMENT-REQUIRED`, `PAYMENT-SIGNATURE`, and `PAYMENT-RESPONSE` flow. Entitlements are stored server-side and protected endpoints never trust a browser premium flag. | Kaan has a username-scoped, zero-charge demo grant. All other accounts remain payment-gated by default; optional simulated purchases require an additional explicit environment flag. Configure a compatible facilitator and receiver for settlement. |
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
  ├─ routers/          auth, access, players, agent, squad, transfers, CCTP
  ├─ agent/            Gemini client + Agent Skills + fallback logic
  ├─ mcp/              standalone MCP server + stdio client
  ├─ access.py         membership/pass policy + entitlement audit records
  ├─ x402.py           x402 facilitator verification boundary
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
X402_ALLOW_SIMULATED_PURCHASES=false
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

1. Log in with the Kaan judge/demo account. Its AI, Analytics and Finance access starts locked.
2. Open **Membership Locked** or **Unlock Deep Tactical Analytics**, then select **Activate Free Demo Membership**. The receipt explicitly says that no money was charged.
3. Add players to the pitch. The picker contains the four semi-finalist FIFA roster snapshots and the backend re-validates catalog, position, availability, duplicates, and budget.
4. Ask the AI about a player, a position, the current matchday, or a starting XI such as “Arjantin–İngiltere için 3-5-2 kadro öner”.
5. Review the structured lineup card and choose **Apply Lineup** or **Reject**. The exact IDs are persisted only after confirmation.
6. Open **Analytics** or run **Deep Tactical Analytics**. Both use the same richer analysis pipeline.
7. Review the budget-valid sell/buy action and choose **Confirm Change** or **Reject**.
8. Connect/save an Injective wallet and use **Acquire Backing** once to run the CCTP flow and expand the budget by 20M.
9. Watch the MCP/CCTP receipts; simulations are visibly labelled.
10. Use **Execute Changes** to persist the final squad snapshot.

### Regression tests

The backend includes a no-network `unittest` suite covering the premium gate, x402 v2 challenge, replay-safe membership receipts, wallet/CCTP invariants, exact formation persistence, idempotent lineup application, transfer validation, Tournament HQ provenance, Matchday Brief provenance and Tactical Lab access. Run it from the repository root:

```powershell
backend\venv\Scripts\python.exe -m unittest discover -s backend\tests -v
```

## API

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/api/auth/register` | Create a manager |
| `POST` | `/api/auth/login` | Get a JWT session |
| `GET` | `/api/players` | Load the World Cup player catalog |
| `GET` | `/api/players/{player_id}/intel` | Load one player’s source-aware Intel Card data and labelled model signals |
| `GET` | `/api/players/meta` | Load roster snapshot date and FIFA source URLs |
| `GET` | `/api/worldcup/snapshot` | Load dated FIFA semifinal fixtures and provenance |
| `GET` | `/api/worldcup/tournament` | Load 48-team groups, fixtures, bracket and source-aware roster details |
| `GET` | `/api/worldcup/matchday-brief` | Load a budget-valid, source-aware Matchday Brief |
| `POST` | `/api/tactical-lab/compare` | Premium, non-mutating formation comparison |
| `POST` | `/api/agent` | Chat with Gemini / fallback agent |
| `GET` | `/api/access/status` | Read server-side membership, Match Pass, wallet and feature access |
| `POST` | `/api/access/unlock` | Activate Kaan demo membership or process an x402 access purchase |
| `POST` | `/api/access/wallet` | Validate and save an Injective/EVM wallet address |
| `GET` | `/api/squad/load` | Load the authenticated squad |
| `POST` | `/api/squad/save` | Validate and persist a squad snapshot |
| `POST` | `/api/squad/apply-lineup` | Apply a confirmed structured AI lineup |
| `POST` | `/api/transfers/execute` | Validate and execute an MCP transfer |
| `POST` | `/api/cctp` | Run the one-time CCTP backing flow |
| `GET` | `/api/operations/recent` | Read the authenticated manager's durable action ledger |
| `GET` | `/docs` | OpenAPI / Swagger documentation |

## Verification

```bash
npm run lint
npm run build

cd backend
python -m compileall -q app
```

The repository intentionally labels simulated CCTP/MCP paths in API responses and the UI. This keeps the hackathon demo usable while making the boundary to live wallet, attestation, and matchday data integrations clear.

### Payment and chain boundaries

- The official x402 v2 flow is `402 Payment Required` → `PAYMENT-REQUIRED` → client-signed `PAYMENT-SIGNATURE` → facilitator verification/settlement → `PAYMENT-RESPONSE`. The local Kaan branch bypasses this only as an explicit zero-charge judge demo.
- `X402_DEMO_MODE=true` does **not** unlock arbitrary users. Set `X402_ALLOW_SIMULATED_PURCHASES=true` only for a labelled presentation environment.
- Real x402 deployment requires `X402_FACILITATOR_URL`, `X402_ASSET`, and a non-zero `X402_PAY_TO`; production use refuses zero token/receiver addresses. Access is granted only after facilitator verification **and settlement**.
- Access grants, MCP lineup/transfer mutations and CCTP backing use a durable idempotency ledger. A completed receipt is replayed for the same `Idempotency-Key`; a key cannot be reused for a different payload. A simulated receipt is never represented as a chain settlement.
- CCTP is accurately described as USDC burn → Circle attestation → destination mint. The included adapter remains visibly simulated until wallet signing and Circle configuration are provided.

References: [Injective USDC + CCTP tutorial](https://docs.injective.network/developers-defi/usdc-cctp-tutorial), [Injective EVM network information](https://docs.injective.network/developers-evm/network-information), [x402 v2 flow](https://docs.cdp.coinbase.com/x402/core-concepts/how-it-works).

Built for the **Injective Global Cup Hackathon 2026**.
