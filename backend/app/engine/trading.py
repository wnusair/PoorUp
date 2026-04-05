from __future__ import annotations

from typing import Any

from app import db
from app.engine.analytics import record_lobbying_contribution
from app.engine.debt import credit_player_with_debt_settlement, spend_player_balance
from app.engine.social import property_private_actions_locked
from app.models.policy import (
    Lobbying as LobbyContribution,
    Policy,
    calculate_lobbying_success_chance,
    ensure_match_lobbying_policy,
    get_lobbying_policy_key,
)


def round_money(value: float | int | None) -> float:
    return round(float(value or 0), 2)


def get_player_by_id(game_state: dict, player_id: int) -> dict | None:
    return next(
        (player for player in game_state.get("players", []) if player.get("id") == player_id),
        None,
    )


def normalize_trade_property_ids(raw_ids: Any) -> list[int]:
    normalized = []
    seen = set()
    values = raw_ids if isinstance(raw_ids, list) else []
    for item in values:
        try:
            prop_id = int(item)
        except (TypeError, ValueError):
            continue
        if prop_id <= 0 or prop_id in seen:
            continue
        normalized.append(prop_id)
        seen.add(prop_id)
    return normalized


def normalize_trade_lobby_pledges(match_id: int, raw_pledges: Any) -> tuple[list[dict], str | None]:
    if raw_pledges is None:
        return [], None

    pledge_items = raw_pledges if isinstance(raw_pledges, list) else [raw_pledges]
    grouped_pledges = {}

    for item in pledge_items:
        if not isinstance(item, dict):
            continue

        raw_amount = item.get("amount", item.get("contribution", 0))
        amount = round_money(raw_amount)
        if amount <= 0:
            continue

        policy = None
        policy_id = item.get("policy_id")
        if policy_id is not None:
            try:
                policy = Policy.query.filter_by(id=int(policy_id), match_id=match_id).first()
            except (TypeError, ValueError):
                policy = None

        if policy is None:
            target = str(item.get("target") or "").strip()
            if target:
                policy = ensure_match_lobbying_policy(match_id, target)

        if policy is None:
            return [], "Select a valid lobbying pledge target."

        target_key = get_lobbying_policy_key(target_stat=policy.target_stat)
        if not target_key:
            return [], "Select a valid lobbying pledge target."

        grouped = grouped_pledges.get(policy.id)
        if grouped is None:
            grouped = {
                "policy_id": policy.id,
                "policy_name": policy.policy_name,
                "target": target_key,
                "target_stat": policy.target_stat,
                "amount": 0.0,
            }
            grouped_pledges[policy.id] = grouped
        grouped["amount"] = round_money(grouped["amount"] + amount)

    return list(grouped_pledges.values()), None


def normalize_stored_lobby_pledges(raw_pledges: Any) -> list[dict]:
    normalized = []
    values = raw_pledges if isinstance(raw_pledges, list) else []
    for item in values:
        if not isinstance(item, dict):
            continue
        amount = round_money(item.get("amount", item.get("contribution", 0)))
        if amount <= 0:
            continue
        normalized.append({
            "policy_id": item.get("policy_id"),
            "policy_name": item.get("policy_name"),
            "target": item.get("target"),
            "target_stat": item.get("target_stat"),
            "amount": amount,
        })
    return normalized


def normalize_trade_request_payload(match_id: int, data: dict | None) -> tuple[dict | None, str | None]:
    data = data or {}

    try:
        receiver_id = int(data.get("receiver_id", 0))
    except (TypeError, ValueError):
        receiver_id = 0

    offered_lobby_pledges, error = normalize_trade_lobby_pledges(
        match_id,
        data.get("offered_lobby_pledges", data.get("offer_lobby_pledges")),
    )
    if error:
        return None, error

    requested_lobby_pledges, error = normalize_trade_lobby_pledges(
        match_id,
        data.get("requested_lobby_pledges", data.get("request_lobby_pledges")),
    )
    if error:
        return None, error

    return {
        "receiver_id": receiver_id,
        "offered_money": round_money(data.get("offered_money", data.get("offer_money", 0))),
        "requested_money": round_money(data.get("requested_money", data.get("request_money", 0))),
        "offered_props": normalize_trade_property_ids(data.get("offered_props", data.get("offer_properties", []))),
        "requested_props": normalize_trade_property_ids(data.get("requested_props", data.get("request_properties", []))),
        "offered_lobby_pledges": offered_lobby_pledges,
        "requested_lobby_pledges": requested_lobby_pledges,
    }, None


