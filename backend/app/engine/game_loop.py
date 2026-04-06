"""
Core game loop engine for PoorUp.
All state mutations flow through Redis first; PostgreSQL is persisted async.
"""
import json
import random
import string
from datetime import datetime
from typing import Any

from app import db
from app.engine.economy import (
    compute_gini_coefficient,
    drift_economy,
    apply_income_tax,
    apply_property_tax,
    apply_per_turn_tax,
    pay_welfare,
    apply_hyper_inflation,
    get_player_properties,
)
from app.engine.analytics import (
    ensure_lobbying_stats,
    ensure_player_finance_history,
    initialize_lobbying_stats,
    initialize_player_finance_history,
    record_lobbying_resolution,
    record_player_finance_snapshot,
    sync_lobbying_policy_pool,
)
from app.engine.events import (
    move_player,
    resolve_space,
    BOARD_SIZE,
    TAX_INCOME_POSITION,
    TAX_LUXURY_POSITION,
    TAX_SUPER_POSITION,
)
from app.engine.taxation import (
    ensure_tax_stats,
    initialize_tax_stats,
    record_budget_history_snapshot,
    record_tax_payment,
    record_welfare_distribution,
)
from app.engine.social import ensure_social_state, resolve_end_of_round_social_state
from app.engine.deals import (
    attach_deals_snapshot,
    decrement_round_deadlines,
    decrement_rotation_deadlines,
    decrement_turn_deadlines,
    expire_player_clauses,
)
from app.engine.debt import (
    calculate_player_liquidation_value,
    clear_player_debts,
    credit_player_with_debt_settlement,
    get_total_pending_player_debt,
    has_pending_player_debt,
    round_money,
    settle_player_debts,
)
from app.utils.settings import normalize_government_type, normalize_settings_payload

# Board layout — full 48-position board
BOARD = [
    {"position": 0,  "name": "START",              "region": None,           "group_color": None,      "base_price": None,  "type": "start"},
    {"position": 1,  "name": "Lagos",               "region": "Africa",       "group_color": "#8B4513", "base_price": 60,    "type": "property"},
    {"position": 2,  "name": "Nairobi",             "region": "Africa",       "group_color": "#8B4513", "base_price": 60,    "type": "property"},
    {"position": 3,  "name": "Community Chest",     "region": None,           "group_color": None,      "base_price": None,  "type": "community_chest"},
    {"position": 4,  "name": "Cairo",               "region": "Africa",       "group_color": "#8B4513", "base_price": 100,   "type": "property"},
    {"position": 5,  "name": "Income Tax",          "region": None,           "group_color": None,      "base_price": None,  "type": "tax"},
    {"position": 6,  "name": "Mumbai Airport",      "region": "Transit",      "group_color": "#6B7280", "base_price": 200,   "type": "transit"},
    {"position": 7,  "name": "Delhi",               "region": "South Asia",   "group_color": "#EC4899", "base_price": 100,   "type": "property"},
    {"position": 8,  "name": "Chance",              "region": None,           "group_color": None,      "base_price": None,  "type": "chance"},
    {"position": 9,  "name": "Karachi",             "region": "South Asia",   "group_color": "#EC4899", "base_price": 120,   "type": "property"},
    {"position": 10, "name": "Dhaka",               "region": "South Asia",   "group_color": "#EC4899", "base_price": 140,   "type": "property"},
    {"position": 11, "name": "Jail / Just Visiting","region": None,           "group_color": None,      "base_price": None,  "type": "jail"},
    {"position": 12, "name": "Istanbul",            "region": "Middle East",  "group_color": "#F59E0B", "base_price": 140,   "type": "property"},
    {"position": 13, "name": "Tehran",              "region": "Middle East",  "group_color": "#F59E0B", "base_price": 160,   "type": "property"},
    {"position": 14, "name": "Riyadh",              "region": "Middle East",  "group_color": "#F59E0B", "base_price": 180,   "type": "property"},
    {"position": 15, "name": "Dubai Airport",       "region": "Transit",      "group_color": "#6B7280", "base_price": 200,   "type": "transit"},
    {"position": 16, "name": "Moscow",              "region": "Eastern Europe","group_color": "#DC2626", "base_price": 180,   "type": "property"},
    {"position": 17, "name": "Community Chest",     "region": None,           "group_color": None,      "base_price": None,  "type": "community_chest"},
    {"position": 18, "name": "St. Petersburg",      "region": "Eastern Europe","group_color": "#DC2626", "base_price": 200,   "type": "property"},
    {"position": 19, "name": "Kiev",                "region": "Eastern Europe","group_color": "#DC2626", "base_price": 220,   "type": "property"},
    {"position": 20, "name": "Free Space",          "region": None,           "group_color": None,      "base_price": None,  "type": "free"},
    {"position": 21, "name": "Berlin",              "region": "Western Europe","group_color": "#EAB308", "base_price": 220,   "type": "property"},
    {"position": 22, "name": "Chance",              "region": None,           "group_color": None,      "base_price": None,  "type": "chance"},
    {"position": 23, "name": "Paris",               "region": "Western Europe","group_color": "#EAB308", "base_price": 240,   "type": "property"},
    {"position": 24, "name": "London",              "region": "Western Europe","group_color": "#EAB308", "base_price": 260,   "type": "property"},
    {"position": 25, "name": "London Heathrow",     "region": "Transit",      "group_color": "#6B7280", "base_price": 200,   "type": "transit"},
    {"position": 26, "name": "Shanghai",            "region": "China",        "group_color": "#F97316", "base_price": 260,   "type": "property"},
    {"position": 27, "name": "Beijing",             "region": "China",        "group_color": "#F97316", "base_price": 280,   "type": "property"},
    {"position": 28, "name": "Chongqing",           "region": "China",        "group_color": "#F97316", "base_price": 300,   "type": "property"},
    {"position": 29, "name": "Community Chest",     "region": None,           "group_color": None,      "base_price": None,  "type": "community_chest"},
    {"position": 30, "name": "Go To Jail",          "region": None,           "group_color": None,      "base_price": None,  "type": "go_to_jail"},
    {"position": 31, "name": "Tokyo",               "region": "East Asia",    "group_color": "#06B6D4", "base_price": 300,   "type": "property"},
    {"position": 32, "name": "Seoul",               "region": "East Asia",    "group_color": "#06B6D4", "base_price": 320,   "type": "property"},
    {"position": 33, "name": "Chance",              "region": None,           "group_color": None,      "base_price": None,  "type": "chance"},
    {"position": 34, "name": "Sydney",              "region": "Oceania",      "group_color": "#06B6D4", "base_price": 320,   "type": "property"},
    {"position": 35, "name": "Melbourne",           "region": "Oceania",      "group_color": "#06B6D4", "base_price": 340,   "type": "property"},
    {"position": 36, "name": "JFK Airport",         "region": "Transit",      "group_color": "#6B7280", "base_price": 200,   "type": "transit"},
    {"position": 37, "name": "São Paulo",           "region": "Latin America", "group_color": "#16A34A", "base_price": 350,   "type": "property"},
    {"position": 38, "name": "Buenos Aires",        "region": "Latin America", "group_color": "#16A34A", "base_price": 370,   "type": "property"},
    {"position": 39, "name": "Luxury Tax",          "region": None,           "group_color": None,      "base_price": None,  "type": "tax"},
    {"position": 40, "name": "New York",            "region": "North America", "group_color": "#16A34A", "base_price": 400,   "type": "property"},
    {"position": 41, "name": "Los Angeles",         "region": "North America", "group_color": "#16A34A", "base_price": 400,   "type": "property"},
    {"position": 42, "name": "Community Chest",     "region": None,           "group_color": None,      "base_price": None,  "type": "community_chest"},
    {"position": 43, "name": "Chicago",             "region": "North America", "group_color": "#2563EB", "base_price": 420,   "type": "property"},
    {"position": 44, "name": "Chance",              "region": None,           "group_color": None,      "base_price": None,  "type": "chance"},
    {"position": 45, "name": "Washington D.C.",     "region": "North America", "group_color": "#2563EB", "base_price": 440,   "type": "property"},
    {"position": 46, "name": "Silicon Valley",      "region": "North America", "group_color": "#2563EB", "base_price": 450,   "type": "property"},
    {"position": 47, "name": "Super Tax",           "region": None,           "group_color": None,      "base_price": None,  "type": "tax"},
]

BOARD_BY_POSITION = {space["position"]: space for space in BOARD}

