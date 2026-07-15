"""
Auto-Gaffer agent skills as Gemini function-calling tools.
These are the skills the LLM can invoke to answer user queries.
"""
import unicodedata
from itertools import combinations
from typing import Dict, List, Optional, Literal
from functools import wraps

from google import genai
from google.genai import types

from ..data import get_players
from ..models import Player, SquadSlot, SuggestedAction


def _normalize(text: str) -> str:
    """Normalize text for matching: lowercase + strip accents."""
    nfkd = unicodedata.normalize('NFD', text.lower())
    return ''.join(c for c in nfkd if not unicodedata.combining(c))


def extract_player_ids_from_prompt(prompt: str) -> List[str]:
    """Extract unambiguous catalog players explicitly mentioned by the user."""
    query = _normalize(prompt)
    matches: List[str] = []
    for player in get_players():
        full_name = _normalize(player.name)
        surname = _normalize(player.name.split()[-1])
        if full_name in query or (len(surname) >= 4 and surname in query):
            matches.append(player.id)
    return list(dict.fromkeys(matches))


def extract_position_team_preferences(prompt: str) -> Dict[str, List[str]]:
    """Read nearby team/position phrases such as 'Spain defence' or 'France midfield'."""
    query = _normalize(prompt)
    team_aliases = {
        'argentina': 'Argentina',
        'arjantin': 'Argentina',
        'albiceleste': 'Argentina',
        'england': 'England',
        'ingiltere': 'England',
        'three lions': 'England',
        'france': 'France',
        'fransa': 'France',
        'les bleus': 'France',
        'spain': 'Spain',
        'ispanya': 'Spain',
        'la roja': 'Spain',
    }
    position_terms = {
        'DF': ('defans', 'savunma', 'defence', 'defense', 'back line'),
        'MF': ('orta saha', 'midfield', 'middle'),
        'FW': ('hucum', 'forvet', 'attack', 'forward'),
        'GK': ('kaleci', 'goalkeeper'),
    }
    preferences: Dict[str, List[str]] = {}
    position_indexes = [
        (position, query.find(term))
        for position, terms in position_terms.items()
        for term in terms
        if query.find(term) >= 0
    ]
    for alias, team in team_aliases.items():
        alias_norm = _normalize(alias)
        search_from = 0
        while True:
            alias_index = query.find(alias_norm, search_from)
            if alias_index < 0:
                break
            search_from = alias_index + len(alias_norm)
            if not position_indexes:
                continue
            nearest_position, nearest_index = min(
                position_indexes,
                key=lambda item: abs(alias_index - item[1]),
            )
            if abs(alias_index - nearest_index) <= 45:
                preferences.setdefault(nearest_position, [])
                if team not in preferences[nearest_position]:
                    preferences[nearest_position].append(team)
    return preferences


def _verified_contribution_score(player: Player) -> float:
    """Score only verified World Cup goals and assists, never app estimates."""
    stats = player.world_cup_stats
    if not stats or stats.data_status != 'verified':
        return 0.0
    return (stats.goals or 0) * 4.0 + (stats.assists or 0) * 3.0


def _lineup_player_score(
    player: Player,
    strategy: str,
    current_squad_ids: set[str],
) -> float:
    """Create a transparent optimization score from catalog and verified data."""
    score = float(player.points)
    verified_contribution = _verified_contribution_score(player)

    if strategy == 'attacking':
        # Verified goals/assists lead the decision. Price is only an app
        # fantasy proxy that breaks ties when the snapshot lacks a stat.
        score += verified_contribution * 2.0
        score += player.price * (
            3.0 if player.position == 'FW'
            else 0.5 if player.position == 'MF'
            else 0.0
        )
    elif strategy == 'defensive':
        score += verified_contribution * 0.5
        score += player.points * (0.08 if player.position in {'GK', 'DF'} else 0.0)
    else:
        score += verified_contribution * 0.5

    # A small novelty bonus prevents every new recommendation from repeating
    # the current XI when similarly rated alternatives exist.
    if player.id not in current_squad_ids:
        score += 1.5
    return score


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


