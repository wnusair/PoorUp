from typing import List

PLAYER_COLOR_PALETTE: List[str] = [
    "#E63946",
    "#2196F3",
    "#4CAF50",
    "#FF9800",
    "#9C27B0",
    "#00BCD4",
    "#F44336",
    "#FFEB3B",
    "#795548",
    "#607D8B",
]

TEAM_COLOR_PALETTE: List[str] = [
    "#B2DFDB",
    "#F8BBD9",
    "#FFF9C4",
    "#CFD8DC",
    "#D7CCC8",
    "#DCEDC8",
]


def get_available_player_colors(taken_colors: List[str]) -> List[str]:
    """Return player colors not already claimed in this match."""
    taken_lower = {c.lower() for c in taken_colors}
    return [c for c in PLAYER_COLOR_PALETTE if c.lower() not in taken_lower]


def get_available_team_colors(taken_colors: List[str]) -> List[str]:
    """Return team colors not already claimed in this match."""
    taken_lower = {c.lower() for c in taken_colors}
    return [c for c in TEAM_COLOR_PALETTE if c.lower() not in taken_lower]


def is_valid_color(color: str, palette: List[str]) -> bool:
    """Check whether a color hex string belongs to the given palette."""
    palette_lower = {c.lower() for c in palette}
    return color.lower() in palette_lower
