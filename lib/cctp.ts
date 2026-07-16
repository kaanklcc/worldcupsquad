'use client';

import {
  createPublicClient,
  createWalletClient,
  custom,
  getAddress,
  http,
  pad,
  parseAbi,
  type Address,
  type Hex,
} from 'viem';
import { injectiveEvmTestnet } from '@injectivelabs/x402/networks';

export type Eip1193Provider = {
  request: (args: { method: string; params?: unknown[] }) => Promise<unknown>;
};

export interface CctpConfig {
  source: { chainId: number; chainName: string; rpcUrl: string; usdc: Address; domain: number };
  destination: { chainId: number; chainName: string; rpcUrl: string; usdc: Address; domain: number };
  tokenMessenger: Address;
  messageTransmitter: Address;
  explorers: { source: string; destination: string };
}

export const sepolia = {
  id: 11155111,
  name: 'Ethereum Sepolia',
  nativeCurrency: { name: 'Sepolia Ether', symbol: 'ETH', decimals: 18 },
  rpcUrls: { default: { http: ['https://ethereum-sepolia-rpc.publicnode.com'] } },
  blockExplorers: { default: { name: 'Etherscan', url: 'https://sepolia.etherscan.io' } },
  testnet: true,
} as const;

const erc20Abi = parseAbi([
  'function approve(address spender, uint256 amount) returns (bool)',
  'function allowance(address owner, address spender) view returns (uint256)',
]);
const tokenMessengerAbi = parseAbi([
  'function depositForBurn(uint256 amount, uint32 destinationDomain, bytes32 mintRecipient, address burnToken, bytes32 destinationCaller, uint256 maxFee, uint32 minFinalityThreshold)',
]);
const messageTransmitterAbi = parseAbi([
  'function receiveMessage(bytes message, bytes attestation) returns (bool)',
]);

function ethereumProvider(): Eip1193Provider {
  const provider = (window as typeof window & { ethereum?: Eip1193Provider }).ethereum;
  if (!provider) throw new Error('MetaMask or another EVM wallet is required for the CCTP testnet bridge.');
  return provider;
}

function paddedAddress(address: Address): Hex {
  return pad(getAddress(address), { size: 32 });
}

export async function connectWalletOnChain(chain: 'sepolia' | 'injective'): Promise<Address> {
  const provider = ethereumProvider();
  const target = chain === 'sepolia'
    ? { chainId: '0xaa36a7', chainName: 'Ethereum Sepolia', rpcUrls: ['https://ethereum-sepolia-rpc.publicnode.com'], nativeCurrency: { name: 'Sepolia Ether', symbol: 'ETH', decimals: 18 }, blockExplorerUrls: ['https://sepolia.etherscan.io'] }
    : { chainId: '0x59f', chainName: 'Injective EVM Testnet', rpcUrls: ['https://k8s.testnet.json-rpc.injective.network/'], nativeCurrency: { name: 'Injective', symbol: 'INJ', decimals: 18 }, blockExplorerUrls: ['https://testnet.blockscout.injective.network/'] };
  try {
    await provider.request({ method: 'wallet_switchEthereumChain', params: [{ chainId: target.chainId }] });
  } catch (error) {
    const code = (error as { code?: number }).code;
    if (code !== 4902) throw error;
    await provider.request({ method: 'wallet_addEthereumChain', params: [target] });
  }
  const accounts = await provider.request({ method: 'eth_requestAccounts' }) as string[];
  if (!accounts[0]) throw new Error('The wallet did not return an account.');
  return getAddress(accounts[0]);
}

export async function approveAndBurn(config: CctpConfig, account: Address, amountUsdc: number): Promise<Hex> {
  const provider = ethereumProvider();
  const walletClient = createWalletClient({ account, chain: sepolia, transport: custom(provider) });
  const publicClient = createPublicClient({ chain: sepolia, transport: http(config.source.rpcUrl) });
  const amount = BigInt(amountUsdc) * BigInt(1_000_000);
  const allowance = await publicClient.readContract({ address: config.source.usdc, abi: erc20Abi, functionName: 'allowance', args: [account, config.tokenMessenger] });
  if (allowance < amount) {
    const approval = await walletClient.writeContract({ address: config.source.usdc, abi: erc20Abi, functionName: 'approve', args: [config.tokenMessenger, amount] });
    await publicClient.waitForTransactionReceipt({ hash: approval });
  }
  // CCTP standard transfers use a zero maxFee and standard finality. The
  // destination is the same connected EVM address on Injective testnet.
  const burnHash = await walletClient.writeContract({
    address: config.tokenMessenger,
    abi: tokenMessengerAbi,
    functionName: 'depositForBurn',
    args: [amount, config.destination.domain, paddedAddress(account), config.source.usdc, paddedAddress('0x0000000000000000000000000000000000000000'), BigInt(0), 2000],
  });
  await publicClient.waitForTransactionReceipt({ hash: burnHash });
  return burnHash;
}

export async function mintAttestedUsdc(config: CctpConfig, account: Address, message: Hex, attestation: Hex): Promise<Hex> {
  const provider = ethereumProvider();
  const walletClient = createWalletClient({ account, chain: injectiveEvmTestnet, transport: custom(provider) });
  const publicClient = createPublicClient({ chain: injectiveEvmTestnet, transport: http(config.destination.rpcUrl) });
  const mintHash = await walletClient.writeContract({
    address: config.messageTransmitter,
    abi: messageTransmitterAbi,
    functionName: 'receiveMessage',
    args: [message, attestation],
  });
  await publicClient.waitForTransactionReceipt({ hash: mintHash });
  return mintHash;
}
