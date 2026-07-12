"""
MCP client for calling Auto-Gaffer squad tools.
Used by the transfers router to execute transfers via MCP.
"""
from typing import Dict, Any, Optional
import json


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

        # In a real implementation, this would connect to the MCP server via stdio/HTTP
        # and execute the actual tool call
        return await self._simulate_tool_call(tool_name, arguments)

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
                    "timestamp": time.time()
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
                "server": "auto-gaffer-mcp"
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
        _mcp_client = MCPClient()
    return _mcp_client