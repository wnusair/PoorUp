from datetime import datetime


TAX_CATEGORIES = (
    "income_tax",
    "property_tax",
    "turn_tax",
    "luxury_tax",
    "super_tax",
)

WELFARE_MAX_RATE = 100.0
WELFARE_TARGET_BUFFER = 200.0
WELFARE_FALLBACK_BALANCE_CAP = 200.0
BUDGET_HISTORY_LIMIT = 40


def _empty_player_tax_totals() -> dict:
    return {
        "income_tax": 0.0,
        "property_tax": 0.0,
        "turn_tax": 0.0,
        "luxury_tax": 0.0,
        "super_tax": 0.0,
        "total_tax_paid": 0.0,
        "welfare_contributed": 0.0,
        "welfare_received": 0.0,
    }


def _empty_tax_totals() -> dict:
    return {
        "income_tax": 0.0,
        "property_tax": 0.0,
        "turn_tax": 0.0,
        "luxury_tax": 0.0,
        "super_tax": 0.0,
        "total_tax_paid": 0.0,
        "welfare_paid": 0.0,
    }


def _build_budget_history_entry(
    *,
    round_number: int,
    treasury_balance: float,
    free_parking_claim: float,
    tax_total_to_date: float,
    welfare_total_to_date: float,
    tax_collected: float,
    welfare_spend: float,
    timestamp: str | None = None,
) -> dict:
    return {
        "timestamp": timestamp or datetime.utcnow().isoformat(),
        "round": int(round_number or 0),
        "treasury_balance": round(float(treasury_balance or 0), 2),
        "free_parking_claim": round(float(free_parking_claim or 0), 2),
        "tax_collected": round(float(tax_collected or 0), 2),
        "welfare_spend": round(float(welfare_spend or 0), 2),
        "tax_total_to_date": round(float(tax_total_to_date or 0), 2),
        "welfare_total_to_date": round(float(welfare_total_to_date or 0), 2),
    }


def _initialize_budget_history(
    *,
    current_round: int = 1,
    treasury_balance: float = 0.0,
    free_parking_claim: float = 0.0,
) -> list[dict]:
    return [
        _build_budget_history_entry(
            round_number=int(current_round or 1),
            treasury_balance=treasury_balance,
            free_parking_claim=free_parking_claim,
            tax_total_to_date=0.0,
            welfare_total_to_date=0.0,
            tax_collected=0.0,
            welfare_spend=0.0,
        )
    ]


def get_welfare_balance_cap(settings: dict | None) -> float:
    raw_value = (settings or {}).get("welfare_balance_cap", 0)
    try:
        balance_cap = float(raw_value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, balance_cap)


def get_welfare_eligible_players(players: list[dict], settings: dict | None) -> list[dict]:
    balance_cap = get_welfare_balance_cap(settings)
    eligible_players = []
    for player in players:
        if player.get("is_bankrupt", False):
            continue
        if balance_cap > 0 and float(player.get("balance", 0)) > balance_cap:
            continue
        eligible_players.append(player)
    return eligible_players


def get_welfare_target_balance(settings: dict | None) -> float:
    settings = settings or {}
    balance_cap = get_welfare_balance_cap(settings)
    try:
        go_salary = float(settings.get("go_salary", WELFARE_FALLBACK_BALANCE_CAP))
    except (TypeError, ValueError):
        go_salary = WELFARE_FALLBACK_BALANCE_CAP

    effective_cap = balance_cap if balance_cap > 0 else max(WELFARE_FALLBACK_BALANCE_CAP, go_salary)
    return round(effective_cap + WELFARE_TARGET_BUFFER, 2)


def calculate_welfare_payment(player_balance: float, welfare_rate: float, target_balance: float) -> float:
    welfare_rate = max(0.0, min(WELFARE_MAX_RATE, float(welfare_rate or 0)))
    shortfall = max(0.0, float(target_balance or 0) - float(player_balance or 0))
    if shortfall <= 0 or welfare_rate <= 0:
        return 0.0
    return round(min(shortfall, shortfall * (welfare_rate / 100.0)), 2)


