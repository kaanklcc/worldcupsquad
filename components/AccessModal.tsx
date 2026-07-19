'use client';

import { useEffect, useState } from 'react';
import type { AccessStatus } from '@/types';

type AccessMode = 'membership' | 'single_use';
type AccessMethod = 'demo' | 'x402';
type EthereumProvider = { request: (args: { method: string; params?: unknown[] }) => Promise<unknown> };

interface AccessModalProps {
  isOpen: boolean;
  status: AccessStatus | null;
  isLoading: boolean;
  error?: string | null;
  onClose: () => void;
  onUnlock: (mode: AccessMode, walletAddress?: string, accessMethod?: AccessMethod) => void;
  onSaveWallet: (walletAddress: string) => void;
}

function remainingLabel(expiresAt: string | null | undefined, now: number): string | null {
  if (!expiresAt) return null;
  const remaining = Math.max(0, Date.parse(expiresAt) - now);
  const minutes = Math.floor(remaining / 60_000);
  const seconds = Math.floor((remaining % 60_000) / 1_000);
  return `${minutes}:${seconds.toString().padStart(2, '0')} remaining`;
}

function isCurrent(active: boolean | undefined, expiresAt: string | null | undefined, now: number): boolean {
  if (!active) return false;
  return !expiresAt || Date.parse(expiresAt) > now;
}

