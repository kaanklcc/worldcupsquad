'use client';

import { useEffect, useState } from 'react';
import { apiFetch } from '@/lib/api';
import type { Player, PlayerIntel } from '@/types';

function statusTone(status: string): string {
  if (status === 'available') return 'bg-emerald-400/15 text-emerald-200 border-emerald-300/35';
  if (status === 'unknown') return 'bg-slate-400/15 text-slate-200 border-slate-300/25';
  return 'bg-amber-400/15 text-amber-100 border-amber-300/35';
}

function Radar({ metrics }: { metrics: PlayerIntel['model']['metrics'] }) {
  const radius = 62;
  const center = 82;
  const active = metrics.slice(0, 5);
  const point = (value: number, index: number, multiplier = 1) => {
    const angle = -Math.PI / 2 + (index / active.length) * Math.PI * 2;
    const distance = radius * multiplier * (value / 100);
    return `${center + Math.cos(angle) * distance},${center + Math.sin(angle) * distance}`;
  };
  const polygon = active.map((metric, index) => point(metric.value, index)).join(' ');
  return <svg className="intel-radar h-56 w-full max-w-64" viewBox="0 0 164 164" role="img" aria-label="Auto-Gaffer player signal radar">{[0.35, 0.65, 1].map((scale) => <polygon key={scale} points={active.map((_, index) => point(100, index, scale)).join(' ')} fill="none" className="!fill-transparent !stroke-white/20" />)}{active.map((metric, index) => { const angle = -Math.PI / 2 + (index / active.length) * Math.PI * 2; return <g key={metric.key}><line x1={center} y1={center} x2={center + Math.cos(angle) * radius} y2={center + Math.sin(angle) * radius} /><text x={center + Math.cos(angle) * 76} y={center + Math.sin(angle) * 76}>{metric.label.split(' ')[0].slice(0, 4).toUpperCase()}</text></g>; })}<polygon points={polygon} /></svg>;
}

function Trend({ values }: { values: number[] }) {
  const min = Math.min(...values) - 4;
  const max = Math.max(...values) + 4;
  const points = values.map((value, index) => `${8 + index * 43},${66 - ((value - min) / Math.max(1, max - min)) * 52}`).join(' ');
  return <svg className="h-20 w-full" viewBox="0 0 190 78" role="img" aria-label="Model form trend"><defs><linearGradient id="trendGlow" x1="0" x2="1"><stop stopColor="#2ecc71" /><stop offset="1" stopColor="#dfb53b" /></linearGradient></defs><polyline points={points} fill="none" stroke="url(#trendGlow)" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />{values.map((value, index) => { const [, y] = points.split(' ')[index].split(','); return <circle key={`${value}-${index}`} cx={8 + index * 43} cy={Number(y)} r="3.5" fill="#f8fafc" stroke="#dfb53b" strokeWidth="2" />; })}</svg>;
}

interface PlayerIntelModalProps {
  player: Player | null;
  isOpen: boolean;
  isPremiumUnlocked: boolean;
  onClose: () => void;
  onReplace?: () => void;
  onUnlockPremium: () => void;
}

