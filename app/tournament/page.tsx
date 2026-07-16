'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import TournamentHub from '@/components/TournamentHub';
import { apiFetch } from '@/lib/api';
import type { AccessStatus, TournamentOverview } from '@/types';

export default function TournamentPage() {
  const [overview, setOverview] = useState<TournamentOverview | null>(null);
  const [accessStatus, setAccessStatus] = useState<AccessStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async (refresh = false) => {
    setLoading(true);
    setError(null);
    try {
      const [tournament, access] = await Promise.all([
        apiFetch<TournamentOverview>(`/api/worldcup/tournament${refresh ? '?refresh=true' : ''}`),
        apiFetch<AccessStatus>('/api/access/status').catch(() => null),
      ]);
      setOverview(tournament);
      setAccessStatus(access);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Tournament feed could not be loaded.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => { void load(); }, 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  return <main className="command-page hq-shell px-4 py-6 text-on-surface md:px-8"><div className="hq-orb hq-orb-gold" /><div className="hq-orb hq-orb-green" /><div className="relative mx-auto max-w-[1600px]"><Link href="/" className="mb-5 inline-flex items-center gap-2 text-sm font-bold text-primary hover:text-secondary">← Return to INJ Control</Link>{loading && <div className="rounded-xl border border-outline-variant/30 bg-surface-container-low p-8 text-on-surface-variant">Loading tournament intelligence…</div>}{error && <div className="rounded-xl border border-rose-400/30 bg-rose-400/10 p-6"><p className="font-bold text-rose-100">Tournament HQ unavailable</p><p className="mt-2 text-sm text-rose-100/80">{error}</p><button onClick={() => void load()} className="mt-4 rounded-md bg-primary px-3 py-2 text-sm font-bold text-on-primary">Retry</button></div>}{overview && !loading && <TournamentHub overview={overview} onRefresh={() => void load(true)} isPremiumUnlocked={accessStatus?.hasAnalyticsAccess ?? false} />}</div></main>;
}
