'use client';

import { useEffect, useState } from 'react';
import { apiFetch } from '@/lib/api';
import { getTeamTheme, teamGradient } from '@/lib/teamTheme';
import type { Player, PlayerIntel } from '@/types';

function statusTone(status: string): string {
  if (status === 'available') return 'border-emerald-300/35 bg-emerald-400/15 text-emerald-200';
  if (status === 'unknown') return 'border-slate-300/25 bg-slate-400/15 text-slate-200';
  return 'border-amber-300/35 bg-amber-400/15 text-amber-100';
}

function readableDate(value?: string): string {
  if (!value) return 'Not listed in snapshot';
  const parsed = new Date(value);
  return Number.isNaN(parsed.valueOf()) ? value : parsed.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
}

function Radar({ metrics, accent }: { metrics: PlayerIntel['model']['metrics']; accent: string }) {
  const radius = 62;
  const center = 82;
  const active = metrics.slice(0, 5);
  const point = (value: number, index: number, multiplier = 1) => {
    const angle = -Math.PI / 2 + (index / active.length) * Math.PI * 2;
    const distance = radius * multiplier * (value / 100);
    return `${center + Math.cos(angle) * distance},${center + Math.sin(angle) * distance}`;
  };
  const polygon = active.map((metric, index) => point(metric.value, index)).join(' ');

  return (
    <svg className="intel-radar h-56 w-full max-w-64" viewBox="0 0 164 164" role="img" aria-label="WCAI player signal radar">
      {[0.35, 0.65, 1].map((scale) => (
        <polygon key={scale} points={active.map((_, index) => point(100, index, scale)).join(' ')} fill="none" className="!fill-transparent !stroke-white/20" />
      ))}
      {active.map((metric, index) => {
        const angle = -Math.PI / 2 + (index / active.length) * Math.PI * 2;
        return (
          <g key={metric.key}>
            <line x1={center} y1={center} x2={center + Math.cos(angle) * radius} y2={center + Math.sin(angle) * radius} />
            <text x={center + Math.cos(angle) * 76} y={center + Math.sin(angle) * 76}>{metric.label.split(' ')[0].slice(0, 4).toUpperCase()}</text>
          </g>
        );
      })}
      <polygon points={polygon} fill={accent} fillOpacity="0.3" stroke={accent} strokeWidth="2" />
    </svg>
  );
}

function Trend({ values, accent }: { values: number[]; accent: string }) {
  const min = Math.min(...values) - 4;
  const max = Math.max(...values) + 4;
  const points = values.map((value, index) => `${8 + index * 43},${66 - ((value - min) / Math.max(1, max - min)) * 52}`).join(' ');
  return (
    <svg className="h-20 w-full" viewBox="0 0 190 78" role="img" aria-label="Model form trend">
      <polyline points={points} fill="none" stroke={accent} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
      {values.map((value, index) => {
        const [, y] = points.split(' ')[index].split(',');
        return <circle key={`${value}-${index}`} cx={8 + index * 43} cy={Number(y)} r="3.5" fill="#f8fafc" stroke={accent} strokeWidth="2" />;
      })}
    </svg>
  );
}

interface PlayerIntelModalProps {
  player: Player | null;
  isOpen: boolean;
  isPremiumUnlocked: boolean;
  onClose: () => void;
  onReplace?: () => void;
  onUnlockPremium: () => void;
}

