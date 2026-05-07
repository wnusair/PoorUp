"""
Space resolution and card logic for PoorUp.
"""
import json
import random
import uuid
from typing import Any

from flask import current_app

from app.engine.economy import (
    calculate_rent_with_dev,
    calculate_transit_rent,
    apply_income_tax,
    apply_luxury_tax,
    apply_super_tax,
    split_development_for_repairs,
)
from app.engine.debt import charge_player_to_player, credit_player_with_debt_settlement, spend_player_balance
from app.engine.liberal_democracy import get_liberal_democracy_go_salary
from app.engine.plot import COMMUNIST_PLOT_OWNER_ID, calculate_solidarity_levy, property_is_plot_seized
from app.engine.social import PROLETARIAT_UNION_ID, calculate_union_charge, property_income_blocked, property_is_unionized
from app.engine.deals import apply_investment_profit_share, apply_rent_deal_effects
from app.utils.settings import normalize_government_type

RETIRED_BOARD_POSITIONS = {1, 3, 7, 8, 21, 28, 29, 33, 35, 41, 42, 43, 44, 45, 46}
BOARD_POSITION_ORDER = tuple(position for position in range(48) if position not in RETIRED_BOARD_POSITIONS)
BOARD_INDEX_BY_POSITION = {position: index for index, position in enumerate(BOARD_POSITION_ORDER)}
BOARD_SIZE = len(BOARD_POSITION_ORDER)

# Positions by type
COMMUNITY_CHEST_POSITIONS = {17}
CHANCE_POSITIONS = {22}
TAX_INCOME_POSITION = 5
TAX_LUXURY_POSITION = 39
TAX_SUPER_POSITION = 47
JAIL_POSITION = 11
AUCTION_COUNTDOWN_SECONDS = 5
GO_TO_JAIL_POSITION = 30
FREE_SPACE_POSITION = 20
START_POSITION = 0

TRANSIT_POSITIONS = {6, 15, 25, 36}


def normalize_board_position(position: int | None) -> int:
    try:
        normalized = int(position)
    except (TypeError, ValueError):
        return START_POSITION

    if normalized in BOARD_INDEX_BY_POSITION:
        return normalized

    for candidate in BOARD_POSITION_ORDER:
        if candidate >= normalized:
            return candidate

    return START_POSITION


def board_index(position: int | None) -> int:
    return BOARD_INDEX_BY_POSITION[normalize_board_position(position)]


def did_pass_go(old_position: int | None, new_position: int | None) -> bool:
    normalized_old = normalize_board_position(old_position)
    normalized_new = normalize_board_position(new_position)
    if normalized_old == normalized_new:
        return False
    return board_index(normalized_new) <= board_index(normalized_old)

# Nearest airport lookup (from a given position, which transit is nearest)
def nearest_transit(position: int) -> int:
    current_idx = board_index(position)
    transits = sorted(TRANSIT_POSITIONS, key=board_index)
    # find clockwise nearest
    for t in transits:
        if board_index(t) >= current_idx:
            return t
    return transits[0]  # wrap around


def move_player(current_position: int, roll: int, board_size: int = BOARD_SIZE) -> tuple[int, bool]:
    normalized_position = normalize_board_position(current_position)
    current_idx = board_index(normalized_position)
    new_idx = (current_idx + roll) % board_size
    new_position = BOARD_POSITION_ORDER[new_idx]
    passed_go = roll > 0 and current_idx + roll >= board_size
    return new_position, passed_go


def _get_property_at(position: int, game_state: dict):
    for p in game_state.get("properties", []):
        if p.get("board_position") == position:
            return p
    return None


def _get_player_by_id(player_id: int, game_state: dict):
    for p in game_state.get("players", []):
        if p["id"] == player_id:
            return p
    return None


def _update_player_state(game_state: dict, updated_player: dict) -> dict:
    next_state = dict(game_state)
    next_state["players"] = [
        updated_player if player.get("id") == updated_player.get("id") else player
        for player in game_state.get("players", [])
    ]
    return next_state


