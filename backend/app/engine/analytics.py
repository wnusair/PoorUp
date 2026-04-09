from __future__ import annotations

from datetime import datetime
from typing import Any

from app.engine.economy import calculate_net_worth
from app.models.policy import (
    calculate_lobbying_success_chance,
    get_default_lobbying_policies,
    get_lobbying_policy_definition,
    get_lobbying_policy_key,
)

PLAYER_FINANCE_HISTORY_LIMIT = 120
LOBBYING_RESOLUTION_HISTORY_LIMIT = 24


def _empty_lobbying_player_totals(player: dict | None = None) -> dict:
    player = player or {}
    return {
        "player_id": player.get("id"),
        "username": player.get("username", "Player"),
        "total_spent": 0.0,
        "policy_totals": {},
    }


def _normalize_policy_totals(raw_policy_totals: dict | None) -> dict:
    normalized = {}
    for target, value in (raw_policy_totals or {}).items():
        if isinstance(value, dict):
            normalized[target] = {
                "policy_name": value.get("policy_name") or target,
                "amount": round(float(value.get("amount", 0) or 0), 2),
            }
        else:
            normalized[target] = {
                "policy_name": target,
                "amount": round(float(value or 0), 2),
            }
    return normalized


def _policy_metadata_map(policy_records: list[Any] | None = None, government_type: str | None = None) -> dict[str, dict]:
    metadata = {
        definition["target"]: dict(definition)
        for definition in get_default_lobbying_policies(government_type=government_type)
    }

    for record in policy_records or []:
        if hasattr(record, "target_stat"):
            target_key = get_lobbying_policy_key(target_stat=record.target_stat)
            record_data = {
                "id": getattr(record, "id", None),
                "policy_name": getattr(record, "policy_name", None),
                "target_stat": getattr(record, "target_stat", None),
                "effect_value": getattr(record, "effect_value", None),
            }
        else:
            target_key = get_lobbying_policy_key(
                target=record.get("target"),
                target_stat=record.get("target_stat"),
            )
            record_data = dict(record)

        if not target_key:
            continue

        definition = dict(metadata.get(target_key) or {})
        if record_data.get("id") is not None:
            definition["id"] = record_data.get("id")
        if record_data.get("policy_name"):
            definition["policy_name"] = record_data.get("policy_name")
        if record_data.get("target_stat"):
            definition["target_stat"] = record_data.get("target_stat")
        metadata[target_key] = definition

    return metadata


def _empty_policy_pool(policy: dict) -> dict:
    success_chance = calculate_lobbying_success_chance(
        target=policy.get("target"),
        target_stat=policy.get("target_stat"),
        total_contribution=0.0,
        contributor_count=0,
    )
    return {
        "target": policy.get("target"),
        "axis": policy.get("axis"),
        "axis_label": policy.get("axis_label"),
        "direction": policy.get("direction"),
        "direction_label": policy.get("direction_label"),
        "policy_id": policy.get("id"),
        "policy_name": policy.get("policy_name", policy.get("target", "Policy")),
        "target_stat": policy.get("target_stat"),
        "description": policy.get("description", ""),
        "cost_hint": int(policy.get("cost_hint", 0) or 0),
        "pool_total": 0.0,
        "contributor_count": 0,
        "estimated_success_chance": round(success_chance * 100, 1),
        "progress_percent": 0.0,
        "contributors": [],
    }


def initialize_lobbying_stats(
    players: list[dict],
    policy_records: list[Any] | None = None,
    government_type: str | None = None,
) -> dict:
    metadata_map = _policy_metadata_map(policy_records, government_type=government_type)
    return {
        "player_totals": {
            str(player["id"]): _empty_lobbying_player_totals(player)
            for player in players
        },
        "policy_pools": {
            target: _empty_policy_pool({"target": target, **definition})
            for target, definition in metadata_map.items()
        },
        "resolved_history": [],
    }