def build_welfare_distribution(players: list[dict], econ: dict, settings: dict | None) -> dict:
    settings = settings or {}
    gov_type = econ.get("gov_type", settings.get("government_type", "liberal_democracy"))
    welfare_system_enabled = bool(settings.get("welfare_system_enabled", True))
    balance_cap = get_welfare_balance_cap(settings)
    target_balance = get_welfare_target_balance(settings)
    welfare_rate = round(max(0.0, min(WELFARE_MAX_RATE, float(econ.get("welfare_payout", 0) or 0))), 2)

    distribution = {
        "government_type": gov_type,
        "welfare_system_enabled": welfare_system_enabled,
        "welfare_balance_cap": balance_cap,
        "target_buffer": WELFARE_TARGET_BUFFER,
        "target_balance": target_balance,
        "configured_rate": welfare_rate,
        "configured_per_player": welfare_rate,
        "per_player_amount": 0.0,
        "average_player_amount": 0.0,
        "player_amounts": {},
        "funding_allocations": {},
        "funding_basis": "tax_paid_share",
        "considered_player_ids": [],
        "eligible_player_ids": [],
        "eligible_count": 0,
        "total_cost": 0.0,
        "treasury_before": round(float(econ.get("treasury_balance", 0) or 0), 2),
        "treasury_after": round(float(econ.get("treasury_balance", 0) or 0), 2),
        "successful": False,
        "reason": "",
    }

    if not welfare_system_enabled:
        distribution["reason"] = "Welfare is disabled in lobby settings."
        return distribution

    if gov_type == "minarchism":
        distribution["reason"] = "Minarchism does not provide welfare."
        return distribution

    if welfare_rate <= 0:
        distribution["reason"] = "Current welfare rate is 0%."
        return distribution

    considered_players = get_welfare_eligible_players(players, settings)
    distribution["considered_player_ids"] = [player["id"] for player in considered_players]

    if not considered_players:
        distribution["reason"] = "No players currently qualify for welfare."
        return distribution

    player_amounts = {}
    eligible_player_ids = []
    for player in considered_players:
        amount = calculate_welfare_payment(
            float(player.get("balance", 0) or 0),
            welfare_rate,
            target_balance,
        )
        if amount <= 0:
            continue
        player_amounts[str(player["id"])] = amount
        eligible_player_ids.append(player["id"])

    distribution["player_amounts"] = player_amounts
    distribution["eligible_player_ids"] = eligible_player_ids
    distribution["eligible_count"] = len(eligible_player_ids)

    if not eligible_player_ids:
        distribution["reason"] = "Eligible players are already at or above the welfare target."
        return distribution

    total_cost = round(sum(player_amounts.values()), 2)
    distribution["total_cost"] = total_cost

    treasury_before = distribution["treasury_before"]
    if treasury_before < total_cost:
        distribution["reason"] = "Treasury cannot cover the next welfare payment."
        return distribution

    average_amount = round(total_cost / len(eligible_player_ids), 2)
    distribution["per_player_amount"] = average_amount
    distribution["average_player_amount"] = average_amount
    distribution["treasury_after"] = round(treasury_before - total_cost, 2)
    distribution["successful"] = True
    distribution["reason"] = ""
    return distribution


def initialize_tax_stats(
    players: list[dict],
    *,
    current_round: int = 1,
    treasury_balance: float = 0.0,
    free_parking_claim: float = 0.0,
) -> dict:
    return {
        "player_totals": {
            str(player["id"]): {
                "player_id": player["id"],
                "username": player.get("username", "Player"),
                **_empty_player_tax_totals(),
            }
            for player in players
        },
        "totals": _empty_tax_totals(),
        "last_welfare_distribution": {
            "timestamp": None,
            "successful": False,
            "configured_rate": 0.0,
            "per_player_amount": 0.0,
            "average_player_amount": 0.0,
            "configured_per_player": 0.0,
            "player_amounts": {},
            "funding_allocations": {},
            "funding_basis": "tax_paid_share",
            "eligible_player_ids": [],
            "considered_player_ids": [],
            "eligible_count": 0,
            "total_cost": 0.0,
            "treasury_before": 0.0,
            "treasury_after": 0.0,
            "welfare_balance_cap": 0.0,
            "target_balance": 0.0,
            "target_buffer": WELFARE_TARGET_BUFFER,
            "reason": "No welfare round has been resolved yet.",
        },
        "budget_history": _initialize_budget_history(
            current_round=current_round,
            treasury_balance=treasury_balance,
            free_parking_claim=free_parking_claim,
        ),
    }


