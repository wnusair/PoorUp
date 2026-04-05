"""Social instability engine for PoorUp."""

from __future__ import annotations

import math
from datetime import datetime
from statistics import median
from typing import Any

from app.engine.debt import spend_player_balance
from app.engine.economy import (
    calculate_net_worth,
    calculate_rent_with_dev,
    calculate_transit_rent,
    compute_gini_coefficient,
)
from app.engine.taxation import get_welfare_target_balance
from app.utils.settings import normalize_game_mode, normalize_government_type

PROLETARIAT_UNION_ID = "proletariat_union"

MODE_PROFILE = {
    "standard": {
        "inflation_ceiling": 0.25,
        "tax_ceiling": 0.60,
        "revolution_rage_gate": 80,
        "revolution_stability_gate": 35,
        "union_spread_rage_gate": 75,
        "union_spread_stability_gate": 40,
    },
    "speed": {
        "inflation_ceiling": 0.25,
        "tax_ceiling": 0.50,
        "revolution_rage_gate": 85,
        "revolution_stability_gate": 30,
        "union_spread_rage_gate": 80,
        "union_spread_stability_gate": 35,
    },
    "chaos": {
        "inflation_ceiling": 0.35,
        "tax_ceiling": 0.75,
        "revolution_rage_gate": 70,
        "revolution_stability_gate": 45,
        "union_spread_rage_gate": 68,
        "union_spread_stability_gate": 50,
    },
    "cooperative": {
        "inflation_ceiling": 0.25,
        "tax_ceiling": 0.60,
        "revolution_rage_gate": 82,
        "revolution_stability_gate": 38,
        "union_spread_rage_gate": 76,
        "union_spread_stability_gate": 42,
    },
}

MODE_NEW_INCIDENT_CAPS = {
    "standard": 2,
    "speed": 1,
    "chaos": 3,
    "cooperative": 2,
}

MODE_SPREAD_COUNTS = {
    "standard": 1,
    "speed": 1,
    "chaos": 2,
    "cooperative": 1,
}

MODE_NEGOTIATION_MULTIPLIERS = {
    "standard": 1.00,
    "speed": 0.75,
    "chaos": 1.15,
    "cooperative": 0.95,
}

MODE_DURATION_BONUS = {
    "standard": 0,
    "speed": -1,
    "chaos": 1,
    "cooperative": 0,
}

SEVERITY_MULTIPLIERS = {
    "protest": 0.20,
    "strike": 0.30,
    "uprising": 0.45,
    "revolution": 0.60,
}

INCIDENT_BASE_DURATION = {
    "protest": 1,
    "strike": 2,
    "uprising": 2,
    "revolution": 3,
}

UNION_BLOC_MULTIPLIERS = {
    1: 2.0,
    2: 4.5,
    3: 8.0,
    4: 12.5,
    5: 18.0,
}

GOVERNMENT_WELFARE_TARGETS = {
    "minarchism": 0.0,
    "liberal_democracy": 30.0,
    "social_democracy": 55.0,
}

INCIDENT_THRESHOLDS = {
    "watchlist": 35.0,
    "protest": 50.0,
    "strike": 65.0,
    "uprising": 80.0,
    "revolution": 90.0,
}

CAUSE_LABELS = {
    "low_stability": "Low national stability",
    "inequality": "Owner net worth is far above the table median",
    "hostile_lobbying": "Owner is funding hostile anti-relief lobbying from a position of concentrated wealth",
    "welfare_shortfall": "Welfare relief is undershooting visible hardship",
    "tax_pressure": "Taxes are amplifying local stress",
    "rent_extraction": "Rent extraction is above the table norm",
    "treasury_distress": "Treasury strain is limiting relief capacity",
    "inflation_pressure": "Inflation is inflaming household pressure",
    "region_momentum": "This region has repeated unrest pressure",
}

GRIEVANCE_POLICY_TARGETS = {
    "hostile_lobbying": ["welfare_increase", "economic_stimulus", "rent_control", "stabilization_fund"],
    "welfare_shortfall": ["welfare_increase", "economic_stimulus"],
    "tax_pressure": ["tax_multiplier_decrease"],
    "treasury_distress": ["stabilization_fund", "bailout_enable"],
    "rent_extraction": ["rent_control"],
    "inequality": ["welfare_increase", "stabilization_fund", "rent_control"],
    "inflation_pressure": ["stabilization_fund"],
    "low_stability": ["stabilization_fund", "rent_control", "welfare_increase"],
}

GRIEVANCE_ACTIONS = {
    "hostile_lobbying": [
        {"type": "negotiate", "label": "Fund local concessions before the backlash compounds", "expected_relief": 18},
        {"type": "lobby", "label": "Reverse the hostile welfare or housing push", "expected_relief": 15},
        {"type": "manage", "label": "Back off extraction pressure until the table cools", "expected_relief": 10},
    ],
    "low_stability": [
        {"type": "lobby", "label": "Back stabilization or treasury relief", "expected_relief": 15},
        {"type": "negotiate", "label": "Fund local concessions", "expected_relief": 20},
    ],
    "welfare_shortfall": [
        {"type": "negotiate", "label": "Fund local concessions", "expected_relief": 20},
        {"type": "lobby", "label": "Push welfare relief or stimulus", "expected_relief": 15},
    ],
    "tax_pressure": [
        {"type": "lobby", "label": "Push tax relief", "expected_relief": 15},
        {"type": "negotiate", "label": "Bridge the local grievance target", "expected_relief": 12},
    ],
    "rent_extraction": [
        {"type": "negotiate", "label": "Fund local concessions", "expected_relief": 20},
        {"type": "lobby", "label": "Push rent control or welfare relief", "expected_relief": 15},
        {"type": "manage", "label": "Pause further development pressure", "expected_relief": 8},
    ],
    "inequality": [
        {"type": "negotiate", "label": "Redistribute local pressure now", "expected_relief": 18},
        {"type": "lobby", "label": "Back welfare or treasury repair", "expected_relief": 15},
    ],
    "treasury_distress": [
        {"type": "support", "label": "Refill treasury breathing room", "expected_relief": 12},
        {"type": "lobby", "label": "Back stabilization or treasury rebuild", "expected_relief": 15},
    ],
    "inflation_pressure": [
        {"type": "lobby", "label": "Push anti-inflation relief", "expected_relief": 15},
        {"type": "negotiate", "label": "Fund near-term concessions", "expected_relief": 10},
    ],
}

PERSISTENT_PROPERTY_KEYS = {
    "incident_id",
    "incident_type",
    "remaining_rounds",
    "former_owner_id",
    "union_territory_key",
    "union_started_round",
    "minimum_hold_rounds",
    "union_development_level",
    "reintegration_progress",
    "negotiation_target",
    "negotiation_committed",
    "negotiation_contributions",
    "re_escalation_immunity_rounds",
    "spread_blocked_until_round",
    "last_started_round",
}

EMERGENCY_REFORM_TARGETS = {
    "private_relief_contract",
    "tax_moratorium",
    "property_rights_compact",
}

EMERGENCY_REFORM_REASONS = {
    "private_relief_contract": {"matching": True},
    "tax_moratorium": {"grievances": {"tax_pressure"}},
    "property_rights_compact": {"grievances": {"low_stability", "rent_extraction", "inequality"}},
}

HOSTILE_LOBBY_TARGETS = {
    "welfare_decrease": {"label": "Welfare Cuts", "weight": 1.0, "hardship_sensitive": True},
    "deregulate_housing": {"label": "Housing Deregulation", "weight": 0.65, "hardship_sensitive": False},
    "bailout_disable": {"label": "Disable Bailouts", "weight": 0.55, "hardship_sensitive": True},
}


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _round(value: float | int | None, digits: int = 2) -> float:
    return round(float(value or 0), digits)


def active_players(game_state: dict) -> list[dict]:
    return [
        player
        for player in game_state.get("players", [])
        if not player.get("is_bankrupt", False)
    ]


def _active_player_ids(game_state: dict) -> set[int]:
    return {player["id"] for player in active_players(game_state)}


def _player_index(game_state: dict) -> dict[int, dict]:
    return {player["id"]: player for player in game_state.get("players", [])}


def _owner_label(owner_id: Any, player_lookup: dict[int, dict]) -> str:
    if owner_id == PROLETARIAT_UNION_ID:
        return "Proletariat Union"
    if owner_id is None:
        return "Unowned"
    owner = player_lookup.get(owner_id)
    if owner is not None:
        return owner.get("username", "Player")
    return f"Owner {owner_id}"


def _normalize_mode(settings: dict | None) -> str:
    return normalize_game_mode((settings or {}).get("game_mode", "standard"))


def _mode_profile(settings: dict | None) -> dict:
    return dict(MODE_PROFILE[_normalize_mode(settings)])


def _game_round(game_state: dict) -> int:
    return int(game_state.get("current_round", 1) or 1)


def _coerce_social_state(game_state: dict, *, preserve_property_fields: bool) -> dict:
    social = dict(game_state.get("social") or {})
    social.setdefault("overall_rage", 0.0)
    social.setdefault("stability_percent", 70)
    social.setdefault("grievance_mix", {})
    social.setdefault("territories", [])
    social.setdefault("properties", {})
    social.setdefault("active_incidents", [])
    social.setdefault("incident_history", [])
    social.setdefault("active_effects", [])
    social.setdefault("emergency_reforms", [])
    social.setdefault("unionized_property_count", 0)
    social.setdefault("national_flashpoint", {})

    properties = {}
    for key, value in (social.get("properties") or {}).items():
        if not isinstance(value, dict):
            continue
        if preserve_property_fields:
            properties[str(key)] = dict(value)
        else:
            properties[str(key)] = {
                persistent_key: value.get(persistent_key)
                for persistent_key in PERSISTENT_PROPERTY_KEYS
                if persistent_key in value
            }
    social["properties"] = properties

    social["incident_history"] = [
        dict(entry)
        for entry in social.get("incident_history", [])
        if isinstance(entry, dict)
    ][-80:]
    social["active_effects"] = [
        dict(entry)
        for entry in social.get("active_effects", [])
        if isinstance(entry, dict)
    ]
    social["emergency_reforms"] = [
        dict(entry)
        for entry in social.get("emergency_reforms", [])
        if isinstance(entry, dict)
    ][-24:]
    return social


def _social_base(game_state: dict) -> dict:
    return _coerce_social_state(game_state, preserve_property_fields=False)


def _social_snapshot(game_state: dict) -> dict:
    return _coerce_social_state(game_state, preserve_property_fields=True)


