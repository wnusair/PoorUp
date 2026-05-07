"""Bot player creation, scheduling, and decision logic for PoorUp."""

from __future__ import annotations

import math
import json
import random
import uuid
from datetime import datetime
from typing import Any

from flask import current_app
from sqlalchemy.exc import OperationalError, ProgrammingError
from werkzeug.security import generate_password_hash

from app import db, redis_client, socketio
from app.engine.debt import (
    credit_player_with_debt_settlement,
    get_total_pending_player_debt,
    has_pending_player_debt,
    spend_player_balance,
)
from app.engine.analytics import record_lobbying_contribution
from app.engine.economy import (
    LIBERAL_DEMOCRACY_MAX_CAPITAL_YIELD_RATE,
    calculate_development_cost,
    calculate_development_refund,
    calculate_net_worth,
    calculate_rent_with_dev,
    calculate_transit_rent,
    count_transits_owned_by,
    get_player_properties,
    has_full_monopoly,
    property_is_fully_developed,
)
from app.engine.events import reset_auction_timer, start_auction
from app.engine.game_loop import (
    DEFAULT_SETTINGS,
    broadcast_game_state_snapshot,
    check_win_condition,
    declare_player_bankruptcy,
    end_turn,
    finalize_turn_resolution,
    load_game_state,
    log_and_broadcast,
    persist_game_state,
    process_turn,
)
from app.engine.plot import (
    start_communist_plot,
    submit_plot_action,
    submit_plot_counter_action,
    submit_plot_join,
    submit_plot_leave,
)
from app.engine.liberal_democracy import (
    buy_corporate_property as execute_liberal_democracy_buyout,
    deposit_bank_funds as execute_liberal_democracy_deposit,
    repay_bank_loan as execute_liberal_democracy_repay,
    request_bank_loan as execute_liberal_democracy_loan,
    submit_market_order as execute_liberal_democracy_market_order,
    withdraw_bank_funds as execute_liberal_democracy_withdraw,
)
from app.engine.social import (
    GRIEVANCE_POLICY_TARGETS,
    property_private_actions_locked,
    submit_minarchist_emergency_reform,
    submit_negotiation_contribution,
)
from app.engine.deals import attach_deals_snapshot, calculate_effective_build_loan_payout, spend_investment_escrow
from app.engine.trading import apply_trade_acceptance, sum_lobby_pledges, validate_trade_proposal
from app.engine.deals import accept_deal, create_deal, normalize_deal_request_payload, reject_deal, serialize_deal
from app.models.deal import Deal
from app.models.player import Match, MatchPlayer, User
from app.models.policy import (
    Lobbying as LobbyContribution,
    Policy,
    calculate_lobbying_success_chance,
    ensure_match_lobbying_policy,
    resolve_lobbying_target,
)
from app.models.property import Property
from app.models.trade import Trade
from app.utils.color_utils import get_available_player_colors
from app.utils.bot_registry import (
    choose_default_personality,
    get_difficulty_metadata,
    get_personality_metadata,
    infer_archetype_from_personality,
    infer_legacy_difficulty,
    normalize_bot_difficulty,
    normalize_bot_personality,
    resolve_bot_configuration,
)
from app.utils.settings import normalize_game_mode, normalize_government_type


STRATEGY_VERSION = 3
BOT_NAME_PARTS = [
    "Atlas",
    "Nova",
    "Sable",
    "Argon",
    "Lyric",
    "Harbor",
    "Delta",
    "Ion",
    "Axiom",
    "Marlin",
    "Cinder",
    "Basil",
    "Orion",
    "Kite",
    "Jasper",
    "Vale",
    "Piper",
    "Talon",
    "Ember",
    "Vanta",
]
BOT_TASK_TTL_SECONDS = 120
BOT_STATE_EVALUATION_DEBOUNCE_SECONDS = 0.35
BOT_STATE_EVALUATION_TTL_SECONDS = 5
TRADE_MIN_INCREMENT = 25.0
HIDDEN_PARTNERSHIP_KEY = "game:{match_id}:bot_hidden_partnerships"
SOCIAL_TARGET_PRIORITY = {
    "stabilization_fund": 1,
    "money_supply_contract": 2,
    "welfare_increase": 2,
    "tax_bracket_rate_up": 3,
    "rent_control": 3,
    "tax_multiplier_decrease": 4,
    "economic_stimulus": 5,
    "bailout_enable": 6,
    "money_supply_expand": 7,
}


