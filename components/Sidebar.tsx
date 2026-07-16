'use client';

import Link from 'next/link';

interface SidebarProps {
  activeTab: string;
  onTabClick: (tab: string) => void;
  onExecuteClick: () => void;
  onLogout?: () => void;
  hasAnalyticsAccess?: boolean;
  hasFinanceAccess?: boolean;
}

const primaryItems: Array<{ tab: string; icon: string; label: string; access?: 'analytics' | 'finance' }> = [
  { tab: 'AI Consultant', icon: 'psychology', label: 'Lineup' },
  { tab: 'Substitutions', icon: 'swap_vert', label: 'Substitutions' },
  { tab: 'Matchday', icon: 'sports_soccer', label: 'Matchday' },
  { tab: 'Analytics', icon: 'query_stats', label: 'Analytics', access: 'analytics' },
  { tab: 'Tactical Lab', icon: 'science', label: 'Tactical Lab', access: 'analytics' },
  { tab: 'Finance', icon: 'payments', label: 'Finance', access: 'finance' },
] as const;

export default function Sidebar({ activeTab, onTabClick, onExecuteClick, onLogout, hasAnalyticsAccess, hasFinanceAccess }: SidebarProps) {
  return (
    <aside className="hidden xl:flex h-full w-80 flex-col gap-stack-md border-r border-outline-variant/10 bg-surface-container-low/95 px-4 py-8 shadow-[10px_0_30px_rgba(0,0,0,0.3)] backdrop-blur-lg">
      <div className="mb-6 px-4">
        <h2 className="font-display-lg text-headline-md uppercase tracking-widest text-on-surface">INJ CONTROL</h2>
        <p className="mt-1 font-label-sm text-label-sm text-primary">Tactical Command</p>
      </div>
      <nav className="flex flex-1 flex-col gap-1.5">
        {primaryItems.map((item) => {
          const locked = item.access === 'analytics' ? !hasAnalyticsAccess : item.access === 'finance' ? !hasFinanceAccess : false;
          return (
            <button key={item.tab} onClick={() => onTabClick(item.tab)} className={`flex w-full items-center gap-4 px-4 py-2.5 text-left transition-all ${activeTab === item.tab ? 'translate-x-1 border-l-4 border-secondary bg-primary-container font-bold text-on-primary-container' : 'text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface'}`}>
              <span className="material-symbols-outlined" style={item.tab === 'AI Consultant' ? { fontVariationSettings: "'FILL' 1" } : undefined}>{item.icon}</span>
              <span className="font-body-md text-body-md uppercase tracking-widest">{item.label}</span>
              {locked && <span className="material-symbols-outlined ml-auto text-sm text-amber-400">lock</span>}
            </button>
          );
        })}
        <div className="my-2 border-t border-outline-variant/20" />
        <Link href="/tournament" className="flex items-center gap-4 px-4 py-2.5 text-on-surface-variant transition hover:bg-surface-container-high hover:text-on-surface"><span className="material-symbols-outlined">emoji_events</span><span className="font-body-md text-body-md uppercase tracking-widest">Tournament HQ</span></Link>
        <Link href="/transactions" className="flex items-center gap-4 px-4 py-2.5 text-on-surface-variant transition hover:bg-surface-container-high hover:text-on-surface"><span className="material-symbols-outlined">receipt_long</span><span className="font-body-md text-body-md uppercase tracking-widest">Action Ledger</span></Link>
      </nav>
      <button onClick={onExecuteClick} className="emerald-gradient mx-4 mb-4 mt-auto rounded-sm px-4 py-3 font-display-lg text-body-md uppercase text-on-primary shadow-lg transition-all hover:brightness-110">Execute changes</button>
      <footer className="flex flex-col gap-2 border-t border-outline-variant/20 px-4 pt-4">
        <a href="#" className="flex items-center gap-4 py-2 font-mono-jb text-xs uppercase tracking-widest text-on-surface-variant transition-colors hover:text-on-surface"><span className="material-symbols-outlined">help</span>Support</a>
        <button onClick={onLogout} className="flex w-full items-center gap-4 py-2 text-left font-mono-jb text-xs uppercase tracking-widest text-on-surface-variant transition-colors hover:text-on-surface"><span className="material-symbols-outlined">logout</span>Log out</button>
      </footer>
    </aside>
  );
}