def _tracked_property_entries(game_state: dict) -> dict[str, dict]:
    social = _social_base(game_state)
    tracked_entries = {}
    active_player_ids = _active_player_ids(game_state)

    for prop in game_state.get("properties", []):
        prop_id = str(prop.get("id"))
        existing = dict(social["properties"].get(prop_id) or {})
        owner_id = prop.get("owner_id")
        is_unionized = owner_id == PROLETARIAT_UNION_ID or existing.get("former_owner_id") is not None
        has_local_state = bool(existing.get("incident_type") or existing.get("negotiation_committed") or existing.get("former_owner_id") is not None)
        if is_unionized or owner_id in active_player_ids or has_local_state:
            tracked_entries[prop_id] = existing

    return tracked_entries


def _sort_key_for_incident(incident_type: str | None) -> int:
    return {
        None: 0,
        "protest": 1,
        "strike": 2,
        "uprising": 3,
        "revolution": 4,
    }.get(incident_type, 0)


def _previous_incident_type(incident_type: str | None) -> str | None:
    return {
        "protest": None,
        "strike": "protest",
        "uprising": "strike",
        "revolution": "uprising",
    }.get(incident_type)


def _next_incident_type(incident_type: str | None) -> str | None:
    return {
        None: "protest",
        "protest": "strike",
        "strike": "uprising",
        "uprising": "revolution",
    }.get(incident_type)


def _incident_lower_bound(incident_type: str | None) -> float:
    if incident_type is None:
        return INCIDENT_THRESHOLDS["watchlist"]
    return INCIDENT_THRESHOLDS.get(incident_type, INCIDENT_THRESHOLDS["watchlist"])


def _state_from_tension(
    tension: float,
    territory_instability: float,
    overall_rage: float,
    stability_percent: float,
    mode_profile: dict,
) -> str | None:
    if tension < INCIDENT_THRESHOLDS["protest"]:
        return None
    if tension < INCIDENT_THRESHOLDS["strike"]:
        return "protest"
    if tension < INCIDENT_THRESHOLDS["uprising"]:
        return "strike"
    if tension < INCIDENT_THRESHOLDS["revolution"]:
        return "uprising"
    if (
        territory_instability >= 75
        and overall_rage >= float(mode_profile.get("revolution_rage_gate", 80) or 80)
        and stability_percent <= float(mode_profile.get("revolution_stability_gate", 35) or 35)
    ):
        return "revolution"
    return "uprising"


def _watch_state(tension: float, incident_type: str | None) -> str:
    if incident_type:
        return "active_incident"
    if tension >= INCIDENT_THRESHOLDS["protest"]:
        return "critical_watch"
    if tension >= INCIDENT_THRESHOLDS["watchlist"]:
        return "watchlist"
    return "stable"


def _get_property_social_entry(game_state: dict, property_id: int | str) -> dict | None:
    social = _social_base(game_state)
    return social.get("properties", {}).get(str(property_id))


def property_is_unionized(prop_or_entry: dict | None, game_state: dict | None = None) -> bool:
    if not prop_or_entry:
        return False
    if prop_or_entry.get("owner_id") == PROLETARIAT_UNION_ID:
        return True
    if prop_or_entry.get("former_owner_id") is not None:
        return True
    if game_state is not None and prop_or_entry.get("id") is not None:
        social_entry = _get_property_social_entry(game_state, prop_or_entry.get("id"))
        return bool(social_entry and social_entry.get("former_owner_id") is not None)
    return False


def property_income_blocked(game_state: dict, property_id: int | str) -> bool:
    social_entry = _get_property_social_entry(game_state, property_id) or {}
    return social_entry.get("incident_type") in {"strike", "uprising", "revolution"}


def property_private_actions_locked(game_state: dict, property_id: int | str) -> bool:
    social_entry = _get_property_social_entry(game_state, property_id) or {}
    return property_is_unionized(social_entry)


def _median_net_worth(game_state: dict) -> float:
    values = [
        float(calculate_net_worth(player, game_state) or 0)
        for player in active_players(game_state)
    ]
    if not values:
        return 1.0
    return max(1.0, float(median(values)))


def _rent_reference(game_state: dict, econ: dict, tracked_props: list[dict]) -> float:
    projected_rents = []
    for prop in tracked_props:
        if prop.get("property_type") == "transit":
            projected_rents.append(float(calculate_transit_rent(prop.get("owner_id"), game_state) or 0))
        else:
            projected_rents.append(float(calculate_rent_with_dev(prop, econ, game_state) or 0))
    if not projected_rents:
        return 25.0
    return max(25.0, float(median(projected_rents)))


def _projected_relief_cost(players: list[dict], welfare_target_balance: float, welfare_target_rate: float) -> float:
    if welfare_target_balance <= 0 or welfare_target_rate <= 0:
        return 0.0
    projected_cost = 0.0
    for player in players:
        balance = float(player.get("balance", 0) or 0)
        hardship_gap = max(0.0, welfare_target_balance - balance)
        projected_cost += min(hardship_gap, welfare_target_balance * (welfare_target_rate / 100.0))
    return _round(projected_cost, 2)


def _macro_metrics(game_state: dict, econ: dict, settings: dict | None = None) -> dict:
    settings = settings or game_state.get("settings", {})
    players = active_players(game_state)
    mode = _normalize_mode(settings)
    profile = MODE_PROFILE[mode]
    government_type = normalize_government_type(
        econ.get("gov_type") or econ.get("government_type") or settings.get("government_type")
    )

    stability = clamp(float(econ.get("stability", 0.7) or 0.7), 0.0, 1.0)
    stability_percent = round(stability * 100)
    gini_norm = clamp(float(compute_gini_coefficient(players) or 0) / 0.75, 0.0, 1.0)
    inflation_norm = clamp(
        float(econ.get("inflation_rate", 0) or 0) / float(profile["inflation_ceiling"]),
        0.0,
        1.0,
    )
    tax_norm = clamp(
        float(econ.get("tax_multiplier", 0) or 0) / float(profile["tax_ceiling"]),
        0.0,
        1.0,
    )

    welfare_target_balance = float(get_welfare_target_balance(settings) or 0)
    players_below_target = sum(
        1 for player in players if float(player.get("balance", 0) or 0) < welfare_target_balance
    )
    players_below_target_ratio = 0.0
    if players:
        players_below_target_ratio = players_below_target / len(players)

    welfare_target_rate = float(GOVERNMENT_WELFARE_TARGETS.get(government_type, 30.0) or 0.0)
    if government_type == "minarchism":
        welfare_relief_norm = 0.0
    else:
        welfare_relief_norm = clamp(
            float(econ.get("welfare_payout", 0) or 0) / max(1.0, welfare_target_rate),
            0.0,
            1.0,
        )

    projected_next_round_relief_cost = _projected_relief_cost(
        players,
        welfare_target_balance,
        welfare_target_rate,
    )
    treasury_balance = float(econ.get("treasury_balance", 0) or 0)
    treasury_target = max(projected_next_round_relief_cost, 400.0)
    treasury_distress = clamp(1.0 - (treasury_balance / max(1.0, treasury_target)), 0.0, 1.0)

    low_stability_points = (1.0 - stability) * 32.0
    inequality_points = gini_norm * 18.0
    inflation_points = inflation_norm * 12.0
    tax_points = tax_norm * 8.0
    treasury_points = treasury_distress * 10.0
    welfare_gap_points = players_below_target_ratio * 10.0
    welfare_relief_points = welfare_relief_norm * 10.0

    overall_rage = clamp(
        low_stability_points
        + inequality_points
        + inflation_points
        + tax_points
        + treasury_points
        + welfare_gap_points
        - welfare_relief_points,
        0.0,
        100.0,
    )

    raw_points = {
        "low_stability": low_stability_points,
        "inequality": inequality_points,
        "inflation_pressure": inflation_points,
        "tax_pressure": tax_points,
        "treasury_distress": treasury_points,
        "welfare_shortfall": max(0.0, welfare_gap_points + ((1.0 - welfare_relief_norm) * 6.0)),
    }

    return {
        "overall_rage": _round(overall_rage, 1),
        "stability_percent": stability_percent,
        "macro_points": raw_points,
        "players_below_target_ratio": _round(players_below_target_ratio, 4),
        "welfare_target_balance": welfare_target_balance,
        "treasury_target": treasury_target,
        "government_type": government_type,
        "mode": mode,
        "mode_profile": profile,
    }


def calculate_overall_rage(game_state: dict, econ: dict, settings: dict | None = None) -> float:
    return float(_macro_metrics(game_state, econ, settings)["overall_rage"])


def _recent_incident_count(social: dict, *, region: str | None = None, property_id: int | None = None, rounds_back: int = 3) -> int:
    current_round = _game_round({"current_round": social.get("current_round", 1)})
    lower_round = current_round - max(0, rounds_back) + 1
    count = 0
    for entry in social.get("incident_history", []):
        round_number = int(entry.get("round", 0) or 0)
        if round_number < lower_round:
            continue
        if region is not None and entry.get("region") != region:
            continue
        if property_id is not None and int(entry.get("property_id", 0) or 0) != int(property_id):
            continue
        count += 1
    return count


def _success_history_entries(game_state: dict, current_round: int) -> list[dict]:
    history = (
        (game_state.get("lobbying_stats") or {}).get("resolved_history")
        or (_social_base(game_state).get("resolved_history") if isinstance(_social_base(game_state), dict) else [])
    )
    successes = []
    for entry in history or []:
        if not isinstance(entry, dict) or not entry.get("success"):
            continue
        if int(entry.get("round", 0) or 0) < current_round - 2:
            continue
        successes.append(dict(entry))
    return successes


def _active_policy_targets(game_state: dict, current_round: int) -> set[str]:
    targets = set()
    for entry in _success_history_entries(game_state, current_round):
        target = entry.get("target") or entry.get("target_stat")
        if target:
            targets.add(str(target))
    if game_state.get("econ", {}).get("rent_control_active"):
        targets.add("rent_control")
    return targets


def _matching_success_multiplier(game_state: dict, grievance: str, current_round: int) -> float:
    candidates = [
        entry
        for entry in _success_history_entries(game_state, current_round)
        if int(entry.get("round", 0) or 0) == current_round
        and _policy_matches_grievance(entry.get("target") or entry.get("target_stat"), grievance)
    ]
    if not candidates:
        return 0.0

    best_multiplier = 0.0
    for entry in candidates:
        target = str(entry.get("target") or entry.get("target_stat") or "")
        same_target_count = sum(
            1
            for candidate in _success_history_entries(game_state, current_round)
            if str(candidate.get("target") or candidate.get("target_stat") or "") == target
        )
        if same_target_count <= 1:
            multiplier = 1.0
        elif same_target_count == 2:
            multiplier = 0.5
        else:
            multiplier = 0.25
        best_multiplier = max(best_multiplier, multiplier)
    return best_multiplier


