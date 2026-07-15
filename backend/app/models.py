"""
Pydantic models matching the frontend types/index.ts.
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Literal

Formation = Literal['4-3-3', '4-4-2', '3-5-2', '4-2-3-1', '5-3-2']


class PremiumStats(BaseModel):
    xg_per_game: float
    injury_risk: Literal['Low', 'Medium', 'High']
    scout_note: str


class Player(BaseModel):
    id: str
    name: str
    position: Literal['GK', 'DF', 'MF', 'FW']
    team: str
    price: float
    isAvailable: bool
    points: int
    premium_stats: PremiumStats
    flag: Optional[str] = None
    number: Optional[int] = None

    class Config:
        populate_by_name = True


class SquadSlot(BaseModel):
    position: Literal['GK', 'DF', 'MF', 'FW']
    slotIndex: int
    player: Optional[Player] = None


class SuggestedAction(BaseModel):
    type: Literal['transfer']
    sellPlayerId: str
    buyPlayerId: str
    reasoning: str


class AgentResponse(BaseModel):
    message: str
    suggestedAction: Optional[SuggestedAction] = None
    isPremium: bool
    paymentVerified: bool = False  # x402 verification status


class AgentRequest(BaseModel):
    prompt: str
    hasPaidX402: bool = False
    squadPlayerIds: List[str] = Field(default_factory=list, max_length=19)


class ChatMessage(BaseModel):
    id: str
    role: Literal['user', 'assistant']
    content: str
    isPremium: Optional[bool] = False
    suggestedAction: Optional[SuggestedAction] = None
    actionApplied: Optional[bool] = False


class CCTPRequest(BaseModel):
    walletAddress: str
    amount: int = 20
    sourceChain: str = 'Ethereum'


class CCTPResponse(BaseModel):
    success: bool
    newBudgetBonus: int
    txHash: str
    message: str
    simulated: bool = False  # Indicates if this is a realistic simulation


class TransferExecuteRequest(BaseModel):
    sellPlayerId: str
    buyPlayerId: str
    reasoning: str = Field(..., min_length=1, max_length=1000)
    squadPlayerIds: List[str] = Field(..., min_length=1, max_length=19)


class TransferExecuteResponse(BaseModel):
    success: bool
    txHash: str
    message: str
    mcpReceipt: Optional[dict] = None
    simulated: bool = False