def sum_lobby_pledges(pledges: list[dict] | None) -> float:
    return round_money(sum((item.get("amount", 0) for item in (pledges or [])), 0))


def validate_trade_proposal(game_state: dict, initiator_id: int, payload: dict) -> str | None:
    receiver_id = int(payload.get("receiver_id", 0) or 0)
    if receiver_id <= 0:
        return "receiver_id required."
    if receiver_id == initiator_id:
        return "Choose another player for this trade."

    initiator = get_player_by_id(game_state, initiator_id)
    receiver = get_player_by_id(game_state, receiver_id)
    if initiator is None:
        return "Player state not found."
    if receiver is None or receiver.get("is_bankrupt", False):
        return "Receiver not found or is bankrupt."

    settings = game_state.get("settings", {})
    econ = game_state.get("econ", {})
    has_lobby_pledges = bool(payload.get("offered_lobby_pledges") or payload.get("requested_lobby_pledges"))
    if has_lobby_pledges and (
        not settings.get("lobbying_enabled", True)
        or econ.get("gov_type") == "minarchism"
    ):
        return "Lobbying pledges are unavailable in the current government."

    offered_commitment = round_money(payload.get("offered_money", 0) + sum_lobby_pledges(payload.get("offered_lobby_pledges")))
    requested_commitment = round_money(payload.get("requested_money", 0) + sum_lobby_pledges(payload.get("requested_lobby_pledges")))

    if offered_commitment > max(0.0, round_money(initiator.get("balance", 0))):
        return "Your offered cash and lobbying pledges exceed your balance."
    if requested_commitment > max(0.0, round_money(receiver.get("balance", 0))):
        return "The requested player cannot currently cover the requested cash and lobbying pledges."

    properties_by_id = {
        int(prop.get("id")): prop
        for prop in game_state.get("properties", [])
        if prop.get("id") is not None
    }

    for prop_id in payload.get("offered_props", []):
        prop = properties_by_id.get(int(prop_id))
        if not prop or prop.get("owner_id") != initiator_id:
            return f"You do not own property {prop_id}."
        if property_private_actions_locked(game_state, int(prop_id)):
            return f"{prop.get('name', 'That property')} is unionized and cannot be traded."
        if int(prop.get("dev_level", 0) or 0) > 0:
            return f"Remove all developments from {prop.get('name', 'that property')} before trading."

    for prop_id in payload.get("requested_props", []):
        prop = properties_by_id.get(int(prop_id))
        if not prop or prop.get("owner_id") != receiver_id:
            return f"Receiver does not own property {prop_id}."
        if property_private_actions_locked(game_state, int(prop_id)):
            return f"{prop.get('name', 'That property')} is unionized and cannot be traded."
        if int(prop.get("dev_level", 0) or 0) > 0:
            return f"Receiver must remove developments from {prop.get('name', 'that property')} first."

    return None


def _apply_lobby_pledges(game_state: dict, payer_id: int, pledges: list[dict], match_id: int) -> tuple[dict, list[dict]]:
    normalized_pledges = normalize_stored_lobby_pledges(pledges)
    if not normalized_pledges:
        return game_state, []

    total_amount = sum_lobby_pledges(normalized_pledges)
    next_state, _ = spend_player_balance(game_state, payer_id, total_amount)
    payer = get_player_by_id(next_state, payer_id)
    pledge_results = []

    policy_records = []
    for pledge in normalized_pledges:
        policy = None
        if pledge.get("policy_id") is not None:
            try:
                policy = Policy.query.filter_by(id=int(pledge["policy_id"]), match_id=match_id).first()
            except (TypeError, ValueError):
                policy = None
        if policy is None and pledge.get("target"):
            policy = ensure_match_lobbying_policy(match_id, pledge["target"])
        if policy is None:
            continue

        entry = LobbyContribution.query.filter_by(
            match_id=match_id,
            policy_id=policy.id,
            player_id=payer_id,
        ).first()
        if entry is None:
            db.session.add(
                LobbyContribution(
                    match_id=match_id,
                    policy_id=policy.id,
                    player_id=payer_id,
                    contribution=pledge["amount"],
                )
            )
        else:
            entry.contribution = round_money(entry.contribution or 0) + pledge["amount"]

        policy_records.append((policy, pledge["amount"]))

    db.session.flush()

    for policy, amount in policy_records:
        policy_entries = LobbyContribution.query.filter_by(match_id=match_id, policy_id=policy.id).all()
        next_state = record_lobbying_contribution(next_state, payer or {}, policy, amount, policy_entries)
        target_key = get_lobbying_policy_key(target_stat=policy.target_stat)
        policy_pool = ((next_state.get("lobbying_stats") or {}).get("policy_pools") or {}).get(target_key, {})
        pledge_results.append({
            "policy": policy.to_dict(),
            "amount": amount,
            "policy_pool_total": round_money(policy_pool.get("pool_total", 0)),
            "estimated_success_chance": round_money(policy_pool.get("estimated_success_chance", 0)),
        })

    return next_state, pledge_results