def _profile_from_player(player: dict[str, Any], current_player_id: int | None = None, current_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    if current_player_id is not None and int(player.get("id") or 0) == int(current_player_id) and current_profile:
        return dict(current_profile)
    profile = player.get("bot_profile")
    if isinstance(profile, dict):
        return dict(profile)
    return {
        "difficulty": player.get("bot_difficulty") or player.get("difficulty"),
        "archetype": player.get("bot_archetype") or player.get("archetype"),
        "persona": player.get("bot_persona") or player.get("persona"),
    }


def _bot_difficulty_from_player(player: dict[str, Any], current_player_id: int | None = None, current_profile: dict[str, Any] | None = None) -> str:
    profile = _profile_from_player(player, current_player_id, current_profile)
    return normalize_bot_difficulty(profile.get("difficulty") or infer_legacy_difficulty(profile.get("persona")))


def _eligible_hidden_partnership_bot_ids(
    game_state: dict[str, Any],
    current_player_id: int | None = None,
    current_profile: dict[str, Any] | None = None,
) -> list[int]:
    active_players = [player for player in game_state.get("players", []) if not player.get("is_bankrupt")]
    if len(active_players) < 4:
        return []
    eligible = []
    for player in active_players:
        if not player.get("is_bot"):
            continue
        difficulty = _bot_difficulty_from_player(player, current_player_id, current_profile)
        if difficulty in {"hard", "expert"}:
            eligible.append(int(player.get("id") or 0))
    return sorted(player_id for player_id in eligible if player_id > 0)


def _load_hidden_partnerships(match_id: int) -> dict[str, Any]:
    if redis_client is None:
        return {"pairs": []}
    raw_value = redis_client.get(HIDDEN_PARTNERSHIP_KEY.format(match_id=match_id))
    if raw_value is None:
        return {"pairs": []}
    if isinstance(raw_value, bytes):
        raw_value = raw_value.decode("utf-8")
    try:
        payload = json.loads(str(raw_value))
    except (TypeError, ValueError):
        return {"pairs": []}
    return {"pairs": list((payload or {}).get("pairs") or [])}


def _save_hidden_partnerships(match_id: int, payload: dict[str, Any]) -> None:
    if redis_client is None:
        return
    redis_client.set(
        HIDDEN_PARTNERSHIP_KEY.format(match_id=match_id),
        json.dumps({"pairs": list(payload.get("pairs") or [])}, sort_keys=True),
        ex=60 * 60 * 8,
    )


def ensure_hidden_bot_partnerships(
    game_state: dict[str, Any],
    *,
    current_player_id: int | None = None,
    current_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    match_id = int(game_state.get("match_id") or 0)
    if match_id <= 0:
        return {"pairs": []}
    eligible_ids = _eligible_hidden_partnership_bot_ids(game_state, current_player_id, current_profile)
    payload = _load_hidden_partnerships(match_id)
    valid_pairs = []
    eligible_set = set(eligible_ids)
    for pair in payload.get("pairs") or []:
        player_ids = sorted(int(value) for value in pair.get("player_ids", []) if int(value or 0) in eligible_set)
        if len(player_ids) == 2:
            valid_pairs.append({**dict(pair), "player_ids": player_ids})
    if valid_pairs:
        payload = {"pairs": valid_pairs[:1]}
        _save_hidden_partnerships(match_id, payload)
        return payload
    if len(eligible_ids) < 2:
        return {"pairs": []}
    payload = {
        "pairs": [
            {
                "player_ids": eligible_ids[:2],
                "formed_round": int(game_state.get("current_round", 1) or 1),
                "cooperation_score": 0.0,
            }
        ]
    }
    _save_hidden_partnerships(match_id, payload)
    return payload


def hidden_partner_ids(player_id: int, game_state: dict[str, Any]) -> list[int]:
    player_id = int(player_id or 0)
    payload = ensure_hidden_bot_partnerships(game_state)
    for pair in payload.get("pairs") or []:
        ids = [int(value) for value in pair.get("player_ids", [])]
        if player_id in ids:
            return [candidate for candidate in ids if candidate != player_id]
    return []


def calculate_hidden_partnership_cooperation_metrics(game_state: dict[str, Any]) -> dict[str, Any]:
    payload = ensure_hidden_bot_partnerships(game_state)
    pairs = payload.get("pairs") or []
    player_lookup = {int(player.get("id") or 0): player for player in game_state.get("players", [])}
    edges = []
    for pair in pairs:
        ids = [int(value) for value in pair.get("player_ids", [])]
        if len(ids) != 2:
            continue
        left = player_lookup.get(ids[0], {})
        right = player_lookup.get(ids[1], {})
        left_cash = float(left.get("balance", 0) or 0)
        right_cash = float(right.get("balance", 0) or 0)
        cash_gap = abs(left_cash - right_cash)
        support_bias = max(0.0, 1.0 - min(1.0, cash_gap / 1800.0))
        edges.append({
            "player_ids": ids,
            "cooperation_score": round(0.35 + support_bias * 0.45, 4),
        })
    return {
        "pair_count": len(edges),
        "cooperation_edges": edges,
        "average_cooperation": round(sum(edge["cooperation_score"] for edge in edges) / max(1, len(edges)), 4) if edges else 0.0,
    }
LOBBY_INCREMENT = 25.0
BOT_NEGOTIATION_SHARE_CAP = {
    "easy": 0.08,
    "normal": 0.15,
    "hard": 0.22,
    "expert": 0.28,
}


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def build_bot_profile(
    settings: dict | None,
    *,
    difficulty: str | None = None,
    persona: str | None = None,
    archetype: str | None = None,
    rng: random.Random | None = None,
    seat_index: int = 0,
) -> dict[str, Any]:
    rng = rng or random.Random()
    merged_settings = {**DEFAULT_SETTINGS, **(settings or {})}
    government_type = normalize_government_type(
        merged_settings.get("government_type", DEFAULT_SETTINGS["government_type"])
    )
    game_mode = normalize_game_mode(merged_settings.get("game_mode", "standard"))
    normalized_difficulty = normalize_bot_difficulty(
        difficulty or infer_legacy_difficulty(persona)
    )
    if persona is None and archetype is None:
        normalized_persona = choose_default_personality(normalized_difficulty, seat_index=seat_index)
        normalized_archetype = infer_archetype_from_personality(normalized_persona)
    else:
        normalized_difficulty, normalized_persona, normalized_archetype = resolve_bot_configuration(
            normalized_difficulty,
            selection=persona,
            archetype=archetype,
        )

    difficulty_meta = get_difficulty_metadata(normalized_difficulty)
    personality_meta = get_personality_metadata(normalized_persona)
    difficulty_style = difficulty_meta["style"]
    difficulty_skill = difficulty_meta["skill"]
    personality_style = personality_meta["style"]
    capabilities = dict(difficulty_meta["allowed_capabilities"])

    planning_horizon = int(difficulty_skill["planning_horizon"])
    valuation_noise = float(difficulty_skill["valuation_noise"])
    aggression = (
        float(personality_style["aggression"])
        + float(difficulty_style["aggression_bonus"])
        + rng.uniform(-(valuation_noise * 0.6), valuation_noise * 0.6)
    )
    liquidity_bias = (
        float(personality_style["liquidity_bias"])
        + float(difficulty_style["liquidity_bonus"])
        + rng.uniform(-0.05, 0.05)
    )
    macro_focus = float(personality_style["macro_focus"])
    trade_focus = float(personality_style["trade_focus"])
    auction_focus = float(personality_style["auction_focus"])
    development_focus = float(personality_style["development_focus"])
    denial_focus = float(personality_style["denial_focus"])
    patience = float(personality_style["patience"])
    lobby_focus = float(personality_style["lobby_focus"])
    set_focus = float(personality_style["set_focus"])

    if game_mode == "chaos":
        aggression -= 0.03
        liquidity_bias += 0.10
        macro_focus += 0.10
        patience += 0.08
    elif game_mode == "speed":
        aggression += 0.08
        liquidity_bias -= 0.06
        development_focus += 0.06
        set_focus += 0.08
        planning_horizon = max(2, planning_horizon - 1)
    elif game_mode == "cooperative":
        aggression -= 0.04
        liquidity_bias += 0.04
        denial_focus -= 0.08
        trade_focus += 0.08
        macro_focus += 0.06

    if government_type == "liberal_democracy":
        liquidity_bias += 0.06
        macro_focus += 0.08
        trade_focus += 0.04
        lobby_focus += 0.08
    elif government_type == "social_democracy":
        aggression += 0.04
        liquidity_bias -= 0.08
        macro_focus += 0.08
        lobby_focus += 0.08
    elif government_type == "minarchism":
        aggression -= 0.03
        liquidity_bias += 0.12
        macro_focus -= 0.08
        lobby_focus = 0.0

    risk_tolerance = max(0.2, min(0.95, aggression + (1.0 - liquidity_bias) * 0.22))
    liquidity_bias = max(0.2, min(0.92, liquidity_bias))
    macro_focus = max(0.1, min(0.98, macro_focus + rng.uniform(-0.04, 0.05)))
    trade_focus = max(0.18, min(0.95, trade_focus + rng.uniform(-0.05, 0.05)))
    auction_focus = max(0.22, min(0.92, auction_focus + rng.uniform(-0.05, 0.04)))
    development_focus = max(0.22, min(0.98, development_focus + rng.uniform(-0.04, 0.05)))
    denial_focus = max(0.08, min(0.98, denial_focus + rng.uniform(-0.04, 0.05)))
    patience = max(0.15, min(0.95, patience + rng.uniform(-0.04, 0.04)))
    lobby_focus = max(0.0, min(0.98, lobby_focus + rng.uniform(-0.04, 0.04)))
    set_focus = max(0.18, min(0.98, set_focus + rng.uniform(-0.05, 0.05)))

    reserve_floor = (175 + (liquidity_bias * 225)) * float(difficulty_style["reserve_multiplier"])
    development_buffer = (220 + (liquidity_bias * 280)) * (0.84 + (liquidity_bias * 0.32))
    auction_cap = 0.36 + (risk_tolerance * 0.28)
    purchase_cap = 0.42 + (risk_tolerance * 0.3) + (set_focus * 0.06)
    lobby_cap = (0.08 + (lobby_focus * 0.11)) * float(difficulty_style["lobby_share_multiplier"])

    if game_mode == "chaos":
        reserve_floor += 90
        development_buffer += 120
        lobby_cap -= 0.02
    elif game_mode == "speed":
        reserve_floor -= 35
        development_buffer -= 55
        auction_cap += 0.03

    if government_type == "liberal_democracy":
        reserve_floor += 35
        development_buffer += 40
        lobby_cap += 0.02
    elif government_type == "social_democracy":
        reserve_floor -= 25
        lobby_cap += 0.03
    elif government_type == "minarchism":
        reserve_floor += 40
        lobby_cap = 0.0

    leverage_confidence = float(difficulty_skill["leverage_confidence"])
    trade_precision = float(difficulty_skill["trade_precision"])
    welfare_dependency_tolerance = 0.12 + (0.24 if capabilities["welfare_abuse"] else 0.0)
    if normalized_persona in {"welfare_optimizer", "leverage_architect", "expansionist"}:
        welfare_dependency_tolerance += 0.18
    bailout_abuse = 0.0
    if capabilities["bailout_abuse"]:
        bailout_abuse = 0.42 + (leverage_confidence * 0.46)
        if normalized_persona in {"leverage_architect", "treasury_predator", "expansionist"}:
            bailout_abuse += 0.1
    treasury_shaping_bias = 0.18 + (lobby_focus * 0.55)
    if normalized_persona in {"policy_shaper", "treasury_predator"}:
        treasury_shaping_bias += 0.18
    cash_buffer_discount = 0.12 + (leverage_confidence * 0.38)
    if government_type == "social_democracy":
        cash_buffer_discount += 0.08

    doctrine = personality_meta["preferred_doctrines"][0]
    if government_type == "social_democracy" and normalized_difficulty in {"hard", "expert"}:
        if any(
            candidate in personality_meta["preferred_doctrines"]
            for candidate in {"social_democracy_leverage", "treasury_rebuild_then_leverage", "policy_shaping"}
        ):
            doctrine = "social_democracy_leverage"
    if government_type == "liberal_democracy" and "capital_markets_arbitrage" in personality_meta["preferred_doctrines"]:
        doctrine = "capital_markets_arbitrage"

    profile = {
        "strategy_version": STRATEGY_VERSION,
        "difficulty": normalized_difficulty,
        "persona": normalized_persona,
        "archetype": normalized_archetype,
        "doctrine": doctrine,
        "doctrine_preferences": list(personality_meta["preferred_doctrines"]),
        "economic_mode": game_mode,
        "government_type": government_type,
        "metadata": {
            "difficulty_label": difficulty_meta["label"],
            "persona_label": personality_meta["label"],
            "persona_description": personality_meta["short_description"],
        },
        "difficulty_capabilities": capabilities,
        "skill": {
            "planning_horizon": planning_horizon,
            "valuation_noise": round(valuation_noise, 3),
            "policy_lookahead": bool(capabilities["policy_lookahead"]),
            "leverage_confidence": round(leverage_confidence, 3),
            "trade_precision": round(trade_precision, 3),
        },
        "regime_bias": {
            "bailout_abuse": round(min(1.0, bailout_abuse), 3),
            "welfare_dependency_tolerance": round(min(1.0, welfare_dependency_tolerance), 3),
            "cash_buffer_discount": round(min(0.95, cash_buffer_discount), 3),
            "treasury_shaping_bias": round(min(1.0, treasury_shaping_bias), 3),
        },
        "core": {
            "aggression": round(max(0.18, min(0.96, aggression)), 3),
            "risk_tolerance": round(risk_tolerance, 3),
            "liquidity_bias": round(liquidity_bias, 3),
            "macro_focus": round(macro_focus, 3),
            "trade_focus": round(trade_focus, 3),
            "auction_focus": round(auction_focus, 3),
            "development_focus": round(development_focus, 3),
            "denial_focus": round(denial_focus * float(difficulty_style["denial_multiplier"]), 3),
            "patience": round(patience, 3),
            "lobby_focus": round(lobby_focus, 3),
            "set_focus": round(set_focus, 3),
        },
        "timing": {
            "roll_min_seconds": round(max(0.6, 1.2 - (leverage_confidence * 0.35)), 2),
            "roll_max_seconds": round(max(1.0, 1.85 - (leverage_confidence * 0.3)), 2),
            "decision_min_seconds": round(max(0.55, 0.95 - (trade_precision * 0.22)), 2),
            "decision_max_seconds": round(max(1.0, 1.55 - (trade_precision * 0.16)), 2),
            "management_min_seconds": round(max(0.55, 0.9 - (trade_precision * 0.18)), 2),
            "management_max_seconds": round(max(0.95, 1.4 - (trade_precision * 0.14)), 2),
            "auction_min_seconds": round(max(0.5, 0.8 - (trade_precision * 0.14)), 2),
            "auction_max_seconds": round(max(0.85, 1.3 - (trade_precision * 0.1)), 2),
            "trade_response_min_seconds": round(max(0.7, 1.15 - (trade_precision * 0.18)), 2),
            "trade_response_max_seconds": round(max(1.2, 2.1 - (trade_precision * 0.28)), 2),
            "post_trade_follow_up_seconds": 1.0,
        },
        "liquidity": {
            "emergency_cash_floor": round(reserve_floor * 0.72, 2),
            "reserve_cash_floor": round(reserve_floor, 2),
            "wealth_threshold": round(1650 + (risk_tolerance * 350), 2),
            "poor_threshold": round(300 + (liquidity_bias * 150), 2),
            "max_purchase_share": round(min(0.88, purchase_cap), 3),
            "max_auction_share": round(min(0.82, auction_cap), 3),
            "max_lobby_share": round(max(0.0, min(0.24, lobby_cap)), 3),
            "development_cash_buffer": round(development_buffer, 2),
            "unmortgage_cash_buffer": round(development_buffer + 80, 2),
            "post_monopoly_cash_floor": round(reserve_floor * 0.55, 2),
            "minimum_bail_reserve": round(reserve_floor * 0.45, 2),
        },
        "acquisition": {
            "base_price_weight": round(0.96 + rng.uniform(-0.06, 0.08), 3),
            "rent_turns_weight": round(4.8 + (risk_tolerance * 2.4) + (planning_horizon * 0.18), 3),
            "transit_turns_weight": round(4.4 + (risk_tolerance * 2.0), 3),
            "partial_set_bonus": round(0.18 + (risk_tolerance * 0.22), 3),
            "monopoly_completion_bonus": round(0.92 + (risk_tolerance * 0.78) + (set_focus * 0.18), 3),
            "monopoly_denial_bonus": round(0.14 + (denial_focus * 0.32), 3),
            "transit_synergy_bonus": round(0.18 + (risk_tolerance * 0.18), 3),
            "inflation_capture_weight": round(1.8 + (risk_tolerance * 2.0), 3),
            "tax_penalty_weight": round(0.32 + (liquidity_bias * 0.35), 3),
            "rent_control_penalty": round(0.10 + (liquidity_bias * 0.12), 3),
            "buy_value_margin": round(0.98 + (liquidity_bias * 0.09), 3),
            "force_buy_monopoly_margin": round(0.68 + (risk_tolerance * 0.16), 3),
            "late_game_multiplier": round(1.05 + (risk_tolerance * 0.18), 3),
            "chaos_reserve_penalty": round(0.09 + (liquidity_bias * 0.12), 3),
        },
        "development": {
            "minimum_cash_after_develop": round(development_buffer, 2),
            "target_roi_turns": round(6.5 - (risk_tolerance * 2.0), 3),
            "group_focus_bonus": round(0.18 + (set_focus * 0.22), 3),
            "even_build_priority": round(0.52 + rng.uniform(-0.08, 0.08), 3),
            "tax_drag_limit": round(0.42 + (liquidity_bias * 0.18), 3),
            "stability_floor": round(0.18 + (liquidity_bias * 0.10), 3),
            "rent_control_build_penalty": round(0.12 + (liquidity_bias * 0.10), 3),
            "max_build_level_without_surplus": 3 if normalized_difficulty in {"hard", "expert"} else 2,
            "sell_house_bias": round(0.62 + (liquidity_bias * 0.18), 3),
        },
        "auction": {
            "bid_increment_ratio": round(0.07 + (risk_tolerance * 0.05), 3),
            "bid_increment_min": 10.0,
            "valuation_buffer": round(0.96 + (risk_tolerance * 0.08), 3),
            "join_auction_threshold": round(0.84 + (risk_tolerance * 0.10), 3),
            "sniping_bias": round(0.32 + rng.uniform(-0.08, 0.10), 3),
            "max_competitor_persistence": round(0.38 + (risk_tolerance * 0.25), 3),
            "pass_when_below_reserve": True,
            "max_bids_per_auction": 8,
        },
        "trade": {
            "proposal_chance": round(0.18 + (risk_tolerance * 0.16), 3),
            "acceptance_margin": round(25 + (liquidity_bias * 45) - (trade_precision * 8), 2),
            "counter_margin": round(10 + (risk_tolerance * 20) - (trade_precision * 4), 2),
            "max_cash_offer_share": round(0.24 + (risk_tolerance * 0.18), 3),
            "max_cash_request_share": round(0.14 + (risk_tolerance * 0.18), 3),
            "monopoly_trade_bonus": round(115 + (risk_tolerance * 110), 2),
            "monopoly_break_penalty": round(160 + (liquidity_bias * 140) + (denial_focus * 55), 2),
            "mortgaged_property_penalty": 55.0,
            "transit_trade_bonus": round(45 + (risk_tolerance * 40), 2),
            "minimum_cash_offer": 50.0,
            "proposal_cooldown_rounds": 1,
        },
        "lobbying": {
            "enabled": government_type != "minarchism",
            "target_success_chance": round(0.42 + (lobby_focus * 0.18), 3),
            "wealthy_welfare_cut_target_success": 0.50,
            "wealthy_welfare_cut_trigger": round(48 + (risk_tolerance * 10), 2),
            "wealthy_tax_relief_trigger": round(0.26 + (liquidity_bias * 0.10), 3),
            "wealthy_tax_hike_treasury_trigger": round(1050 + (liquidity_bias * 250), 2),
            "distress_welfare_trigger": round(18 + (liquidity_bias * 12), 2),
            "distress_balance_threshold": round(350 + (liquidity_bias * 180), 2),
            "stability_alert_threshold": round(0.43 + (liquidity_bias * 0.10), 3),
            "rent_control_relief_threshold": round(0.68 + (risk_tolerance * 0.12), 3),
            "max_treasury_stimulus_threshold": round(550 + (risk_tolerance * 400), 2),
            "minimum_contribution": 50.0,
            "round_cooldown": 1,
        },
        "jail": {
            "pay_bail_cash_floor": round(reserve_floor * 0.58, 2),
            "pay_bail_after_turns_remaining": 1,
            "use_card_aggressively": True,
            "prefer_roll_if_cash_low": True,
            "max_wait_turns": 2,
        },
        "bankruptcy": {
            "liquidation_priority_houses": 1.0,
            "liquidation_priority_non_monopoly": 0.82,
            "liquidation_priority_transit": 0.58,
            "bankruptcy_buffer": 25.0,
            "declare_after_no_assets": True,
        },
    }
    return profile


def ensure_bot_profile(match_player: MatchPlayer, settings: dict | None = None) -> dict[str, Any]:
    profile = match_player.bot_profile or {}
    settings = {**DEFAULT_SETTINGS, **(settings or {})}
    existing_difficulty = normalize_bot_difficulty(
        profile.get("difficulty") or infer_legacy_difficulty(profile.get("persona"))
    )
    existing_persona = normalize_bot_personality(
        profile.get("persona"),
        difficulty=existing_difficulty,
        fallback_persona=True,
    )
    needs_refresh = (
        profile.get("strategy_version") != STRATEGY_VERSION
        or profile.get("difficulty") != existing_difficulty
        or profile.get("persona") != existing_persona
        or profile.get("government_type") != normalize_government_type(settings.get("government_type"))
        or profile.get("economic_mode") != str(settings.get("game_mode", "standard") or "standard").strip().lower()
        or not isinstance(profile.get("skill"), dict)
        or not isinstance(profile.get("regime_bias"), dict)
        or not isinstance(profile.get("difficulty_capabilities"), dict)
    )
    if needs_refresh:
        seat_index = MatchPlayer.query.filter(
            MatchPlayer.match_id == match_player.match_id,
            MatchPlayer.id <= match_player.id,
            MatchPlayer.is_bot.is_(True),
        ).count() - 1
        match_player.bot_profile = build_bot_profile(
            settings,
            difficulty=existing_difficulty,
            persona=existing_persona,
            archetype=profile.get("archetype"),
            seat_index=max(0, seat_index),
        )
        db.session.commit()
        profile = match_player.bot_profile
    return profile


def create_bot_for_lobby(
    match: Match,
    *,
    difficulty: str | None = None,
    persona: str | None = None,
    archetype: str | None = None,
) -> MatchPlayer:
    settings = {**DEFAULT_SETTINGS, **(match.settings_json or {})}
    max_players = int(settings.get("max_players", DEFAULT_SETTINGS["max_players"]))
    current_count = MatchPlayer.query.filter_by(match_id=match.id).count()
    if current_count >= max_players:
        raise ValueError("Lobby is full.")

    taken_colors = [player.color_hex for player in MatchPlayer.query.filter_by(match_id=match.id).all()]
    available_colors = get_available_player_colors(taken_colors)
    if not available_colors:
        raise ValueError("No colors available for a bot.")

    username = _generate_bot_username()
    user = User(
        username=username,
        password_hash=generate_password_hash(uuid.uuid4().hex),
    )
    db.session.add(user)
    db.session.flush()

    bot_count = MatchPlayer.query.filter_by(match_id=match.id, is_bot=True).count()
    normalized_difficulty = normalize_bot_difficulty(difficulty or "normal")
    if persona is None and archetype is None:
        normalized_persona = choose_default_personality(normalized_difficulty, seat_index=bot_count)
        normalized_archetype = infer_archetype_from_personality(normalized_persona)
    else:
        normalized_difficulty, normalized_persona, normalized_archetype = resolve_bot_configuration(
            normalized_difficulty,
            selection=persona,
            archetype=archetype,
        )
    bot_player = MatchPlayer(
        match_id=match.id,
        user_id=user.id,
        color_hex=available_colors[0],
        balance=0,
        is_ready=True,
        is_connected=True,
        is_bot=True,
        bot_profile=build_bot_profile(
            settings,
            difficulty=normalized_difficulty,
            persona=normalized_persona,
            archetype=normalized_archetype,
            seat_index=bot_count,
        ),
    )
    db.session.add(bot_player)
    db.session.commit()
    return bot_player


def remove_bot_from_lobby(match: Match, bot_player_id: int) -> MatchPlayer | None:
    bot_player = MatchPlayer.query.filter_by(match_id=match.id, id=bot_player_id, is_bot=True).first()
    if bot_player is None:
        return None

    bot_user = bot_player.user
    db.session.delete(bot_player)
    if bot_user is not None:
        db.session.delete(bot_user)
    db.session.commit()
    return bot_player


def update_bot_for_lobby(
    match: Match,
    bot_player_id: int,
    *,
    difficulty: str | None = None,
    persona: str | None = None,
    archetype: str | None = None,
) -> MatchPlayer | None:
    bot_player = MatchPlayer.query.filter_by(match_id=match.id, id=bot_player_id, is_bot=True).first()
    if bot_player is None:
        return None

    settings = {**DEFAULT_SETTINGS, **(match.settings_json or {})}
    existing_profile = dict(bot_player.bot_profile or {})
    seat_index = MatchPlayer.query.filter(
        MatchPlayer.match_id == match.id,
        MatchPlayer.id <= bot_player.id,
        MatchPlayer.is_bot.is_(True),
    ).count() - 1

    requested_difficulty = normalize_bot_difficulty(
        difficulty or existing_profile.get("difficulty") or infer_legacy_difficulty(existing_profile.get("persona"))
    )
    requested_persona = persona or existing_profile.get("persona")
    requested_archetype = archetype or existing_profile.get("archetype")
    if requested_persona is None and requested_archetype is None:
        requested_persona = choose_default_personality(requested_difficulty, seat_index=max(0, seat_index))
        requested_archetype = infer_archetype_from_personality(requested_persona)

    requested_difficulty, requested_persona, requested_archetype = resolve_bot_configuration(
        requested_difficulty,
        selection=requested_persona,
        archetype=requested_archetype,
    )
    bot_player.bot_profile = build_bot_profile(
        settings,
        difficulty=requested_difficulty,
        persona=requested_persona,
        archetype=requested_archetype,
        seat_index=max(0, seat_index),
    )
    db.session.commit()
    return bot_player


def _queue_bot_state_evaluation(
    match_id: int,
    game_state: dict | None = None,
    reason: str = "state_update",
    *,
    replace_existing: bool = True,
) -> None:
    game_state = game_state or load_game_state(match_id, redis_client)
    if not game_state or game_state.get("status") != "active" or game_state.get("game_paused"):
        return
    auction_active = has_active_auction(match_id)

    bot_ids = [player["id"] for player in game_state.get("players", []) if player.get("is_bot") and not player.get("is_bankrupt")]
    if not bot_ids:
        return

    pending_action = game_state.get("pending_action") or {}
    if pending_action.get("type") in {"buy_property", "buy_corporate_property"} and pending_action.get("player_id") in bot_ids:
        _schedule_player_task(
            match_id,
            pending_action["player_id"],
            "property_decision",
            reason,
            replace_existing=replace_existing,
        )

    awaiting_id = game_state.get("awaiting_end_turn_player_id")
    if awaiting_id in bot_ids and not auction_active:
        _schedule_player_task(
            match_id,
            awaiting_id,
            "manage_turn",
            reason,
            replace_existing=replace_existing,
        )
    else:
        current_player_id = game_state.get("current_player_id")
        if current_player_id in bot_ids and not game_state.get("dice_rolled_this_turn", False) and not auction_active:
            _schedule_player_task(
                match_id,
                current_player_id,
                "take_turn",
                reason,
                replace_existing=replace_existing,
            )

    settings = game_state.get("settings", {})
    queue_bot_trade_responses(match_id, settings=settings, replace_existing=replace_existing)
    queue_bot_deal_responses(match_id, settings=settings, replace_existing=replace_existing)
    queue_bot_auction_reactions(match_id, game_state=game_state, settings=settings, reason=reason, replace_existing=replace_existing)


def _bot_state_evaluation_key(match_id: int) -> str:
    return f"game:{match_id}:bot_state_evaluation:pending"


def _run_debounced_state_evaluation(app_obj, redis_key: str, token: str, match_id: int, reason: str) -> None:
    socketio.sleep(BOT_STATE_EVALUATION_DEBOUNCE_SECONDS)

    with app_obj.app_context():
        if redis_client.get(redis_key) != token:
            return
        redis_client.delete(redis_key)
        _queue_bot_state_evaluation(match_id, None, reason, replace_existing=True)


def queue_bot_state_evaluation(match_id: int, game_state: dict | None = None, reason: str = "state_update") -> None:
    active_state = game_state or load_game_state(match_id, redis_client)
    if not active_state or active_state.get("status") != "active" or active_state.get("game_paused"):
        return

    redis_key = _bot_state_evaluation_key(match_id)
    if redis_client.get(redis_key):
        return

    token = uuid.uuid4().hex
    redis_client.set(redis_key, token, ex=BOT_STATE_EVALUATION_TTL_SECONDS)
    app_obj = current_app._get_current_object()
    socketio.start_background_task(
        _run_debounced_state_evaluation,
        app_obj,
        redis_key,
        token,
        match_id,
        reason,
    )


def recover_bot_state_evaluation(match_id: int, game_state: dict | None = None, reason: str = "state_recovery") -> None:
    _queue_bot_state_evaluation(match_id, game_state, reason, replace_existing=False)


def queue_bot_trade_responses(match_id: int, *, settings: dict | None = None, replace_existing: bool = True) -> None:
    if has_active_auction(match_id):
        return

    pending_trades = (
        Trade.query.filter_by(match_id=match_id, status="pending")
        .order_by(Trade.created_at.asc(), Trade.id.asc())
        .all()
    )
    for trade in pending_trades:
        receiver = MatchPlayer.query.get(trade.receiver_id)
        if receiver and receiver.is_bot and not receiver.is_bankrupt:
            _schedule_player_task(
                match_id,
                receiver.id,
                f"trade_response:{trade.id}",
                "trade_response",
                match_player=receiver,
                settings=settings,
                replace_existing=replace_existing,
            )


def queue_bot_deal_responses(match_id: int, *, settings: dict | None = None, replace_existing: bool = True) -> None:
    try:
        pending_deals = (
            Deal.query.filter_by(match_id=match_id, status="proposed")
            .order_by(Deal.created_at.asc(), Deal.id.asc())
            .all()
        )
    except (OperationalError, ProgrammingError):
        db.session.rollback()
        return
    for deal in pending_deals:
        receiver = MatchPlayer.query.get(deal.counterparty_id)
        if receiver and receiver.is_bot and not receiver.is_bankrupt:
            _schedule_player_task(
                match_id,
                receiver.id,
                f"deal_response:{deal.id}",
                "deal_response",
                match_player=receiver,
                settings=settings,
                replace_existing=replace_existing,
            )


def queue_bot_auction_reactions(
    match_id: int,
    game_state: dict | None = None,
    settings: dict | None = None,
    reason: str = "auction",
    *,
    replace_existing: bool = True,
) -> None:
    game_state = game_state or load_game_state(match_id, redis_client)
    if not game_state or game_state.get("status") != "active":
        return

    for prop_id in _get_active_auction_property_ids(match_id):
        prop = next((entry for entry in game_state.get("properties", []) if entry.get("id") == prop_id), None)
        if prop is None:
            continue

        current_bid = float(redis_client.get(f"game:{match_id}:auction:{prop_id}:current_bid") or 0)
        current_bidder_raw = redis_client.get(f"game:{match_id}:auction:{prop_id}:current_bidder")
        current_bidder = int(current_bidder_raw) if current_bidder_raw and str(current_bidder_raw).isdigit() else None

        for player in game_state.get("players", []):
            if not player.get("is_bot") or player.get("is_bankrupt") or player.get("id") == current_bidder:
                continue

            record = MatchPlayer.query.get(player["id"])
            if record is None:
                continue
            profile = ensure_bot_profile(record, game_state.get("settings", {}))
            if choose_auction_bid_amount(player, prop, current_bid, game_state, profile) is None:
                continue
            _schedule_player_task(
                match_id,
                player["id"],
                f"auction_bid:{prop_id}",
                reason,
                match_player=record,
                profile=profile,
                settings=settings,
                replace_existing=replace_existing,
            )


def _find_player(game_state: dict, player_id: int | None) -> dict[str, Any] | None:
    if player_id is None:
        return None
    return next((entry for entry in game_state.get("players", []) if entry.get("id") == player_id), None)


def _find_property(game_state: dict, property_id: int | None) -> dict[str, Any] | None:
    if property_id is None:
        return None
    return next((entry for entry in game_state.get("properties", []) if entry.get("id") == property_id), None)


def _coerce_player_owner_id(owner_id: Any) -> int | None:
    try:
        normalized = int(owner_id)
    except (TypeError, ValueError):
        return None
    return normalized if normalized > 0 else None


def _property_owned_by_player(prop: dict[str, Any] | None, owner_id: int | None) -> bool:
    if prop is None:
        return False
    normalized_owner_id = _coerce_player_owner_id(prop.get("owner_id"))
    normalized_player_id = _coerce_player_owner_id(owner_id)
    return normalized_owner_id is not None and normalized_owner_id == normalized_player_id


def _deal_scope_matches_property(scope: dict | None, prop: dict | None, owner_id: int) -> bool:
    if not _property_owned_by_player(prop, owner_id):
        return False

    scope = scope or {}
    mode = str(scope.get("mode") or "all_grantor_properties")
    if mode == "all_grantor_properties":
        return True
    if mode == "selected_group_colors":
        return prop.get("group_color") in set(scope.get("group_colors") or [])
    if mode == "selected_property_ids":
        return int(prop.get("id") or 0) in {int(value) for value in (scope.get("property_ids") or [])}
    return False


def _estimate_owner_rent_threat(owner_id: int, game_state: dict) -> float:
    normalized_owner_id = _coerce_player_owner_id(owner_id)
    if normalized_owner_id is None:
        return 0.0

    econ = game_state.get("econ", {})
    rents = []
    for prop in game_state.get("properties", []):
        if not _property_owned_by_player(prop, normalized_owner_id) or prop.get("is_mortgaged"):
            continue
        if prop.get("property_type") == "transit":
            rent = calculate_transit_rent(normalized_owner_id, game_state)
        else:
            rent = calculate_rent_with_dev(prop, econ, game_state)
        if rent > 0:
            rents.append(float(rent))

    if not rents:
        return 0.0
    rents.sort(reverse=True)
    sample = rents[:3]
    return round(sum(sample) / max(1, len(sample)), 2)


def _pairwise_deal_context(player_id: int, other_id: int, game_state: dict) -> dict[str, Any]:
    active_deal_count = 0
    pending_outgoing = 0
    pending_incoming = 0
    incoming_protection = 0.0
    outgoing_obligation = 0.0
    investment_support = 0.0
    investment_obligation = 0.0
    protective_ties = 0

    for deal in game_state.get("deals") or []:
        participants = {int(deal.get("proposer_id") or 0), int(deal.get("counterparty_id") or 0)}
        if participants != {int(player_id or 0), int(other_id or 0)}:
            continue

        status = str(deal.get("status") or "")
        if status == "proposed":
            if int(deal.get("counterparty_id") or 0) == int(player_id or 0):
                pending_incoming += 1
            if int(deal.get("proposer_id") or 0) == int(player_id or 0):
                pending_outgoing += 1

        if status != "accepted":
            continue

        active_deal_count += 1
        for clause in deal.get("clauses") or []:
            if clause.get("status") != "active":
                continue
            deadline = clause.get("deadline") or {}
            uses = max(1, int(deadline.get("remaining", deadline.get("initial", 1)) or 1))
            clause_type = clause.get("type")
            if clause_type == "rent_immunity":
                threat_value = _estimate_owner_rent_threat(int(clause.get("grantor_id") or 0), game_state)
                if int(clause.get("beneficiary_id") or 0) == int(player_id or 0):
                    incoming_protection += threat_value * uses
                    protective_ties += 1
                elif int(clause.get("grantor_id") or 0) == int(player_id or 0):
                    outgoing_obligation += threat_value * uses
                    protective_ties += 1
            elif clause_type == "rent_discount":
                threat_value = _estimate_owner_rent_threat(int(clause.get("grantor_id") or 0), game_state)
                concession = threat_value * max(0.0, 1.0 - float((clause.get("config") or {}).get("rent_multiplier", 1) or 1)) * uses
                if int(clause.get("beneficiary_id") or 0) == int(player_id or 0):
                    incoming_protection += concession
                    protective_ties += 1
                elif int(clause.get("grantor_id") or 0) == int(player_id or 0):
                    outgoing_obligation += concession
                    protective_ties += 1
            elif clause_type == "development_investment":
                config = clause.get("config") or {}
                escrow_remaining = float(config.get("escrow_remaining", config.get("escrow_amount", 0)) or 0)
                max_payout = float(config.get("max_payout", 0) or 0)
                payout_to_date = float(config.get("payout_to_date", 0) or 0)
                remaining_payout = max(0.0, max_payout - payout_to_date)
                if int(clause.get("beneficiary_id") or 0) == int(player_id or 0):
                    investment_support += escrow_remaining
                    investment_obligation += remaining_payout
                elif int(clause.get("grantor_id") or 0) == int(player_id or 0):
                    outgoing_obligation += max(0.0, escrow_remaining * 0.55)

    return {
        "active_deal_count": active_deal_count,
        "pending_incoming": pending_incoming,
        "pending_outgoing": pending_outgoing,
        "incoming_protection": round(incoming_protection, 2),
        "outgoing_obligation": round(outgoing_obligation, 2),
        "investment_support": round(investment_support, 2),
        "investment_obligation": round(investment_obligation, 2),
        "protective_ties": protective_ties,
    }


def build_deal_summary(player: dict, game_state: dict, profile: dict[str, Any] | None = None) -> dict[str, Any]:
    player_id = int(player.get("id") or 0)
    balance = float(player.get("balance", 0) or 0)
    reserve_floor = float((profile or {}).get("liquidity", {}).get("reserve_cash_floor", 250) or 250)
    active_deal_count = 0
    pending_incoming_count = 0
    pending_outgoing_count = 0
    incoming_protection_value = 0.0
    outgoing_obligation_value = 0.0
    investment_support_value = 0.0
    investment_obligation_value = 0.0

    for other in game_state.get("players", []):
        other_id = int(other.get("id") or 0)
        if other_id <= 0 or other_id == player_id or other.get("is_bankrupt"):
            continue
        context = _pairwise_deal_context(player_id, other_id, game_state)
        active_deal_count += context["active_deal_count"]
        pending_incoming_count += context["pending_incoming"]
        pending_outgoing_count += context["pending_outgoing"]
        incoming_protection_value += context["incoming_protection"]
        outgoing_obligation_value += context["outgoing_obligation"]
        investment_support_value += context["investment_support"]
        investment_obligation_value += context["investment_obligation"]

    threat_pressure = max(
        (_estimate_owner_rent_threat(int(other.get("id") or 0), game_state) for other in game_state.get("players", []) if int(other.get("id") or 0) != player_id and not other.get("is_bankrupt")),
        default=0.0,
    )
    immunity_need_score = min(1.0, max(0.0, threat_pressure - incoming_protection_value * 0.35) / max(80.0, reserve_floor * 0.9))
    investment_opportunity_score = 0.0
    if balance < reserve_floor * 1.25 and any(
        prop.get("property_type") == "property" and has_full_monopoly(prop, game_state) and _property_owned_by_player(prop, player_id)
        for prop in game_state.get("properties", [])
    ):
        investment_opportunity_score = min(1.0, (reserve_floor * 1.25 - balance) / max(120.0, reserve_floor))
    active_deal_burden = min(
        1.0,
        (active_deal_count * 0.18)
        + (outgoing_obligation_value + investment_obligation_value) / max(250.0, reserve_floor * 1.6),
    )
    deal_pressure_score = round(
        min(
            1.0,
            (immunity_need_score * 0.55)
            + (active_deal_burden * 0.3)
            + min(0.15, pending_incoming_count * 0.08)
            + min(0.2, pending_outgoing_count * 0.05),
        ),
        4,
    )

    return {
        "active_deal_count": active_deal_count,
        "pending_incoming_count": pending_incoming_count,
        "pending_outgoing_count": pending_outgoing_count,
        "incoming_protection_value": round(incoming_protection_value, 2),
        "outgoing_obligation_value": round(outgoing_obligation_value, 2),
        "investment_support_value": round(investment_support_value, 2),
        "investment_obligation_value": round(investment_obligation_value, 2),
        "deal_pressure_score": deal_pressure_score,
        "immunity_need_score": round(immunity_need_score, 4),
        "investment_opportunity_score": round(investment_opportunity_score, 4),
        "active_deal_burden": round(active_deal_burden, 4),
    }


def _players_are_allied(player: dict, other: dict | None, game_state: dict) -> bool:
    if other is None:
        return False
    mode = str(game_state.get("settings", {}).get("game_mode", "standard") or "standard").strip().lower()
    context = _pairwise_deal_context(int(player.get("id") or 0), int(other.get("id") or 0), game_state)
    if context["protective_ties"] > 0:
        return True
    return mode == "cooperative" and context["active_deal_count"] > 0


def _player_has_engine_assets(player_id: int, game_state: dict) -> bool:
    for prop in get_player_properties(player_id, game_state):
        if prop.get("property_type") == "property" and has_full_monopoly(prop, game_state):
            return True
    return False


def _player_social_entries(player: dict, game_state: dict) -> list[dict[str, Any]]:
    social_props = (game_state.get("social") or {}).get("properties") or {}
    relevant_entries = []
    for prop in game_state.get("properties", []):
        social_entry = social_props.get(str(prop.get("id")))
        if not social_entry:
            continue
        if prop.get("owner_id") == player.get("id") or social_entry.get("former_owner_id") == player.get("id"):
            relevant_entries.append({**dict(social_entry), "property_name": prop.get("name"), "current_owner_id": prop.get("owner_id")})
    return relevant_entries


def _social_lobby_target(entry: dict) -> str | None:
    dominant_grievance = entry.get("dominant_grievance") or ""
    targets = GRIEVANCE_POLICY_TARGETS.get(dominant_grievance, [])
    if not targets:
        return None
    return sorted(targets, key=lambda key: SOCIAL_TARGET_PRIORITY.get(key, 99))[0]


def _social_pressure_summary(player: dict, game_state: dict) -> dict[str, Any]:
    social = game_state.get("social") or {}
    player_entries = _player_social_entries(player, game_state)
    directly_owned_entries = [entry for entry in player_entries if entry.get("current_owner_id") == player.get("id")]
    threatened_entries = [entry for entry in player_entries if float(entry.get("tension", 0) or 0) >= 50.0]
    incident_entries = [entry for entry in player_entries if entry.get("incident_type")]
    unionized_entries = [entry for entry in player_entries if entry.get("former_owner_id") is not None]
    max_tension = max((float(entry.get("tension", 0) or 0) for entry in directly_owned_entries), default=0.0)
    avg_tension = sum(float(entry.get("tension", 0) or 0) for entry in player_entries) / max(1, len(player_entries))
    owned_regions = {
        entry.get("region")
        for entry in player_entries
        if entry.get("region")
    }
    neighboring_properties = 0
    neighboring_unionized = 0
    regional_contagion_candidates = []
    for entry in (social.get("properties") or {}).values():
        region = entry.get("region")
        if region not in owned_regions:
            continue
        if entry.get("owner_id") == player.get("id") or entry.get("former_owner_id") == player.get("id"):
            continue
        neighboring_properties += 1
        if entry.get("former_owner_id") is not None:
            neighboring_unionized += 1
        if entry.get("incident_type"):
            regional_contagion_candidates.append({**dict(entry), "current_owner_id": entry.get("owner_id")})

    contagion_risk = min(1.0, neighboring_unionized / max(1, neighboring_properties)) if neighboring_properties else 0.0
    top_incident = next(
        iter(
            sorted(
                incident_entries,
                key=lambda entry: (
                    1 if entry.get("former_owner_id") == player.get("id") else 0,
                    float(entry.get("tension", 0) or 0),
                    float(entry.get("negotiation_target", 0) or 0),
                ),
                reverse=True,
            )
        ),
        None,
    )
    flashpoint = next(
        iter(sorted(player_entries, key=lambda entry: float(entry.get("tension", 0) or 0), reverse=True)),
        None,
    )
    owned_territory_instability_max = max(
        (
            float(entry.get("territory_instability", 0) or 0)
            for entry in (social.get("territories") or [])
            if entry.get("owner_id") == player.get("id")
        ),
        default=0.0,
    )
    preferred_lobby_target = _social_lobby_target(top_incident or flashpoint or {})
    overall_rage = float(social.get("overall_rage", 0) or 0)
    stability = float((game_state.get("econ") or {}).get("stability", 0.7) or 0.7)
    macro_risk = (overall_rage / 100.0) * 0.6 + ((1.0 - stability) * 0.4)
    civil_risk_score = max(
        0.0,
        min(
            1.0,
            max_tension / 100.0,
            min(1.0, len(unionized_entries) * 0.35),
            owned_territory_instability_max / 100.0,
            macro_risk,
            contagion_risk,
        ),
    )
    return {
        "owned_property_count": len(player_entries),
        "threatened_property_count": len(threatened_entries),
        "incident_count": len(incident_entries),
        "unionized_property_count": len(unionized_entries),
        "highest_owned_property_tension": round(max_tension, 2),
        "owned_unionized_property_count": len(unionized_entries),
        "owned_territory_instability_max": round(owned_territory_instability_max, 2),
        "global_revolt_risk": round(overall_rage / 100.0, 4),
        "contagion_risk": round(contagion_risk, 4),
        "max_tension": round(max_tension, 2),
        "average_tension": round(avg_tension, 2),
        "contagion_exposure": neighboring_unionized,
        "civil_risk_score": round(civil_risk_score, 4),
        "top_incident": top_incident,
        "flashpoint": flashpoint,
        "regional_contagion_candidate": next(
            iter(
                sorted(
                    regional_contagion_candidates,
                    key=lambda entry: (
                        float(entry.get("tension", 0) or 0),
                        1 if entry.get("incident_type") == "revolution" else 0,
                    ),
                    reverse=True,
                )
            ),
            None,
        ),
        "preferred_lobby_target": preferred_lobby_target,
    }


def build_regime_summary(player: dict, game_state: dict, profile: dict[str, Any]) -> dict[str, Any]:
    settings = game_state.get("settings", {})
    econ = game_state.get("econ", {})
    difficulty = normalize_bot_difficulty(
        profile.get("difficulty") or infer_legacy_difficulty(profile.get("persona"))
    )
    capabilities = dict(
        profile.get("difficulty_capabilities")
        or get_difficulty_metadata(difficulty)["allowed_capabilities"]
    )
    skill = dict(profile.get("skill") or {})
    regime_bias = dict(profile.get("regime_bias") or {})
    government_type = normalize_government_type(
        econ.get("gov_type")
        or econ.get("government_type")
        or settings.get("government_type")
        or profile.get("government_type")
    )
    game_mode = normalize_game_mode(
        settings.get("game_mode")
        or profile.get("economic_mode")
        or "standard"
    )
    actual_cash = round(float(player.get("balance", 0) or 0), 2)
    pending_debt = round(float(get_total_pending_player_debt(game_state, player["id"]) or 0), 2)
    balance_shortfall = round(max(0.0, -actual_cash) + pending_debt, 2)
    expected_bailout_amount = round(max(0.0, balance_shortfall + 200.0), 2)
    treasury_balance = round(float(econ.get("treasury_balance", 0) or 0), 2)
    bailout_enabled = bool(econ.get("bailout_enabled", False))
    welfare_rate = round(float(econ.get("welfare_payout", 0) or 0), 2)
    tax_multiplier = round(float(econ.get("tax_multiplier", 0) or 0), 4)
    stability = round(float(econ.get("stability", 0.7) or 0.7), 4)
    inflation_rate = round(float(econ.get("inflation_rate", 0) or 0), 4)
    free_parking_claim = round(float(game_state.get("free_parking_pot", 0) or 0), 2)
    reserve_floor = round(float(profile.get("liquidity", {}).get("reserve_cash_floor", 250) or 250), 2)
    emergency_floor = round(float(profile.get("liquidity", {}).get("emergency_cash_floor", reserve_floor * 0.72) or reserve_floor * 0.72), 2)
    market_confidence = round(float(econ.get("market_confidence", 0) or 0), 2)
    capital_yield_rate = round(float(econ.get("capital_yield_rate", 0) or 0), 4)
    capital_yield_reserve_floor = round(float(econ.get("capital_yield_reserve_floor", reserve_floor) or reserve_floor), 2)
    private_equity_bonus_multiplier = round(float(econ.get("private_equity_bonus_multiplier", 1.0) or 1.0), 4)
    welfare_cap = round(float(settings.get("welfare_balance_cap", 0) or 0), 2)
    welfare_target_balance = 400.0 if welfare_cap <= 0 else welfare_cap + 200.0
    welfare_gap = max(0.0, welfare_target_balance - max(actual_cash, 0.0))
    expected_welfare_recovery = 0.0
    if capabilities.get("welfare_abuse"):
        expected_welfare_recovery = round(welfare_gap * (welfare_rate / 100.0), 2)

    treasury_cover_ratio = 1.5 if expected_bailout_amount <= 0 else min(1.5, treasury_balance / expected_bailout_amount)
    expected_bailout_capacity = 0.0
    if bailout_enabled and capabilities.get("bailout_abuse"):
        expected_bailout_capacity = round(expected_bailout_amount * min(1.0, treasury_cover_ratio), 2)

    government_baseline = {
        "minarchism": 0.02,
        "liberal_democracy": 0.26,
        "social_democracy": 0.42,
    }.get(government_type, 0.24)
    treasury_component = min(0.18, max(0.0, treasury_balance / 1800.0) * 0.18)
    bailout_component = 0.0
    if bailout_enabled:
        bailout_component = min(0.34, max(0.0, treasury_cover_ratio - 0.2) * 0.28)
        if not capabilities.get("bailout_abuse"):
            bailout_component *= 0.3
    welfare_component = 0.0
    if capabilities.get("welfare_abuse"):
        welfare_component = min(0.22, (welfare_rate / 100.0) * 0.22)
    execution_component = min(
        0.16,
        float(skill.get("leverage_confidence", 0.2) or 0.2) * 0.18,
    )
    state_protection_score = round(
        max(
            0.0,
            min(
                1.0,
                government_baseline
                + treasury_component
                + bailout_component
                + welfare_component
                + execution_component,
            ),
        ),
        4,
    )

    welfare_reliance_score = 0.0
    if capabilities.get("welfare_abuse"):
        welfare_reliance_score = round(
            min(1.0, expected_welfare_recovery / max(1.0, reserve_floor)),
            4,
        )

    bailout_reliance_score = 0.0
    if capabilities.get("bailout_abuse"):
        bailout_reliance_score = round(
            min(1.0, expected_bailout_capacity / max(1.0, reserve_floor * 1.1)),
            4,
        )

    cash_buffer_discount = float(regime_bias.get("cash_buffer_discount", 0.2) or 0.2)
    soft_reserve = round(
        max(
            emergency_floor * 0.4,
            reserve_floor * (1.0 - (state_protection_score * cash_buffer_discount)),
        ),
        2,
    )
    state_backed_credit = round(
        expected_bailout_capacity
        * min(0.78, 0.24 + float(skill.get("leverage_confidence", 0.2) or 0.2) * 0.58),
        2,
    )
    welfare_recovery_credit = round(
        expected_welfare_recovery
        * min(1.0, 0.42 + float(skill.get("trade_precision", 0.5) or 0.5) * 0.36),
        2,
    )
    effective_cash = round(actual_cash - soft_reserve + state_backed_credit + welfare_recovery_credit, 2)

    allowed_negative_exposure = 0.0
    if capabilities.get("negative_exposure") and government_type == "social_democracy":
        leverage_room = max(0.0, (state_protection_score - 0.45) * 520.0)
        allowed_negative_exposure = round(
            min(
                320.0,
                leverage_room * max(0.35, bailout_reliance_score + welfare_reliance_score * 0.6),
            ),
            2,
        )
        if not bailout_enabled or treasury_cover_ratio < 1.05:
            allowed_negative_exposure = 0.0

    chaos_penalty = 0.08 if game_mode == "chaos" else 0.0
    macro_stress_score = round(
        min(
            1.0,
            max(
                0.0,
                (tax_multiplier * 0.45)
                + ((1.0 - stability) * 0.4)
                + min(0.2, inflation_rate * 2.6)
                + chaos_penalty,
            ),
        ),
        4,
    )
    rescue_viable = bool(
        bailout_enabled
        and expected_bailout_amount > 0
        and treasury_balance >= expected_bailout_amount * 1.15
    )
    social_summary = _social_pressure_summary(player, game_state)
    buildable_property_count = sum(
        1
        for prop in get_player_properties(player["id"], game_state)
        if prop.get("property_type") == "property"
        and not prop.get("is_mortgaged")
        and has_full_monopoly(prop, game_state)
        and not property_is_fully_developed(prop, game_state)
        and not property_private_actions_locked(game_state, prop.get("id"))
    )
    deal_summary = build_deal_summary(player, game_state, profile)
    liquid_capital_above_yield_floor = 0.0
    capital_yield_capture_score = 0.0
    private_equity_edge_score = 0.0
    market_overheat_score = 0.0
    if government_type == "liberal_democracy":
        confidence_norm = _clamp((market_confidence - 50.0) / 40.0, 0.0, 1.0)
        yield_norm = _clamp(capital_yield_rate / LIBERAL_DEMOCRACY_MAX_CAPITAL_YIELD_RATE, 0.0, 1.0)
        private_equity_norm = _clamp((private_equity_bonus_multiplier - 1.0) / 0.25, 0.0, 1.0)
        liquid_capital_above_yield_floor = round(
            max(0.0, actual_cash - max(capital_yield_reserve_floor, soft_reserve)),
            2,
        )
        capital_yield_capture_score = round(
            min(
                1.0,
                (liquid_capital_above_yield_floor / max(250.0, reserve_floor * 1.2))
                * (0.55 + (confidence_norm * 0.45))
                * (0.50 + (yield_norm * 0.50)),
            ),
            4,
        )
        private_equity_edge_score = round(
            min(
                1.0,
                (min(1.0, buildable_property_count / 2.0) * 0.5)
                + (private_equity_norm * 0.35)
                + (confidence_norm * 0.15),
            ),
            4,
        )
        market_overheat_score = round(
            min(
                1.0,
                (float(social_summary.get("civil_risk_score", 0) or 0) * 0.40)
                + (private_equity_norm * 0.18)
                + (yield_norm * 0.18)
                + (max(0.0, confidence_norm - 0.45) * 0.24)
                + (max(0.0, inflation_rate - 0.035) * 2.5),
            ),
            4,
        )

    if actual_cash >= reserve_floor and effective_cash >= 0:
        distress_state = "stable"
    elif actual_cash >= 0 and effective_cash >= -25:
        distress_state = "tight"
    elif actual_cash >= -allowed_negative_exposure:
        distress_state = "leveraged"
    elif rescue_viable and effective_cash >= (-allowed_negative_exposure - 80):
        distress_state = "recoverable_distress"
    else:
        distress_state = "terminal_distress"

    return {
        "difficulty": difficulty,
        "persona": profile.get("persona"),
        "government_type": government_type,
        "game_mode": game_mode,
        "bailout_enabled": bailout_enabled,
        "welfare_rate": welfare_rate,
        "tax_multiplier": tax_multiplier,
        "treasury_balance": treasury_balance,
        "free_parking_claim": free_parking_claim,
        "stability": stability,
        "rent_control_active": bool(econ.get("rent_control_active", False)),
        "inflation_rate": inflation_rate,
        "market_confidence": market_confidence,
        "capital_yield_rate": capital_yield_rate,
        "capital_yield_reserve_floor": capital_yield_reserve_floor,
        "private_equity_bonus_multiplier": private_equity_bonus_multiplier,
        "actual_cash": actual_cash,
        "net_worth": round(float(calculate_net_worth(player, game_state) or 0), 2),
        "pending_debt": pending_debt,
        "expected_bailout_amount": expected_bailout_amount,
        "expected_bailout_capacity": expected_bailout_capacity,
        "expected_welfare_recovery": expected_welfare_recovery,
        "state_protection_score": state_protection_score,
        "welfare_reliance_score": welfare_reliance_score,
        "bailout_reliance_score": bailout_reliance_score,
        "effective_cash": effective_cash,
        "soft_reserve": soft_reserve,
        "state_backed_credit": state_backed_credit,
        "welfare_recovery_credit": welfare_recovery_credit,
        "allowed_negative_exposure": allowed_negative_exposure,
        "macro_stress_score": macro_stress_score,
        "overall_rage": round(float((game_state.get("social") or {}).get("overall_rage", game_state.get("rage", 0)) or 0), 2),
        "social_civil_risk_score": social_summary["civil_risk_score"],
        "social_summary": social_summary,
        "buildable_property_count": buildable_property_count,
        "liquid_capital_above_yield_floor": liquid_capital_above_yield_floor,
        "capital_yield_capture_score": capital_yield_capture_score,
        "private_equity_edge_score": private_equity_edge_score,
        "market_overheat_score": market_overheat_score,
        "active_deal_count": deal_summary["active_deal_count"],
        "pending_deal_incoming_count": deal_summary["pending_incoming_count"],
        "pending_deal_outgoing_count": deal_summary["pending_outgoing_count"],
        "incoming_deal_protection_value": deal_summary["incoming_protection_value"],
        "outgoing_deal_obligation_value": deal_summary["outgoing_obligation_value"],
        "deal_pressure_score": deal_summary["deal_pressure_score"],
        "immunity_need_score": deal_summary["immunity_need_score"],
        "investment_opportunity_score": deal_summary["investment_opportunity_score"],
        "active_deal_burden": deal_summary["active_deal_burden"],
        "distress_state": distress_state,
        "rescue_viable": rescue_viable,
        "treasury_cover_ratio": round(treasury_cover_ratio, 4),
        "capabilities": capabilities,
    }


def choose_bot_doctrine(player: dict, game_state: dict, profile: dict[str, Any], regime: dict[str, Any] | None = None) -> str:
    regime = regime or build_regime_summary(player, game_state, profile)
    personality_meta = get_personality_metadata(profile.get("persona"))
    preferred = list(profile.get("doctrine_preferences") or personality_meta["preferred_doctrines"])
    difficulty = regime["difficulty"]
    game_mode = regime["game_mode"]
    has_engine_assets = _player_has_engine_assets(player["id"], game_state)

    if regime["distress_state"] in {"recoverable_distress", "terminal_distress"}:
        return "distress_recovery"

    if game_mode == "speed":
        if has_engine_assets or float(profile.get("core", {}).get("set_focus", 0.5) or 0.5) >= 0.6:
            return "monopoly_rush"
        return preferred[0]

    if game_mode == "chaos" and regime["macro_stress_score"] >= 0.55:
        if difficulty in {"hard", "expert"} and "policy_shaping" in preferred:
            return "policy_shaping"
        return "liquidity_preservation"

    if regime["government_type"] == "social_democracy" and difficulty in {"hard", "expert"}:
        if not regime["bailout_enabled"]:
            return "policy_shaping"
        if regime["treasury_balance"] < regime["expected_bailout_amount"] * 1.3:
            return "treasury_rebuild_then_leverage"
        if regime["rescue_viable"] and has_engine_assets:
            return "social_democracy_leverage"

    if regime["government_type"] == "liberal_democracy":
        if regime.get("market_overheat_score", 0) >= 0.62:
            if difficulty in {"hard", "expert"} and "policy_shaping" in preferred:
                return "policy_shaping"
            return "liquidity_preservation"
        if regime.get("private_equity_edge_score", 0) >= 0.46 and regime["investment_opportunity_score"] >= 0.28:
            return "capital_markets_arbitrage"
        if regime.get("capital_yield_capture_score", 0) >= 0.38 and not has_engine_assets:
            return "capital_markets_arbitrage"

    if regime["immunity_need_score"] >= 0.64:
        return "liquidity_preservation"

    if regime["investment_opportunity_score"] >= 0.52 and not has_engine_assets:
        if "policy_shaping" in preferred and difficulty in {"hard", "expert"}:
            return "policy_shaping"
        return "development_snowball"

    if game_mode == "cooperative" and regime["active_deal_count"] > 0:
        if "policy_shaping" in preferred:
            return "policy_shaping"
        return "development_snowball"

    if has_engine_assets and float(profile.get("core", {}).get("development_focus", 0.5) or 0.5) >= 0.62:
        return "development_snowball"

    if float(profile.get("core", {}).get("set_focus", 0.5) or 0.5) >= 0.68:
        return "monopoly_rush"

    return preferred[0]


def choose_property_purchase(player: dict, prop: dict, game_state: dict, profile: dict[str, Any]) -> dict[str, Any]:
    regime = build_regime_summary(player, game_state, profile)
    doctrine = choose_bot_doctrine(player, game_state, profile, regime)
    value = estimate_property_value(player, prop, game_state, profile)
    price = float(prop.get("current_value") or prop.get("base_price") or 0)
    balance = float(player.get("balance", 0) or 0)
    liquidity = profile["liquidity"]
    reserve = max(0.0, float(regime["soft_reserve"]))
    post_purchase = balance - price
    post_purchase_effective = regime["effective_cash"] - price
    completion = monopoly_completion_ratio(player["id"], prop, game_state)
    force_buy_margin = float(profile["acquisition"]["force_buy_monopoly_margin"])
    buy_value_margin = float(profile["acquisition"]["buy_value_margin"])
    purchase_reserve = reserve
    if regime["government_type"] == "liberal_democracy":
        purchase_reserve = max(reserve, float(regime.get("capital_yield_reserve_floor", reserve) or reserve))
        if doctrine == "capital_markets_arbitrage" and completion < 1.0:
            buy_value_margin += 0.08 + (float(regime.get("capital_yield_capture_score", 0) or 0) * 0.06)

    if balance < price:
        return {
            "decision": "decline",
            "score": round(value - price, 2),
            "reason": "insufficient_cash",
            "doctrine": doctrine,
        }

    forced_buy = (
        completion >= 1.0
        and post_purchase >= (float(liquidity["post_monopoly_cash_floor"]) - regime["allowed_negative_exposure"])
    )
    conservative_buy = value >= price * buy_value_margin and post_purchase >= purchase_reserve
    leverage_buy = (
        doctrine in {"social_democracy_leverage", "development_snowball", "monopoly_rush"}
        and post_purchase_effective >= -regime["allowed_negative_exposure"]
        and value >= price * (buy_value_margin - 0.08)
    )
    if forced_buy and value >= price * force_buy_margin:
        return {
            "decision": "buy",
            "score": round(value - price, 2),
            "reason": "monopoly_completion",
            "doctrine": doctrine,
        }
    if conservative_buy or leverage_buy:
        return {
            "decision": "buy",
            "score": round(value - price, 2),
            "reason": "positive_expected_value" if conservative_buy else "state_backed_leverage",
            "doctrine": doctrine,
        }
    return {
        "decision": "decline",
        "score": round(value - price, 2),
        "reason": "liquidity_or_value",
        "doctrine": doctrine,
    }


def choose_auction_bid_amount(
    player: dict,
    prop: dict,
    current_bid: float,
    game_state: dict,
    profile: dict[str, Any],
) -> float | None:
    value = estimate_property_value(player, prop, game_state, profile)
    balance = float(player.get("balance", 0) or 0)
    liquidity = profile["liquidity"]
    max_cash = balance * float(liquidity["max_auction_share"])
    reserve_floor = float(liquidity["reserve_cash_floor"])
    if balance - current_bid <= reserve_floor and profile["auction"]["pass_when_below_reserve"]:
        return None

    cap = min(max_cash, value * float(profile["auction"]["valuation_buffer"]))
    if cap <= current_bid:
        return None

    increment = max(
        float(profile["auction"]["bid_increment_min"]),
        current_bid * float(profile["auction"]["bid_increment_ratio"]),
    )
    next_bid = round(min(cap, current_bid + increment), 2)
    if next_bid <= current_bid:
        return None
    return next_bid


def choose_jail_resolution(player: dict, game_state: dict, profile: dict[str, Any]) -> str:
    jail_profile = profile["jail"]
    balance = float(player.get("balance", 0) or 0)
    if player.get("has_jail_card") and jail_profile.get("use_card_aggressively", False):
        return "card"
    if balance >= float(jail_profile["pay_bail_cash_floor"]) and int(player.get("jail_turns_remaining", 0) or 0) <= int(jail_profile["pay_bail_after_turns_remaining"]):
        return "pay"
    return "roll"


def _list_tradeable_properties(owner_id: int, game_state: dict) -> list[dict[str, Any]]:
    candidates = []
    for prop in game_state.get("properties", []):
        prop_id = int(prop.get("id") or 0)
        if prop.get("owner_id") != owner_id or prop_id <= 0:
            continue
        if prop.get("is_mortgaged") or int(prop.get("dev_level", 0) or 0) > 0:
            continue
        if property_private_actions_locked(game_state, prop_id):
            continue
        candidates.append(prop)
    return candidates


def _round_up_trade_amount(amount: float) -> float:
    if amount <= 0:
        return 0.0
    return round(math.ceil(amount / TRADE_MIN_INCREMENT) * TRADE_MIN_INCREMENT, 2)


def _score_trade_terms_for_player(
    player: dict,
    *,
    counterparty_id: int | None,
    offered_money: float,
    requested_money: float,
    offered_props: list[int] | None,
    requested_props: list[int] | None,
    offered_lobby_pledges: list[dict] | None,
    requested_lobby_pledges: list[dict] | None,
    game_state: dict,
    profile: dict[str, Any],
) -> float:
    offered_value = float(offered_money or 0)
    requested_value = float(requested_money or 0)

    for prop_id in offered_props or []:
        prop = _find_property(game_state, prop_id)
        if prop is None:
            continue
        offered_value += estimate_property_value(player, prop, game_state, profile)
        if monopoly_completion_ratio(player["id"], prop, game_state) >= 1.0:
            offered_value += float(profile["trade"]["monopoly_trade_bonus"]) * 0.35

    offered_value += _score_lobby_pledges_for_player(
        player,
        offered_lobby_pledges or [],
        game_state,
        profile,
    )

    for prop_id in requested_props or []:
        prop = _find_property(game_state, prop_id)
        if prop is None:
            continue
        penalty = estimate_property_value(player, prop, game_state, profile)
        if has_full_monopoly(prop, game_state):
            penalty += float(profile["trade"]["monopoly_break_penalty"])
        if counterparty_id and monopoly_completion_ratio(counterparty_id, prop, game_state) >= 1.0:
            penalty += float(profile["trade"]["monopoly_break_penalty"]) * 0.55
        requested_value += penalty

    requested_value += _score_lobby_pledges_for_player(
        player,
        requested_lobby_pledges or [],
        game_state,
        profile,
    )

    return round(offered_value - requested_value, 2)


def _mirror_trade_terms(action: dict[str, Any]) -> dict[str, Any]:
    return {
        "offered_money": float(action.get("requested_money", 0) or 0),
        "requested_money": float(action.get("offered_money", 0) or 0),
        "offered_props": list(action.get("requested_props", []) or []),
        "requested_props": list(action.get("offered_props", []) or []),
        "offered_lobby_pledges": list(action.get("requested_lobby_pledges", []) or []),
        "requested_lobby_pledges": list(action.get("offered_lobby_pledges", []) or []),
    }


def _project_trade_candidate_state(
    game_state: dict,
    proposer_id: int,
    receiver_id: int,
    candidate: dict[str, Any],
) -> dict[str, Any]:
    offered_prop_ids = set()
    requested_prop_ids = set()
    for values, bucket in (
        (candidate.get("offered_props"), offered_prop_ids),
        (candidate.get("requested_props"), requested_prop_ids),
    ):
        for value in values or []:
            try:
                prop_id = int(value)
            except (TypeError, ValueError):
                continue
            if prop_id > 0:
                bucket.add(prop_id)

    offered_money = float(candidate.get("offered_money", 0) or 0)
    requested_money = float(candidate.get("requested_money", 0) or 0)

    next_players = []
    for entry in game_state.get("players", []):
        next_entry = dict(entry)
        player_id = int(next_entry.get("id") or 0)
        balance = float(next_entry.get("balance", 0) or 0)
        if player_id == int(proposer_id or 0):
            balance = balance - offered_money + requested_money
        elif player_id == int(receiver_id or 0):
            balance = balance + offered_money - requested_money
        next_entry["balance"] = round(balance, 2)
        next_players.append(next_entry)

    next_properties = []
    for prop in game_state.get("properties", []):
        next_prop = dict(prop)
        prop_id = int(next_prop.get("id") or 0)
        if prop_id in offered_prop_ids:
            next_prop["owner_id"] = receiver_id
        elif prop_id in requested_prop_ids:
            next_prop["owner_id"] = proposer_id
        next_properties.append(next_prop)

    return {
        **game_state,
        "players": next_players,
        "properties": next_properties,
    }


def _score_bundled_deal_drafts_for_player(
    player: dict,
    bundled_deal_drafts: list[dict] | None,
    projected_state: dict,
    profile: dict[str, Any],
) -> float:
    valid_drafts = [draft for draft in (bundled_deal_drafts or []) if isinstance(draft, dict)]
    if not valid_drafts:
        return 0.0
    return round(
        sum(score_deal_proposal(player, draft, projected_state, profile) for draft in valid_drafts),
        2,
    )


def _build_trade_bundle_drafts(
    player: dict,
    receiver: dict,
    candidate: dict[str, Any],
    game_state: dict,
    profile: dict[str, Any],
) -> list[dict[str, Any]]:
    settings = game_state.get("settings", {})
    if not settings.get("deals_enabled", True):
        return []

    player_id = int(player.get("id") or 0)
    receiver_id = int(receiver.get("id") or 0)
    if player_id <= 0 or receiver_id <= 0:
        return []

    max_active_deals = int(settings.get("max_active_deals_per_player", 3) or 3)
    if build_deal_summary(player, game_state, profile)["active_deal_count"] >= max_active_deals:
        return []
    if build_deal_summary(receiver, game_state, profile)["active_deal_count"] >= max_active_deals:
        return []

    context = _pairwise_deal_context(player_id, receiver_id, game_state)
    if context["active_deal_count"] > 0 or context["pending_incoming"] > 0 or context["pending_outgoing"] > 0:
        return []

    projected_state = _project_trade_candidate_state(game_state, player_id, receiver_id, candidate)
    econ = projected_state.get("econ", {})

    focus_props = []
    for prop_id in candidate.get("requested_props") or []:
        prop = _find_property(projected_state, prop_id)
        if prop is None or prop.get("property_type") != "property" or not prop.get("group_color"):
            continue
        if monopoly_completion_ratio(player_id, prop, projected_state) < 1.0:
            continue
        if not any(
            _property_owned_by_player(existing, player_id)
            and existing.get("property_type") == "property"
            and existing.get("group_color") == prop.get("group_color")
            for existing in game_state.get("properties", [])
        ):
            continue
        focus_props.append(prop)

    if not focus_props:
        return []

    focus_prop = sorted(
        focus_props,
        key=lambda entry: (
            float(entry.get("base_price", 0) or 0),
            float(calculate_rent_with_dev(entry, econ, projected_state) or 0),
        ),
        reverse=True,
    )[0]
    group_color = focus_prop.get("group_color")
    group_scope = {"mode": "selected_group_colors", "group_colors": [group_color]}
    group_props = [
        prop
        for prop in projected_state.get("properties", [])
        if _property_owned_by_player(prop, player_id)
        and prop.get("property_type") == "property"
        and prop.get("group_color") == group_color
    ]
    if not group_props:
        return []

    group_rent = round(
        sum(float(calculate_rent_with_dev(prop, econ, projected_state) or 0) for prop in group_props),
        2,
    )
    protection_options: list[dict[str, Any] | None] = [None]
    if group_rent >= 28.0:
        protection_options.append({
            "type": "rent_discount",
            "grantor_id": player_id,
            "beneficiary_id": receiver_id,
            "scope": group_scope,
            "config": {"rent_multiplier": 0.42 if group_rent >= 85.0 else 0.55},
            "deadline": {"metric": "beneficiary_turns", "initial": 3 if group_rent >= 85.0 else 2},
        })
    if group_rent >= 60.0:
        protection_options.append({
            "type": "rent_immunity",
            "grantor_id": player_id,
            "beneficiary_id": receiver_id,
            "scope": group_scope,
            "config": {},
            "deadline": {"metric": "beneficiary_turns", "initial": 2 if group_rent >= 110.0 else 1},
        })

    investment_options: list[dict[str, Any] | None] = [None]
    if settings.get("private_equity_enabled", True):
        buildable_group_props = [
            prop for prop in group_props
            if not prop.get("is_mortgaged")
            and has_full_monopoly(prop, projected_state)
            and not property_is_fully_developed(prop, projected_state)
        ]
        receiver_projection = _find_player(projected_state, receiver_id) or receiver
        receiver_balance = float(receiver_projection.get("balance", 0) or 0)
        reserve_floor = float(profile.get("liquidity", {}).get("reserve_cash_floor", 250) or 250)
        available_cash = max(0.0, receiver_balance - max(125.0, reserve_floor * 0.6))
        if buildable_group_props and available_cash >= 100.0:
            focus_build = sorted(
                buildable_group_props,
                key=lambda prop: (float(prop.get("base_price", 0) or 0), -int(prop.get("dev_level", 0) or 0)),
                reverse=True,
            )[0]
            next_level = min(5, int(focus_build.get("dev_level", 0) or 0) + 1)
            development_cost = max(
                100.0,
                float(calculate_development_cost(focus_build.get("base_price", 0), next_level, projected_state) or 0),
            )
            base_escrow = round(min(available_cash, max(100.0, development_cost * 0.95)), 2)
            payout_limit = float(settings.get("max_private_equity_payout_multiple", 1.75) or 1.75)
            payout_multiple = min(payout_limit, 1.6 if group_rent >= 85.0 else 1.48)
            if base_escrow >= 100.0:
                investment_options.append({
                    "type": "development_investment",
                    "investor_id": receiver_id,
                    "recipient_id": player_id,
                    "grantor_id": receiver_id,
                    "beneficiary_id": player_id,
                    "scope": group_scope,
                    "config": {
                        "escrow_amount": base_escrow,
                        "profit_share_percent": 0.42 if group_rent >= 85.0 else 0.34,
                        "max_payout": round(base_escrow * payout_multiple, 2),
                    },
                    "deadline": {"metric": "beneficiary_rotations", "initial": 3 if group_rent >= 85.0 else 2},
                })

            aggressive_escrow = round(min(available_cash, max(base_escrow + 50.0, development_cost * 1.2)), 2)
            aggressive_multiple = min(payout_limit, 1.72)
            if aggressive_escrow >= base_escrow + 25.0 and aggressive_escrow <= receiver_balance:
                investment_options.append({
                    "type": "development_investment",
                    "investor_id": receiver_id,
                    "recipient_id": player_id,
                    "grantor_id": receiver_id,
                    "beneficiary_id": player_id,
                    "scope": group_scope,
                    "config": {
                        "escrow_amount": aggressive_escrow,
                        "profit_share_percent": 0.48 if group_rent >= 110.0 else 0.4,
                        "max_payout": round(aggressive_escrow * aggressive_multiple, 2),
                    },
                    "deadline": {"metric": "beneficiary_rotations", "initial": 3},
                })

    best_draft = None
    best_score = float("-inf")
    for protection in protection_options:
        for investment in investment_options:
            clauses = [clause for clause in (protection, investment) if clause]
            if not clauses:
                continue
            proposal = {
                "counterparty_id": receiver_id,
                "title": "Set completion equity pact" if protection and investment else "Set completion sweetener",
                "clauses": clauses,
            }
            my_score = score_deal_proposal(player, proposal, projected_state, profile)
            other_score = score_deal_proposal(receiver, proposal, projected_state, profile)
            total_score = my_score + max(0.0, other_score * 0.45)
            if protection and investment:
                total_score += 4.0
            if my_score < -24.0 or other_score < 4.0 or total_score <= 0.0:
                continue
            if total_score > best_score:
                best_draft = proposal
                best_score = total_score

    return [best_draft] if best_draft is not None else []


def _finalize_trade_candidate(
    player: dict,
    receiver: dict,
    candidate: dict[str, Any],
    *,
    balance: float,
    reserve: float,
    max_offer: float,
    receiver_floor: float,
    self_floor: float,
    doctrine: str,
    game_state: dict,
    profile: dict[str, Any],
) -> dict[str, Any] | None:
    candidate = {
        "receiver_id": int(candidate["receiver_id"]),
        "offered_money": round(float(candidate.get("offered_money", 0) or 0), 2),
        "requested_money": round(float(candidate.get("requested_money", 0) or 0), 2),
        "offered_props": list(candidate.get("offered_props", []) or []),
        "requested_props": list(candidate.get("requested_props", []) or []),
        "offered_lobby_pledges": list(candidate.get("offered_lobby_pledges", []) or []),
        "requested_lobby_pledges": list(candidate.get("requested_lobby_pledges", []) or []),
        "included_deal_drafts": [
            draft for draft in (candidate.get("included_deal_drafts", []) or []) if isinstance(draft, dict)
        ],
    }

    def score_candidate() -> tuple[float, float]:
        self_score = _score_trade_terms_for_player(
            player,
            counterparty_id=receiver["id"],
            game_state=game_state,
            profile=profile,
            **_mirror_trade_terms(candidate),
        )
        receiver_score = _score_trade_terms_for_player(
            receiver,
            counterparty_id=player["id"],
            offered_money=candidate["offered_money"],
            requested_money=candidate["requested_money"],
            offered_props=candidate["offered_props"],
            requested_props=candidate["requested_props"],
            offered_lobby_pledges=candidate["offered_lobby_pledges"],
            requested_lobby_pledges=candidate["requested_lobby_pledges"],
            game_state=game_state,
            profile=profile,
        )
        if candidate["included_deal_drafts"]:
            projected_state = _project_trade_candidate_state(
                game_state,
                int(player.get("id") or 0),
                int(receiver.get("id") or 0),
                candidate,
            )
            self_score = round(
                self_score + _score_bundled_deal_drafts_for_player(
                    player,
                    candidate["included_deal_drafts"],
                    projected_state,
                    profile,
                ),
                2,
            )
            receiver_score = round(
                receiver_score + _score_bundled_deal_drafts_for_player(
                    receiver,
                    candidate["included_deal_drafts"],
                    projected_state,
                    profile,
                ),
                2,
            )
        return self_score, receiver_score

    self_score, receiver_score = score_candidate()

    if receiver_score < receiver_floor:
        cash_needed = _round_up_trade_amount(receiver_floor - receiver_score)
        cash_room = max(0.0, max_offer - candidate["offered_money"])
        if cash_needed > 0 and cash_room >= TRADE_MIN_INCREMENT:
            candidate["offered_money"] = round(candidate["offered_money"] + min(cash_room, cash_needed), 2)
            self_score, receiver_score = score_candidate()

    remaining_offer_capacity = max(0.0, balance - reserve - candidate["offered_money"])
    if receiver_score < receiver_floor and not candidate["offered_lobby_pledges"]:
        pledge_option = _select_trade_lobby_pledge(
            player,
            receiver,
            game_state,
            profile,
            min(remaining_offer_capacity, receiver_floor - receiver_score),
        )
        if pledge_option is not None:
            candidate["offered_lobby_pledges"] = [pledge_option]
            self_score, receiver_score = score_candidate()

    if (
        candidate["offered_money"] <= 0
        and not candidate["offered_props"]
        and not candidate["offered_lobby_pledges"]
        and not candidate["included_deal_drafts"]
    ):
        return None
    if self_score < self_floor or receiver_score < receiver_floor:
        return None

    total_score = self_score + max(0.0, receiver_score * 0.65)
    requested_completion = any(
        monopoly_completion_ratio(player["id"], prop, game_state) >= 1.0
        for prop in (_find_property(game_state, prop_id) for prop_id in candidate["requested_props"])
        if prop is not None
    )
    offered_completion = any(
        monopoly_completion_ratio(receiver["id"], prop, game_state) >= 1.0
        for prop in (_find_property(game_state, prop_id) for prop_id in candidate["offered_props"])
        if prop is not None
    )
    if requested_completion:
        total_score += 12.0
        if doctrine == "monopoly_rush":
            total_score += 18.0
    if offered_completion:
        total_score += 10.0
    if requested_completion and offered_completion:
        total_score += 24.0

    return {
        **candidate,
        "candidate_score": round(total_score, 2),
        "self_score": round(self_score, 2),
        "receiver_score": round(receiver_score, 2),
    }


def choose_trade_proposal(player: dict, game_state: dict, profile: dict[str, Any]) -> dict[str, Any] | None:
    settings = game_state.get("settings", {})
    if not settings.get("trading_enabled", True):
        return None
    if has_active_auction(game_state["match_id"]):
        return None

    if Trade.query.filter_by(match_id=game_state["match_id"], status="pending").filter(
        (Trade.initiator_id == player["id"]) | (Trade.receiver_id == player["id"])
    ).count():
        return None

    redis_key = f"game:{game_state['match_id']}:bot:{player['id']}:last_trade_round"
    if redis_client.get(redis_key) == str(game_state.get("current_round", 0)):
        return None

    regime = build_regime_summary(player, game_state, profile)
    doctrine = choose_bot_doctrine(player, game_state, profile, regime)
    balance = float(player.get("balance", 0) or 0)
    reserve = max(0.0, regime["soft_reserve"])
    receiver_floor = max(0.0, float(profile["trade"]["counter_margin"]) * 0.35)
    self_floor = max(10.0, float(profile["trade"]["counter_margin"]) * 0.45)
    max_offer = max(
        0.0,
        min(
            balance - max(0.0, reserve - (regime["allowed_negative_exposure"] * 0.2)),
            balance * float(profile["trade"]["max_cash_offer_share"]),
        ),
    )
    if max_offer < float(profile["trade"]["minimum_cash_offer"]) and game_state.get("econ", {}).get("gov_type") == "minarchism":
        return None

    candidate = None
    best_score = 0.0
    players_by_id = {
        entry.get("id"): entry
        for entry in game_state.get("players", [])
    }
    my_tradeable_props = _list_tradeable_properties(player["id"], game_state)

    for prop in game_state.get("properties", []):
        owner_id = prop.get("owner_id")
        if owner_id in (None, player["id"]) or prop.get("is_mortgaged") or int(prop.get("dev_level", 0) or 0) > 0:
            continue
        if property_private_actions_locked(game_state, prop.get("id")):
            continue

        projected_score = _trade_value_delta(player["id"], owner_id, prop, game_state, profile)
        if projected_score <= best_score:
            continue

        receiver = players_by_id.get(owner_id)
        if receiver is None:
            continue
        if _players_are_allied(player, receiver, game_state):
            continue

        minimum_cash_offer = float(profile["trade"]["minimum_cash_offer"])
        cash_offer = 0.0
        if max_offer > 0:
            cash_offer = round(min(max_offer, max(minimum_cash_offer, projected_score * 0.72)), 2)

        def promote_candidate(finalized: dict[str, Any] | None) -> None:
            nonlocal candidate, best_score
            if finalized is None or finalized["candidate_score"] <= best_score:
                return
            candidate = {
                "receiver_id": owner_id,
                "offered_money": finalized["offered_money"],
                "requested_money": finalized["requested_money"],
                "offered_props": finalized["offered_props"],
                "requested_props": finalized["requested_props"],
                "offered_lobby_pledges": finalized["offered_lobby_pledges"],
                "requested_lobby_pledges": finalized["requested_lobby_pledges"],
                "included_deal_drafts": finalized["included_deal_drafts"],
                "reason": doctrine,
            }
            best_score = finalized["candidate_score"]

        base_terms = {
            "receiver_id": owner_id,
            "offered_money": cash_offer,
            "requested_money": 0.0,
            "offered_props": [],
            "requested_props": [prop["id"]],
            "offered_lobby_pledges": [],
            "requested_lobby_pledges": [],
        }
        base_candidate = _finalize_trade_candidate(
            player,
            receiver,
            base_terms,
            balance=balance,
            reserve=reserve,
            max_offer=max_offer,
            receiver_floor=receiver_floor,
            self_floor=self_floor,
            doctrine=doctrine,
            game_state=game_state,
            profile=profile,
        )
        promote_candidate(base_candidate)

        bundled_base_terms = {
            **base_terms,
            "offered_money": round(max(0.0, base_terms["offered_money"] * 0.55), 2),
        }
        bundled_base_drafts = _build_trade_bundle_drafts(
            player,
            receiver,
            bundled_base_terms,
            game_state,
            profile,
        )
        if bundled_base_drafts:
            promote_candidate(
                _finalize_trade_candidate(
                    player,
                    receiver,
                    {
                        **bundled_base_terms,
                        "included_deal_drafts": bundled_base_drafts,
                    },
                    balance=balance,
                    reserve=reserve,
                    max_offer=max_offer,
                    receiver_floor=receiver_floor,
                    self_floor=self_floor,
                    doctrine=doctrine,
                    game_state=game_state,
                    profile=profile,
                )
            )

        for offered_prop in my_tradeable_props:
            offered_prop_id = int(offered_prop.get("id") or 0)
            if offered_prop_id <= 0 or offered_prop_id == int(prop.get("id") or 0):
                continue
            if (
                offered_prop.get("property_type") == "property"
                and prop.get("property_type") == "property"
                and offered_prop.get("group_color")
                and offered_prop.get("group_color") == prop.get("group_color")
            ):
                continue

            swap_terms = {
                "receiver_id": owner_id,
                "offered_money": 0.0,
                "requested_money": 0.0,
                "offered_props": [offered_prop_id],
                "requested_props": [prop["id"]],
                "offered_lobby_pledges": [],
                "requested_lobby_pledges": [],
            }
            swap_candidate = _finalize_trade_candidate(
                player,
                receiver,
                swap_terms,
                balance=balance,
                reserve=reserve,
                max_offer=max_offer,
                receiver_floor=receiver_floor,
                self_floor=self_floor,
                doctrine=doctrine,
                game_state=game_state,
                profile=profile,
            )
            promote_candidate(swap_candidate)

            bundled_swap_drafts = _build_trade_bundle_drafts(
                player,
                receiver,
                swap_terms,
                game_state,
                profile,
            )
            if bundled_swap_drafts:
                promote_candidate(
                    _finalize_trade_candidate(
                        player,
                        receiver,
                        {
                            **swap_terms,
                            "included_deal_drafts": bundled_swap_drafts,
                        },
                        balance=balance,
                        reserve=reserve,
                        max_offer=max_offer,
                        receiver_floor=receiver_floor,
                        self_floor=self_floor,
                        doctrine=doctrine,
                        game_state=game_state,
                        profile=profile,
                    )
                )

    if candidate is not None:
        redis_client.set(redis_key, str(game_state.get("current_round", 0)), ex=BOT_TASK_TTL_SECONDS)
    return candidate


def evaluate_trade_response(
    trade: Trade,
    player: dict,
    game_state: dict,
    profile: dict[str, Any],
) -> str:
    regime = build_regime_summary(player, game_state, profile)
    doctrine = choose_bot_doctrine(player, game_state, profile, regime)
    score = _score_trade_terms_for_player(
        player,
        counterparty_id=getattr(trade, "initiator_id", None),
        offered_money=float(trade.offered_money or 0),
        requested_money=float(trade.requested_money or 0),
        offered_props=getattr(trade, "offered_props", []) or [],
        requested_props=getattr(trade, "requested_props", []) or [],
        offered_lobby_pledges=getattr(trade, "offered_lobby_pledges", []) or [],
        requested_lobby_pledges=getattr(trade, "requested_lobby_pledges", []) or [],
        game_state=game_state,
        profile=profile,
    )
    bundled_deal_drafts = [
        draft
        for draft in (getattr(trade, "included_deal_drafts", []) or [])
        if isinstance(draft, dict)
    ]
    if bundled_deal_drafts:
        projected_state = _project_trade_candidate_state(
            game_state,
            int(getattr(trade, "initiator_id", 0) or 0),
            int(getattr(trade, "receiver_id", player.get("id")) or player.get("id") or 0),
            {
                "offered_money": float(getattr(trade, "offered_money", 0) or 0),
                "requested_money": float(getattr(trade, "requested_money", 0) or 0),
                "offered_props": getattr(trade, "offered_props", []) or [],
                "requested_props": getattr(trade, "requested_props", []) or [],
            },
        )
        score = round(
            score + _score_bundled_deal_drafts_for_player(player, bundled_deal_drafts, projected_state, profile),
            2,
        )
    acceptance_margin = float(profile["trade"]["acceptance_margin"])
    if doctrine in {"policy_shaping", "social_democracy_leverage"}:
        acceptance_margin -= regime["state_protection_score"] * 12.0
    if score >= acceptance_margin:
        return "accept"
    return "reject"


def _score_deal_clause_for_player(player: dict, clause: dict, game_state: dict, profile: dict[str, Any]) -> float:
    player_id = int(player.get("id") or 0)
    uses = max(1, int((clause.get("deadline") or {}).get("remaining", (clause.get("deadline") or {}).get("initial", 1)) or 1))
    clause_type = clause.get("type")

    if clause_type == "rent_immunity":
        threat_value = _estimate_owner_rent_threat(int(clause.get("grantor_id") or 0), game_state)
        score = threat_value * min(3, uses) * 0.75
        return score if int(clause.get("beneficiary_id") or 0) == player_id else -score

    if clause_type == "rent_discount":
        threat_value = _estimate_owner_rent_threat(int(clause.get("grantor_id") or 0), game_state)
        concession = threat_value * max(0.0, 1.0 - float((clause.get("config") or {}).get("rent_multiplier", 1) or 1)) * min(3, uses) * 0.7
        return concession if int(clause.get("beneficiary_id") or 0) == player_id else -concession

    if clause_type == "development_investment":
        config = clause.get("config") or {}
        escrow_amount = float(config.get("escrow_amount", 0) or 0)
        max_payout = float(config.get("max_payout", 0) or 0)
        effective_max_payout = calculate_effective_build_loan_payout(max_payout, game_state, game_state.get("econ") or {})
        reserve_floor = float(profile.get("liquidity", {}).get("reserve_cash_floor", 250) or 250)
        balance = float(player.get("balance", 0) or 0)
        recipient_id = int(clause.get("beneficiary_id") or clause.get("recipient_id") or 0)
        investor_id = int(clause.get("grantor_id") or clause.get("investor_id") or 0)
        if recipient_id == player_id:
            relief_bonus = max(0.0, reserve_floor - balance) * 0.18
            return (escrow_amount * 0.72) - max(0.0, effective_max_payout - escrow_amount) * 0.18 + relief_bonus
        if investor_id == player_id:
            cash_buffer = max(0.0, balance - reserve_floor)
            return_bias = 0.36 + min(0.18, cash_buffer / max(200.0, reserve_floor * 2.0))
            return (max(0.0, effective_max_payout - escrow_amount) * return_bias) - (escrow_amount * 0.62)

    return 0.0


def score_deal_proposal(player: dict, proposal: dict, game_state: dict, profile: dict[str, Any]) -> float:
    score = 0.0
    for clause in proposal.get("clauses") or []:
        score += _score_deal_clause_for_player(player, clause, game_state, profile)

    deal_summary = build_deal_summary(player, game_state, profile)
    score -= deal_summary["active_deal_burden"] * 18.0
    score += deal_summary["immunity_need_score"] * 10.0
    return round(score, 2)


def evaluate_deal_response(deal_payload: dict, player: dict, game_state: dict, profile: dict[str, Any]) -> str:
    score = score_deal_proposal(player, deal_payload, game_state, profile)
    difficulty = normalize_bot_difficulty(profile.get("difficulty") or infer_legacy_difficulty(profile.get("persona")))
    threshold = {
        "easy": -12.0,
        "normal": -2.0,
        "hard": 8.0,
        "expert": 15.0,
    }.get(difficulty, 0.0)
    return "accept" if score >= threshold else "reject"


def choose_lobbying_move(player: dict, game_state: dict, profile: dict[str, Any]) -> dict[str, Any] | None:
    settings = game_state.get("settings", {})
    econ = game_state.get("econ", {})
    lobbying_profile = profile["lobbying"]
    if not settings.get("lobbying_enabled", True) or not lobbying_profile.get("enabled", False):
        return None

    regime = build_regime_summary(player, game_state, profile)
    doctrine = choose_bot_doctrine(player, game_state, profile, regime)

    redis_key = f"game:{game_state['match_id']}:bot:{player['id']}:last_lobby_round"
    current_round = str(game_state.get("current_round", 0))
    if redis_client.get(redis_key) == current_round:
        return None

    active_players = [entry for entry in game_state.get("players", []) if not entry.get("is_bankrupt")]
    if not active_players:
        return None

    avg_balance = sum(float(entry.get("balance", 0) or 0) for entry in active_players) / max(len(active_players), 1)
    net_worth = calculate_net_worth(player, game_state)
    wealthy = (
        float(player.get("balance", 0) or 0) >= float(profile["liquidity"]["wealth_threshold"])
        or net_worth >= avg_balance * 1.45
    )
    distressed = (
        float(player.get("balance", 0) or 0) <= float(lobbying_profile["distress_balance_threshold"])
        or net_worth < avg_balance * 0.85
    )

    axis = None
    direction = None
    target = None
    reason = None
    target_success = float(lobbying_profile["target_success_chance"])
    welfare_rate = float(econ.get("welfare_payout", 0) or 0)
    tax_multiplier = float(econ.get("tax_multiplier", 0) or 0)
    stability = float(econ.get("stability", 0.7) or 0.7)
    treasury_balance = float(econ.get("treasury_balance", 0) or 0)
    rent_control_active = bool(econ.get("rent_control_active", False))
    social_summary = regime.get("social_summary", {})
    government_type = regime["government_type"]
    market_confidence = float(regime.get("market_confidence", econ.get("market_confidence", 0)) or 0)
    private_equity_edge_score = float(regime.get("private_equity_edge_score", 0) or 0)
    market_overheat_score = float(regime.get("market_overheat_score", 0) or 0)

    if social_summary.get("preferred_lobby_target") and (
        social_summary.get("civil_risk_score", 0) >= 0.60
        or social_summary.get("incident_count", 0) > 0
    ):
        target = social_summary["preferred_lobby_target"]
        reason = "reduce_civil_risk"
        target_success = max(target_success, 0.58)

    if target is None and government_type == "liberal_democracy":
        if social_summary.get("preferred_lobby_target") == "money_supply_contract" and (
            social_summary.get("civil_risk_score", 0) >= 0.52
            or social_summary.get("incident_count", 0) > 0
            or market_overheat_score >= 0.58
        ):
            axis = "money_supply"
            direction = "contract"
            reason = "cool_shareholder_backlash"
            target_success = max(target_success, 0.56)
        elif doctrine == "capital_markets_arbitrage":
            if market_confidence <= 64.0 and social_summary.get("civil_risk_score", 0) < 0.55 and stability >= 0.48:
                axis = "money_supply"
                direction = "expand"
                reason = "restore_market_confidence"
                target_success = max(target_success, 0.54)
            elif private_equity_edge_score >= 0.46 and market_overheat_score < 0.58:
                axis = "tax_brackets"
                direction = "lower_rate"
                reason = "expand_private_equity_upside"
                target_success = max(target_success, 0.52)
            elif market_overheat_score >= 0.62:
                axis = "money_supply"
                direction = "contract"
                reason = "cool_overheated_market"
                target_success = max(target_success, 0.56)
        elif wealthy and market_confidence <= 60.0 and social_summary.get("civil_risk_score", 0) < 0.48:
            axis = "money_supply"
            direction = "expand"
            reason = "restore_market_confidence"
        elif wealthy and market_overheat_score >= 0.68:
            axis = "money_supply"
            direction = "contract"
            reason = "protect_against_backlash"

    if target is None and axis and direction:
        target = resolve_lobbying_target(axis=axis, direction=direction)

    if target is None and doctrine in {"policy_shaping", "social_democracy_leverage", "treasury_rebuild_then_leverage"} and government_type == "social_democracy":
        if not regime["bailout_enabled"] and regime["difficulty"] in {"hard", "expert"}:
            axis = "bailouts"
            direction = "enable"
            reason = "unlock_safety_net"
            target_success += 0.04
        elif regime["treasury_balance"] < max(450.0, regime["expected_bailout_amount"] * 1.3):
            if regime["tax_multiplier"] < 0.42 and float(profile.get("regime_bias", {}).get("treasury_shaping_bias", 0.3) or 0.3) >= 0.52:
                axis = "tax_multiplier"
                direction = "increase"
                reason = "rebuild_treasury_for_rescue"
            else:
                axis = "treasury_posture"
                direction = "rebuild"
                reason = "stabilize_treasury_before_leverage"
        elif regime["welfare_rate"] < 28.0 and regime["capabilities"].get("welfare_abuse"):
            axis = "welfare_rate"
            direction = "increase"
            reason = "increase_recovery_support"
        elif rent_control_active and monopoly_property_count(player["id"], game_state) > 0:
            axis = "housing_regulation"
            direction = "loosen"
            reason = "restore_development_upside"
    elif target is None and wealthy and welfare_rate >= float(lobbying_profile["wealthy_welfare_cut_trigger"]):
        axis = "welfare_rate"
        direction = "decrease"
        reason = "cut_wealthy_welfare_drag"
        target_success = float(lobbying_profile["wealthy_welfare_cut_target_success"])
    elif target is None and wealthy and treasury_balance <= float(lobbying_profile["wealthy_tax_hike_treasury_trigger"]):
        axis = "tax_multiplier"
        direction = "increase"
        reason = "refuel_thin_treasury"
    elif target is None and distressed and tax_multiplier >= float(lobbying_profile["wealthy_tax_relief_trigger"]):
        axis = "tax_multiplier"
        direction = "decrease"
        reason = "reduce_tax_pressure"
    elif target is None and distressed and welfare_rate <= float(lobbying_profile["distress_welfare_trigger"]):
        axis = "welfare_rate"
        direction = "increase"
        reason = "support_distress_recovery"
    elif target is None and distressed and treasury_balance >= float(lobbying_profile["max_treasury_stimulus_threshold"]):
        axis = "treasury_posture"
        direction = "stimulate"
        reason = "fund_direct_relief"
    elif target is None and rent_control_active and monopoly_property_count(player["id"], game_state) > 0:
        axis = "housing_regulation"
        direction = "loosen"
        reason = "restore_rent_growth"
    elif target is None and stability <= float(lobbying_profile["stability_alert_threshold"]):
        axis = "treasury_posture"
        direction = "rebuild"
        reason = "stabilize_macro_state"

    target = resolve_lobbying_target(axis=axis, direction=direction, target=target)
    if target is None:
        return None

    policy = ensure_match_lobbying_policy(game_state["match_id"], target)
    if policy is None:
        return None

    balance = float(player.get("balance", 0) or 0)
    reserve = max(0.0, regime["soft_reserve"])
    max_contribution = max(
        0.0,
        min(
            balance - max(0.0, reserve - (regime["allowed_negative_exposure"] * 0.15)),
            balance * float(profile["liquidity"]["max_lobby_share"]),
        ),
    )
    minimum_contribution = float(lobbying_profile["minimum_contribution"])
    if max_contribution < minimum_contribution:
        return None

    entries = LobbyContribution.query.filter_by(match_id=game_state["match_id"], policy_id=policy.id).all()
    pool_total = round(sum(float(entry.contribution or 0) for entry in entries), 2)
    contributor_ids = {entry.player_id for entry in entries}
    contributor_count = len(contributor_ids | {player["id"]})

    contribution = minimum_contribution
    selected = None
    while contribution <= max_contribution + 0.001:
        success_chance = calculate_lobbying_success_chance(
            target_stat=policy.target_stat,
            government_type=government_type,
            total_contribution=pool_total + contribution,
            contributor_count=contributor_count,
        )
        if success_chance >= target_success:
            selected = {
                "axis": axis,
                "direction": direction,
                "target": target,
                "policy_id": policy.id,
                "contribution": round(contribution, 2),
                "success_chance": success_chance,
                "reason": reason or doctrine,
                "doctrine": doctrine,
            }
            break
        contribution += LOBBY_INCREMENT

    if selected is None:
        opportunistic_cap = round(min(max_contribution, minimum_contribution * 2), 2)
        if opportunistic_cap < minimum_contribution:
            return None
        success_chance = calculate_lobbying_success_chance(
            target_stat=policy.target_stat,
            government_type=government_type,
            total_contribution=pool_total + opportunistic_cap,
            contributor_count=contributor_count,
        )
        if success_chance >= target_success * 0.82:
            selected = {
                "axis": axis,
                "direction": direction,
                "target": target,
                "policy_id": policy.id,
                "contribution": opportunistic_cap,
                "success_chance": success_chance,
                "reason": reason or doctrine,
                "doctrine": doctrine,
            }

    if selected is not None:
        redis_client.set(redis_key, current_round, ex=BOT_TASK_TTL_SECONDS)
    return selected


def choose_negotiation_move(player: dict, game_state: dict, profile: dict[str, Any], regime: dict[str, Any] | None = None) -> dict[str, Any] | None:
    regime = regime or build_regime_summary(player, game_state, profile)
    social_summary = regime.get("social_summary", {})
    candidate = social_summary.get("top_incident")
    difficulty = regime.get("difficulty", normalize_bot_difficulty(profile.get("difficulty")))
    if not candidate and difficulty == "expert" and social_summary.get("contagion_risk", 0) >= 0.5:
        candidate = social_summary.get("regional_contagion_candidate")
    if not candidate:
        return None

    balance = float(player.get("balance", 0) or 0)
    civil_risk = float(social_summary.get("civil_risk_score", 0) or 0)
    soft_reserve = max(0.0, regime.get("soft_reserve", 0) or 0)
    if civil_risk >= 0.85:
        reserve = max(20.0, soft_reserve * 0.4)
    elif civil_risk >= 0.75:
        reserve = max(30.0, soft_reserve * 0.55)
    else:
        reserve = max(40.0, soft_reserve * 0.65)

    cap_share = float(BOT_NEGOTIATION_SHARE_CAP.get(difficulty, 0.15))
    max_commitment = max(
        0.0,
        min(
            balance * cap_share,
            balance - reserve + (regime.get("allowed_negative_exposure", 0) * 0.1),
        ),
    )
    if max_commitment < 25.0:
        return None

    incident_type = candidate.get("incident_type")
    current_owner_id = candidate.get("current_owner_id", candidate.get("owner_id"))
    is_owned_exposure = current_owner_id == player.get("id") or candidate.get("former_owner_id") == player.get("id")
    if not is_owned_exposure and difficulty != "expert":
        return None

    coverage_goal = 1.0 if incident_type in {"strike", "uprising", "revolution"} or candidate.get("former_owner_id") == player.get("id") or not is_owned_exposure else 0.5
    required = max(
        0.0,
        (float(candidate.get("negotiation_target", 0) or 0) * coverage_goal) - float(candidate.get("negotiation_committed", 0) or 0),
    )
    if required <= 10.0 and civil_risk < 0.60:
        return None

    contribution = round(min(max_commitment, max(25.0, required)), 2)
    if contribution < 25.0:
        return None

    return {
        "type": "negotiate",
        "property_id": int(candidate["property_id"]),
        "contribution": contribution,
        "reason": "civil_risk_relief" if is_owned_exposure else "contain_contagion",
    }


def choose_emergency_reform(player: dict, game_state: dict, profile: dict[str, Any], regime: dict[str, Any] | None = None) -> dict[str, Any] | None:
    regime = regime or build_regime_summary(player, game_state, profile)
    if regime.get("government_type") != "minarchism":
        return None
    social = game_state.get("social") or {}
    current_round = int(game_state.get("current_round", 1) or 1)
    resolution_round = current_round + 1
    if any(int(entry.get("round", 0) or 0) == resolution_round for entry in social.get("emergency_reforms", [])):
        return None

    social_summary = regime.get("social_summary", {})
    flashpoint = social_summary.get("top_incident") or social_summary.get("flashpoint")
    if not flashpoint or social_summary.get("civil_risk_score", 0) < 0.45:
        return None

    grievance = flashpoint.get("dominant_grievance")
    if grievance == "tax_pressure":
        return {"type": "emergency_reform", "reform_type": "tax_moratorium", "reason": "tax_pressure_relief"}
    if flashpoint.get("incident_type") in {"protest", "strike", "uprising"} and flashpoint.get("former_owner_id") is None:
        return {
            "type": "emergency_reform",
            "reform_type": "private_relief_contract",
            "property_id": int(flashpoint["property_id"]),
            "reason": "private_relief_contract",
        }
    return {
        "type": "emergency_reform",
        "reform_type": "property_rights_compact",
        "property_id": int(flashpoint.get("property_id", 0) or 0) or None,
        "target_region": flashpoint.get("region"),
        "reason": "contain_contagion",
    }


def _plot_region_order(plot: dict) -> list[str]:
    regions = list((plot.get("regions") or {}).items())
    regions.sort(
        key=lambda item: (
            int((item[1] or {}).get("hardship_pressure", 0) or 0),
            int((item[1] or {}).get("seeded_cells", 0) or 0),
            str(item[0]),
        ),
        reverse=True,
    )
    return [str(region_name) for region_name, _region_state in regions]


def _plot_total_seeded_cells(plot: dict) -> int:
    return sum(int((region_state or {}).get("seeded_cells", 0) or 0) for region_state in (plot.get("regions") or {}).values())


def _plot_near_victory(plot: dict) -> bool:
    victory = dict(plot.get("victory_countdown") or {})
    return bool(
        victory.get("active")
        or victory.get("countdown_eligible")
        or int(plot.get("stage", 0) or 0) >= 4
        and (
            float(plot.get("control_percent", 0) or 0) >= 24.0
            or len(plot.get("seized_property_ids") or []) >= 6
        )
    )


def _plot_primary_seizure_targets(plot: dict) -> list[dict[str, Any]]:
    legal_targets = [
        entry
        for entry in (plot.get("legal_targets") or [])
        if entry.get("property_id") is not None
    ]
    if not legal_targets:
        return []

    region_sizes: dict[str, int] = {}
    for entry in legal_targets:
        region_name = str(entry.get("region") or "")
        region_sizes[region_name] = region_sizes.get(region_name, 0) + 1

    return sorted(
        legal_targets,
        key=lambda entry: (
            bool(entry.get("adjacent_to_control")),
            region_sizes.get(str(entry.get("region") or ""), 0),
            float(entry.get("preview_score", 0) or 0),
            float(entry.get("agitation", 0) or 0),
        ),
        reverse=True,
    )


def _plot_coordination_targets(plot: dict, prioritized_targets: list[dict[str, Any]]) -> int:
    if int(plot.get("stage", 0) or 0) < 3:
        return 1
    if len(prioritized_targets) < 2:
        return 1
    if len(plot.get("seized_property_ids") or []) >= 4 or int(plot.get("stage", 0) or 0) >= 4:
        return 1
    return 2


def _plot_should_hold_for_coordinated_push(plot: dict, prioritized_targets: list[dict[str, Any]]) -> bool:
    required_targets = _plot_coordination_targets(plot, prioritized_targets)
    if required_targets <= 1:
        return False

    support = float(plot.get("support", 0) or 0)
    supply = float(plot.get("supply", 0) or 0)
    return support < (6 * required_targets) or supply < (4 * required_targets)


def _plot_private_win_signal(player: dict, game_state: dict) -> dict[str, float | int | bool]:
    player_id = int(player.get("id") or 0)
    owned_properties = []
    total_development = 0
    monopoly_groups: set[str] = set()
    for prop in game_state.get("properties", []):
        owner_id = prop.get("owner_id")
        if not isinstance(owner_id, int) or owner_id != player_id:
            continue
        if prop.get("property_type") not in {"property", "transit"}:
            continue
        owned_properties.append(prop)
        total_development += max(0, int(prop.get("dev_level", 0) or 0))
        if prop.get("property_type") == "property" and has_full_monopoly(prop, game_state):
            monopoly_groups.add(str(prop.get("group_color") or prop.get("region") or prop.get("id") or ""))

    active_players = [candidate for candidate in game_state.get("players", []) if not candidate.get("is_bankrupt")]
    net_worths = sorted(
        (float(calculate_net_worth(candidate, game_state) or 0) for candidate in active_players),
        reverse=True,
    )
    player_net_worth = float(calculate_net_worth(player, game_state) or 0)
    median_net_worth = net_worths[len(net_worths) // 2] if net_worths else 0.0
    return {
        "property_count": len(owned_properties),
        "total_development": total_development,
        "monopoly_count": len(monopoly_groups),
        "net_worth": player_net_worth,
        "median_net_worth": median_net_worth,
        "strong_private_path": bool(
            monopoly_groups
            or total_development >= 4
            or (len(owned_properties) >= 5 and player_net_worth >= median_net_worth * 1.1)
        ),
    }


def _choose_plot_counter_action(player: dict, plot: dict, profile: dict[str, Any]) -> dict[str, Any] | None:
    player_id = int(player.get("id") or 0)
    balance = float(player.get("balance", 0) or 0)
    counter_defs = {
        str(entry.get("action_type") or ""): entry
        for entry in (plot.get("counter_action_catalog") or [])
        if entry.get("action_type")
    }
    seized_properties = sorted(
        [entry for entry in (plot.get("seized_properties") or []) if entry.get("property_id") is not None],
        key=lambda entry: (
            int(entry.get("reintegration_progress", 0) or 0),
            float(entry.get("current_value", 0) or 0),
            int(entry.get("entrenchment", 0) or 0),
        ),
        reverse=True,
    )
    legal_targets = sorted(
        [entry for entry in (plot.get("legal_targets") or []) if entry.get("property_id") is not None],
        key=lambda entry: (float(entry.get("preview_score", 0) or 0), float(entry.get("agitation", 0) or 0)),
        reverse=True,
    )
    regions = _plot_region_order(plot)
    clusters = sorted(
        [entry for entry in (plot.get("clusters") or []) if entry.get("cluster_id")],
        key=lambda entry: (int(entry.get("size", 0) or 0), float(entry.get("avg_entrenchment", 0) or 0)),
        reverse=True,
    )

    reintegration_cost = float((counter_defs.get("reintegration_campaign") or {}).get("cash_cost", 220) or 220)
    if seized_properties and balance >= reintegration_cost:
        return {
            "type": "plot_counter_action",
            "action_type": "reintegration_campaign",
            "property_id": int(seized_properties[0]["property_id"]),
            "supporter_ids": [player_id],
            "reason": "reclaim_private_control",
        }

    subsidy_cost = float((counter_defs.get("security_subsidy") or {}).get("cash_cost", 180) or 180)
    if legal_targets and balance >= subsidy_cost:
        return {
            "type": "plot_counter_action",
            "action_type": "security_subsidy",
            "property_id": int(legal_targets[0]["property_id"]),
            "reason": "harden_best_target",
        }

    relief_cost = float((counter_defs.get("relief_package") or {}).get("cash_cost", 150) or 150)
    if regions and balance >= relief_cost:
        return {
            "type": "plot_counter_action",
            "action_type": "relief_package",
            "region": regions[0],
            "reason": "reduce_regional_hardship",
        }

    blockade_cost = float((counter_defs.get("blockade_cluster") or {}).get("cash_cost", 220) or 220)
    if clusters and balance >= blockade_cost:
        return {
            "type": "plot_counter_action",
            "action_type": "blockade_cluster",
            "cluster_id": str(clusters[0]["cluster_id"]),
            "supporter_ids": [player_id],
            "reason": "choke_cluster_supply",
        }

    propaganda_cost = float((counter_defs.get("propaganda_counteroffensive") or {}).get("cash_cost", 140) or 140)
    if balance >= propaganda_cost:
        return {
            "type": "plot_counter_action",
            "action_type": "propaganda_counteroffensive",
            "reason": "slow_public_recruitment",
        }

    return None


def choose_plot_management_action(player: dict, game_state: dict, profile: dict[str, Any], regime: dict[str, Any] | None = None) -> dict[str, Any] | None:
    regime = regime or build_regime_summary(player, game_state, profile)
    social = game_state.get("social") or {}
    plot = dict(social.get("plot") or {})
    player_id = int(player.get("id") or 0)
    current_round = int(game_state.get("current_round", 1) or 1)
    balance = float(player.get("balance", 0) or 0)
    poor_threshold = float(profile.get("liquidity", {}).get("poor_threshold", 350) or 350)
    hardship_score = int(player.get("plot_hardship_score", 0) or 0)
    hardship_triggers = int(player.get("plot_hardship_trigger_count", 0) or 0)

    if not bool(plot.get("exists")):
        if bool(player.get("plot_can_found", False)) and hardship_score >= 2 and balance <= max(650.0, poor_threshold * 1.35):
            return {"type": "plot_start", "reason": "hardship_founding"}
        return None

    member_ids = {int(value) for value in (plot.get("member_ids") or []) if value is not None}
    committed_member_ids = {int(value) for value in (plot.get("committed_member_ids") or []) if value is not None}
    coalition_member_ids = {int(value) for value in (plot.get("coalition_member_ids") or []) if value is not None}
    raw_member_entry = dict((plot.get("members") or {}).get(str(player_id)) or {})
    invite_pending = bool((plot.get("join_invites") or {}).get(str(player_id)))
    request_pending = bool((plot.get("join_requests") or {}).get(str(player_id)))
    defection_cooldown_until = int(player.get("plot_defection_cooldown_until", 0) or 0)
    defection_reason = str(raw_member_entry.get("defection_reason") or "")
    left_round = int(raw_member_entry.get("left_round", 0) or 0)
    private_defection_reentry_locked = (
        defection_reason == "protect_private_win_path"
        and left_round > 0
        and current_round <= left_round + 8
        and not _plot_near_victory(plot)
    )
    plot_role = str(player.get("plot_role") or "")
    command_entry = next(
        (entry for entry in (plot.get("command_chain") or []) if int(entry.get("player_id") or 0) == player_id),
        {},
    )
    total_seeded_cells = _plot_total_seeded_cells(plot)
    private_win_signal = _plot_private_win_signal(player, game_state)
    strong_private_path = bool(private_win_signal.get("strong_private_path"))
    plot_close_to_victory = _plot_near_victory(plot)
    commander_id = int(((plot.get("commander") or {}).get("player_id") or plot.get("commander_id") or 0) or 0)
    strategic_goal = str(plot.get("strategic_goal") or "")
    strategic_goal_region = str(plot.get("goal_target_region") or "")
    strategic_goal_property_id = int(plot.get("goal_target_property_id") or 0) or None
    joint_account_balance = float(plot.get("joint_account_balance", 0) or 0)
    seized_properties = sorted(
        [entry for entry in (plot.get("seized_properties") or []) if entry.get("property_id") is not None],
        key=lambda entry: (
            int(entry.get("reintegration_progress", 0) or 0),
            int(entry.get("entrenchment", 0) or 0),
            float(entry.get("current_value", 0) or 0),
        ),
        reverse=True,
    )
    legal_targets = _plot_primary_seizure_targets(plot)
    recruitable_players = sorted(
        [entry for entry in (plot.get("recruitable_players") or []) if int(entry.get("player_id") or 0) != player_id],
        key=lambda entry: (
            int(entry.get("hardship_trigger_count", 0) or 0),
            int(entry.get("hardship_score", 0) or 0),
            not bool(entry.get("invited", False)),
        ),
        reverse=True,
    )
    pending_join_requests = sorted(
        [entry for entry in (plot.get("join_requests") or {}).values() if int(entry.get("player_id") or 0) != player_id],
        key=lambda entry: (
            int(entry.get("hardship_trigger_count", 0) or 0),
            int(entry.get("hardship_score", 0) or 0),
            -int(entry.get("requested_round", 0) or 0),
        ),
        reverse=True,
    )
    clusters = sorted(
        [entry for entry in (plot.get("clusters") or []) if entry.get("cluster_id")],
        key=lambda entry: (
            int(entry.get("size", 0) or 0),
            float(entry.get("avg_entrenchment", 0) or 0),
            -int(entry.get("reintegration_pressure", 0) or 0),
        ),
        reverse=True,
    )
    region_order = _plot_region_order(plot)
    unseeded_regions = [
        region_name
        for region_name in region_order
        if int(((plot.get("regions") or {}).get(region_name) or {}).get("seeded_cells", 0) or 0) <= 0
    ]
    coordinated_push_target_count = _plot_coordination_targets(plot, legal_targets)
    coordinated_push_ready = not _plot_should_hold_for_coordinated_push(plot, legal_targets)
    joined_round = int(command_entry.get("joined_round", raw_member_entry.get("joined_round", current_round)) or current_round)
    overwhelming_private_path = bool(
        int(private_win_signal.get("monopoly_count", 0) or 0) >= 2
        or (
            int(private_win_signal.get("monopoly_count", 0) or 0) >= 1
            and int(private_win_signal.get("total_development", 0) or 0) >= 4
        )
        or (
            int(private_win_signal.get("monopoly_count", 0) or 0) >= 1
            and int(private_win_signal.get("total_development", 0) or 0) >= 5
            and float(private_win_signal.get("net_worth", 0) or 0)
            >= float(private_win_signal.get("median_net_worth", 0) or 0) * 1.35
        )
    )

    if player_id not in member_ids:
        if private_defection_reentry_locked:
            if invite_pending:
                return {"type": "plot_join", "intent": "decline", "reason": "recent_private_path_defection"}
            if player_id in coalition_member_ids:
                return _choose_plot_counter_action(player, plot, profile)
            return None
        if invite_pending and current_round > defection_cooldown_until:
            if strong_private_path and not plot_close_to_victory:
                return {"type": "plot_join", "intent": "decline", "reason": "protect_private_win_path"}
            join_cost = 0.0 if hardship_triggers >= 2 else 150.0
            if balance >= join_cost:
                return {"type": "plot_join", "intent": "accept", "reason": "invited_alignment"}
        if player_id in coalition_member_ids:
            return _choose_plot_counter_action(player, plot, profile)
        if not request_pending and current_round > defection_cooldown_until and (bool(plot.get("public")) or hardship_triggers >= 2) and not strong_private_path:
            return {"type": "plot_join", "intent": "request", "reason": "self_recruitment_under_pressure"}
        if bool(plot.get("public")) and bool(plot.get("coalition_unlocked")):
            return {
                "type": "plot_counter_action",
                "action_type": "join_coalition",
                "reason": "counter_revolution_alignment",
            }
        return None

    if (
        strong_private_path
        and overwhelming_private_path
        and not plot_close_to_victory
        and len(member_ids) > 2
        and current_round >= joined_round + 2
        and player_id != commander_id
        and plot_role != "founder"
    ):
        return {"type": "plot_leave", "reason": "protect_private_win_path"}

    if plot_role == "sympathizer":
        contribution_cost = 100.0 if hardship_triggers < 2 else 50.0
        contribution_round_count = int(command_entry.get("contribution_round_count", 0) or 0)
        required_contribution_rounds = max(1, int(command_entry.get("required_contribution_rounds", 2) or 2))
        if (
            current_round > int(player.get("plot_join_round", current_round) or current_round)
            and contribution_round_count < required_contribution_rounds
            and joint_account_balance >= contribution_cost
        ):
            return {
                "type": "plot_join",
                "intent": "contribute",
                "amount": contribution_cost,
                "reason": "build_membership_credibility",
            }
        return None

    ready_sympathizer = next(
        (
            entry
            for entry in (plot.get("command_chain") or [])
            if str(entry.get("role") or "") == "sympathizer" and bool(entry.get("promotion_ready"))
        ),
        None,
    )
    if commander_id == player_id and ready_sympathizer is not None and int(plot.get("stage", 0) or 0) >= 1 and float(plot.get("support", 0) or 0) >= 2 and float(plot.get("supply", 0) or 0) >= 1:
        return {
            "type": "plot_action",
            "action_type": "convert_to_organizer",
            "target_player_id": int(ready_sympathizer.get("player_id") or 0),
            "reason": "promote_ready_cadre",
        }

    if commander_id == player_id and pending_join_requests:
        viable_request = next(
            (
                entry
                for entry in pending_join_requests
                if float((next((candidate for candidate in game_state.get("players", []) if int(candidate.get("id") or 0) == int(entry.get("player_id") or 0)), {}) or {}).get("balance", 0) or 0)
                >= (0.0 if int(entry.get("hardship_trigger_count", 0) or 0) >= 2 else 150.0)
            ),
            None,
        )
        if viable_request is not None:
            return {
                "type": "plot_join",
                "intent": "accept_request",
                "target_player_id": int(viable_request.get("player_id") or 0),
                "reason": "expand_command_structure",
            }

    if strategic_goal == "seize_property" and strategic_goal_property_id is not None:
        targeted_entry = next(
            (entry for entry in legal_targets if int(entry.get("property_id") or 0) == strategic_goal_property_id),
            None,
        )
        if targeted_entry is not None and player_id in committed_member_ids:
            if float(plot.get("support", 0) or 0) >= 6 and float(plot.get("supply", 0) or 0) >= 4:
                return {
                    "type": "plot_action",
                    "action_type": "attempt_seizure",
                    "property_id": strategic_goal_property_id,
                    "reason": "follow_commander_goal",
                }
            if float(plot.get("support", 0) or 0) >= 2:
                return {
                    "type": "plot_action",
                    "action_type": "agitate_property",
                    "property_id": strategic_goal_property_id,
                    "reason": "prepare_commander_target",
                }

    if strategic_goal == "fortify_region":
        fortify_target = next(
            (
                entry
                for entry in seized_properties
                if not strategic_goal_region or str(entry.get("region") or "") == strategic_goal_region
            ),
            None,
        )
        if fortify_target is not None and float(plot.get("supply", 0) or 0) >= 2:
            return {
                "type": "plot_action",
                "action_type": "fortify_property",
                "property_id": int(fortify_target.get("property_id") or 0),
                "reason": "follow_commander_goal",
            }

    if strategic_goal == "increase_supply" and float(plot.get("support", 0) or 0) >= 2:
        return {
            "type": "plot_action",
            "action_type": "stockpile_supply",
            "region": strategic_goal_region or (region_order[0] if region_order else None),
            "reason": "follow_commander_goal",
        }

    if strategic_goal == "build_support" and float(plot.get("support", 0) or 0) >= 2 and region_order:
        return {
            "type": "plot_action",
            "action_type": "mutual_aid",
            "region": strategic_goal_region or region_order[0],
            "reason": "follow_commander_goal",
        }

    highest_reintegration = int(seized_properties[0].get("reintegration_progress", 0) or 0) if seized_properties else 0
    if seized_properties and highest_reintegration >= 70 and float(plot.get("supply", 0) or 0) >= 3:
        return {
            "type": "plot_action",
            "action_type": "defend_reintegration",
            "property_id": int(seized_properties[0]["property_id"]),
            "reason": "hold_revolutionary_control",
        }

    if unseeded_regions and int(plot.get("stage", 0) or 0) <= 1 and total_seeded_cells < 2 and float(plot.get("support", 0) or 0) >= 3:
        return {
            "type": "plot_action",
            "action_type": "seed_cell",
            "region": unseeded_regions[0],
            "reason": "build_hidden_network",
        }

    if int(plot.get("stage", 0) or 0) >= 2 and float(plot.get("support", 0) or 0) >= 2 and float(plot.get("supply", 0) or 0) < 4:
        return {
            "type": "plot_action",
            "action_type": "stockpile_supply",
            "region": region_order[0] if region_order else None,
            "reason": "reach_seizure_supply_threshold",
        }

    if (
        player_id in committed_member_ids
        and int(plot.get("stage", 0) or 0) >= 3
        and len(legal_targets) >= coordinated_push_target_count
        and coordinated_push_target_count > 1
        and not coordinated_push_ready
    ):
        if float(plot.get("supply", 0) or 0) < (4 * coordinated_push_target_count) and float(plot.get("support", 0) or 0) >= 2:
            return {
                "type": "plot_action",
                "action_type": "stockpile_supply",
                "region": region_order[0] if region_order else None,
                "reason": "prepare_coordinated_seizure_wave",
            }
        if region_order and float(plot.get("support", 0) or 0) >= 2 and float(plot.get("heat", 0) or 0) <= 70:
            return {
                "type": "plot_action",
                "action_type": "mutual_aid",
                "region": region_order[0],
                "reason": "build_support_for_coordinated_seizure_wave",
            }

    if int(plot.get("stage", 0) or 0) >= 4 and clusters and float(plot.get("support", 0) or 0) >= 2 and float(plot.get("supply", 0) or 0) >= 4:
        shallow_cluster = next((entry for entry in clusters if float(entry.get("avg_entrenchment", 0) or 0) < 2.4), None)
        if shallow_cluster is not None:
            return {
                "type": "plot_action",
                "action_type": "increase_entrenchment",
                "cluster_id": shallow_cluster.get("cluster_id"),
                "reason": "stabilize_existing_territory",
            }

    if player_id in committed_member_ids and int(plot.get("stage", 0) or 0) >= 3 and legal_targets and float(plot.get("support", 0) or 0) >= 6 and float(plot.get("supply", 0) or 0) >= 4 and coordinated_push_ready:
        return {
            "type": "plot_action",
            "action_type": "attempt_seizure",
            "property_id": int(legal_targets[0]["property_id"]),
            "reason": "expand_revolutionary_control",
        }

    expansion_cluster = next((entry for entry in clusters if not bool(entry.get("blockaded"))), None)
    adjacent_expansion_exists = any(bool(entry.get("adjacent_to_control")) for entry in legal_targets)
    if (
        expansion_cluster is not None
        and adjacent_expansion_exists
        and int(plot.get("stage", 0) or 0) >= 3
        and float(plot.get("support", 0) or 0) >= 3
        and float(plot.get("supply", 0) or 0) >= 2
    ):
        return {
            "type": "plot_action",
            "action_type": "spread_to_adjacent_territory",
            "cluster_id": expansion_cluster.get("cluster_id"),
            "reason": "prepare_adjacent_expansion",
        }

    fortify_target = next(
        (entry for entry in seized_properties if int(entry.get("entrenchment", 0) or 0) < 2 or int(entry.get("reintegration_progress", 0) or 0) >= 35),
        None,
    )
    if fortify_target is not None and int(plot.get("stage", 0) or 0) >= 3 and float(plot.get("supply", 0) or 0) >= 2:
        return {
            "type": "plot_action",
            "action_type": "fortify_property",
            "property_id": int(fortify_target["property_id"]),
            "reason": "dig_in_after_gains",
        }

    if recruitable_players and int(plot.get("stage", 0) or 0) >= 2 and float(plot.get("support", 0) or 0) >= 4:
        return {
            "type": "plot_action",
            "action_type": "recruit_publicly" if bool(plot.get("public")) else "recruit_sympathizer",
            "target_player_id": int(recruitable_players[0]["player_id"]),
            "reason": "grow_faction_depth",
        }

    # Seeding cells is required for stage advancement — prioritise over mutual_aid at stage ≤ 2
    if unseeded_regions and int(plot.get("stage", 0) or 0) <= 2 and float(plot.get("support", 0) or 0) >= 3:
        return {
            "type": "plot_action",
            "action_type": "seed_cell",
            "region": unseeded_regions[0],
            "reason": "expand_hidden_network",
        }

    if region_order and int(plot.get("stage", 0) or 0) <= 1 and float(plot.get("support", 0) or 0) >= 2:
        return {
            "type": "plot_action",
            "action_type": "mutual_aid",
            "region": region_order[0],
            "reason": "keep_support_alive",
        }

    # Whisper campaign costs only 1 support — use it when too low for anything else at stage 1
    if region_order and int(plot.get("stage", 0) or 0) <= 1 and float(plot.get("support", 0) or 0) >= 1:
        return {
            "type": "plot_action",
            "action_type": "whisper_campaign",
            "region": region_order[0],
            "reason": "build_underground_presence",
        }

    if int(plot.get("stage", 0) or 0) >= 2 and float(plot.get("support", 0) or 0) >= 2:
        agitation_targets = []
        for prop in game_state.get("properties", []):
            prop_id = int(prop.get("id") or 0)
            if prop_id <= 0 or prop.get("owner_id") in {None, player_id}:
                continue
            if property_private_actions_locked(game_state, prop_id):
                continue
            social_entry = dict((social.get("properties") or {}).get(str(prop_id)) or {})
            if bool(social_entry.get("plot_seized")):
                continue
            agitation_targets.append((
                float(social_entry.get("tension", 0) or 0),
                float(prop.get("base_price", 0) or 0),
                prop_id,
            ))
        agitation_targets.sort(reverse=True)
        if agitation_targets:
            return {
                "type": "plot_action",
                "action_type": "agitate_property",
                "property_id": agitation_targets[0][2],
                "reason": "prepare_future_seizure",
            }

    if region_order and int(plot.get("stage", 0) or 0) >= 2 and float(plot.get("support", 0) or 0) >= 2:
        return {
            "type": "plot_action",
            "action_type": "stockpile_supply",
            "region": region_order[0],
            "reason": "prepare_logistics",
        }

    return None


def choose_liberal_democracy_finance_action(
    player: dict,
    game_state: dict,
    profile: dict[str, Any],
    regime: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    regime = regime or build_regime_summary(player, game_state, profile)
    if regime.get("government_type") != "liberal_democracy":
        return None
    archetype = str(profile.get("archetype") or "")
    doctrine = choose_bot_doctrine(player, game_state, profile, regime)
    if archetype != "liberal_democrat" and doctrine != "capital_markets_arbitrage":
        return None

    player_id = int(player.get("id") or 0)
    current_round = int(game_state.get("current_round", 1) or 1)
    redis_key = f"game:{game_state.get('match_id', 0)}:bot:{player_id}:ld_finance_round"
    if redis_client is not None and redis_client.get(redis_key) == str(current_round):
        return None

    balance = float(player.get("balance", 0) or 0)
    soft_reserve = float(regime.get("soft_reserve", 260.0) or 260.0)
    market = dict((game_state.get("econ") or {}).get("market") or {})
    assets = dict(market.get("assets") or {})
    sentiment = float(market.get("sentiment", (game_state.get("econ") or {}).get("market_confidence", 70)) or 70)
    loan_principal = float(player.get("bank_loan_principal", 0) or 0)
    savings = float(player.get("bank_savings_balance", 0) or 0)
    difficulty = normalize_bot_difficulty(profile.get("difficulty") or infer_legacy_difficulty(profile.get("persona")))

    if loan_principal > 0 and balance > soft_reserve + 140.0:
        return {
            "type": "bank_action",
            "bank_action": "repay",
            "amount": round(min(loan_principal, max(50.0, balance - soft_reserve)), 2),
            "reason": "reduce_bank_leverage",
        }

    if savings < 220.0 and balance > soft_reserve + 260.0:
        return {
            "type": "bank_action",
            "bank_action": "deposit",
            "amount": round(min(220.0 - savings, balance - soft_reserve), 2),
            "reason": "build_savings_buffer",
        }

    if difficulty in {"hard", "expert"} and loan_principal <= 0 and balance < soft_reserve and sentiment >= 68.0:
        return {
            "type": "bank_action",
            "bank_action": "loan",
            "amount": 250.0,
            "reason": "use_bank_leverage_for_market_entry",
        }

    investable_cash = balance - soft_reserve
    if investable_cash < 120.0 or not assets:
        return None

    ranked_assets = sorted(
        assets.values(),
        key=lambda asset: (
            str(asset.get("kind") or "") == "stock",
            float(asset.get("price_change_last_round", 0) or 0),
            -float(asset.get("volatility", 0) or 0),
        ),
        reverse=True,
    )
    asset = dict(ranked_assets[0] or {})
    asset_key = str(asset.get("asset_key") or "")
    price = float(asset.get("price", 0) or 0)
    if not asset_key or price <= 0:
        return None
    if str(asset.get("kind") or "") == "stock":
        quantity = max(1, int(min(3, investable_cash // price)))
    else:
        quantity = round(min(2.0, investable_cash / price), 4)
    if quantity <= 0:
        return None
    return {
        "type": "market_order",
        "asset_key": asset_key,
        "side": "buy",
        "quantity": quantity,
        "reason": "liberal_democrat_market_allocation",
    }


def choose_management_action(player: dict, game_state: dict, profile: dict[str, Any]) -> dict[str, Any] | None:
    regime = build_regime_summary(player, game_state, profile)
    if regime.get("difficulty") in {"hard", "expert"}:
        ensure_hidden_bot_partnerships(game_state, current_player_id=int(player.get("id") or 0), current_profile=profile)
    doctrine = choose_bot_doctrine(player, game_state, profile, regime)
    debt_action = choose_liquidation_action(player, game_state, profile)
    if debt_action is not None:
        return debt_action

    plot_action = choose_plot_management_action(player, game_state, profile, regime)
    if plot_action is not None:
        return plot_action

    emergency_reform = choose_emergency_reform(player, game_state, profile, regime)
    if emergency_reform is not None:
        return emergency_reform

    negotiation_move = choose_negotiation_move(player, game_state, profile, regime)
    if negotiation_move is not None:
        return negotiation_move

    finance_action = choose_liberal_democracy_finance_action(player, game_state, profile, regime)
    if finance_action is not None:
        return finance_action

    lobbying_move = choose_lobbying_move(player, game_state, profile)
    if lobbying_move is not None and doctrine in {"policy_shaping", "treasury_rebuild_then_leverage"}:
        return {"type": "lobby", **lobbying_move}
    if lobbying_move is not None and doctrine == "social_democracy_leverage" and (
        not regime["bailout_enabled"]
        or regime["treasury_balance"] < regime["expected_bailout_amount"] * 1.25
    ):
        return {"type": "lobby", **lobbying_move}

    unmortgage_target = choose_unmortgage_target(player, game_state, profile)
    if unmortgage_target is not None:
        return {"type": "unmortgage", "property_id": unmortgage_target["id"]}

    development_target = choose_development_target(player, game_state, profile)
    if development_target is not None:
        return {"type": "develop", "property_id": development_target["id"]}

    if lobbying_move is not None:
        return {"type": "lobby", **lobbying_move}

    deal_move = choose_deal_proposal(player, game_state, profile)
    if deal_move is not None:
        return {"type": "deal", **deal_move}

    trade_move = choose_trade_proposal(player, game_state, profile)
    if trade_move is not None:
        return {"type": "trade", **trade_move}

    return None


def choose_liquidation_action(player: dict, game_state: dict, profile: dict[str, Any]) -> dict[str, Any] | None:
    total_debt = max(
        0.0,
        -float(player.get("balance", 0) or 0) + get_total_pending_player_debt(game_state, player["id"]),
    )
    if total_debt <= 0 and not has_pending_player_debt(game_state, player["id"]):
        return None

    regime = build_regime_summary(player, game_state, profile)
    if (
        regime["rescue_viable"]
        and regime["distress_state"] in {"leveraged", "recoverable_distress"}
        and regime["allowed_negative_exposure"] >= total_debt
        and _player_has_engine_assets(player["id"], game_state)
    ):
        return {"type": "bankruptcy", "reason": "recoverable_distress_bailout"}

    sellable_house = _select_house_sale(player, game_state)
    if sellable_house is not None:
        return {"type": "sell_house", "property_id": sellable_house["id"]}

    mortgage_target = _select_mortgage_target(player, game_state, profile)
    if mortgage_target is not None:
        return {"type": "mortgage", "property_id": mortgage_target["id"]}

    if profile["bankruptcy"].get("declare_after_no_assets", True):
        return {"type": "bankruptcy"}
    return None


def choose_unmortgage_target(player: dict, game_state: dict, profile: dict[str, Any]) -> dict[str, Any] | None:
    regime = build_regime_summary(player, game_state, profile)
    doctrine = choose_bot_doctrine(player, game_state, profile, regime)
    balance = float(player.get("balance", 0) or 0)
    reserve = max(float(profile["liquidity"]["unmortgage_cash_buffer"]), regime["soft_reserve"])
    if regime["government_type"] == "liberal_democracy" and regime.get("capital_yield_capture_score", 0) >= 0.25:
        reserve = max(reserve, float(regime.get("capital_yield_reserve_floor", reserve) or reserve))
    if balance <= reserve and regime["effective_cash"] <= 0:
        return None

    candidates = []
    for prop in get_player_properties(player["id"], game_state):
        if not prop.get("is_mortgaged"):
            continue
        cost = round(float(prop.get("base_price", 0) or 0) * 0.55, 2)
        if balance - cost < reserve and regime["effective_cash"] - cost < 0:
            continue
        score = estimate_property_value(player, prop, game_state, profile) - cost
        if doctrine in {"development_snowball", "social_democracy_leverage"} and has_full_monopoly(prop, game_state):
            score += 45.0
        candidates.append((score, prop))

    if not candidates:
        return None
    candidates.sort(key=lambda entry: entry[0], reverse=True)
    return candidates[0][1]


def choose_development_target(player: dict, game_state: dict, profile: dict[str, Any]) -> dict[str, Any] | None:
    regime = build_regime_summary(player, game_state, profile)
    doctrine = choose_bot_doctrine(player, game_state, profile, regime)
    balance = float(player.get("balance", 0) or 0)
    econ = game_state.get("econ", {})
    buffer = float(profile["development"]["minimum_cash_after_develop"])
    reserve_floor = float(profile["liquidity"]["reserve_cash_floor"])
    if doctrine == "social_democracy_leverage":
        buffer = max(0.0, buffer - (regime["state_backed_credit"] * 0.45) - (regime["welfare_recovery_credit"] * 0.35))
    elif doctrine == "treasury_rebuild_then_leverage":
        buffer = max(reserve_floor * 0.8, buffer * 0.76)
    elif doctrine == "monopoly_rush":
        buffer = max(reserve_floor * 0.72, buffer * 0.78)
    wealthy = (
        balance >= float(profile["liquidity"]["wealth_threshold"])
        or regime["effective_cash"] >= float(profile["development"]["minimum_cash_after_develop"]) * 0.35
    )
    if wealthy:
        buffer = max(reserve_floor, buffer * 0.65)
    if regime["government_type"] == "liberal_democracy":
        yield_floor = float(regime.get("capital_yield_reserve_floor", reserve_floor) or reserve_floor)
        if doctrine == "capital_markets_arbitrage":
            buffer = max(buffer, yield_floor + 40.0)
        else:
            buffer = max(buffer, yield_floor * 0.85)
    if balance <= buffer and regime["effective_cash"] <= 0 and regime["allowed_negative_exposure"] <= 0:
        return None

    stability = float(econ.get("stability", 0.7) or 0.7)
    tax_multiplier = float(econ.get("tax_multiplier", 0.15) or 0.15)
    best_candidate = None
    best_score = 0.0
    social_props = (game_state.get("social") or {}).get("properties") or {}
    for prop in get_player_properties(player["id"], game_state):
        if prop.get("property_type") != "property" or prop.get("is_mortgaged"):
            continue
        max_dev_level = player.get("plot_max_development_level")
        if player.get("plot_locked_poverty") and max_dev_level is not None and int(prop.get("dev_level", 0) or 0) >= int(max_dev_level):
            continue
        if property_private_actions_locked(game_state, prop.get("id")):
            continue
        if property_is_fully_developed(prop, game_state) or not has_full_monopoly(prop, game_state):
            continue

        social_entry = dict(social_props.get(str(prop.get("id"))) or {})
        if social_entry.get("incident_type") in {"strike", "uprising", "revolution"}:
            continue
        if float(social_entry.get("tension", 0) or 0) >= 65.0:
            continue
        if float(social_entry.get("territory_instability", 0) or 0) >= 75.0:
            continue

        group_props = [
            entry for entry in game_state.get("properties", [])
            if entry.get("group_color") == prop.get("group_color") and entry.get("property_type") == "property"
        ]
        min_group_level = min(int(group_prop.get("dev_level", 0) or 0) for group_prop in group_props)
        if int(prop.get("dev_level", 0) or 0) != min_group_level:
            continue

        cost = calculate_development_cost(
            prop.get("base_price", 0),
            int(prop.get("dev_level", 0) or 0) + 1,
            game_state,
        )
        projected_cash = balance - cost
        projected_effective = regime["effective_cash"] - cost
        if projected_cash < -regime["allowed_negative_exposure"] and projected_effective < -max(20.0, regime["allowed_negative_exposure"] * 0.35):
            continue
        if projected_cash < buffer and projected_effective < 0 and not wealthy and doctrine not in {"social_democracy_leverage", "development_snowball"}:
            continue

        current_rent = calculate_rent_with_dev(prop, econ, game_state)
        projected = dict(prop)
        projected["dev_level"] = int(prop.get("dev_level", 0) or 0) + 1
        projected_rent = calculate_rent_with_dev(projected, econ, game_state)
        rent_delta = projected_rent - current_rent
        roi = rent_delta / max(cost, 1.0)
        surplus_factor = max(0.0, (projected_cash - buffer) / max(cost, 1.0))
        score = (roi * (1.05 + float(profile["core"]["development_focus"]))) + float(profile["development"]["group_focus_bonus"])
        score += min(0.45, surplus_factor * 0.12)
        score += min(0.3, rent_delta / max(80.0, cost * 3.0))
        if int(prop.get("dev_level", 0) or 0) == 0:
            score += 0.12
        if econ.get("rent_control_active"):
            score -= float(profile["development"]["rent_control_build_penalty"])
        score -= max(0.0, tax_multiplier - float(profile["development"]["tax_drag_limit"])) * 0.35
        score -= max(0.0, float(profile["development"]["stability_floor"]) - stability) * 0.45
        score -= regime["macro_stress_score"] * (0.18 if regime["game_mode"] == "chaos" else 0.08)
        score -= min(0.38, float(social_entry.get("tension", 0) or 0) / 100.0 * 0.42)
        score -= min(0.22, float(social_entry.get("territory_instability", 0) or 0) / 100.0 * 0.28)
        score -= regime.get("social_civil_risk_score", 0) * 0.18
        if regime["government_type"] == "liberal_democracy":
            score += regime.get("private_equity_edge_score", 0) * 0.10
            score -= regime.get("capital_yield_capture_score", 0) * 0.14
            score -= regime.get("market_overheat_score", 0) * 0.12
            if doctrine == "capital_markets_arbitrage":
                score -= 0.10
                if roi >= 0.24:
                    score += 0.08
        if doctrine == "social_democracy_leverage":
            score += regime["state_protection_score"] * 0.42
            if projected_cash < 0:
                score += regime["bailout_reliance_score"] * 0.34
                score += regime["welfare_reliance_score"] * 0.2
        elif doctrine == "treasury_rebuild_then_leverage":
            score -= 0.08
        elif doctrine == "monopoly_rush":
            score += 0.14
        elif doctrine == "development_snowball":
            score += 0.18
        if regime["game_mode"] == "speed":
            score += min(0.24, roi * 0.28)
        if regime["game_mode"] == "cooperative" and regime["active_deal_count"] > 0:
            score += 0.04
        if projected_cash < 0 and regime["allowed_negative_exposure"] <= 0:
            score -= 0.3
        if score > best_score:
            best_score = score
            best_candidate = {
                **prop,
                "bot_score": round(score, 4),
                "bot_reason": doctrine,
                "bot_projected_cash": round(projected_cash, 2),
            }

    if best_candidate is None:
        return None
    if best_score <= 0.02 and not wealthy and doctrine != "social_democracy_leverage":
        return None
    return best_candidate


def choose_deal_proposal(player: dict, game_state: dict, profile: dict[str, Any]) -> dict[str, Any] | None:
    settings = game_state.get("settings", {})
    if not settings.get("deals_enabled", settings.get("teams_enabled", True)):
        return None

    regime = build_regime_summary(player, game_state, profile)
    doctrine = choose_bot_doctrine(player, game_state, profile, regime)
    if regime["pending_deal_outgoing_count"] > 0:
        return None

    max_active_deals = int(settings.get("max_active_deals_per_player", 3) or 3)
    if regime["active_deal_count"] >= max_active_deals:
        return None

    buildable_props = [
        prop for prop in get_player_properties(player["id"], game_state)
        if prop.get("property_type") == "property"
        and not prop.get("is_mortgaged")
        and has_full_monopoly(prop, game_state)
        and not property_is_fully_developed(prop, game_state)
        and not property_private_actions_locked(game_state, prop.get("id"))
    ]
    want_investment = bool(settings.get("private_equity_enabled", True)) and bool(buildable_props) and (
        regime["investment_opportunity_score"] >= 0.32
        or (regime["government_type"] == "liberal_democracy" and regime.get("private_equity_edge_score", 0) >= 0.26)
    )
    need_protection = regime["immunity_need_score"] >= 0.4

    best_proposal = None
    best_score = 0.0
    for other in game_state.get("players", []):
        other_id = int(other.get("id") or 0)
        if other_id <= 0 or other_id == int(player["id"]) or other.get("is_bankrupt"):
            continue
        context = _pairwise_deal_context(int(player["id"]), other_id, game_state)
        if context["active_deal_count"] > 0 or context["pending_incoming"] > 0 or context["pending_outgoing"] > 0:
            continue

        clauses = []
        threat_from_other = _estimate_owner_rent_threat(other_id, game_state)
        threat_to_other = _estimate_owner_rent_threat(int(player["id"]), game_state)
        if need_protection and threat_from_other >= 45.0:
            clauses.append({
                "type": "rent_discount",
                "grantor_id": other_id,
                "beneficiary_id": int(player["id"]),
                "scope": {"mode": "all_grantor_properties"},
                "config": {"rent_multiplier": 0.5 if threat_from_other >= 95.0 else 0.65},
                "deadline": {"metric": "beneficiary_turns", "initial": 3 if threat_from_other >= 95.0 else 2},
            })
            if threat_to_other >= 25.0:
                clauses.append({
                    "type": "rent_discount",
                    "grantor_id": int(player["id"]),
                    "beneficiary_id": other_id,
                    "scope": {"mode": "all_grantor_properties"},
                    "config": {"rent_multiplier": 0.8 if threat_to_other < threat_from_other else 0.72},
                    "deadline": {"metric": "beneficiary_turns", "initial": 1},
                })

        if not clauses and want_investment and float(other.get("balance", 0) or 0) >= 250.0:
            focus_prop = sorted(buildable_props, key=lambda prop: float(prop.get("base_price", 0) or 0), reverse=True)[0]
            escrow_amount = round(min(float(other.get("balance", 0) or 0) * 0.22, max(150.0, float(focus_prop.get("base_price", 0) or 0))), 2)
            pe_bonus = float(regime.get("private_equity_bonus_multiplier", 1.0) or 1.0)
            payout_multiple = 1.35 if regime["government_type"] == "liberal_democracy" and pe_bonus > 1.04 else 1.45
            profit_share_percent = 0.28 if regime["government_type"] == "liberal_democracy" and pe_bonus > 1.04 else 0.30
            clauses.append({
                "type": "development_investment",
                "investor_id": other_id,
                "recipient_id": int(player["id"]),
                "scope": {"mode": "selected_group_colors", "group_colors": [focus_prop.get("group_color")]},
                "config": {
                    "escrow_amount": escrow_amount,
                    "profit_share_percent": profit_share_percent,
                    "max_payout": round(escrow_amount * payout_multiple, 2),
                },
                "deadline": {"metric": "beneficiary_rotations", "initial": 2},
            })

        if not clauses:
            continue

        proposal = {
            "counterparty_id": other_id,
            "title": (
                "Build loan"
                if clauses[0]["type"] == "development_investment"
                else "Short-term risk pact"
            ),
            "clauses": clauses,
        }
        my_score = score_deal_proposal(player, proposal, game_state, profile)
        other_score = score_deal_proposal(other, proposal, game_state, profile)
        total_score = my_score + max(-5.0, other_score * 0.2)
        minimum_my_score = 6.0
        if regime["government_type"] == "liberal_democracy" and any(clause.get("type") == "development_investment" for clause in clauses):
            minimum_my_score = 4.0 if doctrine == "capital_markets_arbitrage" else 5.0
        if my_score >= minimum_my_score and other_score >= -10.0 and total_score > best_score:
            best_proposal = proposal
            best_score = total_score

    return best_proposal


def estimate_property_value(player: dict, prop: dict, game_state: dict, profile: dict[str, Any]) -> float:
    regime = build_regime_summary(player, game_state, profile)
    doctrine = choose_bot_doctrine(player, game_state, profile, regime)
    econ = game_state.get("econ", {})
    acquisition = profile["acquisition"]
    price = float(prop.get("current_value") or prop.get("base_price") or 0)
    if price <= 0:
        return 0.0

    balance = float(player.get("balance", 0) or 0)
    value = price * float(acquisition["base_price_weight"])
    completion_ratio = monopoly_completion_ratio(player["id"], prop, game_state)
    opponent_completion = monopoly_completion_ratio_for_other_owner(prop, game_state)
    planning_horizon = int(profile.get("skill", {}).get("planning_horizon", 4) or 4)

    if prop.get("property_type") == "transit":
        owned_transits = count_transits_owned_by(player["id"], game_state)
        transit_rent = calculate_transit_rent(player["id"], {**game_state, "properties": _with_owner_override(game_state.get("properties", []), prop["id"], player["id"])})
        value += transit_rent * float(acquisition["transit_turns_weight"])
        value += price * float(acquisition["transit_synergy_bonus"]) * owned_transits
    else:
        expected_rent = calculate_rent_with_dev({**prop, "owner_id": player["id"]}, econ, game_state)
        value += expected_rent * (float(acquisition["rent_turns_weight"]) + (planning_horizon * 0.12))
        value += price * completion_ratio * float(acquisition["partial_set_bonus"])
        if completion_ratio >= 1.0:
            value += price * float(acquisition["monopoly_completion_bonus"])
        if opponent_completion >= 1.0:
            value += price * float(acquisition["monopoly_denial_bonus"]) * (1.0 + float(profile["core"].get("denial_focus", 0.4) or 0.4) * 0.35)
        if doctrine == "monopoly_rush" and completion_ratio >= 0.67:
            value += price * 0.12
        if doctrine in {"development_snowball", "social_democracy_leverage"}:
            value += price * regime["state_protection_score"] * 0.12

    value += price * float(econ.get("inflation_rate", 0) or 0) * float(acquisition["inflation_capture_weight"])
    value -= price * float(econ.get("tax_multiplier", 0) or 0) * float(acquisition["tax_penalty_weight"])
    if econ.get("rent_control_active") and prop.get("property_type") == "property":
        value -= price * float(acquisition["rent_control_penalty"])
    if str(game_state.get("settings", {}).get("game_mode", "standard") or "standard").lower() == "chaos":
        value -= price * (float(acquisition["chaos_reserve_penalty"]) + regime["macro_stress_score"] * 0.05)
    elif regime["game_mode"] == "speed":
        value += price * 0.08
    if int(game_state.get("current_round", 1) or 1) >= 15:
        value *= float(acquisition["late_game_multiplier"])
    if balance < float(profile["liquidity"]["reserve_cash_floor"]):
        value *= 0.88
    owner = _find_player(game_state, prop.get("owner_id"))
    if _players_are_allied(player, owner, game_state):
        value *= 0.82
    return round(value, 2)


def monopoly_completion_ratio(player_id: int, prop: dict, game_state: dict) -> float:
    if prop.get("property_type") != "property" or not prop.get("group_color"):
        return 0.0
    group = [
        entry for entry in game_state.get("properties", [])
        if entry.get("group_color") == prop.get("group_color") and entry.get("property_type") == "property"
    ]
    if not group:
        return 0.0
    owned = sum(1 for entry in group if entry.get("owner_id") == player_id)
    if prop.get("owner_id") != player_id:
        owned += 1
    return round(min(1.0, owned / len(group)), 4)


def monopoly_completion_ratio_for_other_owner(prop: dict, game_state: dict) -> float:
    owner_id = prop.get("owner_id")
    if owner_id is None or prop.get("property_type") != "property" or not prop.get("group_color"):
        return 0.0
    return monopoly_completion_ratio(owner_id, prop, game_state)


def monopoly_property_count(player_id: int, game_state: dict) -> int:
    return sum(1 for prop in get_player_properties(player_id, game_state) if has_full_monopoly(prop, game_state))


def _score_lobby_pledges_for_player(
    player: dict,
    pledges: list[dict] | None,
    game_state: dict,
    profile: dict[str, Any],
) -> float:
    pledge_items = pledges or []
    if not pledge_items:
        return 0.0

    settings = game_state.get("settings", {})
    econ = game_state.get("econ", {})
    if not settings.get("lobbying_enabled", True) or econ.get("gov_type") == "minarchism":
        return 0.0

    regime = build_regime_summary(player, game_state, profile)
    doctrine = choose_bot_doctrine(player, game_state, profile, regime)

    active_players = [entry for entry in game_state.get("players", []) if not entry.get("is_bankrupt")]
    avg_balance = sum(float(entry.get("balance", 0) or 0) for entry in active_players) / max(len(active_players), 1)
    net_worth = calculate_net_worth(player, game_state)
    distressed = (
        float(player.get("balance", 0) or 0) <= float(profile["lobbying"]["distress_balance_threshold"])
        or net_worth < avg_balance * 0.9
    )
    wealthy = (
        float(player.get("balance", 0) or 0) >= float(profile["liquidity"]["wealth_threshold"])
        or net_worth > avg_balance * 1.35
    )

    total_value = 0.0
    for pledge in pledge_items:
        amount = float(pledge.get("amount", 0) or 0)
        target = resolve_lobbying_target(
            axis=pledge.get("axis"),
            direction=pledge.get("direction"),
            target=pledge.get("target"),
            target_stat=pledge.get("target_stat"),
        )
        multiplier = 0.45
        if distressed and target in {"welfare_increase", "tax_multiplier_decrease", "economic_stimulus"}:
            multiplier = 1.0
        elif wealthy and target in {"welfare_decrease", "tax_multiplier_increase", "deregulate_housing"}:
            multiplier = 0.9
        elif target == "stabilization_fund":
            multiplier = 0.7
        if doctrine in {"social_democracy_leverage", "policy_shaping", "treasury_rebuild_then_leverage"}:
            if target == "bailout_enable":
                multiplier = max(multiplier, 1.15)
                if regime["difficulty"] == "expert":
                    multiplier += 0.1
                elif regime["difficulty"] == "hard":
                    multiplier += 0.04
            elif target in {"welfare_increase", "tax_multiplier_increase", "stabilization_fund"}:
                multiplier = max(multiplier, 0.92)
        if doctrine == "monopoly_rush" and target == "deregulate_housing":
            multiplier = max(multiplier, 0.88)
        if regime["game_mode"] == "cooperative" and target in {"economic_stimulus", "stabilization_fund"}:
            multiplier += 0.08
        total_value += amount * multiplier

    return round(total_value, 2)


def _select_trade_lobby_pledge(
    offerer: dict,
    receiver: dict,
    game_state: dict,
    profile: dict[str, Any],
    max_amount: float,
) -> dict[str, Any] | None:
    settings = game_state.get("settings", {})
    econ = game_state.get("econ", {})
    if not settings.get("lobbying_enabled", True) or econ.get("gov_type") == "minarchism":
        return None

    regime = build_regime_summary(offerer, game_state, profile)
    doctrine = choose_bot_doctrine(offerer, game_state, profile, regime)

    minimum_contribution = float(profile["lobbying"]["minimum_contribution"])
    pledge_cap = round(min(max(0.0, max_amount), float(offerer.get("balance", 0) or 0) * float(profile["liquidity"]["max_lobby_share"])), 2)
    if pledge_cap < minimum_contribution:
        return None

    active_players = [entry for entry in game_state.get("players", []) if not entry.get("is_bankrupt")]
    avg_balance = sum(float(entry.get("balance", 0) or 0) for entry in active_players) / max(len(active_players), 1)
    receiver_net_worth = calculate_net_worth(receiver, game_state)
    receiver_balance = float(receiver.get("balance", 0) or 0)

    axis = None
    direction = None
    if doctrine in {"social_democracy_leverage", "policy_shaping", "treasury_rebuild_then_leverage"} and regime["government_type"] == "social_democracy":
        if not regime["bailout_enabled"] and regime["difficulty"] in {"hard", "expert"}:
            axis = "bailouts"
            direction = "enable"
        elif regime["treasury_balance"] < max(450.0, regime["expected_bailout_amount"] * 1.25):
            axis = "tax_multiplier"
            direction = "increase"
        elif regime["welfare_rate"] < 28.0:
            axis = "welfare_rate"
            direction = "increase"
    elif receiver_balance <= float(profile["lobbying"]["distress_balance_threshold"]) or receiver_net_worth < avg_balance * 0.9:
        axis = "welfare_rate"
        direction = "increase"
    elif receiver_balance <= float(profile["liquidity"]["poor_threshold"]) * 1.4:
        axis = "tax_multiplier"
        direction = "decrease"
    else:
        axis = "treasury_posture"
        direction = "rebuild"

    target = resolve_lobbying_target(axis=axis, direction=direction)
    if target is None:
        return None

    pledge_amount = round(max(minimum_contribution, min(pledge_cap, max_amount)), 2)
    pledge_amount = round(max(minimum_contribution, (pledge_amount // LOBBY_INCREMENT) * LOBBY_INCREMENT or minimum_contribution), 2)
    if pledge_amount > pledge_cap:
        pledge_amount = round(pledge_cap, 2)
    if pledge_amount < minimum_contribution:
        return None

    return {
        "axis": axis,
        "direction": direction,
        "target": target,
        "amount": pledge_amount,
    }


def _trade_value_delta(player_id: int, owner_id: int, prop: dict, game_state: dict, profile: dict[str, Any]) -> float:
    current_player = next((entry for entry in game_state.get("players", []) if entry.get("id") == player_id), None)
    if current_player is None:
        return 0.0
    owner = _find_player(game_state, owner_id)
    if owner is not None and _players_are_allied(current_player, owner, game_state):
        return 0.0
    regime = build_regime_summary(current_player, game_state, profile)
    doctrine = choose_bot_doctrine(current_player, game_state, profile, regime)
    value = estimate_property_value(current_player, prop, game_state, profile)
    if monopoly_completion_ratio(player_id, prop, game_state) >= 1.0:
        value += float(profile["trade"]["monopoly_trade_bonus"])
    if prop.get("property_type") == "transit":
        value += float(profile["trade"]["transit_trade_bonus"])
    if opponent_completion := monopoly_completion_ratio(owner_id, prop, game_state):
        denial_weight = float(profile.get("core", {}).get("denial_focus", 0.4) or 0.4)
        if doctrine in {"policy_shaping", "distress_recovery"}:
            denial_weight += 0.18
        value += float(prop.get("base_price", 0) or 0) * opponent_completion * denial_weight
    if doctrine == "social_democracy_leverage" and has_full_monopoly(prop, game_state):
        value += regime["state_protection_score"] * 55.0
    if regime["game_mode"] == "speed" and monopoly_completion_ratio(player_id, prop, game_state) >= 0.67:
        value += 35.0
    return round(value, 2)


def _select_house_sale(player: dict, game_state: dict) -> dict[str, Any] | None:
    candidates = []
    for prop in get_player_properties(player["id"], game_state):
        level = int(prop.get("dev_level", 0) or 0)
        if prop.get("property_type") != "property" or level <= 0:
            continue
        group_props = [
            entry for entry in game_state.get("properties", [])
            if entry.get("group_color") == prop.get("group_color") and entry.get("property_type") == "property"
        ]
        max_level = max(int(entry.get("dev_level", 0) or 0) for entry in group_props)
        if level < max_level:
            continue
        candidates.append((float(prop.get("base_price", 0) or 0), prop))
    if not candidates:
        return None
    candidates.sort(key=lambda entry: entry[0], reverse=True)
    return candidates[0][1]


def _select_mortgage_target(player: dict, game_state: dict, profile: dict[str, Any]) -> dict[str, Any] | None:
    regime = build_regime_summary(player, game_state, profile)
    candidates = []
    for prop in get_player_properties(player["id"], game_state):
        if prop.get("is_mortgaged") or int(prop.get("dev_level", 0) or 0) > 0:
            continue
        priority = 0.0
        if prop.get("property_type") == "transit":
            priority += 0.35
        elif has_full_monopoly(prop, game_state):
            priority += 1.3
            if regime["rescue_viable"]:
                priority += 0.55
        else:
            owner_override_properties = _with_owner_override(game_state.get("properties", []), prop["id"], None)
            denial_value = 0.0
            for opponent in game_state.get("players", []):
                if opponent.get("id") == player["id"] or opponent.get("is_bankrupt"):
                    continue
                denial_ratio = monopoly_completion_ratio(opponent["id"], {**prop, "owner_id": None}, {**game_state, "properties": owner_override_properties})
                denial_value = max(denial_value, denial_ratio)
            if denial_value >= 1.0:
                priority += 0.68
            elif denial_value >= 0.67:
                priority += 0.52
            else:
                priority += 0.2
        price = float(prop.get("base_price", 0) or 0)
        candidates.append((priority, price, prop))
    if not candidates:
        return None
    candidates.sort(key=lambda entry: (entry[0], entry[1]))
    return candidates[0][2]


def _with_owner_override(properties: list[dict], prop_id: int, owner_id: int) -> list[dict]:
    return [
        {**prop, "owner_id": owner_id} if prop.get("id") == prop_id else dict(prop)
        for prop in properties
    ]


def _get_active_auction_property_ids(match_id: int) -> list[int]:
    pattern = f"game:{match_id}:auction:*:active"
    property_ids = []
    for key in redis_client.keys(pattern):
        try:
            property_ids.append(int(key.split(":")[-2]))
        except (TypeError, ValueError, IndexError):
            continue
    return sorted(set(property_ids))


def has_active_auction(match_id: int) -> bool:
    return bool(_get_active_auction_property_ids(match_id))


def _generate_bot_username() -> str:
    for _ in range(50):
        base = random.choice(BOT_NAME_PARTS)
        suffix = f"{random.randint(10, 99)}"
        username = f"{base[:10-len(suffix)]}{suffix}"[:12]
        if not User.query.filter_by(username=username).first():
            return username
    return f"Bot{uuid.uuid4().hex[:8]}"[:12]


def _freeze_action_value(value: Any) -> Any:
    if isinstance(value, dict):
        return tuple(sorted((key, _freeze_action_value(item)) for key, item in value.items()))
    if isinstance(value, list):
        return tuple(_freeze_action_value(item) for item in value)
    return value


def _action_signature(action: dict[str, Any]) -> tuple[tuple[str, Any], ...]:
    return tuple(sorted((key, _freeze_action_value(value)) for key, value in action.items()))


def _schedule_player_task(
    match_id: int,
    player_id: int,
    task_name: str,
    reason: str,
    *,
    match_player: MatchPlayer | None = None,
    profile: dict[str, Any] | None = None,
    settings: dict | None = None,
    replace_existing: bool = True,
) -> None:
    match_player = match_player or MatchPlayer.query.get(player_id)
    if match_player is None or not match_player.is_bot or match_player.is_bankrupt:
        return

    app_obj = current_app._get_current_object()
    effective_settings = settings
    if effective_settings is None:
        effective_settings = (load_game_state(match_id, redis_client) or {}).get("settings", {})
    profile = profile or ensure_bot_profile(match_player, effective_settings)
    delay = _resolve_delay(profile, task_name)
    token = uuid.uuid4().hex
    redis_key = f"game:{match_id}:bot_task:{player_id}:{task_name}"
    if not replace_existing and redis_client.get(redis_key):
        return
    redis_client.set(redis_key, token, ex=BOT_TASK_TTL_SECONDS)
    socketio.start_background_task(
        _run_scheduled_task,
        app_obj,
        delay,
        redis_key,
        token,
        match_id,
        player_id,
        task_name,
        reason,
    )


def _resolve_delay(profile: dict[str, Any], task_name: str) -> float:
    timing = profile["timing"]
    if task_name.startswith("trade_response") or task_name.startswith("deal_response"):
        return random.uniform(timing["trade_response_min_seconds"], timing["trade_response_max_seconds"])
    if task_name.startswith("auction_bid"):
        return random.uniform(timing["auction_min_seconds"], timing["auction_max_seconds"])
    if task_name == "take_turn":
        return random.uniform(timing["roll_min_seconds"], timing["roll_max_seconds"])
    if task_name in {"property_decision", "manage_turn"}:
        return random.uniform(timing["decision_min_seconds"], timing["decision_max_seconds"])
    return random.uniform(timing["management_min_seconds"], timing["management_max_seconds"])


def _run_scheduled_task(
    app_obj,
    delay: float,
    redis_key: str,
    token: str,
    match_id: int,
    player_id: int,
    task_name: str,
    reason: str,
) -> None:
    socketio.sleep(delay)
    with app_obj.app_context():
        if redis_client.get(redis_key) != token:
            return
        redis_client.delete(redis_key)
        try:
            if task_name == "take_turn":
                _execute_take_turn(match_id, player_id)
            elif task_name == "manage_turn":
                _execute_manage_turn(match_id, player_id)
            elif task_name == "property_decision":
                _execute_property_decision(match_id, player_id)
            elif task_name.startswith("trade_response:"):
                _execute_trade_response(match_id, player_id, int(task_name.split(":", 1)[1]))
            elif task_name.startswith("deal_response:"):
                _execute_deal_response(match_id, player_id, int(task_name.split(":", 1)[1]))
            elif task_name.startswith("auction_bid:"):
                _execute_auction_bid(match_id, player_id, int(task_name.split(":", 1)[1]))
        except Exception as exc:
            current_app.logger.exception(
                "Bot task failed for match=%s player=%s task=%s reason=%s: %s",
                match_id,
                player_id,
                task_name,
                reason,
                exc,
            )


def _execute_take_turn(match_id: int, player_id: int) -> None:
    if has_active_auction(match_id):
        return

    match_player = MatchPlayer.query.get(player_id)
    if match_player is None or not match_player.is_bot or match_player.is_bankrupt:
        return
    attempted_liquidations: set[tuple[tuple[str, Any], ...]] = set()
    while True:
        game_state = load_game_state(match_id, redis_client)
        if not game_state or game_state.get("status") != "active" or game_state.get("game_paused"):
            return
        if game_state.get("current_player_id") != player_id or game_state.get("dice_rolled_this_turn", False):
            return

        profile = ensure_bot_profile(match_player, game_state.get("settings", {}))
        player = next((entry for entry in game_state.get("players", []) if entry.get("id") == player_id), None)
        if player is None:
            return

        liquidation = choose_liquidation_action(player, game_state, profile)
        if liquidation is None:
            break

        liquidation_signature = _action_signature(liquidation)
        if liquidation_signature in attempted_liquidations:
            if float(player.get("balance", 0) or 0) < 0 or has_pending_player_debt(game_state, player_id):
                _bot_declare_bankruptcy(match_id, player_id)
            return

        attempted_liquidations.add(liquidation_signature)
        if _execute_management_action(match_id, player_id, liquidation, game_state):
            return

    game_state = load_game_state(match_id, redis_client)
    if not game_state or game_state.get("status") != "active" or game_state.get("game_paused"):
        return
    if game_state.get("current_player_id") != player_id or game_state.get("dice_rolled_this_turn", False):
        return

    profile = ensure_bot_profile(match_player, game_state.get("settings", {}))
    player = next((entry for entry in game_state.get("players", []) if entry.get("id") == player_id), None)
    if player is None:
        return

    if float(player.get("balance", 0) or 0) < 0 or has_pending_player_debt(game_state, player_id):
        _bot_declare_bankruptcy(match_id, player_id)
        return

    if player.get("is_jailed"):
        decision = choose_jail_resolution(player, game_state, profile)
        if decision == "card":
            _bot_use_jail_card(match_id, player_id)
            return
        if decision == "pay":
            _bot_pay_jail_bail(match_id, player_id)
            return

    process_turn(
        match_id=match_id,
        player_id=player_id,
        game_state=game_state,
        redis_client=redis_client,
        socketio_instance=socketio,
    )


def _execute_manage_turn(match_id: int, player_id: int) -> None:
    if has_active_auction(match_id):
        return

    match_player = MatchPlayer.query.get(player_id)
    if match_player is None or not match_player.is_bot or match_player.is_bankrupt:
        return
    attempted_actions: set[tuple[tuple[str, Any], ...]] = set()
    for _ in range(4):
        game_state = load_game_state(match_id, redis_client)
        if not game_state or game_state.get("game_paused") or game_state.get("awaiting_end_turn_player_id") != player_id:
            return

        profile = ensure_bot_profile(match_player, game_state.get("settings", {}))
        player = next((entry for entry in game_state.get("players", []) if entry.get("id") == player_id), None)
        if player is None:
            return

        action = choose_management_action(player, game_state, profile)
        if action is None:
            break

        action_signature = _action_signature(action)
        if action_signature in attempted_actions:
            break
        attempted_actions.add(action_signature)

        if _execute_management_action(match_id, player_id, action, game_state):
            return

    game_state = load_game_state(match_id, redis_client)
    if not game_state or game_state.get("game_paused") or game_state.get("awaiting_end_turn_player_id") != player_id:
        return

    player = next((entry for entry in game_state.get("players", []) if entry.get("id") == player_id), None)
    if player is None:
        return
    if float(player.get("balance", 0) or 0) < 0 or has_pending_player_debt(game_state, player_id):
        _bot_declare_bankruptcy(match_id, player_id)
        return

    current_round = game_state.get("current_round", 1)
    next_state = end_turn(
        game_state,
        player_id,
        {"is_doubles": False},
        match_id,
        redis_client,
        socketio,
        game_state.get("settings", {}),
        game_state.get("econ", {}),
        current_round,
    )
    persist_game_state(next_state, match_id, redis_client)
    broadcast_game_state_snapshot(socketio, match_id, next_state)


def _execute_property_decision(match_id: int, player_id: int) -> None:
    match_player = MatchPlayer.query.get(player_id)
    if match_player is None or not match_player.is_bot or match_player.is_bankrupt:
        return
    attempted_decisions: set[str] = set()
    for _ in range(2):
        game_state = load_game_state(match_id, redis_client)
        if not game_state:
            return
        pending_action = game_state.get("pending_action") or {}
        pending_turn = game_state.get("pending_turn_context") or {}
        pending_type = pending_action.get("type")
        if pending_type not in {"buy_property", "buy_corporate_property"} or pending_action.get("player_id") != player_id:
            return

        profile = ensure_bot_profile(match_player, game_state.get("settings", {}))
        player = next((entry for entry in game_state.get("players", []) if entry.get("id") == player_id), None)
        prop = next((entry for entry in game_state.get("properties", []) if entry.get("id") == pending_action.get("property_id")), None)
        if player is None or prop is None:
            return

        if pending_type == "buy_corporate_property":
            listing_price = float(prop.get("corporate_listing_price", 0) or 0)
            reserve_floor = float(profile.get("liquidity", {}).get("reserve_cash_floor", 260) or 260)
            is_liberal_democrat = str(profile.get("archetype") or "") == "liberal_democrat"
            decision_name = "buy" if is_liberal_democrat and listing_price > 0 and float(player.get("balance", 0) or 0) >= listing_price + reserve_floor else "decline"
        else:
            decision = choose_property_purchase(player, prop, game_state, profile)
            decision_name = str(decision.get("decision") or "decline")
        if decision_name in attempted_decisions:
            break
        attempted_decisions.add(decision_name)

        if decision_name == "buy":
            if pending_type == "buy_corporate_property":
                if _bot_buy_corporate_property(match_id, player_id, prop, pending_turn.get("dice_result")):
                    return
                continue
            if _bot_buy_property(match_id, player_id, prop, pending_turn.get("dice_result")):
                return
            continue
        if pending_type == "buy_corporate_property":
            if _bot_decline_corporate_property(match_id, player_id, prop, pending_turn.get("dice_result")):
                return
            continue
        if _bot_decline_property(match_id, player_id, prop, pending_turn.get("dice_result")):
            return

    game_state = load_game_state(match_id, redis_client)
    if not game_state:
        return
    pending_action = game_state.get("pending_action") or {}
    pending_turn = game_state.get("pending_turn_context") or {}
    if pending_action.get("type") not in {"buy_property", "buy_corporate_property"} or pending_action.get("player_id") != player_id:
        return

    prop = next((entry for entry in game_state.get("properties", []) if entry.get("id") == pending_action.get("property_id")), None)
    if prop is not None and pending_action.get("type") == "buy_corporate_property" and _bot_decline_corporate_property(match_id, player_id, prop, pending_turn.get("dice_result")):
        return
    if prop is not None and _bot_decline_property(match_id, player_id, prop, pending_turn.get("dice_result")):
        return

    _schedule_player_task(match_id, player_id, "property_decision", "property_decision_retry")


def _execute_trade_response(match_id: int, player_id: int, trade_id: int) -> None:
    if has_active_auction(match_id):
        return

    trade = Trade.query.get(trade_id)
    if trade is None or trade.match_id != match_id or trade.status != "pending":
        return
    match_player = MatchPlayer.query.get(player_id)
    if match_player is None or not match_player.is_bot or trade.receiver_id != player_id:
        return

    game_state = load_game_state(match_id, redis_client)
    if not game_state:
        return
    profile = ensure_bot_profile(match_player, game_state.get("settings", {}))
    player = next((entry for entry in game_state.get("players", []) if entry.get("id") == player_id), None)
    if player is None:
        return

    decision = evaluate_trade_response(trade, player, game_state, profile)
    if decision == "accept":
        _bot_accept_trade(match_id, trade)
    else:
        _bot_reject_trade(match_id, trade)


def _execute_deal_response(match_id: int, player_id: int, deal_id: int) -> None:
    deal = Deal.query.get(deal_id)
    if deal is None or deal.match_id != match_id or deal.status != "proposed":
        return

    match_player = MatchPlayer.query.get(player_id)
    if match_player is None or not match_player.is_bot or match_player.is_bankrupt or deal.counterparty_id != player_id:
        return

    game_state = load_game_state(match_id, redis_client)
    if not game_state:
        return
    game_state = attach_deals_snapshot(game_state, match_id)
    profile = ensure_bot_profile(match_player, game_state.get("settings", {}))
    player = next((entry for entry in game_state.get("players", []) if entry.get("id") == player_id), None)
    if player is None:
        return

    player_lookup = {entry.get("id"): entry for entry in game_state.get("players", [])}
    deal_payload = serialize_deal(deal, player_lookup)
    decision = evaluate_deal_response(deal_payload, player, game_state, profile)
    if decision == "accept":
        _bot_accept_deal(match_id, deal)
    else:
        _bot_reject_deal(match_id, deal)


def _execute_auction_bid(match_id: int, player_id: int, prop_id: int) -> None:
    if not redis_client.get(f"game:{match_id}:auction:{prop_id}:active"):
        return
    game_state = load_game_state(match_id, redis_client)
    if not game_state:
        return

    player = next((entry for entry in game_state.get("players", []) if entry.get("id") == player_id), None)
    match_player = MatchPlayer.query.get(player_id)
    prop = next((entry for entry in game_state.get("properties", []) if entry.get("id") == prop_id), None)
    if player is None or match_player is None or prop is None or not match_player.is_bot or player.get("is_bankrupt"):
        return

    profile = ensure_bot_profile(match_player, game_state.get("settings", {}))
    current_bid = float(redis_client.get(f"game:{match_id}:auction:{prop_id}:current_bid") or 0)
    current_bidder_raw = redis_client.get(f"game:{match_id}:auction:{prop_id}:current_bidder")
    if current_bidder_raw and str(current_bidder_raw).isdigit() and int(current_bidder_raw) == player_id:
        return
    bid_amount = choose_auction_bid_amount(player, prop, current_bid, game_state, profile)
    if bid_amount is None:
        return

    redis_client.set(f"game:{match_id}:auction:{prop_id}:current_bid", str(bid_amount))
    redis_client.set(f"game:{match_id}:auction:{prop_id}:current_bidder", str(player_id))
    redis_client.rpush(
        f"game:{match_id}:auction:{prop_id}:bids",
        str({"player_id": player_id, "amount": bid_amount, "bot": True}),
    )
    socketio.emit(
        "auction_bid",
        {
            "player_id": player_id,
            "player_name": player.get("username"),
            "amount": bid_amount,
            "property_id": prop_id,
            "property_name": prop.get("name"),
            "countdown_seconds": 5,
        },
        room=str(match_id),
    )
    reset_auction_timer(match_id, prop_id, redis_client, socketio)
    queue_bot_auction_reactions(match_id, game_state=game_state, reason="bot_bid")


def _execute_management_action(match_id: int, player_id: int, action: dict[str, Any], game_state: dict | None = None) -> bool:
    action_type = action.get("type")
    if action_type == "sell_house":
        return _bot_sell_house(match_id, player_id, int(action["property_id"]))
    if action_type == "mortgage":
        return _bot_mortgage_property(match_id, player_id, int(action["property_id"]))
    if action_type == "bankruptcy":
        return _bot_declare_bankruptcy(match_id, player_id)
    if action_type == "unmortgage":
        return _bot_unmortgage_property(match_id, player_id, int(action["property_id"]))
    if action_type == "develop":
        return _bot_develop_property(match_id, player_id, int(action["property_id"]))
    if action_type == "lobby":
        return _bot_submit_lobby(match_id, player_id, action)
    if action_type == "negotiate":
        return _bot_submit_negotiation(match_id, player_id, action)
    if action_type == "emergency_reform":
        return _bot_apply_emergency_reform(match_id, player_id, action)
    if action_type == "market_order":
        return _bot_submit_market_order(match_id, player_id, action)
    if action_type == "bank_action":
        return _bot_apply_bank_action(match_id, player_id, action)
    if action_type == "plot_start":
        return _bot_plot_start(match_id, player_id)
    if action_type == "plot_action":
        return _bot_plot_action(match_id, player_id, action)
    if action_type == "plot_join":
        return _bot_plot_join(match_id, player_id, action)
    if action_type == "plot_leave":
        return _bot_plot_leave(match_id, player_id, action)
    if action_type == "plot_counter_action":
        return _bot_plot_counter_action(match_id, player_id, action)
    if action_type == "deal":
        return _bot_propose_deal(match_id, player_id, action)
    if action_type == "trade":
        return _bot_propose_trade(match_id, player_id, action)
    return False


def _bot_buy_property(match_id: int, player_id: int, prop: dict, dice_result: dict | None) -> bool:
    game_state = load_game_state(match_id, redis_client)
    if not game_state:
        return False
    player = next((entry for entry in game_state.get("players", []) if entry.get("id") == player_id), None)
    if player is None:
        return False
    price = float(prop.get("current_value") or prop.get("base_price") or 0)
    if float(player.get("balance", 0)) < price:
        return _bot_decline_property(match_id, player_id, prop, dice_result)

    updated_props = [
        {**entry, "owner_id": player_id} if entry.get("id") == prop.get("id") else entry
        for entry in game_state.get("properties", [])
    ]
    updated_players = [
        {**entry, "balance": round(float(entry.get("balance", 0) or 0) - price, 2)} if entry.get("id") == player_id else entry
        for entry in game_state.get("players", [])
    ]
    next_state = {**game_state, "properties": updated_props, "players": updated_players}

    db_prop = Property.query.get(prop["id"])
    if db_prop:
        db_prop.owner_id = player_id
    mp = MatchPlayer.query.get(player_id)
    if mp:
        mp.balance = round(float(mp.balance or 0) - price, 2)
    db.session.commit()

    next_state = log_and_broadcast(
        next_state,
        "property_purchased",
        f"{player.get('username')} bought {prop['name']} for ${price:.2f}",
        match_id,
        redis_client,
        socketio,
        player_id=player_id,
    )
    socketio.emit(
        "property_purchased",
        {
            "player_id": player_id,
            "player_name": player.get("username"),
            "property_id": prop["id"],
            "position": prop.get("board_position"),
            "price": price,
            "property_name": prop.get("name"),
        },
        room=str(match_id),
    )
    finalize_turn_resolution(next_state, player_id, dice_result or {"is_doubles": False}, match_id, redis_client, socketio)
    return True


def _bot_buy_corporate_property(match_id: int, player_id: int, prop: dict, dice_result: dict | None) -> bool:
    game_state = load_game_state(match_id, redis_client)
    if not game_state:
        return False
    try:
        next_state, result = execute_liberal_democracy_buyout(
            game_state,
            player_id=player_id,
            property_id=int(prop.get("id") or 0),
        )
    except ValueError:
        return False

    db_prop = Property.query.get(prop["id"])
    if db_prop:
        db_prop.owner_id = player_id
    mp = MatchPlayer.query.get(player_id)
    result_player = result.get("player") or {}
    if mp and result_player:
        mp.balance = float(result_player.get("balance", mp.balance) or mp.balance)
    db.session.commit()

    player_name = result_player.get("username", "Bot")
    next_state = log_and_broadcast(
        next_state,
        "property_purchased",
        f"{player_name} bought out {result.get('property_name', prop.get('name', 'the property'))} for ${float(result.get('price', 0) or 0):.2f}.",
        match_id,
        redis_client,
        socketio,
        player_id=player_id,
    )
    socketio.emit(
        "property_purchased",
        {
            "player_id": player_id,
            "player_name": player_name,
            "property_id": result.get("property_id"),
            "position": prop.get("board_position"),
            "price": result.get("price"),
            "property_name": result.get("property_name"),
            "is_corporate_buyout": True,
        },
        room=str(match_id),
    )
    finalize_turn_resolution(next_state, player_id, dice_result or {"is_doubles": False}, match_id, redis_client, socketio)
    return True


def _bot_decline_corporate_property(match_id: int, player_id: int, prop: dict, dice_result: dict | None) -> bool:
    game_state = load_game_state(match_id, redis_client)
    if not game_state:
        return False
    player = next((entry for entry in game_state.get("players", []) if entry.get("id") == player_id), None)
    if player is None:
        return False
    rent_amount = round(float(prop.get("corporate_rent", 0) or 0), 2)
    try:
        next_state, updated_player = spend_player_balance(game_state, player_id, rent_amount)
    except ValueError:
        return False

    econ = dict(next_state.get("econ", {}) or {})
    corporations = dict(((econ.get("corporations") or {}).get("by_id") or {}))
    corporation_id = prop.get("corporate_owner_id")
    if corporation_id and str(corporation_id) in corporations:
        corporation = dict(corporations[str(corporation_id)] or {})
        corporation["cash_reserve"] = round(float(corporation.get("cash_reserve", 0) or 0) + rent_amount, 2)
        corporation["rent_income_last_round"] = round(float(corporation.get("rent_income_last_round", 0) or 0) + rent_amount, 2)
        corporations[str(corporation_id)] = corporation
        econ["corporations"] = {**dict(econ.get("corporations") or {}), "by_id": corporations}
        next_state["econ"] = econ

    mp = MatchPlayer.query.get(player_id)
    if mp and updated_player:
        mp.balance = float(updated_player.get("balance", mp.balance) or mp.balance)
    db.session.commit()

    next_state = log_and_broadcast(
        next_state,
        "rent_collected",
        f"{player.get('username', 'Bot')} declined a corporate buyout on {prop.get('name', 'the property')} and paid ${rent_amount:.2f}.",
        match_id,
        redis_client,
        socketio,
        player_id=player_id,
    )
    finalize_turn_resolution(next_state, player_id, dice_result or {"is_doubles": False}, match_id, redis_client, socketio)
    return True


def _bot_decline_property(match_id: int, player_id: int, prop: dict, dice_result: dict | None) -> bool:
    game_state = load_game_state(match_id, redis_client)
    if not game_state:
        return False
    player = next((entry for entry in game_state.get("players", []) if entry.get("id") == player_id), None)
    if player is None:
        return False

    if game_state.get("settings", {}).get("auction_enabled", True):
        start_auction(prop, game_state, redis_client, socketio, match_id)

    next_state = log_and_broadcast(
        game_state,
        "move",
        f"{player.get('username')} declined {prop['name']}",
        match_id,
        redis_client,
        socketio,
        player_id=player_id,
    )
    finalize_turn_resolution(next_state, player_id, dice_result or {"is_doubles": False}, match_id, redis_client, socketio)
    return True


def _bot_develop_property(match_id: int, player_id: int, property_id: int) -> bool:
    game_state = load_game_state(match_id, redis_client)
    if not game_state:
        return False
    prop = next((entry for entry in game_state.get("properties", []) if entry.get("id") == property_id), None)
    player = next((entry for entry in game_state.get("players", []) if entry.get("id") == player_id), None)
    if prop is None or player is None:
        return False
    if property_private_actions_locked(game_state, property_id):
        return False
    if property_is_fully_developed(prop, game_state):
        return False
    new_level = int(prop.get("dev_level", 0) or 0) + 1
    max_dev_level = player.get("plot_max_development_level")
    if player.get("plot_locked_poverty") and max_dev_level is not None and int(new_level) > int(max_dev_level):
        return False
    cost = calculate_development_cost(prop.get("base_price", 0), new_level, game_state)

    game_state, escrow_result = spend_investment_escrow(
        game_state,
        match_id,
        player_id=player_id,
        property_id=property_id,
        property_snapshot=prop,
        build_cost=cost,
        next_dev_level=new_level,
        econ=game_state.get("econ", {}),
    )
    player = next((entry for entry in game_state.get("players", []) if entry.get("id") == player_id), player)
    personal_cost = round(max(0.0, cost - float((escrow_result or {}).get("escrow_used", 0) or 0)), 2)
    if float(player.get("balance", 0) or 0) < personal_cost:
        return False

    updated_props = [
        {**entry, "dev_level": new_level} if entry.get("id") == property_id else entry
        for entry in game_state.get("properties", [])
    ]
    updated_players = [
        {**entry, "balance": round(float(entry.get("balance", 0) or 0) - personal_cost, 2)} if entry.get("id") == player_id else entry
        for entry in game_state.get("players", [])
    ]
    next_state = {**game_state, "properties": updated_props, "players": updated_players}

    db_prop = Property.query.get(property_id)
    if db_prop:
        db_prop.dev_level = new_level
    mp = MatchPlayer.query.get(player_id)
    if mp:
        final_player = next((entry for entry in updated_players if entry.get("id") == player_id), player)
        mp.balance = round(float(final_player.get("balance", mp.balance) or 0), 2)
    db.session.commit()

    next_state = log_and_broadcast(
        next_state,
        "property_purchased",
        f"{player.get('username')} developed {prop['name']} to level {new_level} for ${personal_cost:.2f}{' plus deal escrow' if escrow_result else ''}",
        match_id,
        redis_client,
        socketio,
        player_id=player_id,
    )
    if escrow_result:
        next_state = log_and_broadcast(
            next_state,
            "deal_investment_spent",
            f"{player.get('username')} used ${escrow_result['escrow_used']:.2f} of deal escrow to develop {prop['name']}",
            match_id,
            redis_client,
            socketio,
            player_id=player_id,
        )
        socketio.emit(
            "deal_investment_spent",
            {
                "match_id": match_id,
                "property_id": property_id,
                "property_name": prop["name"],
                **escrow_result,
            },
            room=str(match_id),
        )
    persist_game_state(next_state, match_id, redis_client)
    broadcast_game_state_snapshot(socketio, match_id, next_state)
    return True


def _bot_sell_house(match_id: int, player_id: int, property_id: int) -> bool:
    game_state = load_game_state(match_id, redis_client)
    if not game_state:
        return False
    prop = next((entry for entry in game_state.get("properties", []) if entry.get("id") == property_id), None)
    if prop is None:
        return False
    if property_private_actions_locked(game_state, property_id):
        return False
    refund = calculate_development_refund(
        prop.get("base_price", 0),
        int(prop.get("dev_level", 0) or 0),
        game_state,
    )
    new_level = int(prop.get("dev_level", 0) or 0) - 1
    updated_props = [
        {**entry, "dev_level": new_level} if entry.get("id") == property_id else entry
        for entry in game_state.get("properties", [])
    ]
    next_state = {**game_state, "properties": updated_props}
    next_state, credit_result = credit_player_with_debt_settlement(next_state, player_id, refund)

    db_prop = Property.query.get(property_id)
    if db_prop:
        db_prop.dev_level = new_level
    mp = MatchPlayer.query.get(player_id)
    player = next((entry for entry in next_state.get("players", []) if entry.get("id") == player_id), None)
    if mp and player:
        mp.balance = player.get("balance", mp.balance)
    db.session.commit()

    debt_suffix = ""
    if credit_result.get("settled_amount", 0) > 0:
        debt_suffix = f" and cleared ${credit_result['settled_amount']:.2f} of debt"
    next_state = log_and_broadcast(
        next_state,
        "property_purchased",
        f"{player.get('username')} sold one house on {prop['name']} for ${refund:.2f}{debt_suffix}",
        match_id,
        redis_client,
        socketio,
        player_id=player_id,
    )
    persist_game_state(next_state, match_id, redis_client)
    broadcast_game_state_snapshot(socketio, match_id, next_state)
    return True


def _bot_mortgage_property(match_id: int, player_id: int, property_id: int) -> bool:
    game_state = load_game_state(match_id, redis_client)
    if not game_state:
        return False
    prop = next((entry for entry in game_state.get("properties", []) if entry.get("id") == property_id), None)
    if prop is None:
        return False
    if property_private_actions_locked(game_state, property_id):
        return False
    mortgage_value = round(float(prop.get("base_price", 0) or 0) * 0.5, 2)
    updated_props = [
        {**entry, "is_mortgaged": True} if entry.get("id") == property_id else entry
        for entry in game_state.get("properties", [])
    ]
    next_state = {**game_state, "properties": updated_props}
    next_state, credit_result = credit_player_with_debt_settlement(next_state, player_id, mortgage_value)

    db_prop = Property.query.get(property_id)
    if db_prop:
        db_prop.is_mortgaged = True
    mp = MatchPlayer.query.get(player_id)
    player = next((entry for entry in next_state.get("players", []) if entry.get("id") == player_id), None)
    if mp and player:
        mp.balance = player.get("balance", mp.balance)
    db.session.commit()

    debt_suffix = ""
    if credit_result.get("settled_amount", 0) > 0:
        debt_suffix = f" and paid down ${credit_result['settled_amount']:.2f} in debt"
    next_state = log_and_broadcast(
        next_state,
        "mortgage",
        f"{player.get('username')} mortgaged {prop['name']} for ${mortgage_value:.2f}{debt_suffix}",
        match_id,
        redis_client,
        socketio,
        player_id=player_id,
    )
    persist_game_state(next_state, match_id, redis_client)
    broadcast_game_state_snapshot(socketio, match_id, next_state)
    return True


def _bot_unmortgage_property(match_id: int, player_id: int, property_id: int) -> bool:
    game_state = load_game_state(match_id, redis_client)
    if not game_state:
        return False
    prop = next((entry for entry in game_state.get("properties", []) if entry.get("id") == property_id), None)
    if prop is None:
        return False
    if property_private_actions_locked(game_state, property_id):
        return False
    cost = round(float(prop.get("base_price", 0) or 0) * 0.55, 2)
    player = next((entry for entry in game_state.get("players", []) if entry.get("id") == player_id), None)
    if player is None or float(player.get("balance", 0) or 0) < cost:
        return False

    updated_props = [
        {**entry, "is_mortgaged": False} if entry.get("id") == property_id else entry
        for entry in game_state.get("properties", [])
    ]
    updated_players = [
        {**entry, "balance": round(float(entry.get("balance", 0) or 0) - cost, 2)} if entry.get("id") == player_id else entry
        for entry in game_state.get("players", [])
    ]
    next_state = {**game_state, "properties": updated_props, "players": updated_players}

    db_prop = Property.query.get(property_id)
    if db_prop:
        db_prop.is_mortgaged = False
    mp = MatchPlayer.query.get(player_id)
    if mp:
        mp.balance = round(float(mp.balance or 0) - cost, 2)
    db.session.commit()

    player = next((entry for entry in updated_players if entry.get("id") == player_id), None)
    next_state = log_and_broadcast(
        next_state,
        "unmortgage",
        f"{player.get('username')} unmortgaged {prop['name']} for ${cost:.2f}",
        match_id,
        redis_client,
        socketio,
        player_id=player_id,
    )
    persist_game_state(next_state, match_id, redis_client)
    broadcast_game_state_snapshot(socketio, match_id, next_state)
    return True


def _bot_submit_lobby(match_id: int, player_id: int, action: dict[str, Any]) -> bool:
    game_state = load_game_state(match_id, redis_client)
    if not game_state:
        return False
    player = next((entry for entry in game_state.get("players", []) if entry.get("id") == player_id), None)
    if player is None:
        return False

    contribution = round(float(action.get("contribution", 0) or 0), 2)
    policy = None
    policy_id = action.get("policy_id")
    if policy_id is not None:
        policy = Policy.query.filter_by(id=int(policy_id), match_id=match_id).first()
    else:
        target = resolve_lobbying_target(
            axis=action.get("axis"),
            direction=action.get("direction"),
            target=action.get("target"),
        )
        if target:
            policy = ensure_match_lobbying_policy(match_id, target)
    if policy is None or contribution <= 0 or float(player.get("balance", 0) or 0) < contribution:
        return False

    updated_players = []
    updated_player = None
    for state_player in game_state.get("players", []):
        state_player = dict(state_player)
        if state_player["id"] == player_id:
            state_player["balance"] = round(float(state_player.get("balance", 0) or 0) - contribution, 2)
            updated_player = state_player
        updated_players.append(state_player)
    next_state = {**game_state, "players": updated_players}

    entry = LobbyContribution.query.filter_by(match_id=match_id, policy_id=policy.id, player_id=player_id).first()
    if entry:
        entry.contribution = round(float(entry.contribution or 0) + contribution, 2)
    else:
        db.session.add(
            LobbyContribution(
                match_id=match_id,
                policy_id=policy.id,
                player_id=player_id,
                contribution=contribution,
            )
        )

    mp = MatchPlayer.query.get(player_id)
    if mp:
        mp.balance = updated_player.get("balance", mp.balance) if updated_player else mp.balance
    db.session.commit()

    policy_entries = LobbyContribution.query.filter_by(match_id=match_id, policy_id=policy.id).all()
    policy_pool_total = round(sum(float(item.contribution or 0) for item in policy_entries), 2)
    next_state = record_lobbying_contribution(next_state, updated_player or player, policy, contribution, policy_entries)
    next_state = log_and_broadcast(
        next_state,
        "lobby_pending",
        (
            f"{player.get('username')} committed ${contribution:.2f} to '{policy.policy_name}'. "
            f"Current pool: ${policy_pool_total:.2f}."
        ),
        match_id,
        redis_client,
        socketio,
        player_id=player_id,
    )
    persist_game_state(next_state, match_id, redis_client)
    broadcast_game_state_snapshot(socketio, match_id, next_state)
    return True


def _bot_submit_negotiation(match_id: int, player_id: int, action: dict[str, Any]) -> bool:
    game_state = load_game_state(match_id, redis_client)
    if not game_state:
        return False
    try:
        next_state, _ = submit_negotiation_contribution(
            game_state,
            property_id=int(action.get("property_id", 0) or 0),
            player_id=player_id,
            amount=float(action.get("contribution", 0) or 0),
        )
    except ValueError:
        return False

    persist_game_state(next_state, match_id, redis_client)
    broadcast_game_state_snapshot(socketio, match_id, next_state)
    return True


def _bot_apply_emergency_reform(match_id: int, player_id: int, action: dict[str, Any]) -> bool:
    game_state = load_game_state(match_id, redis_client)
    if not game_state:
        return False
    try:
        next_state, _ = submit_minarchist_emergency_reform(
            game_state,
            player_id=player_id,
            reform_type=str(action.get("reform_type") or ""),
            property_id=int(action.get("property_id")) if action.get("property_id") is not None else None,
            target_region=action.get("target_region"),
        )
    except (TypeError, ValueError):
        return False

    persist_game_state(next_state, match_id, redis_client)
    broadcast_game_state_snapshot(socketio, match_id, next_state)
    return True


def _finalize_liberal_democracy_bot_action(match_id: int, player_id: int, next_state: dict, result: dict, event_type: str, summary: str) -> bool:
    player = result.get("player") or next((entry for entry in next_state.get("players", []) if int(entry.get("id") or 0) == player_id), None)
    mp = MatchPlayer.query.get(player_id)
    if mp and player:
        mp.balance = float(player.get("balance", mp.balance) or mp.balance)
    db.session.commit()
    if redis_client is not None:
        redis_client.set(
            f"game:{match_id}:bot:{player_id}:ld_finance_round",
            str(next_state.get("current_round", 1)),
            ex=BOT_TASK_TTL_SECONDS,
        )
    next_state = log_and_broadcast(
        next_state,
        event_type,
        summary,
        match_id,
        redis_client,
        socketio,
        player_id=player_id,
    )
    persist_game_state(next_state, match_id, redis_client)
    broadcast_game_state_snapshot(socketio, match_id, next_state)
    return True


def _bot_submit_market_order(match_id: int, player_id: int, action: dict[str, Any]) -> bool:
    game_state = load_game_state(match_id, redis_client)
    if not game_state:
        return False
    try:
        next_state, result = execute_liberal_democracy_market_order(
            game_state,
            player_id=player_id,
            asset_key=str(action.get("asset_key") or ""),
            side=str(action.get("side") or "buy"),
            quantity=float(action.get("quantity", 0) or 0),
        )
    except ValueError:
        return False
    player_name = (result.get("player") or {}).get("username", "Bot")
    summary = f"{player_name} placed a {result.get('side', 'buy')} order for {result.get('quantity')} {result.get('asset_key')}."
    return _finalize_liberal_democracy_bot_action(match_id, player_id, next_state, result, "market_order_submitted", summary)


def _bot_apply_bank_action(match_id: int, player_id: int, action: dict[str, Any]) -> bool:
    game_state = load_game_state(match_id, redis_client)
    if not game_state:
        return False
    amount = float(action.get("amount", 0) or 0)
    action_name = str(action.get("bank_action") or "")
    executor = {
        "deposit": execute_liberal_democracy_deposit,
        "withdraw": execute_liberal_democracy_withdraw,
        "loan": execute_liberal_democracy_loan,
        "repay": execute_liberal_democracy_repay,
    }.get(action_name)
    if executor is None:
        return False
    try:
        next_state, result = executor(game_state, player_id=player_id, amount=amount)
    except ValueError:
        return False
    player_name = (result.get("player") or {}).get("username", "Bot")
    verb = {
        "deposit": "deposited",
        "withdraw": "withdrew",
        "loan": "borrowed",
        "repay": "repaid",
    }.get(action_name, "used the bank for")
    summary = f"{player_name} {verb} ${float(result.get('amount', amount) or amount):.2f}."
    return _finalize_liberal_democracy_bot_action(match_id, player_id, next_state, result, "bank_action_submitted", summary)


def _extract_plot_payload(action: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in action.items()
        if key not in {"type", "action_type", "reason"}
    }


def _finalize_plot_bot_action(match_id: int, player_id: int, next_state: dict, result: dict, event_type: str) -> bool:
    next_state = log_and_broadcast(
        next_state,
        event_type,
        result.get("summary") or "A communist plot action resolved.",
        match_id,
        redis_client,
        socketio,
        player_id=player_id,
    )
    persist_game_state(next_state, match_id, redis_client)
    broadcast_game_state_snapshot(socketio, match_id, next_state)
    socketio.emit(
        "plot_updated",
        {"match_id": match_id, "plot": next_state.get("social", {}).get("plot", {})},
        room=str(match_id),
    )
    return True


def _bot_plot_start(match_id: int, player_id: int) -> bool:
    game_state = load_game_state(match_id, redis_client)
    if not game_state:
        return False
    try:
        next_state, result = start_communist_plot(game_state, player_id=player_id)
    except ValueError:
        return False
    return _finalize_plot_bot_action(match_id, player_id, next_state, result, "plot_action")


def _bot_plot_action(match_id: int, player_id: int, action: dict[str, Any]) -> bool:
    game_state = load_game_state(match_id, redis_client)
    if not game_state:
        return False
    try:
        next_state, result = submit_plot_action(
            game_state,
            player_id=player_id,
            action_type=str(action.get("action_type") or ""),
            payload=_extract_plot_payload(action),
        )
    except ValueError:
        return False
    return _finalize_plot_bot_action(match_id, player_id, next_state, result, "plot_action")


def _bot_plot_join(match_id: int, player_id: int, action: dict[str, Any]) -> bool:
    game_state = load_game_state(match_id, redis_client)
    if not game_state:
        return False
    try:
        next_state, result = submit_plot_join(
            game_state,
            player_id=player_id,
            payload=_extract_plot_payload(action),
        )
    except ValueError:
        return False
    return _finalize_plot_bot_action(match_id, player_id, next_state, result, "plot_membership")


def _bot_plot_leave(match_id: int, player_id: int, action: dict[str, Any] | None = None) -> bool:
    game_state = load_game_state(match_id, redis_client)
    if not game_state:
        return False
    try:
        next_state, result = submit_plot_leave(
            game_state,
            player_id=player_id,
            reason=str((action or {}).get("reason") or ""),
        )
    except ValueError:
        return False
    return _finalize_plot_bot_action(match_id, player_id, next_state, result, "plot_membership")


def _bot_plot_counter_action(match_id: int, player_id: int, action: dict[str, Any]) -> bool:
    game_state = load_game_state(match_id, redis_client)
    if not game_state:
        return False
    try:
        next_state, result = submit_plot_counter_action(
            game_state,
            player_id=player_id,
            action_type=str(action.get("action_type") or ""),
            payload=_extract_plot_payload(action),
        )
    except ValueError:
        return False
    return _finalize_plot_bot_action(match_id, player_id, next_state, result, "plot_counter_action")


def _bot_propose_deal(match_id: int, player_id: int, action: dict[str, Any]) -> bool:
    game_state = load_game_state(match_id, redis_client)
    if not game_state:
        return False

    payload, error = normalize_deal_request_payload(match_id, player_id, game_state, action)
    if error:
        return False

    deal = create_deal(match_id, player_id, payload)
    if deal is None:
        return False

    game_state = attach_deals_snapshot(game_state, match_id)
    player_lookup = {player.get("id"): player for player in game_state.get("players", [])}
    deal_payload = serialize_deal(deal, player_lookup)
    socketio.emit("deal_proposed", deal_payload, room=str(match_id))
    next_state = log_and_broadcast(
        game_state,
        "deal_proposed",
        f"{player_lookup.get(player_id, {}).get('username', 'Player')} proposed a deal to {deal_payload.get('counterparty_name', 'another player')}",
        match_id,
        redis_client,
        socketio,
        player_id=player_id,
    )
    persist_game_state(next_state, match_id, redis_client)
    queue_bot_deal_responses(match_id)
    queue_bot_state_evaluation(match_id, next_state, reason="bot_deal_follow_up")
    return True


def _bot_propose_trade(match_id: int, player_id: int, action: dict[str, Any]) -> bool:
    if has_active_auction(match_id):
        return False

    game_state = load_game_state(match_id, redis_client)
    if not game_state:
        return False

    payload = {
        "receiver_id": int(action["receiver_id"]),
        "offered_money": float(action.get("offered_money", 0) or 0),
        "requested_money": float(action.get("requested_money", 0) or 0),
        "offered_props": action.get("offered_props", []),
        "requested_props": action.get("requested_props", []),
        "offered_lobby_pledges": action.get("offered_lobby_pledges", []),
        "requested_lobby_pledges": action.get("requested_lobby_pledges", []),
        "included_deal_drafts": action.get("included_deal_drafts", []),
    }
    if validate_trade_proposal(game_state, player_id, payload):
        return False

    trade = Trade(
        match_id=match_id,
        initiator_id=player_id,
        receiver_id=payload["receiver_id"],
        offered_money=payload["offered_money"],
        requested_money=payload["requested_money"],
        offered_props=payload["offered_props"],
        requested_props=payload["requested_props"],
        offered_lobby_pledges=payload["offered_lobby_pledges"],
        requested_lobby_pledges=payload["requested_lobby_pledges"],
        included_deal_drafts=payload["included_deal_drafts"],
        status="pending",
        created_at=datetime.utcnow(),
    )
    db.session.add(trade)
    db.session.commit()

    initiator = next((entry for entry in game_state.get("players", []) if entry.get("id") == player_id), None)
    receiver = next((entry for entry in game_state.get("players", []) if entry.get("id") == int(action["receiver_id"])), None)
    trade_data = trade.to_dict()
    trade_data["initiator_username"] = initiator.get("username") if initiator else ""
    trade_data["receiver_username"] = receiver.get("username") if receiver else ""
    pledge_suffix = " including lobbying pledges" if action.get("offered_lobby_pledges") or action.get("requested_lobby_pledges") else ""
    bundle_suffix = " with bundled deal terms" if payload.get("included_deal_drafts") else ""

    socketio.emit("trade_proposed", trade_data, room=str(match_id))
    next_state = log_and_broadcast(
        game_state,
        "trade_proposed",
        f"{initiator.get('username')} proposed a trade to {receiver.get('username')}{pledge_suffix}{bundle_suffix}",
        match_id,
        redis_client,
        socketio,
        player_id=player_id,
    )
    persist_game_state(next_state, match_id, redis_client)
    queue_bot_trade_responses(match_id)
    queue_bot_state_evaluation(match_id, next_state, reason="bot_trade_follow_up")
    return True


def _bot_accept_deal(match_id: int, deal: Deal) -> bool:
    game_state = load_game_state(match_id, redis_client)
    if not game_state:
        return False

    game_state, error = accept_deal(deal, game_state)
    if error:
        return False

    player_lookup = {player.get("id"): player for player in game_state.get("players", [])}
    deal_payload = serialize_deal(deal, player_lookup)
    game_state = log_and_broadcast(
        game_state,
        "deal_accepted",
        f"Deal accepted between {deal_payload.get('proposer_name', 'Player')} and {deal_payload.get('counterparty_name', 'Player')}",
        match_id,
        redis_client,
        socketio,
        player_id=deal.counterparty_id,
    )
    persist_game_state(game_state, match_id, redis_client)
    socketio.emit("deal_accepted", deal_payload, room=str(match_id))
    broadcast_game_state_snapshot(socketio, match_id, game_state)
    queue_bot_state_evaluation(match_id, game_state, reason="bot_deal_accepted")
    return True


def _bot_reject_deal(match_id: int, deal: Deal) -> bool:
    if not reject_deal(deal):
        return False

    game_state = load_game_state(match_id, redis_client)
    if not game_state:
        return False
    game_state = attach_deals_snapshot(game_state, match_id)
    player_lookup = {player.get("id"): player for player in game_state.get("players", [])}
    deal_payload = serialize_deal(deal, player_lookup)
    log_and_broadcast(
        game_state,
        "deal_rejected",
        f"Deal rejected between {deal_payload.get('proposer_name', 'Player')} and {deal_payload.get('counterparty_name', 'Player')}",
        match_id,
        redis_client,
        socketio,
        player_id=deal.counterparty_id,
    )
    socketio.emit("deal_rejected", deal_payload, room=str(match_id))
    return True


def _bot_accept_trade(match_id: int, trade: Trade) -> None:
    game_state = load_game_state(match_id, redis_client)
    if not game_state:
        return

    game_state, pledge_results, created_deals, error = apply_trade_acceptance(game_state, trade, match_id)
    if error:
        _bot_reject_trade(match_id, trade)
        return

    initiator = next((player for player in game_state.get("players", []) if player.get("id") == trade.initiator_id), None)
    receiver = next((player for player in game_state.get("players", []) if player.get("id") == trade.receiver_id), None)
    if initiator is None or receiver is None:
        _bot_reject_trade(match_id, trade)
        return

    mp_init = MatchPlayer.query.get(trade.initiator_id)
    mp_recv = MatchPlayer.query.get(trade.receiver_id)
    final_initiator = next((player for player in game_state.get("players", []) if player["id"] == trade.initiator_id), None)
    final_receiver = next((player for player in game_state.get("players", []) if player["id"] == trade.receiver_id), None)
    if mp_init and final_initiator:
        mp_init.balance = final_initiator.get("balance", mp_init.balance)
    if mp_recv and final_receiver:
        mp_recv.balance = final_receiver.get("balance", mp_recv.balance)
    for prop_id in (trade.offered_props or []):
        db_prop = Property.query.get(prop_id)
        if db_prop:
            db_prop.owner_id = trade.receiver_id
    for prop_id in (trade.requested_props or []):
        db_prop = Property.query.get(prop_id)
        if db_prop:
            db_prop.owner_id = trade.initiator_id

    trade.status = "accepted"
    trade.resolved_at = datetime.utcnow()
    db.session.commit()

    game_state = attach_deals_snapshot(game_state, match_id)

    activated_deals_suffix = ""
    if created_deals:
        count = len(created_deals)
        activated_deals_suffix = f" and activated {count} bundled deal{'s' if count != 1 else ''}"

    game_state = log_and_broadcast(
        game_state,
        "trade_completed",
        f"Trade accepted between {initiator.get('username')} and {receiver.get('username')}{activated_deals_suffix}",
        match_id,
        redis_client,
        socketio,
    )
    for payer_id, entries in ((trade.initiator_id, (pledge_results or {}).get("initiator", [])), (trade.receiver_id, (pledge_results or {}).get("receiver", []))):
        payer = next((player for player in game_state.get("players", []) if player.get("id") == payer_id), None)
        for entry in entries:
            game_state = log_and_broadcast(
                game_state,
                "lobby_pending",
                f"{payer.get('username', 'Player')} committed ${entry['amount']:.2f} to '{entry['policy'].get('policy_name', 'Policy')}' as part of a trade.",
                match_id,
                redis_client,
                socketio,
                player_id=payer_id,
            )
    socketio.emit(
        "trade_resolved",
        {"trade": trade.to_dict(), "accepted": True, "created_deals": created_deals},
        room=str(match_id),
    )
    persist_game_state(game_state, match_id, redis_client)
    broadcast_game_state_snapshot(socketio, match_id, game_state)


def _bot_reject_trade(match_id: int, trade: Trade) -> None:
    trade.status = "rejected"
    trade.resolved_at = datetime.utcnow()
    db.session.commit()
    game_state = load_game_state(match_id, redis_client)
    if game_state:
        log_and_broadcast(game_state, "trade_rejected", "A trade was rejected.", match_id, redis_client, socketio)
    socketio.emit("trade_resolved", {"trade": trade.to_dict(), "accepted": False}, room=str(match_id))


def _bot_declare_bankruptcy(match_id: int, player_id: int) -> bool:
    game_state = load_game_state(match_id, redis_client)
    if not game_state:
        return False
    next_state, outcome = declare_player_bankruptcy(game_state, player_id, match_id, redis_client, socketio)
    if outcome.get("bankrupt"):
        winner = check_win_condition(next_state, next_state.get("settings", {}))
        if winner:
            next_state = dict(next_state)
            next_state["status"] = "completed"
            next_state["winner"] = winner
            next_state.pop("awaiting_end_turn_player_id", None)
            next_state["dice_rolled_this_turn"] = False
            socketio.emit("game_over", {"match_id": match_id, "winner": winner}, room=str(match_id))
        elif next_state.get("current_player_id") == player_id:
            next_state = end_turn(
                next_state,
                player_id,
                {"is_doubles": False},
                match_id,
                redis_client,
                socketio,
                next_state.get("settings", {}),
                next_state.get("econ", {}),
                next_state.get("current_round", 1),
            )
    persist_game_state(next_state, match_id, redis_client)
    broadcast_game_state_snapshot(socketio, match_id, next_state)
    return True


def _bot_pay_jail_bail(match_id: int, player_id: int) -> None:
    game_state = load_game_state(match_id, redis_client)
    if not game_state:
        return
    bail = 50.0
    updated_players = [
        {**entry, "balance": round(float(entry.get("balance", 0) or 0) - bail, 2), "is_jailed": False, "jail_turns_remaining": 0}
        if entry.get("id") == player_id else entry
        for entry in game_state.get("players", [])
    ]
    next_state = {**game_state, "players": updated_players}
    mp = MatchPlayer.query.get(player_id)
    if mp:
        mp.balance = round(float(mp.balance or 0) - bail, 2)
        mp.is_jailed = False
        mp.jail_turns_remaining = 0
    db.session.commit()

    player = next((entry for entry in updated_players if entry.get("id") == player_id), None)
    next_state = log_and_broadcast(
        next_state,
        "jail_released",
        f"{player.get('username')} paid ${bail:.2f} bail.",
        match_id,
        redis_client,
        socketio,
        player_id=player_id,
    )
    persist_game_state(next_state, match_id, redis_client)
    broadcast_game_state_snapshot(socketio, match_id, next_state)


def _bot_use_jail_card(match_id: int, player_id: int) -> None:
    game_state = load_game_state(match_id, redis_client)
    if not game_state:
        return
    updated_players = [
        {**entry, "is_jailed": False, "jail_turns_remaining": 0, "has_jail_card": False}
        if entry.get("id") == player_id else entry
        for entry in game_state.get("players", [])
    ]
    next_state = {**game_state, "players": updated_players}

    mp = MatchPlayer.query.get(player_id)
    if mp:
        mp.is_jailed = False
        mp.jail_turns_remaining = 0
        mp.has_jail_card = False
    db.session.commit()

    player = next((entry for entry in updated_players if entry.get("id") == player_id), None)
    next_state = log_and_broadcast(
        next_state,
        "jail_released",
        f"{player.get('username')} used a Get Out of Jail Free card.",
        match_id,
        redis_client,
        socketio,
        player_id=player_id,
    )
    persist_game_state(next_state, match_id, redis_client)
    broadcast_game_state_snapshot(socketio, match_id, next_state)
