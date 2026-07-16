"""Import the FIFA World Cup 2026 official 48-team squad-list PDF.

Usage:
    python scripts/import_official_fifa_squads.py

The generated file is intentionally a source snapshot. Player prices, fantasy
points and scouting signals are calculated in ``backend/app/data.py`` and are
never stored here as official FIFA data.
"""
from __future__ import annotations

import json
import re
import unicodedata
import urllib.request
from collections import defaultdict
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "worldcup_2026_rosters.json"
PDF_URL = "https://fdp.fifa.org/assetspublic/ce281/pdf/SquadLists-English.pdf"
FIFA_TEAMS_URL = "https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/teams"
SNAPSHOT_DATE = "2026-07-15"

# FIFA codes used in the official squad-list PDF. England and Scotland use the
# football flags because they are separate FIFA member associations.
FLAGS = {
    "ALG": "🇩🇿", "ARG": "🇦🇷", "AUS": "🇦🇺", "AUT": "🇦🇹", "BEL": "🇧🇪",
    "BIH": "🇧🇦", "BRA": "🇧🇷", "CPV": "🇨🇻", "CAN": "🇨🇦", "COL": "🇨🇴",
    "COD": "🇨🇩", "CIV": "🇨🇮", "CRO": "🇭🇷", "CUW": "🇨🇼", "CZE": "🇨🇿",
    "ECU": "🇪🇨", "EGY": "🇪🇬", "ENG": "🏴", "FRA": "🇫🇷", "GER": "🇩🇪",
    "GHA": "🇬🇭", "HAI": "🇭🇹", "IRN": "🇮🇷", "IRQ": "🇮🇶", "JPN": "🇯🇵",
    "JOR": "🇯🇴", "KOR": "🇰🇷", "MEX": "🇲🇽", "MAR": "🇲🇦", "NED": "🇳🇱",
    "NZL": "🇳🇿", "NOR": "🇳🇴", "PAN": "🇵🇦", "PAR": "🇵🇾", "POR": "🇵🇹",
    "QAT": "🇶🇦", "KSA": "🇸🇦", "SCO": "🏴", "SEN": "🇸🇳", "RSA": "🇿🇦",
    "ESP": "🇪🇸", "SWE": "🇸🇪", "SUI": "🇨🇭", "TUN": "🇹🇳", "TUR": "🇹🇷",
    "URU": "🇺🇾", "USA": "🇺🇸", "UZB": "🇺🇿",
}


def normalized(value: str) -> str:
    value = unicodedata.normalize("NFD", value.casefold())
    return "".join(char for char in value if not unicodedata.combining(char))


def slug(value: str) -> str:
    value = normalized(value)
    value = re.sub(r"[^a-z0-9]+", "_", value).strip("_")
    return value or "player"


def title_name(value: str) -> str:
    """Turn FIFA table surnames into a readable display name without guessing."""
    return " ".join(part.capitalize() if part.isupper() else part for part in value.split())


def display_name(table_name: str, first_names: str) -> str:
    """Convert FIFA's source-stable 'SURNAME Given' field to a display name."""
    table_parts = table_name.split()
    surname_end = 0
    for index, part in enumerate(table_parts):
        if part == part.upper() and any(char.isalpha() for char in part):
            surname_end = index + 1
        else:
            break
    if 0 < surname_end < len(table_parts):
        surname = " ".join(table_parts[:surname_end])
        given = table_parts[surname_end:]
        # Some PDF pages merge the player-name and first-name cells. Preserve
        # the official wording but collapse only adjacent duplicated tokens.
        deduplicated = []
        for part in given:
            if not deduplicated or normalized(part) != normalized(deduplicated[-1]):
                deduplicated.append(part)
        return f"{' '.join(deduplicated)} {title_name(surname)}"
    if len(table_parts) > 1:
        return f"{title_name(table_parts[-1])} {title_name(' '.join(table_parts[:-1]))}"
    return title_name(table_name)


def legacy_ids() -> dict[tuple[str, str], list[tuple[str, set[str]]]]:
    """Retain old IDs where an official record matches a former catalog player."""
    if not OUTPUT.exists():
        return {}
    source = json.loads(OUTPUT.read_text(encoding="utf-8"))
    matches: dict[tuple[str, str], list[tuple[str, set[str]]]] = defaultdict(list)
    for team, team_data in source.get("teams", {}).items():
        for player in team_data.get("players", []):
            words = {word for word in re.findall(r"[a-z0-9]+", normalized(player["name"])) if len(word) >= 3}
            matches[(team, player["position"])].append((player["id"], words))
    return matches


