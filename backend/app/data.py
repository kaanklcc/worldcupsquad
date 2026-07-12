"""
Load and serve the players data from the shared data folder.
The data is shared with the Next.js frontend.
"""
import json
from pathlib import Path
from typing import List

from .models import Player

# Path to the shared players.json file
DATA_DIR = Path(__file__).parent.parent.parent / "data"
PLAYERS_FILE = DATA_DIR / "worldcup_players.json"


def load_players() -> List[Player]:
    """Load players from the shared JSON file."""
    with open(PLAYERS_FILE, 'r', encoding='utf-8') as f:
        players_data = json.load(f)
    return [Player.model_validate(p) for p in players_data]


# Cache players in memory
_players_cache: List[Player] = []


def get_players() -> List[Player]:
    """Get cached players or load them if not cached."""
    global _players_cache
    if not _players_cache:
        _players_cache = load_players()
    return _players_cache


def reload_players() -> List[Player]:
    """Force reload players from file."""
    global _players_cache
    _players_cache = load_players()
    return _players_cache