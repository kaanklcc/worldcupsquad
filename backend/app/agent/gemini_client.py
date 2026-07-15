"""
Gemini LLM client with function-calling support for the Auto-Gaffer agent.
Includes fallback to rule-based logic when no API key is configured.
"""
import json
import asyncio
from datetime import datetime, timezone
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
        self.model = settings.gemini_model

        if settings.gemini_api_key:
            self.client = genai.Client(api_key=settings.gemini_api_key)
        else:
            print("Warning: GEMINI_API_KEY not configured. Falling back to rule-based logic.")

    def is_available(self) -> bool:
        """Check if the Gemini client is properly configured."""
        return self.client is not None

    def _build_tools(
        self,
        squad_player_ids: List[str],
        is_premium: bool,
        current_formation: str = '4-3-3',
        max_budget: float = 100,
        allow_lineup: bool = False,
        allow_transfer: bool = False,
    ) -> list:
        """
        Build tool functions with squad context captured via closures.
        The google-genai SDK auto-generates FunctionDeclarations from these.
        """
        from ..data import get_players, get_world_cup_snapshot
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
            return skills.suggest_transfer(squad_player_ids, target_position, max_budget)

        def suggest_player_replacement(sell_player_id: str) -> dict:
            """Suggest one same-position replacement for a player the manager explicitly named."""
            return skills.suggest_player_replacement(squad_player_ids, sell_player_id, max_budget)

        def validate_budget() -> dict:
            """Validate the current squad against the authenticated manager's server-side budget."""
            return skills.validate_budget(squad_player_ids, max_budget)

        def get_current_world_cup_data(topic: str = "") -> dict:
            """Return the dated FIFA World Cup 2026 roster and semifinal fixture snapshot.

            Args:
                topic: Optional team, player, match, date or venue keyword to filter fixtures.
            """
            return get_world_cup_snapshot(topic)

        def propose_lineup(
            formation: str = current_formation,
            match_context: str = "",
            required_player_ids: Optional[List[str]] = None,
            strategy: str = "balanced",
            position_team_preferences: Optional[dict] = None,
        ) -> dict:
            """Propose a budget-valid starting XI using stable catalog player IDs.

            Args:
                formation: One of 4-3-3, 4-4-2, 3-5-2, 4-2-3-1 or 5-3-2.
                match_context: Match or tactical context such as 'England vs Argentina'.
                required_player_ids: Player IDs explicitly requested by the user.
                strategy: 'balanced', 'attacking' or 'defensive'.
                position_team_preferences: Optional position-to-team preferences, e.g. {'DF': ['Spain']}.
            """
            return skills.suggest_lineup(
                formation,
                match_context,
                required_player_ids=required_player_ids,
                strategy=strategy,
                position_team_preferences=position_team_preferences,
                current_squad_player_ids=squad_player_ids,
                max_budget=max_budget,
            )

        def get_player_report(player_id: str) -> dict:
            """Get a detailed premium scouting report for a specific player including xG, injury risk, and scout notes.

            Args:
                player_id: The unique ID of the player
            """
            return skills.get_player_report(player_id)

        # Only expose premium tools if user has premium access
        all_tools = [
            search_player,
            rank_position,
            analyze_squad,
            validate_budget,
            get_current_world_cup_data,
        ]
        if allow_lineup:
            all_tools.append(propose_lineup)
        if is_premium:
            all_tools.append(get_player_report)
            if allow_transfer:
                all_tools.extend([suggest_transfer, suggest_player_replacement])

        return all_tools

    @staticmethod
    def _is_retryable_model_error(error: Exception) -> bool:
        """Identify transient/provider model errors without hiding auth errors."""
        error_text = str(error).upper()
        return any(marker in error_text for marker in (
            '503', 'UNAVAILABLE', '429', 'RESOURCE_EXHAUSTED',
            '500', 'INTERNAL', '504', 'DEADLINE_EXCEEDED',
            '404', 'NOT_FOUND',
        ))

    async def _generate_with_failover(self, prompt: str, system_instruction: str, tools: list):
        """Call Gemini with a short retry and a supported model fallback.

        A provider-side 503 must not force the whole product into rule-based
        mode when another model exposed by the same API key is healthy.
        """
        candidates = []
        for model in (self.model, 'gemini-3.1-flash-lite', 'gemini-flash-lite-latest'):
            if model and model not in candidates:
                candidates.append(model)

        last_error: Optional[Exception] = None
        for model in candidates:
            for attempt in range(2):
                try:
                    response = await asyncio.to_thread(
                        self.client.models.generate_content,
                        model=model,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            system_instruction=system_instruction,
                            tools=tools,
                            temperature=0.7,
                            max_output_tokens=2048,
                        ),
                    )
                    if model != self.model:
                        print(f"Gemini model failover succeeded with {model}")
                    return response
                except Exception as error:
                    last_error = error
                    if not self._is_retryable_model_error(error):
                        break
                    if attempt == 0:
                        await asyncio.sleep(1.0)

        if last_error:
            raise last_error
        raise RuntimeError('No Gemini model candidate is configured')

    async def chat(
        self,
        prompt: str,
        squad_player_ids: List[str],
        is_premium: bool = False,
        x402_verified: bool = False,
        formation: str = '4-3-3',
        max_budget: float = 100,
        analysis_mode: bool = False,
    ) -> AgentResponse:
        """
        Chat with the agent via Gemini tool-calling or rule-based fallback.
        """
        if not self.client:
            return self._rule_based_fallback(
                prompt,
                squad_player_ids,
                is_premium,
                formation,
                max_budget,
                analysis_mode,
            )

        try:
            access_level = "ENTITLED (active membership or x402 Match Pass)" if is_premium else "LOCKED"
            intent = 'deep_analysis' if analysis_mode else self._classify_intent(prompt, squad_player_ids)
            from ..data import get_data_metadata
            data_snapshot = get_data_metadata()
            system_instruction = (
                f"{SYSTEM_PROMPT}\n\n"
                f"SERVER REQUEST TIME (UTC): {datetime.now(timezone.utc).isoformat()}\n"
                f"CURRENT WORLD CUP DATA SNAPSHOT: {json.dumps(data_snapshot, ensure_ascii=False)}\n"
                f"CURRENT UI FORMATION: {formation}\n"
                f"AUTHORITATIVE MANAGER BUDGET: {max_budget:g}M USDC\n"
                f"CURRENT ACCESS LEVEL: {access_level}\n"
                f"X402 RECEIPT VERIFIED FOR THIS ACCESS: {x402_verified}\n"
                f"CURRENT SQUAD PLAYER IDS: {json.dumps(squad_player_ids)}\n"
                f"REQUEST INTENT: {intent}. A lineup tool is available only for an explicit full-XI request. "
                f"For conversation, match analysis, winner questions, or general player advice: answer the question, "
                f"offer options in prose, and do not output a complete XI or an executable action. "
                f"For targeted_transfer: discuss only the named player replacement, never rebuild the whole XI. "
                f"For deep_analysis: provide a detailed diagnostic and at most one optional transfer card; never create a full XI.\n"
                f"Premium features (xG, injury risk, transfer suggestions) are "
                f"{'ENABLED' if is_premium else 'DISABLED - only give basic info and suggest upgrading'}."
            )

            tools = self._build_tools(
                squad_player_ids,
                is_premium,
                formation,
                max_budget,
                allow_lineup=intent == 'lineup',
                allow_transfer=intent in {'targeted_transfer', 'transfer', 'deep_analysis'},
            )

            response = await self._generate_with_failover(prompt, system_instruction, tools)

            message = response.text if response.text else "I couldn't process your request, gaffer."

            # Check for transfer suggestions in the automatic function calling history
            suggested_action = None
            if intent == 'targeted_transfer':
                suggested_action = self._extract_targeted_transfer_action(prompt, squad_player_ids, max_budget)
            elif intent == 'lineup':
                suggested_action = self._extract_lineup_action(
                    prompt,
                    squad_player_ids,
                    formation,
                    max_budget,
                )
            elif intent in {'transfer', 'deep_analysis'} and is_premium:
                suggested_action = self._extract_transfer_action(prompt, squad_player_ids, max_budget)

            # The structured action is authoritative. Returning Gemini's raw
            # lineup prose here could show different names/formation than the
            # IDs that the pitch will actually apply.
            if suggested_action and suggested_action.type == 'lineup':
                message = self._format_lineup_message(suggested_action)

            return AgentResponse(
                message=message,
                suggestedAction=suggested_action,
                isPremium=is_premium,
                paymentVerified=x402_verified,
                provider='gemini',
                model=self.model,
            )

        except Exception as e:
            print(f"Gemini API error: {e}")
            err_str = str(e)
            warning = "⚠️ Not: Gemini API bağlantı hatası nedeniyle geçici olarak statik moda geçildi."
            if "RESOURCE_EXHAUSTED" in err_str or "quota" in err_str.lower() or "429" in err_str:
                warning = "⚠️ Not: Gemini API Kota Sınırına Ulaşıldı (429 Resource Exhausted). Lütfen Google AI Studio API anahtarınızın limitlerini kontrol edin veya bir süre bekleyin."
            elif "API_KEY_INVALID" in err_str or "api key" in err_str.lower():
                warning = "⚠️ Not: Geçersiz GEMINI_API_KEY. Lütfen backend/.env dosyasındaki API anahtarını kontrol edin."

            fallback_res = self._rule_based_fallback(
                prompt,
                squad_player_ids,
                is_premium,
                formation,
                max_budget,
                analysis_mode,
            )
            fallback_res.message = f"{warning}\n\n{fallback_res.message}"
            fallback_res.provider = 'fallback'
            fallback_res.model = None
            return fallback_res

    def _format_lineup_message(self, action: SuggestedAction) -> str:
        """Render the exact structured XI shown in the UI proposal card."""
        catalog = {player.id: player for player in skills.get_players()}
        selected = [
            catalog[player_id]
            for player_id in (action.startingPlayerIds or [])
            if player_id in catalog
        ]
        grouped = {
            position: [player.name for player in selected if player.position == position]
            for position in ('GK', 'DF', 'MF', 'FW')
        }
        budget = (
            f"{action.budgetUsed:.1f}M / {(action.maxBudget or 100):g}M"
            if action.budgetUsed is not None else 'validated by backend'
        )
        points = (
            f"{action.totalPoints} fantasy points"
            if action.totalPoints is not None else 'catalog ranking'
        )
        return (
            f"⚽ **{action.formation} World Cup 2026 kadro önerisi**\n\n"
            f"**GK:** {', '.join(grouped['GK'])}\n"
            f"**DF:** {', '.join(grouped['DF'])}\n"
            f"**MF:** {', '.join(grouped['MF'])}\n"
            f"**FW:** {', '.join(grouped['FW'])}\n\n"
            f"**Bütçe:** {budget} · **Skor:** {points}\n"
            f"{action.reasoning}\n\n"
            "Bu kadro resmi ilk 11 değil; mevcut FIFA World Cup 2026 snapshotı "
            "ve uygulama fantasy skorlarıyla oluşturulmuş bütçe geçerli bir öneridir. "
            "Kadroyu sahaya yerleştireyim mi?"
        )

    def _extract_transfer_action(
        self,
        prompt: str,
        squad_player_ids: List[str],
        max_budget: float = 100,
    ) -> Optional[SuggestedAction]:
        """Build a structured, budget-valid transfer for the requested position."""
        target_position = skills.detect_position_from_prompt(prompt)
        transfer = skills.suggest_transfer(squad_player_ids, target_position, max_budget)
        if 'sell_player' in transfer:
            return SuggestedAction(
                type='transfer',
                sellPlayerId=transfer['sell_player']['id'],
                buyPlayerId=transfer['buy_player']['id'],
                reasoning=transfer['reasoning']
            )
        return None

    def _extract_targeted_transfer_action(
        self,
        prompt: str,
        squad_player_ids: List[str],
        max_budget: float = 100,
    ) -> Optional[SuggestedAction]:
        """Return one player-for-player action for an explicitly named squad member."""
        named_ids = skills.extract_player_ids_from_prompt(prompt)
        named_in_squad = [player_id for player_id in named_ids if player_id in squad_player_ids]
        if len(named_in_squad) != 1:
            return None
        replacement = skills.suggest_player_replacement(
            squad_player_ids,
            named_in_squad[0],
            max_budget,
        )
        if 'sell_player' not in replacement:
            return None
        return SuggestedAction(
            type='transfer',
            sellPlayerId=replacement['sell_player']['id'],
            buyPlayerId=replacement['buy_player']['id'],
            reasoning=replacement['reasoning'],
        )

    @staticmethod
    def _classify_intent(prompt: str, squad_player_ids: List[str]) -> str:
        """Keep normal football conversation separate from mutating proposals."""
        normalized = skills._normalize(prompt)
        named_in_squad = [
            player_id for player_id in skills.extract_player_ids_from_prompt(prompt)
            if player_id in squad_player_ids
        ]
        replacement_terms = (
            'yerine', 'degistir', 'cikar', 'kaldir', 'cikart', 'sevmiyorum',
            'replace', 'swap', 'change', 'remove',
        )
        if len(named_in_squad) == 1 and any(term in normalized for term in replacement_terms):
            return 'targeted_transfer'
        if GeminiAgentClient._is_lineup_request(prompt):
            return 'lineup'
        transfer_terms = (
            'transfer yap', 'transfer oner', 'transfer öner', 'tekli transfer',
            'kadrodan degistir', 'oyuncu degistir', 'uygula transfer',
            'make a transfer', 'execute transfer',
        )
        if any(term in normalized for term in transfer_terms):
            return 'transfer'
        return 'conversation'

    @staticmethod
    def _is_lineup_request(prompt: str) -> bool:
        """Require an explicit full-XI/squad-building request for a lineup action."""
        prompt_lower = skills._normalize(prompt)
        lineup_terms = (
            'lineup', 'starting xi', 'starting eleven', 'first eleven',
            'ilk 11', 'ilk on bir', 'tam kadro', 'full squad',
            'kadro kur', 'kadro olustur', 'kadro oluştur', 'kadro oner', 'kadro öner',
            'dizilis kur', 'diziliş kur', 'starting team', 'build a squad',
            'sahaya yerlestir', 'sahaya yerleştir', 'apply lineup',
        )
        if any(term in prompt_lower for term in lineup_terms):
            return True
        tactical_terms = (
            'defans', 'savunma', 'orta saha', 'hucum', 'forvet',
            'goalkeeper', 'defender', 'midfielder', 'forward',
        )
        action_terms = (
            'kur', 'olustur', 'yerlestir',
            'build', 'create', 'place',
        )
        return (
            any(term in prompt_lower for term in tactical_terms)
            and any(term in prompt_lower for term in action_terms)
        )

    def _extract_lineup_action(
        self,
        prompt: str,
        squad_player_ids: Optional[List[str]] = None,
        current_formation: str = '4-3-3',
        max_budget: float = 100,
    ) -> Optional[SuggestedAction]:
        """Build a structured UI action that honors explicit player requests."""
        formation = current_formation
        prompt_normalized = skills._normalize(prompt)
        for candidate in ('4-2-3-1', '4-4-2', '3-5-2', '5-3-2', '4-3-3'):
            if candidate in prompt_normalized:
                formation = candidate
                break

        required_player_ids = skills.extract_player_ids_from_prompt(prompt)
        position_team_preferences = skills.extract_position_team_preferences(prompt)
        attacking_terms = (
            'hucum', 'attacking', 'attack', 'ofansif', 'gol', 'golcu',
            'forvet', 'bitiricilik', 'hucum gucu', 'assist', 'asist',
            'skor', 'scorer', 'goal contribution',
        )
        defensive_terms = (
            'gol yemeyen', 'clean sheet', 'savunma guvenligi',
            'defansif', 'defensive', 'defans', 'savunma',
        )
        wants_attack = any(term in prompt_normalized for term in attacking_terms)
        wants_defense = any(term in prompt_normalized for term in defensive_terms)
        strategy = (
            'attacking'
            if wants_attack
            else 'defensive' if wants_defense
            else 'balanced'
        )
        lineup = skills.suggest_lineup(
            formation,
            prompt,
            required_player_ids=required_player_ids,
            strategy=strategy,
            position_team_preferences=position_team_preferences,
            current_squad_player_ids=squad_player_ids,
            max_budget=max_budget,
        )
        if 'starting_player_ids' not in lineup:
            return None
        catalog = {player.id: player for player in skills.get_players()}
        required_names = [
            catalog[player_id].name
            for player_id in required_player_ids
            if player_id in catalog
        ]
        requirement_note = (
            f" Explicitly requested players included: {', '.join(required_names)}."
            if required_names else ''
        )
        strategy_note = (
            ' Attacking contribution priority applied.'
            if strategy == 'attacking'
            else ' Defensive stability priority applied.'
            if strategy == 'defensive'
            else ''
        )
        preference_note = (
            ' Positional team preferences: '
            + ', '.join(
                f"{position}={', '.join(teams)}"
                for position, teams in position_team_preferences.items()
            )
            + '.'
            if position_team_preferences else ''
        )
        return SuggestedAction(
            type='lineup',
            formation=lineup['formation'],
            startingPlayerIds=lineup['starting_player_ids'],
            benchPlayerIds=[],
            budgetUsed=lineup['budget_used'],
            maxBudget=lineup.get('max_budget', max_budget),
            totalPoints=lineup['total_points'],
            strategy=strategy,
            reasoning=lineup['reasoning'] + requirement_note + preference_note + strategy_note,
        )

    def _rule_based_fallback(
        self,
        prompt: str,
        squad_player_ids: List[str],
        is_premium: bool,
        formation: str = '4-3-3',
        max_budget: float = 100,
        analysis_mode: bool = False,
    ) -> AgentResponse:
        """Fallback to rule-based logic when Gemini is unavailable."""
        prompt_lower = skills._normalize(prompt)

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

        intent = 'deep_analysis' if analysis_mode else self._classify_intent(prompt, squad_player_ids)
        if intent == 'targeted_transfer':
            action = self._extract_targeted_transfer_action(prompt, squad_player_ids, max_budget)
            if action:
                catalog = {player.id: player for player in skills.get_players()}
                sell = catalog.get(action.sellPlayerId or '')
                buy = catalog.get(action.buyPlayerId or '')
                return AgentResponse(
                    message=(
                        f"🔁 **Tekli değişim önerisi**\n\n"
                        f"{sell.name if sell else 'Seçilen oyuncu'} → {buy.name if buy else 'önerilen oyuncu'}\n\n"
                        f"{action.reasoning}\n\n"
                        "Bu yalnızca tek bir oyuncu için öneridir; diğer 10 oyuncuya dokunmaz. "
                        "Onaylarsan sadece bu değişimi uygularım."
                    ),
                    suggestedAction=action,
                    isPremium=is_premium,
                )

        # Full-XI proposals remain available offline, but only after an
        # explicit squad-building request.
        if intent == 'lineup':
            action = self._extract_lineup_action(prompt, squad_player_ids, formation, max_budget)
            if action and action.startingPlayerIds:
                return AgentResponse(
                    message=self._format_lineup_message(action),
                    suggestedAction=action,
                    isPremium=is_premium,
                )

        match_discussion = self._build_match_discussion(prompt) if intent == 'conversation' else None
        if match_discussion:
            return AgentResponse(message=match_discussion, isPremium=is_premium)

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

                transfer = skills.suggest_transfer(squad_player_ids, max_budget=max_budget)
                if intent in {'transfer', 'deep_analysis'} and 'sell_player' in transfer:
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

        # Transfer suggestion is a premium action. Free users can ask for an
        # upgrade path, but must never receive an executable recommendation.
        if intent in {'transfer', 'deep_analysis'}:
            if not is_premium:
                return AgentResponse(
                    message=(
                        "I can prepare an executable transfer recommendation after you unlock "
                        "Deep Tactical Analytics with x402."
                    ),
                    isPremium=False
                )

            target_position = skills.detect_position_from_prompt(prompt)
            transfer = skills.suggest_transfer(squad_player_ids, target_position, max_budget)
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
        scope_terms = (
            'world cup', 'worldcup', 'world cup 2026', 'fifa', 'football',
            'soccer', 'player', 'squad', 'team', 'lineup', 'kadro', 'oyuncu',
            'maç', 'mac', 'match', 'transfer', 'formation', 'diziliş',
            'dizilis', 'goalkeeper', 'defender', 'midfielder', 'forward',
            'forvet', 'defans', 'orta saha', 'kaleci', 'injury', 'sakat',
            'budget', 'bütçe', 'xg', 'injective', 'x402', 'cctp', 'mcp',
        )
        if not any(term in prompt_lower for term in scope_terms):
            return AgentResponse(
                message=(
                    "Bu konuda yardımcı olamam, gaffer. Auto-Gaffer yalnızca "
                    "FIFA World Cup 2026, futbol maçları, oyuncular ve kadro "
                    "yönetimi hakkında yanıt verir."
                ),
                isPremium=is_premium,
            )

        return AgentResponse(
            message=(
                "Good question, gaffer. I can help with player analysis, squad composition, "
                "position rankings, and transfer strategy. Try asking about a specific player, "
                "position, or your squad."
            ),
            isPremium=False
        )

    @staticmethod
    def _build_match_discussion(prompt: str) -> Optional[str]:
        """Offer a useful non-mutating answer for match/winner/player questions."""
        normalized = skills._normalize(prompt)
        aliases = {
            'argentina': 'Argentina', 'arjantin': 'Argentina',
            'england': 'England', 'ingiltere': 'England',
            'france': 'France', 'fransa': 'France',
            'spain': 'Spain', 'ispanya': 'Spain',
        }
        mentioned = []
        for alias, team in aliases.items():
            if alias in normalized and team not in mentioned:
                mentioned.append(team)
        conversation_terms = (
            'kim yener', 'kim kazanir', 'winner', 'kazanir mi', 'kazanir',
            'ne dersin', 'yorumla', 'analiz', 'kimi almali', 'kimi alayim',
            'hangi oyuncu', 'oyuncu tavsiye',
        )
        if len(mentioned) < 2 or not any(term in normalized for term in conversation_terms):
            return None

        players = skills.get_players()
        teams = mentioned[:2]
        ranked = {
            team: sorted([player for player in players if player.team == team], key=lambda player: player.points, reverse=True)
            for team in teams
        }
        averages = {
            team: round(sum(player.points for player in ranked[team][:5]) / max(1, len(ranked[team][:5])), 1)
            for team in teams
        }
        leader = max(teams, key=lambda team: averages[team])
        options = []
        for team in teams:
            for player in ranked[team][:2]:
                stats = player.world_cup_stats
                verified = f"{stats.goals or 0}G/{stats.assists or 0}A verified" if stats and stats.data_status == 'verified' else f"{player.points} fantasy pts"
                options.append(f"{player.name} ({team}, {verified})")
        return (
            f"⚽ **{teams[0]} vs {teams[1]} — konuşma bazlı ön analiz**\n\n"
            f"Auto-Gaffer modelinde küçük avantaj **{leader}** tarafında: ilk beş oyuncunun uygulama fantasy puanı ortalaması "
            f"{averages[leader]:.1f}. Bu bir maç sonucu veya resmi olasılık değildir; güncel resmi ilk 11, sakatlık ve canlı oran olmadan kesin kazanan söylemem.\n\n"
            f"**Kadroya bakılabilecek isimler:**\n- " + "\n- ".join(options[:4]) +
            "\n\nİstersen bir sonraki mesajda sadece şu üç konudan birini derinleştirebilirim: "
            "maç eşleşmesi, iki takımın belirli bir bölgesi veya mevcut kadrona tekli oyuncu önerisi. "
            "Açıkça ‘11 kur’ ya da ‘X yerine Y koy’ demedikçe kadro aksiyonu oluşturmam."
        )


# Singleton instance
_agent_client: Optional[GeminiAgentClient] = None


def get_agent_client() -> GeminiAgentClient:
    """Get or create the singleton agent client."""
    global _agent_client
    if _agent_client is None:
        _agent_client = GeminiAgentClient()
    return _agent_client
