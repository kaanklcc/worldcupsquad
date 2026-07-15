'use client';

import { useState, useEffect, useCallback, useMemo } from 'react';
import type { Player, SquadSlot, ChatMessage, SuggestedAction, TransferReceipt } from '@/types';
import Header from '@/components/Header';
import Pitch from '@/components/Pitch';
import ChatPanel from '@/components/ChatPanel';
import PlayerSelectionModal from '@/components/PlayerSelectionModal';
import Sidebar from '@/components/Sidebar';
import ExecuteSyncModal from '@/components/ExecuteSyncModal';
import AuthOverlay from '@/components/AuthOverlay';
import { apiFetch } from '@/lib/api';

type SelectedSlot = SquadSlot & { isBench: boolean };

const FORMATION_COUNTS: Record<string, { df: number; mf: number; fw: number }> = {
  '4-3-3': { df: 4, mf: 3, fw: 3 },
  '4-2-3-1': { df: 4, mf: 5, fw: 1 },
  '3-5-2': { df: 3, mf: 5, fw: 2 },
  '4-4-2': { df: 4, mf: 4, fw: 2 },
  '5-3-2': { df: 5, mf: 3, fw: 2 },
};

function createSquadForFormation(formation: string): SquadSlot[] {
  const counts = FORMATION_COUNTS[formation] ?? FORMATION_COUNTS['4-3-3'];
  const slots: SquadSlot[] = [{ position: 'GK', slotIndex: 0, player: null }];

  for (const [position, count] of [
    ['DF', counts.df],
    ['MF', counts.mf],
    ['FW', counts.fw],
  ] as const) {
    for (let index = 0; index < count; index++) {
      slots.push({ position, slotIndex: index, player: null });
    }
  }

  return slots;
}