def resolve_space(
    player: dict,
    game_state: dict,
    econ: dict,
    settings: dict,
    redis_client,
    socketio_instance,
    match_id: int,
) -> tuple[dict, dict, dict, list[dict]]:
    """
    Resolve the effect of a player landing on their current position.
    Returns (updated_player, updated_game_state, updated_econ, log_entries).
    """
    position = normalize_board_position(player["current_position"])
    if position != player["current_position"]:
        player = dict(player)
        player["current_position"] = position
        game_state = _update_player_state(game_state, player)
    logs = []
    free_parking_pot = float(game_state.get("free_parking_pot", 0.0))
    fp_enabled = settings.get("free_parking_pot_enabled", False)

    # --- START (0) ---
    if position == START_POSITION:
        go_salary = float(settings.get("go_salary", 200))
        if normalize_government_type(settings.get("government_type")) == "liberal_democracy":
            go_salary = get_liberal_democracy_go_salary(game_state, player["id"], go_salary)
        if settings.get("double_on_go", False):
            go_salary *= 2
        game_state, credit_result = credit_player_with_debt_settlement(game_state, player["id"], go_salary)
        player = credit_result.get("player") or dict(player)
        logs.append({"event_type": "move", "description": f"{player.get('username','Player')} landed on START, collected ${go_salary:.2f}"})
        return player, game_state, econ, logs

    # --- JAIL / JUST VISITING (11) ---
    if position == JAIL_POSITION:
        logs.append({"event_type": "move", "description": f"{player.get('username','Player')} is just visiting jail."})
        return player, game_state, econ, logs

    # --- GO TO JAIL (30) ---
    if position == GO_TO_JAIL_POSITION:
        player = dict(player)
        player["current_position"] = JAIL_POSITION
        player["is_jailed"] = True
        player["jail_turns_remaining"] = 3
        player["consecutive_doubles"] = 0
        logs.append({"event_type": "jail_sent", "description": f"{player.get('username','Player')} was sent to jail!"})
        socketio_instance.emit("player_moved", {"player_id": player["id"], "position": JAIL_POSITION, "jailed": True}, room=str(match_id))
        return player, game_state, econ, logs

    # --- FREE SPACE (20) ---
    if position == FREE_SPACE_POSITION:
        if fp_enabled and free_parking_pot > 0:
            treasury_balance = round(float(econ.get("treasury_balance", 0) or 0), 2)
            payout = round(min(free_parking_pot, treasury_balance), 2)
            if payout > 0:
                game_state, credit_result = credit_player_with_debt_settlement(game_state, player["id"], payout)
                player = credit_result.get("player") or dict(player)
                econ = dict(econ)
                econ["treasury_balance"] = round(treasury_balance - payout, 2)
                logs.append({"event_type": "move", "description": f"{player.get('username','Player')} collected Free Parking pot of ${payout:.2f}"})
                game_state = dict(game_state)
                game_state["free_parking_pot"] = round(free_parking_pot - payout, 2)
                if free_parking_pot > payout:
                    logs.append({"event_type": "move", "description": f"Treasury could only cover ${payout:.2f} of the ${free_parking_pot:.2f} Free Parking pot."})
            else:
                logs.append({"event_type": "move", "description": f"{player.get('username','Player')} reached Free Space, but the treasury could not cover the current Free Parking pot."})
        else:
            logs.append({"event_type": "move", "description": f"{player.get('username','Player')} landed on Free Space."})
        return player, game_state, econ, logs

    # --- INCOME TAX (5) ---
    if position == TAX_INCOME_POSITION:
        amount, new_balance = apply_income_tax(player, econ, settings)
        player = dict(player)
        player["balance"] = new_balance
        econ = dict(econ)
        econ["treasury_balance"] = round(float(econ.get("treasury_balance", 0)) + amount, 2)
        if fp_enabled:
            game_state = dict(game_state)
            game_state["free_parking_pot"] = round(free_parking_pot + amount, 2)
        logs.append({"event_type": "income_tax", "description": f"{player.get('username','Player')} paid Income Tax of ${amount:.2f}"})
        return player, game_state, econ, logs

    # --- LUXURY TAX (39) ---
    if position == TAX_LUXURY_POSITION:
        amount, new_balance, new_pot = apply_luxury_tax(player, econ, free_parking_pot if fp_enabled else 0.0)
        player = dict(player)
        player["balance"] = new_balance
        econ = dict(econ)
        econ["treasury_balance"] = round(float(econ.get("treasury_balance", 0)) + amount, 2)
        if fp_enabled:
            game_state = dict(game_state)
            game_state["free_parking_pot"] = new_pot
        logs.append({"event_type": "luxury_tax", "description": f"{player.get('username','Player')} paid Luxury Tax of ${amount:.2f}"})
        return player, game_state, econ, logs

    # --- SUPER TAX (47) ---
    if position == TAX_SUPER_POSITION:
        amount, new_balance, new_pot = apply_super_tax(player, econ, free_parking_pot if fp_enabled else 0.0)
        player = dict(player)
        player["balance"] = new_balance
        econ = dict(econ)
        econ["treasury_balance"] = round(float(econ.get("treasury_balance", 0)) + amount, 2)
        if fp_enabled:
            game_state = dict(game_state)
            game_state["free_parking_pot"] = new_pot
        logs.append({"event_type": "super_tax", "description": f"{player.get('username','Player')} paid Super Tax of ${amount:.2f}"})
        return player, game_state, econ, logs

    # --- COMMUNITY CHEST ---
    if position in COMMUNITY_CHEST_POSITIONS:
        if settings.get("community_chest_enabled", True):
            player, game_state, econ, card_logs = draw_community_chest_card(
                player, game_state, econ, settings, redis_client, socketio_instance, match_id
            )
            logs.extend(card_logs)
        return player, game_state, econ, logs

    # --- CHANCE ---
    if position in CHANCE_POSITIONS:
        if settings.get("chance_cards_enabled", True):
            player, game_state, econ, card_logs = draw_chance_card(
                player, game_state, econ, settings, redis_client, socketio_instance, match_id
            )
            logs.extend(card_logs)
        return player, game_state, econ, logs

    # --- PROPERTY / TRANSIT ---
    prop = _get_property_at(position, game_state)
    if prop is None:
        return player, game_state, econ, logs

    prop_type = prop.get("property_type", "property")
    owner_id = prop.get("owner_id")
    corporate_owner_id = prop.get("corporate_owner_id")

    if owner_id is None and corporate_owner_id:
        game_state = dict(game_state)
        game_state["pending_action"] = {
            "type": "buy_corporate_property",
            "player_id": player["id"],
            "player_name": player.get("username", "Player"),
            "property_id": prop["id"],
            "position": position,
            "property": dict(prop),
            "corporation_id": corporate_owner_id,
        }
        logs.append({"event_type": "move", "description": f"{player.get('username','Player')} landed on corporate-owned {prop['name']} and can attempt a buyout."})
        socketio_instance.emit(
            "property_action_required",
            game_state["pending_action"],
            room=str(match_id),
        )
        return player, game_state, econ, logs

    if owner_id is None:
        game_state = dict(game_state)
        game_state["pending_action"] = {
            "type": "buy_property",
            "player_id": player["id"],
            "player_name": player.get("username", "Player"),
            "property_id": prop["id"],
            "position": position,
            "property": dict(prop),
        }
        logs.append({"event_type": "move", "description": f"{player.get('username','Player')} landed on unowned {prop['name']}."})
        socketio_instance.emit(
            "property_action_required",
            game_state["pending_action"],
            room=str(match_id),
        )
        return player, game_state, econ, logs

    if owner_id == player["id"]:
        # Own property
        logs.append({"event_type": "move", "description": f"{player.get('username','Player')} landed on their own {prop['name']}."})
        return player, game_state, econ, logs

    if prop.get("is_mortgaged", False):
        logs.append({"event_type": "move", "description": f"{prop['name']} is mortgaged — no rent due."})
        return player, game_state, econ, logs

    owner = _get_player_by_id(owner_id, game_state)

    if property_is_plot_seized(prop, game_state):
        plot = ((game_state.get("social") or {}).get("plot") or {})
        plot_member_ids = set(int(value) for value in (plot.get("member_ids") or []) if value is not None)
        if int(player.get("id") or 0) in plot_member_ids:
            logs.append(
                {
                    "event_type": "solidarity_levy_exempt",
                    "description": f"{player.get('username', 'Player')} moved through {prop['name']} without paying a solidarity levy because they are part of the communist faction.",
                }
            )
            return player, game_state, econ, logs

        levy_info = calculate_solidarity_levy(prop, game_state)
        levy_amount = float(levy_info.get("amount", 0) or 0)
        if levy_amount > 0:
            game_state, updated_player = spend_player_balance(game_state, player["id"], levy_amount)
            player = updated_player or _get_player_by_id(player["id"], game_state) or player
            social = dict(game_state.get("social") or {})
            social_properties = {str(key): dict(value) for key, value in (social.get("properties") or {}).items()}
            entry = dict(social_properties.get(str(prop.get("id"))) or {})
            entry["plot_last_levy_round"] = int(game_state.get("current_round", 1) or 1)
            social_properties[str(prop.get("id"))] = entry
            social["properties"] = social_properties
            game_state = dict(game_state)
            game_state["social"] = social
            logs.append(
                {
                    "event_type": "solidarity_levy_collected",
                    "description": (
                        f"{player.get('username', 'Player')} paid ${levy_amount:.2f} in solidarity levy for landing on {prop['name']}."
                    ),
                }
            )
            socketio_instance.emit(
                "rent_collected",
                {
                    "payer_id": player["id"],
                    "payer_name": player.get("username", "Player"),
                    "payer_balance": player.get("balance"),
                    "owner_id": COMMUNIST_PLOT_OWNER_ID,
                    "owner_name": levy_info.get("owner_name", "People's Committees"),
                    "owner_balance": None,
                    "amount": levy_amount,
                    "amount_paid": levy_amount,
                    "amount_due": 0,
                    "total_rent": levy_amount,
                    "property": prop["name"],
                    "is_plot_levy": True,
                },
                room=str(match_id),
            )
        else:
            logs.append(
                {
                    "event_type": "solidarity_levy_exempt",
                    "description": f"{player.get('username', 'Player')} landed on {prop['name']} but paid no solidarity levy.",
                }
            )
        return player, game_state, econ, logs

    if property_is_unionized(prop, game_state):
        union_charge = calculate_union_charge(prop, game_state, game_state.get("social"))
        game_state, updated_player = spend_player_balance(game_state, player["id"], union_charge)
        player = updated_player or _get_player_by_id(player["id"], game_state) or player
        logs.append(
            {
                "event_type": "union_charge_collected",
                "description": (
                    f"{player.get('username','Player')} paid ${union_charge:.2f} in bloc extraction "
                    f"for entering {prop['name']}. The charge was removed from circulation."
                ),
            }
        )
        socketio_instance.emit(
            "rent_collected",
            {
                "payer_id": player["id"],
                "payer_name": player.get("username", "Player"),
                "payer_balance": player.get("balance"),
                "owner_id": PROLETARIAT_UNION_ID,
                "owner_name": "Proletariat Union",
                "owner_balance": None,
                "amount": union_charge,
                "amount_paid": union_charge,
                "amount_due": 0,
                "total_rent": union_charge,
                "property": prop["name"],
                "is_union_charge": True,
            },
            room=str(match_id),
        )
        return player, game_state, econ, logs

    if property_income_blocked(game_state, prop.get("id")):
        logs.append(
            {
                "event_type": "rent_suspended",
                "description": f"{prop['name']} is under labor action — no rent is collected this turn.",
            }
        )
        return player, game_state, econ, logs

    if owner.get("is_jailed", False) and not settings.get("collect_rent_while_jailed", False):
        logs.append(
            {
                "event_type": "rent_suspended",
                "description": f"{owner.get('username', 'The owner')} is in jail — {prop['name']} does not collect rent this turn.",
            }
        )
        return player, game_state, econ, logs

    # Calculate and collect rent
    if prop_type == "transit":
        rent = calculate_transit_rent(owner_id, game_state)
    else:
        rent = calculate_rent_with_dev(prop, econ, game_state)
    base_rent_before_deals = float(rent or 0)

    game_state, rent, deal_logs = apply_rent_deal_effects(
        game_state,
        match_id,
        payer_id=player["id"],
        owner_id=owner_id,
        prop=prop,
        base_rent=rent,
    )
    logs.extend(deal_logs)
    for entry in deal_logs:
        socketio_instance.emit(
            "deal_clause_consumed",
            {
                "match_id": match_id,
                "player_id": player["id"],
                "owner_id": owner_id,
                "property_id": prop.get("id"),
                "property_name": prop.get("name"),
                **entry,
            },
            room=str(match_id),
        )

    if rent <= 0:
        owner_funded_build_loan = any(entry.get("event_type") == "deal_immunity_applied" for entry in deal_logs)
        if owner_funded_build_loan and base_rent_before_deals > 0:
            game_state, profit_logs = apply_investment_profit_share(
                game_state,
                match_id,
                property_id=int(prop.get("id") or 0),
                owner_id=owner_id,
                actual_rent_paid=0.0,
                triggered_rent_amount=base_rent_before_deals,
                owner_funded=True,
            )
            if profit_logs:
                owner = _get_player_by_id(owner_id, game_state) or owner
                logs.extend(profit_logs)
                for entry in profit_logs:
                    socketio_instance.emit(
                        "deal_profit_paid",
                        {
                            "match_id": match_id,
                            "property_id": prop.get("id"),
                            "property_name": prop.get("name"),
                            **entry,
                        },
                        room=str(match_id),
                    )
        return player, game_state, econ, logs

    game_state, rent_result = charge_player_to_player(
        game_state,
        player["id"],
        owner_id,
        rent,
        reason="rent",
        property_id=prop.get("id"),
        property_name=prop.get("name"),
    )
    player = _get_player_by_id(player["id"], game_state) or player
    owner = _get_player_by_id(owner_id, game_state) or owner
    paid_now = float(rent_result.get("paid_now", 0) or 0)
    shortfall = float(rent_result.get("shortfall", 0) or 0)

    game_state, profit_logs = apply_investment_profit_share(
        game_state,
        match_id,
        property_id=int(prop.get("id") or 0),
        owner_id=owner_id,
        actual_rent_paid=paid_now,
        triggered_rent_amount=rent,
    )
    if profit_logs:
        owner = _get_player_by_id(owner_id, game_state) or owner
        logs.extend(profit_logs)
        for entry in profit_logs:
            socketio_instance.emit(
                "deal_profit_paid",
                {
                    "match_id": match_id,
                    "property_id": prop.get("id"),
                    "property_name": prop.get("name"),
                    **entry,
                },
                room=str(match_id),
            )

    if shortfall > 0:
        description = (
            f"{player.get('username','Player')} paid ${paid_now:.2f} of ${rent:.2f} rent to "
            f"{owner.get('username','owner')} for {prop['name']}. ${shortfall:.2f} is still owed."
        )
    else:
        description = (
            f"{player.get('username','Player')} paid ${rent:.2f} rent to "
            f"{owner.get('username','owner')} for {prop['name']}."
        )

    logs.append({
        "event_type": "rent_collected",
        "description": description,
    })
    socketio_instance.emit(
        "rent_collected",
        {
            "payer_id": player["id"],
            "payer_name": player.get("username", "Player"),
            "payer_balance": player["balance"],
            "owner_id": owner_id,
            "owner_name": owner.get("username", "owner") if owner else "owner",
            "owner_balance": owner.get("balance") if owner else None,
            "amount": paid_now,
            "amount_paid": paid_now,
            "amount_due": shortfall,
            "total_rent": rent,
            "property": prop["name"],
        },
        room=str(match_id),
    )
    return player, game_state, econ, logs


