'use client';

import { useState, useEffect, useCallback, useMemo } from 'react';
import type { Player, SquadSlot, ChatMessage, SuggestedAction, TransferReceipt, LineupApplyReceipt, AccessStatus, AccessUnlockResponse, CCTPReceipt, MatchdayBriefResponse, TacticalLabResponse } from '@/types';
import Header from '@/components/Header';
import Pitch from '@/components/Pitch';
import ChatPanel from '@/components/ChatPanel';
import PlayerSelectionModal from '@/components/PlayerSelectionModal';
import Sidebar from '@/components/Sidebar';
import ExecuteSyncModal from '@/components/ExecuteSyncModal';
import AuthOverlay from '@/components/AuthOverlay';
import AccessModal from '@/components/AccessModal';
import TacticalLabPanel from '@/components/TacticalLabPanel';
import PlayerIntelModal from '@/components/PlayerIntelModal';
import CctpBridgeModal from '@/components/CctpBridgeModal';
import { apiFetch, setCsrfToken } from '@/lib/api';
import { payWithX402 } from '@/lib/x402';

type SelectedSlot = SquadSlot & { isBench: boolean };

const FORMATION_COUNTS: Record<string, { df: number; mf: number; fw: number }> = {
  '4-3-3': { df: 4, mf: 3, fw: 3 },
  '4-2-3-1': { df: 4, mf: 5, fw: 1 },
  '3-5-2': { df: 3, mf: 5, fw: 2 },
  '4-4-2': { df: 4, mf: 4, fw: 2 },
  '5-3-2': { df: 5, mf: 3, fw: 2 },
};

const DEEP_ANALYTICS_PROMPT = 'Run Deep Tactical Analytics on my current squad. Respect the selected formation and the authenticated server-side budget. Evaluate positional balance, verified World Cup 2026 goals and assists where available, model xG estimates, player availability, clean-sheet potential and price efficiency. Identify the three weakest tactical points, compare at least two viable transfer alternatives, then return one executable budget-valid transfer only when it materially improves the squad. Clearly distinguish verified tournament facts from model estimates.';