def _policy_matches_grievance(target: str | None, grievance: str) -> bool:
    if not target:
        return False
    return str(target) in GRIEVANCE_POLICY_TARGETS.get(grievance, [])


def _has_active_relief(game_state: dict, grievance: str, current_round: int) -> bool:
    return any(
        _policy_matches_grievance(target, grievance)
        for target in _active_policy_targets(game_state, current_round)
    )


def _property_value_basis(prop: dict, game_state: dict) -> float:
    social_properties = (_social_base(game_state).get("properties") or {})
    social_entry = dict(social_properties.get(str(prop.get("id"))) or {})

    if property_is_unionized({**prop, **social_entry}, game_state):
        region = prop.get("region")
        territory_key = social_entry.get("union_territory_key") or _territory_key(
            social_entry.get("former_owner_id"),
            region,
        )
        total = 0.0
        for candidate in game_state.get("properties", []):
            candidate_entry = dict(social_properties.get(str(candidate.get("id"))) or {})
            if candidate.get("region") != region:
                continue
            if not property_is_unionized({**candidate, **candidate_entry}, game_state):
                continue
            candidate_territory_key = candidate_entry.get("union_territory_key") or _territory_key(
                candidate_entry.get("former_owner_id"),
                candidate.get("region"),
            )
            if territory_key and candidate_territory_key != territory_key:
                continue
            base_price = float(candidate.get("base_price", 0) or 0)
            total += base_price * (1.0 + (int(candidate.get("dev_level", 0) or 0) * 0.25))
        return max(total, float(prop.get("base_price", 0) or 0))

    base_price = float(prop.get("base_price", 0) or 0)
    dev_level = int(prop.get("dev_level", 0) or 0)
    return base_price * (1.0 + (dev_level * 0.25))


def _hostile_lobbying_pressure(
    owner_id: Any,
    *,
    owner_gap_norm: float,
    macro: dict,
    game_state: dict,
) -> dict:
    if owner_id in {None, PROLETARIAT_UNION_ID}:
        return {"points": 0.0, "targets": []}

    pools = ((game_state.get("lobbying_stats") or {}).get("policy_pools") or {}).values()
    if not pools:
        return {"points": 0.0, "targets": []}

    hardship_ratio = clamp(float(macro.get("players_below_target_ratio", 0) or 0), 0.0, 1.0)
    raw_pressure = 0.0
    target_entries = []

    for pool in pools:
        if not isinstance(pool, dict):
            continue
        target_key = str(pool.get("target") or "")
        target_definition = HOSTILE_LOBBY_TARGETS.get(target_key)
        if not target_definition:
            continue

        cost_hint = max(1.0, float(pool.get("cost_hint", 250) or 250))
        hardship_multiplier = 1.0
        if target_definition.get("hardship_sensitive"):
            hardship_multiplier = 0.35 + (0.65 * hardship_ratio)

        for contributor in pool.get("contributors") or []:
            if not isinstance(contributor, dict):
                continue
            if contributor.get("player_id") != owner_id:
                continue

            contribution = max(0.0, float(contributor.get("contribution", 0) or 0))
            contribution_ratio = clamp(contribution / cost_hint, 0.0, 1.25)
            if contribution_ratio <= 0:
                continue

            raw_target_pressure = contribution_ratio * float(target_definition.get("weight", 0) or 0) * hardship_multiplier
            if raw_target_pressure <= 0:
                continue

            raw_pressure += raw_target_pressure
            target_entries.append(
                {
                    "target": target_key,
                    "label": target_definition.get("label", target_key.replace("_", " ").title()),
                    "contribution": _round(contribution, 2),
                    "pool_total": _round(pool.get("pool_total", 0), 2),
                    "points": _round(raw_target_pressure * owner_gap_norm * 16.0, 1),
                }
            )

    target_entries.sort(key=lambda entry: float(entry.get("points", 0) or 0), reverse=True)
    points = clamp(owner_gap_norm * raw_pressure * 16.0, 0.0, 18.0)
    return {
        "points": _round(points, 1),
        "targets": target_entries[:3],
    }


def _target_incident_type(prop_entry: dict, tension: float, territory_instability: float, overall_rage: float, stability_percent: float, mode_profile: dict) -> str:
    existing = prop_entry.get("incident_type")
    if existing:
        return existing
    incident_type = _state_from_tension(tension, territory_instability, overall_rage, stability_percent, mode_profile)
    return incident_type or "protest"


def _calculate_negotiation_target(prop: dict, prop_entry: dict, game_state: dict, mode: str, territory_instability: float, overall_rage: float, stability_percent: float, mode_profile: dict) -> float:
    incident_type = _target_incident_type(
        prop_entry,
        float(prop_entry.get("tension", 0) or 0),
        territory_instability,
        overall_rage,
        stability_percent,
        mode_profile,
    )
    value_basis = _property_value_basis(prop, game_state)
    target = value_basis * SEVERITY_MULTIPLIERS.get(incident_type, SEVERITY_MULTIPLIERS["protest"]) * MODE_NEGOTIATION_MULTIPLIERS.get(mode, 1.0)
    return _round(target, 2)


def _next_threshold(tension: float) -> float | None:
    for threshold in [
        INCIDENT_THRESHOLDS["watchlist"],
        INCIDENT_THRESHOLDS["protest"],
        INCIDENT_THRESHOLDS["strike"],
        INCIDENT_THRESHOLDS["uprising"],
        INCIDENT_THRESHOLDS["revolution"],
    ]:
        if tension < threshold:
            return threshold
    return None


def _eta_to_next_threshold(prev_tension: float, current_tension: float, incident_type: str | None, remaining_rounds: int | None) -> int | None:
    if incident_type:
        return int(max(0, remaining_rounds or 0))
    if current_tension < INCIDENT_THRESHOLDS["watchlist"]:
        return None
    delta = current_tension - prev_tension
    if delta <= 0:
        return None
    next_threshold = _next_threshold(current_tension)
    if next_threshold is None:
        return None
    return int(math.ceil((next_threshold - current_tension) / max(delta, 1.0)))


def _coerce_property_for_social(game_state: dict, prop: dict, persistent_entry: dict, macro: dict, rent_reference: float, median_net_worth: float, player_lookup: dict[int, dict]) -> dict:
    prop_id = str(prop.get("id"))
    owner_id = prop.get("owner_id")
    region = prop.get("region")
    current_round = _game_round(game_state)
    econ = game_state.get("econ", {})
    mode = macro["mode"]
    mode_profile = macro["mode_profile"]

    region_momentum_norm = clamp(
        _recent_incident_count(_social_base(game_state), region=region, rounds_back=3) / 3.0,
        0.0,
        1.0,
    )
    repeat_property_norm = clamp(
        _recent_incident_count(_social_base(game_state), property_id=int(prop.get("id", 0) or 0), rounds_back=5) / 2.0,
        0.0,
        1.0,
    )
    macro_total = float(macro["overall_rage"] or 0) * 0.35

    owner_gap_norm = 0.0
    monopoly_bonus = 0.0
    if owner_id in player_lookup:
        owner_net_worth = max(0.0, float(calculate_net_worth(player_lookup[owner_id], game_state) or 0))
        owner_gap_norm = clamp(((owner_net_worth / max(1.0, median_net_worth)) - 1.0) / 2.0, 0.0, 1.0)
        monopoly_bonus = 1.0 if _has_full_group(prop, game_state) else 0.0

    if prop.get("property_type") == "transit":
        projected_rent = float(calculate_transit_rent(owner_id, game_state) or 0)
        development_norm = 0.0
    else:
        projected_rent = float(calculate_rent_with_dev(prop, econ, game_state) or 0)
        development_norm = clamp(int(prop.get("dev_level", 0) or 0) / 5.0, 0.0, 1.0)

    rent_load_norm = clamp(((projected_rent / max(25.0, rent_reference)) - 1.0) / 2.0, 0.0, 1.0)
    tax_norm = clamp(
        float(econ.get("tax_multiplier", 0) or 0) / float(mode_profile["tax_ceiling"]),
        0.0,
        1.0,
    )

    macro_points = dict(macro["macro_points"])
    macro_total_points = max(1.0, sum(float(value or 0) for value in macro_points.values()))
    cause_points = {
        cause: macro_total * (float(points or 0) / macro_total_points)
        for cause, points in macro_points.items()
    }
    hostile_lobbying = _hostile_lobbying_pressure(
        owner_id,
        owner_gap_norm=owner_gap_norm,
        macro=macro,
        game_state=game_state,
    )
    cause_points["inequality"] = cause_points.get("inequality", 0.0) + (owner_gap_norm * 18.0)
    cause_points["hostile_lobbying"] = cause_points.get("hostile_lobbying", 0.0) + float(hostile_lobbying.get("points", 0) or 0)
    cause_points["rent_extraction"] = cause_points.get("rent_extraction", 0.0) + (rent_load_norm * 15.0) + (development_norm * 10.0) + (monopoly_bonus * 6.0)
    cause_points["tax_pressure"] = cause_points.get("tax_pressure", 0.0) + (tax_norm * 6.0)
    cause_points["region_momentum"] = cause_points.get("region_momentum", 0.0) + (region_momentum_norm * 8.0) + (repeat_property_norm * 6.0)

    dominant_grievance = max(cause_points.items(), key=lambda item: item[1])[0] if cause_points else "low_stability"
    negotiation_committed = _round(persistent_entry.get("negotiation_committed", 0), 2)

    provisional_entry = {
        **persistent_entry,
        "property_id": prop.get("id"),
        "owner_id": owner_id,
        "region": region,
        "dominant_grievance": dominant_grievance,
    }

    matching_policy_relief = 1.0 if _has_active_relief(game_state, dominant_grievance, current_round) else 0.0
    territory_instability = 0.0
    if persistent_entry.get("territory_instability") is not None:
        territory_instability = float(persistent_entry.get("territory_instability") or 0)
    negotiation_target = float(persistent_entry.get("negotiation_target") or 0)
    if negotiation_target <= 0:
        provisional_entry["tension"] = 0.0
        negotiation_target = _calculate_negotiation_target(
            prop,
            provisional_entry,
            game_state,
            mode,
            territory_instability,
            float(macro["overall_rage"] or 0),
            float(macro["stability_percent"] or 0),
            mode_profile,
        )
    negotiation_coverage = clamp(negotiation_committed / max(1.0, negotiation_target), 0.0, 1.5)

    property_tension = clamp(
        macro_total
        + (owner_gap_norm * 18.0)
        + float(hostile_lobbying.get("points", 0) or 0)
        + (rent_load_norm * 15.0)
        + (development_norm * 10.0)
        + (monopoly_bonus * 6.0)
        + (tax_norm * 6.0)
        + (region_momentum_norm * 8.0)
        + (repeat_property_norm * 6.0)
        - (min(1.0, negotiation_coverage) * 12.0)
        - (matching_policy_relief * 10.0),
        0.0,
        100.0,
    )

    previous_tension = float((game_state.get("social") or {}).get("properties", {}).get(prop_id, {}).get("tension", 0) or 0)
    reason_breakdown = [
        {
            "key": key,
            "label": CAUSE_LABELS.get(key, key.replace("_", " ").title()),
            "points": _round(value, 1),
        }
        for key, value in sorted(cause_points.items(), key=lambda item: item[1], reverse=True)
        if value > 0.01
    ][:3]

    entry = {
        **persistent_entry,
        "property_id": prop.get("id"),
        "owner_id": owner_id,
        "region": region,
        "tension": _round(property_tension, 1),
        "watch_state": _watch_state(property_tension, persistent_entry.get("incident_type")),
        "incident_type": persistent_entry.get("incident_type"),
        "remaining_rounds": int(persistent_entry.get("remaining_rounds", 0) or 0),
        "dominant_grievance": dominant_grievance,
        "reason_breakdown": reason_breakdown,
        "hostile_lobbying_points": _round(hostile_lobbying.get("points", 0), 1),
        "hostile_lobby_targets": list(hostile_lobbying.get("targets") or []),
        "recommended_actions": list(GRIEVANCE_ACTIONS.get(dominant_grievance, GRIEVANCE_ACTIONS["low_stability"]))[:4],
        "recommended_lobby_targets": list(GRIEVANCE_POLICY_TARGETS.get(dominant_grievance, []))[:4],
        "negotiation_target": _round(negotiation_target, 2),
        "negotiation_committed": negotiation_committed,
        "former_owner_id": persistent_entry.get("former_owner_id"),
        "union_territory_key": persistent_entry.get("union_territory_key"),
        "union_development_level": int(persistent_entry.get("union_development_level", 0) or 0),
        "reintegration_progress": int(clamp(float(persistent_entry.get("reintegration_progress", 0) or 0), 0.0, 100.0)),
        "negotiation_contributions": list(persistent_entry.get("negotiation_contributions") or []),
        "re_escalation_immunity_rounds": int(persistent_entry.get("re_escalation_immunity_rounds", 0) or 0),
        "spread_blocked_until_round": int(persistent_entry.get("spread_blocked_until_round", 0) or 0),
    }
    entry["eta_to_next_threshold"] = _eta_to_next_threshold(previous_tension, property_tension, entry.get("incident_type"), entry.get("remaining_rounds"))
    return entry