# ---------------------------------------------------------------------------
# Card deck helpers
# ---------------------------------------------------------------------------

def _pop_card_from_deck(deck_key: str, redis_client) -> dict | None:
    """Pop top card from Redis deck list, rotate to bottom, return card dict."""
    raw = redis_client.lindex(deck_key, 0)
    if raw is None:
        return None
    redis_client.lpop(deck_key)
    redis_client.rpush(deck_key, raw)
    return json.loads(raw)


def _build_card_draw_payload(card_type: str, card: dict, player: dict) -> dict[str, Any]:
    return {
        "type": card_type,
        "card_type": card_type,
        "card_text": card.get("card_text", "Unknown card"),
        "card": card,
        "player_id": player["id"],
        "player_name": player.get("username", "Player"),
    }


def draw_chance_card(
    player: dict, game_state: dict, econ: dict, settings: dict,
    redis_client, socketio_instance, match_id: int
) -> tuple[dict, dict, dict, list[dict]]:
    match_id_str = str(match_id)
    deck_key = f"game:{match_id}:chance_deck"
    card = _pop_card_from_deck(deck_key, redis_client)
    if card is None:
        return player, game_state, econ, []
    socketio_instance.emit("card_drawn", _build_card_draw_payload("chance", card, player), room=match_id_str)
    player, game_state, econ, logs = apply_card_effect(
        card,
        player,
        game_state,
        econ,
        settings,
        socketio_instance,
        match_id,
        redis_client,
    )
    logs.insert(0, {"event_type": "chance_card", "description": f"{player.get('username','Player')} drew Chance: {card['card_text']}"})
    return player, game_state, econ, logs


