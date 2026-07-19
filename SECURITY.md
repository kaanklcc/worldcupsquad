# Security policy

WCAI is a hackathon project and its blockchain integrations are testnet-only by design. Please do not open a public issue with an API key, JWT, wallet seed phrase, private key, transaction signature, or a reproducible security detail.

Report a potential issue privately to the repository owner with the affected route or file, a concise reproduction and the security impact. Do not send funds or attempt to access another user's account while testing.

## Operator rules

- Keep `backend/.env`, `.env.local` and `x402-facilitator/.env` out of Git.
- `X402_PAY_TO` is public and may be a testnet receiver. The facilitator private key must be a separate, low-balance testnet burner key.
- Never configure a mainnet RPC, mainnet USDC or a personal-wallet private key for this demo.
- Rotate any key that is pasted into a chat, issue, screenshot, terminal recording or committed by mistake.
- Deploy FastAPI behind HTTPS with exact `CORS_ORIGINS` and `ALLOWED_HOSTS`; set `AUTH_COOKIE_SECURE=true` and normally `DOCS_ENABLED=false`.
- Keep the facilitator on loopback or a private API network. If it is reachable beyond loopback, configure the same high-entropy `X402_FACILITATOR_TOKEN` on both services.
- Demo access is configuration-based and never tied to a privileged username. Keep `X402_ALLOW_SIMULATED_PURCHASES=true` only when the public judge demo is intentionally available.
- Put a reverse proxy request/rate limit in front of a multi-instance deployment. The built-in limiter is process-local and is intended for the single-instance hackathon demo.
- Do not change the configured CCTP or x402 networks/assets to mainnet for this submission.

The app never requests a MetaMask seed phrase or private key. Browser wallet transactions are signed in MetaMask, and the backend verifies resulting public receipts. Browser authentication uses an HttpOnly session cookie plus CSRF validation. Password recovery uses a random one-time code shown at registration—not guessable security questions—and payment/bridge receipts are one-time consumable records.
