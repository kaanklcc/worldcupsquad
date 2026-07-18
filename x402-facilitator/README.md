# WCAI private x402 facilitator (Injective EVM Testnet)

This small service is the real x402 `/verify` and `/settle` boundary used by WCAI. It wraps the official `@injectivelabs/x402` `InjectiveFacilitator` and is intentionally separate from the FastAPI application.

Its private key is **not** a user key, MetaMask key, payment receiver key, or mainnet treasury. Create a fresh, low-balance, **Injective EVM Testnet-only burner wallet** for it and fund it only with enough test INJ to pay testnet settlement gas. Never reuse a personal wallet or commit the file.

## Configure

```powershell
Copy-Item .env.example .env
```

Fill these fields in `x402-facilitator/.env`:

```env
# Fresh testnet burner private key. This is the only secret in this file.
X402_FACILITATOR_PRIVATE_KEY=

# Public Injective EVM Testnet receiver address for WCAI access payments.
X402_PAY_TO=

# Optional. Required if the API and facilitator are not both bound to loopback.
X402_FACILITATOR_TOKEN=
```

Keep the public defaults unchanged unless Injective changes them:

```env
X402_NETWORK=eip155:1439
X402_ASSET=0x0C382e685bbeeFE5d3d9C29e29E341fEE8E84C5d
X402_FACILITATOR_RPC_URL=https://k8s.testnet.json-rpc.injective.network/
X402_MIN_ATOMIC_AMOUNT=50000
X402_MAX_ATOMIC_AMOUNT=5000000
```

The API’s `backend/.env` must use the same receiver, asset and network:

```env
X402_FACILITATOR_URL=http://127.0.0.1:4021
X402_PAY_TO=<same value>
X402_ASSET=0x0C382e685bbeeFE5d3d9C29e29E341fEE8E84C5d
X402_NETWORK=eip155:1439
# Set this to the same value only when X402_FACILITATOR_TOKEN is set above.
X402_FACILITATOR_TOKEN=
```

## Run and check

From the repository root:

```powershell
npm run facilitator
```

In a second terminal:

```powershell
Invoke-WebRequest http://127.0.0.1:4021/health | Select-Object -ExpandProperty Content
```

Expected configured response:

```json
{"service":"wcai-x402-facilitator","configured":true,"network":"eip155:1439","testnetOnly":true}
```

The service binds to `127.0.0.1` by default. If an operator changes the host, a bearer token is mandatory; WCAI passes it from `X402_FACILITATOR_TOKEN`. Do not expose `/verify` or `/settle` directly to the browser or public internet.

The service rejects a payment requirement unless the network, USDC asset, receiver and amount are exactly within WCAI’s configured testnet limits. It does not grant WCAI membership itself; FastAPI grants access only after both facilitator verification and settlement succeed.
