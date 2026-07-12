"""
Auto-Gaffer agent skills as Gemini function-calling tools.
These are the skills the LLM can invoke to answer user queries.
"""
import unicodedata
from typing import List, Optional, Literal
from functools import wraps

from google import genai
from google.genai import types

from ..data import get_players
from ..models import Player, SquadSlot, SuggestedAction


def _normalize(text: str) -> str:
    """Normalize text for matching: lowercase + strip accents."""
    nfkd = unicodedata.normalize('NFD', text.lower())
    return ''.join(c for c in nfkd if not unicodedata.combining(c))


# Helper to convert Python functions to Gemini tool definitions
def gemini_tool(func):
    """Decorator to mark a function as a Gemini tool."""
    func.is_gemini_tool = True
    return func


# ============================================================================
# AGENT SKILLS (Function Calling Tools)
# ============================================================================


@gemini_tool
def search_player(name_query: str) -> dict:
    """
    Search for a player by name or surname. Returns player details including price, points, position, team, and premium stats.

    Args:
        name_query: Partial or full player name (e.g., "Mbappe", "Bellingham", "Kylian")

    Returns:
        dict with player details or None if not found
    """
    players = get_players()
    query_norm = _normalize(name_query)
    
    for player in players:
        surname_norm = _normalize(player.name.split(' ')[-1])
        full_norm = _normalize(player.name)
        if (query_norm in full_norm or full_norm in query_norm or
            query_norm in surname_norm or surname_norm in query_norm):
            return player.model_dump()
    
    return {"error": f"Player '{name_query}' not found"}


@gemini_tool
def rank_position(position: Literal['GK', 'DF', 'MF', 'FW'], top_n: int = 3) -> dict:
    """
    Get the top-ranked players at a specific position, sorted by points descending.

    Args:
        position: One of 'GK', 'DF', 'MF', 'FW'
        top_n: Number of top players to return (default 3)

    Returns:
        dict with list of top players at this position
    """
    players = get_players()
    filtered = [p for p in players if p.position == position and p.isAvailable]
    sorted_players = sorted(filtered, key=lambda p: p.points, reverse=True)
    
    return {
        "position": position,
        "count": len(sorted_players),
        "top_players": [p.model_dump() for p in sorted_players[:top_n]]
    }


@gemini_tool
def analyze_squad(squad_player_ids: List[str]) -> dict:
    """
    Analyze a squad given the player IDs. Returns total points, budget, xG average, injury risks, and positional breakdown.

    Args:
        squad_player_ids: List of player IDs in the current squad

    Returns:
        dict with squad analysis including points, budget, xG, injury risks, and position counts
    """
    players = get_players()
    squad_players = []
    
    for player in players:
        if player.id in squad_player_ids:
            squad_players.append(player)
    
    if not squad_players:
        return {"error": "Squad is empty", "squad_players": []}
    
    # Calculate metrics
    total_points = sum(p.points for p in squad_players)
    total_budget = sum(p.price for p in squad_players)
    avg_xg = sum(p.premium_stats.xg_per_game for p in squad_players) / len(squad_players)
    
    # Injury risks
    high_risk = [p.name for p in squad_players if p.premium_stats.injury_risk == 'High']
    medium_risk = [p.name for p in squad_players if p.premium_stats.injury_risk == 'Medium']
    
    # Position counts
    pos_counts = {'GK': 0, 'DF': 0, 'MF': 0, 'FW': 0}
    for player in squad_players:
        pos_counts[player.position] += 1
    
    return {
        "total_points": total_points,
        "total_budget": total_budget,
        "avg_xg_per_game": round(avg_xg, 3),
        "squad_size": len(squad_players),
        "position_breakdown": pos_counts,
        "high_injury_risk": high_risk,
        "medium_injury_risk": medium_risk,
        "players": [p.model_dump() for p in squad_players]
    }


@gemini_tool
def suggest_transfer(squad_player_ids: List[str], target_position: Optional[Literal['GK', 'DF', 'MF', 'FW']] = None) -> dict:
    """
    Suggest the best transfer (sell weakest, buy strongest available) for a squad. Optionally target a specific position.

    Args:
        squad_player_ids: List of player IDs in the current squad
        target_position: If provided, only suggest transfers for this position

    Returns:
        dict with sell player, buy player, and reasoning
    """
    players = get_players()
    squad_players = [p for p in players if p.id in squad_player_ids]
    available_players = [p for p in players if p.isAvailable and p.id not in squad_player_ids]
    
    if not squad_players:
        return {"error": "Cannot suggest transfer: squad is empty"}
    
    if not available_players:
        return {"error": "Cannot suggest transfer: no available players"}
    
    # Filter by position if specified
    if target_position:
        candidates = [p for p in squad_players if p.position == target_position]
        if not candidates:
            return {"error": f"No players in squad at position {target_position}"}
        replacements = [p for p in available_players if p.position == target_position]
    else:
        candidates = squad_players
        replacements = available_players
    
    if not replacements:
        return {"error": f"No available replacements for position(s)"}
    
    # Find weakest in squad (by points)
    weakest = min(candidates, key=lambda p: p.points)
    
    # Find best available replacement at same position
    position_replacements = [p for p in replacements if p.position == weakest.position]
    if not position_replacements:
        return {"error": f"No available replacements for position {weakest.position}"}
    
    best_replacement = max(position_replacements, key=lambda p: p.points)
    
    # Only suggest if replacement is actually better
    if best_replacement.points <= weakest.points:
        return {"message": "Squad is already optimized - no clear upgrade available"}
    
    price_diff = best_replacement.price - weakest.price
    xg_diff = best_replacement.premium_stats.xg_per_game - weakest.premium_stats.xg_per_game
    
    price_diff_text = (
        f"+{price_diff}M" if price_diff > 0 else
        f"{price_diff}M (saves {-price_diff}M)" if price_diff < 0 else
        "like-for-like price"
    )
    
    return {
        "sell_player": weakest.model_dump(),
        "buy_player": best_replacement.model_dump(),
        "points_upgrade": best_replacement.points - weakest.points,
        "price_change": price_diff,
        "xg_improvement": round(xg_diff, 2),
        "reasoning": (
            f"Sell {weakest.name} ({weakest.points} pts, {weakest.price}M) → "
            f"Buy {best_replacement.name} ({best_replacement.points} pts, {best_replacement.price}M). "
            f"+{best_replacement.points - weakest.points} points upgrade. "
            f"Price: {price_diff_text}. "
            f"xG improvement: {round(xg_diff, 2)} per game. "
            f"{best_replacement.premium_stats.scout_note}"
        )
    }