function FactCard({ label, value, detail }: { label: string; value: string; detail?: string }) {
  return (
    <div className="rounded-xl border border-white/10 bg-white/[.055] p-4">
      <p className="font-mono-jb text-[10px] uppercase tracking-widest text-slate-400">{label}</p>
      <p className="mt-2 truncate font-bold text-white" title={value}>{value}</p>
      {detail && <p className="mt-1 text-[10px] text-slate-400">{detail}</p>}
    </div>
  );
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
      setIntel(null);
      apiFetch<PlayerIntel>(`/api/players/${encodeURIComponent(player.id)}/intel`)
        .then((next) => { if (active) setIntel(next); })
        .catch((requestError) => { if (active) setError(requestError instanceof Error ? requestError.message : 'Scout card could not be loaded.'); })
        .finally(() => { if (active) setLoading(false); });
    }, 0);
    return () => { active = false; window.clearTimeout(timer); };
  }, [isOpen, player]);

  if (!isOpen || !player) return null;

  const stats = player.world_cup_stats;
  const profile = intel?.verified.officialProfile;
  const teamTheme = getTeamTheme(player.team);
  const tournamentStatsAvailable = stats?.data_status === 'verified';

  return (
    <div className="fixed inset-0 z-[90] overflow-y-auto bg-slate-950/70 p-3 backdrop-blur-md md:p-7">
      <button aria-label="Close player card" onClick={onClose} className="fixed inset-0 cursor-default" />
      <section className="relative mx-auto my-3 w-full max-w-6xl overflow-hidden rounded-3xl border border-white/20 bg-slate-950 text-slate-100 shadow-[0_35px_90px_rgba(2,12,27,0.6)] animate-fade-in">
        <div className="pointer-events-none absolute inset-0" style={{ background: `radial-gradient(circle_at_8%_0%,${teamTheme.primary}75,transparent 32%), radial-gradient(circle_at_96%_10%,${teamTheme.accent}55,transparent 26%), linear-gradient(130deg,transparent 40%,rgba(255,255,255,.035))` }} />
        <header className="relative flex items-center justify-between border-b border-white/10 px-5 py-4 md:px-7">
          <div>
            <p className="font-mono-jb text-[10px] font-bold uppercase tracking-[0.22em]" style={{ color: teamTheme.secondary }}>Player Intel // {player.team}</p>
            <p className="mt-1 text-xs text-slate-400">Official FIFA squad profile + separately labelled WCAI model layer</p>
          </div>
          <button onClick={onClose} className="grid h-10 w-10 place-items-center rounded-full border border-white/15 text-slate-300 transition hover:text-white" style={{ borderColor: `${teamTheme.accent}99` }}>
            <span className="material-symbols-outlined">close</span>
          </button>
        </header>

        <div className="relative grid gap-6 p-5 md:p-7 lg:grid-cols-[minmax(280px,.85fr)_minmax(0,1.45fr)]">
          <aside className="foil-sweep relative overflow-hidden rounded-2xl border border-white/35 p-5 shadow-[inset_0_1px_0_rgba(255,255,255,.28),0_20px_50px_rgba(0,0,0,.3)]" style={{ background: `radial-gradient(circle_at_80%_8%,rgba(255,255,255,.34),transparent 21%), ${teamGradient(player.team)}` }}>
            <div className="absolute inset-0 bg-slate-950/38" />
            <div className="relative flex items-start justify-between">
              <div>
                <span className="rounded border border-white/25 bg-black/15 px-2 py-1 font-mono-jb text-[10px] font-bold tracking-widest text-white">{player.position}</span>
                <p className="mt-3 font-display-lg text-6xl font-black leading-none text-white">{isPremiumUnlocked && intel ? intel.model.overall : player.points}</p>
                <span className="font-mono-jb text-[10px] font-bold uppercase tracking-widest text-white/80">{isPremiumUnlocked ? 'Model rating' : 'Fantasy points'}</span>
              </div>
              <span className="text-3xl">{player.flag}</span>
            </div>
            <div className="relative my-7 grid min-h-40 place-items-center overflow-hidden rounded-2xl border border-white/20 bg-slate-950/25">
              <span className="font-display-lg text-8xl font-black text-white/25">{player.number ?? player.name.charAt(0)}</span>
              <div className="absolute bottom-3 left-3 rounded-full bg-black/35 px-3 py-1 font-mono-jb text-[10px] font-bold text-white">{player.team.toUpperCase()}</div>
            </div>
            <div className="relative border-t border-white/20 pt-4 text-center">
              <h2 className="font-display-lg text-3xl font-black uppercase tracking-wide text-white">{player.name}</h2>
              <p className="mt-1 font-mono-jb text-xs text-white/85">#{player.number ?? '—'} · {player.position} · {player.price}M</p>
              <p className="mt-2 truncate text-[11px] text-white/75">{profile?.listedClub || player.club || 'Official FIFA final squad'}</p>
            </div>
            <div className="relative mt-5 grid grid-cols-3 gap-2 border-t border-white/20 pt-4 text-center text-xs">
              <div><p className="text-white/70">Goals</p><strong className="mt-1 block text-lg">{tournamentStatsAvailable ? stats?.goals ?? 0 : '—'}</strong></div>
              <div><p className="text-white/70">Assists</p><strong className="mt-1 block text-lg">{tournamentStatsAvailable ? stats?.assists ?? 0 : '—'}</strong></div>
              <div><p className="text-white/70">Shirt no.</p><strong className="mt-1 block text-lg">{player.number ?? '—'}</strong></div>
            </div>
          </aside>

          <div className="min-w-0 space-y-5">
            {loading && <div className="rounded-xl border border-white/10 bg-white/5 p-5 text-sm text-slate-300">Loading source-aware player profile…</div>}
            {error && <div className="rounded-xl border border-amber-300/30 bg-amber-300/10 p-4 text-sm text-amber-100">Basic official roster card remains available. Detailed scout request: {error}</div>}

            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <FactCard label="Official name" value={profile?.officialName || player.official_name || player.name} />
              <FactCard label="Listed club" value={profile?.listedClub || player.club || 'Not listed'} />
              <FactCard label="Date of birth" value={readableDate(profile?.dateOfBirth || player.date_of_birth)} />
              <div className="rounded-xl border border-white/10 bg-white/[.055] p-4">
                <p className="font-mono-jb text-[10px] uppercase tracking-widest text-slate-400">Availability</p>
                <span className={`mt-2 inline-flex rounded-full border px-2 py-1 text-xs font-bold capitalize ${statusTone(player.availability_status ?? 'unknown')}`}>{(player.availability_status ?? 'unknown').replace('_', ' ')}</span>
                <p className="mt-1 text-[10px] text-slate-400">Roster: {player.roster_status ?? 'snapshot'}</p>
              </div>
            </div>

            <div className="rounded-2xl border border-white/10 bg-white/[.055] p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="font-mono-jb text-[10px] font-bold uppercase tracking-widest" style={{ color: teamTheme.secondary }}>Official World Cup output</p>
                  <p className="mt-1 text-xs text-slate-400">Goals and assists refresh from live match events; the official FIFA player-statistics page remains linked for reference.</p>
                </div>
                <span className={`rounded-full px-2 py-1 font-mono-jb text-[10px] font-bold uppercase ${tournamentStatsAvailable ? 'bg-emerald-300/15 text-emerald-200' : 'bg-slate-300/10 text-slate-300'}`}>{tournamentStatsAvailable ? 'Live event tally' : 'Live feed unavailable'}</span>
              </div>
              <div className="mt-4 grid grid-cols-3 gap-2 text-center">
                {[
                  ['Goals', tournamentStatsAvailable ? String(stats?.goals ?? 0) : '—'],
                  ['Assists', tournamentStatsAvailable ? String(stats?.assists ?? 0) : '—'],
                  ['Minutes', tournamentStatsAvailable ? String(stats?.minutes ?? 0) : '—'],
                ].map(([label, value]) => <div key={label} className="rounded-lg bg-slate-900/60 p-3"><p className="text-[10px] uppercase tracking-wider text-slate-400">{label}</p><strong className="mt-1 block text-lg text-white">{value}</strong></div>)}
              </div>
            </div>

            {isPremiumUnlocked && intel ? (
              <div className="grid gap-5 lg:grid-cols-[250px_minmax(0,1fr)]">
                <div className="rounded-2xl border border-white/15 p-4" style={{ background: `linear-gradient(160deg,${teamTheme.primary}88,rgba(2,6,23,.75))` }}>
                  <p className="font-mono-jb text-[10px] font-bold uppercase tracking-widest" style={{ color: teamTheme.secondary }}>Personal signal radar</p>
                  <Radar metrics={intel.model.metrics} accent={teamTheme.accent} />
                  <div className="flex flex-wrap justify-center gap-1">{intel.model.strengths.map((strength) => <span key={strength} className="rounded-full border border-white/25 bg-white/10 px-2 py-1 text-[10px] text-white">{strength}</span>)}</div>
                </div>
                <div className="space-y-4">
                  <div className="rounded-2xl border border-white/10 bg-white/[.055] p-4">
                    <div className="flex items-center justify-between gap-3">
                      <div><p className="font-mono-jb text-[10px] font-bold uppercase tracking-widest text-emerald-200">WCAI tactical signal</p><p className="mt-1 text-xs text-slate-400">Personalised from official roster facts and position context; not a FIFA rating.</p></div>
                      <span className="rounded-full px-2 py-1 font-mono-jb text-[10px] font-bold uppercase" style={{ backgroundColor: `${teamTheme.accent}28`, color: teamTheme.secondary }}>{intel.model.tier}</span>
                    </div>
                    <Trend values={intel.model.trend} accent={teamTheme.accent} />
                  </div>
                  <div className="grid gap-2 sm:grid-cols-2">{intel.model.metrics.map((metric) => <div key={metric.key} className="rounded-xl border border-white/10 bg-slate-900/60 p-3"><div className="flex items-center justify-between text-xs"><span className="text-slate-300">{metric.label}</span><strong className="font-mono-jb" style={{ color: teamTheme.secondary }}>{metric.value}</strong></div><div className="mt-2 h-1.5 overflow-hidden rounded-full bg-white/10"><div className="h-full rounded-full" style={{ width: `${metric.value}%`, backgroundColor: teamTheme.accent }} /></div></div>)}</div>
                  <blockquote className="rounded-xl border-l-4 bg-white/[.055] p-4 text-sm leading-relaxed text-slate-200" style={{ borderLeftColor: teamTheme.accent }}>“{intel.model.scoutBrief}”</blockquote>
                </div>
              </div>
            ) : (
              <div className="rounded-2xl border border-amber-300/25 bg-[linear-gradient(135deg,rgba(223,181,59,.16),rgba(15,107,81,.2))] p-5">
                <div className="flex flex-wrap items-center justify-between gap-4"><div><p className="font-display-lg text-xl font-bold uppercase text-white">Deep Scout Layer locked</p><p className="mt-1 max-w-xl text-sm leading-relaxed text-slate-300">Unlock the player-specific radar, five-signal curve, tactical attributes and roster-fact-led scout brief through Pro membership or an x402 Match Pass.</p></div><button onClick={onUnlockPremium} className="gold-gradient rounded-lg px-4 py-3 font-display-lg text-xs font-bold uppercase text-slate-950">Unlock analytics</button></div>
              </div>
            )}

            <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-white/10 pt-4">
              <p className="max-w-2xl text-[10px] leading-relaxed text-slate-500">{intel?.provenance.notice ?? 'Official squad fields are source-labelled. The detailed model layer loads with this player card.'}</p>
              <div className="flex gap-2">{player.source_url && <a href={player.source_url} target="_blank" rel="noreferrer" className="rounded-lg border border-white/15 px-3 py-2 text-xs font-bold text-slate-200 hover:text-white" style={{ borderColor: `${teamTheme.accent}88` }}>FIFA roster source ↗</a>}{onReplace && <button onClick={onReplace} className="rounded-lg px-3 py-2 text-xs font-bold text-slate-950" style={{ backgroundColor: teamTheme.secondary }}>Change player</button>}</div>
            </footer>
          </div>
        </div>
      </section>
    </div>
  );
}
