"use client";

import { useMemo, useState } from "react";
import type {
  Player,
  TournamentMatch,
  TournamentOverview,
  TournamentTeam,
} from "@/types";
import PlayerIntelModal from "./PlayerIntelModal";
import PlayerScoutCard from "./PlayerScoutCard";

type TournamentView = "bracket" | "fixtures" | "teams";

const BRACKET_STAGES = ["r32", "r16", "qf", "sf", "third", "final"];
const STAGE_ACCENT: Record<string, string> = {
  r32: "from-emerald-500 to-teal-500",
  r16: "from-cyan-500 to-blue-500",
  qf: "from-violet-500 to-fuchsia-500",
  sf: "from-amber-400 to-orange-500",
  third: "from-slate-500 to-slate-700",
  final: "from-amber-300 via-yellow-400 to-amber-600",
};

function readableKickoff(value: string): string {
  if (!value) return "Kickoff pending";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime())
    ? value
    : parsed.toLocaleString(undefined, {
        dateStyle: "medium",
        timeStyle: "short",
      });
}

function statusClass(status: string): string {
  if (status === "live")
    return "bg-rose-500/15 text-rose-200 border-rose-300/35 animate-pulse";
  if (status === "final")
    return "bg-emerald-400/15 text-emerald-100 border-emerald-300/35";
  return "bg-white/10 text-slate-200 border-white/15";
}

function MatchTile({
  match,
  compact = false,
}: {
  match: TournamentMatch;
  compact?: boolean;
}) {
  const score = (value: number | null) => value ?? "—";
  return (
    <article
      className={`group relative overflow-hidden rounded-xl border border-slate-200 bg-white/90 p-3 shadow-[0_10px_24px_rgba(15,72,57,.1)] transition hover:-translate-y-1 hover:border-emerald-300 hover:shadow-[0_16px_34px_rgba(15,72,57,.18)] ${compact ? "min-w-60" : ""}`}
    >
      <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-emerald-400 via-amber-300 to-emerald-500 opacity-60 transition group-hover:opacity-100" />
      <div className="mb-3 flex items-center justify-between gap-2 pt-1">
        <span className="font-mono-jb text-[10px] font-bold uppercase tracking-[0.13em] text-slate-500">
          Match {match.matchNumber || "—"}{" "}
          {match.group ? `· ${match.group}` : ""}
        </span>
        <span
          className={`rounded-full border px-2 py-1 font-mono-jb text-[9px] font-bold uppercase tracking-wider ${statusClass(match.status)}`}
        >
          {match.status}
        </span>
      </div>
      <div className="space-y-2 text-sm">
        <div className="flex items-center justify-between gap-3">
          <span className="truncate font-bold text-slate-800">
            {match.homeTeam}
          </span>
          <strong className="rounded bg-slate-100 px-2 py-0.5 font-mono-jb text-slate-900">
            {score(match.homeScore)}
          </strong>
        </div>
        <div className="flex items-center justify-between gap-3">
          <span className="truncate font-bold text-slate-800">
            {match.awayTeam}
          </span>
          <strong className="rounded bg-slate-100 px-2 py-0.5 font-mono-jb text-slate-900">
            {score(match.awayScore)}
          </strong>
        </div>
      </div>
      <div className="mt-3 flex items-center gap-1.5 border-t border-slate-100 pt-2 text-[10px] leading-relaxed text-slate-500">
        <span className="material-symbols-outlined text-xs text-emerald-600">
          stadium
        </span>
        <span className="truncate">
          {readableKickoff(match.kickoffLocal)} · {match.venue}
        </span>
      </div>
    </article>
  );
}