DEFAULT_SETTINGS = {
    "starting_money": 1500,
    "government_type": "liberal_democracy",
    "game_mode": "standard",
    "auction_enabled": True,
    "mortgage_enabled": True,
    "deals_enabled": True,
    "private_equity_enabled": True,
    "uprisings_enabled": True,
    "tax_every_turn": False,
    "income_tax_on_pass_go": True,
    "property_tax_every_n_rounds": 5,
    "lobbying_enabled": True,
    "trading_enabled": True,
    "chance_cards_enabled": True,
    "community_chest_enabled": True,
    "hyper_inflation_trigger": True,
    "hyper_inflation_round": 50,
    "go_salary": 200,
    "max_players": 6,
    "turn_timer_enabled": True,
    "turn_time_limit_seconds": 90,
    "allow_spectators": True,
    "rage_system_enabled": True,
    "welfare_system_enabled": True,
    "welfare_balance_cap": 0,
    "policy_voting_enabled": True,
    "jail_enabled": True,
    "free_parking_pot_enabled": False,
    "double_on_go": False,
    "max_active_deals_per_player": 3,
    "max_rent_discount_percent": 90,
    "max_private_equity_payout_multiple": 1.75,
}

# Chance cards seed data
REMOVED_CARD_EFFECT_TYPES = {"get_out_of_jail_free", "go_to_jail"}


CHANCE_CARDS = [
    {"deck_type": "chance", "card_text": "Advance to START — Collect GO salary.", "effect_type": "advance_to_start", "effect_value": None},
    {"deck_type": "chance", "card_text": "Advance to Shanghai.", "effect_type": "advance_to_position", "effect_value": 26},
    {"deck_type": "chance", "card_text": "Advance to London.", "effect_type": "advance_to_position", "effect_value": 24},
    {"deck_type": "chance", "card_text": "Advance to nearest Airport.", "effect_type": "advance_to_nearest_transit", "effect_value": None},
    {"deck_type": "chance", "card_text": "Bank pays dividend — Collect $50.", "effect_type": "collect", "effect_value": 50},
    {"deck_type": "chance", "card_text": "Go Back 3 Spaces.", "effect_type": "move_back", "effect_value": 3},
    {"deck_type": "chance", "card_text": "Make general repairs — $25 per building, $100 per hotel.", "effect_type": "street_repairs", "effect_value": 100},
    {"deck_type": "chance", "card_text": "Pay $15 poor tax.", "effect_type": "pay", "effect_value": 15},
    {"deck_type": "chance", "card_text": "Take a trip to Dubai Airport.", "effect_type": "advance_to_position", "effect_value": 15},
    {"deck_type": "chance", "card_text": "Take a walk to Free Space.", "effect_type": "advance_to_position", "effect_value": 20},
    {"deck_type": "chance", "card_text": "You are assessed street repairs — $40 per building, $115 per hotel.", "effect_type": "street_repairs_community", "effect_value": 115},
    {"deck_type": "chance", "card_text": "Receive consulting fee — Collect $25.", "effect_type": "collect", "effect_value": 25},
    {"deck_type": "chance", "card_text": "Elected board chairperson — Pay $50 to each player.", "effect_type": "pay_each_player", "effect_value": 50},
    {"deck_type": "chance", "card_text": "Loan matures — Collect $150.", "effect_type": "collect", "effect_value": 150},
]

# Community Chest cards seed data
COMMUNITY_CHEST_CARDS = [
    {"deck_type": "community_chest", "card_text": "Advance to START — Collect GO salary.", "effect_type": "advance_to_start", "effect_value": None},
    {"deck_type": "community_chest", "card_text": "Bank error in your favor — Collect $200.", "effect_type": "collect", "effect_value": 200},
    {"deck_type": "community_chest", "card_text": "Doctor's fee — Pay $50.", "effect_type": "pay", "effect_value": 50},
    {"deck_type": "community_chest", "card_text": "From sale of stock — Collect $50.", "effect_type": "collect", "effect_value": 50},
    {"deck_type": "community_chest", "card_text": "Grand Opera Night — Collect $50 from each player.", "effect_type": "collect_from_each_player", "effect_value": 50},
    {"deck_type": "community_chest", "card_text": "Holiday Fund matures — Collect $100.", "effect_type": "collect", "effect_value": 100},
    {"deck_type": "community_chest", "card_text": "Income tax refund — Collect $20.", "effect_type": "collect", "effect_value": 20},
    {"deck_type": "community_chest", "card_text": "It is your birthday — Collect $10 from each player.", "effect_type": "collect_from_each_player", "effect_value": 10},
    {"deck_type": "community_chest", "card_text": "Life insurance matures — Collect $100.", "effect_type": "collect", "effect_value": 100},
    {"deck_type": "community_chest", "card_text": "Hospital fees — Pay $100.", "effect_type": "pay", "effect_value": 100},
    {"deck_type": "community_chest", "card_text": "School fees — Pay $150.", "effect_type": "pay", "effect_value": 150},
    {"deck_type": "community_chest", "card_text": "Receive consultancy fee — Collect $25.", "effect_type": "collect", "effect_value": 25},
    {"deck_type": "community_chest", "card_text": "You inherit $100 — Collect $100.", "effect_type": "collect", "effect_value": 100},
    {"deck_type": "community_chest", "card_text": "Welfare bonus — Collect current welfare payout doubled.", "effect_type": "collect_welfare_bonus", "effect_value": None},
]


def generate_room_code() -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


def initialize_government(gov_type: str) -> dict:
    gov_type = normalize_government_type(gov_type)

    if gov_type == "minarchism":
        return {
            "gov_type": gov_type,
            "bailout_enabled": False,
            "welfare_payout": 0.0,
            "tax_multiplier": 0.05,
            "stability": 0.90,
            "inflation_rate": round(random.uniform(0.01, 0.04), 4),
            "interest_rate": round(random.uniform(0.03, 0.07), 4),
            "treasury_balance": 0.0,
        }
    elif gov_type == "social_democracy":
        return {
            "gov_type": gov_type,
            "bailout_enabled": random.choice([True, False]),
            "welfare_payout": round(random.uniform(60, 100), 2),
            "tax_multiplier": round(random.uniform(0.40, 0.50), 3),
            "stability": 0.50,
            "inflation_rate": round(random.uniform(0.03, 0.07), 4),
            "interest_rate": round(random.uniform(0.05, 0.10), 4),
            "treasury_balance": 2000.0,
        }
    else:  # liberal_democracy (default)
        return {
            "gov_type": gov_type,
            "bailout_enabled": False,
            "welfare_payout": round(random.uniform(10, 50), 2),
            "tax_multiplier": round(random.uniform(0.15, 0.25), 3),
            "stability": 0.70,
            "inflation_rate": round(random.uniform(0.02, 0.06), 4),
            "interest_rate": round(random.uniform(0.04, 0.09), 4),
            "treasury_balance": 500.0,
        }


