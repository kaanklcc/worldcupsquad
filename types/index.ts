export interface PremiumStats {
  xg_per_game: number;
  injury_risk: 'Low' | 'Medium' | 'High';
  scout_note: string;
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
}

export interface SquadSlot {
  position: 'GK' | 'DF' | 'MF' | 'FW';
  slotIndex: number;
  player: Player | null;
}

export interface SuggestedAction {
  type: 'transfer';
  sellPlayerId: string;
  buyPlayerId: string;
  reasoning: string;
}

export interface AgentResponse {
  message: string;
  suggestedAction?: SuggestedAction;
  isPremium: boolean;
  paymentVerified?: boolean;
}

export interface TransferReceipt {
  success: boolean;
  txHash: string;
  message: string;
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
}
