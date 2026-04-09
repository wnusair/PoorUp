"""Debt-resolution helpers for PoorUp."""

from __future__ import annotations

from datetime import datetime
import uuid


def round_money(value: float | int | None) -> float:
    return round(float(value or 0), 2)


def ensure_pending_debts(game_state: dict) -> dict:
    next_state = dict(game_state)
    pending_debts = next_state.get("pending_debts")
    if not isinstance(pending_debts, list):
        next_state["pending_debts"] = []
        return next_state

    normalized_debts = []
    for debt in pending_debts:
        if not isinstance(debt, dict):
            continue
        amount_due = round_money(debt.get("amount_due", 0))
        if amount_due <= 0:
            continue
        entry = dict(debt)
        entry["amount_due"] = amount_due
        entry["original_amount"] = round_money(entry.get("original_amount", amount_due))
        normalized_debts.append(entry)

    next_state["pending_debts"] = normalized_debts
    return next_state


def get_player_state(game_state: dict, player_id: int) -> dict | None:
    return next(
        (player for player in game_state.get("players", []) if player.get("id") == player_id),
        None,
    )


def _replace_player(game_state: dict, updated_player: dict) -> dict:
    next_state = dict(game_state)
    next_state["players"] = [
        updated_player if player.get("id") == updated_player.get("id") else player
        for player in game_state.get("players", [])
    ]
    return next_state


def set_player_balance(game_state: dict, player_id: int, balance: float) -> tuple[dict, dict | None]:
    player = get_player_state(game_state, player_id)
    if player is None:
        return game_state, None

    updated_player = dict(player)
    updated_player["balance"] = round_money(balance)
    return _replace_player(game_state, updated_player), updated_player


def spend_player_balance(game_state: dict, player_id: int, amount: float) -> tuple[dict, dict | None]:
    amount = round_money(amount)
    if amount <= 0:
        return game_state, get_player_state(game_state, player_id)

    player = get_player_state(game_state, player_id)
    if player is None:
        return game_state, None

    current_balance = round_money(player.get("balance", 0))
    return set_player_balance(game_state, player_id, current_balance - amount)


def _credit_player_direct(game_state: dict, player_id: int, amount: float) -> tuple[dict, dict | None]:
    amount = round_money(amount)
    if amount <= 0:
        return game_state, get_player_state(game_state, player_id)

    player = get_player_state(game_state, player_id)
    if player is None:
        return game_state, None

    current_balance = round_money(player.get("balance", 0))
    return set_player_balance(game_state, player_id, current_balance + amount)


def add_pending_player_debt(
    game_state: dict,
    debtor_id: int,
    creditor_id: int,
    amount_due: float,
    *,
    reason: str,
    property_id: int | None = None,
    property_name: str | None = None,
) -> tuple[dict, dict | None]:
    amount_due = round_money(amount_due)
    if amount_due <= 0:
        return game_state, None

    next_state = ensure_pending_debts(game_state)
    debtor = get_player_state(next_state, debtor_id)
    creditor = get_player_state(next_state, creditor_id)

    debt_entry = {
        "id": uuid.uuid4().hex,
        "debtor_id": debtor_id,
        "debtor_name": debtor.get("username", "Player") if debtor else "Player",
        "creditor_id": creditor_id,
        "creditor_name": creditor.get("username", "Player") if creditor else "Player",
        "reason": reason,
        "property_id": property_id,
        "property_name": property_name,
        "original_amount": amount_due,
        "amount_due": amount_due,
        "created_at": datetime.utcnow().isoformat(),
    }

    pending_debts = list(next_state.get("pending_debts", []))
    pending_debts.append(debt_entry)
    next_state["pending_debts"] = pending_debts
    return next_state, debt_entry


def get_player_pending_debts(game_state: dict, player_id: int) -> list[dict]:
    return [
        dict(debt)
        for debt in ensure_pending_debts(game_state).get("pending_debts", [])
        if debt.get("debtor_id") == player_id and round_money(debt.get("amount_due", 0)) > 0
    ]


def get_total_pending_player_debt(game_state: dict, player_id: int) -> float:
    return round_money(
        sum(debt.get("amount_due", 0) for debt in get_player_pending_debts(game_state, player_id))
    )


def has_pending_player_debt(game_state: dict, player_id: int) -> bool:
    return get_total_pending_player_debt(game_state, player_id) > 0