def initialize_game_state(match, match_players, redis_client, socketio_instance) -> dict:
    """
    Build initial Redis game state for a match.
    Seeds card decks, properties, players, government, and turn order.
    """
    from app.models.card import Card
    from app.models.property import Property as PropertyModel
    from app.models.policy import seed_default_lobbying_policies
    from app.models.government import Government

    settings = {
        **DEFAULT_SETTINGS,
        **normalize_settings_payload(match.settings_json or {}, set(DEFAULT_SETTINGS.keys())),
    }
    gov_type = normalize_government_type(settings.get("government_type", DEFAULT_SETTINGS["government_type"]))
    settings["government_type"] = gov_type

    # Initialize government in DB
    gov_data = initialize_government(gov_type)
    gov = Government(
        match_id=match.id,
        gov_type=gov_data["gov_type"],
        stability=gov_data["stability"],
        treasury_balance=gov_data["treasury_balance"],
        welfare_payout=gov_data["welfare_payout"],
        tax_multiplier=gov_data["tax_multiplier"],
        inflation_rate=gov_data["inflation_rate"],
        interest_rate=gov_data["interest_rate"],
    )
    db.session.add(gov)

    # Initialize properties in DB
    properties_data = []
    for space in BOARD:
        if space["type"] in ("property", "transit"):
            prop = PropertyModel(
                match_id=match.id,
                name=space["name"],
                region=space.get("region"),
                group_color=space.get("group_color"),
                board_position=space["position"],
                base_price=space["base_price"],
                current_value=space["base_price"],
                dev_level=0,
                owner_id=None,
                is_mortgaged=False,
                property_type=space["type"],
            )
            db.session.add(prop)
            properties_data.append(prop)

    db.session.flush()  # Get IDs

    seeded_policies = seed_default_lobbying_policies(match.id)

    # Seed cards if not already seeded
    if Card.query.count() == 0:
        for card_data in CHANCE_CARDS + COMMUNITY_CHEST_CARDS:
            card = Card(
                deck_type=card_data["deck_type"],
                card_text=card_data["card_text"],
                effect_type=card_data["effect_type"],
                effect_value=card_data.get("effect_value"),
            )
            db.session.add(card)
        db.session.flush()

    # Build card decks for Redis (shuffled)
    chance_cards = Card.query.filter_by(deck_type="chance").all()
    community_cards = Card.query.filter_by(deck_type="community_chest").all()
    chance_shuffled = [c.to_dict() for c in chance_cards if c.effect_type not in REMOVED_CARD_EFFECT_TYPES]
    community_shuffled = [c.to_dict() for c in community_cards if c.effect_type not in REMOVED_CARD_EFFECT_TYPES]
    random.shuffle(chance_shuffled)
    random.shuffle(community_shuffled)

    chance_key = f"game:{match.id}:chance_deck"
    community_key = f"game:{match.id}:community_deck"
    redis_client.delete(chance_key)
    redis_client.delete(community_key)
    for card in chance_shuffled:
        redis_client.rpush(chance_key, json.dumps(card))
    for card in community_shuffled:
        redis_client.rpush(community_key, json.dumps(card))

    # Build player state
    player_states = []
    for mp in match_players:
        player_states.append({
            "id": mp.id,
            "user_id": mp.user_id,
            "username": mp.user.username,
            "color_hex": mp.color_hex,
            "balance": float(settings.get("starting_money", 1500)),
            "influence_score": 0.0,
            "approval_rating": 50.0,
            "current_position": 0,
            "is_jailed": False,
            "jail_turns_remaining": 0,
            "team_id": mp.team_id,
            "is_bankrupt": False,
            "is_connected": True,
            "has_jail_card": False,
            "consecutive_doubles": 0,
            "is_ready": True,
            "is_bot": bool(mp.is_bot),
        })
        # Persist starting balance
        mp.balance = settings.get("starting_money", 1500)

    # Build property state
    prop_states = []
    for prop in properties_data:
        prop_states.append({
            "id": prop.id,
            "match_id": match.id,
            "name": prop.name,
            "region": prop.region,
            "group_color": prop.group_color,
            "board_position": prop.board_position,
            "base_price": float(prop.base_price) if prop.base_price else None,
            "current_value": float(prop.current_value) if prop.current_value else None,
            "dev_level": 0,
            "owner_id": None,
            "is_mortgaged": False,
            "property_type": prop.property_type,
        })

    # Randomize turn order
    turn_order = [mp.id for mp in match_players]
    random.shuffle(turn_order)

    # Full game state
    game_state = {
        "match_id": match.id,
        "status": "active",
        "current_round": 1,
        "current_turn_index": 0,
        "turn_order": turn_order,
        "current_player_id": turn_order[0] if turn_order else None,
        "players": player_states,
        "properties": prop_states,
        "econ": gov_data,
        "settings": settings,
        "rage": 0.0,
        "free_parking_pot": 0.0,
        "log_buffer": [],
        "tax_stats": initialize_tax_stats(
            player_states,
            current_round=1,
            treasury_balance=float(gov_data.get("treasury_balance", 0) or 0),
            free_parking_claim=0.0,
        ),
        "lobbying_stats": initialize_lobbying_stats(player_states, seeded_policies),
        "pending_debts": [],
    }
    game_state = initialize_player_finance_history(game_state)
    game_state = ensure_social_state(game_state)
    game_state = attach_deals_snapshot(game_state, match.id)

    # Write to Redis
    _write_game_state_to_redis(game_state, match.id, redis_client)

    # Update match in DB
    match.status = "active"
    match.current_round = 1
    db.session.commit()

    return game_state


def _write_game_state_to_redis(game_state: dict, match_id: int, redis_client) -> None:
    mid = str(match_id)
    redis_client.set(f"game:{mid}:state", json.dumps(game_state))
    redis_client.set(f"game:{mid}:current_turn", str(game_state.get("current_player_id", "")))
    redis_client.set(f"game:{mid}:rage", str(game_state.get("rage", 0.0)))
    redis_client.set(f"game:{mid}:social", json.dumps(game_state.get("social", {})))

    turn_order = game_state.get("turn_order", [])
    redis_client.delete(f"game:{mid}:turn_order")
    for pid in turn_order:
        redis_client.rpush(f"game:{mid}:turn_order", pid)

    econ = game_state.get("econ", {})
    redis_client.set(f"game:{mid}:econ", json.dumps(econ))


def _synchronize_property_metadata(game_state: dict) -> dict:
    properties = game_state.get("properties", [])
    if not properties:
        return game_state

    updated = False
    normalized_properties = []

    for prop in properties:
        normalized_prop = dict(prop)
        board_space = BOARD_BY_POSITION.get(normalized_prop.get("board_position"))

        if board_space and board_space.get("type") in ("property", "transit"):
            if normalized_prop.get("name") != board_space.get("name"):
                normalized_prop["name"] = board_space.get("name")
                updated = True

            if normalized_prop.get("region") != board_space.get("region"):
                normalized_prop["region"] = board_space.get("region")
                updated = True

            if normalized_prop.get("group_color") != board_space.get("group_color"):
                normalized_prop["group_color"] = board_space.get("group_color")
                updated = True

            base_price = board_space.get("base_price")
            normalized_base_price = float(base_price) if base_price is not None else None
            if normalized_prop.get("base_price") != normalized_base_price:
                normalized_prop["base_price"] = normalized_base_price
                updated = True

            if normalized_prop.get("property_type") != board_space.get("type"):
                normalized_prop["property_type"] = board_space.get("type")
                updated = True

            if normalized_prop.get("current_value") is None and normalized_base_price is not None:
                normalized_prop["current_value"] = normalized_base_price
                updated = True

        normalized_properties.append(normalized_prop)

    if not updated:
        return game_state

    next_state = dict(game_state)
    next_state["properties"] = normalized_properties
    return next_state


def load_game_state(match_id: int, redis_client) -> dict | None:
    from app.models.policy import Lobbying as LobbyContribution, Policy

    raw = redis_client.get(f"game:{match_id}:state")
    if raw is None:
        return None
    game_state = _synchronize_property_metadata(json.loads(raw))
    game_state = ensure_tax_stats(game_state)

    policy_records = Policy.query.filter_by(match_id=match_id).all()
    game_state = ensure_lobbying_stats(game_state, policy_records=policy_records)
    if not (game_state.get("lobbying_stats") or {}).get("policy_pools"):
        game_state = dict(game_state)
        game_state["lobbying_stats"] = initialize_lobbying_stats(game_state.get("players", []), policy_records)

    if policy_records:
        for policy in policy_records:
            entries = LobbyContribution.query.filter_by(match_id=match_id, policy_id=policy.id).all()
            game_state = sync_lobbying_policy_pool(game_state, policy, entries)

    game_state = ensure_player_finance_history(game_state)
    if not (game_state.get("player_finance_history") or {}).get("last_fingerprint"):
        game_state = record_player_finance_snapshot(game_state, force=True)
    game_state = ensure_social_state(game_state)
    return attach_deals_snapshot(game_state, match_id)


def persist_game_state(game_state: dict, match_id: int, redis_client) -> None:
    """Write game state to Redis. PostgreSQL sync happens via persist_to_db."""
    next_state = ensure_tax_stats(game_state)
    next_state = ensure_lobbying_stats(next_state)
    next_state = record_player_finance_snapshot(next_state)
    next_state = ensure_social_state(next_state)
    next_state = attach_deals_snapshot(next_state, match_id)
    game_state.clear()
    game_state.update(next_state)
    _write_game_state_to_redis(game_state, match_id, redis_client)


def broadcast_game_state_snapshot(socketio_instance, match_id: int, game_state: dict) -> None:
    next_state = ensure_tax_stats(game_state)
    next_state = ensure_lobbying_stats(next_state)
    next_state = record_player_finance_snapshot(next_state)
    next_state = ensure_social_state(next_state)
    next_state = attach_deals_snapshot(next_state, match_id)
    game_state.clear()
    game_state.update(next_state)
    socketio_instance.emit(
        "game_state_snapshot",
        {"state": game_state},
        room=str(match_id),
    )
    from app.engine.bots import queue_bot_state_evaluation
    queue_bot_state_evaluation(match_id, game_state, reason="snapshot")


