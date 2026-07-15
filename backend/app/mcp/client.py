"""
MCP client for calling Auto-Gaffer squad tools.
Used by the transfers router to execute transfers via MCP.
"""
from typing import Dict, Any, Optional
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class MCPClient:
    """Simple MCP client for calling Auto-Gaffer tools."""

    def __init__(self, server_command: Optional[list] = None):
        """
        Initialize the MCP client.

        Args:
            server_command: Command to start the MCP server. If None, uses simulated responses.
        """
        self.server_command = server_command
        self.use_simulation = server_command is None

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call an MCP tool by name.

        Args:
            tool_name: Name of the tool to call
            arguments: Arguments to pass to the tool

        Returns:
            dict with tool result
        """
        if self.use_simulation:
            return await self._simulate_tool_call(tool_name, arguments)

        if not self.server_command:
            return {"success": False, "error": "MCP server command is not configured"}

        command, *args = self.server_command
        server_params = StdioServerParameters(
            command=command,
            args=args,
            cwd=str(Path(__file__).resolve().parents[2]),
        )

        try:
            async with stdio_client(server_params) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, arguments)

            for content in result.content:
                if getattr(content, "type", None) == "text":
                    parsed = json.loads(content.text)
                    if isinstance(parsed, dict):
                        parsed.setdefault("simulated", False)
                        parsed.setdefault("mcp_version", "1.0.0")
                        parsed.setdefault("server", "auto-gaffer-mcp")
                        return parsed

            return {"success": False, "error": "MCP server returned no JSON content"}
        except Exception as exc:
            return {"success": False, "error": f"MCP stdio call failed: {exc}"}

    async def _simulate_tool_call(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Simulate an MCP tool call for demo purposes.

        This mimics what a real MCP server would return.
        """
        import time
        from ..data import get_players

        if tool_name == "apply_transfer":
            sell_id = arguments.get("sell_player_id")
            buy_id = arguments.get("buy_player_id")
            reasoning = arguments.get("reasoning", "")

            # Validate players
            players = get_players()
            sell_player = next((p for p in players if p.id == sell_id), None)
            buy_player = next((p for p in players if p.id == buy_id), None)

            if not sell_player or not buy_player:
                return {
                    "success": False,
                    "error": "Player not found",
                    "timestamp": time.time(),
                    "simulated": True,
                    "server": "auto-gaffer-mcp"
                }

            # Generate realistic MCP receipt
            tx_hash = f"mcp_swap_{int(time.time())}_{sell_id[-6:]}_{buy_id[-6:]}"
            
            return {
                "success": True,
                "tx_hash": tx_hash,
                "sold": sell_player.model_dump(),
                "bought": buy_player.model_dump(),
                "reasoning": reasoning,
                "timestamp": time.time(),
                "mcp_version": "1.0.0",
                "server": "auto-gaffer-mcp",
                "simulated": True
            }

        elif tool_name == "get_squad":
            return {
                "formation": "4-3-3",
                "players": [],
                "budget_used": 0,
                "budget_remaining": 100,
                "timestamp": time.time()
            }

        elif tool_name == "set_formation":
            formation = arguments.get("formation")
            return {
                "success": True,
                "formation": formation,
                "message": f"Formation set to {formation}",
                "timestamp": time.time()
            }

        elif tool_name == "apply_lineup":
            from ..agent.skills import suggest_lineup
            formation = arguments.get("formation", "4-3-3")
            starting_ids = arguments.get("starting_player_ids", [])
            bench_ids = arguments.get("bench_player_ids", [])
            players = get_players()
            catalog = {player.id: player for player in players}
            selected = [catalog.get(player_id) for player_id in [*starting_ids, *bench_ids]]
            if len(starting_ids) != 11 or len(set([*starting_ids, *bench_ids])) != len([*starting_ids, *bench_ids]):
                return {"success": False, "error": "Invalid lineup shape", "simulated": True}
            if any(player is None or not player.isAvailable for player in selected):
                return {"success": False, "error": "Lineup contains an unknown or unavailable player", "simulated": True}
            # Reuse the same position/formation validator as the agent skill.
            expected = suggest_lineup(formation, "")
            expected_positions = [catalog[player_id].position for player_id in expected.get("starting_player_ids", [])]
            actual_positions = [player.position for player in selected[:11]]
            if sorted(expected_positions) != sorted(actual_positions):
                return {"success": False, "error": "Lineup positions do not match formation", "simulated": True}
            return {
                "success": True,
                "action": "apply_lineup",
                "formation": formation,
                "starting_player_ids": starting_ids,
                "bench_player_ids": bench_ids,
                "reasoning": arguments.get("reasoning", ""),
                "tx_hash": f"mcp_lineup_{int(time.time())}",
                "timestamp": time.time(),
                "mcp_version": "1.0.0",
                "server": "auto-gaffer-mcp",
                "simulated": True
            }

        elif tool_name == "get_player_details":
            player_id = arguments.get("player_id")
            players = get_players()
            player = next((p for p in players if p.id == player_id), None)

            if not player:
                return {
                    "error": f"Player with ID '{player_id}' not found"
                }

            return player.model_dump()

        else:
            return {
                "error": f"Unknown tool: {tool_name}"
            }


# Singleton instance
_mcp_client: Optional[MCPClient] = None


def get_mcp_client() -> MCPClient:
    """Get or create the singleton MCP client."""
    global _mcp_client
    if _mcp_client is None:
        from ..config import settings

        command = None
        if not settings.mcp_simulation:
            command = [sys.executable, "-m", "app.mcp.server"]
        _mcp_client = MCPClient(command)
    return _mcp_client
