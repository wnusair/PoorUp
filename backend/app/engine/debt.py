"""Debt-resolution helpers for PoorUp."""

from __future__ import annotations

from datetime import datetime
import uuid


PLOT_POVERTY_DEFAULT_BALANCE_CAP = 150.0
PLOT_POVERTY_DEFAULT_DEV_CAP = 3


def round_money(value: float | int | None) -> float:
    return round(float(value or 0), 2)


def _coerce_plot_state(game_state: dict | None) -> tuple[dict, dict, dict]:
    next_state = dict(game_state or {})
    social = dict(next_state.get("social") or {})
    plot = dict(social.get("plot") or {})
    return next_state, social, plot


def _plot_member_is_active(plot: dict, player_id: int) -> bool:
    member = dict((plot.get("members") or {}).get(str(player_id)) or {})
    return bool(plot.get("exists")) and bool(member) and bool(member.get("active", True))


def _apply_plot_joint_account_diversion(
    game_state: dict,
    player_id: int,
    amount: float,
) -> tuple[dict, float, float]:
    diverted_amount = 0.0
    net_amount = round_money(amount)
    if net_amount <= 0:
        return game_state, diverted_amount, net_amount

    next_state, social, plot = _coerce_plot_state(game_state)
    if not _plot_member_is_active(plot, player_id):
        return next_state, diverted_amount, net_amount

    contribution_rate = round_money(plot.get("joint_account_contribution_rate", 0.4) or 0.4)
    if contribution_rate <= 0:
        return next_state, diverted_amount, net_amount

    diverted_amount = round_money(net_amount * contribution_rate)
    if diverted_amount <= 0:
        return next_state, 0.0, net_amount

    net_amount = round_money(net_amount - diverted_amount)
    plot["joint_account_balance"] = round_money(
        float(plot.get("joint_account_balance", 0) or 0) + diverted_amount
    )

    contribution_totals = {
        str(key): round_money(value)
        for key, value in (plot.get("joint_account_contributions") or {}).items()
    }
    contribution_totals[str(player_id)] = round_money(
        float(contribution_totals.get(str(player_id), 0) or 0) + diverted_amount
    )
    plot["joint_account_contributions"] = contribution_totals

    members = {str(key): dict(value) for key, value in (plot.get("members") or {}).items()}
    member = dict(members.get(str(player_id)) or {})
    member["cash_contributed"] = round_money(
        float(member.get("cash_contributed", 0) or 0) + diverted_amount
    )
    members[str(player_id)] = member
    plot["members"] = members

    social["plot"] = plot
    next_state["social"] = social
    return next_state, diverted_amount, net_amount


def is_plot_poverty_locked(player: dict | None) -> bool:
    return bool((player or {}).get("plot_locked_poverty", False))


def get_plot_poverty_balance_cap(player: dict | None) -> float:
    if not is_plot_poverty_locked(player):
        return 0.0
    cap = round_money((player or {}).get("plot_poverty_balance_cap", PLOT_POVERTY_DEFAULT_BALANCE_CAP))
    return cap if cap > 0 else PLOT_POVERTY_DEFAULT_BALANCE_CAP


def get_plot_development_cap(player: dict | None) -> int | None:
    if not is_plot_poverty_locked(player):
        return None
    return max(0, int((player or {}).get("plot_max_development_level", PLOT_POVERTY_DEFAULT_DEV_CAP) or PLOT_POVERTY_DEFAULT_DEV_CAP))


def _normalize_plot_poverty_player(player: dict) -> dict:
    updated_player = dict(player)
    if not is_plot_poverty_locked(updated_player):
        return updated_player

    updated_player["plot_poverty_balance_cap"] = get_plot_poverty_balance_cap(updated_player)
    updated_player["plot_max_development_level"] = get_plot_development_cap(updated_player)
    savings_balance = round_money(updated_player.get("plot_savings_balance", 0))
    balance = round_money(updated_player.get("balance", 0))
    balance_cap = get_plot_poverty_balance_cap(updated_player)

    if balance > balance_cap:
        savings_balance = round_money(savings_balance + (balance - balance_cap))
        balance = balance_cap

    updated_player["balance"] = balance
    updated_player["plot_savings_balance"] = savings_balance
    return updated_player


def enforce_plot_poverty_constraints(game_state: dict) -> dict:
    next_state = dict(game_state)
    next_state["players"] = [
        _normalize_plot_poverty_player(dict(player))
        for player in game_state.get("players", [])
    ]
    return next_state


def apply_plot_poverty_rescue(game_state: dict, player_id: int) -> tuple[dict, dict | None, dict]:
    next_state = dict(game_state)
    player = get_player_state(next_state, player_id)
    if player is None or not is_plot_poverty_locked(player):
        return next_state, player, {"balance_rescue": 0.0, "debt_rescue": 0.0}

    updated_player = dict(player)
    savings_balance = round_money(updated_player.get("plot_savings_balance", 0))
    balance = round_money(updated_player.get("balance", 0))
    balance_rescue = 0.0
    debt_rescue = 0.0

    if savings_balance > 0 and balance < 0:
        balance_rescue = round_money(min(savings_balance, abs(balance)))
        savings_balance = round_money(savings_balance - balance_rescue)
        balance = round_money(balance + balance_rescue)

    updated_player["balance"] = balance
    updated_player["plot_savings_balance"] = savings_balance
    next_state = _replace_player(next_state, updated_player)

    total_pending_debt = get_total_pending_player_debt(next_state, player_id)
    if savings_balance > 0 and total_pending_debt > 0:
        debt_rescue = round_money(min(savings_balance, total_pending_debt))
        if debt_rescue > 0:
            next_state, settlement = settle_player_debts(next_state, player_id, debt_rescue)
            debt_rescue = round_money(settlement.get("settled_amount", 0))
            updated_player = get_player_state(next_state, player_id) or updated_player
            updated_player = dict(updated_player)
            updated_player["plot_savings_balance"] = round_money(max(0.0, savings_balance - debt_rescue))
            next_state = _replace_player(next_state, updated_player)

    updated_player = get_player_state(next_state, player_id)
    return next_state, updated_player, {
        "balance_rescue": balance_rescue,
        "debt_rescue": debt_rescue,
    }


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
    updated_player = _normalize_plot_poverty_player(updated_player)
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

    game_state, _, net_amount = _apply_plot_joint_account_diversion(game_state, player_id, amount)
    if net_amount <= 0:
        return game_state, get_player_state(game_state, player_id)

    player = get_player_state(game_state, player_id)
    if player is None:
        return game_state, None

    current_balance = round_money(player.get("balance", 0))
    return set_player_balance(game_state, player_id, current_balance + net_amount)


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