def ensure_lobbying_stats(game_state: dict, policy_records: list[Any] | None = None) -> dict:
    next_state = dict(game_state)
    stats = dict(next_state.get("lobbying_stats") or {})
    government_type = ((next_state.get("econ") or {}).get("gov_type") or (next_state.get("settings") or {}).get("government_type"))
    metadata_map = _policy_metadata_map(policy_records, government_type=government_type)

    player_totals = {
        str(player_id): dict(values)
        for player_id, values in (stats.get("player_totals") or {}).items()
    }
    for player in next_state.get("players", []):
        player_key = str(player["id"])
        entry = dict(player_totals.get(player_key, _empty_lobbying_player_totals(player)))
        entry["player_id"] = player["id"]
        entry["username"] = player.get("username", entry.get("username", "Player"))
        entry["total_spent"] = round(float(entry.get("total_spent", 0) or 0), 2)
        entry["policy_totals"] = _normalize_policy_totals(entry.get("policy_totals"))
        player_totals[player_key] = entry

    policy_pools = {
        key: dict(value)
        for key, value in (stats.get("policy_pools") or {}).items()
    }
    normalized_pools = {}
    for target, definition in metadata_map.items():
        pool = dict(policy_pools.get(target, _empty_policy_pool({"target": target, **definition})))
        default_pool = _empty_policy_pool({"target": target, **definition})
        pool["target"] = target
        pool["axis"] = pool.get("axis") or definition.get("axis") or default_pool.get("axis")
        pool["axis_label"] = pool.get("axis_label") or definition.get("axis_label") or default_pool.get("axis_label")
        pool["direction"] = pool.get("direction") or definition.get("direction") or default_pool.get("direction")
        pool["direction_label"] = pool.get("direction_label") or definition.get("direction_label") or default_pool.get("direction_label")
        pool["policy_id"] = pool.get("policy_id") or definition.get("id")
        pool["policy_name"] = pool.get("policy_name") or definition.get("policy_name") or target
        pool["target_stat"] = pool.get("target_stat") or definition.get("target_stat")
        pool["description"] = definition.get("description", pool.get("description", ""))
        pool["cost_hint"] = int(definition.get("cost_hint", pool.get("cost_hint", 0)) or 0)
        pool["pool_total"] = round(float(pool.get("pool_total", 0) or 0), 2)
        pool["contributor_count"] = int(pool.get("contributor_count", 0) or 0)
        pool["estimated_success_chance"] = round(float(pool.get("estimated_success_chance", default_pool["estimated_success_chance"]) or 0), 1)
        pool["progress_percent"] = round(float(pool.get("progress_percent", 0) or 0), 1)
        contributors = []
        for contributor in pool.get("contributors") or []:
            if not isinstance(contributor, dict):
                continue
            contributors.append({
                "player_id": contributor.get("player_id"),
                "username": contributor.get("username", "Player"),
                "contribution": round(float(contributor.get("contribution", 0) or 0), 2),
            })
        pool["contributors"] = contributors
        normalized_pools[target] = pool

    resolved_history = []
    for entry in stats.get("resolved_history") or []:
        if not isinstance(entry, dict):
            continue
        resolved_history.append({
            **entry,
            "total_contribution": round(float(entry.get("total_contribution", 0) or 0), 2),
            "success_chance": round(float(entry.get("success_chance", 0) or 0), 1),
        })
    resolved_history = resolved_history[-LOBBYING_RESOLUTION_HISTORY_LIMIT:]

    next_state["lobbying_stats"] = {
        "player_totals": player_totals,
        "policy_pools": normalized_pools,
        "resolved_history": resolved_history,
    }
    return next_state