def draw_community_chest_card(
    player: dict, game_state: dict, econ: dict, settings: dict,
    redis_client, socketio_instance, match_id: int
) -> tuple[dict, dict, dict, list[dict]]:
    match_id_str = str(match_id)
    deck_key = f"game:{match_id}:community_deck"
    card = _pop_card_from_deck(deck_key, redis_client)
    if card is None:
        return player, game_state, econ, []
    socketio_instance.emit("card_drawn", _build_card_draw_payload("community_chest", card, player), room=match_id_str)
    player, game_state, econ, logs = apply_card_effect(
        card,
        player,
        game_state,
        econ,
        settings,
        socketio_instance,
        match_id,
        redis_client,
    )
    logs.insert(0, {"event_type": "community_chest", "description": f"{player.get('username','Player')} drew Community Chest: {card['card_text']}"})
    return player, game_state, econ, logs


def apply_card_effect(
    card: dict, player: dict, game_state: dict, econ: dict,
    settings: dict, socketio_instance, match_id: int, redis_client=None
) -> tuple[dict, dict, dict, list[dict]]:
    """Apply a card's effect to the player/game state. Returns (player, game_state, econ, logs)."""
    effect = card.get("effect_type", "")
    value = float(card.get("effect_value") or 0)
    logs = []
    player = dict(player)

    if effect == "advance_to_start":
        old_pos = player["current_position"]
        player["current_position"] = 0
        game_state = _update_player_state(game_state, player)
        if old_pos > 0:  # passed go
            go_salary = float(settings.get("go_salary", 200))
            if settings.get("double_on_go", False):
                go_salary *= 2
            game_state, credit_result = credit_player_with_debt_settlement(game_state, player["id"], go_salary)
            player = credit_result.get("player") or player
        logs.append({"event_type": "move", "description": "Advanced to START."})

    elif effect == "advance_to_position":
        target = normalize_board_position(int(value))
        old_pos = normalize_board_position(player["current_position"])
        player["current_position"] = target
        game_state = _update_player_state(game_state, player)
        if did_pass_go(old_pos, target):
            go_salary = float(settings.get("go_salary", 200))
            if settings.get("double_on_go", False):
                go_salary *= 2
            game_state, credit_result = credit_player_with_debt_settlement(game_state, player["id"], go_salary)
            player = credit_result.get("player") or player
        # Resolve landing
        player, game_state, econ, land_logs = resolve_space(
            player, game_state, econ, settings, redis_client, socketio_instance, match_id
        )
        logs.extend(land_logs)

    elif effect == "advance_to_nearest_transit":
        old_pos = normalize_board_position(player["current_position"])
        near = nearest_transit(old_pos)
        player["current_position"] = near
        game_state = _update_player_state(game_state, player)
        if did_pass_go(old_pos, near):
            go_salary = float(settings.get("go_salary", 200))
            game_state, credit_result = credit_player_with_debt_settlement(game_state, player["id"], go_salary)
            player = credit_result.get("player") or player
        player, game_state, econ, land_logs = resolve_space(
            player, game_state, econ, settings, redis_client, socketio_instance, match_id
        )
        logs.extend(land_logs)

    elif effect == "collect":
        game_state, credit_result = credit_player_with_debt_settlement(game_state, player["id"], value)
        player = credit_result.get("player") or player
        logs.append({"event_type": "community_chest", "description": f"Collected ${value:.2f}."})

    elif effect == "pay":
        player["balance"] = round(float(player["balance"]) - value, 2)
        econ = dict(econ)
        econ["treasury_balance"] = round(float(econ.get("treasury_balance", 0)) + value, 2)
        logs.append({"event_type": "income_tax", "description": f"Paid ${value:.2f}."})

    elif effect == "collect_from_each_player":
        # Collect value from each active player
        total_collected = 0.0
        for p in game_state.get("players", []):
            if p["id"] != player["id"] and not p.get("is_bankrupt", False):
                game_state, charge_result = charge_player_to_player(
                    game_state,
                    p["id"],
                    player["id"],
                    value,
                    reason="card_collect_from_each_player",
                )
                total_collected += float(charge_result.get("paid_now", 0) or 0)
        player = _get_player_by_id(player["id"], game_state) or player
        logs.append({"event_type": "community_chest", "description": f"Collected ${value:.2f} from each player."})

    elif effect == "pay_each_player":
        # Pay value to each active player
        active_others = [p for p in game_state.get("players", []) if p["id"] != player["id"] and not p.get("is_bankrupt", False)]
        total_paid = value * len(active_others)
        for other_player in active_others:
            game_state, _ = charge_player_to_player(
                game_state,
                player["id"],
                other_player["id"],
                value,
                reason="card_pay_each_player",
            )
        player = _get_player_by_id(player["id"], game_state) or player
        logs.append({"event_type": "community_chest", "description": f"Paid ${value:.2f} to each player."})

    elif effect == "go_to_jail":
        player["current_position"] = JAIL_POSITION
        player["is_jailed"] = True
        player["jail_turns_remaining"] = 3
        player["consecutive_doubles"] = 0
        game_state = _update_player_state(game_state, player)
        logs.append({"event_type": "jail_sent", "description": "Sent to jail!"})

    elif effect == "get_out_of_jail_free":
        player["has_jail_card"] = True
        logs.append({"event_type": "community_chest", "description": "Received Get Out of Jail Free card."})

    elif effect == "move_back":
        steps = int(value)
        player["current_position"] = move_player(player["current_position"], -steps)[0]
        game_state = _update_player_state(game_state, player)
        player, game_state, econ, land_logs = resolve_space(
            player, game_state, econ, settings, redis_client, socketio_instance, match_id
        )
        logs.extend(land_logs)

    elif effect == "street_repairs":
        # Pay per building and hotel
        props = [
            p for p in game_state.get("properties", [])
            if p.get("owner_id") == player["id"]
        ]
        total = 0.0
        for p in props:
            building_count, hotel_count = split_development_for_repairs(
                p.get("dev_level", 0),
                game_state,
                econ,
                game_state.get("settings", {}),
            )
            total += 25.0 * building_count
            total += float(value or 0) * hotel_count
        player["balance"] = round(float(player["balance"]) - total, 2)
        logs.append({"event_type": "income_tax", "description": f"Paid ${total:.2f} in street repairs."})

    elif effect == "street_repairs_community":
        # $40/building, $115/hotel
        props = [
            p for p in game_state.get("properties", [])
            if p.get("owner_id") == player["id"]
        ]
        total = 0.0
        for p in props:
            building_count, hotel_count = split_development_for_repairs(
                p.get("dev_level", 0),
                game_state,
                econ,
                game_state.get("settings", {}),
            )
            total += 40.0 * building_count
            total += 115.0 * hotel_count
        player["balance"] = round(float(player["balance"]) - total, 2)
        logs.append({"event_type": "income_tax", "description": f"Paid ${total:.2f} in street repairs."})

    elif effect == "collect_welfare_bonus":
        welfare = float(econ.get("welfare_payout", 0))
        bonus = round(welfare * 2, 2)
        game_state, credit_result = credit_player_with_debt_settlement(game_state, player["id"], bonus)
        player = credit_result.get("player") or player
        logs.append({"event_type": "community_chest", "description": f"Received welfare bonus of ${bonus:.2f}."})

    return player, game_state, econ, logs