// ─── Initial Squad (4-3-3) ─────────────────────────────────────────────────────
function createInitialSquad(): SquadSlot[] {
  return createSquadForFormation('4-3-3');
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

  // Authentication State
  const [currentUser, setCurrentUser] = useState<string | null>(null);
  const [authLoading, setAuthLoading] = useState(true);

  // Modal state
  const [modalOpen, setModalOpen] = useState(false);
  const [selectedSlot, setSelectedSlot] = useState<SelectedSlot | null>(null);

  // Formation state
  const [formation, setFormation] = useState('4-3-3');

  // Chat state
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [actionExecuting, setActionExecuting] = useState(false);
  const [syncStage, setSyncStage] = useState<'signing' | 'broadcasting' | 'success' | 'error'>('signing');
  const [syncTxHash, setSyncTxHash] = useState<string | undefined>();
  const [syncError, setSyncError] = useState<string | undefined>();

  // Fetch squad lineup from SQLite database
  const fetchSquadLineup = useCallback((token: string) => {
    const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    fetch(`${API_URL}/api/squad/load`, {
      headers: { 'Authorization': `Bearer ${token}` }
    })
      .then((res) => res.json())
      .then((data) => {
        if (data.success) {
          setBudget(data.budget);
          setCctpUsed(data.cctpUsed);
          const loadedFormation = data.formation || '4-3-3';
          setFormation(loadedFormation);

          if (data.squad) {
            const savedSlots = new Map<string, Player | null>(
              data.squad.map((slot: SquadSlot): [string, Player | null] => [
                `${slot.position}-${slot.slotIndex}`,
                slot.player,
              ])
            );
            setSquad(
              createSquadForFormation(loadedFormation).map((slot) => ({
                ...slot,
                player: savedSlots.get(`${slot.position}-${slot.slotIndex}`) ?? null,
              }))
            );
          }
          if (data.bench) {
            const savedBench = new Map<string, Player | null>(
              data.bench.map((slot: SquadSlot): [string, Player | null] => [
                `${slot.position}-${slot.slotIndex}`,
                slot.player,
              ])
            );
            setBench(
              createInitialBench().map((slot) => ({
                ...slot,
                player: savedBench.get(`${slot.position}-${slot.slotIndex}`) ?? null,
              }))
            );
          }
        }
      })
      .catch(console.error);
  }, []);

  // ─── Load players & Verify Token ───────────────────────────────────────────
  useEffect(() => {
    const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    
    // 1. Fetch Players
    fetch(`${API_URL}/api/players`)
      .then((res) => res.json())
      .then((data: Player[]) => setPlayers(data))
      .catch(console.error);

    // 2. Validate session token
    const token = localStorage.getItem('token');
    const username = localStorage.getItem('username');
    if (token && username) {
      fetch(`${API_URL}/api/auth/me`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
        .then(res => {
          if (res.ok) {
            setCurrentUser(username);
            fetchSquadLineup(token);
          } else {
            localStorage.removeItem('token');
            localStorage.removeItem('username');
          }
        })
        .catch(() => {
          // If server is offline but we have stored credentials, let them in local mode
          setCurrentUser(username);
        })
        .finally(() => {
          setAuthLoading(false);
        });
    } else {
      // Defer the browser-only auth state transition until after the effect
      // has subscribed to the storage/network checks above.
      const timer = window.setTimeout(() => setAuthLoading(false), 0);
      return () => window.clearTimeout(timer);
    }
  }, [fetchSquadLineup]);

  // ─── Derived ────────────────────────────────────────────────────────────
  const squadPlayerIds = useMemo(
    () => [
      ...squad.filter((s) => s.player !== null).map((s) => s.player!.id),
      ...bench.filter((s) => s.player !== null).map((s) => s.player!.id),
    ],
    [squad, bench]
  );

  const currentSquadCost = useMemo(
    () =>
      squad.reduce((sum, s) => sum + (s.player?.price ?? 0), 0) +
      bench.reduce((sum, s) => sum + (s.player?.price ?? 0), 0),
    [squad, bench]
  );

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
      setSelectedSlot({ ...slot, isBench: false });
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
      setSelectedSlot({ ...slot, isBench: true });
      setModalOpen(true);
    }
  }, []);

  // Player selection from modal
  const handleSelectPlayer = useCallback(
    (player: Player) => {
      if (!selectedSlot) return;
      const { isBench } = selectedSlot;
      
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
      const data = await apiFetch<{
        success: boolean;
        newBudgetBonus: number;
        txHash: string;
        message: string;
        simulated: boolean;
      }>('/api/cctp', {
        method: 'POST',
        body: JSON.stringify({
          walletAddress: 'inj1x8dq7f3k9v2m4n5p6r7s8t9u0w1x2y3z4k4m2',
          amount: 20,
          sourceChain: 'Ethereum',
        }),
      });
      if (data.success) {
        setBudget((prev) => prev + data.newBudgetBonus);
        setCctpUsed(true);
        // Add system message to chat
        setMessages((prev) => [
          ...prev,
          {
            id: `msg-${Date.now()}`,
            role: 'assistant',
            content: `⛓️ **CCTP Bridge Başarılı!**\n\n${data.message}\n\nTx Hash: \`${data.txHash}\`\n\nOyun bütçeniz artık **${budget + data.newBudgetBonus}M**.${data.simulated ? '\n\n_Not: Bu işlem demo modunda simüle edildi._' : ''}`,
          },
        ]);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'CCTP bridge failed.';
      setMessages((prev) => [
        ...prev,
        { id: `msg-${Date.now()}-cctp-error`, role: 'assistant', content: `❌ CCTP işlemi başarısız: ${message}` },
      ]);
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

      try {
        const data = await apiFetch<{
          message: string;
          suggestedAction?: SuggestedAction;
          isPremium: boolean;
          paymentVerified?: boolean;
        }>('/api/agent', {
          method: 'POST',
          body: JSON.stringify({
            prompt,
            hasPaidX402: isPremium,
            squadPlayerIds,
          }),
        });
        
        const assistantMsg: ChatMessage = {
          id: `msg-${Date.now()}-resp`,
          role: 'assistant',
          content: data.message,
          isPremium: data.isPremium,
          suggestedAction: data.suggestedAction,
          actionApplied: false,
        };
        
        if (data.isPremium) {
          setIsPremiumUnlocked(true);
        }
        setMessages((prev) => [...prev, assistantMsg]);
        if (isPremium && data.suggestedAction) {
          setPendingAction(data.suggestedAction);
        }
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Bilinmeyen bir hata.';
        setMessages((prev) => [
          ...prev,
          {
            id: `msg-${Date.now()}-err`,
            role: 'assistant',
            content: `❌ AI danışmanı yanıt veremedi: ${message}`,
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
    setMessages((prev) => [
      ...prev,
      {
        id: `msg-premium-unlock-tooltip-${Date.now()}`,
        role: 'assistant',
          content: `🔮 **Deep Tactical Analytics requested.**\n\nThe AI is verifying your x402 access before revealing premium scouting data.`,
        isPremium: true,
      },
    ]);
    handleAgentChat('Analyse my squad and suggest the best transfer', true);
  }, [handleAgentChat]);



  // Persist the current tactical snapshot. The backend recalculates cost and
  // verifies player IDs, so this is safe even if the browser is tampered with.
  const saveSquadSnapshot = useCallback(async () => {
    return apiFetch<{ success: boolean; message: string }>('/api/squad/save', {
      method: 'POST',
      body: JSON.stringify({ budget, cctpUsed, formation, squad, bench }),
    });
  }, [budget, cctpUsed, formation, squad, bench]);

  // Execute changes sync handler
  const handleExecuteChanges = useCallback(async () => {
    setIsSyncing(true);
    setSyncStage('signing');
    setSyncTxHash(undefined);
    setSyncError(undefined);

    if (!localStorage.getItem('token')) {
      setSyncStage('error');
      setSyncError('Oturum bulunamadı. Lütfen tekrar giriş yapın.');
      return;
    }

    try {
      setSyncStage('broadcasting');
      await saveSquadSnapshot();
      setSyncStage('success');
      setSyncTxHash(`inj_squad_sync_${Date.now().toString(16)}`);
    } catch (err) {
      setSyncStage('error');
      setSyncError(err instanceof Error ? err.message : 'Kadronuz kaydedilemedi.');
    }
  }, [saveSquadSnapshot]);

  // Authentication Callbacks
  const handleLoginSuccess = useCallback((username: string, token: string) => {
    localStorage.setItem('token', token);
    localStorage.setItem('username', username);
    setCurrentUser(username);
    fetchSquadLineup(token);
  }, [fetchSquadLineup]);

  const handleLogout = useCallback(() => {
    localStorage.removeItem('token');
    localStorage.removeItem('username');
    setCurrentUser(null);
  }, []);

  // Approve MCP action. Save first so the server validates the same snapshot
  // the AI analysed, then execute and display the returned MCP receipt.
  const handleApproveAction = useCallback(
    async (action: SuggestedAction) => {
      const sellPlayer = players.find((p) => p.id === action.sellPlayerId);
      const buyPlayer = players.find((p) => p.id === action.buyPlayerId);
      if (!sellPlayer || !buyPlayer) return;

      setActionExecuting(true);
      try {
        await saveSquadSnapshot();
        const receipt = await apiFetch<TransferReceipt>('/api/transfers/execute', {
          method: 'POST',
          body: JSON.stringify({
            sellPlayerId: action.sellPlayerId,
            buyPlayerId: action.buyPlayerId,
            reasoning: action.reasoning,
            squadPlayerIds,
          }),
        });

        setSquad((prev) =>
          prev.map((slot) =>
            slot.player?.id === action.sellPlayerId ? { ...slot, player: buyPlayer } : slot
          )
        );
        setBench((prev) =>
          prev.map((slot) =>
            slot.player?.id === action.sellPlayerId ? { ...slot, player: buyPlayer } : slot
          )
        );
        setMessages((prev) => [
          ...prev.map((msg) =>
            msg.suggestedAction?.sellPlayerId === action.sellPlayerId &&
            msg.suggestedAction?.buyPlayerId === action.buyPlayerId
              ? { ...msg, actionApplied: true }
              : msg
          ),
          {
            id: `msg-${Date.now()}-mcp`,
            role: 'assistant',
            content:
              `🔗 **MCP Transfer Onaylandı**\n\n` +
              `❌ Satıldı: **${sellPlayer.name}** (${sellPlayer.price}M)\n` +
              `✅ Alındı: **${buyPlayer.name}** (${buyPlayer.price}M)\n\n` +
              `${receipt.message}\n` +
              `Receipt: \`${receipt.txHash}\`${receipt.simulated ? '\n\n_Not: MCP işlemi demo transportunda simüle edildi._' : ''}`,
          },
        ]);
        setPendingAction(null);
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Transfer gerçekleştirilemedi.';
        setMessages((prev) => [
          ...prev,
          { id: `msg-${Date.now()}-mcp-error`, role: 'assistant', content: `❌ Transfer reddedildi: ${message}` },
        ]);
      } finally {
        setActionExecuting(false);
      }
    },
    [players, saveSquadSnapshot, squadPlayerIds]
  );

  // ─── Render ─────────────────────────────────────────────────────────────
  if (authLoading) {
    return (
      <div className="h-screen w-screen flex flex-col items-center justify-center bg-slate-950 text-slate-300">
        <div className="h-10 w-10 border-4 border-emerald-500 border-t-transparent rounded-full animate-spin"></div>
        <span className="mt-4 font-mono-jb text-xs uppercase tracking-widest text-emerald-400">Verifying Manager Credentials...</span>
      </div>
    );
  }

  if (!currentUser) {
    return <AuthOverlay onLoginSuccess={handleLoginSuccess} />;
  }

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
          onLogout={handleLogout}
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
              actionLoading={actionExecuting}
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
        stage={syncStage}
        txHash={syncTxHash}
        error={syncError}
        onClose={() => setIsSyncing(false)}
      />
    </div>
  );
}