@gemini_tool
def validate_budget(squad_player_ids: List[str], max_budget: float = 100) -> dict:
    """
    Validate that a squad fits within the budget limit.

    Args:
        squad_player_ids: List of player IDs in the squad
        max_budget: Maximum budget allowed (default 100M)

    Returns:
        dict with total, remaining, and validity status
    """
    players = get_players()
    squad_players = [p for p in players if p.id in squad_player_ids]
    
    total = sum(p.price for p in squad_players)
    remaining = max_budget - total
    
    return {
        "total": round(total, 1),
        "remaining": round(remaining, 1),
        "max_budget": max_budget,
        "is_valid": total <= max_budget
    }


@gemini_tool
def get_player_report(player_id: str) -> dict:
    """
    Get a detailed premium scouting report for a specific player including xG, injury risk, and scout notes.

    Args:
        player_id: The unique ID of the player

    Returns:
        dict with full player details and comparison to alternatives
    """
    players = get_players()
    player = next((p for p in players if p.id == player_id), None)
    
    if not player:
        return {"error": f"Player with ID '{player_id}' not found"}
    
    # Find positional alternatives
    alternatives = [
        p for p in players 
        if p.position == player.position and p.id != player.id and p.isAvailable
    ]
    alternatives_sorted = sorted(alternatives, key=lambda p: p.points, reverse=True)[:3]
    
    return {
        "player": player.model_dump(),
        "position_rank": (
            sorted([p for p in players if p.position == player.position and p.isAvailable], 
                   key=lambda p: p.points, reverse=True).index(player) + 1
            if player.isAvailable else "N/A"
        ),
        "top_alternatives": [p.model_dump() for p in alternatives_sorted],
        "is_injured_risk_high": player.premium_stats.injury_risk == 'High',
        "xg_percentile": None,  # Could calculate if needed
    }


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_all_tools() -> List[types.FunctionDeclaration]:
    """Get all agent skills as Gemini FunctionDeclarations."""
    tools = [
        search_player,
        rank_position,
        analyze_squad,
        suggest_transfer,
        validate_budget,
        get_player_report,
    ]
    
    function_declarations = []
    for tool in tools:
        # Convert function to Gemini FunctionDeclaration
        # This is a simplified conversion - in production you'd parse the docstring more carefully
        sig = tool.__name__
        desc = tool.__doc__ or ""
        function_declarations.append(
            types.FunctionDeclaration(
                name=sig,
                description=desc,
                parameters={
                    "type": "object",
                    "properties": {},  # Could parse from type hints
                }
            )
        )
    
    return function_declarations


def find_player_by_name(query: str) -> Optional[Player]:
    """Find a player by name (not a tool, used internally)."""
    players = get_players()
    query_norm = _normalize(query)
    
    for player in players:
        surname_norm = _normalize(player.name.split(' ')[-1])
        full_norm = _normalize(player.name)
        if (full_norm in query_norm or surname_norm in query_norm):
            return player
    return None


def find_player_by_id(player_id: str) -> Optional[Player]:
    """Find a player by ID."""
    players = get_players()
    return next((p for p in players if p.id == player_id), None)


def find_players_by_position(position: str) -> List[Player]:
    """Find all available players at a position."""
    players = get_players()
    return [p for p in players if p.position == position and p.isAvailable]


def detect_position_from_prompt(prompt: str) -> Optional[str]:
    """Detect if prompt mentions a specific position."""
    p_lower = prompt.lower()
    if any(word in p_lower for word in ['goalkeeper', ' gk', 'keeper']):
        return 'GK'
    if any(word in p_lower for word in ['defender', 'defense', ' df', 'backline', 'centre-back', 'fullback', 'right-back', 'left-back']):
        return 'DF'
    if any(word in p_lower for word in ['midfielder', 'midfield', ' mf', 'central mid', 'box-to-box']):
        return 'MF'
    if any(word in p_lower for word in ['forward', 'striker', ' fw', 'attacker', 'winger']):
        return 'FW'
    return None