'use client';

import type { Player } from '@/types';

const POSITION_STYLE: Record<Player['position'], { label: string; accent: string; bar: string }> = {
  GK: { label: 'Goalkeeper', accent: 'border-sky-400/50 bg-sky-400/10 text-sky-200', bar: 'bg-sky-400' },
  DF: { label: 'Defender', accent: 'border-emerald-400/50 bg-emerald-400/10 text-emerald-200', bar: 'bg-emerald-400' },
  MF: { label: 'Midfielder', accent: 'border-violet-400/50 bg-violet-400/10 text-violet-200', bar: 'bg-violet-400' },
  FW: { label: 'Forward', accent: 'border-amber-400/50 bg-amber-400/10 text-amber-100', bar: 'bg-amber-400' },
};

function contribution(player: Player): string {
  const stats = player.world_cup_stats;
  if (!stats || stats.data_status !== 'verified') return 'Snapshot tracked';
  return `${stats.goals ?? 0}G · ${stats.assists ?? 0}A`;
}

export default function PlayerScoutCard({ player, onSelect }: { player: Player; onSelect?: (player: Player) => void }) {
  const style = POSITION_STYLE[player.position];
  const availability = player.availability_status ?? (player.isAvailable ? 'available' : 'unknown');
  const creative = Math.min(100, Math.round((player.world_cup_stats?.assists ?? 0) * 24 + player.points * 3));
  const finishing = Math.min(100, Math.round((player.world_cup_stats?.goals ?? 0) * 28 + player.premium_stats.xg_per_game * 55 + player.points * 2));
  const readiness = availability === 'available' ? 92 : availability === 'doubtful' ? 52 : 25;

  return (
    <article
      role={onSelect ? 'button' : undefined}
      tabIndex={onSelect ? 0 : undefined}
      onClick={() => onSelect?.(player)}
      onKeyDown={(event) => {
        if (onSelect && (event.key === 'Enter' || event.key === ' ')) {
          event.preventDefault();
          onSelect(player);
        }
      }}
      className={`foil-sweep group relative overflow-hidden rounded-xl border border-outline-variant/30 bg-surface-container-low shadow-[0_16px_35px_rgba(0,0,0,0.18)] transition hover:-translate-y-1 hover:border-primary/80 hover:shadow-[0_22px_45px_rgba(15,72,57,0.2)] ${onSelect ? 'cursor-pointer focus:outline-none focus:ring-2 focus:ring-primary/70' : ''}`}
    >
      <div className="relative min-h-36 overflow-hidden bg-[radial-gradient(circle_at_85%_10%,rgba(255,184,77,.23),transparent_36%),linear-gradient(135deg,rgba(10,46,41,.96),rgba(11,20,29,.95))] p-4">
        <div className="absolute -right-4 -top-8 select-none font-display-lg text-[7rem] font-black leading-none text-white/[0.045]">
          {player.number ?? player.position}
        </div>
        <div className="relative flex items-start justify-between gap-3">
          <span className={`rounded border px-2 py-1 font-mono-jb text-[10px] font-bold tracking-[0.16em] ${style.accent}`}>
            {player.position} · {style.label.toUpperCase()}
          </span>
          <span className="rounded-full bg-secondary px-2.5 py-1 font-mono-jb text-xs font-black text-on-secondary">
            {player.points} PTS
          </span>
        </div>
        <div className="relative mt-8 flex items-end justify-between gap-3">
          <div>
            <p className="font-label-sm text-xs uppercase tracking-[0.2em] text-primary">{player.team}</p>
            <h3 className="mt-1 text-xl font-black leading-tight text-on-surface">{player.name}</h3>
          </div>
          <div className="grid h-12 w-12 place-items-center rounded-full border border-white/20 bg-black/20 text-center font-display-lg text-base font-black text-on-surface">
            {player.number ?? player.name.charAt(0)}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-3 divide-x divide-outline-variant/20 border-y border-outline-variant/20 bg-surface-container px-1 py-3 text-center">
        <div><p className="text-[10px] uppercase tracking-wider text-on-surface-variant">Price</p><p className="mt-1 font-mono-jb text-sm font-bold text-on-surface">{player.price}M</p></div>
        <div><p className="text-[10px] uppercase tracking-wider text-on-surface-variant">Output</p><p className="mt-1 font-mono-jb text-sm font-bold text-on-surface">{contribution(player)}</p></div>
        <div><p className="text-[10px] uppercase tracking-wider text-on-surface-variant">xG / match</p><p className="mt-1 font-mono-jb text-sm font-bold text-on-surface">{player.premium_stats.xg_per_game.toFixed(2)}</p></div>
      </div>

      <div className="space-y-2.5 p-4">
        {[
          ['Finishing', finishing],
          ['Creation', creative],
          ['Readiness', readiness],
        ].map(([label, value]) => (
          <div key={label as string} className="grid grid-cols-[68px_1fr_28px] items-center gap-2 text-[10px] uppercase tracking-wider">
            <span className="text-on-surface-variant">{label}</span>
            <span className="h-1.5 overflow-hidden rounded-full bg-surface-container-high"><span className={`block h-full rounded-full ${style.bar}`} style={{ width: `${value}%` }} /></span>
            <span className="text-right font-mono-jb text-on-surface">{value}</span>
          </div>
        ))}
        <div className="flex items-center justify-between gap-3 border-t border-outline-variant/20 pt-3">
          <span className={`rounded-full px-2 py-1 text-[10px] font-bold uppercase tracking-wider ${availability === 'available' ? 'bg-emerald-400/10 text-emerald-300' : 'bg-amber-400/10 text-amber-200'}`}>
            {availability.replace('_', ' ')}
          </span>
          <span className="truncate text-right text-[10px] text-on-surface-variant">
            {player.data_source === 'fifa' ? 'FIFA snapshot' : 'Auto-Gaffer model'}
          </span>
        </div>
        {onSelect && <p className="border-t border-outline-variant/15 pt-2 text-center font-mono-jb text-[9px] font-bold uppercase tracking-[0.15em] text-primary">Open player intel ↗</p>}
      </div>
    </article>
  );
}
