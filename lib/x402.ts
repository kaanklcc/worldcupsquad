'use client';

import { createPublicClient, createWalletClient, custom, getAddress, http, type Address } from 'viem';
import { createNonce, getTokenName, signAuthorization } from '@injectivelabs/x402/eip3009';
import { injectiveEvmTestnet } from '@injectivelabs/x402/networks';
import { API_URL, authHeaders } from '@/lib/api';
import type { Eip1193Provider } from '@/lib/cctp';

interface PaymentRequirement {
  scheme: 'exact';
  network: string;
  amount: string;
  asset: Address;
  payTo: Address;
  maxTimeoutSeconds: number;
  extra: Record<string, unknown>;
}

function provider(): Eip1193Provider {
  const ethereum = (window as typeof window & { ethereum?: Eip1193Provider }).ethereum;
  if (!ethereum) throw new Error('MetaMask or another EVM wallet is required for x402 payment.');
  return ethereum;
}

function encodeBase64(value: unknown): string {
  const bytes = new TextEncoder().encode(JSON.stringify(value));
  let binary = '';
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return window.btoa(binary);
}

function decodeRequired(response: Response, body: unknown): PaymentRequirement {
  const detail = (body as { detail?: { accepts?: PaymentRequirement[] } })?.detail;
  const fromBody = detail?.accepts?.[0];
  if (fromBody) return fromBody;
  const header = response.headers.get('PAYMENT-REQUIRED');
  if (!header) throw new Error('The WCAI payment endpoint did not return x402 requirements.');
  const decoded = JSON.parse(new TextDecoder().decode(Uint8Array.from(window.atob(header), (char) => char.charCodeAt(0)))) as { accepts?: PaymentRequirement[] };
  if (!decoded.accepts?.[0]) throw new Error('The x402 payment requirements are invalid.');
  return decoded.accepts[0];
}

async function switchToInjectiveTestnet(wallet: Eip1193Provider): Promise<Address> {
  const chain = { chainId: '0x59f', chainName: 'Injective EVM Testnet', rpcUrls: ['https://k8s.testnet.json-rpc.injective.network/'], nativeCurrency: { name: 'Injective', symbol: 'INJ', decimals: 18 }, blockExplorerUrls: ['https://testnet.blockscout.injective.network/'] };
  try {
    await wallet.request({ method: 'wallet_switchEthereumChain', params: [{ chainId: chain.chainId }] });
  } catch (error) {
    if ((error as { code?: number }).code !== 4902) throw error;
    await wallet.request({ method: 'wallet_addEthereumChain', params: [chain] });
  }
  const accounts = await wallet.request({ method: 'eth_requestAccounts' }) as string[];
  if (!accounts[0]) throw new Error('The wallet did not return an account.');
  return getAddress(accounts[0]);
}

function responseError(body: unknown, status: number): Error {
  const detail = (body as { detail?: unknown; message?: unknown })?.detail;
  const message = typeof detail === 'string' ? detail : typeof (body as { message?: unknown })?.message === 'string' ? String((body as { message: string }).message) : `x402 request failed (${status})`;
  return new Error(message);
}

/**
 * Browser-wallet x402 v2 flow: request -> 402 -> EIP-3009 signature -> retry.
 * The wallet signs an authorization only; the configured facilitator verifies
 * and settles it, so WCAI never receives a wallet private key.
 */
export async function payWithX402<T>(path: string, body: Record<string, unknown>, idempotencyKey: string): Promise<T> {
  const initialHeaders = authHeaders({ 'Content-Type': 'application/json', 'Idempotency-Key': idempotencyKey });
  const init: RequestInit = { method: 'POST', headers: initialHeaders, body: JSON.stringify(body) };
  const initial = await fetch(`${API_URL}${path}`, init);
  const initialBody = await initial.json().catch(() => ({}));
  if (initial.status !== 402) {
    if (!initial.ok) throw responseError(initialBody, initial.status);
    return initialBody as T;
  }

  const requirement = decodeRequired(initial, initialBody);
  if (requirement.network !== 'eip155:1439') throw new Error(`WCAI offered unsupported x402 network ${requirement.network}.`);
  const walletProvider = provider();
  const account = await switchToInjectiveTestnet(walletProvider);
  const walletClient = createWalletClient({ account, chain: injectiveEvmTestnet, transport: custom(walletProvider) });
  const publicClient = createPublicClient({ chain: injectiveEvmTestnet, transport: http('https://k8s.testnet.json-rpc.injective.network/') });
  const now = BigInt(Math.floor(Date.now() / 1000));
  const authorization = {
    from: account,
    to: getAddress(requirement.payTo),
    value: BigInt(requirement.amount),
    validAfter: now - BigInt(10),
    validBefore: now + BigInt(requirement.maxTimeoutSeconds),
    nonce: createNonce(),
  };
  const version = typeof requirement.extra.version === 'string' ? requirement.extra.version : '2';
  const tokenName = await getTokenName(publicClient, requirement.asset);
  const signature = await signAuthorization(walletClient, requirement.asset, tokenName, 1439, authorization, version);
  const payment = {
    x402Version: 2,
    accepted: requirement,
    payload: {
      signature,
      authorization: {
        from: authorization.from,
        to: authorization.to,
        value: authorization.value.toString(),
        validAfter: authorization.validAfter.toString(),
        validBefore: authorization.validBefore.toString(),
        nonce: authorization.nonce,
      },
    },
  };
  const retryHeaders = authHeaders({
    'Content-Type': 'application/json',
    'Idempotency-Key': idempotencyKey,
    'PAYMENT-SIGNATURE': encodeBase64(payment),
    'X-Payment': encodeBase64(payment),
  });
  const retry = await fetch(`${API_URL}${path}`, { method: 'POST', headers: retryHeaders, body: JSON.stringify(body) });
  const retryBody = await retry.json().catch(() => ({}));
  if (!retry.ok) throw responseError(retryBody, retry.status);
  return retryBody as T;
}