function TeamButton({
  team,
  selected,
  onSelect,
}: {
  team: TournamentTeam;
  selected: boolean;
  onSelect: (team: TournamentTeam) => void;
}) {
  return (
    <button
      onClick={() => onSelect(team)}
      className={`group flex w-full items-center justify-between rounded-lg border px-3 py-2.5 text-left text-sm transition ${selected ? "border-emerald-400 bg-emerald-500 text-slate-950 shadow-md" : "border-transparent text-slate-700 hover:border-amber-300/60 hover:bg-amber-50"}`}
    >
      <span className="font-bold">{team.name}</span>
      <span className="font-mono-jb text-[10px] opacity-70">{team.code}</span>
    </button>
  );
}

function NumberTile({
  icon,
  value,
  label,
  tone,
}: {
  icon: string;
  value: number;
  label: string;
  tone: string;
}) {
  return (
    <div className="rounded-xl border border-white/15 bg-white/[.08] p-3 backdrop-blur-sm">
      <div className="flex items-center justify-between">
        <span className={`grid h-8 w-8 place-items-center rounded-lg ${tone}`}>
          <span className="material-symbols-outlined text-base">{icon}</span>
        </span>
        <strong className="font-display-lg text-3xl text-white">{value}</strong>
      </div>
      <p className="mt-2 font-mono-jb text-[10px] font-bold uppercase tracking-[0.14em] text-emerald-100">
        {label}
      </p>
    </div>
  );
}