def sync_lobbying_policy_pool(game_state: dict, policy, entries: list[Any]) -> dict:
    government_type = ((game_state.get("econ") or {}).get("gov_type") or (game_state.get("settings") or {}).get("government_type"))
    policy_definition = get_lobbying_policy_definition(target_stat=policy.target_stat, government_type=government_type) or {}
    target_key = get_lobbying_policy_key(target_stat=policy.target_stat)
    if not target_key:
        return game_state

    next_state = ensure_lobbying_stats(game_state, policy_records=[policy])
    stats = dict(next_state["lobbying_stats"])
    pools = {key: dict(value) for key, value in stats["policy_pools"].items()}
    players_by_id = {
        player["id"]: player.get("username", "Player")
        for player in next_state.get("players", [])
    }

    normalized_entries = []
    for entry in entries or []:
        contribution = round(float(getattr(entry, "contribution", 0) or 0), 2)
        if contribution <= 0:
            continue
        player_id = getattr(entry, "player_id", None)
        normalized_entries.append({
            "player_id": player_id,
            "username": players_by_id.get(player_id, "Player"),
            "contribution": contribution,
        })

    normalized_entries.sort(key=lambda item: item["contribution"], reverse=True)
    pool_total = round(sum(item["contribution"] for item in normalized_entries), 2)
    contributor_count = len({item["player_id"] for item in normalized_entries if item["player_id"] is not None})
    success_chance = calculate_lobbying_success_chance(
        target_stat=policy.target_stat,
        government_type=government_type,
        total_contribution=pool_total,
        contributor_count=contributor_count,
    )
    cost_hint = max(1.0, float(policy_definition.get("cost_hint", 1) or 1))

    pools[target_key] = {
        **_empty_policy_pool({"target": target_key, **policy_definition}),
        "target": target_key,
        "axis": policy_definition.get("axis"),
        "axis_label": policy_definition.get("axis_label"),
        "direction": policy_definition.get("direction"),
        "direction_label": policy_definition.get("direction_label"),
        "policy_id": policy.id,
        "policy_name": policy.policy_name,
        "target_stat": policy.target_stat,
        "description": policy_definition.get("description", ""),
        "cost_hint": int(policy_definition.get("cost_hint", 0) or 0),
        "pool_total": pool_total,
        "contributor_count": contributor_count,
        "estimated_success_chance": round(success_chance * 100, 1),
        "progress_percent": round(min(100.0, (pool_total / cost_hint) * 100), 1),
        "contributors": normalized_entries,
    }

    next_state["lobbying_stats"] = {
        **stats,
        "policy_pools": pools,
    }
    return next_state


def record_lobbying_contribution(game_state: dict, player: dict, policy, contribution: float, entries: list[Any]) -> dict:
    target_key = get_lobbying_policy_key(target_stat=policy.target_stat)
    if not target_key:
        return game_state

    contribution = round(float(contribution or 0), 2)
    if contribution <= 0:
        return game_state

    next_state = ensure_lobbying_stats(game_state, policy_records=[policy])
    stats = dict(next_state["lobbying_stats"])
    player_totals = {
        key: dict(value)
        for key, value in stats["player_totals"].items()
    }

    player_key = str(player["id"])
    player_entry = dict(player_totals.get(player_key, _empty_lobbying_player_totals(player)))
    policy_totals = _normalize_policy_totals(player_entry.get("policy_totals"))
    current_policy_total = dict(policy_totals.get(target_key, {}))
    current_policy_total["policy_name"] = policy.policy_name
    current_policy_total["amount"] = round(float(current_policy_total.get("amount", 0) or 0) + contribution, 2)
    policy_totals[target_key] = current_policy_total

    player_entry["player_id"] = player["id"]
    player_entry["username"] = player.get("username", player_entry.get("username", "Player"))
    player_entry["total_spent"] = round(float(player_entry.get("total_spent", 0) or 0) + contribution, 2)
    player_entry["policy_totals"] = policy_totals
    player_totals[player_key] = player_entry

    next_state["lobbying_stats"] = {
        **stats,
        "player_totals": player_totals,
    }
    return sync_lobbying_policy_pool(next_state, policy, entries)