# Position constant for jail
JAIL_POSITION = 11


# ---------------------------------------------------------------------------
# Auction
# ---------------------------------------------------------------------------

def start_auction(prop: dict, game_state: dict, redis_client, socketio_instance, match_id: int) -> None:
    """Start an auction for an unowned property. Bids tracked in Redis."""
    prop_id = prop["id"]
    bid_key = f"game:{match_id}:auction:{prop_id}:bids"
    # Initialize with starting bid of 1 for each active player
    redis_client.delete(bid_key)
    starting_bid = max(1.0, float(prop.get("base_price", 10)) * 0.1)
    redis_client.set(f"game:{match_id}:auction:{prop_id}:current_bid", starting_bid)
    redis_client.set(f"game:{match_id}:auction:{prop_id}:current_bidder", "")
    redis_client.set(f"game:{match_id}:auction:{prop_id}:active", "1")
    reset_auction_timer(match_id, prop_id, redis_client, socketio_instance)

    socketio_instance.emit(
        "auction_start",
        {
            "property": dict(prop),
            "property_id": prop_id,
            "position": prop.get("board_position"),
            "property_name": prop["name"],
            "starting_bid": starting_bid,
            "countdown_seconds": AUCTION_COUNTDOWN_SECONDS,
            "match_id": match_id,
        },
        room=str(match_id),
    )
    from app.engine.bots import queue_bot_auction_reactions
    queue_bot_auction_reactions(match_id, game_state=game_state, reason="auction_start")


