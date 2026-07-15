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
  roster_status?: 'announced' | 'confirmed' | 'not_available';
  availability_status?: 'available' | 'doubtful' | 'injured' | 'suspended' | 'unknown';
  world_cup_stats?: {
    appearances?: number;
    starts?: number;
    minutes?: number;
    goals?: number;
    assists?: number;
    data_status: 'verified' | 'not_available';
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
  totalPoints?: number;
  strategy?: 'balanced' | 'attacking' | 'defensive';
  reasoning: string;
}

export interface AgentResponse {
  message: string;
  suggestedAction?: SuggestedAction;
  isPremium: boolean;
  paymentVerified?: boolean;
  provider?: 'gemini' | 'fallback';
  model?: string;
}

export interface TransferReceipt {
  success: boolean;
  txHash: string;
  message: string;
  mcpReceipt?: Record<string, unknown>;
  simulated: boolean;
}

export interface LineupApplyReceipt {
  success: boolean;
  message: string;
  formation: string;
  appliedPlayerIds: string[];
  mcpReceipt?: Record<string, unknown>;
  simulated: boolean;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  isPremium?: boolean;
  suggestedAction?: SuggestedAction;
  actionApplied?: boolean;
  provider?: 'gemini' | 'fallback';
}