def record_lobbying_resolution(
    game_state: dict,
    policy,
    *,
    success: bool,
    effect_summary: str | None,
    failure_reason: str | None,
    total_contribution: float,
    contributor_count: int,
    success_chance: float,
    round_number: int,
) -> dict:
    target_key = get_lobbying_policy_key(target_stat=policy.target_stat)
    if not target_key:
        return game_state

    next_state = ensure_lobbying_stats(game_state, policy_records=[policy])
    stats = dict(next_state["lobbying_stats"])
    pools = {
        key: dict(value)
        for key, value in stats["policy_pools"].items()
    }
    history = list(stats.get("resolved_history") or [])
    government_type = ((next_state.get("econ") or {}).get("gov_type") or (next_state.get("settings") or {}).get("government_type"))
    definition = get_lobbying_policy_definition(target_stat=policy.target_stat, government_type=government_type) or {}
    history.append({
        "timestamp": datetime.utcnow().isoformat(),
        "round": int(round_number or 0),
        "target": target_key,
        "axis": definition.get("axis"),
        "axis_label": definition.get("axis_label"),
        "direction": definition.get("direction"),
        "direction_label": definition.get("direction_label"),
        "policy_id": policy.id,
        "policy_name": policy.policy_name,
        "target_stat": policy.target_stat,
        "success": bool(success),
        "effect_summary": effect_summary or "",
        "reason": failure_reason or "",
        "total_contribution": round(float(total_contribution or 0), 2),
        "contributor_count": int(contributor_count or 0),
        "success_chance": round(float(success_chance or 0), 1),
    })

    pools[target_key] = _empty_policy_pool({"target": target_key, **definition, "id": policy.id})

    next_state["lobbying_stats"] = {
        **stats,
        "policy_pools": pools,
        "resolved_history": history[-LOBBYING_RESOLUTION_HISTORY_LIMIT:],
    }
    return next_state


def initialize_player_finance_history(game_state: dict) -> dict:
    next_state = dict(game_state)
    next_state["player_finance_history"] = {
        "players": {str(player["id"]): [] for player in next_state.get("players", [])},
        "last_fingerprint": None,
    }
    return record_player_finance_snapshot(next_state, force=True)


def ensure_player_finance_history(game_state: dict) -> dict:
    next_state = dict(game_state)
    history = dict(next_state.get("player_finance_history") or {})
    player_history = {
        str(player_id): list(entries)
        for player_id, entries in (history.get("players") or {}).items()
    }

    for player in next_state.get("players", []):
        player_history.setdefault(str(player["id"]), [])

    next_state["player_finance_history"] = {
        "players": player_history,
        "last_fingerprint": history.get("last_fingerprint"),
    }
    return next_state


def _build_finance_fingerprint(game_state: dict) -> str:
    treasury = round(float((game_state.get("econ") or {}).get("treasury_balance", 0) or 0), 2)
    players = []
    for player in sorted(game_state.get("players", []), key=lambda entry: entry.get("id", 0)):
        players.append(
            f"{player.get('id')}:{round(float(player.get('balance', 0) or 0), 2)}:{int(bool(player.get('is_bankrupt', False)))}:{round(float(calculate_net_worth(player, game_state) or 0), 2)}"
        )
    return "|".join([
        str(game_state.get("current_round", 0)),
        str(game_state.get("current_turn_index", 0)),
        str(game_state.get("current_player_id")),
        str(game_state.get("awaiting_end_turn_player_id")),
        str(treasury),
        *players,
    ])


def record_player_finance_snapshot(game_state: dict, *, force: bool = False) -> dict:
    next_state = ensure_player_finance_history(game_state)
    history = dict(next_state["player_finance_history"])
    player_history = {
        str(player_id): list(entries)
        for player_id, entries in history.get("players", {}).items()
    }

    fingerprint = _build_finance_fingerprint(next_state)
    if not force and history.get("last_fingerprint") == fingerprint:
        return next_state

    timestamp = datetime.utcnow().isoformat()
    current_round = int(next_state.get("current_round", 0) or 0)
    turn_index = int(next_state.get("current_turn_index", 0) or 0)
    treasury_balance = round(float((next_state.get("econ") or {}).get("treasury_balance", 0) or 0), 2)

    for player in next_state.get("players", []):
        player_key = str(player["id"])
        snapshots = list(player_history.get(player_key, []))
        snapshots.append({
            "timestamp": timestamp,
            "round": current_round,
            "turn_index": turn_index,
            "balance": round(float(player.get("balance", 0) or 0), 2),
            "net_worth": round(float(calculate_net_worth(player, next_state) or 0), 2),
            "treasury_balance": treasury_balance,
        })
        player_history[player_key] = snapshots[-PLAYER_FINANCE_HISTORY_LIMIT:]

    next_state["player_finance_history"] = {
        "players": player_history,
        "last_fingerprint": fingerprint,
    }
    return next_state