def _has_full_group(prop: dict, game_state: dict) -> bool:
    group_color = prop.get("group_color")
    if not group_color or prop.get("property_type") != "property":
        return False
    owner_id = prop.get("owner_id")
    group_props = [
        candidate
        for candidate in game_state.get("properties", [])
        if candidate.get("group_color") == group_color and candidate.get("property_type") == "property"
    ]
    return bool(group_props) and all(candidate.get("owner_id") == owner_id for candidate in group_props)


def _territory_key(owner_id: Any, region: str | None) -> str:
    return f"{owner_id}|{region}"


def _territory_snapshot(properties: list[dict], player_lookup: dict[int, dict]) -> list[dict]:
    grouped: dict[str, dict] = {}
    for entry in properties:
        territory_key = _territory_key(entry.get("owner_id"), entry.get("region"))
        bucket = grouped.setdefault(
            territory_key,
            {
                "territory_key": territory_key,
                "owner_id": entry.get("owner_id"),
                "owner_name": _owner_label(entry.get("owner_id"), player_lookup),
                "region": entry.get("region"),
                "properties": [],
                "property_ids": [],
                "dominant_grievance_points": {},
            },
        )
        bucket["properties"].append(entry)
        bucket["property_ids"].append(entry.get("property_id"))
        grievance = entry.get("dominant_grievance")
        if grievance:
            bucket["dominant_grievance_points"][grievance] = bucket["dominant_grievance_points"].get(grievance, 0.0) + float(entry.get("tension", 0) or 0)

    territories = []
    for territory in grouped.values():
        tensions = sorted(
            [float(entry.get("tension", 0) or 0) for entry in territory["properties"]],
            reverse=True,
        )
        top_three = tensions[:3] or [0.0]
        active_incident_count = sum(1 for entry in territory["properties"] if entry.get("incident_type"))
        unionized_property_count = sum(1 for entry in territory["properties"] if entry.get("former_owner_id") is not None)
        territory_instability = clamp(
            (sum(top_three) / max(1, len(top_three)))
            + min(10.0, active_incident_count * 4.0)
            + min(6.0, unionized_property_count * 3.0),
            0.0,
            100.0,
        )
        dominant_grievances = [
            key
            for key, _ in sorted(
                territory["dominant_grievance_points"].items(),
                key=lambda item: item[1],
                reverse=True,
            )
        ][:3]
        territories.append(
            {
                "territory_key": territory["territory_key"],
                "owner_id": territory["owner_id"],
                "owner_name": territory["owner_name"],
                "region": territory["region"],
                "property_ids": territory["property_ids"],
                "property_count": len(territory["property_ids"]),
                "territory_instability": _round(territory_instability, 1),
                "active_incident_count": active_incident_count,
                "unionized_property_count": unionized_property_count,
                "dominant_grievances": dominant_grievances,
            }
        )
    territories.sort(key=lambda entry: float(entry.get("territory_instability", 0) or 0), reverse=True)
    return territories


def refresh_social_snapshot(game_state: dict) -> dict:
    next_state = dict(game_state)
    social = _social_base(next_state)
    social["current_round"] = _game_round(next_state)
    settings = next_state.get("settings", {})
    econ = next_state.get("econ", {})
    macro = _macro_metrics(next_state, econ, settings)
    tracked_entries = _tracked_property_entries(next_state)
    tracked_props = []
    for prop in next_state.get("properties", []):
        if str(prop.get("id")) in tracked_entries:
            tracked_props.append(dict(prop))

    rent_reference = _rent_reference(next_state, econ, tracked_props)
    median_net_worth = _median_net_worth(next_state)
    player_lookup = _player_index(next_state)

    property_entries = {}
    for prop in tracked_props:
        prop_id = str(prop.get("id"))
        property_entries[prop_id] = _coerce_property_for_social(
            next_state,
            prop,
            tracked_entries.get(prop_id, {}),
            macro,
            rent_reference,
            median_net_worth,
            player_lookup,
        )

    territories = _territory_snapshot(list(property_entries.values()), player_lookup)
    territories_by_key = {entry["territory_key"]: entry for entry in territories}
    for entry in property_entries.values():
        territory_key = _territory_key(entry.get("owner_id"), entry.get("region"))
        territory = territories_by_key.get(territory_key)
        entry["territory_key"] = territory_key
        entry["territory_instability"] = float(territory.get("territory_instability", 0) if territory else 0)
        entry["negotiation_target"] = _calculate_negotiation_target(
            next(
                (candidate for candidate in tracked_props if str(candidate.get("id")) == str(entry.get("property_id"))),
                {},
            ),
            entry,
            next_state,
            macro["mode"],
            float(entry.get("territory_instability", 0) or 0),
            float(macro["overall_rage"] or 0),
            float(macro["stability_percent"] or 0),
            macro["mode_profile"],
        )
        entry["next_state"] = entry.get("incident_type") or _state_from_tension(
            float(entry.get("tension", 0) or 0),
            float(entry.get("territory_instability", 0) or 0),
            float(macro["overall_rage"] or 0),
            float(macro["stability_percent"] or 0),
            macro["mode_profile"],
        )
        entry["spread_block_active"] = int(entry.get("spread_blocked_until_round", 0) or 0) >= social["current_round"]
        entry["territory_rent_control_active"] = _territory_rent_control_active(social, entry, social["current_round"])

    grievance_totals = {key: float(value or 0) for key, value in macro["macro_points"].items()}
    grievance_totals.setdefault("rent_extraction", 0.0)
    for entry in property_entries.values():
        grievance = entry.get("dominant_grievance")
        if grievance:
            grievance_totals[grievance] = grievance_totals.get(grievance, 0.0) + (float(entry.get("tension", 0) or 0) * 0.12)

    active_incidents = []
    severity_counts = {"protest": 0, "strike": 0, "uprising": 0, "revolution": 0}
    unionized_count = 0
    for entry in property_entries.values():
        if entry.get("former_owner_id") is not None:
            unionized_count += 1
        incident_type = entry.get("incident_type")
        if not incident_type:
            continue
        severity_counts[incident_type] = severity_counts.get(incident_type, 0) + 1
        active_incidents.append(
            {
                "incident_id": entry.get("incident_id") or f"prop_{entry.get('property_id')}_round_{social['current_round']}",
                "property_id": entry.get("property_id"),
                "property_name": next(
                    (candidate.get("name") for candidate in tracked_props if int(candidate.get("id", 0) or 0) == int(entry.get("property_id", 0) or 0)),
                    f"Property #{entry.get('property_id')}",
                ),
                "territory_key": entry.get("territory_key"),
                "region": entry.get("region"),
                "incident_type": incident_type,
                "remaining_rounds": int(entry.get("remaining_rounds", 0) or 0),
                "dominant_grievance": entry.get("dominant_grievance"),
                "negotiation_target": _round(entry.get("negotiation_target", 0), 2),
                "negotiation_committed": _round(entry.get("negotiation_committed", 0), 2),
                "recommended_lobby_targets": list(entry.get("recommended_lobby_targets") or []),
                "recommended_actions": list(entry.get("recommended_actions") or []),
                "eta_to_next_threshold": entry.get("eta_to_next_threshold"),
                "reintegration_progress": int(entry.get("reintegration_progress", 0) or 0),
                "spread_block_active": bool(entry.get("spread_block_active")),
            }
        )

    next_likely = next(
        (
            entry
            for entry in sorted(property_entries.values(), key=lambda item: float(item.get("tension", 0) or 0), reverse=True)
            if not entry.get("incident_type") and float(entry.get("tension", 0) or 0) >= INCIDENT_THRESHOLDS["watchlist"]
        ),
        None,
    )
    hottest_territory = territories[0] if territories else None

    social.update(
        {
            "overall_rage": _round(macro["overall_rage"], 1),
            "stability_percent": int(macro["stability_percent"]),
            "grievance_mix": {
                key: _round(value, 1)
                for key, value in sorted(grievance_totals.items(), key=lambda item: item[1], reverse=True)
                if value > 0.05
            },
            "territories": territories,
            "properties": property_entries,
            "active_incidents": active_incidents,
            "unionized_property_count": unionized_count,
            "national_flashpoint": {
                "active_incidents_by_severity": severity_counts,
                "hottest_territory": hottest_territory,
                "next_likely_escalation": {
                    "property_id": next_likely.get("property_id") if next_likely else None,
                    "tension": next_likely.get("tension") if next_likely else None,
                    "next_state": _state_from_tension(
                        float(next_likely.get("tension", 0) or 0),
                        float(next_likely.get("territory_instability", 0) or 0),
                        float(macro["overall_rage"] or 0),
                        float(macro["stability_percent"] or 0),
                        macro["mode_profile"],
                    ) if next_likely else None,
                },
            },
        }
    )

    next_state["social"] = social
    next_state["rage"] = social["overall_rage"]
    return next_state


