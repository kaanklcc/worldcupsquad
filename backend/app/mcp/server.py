"""
MCP (Model Context Protocol) server for WCAI squad tools.
Exposes squad management tools that can be called via the MCP protocol.
"""
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.server.models import InitializationOptions
from mcp.server.lowlevel.server import NotificationOptions
from mcp.types import (
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
)
from typing import Any
import json

from ..data import get_players
from ..models import Player


class AutoGafferMCPServer:
    """MCP server exposing WCAI squad management tools."""

    def __init__(self, server_name: str = "wcai-mcp"):
        self.server = Server(server_name)
        self._setup_tools()

    def _setup_tools(self):
        """Register all MCP tools."""

        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            """List available MCP tools."""
            return [
                Tool(
                    name="get_squad",
                    description="Get the current squad configuration including formation and players",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                ),
                Tool(
                    name="apply_transfer",
                    description="Apply a transfer: remove a player and add a new one. Returns updated squad.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "sell_player_id": {
                                "type": "string",
                                "description": "ID of player to sell"
                            },
                            "buy_player_id": {
                                "type": "string",
                                "description": "ID of player to buy"
                            },
                            "reasoning": {
                                "type": "string",
                                "description": "Reasoning for this transfer"
                            }
                        },
                        "required": ["sell_player_id", "buy_player_id"]
                    }
                ),
                Tool(
                    name="set_formation",
                    description="Set the squad formation (e.g., '4-3-3', '4-2-3-1')",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "formation": {
                                "type": "string",
                                "description": "Formation string like '4-3-3' or '4-2-3-1'",
                                "enum": ["4-3-3", "4-4-2", "3-5-2", "4-2-3-1", "5-3-2"]
                            }
                        },
                        "required": ["formation"]
                    }
                ),
                Tool(
                    name="apply_lineup",
                    description="Validate an explicitly confirmed starting XI and formation using catalog player IDs",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "formation": {
                                "type": "string",
                                "enum": ["4-3-3", "4-4-2", "3-5-2", "4-2-3-1", "5-3-2"]
                            },
                            "starting_player_ids": {
                                "type": "array",
                                "items": {"type": "string"},
                                "minItems": 11,
                                "maxItems": 11
                            },
                            "bench_player_ids": {
                                "type": "array",
                                "items": {"type": "string"},
                                "maxItems": 8
                            },
                            "reasoning": {"type": "string"}
                        },
                        "required": ["formation", "starting_player_ids"]
                    }
                ),
                Tool(
                    name="get_player_details",
                    description="Get detailed information about a specific player",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "player_id": {
                                "type": "string",
                                "description": "Unique ID of the player"
                            }
                        },
                        "required": ["player_id"]
                    }
                )
            ]

        @self.server.call_tool()
        async def call_tool(name: str, arguments: Any) -> list[TextContent | ImageContent | EmbeddedResource]:
            """Handle tool calls."""
            
            if name == "get_squad":
                # In a real implementation, this would fetch from a database
                # For now, return a mock squad
                return [
                    TextContent(
                        type="text",
                        text=json.dumps({
                            "formation": "4-3-3",
                            "players": [],
                            "budget_used": 0,
                            "budget_remaining": 100
                        }, indent=2)
                    )
                ]

            elif name == "apply_transfer":
                sell_id = arguments.get("sell_player_id")
                buy_id = arguments.get("buy_player_id")
                reasoning = arguments.get("reasoning", "")

                # Validate players exist
                players = get_players()
                sell_player = next((p for p in players if p.id == sell_id), None)
                buy_player = next((p for p in players if p.id == buy_id), None)

                if not sell_player or not buy_player:
                    return [
                        TextContent(
                            type="text",
                            text=json.dumps({
                                "success": False,
                                "error": "Player not found",
                                "sell_player": sell_player.model_dump() if sell_player else None,
                                "buy_player": buy_player.model_dump() if buy_player else None
                            }, indent=2)
                        )
                    ]

                # Return success response
                import time
                tx_hash = f"mcp_swap_{int(time.time())}_{sell_id[-6:]}_{buy_id[-6:]}"

                return [
                    TextContent(
                        type="text",
                        text=json.dumps({
                            "success": True,
                            "tx_hash": tx_hash,
                            "sold": sell_player.model_dump(),
                            "bought": buy_player.model_dump(),
                            "reasoning": reasoning,
                            "timestamp": time.time()
                        }, indent=2)
                    )
                ]

            elif name == "apply_lineup":
                formation = arguments.get("formation")
                starting_ids = arguments.get("starting_player_ids", [])
                bench_ids = arguments.get("bench_player_ids", [])
                counts = {
                    "4-3-3": {"GK": 1, "DF": 4, "MF": 3, "FW": 3},
                    "4-4-2": {"GK": 1, "DF": 4, "MF": 4, "FW": 2},
                    "3-5-2": {"GK": 1, "DF": 3, "MF": 5, "FW": 2},
                    "4-2-3-1": {"GK": 1, "DF": 4, "MF": 5, "FW": 1},
                    "5-3-2": {"GK": 1, "DF": 5, "MF": 3, "FW": 2},
                }
                players = get_players()
                catalog = {player.id: player for player in players}
                all_ids = [*starting_ids, *bench_ids]
                selected = [catalog.get(player_id) for player_id in all_ids]
                if formation not in counts or len(starting_ids) != 11 or len(set(all_ids)) != len(all_ids):
                    return [TextContent(type="text", text=json.dumps({"success": False, "error": "Invalid lineup shape"}))]
                if any(player is None or not player.isAvailable for player in selected):
                    return [TextContent(type="text", text=json.dumps({"success": False, "error": "Lineup contains an unknown or unavailable player"}))]
                position_counts = {position: 0 for position in counts[formation]}
                for player in selected[:11]:
                    position_counts[player.position] += 1
                if position_counts != counts[formation]:
                    return [TextContent(type="text", text=json.dumps({"success": False, "error": "Lineup positions do not match formation"}))]
                import time
                return [TextContent(type="text", text=json.dumps({
                    "success": True,
                    "action": "apply_lineup",
                    "formation": formation,
                    "starting_player_ids": starting_ids,
                    "bench_player_ids": bench_ids,
                    "reasoning": arguments.get("reasoning", ""),
                    "tx_hash": f"mcp_lineup_{int(time.time())}",
                    "timestamp": time.time()
                }, indent=2))]

            elif name == "set_formation":
                formation = arguments.get("formation")
                if formation not in ["4-3-3", "4-4-2", "3-5-2", "4-2-3-1", "5-3-2"]:
                    return [
                        TextContent(
                            type="text",
                            text=json.dumps({
                                "success": False,
                                "error": f"Invalid formation: {formation}"
                            }, indent=2)
                        )
                    ]

                return [
                    TextContent(
                        type="text",
                        text=json.dumps({
                            "success": True,
                            "formation": formation,
                            "message": f"Formation set to {formation}"
                        }, indent=2)
                    )
                ]

            elif name == "get_player_details":
                player_id = arguments.get("player_id")
                players = get_players()
                player = next((p for p in players if p.id == player_id), None)

                if not player:
                    return [
                        TextContent(
                            type="text",
                            text=json.dumps({
                                "error": f"Player with ID '{player_id}' not found"
                            }, indent=2)
                        )
                    ]

                return [
                    TextContent(
                        type="text",
                        text=json.dumps(player.model_dump(), indent=2)
                    )
                ]

            else:
                return [
                    TextContent(
                        type="text",
                        text=json.dumps({
                            "error": f"Unknown tool: {name}"
                        }, indent=2)
                    )
                ]

    async def run(self):
        """Run the MCP server."""
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="wcai-mcp",
                    server_version="1.0.0",
                    capabilities=self.server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={}
                    )
                )
            )


# Convenience function to run the server
def run_mcp_server():
    """Run the WCAI MCP server."""
    import asyncio
    server = AutoGafferMCPServer()
    asyncio.run(server.run())


if __name__ == "__main__":
    run_mcp_server()
