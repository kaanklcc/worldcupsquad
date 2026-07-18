'use client';

import Link from 'next/link';
import type { AccessStatus } from '@/types';

interface HeaderProps {
  budget: number;
  maxBudget: number;
  onAcquireBacking: () => void;
  cctpLoading: boolean;
  cctpUsed: boolean;
  accessStatus: AccessStatus | null;
  onAccessClick: () => void;
  onLogout: () => void;
}

export default function Header({
  budget,
  maxBudget,
  onAcquireBacking,
  cctpLoading,
  cctpUsed,
  accessStatus,
  onAccessClick,
  onLogout,
}: HeaderProps) {
  const wallet = accessStatus?.walletAddress;
  const walletLabel = wallet ? `${wallet.slice(0, 6)}…${wallet.slice(-4)}` : 'Connect wallet';
  const accessLabel = accessStatus?.membershipActive
    ? accessStatus.membershipTier === 'demo_pro' ? 'Demo Pro' : 'Pro Member'
    : accessStatus?.accessPassActive ? 'Match Pass' : 'Membership Locked';

  return (
    <nav className="bg-surface-dim/90 backdrop-blur-xl docked full-width top-0 z-50 border-b border-outline-variant/20 shadow-[0_2px_15px_rgba(0,0,0,0.05)] flex justify-between items-center px-6 md:px-12 py-3 w-full flex-shrink-0">
      {/* Left section */}
      <div className="flex items-center gap-4">
        <div className="h-10 w-10 rounded-full border-2 border-primary bg-primary-container flex items-center justify-center drop-shadow-[0_0_8px_rgba(223,181,59,0.5)]">
          <span className="text-xl">⚽</span>
        </div>
        <span className="font-display-lg text-xl text-primary drop-shadow-[0_0_8px_rgba(223,181,59,0.5)] tracking-tight">
          WCAI
        </span>
      </div>

      {/* Right section */}
      <div className="flex items-center gap-6">
        <div className="hidden lg:flex items-center gap-1">
          <Link href="/tournament" className="rounded-md px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-on-surface-variant transition hover:bg-surface-container-high hover:text-primary">HQ</Link>
          <Link href="/transactions" className="rounded-md px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-on-surface-variant transition hover:bg-surface-container-high hover:text-primary">Ledger</Link>
        </div>
        <button
          onClick={onAccessClick}
          className={`hidden md:flex items-center gap-2 rounded-full border px-3 py-1.5 text-left transition ${
            accessStatus?.hasAiAccess
              ? 'border-emerald-400/30 bg-emerald-500/10 text-emerald-300'
              : 'border-amber-400/30 bg-amber-400/10 text-amber-300 hover:bg-amber-400/20'
          }`}
        >
          <span className="material-symbols-outlined text-base">{accessStatus?.hasAiAccess ? 'verified' : 'lock'}</span>
          <span className="flex flex-col">
            <span className="text-[9px] font-bold uppercase tracking-wider">{accessLabel}</span>
            <span className="text-[9px] text-slate-400">{walletLabel}</span>
          </span>
        </button>

        {/* Wallet pill */}
        <div className="glass-panel px-4 py-1.5 rounded-full flex items-center gap-3">
          <div className="flex flex-col items-end">
            <span className="font-label-sm text-[10px] text-on-surface-variant uppercase">
              Manager Wallet
            </span>
            <span className="font-label-sm text-xs text-primary font-bold">
              {budget}M/{maxBudget}M USDC
            </span>
          </div>
          <span className="material-symbols-outlined text-primary text-lg">
            account_balance_wallet
          </span>
        </div>

        {/* Action button */}
        <button
          onClick={onAcquireBacking}
          disabled={cctpUsed || cctpLoading}
          className={`gold-gradient font-display-lg text-xs uppercase px-5 py-1.5 rounded-sm shadow-md transition-all ${
            cctpUsed
              ? 'opacity-50 cursor-not-allowed'
              : 'hover:brightness-110'
          }`}
        >
          {cctpLoading ? 'PROCESSING...' : cctpUsed ? '✓ BACKING ACQUIRED' : accessStatus?.hasFinanceAccess ? 'ACQUIRE BACKING' : 'UNLOCK FINANCE'}
        </button>

        {/* Icons area */}
        <div className="hidden sm:flex gap-4 text-on-surface items-center">
          <span className="material-symbols-outlined hover:text-primary transition-colors cursor-pointer text-xl">
            notifications_active
          </span>
          <button
            onClick={onLogout}
            title="Log out"
            className="w-8 h-8 rounded-full border border-outline-variant bg-surface-container-high flex items-center justify-center transition hover:border-primary hover:text-primary"
          >
            <span className="material-symbols-outlined text-on-surface-variant text-base">logout</span>
          </button>
        </div>
      </div>
    </nav>
  );
}