def ensure_tax_stats(game_state: dict) -> dict:
    game_state = dict(game_state)
    stats = game_state.get("tax_stats")
    if not isinstance(stats, dict):
        game_state["tax_stats"] = initialize_tax_stats(
            game_state.get("players", []),
            current_round=int(game_state.get("current_round", 1) or 1),
            treasury_balance=float((game_state.get("econ") or {}).get("treasury_balance", 0) or 0),
            free_parking_claim=float(game_state.get("free_parking_pot", 0) or 0),
        )
        return game_state

    player_totals = {
        str(player_id): dict(values)
        for player_id, values in (stats.get("player_totals") or {}).items()
    }
    for player in game_state.get("players", []):
        player_key = str(player["id"])
        entry = dict(player_totals.get(player_key, {}))
        defaults = _empty_player_tax_totals()
        for key, value in defaults.items():
            entry[key] = round(float(entry.get(key, value) or 0), 2)
        entry["player_id"] = player["id"]
        entry["username"] = player.get("username", entry.get("username", "Player"))
        player_totals[player_key] = entry

    totals = dict(_empty_tax_totals())
    for key, default_value in totals.items():
        totals[key] = round(float((stats.get("totals") or {}).get(key, default_value) or 0), 2)

    last_welfare_distribution = dict((stats.get("last_welfare_distribution") or {}))
    last_welfare_distribution.setdefault("timestamp", None)
    last_welfare_distribution.setdefault("successful", False)
    last_welfare_distribution.setdefault("configured_rate", 0.0)
    last_welfare_distribution.setdefault("per_player_amount", 0.0)
    last_welfare_distribution.setdefault("average_player_amount", 0.0)
    last_welfare_distribution.setdefault("configured_per_player", 0.0)
    last_welfare_distribution.setdefault("player_amounts", {})
    last_welfare_distribution.setdefault("funding_allocations", {})
    last_welfare_distribution.setdefault("funding_basis", "tax_paid_share")
    last_welfare_distribution.setdefault("eligible_player_ids", [])
    last_welfare_distribution.setdefault("considered_player_ids", [])
    last_welfare_distribution.setdefault("eligible_count", 0)
    last_welfare_distribution.setdefault("total_cost", 0.0)
    last_welfare_distribution.setdefault("treasury_before", 0.0)
    last_welfare_distribution.setdefault("treasury_after", 0.0)
    last_welfare_distribution.setdefault("welfare_balance_cap", 0.0)
    last_welfare_distribution.setdefault("target_balance", 0.0)
    last_welfare_distribution.setdefault("target_buffer", WELFARE_TARGET_BUFFER)
    last_welfare_distribution.setdefault("reason", "No welfare round has been resolved yet.")

    raw_budget_history = list(stats.get("budget_history") or [])
    budget_history = []
    for entry in raw_budget_history[-BUDGET_HISTORY_LIMIT:]:
        if not isinstance(entry, dict):
            continue
        budget_history.append(
            _build_budget_history_entry(
                round_number=int(entry.get("round", 0) or 0),
                treasury_balance=entry.get("treasury_balance", 0),
                free_parking_claim=entry.get("free_parking_claim", entry.get("free_parking_pot", 0)),
                tax_total_to_date=entry.get("tax_total_to_date", entry.get("total_tax_paid", 0)),
                welfare_total_to_date=entry.get("welfare_total_to_date", entry.get("welfare_paid_total", 0)),
                tax_collected=entry.get("tax_collected", 0),
                welfare_spend=entry.get("welfare_spend", entry.get("welfare_paid_round", 0)),
                timestamp=entry.get("timestamp"),
            )
        )

    if not budget_history:
        budget_history = _initialize_budget_history(
            current_round=int(game_state.get("current_round", 1) or 1),
            treasury_balance=float((game_state.get("econ") or {}).get("treasury_balance", 0) or 0),
            free_parking_claim=float(game_state.get("free_parking_pot", 0) or 0),
        )

    game_state["tax_stats"] = {
        "player_totals": player_totals,
        "totals": totals,
        "last_welfare_distribution": last_welfare_distribution,
        "budget_history": budget_history[-BUDGET_HISTORY_LIMIT:],
    }
    return game_state