def ensure_social_state(game_state: dict) -> dict:
    return refresh_social_snapshot(game_state)


def calculate_union_charge(prop: dict, game_state: dict, social: dict | None = None) -> float:
    social = social or _social_base(game_state)
    social_entry = (social.get("properties") or {}).get(str(prop.get("id"))) or {}
    if not property_is_unionized({**prop, **social_entry}, game_state):
        return 0.0

    econ = game_state.get("econ", {})
    union_level = int(clamp(float(social_entry.get("union_development_level", 1) or 1), 1.0, 5.0))
    if prop.get("property_type") == "transit":
        base_rent = max(25.0, float(prop.get("base_price", 0) or 0) * 0.125)
    else:
        base_rent = float(calculate_rent_with_dev(prop, econ, game_state) or 0)

    union_charge = base_rent * float(UNION_BLOC_MULTIPLIERS.get(union_level, 2.0)) * (1.0 + float(econ.get("inflation_rate", 0) or 0))
    return _round(union_charge, 2)


def _append_log(game_state: dict, event_type: str, description: str, **extra: Any) -> dict:
    next_state = dict(game_state)
    log_buffer = list(next_state.get("log_buffer", []))
    log_buffer.append(
        {
            "event_type": event_type,
            "description": description,
            "timestamp": datetime.utcnow().isoformat(),
            **extra,
        }
    )
    next_state["log_buffer"] = log_buffer[-100:]
    return next_state


def _territory_rent_control_active(social: dict, prop_or_entry: dict, current_round: int) -> bool:
    territory_key = _territory_key(prop_or_entry.get("owner_id"), prop_or_entry.get("region"))
    region = prop_or_entry.get("region")
    for effect in social.get("active_effects", []):
        if effect.get("effect_type") != "territory_rent_control":
            continue
        if int(effect.get("expires_round", 0) or 0) < current_round:
            continue
        target_territory_key = effect.get("target_territory_key")
        if target_territory_key and territory_key and target_territory_key == territory_key:
            return True
        if not target_territory_key and effect.get("target_region") == region:
            return True
    return False


def _apply_solidarity_levy(next_state: dict, owner_id: Any, *, levy_cap: float = 120.0) -> tuple[dict, float]:
    if owner_id in {None, PROLETARIAT_UNION_ID}:
        return next_state, 0.0

    player_lookup = _player_index(next_state)
    owner = player_lookup.get(owner_id)
    if owner is None:
        return next_state, 0.0

    owner_balance = float(owner.get("balance", 0) or 0)
    levy = min(float(levy_cap or 0), max(0.0, owner_balance - 1.0))
    levy = _round(levy, 2)
    if levy <= 0:
        return next_state, 0.0

    next_state, _ = spend_player_balance(next_state, int(owner_id), levy)
    econ = dict(next_state.get("econ", {}))
    econ["treasury_balance"] = _round(float(econ.get("treasury_balance", 0) or 0) + levy, 2)
    next_state["econ"] = econ
    return next_state, levy


def submit_negotiation_contribution(
    game_state: dict,
    *,
    property_id: int,
    player_id: int,
    amount: float,
) -> tuple[dict, dict]:
    next_state = refresh_social_snapshot(game_state)
    social = _social_base(next_state)
    prop_key = str(property_id)
    prop_entry = dict((social.get("properties") or {}).get(prop_key) or {})
    player_lookup = _player_index(next_state)
    player = player_lookup.get(player_id)
    if player is None or player.get("is_bankrupt"):
        raise ValueError("Only active players may negotiate.")
    if not prop_entry or not prop_entry.get("incident_type"):
        raise ValueError("Negotiation is only available for active incidents.")

    contribution = _round(amount, 2)
    if contribution <= 0:
        raise ValueError("Contribution must be positive.")
    if float(player.get("balance", 0) or 0) < contribution:
        raise ValueError("Insufficient funds.")

    current_round = _game_round(next_state)
    prior_entries = list(prop_entry.get("negotiation_contributions") or [])
    if any(int(entry.get("player_id", 0) or 0) == player_id and int(entry.get("round", 0) or 0) == current_round for entry in prior_entries):
        raise ValueError("You may only contribute to the same incident once per round.")

    efficiency_multiplier = 1.0

    effective_amount = _round(contribution * efficiency_multiplier, 2)
    next_state, updated_player = spend_player_balance(next_state, player_id, contribution)
    social = _social_base(next_state)
    properties = dict(social.get("properties") or {})
    prop_entry = dict(properties.get(prop_key) or prop_entry)
    prop_entry["negotiation_committed"] = _round(float(prop_entry.get("negotiation_committed", 0) or 0) + effective_amount, 2)
    prop_entry["negotiation_contributions"] = [
        *prior_entries,
        {
            "player_id": player_id,
            "amount": contribution,
            "effective_amount": effective_amount,
            "round": current_round,
            "deal_bonus": False,
        },
    ]
    properties[prop_key] = prop_entry
    social["properties"] = properties
    next_state["social"] = social
    next_state = _append_log(
        next_state,
        "negotiation_pending",
        f"{player.get('username', 'Player')} committed ${contribution:.2f} toward local concessions for property #{property_id}.",
        player_id=player_id,
        property_id=property_id,
        round=current_round,
    )
    next_state = refresh_social_snapshot(next_state)
    result_entry = (next_state.get("social") or {}).get("properties", {}).get(prop_key, {})
    return next_state, {
        "property_id": property_id,
        "contribution": contribution,
        "effective_contribution": effective_amount,
        "negotiation_committed": _round(result_entry.get("negotiation_committed", 0), 2),
        "negotiation_target": _round(result_entry.get("negotiation_target", 0), 2),
        "remaining_balance": updated_player.get("balance") if updated_player else None,
    }


def submit_minarchist_emergency_reform(
    game_state: dict,
    *,
    player_id: int,
    reform_type: str,
    property_id: int | None = None,
    target_region: str | None = None,
) -> tuple[dict, dict]:
    next_state = refresh_social_snapshot(game_state)
    social = _social_base(next_state)
    econ = dict(next_state.get("econ", {}))
    current_round = _game_round(next_state)
    resolution_round = current_round + 1

    if normalize_government_type(econ.get("gov_type") or econ.get("government_type") or next_state.get("settings", {}).get("government_type")) != "minarchism":
        raise ValueError("Emergency reforms are only available under Minarchism.")
    if reform_type not in EMERGENCY_REFORM_TARGETS:
        raise ValueError("Select a valid emergency reform.")
    if not social.get("active_incidents"):
        raise ValueError("Emergency reforms only unlock while incidents are active.")
    if any(int(entry.get("round", 0) or 0) == resolution_round for entry in social.get("emergency_reforms", [])):
        raise ValueError("Only one emergency reform may succeed each round under Minarchism.")

    effect = {
        "reform_type": reform_type,
        "player_id": player_id,
        "property_id": property_id,
        "target_region": target_region,
        "submitted_round": current_round,
        "round": resolution_round,
        "success": True,
    }

    active_effects = list(social.get("active_effects", []))
    if reform_type == "private_relief_contract":
        if property_id is None:
            raise ValueError("A target property is required for private relief contracts.")
        effect.update(
            {
                "effect_type": "private_relief_contract",
                "coverage_bonus": 0.35,
                "expires_round": resolution_round,
            }
        )
    elif reform_type == "tax_moratorium":
        econ["tax_multiplier"] = _round(max(0.0, float(econ.get("tax_multiplier", 0) or 0) - 0.03), 4)
        effect.update(
            {
                "effect_type": "tax_moratorium",
                "field": "tax_multiplier",
                "delta": 0.03,
                "expires_round": resolution_round + 1,
            }
        )
    elif reform_type == "property_rights_compact":
        target_territory_key = None
        if not target_region:
            if property_id is None:
                raise ValueError("A target territory is required for property rights compacts.")
            prop = next((entry for entry in next_state.get("properties", []) if int(entry.get("id", 0) or 0) == int(property_id)), None)
            target_region = prop.get("region") if prop else None
            if prop is not None:
                target_territory_key = _territory_key(prop.get("owner_id"), prop.get("region"))
        if not target_region:
            raise ValueError("A target territory is required for property rights compacts.")
        if target_territory_key is None and property_id is not None:
            entry = dict((social.get("properties") or {}).get(str(property_id)) or {})
            target_territory_key = entry.get("territory_key") or _territory_key(entry.get("owner_id"), target_region)
        econ["stability"] = _round(min(1.0, float(econ.get("stability", 0.7) or 0.7) + 0.05), 4)
        effect.update(
            {
                "effect_type": "property_rights_compact",
                "field": "stability",
                "delta": 0.05,
                "target_region": target_region,
                "target_territory_key": target_territory_key,
                "expires_round": resolution_round,
            }
        )

    active_effects.append(effect)
    emergency_reforms = [*social.get("emergency_reforms", []), effect]
    social["active_effects"] = active_effects
    social["emergency_reforms"] = emergency_reforms[-24:]
    next_state["social"] = social
    next_state["econ"] = econ
    next_state = _append_log(
        next_state,
        "emergency_reform",
        f"Minarchist emergency reform '{reform_type}' was activated.",
        player_id=player_id,
        property_id=property_id,
        region=target_region,
        round=resolution_round,
    )
    next_state = refresh_social_snapshot(next_state)
    return next_state, effect