@gemini_tool
def suggest_lineup(
    formation: Literal['4-3-3', '4-4-2', '3-5-2', '4-2-3-1', '5-3-2'] = '4-3-3',
    match_context: str = '',
    required_player_ids: Optional[List[str]] = None,
    strategy: Literal['balanced', 'attacking', 'defensive'] = 'balanced',
    position_team_preferences: Optional[Dict[str, List[str]]] = None,
    current_squad_player_ids: Optional[List[str]] = None,
) -> dict:
    """Build a budget-valid World Cup 2026 starting XI with stable player IDs.

    The result is a proposal only. It does not mutate the user's squad. When
    two team names are present in ``match_context``, candidates are restricted
    to those teams; otherwise the four current semi-finalist rosters are used.
    Explicitly requested players are always included when they are available.
    ``position_team_preferences`` can focus a position on a team, while
    ``strategy`` uses verified World Cup contributions and app fantasy values
    to balance attacking or defensive priorities within the same 100M budget.
    """
    formation_counts = {
        '4-3-3': {'GK': 1, 'DF': 4, 'MF': 3, 'FW': 3},
        '4-4-2': {'GK': 1, 'DF': 4, 'MF': 4, 'FW': 2},
        '3-5-2': {'GK': 1, 'DF': 3, 'MF': 5, 'FW': 2},
        '4-2-3-1': {'GK': 1, 'DF': 4, 'MF': 5, 'FW': 1},
        '5-3-2': {'GK': 1, 'DF': 5, 'MF': 3, 'FW': 2},
    }
    if formation not in formation_counts:
        return {'error': f'Unsupported formation: {formation}'}
    if strategy not in {'balanced', 'attacking', 'defensive'}:
        return {'error': f'Unsupported lineup strategy: {strategy}'}

    context = _normalize(match_context)
    team_aliases = {
        'argentina': 'Argentina',
        'arjantin': 'Argentina',
        'albiceleste': 'Argentina',
        'england': 'England',
        'ingiltere': 'England',
        'three lions': 'England',
        'france': 'France',
        'fransa': 'France',
        'les bleus': 'France',
        'spain': 'Spain',
        'ispanya': 'Spain',
        'la roja': 'Spain',
    }
    all_players = get_players()
    catalog = {player.id: player for player in all_players}
    required_ids = list(dict.fromkeys(required_player_ids or []))
    required_players = [catalog[player_id] for player_id in required_ids if player_id in catalog]
    missing_required_ids = [player_id for player_id in required_ids if player_id not in catalog]
    unavailable_required = [
        player.name for player in required_players if not player.isAvailable
    ]
    if missing_required_ids:
        return {'error': f'Unknown required player IDs: {", ".join(missing_required_ids)}'}
    if unavailable_required:
        return {
            'error': (
                'Requested players are not available in the current World Cup snapshot: '
                + ', '.join(unavailable_required)
            )
        }

    mentioned_teams = {
        team
        for alias, team in team_aliases.items()
        if _normalize(alias) in context
    }
    teams = mentioned_teams if len(mentioned_teams) >= 2 else {'Argentina', 'England', 'France', 'Spain'}
    # An explicit player request has priority over an inferred match filter.
    teams.update(player.team for player in required_players)

    required_by_position = {
        position: [player for player in required_players if player.position == position]
        for position in ['GK', 'DF', 'MF', 'FW']
    }
    preferences = position_team_preferences or {}
    current_squad_ids = set(current_squad_player_ids or [])

    candidates_by_position = {}
    for position, count in formation_counts[formation].items():
        candidates = [
            player for player in all_players
            if player.position == position
            and player.team in teams
            and player.isAvailable
        ]
        preferred_teams = set(preferences.get(position, []))
        preferred_candidates = [
            player for player in candidates if player.team in preferred_teams
        ]
        # A positional team preference is strict when the requested team has
        # enough available players; otherwise it remains a best-effort bias.
        if len(preferred_candidates) >= count:
            candidates = preferred_candidates

        # A compact candidate set keeps the combinatorial budget search quick.
        # Required and position-preferred players are placed first so the cap
        # cannot silently discard an explicit user constraint.
        ranked_candidates = sorted(
            candidates,
            key=lambda player: (
                _lineup_player_score(player, strategy, current_squad_ids),
                player.points,
                -player.price,
            ),
            reverse=True,
        )
        required_candidates = required_by_position[position]
        required_candidate_ids = {player.id for player in required_candidates}
        preferred_candidate_ids = {
            player.id for player in preferred_candidates
        }
        prioritized_candidates = (
            required_candidates
            + [player for player in preferred_candidates if player.id not in required_candidate_ids]
            + [
                player for player in ranked_candidates
                if player.id not in required_candidate_ids
                and player.id not in preferred_candidate_ids
            ]
        )
        unique_candidates = list({player.id: player for player in prioritized_candidates}.values())
        candidates_by_position[position] = (
            unique_candidates[:14]
        )
        if len(candidates_by_position[position]) < count:
            return {'error': f'Not enough available {position} players for {formation}'}

    # Dynamic programming over position groups finds the highest-rated XI that
    # still fits the app's authoritative 100M default budget.
    # cost -> (optimization score, actual points, players)
    states = {0: (0, 0, [])}
    for position, count in formation_counts[formation].items():
        options = []
        candidates = candidates_by_position[position]
        required_position_ids = {player.id for player in required_by_position[position]}
        for group in combinations(candidates, count):
            group_ids = {player.id for player in group}
            if not required_position_ids.issubset(group_ids):
                continue
            cost = round(sum(player.price for player in group) * 10)
            actual_points = sum(player.points for player in group)
            optimization_score = sum(
                _lineup_player_score(player, strategy, current_squad_ids)
                for player in group
            )
            options.append((cost, optimization_score, actual_points, list(group)))

        next_states = {}
        for current_cost, (current_score, current_points, current_players) in states.items():
            for option_cost, option_score, option_points, option_players in options:
                total_cost = current_cost + option_cost
                if total_cost > 1000:
                    continue
                total_score = current_score + option_score
                total_points = current_points + option_points
                previous = next_states.get(total_cost)
                if previous is None or total_score > previous[0]:
                    next_states[total_cost] = (
                        total_score,
                        total_points,
                        current_players + option_players,
                    )
        states = next_states

    if not states:
        return {'error': 'No budget-valid lineup could be built'}

    best_cost, (best_score, best_points, lineup_players) = max(
        states.items(), key=lambda item: (item[1][0], -item[0])
    )
    lineup_by_position = {
        position: [player for player in lineup_players if player.position == position]
        for position in ['GK', 'DF', 'MF', 'FW']
    }
    lineup_ids = [
        player.id
        for position in ['GK', 'DF', 'MF', 'FW']
        for player in lineup_by_position[position]
    ]

    return {
        'formation': formation,
        'teams_considered': sorted(teams),
        'starting_player_ids': lineup_ids,
        'starting_players': [player.model_dump() for player in lineup_players],
        'budget_used': round(best_cost / 10, 1),
        'total_points': best_points,
        'optimization_score': best_score,
        'required_player_ids': required_ids,
        'strategy': strategy,
        'reasoning': (
            f'{formation} için mevcut FIFA 2026 kadro snapshotından, '
            f'{", ".join(sorted(teams))} takımları arasından bütçe geçerli '
            f'11 oyuncu seçildi. Bu bir tahmini fantasy XI; resmi ilk 11 değildir.'
        ),
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