export default function TournamentHub({
  overview,
  onRefresh,
  isPremiumUnlocked,
}: {
  overview: TournamentOverview;
  onRefresh: () => void;
  isPremiumUnlocked: boolean;
}) {
  const [view, setView] = useState<TournamentView>("bracket");
  const [selectedTeam, setSelectedTeam] = useState<TournamentTeam | null>(
    overview.teams[0] ?? null,
  );
  const [stageFilter, setStageFilter] = useState("all");
  const [selectedPlayer, setSelectedPlayer] = useState<Player | null>(null);
  const roster = useMemo(
    () => overview.rosters.find((item) => item.team === selectedTeam?.name),
    [overview.rosters, selectedTeam?.name],
  );
  const stages = useMemo(
    () => Array.from(new Set(overview.matches.map((match) => match.stageKey))),
    [overview.matches],
  );
  const fixtureMatches = useMemo(
    () =>
      overview.matches.filter(
        (match) => stageFilter === "all" || match.stageKey === stageFilter,
      ),
    [overview.matches, stageFilter],
  );
  const groupedMatches = useMemo(
    () =>
      new Map(
        BRACKET_STAGES.map((stage) => [
          stage,
          overview.matches.filter((match) => match.stageKey === stage),
        ]),
      ),
    [overview.matches],
  );
  const nextMatch =
    overview.matches.find((match) => match.status === "live") ??
    overview.matches.find((match) => match.status === "scheduled");
  const selectedTeamMatches = overview.matches.filter(
    (match) =>
      match.homeTeam === selectedTeam?.name ||
      match.awayTeam === selectedTeam?.name,
  );
  const tickerMatches = overview.matches
    .filter((match) => match.status !== "scheduled")
    .slice(0, 9);
  const refreshPageForAccess = () => {
    window.location.assign("/transactions");
  };

  return (
    <section className="space-y-6 pb-10">
      <header className="relative overflow-hidden rounded-3xl border border-emerald-300/25 bg-[radial-gradient(circle_at_82%_10%,rgba(223,181,59,.28),transparent_22%),radial-gradient(circle_at_10%_100%,rgba(46,204,113,.23),transparent_28%),linear-gradient(135deg,#072e28,#0b5b47_53%,#123337)] p-5 shadow-[0_28px_55px_rgba(7,46,40,.26)] md:p-7">
        <div className="pointer-events-none absolute -right-10 top-5 select-none font-display-lg text-[11rem] font-black leading-none text-white/[.045]">
          26
        </div>
        <div className="relative flex flex-wrap items-start justify-between gap-5">
          <div className="max-w-2xl">
            <p className="font-mono-jb text-[10px] font-bold uppercase tracking-[0.25em] text-amber-200">
              WCAI // Live Tournament Intelligence
            </p>
            <h1 className="mt-2 font-display-lg text-4xl font-black uppercase tracking-tight text-white md:text-6xl">
              Tournament HQ
            </h1>
            <p className="mt-3 text-sm leading-relaxed text-emerald-50/80 md:text-base">
              Build fantasy edge from the full World Cup map: live fixtures,
              knockout routes, squad intelligence and a source-labelled player
              scout layer.
            </p>
          </div>
          <div className="flex flex-col items-end gap-2">
            <span
              className={`rounded-full border px-3 py-1.5 font-mono-jb text-[10px] font-bold tracking-wider ${overview.mode === "live_event_feed" || overview.mode === "live_community_feed" ? "border-emerald-200/35 bg-emerald-300/15 text-emerald-100" : "border-amber-200/35 bg-amber-300/15 text-amber-100"}`}
            >
              {overview.mode === "live_event_feed" || overview.mode === "live_community_feed"
                ? "● LIVE EVENT FEED"
                : "● LOCAL FALLBACK"}
            </span>
            <button
              onClick={onRefresh}
              className="group rounded-lg border border-white/20 bg-white/10 px-3 py-2 text-xs font-bold text-white transition hover:border-amber-200 hover:bg-white/15"
            >
              <span className="material-symbols-outlined mr-1 text-sm align-middle transition group-hover:rotate-180">
                refresh
              </span>
              Refresh tournament
            </button>
          </div>
        </div>
        <div className="relative mt-6 grid gap-3 sm:grid-cols-3">
          <NumberTile
            icon="groups"
            value={overview.teams.length}
            label="Teams mapped"
            tone="bg-emerald-300 text-emerald-950"
          />
          <NumberTile
            icon="sports_soccer"
            value={overview.matches.length}
            label="Matches tracked"
            tone="bg-amber-300 text-amber-950"
          />
          <NumberTile
            icon="fact_check"
            value={overview.rosters.length}
            label="Detailed squads"
            tone="bg-cyan-300 text-cyan-950"
          />
        </div>
        {nextMatch && (
          <div className="relative mt-5 flex flex-wrap items-center gap-x-4 gap-y-2 rounded-xl border border-amber-200/20 bg-slate-950/25 px-4 py-3 text-sm text-white">
            <span className="rounded bg-amber-300 px-2 py-1 font-mono-jb text-[10px] font-bold uppercase text-slate-950">
              Next radar
            </span>
            <strong>
              {nextMatch.homeTeam} vs {nextMatch.awayTeam}
            </strong>
            <span className="text-emerald-100/75">
              {readableKickoff(nextMatch.kickoffLocal)} · {nextMatch.venue}
            </span>
          </div>
        )}
        <p className="relative mt-4 text-[10px] leading-relaxed text-emerald-100/70">
          {overview.sources.notice}
        </p>
      </header>
      {tickerMatches.length > 0 && (
        <div className="overflow-hidden rounded-xl border border-emerald-200/30 bg-emerald-950 text-white shadow-sm">
          <div className="broadcast-ticker-track">
            {[...tickerMatches, ...tickerMatches].map((match, index) => (
              <div
                key={`${match.id}-${index}`}
                className="flex shrink-0 items-center gap-3 border-r border-white/10 px-5 py-2.5 font-mono-jb text-[10px] uppercase tracking-wider"
              >
                <span
                  className={
                    match.status === "live"
                      ? "text-rose-300 animate-pulse"
                      : "text-emerald-200"
                  }
                >
                  {match.status}
                </span>
                <strong>
                  {match.homeCode} {match.homeScore ?? "—"} :{" "}
                  {match.awayScore ?? "—"} {match.awayCode}
                </strong>
                <span className="text-white/50">{match.stage}</span>
              </div>
            ))}
          </div>
        </div>
      )}
      <nav className="flex flex-wrap gap-2 rounded-2xl border border-slate-200 bg-white/80 p-2 shadow-sm backdrop-blur">
        <span className="hidden px-3 py-2 font-mono-jb text-[10px] font-bold uppercase tracking-widest text-slate-400 md:inline">
          Explore
        </span>
        {(["bracket", "fixtures", "teams"] as TournamentView[]).map((item) => (
          <button
            key={item}
            onClick={() => setView(item)}
            className={`rounded-xl px-4 py-2.5 text-xs font-bold uppercase tracking-wider transition ${view === item ? "bg-emerald-600 text-white shadow-md" : "text-slate-500 hover:bg-emerald-50 hover:text-emerald-800"}`}
          >
            <span className="material-symbols-outlined mr-1.5 text-sm align-middle">
              {item === "bracket"
                ? "account_tree"
                : item === "fixtures"
                  ? "calendar_month"
                  : "groups"}
            </span>
            {item === "teams" ? "Squad Intel" : item}
          </button>
        ))}
      </nav>
      {view === "bracket" && (
        <section className="rounded-3xl border border-slate-200 bg-white/75 p-4 shadow-sm backdrop-blur md:p-5">
          <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
            <div>
              <p className="font-mono-jb text-[10px] font-bold uppercase tracking-widest text-emerald-600">
                Knockout route map
              </p>
              <h2 className="mt-1 font-display-lg text-3xl font-black uppercase text-slate-900">
                From round of 32 to the final
              </h2>
            </div>
            <p className="max-w-md text-xs leading-relaxed text-slate-500">
              Every branch stays visible, so a manager can track potential
              opponents and plan a formation before the route becomes obvious.
            </p>
          </div>
          <div className="overflow-x-auto pb-4">
            <div className="flex min-w-max gap-4 px-1">
              {BRACKET_STAGES.map((stage) => (
                <div key={stage} className="bracket-rail w-64 space-y-3">
                  <div
                    className={`rounded-xl bg-gradient-to-r ${STAGE_ACCENT[stage] ?? "from-slate-500 to-slate-700"} px-3 py-2.5 text-white shadow-md`}
                  >
                    <p className="font-mono-jb text-[9px] font-bold uppercase tracking-widest text-white/75">
                      Stage
                    </p>
                    <h3 className="font-display-lg text-lg font-bold uppercase">
                      {overview.matches.find(
                        (match) => match.stageKey === stage,
                      )?.stage ?? stage}
                    </h3>
                  </div>
                  {(groupedMatches.get(stage) ?? []).length ? (
                    (groupedMatches.get(stage) ?? []).map((match) => (
                      <MatchTile key={match.id} match={match} compact />
                    ))
                  ) : (
                    <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-4 text-center">
                      <span className="material-symbols-outlined text-amber-500">
                        route
                      </span>
                      <p className="mt-2 text-xs font-bold text-slate-600">
                        Route pending
                      </p>
                      <p className="mt-1 text-[10px] text-slate-400">
                        Live pairing will appear here.
                      </p>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </section>
      )}
      {view === "fixtures" && (
        <section className="space-y-4">
          <div className="rounded-2xl border border-slate-200 bg-white/80 p-4 shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="font-mono-jb text-[10px] font-bold uppercase tracking-widest text-emerald-600">
                  Fixture console
                </p>
                <h2 className="mt-1 font-display-lg text-3xl font-black uppercase text-slate-900">
                  Matchday filter
                </h2>
              </div>
              <div className="flex flex-wrap gap-2">
                {["all", ...stages].map((stage) => (
                  <button
                    key={stage}
                    onClick={() => setStageFilter(stage)}
                    className={`rounded-full border px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider transition ${stageFilter === stage ? "border-emerald-600 bg-emerald-600 text-white" : "border-slate-200 bg-white text-slate-500 hover:border-amber-400"}`}
                  >
                    {stage === "all"
                      ? `All · ${overview.matches.length}`
                      : (overview.matches.find(
                          (match) => match.stageKey === stage,
                        )?.stage ?? stage)}
                  </button>
                ))}
              </div>
            </div>
          </div>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {fixtureMatches.map((match) => (
              <MatchTile key={match.id} match={match} />
            ))}
          </div>
        </section>
      )}
      {view === "teams" && (
        <section className="grid gap-5 xl:grid-cols-[minmax(285px,.72fr)_minmax(0,2fr)]">
          <aside className="space-y-3">
            {overview.groups.map((group) => (
              <div
                key={group.name}
                className="rounded-2xl border border-slate-200 bg-white/80 p-3 shadow-sm"
              >
                <h2 className="mb-2 px-2 font-mono-jb text-[10px] font-bold uppercase tracking-widest text-emerald-700">
                  {group.name}
                </h2>
                <div className="space-y-1">
                  {group.teams.map((team) => (
                    <TeamButton
                      key={team.id}
                      team={team}
                      selected={selectedTeam?.id === team.id}
                      onSelect={setSelectedTeam}
                    />
                  ))}
                </div>
              </div>
            ))}
          </aside>
          <div className="min-w-0">
            <header className="relative overflow-hidden rounded-3xl border border-emerald-200 bg-[radial-gradient(circle_at_85%_0%,rgba(223,181,59,.28),transparent_25%),linear-gradient(135deg,#0d6650,#0b3d35)] p-5 text-white shadow-lg">
              <div className="absolute right-4 top-0 font-display-lg text-8xl font-black text-white/10">
                {selectedTeam?.code}
              </div>
              <div className="relative flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="font-mono-jb text-[10px] font-bold uppercase tracking-widest text-amber-200">
                    Squad radar
                  </p>
                  <h2 className="mt-1 font-display-lg text-4xl font-black uppercase">
                    {selectedTeam?.name ?? "Select a team"}
                  </h2>
                  <p className="mt-2 text-sm text-emerald-100/80">
                    {selectedTeamMatches.length} scheduled or completed fixtures
                    tracked · detailed individual cards appear only for
                    source-backed roster snapshots.
                  </p>
                </div>
                {roster?.sourceUrl && (
                  <a
                    href={roster.sourceUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="relative rounded-lg border border-white/20 bg-white/10 px-3 py-2 text-xs font-bold text-white hover:border-amber-200"
                  >
                    FIFA roster source ↗
                  </a>
                )}
              </div>
            </header>
            {roster?.rosterAvailable && roster.players.length ? (
              <>
                <div className="my-5 flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="font-display-lg text-2xl font-black uppercase text-slate-900">
                      Scout card collection
                    </p>
                    <p className="mt-1 text-xs text-slate-500">
                      Select a card to open player-level source and signal
                      detail.
                    </p>
                  </div>
                  <span className="rounded-full border border-amber-300 bg-amber-50 px-3 py-1.5 font-mono-jb text-[10px] font-bold text-amber-800">
                    {roster.players.length} PLAYER SNAPSHOTS
                  </span>
                </div>
                <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
                  {roster.players.map((player) => (
                    <PlayerScoutCard
                      key={player.id}
                      player={player}
                      onSelect={setSelectedPlayer}
                    />
                  ))}
                </div>
              </>
            ) : (
              <div className="mt-5 rounded-3xl border border-dashed border-slate-300 bg-white/70 p-9">
                <span className="material-symbols-outlined text-4xl text-amber-500">
                  manage_search
                </span>
                <p className="mt-3 text-xl font-bold text-slate-800">
                  Detailed roster snapshot unavailable
                </p>
                <p className="mt-2 max-w-xl text-sm leading-relaxed text-slate-500">
                  This live schedule provides team structure, while WCAI keeps
                  individual player availability and performance data
                  source-labelled.
                </p>
              </div>
            )}
          </div>
        </section>
      )}
      <PlayerIntelModal
        player={selectedPlayer}
        isOpen={Boolean(selectedPlayer)}
        isPremiumUnlocked={isPremiumUnlocked}
        onClose={() => setSelectedPlayer(null)}
        onUnlockPremium={refreshPageForAccess}
      />
    </section>
  );
}
