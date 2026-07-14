"""
Gemini LLM client with function-calling support for the Auto-Gaffer agent.
Includes fallback to rule-based logic when no API key is configured.
"""
import json
from typing import List, Optional

from google import genai
from google.genai import types

from ..config import settings
from ..models import AgentResponse, SuggestedAction
from . import skills
from .prompts import SYSTEM_PROMPT


class GeminiAgentClient:
    """Gemini LLM client with tool-calling for the Auto-Gaffer agent."""

    def __init__(self):
        self.client = None
        self.model = "gemini-2.0-flash"

        if settings.gemini_api_key:
            self.client = genai.Client(api_key=settings.gemini_api_key)
        else:
            print("Warning: GEMINI_API_KEY not configured. Falling back to rule-based logic.")

    def is_available(self) -> bool:
        """Check if the Gemini client is properly configured."""
        return self.client is not None

    def _build_tools(self, squad_player_ids: List[str], is_premium: bool) -> list:
        """
        Build tool functions with squad context captured via closures.
        The google-genai SDK auto-generates FunctionDeclarations from these.
        """
        from ..data import get_players
        from .skills import _normalize

        def search_player(name_query: str) -> dict:
            """Search for a player by name or surname. Returns player details including price, points, position, team, and premium stats.

            Args:
                name_query: Partial or full player name (e.g., "Mbappe", "Bellingham", "Kylian")
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

        def rank_position(position: str, top_n: int = 5) -> dict:
            """Get the top-ranked players at a specific position, sorted by points descending.

            Args:
                position: One of 'GK', 'DF', 'MF', 'FW'
                top_n: Number of top players to return (default 5)
            """
            players = get_players()
            filtered = [p for p in players if p.position == position and p.isAvailable]
            sorted_players = sorted(filtered, key=lambda p: p.points, reverse=True)
            return {
                "position": position,
                "count": len(sorted_players),
                "top_players": [p.model_dump() for p in sorted_players[:top_n]]
            }

        def analyze_squad() -> dict:
            """Analyze the user's current squad. Returns total points, budget, xG average, injury risks, and positional breakdown. No arguments needed - uses the current squad context."""
            return skills.analyze_squad(squad_player_ids)

        def suggest_transfer(target_position: Optional[str] = None) -> dict:
            """Suggest the best transfer (sell weakest, buy strongest available) for the current squad. Optionally target a specific position.

            Args:
                target_position: If provided, only suggest transfers for this position (GK, DF, MF, FW)
            """
            return skills.suggest_transfer(squad_player_ids, target_position)

        def validate_budget(max_budget: float = 100) -> dict:
            """Validate that the current squad fits within the budget limit.

            Args:
                max_budget: Maximum budget allowed (default 100M)
            """
            return skills.validate_budget(squad_player_ids, max_budget)

        def get_player_report(player_id: str) -> dict:
            """Get a detailed premium scouting report for a specific player including xG, injury risk, and scout notes.

            Args:
                player_id: The unique ID of the player
            """
            return skills.get_player_report(player_id)

        # Only expose premium tools if user has premium access
        all_tools = [search_player, rank_position, analyze_squad, validate_budget]
        if is_premium:
            all_tools.extend([suggest_transfer, get_player_report])

        return all_tools

    async def chat(
        self,
        prompt: str,
        squad_player_ids: List[str],
        is_premium: bool = False,
        x402_verified: bool = False
    ) -> AgentResponse:
        """
        Chat with the agent via Gemini tool-calling or rule-based fallback.
        """
        if not self.client:
            return self._rule_based_fallback(prompt, squad_player_ids, is_premium)

        try:
            access_level = "PREMIUM (x402 verified)" if is_premium else "FREE"
            system_instruction = (
                f"{SYSTEM_PROMPT}\n\n"
                f"CURRENT ACCESS LEVEL: {access_level}\n"
                f"CURRENT SQUAD PLAYER IDS: {json.dumps(squad_player_ids)}\n"
                f"Premium features (xG, injury risk, transfer suggestions) are "
                f"{'ENABLED' if is_premium else 'DISABLED - only give basic info and suggest upgrading'}."
            )

            tools = self._build_tools(squad_player_ids, is_premium)

            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    tools=tools,
                    temperature=0.7,
                    max_output_tokens=2048,
                ),
            )

            message = response.text if response.text else "I couldn't process your request, gaffer."

            # Check for transfer suggestions in the automatic function calling history
            suggested_action = None
            if is_premium:
                suggested_action = self._extract_transfer_action(response, squad_player_ids)

            return AgentResponse(
                message=message,
                suggestedAction=suggested_action,
                isPremium=is_premium,
                paymentVerified=x402_verified
            )

        except Exception as e:
            print(f"Gemini API error: {e}")
            err_str = str(e)
            warning = "⚠️ Not: Gemini API bağlantı hatası nedeniyle geçici olarak statik moda geçildi."
            if "RESOURCE_EXHAUSTED" in err_str or "quota" in err_str.lower() or "429" in err_str:
                warning = "⚠️ Not: Gemini API Kota Sınırına Ulaşıldı (429 Resource Exhausted). Lütfen Google AI Studio API anahtarınızın limitlerini kontrol edin veya bir süre bekleyin."
            elif "API_KEY_INVALID" in err_str or "api key" in err_str.lower():
                warning = "⚠️ Not: Geçersiz GEMINI_API_KEY. Lütfen backend/.env dosyasındaki API anahtarını kontrol edin."

            fallback_res = self._rule_based_fallback(prompt, squad_player_ids, is_premium)
            fallback_res.message = f"{warning}\n\n{fallback_res.message}"
            return fallback_res

    def _extract_transfer_action(self, response, squad_player_ids: List[str]) -> Optional[SuggestedAction]:
        """Extract a transfer suggestion from the Gemini response or run the tool directly."""
        # If Gemini already called suggest_transfer via automatic function calling,
        # we also run it ourselves to build the structured SuggestedAction
        transfer = skills.suggest_transfer(squad_player_ids)
        if 'sell_player' in transfer:
            return SuggestedAction(
                type='transfer',
                sellPlayerId=transfer['sell_player']['id'],
                buyPlayerId=transfer['buy_player']['id'],
                reasoning=transfer['reasoning']
            )
        return None

    def _rule_based_fallback(
        self,
        prompt: str,
        squad_player_ids: List[str],
        is_premium: bool
    ) -> AgentResponse:
        """Fallback to rule-based logic when Gemini is unavailable."""
        prompt_lower = prompt.lower()

        # Greetings
        if prompt_lower.startswith(('hi', 'hello', 'hey', 'sup', 'yo')):
            return AgentResponse(
                message=(
                    "Hey gaffer! I'm your Auto-Gaffer AI assistant (running in rule-based mode). "
                    "I can help you build your World Cup 2026 squad with tactical analysis, transfer "
                    "advice, and player comparisons. For premium features, please configure GEMINI_API_KEY."
                ),
                isPremium=False
            )

        # Squad analysis
        if any(kw in prompt_lower for kw in ['squad', 'team', 'lineup', 'analyse', 'analyze']):
            squad_analysis = skills.analyze_squad(squad_player_ids)

            if 'error' in squad_analysis:
                return AgentResponse(
                    message="Your squad is empty, gaffer. Head to the pitch board and start picking players!",
                    isPremium=False
                )

            msg = (
                f"📋 **Squad Overview**\n\n"
                f"Total Points: **{squad_analysis['total_points']}** | "
                f"Budget Used: **{squad_analysis['total_budget']}M**\n\n"
                f"Formation breakdown: "
                f"{squad_analysis['position_breakdown']['GK']} GK, "
                f"{squad_analysis['position_breakdown']['DF']} DF, "
                f"{squad_analysis['position_breakdown']['MF']} MF, "
                f"{squad_analysis['position_breakdown']['FW']} FW\n\n"
            )

            if is_premium:
                msg += f"Avg xG/game: **{squad_analysis['avg_xg_per_game']}**\n"
                if squad_analysis['high_injury_risk']:
                    msg += f"⚠️ **Injury Alert**: {', '.join(squad_analysis['high_injury_risk'])}\n"

                transfer = skills.suggest_transfer(squad_player_ids)
                if 'sell_player' in transfer:
                    suggested_action = SuggestedAction(
                        type='transfer',
                        sellPlayerId=transfer['sell_player']['id'],
                        buyPlayerId=transfer['buy_player']['id'],
                        reasoning=transfer['reasoning']
                    )
                    msg += f"\n🔄 **Recommended:**\n{transfer['reasoning']}"
                    return AgentResponse(
                        message=msg,
                        suggestedAction=suggested_action,
                        isPremium=True
                    )
            else:
                msg += "For deep analytics and transfer suggestions, unlock Premium via X402."

            return AgentResponse(message=msg, isPremium=False)

        # Player search
        found_player = skills.find_player_by_name(prompt)
        if found_player:
            msg = (
                f"⚽ **{found_player.name}** | {found_player.position} | {found_player.team}\n\n"
                f"Price: **{found_player.price}M** | Points: **{found_player.points}**\n"
            )
            if is_premium:
                msg += (
                    f"xG/game: **{found_player.premium_stats.xg_per_game}** | "
                    f"Injury Risk: **{found_player.premium_stats.injury_risk}**\n\n"
                    f"{found_player.premium_stats.scout_note}"
                )
            return AgentResponse(message=msg, isPremium=is_premium)

        # Position query
        position = skills.detect_position_from_prompt(prompt)
        if position:
            ranking = skills.rank_position(position, top_n=3)
            msg = f"📊 **Top {position}s**\n\n"
            for i, p in enumerate(ranking['top_players'], 1):
                msg += f"{i}. **{p['name']}** ({p['team']}) — {p['points']} pts, {p['price']}M\n"
            if is_premium:
                msg += "\n💡 *Scout notes and xG available for Premium.*"
            return AgentResponse(message=msg, isPremium=is_premium)

        # Transfer suggestion
        if any(kw in prompt_lower for kw in ['transfer', 'swap', 'replace', 'upgrade', 'improve', 'suggest', 'recommend']):
            transfer = skills.suggest_transfer(squad_player_ids)
            if 'sell_player' in transfer:
                suggested_action = SuggestedAction(
                    type='transfer',
                    sellPlayerId=transfer['sell_player']['id'],
                    buyPlayerId=transfer['buy_player']['id'],
                    reasoning=transfer['reasoning']
                )
                msg = f"🔓 **Transfer Recommendation**\n\n{transfer['reasoning']}"
                return AgentResponse(
                    message=msg,
                    suggestedAction=suggested_action,
                    isPremium=True
                )
            else:
                return AgentResponse(
                    message="Couldn't identify a clear upgrade. Your squad looks well-optimized!",
                    isPremium=is_premium
                )

        # Default
        return AgentResponse(
            message=(
                "Good question, gaffer. I can help with player analysis, squad composition, "
                "position rankings, and transfer strategy. Try asking about a specific player, "
                "position, or your squad."
            ),
            isPremium=False
        )


# Singleton instance
_agent_client: Optional[GeminiAgentClient] = None


def get_agent_client() -> GeminiAgentClient:
    """Get or create the singleton agent client."""
    global _agent_client
    if _agent_client is None:
        _agent_client = GeminiAgentClient()
    return _agent_client