def record_tax_payment(game_state: dict, player_id: int, category: str, amount: float) -> dict:
    if category not in TAX_CATEGORIES:
        return game_state

    amount = round(float(amount or 0), 2)
    if amount <= 0:
        return game_state

    game_state = ensure_tax_stats(game_state)
    stats = dict(game_state["tax_stats"])
    player_totals = {key: dict(value) for key, value in stats["player_totals"].items()}
    totals = dict(stats["totals"])

    player_key = str(player_id)
    player_entry = dict(player_totals.get(player_key, {}))
    if not player_entry:
        defaults = _empty_player_tax_totals()
        player_entry = {
            "player_id": player_id,
            "username": next(
                (player.get("username", "Player") for player in game_state.get("players", []) if player["id"] == player_id),
                "Player",
            ),
            **defaults,
        }

    player_entry[category] = round(float(player_entry.get(category, 0)) + amount, 2)
    player_entry["total_tax_paid"] = round(float(player_entry.get("total_tax_paid", 0)) + amount, 2)
    player_totals[player_key] = player_entry

    totals[category] = round(float(totals.get(category, 0)) + amount, 2)
    totals["total_tax_paid"] = round(float(totals.get("total_tax_paid", 0)) + amount, 2)

    game_state["tax_stats"] = {
        **stats,
        "player_totals": player_totals,
        "totals": totals,
    }
    return game_state


def _round_distribution(shares: dict[str, float], total_amount: float) -> dict[str, float]:
    if not shares:
        return {}

    rounded = {}
    running_total = 0.0
    ordered_keys = list(shares.keys())
    for key in ordered_keys[:-1]:
        amount = round(float(shares.get(key, 0) or 0), 2)
        rounded[key] = amount
        running_total += amount

    final_key = ordered_keys[-1]
    rounded[final_key] = round(float(total_amount or 0) - running_total, 2)
    return rounded


def build_welfare_funding_allocations(game_state: dict, total_cost: float) -> tuple[dict[str, float], str]:
    total_cost = round(float(total_cost or 0), 2)
    if total_cost <= 0:
        return {}, "tax_paid_share"

    active_players = [
        player for player in game_state.get("players", [])
        if not player.get("is_bankrupt", False)
    ]
    if not active_players:
        return {}, "tax_paid_share"

    player_totals = (game_state.get("tax_stats") or {}).get("player_totals") or {}
    tax_weights = {}
    for player in active_players:
        player_key = str(player["id"])
        total_tax_paid = round(float((player_totals.get(player_key) or {}).get("total_tax_paid", 0) or 0), 2)
        if total_tax_paid > 0:
            tax_weights[player_key] = total_tax_paid

    if tax_weights:
        total_weight = sum(tax_weights.values())
        raw_allocations = {
            player_key: total_cost * (weight / total_weight)
            for player_key, weight in tax_weights.items()
        }
        return _round_distribution(raw_allocations, total_cost), "tax_paid_share"

    even_share = total_cost / len(active_players)
    raw_allocations = {
        str(player["id"]): even_share
        for player in active_players
    }
    return _round_distribution(raw_allocations, total_cost), "equal_split"