def resolve_legacy_id(
    previous: dict[tuple[str, str], list[tuple[str, set[str]]]],
    team: str,
    position: str,
    name: str,
) -> str | None:
    words = {word for word in re.findall(r"[a-z0-9]+", normalized(name)) if len(word) >= 3}
    candidates = []
    for old_id, old_words in previous.get((team, position), []):
        overlap = len(words & old_words)
        if overlap:
            candidates.append((overlap, old_id))
    candidates.sort(reverse=True)
    if not candidates:
        return None
    best_score = candidates[0][0]
    if sum(1 for score, _ in candidates if score == best_score) != 1:
        return None
    return candidates[0][1]


def page_chunks(page: Any) -> list[tuple[float, float, str]]:
    chunks: list[tuple[float, float, str]] = []

    def visitor(text: str, _cm: Any, tm: Any, _font: Any, _size: Any) -> None:
        text = text.replace("\x00", "").strip()
        if text:
            chunks.append((round(float(tm[4]), 1), round(float(tm[5]), 1), text))

    page.extract_text(visitor_text=visitor)
    return chunks


def chunks_on_row(chunks: list[tuple[float, float, str]], y: float) -> list[tuple[float, str]]:
    return [(x, text) for x, row_y, text in chunks if abs(row_y - y) < 0.8]


def first_cell(cells: list[tuple[float, str]], lower: float, upper: float) -> str:
    return " ".join(text for x, text in sorted(cells) if lower <= x < upper).strip()


def parse_page(page: Any) -> tuple[str, str, list[dict[str, Any]]]:
    text = page.extract_text()
    heading = text.splitlines()[0]
    match = re.fullmatch(r"(.+) \(([A-Z]{3})\)", heading)
    if not match:
        raise ValueError(f"Unrecognised FIFA squad heading: {heading!r}")
    team, code = match.groups()
    chunks = page_chunks(page)
    rows: list[dict[str, Any]] = []
    seen_numbers: set[int] = set()
    for x, y, value in chunks:
        if not (10 <= x < 25 and value.isdigit() and 1 <= int(value) <= 26):
            continue
        shirt_number = int(value)
        if shirt_number in seen_numbers:
            continue
        cells = chunks_on_row(chunks, y)
        position = first_cell(cells, 25, 50)
        table_name = first_cell(cells, 50, 165)
        if position not in {"GK", "DF", "MF", "FW"} or not table_name:
            continue
        seen_numbers.add(shirt_number)
        first_names = first_cell(cells, 165, 291)
        dob = first_cell(cells, 480, 532)
        club = first_cell(cells, 520, 705)
        rows.append({
            "position": position,
            "number": shirt_number,
            "name": display_name(table_name, first_names),
            "officialName": table_name,
            "dateOfBirth": dob if re.fullmatch(r"\d{2}/\d{2}/\d{4}", dob) else None,
            "club": club or None,
        })
    if len(rows) != 26:
        raise ValueError(f"{team}: expected 26 official players, extracted {len(rows)}")
    return team, code, sorted(rows, key=lambda item: item["number"])


def main() -> None:
    previous = legacy_ids()
    # Windows keeps NamedTemporaryFile handles locked, so close it before the
    # downloader opens the same path.
    with NamedTemporaryFile(suffix=".pdf", delete=False) as download:
        download_path = Path(download.name)
    try:
        urllib.request.urlretrieve(PDF_URL, download_path)
        reader = PdfReader(download_path)
        if len(reader.pages) != 48:
            raise ValueError(f"Expected 48 team pages, found {len(reader.pages)}")
        teams: dict[str, Any] = {}
        seen_ids: set[str] = set()
        for page in reader.pages:
            team, code, players = parse_page(page)
            roster = []
            for player in players:
                legacy = resolve_legacy_id(previous, team, player["position"], player["name"])
                player_id = legacy or f"{code.lower()}_{player['position'].lower()}_{slug(player['name'])}"
                if player_id in seen_ids:
                    player_id = f"{player_id}_{player['number']}"
                seen_ids.add(player_id)
                roster.append({"id": player_id, **player})
            teams[team] = {"code": code, "flag": FLAGS.get(code, "🏳️"), "players": roster}
    finally:
        download_path.unlink(missing_ok=True)

    payload = {
        "tournament": "FIFA World Cup 2026",
        "snapshotDate": SNAPSHOT_DATE,
        "dataSource": "FIFA World Cup 2026 official final Squad Lists PDF",
        "sourceUrls": {team: PDF_URL for team in teams},
        "officialSources": {"squadListsPdf": PDF_URL, "teams": FIFA_TEAMS_URL},
        "teams": teams,
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {sum(len(team['players']) for team in teams.values())} players across {len(teams)} teams to {OUTPUT}")


if __name__ == "__main__":
    main()