def _revert_expired_effects(game_state: dict, current_round: int) -> dict:
    next_state = dict(game_state)
    social = _social_base(next_state)
    econ = dict(next_state.get("econ", {}))
    remaining_effects = []

    for effect in social.get("active_effects", []):
        expires_round = int(effect.get("expires_round", current_round) or current_round)
        if expires_round >= current_round:
            remaining_effects.append(effect)
            continue

        field = effect.get("field")
        delta = float(effect.get("delta", 0) or 0)
        if field == "tax_multiplier" and delta > 0:
            econ["tax_multiplier"] = _round(float(econ.get("tax_multiplier", 0) or 0) + delta, 4)
        elif field == "welfare_payout" and delta > 0:
            econ["welfare_payout"] = _round(max(0.0, float(econ.get("welfare_payout", 0) or 0) - delta), 2)
        elif field == "stability" and delta > 0:
            econ["stability"] = _round(max(0.0, float(econ.get("stability", 0.7) or 0.7) - delta), 4)

    social["active_effects"] = remaining_effects
    next_state["social"] = social
    next_state["econ"] = econ
    return next_state


def _duration_for_incident(incident_type: str, stability_percent: float, region_momentum_count: int, mode: str) -> int:
    stability_penalty = int(math.ceil(max(0.0, 55.0 - stability_percent) / 10.0))
    momentum_penalty = min(2, region_momentum_count)
    duration = INCIDENT_BASE_DURATION[incident_type] + stability_penalty + momentum_penalty + MODE_DURATION_BONUS[mode]
    return int(clamp(duration, 1, 10))


def _record_incident_history(game_state: dict, property_id: int, region: str | None, incident_type: str) -> dict:
    next_state = dict(game_state)
    social = _social_base(next_state)
    history = list(social.get("incident_history", []))
    history.append(
        {
            "property_id": property_id,
            "region": region,
            "incident_type": incident_type,
            "round": _game_round(next_state),
            "timestamp": datetime.utcnow().isoformat(),
        }
    )
    social["incident_history"] = history[-80:]
    next_state["social"] = social
    return next_state


def _incident_event_payload(game_state: dict, property_id: int, *, incident_type: str | None = None) -> dict:
    social = _social_snapshot(game_state)
    entry = dict((social.get("properties") or {}).get(str(property_id)) or {})
    prop = next(
        (candidate for candidate in game_state.get("properties", []) if int(candidate.get("id", 0) or 0) == int(property_id)),
        {},
    )
    player_lookup = _player_index(game_state)
    owner_id = prop.get("owner_id", entry.get("owner_id"))
    grievance = entry.get("dominant_grievance")
    return {
        "property_id": property_id,
        "property_name": prop.get("name") or f"Property #{property_id}",
        "region": prop.get("region") or entry.get("region"),
        "territory_key": entry.get("territory_key") or _territory_key(owner_id, prop.get("region") or entry.get("region")),
        "incident_type": incident_type or entry.get("incident_type"),
        "remaining_rounds": int(entry.get("remaining_rounds", 0) or 0),
        "dominant_grievance": grievance,
        "negotiation_target": _round(entry.get("negotiation_target", 0), 2),
        "negotiation_committed": _round(entry.get("negotiation_committed", 0), 2),
        "recommended_lobby_targets": list(entry.get("recommended_lobby_targets") or GRIEVANCE_POLICY_TARGETS.get(grievance, [])),
        "recommended_actions": list(entry.get("recommended_actions") or []),
        "reintegration_progress": int(entry.get("reintegration_progress", 0) or 0),
        "spread_block_active": bool(entry.get("spread_block_active")),
        "former_owner_id": entry.get("former_owner_id"),
        "current_owner_id": owner_id,
        "current_owner_name": _owner_label(owner_id, player_lookup),
        "eta_to_next_threshold": entry.get("eta_to_next_threshold"),
    }


def _emit_social_event(socketio_instance, event_name: str, match_id: int | None, payload: dict) -> None:
    if not socketio_instance or not match_id:
        return
    socketio_instance.emit(event_name, payload, room=str(match_id))


def _start_revolution(
    game_state: dict,
    *,
    source_property_id: int,
    socketio_instance=None,
    match_id: int | None = None,
) -> tuple[dict, list[int]]:
    next_state = dict(game_state)
    social = _social_snapshot(next_state)
    current_round = _game_round(next_state)
    source_entry = (social.get("properties") or {}).get(str(source_property_id)) or {}
    source_prop = next((entry for entry in next_state.get("properties", []) if int(entry.get("id", 0) or 0) == int(source_property_id)), None)
    if source_prop is None:
        return next_state, []

    region = source_prop.get("region")
    source_owner_id = source_entry.get("former_owner_id") or source_prop.get("owner_id")
    territory_key = _territory_key(source_owner_id, region)
    revolution_duration = _duration_for_incident(
        "revolution",
        float(social.get("stability_percent", 70) or 70),
        _recent_incident_count(social, region=region, rounds_back=3),
        _normalize_mode(next_state.get("settings", {})),
    )
    candidates = []
    for prop in next_state.get("properties", []):
        prop_id = int(prop.get("id", 0) or 0)
        entry = (social.get("properties") or {}).get(str(prop_id)) or {}
        if prop.get("region") != region:
            continue
        if prop.get("owner_id") != source_owner_id:
            continue
        if property_is_unionized({**prop, **entry}, next_state):
            continue
        if float(entry.get("tension", 0) or 0) < 85.0:
            continue
        if entry.get("watch_state") not in {"critical_watch", "active_incident"}:
            continue
        candidates.append((float(entry.get("tension", 0) or 0), prop, entry))

    candidates.sort(key=lambda item: item[0], reverse=True)
    selected = candidates if len(candidates) > 1 else candidates[:1]

    if not selected:
        selected = [(float(source_entry.get("tension", 0) or 0), source_prop, source_entry)]

    selected_ids = []
    updated_props = []
    properties_map = {str(key): dict(value) for key, value in (social.get("properties") or {}).items()}
    selected_lookup = {int(prop[1].get("id", 0) or 0): (prop[1], prop[2]) for prop in selected}
    for prop in next_state.get("properties", []):
        prop_id = int(prop.get("id", 0) or 0)
        if prop_id not in selected_lookup:
            updated_props.append(dict(prop))
            continue
        selected_prop, selected_entry = selected_lookup[prop_id]
        former_owner_id = selected_prop.get("owner_id")
        updated_prop = dict(selected_prop)
        updated_prop["owner_id"] = PROLETARIAT_UNION_ID
        updated_prop["dev_level"] = max(0, int(updated_prop.get("dev_level", 0) or 0) - 1)
        updated_props.append(updated_prop)
        selected_ids.append(prop_id)

        properties_map[str(prop_id)] = {
            **dict(properties_map.get(str(prop_id)) or {}),
            "incident_id": f"prop_{prop_id}_round_{current_round}",
            "incident_type": "revolution",
            "remaining_rounds": revolution_duration,
            "former_owner_id": former_owner_id,
            "union_territory_key": territory_key,
            "union_started_round": current_round,
            "minimum_hold_rounds": revolution_duration,
            "union_development_level": int(clamp(1 + math.floor(max(0.0, float(social.get("overall_rage", 0) or 0) - 80.0) / 5.0), 1, 5)),
            "reintegration_progress": 0,
            "last_started_round": current_round,
        }

    social["properties"] = properties_map
    next_state["social"] = social
    next_state["properties"] = updated_props
    next_state = refresh_social_snapshot(next_state)
    next_state = _append_log(
        next_state,
        "revolution_started",
        f"Proletariat revolution seized {len(selected_ids)} properties in {region}.",
        property_id=source_property_id,
        region=region,
        round=current_round,
    )
    seized_properties = []
    for prop_id in selected_ids:
        payload = {
            "match_id": match_id,
            "union_territory_key": territory_key,
            **_incident_event_payload(next_state, prop_id, incident_type="revolution"),
        }
        seized_properties.append({"property_id": prop_id, "property_name": payload.get("property_name")})
        _emit_social_event(
            socketio_instance,
            "union_property_joined",
            match_id,
            payload,
        )

    source_payload = _incident_event_payload(next_state, source_property_id, incident_type="revolution")
    _emit_social_event(
        socketio_instance,
        "revolution_started",
        match_id,
        {
            "match_id": match_id,
            **source_payload,
            "union_territory_key": territory_key,
            "seized_property_ids": selected_ids,
            "seized_properties": seized_properties,
        },
    )
    return next_state, selected_ids


def _start_incident(
    game_state: dict,
    *,
    property_id: int,
    incident_type: str,
    socketio_instance=None,
    match_id: int | None = None,
) -> dict:
    next_state = dict(game_state)
    social = _social_base(next_state)
    current_round = _game_round(next_state)
    prop = next((entry for entry in next_state.get("properties", []) if int(entry.get("id", 0) or 0) == int(property_id)), None)
    if prop is None:
        return next_state
    prop_key = str(property_id)
    prop_entry = dict((social.get("properties") or {}).get(prop_key) or {})
    region_momentum_count = _recent_incident_count(social, region=prop.get("region"), rounds_back=3)
    duration = _duration_for_incident(
        incident_type,
        float(social.get("stability_percent", 70) or 70),
        region_momentum_count,
        _normalize_mode(next_state.get("settings", {})),
    )

    if incident_type == "revolution":
        next_state, _ = _start_revolution(
            next_state,
            source_property_id=property_id,
            socketio_instance=socketio_instance,
            match_id=match_id,
        )
        return _record_incident_history(next_state, property_id, prop.get("region"), incident_type)

    if incident_type == "uprising":
        updated_props = []
        for entry in next_state.get("properties", []):
            if int(entry.get("id", 0) or 0) == property_id:
                updated_props.append({**entry, "dev_level": max(0, int(entry.get("dev_level", 0) or 0) - 1)})
            else:
                updated_props.append(dict(entry))
        next_state["properties"] = updated_props

    properties_map = {str(key): dict(value) for key, value in (social.get("properties") or {}).items()}
    properties_map[prop_key] = {
        **dict(properties_map.get(prop_key) or {}),
        "incident_id": f"prop_{property_id}_round_{current_round}",
        "incident_type": incident_type,
        "remaining_rounds": duration,
        "last_started_round": current_round,
    }
    social["properties"] = properties_map
    next_state["social"] = social
    next_state = refresh_social_snapshot(next_state)
    next_state = _append_log(
        next_state,
        "revolt_started",
        f"{incident_type.title()} started on {prop.get('name', 'a property')}.",
        property_id=property_id,
        region=prop.get("region"),
        round=current_round,
    )
    _emit_social_event(
        socketio_instance,
        "revolt_started",
        match_id,
        {
            "match_id": match_id,
            **_incident_event_payload(next_state, property_id, incident_type=incident_type),
        },
    )
    return _record_incident_history(next_state, property_id, prop.get("region"), incident_type)