def reset_auction_timer(match_id: int, prop_id: int, redis_client, socketio_instance) -> None:
    close_token = uuid.uuid4().hex
    redis_client.set(f"game:{match_id}:auction:{prop_id}:close_token", close_token)
    app_obj = current_app._get_current_object()
    socketio_instance.start_background_task(
        _auction_auto_close_task,
        app_obj,
        match_id,
        prop_id,
        close_token,
        redis_client,
        socketio_instance,
    )


def _auction_auto_close_task(app_obj, match_id: int, prop_id: int, close_token: str, redis_client, socketio_instance) -> None:
    socketio_instance.sleep(AUCTION_COUNTDOWN_SECONDS)

    with app_obj.app_context():
        active_key = f"game:{match_id}:auction:{prop_id}:active"
        close_token_key = f"game:{match_id}:auction:{prop_id}:close_token"
        if not redis_client.get(active_key):
            return
        if redis_client.get(close_token_key) != close_token:
            return

        from app.engine.game_loop import (
            broadcast_game_state_snapshot,
            load_game_state,
            persist_game_state,
        )

        game_state = load_game_state(match_id, redis_client)
        if not game_state:
            return

        econ = game_state.get("econ", {})
        game_state, econ, _ = resolve_auction(
            prop_id,
            game_state,
            econ,
            redis_client,
            socketio_instance,
            match_id,
        )
        game_state = dict(game_state)
        game_state["econ"] = econ
        persist_game_state(game_state, match_id, redis_client)
        broadcast_game_state_snapshot(socketio_instance, match_id, game_state)


