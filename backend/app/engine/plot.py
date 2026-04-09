"""Communist plot engine for PoorUp."""

from __future__ import annotations

import math
from statistics import median
from typing import Any

from app.engine.debt import has_pending_player_debt, spend_player_balance
from app.engine.economy import (
    calculate_net_worth,
    calculate_rent_with_dev,
    calculate_transit_rent,
    has_full_monopoly,
)
from app.utils.settings import normalize_government_type

COMMUNIST_PLOT_OWNER_ID = "communist_plot"
COMMUNIST_PLOT_OWNER_NAME = "People's Committees"

PLOT_STAGE_NAMES = {
    0: "Eligible Hardship",
    1: "Underground Cell",
    2: "Agitation Network",
    3: "Open Seizure",
    4: "Dual Power",
    5: "People's Victory",
}

TOP_ROW = [47, 40, 39, 38, 37, 36, 34, 32, 31]
RIGHT_COL = [27, 26, 25, 24, 23, 22]
BOTTOM_ROW = [12, 13, 14, 15, 16, 17, 18, 19]
LEFT_COL = [2, 4, 5, 6, 9, 10]
EDGE_CHAINS = {
    "top": TOP_ROW,
    "right": RIGHT_COL,
    "bottom": BOTTOM_ROW,
    "left": LEFT_COL,
}

POSITION_TO_EDGE: dict[int, str] = {}
POSITION_TO_EDGE_INDEX: dict[int, int] = {}
for _edge_name, _edge_chain in EDGE_CHAINS.items():
    for _index, _position in enumerate(_edge_chain):
        POSITION_TO_EDGE[_position] = _edge_name
        POSITION_TO_EDGE_INDEX[_position] = _index

PLOT_ACTION_DEFS = {
    "mutual_aid": {
        "label": "Mutual Aid",
        "stage": 1,
        "cost": {"support": 2},
        "cooldown_scope": "region",
        "cooldown_rounds": 1,
        "target": "region",
        "description": "Gain Support, reduce Heat, improve recruitment odds.",
    },
    "whisper_campaign": {
        "label": "Whisper Campaign",
        "stage": 1,
        "cost": {"support": 1},
        "target": "property_or_region",
        "description": "Increase local agitation slightly.",
    },
    "establish_safehouse": {
        "label": "Establish Safehouse",
        "stage": 1,
        "cost": {"support": 2},
        "cooldown_scope": "region",
        "cooldown_rounds": 1,
        "target": "region",
        "description": "Lower Heat and protect underground work in one region.",
    },
    "seed_cell": {
        "label": "Seed Cell",
        "stage": 1,
        "cost": {"support": 3},
        "cooldown_scope": "region",
        "cooldown_rounds": 1,
        "target": "region",
        "description": "Create a hidden foothold in one region.",
    },
    "recruit_sympathizer": {
        "label": "Recruit Sympathizer",
        "stage": 2,
        "cost": {"support": 4},
        "cooldown_scope": "target",
        "cooldown_rounds": 1,
        "target": "player",
        "description": "Start the join process for another player.",
    },
    "convert_to_organizer": {
        "label": "Convert To Organizer",
        "stage": 2,
        "cost": {"support": 2, "supply": 1},
        "cooldown_scope": "target",
        "cooldown_rounds": 1,
        "target": "player",
        "description": "Upgrade a seasoned sympathizer into an organizer.",
    },
    "agitate_property": {
        "label": "Agitate Property",
        "stage": 2,
        "cost": {"support": 2},
        "cooldown_scope": "property",
        "cooldown_rounds": 1,
        "target": "property",
        "description": "Raise plot pressure on one property.",
    },
    "sabotage_development": {
        "label": "Sabotage Development",
        "stage": 2,
        "cost": {"support": 1, "supply": 1},
        "cooldown_scope": "property",
        "cooldown_rounds": 2,
        "target": "property",
        "description": "Cut owner efficiency and raise local tension.",
    },
    "hide_assets": {
        "label": "Hide Assets",
        "stage": 2,
        "cost": {"support": 1},
        "cooldown_scope": "region",
        "cooldown_rounds": 1,
        "target": "region",
        "description": "Protect a regional cache and reduce Heat.",
    },
    "stockpile_supply": {
        "label": "Stockpile Supply",
        "stage": 2,
        "cost": {"support": 2},
        "target": "region_optional",
        "description": "Convert Support into pre-seizure logistical capacity.",
    },
    "attempt_seizure": {
        "label": "Attempt Seizure",
        "stage": 3,
        "cost": {"support": 6, "supply": 4},
        "cooldown_scope": "property",
        "cooldown_rounds": 1,
        "target": "property",
        "description": "Attempt to seize a legal property target.",
    },
    "fortify_property": {
        "label": "Fortify Property",
        "stage": 3,
        "cost": {"supply": 2},
        "cooldown_scope": "property",
        "cooldown_rounds": 1,
        "target": "seized_property",
        "description": "Raise entrenchment and supply defense.",
    },
    "spread_to_adjacent_territory": {
        "label": "Spread To Adjacent Territory",
        "stage": 3,
        "cost": {"support": 3, "supply": 2},
        "cooldown_scope": "cluster",
        "cooldown_rounds": 1,
        "target": "cluster",
        "description": "Open adjacent territory for expansion.",
    },
    "recruit_publicly": {
        "label": "Recruit Publicly",
        "stage": 3,
        "cost": {"support": 4},
        "cooldown_scope": "target",
        "cooldown_rounds": 1,
        "target": "player",
        "description": "Invite another player into the faction at higher Heat.",
    },
    "call_emergency_redistribution": {
        "label": "Call Emergency Redistribution",
        "stage": 3,
        "cost": {"support": 2, "supply": 2},
        "cooldown_scope": "region",
        "cooldown_rounds": 1,
        "target": "region",
        "description": "Spend resources for immediate relief and local momentum.",
    },
    "establish_regional_council": {
        "label": "Establish Regional Council",
        "stage": 4,
        "cost": {"support": 3, "supply": 5},
        "cooldown_scope": "region",
        "cooldown_rounds": 2,
        "target": "region",
        "description": "Create a regional revolutionary authority.",
    },
    "increase_entrenchment": {
        "label": "Increase Entrenchment",
        "stage": 4,
        "cost": {"support": 2, "supply": 4},
        "cooldown_scope": "cluster",
        "cooldown_rounds": 1,
        "target": "cluster",
        "description": "Fortify an entire seized cluster.",
    },
    "redirect_supply_between_regions": {
        "label": "Redirect Supply Between Regions",
        "stage": 4,
        "cost": {"supply": 2},
        "target": "two_regions",
        "description": "Move pooled supply into a regional defense reserve.",
    },
    "call_mass_action": {
        "label": "Call Mass Action",
        "stage": 4,
        "cost": {"support": 5},
        "cooldown_scope": "global",
        "cooldown_rounds": 2,
        "target": "region_optional",
        "description": "Trade Heat for board-wide agitation and Support.",
    },
    "defend_reintegration": {
        "label": "Defend Against Reintegration",
        "stage": 4,
        "cost": {"supply": 3},
        "target": "seized_property",
        "description": "Spend Supply to blunt a reintegration campaign.",
    },
}

COUNTER_ACTION_DEFS = {
    "join_coalition": {
        "label": "Join Coalition",
        "target": "none",
        "description": "Join the anti-revolution coalition once it unlocks.",
        "cash_cost": 0,
        "supporters_required": 0,
    },
    "relief_package": {
        "label": "Relief Package",
        "target": "region",
        "description": "Lower hardship and Support growth in one region.",
        "cash_cost": 150,
        "supporters_required": 0,
    },
    "labor_settlement": {
        "label": "Labor Settlement",
        "target": "property",
        "description": "Reduce agitation and seizure pressure on one property.",
        "cash_cost": 120,
        "supporters_required": 0,
    },
    "security_subsidy": {
        "label": "Security Subsidy",
        "target": "property",
        "description": "Make a property harder to seize for two rounds.",
        "cash_cost": 180,
        "supporters_required": 0,
    },
    "intelligence_sweep": {
        "label": "Intelligence Sweep",
        "target": "region",
        "description": "Reveal hidden cells or plans in one region.",
        "cash_cost": 160,
        "supporters_required": 1,
    },
    "blockade_cluster": {
        "label": "Blockade Cluster",
        "target": "cluster",
        "description": "Reduce Supply yield on a seized cluster.",
        "cash_cost": 220,
        "supporters_required": 1,
    },
    "reintegration_campaign": {
        "label": "Reintegration Campaign",
        "target": "seized_property",
        "description": "Reclaim a seized property after repeated pressure.",
        "cash_cost": 220,
        "supporters_required": 1,
    },
    "propaganda_counteroffensive": {
        "label": "Propaganda Counteroffensive",
        "target": "none",
        "description": "Slow recruitment globally for one round.",
        "cash_cost": 140,
        "supporters_required": 0,
    },
}


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _round(value: float | int | None, digits: int = 2) -> float:
    return round(float(value or 0), digits)


def _game_round(game_state: dict) -> int:
    return max(1, int(game_state.get("current_round", 1) or 1))


def _active_players(game_state: dict) -> list[dict]:
    return [player for player in game_state.get("players", []) if not player.get("is_bankrupt", False)]


def _player_index(game_state: dict) -> dict[int, dict]:
    return {int(player.get("id") or 0): player for player in game_state.get("players", []) if player.get("id") is not None}


def _ownable_properties(game_state: dict) -> list[dict]:
    return [prop for prop in game_state.get("properties", []) if prop.get("property_type") in {"property", "transit"}]


def _property_index(game_state: dict) -> dict[int, dict]:
    return {int(prop.get("id") or 0): prop for prop in game_state.get("properties", []) if prop.get("id") is not None}


def _plot_defaults() -> dict:
    return {
        "exists": False,
        "founder_id": None,
        "public": False,
        "stage": 0,
        "stage_name": PLOT_STAGE_NAMES[0],
        "created_round": None,
        "public_round": None,
        "support": 0.0,
        "supply": 0.0,
        "heat": 0.0,
        "support_generated_total": 0.0,
        "control_percent": 0.0,
        "first_seizure_round": None,
        "last_mutual_aid_round": 0,
        "last_recruitment_round": 0,
        "last_aggression_round": 0,
        "last_successful_action_round": 0,
        "last_stockpile_round": 0,
        "last_round_resolved": 0,
        "stage_advanced_round": 0,
        "coalition_unlocked": False,
        "recruitment_slowdown_until_round": 0,
        "recent_backlash_support": 0.0,
        "members": {},
        "join_invites": {},
        "regions": {},
        "cooldowns": {},
        "action_history": [],
        "recent_failures": [],
        "victory_countdown": {
            "active": False,
            "rounds_held": 0,
            "required_rounds": 2,
            "completed": False,
            "blocked_reason": None,
            "started_round": None,
            "last_valid_round": None,
        },
    }


def _member_defaults(player_id: int, current_round: int, *, is_founder: bool = False) -> dict:
    return {
        "player_id": player_id,
        "role": "founder" if is_founder else "sympathizer",
        "is_founder": bool(is_founder),
        "joined_round": current_round,
        "contribution_rounds": [current_round] if is_founder else [],
        "required_contribution_rounds": 1 if is_founder else 2,
        "required_successful_actions": 1,
        "successful_actions_supported": 0,
        "support_contributed": 0.0,
        "supply_contributed": 0.0,
        "cash_contributed": 0.0,
        "prosperous_entry": False,
        "defection_cooldown_until": 0,
        "active": True,
    }


def _region_defaults() -> dict:
    return {
        "seeded_cells": 0,
        "safehouse_until_round": 0,
        "aid_bonus_until_round": 0,
        "mutual_aid_until_round": 0,
        "relief_until_round": 0,
        "support_suppressed_until_round": 0,
        "hidden_assets_until_round": 0,
        "revealed_until_round": 0,
        "council_established_round": None,
        "defense_reserve": 0.0,
    }


def _coerce_member(player_id: int, value: dict | None, current_round: int) -> dict:
    coerced = {**_member_defaults(player_id, current_round), **(dict(value or {}))}
    contribution_rounds = []
    for round_value in coerced.get("contribution_rounds", []):
        try:
            contribution_rounds.append(int(round_value))
        except (TypeError, ValueError):
            continue
    coerced["contribution_rounds"] = sorted(set(contribution_rounds))
    coerced["player_id"] = player_id
    coerced["is_founder"] = bool(coerced.get("is_founder", False))
    coerced["successful_actions_supported"] = int(coerced.get("successful_actions_supported", 0) or 0)
    coerced["required_contribution_rounds"] = max(1, int(coerced.get("required_contribution_rounds", 2) or 2))
    coerced["required_successful_actions"] = max(1, int(coerced.get("required_successful_actions", 1) or 1))
    coerced["defection_cooldown_until"] = int(coerced.get("defection_cooldown_until", 0) or 0)
    coerced["support_contributed"] = _round(coerced.get("support_contributed", 0), 2)
    coerced["supply_contributed"] = _round(coerced.get("supply_contributed", 0), 2)
    coerced["cash_contributed"] = _round(coerced.get("cash_contributed", 0), 2)
    coerced["joined_round"] = int(coerced.get("joined_round", current_round) or current_round)
    coerced["active"] = bool(coerced.get("active", True))
    return coerced


def _coerce_region(value: dict | None) -> dict:
    coerced = {**_region_defaults(), **(dict(value or {}))}
    coerced["seeded_cells"] = max(0, int(coerced.get("seeded_cells", 0) or 0))
    coerced["safehouse_until_round"] = int(coerced.get("safehouse_until_round", 0) or 0)
    coerced["aid_bonus_until_round"] = int(coerced.get("aid_bonus_until_round", 0) or 0)
    coerced["mutual_aid_until_round"] = int(coerced.get("mutual_aid_until_round", 0) or 0)
    coerced["relief_until_round"] = int(coerced.get("relief_until_round", 0) or 0)
    coerced["support_suppressed_until_round"] = int(coerced.get("support_suppressed_until_round", 0) or 0)
    coerced["hidden_assets_until_round"] = int(coerced.get("hidden_assets_until_round", 0) or 0)
    coerced["revealed_until_round"] = int(coerced.get("revealed_until_round", 0) or 0)
    coerced["defense_reserve"] = _round(coerced.get("defense_reserve", 0), 2)
    return coerced