def _clear_incident(next_state: dict, property_id: int, socketio_instance=None, match_id: int | None = None) -> dict:
    social = _social_snapshot(next_state)
    properties_map = {str(key): dict(value) for key, value in (social.get("properties") or {}).items()}
    entry = dict(properties_map.get(str(property_id)) or {})
    if not entry.get("incident_type"):
        return next_state
    previous_payload = _incident_event_payload(next_state, property_id, incident_type=entry.get("incident_type"))
    entry["incident_id"] = None
    entry["incident_type"] = None
    entry["remaining_rounds"] = 0
    entry["re_escalation_immunity_rounds"] = max(0, int(entry.get("re_escalation_immunity_rounds", 0) or 0))
    if float(entry.get("tension", 0) or 0) < INCIDENT_THRESHOLDS["watchlist"]:
        entry["negotiation_committed"] = 0.0
        entry["negotiation_contributions"] = []
    properties_map[str(property_id)] = entry
    social["properties"] = properties_map
    next_state["social"] = social
    _emit_social_event(
        socketio_instance,
        "revolt_resolved",
        match_id,
        {
            "match_id": match_id,
            **previous_payload,
        },
    )
    return next_state


def _apply_protest_concession(next_state: dict, property_id: int) -> dict:
    social = _social_snapshot(next_state)
    entry = (social.get("properties") or {}).get(str(property_id)) or {}
    dominant = entry.get("dominant_grievance")
    econ = dict(next_state.get("econ", {}))
    current_round = _game_round(next_state)
    active_effects = list(social.get("active_effects", []))
    prop = next((candidate for candidate in next_state.get("properties", []) if int(candidate.get("id", 0) or 0) == property_id), None)
    target_territory_key = _territory_key(entry.get("owner_id") or (prop or {}).get("owner_id"), entry.get("region") or (prop or {}).get("region"))

    if dominant == "welfare_shortfall":
        econ["welfare_payout"] = _round(min(100.0, float(econ.get("welfare_payout", 0) or 0) + 8.0), 2)
        active_effects.append({"effect_type": "protest_welfare_relief", "field": "welfare_payout", "delta": 8.0, "expires_round": current_round + 3})
    elif dominant == "tax_pressure":
        econ["tax_multiplier"] = _round(max(0.0, float(econ.get("tax_multiplier", 0) or 0) - 0.03), 4)
        active_effects.append({"effect_type": "protest_tax_relief", "field": "tax_multiplier", "delta": 0.03, "expires_round": current_round + 3})
    elif dominant == "treasury_distress":
        next_state, _ = _apply_solidarity_levy(next_state, (prop or {}).get("owner_id"))
        econ = dict(next_state.get("econ", {}))
    elif dominant == "rent_extraction":
        active_effects.append(
            {
                "effect_type": "territory_rent_control",
                "target_region": entry.get("region") or (prop or {}).get("region"),
                "target_territory_key": target_territory_key,
                "expires_round": current_round + 2,
            }
        )
    elif dominant == "inequality":
        next_state, _ = _apply_solidarity_levy(next_state, (prop or {}).get("owner_id"), levy_cap=140.0)
        econ = dict(next_state.get("econ", {}))
        econ["stability"] = _round(min(1.0, float(econ.get("stability", 0.7) or 0.7) + 0.03), 4)
    elif dominant == "inflation_pressure":
        active_effects.append({"effect_type": "inflation_drift_halved", "expires_round": current_round + 2})

    social["active_effects"] = active_effects
    next_state["social"] = social
    next_state["econ"] = econ
    return next_state


def _matching_success_for_entry(game_state: dict, entry: dict, current_round: int) -> float:
    grievance = entry.get("dominant_grievance") or "low_stability"
    multiplier = _matching_success_multiplier(game_state, grievance, current_round)
    if multiplier > 0:
        return multiplier

    social = _social_base(game_state)
    for effect in social.get("emergency_reforms", []):
        if int(effect.get("round", 0) or 0) != current_round:
            continue
        reform_type = effect.get("reform_type")
        reform_meta = EMERGENCY_REFORM_REASONS.get(reform_type, {})
        if reform_meta.get("matching") and int(effect.get("property_id", 0) or 0) == int(entry.get("property_id", 0) or 0):
            return 1.0
        if grievance in reform_meta.get("grievances", set()) and (
            effect.get("target_region") is None or effect.get("target_region") == entry.get("region")
        ):
            return 1.0
    return 0.0


def _coverage_bonus_from_effects(game_state: dict, property_id: int, current_round: int) -> float:
    social = _social_base(game_state)
    for effect in social.get("active_effects", []):
        if effect.get("effect_type") != "private_relief_contract":
            continue
        if int(effect.get("property_id", 0) or 0) != int(property_id):
            continue
        if int(effect.get("expires_round", current_round) or current_round) < current_round:
            continue
        return float(effect.get("coverage_bonus", 0.35) or 0.35)
    return 0.0


def _update_union_progress(next_state: dict, property_id: int, new_incident_regions: set[str]) -> dict:
    refreshed = refresh_social_snapshot(next_state)
    social = _social_snapshot(refreshed)
    entry = dict((social.get("properties") or {}).get(str(property_id)) or {})
    if entry.get("former_owner_id") is None:
        return refreshed

    current_round = _game_round(refreshed)
    overall_rage = float(social.get("overall_rage", 0) or 0)
    stability_percent = float(social.get("stability_percent", 70) or 70)
    coverage = clamp(
        (float(entry.get("negotiation_committed", 0) or 0) / max(1.0, float(entry.get("negotiation_target", 0) or 1.0)))
        + _coverage_bonus_from_effects(refreshed, property_id, current_round),
        0.0,
        1.5,
    )
    matching_active = _has_active_relief(refreshed, entry.get("dominant_grievance") or "low_stability", current_round)
    matching_success = _matching_success_for_entry(refreshed, entry, current_round) > 0
    treasury_target = float(_macro_metrics(refreshed, refreshed.get("econ", {}), refreshed.get("settings", {})).get("treasury_target", 400.0) or 400.0)
    treasury_balance = float(refreshed.get("econ", {}).get("treasury_balance", 0) or 0)

    target_union_level = int(clamp(1 + math.floor(max(0.0, overall_rage - 80.0) / 5.0), 1, 5))
    if coverage >= 1.0:
        target_union_level = max(1, target_union_level - 1)
    if matching_success:
        target_union_level = max(1, target_union_level - 1)
    if stability_percent >= 60.0 and overall_rage <= 55.0:
        target_union_level = max(1, target_union_level - 1)

    union_level = int(entry.get("union_development_level", 1) or 1)
    if union_level < target_union_level:
        union_level += 1
    elif union_level > target_union_level:
        union_level -= 1

    progress_gain = 0
    if coverage >= 1.0:
        progress_gain += 25
    elif coverage >= 0.5:
        progress_gain += 12
    if matching_success:
        progress_gain += 20
    if matching_active:
        progress_gain += 15
    if stability_percent >= 60.0:
        progress_gain += 15
    if overall_rage <= 50.0:
        progress_gain += 10
    if treasury_balance >= treasury_target:
        progress_gain += 10
    if float(entry.get("tension", 0) or 0) >= 85.0:
        progress_gain -= 15
    if entry.get("region") in new_incident_regions:
        progress_gain -= 10

    entry["union_development_level"] = int(clamp(union_level, 1, 5))
    entry["reintegration_progress"] = int(clamp(float(entry.get("reintegration_progress", 0) or 0) + progress_gain, 0.0, 100.0))

    properties_map = {str(key): dict(value) for key, value in (social.get("properties") or {}).items()}
    properties_map[str(property_id)] = {**dict(properties_map.get(str(property_id)) or {}), **entry}
    social["properties"] = properties_map
    refreshed["social"] = social
    return refreshed


def _reintegration_complete(next_state: dict, property_id: int) -> bool:
    social = _social_snapshot(next_state)
    entry = dict((social.get("properties") or {}).get(str(property_id)) or {})
    if entry.get("former_owner_id") is None:
        return False
    current_round = _game_round(next_state)
    union_started_round = int(entry.get("union_started_round", current_round) or current_round)
    minimum_hold_rounds = int(entry.get("minimum_hold_rounds", INCIDENT_BASE_DURATION["revolution"]) or INCIDENT_BASE_DURATION["revolution"])
    hold_elapsed = (current_round - union_started_round) >= minimum_hold_rounds
    return bool(
        hold_elapsed
        and int(entry.get("reintegration_progress", 0) or 0) >= 100
        and float(entry.get("tension", 0) or 0) < 70.0
    )


def _restore_from_union(next_state: dict, property_id: int, socketio_instance=None, match_id: int | None = None) -> dict:
    social = _social_base(next_state)
    entry = dict((social.get("properties") or {}).get(str(property_id)) or {})
    former_owner_id = entry.get("former_owner_id")
    player_lookup = _player_index(next_state)
    restored_owner = former_owner_id if former_owner_id in player_lookup and not player_lookup[former_owner_id].get("is_bankrupt") else None

    updated_props = []
    for prop in next_state.get("properties", []):
        if int(prop.get("id", 0) or 0) == int(property_id):
            updated_props.append({**prop, "owner_id": restored_owner})
        else:
            updated_props.append(dict(prop))
    next_state["properties"] = updated_props

    entry["former_owner_id"] = None
    entry["union_territory_key"] = None
    entry["incident_type"] = None
    entry["remaining_rounds"] = 0
    entry["union_started_round"] = None
    entry["minimum_hold_rounds"] = None
    entry["union_development_level"] = 0
    entry["reintegration_progress"] = 0
    entry["negotiation_committed"] = 0.0
    entry["negotiation_contributions"] = []
    properties_map = {str(key): dict(value) for key, value in (social.get("properties") or {}).items()}
    properties_map[str(property_id)] = entry
    social["properties"] = properties_map
    next_state["social"] = social
    _emit_social_event(
        socketio_instance,
        "union_property_left",
        match_id,
        {
            "match_id": match_id,
            **_incident_event_payload(next_state, property_id, incident_type=None),
            "restored_owner_id": restored_owner,
        },
    )
    return next_state


