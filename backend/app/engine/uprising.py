"""Compatibility wrappers for the legacy uprising module."""

from app.engine.social import calculate_overall_rage, ensure_social_state


def calculate_rage(game_state: dict, econ: dict, settings: dict | None = None) -> float:
    return round(float(calculate_overall_rage(game_state, econ, settings) or 0), 2)


def check_uprising(
    game_state: dict,
    econ: dict,
    socketio_instance=None,
    match_id: int = None,
    settings: dict | None = None,
) -> tuple[dict, dict, bool]:
    next_state = ensure_social_state({**dict(game_state), "econ": dict(econ)})
    return next_state, dict(next_state.get("econ", econ)), False
