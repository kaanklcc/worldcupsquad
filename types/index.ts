export interface PremiumStats {
  xg_per_game: number;
  injury_risk: 'Low' | 'Medium' | 'High';
  scout_note: string;
  source_status?: 'verified' | 'app_estimate';
}

export interface Player {
  id: string;
  name: string;
  position: 'GK' | 'DF' | 'MF' | 'FW';
  team: string;
  price: number;
  isAvailable: boolean;
  points: number;
  premium_stats: PremiumStats;
  flag?: string;
  number?: number;
  data_source?: string;
  data_updated_at?: string;
  source_url?: string;
  official_name?: string;
  club?: string;
  date_of_birth?: string;
  roster_status?: 'announced' | 'confirmed' | 'not_available';
  availability_status?: 'available' | 'doubtful' | 'injured' | 'suspended' | 'unknown';
  world_cup_stats?: {
    appearances?: number;
    starts?: number;
    minutes?: number;
    goals?: number;
    assists?: number;
    data_status: 'verified' | 'not_available';
    source_url?: string;
    updated_at?: string;
  };
}

export interface PlayerIntelMetric {
  key: string;
  label: string;
  value: number;
}

export interface PlayerIntel {
  player: Player;
  verified: {
    rosterStatus: string;
    availabilityStatus: string;
    tournamentStats: NonNullable<Player['world_cup_stats']>;
    officialProfile: {
      officialName: string;
      team: string;
      shirtNumber?: number;
      listedClub?: string;
      dateOfBirth?: string;
      source?: string;
      snapshotDate?: string;
    };
  };
  model: {
    isEstimate: true;
    overall: number;
    tier: 'elite' | 'impact' | 'scout';
    metrics: PlayerIntelMetric[];
    trend: number[];
    strengths: string[];
    scoutBrief: string;
  };
  provenance: {
    snapshotDate?: string;
    rosterSource?: string;
    tournamentStatsSource?: string;
    notice: string;
  };
}

export interface SquadSlot {
  position: 'GK' | 'DF' | 'MF' | 'FW';
  slotIndex: number;
  player: Player | null;
}

export interface SuggestedAction {
  type: 'transfer' | 'lineup';
  sellPlayerId?: string;
  buyPlayerId?: string;
  formation?: string;
  startingPlayerIds?: string[];
  benchPlayerIds?: string[];
  budgetUsed?: number;
  maxBudget?: number;
  totalPoints?: number;
  strategy?: 'balanced' | 'attacking' | 'defensive';
  reasoning: string;
}

export interface AgentResponse {
  message: string;
  suggestedAction?: SuggestedAction;
  isPremium: boolean;
  paymentVerified?: boolean;
  provider?: 'gemini' | 'fallback' | 'locked';
  model?: string;
  accessRequired?: boolean;
  membershipActive?: boolean;
  accessSource?: string;
}

export interface AccessStatus {
  username: string;
  isDemoAccount: boolean;
  membershipTier: 'free' | 'pro' | 'demo_pro';
  membershipStatus: 'active' | 'inactive';
  membershipActive: boolean;
  membershipSource?: string | null;
  membershipExpiresAt?: string | null;
  accessPassActive: boolean;
  accessPassExpiresAt?: string | null;
  hasAiAccess: boolean;
  hasAnalyticsAccess: boolean;
  hasFinanceAccess: boolean;
  accessSource?: string | null;
  walletAddress?: string | null;
  paymentMode: 'demo' | 'verified_x402';
  x402Network: string;
  pricing: {
    membershipUsdc: number;
    singleAccessUsdc: number;
    membershipDays: number;
    singleAccessMinutes: number;
  };
}

export interface AccessUnlockResponse extends AccessStatus {
  success: boolean;
  message: string;
  receipt: string;
  simulated: boolean;
  operation?: OperationReceipt;
}

