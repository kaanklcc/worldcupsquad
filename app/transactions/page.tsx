'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import AccessModal from '@/components/AccessModal';
import TransactionLedger from '@/components/TransactionLedger';
import { apiFetch } from '@/lib/api';
import type { AccessStatus, AccessUnlockResponse, OperationReceipt } from '@/types';

function createIdempotencyKey(action: string): string {
  const suffix = typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  return `gaffer-${action}-${suffix}`;
}

export default function TransactionsPage() {
  const [operations, setOperations] = useState<OperationReceipt[]>([]);
  const [accessStatus, setAccessStatus] = useState<AccessStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [accessOpen, setAccessOpen] = useState(false);
  const [accessLoading, setAccessLoading] = useState(false);
  const [accessError, setAccessError] = useState<string | null>(null);
  const load = useCallback(async () => { setLoading(true); setError(null); try { const [ledger, access] = await Promise.all([apiFetch<{ operations: OperationReceipt[] }>('/api/operations/recent'), apiFetch<AccessStatus>('/api/access/status')]); setOperations(ledger.operations); setAccessStatus(access); } catch (loadError) { setError(loadError instanceof Error ? loadError.message : 'Could not load the authenticated manager ledger.'); } finally { setLoading(false); } }, []);
  useEffect(() => { const timer = window.setTimeout(() => { void load(); }, 0); return () => window.clearTimeout(timer); }, [load]);

  const unlock = useCallback(async (mode: 'membership' | 'single_use', walletAddress?: string) => { setAccessLoading(true); setAccessError(null); try { const result = await apiFetch<AccessUnlockResponse>('/api/access/unlock', { method: 'POST', headers: { 'Idempotency-Key': createIdempotencyKey(`access-${mode}`) }, body: JSON.stringify({ mode, hasPaidX402: !accessStatus?.isDemoAccount, walletAddress: walletAddress || undefined }) }); setAccessStatus(result); setAccessOpen(false); await load(); } catch (unlockError) { setAccessError(unlockError instanceof Error ? unlockError.message : 'Access activation failed.'); } finally { setAccessLoading(false); } }, [accessStatus, load]);
  const saveWallet = useCallback(async (walletAddress: string) => { setAccessLoading(true); setAccessError(null); try { const result = await apiFetch<AccessStatus & { success: boolean }>('/api/access/wallet', { method: 'POST', body: JSON.stringify({ walletAddress }) }); setAccessStatus(result); } catch (walletError) { setAccessError(walletError instanceof Error ? walletError.message : 'Wallet could not be saved.'); } finally { setAccessLoading(false); } }, []);

  return <main className="command-page hq-shell px-4 py-6 text-on-surface md:px-8"><div className="hq-orb hq-orb-gold" /><div className="relative mx-auto max-w-6xl"><div className="mb-5 flex flex-wrap items-center justify-between gap-3"><Link href="/" className="inline-flex items-center gap-2 text-sm font-bold text-primary hover:text-secondary">← Return to INJ Control</Link><button onClick={() => void load()} className="rounded-md border border-outline-variant/50 bg-white/70 px-3 py-2 text-xs font-bold text-on-surface shadow-sm">Refresh ledger</button></div>{loading && <div className="rounded-xl border border-outline-variant/30 bg-surface-container-low p-8 text-on-surface-variant">Loading durable action receipts…</div>}{error && <div className="rounded-xl border border-rose-400/30 bg-rose-400/10 p-6"><p className="font-bold text-rose-800">Action Ledger unavailable</p><p className="mt-2 text-sm text-rose-700">{error}</p></div>}{!loading && !error && <TransactionLedger operations={operations} accessStatus={accessStatus} onOpenMembership={() => { setAccessError(null); setAccessOpen(true); }} />}</div><AccessModal isOpen={accessOpen} status={accessStatus} isLoading={accessLoading} error={accessError} onClose={() => setAccessOpen(false)} onUnlock={unlock} onSaveWallet={saveWallet} /></main>;
}
