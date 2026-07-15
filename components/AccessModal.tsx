'use client';

import { useState } from 'react';
import type { AccessStatus } from '@/types';

type AccessMode = 'membership' | 'single_use';

interface AccessModalProps {
  isOpen: boolean;
  status: AccessStatus | null;
  isLoading: boolean;
  error?: string | null;
  onClose: () => void;
  onUnlock: (mode: AccessMode, walletAddress?: string) => void;
  onSaveWallet: (walletAddress: string) => void;
}

type EthereumProvider = {
  request: (args: { method: string; params?: unknown[] }) => Promise<unknown>;
};

export default function AccessModal({
  isOpen,
  status,
  isLoading,
  error,
  onClose,
  onUnlock,
  onSaveWallet,
}: AccessModalProps) {
  const [walletAddress, setWalletAddress] = useState(status?.walletAddress ?? '');
  const [walletError, setWalletError] = useState<string | null>(null);

  if (!isOpen) return null;

  const connectInjectiveWallet = async () => {
    setWalletError(null);
    const ethereum = (window as typeof window & { ethereum?: EthereumProvider }).ethereum;
    if (!ethereum) {
      setWalletError('MetaMask bulunamadı. inj1... veya 0x... adresini elle girebilirsin.');
      return;
    }

    try {
      try {
        await ethereum.request({
          method: 'wallet_switchEthereumChain',
          params: [{ chainId: '0x59f' }],
        });
      } catch {
        await ethereum.request({
          method: 'wallet_addEthereumChain',
          params: [{
            chainId: '0x59f',
            chainName: 'Injective EVM Testnet',
            rpcUrls: ['https://k8s.testnet.json-rpc.injective.network/'],
            nativeCurrency: { name: 'Injective', symbol: 'INJ', decimals: 18 },
            blockExplorerUrls: ['https://testnet.blockscout.injective.network/'],
          }],
        });
      }
      const accounts = await ethereum.request({ method: 'eth_requestAccounts' }) as string[];
      const address = accounts?.[0];
      if (!address) throw new Error('Wallet account was not returned');
      setWalletAddress(address);
      onSaveWallet(address);
    } catch (connectError) {
      setWalletError(connectError instanceof Error ? connectError.message : 'Wallet connection failed.');
    }
  };

  const activeLabel = status?.membershipActive
    ? `${status.membershipTier === 'demo_pro' ? 'Demo Pro' : 'Pro'} aktif`
    : status?.accessPassActive
      ? 'Match Pass aktif'
      : 'Erişim kilitli';

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center p-4">
      <button aria-label="Close membership dialog" className="absolute inset-0 bg-black/80 backdrop-blur-md" onClick={onClose} />
      <section className="relative z-10 w-full max-w-3xl overflow-hidden rounded-2xl border border-amber-400/25 bg-slate-950 text-slate-100 shadow-2xl">
        <div className="flex items-start justify-between border-b border-slate-800 px-6 py-5">
          <div>
            <div className="mb-1 text-[10px] font-bold uppercase tracking-[0.25em] text-amber-400">Auto-Gaffer Access</div>
            <h2 className="font-display-lg text-2xl uppercase">AI, Analytics & Injective Finance</h2>
            <p className="mt-1 text-xs text-slate-400">{activeLabel} · {status?.x402Network ?? 'eip155:1439'}</p>
          </div>
          <button onClick={onClose} className="rounded-full p-2 text-slate-400 transition hover:bg-slate-800 hover:text-white">
            <span className="material-symbols-outlined">close</span>
          </button>
        </div>

        <div className="grid gap-5 p-6 md:grid-cols-2">
          <div className="rounded-xl border border-amber-400/25 bg-amber-400/[0.06] p-5">
            <span className="material-symbols-outlined text-3xl text-amber-400">workspace_premium</span>
            <h3 className="mt-3 font-display-lg text-xl uppercase">Pro Membership</h3>
            <p className="mt-2 text-sm leading-relaxed text-slate-300">
              Gemini AI sohbeti, sınırsız Deep Tactical Analytics, MCP kadro/transfer uygulama ve CCTP finans özellikleri.
            </p>
            <div className="mt-4 text-2xl font-bold text-amber-300">
              {status?.isDemoAccount ? 'Ücretsiz demo' : `${status?.pricing.membershipUsdc ?? 4.99} USDC`}
            </div>
            <p className="text-[10px] uppercase tracking-wider text-slate-500">
              {status?.isDemoAccount ? 'Kaan hesabına özel · ücret kesilmez' : `${status?.pricing.membershipDays ?? 30} gün · x402`}
            </p>
            <button
              onClick={() => onUnlock('membership', walletAddress || undefined)}
              disabled={isLoading || Boolean(status?.membershipActive)}
              className="gold-gradient mt-5 w-full rounded py-3 font-display-lg text-xs font-bold uppercase text-slate-950 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {status?.membershipActive ? 'Membership Active' : isLoading ? 'Activating...' : status?.isDemoAccount ? 'Activate Free Demo Membership' : 'Pay with x402'}
            </button>
          </div>

          <div className="rounded-xl border border-emerald-400/20 bg-emerald-400/[0.05] p-5">
            <span className="material-symbols-outlined text-3xl text-emerald-400">bolt</span>
            <h3 className="mt-3 font-display-lg text-xl uppercase">x402 Match Pass</h3>
            <p className="mt-2 text-sm leading-relaxed text-slate-300">
              Tek maç planlaması için AI sohbeti, kadro analizi ve Analytics araçlarına süreli erişim. CCTP finansı üyelik gerektirir.
            </p>
            <div className="mt-4 text-2xl font-bold text-emerald-300">{status?.pricing.singleAccessUsdc ?? 0.05} USDC</div>
            <p className="text-[10px] uppercase tracking-wider text-slate-500">{status?.pricing.singleAccessMinutes ?? 15} dakika · x402</p>
            <button
              onClick={() => onUnlock('single_use', walletAddress || undefined)}
              disabled={isLoading || Boolean(status?.hasAiAccess) || Boolean(status?.isDemoAccount)}
              className="mt-5 w-full rounded border border-emerald-400/50 bg-emerald-500/15 py-3 font-display-lg text-xs font-bold uppercase text-emerald-200 transition hover:bg-emerald-500/25 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {status?.accessPassActive ? 'Pass Active' : 'Unlock Match Pass'}
            </button>
          </div>
        </div>

        <div className="mx-6 mb-6 rounded-xl border border-slate-800 bg-slate-900/70 p-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <label className="flex-1 text-[10px] font-bold uppercase tracking-wider text-slate-400">
              Injective wallet
              <input
                value={walletAddress}
                onChange={(event) => setWalletAddress(event.target.value)}
                placeholder="inj1... or 0x..."
                className="mt-2 w-full rounded border border-slate-700 bg-slate-950 px-3 py-2.5 text-xs normal-case text-white outline-none focus:border-amber-400"
              />
            </label>
            <button onClick={connectInjectiveWallet} disabled={isLoading} className="rounded border border-slate-700 px-4 py-2.5 text-xs font-bold uppercase text-slate-200 hover:border-amber-400">
              Connect Injective
            </button>
            <button onClick={() => onSaveWallet(walletAddress)} disabled={isLoading || !walletAddress.trim()} className="rounded bg-slate-800 px-4 py-2.5 text-xs font-bold uppercase text-white hover:bg-slate-700 disabled:opacity-40">
              Save Wallet
            </button>
          </div>
          {(error || walletError) && <p className="mt-3 text-xs text-red-300">{error || walletError}</p>}
          <p className="mt-3 text-[10px] leading-relaxed text-slate-500">
            {status?.paymentMode === 'demo'
              ? status?.isDemoAccount
                ? 'Kaan hackathon demo hesabı: üyelik ücretsiz etkinleştirilir, gerçek USDC transfer edilmez ve demo makbuzu denetim kaydına yazılır.'
                : 'Yerel demo ortamı: bu hesap ücretsiz açılamaz. Gerçek x402 ödeme testi için facilitator ve alıcı adresi yapılandırılmalıdır.'
              : 'Production modu: PAYMENT-SIGNATURE sunucuda facilitator üzerinden doğrulanmadan erişim açılmaz.'}
          </p>
        </div>
      </section>
    </div>
  );
}