def persist_to_db(game_state: dict, match_id: int) -> None:
    """Asynchronously persist key game state fields to PostgreSQL."""
    from app.models.player import Match, MatchPlayer
    from app.models.property import Property as PropertyModel
    from app.models.government import Government

    try:
        match = Match.query.get(match_id)
        if match:
            match.current_round = game_state.get("current_round", match.current_round)
            match.status = game_state.get("status", match.status)

        for p_data in game_state.get("players", []):
            mp = MatchPlayer.query.get(p_data["id"])
            if mp:
                mp.balance = p_data["balance"]
                mp.current_position = p_data["current_position"]
                mp.is_jailed = p_data.get("is_jailed", False)
                mp.jail_turns_remaining = p_data.get("jail_turns_remaining", 0)
                mp.is_bankrupt = p_data.get("is_bankrupt", False)
                mp.is_connected = p_data.get("is_connected", True)
                mp.influence_score = p_data.get("influence_score", 0)
                mp.approval_rating = p_data.get("approval_rating", 50)
                mp.has_jail_card = p_data.get("has_jail_card", False)

        for prop_data in game_state.get("properties", []):
            prop = PropertyModel.query.get(prop_data["id"])
            if prop:
                prop.owner_id = prop_data.get("owner_id")
                prop.dev_level = prop_data.get("dev_level", 0)
                prop.is_mortgaged = prop_data.get("is_mortgaged", False)
                prop.current_value = prop_data.get("current_value")

        econ = game_state.get("econ", {})
        gov = Government.query.filter_by(match_id=match_id).first()
        if gov:
            gov.stability = econ.get("stability", gov.stability)
            gov.treasury_balance = econ.get("treasury_balance", gov.treasury_balance)
            gov.welfare_payout = econ.get("welfare_payout", gov.welfare_payout)
            gov.tax_multiplier = econ.get("tax_multiplier", gov.tax_multiplier)
            gov.inflation_rate = econ.get("inflation_rate", gov.inflation_rate)
            gov.interest_rate = econ.get("interest_rate", gov.interest_rate)

        db.session.commit()
    except Exception as e:
        db.session.rollback()
        raise e


def get_full_game_state(match_id: int, redis_client) -> dict | None:
    return load_game_state(match_id, redis_client)


def _update_player_in_state(game_state: dict, updated_player: dict) -> dict:
    game_state = dict(game_state)
    game_state["players"] = [
        updated_player if p["id"] == updated_player["id"] else p
        for p in game_state["players"]
    ]
    return game_state


def _add_log_entry(game_state: dict, entry: dict, match_id: int, redis_client) -> dict:
    game_state = dict(game_state)
    log_buffer = list(game_state.get("log_buffer", []))
    entry["timestamp"] = datetime.utcnow().isoformat()
    log_buffer.append(entry)
    # Keep last 100 entries
    if len(log_buffer) > 100:
        log_buffer = log_buffer[-100:]
    game_state["log_buffer"] = log_buffer

    # Also push to Redis log buffer
    log_key = f"game:{match_id}:log_buffer"
    redis_client.rpush(log_key, json.dumps(entry))
    redis_client.ltrim(log_key, -100, -1)
    return game_state


def update_approval_ratings(players: list[dict], econ: dict) -> list[dict]:
    """Update approval ratings for all players based on government type."""
    gov_type = econ.get("gov_type", "liberal_democracy")
    updated = []
    for p in players:
        p = dict(p)
        if p.get("is_bankrupt", False):
            updated.append(p)
            continue
        rating = float(p.get("approval_rating", 50))
        if gov_type == "minarchism":
            rating -= random.uniform(1, 3)
        elif gov_type == "liberal_democracy":
            stability = float(econ.get("stability", 0.5))
            inflation = float(econ.get("inflation_rate", 0.03))
            delta = random.uniform(-5, 5) + stability * 5 - inflation * 20
            rating += delta
        elif gov_type == "social_democracy":
            treasury = float(econ.get("treasury_balance", 0))
            rating += 2 if treasury > 0 else -5
        p["approval_rating"] = round(max(0.0, min(100.0, rating)), 2)
        updated.append(p)
    return updated


def resolve_lobbying(game_state: dict, econ: dict, settings: dict, socketio_instance, match_id: int) -> tuple[dict, dict]:
    """
    Resolve all pending lobbying contributions at end of round.
    Returns (updated_game_state, updated_econ).
    """
    from app.models.policy import (
        Policy,
        Lobbying,
        calculate_lobbying_effect_multiplier,
        calculate_lobbying_success_chance,
        get_lobbying_policy_definition,
    )
    from app import db

    if not settings.get("lobbying_enabled", True):
        return game_state, econ

    policies = Policy.query.filter_by(match_id=match_id).all()
    for policy in policies:
        entries = Lobbying.query.filter_by(match_id=match_id, policy_id=policy.id).all()
        if not entries:
            continue

        total_contribution = round(sum(float(e.contribution or 0) for e in entries), 2)
        contributor_count = len({e.player_id for e in entries})
        success_chance = calculate_lobbying_success_chance(
            target_stat=policy.target_stat,
            total_contribution=total_contribution,
            contributor_count=contributor_count,
        )
        effect_multiplier = calculate_lobbying_effect_multiplier(
            target_stat=policy.target_stat,
            total_contribution=total_contribution,
            contributor_count=contributor_count,
        )

        success = random.random() < success_chance
        econ = dict(econ)
        gov_type = econ.get("gov_type", "liberal_democracy")
        definition = get_lobbying_policy_definition(target_stat=policy.target_stat) or {}
        base_value = abs(float(definition.get("effect_value", policy.effect_value or 0) or 0))
        effect_summary = None
        failure_reason = (
            f"{policy.policy_name} stalled after ${total_contribution:.2f} in lobbying "
            f"({success_chance * 100:.0f}% estimated odds)."
        )
        payload = {
            "policy_id": policy.id,
            "policy_name": policy.policy_name,
            "target_stat": policy.target_stat,
            "total_contribution": total_contribution,
            "contributor_count": contributor_count,
            "success_chance": round(success_chance * 100, 1),
        }

        if success:
            target = policy.target_stat

            if target == "tax_multiplier_decrease":
                delta = round(min(0.20, base_value * effect_multiplier), 4)
                econ["tax_multiplier"] = round(max(0.0, float(econ.get("tax_multiplier", 0.15)) - delta), 4)
                effect_summary = (
                    f"Tax multiplier dropped by {delta:.2f} to {econ['tax_multiplier']:.2f}."
                )
            elif target == "welfare_increase":
                if gov_type != "minarchism":
                    delta = round(min(35.0, base_value * effect_multiplier), 2)
                    econ["welfare_payout"] = round(min(100.0, float(econ.get("welfare_payout", 0)) + delta), 2)
                    effect_summary = (
                        f"Welfare rate rose by {delta:.1f} points to {econ['welfare_payout']:.1f}%."
                    )
                else:
                    success = False
            elif target == "welfare_decrease":
                if gov_type != "minarchism":
                    delta = round(min(35.0, base_value * effect_multiplier), 2)
                    econ["welfare_payout"] = round(max(0.0, float(econ.get("welfare_payout", 0)) - delta), 2)
                    effect_summary = (
                        f"Welfare rate fell by {delta:.1f} points to {econ['welfare_payout']:.1f}%."
                    )
                else:
                    success = False
            elif target == "rent_control":
                econ["rent_control_active"] = True
                stability_bonus = round(min(0.08, 0.03 * effect_multiplier), 4)
                econ["stability"] = round(min(1.0, float(econ.get("stability", 0.5)) + stability_bonus), 4)
                effect_summary = (
                    f"Rent control is active and stability improved by {stability_bonus * 100:.0f} points."
                )
            elif target == "deregulate_housing":
                econ["rent_control_active"] = False
                dev_boost = round(min(0.35, base_value * effect_multiplier), 4)
                econ["dev_value_multiplier"] = round(
                    float(econ.get("dev_value_multiplier", 1.0)) * (1.0 + dev_boost),
                    4,
                )
                effect_summary = (
                    f"Development values gained {dev_boost * 100:.0f}% (multiplier {econ['dev_value_multiplier']:.2f}x)."
                )
            elif target == "stabilization_fund":
                treasury_bonus = round(base_value * effect_multiplier, 2)
                stability_bonus = round(min(0.15, 0.04 * effect_multiplier), 4)
                econ["treasury_balance"] = round(float(econ.get("treasury_balance", 0)) + treasury_bonus, 2)
                econ["stability"] = round(min(1.0, float(econ.get("stability", 0.5)) + stability_bonus), 4)
                effect_summary = (
                    f"Treasury gained ${treasury_bonus:.2f} and stability improved by {stability_bonus * 100:.0f} points."
                )
            elif target == "tax_multiplier_increase":
                delta = round(min(0.20, base_value * effect_multiplier), 4)
                econ["tax_multiplier"] = round(min(2.0, float(econ.get("tax_multiplier", 0.15)) + delta), 4)
                effect_summary = (
                    f"Tax multiplier increased by {delta:.2f} to {econ['tax_multiplier']:.2f}."
                )
            elif target == "economic_stimulus":
                treasury = float(econ.get("treasury_balance", 0))
                active_players = [p for p in game_state.get("players", []) if not p.get("is_bankrupt", False)]
                planned_stimulus = round(min(250.0, base_value * effect_multiplier), 2)
                affordable_stimulus = round(treasury / len(active_players), 2) if active_players else 0.0
                actual_stimulus = round(min(planned_stimulus, max(0.0, affordable_stimulus)), 2)
                if active_players and actual_stimulus > 0:
                    updated = []
                    for p in game_state.get("players", []):
                        p = dict(p)
                        if not p.get("is_bankrupt", False):
                            p["balance"] = round(float(p["balance"]) + actual_stimulus, 2)
                        updated.append(p)
                    game_state = dict(game_state)
                    game_state["players"] = updated
                    total_cost = round(actual_stimulus * len(active_players), 2)
                    stability_bonus = round(min(0.08, 0.025 * effect_multiplier), 4)
                    econ["stability"] = round(min(1.0, float(econ.get("stability", 0.5)) + stability_bonus), 4)
                    effect_summary = (
                        f"Every active player received ${actual_stimulus:.2f}."
                    )
                    if actual_stimulus < planned_stimulus:
                        effect_summary = (
                            f"Treasury could only fund ${actual_stimulus:.2f} per active player."
                        )
                    effect_summary = (
                        f"{effect_summary} Stability improved by {stability_bonus * 100:.0f} points."
                    )
                    econ["treasury_balance"] = round(treasury - total_cost, 2)
                else:
                    success = False
                    failure_reason = (
                        f"{policy.policy_name} passed politically, but the treasury had no room to fund a stimulus."
                    )
            elif target == "bailout_enable":
                if gov_type != "minarchism":
                    econ["bailout_enabled"] = True
                    effect_summary = "Government bailouts are now enabled whenever the treasury can cover the rescue."
                else:
                    success = False
                    failure_reason = "Minarchism does not allow government bailouts."
            elif target == "bailout_disable":
                if gov_type != "minarchism":
                    econ["bailout_enabled"] = False
                    effect_summary = "Government bailouts are now disabled."
                else:
                    success = False
                    failure_reason = "Minarchism already runs without government bailouts."
            else:
                success = False
                failure_reason = f"{policy.policy_name} has no effect configured."

            if success:
                socketio_instance.emit(
                    "lobby_success",
                    {
                        **payload,
                        "effect_summary": effect_summary,
                    },
                    room=str(match_id),
                )
                policy.is_active = True
            else:
                socketio_instance.emit(
                    "lobby_failed",
                    {
                        **payload,
                        "reason": failure_reason,
                    },
                    room=str(match_id),
                )
        else:
            socketio_instance.emit(
                "lobby_failed",
                {
                    **payload,
                    "reason": failure_reason,
                },
                room=str(match_id),
            )

        game_state = record_lobbying_resolution(
            game_state,
            policy,
            success=success,
            effect_summary=effect_summary,
            failure_reason=failure_reason,
            total_contribution=total_contribution,
            contributor_count=contributor_count,
            success_chance=round(success_chance * 100, 1),
            round_number=game_state.get("current_round", 0),
        )

        # Clean up contributions
        for e in entries:
            db.session.delete(e)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()

    return game_state, econ