export default function AccessModal({ isOpen, status, isLoading, error, onClose, onUnlock, onSaveWallet }: AccessModalProps) {
  const [walletAddress, setWalletAddress] = useState(status?.walletAddress ?? '');
  const [walletError, setWalletError] = useState<string | null>(null);
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (!isOpen) return;
    const tick = window.setInterval(() => setNow(Date.now()), 1_000);
    return () => window.clearInterval(tick);
  }, [isOpen]);

  if (!isOpen) return null;

  const membershipCurrent = isCurrent(status?.membershipActive, status?.membershipExpiresAt, now);
  const passCurrent = isCurrent(status?.accessPassActive, status?.accessPassExpiresAt, now);
  const currentExpiry = membershipCurrent ? status?.membershipExpiresAt : passCurrent ? status?.accessPassExpiresAt : null;
  const countdown = remainingLabel(currentExpiry, now);
  const duration = status?.demoDurationMinutes ?? 30;
  const effectiveWallet = walletAddress || status?.walletAddress || '';
  const demoAvailable = Boolean(status?.demoAccessAvailable);
  const hasCurrentAccess = membershipCurrent || passCurrent;
  const activeLabel = membershipCurrent
    ? `${status?.membershipTier === 'demo_pro' ? 'Hackathon Demo Pro' : 'Pro'} active`
    : passCurrent
      ? 'Demo Match Pass active'
      : 'Access locked';

  const connectInjectiveWallet = async () => {
    setWalletError(null);
    const ethereum = (window as typeof window & { ethereum?: EthereumProvider }).ethereum;
    if (!ethereum) {
      setWalletError('MetaMask was not found. Enter an inj1... or 0x... address manually.');
      return;
    }
    try {
      try {
        await ethereum.request({ method: 'wallet_switchEthereumChain', params: [{ chainId: '0x59f' }] });
      } catch {
        await ethereum.request({ method: 'wallet_addEthereumChain', params: [{ chainId: '0x59f', chainName: 'Injective EVM Testnet', rpcUrls: ['https://k8s.testnet.json-rpc.injective.network/'], nativeCurrency: { name: 'Injective', symbol: 'INJ', decimals: 18 }, blockExplorerUrls: ['https://testnet.blockscout.injective.network/'] }] });
      }
      const accounts = await ethereum.request({ method: 'eth_requestAccounts' }) as string[];
      if (!accounts?.[0]) throw new Error('Wallet account was not returned.');
      setWalletAddress(accounts[0]);
      onSaveWallet(accounts[0]);
    } catch (connectError) {
      setWalletError(connectError instanceof Error ? connectError.message : 'Wallet connection failed.');
    }
  };

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center p-4">
      <button aria-label="Close membership dialog" className="absolute inset-0 bg-black/80 backdrop-blur-md" onClick={onClose} />
      <section className="relative z-10 max-h-[92vh] w-full max-w-3xl overflow-y-auto rounded-2xl border border-amber-400/25 bg-slate-950 text-slate-100 shadow-2xl">
        <header className="flex items-start justify-between border-b border-slate-800 px-6 py-5">
          <div>
            <p className="mb-1 text-[10px] font-bold uppercase tracking-[.25em] text-amber-400">WCAI Access</p>
            <h2 className="font-display-lg text-2xl uppercase">AI, Analytics & Injective Finance</h2>
            <p className="mt-1 text-xs text-slate-400">
              {activeLabel}{countdown ? ` · ${countdown}` : ''} · {status?.x402Network ?? 'eip155:1439'}
            </p>
          </div>
          <button aria-label="Close" onClick={onClose} className="rounded-full p-2 text-slate-400 transition hover:bg-slate-800 hover:text-white">
            <span className="material-symbols-outlined">close</span>
          </button>
        </header>

        {demoAvailable && (
          <div className="mx-6 mt-5 rounded-xl border border-cyan-300/25 bg-cyan-300/[.07] p-4">
            <p className="text-[10px] font-bold uppercase tracking-[.2em] text-cyan-300">Hackathon judge checkout</p>
            <p className="mt-2 text-sm leading-relaxed text-slate-300">
              Choose a plan to activate it for {duration} minutes. This is a labelled simulation: no wallet signature, blockchain settlement or funds are charged. A replay-safe demo receipt is still written to the Action Ledger.
            </p>
          </div>
        )}

        <div className="grid gap-5 p-6 md:grid-cols-2">
          <section className="rounded-xl border border-amber-400/25 bg-amber-400/[.06] p-5">
            <span className="material-symbols-outlined text-3xl text-amber-400">workspace_premium</span>
            <h3 className="mt-3 font-display-lg text-xl uppercase">{demoAvailable ? 'Hackathon Demo Pro' : 'Pro Membership'}</h3>
            <p className="mt-2 text-sm leading-relaxed text-slate-300">Gemini chat, Deep Tactical Analytics, MCP lineup and transfer actions, plus the Injective finance console.</p>
            {demoAvailable ? (
              <>
                <p className="mt-4 text-2xl font-bold text-amber-300">0 USDC <span className="text-sm font-normal text-slate-500 line-through">{status?.pricing.membershipUsdc ?? 4.99} test USDC</span></p>
                <p className="text-[10px] uppercase tracking-wider text-slate-500">{duration} minutes · no charge · simulated receipt</p>
              </>
            ) : (
              <>
                <p className="mt-4 text-2xl font-bold text-amber-300">{status?.pricing.membershipUsdc ?? 4.99} USDC</p>
                <p className="text-[10px] uppercase tracking-wider text-slate-500">{status?.pricing.membershipDays ?? 30} days · verified x402</p>
              </>
            )}
            <button
              onClick={() => onUnlock('membership', effectiveWallet || undefined, demoAvailable ? 'demo' : 'x402')}
              disabled={isLoading || membershipCurrent}
              className="gold-gradient mt-5 w-full rounded py-3 font-display-lg text-xs font-bold uppercase text-slate-950 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {membershipCurrent ? `Active${countdown ? ` · ${countdown}` : ''}` : isLoading ? 'Activating…' : demoAvailable ? `Activate ${duration}-min Demo Pro` : 'Pay with x402'}
            </button>
          </section>

          <section className="rounded-xl border border-emerald-400/20 bg-emerald-400/[.05] p-5">
            <span className="material-symbols-outlined text-3xl text-emerald-400">bolt</span>
            <h3 className="mt-3 font-display-lg text-xl uppercase">{demoAvailable ? 'Hackathon Match Pass' : 'x402 Match Pass'}</h3>
            <p className="mt-2 text-sm leading-relaxed text-slate-300">Time-limited Gemini chat, squad analysis and Tactical Lab access. The CCTP finance console requires Demo Pro or paid Pro.</p>
            {demoAvailable ? (
              <>
                <p className="mt-4 text-2xl font-bold text-emerald-300">0 USDC <span className="text-sm font-normal text-slate-500 line-through">{status?.pricing.singleAccessUsdc ?? 0.05} test USDC</span></p>
                <p className="text-[10px] uppercase tracking-wider text-slate-500">{duration} minutes · no charge · simulated receipt</p>
              </>
            ) : (
              <>
                <p className="mt-4 text-2xl font-bold text-emerald-300">{status?.pricing.singleAccessUsdc ?? 0.05} USDC</p>
                <p className="text-[10px] uppercase tracking-wider text-slate-500">{status?.pricing.singleAccessMinutes ?? 15} minutes · verified x402</p>
              </>
            )}
            <button
              onClick={() => onUnlock('single_use', effectiveWallet || undefined, demoAvailable ? 'demo' : 'x402')}
              disabled={isLoading || hasCurrentAccess}
              className="mt-5 w-full rounded border border-emerald-400/50 bg-emerald-500/15 py-3 font-display-lg text-xs font-bold uppercase text-emerald-200 transition hover:bg-emerald-500/25 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {passCurrent ? `Active${countdown ? ` · ${countdown}` : ''}` : demoAvailable ? `Activate ${duration}-min Match Pass` : 'Unlock Match Pass'}
            </button>
          </section>
        </div>

        <div className="mx-6 mb-6 rounded-xl border border-slate-800 bg-slate-900/70 p-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <label className="flex-1 text-[10px] font-bold uppercase tracking-wider text-slate-400">
              Injective wallet
              <input value={effectiveWallet} onChange={(event) => setWalletAddress(event.target.value)} placeholder="inj1... or 0x..." className="mt-2 w-full rounded border border-slate-700 bg-slate-950 px-3 py-2.5 text-xs normal-case text-white outline-none focus:border-amber-400" />
            </label>
            <button onClick={connectInjectiveWallet} disabled={isLoading} className="rounded border border-slate-700 px-4 py-2.5 text-xs font-bold uppercase text-slate-200 hover:border-amber-400">Connect Injective</button>
            <button onClick={() => onSaveWallet(effectiveWallet)} disabled={isLoading || !effectiveWallet.trim()} className="rounded bg-slate-800 px-4 py-2.5 text-xs font-bold uppercase text-white hover:bg-slate-700 disabled:opacity-40">Save wallet</button>
          </div>
          {(error || walletError) && <p className="mt-3 text-xs text-red-300">{error || walletError}</p>}
          <p className="mt-3 text-[10px] leading-relaxed text-slate-500">
            {demoAvailable
              ? 'Wallet connection is optional for Demo Pass activation. It is only needed for the separate, browser-signed Injective testnet x402 and CCTP flows.'
              : 'Access remains locked until the server verifies PAYMENT-SIGNATURE and facilitator settlement.'}
          </p>
          {demoAvailable && status?.x402Ready && !membershipCurrent && (
            <button onClick={() => onUnlock('membership', effectiveWallet || undefined, 'x402')} disabled={isLoading || !effectiveWallet.trim()} className="mt-3 text-[10px] font-bold uppercase tracking-wider text-cyan-300 hover:text-cyan-200 disabled:opacity-40">
              Use wallet-signed Injective testnet x402 instead
            </button>
          )}
        </div>
      </section>
    </div>
  );
}