def apply_trade_acceptance(game_state: dict, trade, match_id: int) -> tuple[dict, dict | None, str | None]:
    next_state = dict(game_state)
    initiator = get_player_by_id(next_state, trade.initiator_id)
    receiver = get_player_by_id(next_state, trade.receiver_id)
    if initiator is None or receiver is None:
        return next_state, None, "Trade participants are no longer available."

    offered_money = round_money(getattr(trade, "offered_money", 0))
    requested_money = round_money(getattr(trade, "requested_money", 0))
    offered_lobby_pledges = normalize_stored_lobby_pledges(getattr(trade, "offered_lobby_pledges", []) or [])
    requested_lobby_pledges = normalize_stored_lobby_pledges(getattr(trade, "requested_lobby_pledges", []) or [])

    settings = next_state.get("settings", {})
    econ = next_state.get("econ", {})
    has_lobby_pledges = bool(offered_lobby_pledges or requested_lobby_pledges)
    if has_lobby_pledges and (
        not settings.get("lobbying_enabled", True)
        or econ.get("gov_type") == "minarchism"
    ):
        return next_state, None, "This trade includes lobbying pledges, but lobbying is currently unavailable."

    initiator_available_cash = max(0.0, round_money(initiator.get("balance", 0)))
    receiver_available_cash = max(0.0, round_money(receiver.get("balance", 0)))
    if offered_money > initiator_available_cash:
        return next_state, None, "The proposer no longer has enough cash for this trade."
    if requested_money > receiver_available_cash:
        return next_state, None, "The receiving player no longer has enough cash for this trade."

    initiator_post_cash = round_money(initiator_available_cash - offered_money + requested_money)
    receiver_post_cash = round_money(receiver_available_cash + offered_money - requested_money)
    if sum_lobby_pledges(offered_lobby_pledges) > max(0.0, initiator_post_cash):
        return next_state, None, "The proposer can no longer fund the promised lobbying pledges."
    if sum_lobby_pledges(requested_lobby_pledges) > max(0.0, receiver_post_cash):
        return next_state, None, "The receiving player can no longer fund the requested lobbying pledges."

    for prop_id in (getattr(trade, "offered_props", []) or []):
        if property_private_actions_locked(next_state, int(prop_id)):
            return next_state, None, "A unionized property can no longer be traded."
    for prop_id in (getattr(trade, "requested_props", []) or []):
        if property_private_actions_locked(next_state, int(prop_id)):
            return next_state, None, "A unionized property can no longer be traded."

    if offered_money > 0:
        next_state, _ = spend_player_balance(next_state, trade.initiator_id, offered_money)
        next_state, _ = credit_player_with_debt_settlement(next_state, trade.receiver_id, offered_money)

    if requested_money > 0:
        next_state, _ = spend_player_balance(next_state, trade.receiver_id, requested_money)
        next_state, _ = credit_player_with_debt_settlement(next_state, trade.initiator_id, requested_money)

    updated_props = []
    for prop in next_state.get("properties", []):
        next_prop = dict(prop)
        if next_prop.get("id") in (getattr(trade, "offered_props", []) or []):
            next_prop["owner_id"] = trade.receiver_id
        elif next_prop.get("id") in (getattr(trade, "requested_props", []) or []):
            next_prop["owner_id"] = trade.initiator_id
        updated_props.append(next_prop)
    next_state = {**next_state, "properties": updated_props}

    next_state, initiator_pledge_results = _apply_lobby_pledges(
        next_state,
        trade.initiator_id,
        offered_lobby_pledges,
        match_id,
    )
    next_state, receiver_pledge_results = _apply_lobby_pledges(
        next_state,
        trade.receiver_id,
        requested_lobby_pledges,
        match_id,
    )

    return next_state, {
        "initiator": initiator_pledge_results,
        "receiver": receiver_pledge_results,
    }, None