def run_turn(
    match_id: int,
    player_id: int,
    dice_result: dict,
    redis_client,
    socketio_instance,
) -> dict:
    """
    Execute a full turn sequence for the given player.
    Returns the updated game state.

    Turn order:
    1. START_TURN
    2. ROLL_DICE (dice_result passed in)
    3. MOVE
    4. LAND_RESOLUTION
    5. MANDATORY_TAXES
    6. ECONOMIC_UPDATE
    7. RAGE_CALCULATION
    8. UPRISING_CHECK
    9. POLICY_APPLY (at end of round)
    10. LOG_FLUSH
    11. CHECK_BANKRUPTCY
    12. CHECK_WIN
    13. END_TURN
    """
    game_state = load_game_state(match_id, redis_client)
    if game_state is None:
        raise ValueError(f"No game state found for match {match_id}")

    settings = game_state.get("settings", DEFAULT_SETTINGS)
    econ = game_state.get("econ", {})
    current_round = game_state.get("current_round", 1)

    # Find current player
    player = next((p for p in game_state["players"] if p["id"] == player_id), None)
    if player is None:
        raise ValueError(f"Player {player_id} not in game state")

    # Handle jailed player
    if player.get("is_jailed", False):
        if dice_result.get("is_doubles", False):
            # Roll doubles — free from jail
            player = dict(player)
            player["is_jailed"] = False
            player["jail_turns_remaining"] = 0
            game_state = _update_player_in_state(game_state, player)
            log_entry = {"event_type": "jail_released", "description": f"{player['username']} rolled doubles and escaped jail!", "player_id": player_id, "round": current_round, "turn": game_state.get("current_turn_index", 0)}
            game_state = _add_log_entry(game_state, log_entry, match_id, redis_client)
        else:
            player = dict(player)
            player["jail_turns_remaining"] = max(0, player.get("jail_turns_remaining", 0) - 1)
            if player["jail_turns_remaining"] <= 0:
                # Force release after 3 turns — pay bail
                bail = 50.0
                player["balance"] = round(float(player["balance"]) - bail, 2)
                player["is_jailed"] = False
                econ = dict(econ)
                econ["treasury_balance"] = round(float(econ.get("treasury_balance", 0)) + bail, 2)
                log_entry = {"event_type": "jail_released", "description": f"{player['username']} paid $50 bail after 3 turns.", "player_id": player_id, "round": current_round, "turn": 0}
            else:
                log_entry = {"event_type": "jail_sent", "description": f"{player['username']} is in jail ({player['jail_turns_remaining']} turns remaining).", "player_id": player_id, "round": current_round, "turn": 0}
            game_state = _update_player_in_state(game_state, player)
            game_state = _add_log_entry(game_state, log_entry, match_id, redis_client)

            if player.get("is_jailed", False):
                # Still jailed — end turn
                game_state = end_turn(game_state, player_id, dice_result, match_id, redis_client, socketio_instance, settings, econ, current_round)
                persist_game_state(game_state, match_id, redis_client)
                broadcast_game_state_snapshot(socketio_instance, match_id, game_state)
                return game_state

    # 2. ROLL_DICE (already done, result passed in)
    die1 = dice_result["die1"]
    die2 = dice_result["die2"]
    total = dice_result["total"]
    is_doubles = dice_result["is_doubles"]

    player = dict(player)

    # Track consecutive doubles
    if is_doubles:
        player["consecutive_doubles"] = player.get("consecutive_doubles", 0) + 1
        if player["consecutive_doubles"] >= 3:
            # 3 consecutive doubles — go to jail
            player["current_position"] = 11
            player["is_jailed"] = True
            player["jail_turns_remaining"] = 3
            player["consecutive_doubles"] = 0
            game_state = _update_player_in_state(game_state, player)
            log_entry = {"event_type": "jail_sent", "description": f"{player['username']} rolled 3 consecutive doubles and was jailed!", "player_id": player_id, "round": current_round, "turn": 0}
            game_state = _add_log_entry(game_state, log_entry, match_id, redis_client)
            socketio_instance.emit("dice_rolled", {"player_id": player_id, "player_name": player.get("username", "Player"), "die1": die1, "die2": die2, "total": total, "is_doubles": True}, room=str(match_id))
            game_state = end_turn(game_state, player_id, dice_result, match_id, redis_client, socketio_instance, settings, econ, current_round)
            persist_game_state(game_state, match_id, redis_client)
            broadcast_game_state_snapshot(socketio_instance, match_id, game_state)
            return game_state
    else:
        player["consecutive_doubles"] = 0

    socketio_instance.emit(
        "dice_rolled",
        {"player_id": player_id, "player_name": player.get("username", "Player"), "die1": die1, "die2": die2, "total": total, "is_doubles": is_doubles},
        room=str(match_id),
    )
    redis_client.set(f"game:{match_id}:dice", json.dumps({"die1": die1, "die2": die2, "total": total}))
    game_state = dict(game_state)
    game_state["dice_rolled_this_turn"] = True

    # 3. MOVE
    old_position = player["current_position"]
    new_position, passed_go = move_player(old_position, total)
    player["current_position"] = new_position
    game_state = _update_player_in_state(game_state, player)

    space_info = next((s for s in BOARD if s["position"] == new_position), {})
    socketio_instance.emit(
        "player_moved",
        {"player_id": player_id, "from": old_position, "to": new_position, "position": new_position, "passed_go": passed_go, "player_name": player.get("username", "Player"), "space_name": space_info.get("name", f"Space {new_position}")},
        room=str(match_id),
    )

    # Handle passing GO
    if passed_go and settings.get("income_tax_on_pass_go", True):
        go_salary = float(settings.get("go_salary", 200))
        if settings.get("double_on_go", False):
            go_salary *= 2
        # Collect GO salary
        game_state, credit_result = credit_player_with_debt_settlement(game_state, player_id, go_salary)
        player = credit_result.get("player") or dict(player)
        # Apply income tax on pass GO
        tax_amt, new_bal = apply_income_tax(player, econ, settings)
        player["balance"] = new_bal
        econ = dict(econ)
        econ["treasury_balance"] = round(float(econ.get("treasury_balance", 0)) + tax_amt, 2)
        if settings.get("free_parking_pot_enabled", False):
            game_state["free_parking_pot"] = round(float(game_state.get("free_parking_pot", 0) or 0) + tax_amt, 2)
        log_entry = {"event_type": "income_tax", "description": f"{player['username']} passed GO, collected ${go_salary:.2f} but paid ${tax_amt:.2f} income tax.", "player_id": player_id, "round": current_round, "turn": 0}
        game_state = _update_player_in_state(game_state, player)
        game_state = _add_log_entry(game_state, log_entry, match_id, redis_client)
        game_state = record_tax_payment(game_state, player_id, "income_tax", tax_amt)
        game_state = decrement_rotation_deadlines(game_state, match_id, beneficiary_id=player_id)
    elif passed_go:
        go_salary = float(settings.get("go_salary", 200))
        if settings.get("double_on_go", False):
            go_salary *= 2
        game_state, credit_result = credit_player_with_debt_settlement(game_state, player_id, go_salary)
        player = credit_result.get("player") or dict(player)
        game_state = _update_player_in_state(game_state, player)
        log_entry = {"event_type": "move", "description": f"{player['username']} passed GO and collected ${go_salary:.2f}.", "player_id": player_id, "round": current_round, "turn": 0}
        game_state = _add_log_entry(game_state, log_entry, match_id, redis_client)
        game_state = decrement_rotation_deadlines(game_state, match_id, beneficiary_id=player_id)

    # 4. LAND_RESOLUTION
    player = next((p for p in game_state["players"] if p["id"] == player_id), player)
    pre_resolution_player = dict(player)
    player, game_state, econ, land_logs = resolve_space(
        player, game_state, econ, settings, redis_client, socketio_instance, match_id
    )
    game_state = _update_player_in_state(game_state, player)
    game_state = dict(game_state)
    game_state["econ"] = econ

    if new_position == TAX_INCOME_POSITION:
        tax_amt, _ = apply_income_tax(pre_resolution_player, econ, settings)
        game_state = record_tax_payment(game_state, player_id, "income_tax", tax_amt)
    elif new_position == TAX_LUXURY_POSITION:
        tax_amt, _, _ = apply_luxury_tax(pre_resolution_player, econ)
        game_state = record_tax_payment(game_state, player_id, "luxury_tax", tax_amt)
    elif new_position == TAX_SUPER_POSITION:
        tax_amt, _, _ = apply_super_tax(pre_resolution_player, econ)
        game_state = record_tax_payment(game_state, player_id, "super_tax", tax_amt)

    for entry in land_logs:
        entry["player_id"] = player_id
        entry["round"] = current_round
        entry["turn"] = game_state.get("current_turn_index", 0)
        game_state = _add_log_entry(game_state, entry, match_id, redis_client)

    pending_action = game_state.get("pending_action")
    if pending_action and pending_action.get("type") == "buy_property":
        game_state = dict(game_state)
        game_state["pending_turn_context"] = {
            "player_id": player_id,
            "dice_result": dict(dice_result),
        }
        persist_game_state(game_state, match_id, redis_client)
        broadcast_game_state_snapshot(socketio_instance, match_id, game_state)
        return game_state

    return finalize_turn_resolution(
        game_state,
        player_id,
        dice_result,
        match_id,
        redis_client,
        socketio_instance,
    )