def _coerce_plot_state(value: dict | None, current_round: int) -> dict:
    plot = {**_plot_defaults(), **(dict(value or {}))}
    plot["exists"] = bool(plot.get("exists", False))
    plot["support"] = _round(plot.get("support", 0), 2)
    plot["supply"] = _round(plot.get("supply", 0), 2)
    plot["heat"] = _round(plot.get("heat", 0), 2)
    plot["support_generated_total"] = _round(plot.get("support_generated_total", 0), 2)
    plot["control_percent"] = _round(plot.get("control_percent", 0), 2)
    plot["stage"] = max(0, int(plot.get("stage", 0) or 0))
    plot["stage_name"] = PLOT_STAGE_NAMES.get(plot["stage"], PLOT_STAGE_NAMES[0])
    plot["public"] = bool(plot.get("public", False))
    plot["coalition_unlocked"] = bool(plot.get("coalition_unlocked", False))
    plot["recruitment_slowdown_until_round"] = int(plot.get("recruitment_slowdown_until_round", 0) or 0)
    plot["recent_backlash_support"] = _round(plot.get("recent_backlash_support", 0), 2)
    plot["last_round_resolved"] = int(plot.get("last_round_resolved", 0) or 0)
    plot["stage_advanced_round"] = int(plot.get("stage_advanced_round", 0) or 0)
    plot["last_mutual_aid_round"] = int(plot.get("last_mutual_aid_round", 0) or 0)
    plot["last_recruitment_round"] = int(plot.get("last_recruitment_round", 0) or 0)
    plot["last_aggression_round"] = int(plot.get("last_aggression_round", 0) or 0)
    plot["last_successful_action_round"] = int(plot.get("last_successful_action_round", 0) or 0)
    plot["last_stockpile_round"] = int(plot.get("last_stockpile_round", 0) or 0)

    victory = dict(_plot_defaults()["victory_countdown"])
    victory.update(dict(plot.get("victory_countdown") or {}))
    victory["active"] = bool(victory.get("active", False))
    victory["rounds_held"] = max(0, int(victory.get("rounds_held", 0) or 0))
    victory["required_rounds"] = max(1, int(victory.get("required_rounds", 2) or 2))
    victory["completed"] = bool(victory.get("completed", False))
    plot["victory_countdown"] = victory

    plot["members"] = {
        str(int(player_id)): _coerce_member(int(player_id), member_state, current_round)
        for player_id, member_state in (plot.get("members") or {}).items()
        if str(player_id).isdigit()
    }
    plot["join_invites"] = {
        str(int(player_id)): dict(invite or {})
        for player_id, invite in (plot.get("join_invites") or {}).items()
        if str(player_id).isdigit()
    }
    plot["regions"] = {
        str(region): _coerce_region(region_state)
        for region, region_state in (plot.get("regions") or {}).items()
        if str(region).strip()
    }
    plot["cooldowns"] = {
        str(key): int(value or 0)
        for key, value in (plot.get("cooldowns") or {}).items()
        if str(key).strip()
    }
    plot["action_history"] = [dict(entry) for entry in (plot.get("action_history") or []) if isinstance(entry, dict)][-40:]
    plot["recent_failures"] = [dict(entry) for entry in (plot.get("recent_failures") or []) if isinstance(entry, dict)][-12:]
    return plot


def _ensure_plot_contract(game_state: dict) -> dict:
    next_state = dict(game_state)
    social = dict(next_state.get("social") or {})
    current_round = _game_round(next_state)
    social["plot"] = _coerce_plot_state(social.get("plot"), current_round)
    next_state["social"] = social

    updated_players = []
    for player in next_state.get("players", []):
        next_player = dict(player)
        next_player.setdefault("plot_role", None)
        next_player.setdefault("plot_join_round", None)
        next_player.setdefault("plot_defection_cooldown_until", 0)
        next_player.setdefault("plot_hardship_score", 0)
        next_player.setdefault("plot_hardship_trigger_count", 0)
        next_player.setdefault("plot_hardship_reasons", [])
        next_player.setdefault("plot_hardship_triggers", [])
        next_player.setdefault("plot_hidden_hardship_pressure", 0)
        next_player.setdefault("plot_support_contributed", 0.0)
        next_player.setdefault("plot_supply_contributed", 0.0)
        next_player.setdefault("plot_bottom_half_streak", 0)
        next_player.setdefault("plot_last_hardship_round", 0)
        next_player.setdefault("plot_last_counter_commit_round", 0)
        updated_players.append(next_player)
    next_state["players"] = updated_players
    return next_state


def _get_plot(game_state: dict) -> dict:
    return ((game_state.get("social") or {}).get("plot") or {})


def _social_properties(game_state: dict) -> dict[str, dict]:
    social = dict(game_state.get("social") or {})
    return {str(key): dict(value) for key, value in (social.get("properties") or {}).items()}


def _set_social_properties(game_state: dict, properties: dict[str, dict], plot: dict) -> dict:
    next_state = dict(game_state)
    social = dict(next_state.get("social") or {})
    social["properties"] = properties
    social["plot"] = plot
    next_state["social"] = social
    return next_state


def _replace_player(game_state: dict, player_id: int, updates: dict) -> dict:
    next_state = dict(game_state)
    updated_players = []
    for player in next_state.get("players", []):
        if int(player.get("id") or 0) == int(player_id):
            updated_players.append({**dict(player), **updates})
        else:
            updated_players.append(dict(player))
    next_state["players"] = updated_players
    return next_state


def _append_history(plot: dict, *, action_type: str, player_id: int | None, current_round: int, success: bool, summary: str, extra: dict | None = None) -> dict:
    updated_plot = dict(plot)
    history = list(updated_plot.get("action_history") or [])
    entry = {
        "action_type": action_type,
        "player_id": player_id,
        "round": current_round,
        "success": bool(success),
        "summary": summary,
    }
    if extra:
        entry.update(extra)
    history.append(entry)
    updated_plot["action_history"] = history[-40:]
    if not success:
        failures = list(updated_plot.get("recent_failures") or [])
        failures.append(entry)
        updated_plot["recent_failures"] = failures[-12:]
    return updated_plot


def _add_support(plot: dict, amount: float) -> dict:
    updated_plot = dict(plot)
    delta = _round(amount, 2)
    updated_plot["support"] = _round(clamp(float(updated_plot.get("support", 0) or 0) + delta, 0.0, 60.0), 2)
    if delta > 0:
        updated_plot["support_generated_total"] = _round(float(updated_plot.get("support_generated_total", 0) or 0) + delta, 2)
    return updated_plot


def _add_supply(plot: dict, amount: float) -> dict:
    updated_plot = dict(plot)
    updated_plot["supply"] = _round(clamp(float(updated_plot.get("supply", 0) or 0) + float(amount or 0), 0.0, 80.0), 2)
    return updated_plot


def _add_heat(plot: dict, amount: float) -> dict:
    updated_plot = dict(plot)
    updated_plot["heat"] = _round(clamp(float(updated_plot.get("heat", 0) or 0) + float(amount or 0), 0.0, 100.0), 2)
    return updated_plot


def _active_member_ids(plot: dict, player_lookup: dict[int, dict]) -> list[int]:
    member_ids = []
    for player_id_text, member in (plot.get("members") or {}).items():
        player_id = int(player_id_text)
        player = player_lookup.get(player_id)
        if player is None or player.get("is_bankrupt") or not member.get("active", True):
            continue
        member_ids.append(player_id)
    return member_ids


def _committed_member_ids(plot: dict, player_lookup: dict[int, dict]) -> list[int]:
    committed = []
    for player_id in _active_member_ids(plot, player_lookup):
        member = (plot.get("members") or {}).get(str(player_id)) or {}
        if member.get("role") in {"committed_member", "cadre"}:
            committed.append(player_id)
    return committed


def _cadre_ids(plot: dict, player_lookup: dict[int, dict]) -> list[int]:
    cadre_ids = []
    for player_id in _active_member_ids(plot, player_lookup):
        member = (plot.get("members") or {}).get(str(player_id)) or {}
        if member.get("role") == "cadre":
            cadre_ids.append(player_id)
    return cadre_ids


def _coalition_member_ids(plot: dict, player_lookup: dict[int, dict]) -> list[int]:
    coalition_ids = []
    for player_id_text, member in (plot.get("members") or {}).items():
        player_id = int(player_id_text)
        if player_id in player_lookup and member.get("role") == "coalition":
            coalition_ids.append(player_id)
    for invite_player_id in (plot.get("coalition_member_ids") or []):
        try:
            player_id = int(invite_player_id)
        except (TypeError, ValueError):
            continue
        if player_lookup.get(player_id) and player_id not in coalition_ids:
            coalition_ids.append(player_id)
    return coalition_ids


def _wealthiest_active_player_id(game_state: dict) -> int | None:
    players = _active_players(game_state)
    if not players:
        return None
    return max(
        (int(player.get("id") or 0) for player in players),
        key=lambda candidate: float(calculate_net_worth(_player_index(game_state).get(candidate) or {}, game_state) or 0),
    )


def _median_balance(game_state: dict) -> float:
    values = [float(player.get("balance", 0) or 0) for player in _active_players(game_state)]
    if not values:
        return 0.0
    return float(median(values))


def _median_rent_reference(game_state: dict) -> float:
    econ = dict(game_state.get("econ") or {})
    rents = []
    for prop in _ownable_properties(game_state):
        try:
            if prop.get("property_type") == "transit":
                rents.append(float(calculate_transit_rent(prop.get("owner_id"), game_state) or max(25.0, float(prop.get("base_price", 0) or 0) * 0.125)))
            else:
                rents.append(float(calculate_rent_with_dev(prop, econ, game_state) or 0))
        except Exception:
            rents.append(float(prop.get("base_price", 0) or 0) * 0.16)
    if not rents:
        return 120.0
    return max(80.0, float(median(rents)))


def _property_count_by_player(game_state: dict) -> dict[int, int]:
    counts: dict[int, int] = {}
    for prop in _ownable_properties(game_state):
        owner_id = prop.get("owner_id")
        if not isinstance(owner_id, int):
            continue
        counts[owner_id] = counts.get(owner_id, 0) + 1
    return counts


def _property_owned_by_player(prop: dict, player_id: int) -> bool:
    owner_id = prop.get("owner_id")
    return isinstance(owner_id, int) and owner_id == int(player_id)


def _monopoly_count_for_player(player_id: int, game_state: dict) -> int:
    return sum(
        1
        for prop in _ownable_properties(game_state)
        if _property_owned_by_player(prop, player_id)
        and prop.get("property_type") == "property"
        and has_full_monopoly(prop, game_state)
    )


def _recent_player_setback(game_state: dict, player: dict, current_round: int) -> bool:
    player_id = int(player.get("id") or 0)
    player_name = str(player.get("username") or "")
    recent_logs = list(game_state.get("log_buffer") or [])[-40:]
    relevant_types = {
        "trade_rejected",
        "deal_rejected",
        "deal_expired",
        "player_bankrupt",
        "auction_won",
        "property_transferred",
        "property_lost",
        "bankruptcy",
    }
    for entry in recent_logs:
        event_type = str(entry.get("event_type") or "")
        entry_round = entry.get("round")
        if entry_round is not None:
            try:
                if current_round - int(entry_round) > 2:
                    continue
            except (TypeError, ValueError):
                pass
        if int(entry.get("player_id", 0) or 0) == player_id and event_type in relevant_types:
            return True
        description = str(entry.get("description") or "")
        if player_name and player_name in description and event_type in relevant_types:
            return True
    return False


def _player_local_region(player_id: int, game_state: dict) -> str | None:
    owned_regions = [prop.get("region") for prop in _ownable_properties(game_state) if _property_owned_by_player(prop, player_id) and prop.get("region")]
    if owned_regions:
        region_counts: dict[str, int] = {}
        for region in owned_regions:
            region_counts[region] = region_counts.get(region, 0) + 1
        return max(region_counts, key=region_counts.get)

    player_lookup = _player_index(game_state)
    player = player_lookup.get(player_id) or {}
    current_position = int(player.get("current_position", 0) or 0)
    for prop in _ownable_properties(game_state):
        if int(prop.get("board_position", -1) or -1) == current_position and prop.get("region"):
            return str(prop.get("region"))
    return None


