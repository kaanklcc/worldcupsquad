'use client';

import { useState, useEffect, useCallback } from 'react';
import type { Player, SquadSlot, ChatMessage, SuggestedAction } from '@/types';
import Header from '@/components/Header';
import Pitch from '@/components/Pitch';
import ChatPanel from '@/components/ChatPanel';
import PlayerSelectionModal from '@/components/PlayerSelectionModal';
import Sidebar from '@/components/Sidebar';
import ExecuteSyncModal from '@/components/ExecuteSyncModal';

// ─── Initial Squad (4-3-3) ─────────────────────────────────────────────────────
function createInitialSquad(): SquadSlot[] {
  const positions: { pos: SquadSlot['position']; count: number }[] = [
    { pos: 'GK', count: 1 },
    { pos: 'DF', count: 4 },
    { pos: 'MF', count: 3 },
    { pos: 'FW', count: 3 },
  ];
  const slots: SquadSlot[] = [];
  for (const { pos, count } of positions) {
    for (let i = 0; i < count; i++) {
      slots.push({ position: pos, slotIndex: i, player: null });
    }
  }
  return slots;
}

// ─── Initial Bench (8 players) ──────────────────────────────────────────────────
function createInitialBench(): SquadSlot[] {
  return [
    { position: 'GK', slotIndex: 10, player: null },
    { position: 'DF', slotIndex: 10, player: null },
    { position: 'DF', slotIndex: 11, player: null },
    { position: 'MF', slotIndex: 10, player: null },
    { position: 'MF', slotIndex: 11, player: null },
    { position: 'MF', slotIndex: 12, player: null },
    { position: 'FW', slotIndex: 10, player: null },
    { position: 'FW', slotIndex: 11, player: null },
  ];
}