def finalize_turn_resolution(
    game_state: dict,
    player_id: int,
    dice_result: dict,
    match_id: int,
    redis_client,
    socketio_instance,
) -> dict:
    settings = game_state.get("settings", DEFAULT_SETTINGS)
    econ = game_state.get("econ", {})
    current_round = game_state.get("current_round", 1)

    # 5. MANDATORY_TAXES
    player = next((p for p in game_state["players"] if p["id"] == player_id), None)
    if player is None:
        raise ValueError(f"Player {player_id} not in game state")

    if settings.get("tax_every_turn", False):
        tax_amt, new_bal = apply_per_turn_tax(player, econ)
        player = dict(player)
        player["balance"] = new_bal
        econ = dict(econ)
        econ["treasury_balance"] = round(float(econ.get("treasury_balance", 0)) + tax_amt, 2)
        if settings.get("free_parking_pot_enabled", False):
            game_state["free_parking_pot"] = round(float(game_state.get("free_parking_pot", 0) or 0) + tax_amt, 2)
        game_state = _update_player_in_state(game_state, player)
        log_entry = {"event_type": "turn_tax", "description": f"{player['username']} paid per-turn tax of ${tax_amt:.2f}.", "player_id": player_id, "round": current_round, "turn": 0}
        game_state = _add_log_entry(game_state, log_entry, match_id, redis_client)
        game_state = record_tax_payment(game_state, player_id, "turn_tax", tax_amt)

    # Property tax every N rounds
    n = settings.get("property_tax_every_n_rounds", 5)
    if current_round > 0 and current_round % n == 0:
        player = next((p for p in game_state["players"] if p["id"] == player_id), player)
        player_props = get_player_properties(player_id, game_state)
        if player_props:
            tax_amt, new_bal = apply_property_tax(player, player_props, econ)
            player = dict(player)
            player["balance"] = new_bal
            econ = dict(econ)
            econ["treasury_balance"] = round(float(econ.get("treasury_balance", 0)) + tax_amt, 2)
            if settings.get("free_parking_pot_enabled", False):
                game_state["free_parking_pot"] = round(float(game_state.get("free_parking_pot", 0) or 0) + tax_amt, 2)
            game_state = _update_player_in_state(game_state, player)
            log_entry = {"event_type": "property_tax", "description": f"{player['username']} paid ${tax_amt:.2f} in property taxes.", "player_id": player_id, "round": current_round, "turn": 0}
            game_state = _add_log_entry(game_state, log_entry, match_id, redis_client)
            game_state = record_tax_payment(game_state, player_id, "property_tax", tax_amt)

    # 6. ECONOMIC_UPDATE
    all_players = game_state.get("players", [])
    econ = drift_economy(econ, all_players, current_round, settings, game_state)
    game_state = dict(game_state)
    game_state["econ"] = econ
    game_state = ensure_social_state(game_state)
    econ = game_state.get("econ", econ)
    redis_client.set(f"game:{match_id}:econ", json.dumps(econ))
    socketio_instance.emit("economy_update", {"match_id": match_id, "econ": econ}, room=str(match_id))
    socketio_instance.emit(
        "stability_update",
        {"match_id": match_id, "social": game_state.get("social", {})},
        room=str(match_id),
    )

    # 9. HYPER-INFLATION
    if settings.get("hyper_inflation_trigger", True):
        econ, updated_props = apply_hyper_inflation(econ, game_state.get("properties", []), current_round, settings)
        game_state = dict(game_state)
        game_state["econ"] = econ
        game_state["properties"] = updated_props
        game_state = ensure_social_state(game_state)
        if current_round >= settings.get("hyper_inflation_round", 50):
            socketio_instance.emit("hyper_inflation_alert", {"match_id": match_id, "round": current_round, "econ": econ}, room=str(match_id))

    # 11. CHECK_BANKRUPTCY (auto-rescue only; liquidation remains manual)
    game_state = check_bankruptcy(game_state, match_id, redis_client, socketio_instance, player_id=player_id)

    # 12. CHECK_WIN
    winner = check_win_condition(game_state, settings)
    if winner:
        game_state = dict(game_state)
        game_state["status"] = "completed"
        game_state["winner"] = winner
        socketio_instance.emit("game_over", {"match_id": match_id, "winner": winner}, room=str(match_id))

    # 13. TURN READY / END_TURN
    game_state.pop("pending_action", None)
    game_state.pop("pending_turn_context", None)

    resolved_player = next((p for p in game_state.get("players", []) if p["id"] == player_id), None)
    player_in_debt = (
        resolved_player is not None
        and (
            float(resolved_player.get("balance", 0) or 0) < 0
            or has_pending_player_debt(game_state, player_id)
        )
    )
    should_wait_for_end_turn = (
        game_state.get("status") != "completed"
        and not dice_result.get("is_doubles", False)
        and resolved_player is not None
        and not resolved_player.get("is_jailed", False)
        and (player_in_debt or resolved_player.get("is_connected", True))
    )

    if should_wait_for_end_turn:
        game_state["awaiting_end_turn_player_id"] = player_id
        persist_game_state(game_state, match_id, redis_client)
        broadcast_game_state_snapshot(socketio_instance, match_id, game_state)
        return game_state

    game_state.pop("awaiting_end_turn_player_id", None)
    game_state = end_turn(game_state, player_id, dice_result, match_id, redis_client, socketio_instance, settings, econ, current_round)

    persist_game_state(game_state, match_id, redis_client)
    broadcast_game_state_snapshot(socketio_instance, match_id, game_state)
    return game_state