def _minarchist_hidden_pressure(player_id: int, game_state: dict) -> int:
    gov_type = normalize_government_type((game_state.get("econ") or {}).get("gov_type") or (game_state.get("settings") or {}).get("government_type"))
    if gov_type != "minarchism":
        return 0
    region = _player_local_region(player_id, game_state)
    if not region:
        return 0

    development_by_owner: dict[int, int] = {}
    for prop in _ownable_properties(game_state):
        owner_id = prop.get("owner_id")
        if not isinstance(owner_id, int) or owner_id == player_id:
            continue
        if str(prop.get("region") or "") != region:
            continue
        development_by_owner[owner_id] = development_by_owner.get(owner_id, 0) + max(0, int(prop.get("dev_level", 0) or 0))

    if not development_by_owner:
        return 0
    dominant_dev = max(development_by_owner.values())
    return min(3, dominant_dev // 2)


def _evaluate_hardship(player: dict, game_state: dict, current_round: int, net_worth_by_player: dict[int, float], bottom_half_ids: set[int], median_balance: float, median_rent: float, bailout_history: list[dict]) -> dict:
    player_id = int(player.get("id") or 0)
    reasons = []
    trigger_keys = []

    last_hardship_round = int(player.get("plot_last_hardship_round", 0) or 0)
    bottom_half_streak = int(player.get("plot_bottom_half_streak", 0) or 0)
    if current_round != last_hardship_round:
        if player_id in bottom_half_ids:
            bottom_half_streak += 1
        else:
            bottom_half_streak = 0
    if float(player.get("balance", 0) or 0) <= median_balance * 0.65:
        trigger_keys.append("low_balance")
        reasons.append("Current balance is below 65% of the active-player median.")
    if bottom_half_streak >= 2:
        trigger_keys.append("bottom_half_net_worth")
        reasons.append("Net worth has sat in the bottom half for two consecutive rounds.")
    if _recent_player_setback(game_state, player, current_round):
        trigger_keys.append("recent_setback")
        reasons.append("A recent auction, deal, or property setback still hangs over this player.")
    recent_bailout = any(int(entry.get("player_id", 0) or 0) == player_id and current_round - int(entry.get("round", current_round) or current_round) <= 3 for entry in bailout_history)
    if has_pending_player_debt(game_state, player_id) or recent_bailout or float(player.get("balance", 0) or 0) <= max(120.0, median_rent * 1.15):
        trigger_keys.append("debt_or_bailout")
        reasons.append("Pending debt, bailout stress, or a near-bankruptcy position is present.")
    property_count = sum(1 for prop in _ownable_properties(game_state) if _property_owned_by_player(prop, player_id))
    if current_round >= 4 and property_count <= 2 and _monopoly_count_for_player(player_id, game_state) == 0:
        trigger_keys.append("low_property_base")
        reasons.append("No monopoly and too few properties remain after the opening rounds.")

    hidden_pressure = _minarchist_hidden_pressure(player_id, game_state)
    if hidden_pressure > 0:
        reasons.append(f"Local overdevelopment under Minarchism adds {hidden_pressure} hidden hardship pressure.")

    trigger_count = len(trigger_keys)
    hardship_score = trigger_count + hidden_pressure
    return {
        "score": hardship_score,
        "trigger_count": trigger_count,
        "triggers": trigger_keys,
        "reasons": reasons,
        "bottom_half_streak": bottom_half_streak,
        "hidden_pressure": hidden_pressure,
        "eligible": trigger_count >= 2,
        "net_worth": _round(net_worth_by_player.get(player_id, 0), 2),
        "property_count": property_count,
    }


def _neighbor_positions(position: int) -> list[int]:
    edge = POSITION_TO_EDGE.get(position)
    if not edge:
        return []
    chain = EDGE_CHAINS[edge]
    index = POSITION_TO_EDGE_INDEX.get(position, -1)
    neighbors = []
    if index > 0:
        neighbors.append(chain[index - 1])
    if index >= 0 and index < len(chain) - 1:
        neighbors.append(chain[index + 1])
    return neighbors


def _is_property_plot_seized(prop: dict | None, social_entry: dict | None = None) -> bool:
    if not prop and not social_entry:
        return False
    if prop and prop.get("owner_id") == COMMUNIST_PLOT_OWNER_ID:
        return True
    return bool((social_entry or {}).get("plot_seized"))


def property_is_plot_seized(prop_or_entry: dict | None, game_state: dict | None = None) -> bool:
    if not prop_or_entry:
        return False
    if prop_or_entry.get("owner_id") == COMMUNIST_PLOT_OWNER_ID or prop_or_entry.get("plot_seized"):
        return True
    if game_state is None:
        return False
    social_entry = (_social_properties(game_state).get(str(prop_or_entry.get("id"))) or {}) if prop_or_entry.get("id") is not None else {}
    return bool(social_entry.get("plot_seized"))


def _cluster_map(game_state: dict, social_properties: dict[str, dict]) -> tuple[dict[str, dict], dict[int, str]]:
    properties_by_id = _property_index(game_state)
    seized_ids = [
        property_id
        for property_id, prop in properties_by_id.items()
        if _is_property_plot_seized(prop, social_properties.get(str(property_id)))
    ]
    remaining = set(seized_ids)
    clusters: dict[str, dict] = {}
    property_to_cluster: dict[int, str] = {}
    counter = 1

    while remaining:
        seed_id = next(iter(remaining))
        queue = [seed_id]
        cluster_ids = []
        remaining.remove(seed_id)

        while queue:
            current_id = queue.pop(0)
            current_prop = properties_by_id.get(current_id) or {}
            current_position = int(current_prop.get("board_position", -1) or -1)
            cluster_ids.append(current_id)
            for neighbor_position in _neighbor_positions(current_position):
                neighbor_prop = next((prop for prop in properties_by_id.values() if int(prop.get("board_position", -1) or -1) == neighbor_position), None)
                if neighbor_prop is None:
                    continue
                neighbor_id = int(neighbor_prop.get("id") or 0)
                if neighbor_id in remaining and _is_property_plot_seized(neighbor_prop, social_properties.get(str(neighbor_id))):
                    remaining.remove(neighbor_id)
                    queue.append(neighbor_id)

        cluster_id = f"cluster_{counter}"
        counter += 1
        cluster_props = [properties_by_id[property_id] for property_id in cluster_ids if property_id in properties_by_id]
        regions = sorted({str(prop.get("region") or "Unassigned") for prop in cluster_props})
        edge = POSITION_TO_EDGE.get(int(cluster_props[0].get("board_position", -1) or -1)) if cluster_props else None
        clusters[cluster_id] = {
            "cluster_id": cluster_id,
            "property_ids": sorted(cluster_ids, key=lambda property_id: int((properties_by_id.get(property_id) or {}).get("board_position", 0) or 0)),
            "region_names": regions,
            "edge": edge,
            "size": len(cluster_ids),
        }
        for property_id in cluster_ids:
            property_to_cluster[property_id] = cluster_id

    return clusters, property_to_cluster


def _region_pressure(region: str, social: dict, plot_region: dict, treasury_balance: float) -> int:
    territory_entries = [entry for entry in (social.get("territories") or []) if str(entry.get("region") or "") == str(region)]
    max_instability = max((float(entry.get("territory_instability", 0) or 0) for entry in territory_entries), default=0.0)
    active_incidents = sum(int(entry.get("active_incident_count", 0) or 0) for entry in territory_entries)
    pressure = 0
    if max_instability >= 50:
        pressure += 1
    if max_instability >= 65:
        pressure += 1
    if max_instability >= 80:
        pressure += 1
    if active_incidents > 0:
        pressure += 1
    if treasury_balance < 350:
        pressure += 1
    if int(plot_region.get("relief_until_round", 0) or 0) >= int(social.get("current_round", 1) or 1):
        pressure = max(0, pressure - 2)
    return max(0, min(5, pressure))


def _calculate_supply_yield(prop: dict, social_entry: dict, *, cluster_size: int, government_type: str, current_round: int, first_seizure_round: int | None) -> int:
    base_tier = min(4, 1 + int(math.floor(float(prop.get("base_price", 0) or 0) / 180.0)))
    dev_cap = 4 if government_type == "minarchism" and first_seizure_round is not None and int(social_entry.get("plot_seized_round", 0) or 0) == int(first_seizure_round) else 3
    development_bonus = min(dev_cap, max(0, int(prop.get("dev_level", 0) or 0)))
    contiguous_bonus = 0
    if cluster_size >= 2:
        contiguous_bonus = 1
    if cluster_size >= 3:
        contiguous_bonus = 2

    volatility = 0
    territory_instability = float(social_entry.get("territory_instability", 0) or 0)
    if territory_instability >= 70 or social_entry.get("incident_type"):
        volatility = 1
    elif territory_instability <= 35:
        volatility = -1

    blockade_penalty = 2 if int(social_entry.get("plot_blockaded_until_round", 0) or 0) >= current_round else 0
    exhaustion_penalty = 1 if int(social_entry.get("plot_last_levy_round", 0) or 0) == current_round and int(social_entry.get("plot_last_spread_round", 0) or 0) == current_round else 0
    yield_value = base_tier + development_bonus + contiguous_bonus + volatility - blockade_penalty - exhaustion_penalty
    return int(clamp(yield_value, 0, 8))


def _merge_plot_property_state(game_state: dict, plot: dict, social: dict) -> tuple[dict[str, dict], dict[str, dict], dict[int, str]]:
    social_properties = {str(key): dict(value) for key, value in (social.get("properties") or {}).items()}
    properties_by_id = _property_index(game_state)
    clusters, property_to_cluster = _cluster_map(game_state, social_properties)
    government_type = normalize_government_type((game_state.get("econ") or {}).get("gov_type") or (game_state.get("settings") or {}).get("government_type"))
    current_round = _game_round(game_state)
    first_seizure_round = plot.get("first_seizure_round")

    for property_id, prop in properties_by_id.items():
        entry = dict(social_properties.get(str(property_id)) or {})
        is_seized = _is_property_plot_seized(prop, entry)
        cluster_id = property_to_cluster.get(property_id)
        cluster = clusters.get(cluster_id or "") or {}
        supply_yield = 0
        if is_seized:
            supply_yield = _calculate_supply_yield(
                prop,
                entry,
                cluster_size=int(cluster.get("size", 1) or 1),
                government_type=government_type,
                current_round=current_round,
                first_seizure_round=first_seizure_round,
            )
        social_properties[str(property_id)] = {
            **entry,
            "plot_seized": bool(is_seized),
            "plot_cluster_id": cluster_id,
            "plot_entrenchment": max(0, int(entry.get("plot_entrenchment", 0) or 0)),
            "plot_supply_yield": supply_yield,
            "plot_contested": bool(entry.get("plot_contested", False)),
            "plot_blockaded": int(entry.get("plot_blockaded_until_round", 0) or 0) >= current_round,
            "plot_last_levy_round": int(entry.get("plot_last_levy_round", 0) or 0),
            "plot_agitation": max(0, int(entry.get("plot_agitation", 0) or 0)),
            "plot_seizure_lockout_until_round": int(entry.get("plot_seizure_lockout_until_round", 0) or 0),
            "plot_former_owner_id": entry.get("plot_former_owner_id"),
            "plot_reintegration_progress": int(entry.get("plot_reintegration_progress", 0) or 0),
            "plot_reintegration_pushes": int(entry.get("plot_reintegration_pushes", 0) or 0),
            "plot_security_subsidy_until_round": int(entry.get("plot_security_subsidy_until_round", 0) or 0),
            "plot_safehouse_until_round": int(entry.get("plot_safehouse_until_round", 0) or 0),
            "plot_hidden_assets_until_round": int(entry.get("plot_hidden_assets_until_round", 0) or 0),
            "plot_sabotaged_until_round": int(entry.get("plot_sabotaged_until_round", 0) or 0),
            "plot_seized_round": int(entry.get("plot_seized_round", 0) or 0),
            "plot_last_spread_round": int(entry.get("plot_last_spread_round", 0) or 0),
            "plot_blockaded_until_round": int(entry.get("plot_blockaded_until_round", 0) or 0),
        }

    return social_properties, clusters, property_to_cluster


def _seized_property_ids(game_state: dict, social_properties: dict[str, dict]) -> list[int]:
    return sorted(
        [
            property_id
            for property_id, prop in _property_index(game_state).items()
            if _is_property_plot_seized(prop, social_properties.get(str(property_id)))
        ],
        key=lambda property_id: int((_property_index(game_state).get(property_id) or {}).get("board_position", 0) or 0),
    )


def _control_percent(game_state: dict, social_properties: dict[str, dict]) -> float:
    total_value = 0.0
    seized_value = 0.0
    for prop in _ownable_properties(game_state):
        prop_value = float(prop.get("current_value") or prop.get("base_price", 0) or 0)
        total_value += max(0.0, prop_value)
        if _is_property_plot_seized(prop, social_properties.get(str(prop.get("id")))):
            seized_value += max(0.0, prop_value)
    if total_value <= 0:
        return 0.0
    return _round((seized_value / total_value) * 100.0, 2)


def _seizure_score(game_state: dict, plot: dict, prop: dict, social_entry: dict, *, supply_commitment: int = 0) -> int:
    current_round = _game_round(game_state)
    properties_by_id = _property_index(game_state)
    player_lookup = _player_index(game_state)
    committed_count = len(_committed_member_ids(plot, player_lookup))
    cadre_count = len(_cadre_ids(plot, player_lookup))
    region_name = str(prop.get("region") or social_entry.get("region") or "")
    region_state = dict((plot.get("regions") or {}).get(region_name) or {})
    hardship_pressure = int(region_state.get("hardship_pressure", 0) or 0)
    adjacency_bonus = 0
    for neighbor_position in _neighbor_positions(int(prop.get("board_position", -1) or -1)):
        neighbor_prop = next((candidate for candidate in properties_by_id.values() if int(candidate.get("board_position", -1) or -1) == neighbor_position), None)
        if neighbor_prop and _is_property_plot_seized(neighbor_prop, _social_properties(game_state).get(str(neighbor_prop.get("id")))):
            adjacency_bonus = 2
            break

    government_type = normalize_government_type((game_state.get("econ") or {}).get("gov_type") or (game_state.get("settings") or {}).get("government_type"))
    minarchism_bonus = 0
    if government_type == "minarchism":
        minarchism_bonus = min(3, max(0, int(prop.get("dev_level", 0) or 0)) // 2)

    owner_strength = min(3, max(0, int(prop.get("dev_level", 0) or 0)) // 2)
    owner_id = prop.get("owner_id")
    if isinstance(owner_id, int):
        owner_props = [candidate for candidate in _ownable_properties(game_state) if _property_owned_by_player(candidate, owner_id)]
        if len(owner_props) >= 4:
            owner_strength += 1
    if int(social_entry.get("plot_security_subsidy_until_round", 0) or 0) >= current_round:
        owner_strength += 2

    heat_penalty = 0
    if float(plot.get("heat", 0) or 0) >= 60:
        heat_penalty += 2
    if float(plot.get("heat", 0) or 0) >= 85:
        heat_penalty += 4

    score = 6
    score += int(social_entry.get("plot_agitation", 0) or 0)
    score += adjacency_bonus
    score += min(3, committed_count + cadre_count)
    score += min(3, int(math.ceil(hardship_pressure / 2.0)))
    score += 1 if float(plot.get("support", 0) or 0) >= 10 else 0
    score += min(2, int(float(plot.get("supply", 0) or 0) // 4))
    score += min(2, max(0, int(supply_commitment)))
    score += minarchism_bonus
    score -= owner_strength
    score -= heat_penalty
    return score


def _cooldown_key(action_type: str, *, region: str | None = None, property_id: int | None = None, cluster_id: str | None = None, target_player_id: int | None = None) -> str:
    if property_id is not None:
        return f"{action_type}:property:{property_id}"
    if region:
        return f"{action_type}:region:{region}"
    if cluster_id:
        return f"{action_type}:cluster:{cluster_id}"
    if target_player_id is not None:
        return f"{action_type}:target:{target_player_id}"
    return f"{action_type}:global"


def _assert_cooldown_available(plot: dict, action_type: str, *, current_round: int, region: str | None = None, property_id: int | None = None, cluster_id: str | None = None, target_player_id: int | None = None) -> None:
    key = _cooldown_key(action_type, region=region, property_id=property_id, cluster_id=cluster_id, target_player_id=target_player_id)
    until_round = int((plot.get("cooldowns") or {}).get(key, 0) or 0)
    if until_round >= current_round:
        raise ValueError("That plot action is still cooling down for this target.")


def _set_cooldown(plot: dict, action_type: str, *, current_round: int, rounds: int, region: str | None = None, property_id: int | None = None, cluster_id: str | None = None, target_player_id: int | None = None) -> dict:
    updated_plot = dict(plot)
    if rounds <= 0:
        return updated_plot
    cooldowns = dict(updated_plot.get("cooldowns") or {})
    key = _cooldown_key(action_type, region=region, property_id=property_id, cluster_id=cluster_id, target_player_id=target_player_id)
    cooldowns[key] = current_round + max(0, rounds - 1)
    updated_plot["cooldowns"] = cooldowns
    return updated_plot


def _spend_plot_cost(plot: dict, cost: dict[str, float]) -> dict:
    updated_plot = dict(plot)
    support_cost = float(cost.get("support", 0) or 0)
    supply_cost = float(cost.get("supply", 0) or 0)
    if float(updated_plot.get("support", 0) or 0) < support_cost:
        raise ValueError("The communist plot does not have enough Support for that operation.")
    if float(updated_plot.get("supply", 0) or 0) < supply_cost:
        raise ValueError("The communist plot does not have enough Supply for that operation.")
    updated_plot["support"] = _round(float(updated_plot.get("support", 0) or 0) - support_cost, 2)
    updated_plot["supply"] = _round(float(updated_plot.get("supply", 0) or 0) - supply_cost, 2)
    return updated_plot


def _refresh_state(game_state: dict) -> dict:
    from app.engine.social import ensure_social_state

    return ensure_social_state(game_state)


def _dissolve_plot(game_state: dict, reason: str | None = None) -> dict:
    next_state = _ensure_plot_contract(game_state)
    social = dict(next_state.get("social") or {})
    plot = _coerce_plot_state(None, _game_round(next_state))
    social_properties = _social_properties(next_state)

    updated_properties = []
    for prop in next_state.get("properties", []):
        next_prop = dict(prop)
        entry = dict(social_properties.get(str(prop.get("id"))) or {})
        if _is_property_plot_seized(next_prop, entry):
            restored_owner = entry.get("plot_former_owner_id")
            if restored_owner in _player_index(next_state):
                next_prop["owner_id"] = restored_owner
            else:
                next_prop["owner_id"] = None
            entry = {
                key: value
                for key, value in entry.items()
                if not str(key).startswith("plot_")
            }
        social_properties[str(prop.get("id"))] = entry
        updated_properties.append(next_prop)

    next_state["properties"] = updated_properties
    social["plot"] = plot
    social["properties"] = social_properties
    next_state["social"] = social
    next_state = _refresh_state(next_state)
    if reason:
        refreshed_plot = dict((_get_plot(next_state) or {}))
        refreshed_plot = _append_history(
            refreshed_plot,
            action_type="plot_dissolved",
            player_id=None,
            current_round=_game_round(next_state),
            success=True,
            summary=reason,
        )
        next_state = _set_social_properties(next_state, _social_properties(next_state), refreshed_plot)
        next_state = _refresh_state(next_state)
    return next_state


def _sync_member_promotions(plot: dict, game_state: dict) -> dict:
    current_round = _game_round(game_state)
    updated_plot = dict(plot)
    members = {str(player_id): dict(member) for player_id, member in (updated_plot.get("members") or {}).items()}
    player_lookup = _player_index(game_state)
    for player_id_text, member in list(members.items()):
        player_id = int(player_id_text)
        player = player_lookup.get(player_id)
        if player is None or player.get("is_bankrupt"):
            member["active"] = False
            members[player_id_text] = member
            continue
        if member.get("role") in {"founder", "organizer"}:
            ready_for_commitment = current_round > int(member.get("joined_round", current_round) or current_round)
            enough_contributions = len(member.get("contribution_rounds") or []) >= int(member.get("required_contribution_rounds", 2) or 2)
            enough_actions = int(member.get("successful_actions_supported", 0) or 0) >= int(member.get("required_successful_actions", 1) or 1)
            founder_can_commit = bool(member.get("is_founder")) and ready_for_commitment and int(member.get("successful_actions_supported", 0) or 0) >= 1
            if (ready_for_commitment and enough_contributions and enough_actions) or founder_can_commit:
                member["role"] = "committed_member"
        if member.get("role") == "committed_member" and int(member.get("successful_actions_supported", 0) or 0) >= max(3, int(member.get("required_successful_actions", 1) or 1) + 1):
            member["role"] = "cadre"
        members[player_id_text] = member
    updated_plot["members"] = members
    return updated_plot


def refresh_plot_snapshot(game_state: dict) -> dict:
    next_state = _ensure_plot_contract(game_state)
    current_round = _game_round(next_state)
    player_lookup = _player_index(next_state)
    active_players = _active_players(next_state)
    social = dict(next_state.get("social") or {})
    plot = _coerce_plot_state((social.get("plot") or {}), current_round)
    plot = _sync_member_promotions(plot, next_state)

    net_worth_by_player = {
        int(player.get("id") or 0): float(calculate_net_worth(player, next_state) or 0)
        for player in active_players
    }
    ranked_ids = [player_id for player_id, _ in sorted(net_worth_by_player.items(), key=lambda item: item[1])]
    bottom_half_cutoff = math.ceil(len(ranked_ids) / 2) if ranked_ids else 0
    bottom_half_ids = set(ranked_ids[:bottom_half_cutoff])
    median_balance = _median_balance(next_state)
    median_rent = _median_rent_reference(next_state)
    bailout_history = list((social.get("bailout_history") or []))
    wealthiest_player_id = _wealthiest_active_player_id(next_state)

    updated_players = []
    hardship_by_player: dict[int, dict] = {}
    for player in next_state.get("players", []):
        next_player = dict(player)
        hardship = _evaluate_hardship(
            next_player,
            next_state,
            current_round,
            net_worth_by_player,
            bottom_half_ids,
            median_balance,
            median_rent,
            bailout_history,
        )
        hardship_by_player[int(next_player.get("id") or 0)] = hardship
        next_player["plot_hardship_score"] = int(hardship["score"])
        next_player["plot_hardship_trigger_count"] = int(hardship["trigger_count"])
        next_player["plot_hardship_triggers"] = list(hardship["triggers"])
        next_player["plot_hardship_reasons"] = list(hardship["reasons"])
        next_player["plot_hidden_hardship_pressure"] = int(hardship["hidden_pressure"])
        next_player["plot_bottom_half_streak"] = int(hardship["bottom_half_streak"])
        next_player["plot_last_hardship_round"] = current_round
        member = (plot.get("members") or {}).get(str(int(next_player.get("id") or 0))) or {}
        next_player["plot_role"] = member.get("role") if member.get("active", True) else None
        next_player["plot_join_round"] = member.get("joined_round")
        next_player["plot_defection_cooldown_until"] = int(member.get("defection_cooldown_until", 0) or 0)
        next_player["plot_support_contributed"] = _round(member.get("support_contributed", 0), 2)
        next_player["plot_supply_contributed"] = _round(member.get("supply_contributed", 0), 2)
        next_player["plot_can_found"] = bool(
            not plot.get("exists")
            and current_round >= 4
            and not next_player.get("is_bankrupt")
            and int(next_player.get("id") or 0) != int(wealthiest_player_id or 0)
            and hardship.get("eligible")
        )
        updated_players.append(next_player)
    next_state["players"] = updated_players

    active_members = _active_member_ids(plot, _player_index(next_state))
    if plot.get("exists") and not active_members:
        return _dissolve_plot(next_state, reason="The communist plot collapsed after losing all active members.")

    social_properties, clusters, property_to_cluster = _merge_plot_property_state(next_state, plot, social)
    seized_ids = _seized_property_ids(next_state, social_properties)
    control_percent = _control_percent(next_state, social_properties)
    plot_regions = {str(region): _coerce_region(region_state) for region, region_state in (plot.get("regions") or {}).items()}
    treasury_balance = float((next_state.get("econ") or {}).get("treasury_balance", 0) or 0)
    all_regions = sorted({str(prop.get("region") or "Unassigned") for prop in _ownable_properties(next_state)})
    for region in all_regions:
        plot_regions[region] = _coerce_region(plot_regions.get(region))
        plot_regions[region]["hardship_pressure"] = _region_pressure(region, social, plot_regions[region], treasury_balance)
        plot_regions[region]["revealed"] = int(plot_regions[region].get("revealed_until_round", 0) or 0) >= current_round
        plot_regions[region]["safehouse_active"] = int(plot_regions[region].get("safehouse_until_round", 0) or 0) >= current_round
        plot_regions[region]["relief_active"] = int(plot_regions[region].get("relief_until_round", 0) or 0) >= current_round
        plot_regions[region]["council_active"] = plot_regions[region].get("council_established_round") is not None

    legal_targets = []
    properties_by_id = _property_index(next_state)
    for property_id, prop in properties_by_id.items():
        entry = dict(social_properties.get(str(property_id)) or {})
        if prop.get("property_type") not in {"property", "transit"}:
            continue
        owner_id = prop.get("owner_id")
        if owner_id is None or owner_id == COMMUNIST_PLOT_OWNER_ID:
            continue
        if _is_property_plot_seized(prop, entry):
            continue
        if int(entry.get("plot_seizure_lockout_until_round", 0) or 0) >= current_round:
            continue
        if int(entry.get("plot_security_subsidy_until_round", 0) or 0) >= current_round:
            continue

        adjacent_to_control = False
        for neighbor_position in _neighbor_positions(int(prop.get("board_position", -1) or -1)):
            neighbor_prop = next((candidate for candidate in properties_by_id.values() if int(candidate.get("board_position", -1) or -1) == neighbor_position), None)
            if neighbor_prop is not None and _is_property_plot_seized(neighbor_prop, social_properties.get(str(neighbor_prop.get("id")))):
                adjacent_to_control = True
                break

        region_state = plot_regions.get(str(prop.get("region") or "Unassigned"), _region_defaults())
        seeded_presence = int(region_state.get("seeded_cells", 0) or 0) > 0
        agitation = int(entry.get("plot_agitation", 0) or 0)
        if agitation < 2 and not adjacent_to_control and not seeded_presence:
            continue

        preview_score = _seizure_score(next_state, plot, prop, entry)
        legal_targets.append(
            {
                "property_id": property_id,
                "property_name": prop.get("name") or f"Property {property_id}",
                "owner_id": owner_id,
                "owner_name": (_player_index(next_state).get(owner_id) or {}).get("username", COMMUNIST_PLOT_OWNER_NAME if owner_id == COMMUNIST_PLOT_OWNER_ID else f"Player {owner_id}"),
                "region": prop.get("region"),
                "board_position": prop.get("board_position"),
                "agitation": agitation,
                "adjacent_to_control": adjacent_to_control,
                "preview_score": preview_score,
            }
        )

    committed_ids = _committed_member_ids(plot, _player_index(next_state))
    cadre_ids = _cadre_ids(plot, _player_index(next_state))
    coalition_ids = [
        player_id
        for player_id in ((social.get("plot") or {}).get("coalition_member_ids") or [])
        if int(player_id or 0) in _player_index(next_state)
    ]
    seized_regions = sorted({str((properties_by_id.get(property_id) or {}).get("region") or "Unassigned") for property_id in seized_ids})
    entrenched_clusters = []
    cluster_summaries = []
    for cluster_id, cluster in clusters.items():
        property_ids = list(cluster.get("property_ids") or [])
        entrenchments = [int((social_properties.get(str(property_id)) or {}).get("plot_entrenchment", 0) or 0) for property_id in property_ids]
        blockaded = any(int((social_properties.get(str(property_id)) or {}).get("plot_blockaded_until_round", 0) or 0) >= current_round for property_id in property_ids)
        reintegration_pressure = max(int((social_properties.get(str(property_id)) or {}).get("plot_reintegration_progress", 0) or 0) for property_id in property_ids) if property_ids else 0
        summary = {
            **cluster,
            "entrenched": bool(property_ids and min(entrenchments or [0]) >= 2),
            "avg_entrenchment": _round(sum(entrenchments) / max(1, len(entrenchments)), 2),
            "blockaded": blockaded,
            "reintegration_pressure": reintegration_pressure,
        }
        if summary["entrenched"]:
            entrenched_clusters.append(cluster_id)
        cluster_summaries.append(summary)

    target_stage = 1 if plot.get("exists") else 0
    total_seeded_cells = sum(int(region_state.get("seeded_cells", 0) or 0) for region_state in plot_regions.values())
    if plot.get("exists") and current_round >= 5 and float(plot.get("support_generated_total", 0) or 0) >= 12 and total_seeded_cells >= 2 and float(plot.get("heat", 0) or 0) < 60:
        target_stage = 2
    if plot.get("exists") and current_round >= 6 and committed_ids and float(plot.get("support", 0) or 0) >= 6 and float(plot.get("supply", 0) or 0) >= 4 and legal_targets:
        target_stage = 3
    if plot.get("exists") and current_round >= 7 and (len(seized_ids) >= 4 or control_percent >= 18.0) and entrenched_clusters and float(plot.get("support", 0) or 0) > 12:
        target_stage = 4
    if bool((plot.get("victory_countdown") or {}).get("completed")):
        target_stage = 5

    if plot.get("exists") and target_stage > int(plot.get("stage", 0) or 0) and int(plot.get("stage_advanced_round", 0) or 0) != current_round:
        plot["stage"] = int(plot.get("stage", 0) or 0) + 1
        plot["stage_advanced_round"] = current_round
    plot["stage"] = max(int(plot.get("stage", 0) or 0), target_stage if target_stage == 5 else int(plot.get("stage", 0) or 0))
    plot["stage_name"] = PLOT_STAGE_NAMES.get(int(plot.get("stage", 0) or 0), PLOT_STAGE_NAMES[0])
    plot["public"] = bool(plot.get("public")) or int(plot.get("stage", 0) or 0) >= 3 or bool(seized_ids)
    if plot.get("public") and not plot.get("public_round"):
        plot["public_round"] = current_round
    plot["coalition_unlocked"] = bool(plot.get("coalition_unlocked")) or bool(plot.get("first_seizure_round"))
    plot["control_percent"] = control_percent
    plot["regions"] = plot_regions

    eligible_players = []
    member_ids = _active_member_ids(plot, _player_index(next_state))
    for player in next_state.get("players", []):
        player_id = int(player.get("id") or 0)
        hardship = hardship_by_player.get(player_id, {})
        eligible_players.append(
            {
                "player_id": player_id,
                "username": player.get("username", f"Player {player_id}"),
                "bankrupt": bool(player.get("is_bankrupt", False)),
                "plot_role": player.get("plot_role"),
                "plot_can_found": bool(player.get("plot_can_found", False)),
                "hardship_score": int(hardship.get("score", 0) or 0),
                "hardship_trigger_count": int(hardship.get("trigger_count", 0) or 0),
                "hardship_reasons": list(hardship.get("reasons", [])),
                "hardship_triggers": list(hardship.get("triggers", [])),
                "invited": str(player_id) in (plot.get("join_invites") or {}),
                "coalition_member": player_id in coalition_ids,
                "wealthiest": player_id == wealthiest_player_id,
                "recruitable": plot.get("exists") and player_id not in member_ids and not player.get("is_bankrupt", False),
            }
        )

    seized_properties = []
    for property_id in seized_ids:
        prop = properties_by_id.get(property_id) or {}
        entry = dict(social_properties.get(str(property_id)) or {})
        seized_properties.append(
            {
                "property_id": property_id,
                "property_name": prop.get("name") or f"Property {property_id}",
                "region": prop.get("region"),
                "board_position": prop.get("board_position"),
                "current_value": float(prop.get("current_value") or prop.get("base_price", 0) or 0),
                "entrenchment": int(entry.get("plot_entrenchment", 0) or 0),
                "supply_yield": int(entry.get("plot_supply_yield", 0) or 0),
                "cluster_id": entry.get("plot_cluster_id"),
                "blockaded": bool(entry.get("plot_blockaded")),
                "reintegration_progress": int(entry.get("plot_reintegration_progress", 0) or 0),
            }
        )

    victory = dict(plot.get("victory_countdown") or {})
    victory["countdown_eligible"] = bool(
        current_round >= 9
        and committed_ids
        and len(entrenched_clusters) >= 2
        and float(plot.get("heat", 0) or 0) < 85
        and int(plot.get("first_seizure_round", 0) or 0) != current_round
        and (control_percent >= 30.0 or (len(seized_ids) >= 8 and len(seized_regions) >= 2))
    )
    if float(plot.get("heat", 0) or 0) >= 85:
        victory["blocked_reason"] = "Heat is too high to start the victory countdown."

    plot_snapshot = {
        **plot,
        "stage_name": PLOT_STAGE_NAMES.get(int(plot.get("stage", 0) or 0), PLOT_STAGE_NAMES[0]),
        "member_ids": member_ids,
        "committed_member_ids": committed_ids,
        "cadre_ids": cadre_ids,
        "coalition_member_ids": coalition_ids,
        "eligible_players": eligible_players,
        "recruitable_players": [entry for entry in eligible_players if entry.get("recruitable")],
        "join_invites": {str(key): dict(value) for key, value in (plot.get("join_invites") or {}).items()},
        "seized_property_ids": seized_ids,
        "seized_properties": seized_properties,
        "seized_region_names": seized_regions,
        "legal_targets": sorted(legal_targets, key=lambda entry: (entry.get("region") or "", int(entry.get("board_position", 0) or 0))),
        "clusters": sorted(cluster_summaries, key=lambda entry: entry.get("cluster_id") or ""),
        "victory_countdown": victory,
        "action_catalog": [
            {"action_type": action_type, **definition}
            for action_type, definition in PLOT_ACTION_DEFS.items()
        ],
        "counter_action_catalog": [
            {"action_type": action_type, **definition}
            for action_type, definition in COUNTER_ACTION_DEFS.items()
        ],
    }

    next_state = _set_social_properties(next_state, social_properties, plot_snapshot)
    return next_state


def seed_debug_communist_plot_state(game_state: dict, *, revolutionary_player_id: int) -> tuple[dict, dict]:
    next_state = _refresh_state(game_state)
    player_lookup = _player_index(next_state)
    founder = player_lookup.get(int(revolutionary_player_id))
    if founder is None or founder.get("is_bankrupt"):
        raise ValueError("The selected revolutionary must be an active non-bankrupt player.")

    active_players = [player for player in _active_players(next_state) if int(player.get("id") or 0) != int(revolutionary_player_id)]
    if not active_players:
        raise ValueError("The debug communist plot scenario needs at least one rival player in the match.")
    fallback_rival = max(
        active_players,
        key=lambda player: float(player.get("balance", 0) or 0),
    )

    active_player_ids = {int(player.get("id") or 0) for player in _active_players(next_state)}
    ownable_properties = [
        dict(prop)
        for prop in _ownable_properties(next_state)
        if int(prop.get("owner_id") or 0) != int(revolutionary_player_id)
    ]
    if not ownable_properties:
        raise ValueError("The board has no ownable properties available for the debug communist plot scenario.")

    current_round = max(7, _game_round(next_state))
    next_state["current_round"] = current_round
    next_state["current_player_id"] = int(revolutionary_player_id)
    next_state["dice_rolled_this_turn"] = False
    next_state["awaiting_end_turn_player_id"] = None
    next_state["pending_action"] = None

    ownable_by_position = {
        int(prop.get("board_position", -1) or -1): prop
        for prop in ownable_properties
        if prop.get("board_position") is not None
    }
    seized_targets: list[dict] = []
    for candidate in sorted(ownable_properties, key=lambda item: (-float(item.get("current_value") or item.get("base_price", 0) or 0), int(item.get("board_position", 0) or 0))):
        candidate_position = int(candidate.get("board_position", -1) or -1)
        for neighbor_position in _neighbor_positions(candidate_position):
            neighbor = ownable_by_position.get(neighbor_position)
            if neighbor is None:
                continue
            seized_targets = [candidate, neighbor]
            break
        if seized_targets:
            break
    if not seized_targets:
        seized_targets = [max(ownable_properties, key=lambda item: float(item.get("current_value") or item.get("base_price", 0) or 0))]

    seized_target_ids = {int(prop.get("id") or 0) for prop in seized_targets}
    adjacent_positions = {
        neighbor_position
        for target in seized_targets
        for neighbor_position in _neighbor_positions(int(target.get("board_position", -1) or -1))
    }
    agitation_target = next(
        (
            prop
            for prop in sorted(ownable_properties, key=lambda item: int(item.get("board_position", 0) or 0))
            if int(prop.get("id") or 0) not in seized_target_ids
            and (
                str(prop.get("region") or "") == str(seized_targets[0].get("region") or "")
                or int(prop.get("board_position", -1) or -1) in adjacent_positions
            )
        ),
        None,
    )

    social_properties = _social_properties(next_state)
    properties_by_id = _property_index(next_state)
    plot_regions = {}
    for prop in seized_targets:
        region = str(prop.get("region") or "Unassigned")
        region_state = _coerce_region(plot_regions.get(region))
        region_state["seeded_cells"] = max(1, int(region_state.get("seeded_cells", 0) or 0) + 1)
        plot_regions[region] = region_state
    if agitation_target is not None:
        region = str(agitation_target.get("region") or "Unassigned")
        region_state = _coerce_region(plot_regions.get(region))
        region_state["seeded_cells"] = max(1, int(region_state.get("seeded_cells", 0) or 0))
        plot_regions[region] = region_state

    plot = _coerce_plot_state(
        {
            "exists": True,
            "founder_id": int(revolutionary_player_id),
            "public": True,
            "stage": 3,
            "created_round": current_round - 3,
            "public_round": current_round - 1,
            "support": 16.0,
            "supply": 9.0,
            "heat": 31.0,
            "support_generated_total": 22.0,
            "first_seizure_round": current_round - 1,
            "coalition_unlocked": True,
            "stage_advanced_round": current_round - 1,
            "last_successful_action_round": current_round - 1,
            "last_recruitment_round": current_round - 2,
            "last_mutual_aid_round": current_round - 2,
            "last_aggression_round": current_round - 1,
            "members": {
                str(int(revolutionary_player_id)): {
                    "player_id": int(revolutionary_player_id),
                    "role": "committed_member",
                    "is_founder": True,
                    "joined_round": current_round - 3,
                    "contribution_rounds": [current_round - 3, current_round - 2, current_round - 1],
                    "required_contribution_rounds": 1,
                    "required_successful_actions": 1,
                    "successful_actions_supported": 2,
                    "active": True,
                },
            },
            "regions": plot_regions,
            "action_history": [
                {
                    "action_type": "debug_seed",
                    "player_id": int(revolutionary_player_id),
                    "round": current_round,
                    "success": True,
                    "summary": "Host seeded a debug communist plot scenario.",
                },
            ],
            "victory_countdown": dict(_plot_defaults()["victory_countdown"]),
        },
        current_round,
    )

    property_updates: dict[int, dict] = {}
    former_owner_ids: list[int] = []
    for index, prop in enumerate(sorted(seized_targets, key=lambda item: int(item.get("board_position", 0) or 0))):
        property_id = int(prop.get("id") or 0)
        original_prop = properties_by_id.get(property_id) or {}
        assigned_owner_id = original_prop.get("owner_id")
        if not isinstance(assigned_owner_id, int) or int(assigned_owner_id or 0) == int(revolutionary_player_id):
            assigned_owner_id = int(fallback_rival.get("id") or 0)
        former_owner_ids.append(int(assigned_owner_id or 0))
        entry = dict(social_properties.get(str(property_id)) or {})
        entry.update(
            {
                "plot_seized": True,
                "plot_former_owner_id": assigned_owner_id,
                "plot_entrenchment": 2 if index == 0 else 1,
                "plot_seized_round": current_round - 1,
                "plot_reintegration_progress": 0,
                "plot_reintegration_pushes": 0,
                "plot_agitation": max(3, int(entry.get("plot_agitation", 0) or 0)),
                "plot_blockaded_until_round": 0,
                "plot_contested": False,
                "plot_last_spread_round": current_round - 1,
            }
        )
        social_properties[str(property_id)] = entry
        property_updates[property_id] = {
            "owner_id": COMMUNIST_PLOT_OWNER_ID,
            "current_value": float(original_prop.get("current_value") or original_prop.get("base_price", 0) or 0),
        }

    if agitation_target is not None:
        agitation_id = int(agitation_target.get("id") or 0)
        entry = dict(social_properties.get(str(agitation_id)) or {})
        entry["plot_agitation"] = max(3, int(entry.get("plot_agitation", 0) or 0))
        social_properties[str(agitation_id)] = entry

    updated_players = []
    founder_balance = min(float(founder.get("balance", 0) or 0), 180.0)
    if founder_balance <= 0:
        founder_balance = 180.0
    for player in next_state.get("players", []):
        next_player = dict(player)
        player_id = int(next_player.get("id") or 0)
        if player_id == int(revolutionary_player_id):
            next_player["balance"] = founder_balance
        elif player_id in former_owner_ids:
            next_player["balance"] = max(float(next_player.get("balance", 0) or 0), founder_balance + 500.0)
        updated_players.append(next_player)
    next_state["players"] = updated_players

    next_state = _apply_plot_updates(next_state, plot, social_properties, property_updates=property_updates)
    refreshed_plot = _get_plot(next_state)
    seized_names = [prop.get("name") or f"Property {int(prop.get('id') or 0)}" for prop in seized_targets]
    return next_state, {
        "summary": f"Debug communist plot seeded for {founder.get('username', 'the host')} with seized territory: {', '.join(seized_names)}.",
        "revolutionary_player_id": int(revolutionary_player_id),
        "seized_property_ids": sorted(seized_target_ids),
        "plot": refreshed_plot,
    }


def _apply_plot_updates(game_state: dict, plot: dict, social_properties: dict[str, dict], *, property_updates: dict[int, dict] | None = None) -> dict:
    next_state = dict(game_state)
    if property_updates:
        updated_properties = []
        for prop in next_state.get("properties", []):
            if int(prop.get("id") or 0) in property_updates:
                updated_properties.append({**dict(prop), **dict(property_updates[int(prop.get("id") or 0)])})
            else:
                updated_properties.append(dict(prop))
        next_state["properties"] = updated_properties
    next_state = _set_social_properties(next_state, social_properties, plot)
    return _refresh_state(next_state)


def _require_plot_exists(plot: dict) -> None:
    if not plot.get("exists"):
        raise ValueError("There is no active communist plot in this match.")


def _require_plot_member(plot: dict, player_id: int) -> dict:
    member = dict((plot.get("members") or {}).get(str(player_id)) or {})
    if not member or not member.get("active", True):
        raise ValueError("Only communist plot members can use that action.")
    return member


def _normalize_region(payload: dict, prop: dict | None = None) -> str | None:
    region = payload.get("region") or payload.get("target_region")
    if region:
        return str(region)
    if prop is not None:
        value = prop.get("region")
        if value:
            return str(value)
    return None


def start_communist_plot(game_state: dict, *, player_id: int) -> tuple[dict, dict]:
    next_state = _refresh_state(game_state)
    current_round = _game_round(next_state)
    plot = _coerce_plot_state(_get_plot(next_state), current_round)
    player_lookup = _player_index(next_state)
    player = player_lookup.get(player_id)
    if player is None or player.get("is_bankrupt"):
        raise ValueError("Only active non-bankrupt players can found the communist plot.")
    if plot.get("exists"):
        raise ValueError("Only one communist plot may exist in a match.")
    if current_round < 4:
        raise ValueError("The communist plot only unlocks from round 4 onward.")
    if not bool(player.get("plot_can_found", False)):
        raise ValueError("This player does not meet the hardship requirements to found the communist plot.")

    hardship_score = int(player.get("plot_hardship_score", 0) or 0)
    initial_support = min(8, 4 + hardship_score)
    member = _member_defaults(player_id, current_round, is_founder=True)
    member["successful_actions_supported"] = 1

    plot.update(
        {
            "exists": True,
            "founder_id": player_id,
            "stage": 1,
            "stage_name": PLOT_STAGE_NAMES[1],
            "created_round": current_round,
            "support": _round(initial_support, 2),
            "support_generated_total": _round(initial_support, 2),
            "heat": 0.0,
            "supply": 0.0,
            "members": {str(player_id): member},
            "join_invites": {},
            "cooldowns": {},
            "regions": {},
            "public": False,
            "public_round": None,
            "first_seizure_round": None,
            "coalition_unlocked": False,
            "recruitment_slowdown_until_round": 0,
            "recent_backlash_support": 0.0,
            "victory_countdown": dict(_plot_defaults()["victory_countdown"]),
        }
    )
    plot = _append_history(
        plot,
        action_type="plot_start",
        player_id=player_id,
        current_round=current_round,
        success=True,
        summary=f"{player.get('username', 'Player')} founded the communist plot underground.",
    )

    next_state = _set_social_properties(next_state, _social_properties(next_state), plot)
    next_state = _refresh_state(next_state)
    refreshed_plot = _get_plot(next_state)
    return next_state, {
        "action_type": "plot_start",
        "summary": f"{player.get('username', 'Player')} founded the communist plot with {initial_support} starting Support.",
        "plot": refreshed_plot,
    }


def _mark_member_action(plot: dict, player_id: int, *, success: bool = True, aggressive: bool = False, recruited: bool = False, mutual_aid: bool = False) -> dict:
    updated_plot = dict(plot)
    current_round = _game_round({"current_round": plot.get("created_round") or 1})
    members = {str(key): dict(value) for key, value in (updated_plot.get("members") or {}).items()}
    member = dict(members.get(str(player_id)) or {})
    if member:
        if success:
            member["successful_actions_supported"] = int(member.get("successful_actions_supported", 0) or 0) + 1
        members[str(player_id)] = member
        updated_plot["members"] = members
    if success:
        updated_plot["last_successful_action_round"] = current_round
    if aggressive:
        updated_plot["last_aggression_round"] = current_round
    if recruited:
        updated_plot["last_recruitment_round"] = current_round
    if mutual_aid:
        updated_plot["last_mutual_aid_round"] = current_round
    return updated_plot


def _current_round_from_plot(plot: dict, fallback: int) -> int:
    return max(fallback, int(plot.get("created_round", fallback) or fallback))


def submit_plot_action(game_state: dict, *, player_id: int, action_type: str, payload: dict | None = None) -> tuple[dict, dict]:
    payload = dict(payload or {})
    next_state = _refresh_state(game_state)
    current_round = _game_round(next_state)
    plot = _coerce_plot_state(_get_plot(next_state), current_round)
    _require_plot_exists(plot)
    member = _require_plot_member(plot, player_id)
    action_def = PLOT_ACTION_DEFS.get(action_type)
    if action_def is None:
        raise ValueError("Unknown plot action.")
    if int(plot.get("stage", 0) or 0) < int(action_def.get("stage", 0) or 0):
        raise ValueError("That plot action has not unlocked yet.")
    if member.get("role") == "sympathizer":
        raise ValueError("Sympathizers must organize further before taking direct actions.")

    social_properties = _social_properties(next_state)
    properties_by_id = _property_index(next_state)
    property_id = int(payload.get("property_id") or 0) if payload.get("property_id") is not None else None
    target_player_id = int(payload.get("target_player_id") or payload.get("player_id") or 0) if payload.get("target_player_id") is not None or payload.get("player_id") is not None else None
    prop = properties_by_id.get(property_id or 0)
    region = _normalize_region(payload, prop)
    cluster_id = payload.get("cluster_id")
    if not cluster_id and prop is not None:
        cluster_id = (social_properties.get(str(prop.get("id"))) or {}).get("plot_cluster_id")

    cooldown_scope = str(action_def.get("cooldown_scope") or "")
    _assert_cooldown_available(
        plot,
        action_type,
        current_round=current_round,
        region=region if cooldown_scope == "region" else None,
        property_id=property_id if cooldown_scope == "property" else None,
        cluster_id=cluster_id if cooldown_scope == "cluster" else None,
        target_player_id=target_player_id if cooldown_scope == "target" else None,
    )
    plot = _spend_plot_cost(plot, action_def.get("cost") or {})

    summary = ""
    property_updates: dict[int, dict] = {}
    success = True

    if action_type == "mutual_aid":
        if not region:
            raise ValueError("Mutual aid requires a target region.")
        region_state = _coerce_region((plot.get("regions") or {}).get(region))
        region_state["mutual_aid_until_round"] = current_round
        region_state["aid_bonus_until_round"] = current_round + 1
        plot_regions = dict(plot.get("regions") or {})
        plot_regions[region] = region_state
        plot["regions"] = plot_regions
        plot = _add_support(plot, 4)
        plot = _add_heat(plot, -4)
        plot["last_mutual_aid_round"] = current_round
        summary = f"Mutual aid strengthened the faction in {region}."
    elif action_type == "whisper_campaign":
        if prop is None and not region:
            raise ValueError("Whisper campaigns need a target property or region.")
        if prop is not None:
            entry = dict(social_properties.get(str(prop.get("id"))) or {})
            entry["plot_agitation"] = int(entry.get("plot_agitation", 0) or 0) + 1
            social_properties[str(prop.get("id"))] = entry
            summary = f"Whisper campaigns intensified around {prop.get('name', 'the property')}."
        else:
            region_state = _coerce_region((plot.get("regions") or {}).get(region))
            region_state["seeded_cells"] = max(1, int(region_state.get("seeded_cells", 0) or 0))
            plot_regions = dict(plot.get("regions") or {})
            plot_regions[region] = region_state
            plot["regions"] = plot_regions
            summary = f"Whisper campaigns expanded the underground network in {region}."
    elif action_type == "establish_safehouse":
        if not region:
            raise ValueError("A region is required for a safehouse.")
        region_state = _coerce_region((plot.get("regions") or {}).get(region))
        region_state["safehouse_until_round"] = current_round + 2
        plot_regions = dict(plot.get("regions") or {})
        plot_regions[region] = region_state
        plot["regions"] = plot_regions
        plot = _add_heat(plot, -6)
        summary = f"A safehouse was established in {region}."
    elif action_type == "seed_cell":
        if not region:
            raise ValueError("A region is required to seed a cell.")
        region_state = _coerce_region((plot.get("regions") or {}).get(region))
        region_state["seeded_cells"] = int(region_state.get("seeded_cells", 0) or 0) + 1
        plot_regions = dict(plot.get("regions") or {})
        plot_regions[region] = region_state
        plot["regions"] = plot_regions
        summary = f"A new underground cell was seeded in {region}."
    elif action_type in {"recruit_sympathizer", "recruit_publicly"}:
        if target_player_id is None:
            raise ValueError("Recruitment requires a target player.")
        target_player = _player_index(next_state).get(target_player_id)
        if target_player is None or target_player.get("is_bankrupt"):
            raise ValueError("That player cannot be recruited.")
        if str(target_player_id) in (plot.get("members") or {}):
            raise ValueError("That player is already aligned with the plot.")
        if action_type == "recruit_publicly":
            plot = _add_heat(plot, 8)
        if int(plot.get("recruitment_slowdown_until_round", 0) or 0) >= current_round:
            plot = _add_support(plot, -1)
        invites = dict(plot.get("join_invites") or {})
        invites[str(target_player_id)] = {
            "player_id": target_player_id,
            "invited_by": player_id,
            "round": current_round,
            "public": action_type == "recruit_publicly" or bool(plot.get("public")),
        }
        plot["join_invites"] = invites
        plot["last_recruitment_round"] = current_round
        summary = f"{target_player.get('username', 'A player')} is now a recruitment target for the communist plot."
    elif action_type == "convert_to_organizer":
        if target_player_id is None:
            raise ValueError("Select a sympathizer to convert.")
        target_member = dict((plot.get("members") or {}).get(str(target_player_id)) or {})
        if target_member.get("role") != "sympathizer":
            raise ValueError("Only sympathizers can be promoted to organizer.")
        if len(target_member.get("contribution_rounds") or []) < int(target_member.get("required_contribution_rounds", 2) or 2):
            raise ValueError("That sympathizer has not contributed across enough rounds yet.")
        target_member["role"] = "organizer"
        members = {str(key): dict(value) for key, value in (plot.get("members") or {}).items()}
        members[str(target_player_id)] = target_member
        plot["members"] = members
        summary = f"{(_player_index(next_state).get(target_player_id) or {}).get('username', 'A player')} was converted into an organizer."
    elif action_type == "agitate_property":
        if prop is None:
            raise ValueError("Agitation requires a target property.")
        entry = dict(social_properties.get(str(prop.get("id"))) or {})
        entry["plot_agitation"] = int(entry.get("plot_agitation", 0) or 0) + 2
        social_properties[str(prop.get("id"))] = entry
        plot = _add_heat(plot, 2)
        summary = f"Agitation escalated around {prop.get('name', 'the target property')}."
    elif action_type == "sabotage_development":
        if prop is None:
            raise ValueError("Sabotage requires a target property.")
        entry = dict(social_properties.get(str(prop.get("id"))) or {})
        entry["plot_sabotaged_until_round"] = current_round + 2
        entry["plot_agitation"] = int(entry.get("plot_agitation", 0) or 0) + 1
        social_properties[str(prop.get("id"))] = entry
        plot = _add_heat(plot, 4)
        summary = f"Sabotage disrupted operations around {prop.get('name', 'the target property')}."
    elif action_type == "hide_assets":
        if not region:
            raise ValueError("Hide Assets requires a target region.")
        region_state = _coerce_region((plot.get("regions") or {}).get(region))
        region_state["hidden_assets_until_round"] = current_round + 2
        plot_regions = dict(plot.get("regions") or {})
        plot_regions[region] = region_state
        plot["regions"] = plot_regions
        plot = _add_heat(plot, -8)
        summary = f"Underground assets were hidden in {region}."
    elif action_type == "stockpile_supply":
        plot = _add_supply(plot, 3)
        plot["last_stockpile_round"] = current_round
        plot = _add_heat(plot, 2)
        summary = "The faction stockpiled revolutionary supply."
    elif action_type == "attempt_seizure":
        if prop is None:
            raise ValueError("Select a property to seize.")
        legal_target_ids = {int(entry.get("property_id") or 0) for entry in (plot.get("legal_targets") or [])}
        if int(prop.get("id") or 0) not in legal_target_ids:
            raise ValueError("That property is not currently a legal seizure target.")
        entry = dict(social_properties.get(str(prop.get("id"))) or {})
        score = _seizure_score(next_state, plot, prop, entry, supply_commitment=int(payload.get("supply_commitment", 0) or 0))
        threshold = 10
        plot = _add_heat(plot, 10)
        plot["last_aggression_round"] = current_round
        if score >= threshold:
            entry["plot_seized"] = True
            entry["plot_former_owner_id"] = prop.get("owner_id")
            entry["plot_entrenchment"] = max(1, int(entry.get("plot_entrenchment", 0) or 0))
            entry["plot_seized_round"] = current_round
            entry["plot_reintegration_progress"] = 0
            entry["plot_reintegration_pushes"] = 0
            entry["plot_blockaded_until_round"] = 0
            entry["plot_contested"] = False
            social_properties[str(prop.get("id"))] = entry
            property_updates[int(prop.get("id") or 0)] = {"owner_id": COMMUNIST_PLOT_OWNER_ID}
            if not plot.get("first_seizure_round"):
                plot["first_seizure_round"] = current_round
            plot["coalition_unlocked"] = True
            plot = _add_support(plot, 2)
            summary = f"The faction seized {prop.get('name', 'the target property')} with a deterministic score of {score}."
        else:
            success = False
            entry["plot_seizure_lockout_until_round"] = current_round + 2
            social_properties[str(prop.get("id"))] = entry
            plot = _add_heat(plot, 6)
            summary = f"The seizure attempt on {prop.get('name', 'the target property')} failed at score {score}."
    elif action_type == "fortify_property":
        if prop is None:
            raise ValueError("Choose a seized property to fortify.")
        entry = dict(social_properties.get(str(prop.get("id"))) or {})
        if not entry.get("plot_seized"):
            raise ValueError("Only seized properties can be fortified.")
        entry["plot_entrenchment"] = min(3, int(entry.get("plot_entrenchment", 0) or 0) + 1)
        social_properties[str(prop.get("id"))] = entry
        summary = f"{prop.get('name', 'The property')} was fortified."
    elif action_type == "spread_to_adjacent_territory":
        if not cluster_id:
            raise ValueError("Spread requires a source cluster.")
        cluster = next((entry for entry in (plot.get("clusters") or []) if entry.get("cluster_id") == cluster_id), None)
        if not cluster:
            raise ValueError("That seized cluster no longer exists.")
        target_ids = []
        for seized_property_id in cluster.get("property_ids") or []:
            source_prop = properties_by_id.get(int(seized_property_id) or 0)
            if source_prop is None:
                continue
            for neighbor_position in _neighbor_positions(int(source_prop.get("board_position", -1) or -1)):
                neighbor_prop = next((candidate for candidate in properties_by_id.values() if int(candidate.get("board_position", -1) or -1) == neighbor_position), None)
                if neighbor_prop is None:
                    continue
                target_ids.append(int(neighbor_prop.get("id") or 0))
        for target_id in sorted(set(target_ids)):
            entry = dict(social_properties.get(str(target_id)) or {})
            entry["plot_agitation"] = int(entry.get("plot_agitation", 0) or 0) + 2
            entry["plot_last_spread_round"] = current_round
            social_properties[str(target_id)] = entry
        summary = f"The plot spread agitation outward from {cluster_id}."
    elif action_type == "call_emergency_redistribution":
        if not region:
            raise ValueError("Emergency redistribution requires a target region.")
        plot = _add_support(plot, 5)
        plot = _add_heat(plot, 5)
        region_state = _coerce_region((plot.get("regions") or {}).get(region))
        region_state["aid_bonus_until_round"] = current_round + 1
        plot_regions = dict(plot.get("regions") or {})
        plot_regions[region] = region_state
        plot["regions"] = plot_regions
        summary = f"Emergency redistribution shored up support in {region}."
    elif action_type == "establish_regional_council":
        if not region:
            raise ValueError("A region is required to establish a council.")
        region_state = _coerce_region((plot.get("regions") or {}).get(region))
        region_state["council_established_round"] = current_round
        plot_regions = dict(plot.get("regions") or {})
        plot_regions[region] = region_state
        plot["regions"] = plot_regions
        summary = f"A regional council was established in {region}."
    elif action_type == "increase_entrenchment":
        if not cluster_id:
            raise ValueError("Entrenchment scaling requires a cluster.")
        cluster = next((entry for entry in (plot.get("clusters") or []) if entry.get("cluster_id") == cluster_id), None)
        if not cluster:
            raise ValueError("That seized cluster no longer exists.")
        for seized_property_id in cluster.get("property_ids") or []:
            entry = dict(social_properties.get(str(seized_property_id)) or {})
            entry["plot_entrenchment"] = min(3, int(entry.get("plot_entrenchment", 0) or 0) + 1)
            social_properties[str(seized_property_id)] = entry
        summary = f"Entrenchment was increased across {cluster_id}."
    elif action_type == "redirect_supply_between_regions":
        source_region = str(payload.get("source_region") or "")
        target_region = str(payload.get("target_region") or "")
        if not source_region or not target_region:
            raise ValueError("Redirecting supply needs a source and target region.")
        plot_regions = dict(plot.get("regions") or {})
        target_state = _coerce_region(plot_regions.get(target_region))
        target_state["defense_reserve"] = _round(float(target_state.get("defense_reserve", 0) or 0) + 2.0, 2)
        plot_regions[target_region] = target_state
        plot["regions"] = plot_regions
        summary = f"Supply was redirected toward {target_region}."
    elif action_type == "call_mass_action":
        target_region = region
        plot = _add_support(plot, 6)
        plot = _add_heat(plot, 8)
        for property_key, entry in list(social_properties.items()):
            prop_region = str(entry.get("region") or (properties_by_id.get(int(property_key) or 0) or {}).get("region") or "")
            if target_region and prop_region != target_region:
                continue
            entry = dict(entry)
            entry["plot_agitation"] = int(entry.get("plot_agitation", 0) or 0) + 1
            social_properties[property_key] = entry
        summary = "The plot called a mass action and shook the board."
    elif action_type == "defend_reintegration":
        if prop is None:
            raise ValueError("Defending reintegration requires a seized property.")
        entry = dict(social_properties.get(str(prop.get("id"))) or {})
        if not entry.get("plot_seized") or int(entry.get("plot_reintegration_progress", 0) or 0) <= 0:
            raise ValueError("That property is not currently under reintegration pressure.")
        entry["plot_reintegration_progress"] = max(0, int(entry.get("plot_reintegration_progress", 0) or 0) - 35)
        entry["plot_entrenchment"] = min(3, int(entry.get("plot_entrenchment", 0) or 0) + 1)
        social_properties[str(prop.get("id"))] = entry
        summary = f"The faction defended {prop.get('name', 'the seized property')} against reintegration."
    else:
        raise ValueError("That plot action is not implemented yet.")

    rounds = int(action_def.get("cooldown_rounds", 0) or 0)
    plot = _set_cooldown(
        plot,
        action_type,
        current_round=current_round,
        rounds=rounds,
        region=region if cooldown_scope == "region" else None,
        property_id=property_id if cooldown_scope == "property" else None,
        cluster_id=cluster_id if cooldown_scope == "cluster" else None,
        target_player_id=target_player_id if cooldown_scope == "target" else None,
    )
    if success:
        plot = _append_history(plot, action_type=action_type, player_id=player_id, current_round=current_round, success=True, summary=summary)
    else:
        plot = _append_history(plot, action_type=action_type, player_id=player_id, current_round=current_round, success=False, summary=summary)

    if action_type in {"attempt_seizure", "spread_to_adjacent_territory", "call_mass_action", "agitate_property", "sabotage_development"}:
        plot["last_aggression_round"] = current_round
    if action_type in {"recruit_sympathizer", "recruit_publicly"}:
        plot["last_recruitment_round"] = current_round
    if action_type == "mutual_aid":
        plot["last_mutual_aid_round"] = current_round

    members = {str(key): dict(value) for key, value in (plot.get("members") or {}).items()}
    actor_member = dict(members.get(str(player_id)) or {})
    if success and actor_member:
        actor_member["successful_actions_supported"] = int(actor_member.get("successful_actions_supported", 0) or 0) + 1
        members[str(player_id)] = actor_member
        plot["members"] = members

    next_state = _apply_plot_updates(next_state, plot, social_properties, property_updates=property_updates)
    return next_state, {
        "action_type": action_type,
        "success": success,
        "summary": summary,
        "plot": _get_plot(next_state),
    }


def submit_plot_join(game_state: dict, *, player_id: int, payload: dict | None = None) -> tuple[dict, dict]:
    payload = dict(payload or {})
    next_state = _refresh_state(game_state)
    current_round = _game_round(next_state)
    plot = _coerce_plot_state(_get_plot(next_state), current_round)
    _require_plot_exists(plot)
    player_lookup = _player_index(next_state)
    player = player_lookup.get(player_id)
    if player is None or player.get("is_bankrupt"):
        raise ValueError("Only active players may join the communist plot.")

    intent = str(payload.get("intent") or "accept").strip().lower()
    member = dict((plot.get("members") or {}).get(str(player_id)) or {})
    hardship_score = int(player.get("plot_hardship_score", 0) or 0)
    hardship_trigger_count = int(player.get("plot_hardship_trigger_count", 0) or 0)
    invites = dict(plot.get("join_invites") or {})
    invite = dict(invites.get(str(player_id)) or {})

    if intent == "decline":
        if str(player_id) in invites:
            invites.pop(str(player_id), None)
            plot["join_invites"] = invites
        next_state = _set_social_properties(next_state, _social_properties(next_state), plot)
        next_state = _refresh_state(next_state)
        return next_state, {
            "action_type": "plot_join",
            "success": True,
            "summary": f"{player.get('username', 'Player')} declined the plot invitation.",
            "plot": _get_plot(next_state),
        }

    if intent == "accept":
        if not invite and not plot.get("public"):
            raise ValueError("That player has not been invited into the plot.")
        if member:
            raise ValueError("That player is already aligned with the plot.")
        prosperous_entry = hardship_trigger_count < 2
        entry_cost = 150.0 if prosperous_entry else 0.0
        if entry_cost > 0:
            if float(player.get("balance", 0) or 0) < entry_cost:
                raise ValueError("Prosperous players must pay a higher political cost to join, and this player cannot afford it.")
            next_state, _ = spend_player_balance(next_state, player_id, entry_cost)
            player_lookup = _player_index(next_state)
            player = player_lookup.get(player_id) or player
        new_member = _member_defaults(player_id, current_round)
        new_member["prosperous_entry"] = prosperous_entry
        new_member["required_contribution_rounds"] = 4 if prosperous_entry else 2
        new_member["required_successful_actions"] = 2 if prosperous_entry else 1
        new_member["cash_contributed"] = entry_cost
        new_member["contribution_rounds"] = [current_round]
        members = {str(key): dict(value) for key, value in (plot.get("members") or {}).items()}
        members[str(player_id)] = new_member
        plot["members"] = members
        if str(player_id) in invites:
            invites.pop(str(player_id), None)
            plot["join_invites"] = invites
        plot = _add_support(plot, 2)
        plot["last_recruitment_round"] = current_round
        plot = _append_history(
            plot,
            action_type="plot_join",
            player_id=player_id,
            current_round=current_round,
            success=True,
            summary=f"{player.get('username', 'Player')} joined the plot as a sympathizer.",
        )
        next_state = _set_social_properties(next_state, _social_properties(next_state), plot)
        next_state = _refresh_state(next_state)
        return next_state, {
            "action_type": "plot_join",
            "success": True,
            "summary": f"{player.get('username', 'Player')} joined the communist plot.",
            "plot": _get_plot(next_state),
        }

    if not member:
        raise ValueError("Only existing members can use that membership action.")

    if intent == "contribute":
        contribution_cost = float(payload.get("amount", 0) or 0)
        if contribution_cost <= 0:
            contribution_cost = 100.0 if bool(member.get("prosperous_entry")) else 50.0
        if current_round in set(member.get("contribution_rounds") or []):
            raise ValueError("A member may only make one major contribution per round.")
        if float(player.get("balance", 0) or 0) < contribution_cost:
            raise ValueError("That player cannot afford the requested contribution.")
        next_state, _ = spend_player_balance(next_state, player_id, contribution_cost)
        player_lookup = _player_index(next_state)
        player = player_lookup.get(player_id) or player
        member["contribution_rounds"] = sorted(set([*(member.get("contribution_rounds") or []), current_round]))
        member["cash_contributed"] = _round(float(member.get("cash_contributed", 0) or 0) + contribution_cost, 2)
        member["support_contributed"] = _round(float(member.get("support_contributed", 0) or 0) + 1.0, 2)
        if plot.get("public") and member.get("role") in {"organizer", "committed_member", "cadre", "founder"}:
            member["supply_contributed"] = _round(float(member.get("supply_contributed", 0) or 0) + 1.0, 2)
            plot = _add_supply(plot, 1)
        members = {str(key): dict(value) for key, value in (plot.get("members") or {}).items()}
        members[str(player_id)] = member
        plot["members"] = members
        plot = _add_support(plot, 1)
        plot = _append_history(
            plot,
            action_type="plot_contribution",
            player_id=player_id,
            current_round=current_round,
            success=True,
            summary=f"{player.get('username', 'Player')} made a political contribution to the plot.",
        )
        next_state = _set_social_properties(next_state, _social_properties(next_state), plot)
        next_state = _refresh_state(next_state)
        return next_state, {
            "action_type": "plot_contribution",
            "success": True,
            "summary": f"{player.get('username', 'Player')} contributed to the communist plot.",
            "plot": _get_plot(next_state),
        }

    if intent == "commit":
        if member.get("role") not in {"organizer", "founder", "committed_member", "cadre"}:
            raise ValueError("Only organizers and above can commit fully to the plot.")
        enough_contributions = len(member.get("contribution_rounds") or []) >= int(member.get("required_contribution_rounds", 2) or 2)
        enough_actions = int(member.get("successful_actions_supported", 0) or 0) >= int(member.get("required_successful_actions", 1) or 1)
        if not enough_contributions or not enough_actions:
            raise ValueError("That member has not yet done enough work to become committed.")
        member["role"] = "committed_member"
        members = {str(key): dict(value) for key, value in (plot.get("members") or {}).items()}
        members[str(player_id)] = member
        plot["members"] = members
        plot = _append_history(
            plot,
            action_type="plot_commitment",
            player_id=player_id,
            current_round=current_round,
            success=True,
            summary=f"{player.get('username', 'Player')} became a committed communist member.",
        )
        next_state = _set_social_properties(next_state, _social_properties(next_state), plot)
        next_state = _refresh_state(next_state)
        return next_state, {
            "action_type": "plot_commitment",
            "success": True,
            "summary": f"{player.get('username', 'Player')} is now a committed communist member.",
            "plot": _get_plot(next_state),
        }

    raise ValueError("Unknown plot membership action.")


def submit_plot_leave(game_state: dict, *, player_id: int) -> tuple[dict, dict]:
    next_state = _refresh_state(game_state)
    current_round = _game_round(next_state)
    plot = _coerce_plot_state(_get_plot(next_state), current_round)
    _require_plot_exists(plot)
    member = _require_plot_member(plot, player_id)
    members = {str(key): dict(value) for key, value in (plot.get("members") or {}).items()}
    departing = dict(members.get(str(player_id)) or member)
    departing["active"] = False
    departing["defection_cooldown_until"] = current_round + 3
    members[str(player_id)] = departing
    plot["members"] = members
    plot = _add_support(plot, -2)
    plot = _add_heat(plot, 6)
    victory = dict(plot.get("victory_countdown") or {})
    if bool(victory.get("active")) and member.get("role") in {"committed_member", "cadre", "founder"}:
        victory["rounds_held"] = max(0, int(victory.get("rounds_held", 0) or 0) - 1)
        if int(victory.get("rounds_held", 0) or 0) == 0:
            victory["active"] = False
        plot["victory_countdown"] = victory

    plot = _append_history(
        plot,
        action_type="plot_leave",
        player_id=player_id,
        current_round=current_round,
        success=True,
        summary=f"{(_player_index(next_state).get(player_id) or {}).get('username', 'A player')} defected from the communist plot.",
    )
    next_state = _set_social_properties(next_state, _social_properties(next_state), plot)
    next_state = _refresh_state(next_state)
    if not (_get_plot(next_state).get("member_ids") or []):
        next_state = _dissolve_plot(next_state, reason="The communist plot lost all of its active members and collapsed.")
    return next_state, {
        "action_type": "plot_leave",
        "success": True,
        "summary": f"{(_player_index(next_state).get(player_id) or {}).get('username', 'A player')} left the communist plot.",
        "plot": _get_plot(next_state),
    }


def _deduct_cash_contributions(game_state: dict, *, contributors: list[dict], default_player_id: int, minimum_total: float, coalition_member_ids: set[int]) -> tuple[dict, list[dict]]:
    next_state = dict(game_state)
    normalized = []
    if not contributors:
        normalized = [{"player_id": default_player_id, "amount": minimum_total}]
    else:
        for entry in contributors:
            player_id = int(entry.get("player_id") or 0)
            amount = float(entry.get("amount", 0) or 0)
            if player_id <= 0 or amount <= 0:
                continue
            normalized.append({"player_id": player_id, "amount": amount})
    if sum(entry["amount"] for entry in normalized) < minimum_total:
        raise ValueError("The coalition did not pool enough cash for that action.")
    for entry in normalized:
        if entry["player_id"] not in coalition_member_ids and entry["player_id"] != default_player_id:
            raise ValueError("Only coalition members may pool funds for coalition actions.")
        player = (_player_index(next_state).get(entry["player_id"]) or {})
        if float(player.get("balance", 0) or 0) < float(entry["amount"] or 0):
            raise ValueError("One coalition contributor cannot afford their share.")
        next_state, _ = spend_player_balance(next_state, entry["player_id"], float(entry["amount"] or 0))
    return next_state, normalized


def _consume_supporter_commitments(next_state: dict, supporter_ids: list[int], coalition_member_ids: set[int], current_round: int, required_count: int) -> dict:
    if required_count <= 0:
        return next_state
    unique_supporters = []
    for supporter_id in supporter_ids:
        if supporter_id not in unique_supporters:
            unique_supporters.append(supporter_id)
    if len(unique_supporters) < required_count:
        raise ValueError("That coalition action needs more political commitments from coalition members.")
    for supporter_id in unique_supporters[:required_count]:
        if supporter_id not in coalition_member_ids:
            raise ValueError("Only coalition members may commit support to that counter-action.")
        player = (_player_index(next_state).get(supporter_id) or {})
        if int(player.get("plot_last_counter_commit_round", 0) or 0) >= current_round:
            raise ValueError("One coalition supporter has already committed their counter-action for this round.")
        next_state = _replace_player(next_state, supporter_id, {"plot_last_counter_commit_round": current_round})
    return next_state


def submit_plot_counter_action(game_state: dict, *, player_id: int, action_type: str, payload: dict | None = None) -> tuple[dict, dict]:
    payload = dict(payload or {})
    next_state = _refresh_state(game_state)
    current_round = _game_round(next_state)
    plot = _coerce_plot_state(_get_plot(next_state), current_round)
    _require_plot_exists(plot)
    action_def = COUNTER_ACTION_DEFS.get(action_type)
    if action_def is None:
        raise ValueError("Unknown coalition action.")

    if action_type != "join_coalition" and not bool(plot.get("coalition_unlocked")):
        raise ValueError("Coalition counterplay unlocks only after the first public seizure.")

    properties_by_id = _property_index(next_state)
    social_properties = _social_properties(next_state)
    property_id = int(payload.get("property_id") or 0) if payload.get("property_id") is not None else None
    prop = properties_by_id.get(property_id or 0)
    region = _normalize_region(payload, prop)
    cluster_id = payload.get("cluster_id")
    coalition_member_ids = set(int(player_id_value) for player_id_value in (plot.get("coalition_member_ids") or []))
    supporter_ids = [int(value) for value in (payload.get("supporter_ids") or []) if value is not None]

    if action_type == "join_coalition":
        if str(player_id) in (plot.get("members") or {}):
            raise ValueError("Communist plot members cannot join the anti-revolution coalition.")
        coalition_ids = set(int(value) for value in (plot.get("coalition_member_ids") or []))
        coalition_ids.add(player_id)
        plot["coalition_member_ids"] = sorted(coalition_ids)
        plot = _append_history(
            plot,
            action_type="join_coalition",
            player_id=player_id,
            current_round=current_round,
            success=True,
            summary=f"{(_player_index(next_state).get(player_id) or {}).get('username', 'A player')} joined the anti-revolution coalition.",
        )
        next_state = _set_social_properties(next_state, social_properties, plot)
        next_state = _refresh_state(next_state)
        return next_state, {
            "action_type": "join_coalition",
            "success": True,
            "summary": f"{(_player_index(next_state).get(player_id) or {}).get('username', 'A player')} joined the anti-revolution coalition.",
            "plot": _get_plot(next_state),
        }

    if player_id not in coalition_member_ids:
        raise ValueError("Only coalition members may use public counter-actions.")

    next_state, used_contributions = _deduct_cash_contributions(
        next_state,
        contributors=list(payload.get("contributors") or []),
        default_player_id=player_id,
        minimum_total=float(action_def.get("cash_cost", 0) or 0),
        coalition_member_ids=coalition_member_ids,
    )
    next_state = _consume_supporter_commitments(
        next_state,
        supporter_ids,
        coalition_member_ids,
        current_round,
        int(action_def.get("supporters_required", 0) or 0),
    )
    plot = _coerce_plot_state(_get_plot(next_state), current_round)
    social_properties = _social_properties(next_state)

    summary = ""
    property_updates: dict[int, dict] = {}
    region_state = _coerce_region((plot.get("regions") or {}).get(region)) if region else None
    backlash_pressure = int((region_state or {}).get("hardship_pressure", 0) or 0)

    if action_type == "relief_package":
        if not region:
            raise ValueError("Relief packages require a target region.")
        region_state = _coerce_region((plot.get("regions") or {}).get(region))
        region_state["relief_until_round"] = current_round + 2
        region_state["support_suppressed_until_round"] = current_round + 2
        plot_regions = dict(plot.get("regions") or {})
        plot_regions[region] = region_state
        plot["regions"] = plot_regions
        summary = f"The coalition funded relief in {region}."
    elif action_type == "labor_settlement":
        if prop is None:
            raise ValueError("Labor settlement requires a target property.")
        entry = dict(social_properties.get(str(prop.get("id"))) or {})
        entry["plot_agitation"] = max(0, int(entry.get("plot_agitation", 0) or 0) - 2)
        social_properties[str(prop.get("id"))] = entry
        summary = f"The coalition struck a labor settlement around {prop.get('name', 'the target property')}."
    elif action_type == "security_subsidy":
        if prop is None:
            raise ValueError("Security subsidies require a target property.")
        entry = dict(social_properties.get(str(prop.get("id"))) or {})
        entry["plot_security_subsidy_until_round"] = current_round + 2
        social_properties[str(prop.get("id"))] = entry
        if backlash_pressure > 0:
            plot = _add_support(plot, min(3, backlash_pressure))
        summary = f"The coalition hardened {prop.get('name', 'the target property')} against seizure attempts."
    elif action_type == "intelligence_sweep":
        if not region:
            raise ValueError("Intelligence sweeps require a target region.")
        region_state = _coerce_region((plot.get("regions") or {}).get(region))
        success = float(plot.get("heat", 0) or 0) >= 40 or int(region_state.get("seeded_cells", 0) or 0) > 0
        if success:
            region_state["revealed_until_round"] = current_round + 2
            plot_regions = dict(plot.get("regions") or {})
            plot_regions[region] = region_state
            plot["regions"] = plot_regions
            summary = f"The coalition exposed underground activity in {region}."
        else:
            if backlash_pressure > 0:
                plot = _add_support(plot, min(3, backlash_pressure))
            summary = f"The intelligence sweep in {region} backfired and fed local resentment."
        plot = _append_history(plot, action_type="intelligence_sweep", player_id=player_id, current_round=current_round, success=success, summary=summary, extra={"contributors": used_contributions})
        next_state = _apply_plot_updates(next_state, plot, social_properties)
        return next_state, {
            "action_type": action_type,
            "success": success,
            "summary": summary,
            "plot": _get_plot(next_state),
        }
    elif action_type == "blockade_cluster":
        if not cluster_id:
            raise ValueError("Blockading requires a seized cluster.")
        cluster = next((entry for entry in (plot.get("clusters") or []) if entry.get("cluster_id") == cluster_id), None)
        if not cluster:
            raise ValueError("That seized cluster is no longer valid.")
        for target_id in cluster.get("property_ids") or []:
            entry = dict(social_properties.get(str(target_id)) or {})
            entry["plot_blockaded_until_round"] = current_round + 2
            social_properties[str(target_id)] = entry
        summary = f"The coalition blockaded {cluster_id}."
    elif action_type == "reintegration_campaign":
        if prop is None:
            raise ValueError("Reintegration campaigns require a seized property.")
        entry = dict(social_properties.get(str(prop.get("id"))) or {})
        if not entry.get("plot_seized"):
            raise ValueError("Only seized properties can be targeted for reintegration.")
        entry["plot_reintegration_pushes"] = int(entry.get("plot_reintegration_pushes", 0) or 0) + 1
        entry["plot_reintegration_progress"] = min(100, int(entry.get("plot_reintegration_progress", 0) or 0) + 50)
        social_properties[str(prop.get("id"))] = entry
        if backlash_pressure > 0:
            plot = _add_support(plot, min(3, backlash_pressure))
        if int(entry.get("plot_reintegration_pushes", 0) or 0) >= 2 or int(entry.get("plot_reintegration_progress", 0) or 0) >= 100:
            restored_owner = entry.get("plot_former_owner_id")
            property_updates[int(prop.get("id") or 0)] = {"owner_id": restored_owner if restored_owner in _player_index(next_state) else None}
            for key in list(entry.keys()):
                if str(key).startswith("plot_"):
                    entry.pop(key, None)
            social_properties[str(prop.get("id"))] = entry
            summary = f"The coalition reintegrated {prop.get('name', 'the target property')} into private control."
        else:
            summary = f"The coalition pushed reintegration forward on {prop.get('name', 'the target property')}."
    elif action_type == "propaganda_counteroffensive":
        plot["recruitment_slowdown_until_round"] = current_round + 1
        summary = "The coalition slowed public communist recruitment for one round."
    else:
        raise ValueError("That coalition action is not implemented yet.")

    plot = _append_history(
        plot,
        action_type=action_type,
        player_id=player_id,
        current_round=current_round,
        success=True,
        summary=summary,
        extra={"contributors": used_contributions},
    )
    next_state = _apply_plot_updates(next_state, plot, social_properties, property_updates=property_updates)
    return next_state, {
        "action_type": action_type,
        "success": True,
        "summary": summary,
        "plot": _get_plot(next_state),
    }


def calculate_solidarity_levy(prop: dict, game_state: dict) -> dict:
    social_entry = (_social_properties(game_state).get(str(prop.get("id"))) or {})
    if not _is_property_plot_seized(prop, social_entry):
        return {"amount": 0.0, "is_exempt": False, "owner_name": COMMUNIST_PLOT_OWNER_NAME}

    econ = dict(game_state.get("econ") or {})
    if prop.get("property_type") == "transit":
        normal_rent = float(calculate_transit_rent(prop.get("owner_id"), {**game_state, "properties": [{**candidate, "owner_id": social_entry.get("plot_former_owner_id", candidate.get("owner_id"))} if int(candidate.get("id") or 0) == int(prop.get("id") or 0) else candidate for candidate in game_state.get("properties", [])]}) or max(25.0, float(prop.get("base_price", 0) or 0) * 0.125))
    else:
        original_prop = {**prop, "owner_id": social_entry.get("plot_former_owner_id", prop.get("owner_id"))}
        normal_rent = float(calculate_rent_with_dev(original_prop, econ, game_state) or 0)
    entrenchment_bonus = min(60.0, float(social_entry.get("plot_entrenchment", 0) or 0) * 15.0)
    levy_cap = max(80.0, float(prop.get("base_price", 0) or 0) * 0.70)
    amount = _round(min((0.8 * normal_rent) + entrenchment_bonus, levy_cap), 2)
    return {
        "amount": amount,
        "is_exempt": False,
        "owner_name": COMMUNIST_PLOT_OWNER_NAME,
    }


def resolve_end_of_round_plot_state(game_state: dict) -> dict:
    next_state = _refresh_state(game_state)
    current_round = _game_round(next_state)
    plot = _coerce_plot_state(_get_plot(next_state), current_round)
    if not plot.get("exists"):
        return next_state
    if int(plot.get("last_round_resolved", 0) or 0) >= current_round:
        return next_state

    social_properties = _social_properties(next_state)
    seized_ids = _seized_property_ids(next_state, social_properties)
    properties_by_id = _property_index(next_state)
    cluster_entries = list((plot.get("clusters") or []))
    cluster_size_by_property = {}
    for cluster in cluster_entries:
        for property_id in cluster.get("property_ids") or []:
            cluster_size_by_property[int(property_id)] = int(cluster.get("size", 1) or 1)

    government_type = normalize_government_type((next_state.get("econ") or {}).get("gov_type") or (next_state.get("settings") or {}).get("government_type"))
    supply_gain = 0.0
    for property_id in seized_ids:
        prop = properties_by_id.get(property_id) or {}
        entry = dict(social_properties.get(str(property_id)) or {})
        supply_gain += _calculate_supply_yield(
            prop,
            entry,
            cluster_size=cluster_size_by_property.get(property_id, 1),
            government_type=government_type,
            current_round=current_round,
            first_seizure_round=plot.get("first_seizure_round"),
        )
    if supply_gain > 0:
        plot = _add_supply(plot, supply_gain)

    region_presence = []
    for region_name, region_state in (plot.get("regions") or {}).items():
        has_presence = int(region_state.get("seeded_cells", 0) or 0) > 0 or any(str((properties_by_id.get(property_id) or {}).get("region") or "") == str(region_name) for property_id in seized_ids)
        if has_presence and int(region_state.get("hardship_pressure", 0) or 0) >= 3:
            region_presence.append(region_name)
            gain = 1.0
            if int(region_state.get("support_suppressed_until_round", 0) or 0) >= current_round:
                gain = 0.0
            plot = _add_support(plot, gain)

    if float((next_state.get("econ") or {}).get("treasury_balance", 0) or 0) < 350 and plot.get("public"):
        plot = _add_support(plot, 1)
    if float(plot.get("recent_backlash_support", 0) or 0) > 0:
        plot = _add_support(plot, float(plot.get("recent_backlash_support", 0) or 0))
        plot["recent_backlash_support"] = 0.0

    last_political_round = max(int(plot.get("last_mutual_aid_round", 0) or 0), int(plot.get("last_recruitment_round", 0) or 0))
    if seized_ids and last_political_round <= current_round - 2:
        plot = _add_support(plot, -2)
    if int(plot.get("last_aggression_round", 0) or 0) < current_round:
        plot = _add_heat(plot, -3)
    if float(plot.get("supply", 0) or 0) > 12 and int(plot.get("last_stockpile_round", 0) or 0) < current_round:
        decay = min(2, max(1, int((float(plot.get("supply", 0) or 0) - 12) // 6) + 1))
        plot = _add_supply(plot, -decay)

    control_percent = float(plot.get("control_percent", 0) or 0)
    committed_ids = list(plot.get("committed_member_ids") or [])
    entrenched_clusters = [entry for entry in (plot.get("clusters") or []) if entry.get("entrenched")]
    seized_regions = set(plot.get("seized_region_names") or [])
    victory = dict(plot.get("victory_countdown") or {})
    countdown_eligible = bool(
        current_round >= 9
        and committed_ids
        and len(entrenched_clusters) >= 2
        and float(plot.get("heat", 0) or 0) < 85
        and int(plot.get("first_seizure_round", 0) or 0) != current_round
        and (control_percent >= 30.0 or (len(seized_ids) >= 8 and len(seized_regions) >= 2))
    )
    if countdown_eligible:
        victory["active"] = True
        victory["rounds_held"] = int(victory.get("rounds_held", 0) or 0) + 1
        victory["last_valid_round"] = current_round
        victory["started_round"] = victory.get("started_round") or current_round
        victory["blocked_reason"] = None
        if int(victory.get("rounds_held", 0) or 0) >= int(victory.get("required_rounds", 2) or 2):
            victory["completed"] = True
    else:
        victory["active"] = False
        victory["rounds_held"] = 0
        victory["completed"] = False
        if float(plot.get("heat", 0) or 0) >= 85:
            victory["blocked_reason"] = "Heat is too high to sustain the revolutionary countdown."
        elif not committed_ids:
            victory["blocked_reason"] = "At least one committed communist member must remain active."
        elif len(entrenched_clusters) < 2:
            victory["blocked_reason"] = "Two entrenched seized clusters are required for victory."
        elif not (control_percent >= 30.0 or (len(seized_ids) >= 8 and len(seized_regions) >= 2)):
            victory["blocked_reason"] = "The faction does not yet control enough of the board."
        else:
            victory["blocked_reason"] = None

    plot["victory_countdown"] = victory
    plot["last_round_resolved"] = current_round
    plot = _append_history(
        plot,
        action_type="round_resolution",
        player_id=None,
        current_round=current_round,
        success=True,
        summary=f"Round-end plot resolution generated {int(supply_gain)} Supply across {len(seized_ids)} seized properties.",
    )
    next_state = _set_social_properties(next_state, social_properties, plot)
    return _refresh_state(next_state)


def check_plot_victory(game_state: dict) -> dict | None:
    plot = _get_plot(game_state)
    victory = dict((plot or {}).get("victory_countdown") or {})
    if not victory.get("completed"):
        return None
    player_lookup = _player_index(game_state)
    committed_member_ids = [player_id for player_id in (plot.get("committed_member_ids") or []) if player_id in player_lookup]
    committed_members = [player_lookup[player_id] for player_id in committed_member_ids]
    return {
        "type": "faction",
        "faction": "communist_plot",
        "label": "People's Victory",
        "committed_members": committed_members,
        "committed_member_ids": committed_member_ids,
        "control_percent": float(plot.get("control_percent", 0) or 0),
        "victory_round": _game_round(game_state),
    }