export default function HomePage() {
  // ─── State ──────────────────────────────────────────────────────────────
  const [players, setPlayers] = useState<Player[]>([]);
  const [squad, setSquad] = useState<SquadSlot[]>(createInitialSquad);
  const [bench, setBench] = useState<SquadSlot[]>(createInitialBench);
  const [budget, setBudget] = useState(100);
  const [cctpLoading, setCctpLoading] = useState(false);
  const [cctpUsed, setCctpUsed] = useState(false);
  const [agentLoading, setAgentLoading] = useState(false);
  const [pendingAction, setPendingAction] = useState<SuggestedAction | null>(null);

  // Tab State
  const [activeTab, setActiveTab] = useState('AI Consultant');

  // Premium / Sync State
  const [isPremiumUnlocked, setIsPremiumUnlocked] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);

  // Modal state
  const [modalOpen, setModalOpen] = useState(false);
  const [selectedSlot, setSelectedSlot] = useState<SquadSlot | null>(null);

  // Formation state
  const [formation, setFormation] = useState('4-3-3');

  // Chat state
  const [messages, setMessages] = useState<ChatMessage[]>([]);

  // ─── Load players ───────────────────────────────────────────────────────
  useEffect(() => {
    const API_URL = process.env.NEXT_PUBLIC_API_URL || '';
    fetch(`${API_URL}/api/players`)
      .then((res) => res.json())
      .then((data: Player[]) => setPlayers(data))
      .catch(console.error);
  }, []);

  // ─── Derived ────────────────────────────────────────────────────────────
  const squadPlayerIds = [
    ...squad.filter((s) => s.player !== null).map((s) => s.player!.id),
    ...bench.filter((s) => s.player !== null).map((s) => s.player!.id)
  ];

  const currentSquadCost = 
    squad.reduce((sum, s) => sum + (s.player?.price ?? 0), 0) +
    bench.reduce((sum, s) => sum + (s.player?.price ?? 0), 0);

  const getFormationCounts = useCallback((form: string) => {
    if (form === '4-2-3-1') return { df: 4, mf: 5, fw: 1 };
    const parts = form.split('-').map(Number);
    return { df: parts[0], mf: parts[1], fw: parts[2] };
  }, []);

  // ─── Handlers ───────────────────────────────────────────────────────────

  // Formation Change Handler
  const handleFormationChange = useCallback((newFormation: string) => {
    setFormation(newFormation);
    const counts = getFormationCounts(newFormation);
    
    // Get all currently selected players
    const selectedPlayers = squad
      .filter(s => s.player !== null)
      .map(s => s.player!);
      
    const newSlots: SquadSlot[] = [];
    
    // Add GK slot
    const existingGK = selectedPlayers.find(p => p.position === 'GK');
    newSlots.push({ position: 'GK', slotIndex: 0, player: existingGK || null });
    
    // Helper to fill slots
    const fillSlotsForPosition = (pos: 'DF' | 'MF' | 'FW', count: number) => {
      const matchingPlayers = selectedPlayers.filter(p => p.position === pos && p.id !== existingGK?.id);
      for (let i = 0; i < count; i++) {
        newSlots.push({
          position: pos,
          slotIndex: i,
          player: matchingPlayers[i] || null
        });
      }
    };
    
    fillSlotsForPosition('DF', counts.df);
    fillSlotsForPosition('MF', counts.mf);
    fillSlotsForPosition('FW', counts.fw);
    
    setSquad(newSlots);
  }, [squad, getFormationCounts]);

  // Slot click → open modal or remove player
  const handleSlotClick = useCallback((slot: SquadSlot) => {
    if (slot.player) {
      // Remove player from slot
      setSquad((prev) =>
        prev.map((s) =>
          s.position === slot.position && s.slotIndex === slot.slotIndex
            ? { ...s, player: null }
            : s
        )
      );
    } else {
      // Open selection modal
      setSelectedSlot({ ...slot, isBench: false } as any);
      setModalOpen(true);
    }
  }, []);

  // Bench slot click
  const handleBenchSlotClick = useCallback((slot: SquadSlot) => {
    if (slot.player) {
      setBench((prev) =>
        prev.map((s) =>
          s.position === slot.position && s.slotIndex === slot.slotIndex
            ? { ...s, player: null }
            : s
        )
      );
    } else {
      setSelectedSlot({ ...slot, isBench: true } as any);
      setModalOpen(true);
    }
  }, []);

  // Player selection from modal
  const handleSelectPlayer = useCallback(
    (player: Player) => {
      if (!selectedSlot) return;
      const isBench = (selectedSlot as any).isBench;
      
      if (isBench) {
        setBench((prev) =>
          prev.map((s) =>
            s.position === selectedSlot.position &&
            s.slotIndex === selectedSlot.slotIndex
              ? { ...s, player }
              : s
          )
        );
      } else {
        setSquad((prev) =>
          prev.map((s) =>
            s.position === selectedSlot.position &&
            s.slotIndex === selectedSlot.slotIndex
              ? { ...s, player }
              : s
          )
        );
      }
      setModalOpen(false);
      setSelectedSlot(null);
    },
    [selectedSlot]
  );

  // CCTP Bridge
  const handleCCTP = useCallback(async () => {
    setCctpLoading(true);
    try {
      const API_URL = process.env.NEXT_PUBLIC_API_URL || '';
      const res = await fetch(`${API_URL}/api/cctp`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          walletAddress: 'inj1x8dq7f3k9v2m4n5p6r7s8t9u0w1x2y3z4k4m2',
          amount: 20,
          sourceChain: 'Ethereum',
        }),
      });
      const data = await res.json();
      if (data.success) {
        setBudget((prev) => prev + data.newBudgetBonus);
        setCctpUsed(true);
        // Add system message to chat
        setMessages((prev) => [
          ...prev,
          {
            id: `msg-${Date.now()}`,
            role: 'assistant',
            content: `⛓️ **CCTP Bridge Başarılı!**\n\n${data.message}\n\nTx Hash: \`${data.txHash}\`\n\nOyun bütçeniz artık **${budget + data.newBudgetBonus}M**.`,
          },
        ]);
      }
    } catch (err) {
      console.error('CCTP error:', err);
    } finally {
      setCctpLoading(false);
    }
  }, [budget]);

  // Send chat message
  const handleAgentChat = useCallback(
    async (prompt: string, isPremium: boolean) => {
      // Add user message
      const userMsg: ChatMessage = {
        id: `msg-${Date.now()}`,
        role: 'user',
        content: isPremium ? `🔮 [Premium] ${prompt}` : prompt,
        isPremium,
      };
      setMessages((prev) => [...prev, userMsg]);
      setAgentLoading(true);
      if (isPremium) {
        setIsPremiumUnlocked(true);
      }

      try {
        const API_URL = process.env.NEXT_PUBLIC_API_URL || '';
        const res = await fetch(`${API_URL}/api/agent`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            prompt,
            hasPaidX402: isPremium,
            squadPlayerIds,
          }),
        });
        const data = await res.json();
        
        const assistantMsg: ChatMessage = {
          id: `msg-${Date.now()}-resp`,
          role: 'assistant',
          content: data.message,
          isPremium: data.isPremium,
          suggestedAction: data.suggestedAction,
          actionApplied: false,
        };
        
        setMessages((prev) => [...prev, assistantMsg]);
        if (isPremium && data.suggestedAction) {
          setPendingAction(data.suggestedAction);
        }
      } catch (err) {
        console.error('Agent error:', err);
        setMessages((prev) => [
          ...prev,
          {
            id: `msg-${Date.now()}-err`,
            role: 'assistant',
            content: '❌ Bir hata oluştu. Lütfen tekrar deneyin.',
          },
        ]);
      } finally {
        setAgentLoading(false);
      }
    },
    [squadPlayerIds]
  );


  // Tab click handler (Triggers Premium analysis when Analytics is clicked)
  const handleTabClick = useCallback((tab: string) => {
    if (tab === 'Analytics') {
      setActiveTab('AI Consultant');
      setIsPremiumUnlocked(true);
      // Add a system notice to chat
      setMessages((prev) => [
        ...prev,
        {
          id: `msg-premium-unlock-${Date.now()}`,
          role: 'assistant',
          content: `🔮 **Deep Tactical Analytics Unlocked!**\n\nInitializing premium database scans for Spain, England, France, and Argentina squad statistics. Compiling optimal tactical recommendation...`,
          isPremium: true,
        },
      ]);
      handleAgentChat('Analyse my squad and suggest the best transfer', true);
    } else if (tab === 'Matchday') {
      setActiveTab('AI Consultant');
      setMessages((prev) => [
        ...prev,
        {
          id: `msg-matchday-${Date.now()}`,
          role: 'assistant',
          content: `🏆 **MATCHDAY LIVE REPORT — 2026 World Cup Semi-Finals**\n\n🕒 Fixtures:\n• **Spain vs France** (July 14, 2026 - Dallas)\n• **England vs Argentina** (July 15, 2026 - Atlanta)\n\n⚽ Scout tips: Mbappe and Messi are tied at 8 goals. Bellingham has scored 6 goals. Make sure to optimize your lineup!`,
        },
      ]);
    } else if (tab === 'Finance') {
      setActiveTab('AI Consultant');
      setMessages((prev) => [
        ...prev,
        {
          id: `msg-finance-${Date.now()}`,
          role: 'assistant',
          content: `💳 **FINANCE & BUDGET REPORTS**\n\n💰 Total Budget Limit: **120M USDC**\n💵 Available Budget: **${budget}M USDC**\n📉 Spent so far: **${currentSquadCost}M USDC**\n\n💡 *Tip: Bridge 20 USDC via CCTP Bridge to increase your squad budget by 20M!*`,
        },
      ]);
    } else {
      setActiveTab(tab);
    }
  }, [handleAgentChat, budget, currentSquadCost]);

  // Premium Unlock Handler
  const handleUnlockPremium = useCallback(() => {
    setIsPremiumUnlocked(true);
    setMessages((prev) => [
      ...prev,
      {
        id: `msg-premium-unlock-tooltip-${Date.now()}`,
        role: 'assistant',
        content: `🔮 **Deep Tactical Analytics Unlocked globally!**\n\nAll player tooltips, scout notes, injury risk levels, and expected goals (xG) metrics are now fully visible on the field.`,
        isPremium: true,
      },
    ]);
    handleAgentChat('Analyse my squad and suggest the best transfer', true);
  }, [handleAgentChat]);

  // Execute changes sync handler
  const handleExecuteChanges = useCallback(() => {
    setIsSyncing(true);
  }, []);

  // Approve MCP action
  const handleApproveAction = useCallback(
    (action: SuggestedAction) => {
      const sellPlayer = players.find((p) => p.id === action.sellPlayerId);
      const buyPlayer = players.find((p) => p.id === action.buyPlayerId);
      if (!sellPlayer || !buyPlayer) return;

      // Execute the transfer on the squad
      setSquad((prev) =>
        prev.map((slot) => {
          if (slot.player?.id === action.sellPlayerId) {
            return { ...slot, player: buyPlayer };
          }
          return slot;
        })
      );

      // Mark the action as applied
      const updatedMessages = messages.map(msg => {
        if (msg.role === 'assistant' && pendingAction) {
          return { ...msg, actionApplied: true };
        }
        return msg;
      });
      setMessages(updatedMessages);
      setPendingAction(null);

      // Add confirmation message
      setMessages((prev) => [
        ...prev,
        {
          id: `msg-${Date.now()}-mcp`,
          role: 'assistant',
          content:
            `🔗 **MCP Transfer Onaylandı (On-Chain)**\n\n` +
            `❌ Satıldı: **${sellPlayer.name}** (${sellPlayer.price}M)\n` +
            `✅ Alındı: **${buyPlayer.name}** (${buyPlayer.price}M)\n\n` +
            `Transfer Injective zincirinde simüle edildi.\n` +
            `Tx: \`inj_mcp_swap_${Date.now()}\`\n\n` +
            `Kadronuz güncellendi, gaffer! ⚽`,
        },
      ]);
    },
    [players, messages, pendingAction]
  );

  // ─── Render ─────────────────────────────────────────────────────────────
  return (
    <div className="flex h-screen flex-col bg-background text-on-background overflow-hidden">
      <Header 
        budget={budget} 
        maxBudget={120}
        onAcquireBacking={handleCCTP} 
        cctpLoading={cctpLoading} 
        cctpUsed={cctpUsed} 
      />

      <div className="flex flex-1 overflow-hidden">
        {/* Left Sidebar (Now stretches all the way to the bottom) */}
        <Sidebar 
          activeTab={activeTab} 
          onTabClick={handleTabClick} 
          onExecuteClick={handleExecuteChanges}
        />

        {/* Middle Column (Pitch + Chat + Footer nested) */}
        <div className="flex-1 flex flex-col overflow-hidden h-full">
          <div className="flex-1 flex overflow-hidden">
            {/* Center Pitch */}
            <Pitch 
              squad={squad} 
              onSlotClick={handleSlotClick}
              formation={formation}
              onChangeFormation={handleFormationChange}
              bench={bench}
              onBenchSlotClick={handleBenchSlotClick}
              showBench={activeTab === 'Substitutions'}
              isPremiumUnlocked={isPremiumUnlocked}
              onUnlockPremium={handleUnlockPremium}
            />

            {/* Right AI Panel */}
            <ChatPanel 
              messages={messages}
              onSendMessage={handleAgentChat}
              onApproveAction={handleApproveAction}
              isLoading={agentLoading}
              pendingAction={pendingAction}
              sellPlayer={pendingAction ? players.find(p => p.id === pendingAction.sellPlayerId) || null : null}
              buyPlayer={pendingAction ? players.find(p => p.id === pendingAction.buyPlayerId) || null : null}
            />
          </div>

          {/* Footer (Nested under center columns to allow sidebar to stretch to bottom) */}
          <footer className="border-t border-slate-200 bg-white/50 px-4 py-4 flex-shrink-0">
            <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-2 sm:flex-row">
              <p className="text-xs text-slate-500 font-label-sm">
                ⚽ Auto-Gaffer — Injective Global Cup Hackathon 2026
              </p>
              <div className="flex items-center gap-4 text-[10px] text-slate-400 font-label-sm">
                <span>Built on Injective</span>
                <span>•</span>
                <span>x402 · CCTP · Agent Skills · MCP</span>
              </div>
            </div>
          </footer>
        </div>
      </div>

      {/* Player Selection Modal */}
      <PlayerSelectionModal
        isOpen={modalOpen}
        onClose={() => {
          setModalOpen(false);
          setSelectedSlot(null);
        }}
        players={players}
        targetPosition={selectedSlot?.position ?? null}
        currentSquadIds={squadPlayerIds}
        budget={budget}
        currentSquadCost={currentSquadCost}
        onSelectPlayer={handleSelectPlayer}
      />

      {/* Execute Sync Modal */}
      <ExecuteSyncModal 
        isOpen={isSyncing} 
        onClose={() => setIsSyncing(false)} 
      />
    </div>
  );
}