def end_turn(
    game_state: dict,
    player_id: int,
    dice_result: dict,
    match_id: int,
    redis_client,
    socketio_instance,
    settings: dict,
    econ: dict,
    current_round: int,
) -> dict:
    """Advance turn/round counter, emit log_flush, handle end-of-round events."""
    game_state = dict(game_state)
    game_state = decrement_turn_deadlines(game_state, match_id, player_id=player_id)
    game_state.pop("awaiting_end_turn_player_id", None)
    game_state["dice_rolled_this_turn"] = False
    if game_state.get("status") == "completed":
        return game_state

    is_doubles = dice_result.get("is_doubles", False)
    is_jailed = next(
        (p.get("is_jailed", False) for p in game_state["players"] if p["id"] == player_id),
        False,
    )

    # Doubles: same player goes again (unless jailed)
    if is_doubles and not is_jailed:
        game_state["current_player_id"] = player_id
        redis_client.set(f"game:{match_id}:current_turn", str(player_id))
        next_player = next((p for p in game_state.get("players", []) if p["id"] == player_id), None)
        socketio_instance.emit(
            "turn_start",
            {
                "player_id": player_id,
                "player_name": next_player.get("username", "Player") if next_player else "Player",
                "round": game_state.get("current_round", current_round),
            },
            room=str(match_id),
        )
        return game_state

    # Advance to next player
    turn_order = game_state.get("turn_order", [])
    current_idx = game_state.get("current_turn_index", 0)
    active_player_ids = {p["id"] for p in game_state["players"] if not p.get("is_bankrupt", False)}

    # Find next non-bankrupt player
    next_idx = (current_idx + 1) % max(len(turn_order), 1)
    attempts = 0
    while turn_order and turn_order[next_idx] not in active_player_ids and attempts < len(turn_order):
        next_idx = (next_idx + 1) % len(turn_order)
        attempts += 1

    # Detect round completion (wrapped around)
    if next_idx <= current_idx and len(turn_order) > 1:
        current_round += 1
        game_state["current_round"] = current_round

        # Welfare at start of each round
        if settings.get("welfare_system_enabled", True):
            players = game_state.get("players", [])
            players, econ, welfare_distribution = pay_welfare(players, econ, settings)
            game_state["players"] = players
            game_state["econ"] = econ
            game_state = record_welfare_distribution(game_state, welfare_distribution)

            welfare_log_type = "welfare_paid" if welfare_distribution.get("successful") else "welfare_failed"
            if welfare_distribution.get("successful"):
                welfare_description = (
                    f"Welfare paid ${welfare_distribution.get('total_cost', 0):.2f} across "
                    f"{welfare_distribution.get('eligible_count', 0)} players."
                )
            else:
                welfare_description = welfare_distribution.get("reason") or "Welfare payment did not resolve."

            game_state = _add_log_entry(
                game_state,
                {
                    "event_type": welfare_log_type,
                    "description": welfare_description,
                    "round": current_round,
                    "turn": 0,
                },
                match_id,
                redis_client,
            )

        # Approval ratings
        players = update_approval_ratings(game_state.get("players", []), econ)
        game_state["players"] = players

        # 9. POLICY_APPLY at end of round
        if settings.get("lobbying_enabled", True) and settings.get("policy_voting_enabled", True):
            game_state, econ = resolve_lobbying(game_state, econ, settings, socketio_instance, match_id)
            game_state["econ"] = econ

        game_state = record_budget_history_snapshot(game_state, current_round)
        if settings.get("uprisings_enabled", True):
            game_state = resolve_end_of_round_social_state(
                game_state,
                socketio_instance=socketio_instance,
                match_id=match_id,
            )
            econ = game_state.get("econ", econ)
        else:
            game_state = ensure_social_state(game_state)

        game_state = decrement_round_deadlines(game_state, match_id)

        # Disconnect decay
        for i, p in enumerate(game_state.get("players", [])):
            if not p.get("is_connected", True) and not p.get("is_bankrupt", False):
                p = dict(p)
                p["influence_score"] = max(0.0, float(p.get("influence_score", 0)) - 2)
                game_state["players"][i] = p

    game_state["current_turn_index"] = next_idx
    next_player_id = turn_order[next_idx] if turn_order else player_id
    game_state["current_player_id"] = next_player_id
    redis_client.set(f"game:{match_id}:current_turn", str(next_player_id))

    next_player = next((p for p in game_state.get("players", []) if p["id"] == next_player_id), None)
    socketio_instance.emit(
        "turn_start",
        {
            "player_id": next_player_id,
            "player_name": next_player.get("username", "Player") if next_player else "Player",
            "round": game_state.get("current_round", current_round),
        },
        room=str(match_id),
    )

    # 10. LOG_FLUSH
    socketio_instance.emit("log_entry", {"match_id": match_id, "log": game_state.get("log_buffer", [])[-10:]}, room=str(match_id))

    return game_state


def _attempt_player_bailout(
    game_state: dict,
    player_id: int,
    match_id: int,
    redis_client,
    socketio_instance,
) -> tuple[dict, dict]:
    game_state = dict(game_state)
    player = next((entry for entry in game_state.get("players", []) if entry["id"] == player_id), None)
    if player is None or player.get("is_bankrupt", False):
        return game_state, {"bailed_out": False, "bankrupt": False}

    if float(player.get("balance", 0) or 0) >= 0 and not has_pending_player_debt(game_state, player_id):
        return game_state, {"bailed_out": False, "bankrupt": False}

    econ = dict(game_state.get("econ", {}))
    settings = game_state.get("settings", {})
    gov_type = econ.get("gov_type", settings.get("government_type", "liberal_democracy"))
    treasury_before = round_money(econ.get("treasury_balance", 0))
    balance_shortfall = round_money(max(0.0, -float(player.get("balance", 0) or 0)))
    bailout_amount = round_money(balance_shortfall + 200.0)
    bailout_enabled = bool(econ.get("bailout_enabled", False))

    if gov_type == "minarchism" or not bailout_enabled or bailout_amount <= 0 or treasury_before < bailout_amount:
        return game_state, {"bailed_out": False, "bankrupt": False}

    econ["treasury_balance"] = round_money(treasury_before - bailout_amount)
    game_state["econ"] = econ
    game_state, credit_result = credit_player_with_debt_settlement(game_state, player_id, bailout_amount)
    rescued_player = credit_result.get("player") or player

    game_state = log_and_broadcast(
        game_state,
        "welfare_paid",
        f"{rescued_player.get('username', 'Player')} was bailed out for ${bailout_amount:.2f} and kept in the game with ${rescued_player.get('balance', 0):.2f}.",
        match_id,
        redis_client,
        socketio_instance,
        player_id=player_id,
    )
    socketio_instance.emit(
        "player_bailed_out",
        {
            "player_id": player_id,
            "player_name": rescued_player.get("username", "Player"),
            "amount": bailout_amount,
            "debt_paid": credit_result.get("settled_amount", 0),
            "player_balance": rescued_player.get("balance", 0),
            "treasury_balance": econ.get("treasury_balance", 0),
            "match_id": match_id,
        },
        room=str(match_id),
    )
    return game_state, {"bailed_out": True, "bankrupt": False}


