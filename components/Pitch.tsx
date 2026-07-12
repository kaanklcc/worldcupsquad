'use client';

import { useRef, useEffect } from 'react';
import { Player, SquadSlot } from '@/types';

interface PitchProps {
  squad: SquadSlot[];
  onSlotClick: (slot: SquadSlot) => void;
  formation: string;
  onChangeFormation: (formation: string) => void;
  bench: SquadSlot[];
  onBenchSlotClick: (slot: SquadSlot) => void;
  showBench: boolean;
  isPremiumUnlocked: boolean;
  onUnlockPremium: () => void;
}

export default function Pitch({
  squad,
  onSlotClick,
  formation,
  onChangeFormation,
  bench,
  onBenchSlotClick,
  showBench,
  isPremiumUnlocked,
  onUnlockPremium,
}: PitchProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  // Smooth scroll to bench when it is activated
  useEffect(() => {
    if (showBench && containerRef.current) {
      const timer = setTimeout(() => {
        containerRef.current?.scrollTo({
          top: containerRef.current.scrollHeight,
          behavior: 'smooth',
        });
      }, 150);
      return () => clearTimeout(timer);
    }
  }, [showBench]);

  // Find the highest rated player to apply the "best player" gold glow effect
  const allSelectedPlayers = [
    ...squad.filter((s) => s.player !== null),
    ...bench.filter((s) => s.player !== null)
  ];
  const maxPoints = allSelectedPlayers.length > 0 
    ? Math.max(...allSelectedPlayers.map((s) => s.player!.points)) 
    : 0;
  const bestPlayerId = allSelectedPlayers.find((s) => s.player?.points === maxPoints)?.player?.id;

  const dfCount = squad.filter(s => s.position === 'DF').length;

  const renderSlot = (slot: SquadSlot, isBenchSlot: boolean = false) => {
    const isFilled = slot.player !== null;
    const isAvailable = isFilled ? slot.player!.isAvailable : false;
    const isBest = isFilled && slot.player!.id === bestPlayerId;

    let positionLabel: string = slot.position;
    if (isBenchSlot) {
      positionLabel = `SUB ${slot.position}`;
    } else {
      if (slot.position === 'FW') {
        if (formation === '4-2-3-1' || formation === '4-5-1' || formation === '6-3-1') {
          positionLabel = 'ST';
        } else if (formation === '4-4-2' || formation === '3-5-2') {
          positionLabel = slot.slotIndex === 0 ? 'LS' : 'RS';
        } else {
          positionLabel = slot.slotIndex === 0 ? 'LW' : slot.slotIndex === 1 ? 'ST' : 'RW';
        }
      } else if (slot.position === 'MF') {
        if (formation === '4-2-3-1') {
          positionLabel = slot.slotIndex < 2 ? 'CDM' : slot.slotIndex === 3 ? 'CAM' : slot.slotIndex === 2 ? 'LAM' : 'RAM';
        } else if (formation === '4-5-1' || formation === '3-5-2') {
          positionLabel = slot.slotIndex === 0 ? 'LM' : slot.slotIndex === 4 ? 'RM' : slot.slotIndex === 2 ? 'CDM' : 'CM';
        } else if (formation === '4-4-2' || formation === '3-4-3') {
          positionLabel = slot.slotIndex === 0 ? 'LM' : slot.slotIndex === 3 ? 'RM' : 'CM';
        } else {
          positionLabel = slot.slotIndex === 0 ? 'LCM' : slot.slotIndex === 1 ? 'CDM' : 'RCM';
        }
      } else if (slot.position === 'DF') {
        if (dfCount === 3) {
          positionLabel = slot.slotIndex === 0 ? 'LCB' : slot.slotIndex === 1 ? 'CB' : 'RCB';
        } else if (dfCount === 6) {
          positionLabel = slot.slotIndex === 0 ? 'LWB' : slot.slotIndex === 5 ? 'RWB' : slot.slotIndex === 1 ? 'LB' : slot.slotIndex === 4 ? 'RB' : 'CB';
        } else {
          positionLabel = slot.slotIndex === 0 ? 'LB' : slot.slotIndex === 3 ? 'RB' : 'CB';
        }
      }
    }

    // Restored original large card sizes
    const cardSizeClass = isBenchSlot
      ? 'w-18 h-26 flex-shrink-0'
      : slot.position === 'DF'
      ? dfCount === 6
        ? 'w-14 h-22 md:w-18 md:h-26'
        : 'w-20 h-28 md:w-24 md:h-34'
      : 'w-22 h-30 md:w-26 md:h-38';

    const clickHandler = () => isBenchSlot ? onBenchSlotClick(slot) : onSlotClick(slot);

    if (!isFilled) {
      return (
        <button
          key={`${slot.position}-${slot.slotIndex}-${isBenchSlot ? 'bench' : 'field'}`}
          onClick={clickHandler}
          className={`player-card relative ${cardSizeClass} rounded-xl bg-white/70 backdrop-blur-md border-2 border-dashed border-slate-300 hover:border-primary hover:bg-white transition-all shadow-md flex flex-col items-center justify-end p-2 overflow-hidden cursor-pointer group`}
        >
          <div className="absolute inset-0 flex items-center justify-center opacity-10">
            <span className="material-symbols-outlined text-5xl pulse-node text-slate-800">person</span>
          </div>
          <div className="absolute top-2 left-2 flex flex-col items-center">
            <span className="font-label-sm text-[8px] md:text-[10px] text-slate-500 uppercase mt-1">
              {positionLabel}
            </span>
          </div>
          <div className="w-full bg-slate-50/90 backdrop-blur-sm p-1 rounded z-10 text-center border-t border-slate-200 border-dashed">
            <span className="font-label-sm text-[8px] md:text-[9px] text-slate-500 uppercase block font-bold">
              + ADD
            </span>
          </div>
        </button>
      );
    }

    const player = slot.player!;
    const nameStr = player.name.split(' ').pop() || player.name;
    const pointsPct = Math.min(player.points, 100);

    // Calculate flag background style based on team
    let cardBgStyle: React.CSSProperties = {};
    const teamName = player.team.toLowerCase();
    
    if (teamName.includes('argentina')) {
      cardBgStyle = { background: 'linear-gradient(90deg, #74acdf 0% 33%, #ffffff 33% 66%, #74acdf 66% 100%)' };
    } else if (teamName.includes('spain')) {
      cardBgStyle = { background: 'linear-gradient(90deg, #c8102e 0% 33%, #ffd900 33% 66%, #c8102e 66% 100%)' };
    } else if (teamName.includes('france')) {
      cardBgStyle = { background: 'linear-gradient(90deg, #002395 0% 33%, #ffffff 33% 66%, #ed2939 66% 100%)' };
    } else if (teamName.includes('england')) {
      cardBgStyle = { background: 'linear-gradient(90deg, #ffffff 0% 45%, #e60000 45% 55%, #ffffff 55% 100%)' };
    }

    // Border and special styles
    let borderClass = 'border-2 border-white/50';
    let containerClass = '';
    let progressFill = 'bg-white';

    if (isBest) {
      borderClass = 'border-2 border-amber-400 glow-bloom scale-105';
      containerClass = 'z-20';
      progressFill = 'bg-amber-400';
    } else if (!isAvailable) {
      borderClass = 'border-2 border-red-500';
      progressFill = 'bg-red-500';
    }

    // Determine tooltip position dynamically to prevent layout clipping
    const tooltipPosClass = isBenchSlot 
      ? 'bottom-full mb-2' 
      : slot.position === 'FW' 
      ? 'top-full mt-2' 
      : 'bottom-full mb-2';

    return (
      <div 
        key={`${slot.position}-${slot.slotIndex}-${isBenchSlot ? 'bench' : 'field'}`}
        className="relative group overflow-visible"
      >
        {/* Card Button */}
        <button
          onClick={clickHandler}
          style={cardBgStyle}
          className={`player-card relative ${cardSizeClass} rounded-xl ${borderClass} ${containerClass} shadow-xl flex flex-col items-center justify-end p-2 overflow-hidden cursor-pointer`}
        >
          {/* Dark vignette overlay */}
          <div className="absolute inset-0 bg-gradient-to-b from-black/40 via-transparent to-black/70 z-0"></div>

          {/* Rating & Position (Top-left) */}
          <div className="absolute top-2 left-2 flex flex-col items-center z-10">
            <span className="font-display-lg text-base md:text-lg text-white drop-shadow-[0_2px_4px_rgba(0,0,0,0.8)] leading-none font-bold">
              {player.points}
            </span>
            <span className="font-label-sm text-[8px] md:text-[9px] text-white/70 drop-shadow-[0_1px_2px_rgba(0,0,0,0.8)] uppercase font-bold">
              {isBenchSlot ? positionLabel.replace('SUB ', '') : positionLabel}
            </span>
          </div>

          {/* Country flag emoji (Top-right) */}
          <div className="absolute top-2 right-2 z-10">
            <span className="text-xs md:text-sm drop-shadow-[0_2px_4px_rgba(0,0,0,0.5)]" title={player.team}>
              {player.flag}
            </span>
          </div>

          {/* Huge jersey number in the center */}
          <div className="absolute inset-0 flex items-center justify-center z-10 pointer-events-none select-none">
            <span className="font-display-lg text-4xl md:text-5xl text-white/60 drop-shadow-[0_2px_5px_rgba(0,0,0,0.65)] font-black tracking-tighter">
              {player.number}
            </span>
          </div>

          {/* Swap / Injured overlay */}
          {!isAvailable && (
            <>
              <div className="absolute inset-0 bg-red-600/20 z-10"></div>
              <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 bg-red-600 text-white rounded-full p-1 z-20 shadow-md border border-white animate-pulse">
                <span className="material-symbols-outlined text-[12px] font-bold">swap_vert</span>
              </div>
            </>
          )}

          {/* Name bar */}
          <div className="w-full bg-black/55 backdrop-blur-[2px] p-1 rounded z-20 text-center border-t border-white/20">
            <span className="font-display-lg text-[9px] md:text-[11px] uppercase block truncate text-white drop-shadow-[0_1px_2px_rgba(0,0,0,0.5)] font-bold">
              {nameStr}
            </span>
          </div>

          {/* Progress bar */}
          <div className="absolute bottom-0 left-0 w-full h-1 bg-white/20 z-20">
            <div className={`h-full ${progressFill}`} style={{ width: `${pointsPct}%` }}></div>
          </div>
        </button>

        {/* Floating Tooltip sibling (Hover Card) */}
        <div className={`absolute left-1/2 transform -translate-x-1/2 ${tooltipPosClass} hidden group-hover:flex flex-col w-60 bg-slate-950/95 border border-slate-800 rounded-xl p-3.5 shadow-2xl backdrop-blur-md z-50 text-[11px] font-body text-slate-300 pointer-events-auto`}>
          <div className="flex flex-col gap-2">
            {/* Header */}
            <div className="flex justify-between items-center border-b border-slate-800 pb-1.5">
              <div className="flex items-center gap-1.5">
                <span className="text-sm">{player.flag}</span>
                <span className="font-display-lg text-slate-100 uppercase font-bold truncate max-w-[120px]" title={player.name}>
                  {player.name}
                </span>
              </div>
              <span className="font-label-sm text-[9px] bg-slate-800 text-slate-400 px-1.5 py-0.5 rounded uppercase font-bold">
                {player.position}
              </span>
            </div>

            {/* Metrics */}
            <div className="grid grid-cols-2 gap-2 text-[10px] font-mono-jb border-b border-slate-800 pb-1.5">
              <div>
                <div className="text-slate-500 uppercase text-[8px]">Points</div>
                <div className="font-bold text-amber-400 text-xs">{player.points} PTS</div>
              </div>
              <div>
                <div className="text-slate-500 uppercase text-[8px]">Price</div>
                <div className="font-bold text-emerald-400 text-xs">{player.price}M</div>
              </div>
            </div>

            {/* Premium scouting stats */}
            <div className="flex flex-col gap-1">
              <div className="text-slate-500 uppercase text-[8px] font-mono-jb font-bold tracking-wider">Scouting Analytics</div>
              
              {isPremiumUnlocked ? (
                <div className="flex flex-col gap-1 text-[10px]">
                  <div className="flex justify-between py-0.5 border-b border-slate-900">
                    <span className="text-slate-400">Expected Goals (xG/G):</span>
                    <span className="font-bold text-slate-200">{player.premium_stats.xg_per_game}</span>
                  </div>
                  <div className="flex justify-between py-0.5 border-b border-slate-900">
                    <span className="text-slate-400">Injury Risk:</span>
                    <span className={`font-bold ${
                      player.premium_stats.injury_risk === 'High' ? 'text-red-400' :
                      player.premium_stats.injury_risk === 'Medium' ? 'text-amber-400' : 'text-emerald-400'
                    }`}>{player.premium_stats.injury_risk}</span>
                  </div>
                  <div className="text-slate-400 text-[10px] italic bg-slate-900/60 p-2 rounded border border-slate-800/80 mt-1 leading-relaxed">
                    "{player.premium_stats.scout_note}"
                  </div>
                  <div className="text-[9px] text-amber-400 font-bold flex items-center gap-1 mt-1 justify-center">
                    <span className="material-symbols-outlined text-[11px]">verified</span>
                    Premium Tactical Unlocked
                  </div>
                </div>
              ) : (
                <div className="flex flex-col items-center text-center p-2 rounded bg-slate-900/50 border border-slate-800/50">
                  <span className="material-symbols-outlined text-slate-500 text-base mb-1">lock</span>
                  <span className="text-[9px] text-slate-400 leading-normal">
                    Premium scouting stats are locked.
                  </span>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onUnlockPremium();
                    }}
                    className="w-full mt-2 gold-gradient font-display-lg text-[9px] uppercase py-1 rounded shadow-sm hover:brightness-110 transition-all font-bold text-center block text-slate-900"
                  >
                    🔮 UNLOCK (0.05 USDC)
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    );
  };

  const dfSlots = squad.filter(s => s.position === 'DF');
  const mfSlots = squad.filter(s => s.position === 'MF');
  const fwSlots = squad.filter(s => s.position === 'FW');
  const gkSlots = squad.filter(s => s.position === 'GK');

  // Helper to render midfielders layout row
  const renderMidfielders = () => {
    if (formation === '4-2-3-1') {
      return (
        <div className="flex flex-col gap-2 z-10 w-full">
          {/* Attacking Midfielders (3) */}
          <div className="flex justify-center gap-12 md:gap-20">
            {mfSlots.slice(2, 5).map(s => renderSlot(s))}
          </div>
          {/* Defensive Midfielders (2) */}
          <div className="flex justify-center gap-16 md:gap-24">
            {mfSlots.slice(0, 2).map(s => renderSlot(s))}
          </div>
        </div>
      );
    }
    
    if (mfSlots.length === 5) {
      return (
        <div className="flex justify-center gap-3 md:gap-6 z-10 w-full">
          {mfSlots.map((s, i) => (
            <div key={`mf-${i}`} className={i === 2 ? 'mt-3' : ''}>
              {renderSlot(s)}
            </div>
          ))}
        </div>
      );
    }

    if (mfSlots.length === 4) {
      return (
        <div className="flex justify-center gap-6 md:gap-10 z-10 w-full">
          {mfSlots.map(s => renderSlot(s))}
        </div>
      );
    }

    return (
      <div className="flex justify-center gap-12 md:gap-20 z-10 w-full">
        {mfSlots.map((s, i) => (
          <div key={`mf-${i}`} className={i === 1 ? 'mt-3' : ''}>
            {renderSlot(s)}
          </div>
        ))}
      </div>
    );
  };

  // Helper to render defenders layout row
  const renderDefenders = () => {
    if (dfCount === 6) {
      return (
        <div className="flex justify-center gap-2 md:gap-3 z-10 w-full">
          {dfSlots.map(s => renderSlot(s))}
        </div>
      );
    }
    if (dfCount === 3) {
      return (
        <div className="flex justify-center gap-12 md:gap-20 z-10 w-full">
          {dfSlots.map((s, i) => (
            <div key={`df-${i}`} className={i === 1 ? 'mt-3' : ''}>
              {renderSlot(s)}
            </div>
          ))}
        </div>
      );
    }
    return (
      <div className="flex justify-center gap-6 md:gap-10 z-10 w-full">
        {dfSlots.map((s, i) => (
          <div key={`df-${i}`} className={i === 1 || i === 2 ? 'mt-3' : ''}>
            {renderSlot(s)}
          </div>
        ))}
      </div>
    );
  };

  const activePitchWidthClass = 'max-w-[480px]';

  return (
    <div 
      ref={containerRef}
      className="flex-1 relative flex flex-col justify-start items-center p-4 pt-2 md:pt-4 overflow-y-auto bg-slate-200/50 h-full scrollbar-thin"
    >
      {/* Formation Selector Tab Row */}
      <div className={`w-full ${activePitchWidthClass} bg-white/80 backdrop-blur-sm px-4 py-2 rounded-full border border-slate-200 shadow-md flex items-center justify-between gap-1 mb-3 overflow-x-auto scrollbar-none font-label-sm text-xs font-bold text-slate-700`}>
        <span className="text-[10px] uppercase text-slate-400 mr-2 flex-shrink-0 flex items-center gap-1">
          <span className="material-symbols-outlined text-sm text-primary">grid_view</span>
          DIZILIŞ:
        </span>
        {['4-3-3', '4-4-2', '4-2-3-1', '4-5-1', '3-4-3', '3-5-2', '6-3-1'].map((form) => (
          <button
            key={form}
            onClick={() => onChangeFormation(form)}
            className={`px-3 py-1 rounded-full transition-all flex-shrink-0 ${
              formation === form
                ? 'bg-primary text-slate-900 shadow-sm border border-amber-300 font-black scale-105'
                : 'hover:bg-slate-100/80 text-slate-600 hover:text-slate-900 border border-transparent'
            }`}
          >
            {form}
          </button>
        ))}
      </div>

      {/* Large Aspect-constrained Football Pitch Container (Correct proportions with 2:3 aspect ratio) */}
      <div className={`relative w-full ${activePitchWidthClass} aspect-[2/3] pitch-bg px-4 py-6 shadow-2xl flex flex-col justify-between overflow-visible`}>
        {/* Crisp Football Pitch Lines Layer */}
        <div className="absolute inset-0 pitch-lines opacity-90 pointer-events-none"></div>

        {/* Formation rows */}
        {/* FW row */}
        <div className="flex justify-center gap-16 md:gap-24 z-10">
          {fwSlots.map(s => renderSlot(s))}
        </div>

        {/* MF row */}
        {renderMidfielders()}

        {/* DF row */}
        {renderDefenders()}

        {/* GK row */}
        <div className="flex justify-center z-10">
          {gkSlots.map(s => renderSlot(s))}
        </div>
      </div>

      {/* Substitutes Bench Area (statically rendered at the bottom of aligned container) */}
      {showBench && (
        <div className={`w-full ${activePitchWidthClass} mt-4 bg-white/95 backdrop-blur-sm p-4 rounded-2xl border border-slate-200 shadow-lg flex flex-col gap-2 animate-fade-in`}>
          <div className="flex justify-between items-center border-b border-slate-100 pb-1.5">
            <span className="font-display-lg text-sm uppercase text-slate-800 flex items-center gap-2">
              <span className="material-symbols-outlined text-secondary animate-pulse">sports_soccer</span>
              Yedek Kulübesi (Substitutes)
            </span>
            <span className="font-label-sm text-[10px] text-slate-400">
              {bench.filter(b => b.player !== null).length}/8 Oyuncu
            </span>
          </div>
          
          {/* Horizontal Scrollable Bench Slots */}
          <div className="flex gap-3 overflow-x-auto py-1 px-0.5 scrollbar-thin">
            {bench.map((slot, index) => renderSlot(slot, true))}
          </div>
        </div>
      )}
    </div>
  );
}