function createIdempotencyKey(action: string): string {
  const suffix = typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  return `wcai-${action}-${suffix}`;
}

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
  const [cctpUsed, setCctpUsed] = useState(false);
  const [cctpModalOpen, setCctpModalOpen] = useState(false);
  const [agentLoading, setAgentLoading] = useState(false);
  const [pendingAction, setPendingAction] = useState<SuggestedAction | null>(null);

  // Tab State
  const [activeTab, setActiveTab] = useState('AI Consultant');

  // Membership / x402 access is always sourced from the backend.
  const [accessStatus, setAccessStatus] = useState<AccessStatus | null>(null);
  const [accessModalOpen, setAccessModalOpen] = useState(false);
  const [accessLoading, setAccessLoading] = useState(false);
  const [accessError, setAccessError] = useState<string | null>(null);
  const [isSyncing, setIsSyncing] = useState(false);
  const [matchdayBrief, setMatchdayBrief] = useState<MatchdayBriefResponse | null>(null);
  const [tacticalLab, setTacticalLab] = useState<TacticalLabResponse | null>(null);

  // Authentication State
  const [currentUser, setCurrentUser] = useState<string | null>(null);
  const [authLoading, setAuthLoading] = useState(true);

  // Modal state
  const [modalOpen, setModalOpen] = useState(false);
  const [selectedSlot, setSelectedSlot] = useState<SelectedSlot | null>(null);
  const [intelPlayer, setIntelPlayer] = useState<Player | null>(null);
  const [intelSlot, setIntelSlot] = useState<SelectedSlot | null>(null);

  // Formation state
  const [formation, setFormation] = useState('4-3-3');

  // Chat state
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [actionExecuting, setActionExecuting] = useState(false);
  const [syncStage, setSyncStage] = useState<'signing' | 'broadcasting' | 'success' | 'error'>('signing');
  const [syncTxHash, setSyncTxHash] = useState<string | undefined>();
  const [syncError, setSyncError] = useState<string | undefined>();

  // Fetch squad lineup from SQLite database
  const fetchSquadLineup = useCallback(() => {
    apiFetch<{
      success: boolean;
      budget: number;
      cctpUsed: boolean;
      formation: string;
      squad: SquadSlot[];
      bench: SquadSlot[];
    }>('/api/squad/load')
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

  const fetchAccessStatus = useCallback(async () => {
    try {
      const access = await apiFetch<AccessStatus>('/api/access/status');
      setAccessStatus(access);
    } catch (error) {
      console.error(error);
      setAccessStatus(null);
    }
  }, []);

  // ─── Load players & Verify Token ───────────────────────────────────────────
  useEffect(() => {
    const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    
    // 1. Fetch Players
    fetch(`${API_URL}/api/players`)
      .then((res) => res.json())
      .then((data: Player[]) => setPlayers(data))
      .catch(console.error);

    // 2. Validate the server-side HttpOnly session cookie. The UI never treats
    // stale browser storage or an offline backend as an authenticated session.
    apiFetch<{ authenticated: boolean; username: string; csrfToken?: string }>('/api/auth/me')
      .then((session) => {
        setCsrfToken(session.csrfToken ?? null);
        setCurrentUser(session.username);
        fetchSquadLineup();
        fetchAccessStatus();
      })
      .catch(() => setCurrentUser(null))
      .finally(() => setAuthLoading(false));
  }, [fetchAccessStatus, fetchSquadLineup]);

  // Revalidate short-lived judge access while the dashboard remains open so
  // locked controls return automatically when the 30-minute pass expires.
  useEffect(() => {
    if (!currentUser) return;
    const interval = window.setInterval(() => {
      void fetchAccessStatus();
    }, 15_000);
    return () => window.clearInterval(interval);
  }, [currentUser, fetchAccessStatus]);

  // Keep player cards, prices and live World Cup goal/assist tallies current
  // without forcing the user to reload the dashboard. The API itself caches
  // provider requests for one minute, so this interval never polls the source
  // more often than the server-side freshness policy permits.
  useEffect(() => {
    const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    const refreshPlayers = () => {
      fetch(`${API_URL}/api/players`)
        .then((res) => {
          if (!res.ok) throw new Error(`Player refresh failed (${res.status})`);
          return res.json() as Promise<Player[]>;
        })
        .then((data) => setPlayers(data))
        .catch((error) => console.error('Live player refresh failed:', error));
    };
    const interval = window.setInterval(refreshPlayers, 60_000);
    return () => window.clearInterval(interval);
  }, []);

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

  const isPremiumUnlocked = accessStatus?.hasAiAccess ?? false;

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
    setSelectedSlot({ ...slot, isBench: false });
    setModalOpen(true);
  }, []);

  // Bench slot click
  const handleBenchSlotClick = useCallback((slot: SquadSlot) => {
    setSelectedSlot({ ...slot, isBench: true });
    setModalOpen(true);
  }, []);

  const handleRemovePlayer = useCallback((slot: SquadSlot, isBench: boolean) => {
    const playerName = slot.player?.name;
    if (!playerName) return;

    const updateSlots = (previous: SquadSlot[]) =>
      previous.map((current) =>
        current.position === slot.position && current.slotIndex === slot.slotIndex
          ? { ...current, player: null }
          : current
      );

    if (isBench) {
      setBench(updateSlots);
    } else {
      setSquad(updateSlots);
    }

    setMessages((previous) => [
      ...previous,
      {
        id: `msg-${Date.now()}-remove`,
        role: 'assistant',
        content: `🗑️ **${playerName}** was removed from the ${isBench ? 'bench' : 'starting squad'}.`,
      },
    ]);
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

  const handleOpenPlayerIntel = useCallback((player: Player, slot: SquadSlot, isBench: boolean) => {
    setIntelPlayer(player);
    setIntelSlot({ ...slot, isBench });
  }, []);

  const handleReplaceFromIntel = useCallback(() => {
    if (!intelSlot) return;
    setSelectedSlot(intelSlot);
    setIntelPlayer(null);
    setIntelSlot(null);
    setModalOpen(true);
  }, [intelSlot]);

  // CCTP backing is browser-signed; the server credits a budget only after
  // it verifies both the Sepolia burn and Injective mint receipts.
  const handleCCTP = useCallback(() => {
    if (!accessStatus?.hasFinanceAccess) {
      setAccessError(null);
      setAccessModalOpen(true);
      setMessages((previous) => [
        ...previous,
        {
          id: `msg-${Date.now()}-finance-locked`,
          role: 'assistant',
          content: '🔒 **Injective Finance is locked**\n\nCCTP USDC backing requires an active Pro membership and a saved Injective wallet.',
          provider: 'locked',
        },
      ]);
      return;
    }
    if (!accessStatus.walletAddress) {
      setAccessError('Connect and save an Injective wallet address before using CCTP.');
      setAccessModalOpen(true);
      return;
    }

    setCctpModalOpen(true);
  }, [accessStatus]);

  const handleCctpComplete = useCallback((receipt: CCTPReceipt) => {
    setBudget((previous) => previous + receipt.newBudgetBonus);
    setCctpUsed(true);
    setCctpModalOpen(false);
    setMessages((previous) => [
      ...previous,
      {
        id: `msg-${Date.now()}-cctp-confirmed`,
        role: 'assistant',
        content: `**CCTP backing confirmed**\n\n${receipt.message}\n\nSepolia burn: \`${receipt.burnTxHash ?? 'verified'}\`\nInjective mint: \`${receipt.mintTxHash ?? receipt.txHash}\`\n\nYour WCAI squad budget increased by **${receipt.newBudgetBonus}M** after on-chain receipt verification.`,
      },
    ]);
  }, []);

  // Send chat message
  const handleAgentChat = useCallback(
    async (prompt: string, isAnalytics: boolean) => {
      // Add user message
      const userMsg: ChatMessage = {
        id: `msg-${Date.now()}`,
        role: 'user',
        content: isAnalytics ? `🔮 [Analytics] ${prompt}` : prompt,
        isPremium: isAnalytics,
      };
      setMessages((prev) => [...prev, userMsg]);
      setAgentLoading(true);

      try {
        const data = await apiFetch<{
          message: string;
          suggestedAction?: SuggestedAction;
          isPremium: boolean;
          paymentVerified?: boolean;
          provider?: 'gemini' | 'fallback' | 'locked';
          model?: string;
          accessRequired?: boolean;
          membershipActive?: boolean;
          accessSource?: string;
        }>('/api/agent', {
          method: 'POST',
          body: JSON.stringify({
            prompt,
            // Access is determined from the authenticated user on the server.
            hasPaidX402: false,
            squadPlayerIds,
            formation,
            analysisMode: isAnalytics,
          }),
        });
        
        const assistantMsg: ChatMessage = {
          id: `msg-${Date.now()}-resp`,
          role: 'assistant',
          content: data.message,
          isPremium: data.isPremium,
          suggestedAction: data.suggestedAction,
          actionApplied: false,
          provider: data.provider,
        };
        
        setMessages((prev) => [...prev, assistantMsg]);
        if (data.suggestedAction) {
          setPendingAction(data.suggestedAction);
        }
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Unknown error.';
        setMessages((prev) => [
          ...prev,
          {
            id: `msg-${Date.now()}-err`,
            role: 'assistant',
            content: `❌ WCAI could not respond: ${message}`,
          },
        ]);
      } finally {
        setAgentLoading(false);
      }
    },
    [formation, squadPlayerIds]
  );


  const handleMatchdayBrief = useCallback(async () => {
    setActiveTab('Matchday');
    setTacticalLab(null);
    setMatchdayBrief(null);
    try {
      const data = await apiFetch<MatchdayBriefResponse>(`/api/worldcup/matchday-brief?formation=${encodeURIComponent(formation)}`);
      setMatchdayBrief(data);
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        {
          id: `msg-matchday-error-${Date.now()}`,
          role: 'assistant',
          content: `⚠️ Matchday Brief could not be loaded: ${error instanceof Error ? error.message : 'Unknown error'}`,
        },
      ]);
    }
  }, [formation]);

  const handleTacticalLab = useCallback(async () => {
    if (!accessStatus?.hasAnalyticsAccess) {
      setAccessError(null);
      setAccessModalOpen(true);
      setMessages((prev) => [
        ...prev,
        {
          id: `msg-lab-locked-${Date.now()}`,
          role: 'assistant',
          content: '🔒 **Tactical Lab is locked**\n\nWhat-if formation comparisons, budget optimisation and non-mutating scenario tests require Pro membership or an x402 Match Pass.',
          provider: 'locked',
        },
      ]);
      return;
    }
    setActiveTab('Tactical Lab');
    setMatchdayBrief(null);
    setTacticalLab(null);
    try {
      const data = await apiFetch<TacticalLabResponse>('/api/tactical-lab/compare', {
        method: 'POST',
        body: JSON.stringify({
          formation,
          strategy: 'attacking',
          squadPlayerIds,
          matchContext: 'FIFA World Cup 2026 confirmed 48-team squad pool',
        }),
      });
      setTacticalLab(data);
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        {
          id: `msg-lab-error-${Date.now()}`,
          role: 'assistant',
          content: `⚠️ Tactical Lab could not run: ${error instanceof Error ? error.message : 'Unknown error'}`,
        },
      ]);
    }
  }, [accessStatus?.hasAnalyticsAccess, formation, squadPlayerIds]);

  // Tab click handler (Triggers Premium analysis when Analytics is clicked)
  const handleTabClick = useCallback((tab: string) => {
    if (tab === 'Matchday') {
      handleMatchdayBrief();
      return;
    }
    if (tab === 'Tactical Lab') {
      handleTacticalLab();
      return;
    }
    if (tab === 'Analytics') {
      setActiveTab('AI Consultant');
      // Locked users receive the complete capability/paywall text from the
      // agent endpoint; entitled users receive the same deep analysis used by
      // the dedicated button.
      handleAgentChat(DEEP_ANALYTICS_PROMPT, true);
    } else if (tab === 'Finance') {
      setActiveTab('AI Consultant');
      if (!accessStatus?.hasFinanceAccess) {
        setAccessError(null);
        setAccessModalOpen(true);
        setMessages((prev) => [
          ...prev,
          {
            id: `msg-finance-locked-${Date.now()}`,
            role: 'assistant',
            content: '🔒 **Finance & Wallet access is locked**\n\nInjective wallet management and CCTP USDC backing require an active Pro membership. When Hackathon Demo checkout is enabled, any signed-in reviewer can explicitly activate a time-limited simulated membership without being charged.',
            provider: 'locked',
          },
        ]);
        return;
      }
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
  }, [accessStatus?.hasFinanceAccess, handleAgentChat, handleMatchdayBrief, handleTacticalLab, budget, currentSquadCost]);

  // Premium Unlock Handler
  const handleUnlockPremium = useCallback(() => {
    if (!accessStatus?.hasAnalyticsAccess) {
      setAccessError(null);
      setAccessModalOpen(true);
      return;
    }
    handleAgentChat(DEEP_ANALYTICS_PROMPT, true);
  }, [accessStatus?.hasAnalyticsAccess, handleAgentChat]);

  const handleUnlockAccess = useCallback(async (
    mode: 'membership' | 'single_use',
    walletAddress?: string,
    accessMethod: 'demo' | 'x402' = 'demo',
  ) => {
    setAccessLoading(true);
    setAccessError(null);
    try {
      const data = await payWithX402<AccessUnlockResponse>(
        '/api/access/unlock',
        {
          mode,
          accessMethod,
          hasPaidX402: accessMethod === 'x402',
          walletAddress: walletAddress || undefined,
        },
        createIdempotencyKey(`access-${mode}`),
      );
      setAccessStatus(data);
      setMessages((previous) => [
        ...previous,
        {
          id: `msg-access-${Date.now()}`,
          role: 'assistant',
          content:
            `✅ **Access activated**\n\n${data.message}\n` +
            `Plan: **${data.membershipActive ? data.membershipTier : 'Match Pass'}**\n` +
            `Receipt: \`${data.receipt}\`` +
            `${data.simulated
              ? `\n\n_Hackathon Demo receipt: 0 USDC charged, no wallet signature and no on-chain settlement.${data.demoExpiresAt ? ` Access expires at ${new Date(data.demoExpiresAt).toLocaleString()}.` : ''}_`
              : '\n\nOn-chain x402 testnet settlement was verified before access changed.'}`,
          isPremium: true,
        },
      ]);
      setAccessModalOpen(false);
    } catch (error) {
      setAccessError(error instanceof Error ? error.message : 'Access activation failed.');
    } finally {
      setAccessLoading(false);
    }
  }, []);

  const handleSaveWallet = useCallback(async (walletAddress: string) => {
    setAccessLoading(true);
    setAccessError(null);
    try {
      const data = await apiFetch<AccessStatus & { success: boolean }>('/api/access/wallet', {
        method: 'POST',
        body: JSON.stringify({ walletAddress }),
      });
      setAccessStatus(data);
    } catch (error) {
      setAccessError(error instanceof Error ? error.message : 'Wallet could not be saved.');
    } finally {
      setAccessLoading(false);
    }
  }, []);



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

    if (!currentUser) {
      setSyncStage('error');
      setSyncError('No active session was found. Please sign in again.');
      return;
    }

    try {
      setSyncStage('broadcasting');
      await saveSquadSnapshot();
      setSyncStage('success');
      setSyncTxHash(`inj_squad_sync_${Date.now().toString(16)}`);
    } catch (err) {
      setSyncStage('error');
      setSyncError(err instanceof Error ? err.message : 'Your squad could not be saved.');
    }
  }, [currentUser, saveSquadSnapshot]);

  // Authentication Callbacks
  const handleLoginSuccess = useCallback((username: string) => {
    setCurrentUser(username);
    fetchSquadLineup();
    fetchAccessStatus();
  }, [fetchAccessStatus, fetchSquadLineup]);

  const handleLogout = useCallback(() => {
    apiFetch<{ success: boolean }>('/api/auth/logout', { method: 'POST' })
      .catch(() => undefined)
      .finally(() => {
        setCsrfToken(null);
        setCurrentUser(null);
        setAccessStatus(null);
        setMessages([]);
        setPendingAction(null);
      });
  }, []);

  // Approve MCP action. Save first so the server validates the same snapshot
  // the AI analysed, then execute and display the returned MCP receipt.
  const handleApproveAction = useCallback(
    async (action: SuggestedAction) => {
      if (action.type === 'lineup') {
        const startingPlayerIds = action.startingPlayerIds ?? [];
        const lineupFormation = action.formation;
        if (!lineupFormation || startingPlayerIds.length !== 11) return;

        const lineupPlayers = startingPlayerIds
          .map((playerId) => players.find((player) => player.id === playerId))
          .filter((player): player is Player => Boolean(player));
        if (lineupPlayers.length !== 11) return;
        const benchPlayers = (action.benchPlayerIds ?? [])
          .map((playerId) => players.find((player) => player.id === playerId))
          .filter((player): player is Player => Boolean(player));

        setActionExecuting(true);
        try {
          const receipt = await apiFetch<LineupApplyReceipt>('/api/squad/apply-lineup', {
            method: 'POST',
            headers: { 'Idempotency-Key': createIdempotencyKey('lineup') },
            body: JSON.stringify({
              formation: lineupFormation,
              startingPlayerIds,
              benchPlayerIds: action.benchPlayerIds ?? [],
              reasoning: action.reasoning,
            }),
          });

          const byPosition: Record<Player['position'], Player[]> = {
            GK: lineupPlayers.filter((player) => player.position === 'GK'),
            DF: lineupPlayers.filter((player) => player.position === 'DF'),
            MF: lineupPlayers.filter((player) => player.position === 'MF'),
            FW: lineupPlayers.filter((player) => player.position === 'FW'),
          };
          const appliedSquad = createSquadForFormation(lineupFormation).map((slot) => ({
            ...slot,
            player: byPosition[slot.position].shift() ?? null,
          }));
          const benchByPosition: Record<Player['position'], Player[]> = {
            GK: benchPlayers.filter((player) => player.position === 'GK'),
            DF: benchPlayers.filter((player) => player.position === 'DF'),
            MF: benchPlayers.filter((player) => player.position === 'MF'),
            FW: benchPlayers.filter((player) => player.position === 'FW'),
          };
          const appliedBench = createInitialBench().map((slot) => ({
            ...slot,
            player: benchByPosition[slot.position].shift() ?? null,
          }));

          setFormation(lineupFormation);
          setSquad(appliedSquad);
          setBench(appliedBench);
          setMessages((prev) => [
            ...prev.map((msg) =>
              msg.suggestedAction?.type === 'lineup' &&
              msg.suggestedAction?.formation === lineupFormation
                ? { ...msg, actionApplied: true }
                : msg
            ),
            {
              id: `msg-${Date.now()}-lineup`,
              role: 'assistant',
              content:
                `✅ **AI lineup applied**\n\n${receipt.message}\n` +
                `Formation: **${receipt.formation}**\n` +
                `Players: **${receipt.appliedPlayerIds.length}**\n` +
                `MCP receipt: ${String((receipt.mcpReceipt as Record<string, unknown> | undefined)?.tx_hash ?? 'confirmed')}` +
                `${receipt.simulated ? '\n_Note: the MCP operation is simulated in demo transport._' : ''}`,
            },
          ]);
          setPendingAction(null);
        } catch (err) {
          const message = err instanceof Error ? err.message : 'The lineup could not be applied.';
          setMessages((prev) => [
            ...prev,
            { id: `msg-${Date.now()}-lineup-error`, role: 'assistant', content: `❌ Lineup rejected: ${message}` },
          ]);
        } finally {
          setActionExecuting(false);
        }
        return;
      }

      if (!action.sellPlayerId || !action.buyPlayerId) return;
      const sellPlayer = players.find((p) => p.id === action.sellPlayerId);
      const buyPlayer = players.find((p) => p.id === action.buyPlayerId);
      if (!sellPlayer || !buyPlayer) return;

      setActionExecuting(true);
      try {
        await saveSquadSnapshot();
        const receipt = await apiFetch<TransferReceipt>('/api/transfers/execute', {
          method: 'POST',
          headers: { 'Idempotency-Key': createIdempotencyKey('transfer') },
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
              `🔗 **MCP Transfer confirmed**\n\n` +
              `❌ Sold: **${sellPlayer.name}** (${sellPlayer.price}M)\n` +
              `✅ Signed: **${buyPlayer.name}** (${buyPlayer.price}M)\n\n` +
              `${receipt.message}\n` +
              `Receipt: \`${receipt.txHash}\`${receipt.simulated ? '\n\n_Note: the MCP operation is simulated in demo transport._' : ''}`,
          },
        ]);
        setPendingAction(null);
      } catch (err) {
        const message = err instanceof Error ? err.message : 'The transfer could not be completed.';
        setMessages((prev) => [
          ...prev,
          { id: `msg-${Date.now()}-mcp-error`, role: 'assistant', content: `❌ Transfer rejected: ${message}` },
        ]);
      } finally {
        setActionExecuting(false);
      }
    },
    [players, saveSquadSnapshot, squadPlayerIds]
  );

  const handleRejectAction = useCallback((action: SuggestedAction) => {
    const actionLabel = action.type === 'lineup'
      ? `${action.formation ?? formation} AI lineup`
      : 'tactical transfer';
    setPendingAction(null);
    setMessages((previous) => [
      ...previous,
      {
        id: `msg-${Date.now()}-action-rejected`,
        role: 'assistant',
        content: `🚫 **Proposal rejected**\n\n${actionLabel} was not applied; your current squad is unchanged.`,
      },
    ]);
  }, [formation]);

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
        cctpLoading={cctpModalOpen}
        cctpUsed={cctpUsed}
        accessStatus={accessStatus}
        onAccessClick={() => {
          setAccessError(null);
          setAccessModalOpen(true);
        }}
        onLogout={handleLogout}
      />

      <div className="flex flex-1 overflow-hidden">
        {/* Left Sidebar (Now stretches all the way to the bottom) */}
        <Sidebar 
          activeTab={activeTab} 
          onTabClick={handleTabClick} 
          onExecuteClick={handleExecuteChanges}
          onLogout={handleLogout}
          hasAnalyticsAccess={accessStatus?.hasAnalyticsAccess}
          hasFinanceAccess={accessStatus?.hasFinanceAccess}
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
              onRemovePlayer={handleRemovePlayer}
              onPlayerClick={handleOpenPlayerIntel}
              showBench={activeTab === 'Substitutions'}
              isPremiumUnlocked={isPremiumUnlocked}
              onUnlockPremium={handleUnlockPremium}
            />

            {/* Right AI Panel */}
            <ChatPanel 
              messages={messages}
              onSendMessage={handleAgentChat}
              onApproveAction={handleApproveAction}
              onRejectAction={handleRejectAction}
              onUnlockAccess={handleUnlockPremium}
              hasAiAccess={accessStatus?.hasAiAccess ?? false}
              isLoading={agentLoading}
              actionLoading={actionExecuting}
              pendingAction={pendingAction}
              sellPlayer={pendingAction ? players.find(p => p.id === pendingAction.sellPlayerId) || null : null}
              buyPlayer={pendingAction ? players.find(p => p.id === pendingAction.buyPlayerId) || null : null}
              players={players}
            />
          </div>

          {/* Footer (Nested under center columns to allow sidebar to stretch to bottom) */}
          <footer className="border-t border-slate-200 bg-white/50 px-4 py-4 flex-shrink-0">
            <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-2 sm:flex-row">
              <p className="text-xs text-slate-500 font-label-sm">
                ⚽ WCAI — Injective Global Cup Hackathon 2026
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
        currentPlayerPrice={selectedSlot?.player?.price ?? 0}
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

      <PlayerIntelModal
        player={intelPlayer}
        isOpen={Boolean(intelPlayer)}
        isPremiumUnlocked={isPremiumUnlocked}
        onClose={() => {
          setIntelPlayer(null);
          setIntelSlot(null);
        }}
        onReplace={handleReplaceFromIntel}
        onUnlockPremium={handleUnlockPremium}
      />

      <CctpBridgeModal
        isOpen={cctpModalOpen}
        savedWallet={accessStatus?.walletAddress}
        onClose={() => setCctpModalOpen(false)}
        onComplete={handleCctpComplete}
      />

      {accessModalOpen && (
        <AccessModal
          isOpen
          status={accessStatus}
          isLoading={accessLoading}
          error={accessError}
          onClose={() => setAccessModalOpen(false)}
          onUnlock={handleUnlockAccess}
          onSaveWallet={handleSaveWallet}
        />
      )}

      <TacticalLabPanel
        matchdayBrief={matchdayBrief}
        tacticalLab={tacticalLab}
        players={players}
        onClose={() => {
          setMatchdayBrief(null);
          setTacticalLab(null);
        }}
      />
    </div>
  );
}
