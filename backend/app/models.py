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
    source_status: Literal['verified', 'app_estimate'] = 'app_estimate'


class WorldCupStats(BaseModel):
    """Verified tournament stats, when the current source exposes them.

    Optional fields are intentional: a roster snapshot must not be presented
    as a fabricated live statistics feed.
    """

    appearances: Optional[int] = None
    starts: Optional[int] = None
    minutes: Optional[int] = None
    goals: Optional[int] = None
    assists: Optional[int] = None
    data_status: Literal['verified', 'not_available'] = 'not_available'
    source_url: Optional[str] = None
    updated_at: Optional[str] = None


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
    data_source: Optional[str] = None
    data_updated_at: Optional[str] = None
    source_url: Optional[str] = None
    roster_status: Optional[Literal['announced', 'confirmed', 'not_available']] = None
    availability_status: Optional[Literal['available', 'doubtful', 'injured', 'suspended', 'unknown']] = None
    world_cup_stats: Optional[WorldCupStats] = None

    class Config:
        populate_by_name = True


class SquadSlot(BaseModel):
    position: Literal['GK', 'DF', 'MF', 'FW']
    slotIndex: int
    player: Optional[Player] = None


class SuggestedAction(BaseModel):
    type: Literal['transfer', 'lineup']
    sellPlayerId: Optional[str] = None
    buyPlayerId: Optional[str] = None
    formation: Optional[Formation] = None
    startingPlayerIds: Optional[List[str]] = None
    benchPlayerIds: Optional[List[str]] = None
    budgetUsed: Optional[float] = None
    totalPoints: Optional[int] = None
    strategy: Optional[Literal['balanced', 'attacking', 'defensive']] = None
    reasoning: str


class AgentResponse(BaseModel):
    message: str
    suggestedAction: Optional[SuggestedAction] = None
    isPremium: bool
    paymentVerified: bool = False  # x402 verification status
    provider: Literal['gemini', 'fallback'] = 'fallback'
    model: Optional[str] = None


class AgentRequest(BaseModel):
    prompt: str
    hasPaidX402: bool = False
    squadPlayerIds: List[str] = Field(default_factory=list, max_length=19)
    formation: Formation = '4-3-3'


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


class LineupApplyRequest(BaseModel):
    formation: Formation
    startingPlayerIds: List[str] = Field(..., min_length=11, max_length=11)
    benchPlayerIds: List[str] = Field(default_factory=list, max_length=8)
    reasoning: str = Field(..., min_length=1, max_length=1000)


class LineupApplyResponse(BaseModel):
    success: bool
    message: str
    formation: Formation
    appliedPlayerIds: List[str]
    mcpReceipt: Optional[dict] = None
    simulated: bool = False
