'use client';

import type { MatchdayBriefResponse, Player, TacticalLabResponse } from '@/types';

interface TacticalLabPanelProps {
  matchdayBrief: MatchdayBriefResponse | null;
  tacticalLab: TacticalLabResponse | null;
  players: Player[];
  onClose: () => void;
}

function shortName(player?: Player) {
  return player?.name.split(' ').pop() ?? '—';
}

export default function TacticalLabPanel({
  matchdayBrief,
  tacticalLab,
  players,
  onClose,
}: TacticalLabPanelProps) {
  if (!matchdayBrief && !tacticalLab) return null;

  const playerById = new Map(players.map((player) => [player.id, player]));

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-slate-950/65 p-4 backdrop-blur-sm">
      <section className="glass-panel max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-2xl border border-primary/40 p-5 shadow-2xl md:p-7">
        <div className="mb-5 flex items-start justify-between gap-4 border-b border-slate-200 pb-4">
          <div>
            <p className="font-label-sm text-[10px] uppercase tracking-[0.2em] text-primary">
              {matchdayBrief ? 'FIFA DATA COCKPIT' : 'PREMIUM WHAT-IF ENGINE'}
            </p>
            <h2 className="mt-1 font-display-lg text-2xl uppercase tracking-wide text-slate-900">
              {matchdayBrief ? 'Gaffer Matchday Brief' : 'Tactical Lab'}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close tactical panel"
            className="rounded-full border border-slate-300 p-2 text-slate-500 transition hover:border-red-400 hover:text-red-600"
          >
            <span className="material-symbols-outlined">close</span>
          </button>
        </div>

        {matchdayBrief && (
          <div className="space-y-5">
            <div className="rounded-xl bg-slate-900 p-5 text-white">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="font-label-sm text-[10px] uppercase tracking-widest text-emerald-300">
                    {matchdayBrief.match.stage} · {matchdayBrief.match.date}
                  </p>
                  <h3 className="mt-1 font-display-lg text-2xl uppercase">
                    {matchdayBrief.match.homeTeam} <span className="text-primary">vs</span> {matchdayBrief.match.awayTeam}
                  </h3>
                  <p className="mt-1 text-xs text-slate-300">
                    {matchdayBrief.match.kickoffLocal} local · {matchdayBrief.match.venue}
                  </p>
                </div>
                <div className="rounded-lg border border-amber-300/30 bg-amber-300/10 px-3 py-2 text-right">
                  <p className="text-[9px] uppercase tracking-widest text-amber-200">Data confidence</p>
                  <p className="font-display-lg text-lg uppercase text-amber-300">{matchdayBrief.dataConfidence}</p>
                </div>
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-xl border border-emerald-300/40 bg-emerald-50 p-4">
                <p className="text-[10px] font-bold uppercase tracking-widest text-emerald-700">Captain signal</p>
                <p className="mt-1 font-display-lg text-xl text-slate-900">{matchdayBrief.captain.name}</p>
                <p className="text-xs text-slate-600">{matchdayBrief.captain.team} · verified contribution weighted</p>
              </div>
              <div className="rounded-xl border border-sky-300/40 bg-sky-50 p-4">
                <p className="text-[10px] font-bold uppercase tracking-widest text-sky-700">Vice-captain signal</p>
                <p className="mt-1 font-display-lg text-xl text-slate-900">{matchdayBrief.viceCaptain.name}</p>
                <p className="text-xs text-slate-600">{matchdayBrief.viceCaptain.team} · points fallback when stats are unavailable</p>
              </div>
            </div>

            <div>
              <div className="mb-2 flex items-center justify-between">
                <h3 className="font-display-lg text-lg uppercase text-slate-900">{matchdayBrief.lineup.formation} recommended XI</h3>
                <span className="font-label-sm text-[10px] text-slate-500">
                  {matchdayBrief.lineup.budgetUsed}M / {matchdayBrief.lineup.maxBudget}M
                </span>
              </div>
              <div className="flex flex-wrap gap-2">
                {matchdayBrief.lineup.playerIds.map((id) => {
                  const player = playerById.get(id);
                  return (
                    <span key={id} className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-700 shadow-sm">
                      <span className="mr-1 text-[9px] font-bold text-primary">{player?.position}</span>
                      {shortName(player)}
                    </span>
                  );
                })}
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div className="rounded-xl border border-slate-200 bg-white/70 p-4">
                <h3 className="mb-2 font-display-lg text-sm uppercase text-slate-900">Watch-outs</h3>
                <ul className="space-y-2 text-xs leading-relaxed text-slate-600">
                  {matchdayBrief.watchouts.map((item) => <li key={item}>• {item}</li>)}
                </ul>
              </div>
              <div className="rounded-xl border border-slate-200 bg-white/70 p-4">
                <h3 className="mb-2 font-display-lg text-sm uppercase text-slate-900">Scenario cards</h3>
                <div className="space-y-2">
                  {matchdayBrief.scenarios.map((scenario) => (
                    <div key={scenario.id} className="rounded-lg bg-slate-100 p-2.5">
                      <div className="flex items-center justify-between text-xs font-bold text-slate-800">
                        <span>{scenario.label}</span><span className="text-primary">{scenario.formation}</span>
                      </div>
                      <p className="mt-1 text-[11px] text-slate-600">{scenario.instruction}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <p className="text-[10px] leading-relaxed text-slate-500">
              Snapshot: {matchdayBrief.snapshotDate}. {matchdayBrief.dataQuality}
            </p>
          </div>
        )}

        {tacticalLab && (
          <div className="space-y-5">
            <div className="rounded-xl bg-slate-900 p-5 text-white">
              <p className="font-label-sm text-[10px] uppercase tracking-widest text-amber-300">{tacticalLab.strategy} strategy</p>
              <h3 className="mt-1 font-display-lg text-2xl uppercase">Which shape wins your budget?</h3>
              <p className="mt-2 text-xs leading-relaxed text-slate-300">
                Five formation proposals were scored without mutating the saved squad. The apply action remains a separate explicit confirmation.
              </p>
            </div>
            <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
              <table className="w-full min-w-[560px] text-left text-xs">
                <thead className="bg-slate-100 text-[10px] uppercase tracking-wider text-slate-500">
                  <tr><th className="px-4 py-3">Shape</th><th className="px-4 py-3">Points</th><th className="px-4 py-3">Budget</th><th className="px-4 py-3">Delta</th><th className="px-4 py-3">State</th></tr>
                </thead>
                <tbody>
                  {tacticalLab.comparisons.map((item) => (
                    <tr key={item.formation} className={`border-t border-slate-100 ${item.formation === tacticalLab.recommended.formation ? 'bg-emerald-50' : ''}`}>
                      <td className="px-4 py-3 font-bold text-slate-800">{item.formation}</td>
                      <td className="px-4 py-3 text-slate-700">{item.totalPoints ?? '—'}</td>
                      <td className="px-4 py-3 text-slate-700">{item.budgetUsed !== undefined ? `${item.budgetUsed}M` : '—'}</td>
                      <td className={`px-4 py-3 font-bold ${(item.pointsDeltaFromBest ?? 0) === 0 ? 'text-emerald-600' : 'text-slate-500'}`}>
                        {item.pointsDeltaFromBest !== undefined ? `${item.pointsDeltaFromBest > 0 ? '+' : ''}${item.pointsDeltaFromBest}` : '—'}
                      </td>
                      <td className="px-4 py-3">{item.status === 'ready' ? <span className="text-emerald-600">READY</span> : <span className="text-rose-500">{item.reason ?? 'UNAVAILABLE'}</span>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="rounded-xl border border-primary/30 bg-amber-50 p-4 text-xs text-slate-700">
              <strong className="text-slate-900">Recommended shape: {tacticalLab.recommended.formation}</strong> · {tacticalLab.recommended.totalPoints} points using {tacticalLab.recommended.budgetUsed}M of {tacticalLab.serverBudget}M.
            </div>
            <p className="text-[10px] leading-relaxed text-slate-500">Snapshot: {tacticalLab.snapshotDate}. {tacticalLab.dataQuality}</p>
          </div>
        )}
      </section>
    </div>
  );
}