export interface OperationReceipt {
  operationId: string;
  idempotencyKey: string;
  actionType: 'apply_lineup' | 'execute_transfer' | 'acquire_cctp_backing' | string;
  status: 'processing' | 'confirmed' | 'failed';
  provider: string;
  network?: string | null;
  txHash?: string | null;
  receipt?: Record<string, unknown> | null;
  error?: string | null;
  simulated: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface TransferReceipt {
  success: boolean;
  txHash: string;
  message: string;
  mcpReceipt?: Record<string, unknown>;
  simulated: boolean;
  operation?: OperationReceipt;
}

export interface CCTPReceipt {
  success: boolean;
  newBudgetBonus: number;
  txHash: string;
  message: string;
  simulated: boolean;
  operation?: OperationReceipt;
}

export interface LineupApplyReceipt {
  success: boolean;
  message: string;
  formation: string;
  appliedPlayerIds: string[];
  mcpReceipt?: Record<string, unknown>;
  simulated: boolean;
  operation?: OperationReceipt;
}

export interface TournamentTeam {
  id: string;
  code: string;
  name: string;
  group: string;
  flag?: string;
}

export interface TournamentMatch {
  id: string;
  matchNumber: number;
  stageKey: string;
  stage: string;
  group: string;
  homeTeam: string;
  awayTeam: string;
  homeCode: string;
  awayCode: string;
  homeScore: number | null;
  awayScore: number | null;
  status: 'scheduled' | 'live' | 'final' | string;
  kickoffLocal: string;
  venue: string;
  city: string;
}

export interface TournamentRoster {
  team: string;
  rosterAvailable: boolean;
  sourceUrl?: string;
  players: Player[];
}

export interface TournamentOverview {
  mode: 'live_event_feed' | 'live_community_feed' | 'local_fallback';
  updatedAt: string;
  liveError?: string;
  teams: TournamentTeam[];
  groups: Array<{ name: string; teams: TournamentTeam[] }>;
  matches: TournamentMatch[];
  rosters: TournamentRoster[];
  stageOrder: Record<string, number>;
  sources: {
    liveSchedule: string;
    localRoster: Record<string, string>;
    notice: string;
  };
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  isPremium?: boolean;
  suggestedAction?: SuggestedAction;
  actionApplied?: boolean;
  provider?: 'gemini' | 'fallback' | 'locked';
}

export interface MatchdayBriefResponse {
  success: boolean;
  briefType: 'wcai_matchday_brief';
  match: {
    id: string;
    stage: string;
    homeTeam: string;
    awayTeam: string;
    date: string;
    kickoffLocal: string;
    venue: string;
    status: string;
  };
  lineup: {
    formation: string;
    playerIds: string[];
    players: Player[];
    budgetUsed: number;
    maxBudget: number;
    totalPoints: number;
  };
  captain: Player;
  viceCaptain: Player;
  watchouts: string[];
  availabilitySignals: string[];
  dataConfidence: 'low' | 'medium' | 'high';
  snapshotDate: string;
  dataQuality: string;
  sourceUrls: string[];
  scenarios: Array<{
    id: string;
    label: string;
    formation: string;
    instruction: string;
  }>;
}

export interface TacticalLabComparison {
  formation: string;
  status: 'ready' | 'unavailable';
  budgetUsed?: number;
  maxBudget?: number;
  totalPoints?: number;
  optimizationScore?: number;
  playerIds?: string[];
  pointsDeltaFromBest?: number;
  reason?: string;
}

export interface TacticalLabResponse {
  success: boolean;
  feature: 'what_if_tactical_lab';
  selectedFormation: string;
  strategy: 'balanced' | 'attacking' | 'defensive';
  serverBudget: number;
  baseline: {
    playerCount: number;
    totalPoints: number;
    budgetUsed: number;
    positionBreakdown: Record<'GK' | 'DF' | 'MF' | 'FW', number>;
  } | null;
  recommended: TacticalLabComparison;
  comparisons: TacticalLabComparison[];
  snapshotDate: string;
  dataQuality: string;
  notice: string;
}