def charge_player_to_player(
    game_state: dict,
    debtor_id: int,
    creditor_id: int,
    amount: float,
    *,
    reason: str,
    property_id: int | None = None,
    property_name: str | None = None,
) -> tuple[dict, dict]:
    amount = round_money(amount)
    if amount <= 0:
        debtor = get_player_state(game_state, debtor_id)
        creditor = get_player_state(game_state, creditor_id)
        return game_state, {
            "charged_amount": 0.0,
            "paid_now": 0.0,
            "shortfall": 0.0,
            "debtor": debtor,
            "creditor": creditor,
        }

    next_state = ensure_pending_debts(game_state)
    debtor = get_player_state(next_state, debtor_id)
    creditor = get_player_state(next_state, creditor_id)
    if debtor is None or creditor is None:
        return next_state, {
            "charged_amount": 0.0,
            "paid_now": 0.0,
            "shortfall": 0.0,
            "debtor": debtor,
            "creditor": creditor,
        }

    balance_before = round_money(debtor.get("balance", 0))
    paid_now = min(max(balance_before, 0.0), amount)

    next_state, _ = spend_player_balance(next_state, debtor_id, amount)
    next_state, creditor = _credit_player_direct(next_state, creditor_id, paid_now)

    shortfall = round_money(amount - paid_now)
    debt_entry = None
    if shortfall > 0:
        next_state, debt_entry = add_pending_player_debt(
            next_state,
            debtor_id,
            creditor_id,
            shortfall,
            reason=reason,
            property_id=property_id,
            property_name=property_name,
        )

    debtor = get_player_state(next_state, debtor_id)
    creditor = get_player_state(next_state, creditor_id)

    return next_state, {
        "charged_amount": amount,
        "paid_now": paid_now,
        "shortfall": shortfall,
        "debtor": debtor,
        "creditor": creditor,
        "debt_entry": debt_entry,
    }


def settle_player_debts(game_state: dict, debtor_id: int, amount_available: float) -> tuple[dict, dict]:
    amount_available = round_money(amount_available)
    next_state = ensure_pending_debts(game_state)
    if amount_available <= 0:
        return next_state, {
            "settled_amount": 0.0,
            "settlements": [],
        }

    remaining_amount = amount_available
    settlements = []
    updated_debts = []

    for debt in next_state.get("pending_debts", []):
        current_debt = dict(debt)
        amount_due = round_money(current_debt.get("amount_due", 0))

        if current_debt.get("debtor_id") != debtor_id or amount_due <= 0 or remaining_amount <= 0:
            if amount_due > 0:
                updated_debts.append(current_debt)
            continue

        payment = min(amount_due, remaining_amount)
        remaining_amount = round_money(remaining_amount - payment)
        amount_due = round_money(amount_due - payment)
        if payment > 0:
            next_state, creditor = _credit_player_direct(next_state, current_debt.get("creditor_id"), payment)
            settlements.append({
                **current_debt,
                "amount_paid": payment,
                "creditor_name": creditor.get("username", current_debt.get("creditor_name", "Player")) if creditor else current_debt.get("creditor_name", "Player"),
            })

        if amount_due > 0:
            current_debt["amount_due"] = amount_due
            updated_debts.append(current_debt)

    next_state["pending_debts"] = updated_debts
    return next_state, {
        "settled_amount": round_money(amount_available - remaining_amount),
        "settlements": settlements,
    }


def credit_player_with_debt_settlement(game_state: dict, player_id: int, amount: float) -> tuple[dict, dict]:
    amount = round_money(amount)
    if amount <= 0:
        player = get_player_state(game_state, player_id)
        return game_state, {
            "credited_amount": 0.0,
            "settled_amount": 0.0,
            "player": player,
            "settlements": [],
        }

    next_state, _ = _credit_player_direct(game_state, player_id, amount)
    next_state, settlement = settle_player_debts(next_state, player_id, amount)
    player = get_player_state(next_state, player_id)
    return next_state, {
        "credited_amount": amount,
        "settled_amount": settlement["settled_amount"],
        "player": player,
        "settlements": settlement["settlements"],
    }


def clear_player_debts(game_state: dict, player_id: int) -> dict:
    next_state = ensure_pending_debts(game_state)
    next_state["pending_debts"] = [
        dict(debt)
        for debt in next_state.get("pending_debts", [])
        if debt.get("debtor_id") != player_id
    ]
    return next_state


def calculate_player_liquidation_value(game_state: dict, player_id: int) -> float:
    liquidation_value = 0.0
    for prop in game_state.get("properties", []):
        if prop.get("owner_id") != player_id:
            continue

        base_price = round_money(prop.get("base_price", 0))
        dev_level = int(prop.get("dev_level", 0) or 0)
        build_cost = round_money(base_price * 0.5)
        liquidation_value += round_money(dev_level * build_cost * 0.5)

        if not prop.get("is_mortgaged", False):
            liquidation_value += round_money(base_price * 0.5)

    return round_money(liquidation_value)