def record_welfare_distribution(game_state: dict, distribution: dict) -> dict:
    game_state = ensure_tax_stats(game_state)
    stats = dict(game_state["tax_stats"])
    player_totals = {key: dict(value) for key, value in stats["player_totals"].items()}
    totals = dict(stats["totals"])

    normalized_player_amounts = {
        str(player_id): round(float(amount or 0), 2)
        for player_id, amount in (distribution.get("player_amounts") or {}).items()
        if round(float(amount or 0), 2) > 0
    }

    normalized_distribution = {
        "timestamp": datetime.utcnow().isoformat(),
        "successful": bool(distribution.get("successful", False)),
        "configured_rate": round(float(distribution.get("configured_rate", distribution.get("configured_per_player", 0)) or 0), 2),
        "per_player_amount": round(float(distribution.get("per_player_amount", 0) or 0), 2),
        "average_player_amount": round(float(distribution.get("average_player_amount", distribution.get("per_player_amount", 0)) or 0), 2),
        "configured_per_player": round(float(distribution.get("configured_per_player", 0) or 0), 2),
        "player_amounts": normalized_player_amounts,
        "funding_allocations": {},
        "funding_basis": distribution.get("funding_basis", "tax_paid_share"),
        "eligible_player_ids": list(distribution.get("eligible_player_ids", [])),
        "considered_player_ids": list(distribution.get("considered_player_ids", [])),
        "eligible_count": int(distribution.get("eligible_count", 0) or 0),
        "total_cost": round(float(distribution.get("total_cost", 0) or 0), 2),
        "treasury_before": round(float(distribution.get("treasury_before", 0) or 0), 2),
        "treasury_after": round(float(distribution.get("treasury_after", 0) or 0), 2),
        "welfare_balance_cap": round(float(distribution.get("welfare_balance_cap", 0) or 0), 2),
        "target_balance": round(float(distribution.get("target_balance", 0) or 0), 2),
        "target_buffer": round(float(distribution.get("target_buffer", WELFARE_TARGET_BUFFER) or 0), 2),
        "reason": distribution.get("reason", ""),
    }

    if normalized_distribution["successful"] and normalized_distribution["total_cost"] > 0:
        funding_allocations, funding_basis = build_welfare_funding_allocations(
            game_state,
            normalized_distribution["total_cost"],
        )
        normalized_distribution["funding_allocations"] = funding_allocations
        normalized_distribution["funding_basis"] = funding_basis

        for player_key, welfare_amount in normalized_distribution["player_amounts"].items():
            player_entry = dict(player_totals.get(player_key, {}))
            if not player_entry:
                defaults = _empty_player_tax_totals()
                player_entry = {
                    "player_id": int(player_key),
                    "username": next(
                        (player.get("username", "Player") for player in game_state.get("players", []) if player["id"] == int(player_key)),
                        "Player",
                    ),
                    **defaults,
                }
            player_entry["welfare_received"] = round(float(player_entry.get("welfare_received", 0)) + welfare_amount, 2)
            player_totals[player_key] = player_entry

        for player_key, contribution_amount in funding_allocations.items():
            player_entry = dict(player_totals.get(player_key, {}))
            if not player_entry:
                defaults = _empty_player_tax_totals()
                player_entry = {
                    "player_id": int(player_key),
                    "username": next(
                        (player.get("username", "Player") for player in game_state.get("players", []) if player["id"] == int(player_key)),
                        "Player",
                    ),
                    **defaults,
                }
            player_entry["welfare_contributed"] = round(float(player_entry.get("welfare_contributed", 0)) + contribution_amount, 2)
            player_totals[player_key] = player_entry
        totals["welfare_paid"] = round(float(totals.get("welfare_paid", 0)) + normalized_distribution["total_cost"], 2)

    game_state["tax_stats"] = {
        **stats,
        "player_totals": player_totals,
        "totals": totals,
        "last_welfare_distribution": normalized_distribution,
    }
    return game_state


def record_budget_history_snapshot(game_state: dict, round_number: int | None = None) -> dict:
    next_state = ensure_tax_stats(game_state)
    stats = dict(next_state["tax_stats"])
    budget_history = list(stats.get("budget_history") or [])
    current_round = int(round_number if round_number is not None else next_state.get("current_round", 1) or 1)

    totals = dict(stats.get("totals") or {})
    current_tax_total = round(float(totals.get("total_tax_paid", 0) or 0), 2)
    current_welfare_total = round(float(totals.get("welfare_paid", 0) or 0), 2)

    previous_entry = budget_history[-1] if budget_history else None
    if previous_entry and int(previous_entry.get("round", 0) or 0) == current_round:
        previous_entry = budget_history[-2] if len(budget_history) > 1 else None
        budget_history = budget_history[:-1]

    previous_tax_total = round(float((previous_entry or {}).get("tax_total_to_date", 0) or 0), 2)
    previous_welfare_total = round(float((previous_entry or {}).get("welfare_total_to_date", 0) or 0), 2)

    budget_history.append(
        _build_budget_history_entry(
            round_number=current_round,
            treasury_balance=float((next_state.get("econ") or {}).get("treasury_balance", 0) or 0),
            free_parking_claim=float(next_state.get("free_parking_pot", 0) or 0),
            tax_total_to_date=current_tax_total,
            welfare_total_to_date=current_welfare_total,
            tax_collected=max(0.0, round(current_tax_total - previous_tax_total, 2)),
            welfare_spend=max(0.0, round(current_welfare_total - previous_welfare_total, 2)),
        )
    )

    next_state["tax_stats"] = {
        **stats,
        "budget_history": budget_history[-BUDGET_HISTORY_LIMIT:],
    }
    return next_state