def _apply_union_spread(next_state: dict, socketio_instance=None, match_id: int | None = None) -> dict:
    refreshed = refresh_social_snapshot(next_state)
    social = _social_snapshot(refreshed)
    mode = _normalize_mode(refreshed.get("settings", {}))
    profile = MODE_PROFILE[mode]
    overall_rage = float(social.get("overall_rage", 0) or 0)
    stability_percent = float(social.get("stability_percent", 70) or 70)
    if overall_rage < float(profile["union_spread_rage_gate"]) or stability_percent > float(profile["union_spread_stability_gate"]):
        return refreshed

    spread_count = MODE_SPREAD_COUNTS[mode]
    current_round = _game_round(refreshed)
    unionized_territories = {
        entry.get("union_territory_key") or _territory_key(entry.get("former_owner_id"), entry.get("region"))
        for entry in (social.get("properties") or {}).values()
        if entry.get("former_owner_id") is not None and entry.get("region")
    }
    blocked_territories = {
        effect.get("target_territory_key")
        for effect in social.get("active_effects", [])
        if effect.get("effect_type") == "property_rights_compact"
        and int(effect.get("expires_round", 0) or 0) >= current_round
        and effect.get("target_territory_key")
    }
    blocked_territories.update(
        entry.get("union_territory_key") or _territory_key(entry.get("former_owner_id"), entry.get("region"))
        for entry in (social.get("properties") or {}).values()
        if entry.get("former_owner_id") is not None
        and int(entry.get("spread_blocked_until_round", 0) or 0) >= current_round
    )

    for territory_key in unionized_territories:
        if not territory_key or territory_key in blocked_territories:
            continue
        origin_owner_id, _, region = str(territory_key).partition("|")
        if any(
            effect.get("effect_type") == "property_rights_compact"
            and int(effect.get("expires_round", 0) or 0) >= current_round
            and not effect.get("target_territory_key")
            and effect.get("target_region") == region
            for effect in social.get("active_effects", [])
        ):
            continue
        candidates = []
        for prop in refreshed.get("properties", []):
            prop_id = int(prop.get("id", 0) or 0)
            entry = dict((social.get("properties") or {}).get(str(prop_id)) or {})
            if prop.get("region") != region:
                continue
            if str(prop.get("owner_id")) != origin_owner_id:
                continue
            if property_is_unionized({**prop, **entry}, refreshed):
                continue
            if float(entry.get("tension", 0) or 0) < 85.0:
                continue
            if entry.get("watch_state") not in {"critical_watch", "active_incident"}:
                continue
            candidates.append((float(entry.get("tension", 0) or 0), prop_id))
        candidates.sort(key=lambda item: item[0], reverse=True)
        for _, prop_id in candidates[:spread_count]:
            refreshed, _ = _start_revolution(refreshed, source_property_id=prop_id, socketio_instance=socketio_instance, match_id=match_id)
    return refreshed


def resolve_end_of_round_social_state(game_state: dict, socketio_instance=None, match_id: int | None = None) -> dict:
    current_round = _game_round(game_state)
    next_state = _revert_expired_effects(game_state, current_round)
    next_state = refresh_social_snapshot(next_state)

    social = _social_snapshot(next_state)
    properties_map = {str(key): dict(value) for key, value in (social.get("properties") or {}).items()}
    mode = _normalize_mode(next_state.get("settings", {}))
    mode_profile = MODE_PROFILE[mode]
    new_incident_regions: set[str] = set()

    for prop_id, entry in list(properties_map.items()):
        incident_type = entry.get("incident_type")
        if not incident_type:
            continue

        remaining_rounds = max(0, int(entry.get("remaining_rounds", 0) or 0) - 1)
        coverage = clamp(
            (float(entry.get("negotiation_committed", 0) or 0) / max(1.0, float(entry.get("negotiation_target", 0) or 1.0)))
            + _coverage_bonus_from_effects(next_state, int(prop_id), current_round),
            0.0,
            1.5,
        )
        relief_points = 0.0
        if coverage >= 0.5:
            remaining_rounds = max(0, remaining_rounds - 1)
            relief_points = 10.0
        if coverage >= 1.0:
            relief_points = 20.0
            entry["spread_blocked_until_round"] = current_round
        if coverage >= 1.5:
            entry["re_escalation_immunity_rounds"] = 1

        success_multiplier = _matching_success_for_entry(next_state, entry, current_round)
        if success_multiplier > 0 and incident_type in {"strike", "uprising"}:
            relief_points += 15.0 * success_multiplier
            remaining_rounds = max(0, remaining_rounds - max(1, int(math.ceil(2 * success_multiplier))))
            entry["spread_blocked_until_round"] = current_round
        elif success_multiplier > 0 and incident_type == "revolution":
            entry["reintegration_progress"] = int(clamp(float(entry.get("reintegration_progress", 0) or 0) + (20.0 * success_multiplier), 0.0, 100.0))
            entry["spread_blocked_until_round"] = current_round

        effective_tension = max(0.0, float(entry.get("tension", 0) or 0) - relief_points)
        desired_state = _state_from_tension(
            effective_tension,
            float(entry.get("territory_instability", 0) or 0),
            float(social.get("overall_rage", 0) or 0),
            float(social.get("stability_percent", 70) or 70),
            mode_profile,
        )

        if incident_type == "revolution":
            entry["remaining_rounds"] = max(1, remaining_rounds)
            properties_map[prop_id] = {**entry, "current_effective_tension": _round(effective_tension, 1)}
            continue

        if desired_state is None and incident_type == "protest":
            entry["remaining_rounds"] = 0
            properties_map[prop_id] = entry
            social["properties"] = properties_map
            next_state["social"] = social
            next_state = _clear_incident(next_state, int(prop_id), socketio_instance=socketio_instance, match_id=match_id)
            social = _social_snapshot(next_state)
            properties_map = {str(key): dict(value) for key, value in (social.get("properties") or {}).items()}
            continue

        current_rank = _sort_key_for_incident(incident_type)
        desired_rank = _sort_key_for_incident(desired_state)
        immunity_rounds = int(entry.get("re_escalation_immunity_rounds", 0) or 0)
        new_state = incident_type

        if desired_rank < current_rank:
            new_state = _previous_incident_type(incident_type)
        elif desired_rank > current_rank and remaining_rounds <= 0 and immunity_rounds <= 0:
            new_state = _next_incident_type(incident_type)
        elif desired_rank == current_rank and remaining_rounds <= 0:
            remaining_rounds = 1

        if immunity_rounds > 0:
            entry["re_escalation_immunity_rounds"] = max(0, immunity_rounds - 1)

        if new_state is None:
            entry["remaining_rounds"] = 0
            properties_map[prop_id] = entry
            social["properties"] = properties_map
            next_state["social"] = social
            next_state = _clear_incident(next_state, int(prop_id), socketio_instance=socketio_instance, match_id=match_id)
            social = _social_snapshot(next_state)
            properties_map = {str(key): dict(value) for key, value in (social.get("properties") or {}).items()}
            continue

        if new_state != incident_type:
            entry["incident_type"] = new_state
            if new_state == "uprising":
                updated_props = []
                for prop in next_state.get("properties", []):
                    if int(prop.get("id", 0) or 0) == int(prop_id):
                        updated_props.append({**prop, "dev_level": max(0, int(prop.get("dev_level", 0) or 0) - 1)})
                    else:
                        updated_props.append(dict(prop))
                next_state["properties"] = updated_props
            if new_state == "revolution":
                social["properties"] = properties_map
                next_state["social"] = social
                next_state = _start_incident(next_state, property_id=int(prop_id), incident_type="revolution", socketio_instance=socketio_instance, match_id=match_id)
                new_incident_regions.add(entry.get("region"))
                social = _social_snapshot(next_state)
                properties_map = {str(key): dict(value) for key, value in (social.get("properties") or {}).items()}
                continue
            region_momentum_count = _recent_incident_count(social, region=entry.get("region"), rounds_back=3)
            entry["remaining_rounds"] = _duration_for_incident(
                new_state,
                float(social.get("stability_percent", 70) or 70),
                region_momentum_count,
                mode,
            )
            _emit_social_event(
                socketio_instance,
                "revolt_updated",
                match_id,
                {
                    "match_id": match_id,
                    **_incident_event_payload(
                        {
                            **next_state,
                            "social": {**social, "properties": {**properties_map, prop_id: entry}},
                        },
                        int(prop_id),
                        incident_type=new_state,
                    ),
                },
            )
        else:
            entry["remaining_rounds"] = max(1, remaining_rounds)

        properties_map[prop_id] = {**entry, "current_effective_tension": _round(effective_tension, 1)}

    social["properties"] = properties_map
    next_state["social"] = social
    next_state = refresh_social_snapshot(next_state)
    social = _social_snapshot(next_state)

    active_incident_count = 0
    territory_started_counts: dict[str, int] = {}
    player_lookup = _player_index(next_state)
    candidates = []
    for prop_id, entry in (social.get("properties") or {}).items():
        if entry.get("incident_type") or entry.get("former_owner_id") is not None:
            continue
        desired_state = _state_from_tension(
            float(entry.get("tension", 0) or 0),
            float(entry.get("territory_instability", 0) or 0),
            float(social.get("overall_rage", 0) or 0),
            float(social.get("stability_percent", 70) or 70),
            mode_profile,
        )
        if desired_state is None:
            continue
        candidates.append((float(entry.get("tension", 0) or 0), int(prop_id), desired_state, dict(entry)))

    candidates.sort(key=lambda item: item[0], reverse=True)
    max_new_incidents = MODE_NEW_INCIDENT_CAPS[mode]
    for _, prop_id, desired_state, entry in candidates:
        if active_incident_count >= max_new_incidents:
            break
        territory_key = entry.get("territory_key")
        if mode != "chaos" and territory_started_counts.get(territory_key, 0) >= 1:
            continue
        next_state = _start_incident(next_state, property_id=prop_id, incident_type=desired_state, socketio_instance=socketio_instance, match_id=match_id)
        if desired_state == "protest":
            next_state = _apply_protest_concession(next_state, prop_id)
        active_incident_count += 1
        territory_started_counts[territory_key] = territory_started_counts.get(territory_key, 0) + 1
        if entry.get("region"):
            new_incident_regions.add(entry.get("region"))

    next_state = refresh_social_snapshot(next_state)
    social = _social_snapshot(next_state)
    for prop_id, entry in list((social.get("properties") or {}).items()):
        if entry.get("former_owner_id") is None:
            continue
        next_state = _update_union_progress(next_state, int(prop_id), new_incident_regions)
        if _reintegration_complete(next_state, int(prop_id)):
            next_state = _restore_from_union(next_state, int(prop_id), socketio_instance=socketio_instance, match_id=match_id)

    next_state = _apply_union_spread(next_state, socketio_instance=socketio_instance, match_id=match_id)
    next_state = refresh_social_snapshot(next_state)
    _emit_social_event(
        socketio_instance,
        "stability_update",
        match_id,
        {
            "match_id": match_id,
            "social": next_state.get("social", {}),
        },
    )
    return next_state