def resolve_auction(prop_id: int, game_state: dict, econ: dict, redis_client, socketio_instance, match_id: int) -> tuple[dict, dict, list[dict]]:
    """
    Close auction, transfer property to highest bidder.
    Returns (updated_game_state, updated_econ, logs).
    """
    bid_key = f"game:{match_id}:auction:{prop_id}:bids"
    current_bid_key = f"game:{match_id}:auction:{prop_id}:current_bid"
    bidder_key = f"game:{match_id}:auction:{prop_id}:current_bidder"

    current_bid = float(redis_client.get(current_bid_key) or 0)
    winner_id_raw = redis_client.get(bidder_key)
    logs = []

    if not winner_id_raw:
        # No bids — property stays unowned
        redis_client.delete(f"game:{match_id}:auction:{prop_id}:active")
        redis_client.delete(f"game:{match_id}:auction:{prop_id}:close_token")
        prop = next((p for p in game_state.get("properties", []) if p["id"] == prop_id), None)
        socketio_instance.emit(
            "auction_end",
            {
                "property_id": prop_id,
                "position": prop.get("board_position") if prop else None,
                "property_name": prop.get("name") if prop else "",
                "winner_id": None,
                "winner_name": None,
                "winner_balance": None,
                "amount": 0,
            },
            room=str(match_id),
        )
        return game_state, econ, logs

    winner_id = int(winner_id_raw)

    # Deduct balance from winner, assign property
    updated_players = []
    for p in game_state.get("players", []):
        p = dict(p)
        if p["id"] == winner_id:
            p["balance"] = round(float(p["balance"]) - current_bid, 2)
        updated_players.append(p)

    updated_props = []
    for p in game_state.get("properties", []):
        p = dict(p)
        if p["id"] == prop_id:
            p["owner_id"] = winner_id
            p["current_value"] = float(p.get("base_price", current_bid))
        updated_props.append(p)

    game_state = dict(game_state)
    game_state["players"] = updated_players
    game_state["properties"] = updated_props

    redis_client.delete(f"game:{match_id}:auction:{prop_id}:active")
    redis_client.delete(f"game:{match_id}:auction:{prop_id}:close_token")

    prop = next((p for p in updated_props if p["id"] == prop_id), None)
    winner = next((p for p in updated_players if p["id"] == winner_id), None)

    logs.append({
        "event_type": "auction_won",
        "description": f"Player {winner_id} won auction for property {prop_id} at ${current_bid:.2f}.",
    })
    socketio_instance.emit(
        "auction_end",
        {
            "property_id": prop_id,
            "position": prop.get("board_position") if prop else None,
            "property_name": prop.get("name") if prop else "",
            "winner_id": winner_id,
            "winner_name": winner.get("username") if winner else f"Player {winner_id}",
            "winner_balance": winner.get("balance") if winner else None,
            "amount": current_bid,
        },
        room=str(match_id),
    )
    return game_state, econ, logs
