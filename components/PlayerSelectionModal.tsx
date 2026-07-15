import { useState, useMemo } from 'react';
import { Player } from '@/types';

interface PlayerSelectionModalProps {
  isOpen: boolean;
  onClose: () => void;
  players: Player[];
  targetPosition: 'GK' | 'DF' | 'MF' | 'FW' | null;
  currentSquadIds: string[];
  budget: number;
  currentSquadCost: number;
  currentPlayerPrice?: number;
  onSelectPlayer: (player: Player) => void;
}

export default function PlayerSelectionModal({
  isOpen,
  onClose,
  players,
  targetPosition,
  currentSquadIds,
  budget,
  currentSquadCost,
  currentPlayerPrice = 0,
  onSelectPlayer,
}: PlayerSelectionModalProps) {
  const [searchTerm, setSearchTerm] = useState('');
  const [sortBy, setSortBy] = useState<'price' | 'points'>('points');

  const filteredPlayers = useMemo(() => {
    let result = players.filter((p) => !currentSquadIds.includes(p.id));

    if (targetPosition) {
      result = result.filter((p) => p.position === targetPosition);
    }

    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      result = result.filter(
        (p) => p.name.toLowerCase().includes(term) || p.team.toLowerCase().includes(term)
      );
    }

    return result.sort((a, b) => b[sortBy] - a[sortBy]);
  }, [players, targetPosition, currentSquadIds, searchTerm, sortBy]);

  if (!isOpen) return null;

  // When replacing a filled slot, release the outgoing player's value before
  // checking the incoming player. Empty slots keep the original calculation.
  const remainingBudget = budget - currentSquadCost + currentPlayerPrice;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-black/70 backdrop-blur-sm"
        onClick={onClose}
      ></div>

      {/* Modal Card */}
      <div className="relative bg-surface-container-low/95 backdrop-blur-xl border border-outline-variant/20 rounded-xl shadow-2xl w-full max-w-lg max-h-[85vh] flex flex-col animate-fade-in overflow-hidden">
        
        {/* Header */}
        <div className="border-b border-outline-variant/20 px-5 py-4 flex justify-between items-center bg-surface-dim">
          <div>
            <h2 className="font-display-lg text-headline-md uppercase tracking-tight text-on-surface">
              SELECT {targetPosition || 'PLAYER'}
            </h2>
            <p className="font-label-sm text-label-sm text-primary mt-1">
              Available Budget: <span className="font-bold">{remainingBudget.toFixed(1)}M</span>
            </p>
          </div>
          <button 
            onClick={onClose}
            className="text-on-surface-variant hover:text-error transition-colors"
          >
            <span className="material-symbols-outlined text-2xl">close</span>
          </button>
        </div>

        {/* Filters */}
        <div className="px-5 py-3 border-b border-outline-variant/20 flex gap-4 bg-surface-container">
          <div className="relative flex-1">
            <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant text-sm">
              search
            </span>
            <input
              type="text"
              placeholder="Search by name or team..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full bg-surface-dim border border-outline-variant rounded-md py-1.5 pl-9 pr-3 text-sm text-on-surface font-body focus:border-secondary focus:ring-1 focus:ring-secondary outline-none"
            />
          </div>
          <div className="flex bg-surface-dim rounded-md border border-outline-variant overflow-hidden font-label-sm text-label-sm">
            <button
              onClick={() => setSortBy('points')}
              className={`px-3 py-1.5 ${
                sortBy === 'points' 
                  ? 'bg-secondary text-surface font-bold' 
                  : 'text-on-surface-variant hover:bg-surface-container-high'
              }`}
            >
              PTS
            </button>
            <button
              onClick={() => setSortBy('price')}
              className={`px-3 py-1.5 ${
                sortBy === 'price' 
                  ? 'bg-primary text-surface font-bold' 
                  : 'text-on-surface-variant hover:bg-surface-container-high'
              }`}
            >
              PRICE
            </button>
          </div>
        </div>

        {/* Player List */}
        <div className="flex-1 overflow-y-auto scrollbar-thin p-2">
          {filteredPlayers.length === 0 ? (
            <div className="text-center py-10 text-on-surface-variant">
              No players found matching your criteria.
            </div>
          ) : (
            <div className="flex flex-col gap-1">
              {filteredPlayers.map((player) => {
                const exceedsBudget = player.price > remainingBudget;

                return (
                  <button
                    key={player.id}
                    onClick={() => {
                      if (exceedsBudget || !player.isAvailable) return;
                      onSelectPlayer(player);
                    }}
                    disabled={exceedsBudget || !player.isAvailable}
                    className={`w-full flex items-center gap-3 p-3 rounded-lg border transition-all text-left group ${
                      !player.isAvailable 
                        ? 'opacity-60 border-outline-variant/10 hover:border-outline-variant/30 cursor-pointer' 
                        : !player.isAvailable
                        ? 'border-error/20 bg-error/5 opacity-50 cursor-not-allowed'
                        : exceedsBudget
                        ? 'border-error/20 bg-error/5 opacity-50 cursor-not-allowed'
                        : 'border-outline-variant/20 hover:border-secondary/50 bg-surface hover:bg-surface-container-high cursor-pointer'
                    }`}
                  >
                    {/* Position Badge */}
                    <div className="w-10 h-10 rounded-md flex items-center justify-center font-label-sm text-label-sm font-bold bg-surface-container-highest border border-outline-variant/30 text-primary">
                      {player.position}
                    </div>

                    {/* Details */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-xl" title={player.team}>
                          {player.flag}
                        </span>
                        <span className={`font-display-lg text-body-lg uppercase truncate ${!player.isAvailable ? 'text-on-surface-variant' : 'text-on-surface'}`}>
                          {player.name}
                        </span>
                        {!player.isAvailable && (
                          <span className="bg-error-container text-on-error-container text-[10px] px-1.5 py-0.5 rounded uppercase font-bold tracking-wider font-display-lg">
                            🚑 Injured
                          </span>
                        )}
                      </div>
                      <div className="font-body-md text-label-sm text-on-surface-variant flex items-center gap-2">
                        <span>{player.team}</span>
                        <span>•</span>
                        <span className="font-bold font-label-sm text-[10px] bg-slate-100 text-slate-700 px-1.5 py-0.5 rounded border border-slate-200">
                          {player.number ? `#${player.number}` : 'FIFA roster'}
                        </span>
                        <span className="text-[9px] text-slate-400">
                          WC26 · {player.data_updated_at ?? 'snapshot'}
                        </span>
                      </div>
                    </div>

                    {/* Stats */}
                    <div className="flex flex-col items-end gap-1 font-label-sm text-label-sm">
                      <div className="flex gap-4">
                        <div className="flex flex-col items-end">
                          <span className="text-[10px] text-on-surface-variant uppercase">Pts</span>
                          <span className="font-bold text-primary">{player.points}</span>
                        </div>
                        <div className="flex flex-col items-end">
                          <span className="text-[10px] text-on-surface-variant uppercase">Price</span>
                          <span className={`font-bold ${exceedsBudget ? 'text-error' : 'text-secondary'}`}>
                            {player.price}M
                          </span>
                        </div>
                      </div>
                      {exceedsBudget && (
                        <span className="text-[10px] text-error flex items-center gap-1">
                          <span className="material-symbols-outlined text-[12px]">warning</span>
                          Over Budget
                        </span>
                      )}
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
