/**
 * WCAI's private, testnet-only x402 facilitator.
 *
 * It exposes the standard /verify and /settle boundaries consumed by the
 * FastAPI backend. The user's MetaMask remains non-custodial: this process
 * only holds a separate, low-balance burner key to pay Injective testnet gas.
 */
import { createServer } from 'node:http';
import { existsSync } from 'node:fs';
import { resolve } from 'node:path';
import { isAddress } from 'viem';
import { InjectiveFacilitator } from '@injectivelabs/x402/facilitator';

const envFile = resolve('x402-facilitator/.env');
if (existsSync(envFile)) process.loadEnvFile(envFile);

const zeroAddress = '0x0000000000000000000000000000000000000000';
const config = {
  host: process.env.X402_FACILITATOR_HOST || '127.0.0.1',
  port: Number(process.env.X402_FACILITATOR_PORT || 4021),
  privateKey: process.env.X402_FACILITATOR_PRIVATE_KEY || '',
  token: process.env.X402_FACILITATOR_TOKEN || '',
  network: process.env.X402_NETWORK || 'eip155:1439',
  asset: (process.env.X402_ASSET || '').toLowerCase(),
  payTo: (process.env.X402_PAY_TO || '').toLowerCase(),
  rpcUrl: process.env.X402_FACILITATOR_RPC_URL || '',
  minAmount: BigInt(process.env.X402_MIN_ATOMIC_AMOUNT || '50000'),
  maxAmount: BigInt(process.env.X402_MAX_ATOMIC_AMOUNT || '5000000'),
};

const configured = /^0x[a-fA-F0-9]{64}$/.test(config.privateKey)
  && isAddress(config.asset)
  && config.asset !== zeroAddress
  && isAddress(config.payTo)
  && config.payTo !== zeroAddress
  && Number.isInteger(config.port)
  && config.port > 0;

const facilitator = configured
  ? new InjectiveFacilitator({
      privateKey: config.privateKey,
      rpcUrl: config.rpcUrl || undefined,
      allowedAssets: [config.asset],
      minPaymentPerAsset: { [config.asset]: config.minAmount.toString() },
      confirmations: 1,
    })
  : null;

function sendJson(response, status, payload) {
  response.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'no-store',
    'X-Content-Type-Options': 'nosniff',
  });
  response.end(JSON.stringify(payload));
}

function isLoopback(address = '') {
  return address === '127.0.0.1' || address === '::1' || address === '::ffff:127.0.0.1';
}

function isAuthorized(request) {
  if (config.token) return request.headers.authorization === `Bearer ${config.token}`;
  return isLoopback(request.socket.remoteAddress);
}

function validRequirement(body) {
  const requirement = body?.paymentRequirements;
  if (!requirement || requirement.network !== config.network) return 'unsupported network';
  if (String(requirement.asset || '').toLowerCase() !== config.asset) return 'unsupported asset';
  if (String(requirement.payTo || '').toLowerCase() !== config.payTo) return 'unexpected payment receiver';
  try {
    const amount = BigInt(requirement.amount);
    if (amount < config.minAmount || amount > config.maxAmount) return 'payment amount outside WCAI limits';
  } catch {
    return 'invalid payment amount';
  }
  return null;
}

async function parseJson(request) {
  let raw = '';
  for await (const chunk of request) {
    raw += chunk;
    if (raw.length > 65_536) throw new Error('request body too large');
  }
  return JSON.parse(raw || '{}');
}

const server = createServer(async (request, response) => {
  if (request.method === 'GET' && request.url === '/health') {
    return sendJson(response, configured ? 200 : 503, {
      service: 'wcai-x402-facilitator',
      configured,
      network: config.network,
      testnetOnly: config.network === 'eip155:1439',
    });
  }

  if (request.method !== 'POST' || !['/verify', '/settle'].includes(request.url || '')) {
    return sendJson(response, 404, { error: 'not_found' });
  }
  if (!isAuthorized(request)) return sendJson(response, 401, { error: 'unauthorized' });
  if (!facilitator) return sendJson(response, 503, { error: 'facilitator_not_configured' });

  try {
    const body = await parseJson(request);
    const invalid = validRequirement(body);
    if (invalid) return sendJson(response, 422, { error: invalid });
    const result = request.url === '/verify'
      ? await facilitator.verify(body)
      : await facilitator.settle(body);
    return sendJson(response, 200, result);
  } catch (error) {
    return sendJson(response, 400, { error: error instanceof Error ? error.message : 'invalid_request' });
  }
});

server.listen(config.port, config.host, () => {
  console.log(`WCAI x402 facilitator listening on http://${config.host}:${config.port} (${configured ? 'configured' : 'configuration required'})`);
});
