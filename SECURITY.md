# Security policy

WCAI is a hackathon project and its blockchain integrations are testnet-only by design. Please do not open a public issue with an API key, JWT, wallet seed phrase, private key, transaction signature, or a reproducible security detail.

Report a potential issue privately to the repository owner with the affected route or file, a concise reproduction and the security impact. Do not send funds or attempt to access another user's account while testing.

## Operator rules

- Keep `backend/.env`, `.env.local` and `x402-facilitator/.env` out of Git.
- `X402_PAY_TO` is public and may be a testnet receiver. The facilitator private key must be a separate, low-balance testnet burner key.
- Never configure a mainnet RPC, mainnet USDC or a personal-wallet private key for this demo.
- Rotate any key that is pasted into a chat, issue, screenshot, terminal recording or committed by mistake.
- Deploy FastAPI behind HTTPS with explicit `CORS_ORIGINS`; keep the facilitator private to the API network.

The app never requests a MetaMask seed phrase or private key. Browser wallet transactions are signed in MetaMask, and the backend verifies resulting public receipts.
