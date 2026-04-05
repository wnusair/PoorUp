from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.exc import OperationalError, ProgrammingError

from app import db
from app.engine.debt import credit_player_with_debt_settlement, round_money, spend_player_balance
from app.engine.economy import calculate_rent_with_dev
from app.models.deal import Deal, DealClause, DealInvestmentTranche

CLAUSE_IMMUNITY = "rent_immunity"
CLAUSE_DISCOUNT = "rent_discount"
CLAUSE_INVESTMENT = "development_investment"

DEAL_STATUS_PROPOSED = "proposed"
DEAL_STATUS_ACCEPTED = "accepted"
DEAL_STATUS_REJECTED = "rejected"
DEAL_STATUS_COUNTERED = "countered"
DEAL_STATUS_CANCELLED = "cancelled"
DEAL_STATUS_EXPIRED = "expired"
DEAL_STATUS_COMPLETED = "completed"

CLAUSE_STATUS_PENDING = "pending"
CLAUSE_STATUS_ACTIVE = "active"
CLAUSE_STATUS_EXPIRED = "expired"
CLAUSE_STATUS_CANCELLED = "cancelled"
CLAUSE_STATUS_COMPLETED = "completed"

DEADLINE_BENEFICIARY_LANDINGS = "beneficiary_landings_on_grantor"
DEADLINE_BENEFICIARY_TURNS = "beneficiary_turns"
DEADLINE_GRANTOR_TURNS = "grantor_turns"
DEADLINE_FULL_ROUNDS = "full_rounds"
DEADLINE_BENEFICIARY_ROTATIONS = "beneficiary_rotations"

SUPPORTED_DEADLINE_METRICS = {
    DEADLINE_BENEFICIARY_LANDINGS,
    DEADLINE_BENEFICIARY_TURNS,
    DEADLINE_GRANTOR_TURNS,
    DEADLINE_FULL_ROUNDS,
    DEADLINE_BENEFICIARY_ROTATIONS,
}

SUPPORTED_CLAUSE_TYPES = {
    CLAUSE_IMMUNITY,
    CLAUSE_DISCOUNT,
    CLAUSE_INVESTMENT,
}


def deals_enabled(settings: dict | None) -> bool:
    settings = settings or {}
    if "deals_enabled" in settings:
        return bool(settings.get("deals_enabled", True))
    return bool(settings.get("teams_enabled", True))


def private_equity_enabled(settings: dict | None) -> bool:
    settings = settings or {}
    return bool(settings.get("private_equity_enabled", True))


def _player_map(game_state: dict) -> dict[int, dict]:
    return {
        int(player.get("id")): player
        for player in (game_state.get("players") or [])
        if player.get("id") is not None
    }


def _property_map(game_state: dict) -> dict[int, dict]:
    return {
        int(prop.get("id")): prop
        for prop in (game_state.get("properties") or [])
        if prop.get("id") is not None
    }


def _safe_all(query):
    try:
        return query.all()
    except (OperationalError, ProgrammingError):
        db.session.rollback()
        return []


def _safe_first(query):
    try:
        return query.first()
    except (OperationalError, ProgrammingError):
        db.session.rollback()
        return None


def _safe_commit() -> bool:
    try:
        db.session.commit()
        return True
    except (OperationalError, ProgrammingError):
        db.session.rollback()
        return False


def _clause_state(clause: DealClause) -> dict:
    return dict(clause.state_json or {})


def _set_clause_state(clause: DealClause, updates: dict) -> None:
    state = _clause_state(clause)
    state.update(updates)
    clause.state_json = state


def _deadline_payload(raw: Any) -> dict | None:
    if not isinstance(raw, dict):
        return None
    metric = str(raw.get("metric") or "").strip()
    try:
        initial = int(raw.get("initial", 0))
    except (TypeError, ValueError):
        initial = 0
    if metric not in SUPPORTED_DEADLINE_METRICS or initial <= 0:
        return None
    return {
        "metric": metric,
        "initial": initial,
    }


def _scope_payload(raw: Any) -> dict:
    if not isinstance(raw, dict):
        return {"mode": "all_grantor_properties"}

    mode = str(raw.get("mode") or "all_grantor_properties").strip()
    if mode == "selected_group_colors":
        group_colors = []
        seen = set()
        for color in raw.get("group_colors") or []:
            normalized = str(color or "").strip()
            if normalized and normalized not in seen:
                group_colors.append(normalized)
                seen.add(normalized)
        if group_colors:
            return {
                "mode": mode,
                "group_colors": group_colors,
            }
    elif mode == "selected_property_ids":
        property_ids = []
        seen = set()
        for value in raw.get("property_ids") or []:
            try:
                property_id = int(value)
            except (TypeError, ValueError):
                continue
            if property_id > 0 and property_id not in seen:
                property_ids.append(property_id)
                seen.add(property_id)
        if property_ids:
            return {
                "mode": mode,
                "property_ids": property_ids,
            }
    return {"mode": "all_grantor_properties"}


def _scope_matches_property(scope: dict | None, prop: dict | None, grantor_id: int) -> bool:
    if not prop or int(prop.get("owner_id") or 0) != int(grantor_id or 0):
        return False

    scope = scope or {}
    mode = scope.get("mode") or "all_grantor_properties"
    if mode == "all_grantor_properties":
        return True
    if mode == "selected_group_colors":
        return prop.get("group_color") in set(scope.get("group_colors") or [])
    if mode == "selected_property_ids":
        return int(prop.get("id") or 0) in {int(value) for value in (scope.get("property_ids") or [])}
    return False