export default function PlayerIntelModal({ player, isOpen, isPremiumUnlocked, onClose, onReplace, onUnlockPremium }: PlayerIntelModalProps) {
  const [intel, setIntel] = useState<PlayerIntel | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!isOpen || !player) return;
    let active = true;
    const timer = window.setTimeout(() => {
      setLoading(true);
      setError(null);
      apiFetch<PlayerIntel>(`/api/players/${encodeURIComponent(player.id)}/intel`)
        .then((next) => { if (active) setIntel(next); })
        .catch((requestError) => { if (active) setError(requestError instanceof Error ? requestError.message : 'Scout card could not be loaded.'); })
        .finally(() => { if (active) setLoading(false); });
    }, 0);
    return () => { active = false; window.clearTimeout(timer); };
  }, [isOpen, player]);

  const stats = player?.world_cup_stats;
  if (!isOpen || !player) return null;

  return <div className="fixed inset-0 z-[90] overflow-y-auto bg-slate-950/70 p-3 backdrop-blur-md md:p-7"><button aria-label="Close player card" onClick={onClose} className="fixed inset-0 cursor-default" /><section className="relative mx-auto my-3 w-full max-w-6xl overflow-hidden rounded-3xl border border-amber-300/30 bg-slate-950 text-slate-100 shadow-[0_35px_90px_rgba(2,12,27,0.6)] animate-fade-in"><div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_10%_0%,rgba(46,204,113,.22),transparent_30%),radial-gradient(circle_at_96%_10%,rgba(223,181,59,.28),transparent_26%),linear-gradient(130deg,transparent_40%,rgba(255,255,255,.035))]" /><div className="relative flex items-center justify-between border-b border-white/10 px-5 py-4 md:px-7"><div><p className="font-mono-jb text-[10px] font-bold uppercase tracking-[0.22em] text-amber-300">Player Intel // World Cup 2026</p><p className="mt-1 text-xs text-slate-400">Source-aware roster card · the model layer is visibly labelled</p></div><button onClick={onClose} className="grid h-10 w-10 place-items-center rounded-full border border-white/15 text-slate-300 transition hover:border-amber-300 hover:text-white"><span className="material-symbols-outlined">close</span></button></div><div className="relative grid gap-6 p-5 md:p-7 lg:grid-cols-[minmax(280px,.85fr)_minmax(0,1.45fr)]"><aside className="foil-sweep relative overflow-hidden rounded-2xl border border-amber-200/45 bg-[radial-gradient(circle_at_80%_8%,rgba(255,255,255,.34),transparent_21%),linear-gradient(145deg,#0b4035,#0f6b51_48%,#dfb53b_130%)] p-5 shadow-[inset_0_1px_0_rgba(255,255,255,.28),0_20px_50px_rgba(0,0,0,.3)]"><div className="relative flex items-start justify-between"><div><span className="rounded border border-white/25 bg-black/15 px-2 py-1 font-mono-jb text-[10px] font-bold tracking-widest text-white">{player.position}</span><p className="mt-3 font-display-lg text-6xl font-black leading-none text-white">{isPremiumUnlocked && intel ? intel.model.overall : player.points}</p><span className="font-mono-jb text-[10px] font-bold uppercase tracking-widest text-emerald-100">{isPremiumUnlocked ? 'Model rating' : 'Fantasy points'}</span></div><span className="text-3xl">{player.flag}</span></div><div className="relative my-7 grid min-h-40 place-items-center overflow-hidden rounded-2xl border border-white/15 bg-slate-950/20"><span className="font-display-lg text-8xl font-black text-white/20">{player.number ?? player.name.charAt(0)}</span><div className="absolute bottom-3 left-3 rounded-full bg-black/30 px-3 py-1 font-mono-jb text-[10px] font-bold text-white">{player.team.toUpperCase()}</div></div><div className="relative border-t border-white/20 pt-4 text-center"><h2 className="font-display-lg text-3xl font-black uppercase tracking-wide text-white">{player.name}</h2><p className="mt-1 font-mono-jb text-xs text-emerald-100">#{player.number ?? '—'} · {player.position} · {player.price}M</p></div><div className="relative mt-5 grid grid-cols-3 gap-2 border-t border-white/20 pt-4 text-center text-xs"><div><p className="text-emerald-100/75">Goals</p><strong className="mt-1 block text-lg">{stats?.data_status === 'verified' ? stats.goals ?? 0 : '—'}</strong></div><div><p className="text-emerald-100/75">Assists</p><strong className="mt-1 block text-lg">{stats?.data_status === 'verified' ? stats.assists ?? 0 : '—'}</strong></div><div><p className="text-emerald-100/75">Snapshot</p><strong className="mt-1 block text-lg">{player.data_updated_at?.slice(5, 10) ?? '—'}</strong></div></div></aside><div className="min-w-0 space-y-5">{loading && <div className="rounded-xl border border-white/10 bg-white/5 p-5 text-sm text-slate-300">Loading player-specific scouting card…</div>}{error && <div className="rounded-xl border border-amber-300/30 bg-amber-300/10 p-4 text-sm text-amber-100">Basic roster card is available. Detailed scouting request: {error}</div>}<div className="grid gap-3 sm:grid-cols-3"><div className="rounded-xl border border-white/10 bg-white/[.055] p-4"><p className="font-mono-jb text-[10px] uppercase tracking-widest text-slate-400">Roster</p><p className="mt-2 font-bold text-white">{player.roster_status ?? 'snapshot'}</p></div><div className="rounded-xl border border-white/10 bg-white/[.055] p-4"><p className="font-mono-jb text-[10px] uppercase tracking-widest text-slate-400">Availability</p><span className={`mt-2 inline-flex rounded-full border px-2 py-1 text-xs font-bold capitalize ${statusTone(player.availability_status ?? 'unknown')}`}>{(player.availability_status ?? 'unknown').replace('_', ' ')}</span></div><div className="rounded-xl border border-white/10 bg-white/[.055] p-4"><p className="font-mono-jb text-[10px] uppercase tracking-widest text-slate-400">Tournament facts</p><p className="mt-2 font-bold text-white">{stats?.data_status === 'verified' ? 'Verified snapshot' : 'Not available'}</p></div></div>{isPremiumUnlocked && intel ? <div className="grid gap-5 lg:grid-cols-[250px_minmax(0,1fr)]"><div className="rounded-2xl border border-amber-300/20 bg-[linear-gradient(160deg,rgba(15,107,81,.38),rgba(2,6,23,.5))] p-4"><p className="font-mono-jb text-[10px] font-bold uppercase tracking-widest text-amber-200">Signal radar</p><Radar metrics={intel.model.metrics} /><div className="flex flex-wrap justify-center gap-1">{intel.model.strengths.map((strength) => <span key={strength} className="rounded-full border border-amber-300/25 bg-amber-300/10 px-2 py-1 text-[10px] text-amber-100">{strength}</span>)}</div></div><div className="space-y-4"><div className="rounded-2xl border border-white/10 bg-white/[.055] p-4"><div className="flex items-center justify-between gap-3"><div><p className="font-mono-jb text-[10px] font-bold uppercase tracking-widest text-emerald-200">Model form signal</p><p className="mt-1 text-xs text-slate-400">Stable application estimate, not official live form.</p></div><span className="rounded-full bg-amber-300/10 px-2 py-1 font-mono-jb text-[10px] font-bold uppercase text-amber-200">{intel.model.tier}</span></div><Trend values={intel.model.trend} /></div><div className="grid gap-2 sm:grid-cols-2">{intel.model.metrics.map((metric) => <div key={metric.key} className="rounded-xl border border-white/10 bg-slate-900/60 p-3"><div className="flex items-center justify-between text-xs"><span className="text-slate-300">{metric.label}</span><strong className="font-mono-jb text-amber-200">{metric.value}</strong></div><div className="mt-2 h-1.5 overflow-hidden rounded-full bg-white/10"><div className="h-full rounded-full bg-gradient-to-r from-emerald-400 to-amber-300" style={{ width: `${metric.value}%` }} /></div></div>)}</div><blockquote className="rounded-xl border-l-4 border-amber-300 bg-amber-300/[.08] p-4 text-sm leading-relaxed text-slate-200">“{intel.model.scoutBrief}”</blockquote></div></div> : <div className="rounded-2xl border border-amber-300/25 bg-[linear-gradient(135deg,rgba(223,181,59,.16),rgba(15,107,81,.2))] p-5"><div className="flex flex-wrap items-center justify-between gap-4"><div><p className="font-display-lg text-xl font-bold uppercase text-white">Deep Scout Layer locked</p><p className="mt-1 max-w-xl text-sm leading-relaxed text-slate-300">Unlock player radar, five-signal form curve, tactical attributes and the model scouting brief through Pro membership or x402 Match Pass.</p></div><button onClick={onUnlockPremium} className="gold-gradient rounded-lg px-4 py-3 font-display-lg text-xs font-bold uppercase text-slate-950">Unlock analytics</button></div></div>}<div className="flex flex-wrap items-center justify-between gap-3 border-t border-white/10 pt-4"><p className="max-w-2xl text-[10px] leading-relaxed text-slate-500">{intel?.provenance.notice ?? 'Detailed model signals load only after the player card request completes. Roster data remains source-labelled.'}</p><div className="flex gap-2">{player.source_url && <a href={player.source_url} target="_blank" rel="noreferrer" className="rounded-lg border border-white/15 px-3 py-2 text-xs font-bold text-slate-200 hover:border-emerald-300">FIFA roster source ↗</a>}{onReplace && <button onClick={onReplace} className="rounded-lg bg-emerald-500 px-3 py-2 text-xs font-bold text-slate-950">Change player</button>}</div></div></div></div></section></div>;
}