def check_bankruptcy(
    game_state: dict,
    match_id: int,
    redis_client,
    socketio_instance,
    player_id: int | None = None,
) -> dict:
    """Automatically rescue eligible in-debt players; manual liquidation remains explicit."""
    candidate_ids = [player_id] if player_id is not None else [
        player["id"]
        for player in game_state.get("players", [])
        if not player.get("is_bankrupt", False)
    ]

    next_state = dict(game_state)
    for candidate_id in candidate_ids:
        next_state, outcome = _attempt_player_bailout(
            next_state,
            candidate_id,
            match_id,
            redis_client,
            socketio_instance,
        )
        if outcome.get("bailed_out"):
            break

    return next_state


def handle_player_bankrupt(
    game_state: dict,
    player_id: int,
    creditor_id: int | None,
    match_id: int,
    socketio_instance,
    resolution: dict | None = None,
) -> dict:
    """
    Mark player as bankrupt.
    Transfer properties to creditor (or unown if tax-caused).
    Reset dev_level to 0 on transferred properties.
    """
    game_state = dict(game_state)
    updated_players = []
    bankrupt_player = None

    for p in game_state["players"]:
        p = dict(p)
        if p["id"] == player_id:
            p["is_bankrupt"] = True
            p["balance"] = 0.0
            bankrupt_player = p
        updated_players.append(p)
    game_state["players"] = updated_players
    game_state = clear_player_debts(game_state, player_id)
    game_state = expire_player_clauses(game_state, match_id, player_id=player_id)

    # Transfer properties
    updated_props = []
    for prop in game_state.get("properties", []):
        prop = dict(prop)
        if prop.get("owner_id") == player_id:
            prop["dev_level"] = 0
            prop["is_mortgaged"] = False
            if creditor_id is not None:
                prop["owner_id"] = creditor_id
                prop["current_value"] = float(prop.get("base_price", 0))
            else:
                prop["owner_id"] = None
        updated_props.append(prop)
    game_state["properties"] = updated_props

    socketio_instance.emit(
        "player_bankrupt",
        {
            "player_id": player_id,
            "player_name": bankrupt_player.get("username", "Player") if bankrupt_player else "Player",
            "creditor_id": creditor_id,
            "match_id": match_id,
            **(resolution or {}),
        },
        room=str(match_id),
    )
    return game_state


def declare_player_bankruptcy(
    game_state: dict,
    player_id: int,
    match_id: int,
    redis_client,
    socketio_instance,
) -> tuple[dict, dict]:
    game_state = dict(game_state)
    player = next((entry for entry in game_state.get("players", []) if entry["id"] == player_id), None)
    if player is None:
        return game_state, {"bailed_out": False, "bankrupt": False}

    game_state, bailout_outcome = _attempt_player_bailout(
        game_state,
        player_id,
        match_id,
        redis_client,
        socketio_instance,
    )
    if bailout_outcome.get("bailed_out"):
        return game_state, bailout_outcome

    econ = dict(game_state.get("econ", {}))
    settings = game_state.get("settings", {})
    gov_type = econ.get("gov_type", settings.get("government_type", "liberal_democracy"))
    treasury_before = round_money(econ.get("treasury_balance", 0))
    private_debt_total = get_total_pending_player_debt(game_state, player_id)

    resolution = {
        "government_type": gov_type,
        "resolution_type": "asset_liquidation" if gov_type == "minarchism" else "government_reimbursement",
        "treasury_before": treasury_before,
        "treasury_after": treasury_before,
        "debt_paid": 0.0,
        "debt_forgiven": 0.0,
        "liquidation_value": 0.0,
        "reimbursed_amount": 0.0,
    }

    if gov_type == "minarchism":
        liquidation_value = calculate_player_liquidation_value(game_state, player_id)
        game_state, settlement = settle_player_debts(game_state, player_id, liquidation_value)
        resolution["liquidation_value"] = liquidation_value
        resolution["debt_paid"] = settlement.get("settled_amount", 0)
        resolution["debt_forgiven"] = round_money(max(0.0, private_debt_total - resolution["debt_paid"]))
        log_message = (
            f"{player.get('username', 'Player')} declared bankruptcy under Minarchism. "
            f"Liquidation covered ${resolution['debt_paid']:.2f} of private debt."
        )
    else:
        reimbursement_amount = private_debt_total
        if reimbursement_amount > 0:
            econ["treasury_balance"] = round_money(treasury_before - reimbursement_amount)
            game_state["econ"] = econ
            game_state, settlement = settle_player_debts(game_state, player_id, reimbursement_amount)
            resolution["reimbursed_amount"] = settlement.get("settled_amount", 0)
            resolution["debt_paid"] = resolution["reimbursed_amount"]
        resolution["treasury_after"] = round_money(econ.get("treasury_balance", 0))
        log_message = (
            f"{player.get('username', 'Player')} declared bankruptcy. "
            f"The government covered ${resolution['reimbursed_amount']:.2f} in private debt."
        )

    resolution["treasury_after"] = round_money(game_state.get("econ", {}).get("treasury_balance", treasury_before))
    game_state = clear_player_debts(game_state, player_id)
    game_state = handle_player_bankrupt(game_state, player_id, None, match_id, socketio_instance, resolution)
    game_state = log_and_broadcast(
        game_state,
        "bankruptcy",
        log_message,
        match_id,
        redis_client,
        socketio_instance,
        player_id=player_id,
    )
    return game_state, {"bailed_out": False, "bankrupt": True}


def check_win_condition(game_state: dict, settings: dict) -> dict | None:
    """
    Returns winner dict if win condition is met, else None.
    Win: last non-bankrupt player (or last non-bankrupt team).
    """
    active_players = [p for p in game_state.get("players", []) if not p.get("is_bankrupt", False)]

    if len(active_players) == 1:
        return {"type": "player", "player": active_players[0]}
    if len(active_players) == 0:
        return {"type": "draw"}

    return None


# ---------------------------------------------------------------------------
# Public helpers used by routes
# ---------------------------------------------------------------------------

def log_and_broadcast(
    game_state: dict,
    event_type: str,
    description: str,
    match_id: int,
    redis_client,
    socketio_instance,
    player_id: int = None,
) -> dict:
    """
    Add a log entry to the game state, push to Redis buffer, persist to DB,
    and broadcast via Socket.IO.
    """
    from app import db
    from app.models.log import GameLog

    entry = {
        "event_type": event_type,
        "description": description,
        "player_id": player_id,
        "round": game_state.get("current_round", 0),
        "turn": game_state.get("current_turn_index", 0),
        "timestamp": datetime.utcnow().isoformat(),
    }

    game_state = _add_log_entry(game_state, entry, match_id, redis_client)

    # Persist to DB asynchronously (best-effort)
    try:
        log_record = GameLog(
            match_id=match_id,
            round=entry["round"],
            turn=entry["turn"],
            player_id=player_id,
            event_type=event_type,
            description=description,
        )
        db.session.add(log_record)
        db.session.commit()
    except Exception:
        pass

    socketio_instance.emit("log_entry", entry, room=str(match_id))
    return game_state


def process_turn(
    match_id: int,
    player_id: int,
    game_state: dict,
    redis_client,
    socketio_instance,
) -> dict:
    """
    Roll dice for the given player and execute a full turn.
    Convenience wrapper around run_turn that generates the dice roll internally.
    """
    from app.utils.dice import roll_dice

    _roll = roll_dice()
    d1, d2, is_doubles = _roll["die1"], _roll["die2"], _roll["is_doubles"]
    dice_result = {"die1": d1, "die2": d2, "total": d1 + d2, "is_doubles": is_doubles}

    return run_turn(match_id, player_id, dice_result, redis_client, socketio_instance)