def _deal_timestamp(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _serialize_tranche(tranche: DealInvestmentTranche) -> dict:
    return {
        "id": tranche.id,
        "property_id": tranche.property_id,
        "investor_id": tranche.investor_id,
        "recipient_id": tranche.recipient_id,
        "funded_cost": float(tranche.funded_cost or 0),
        "baseline_dev_level": int(tranche.baseline_dev_level or 0),
        "funded_dev_level": int(tranche.funded_dev_level or 0),
        "baseline_rent": float(tranche.baseline_rent or 0),
        "funded_rent": float(tranche.funded_rent or 0),
        "profit_share_percent": float(tranche.profit_share_percent or 0),
        "max_payout": float(tranche.max_payout or 0),
        "payout_to_date": float(tranche.payout_to_date or 0),
        "active": bool(tranche.active),
        "created_at": _deal_timestamp(tranche.created_at),
    }


def _serialize_clause(clause: DealClause) -> dict:
    state = _clause_state(clause)
    deadline = dict(clause.deadline_json or {})
    config = dict(clause.config_json or {})
    if clause.clause_type == CLAUSE_INVESTMENT:
        config = {
            **config,
            "escrow_remaining": round_money(state.get("escrow_remaining", config.get("escrow_amount", 0))),
            "payout_to_date": round_money(state.get("payout_to_date", 0)),
        }

    return {
        "id": clause.id,
        "type": clause.clause_type,
        "grantor_id": clause.grantor_id,
        "beneficiary_id": clause.beneficiary_id,
        "scope": dict(clause.scope_json or {}),
        "config": config,
        "deadline": {
            "metric": deadline.get("metric"),
            "initial": int(deadline.get("initial", 0) or 0),
            "remaining": int(state.get("remaining", deadline.get("initial", 0)) or 0),
        },
        "status": clause.status,
        "activated_at": _deal_timestamp(clause.activated_at),
        "expired_at": _deal_timestamp(clause.expired_at),
        "tranches": [_serialize_tranche(tranche) for tranche in (clause.investment_tranches or [])],
    }


def serialize_deal(deal: Deal, player_lookup: dict[int, dict] | None = None) -> dict:
    player_lookup = player_lookup or {}
    clauses = [_serialize_clause(clause) for clause in (deal.clauses or [])]
    return {
        "id": deal.id,
        "match_id": deal.match_id,
        "proposer_id": deal.proposer_id,
        "counterparty_id": deal.counterparty_id,
        "proposer_name": (player_lookup.get(deal.proposer_id) or {}).get("username"),
        "counterparty_name": (player_lookup.get(deal.counterparty_id) or {}).get("username"),
        "status": deal.status,
        "title": deal.title,
        "created_at": _deal_timestamp(deal.created_at),
        "responded_at": _deal_timestamp(deal.responded_at),
        "accepted_at": _deal_timestamp(deal.accepted_at),
        "cancelled_at": _deal_timestamp(deal.cancelled_at),
        "last_updated_at": _deal_timestamp(deal.last_updated_at),
        "proposal_version": int(deal.proposal_version or 1),
        "counter_of_deal_id": deal.counter_of_deal_id,
        "clauses": clauses,
    }


def _active_clause_snapshots(deal_snapshots: list[dict]) -> list[dict]:
    snapshots = []
    for deal in deal_snapshots:
        if deal.get("status") != DEAL_STATUS_ACCEPTED:
            continue
        for clause in deal.get("clauses") or []:
            if clause.get("status") != CLAUSE_STATUS_ACTIVE:
                continue
            snapshots.append({**clause, "deal_id": deal.get("id"), "deal_title": deal.get("title")})
    return snapshots


def _player_deal_summary(player_id: int, deal_snapshots: list[dict]) -> dict:
    active_deals = []
    incoming_immunities = []
    discounts_from = []
    investor_in = []
    recipient_in = []
    pending_incoming_count = 0
    pending_outgoing_count = 0

    for deal in deal_snapshots:
        is_involved = player_id in {deal.get("proposer_id"), deal.get("counterparty_id")}
        if not is_involved:
            continue

        if deal.get("status") == DEAL_STATUS_PROPOSED:
            if deal.get("counterparty_id") == player_id:
                pending_incoming_count += 1
            if deal.get("proposer_id") == player_id:
                pending_outgoing_count += 1

        if deal.get("status") != DEAL_STATUS_ACCEPTED:
            continue

        if any(clause.get("status") == CLAUSE_STATUS_ACTIVE for clause in (deal.get("clauses") or [])):
            active_deals.append(deal.get("id"))

        for clause in deal.get("clauses") or []:
            if clause.get("status") != CLAUSE_STATUS_ACTIVE:
                continue
            if clause.get("type") == CLAUSE_IMMUNITY and int(clause.get("beneficiary_id") or 0) == player_id:
                incoming_immunities.append(int(clause.get("grantor_id") or 0))
            elif clause.get("type") == CLAUSE_DISCOUNT and int(clause.get("beneficiary_id") or 0) == player_id:
                discounts_from.append({
                    "player_id": int(clause.get("grantor_id") or 0),
                    "rent_multiplier": float((clause.get("config") or {}).get("rent_multiplier", 1)),
                })
            elif clause.get("type") == CLAUSE_INVESTMENT:
                if int(clause.get("grantor_id") or 0) == player_id:
                    investor_in.append(int(deal.get("id") or 0))
                if int(clause.get("beneficiary_id") or 0) == player_id:
                    recipient_in.append(int(deal.get("id") or 0))

    return {
        "active_deal_count": len({deal_id for deal_id in active_deals if deal_id}),
        "incoming_immunities_from": sorted({player for player in incoming_immunities if player}),
        "discounts_from": discounts_from,
        "investor_in": sorted({deal_id for deal_id in investor_in if deal_id}),
        "recipient_in": sorted({deal_id for deal_id in recipient_in if deal_id}),
        "pending_incoming_count": pending_incoming_count,
        "pending_outgoing_count": pending_outgoing_count,
    }


def _property_deal_annotations(prop: dict, deal_snapshots: list[dict]) -> dict:
    modifiers = []
    investment_options = []
    profit_obligations = []

    for deal in deal_snapshots:
        for clause in deal.get("clauses") or []:
            if clause.get("status") != CLAUSE_STATUS_ACTIVE:
                continue
            if clause.get("type") in {CLAUSE_IMMUNITY, CLAUSE_DISCOUNT} and _scope_matches_property(clause.get("scope"), prop, int(clause.get("grantor_id") or 0)):
                modifiers.append({
                    "deal_id": deal.get("id"),
                    "deal_title": deal.get("title"),
                    "type": clause.get("type"),
                    "grantor_id": clause.get("grantor_id"),
                    "beneficiary_id": clause.get("beneficiary_id"),
                    "deadline": clause.get("deadline"),
                    "rent_multiplier": float((clause.get("config") or {}).get("rent_multiplier", 1)),
                })
            elif clause.get("type") == CLAUSE_INVESTMENT and int(prop.get("owner_id") or 0) == int(clause.get("beneficiary_id") or 0) and _scope_matches_property(clause.get("scope"), {**prop, "owner_id": clause.get("beneficiary_id")}, int(clause.get("beneficiary_id") or 0)):
                if float((clause.get("config") or {}).get("escrow_remaining", 0) or 0) > 0:
                    investment_options.append({
                        "deal_id": deal.get("id"),
                        "clause_id": clause.get("id"),
                        "counterparty_id": clause.get("grantor_id"),
                        "escrow_remaining": float((clause.get("config") or {}).get("escrow_remaining", 0) or 0),
                        "profit_share_percent": float((clause.get("config") or {}).get("profit_share_percent", 0) or 0),
                        "max_payout": float((clause.get("config") or {}).get("max_payout", 0) or 0),
                        "payout_to_date": float((clause.get("config") or {}).get("payout_to_date", 0) or 0),
                        "deadline": clause.get("deadline"),
                    })
                for tranche in clause.get("tranches") or []:
                    if int(tranche.get("property_id") or 0) == int(prop.get("id") or 0) and tranche.get("active"):
                        profit_obligations.append({
                            "deal_id": deal.get("id"),
                            "clause_id": clause.get("id"),
                            "tranche_id": tranche.get("id"),
                            "investor_id": tranche.get("investor_id"),
                            "recipient_id": tranche.get("recipient_id"),
                            "profit_share_percent": float(tranche.get("profit_share_percent", 0) or 0),
                            "payout_to_date": float(tranche.get("payout_to_date", 0) or 0),
                            "max_payout": float(tranche.get("max_payout", 0) or 0),
                            "baseline_rent": float(tranche.get("baseline_rent", 0) or 0),
                        })

    return {
        "deal_modifiers": modifiers,
        "deal_investment_options": investment_options,
        "deal_profit_obligations": profit_obligations,
        "deal_trade_warning": bool(profit_obligations),
    }


def _migrate_legacy_team_deals(match_id: int, game_state: dict) -> None:
    existing = _safe_first(Deal.query.filter_by(match_id=match_id))
    if existing is not None:
        return

    teams: dict[int, list[dict]] = {}
    for player in game_state.get("players") or []:
        team_id = player.get("team_id")
        if team_id:
            teams.setdefault(int(team_id), []).append(player)

    created_any = False
    for members in teams.values():
        if len(members) < 2:
            continue
        member_ids = [int(player.get("id")) for player in members if player.get("id") is not None]
        for proposer_id in member_ids:
            for counterparty_id in member_ids:
                if proposer_id >= counterparty_id:
                    continue
                deal = Deal(
                    match_id=match_id,
                    proposer_id=proposer_id,
                    counterparty_id=counterparty_id,
                    status=DEAL_STATUS_ACCEPTED,
                    title="Legacy team migration",
                    created_at=datetime.utcnow(),
                    responded_at=datetime.utcnow(),
                    accepted_at=datetime.utcnow(),
                    last_updated_at=datetime.utcnow(),
                )
                db.session.add(deal)
                db.session.flush()
                for grantor_id, beneficiary_id in ((proposer_id, counterparty_id), (counterparty_id, proposer_id)):
                    db.session.add(
                        DealClause(
                            deal_id=deal.id,
                            clause_type=CLAUSE_IMMUNITY,
                            grantor_id=grantor_id,
                            beneficiary_id=beneficiary_id,
                            scope_json={"mode": "all_grantor_properties"},
                            config_json={},
                            deadline_json={"metric": DEADLINE_BENEFICIARY_TURNS, "initial": 999},
                            state_json={"remaining": 999},
                            status=CLAUSE_STATUS_ACTIVE,
                            activated_at=datetime.utcnow(),
                        )
                    )
                created_any = True

    if created_any:
        _safe_commit()


def attach_deals_snapshot(game_state: dict, match_id: int | None = None) -> dict:
    match_id = int(match_id or game_state.get("match_id") or 0)
    if match_id <= 0:
        return game_state

    _migrate_legacy_team_deals(match_id, game_state)

    deals = _safe_all(
        Deal.query.filter_by(match_id=match_id)
        .order_by(Deal.last_updated_at.desc(), Deal.id.desc())
    )
    player_lookup = _player_map(game_state)
    deal_snapshots = [serialize_deal(deal, player_lookup) for deal in deals]

    next_state = dict(game_state)
    next_state["deals"] = deal_snapshots

    next_players = []
    for player in game_state.get("players") or []:
        next_player = dict(player)
        next_player["deal_summary"] = _player_deal_summary(int(player.get("id") or 0), deal_snapshots)
        next_players.append(next_player)
    next_state["players"] = next_players

    next_props = []
    for prop in game_state.get("properties") or []:
        next_prop = dict(prop)
        next_prop.update(_property_deal_annotations(next_prop, deal_snapshots))
        next_props.append(next_prop)
    next_state["properties"] = next_props
    return next_state


def list_match_deals(match_id: int, game_state: dict | None = None) -> list[dict]:
    game_state = game_state or {"match_id": match_id, "players": [], "properties": []}
    hydrated = attach_deals_snapshot(game_state, match_id)
    return hydrated.get("deals") or []


def _validate_counterparty(game_state: dict, proposer_id: int, counterparty_id: int) -> str | None:
    if counterparty_id <= 0 or counterparty_id == proposer_id:
        return "Choose another player for this deal."

    players = _player_map(game_state)
    proposer = players.get(proposer_id)
    counterparty = players.get(counterparty_id)
    if proposer is None:
        return "Deal proposer not found."
    if counterparty is None or counterparty.get("is_bankrupt"):
        return "Counterparty not found or bankrupt."
    return None


def _validate_scope_coverage(scope: dict, grantor_id: int, game_state: dict) -> str | None:
    properties = [prop for prop in game_state.get("properties") or [] if int(prop.get("owner_id") or 0) == grantor_id]
    if scope.get("mode") == "selected_group_colors":
        selected = set(scope.get("group_colors") or [])
        if not selected:
            return "Choose at least one property group."
        if not any(prop.get("group_color") in selected for prop in properties):
            return "The chosen grantor does not currently own any properties in the selected groups."
    elif scope.get("mode") == "selected_property_ids":
        selected = {int(value) for value in (scope.get("property_ids") or [])}
        if not selected:
            return "Choose at least one property."
        owned = {int(prop.get("id") or 0) for prop in properties}
        if not selected.issubset(owned):
            return "The chosen grantor must currently own every selected property."
    return None


def _scope_signature(scope: dict) -> tuple:
    mode = scope.get("mode") or "all_grantor_properties"
    if mode == "selected_group_colors":
        return (mode, tuple(sorted(scope.get("group_colors") or [])))
    if mode == "selected_property_ids":
        return (mode, tuple(sorted(int(value) for value in (scope.get("property_ids") or []))))
    return ("all_grantor_properties",)


def _has_overlapping_active_clause(match_id: int, clause_type: str, grantor_id: int, beneficiary_id: int, scope: dict) -> bool:
    clauses = _safe_all(
        DealClause.query.join(Deal, Deal.id == DealClause.deal_id).filter(
            Deal.match_id == match_id,
            Deal.status == DEAL_STATUS_ACCEPTED,
            DealClause.status == CLAUSE_STATUS_ACTIVE,
            DealClause.clause_type == clause_type,
            DealClause.grantor_id == grantor_id,
            DealClause.beneficiary_id == beneficiary_id,
        )
    )
    signature = _scope_signature(scope)
    return any(_scope_signature(dict(clause.scope_json or {})) == signature for clause in clauses)


def normalize_deal_request_payload(match_id: int, proposer_id: int, game_state: dict, data: dict | None) -> tuple[dict | None, str | None]:
    data = data or {}
    try:
        counterparty_id = int(data.get("counterparty_id", 0))
    except (TypeError, ValueError):
        counterparty_id = 0

    error = _validate_counterparty(game_state, proposer_id, counterparty_id)
    if error:
        return None, error

    settings = game_state.get("settings") or {}
    if not deals_enabled(settings):
        return None, "Deals are disabled."

    raw_clauses = data.get("clauses") or []
    if not isinstance(raw_clauses, list) or not raw_clauses:
        return None, "Add at least one clause to the deal."

    normalized_clauses = []
    players = _player_map(game_state)
    proposer = players.get(proposer_id)
    counterparty = players.get(counterparty_id)
    max_discount_percent = float(settings.get("max_rent_discount_percent", 90) or 90) / 100.0
    max_active_deals = int(settings.get("max_active_deals_per_player", 3) or 3)
    active_deals = attach_deals_snapshot(game_state, match_id).get("deals") or []
    proposer_active = sum(
        1
        for deal in active_deals
        if deal.get("status") == DEAL_STATUS_ACCEPTED
        and proposer_id in {deal.get("proposer_id"), deal.get("counterparty_id")}
        and any(clause.get("status") == CLAUSE_STATUS_ACTIVE for clause in (deal.get("clauses") or []))
    )
    counterparty_active = sum(
        1
        for deal in active_deals
        if deal.get("status") == DEAL_STATUS_ACCEPTED
        and counterparty_id in {deal.get("proposer_id"), deal.get("counterparty_id")}
        and any(clause.get("status") == CLAUSE_STATUS_ACTIVE for clause in (deal.get("clauses") or []))
    )
    if proposer_active >= max_active_deals:
        return None, "You already reached the active deal limit."
    if counterparty_active >= max_active_deals:
        return None, "That player already reached the active deal limit."

    for raw_clause in raw_clauses:
        if not isinstance(raw_clause, dict):
            continue
        clause_type = str(raw_clause.get("type") or raw_clause.get("clause_type") or "").strip()
        if clause_type not in SUPPORTED_CLAUSE_TYPES:
            return None, "Choose a valid clause type."

        deadline = _deadline_payload(raw_clause.get("deadline"))
        if deadline is None:
            return None, "Choose a valid deadline metric and amount."

        scope = _scope_payload(raw_clause.get("scope"))
        config = dict(raw_clause.get("config") or {})

        if clause_type in {CLAUSE_IMMUNITY, CLAUSE_DISCOUNT}:
            try:
                grantor_id = int(raw_clause.get("grantor_id", proposer_id))
                beneficiary_id = int(raw_clause.get("beneficiary_id", counterparty_id))
            except (TypeError, ValueError):
                return None, "Choose valid players for every clause."

            if {grantor_id, beneficiary_id} != {proposer_id, counterparty_id}:
                return None, "Deal clauses may only involve the proposer and counterparty."

            scope_error = _validate_scope_coverage(scope, grantor_id, game_state)
            if scope_error:
                return None, scope_error

            if clause_type == CLAUSE_DISCOUNT:
                multiplier = round(float(config.get("rent_multiplier", 0) or 0), 2)
                if multiplier < 0.10 or multiplier > max_discount_percent:
                    return None, f"Rent discounts must stay between 10% and {int(max_discount_percent * 100)}%."
                config = {"rent_multiplier": multiplier}
            else:
                config = {}

            if _has_overlapping_active_clause(match_id, clause_type, grantor_id, beneficiary_id, scope):
                return None, "An overlapping active deal clause already exists for that player pair and scope."

        else:
            if not private_equity_enabled(settings):
                return None, "Private equity deals are disabled."

            try:
                investor_id = int(raw_clause.get("investor_id", proposer_id))
                recipient_id = int(raw_clause.get("recipient_id", counterparty_id))
            except (TypeError, ValueError):
                return None, "Choose valid investment participants."

            if {investor_id, recipient_id} != {proposer_id, counterparty_id} or investor_id == recipient_id:
                return None, "Investment clauses may only involve the proposer and counterparty."

            scope_error = _validate_scope_coverage(scope, recipient_id, game_state)
            if scope_error:
                return None, scope_error

            escrow_amount = round_money(config.get("escrow_amount", 0))
            profit_share_percent = round(float(config.get("profit_share_percent", 0) or 0), 4)
            max_payout = round_money(config.get("max_payout", 0))
            payout_multiple_limit = float(settings.get("max_private_equity_payout_multiple", 1.75) or 1.75)
            investor = players.get(investor_id) or proposer
            if escrow_amount <= 0:
                return None, "Investment escrow must be positive."
            if escrow_amount > float(investor.get("balance", 0) or 0):
                return None, "The investor cannot currently fund that escrow amount."
            if profit_share_percent <= 0 or profit_share_percent >= 1:
                return None, "Profit share percent must be between 0 and 1."
            if max_payout <= 0 or max_payout > round_money(escrow_amount * payout_multiple_limit):
                return None, f"Max payout cannot exceed {payout_multiple_limit:.2f}x the escrow amount."

            grantor_id = investor_id
            beneficiary_id = recipient_id
            config = {
                "escrow_amount": escrow_amount,
                "profit_share_percent": profit_share_percent,
                "max_payout": max_payout,
            }

        normalized_clauses.append({
            "type": clause_type,
            "grantor_id": grantor_id,
            "beneficiary_id": beneficiary_id,
            "scope": scope,
            "config": config,
            "deadline": deadline,
        })

    if not normalized_clauses:
        return None, "Add at least one valid clause to the deal."

    return {
        "counterparty_id": counterparty_id,
        "title": (str(data.get("title") or "").strip() or None),
        "clauses": normalized_clauses,
    }, None


def create_deal(match_id: int, proposer_id: int, payload: dict, *, counter_of_deal_id: int | None = None) -> Deal | None:
    proposal_version = 1
    if counter_of_deal_id:
        prior = _safe_first(Deal.query.filter_by(id=counter_of_deal_id, match_id=match_id))
        if prior is not None:
            proposal_version = int(prior.proposal_version or 1) + 1

    deal = Deal(
        match_id=match_id,
        proposer_id=proposer_id,
        counterparty_id=int(payload["counterparty_id"]),
        status=DEAL_STATUS_PROPOSED,
        title=(payload.get("title") or None),
        created_at=datetime.utcnow(),
        last_updated_at=datetime.utcnow(),
        proposal_version=proposal_version,
        counter_of_deal_id=counter_of_deal_id,
    )
    db.session.add(deal)
    db.session.flush()

    for clause_payload in payload.get("clauses") or []:
        deadline = clause_payload.get("deadline") or {}
        state = {
            "remaining": int(deadline.get("initial", 0) or 0),
        }
        if clause_payload.get("type") == CLAUSE_INVESTMENT:
            state.update({
                "escrow_remaining": 0.0,
                "payout_to_date": 0.0,
            })
        db.session.add(
            DealClause(
                deal_id=deal.id,
                clause_type=clause_payload["type"],
                grantor_id=int(clause_payload["grantor_id"]),
                beneficiary_id=int(clause_payload["beneficiary_id"]),
                scope_json=clause_payload.get("scope") or {},
                config_json=clause_payload.get("config") or {},
                deadline_json=deadline,
                state_json=state,
                status=CLAUSE_STATUS_PENDING,
            )
        )

    if not _safe_commit():
        return None
    return _safe_first(Deal.query.filter_by(id=deal.id))


def _sync_player_balances_to_db(game_state: dict) -> None:
    from app.models.player import MatchPlayer

    player_lookup = _player_map(game_state)
    for player_id, player in player_lookup.items():
        record = MatchPlayer.query.get(player_id)
        if record is not None:
            record.balance = round_money(player.get("balance", 0))


def _update_deal_status_from_clauses(deal: Deal) -> None:
    clause_statuses = {clause.status for clause in (deal.clauses or [])}
    if deal.status in {DEAL_STATUS_REJECTED, DEAL_STATUS_CANCELLED, DEAL_STATUS_COUNTERED}:
        return
    if not clause_statuses:
        deal.status = DEAL_STATUS_COMPLETED
    elif clause_statuses <= {CLAUSE_STATUS_COMPLETED}:
        deal.status = DEAL_STATUS_COMPLETED
    elif clause_statuses <= {CLAUSE_STATUS_EXPIRED, CLAUSE_STATUS_COMPLETED}:
        deal.status = DEAL_STATUS_EXPIRED
    elif all(status in {CLAUSE_STATUS_CANCELLED, CLAUSE_STATUS_EXPIRED, CLAUSE_STATUS_COMPLETED} for status in clause_statuses):
        deal.status = DEAL_STATUS_EXPIRED
    else:
        deal.status = DEAL_STATUS_ACCEPTED
    deal.last_updated_at = datetime.utcnow()


def accept_deal(deal: Deal, game_state: dict) -> tuple[dict, str | None]:
    if deal.status != DEAL_STATUS_PROPOSED:
        return game_state, "Deal is no longer pending."

    if not deals_enabled(game_state.get("settings")):
        return game_state, "Deals are disabled."

    next_state = dict(game_state)
    players = _player_map(next_state)

    for clause in deal.clauses or []:
        if clause.clause_type == CLAUSE_INVESTMENT:
            config = dict(clause.config_json or {})
            escrow_amount = round_money(config.get("escrow_amount", 0))
            investor = players.get(int(clause.grantor_id or 0))
            if investor is None or investor.get("is_bankrupt"):
                return game_state, "The investor is no longer available."
            if round_money(investor.get("balance", 0)) < escrow_amount:
                return game_state, "The investor can no longer fund the escrow amount."
            next_state, _ = spend_player_balance(next_state, clause.grantor_id, escrow_amount)
            _set_clause_state(clause, {
                "remaining": int((clause.deadline_json or {}).get("initial", 0) or 0),
                "escrow_remaining": escrow_amount,
                "payout_to_date": 0.0,
            })
        else:
            _set_clause_state(clause, {
                "remaining": int((clause.deadline_json or {}).get("initial", 0) or 0),
            })

        clause.status = CLAUSE_STATUS_ACTIVE
        clause.activated_at = datetime.utcnow()

    deal.status = DEAL_STATUS_ACCEPTED
    deal.accepted_at = datetime.utcnow()
    deal.responded_at = datetime.utcnow()
    deal.last_updated_at = datetime.utcnow()
    _sync_player_balances_to_db(next_state)
    if not _safe_commit():
        return game_state, "Failed to activate the deal."

    return attach_deals_snapshot(next_state, deal.match_id), None


def reject_deal(deal: Deal) -> bool:
    deal.status = DEAL_STATUS_REJECTED
    deal.responded_at = datetime.utcnow()
    deal.last_updated_at = datetime.utcnow()
    return _safe_commit()


def cancel_deal(deal: Deal, game_state: dict) -> tuple[dict, bool]:
    next_state = dict(game_state)
    if deal.status == DEAL_STATUS_ACCEPTED:
        next_state = terminate_deal(deal, next_state, status=DEAL_STATUS_CANCELLED)
    else:
        deal.status = DEAL_STATUS_CANCELLED
        deal.cancelled_at = datetime.utcnow()
        deal.last_updated_at = datetime.utcnow()
        _safe_commit()
    return attach_deals_snapshot(next_state, deal.match_id), True


def terminate_deal(deal: Deal, game_state: dict, *, status: str) -> dict:
    next_state = dict(game_state)
    for clause in deal.clauses or []:
        if clause.status not in {CLAUSE_STATUS_ACTIVE, CLAUSE_STATUS_PENDING}:
            continue
        next_state = terminate_clause(clause, next_state, status=CLAUSE_STATUS_CANCELLED if status == DEAL_STATUS_CANCELLED else CLAUSE_STATUS_EXPIRED)

    deal.status = status
    if status == DEAL_STATUS_CANCELLED:
        deal.cancelled_at = datetime.utcnow()
    else:
        deal.responded_at = datetime.utcnow()
    deal.last_updated_at = datetime.utcnow()
    _safe_commit()
    return next_state


def terminate_clause(clause: DealClause, game_state: dict, *, status: str) -> dict:
    next_state = dict(game_state)
    state = _clause_state(clause)
    if clause.clause_type == CLAUSE_INVESTMENT:
        escrow_remaining = round_money(state.get("escrow_remaining", 0))
        if escrow_remaining > 0:
            next_state, _ = credit_player_with_debt_settlement(next_state, clause.grantor_id, escrow_remaining)
            state["escrow_remaining"] = 0.0
        for tranche in clause.investment_tranches or []:
            tranche.active = False
    state["remaining"] = max(0, int(state.get("remaining", 0) or 0))
    clause.state_json = state
    clause.status = status
    clause.expired_at = datetime.utcnow()
    _sync_player_balances_to_db(next_state)
    _update_deal_status_from_clauses(clause.deal)
    _safe_commit()
    return next_state


def get_active_pairwise_deals(game_state: dict, player_id: int, other_id: int) -> list[dict]:
    deals = game_state.get("deals") or []
    active = []
    for deal in deals:
        if deal.get("status") != DEAL_STATUS_ACCEPTED:
            continue
        participants = {int(deal.get("proposer_id") or 0), int(deal.get("counterparty_id") or 0)}
        if participants == {int(player_id or 0), int(other_id or 0)}:
            active.append(deal)
    return active


def apply_rent_deal_effects(
    game_state: dict,
    match_id: int,
    *,
    payer_id: int,
    owner_id: int,
    prop: dict,
    base_rent: float,
) -> tuple[dict, float, list[dict]]:
    next_state = attach_deals_snapshot(game_state, match_id)
    applicable_immunities = []
    applicable_discounts = []
    logs: list[dict] = []

    for deal in next_state.get("deals") or []:
        if deal.get("status") != DEAL_STATUS_ACCEPTED:
            continue
        for clause in deal.get("clauses") or []:
            if clause.get("status") != CLAUSE_STATUS_ACTIVE:
                continue
            if int(clause.get("beneficiary_id") or 0) != int(payer_id or 0):
                continue
            if int(clause.get("grantor_id") or 0) != int(owner_id or 0):
                continue
            if not _scope_matches_property(clause.get("scope"), prop, owner_id):
                continue
            if clause.get("type") == CLAUSE_IMMUNITY:
                applicable_immunities.append(clause)
            elif clause.get("type") == CLAUSE_DISCOUNT:
                applicable_discounts.append(clause)

    if applicable_immunities:
        selected = sorted(applicable_immunities, key=lambda clause: int((clause.get("deadline") or {}).get("remaining", 0) or 0))[0]
        next_state = consume_clause_trigger(next_state, int(selected["id"]), match_id, trigger_metric=DEADLINE_BENEFICIARY_LANDINGS)
        refreshed = next(
            (
                clause
                for deal in (next_state.get("deals") or [])
                for clause in (deal.get("clauses") or [])
                if int(clause.get("id") or 0) == int(selected.get("id") or 0)
            ),
            selected,
        )
        logs.append({
            "event_type": "deal_immunity_applied",
            "description": (
                f"Deal immunity blocked rent on {prop.get('name', 'a property')} for this landing. "
                f"{int((refreshed.get('deadline') or {}).get('remaining', 0) or 0)} uses remain."
            ),
            "deal_id": selected.get("deal_id"),
            "clause_id": selected.get("id"),
            "remaining": int((refreshed.get("deadline") or {}).get("remaining", 0) or 0),
        })
        return next_state, 0.0, logs

    if applicable_discounts:
        selected = sorted(
            applicable_discounts,
            key=lambda clause: float((clause.get("config") or {}).get("rent_multiplier", 1) or 1),
        )[0]
        multiplier = float((selected.get("config") or {}).get("rent_multiplier", 1) or 1)
        discounted_rent = round_money(base_rent * multiplier)
        next_state = consume_clause_trigger(next_state, int(selected["id"]), match_id, trigger_metric=DEADLINE_BENEFICIARY_LANDINGS)
        refreshed = next(
            (
                clause
                for deal in (next_state.get("deals") or [])
                for clause in (deal.get("clauses") or [])
                if int(clause.get("id") or 0) == int(selected.get("id") or 0)
            ),
            selected,
        )
        logs.append({
            "event_type": "deal_discount_applied",
            "description": (
                f"Deal discount reduced rent on {prop.get('name', 'a property')} to ${discounted_rent:.2f}. "
                f"{int((refreshed.get('deadline') or {}).get('remaining', 0) or 0)} uses remain."
            ),
            "deal_id": selected.get("deal_id"),
            "clause_id": selected.get("id"),
            "remaining": int((refreshed.get("deadline") or {}).get("remaining", 0) or 0),
            "rent_multiplier": multiplier,
        })
        return next_state, discounted_rent, logs

    return next_state, round_money(base_rent), logs


def _find_clause(clause_id: int) -> DealClause | None:
    return _safe_first(DealClause.query.filter_by(id=clause_id))


def consume_clause_trigger(game_state: dict, clause_id: int, match_id: int, *, trigger_metric: str) -> dict:
    clause = _find_clause(clause_id)
    if clause is None or clause.status != CLAUSE_STATUS_ACTIVE:
        return attach_deals_snapshot(game_state, match_id)
    deadline = dict(clause.deadline_json or {})
    if deadline.get("metric") != trigger_metric:
        return attach_deals_snapshot(game_state, match_id)

    state = _clause_state(clause)
    remaining = max(0, int(state.get("remaining", deadline.get("initial", 0)) or 0) - 1)
    state["remaining"] = remaining
    clause.state_json = state
    clause.deal.last_updated_at = datetime.utcnow()
    if remaining <= 0:
        updated_state = terminate_clause(clause, game_state, status=CLAUSE_STATUS_EXPIRED)
        from app.engine.game_loop import log_and_broadcast
        return log_and_broadcast(
            updated_state,
            "deal_expired",
            f"A deal clause expired for deal #{clause.deal_id}.",
            match_id,
            None,
            DummySocketIO(),
        ) if False else attach_deals_snapshot(updated_state, match_id)

    _safe_commit()
    return attach_deals_snapshot(game_state, match_id)


class DummySocketIO:
    def emit(self, *args, **kwargs):
        return None


def decrement_turn_deadlines(game_state: dict, match_id: int, *, player_id: int) -> dict:
    next_state = dict(game_state)
    clauses = _safe_all(
        DealClause.query.join(Deal, Deal.id == DealClause.deal_id).filter(
            Deal.match_id == match_id,
            Deal.status == DEAL_STATUS_ACCEPTED,
            DealClause.status == CLAUSE_STATUS_ACTIVE,
        )
    )
    for clause in clauses:
        metric = (clause.deadline_json or {}).get("metric")
        if metric == DEADLINE_BENEFICIARY_TURNS and int(clause.beneficiary_id or 0) == int(player_id or 0):
            next_state = consume_clause_trigger(next_state, clause.id, match_id, trigger_metric=metric)
        elif metric == DEADLINE_GRANTOR_TURNS and int(clause.grantor_id or 0) == int(player_id or 0):
            next_state = consume_clause_trigger(next_state, clause.id, match_id, trigger_metric=metric)
    return attach_deals_snapshot(next_state, match_id)


def decrement_round_deadlines(game_state: dict, match_id: int) -> dict:
    next_state = dict(game_state)
    clauses = _safe_all(
        DealClause.query.join(Deal, Deal.id == DealClause.deal_id).filter(
            Deal.match_id == match_id,
            Deal.status == DEAL_STATUS_ACCEPTED,
            DealClause.status == CLAUSE_STATUS_ACTIVE,
            DealClause.deadline_json["metric"].as_string() == DEADLINE_FULL_ROUNDS,
        )
    )
    if not clauses:
        clauses = [
            clause
            for clause in _safe_all(
                DealClause.query.join(Deal, Deal.id == DealClause.deal_id).filter(
                    Deal.match_id == match_id,
                    Deal.status == DEAL_STATUS_ACCEPTED,
                    DealClause.status == CLAUSE_STATUS_ACTIVE,
                )
            )
            if (clause.deadline_json or {}).get("metric") == DEADLINE_FULL_ROUNDS
        ]
    for clause in clauses:
        next_state = consume_clause_trigger(next_state, clause.id, match_id, trigger_metric=DEADLINE_FULL_ROUNDS)
    return attach_deals_snapshot(next_state, match_id)


def decrement_rotation_deadlines(game_state: dict, match_id: int, *, beneficiary_id: int) -> dict:
    next_state = dict(game_state)
    clauses = _safe_all(
        DealClause.query.join(Deal, Deal.id == DealClause.deal_id).filter(
            Deal.match_id == match_id,
            Deal.status == DEAL_STATUS_ACCEPTED,
            DealClause.status == CLAUSE_STATUS_ACTIVE,
        )
    )
    for clause in clauses:
        if (clause.deadline_json or {}).get("metric") == DEADLINE_BENEFICIARY_ROTATIONS and int(clause.beneficiary_id or 0) == int(beneficiary_id or 0):
            next_state = consume_clause_trigger(next_state, clause.id, match_id, trigger_metric=DEADLINE_BENEFICIARY_ROTATIONS)
    return attach_deals_snapshot(next_state, match_id)


def expire_player_clauses(game_state: dict, match_id: int, *, player_id: int) -> dict:
    next_state = dict(game_state)
    clauses = _safe_all(
        DealClause.query.join(Deal, Deal.id == DealClause.deal_id).filter(
            Deal.match_id == match_id,
            Deal.status == DEAL_STATUS_ACCEPTED,
            DealClause.status == CLAUSE_STATUS_ACTIVE,
        )
    )
    for clause in clauses:
        if int(clause.grantor_id or 0) == int(player_id or 0) or int(clause.beneficiary_id or 0) == int(player_id or 0):
            next_state = terminate_clause(clause, next_state, status=CLAUSE_STATUS_EXPIRED)
    return attach_deals_snapshot(next_state, match_id)


def spend_investment_escrow(
    game_state: dict,
    match_id: int,
    *,
    player_id: int,
    property_id: int,
    property_snapshot: dict,
    build_cost: float,
    next_dev_level: int,
    econ: dict,
    selected_clause_id: int | None = None,
) -> tuple[dict, dict | None]:
    next_state = attach_deals_snapshot(game_state, match_id)
    eligible_options = []
    for prop in next_state.get("properties") or []:
        if int(prop.get("id") or 0) == int(property_id or 0):
            eligible_options = list(prop.get("deal_investment_options") or [])
            break

    if selected_clause_id is not None:
        eligible_options = [option for option in eligible_options if int(option.get("clause_id") or 0) == int(selected_clause_id)]

    if not eligible_options:
        return next_state, None

    option = sorted(eligible_options, key=lambda entry: float(entry.get("escrow_remaining", 0) or 0), reverse=True)[0]
    clause = _find_clause(int(option.get("clause_id") or 0))
    if clause is None or clause.status != CLAUSE_STATUS_ACTIVE:
        return next_state, None

    state = _clause_state(clause)
    escrow_remaining = round_money(state.get("escrow_remaining", 0))
    if escrow_remaining <= 0:
        return next_state, None

    escrow_used = min(round_money(build_cost), escrow_remaining)
    if escrow_used <= 0:
        return next_state, None

    baseline_rent = calculate_rent_with_dev(property_snapshot, econ, next_state)
    funded_property = dict(property_snapshot)
    funded_property["dev_level"] = next_dev_level
    funded_rent = calculate_rent_with_dev(funded_property, econ, next_state)

    config = dict(clause.config_json or {})
    escrow_amount = round_money(config.get("escrow_amount", build_cost))
    payout_ratio = 0.0 if escrow_amount <= 0 else min(1.0, escrow_used / escrow_amount)
    tranche_max_payout = round_money(float(config.get("max_payout", 0) or 0) * payout_ratio)
    if tranche_max_payout <= 0:
        tranche_max_payout = round_money(escrow_used * 1.5)

    db.session.add(
        DealInvestmentTranche(
            deal_clause_id=clause.id,
            property_id=property_id,
            investor_id=clause.grantor_id,
            recipient_id=clause.beneficiary_id,
            funded_cost=escrow_used,
            baseline_dev_level=int(property_snapshot.get("dev_level", 0) or 0),
            funded_dev_level=int(next_dev_level),
            baseline_rent=baseline_rent,
            funded_rent=funded_rent,
            profit_share_percent=float(config.get("profit_share_percent", 0) or 0),
            max_payout=tranche_max_payout,
            payout_to_date=0,
            active=True,
        )
    )
    state["escrow_remaining"] = round_money(escrow_remaining - escrow_used)
    clause.state_json = state
    clause.deal.last_updated_at = datetime.utcnow()
    _safe_commit()

    return attach_deals_snapshot(next_state, match_id), {
        "deal_id": clause.deal_id,
        "clause_id": clause.id,
        "escrow_used": escrow_used,
        "escrow_remaining": state["escrow_remaining"],
        "investor_id": clause.grantor_id,
        "recipient_id": clause.beneficiary_id,
    }


def apply_investment_profit_share(
    game_state: dict,
    match_id: int,
    *,
    property_id: int,
    owner_id: int,
    actual_rent_paid: float,
) -> tuple[dict, list[dict]]:
    next_state = attach_deals_snapshot(game_state, match_id)
    tranches = _safe_all(
        DealInvestmentTranche.query.join(DealClause, DealClause.id == DealInvestmentTranche.deal_clause_id).join(Deal, Deal.id == DealClause.deal_id).filter(
            Deal.match_id == match_id,
            Deal.status == DEAL_STATUS_ACCEPTED,
            DealClause.status == CLAUSE_STATUS_ACTIVE,
            DealInvestmentTranche.property_id == property_id,
            DealInvestmentTranche.active.is_(True),
        )
    )
    if not tranches or actual_rent_paid <= 0:
        return next_state, []

    logs = []
    distributable = round_money(actual_rent_paid)
    for tranche in sorted(tranches, key=lambda entry: entry.created_at or datetime.utcnow()):
        remaining_cap = round_money(float(tranche.max_payout or 0) - float(tranche.payout_to_date or 0))
        if remaining_cap <= 0 or distributable <= 0:
            tranche.active = remaining_cap > 0
            continue

        incremental_rent = max(0.0, round_money(actual_rent_paid - float(tranche.baseline_rent or 0)))
        uplift_cap = max(0.0, round_money(float(tranche.funded_rent or 0) - float(tranche.baseline_rent or 0)))
        if uplift_cap > 0:
            incremental_rent = min(incremental_rent, uplift_cap)
        if incremental_rent <= 0:
            continue

        investor_share = round_money(incremental_rent * float(tranche.profit_share_percent or 0))
        investor_share = min(investor_share, remaining_cap, distributable)
        if investor_share <= 0:
            continue

        next_state, _ = spend_player_balance(next_state, owner_id, investor_share)
        next_state, _ = credit_player_with_debt_settlement(next_state, tranche.investor_id, investor_share)
        distributable = round_money(distributable - investor_share)
        tranche.payout_to_date = round_money(float(tranche.payout_to_date or 0) + investor_share)
        if round_money(float(tranche.max_payout or 0) - float(tranche.payout_to_date or 0)) <= 0:
            tranche.active = False
        logs.append({
            "event_type": "deal_profit_paid",
            "description": f"${investor_share:.2f} of rent from property #{property_id} was routed to an investor under an active deal.",
            "investor_id": tranche.investor_id,
            "recipient_id": tranche.recipient_id,
            "amount": investor_share,
            "deal_id": tranche.clause.deal_id,
            "deal_clause_id": tranche.deal_clause_id,
        })

        clause = tranche.clause
        state = _clause_state(clause)
        state["payout_to_date"] = round_money(state.get("payout_to_date", 0) + investor_share)
        clause.state_json = state
        if round_money(float((clause.config_json or {}).get("max_payout", 0) or 0) - float(state.get("payout_to_date", 0) or 0)) <= 0:
            next_state = terminate_clause(clause, next_state, status=CLAUSE_STATUS_COMPLETED)

    _sync_player_balances_to_db(next_state)
    _safe_commit()
    return attach_deals_snapshot(next_state, match_id), logs