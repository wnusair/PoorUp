"""
In-game REST endpoints for PoorUp.
All game-state mutations emit Socket.IO events alongside the REST response.
"""
import json
from datetime import datetime
from flask import Blueprint, request, jsonify, session

from app import db, redis_client, socketio
from app.models.player import Match, MatchPlayer
from app.models.property import Property
from app.models.trade import Trade
from app.models.deal import Deal
from app.models.log import GameLog
from app.models.policy import (
    Policy,
    Lobbying as LobbyContribution,
    calculate_lobbying_success_chance,
    extract_lobbying_request_identifiers,
    resolve_lobbying_policy,
)
from app.utils.settings import normalize_government_type
from app.engine.game_loop import (
    process_turn,
    load_game_state,
    persist_game_state,
    broadcast_game_state_snapshot,
    handle_player_bankrupt,
    check_win_condition,
    log_and_broadcast,
    release_player_from_jail,
)
from app.engine.events import start_auction, resolve_auction
from app.engine.analytics import record_lobbying_contribution
from app.engine.bots import recover_bot_state_evaluation
from app.engine.economy import (
    calculate_development_cost,
    has_full_monopoly,
    get_player_properties,
    calculate_net_worth,
    property_is_fully_developed,
)
from app.engine.social import (
    property_private_actions_locked,
    submit_minarchist_emergency_reform,
    submit_negotiation_contribution,
)
from app.engine.deals import (
    accept_deal,
    attach_deals_snapshot,
    cancel_deal,
    create_deal,
    normalize_deal_request_payload,
    reject_deal,
    request_deal_termination,
    serialize_deal,
    spend_investment_escrow,
    terminate_deal,
)
from app.engine.trading import (
    apply_trade_acceptance,
    normalize_trade_request_payload,
    validate_trade_proposal,
)

game_bp = Blueprint("game", __name__)

# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------

def _require_active_player(match_id: int):
    """Return (user, match_player, match, error_tuple)."""
    user_id = session.get("user_id")
    if not user_id:
        return None, None, None, (jsonify({"error": "Not authenticated."}), 401)

    match = Match.query.get(match_id)
    if not match:
        return None, None, None, (jsonify({"error": "Match not found."}), 404)

    mp = MatchPlayer.query.filter_by(match_id=match_id, user_id=user_id).first()
    if not mp:
        return None, None, None, (jsonify({"error": "You are not in this match."}), 403)

    if mp.is_bankrupt:
        return None, None, None, (jsonify({"error": "You are bankrupt."}), 403)

    if match.status != "active":
        return None, None, None, (jsonify({"error": "Game is not active."}), 403)

    return user_id, mp, match, None


def _reject_locked_property_action(game_state: dict, property_id: int, message: str):
    if property_private_actions_locked(game_state, property_id):
        return jsonify({"error": message}), 409
    return None


# ---------------------------------------------------------------------------
# GET /api/game/<match_id>/state
# ---------------------------------------------------------------------------

@game_bp.route("/<int:match_id>/state", methods=["GET"])
def get_state(match_id):
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not authenticated."}), 401

    match = Match.query.get(match_id)
    if not match:
        return jsonify({"error": "Match not found."}), 404

    gs = load_game_state(match_id, redis_client)
    recover_bot_state_evaluation(match_id, gs, reason="state_fetch")
    return jsonify({"state": gs}), 200


# ---------------------------------------------------------------------------
# POST /api/game/<match_id>/roll
# ---------------------------------------------------------------------------

@game_bp.route("/<int:match_id>/roll", methods=["POST"])
def roll_dice(match_id):
    user_id, mp, match, err = _require_active_player(match_id)
    if err:
        return err

    gs = load_game_state(match_id, redis_client)

    # Only the active player may roll
    current_player_id = gs.get("current_player_id")
    if current_player_id != mp.id:
        return jsonify({"error": "It is not your turn."}), 403

    # Has the player already rolled this turn?
    if gs.get("dice_rolled_this_turn", False):
        return jsonify({"error": "You have already rolled this turn."}), 403

    # Delegate to full turn processor
    gs = process_turn(
        match_id=match_id,
        player_id=mp.id,
        game_state=gs,
        redis_client=redis_client,
        socketio_instance=socketio,
    )

    persist_game_state(gs, match_id, redis_client)
    return jsonify({"state": gs}), 200


# ---------------------------------------------------------------------------
# POST /api/game/<match_id>/buy
# ---------------------------------------------------------------------------

@game_bp.route("/<int:match_id>/buy", methods=["POST"])
def buy_property(match_id):
    user_id, mp, match, err = _require_active_player(match_id)
    if err:
        return err

    gs = load_game_state(match_id, redis_client)

    # Find the property at the player's current position
    player = next((p for p in gs["players"] if p["id"] == mp.id), None)
    if not player:
        return jsonify({"error": "Player not found in game state."}), 500

    position = player["current_position"]
    prop = next((p for p in gs["properties"] if p["board_position"] == position), None)
    if not prop:
        return jsonify({"error": "No property at your position."}), 400

    if prop.get("owner_id") is not None:
        return jsonify({"error": "Property is already owned."}), 400

    price = float(prop.get("current_value") or prop.get("base_price", 0))
    if float(player["balance"]) < price:
        return jsonify({"error": "Insufficient funds."}), 400

    # Update property owner in game state
    updated_props = []
    for p in gs["properties"]:
        p = dict(p)
        if p["board_position"] == position:
            p["owner_id"] = mp.id
        updated_props.append(p)

    # Deduct balance from player
    updated_players = []
    for p in gs["players"]:
        p = dict(p)
        if p["id"] == mp.id:
            p["balance"] = round(float(p["balance"]) - price, 2)
        updated_players.append(p)

    gs = dict(gs)
    gs["properties"] = updated_props
    gs["players"] = updated_players

    # Also persist to DB
    db_prop = Property.query.filter_by(match_id=match_id, board_position=position).first()
    if db_prop:
        db_prop.owner_id = mp.id
        mp.balance = float(mp.balance) - price
        db.session.commit()

    log_and_broadcast(
        gs, "property_purchased",
        f"{player.get('username', 'Player')} bought {prop['name']} for ${price:.2f}",
        match_id, redis_client, socketio, player_id=mp.id,
    )
    socketio.emit(
        "property_purchased",
        {"player_id": mp.id, "property_id": prop["id"], "amount": price, "position": position},
        room=str(match_id),
    )

    # Allow the pending action to clear
    gs["pending_action"] = None
    persist_game_state(gs, match_id, redis_client)
    return jsonify({"state": gs}), 200


# ---------------------------------------------------------------------------
# POST /api/game/<match_id>/decline
# ---------------------------------------------------------------------------

@game_bp.route("/<int:match_id>/decline", methods=["POST"])
def decline_property(match_id):
    user_id, mp, match, err = _require_active_player(match_id)
    if err:
        return err

    gs = load_game_state(match_id, redis_client)
    player = next((p for p in gs["players"] if p["id"] == mp.id), None)
    if not player:
        return jsonify({"error": "Player state not found."}), 500

    settings = gs.get("settings", {})
    position = player["current_position"]
    prop = next((p for p in gs["properties"] if p["board_position"] == position), None)

    if not prop:
        return jsonify({"error": "No property at your position."}), 400

    if settings.get("auction_enabled", True):
        start_auction(prop, gs, redis_client, socketio, match_id)

    gs["pending_action"] = None
    persist_game_state(gs, match_id, redis_client)
    return jsonify({"message": "Declined. Auction started." if settings.get("auction_enabled") else "Declined."}), 200


# ---------------------------------------------------------------------------
# POST /api/game/<match_id>/auction/close  (internal / admin — closed via timer)
# ---------------------------------------------------------------------------

@game_bp.route("/<int:match_id>/auction/close", methods=["POST"])
def close_auction(match_id):
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not authenticated."}), 401

    data = request.get_json(silent=True) or {}
    prop_id = data.get("property_id")
    if not prop_id:
        return jsonify({"error": "property_id required."}), 400

    gs = load_game_state(match_id, redis_client)
    econ = gs.get("econ", {})
    gs, econ, logs = resolve_auction(int(prop_id), gs, econ, redis_client, socketio, match_id)
    gs["econ"] = econ
    persist_game_state(gs, match_id, redis_client)
    return jsonify({"logs": logs}), 200


# ---------------------------------------------------------------------------
# POST /api/game/<match_id>/develop
# ---------------------------------------------------------------------------

@game_bp.route("/<int:match_id>/develop", methods=["POST"])
def develop_property(match_id):
    user_id, mp, match, err = _require_active_player(match_id)
    if err:
        return err

    data = request.get_json(silent=True) or {}
    prop_id = data.get("property_id")
    if not prop_id:
        return jsonify({"error": "property_id required."}), 400

    gs = load_game_state(match_id, redis_client)
    settings = gs.get("settings", {})
    econ = gs.get("econ", {})

    # Find prop in game state
    prop = next((p for p in gs["properties"] if p["id"] == int(prop_id)), None)
    if not prop:
        return jsonify({"error": "Property not found."}), 404

    if prop.get("owner_id") != mp.id:
        return jsonify({"error": "You do not own this property."}), 403

    locked_error = _reject_locked_property_action(gs, int(prop_id), "Unionized properties cannot be developed.")
    if locked_error:
        return locked_error

    if prop.get("is_mortgaged", False):
        return jsonify({"error": "Cannot develop a mortgaged property."}), 400

    if property_is_fully_developed(prop, gs, econ, settings):
        return jsonify({"error": "Property is fully developed."}), 400

    if not has_full_monopoly(prop, gs):
        return jsonify({"error": "You must own all properties in the group to develop."}), 400

    # Enforce even development rule
    group_color = prop.get("group_color")
    group_props = [p for p in gs["properties"] if p.get("group_color") == group_color and p.get("property_type") == "property"]
    target_level = prop["dev_level"] + 1
    for gp in group_props:
        if gp["id"] != prop["id"] and gp.get("dev_level", 0) < prop["dev_level"]:
            return jsonify({"error": "Development must be even across the group. Develop other properties first."}), 400

    player = next((p for p in gs["players"] if p["id"] == mp.id), None)
    cost = calculate_development_cost(prop.get("base_price"), target_level, gs, econ, settings)
    try:
        selected_clause_id = int(data.get("deal_clause_id", 0) or 0)
    except (TypeError, ValueError):
        selected_clause_id = 0
    use_deal_escrow = bool(data.get("use_deal_escrow", selected_clause_id > 0))

    escrow_result = None
    if use_deal_escrow:
        gs, escrow_result = spend_investment_escrow(
            gs,
            match_id,
            player_id=mp.id,
            property_id=int(prop_id),
            property_snapshot=prop,
            build_cost=cost,
            next_dev_level=target_level,
            econ=econ,
            selected_clause_id=selected_clause_id or None,
        )
        player = next((p for p in gs["players"] if p["id"] == mp.id), player)

    personal_cost = round(max(0.0, cost - float((escrow_result or {}).get("escrow_used", 0) or 0)), 2)
    if float(player["balance"]) < personal_cost:
        return jsonify({"error": "Insufficient funds to develop."}), 400

    # Update property
    updated_props = []
    for p in gs["properties"]:
        p = dict(p)
        if p["id"] == int(prop_id):
            p["dev_level"] = target_level
        updated_props.append(p)

    updated_players = []
    for p in gs["players"]:
        p = dict(p)
        if p["id"] == mp.id:
            p["balance"] = round(float(p["balance"]) - personal_cost, 2)
        updated_players.append(p)

    gs = dict(gs)
    gs["properties"] = updated_props
    gs["players"] = updated_players

    # Persist to DB
    db_prop = Property.query.get(int(prop_id))
    if db_prop:
        db_prop.dev_level = target_level
    final_player = next((p for p in gs["players"] if p["id"] == mp.id), player)
    mp.balance = float(final_player.get("balance", mp.balance))
    db.session.commit()

    log_and_broadcast(
        gs, "property_purchased",
        f"{player.get('username')} developed {prop['name']} to level {target_level} for ${personal_cost:.2f}{' plus deal escrow' if escrow_result else ''}",
        match_id, redis_client, socketio, player_id=mp.id,
    )
    if escrow_result:
        log_and_broadcast(
            gs,
            "deal_investment_spent",
            f"{player.get('username')} used ${escrow_result['escrow_used']:.2f} of deal escrow to develop {prop['name']}.",
            match_id,
            redis_client,
            socketio,
            player_id=mp.id,
        )
        socketio.emit(
            "deal_investment_spent",
            {
                "match_id": match_id,
                "property_id": int(prop_id),
                "property_name": prop["name"],
                **escrow_result,
            },
            room=str(match_id),
        )
    persist_game_state(gs, match_id, redis_client)
    return jsonify({"state": gs}), 200


# ---------------------------------------------------------------------------
# POST /api/game/<match_id>/mortgage
# ---------------------------------------------------------------------------

@game_bp.route("/<int:match_id>/mortgage", methods=["POST"])
def mortgage_property(match_id):
    user_id, mp, match, err = _require_active_player(match_id)
    if err:
        return err

    data = request.get_json(silent=True) or {}
    prop_id = data.get("property_id")
    if not prop_id:
        return jsonify({"error": "property_id required."}), 400

    gs = load_game_state(match_id, redis_client)
    settings = gs.get("settings", {})
    if not settings.get("mortgage_enabled", True):
        return jsonify({"error": "Mortgages are disabled in this game."}), 403

    prop = next((p for p in gs["properties"] if p["id"] == int(prop_id)), None)
    if not prop:
        return jsonify({"error": "Property not found."}), 404

    if prop.get("owner_id") != mp.id:
        return jsonify({"error": "You do not own this property."}), 403

    locked_error = _reject_locked_property_action(gs, int(prop_id), "Unionized properties cannot be mortgaged.")
    if locked_error:
        return locked_error

    if prop.get("is_mortgaged", False):
        return jsonify({"error": "Property is already mortgaged."}), 400

    if prop.get("dev_level", 0) > 0:
        return jsonify({"error": "Must remove all developments before mortgaging."}), 400

    mortgage_value = round(float(prop["base_price"]) * 0.5, 2)

    updated_props = []
    for p in gs["properties"]:
        p = dict(p)
        if p["id"] == int(prop_id):
            p["is_mortgaged"] = True
        updated_props.append(p)

    updated_players = []
    for p in gs["players"]:
        p = dict(p)
        if p["id"] == mp.id:
            p["balance"] = round(float(p["balance"]) + mortgage_value, 2)
        updated_players.append(p)

    gs = dict(gs)
    gs["properties"] = updated_props
    gs["players"] = updated_players

    db_prop = Property.query.get(int(prop_id))
    if db_prop:
        db_prop.is_mortgaged = True
    mp.balance = float(mp.balance) + mortgage_value
    db.session.commit()

    player = next((p for p in gs["players"] if p["id"] == mp.id), None)
    log_and_broadcast(
        gs, "mortgage",
        f"{player.get('username')} mortgaged {prop['name']} for ${mortgage_value:.2f}",
        match_id, redis_client, socketio, player_id=mp.id,
    )
    persist_game_state(gs, match_id, redis_client)
    return jsonify({"state": gs}), 200


# ---------------------------------------------------------------------------
# POST /api/game/<match_id>/unmortgage
# ---------------------------------------------------------------------------

@game_bp.route("/<int:match_id>/unmortgage", methods=["POST"])
def unmortgage_property(match_id):
    user_id, mp, match, err = _require_active_player(match_id)
    if err:
        return err

    data = request.get_json(silent=True) or {}
    prop_id = data.get("property_id")
    if not prop_id:
        return jsonify({"error": "property_id required."}), 400

    gs = load_game_state(match_id, redis_client)
    prop = next((p for p in gs["properties"] if p["id"] == int(prop_id)), None)
    if not prop:
        return jsonify({"error": "Property not found."}), 404

    if prop.get("owner_id") != mp.id:
        return jsonify({"error": "You do not own this property."}), 403

    locked_error = _reject_locked_property_action(gs, int(prop_id), "Unionized properties cannot be unmortgaged.")
    if locked_error:
        return locked_error

    if not prop.get("is_mortgaged", False):
        return jsonify({"error": "Property is not mortgaged."}), 400

    unmortgage_cost = round(float(prop["base_price"]) * 0.5 * 1.1, 2)
    player = next((p for p in gs["players"] if p["id"] == mp.id), None)

    if float(player["balance"]) < unmortgage_cost:
        return jsonify({"error": f"Insufficient funds. Need ${unmortgage_cost:.2f}."}), 400

    updated_props = []
    for p in gs["properties"]:
        p = dict(p)
        if p["id"] == int(prop_id):
            p["is_mortgaged"] = False
        updated_props.append(p)

    updated_players = []
    for p in gs["players"]:
        p = dict(p)
        if p["id"] == mp.id:
            p["balance"] = round(float(p["balance"]) - unmortgage_cost, 2)
        updated_players.append(p)

    gs = dict(gs)
    gs["properties"] = updated_props
    gs["players"] = updated_players

    db_prop = Property.query.get(int(prop_id))
    if db_prop:
        db_prop.is_mortgaged = False
    mp.balance = float(mp.balance) - unmortgage_cost
    db.session.commit()

    log_and_broadcast(
        gs, "unmortgage",
        f"{player.get('username')} unmortgaged {prop['name']} for ${unmortgage_cost:.2f}",
        match_id, redis_client, socketio, player_id=mp.id,
    )
    persist_game_state(gs, match_id, redis_client)
    return jsonify({"state": gs}), 200


# ---------------------------------------------------------------------------
# POST /api/game/<match_id>/trade  — propose a trade
# ---------------------------------------------------------------------------

@game_bp.route("/<int:match_id>/trade", methods=["POST"])
def propose_trade(match_id):
    user_id, mp, match, err = _require_active_player(match_id)
    if err:
        return err

    from app.engine.bots import has_active_auction
    if has_active_auction(match_id):
        return jsonify({"error": "Trading is unavailable while an auction is active."}), 409

    gs = load_game_state(match_id, redis_client)
    settings = gs.get("settings", {})
    if not settings.get("trading_enabled", True):
        return jsonify({"error": "Trading is disabled in this game."}), 403

    payload, error = normalize_trade_request_payload(match_id, mp.id, gs, request.get_json(silent=True) or {})
    if error:
        return jsonify({"error": error}), 400

    error = validate_trade_proposal(gs, mp.id, payload)
    if error:
        return jsonify({"error": error}), 400

    receiver_id = payload["receiver_id"]
    receiver = next((p for p in gs["players"] if p["id"] == receiver_id), None)
    player = next((p for p in gs["players"] if p["id"] == mp.id), None)

    trade = Trade(
        match_id=match_id,
        initiator_id=mp.id,
        receiver_id=receiver_id,
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

    trade_data = trade.to_dict()
    trade_data["initiator_username"] = player.get("username")
    trade_data["receiver_username"] = receiver.get("username")
    pledge_suffix = " including lobbying pledges" if payload["offered_lobby_pledges"] or payload["requested_lobby_pledges"] else ""
    deal_suffix = ""
    if payload["included_deal_drafts"]:
        count = len(payload["included_deal_drafts"])
        deal_suffix = f" and {count} attached deal draft{'s' if count != 1 else ''}"

    socketio.emit("trade_proposed", trade_data, room=str(match_id))
    log_and_broadcast(
        gs, "trade_proposed",
        f"{player.get('username')} proposed a trade to {receiver.get('username')}{pledge_suffix}{deal_suffix}",
        match_id, redis_client, socketio, player_id=mp.id,
    )
    from app.engine.bots import queue_bot_trade_responses
    queue_bot_trade_responses(match_id)
    return jsonify({"trade": trade.to_dict()}), 201


# ---------------------------------------------------------------------------
# PATCH /api/game/<match_id>/trade/<trade_id>  — accept / reject / counter
# ---------------------------------------------------------------------------

@game_bp.route("/<int:match_id>/trade/<int:trade_id>", methods=["PATCH"])
def respond_to_trade(match_id, trade_id):
    user_id, mp, match, err = _require_active_player(match_id)
    if err:
        return err

    from app.engine.bots import has_active_auction
    if has_active_auction(match_id):
        return jsonify({"error": "Trading is unavailable while an auction is active."}), 409

    data = request.get_json(silent=True) or {}
    action = data.get("action")  # 'accept' | 'reject' | 'counter'
    if action not in ("accept", "reject", "counter", "cancel"):
        return jsonify({"error": "action must be accept, reject, counter, or cancel."}), 400

    trade = Trade.query.get(trade_id)
    if not trade or trade.match_id != match_id:
        return jsonify({"error": "Trade not found."}), 404

    if trade.status != "pending":
        return jsonify({"error": "Trade is no longer pending."}), 400

    gs = load_game_state(match_id, redis_client)

    # Accept
    if action == "accept":
        if mp.id != trade.receiver_id:
            return jsonify({"error": "Only the receiver can accept."}), 403

        gs, pledge_results, created_deals, error = apply_trade_acceptance(gs, trade, match_id)
        if error:
            return jsonify({"error": error}), 400

        initiator = next((p for p in gs["players"] if p["id"] == trade.initiator_id), None)
        receiver = next((p for p in gs["players"] if p["id"] == trade.receiver_id), None)

        # DB updates
        mp_init = MatchPlayer.query.get(trade.initiator_id)
        mp_recv = MatchPlayer.query.get(trade.receiver_id)
        final_initiator = next((player for player in gs["players"] if player["id"] == trade.initiator_id), None)
        final_receiver = next((player for player in gs["players"] if player["id"] == trade.receiver_id), None)
        if mp_init and final_initiator:
            mp_init.balance = final_initiator.get("balance", mp_init.balance)
        if mp_recv and final_receiver:
            mp_recv.balance = final_receiver.get("balance", mp_recv.balance)

        for pid in (trade.offered_props or []):
            db_prop = Property.query.get(pid)
            if db_prop:
                db_prop.owner_id = trade.receiver_id
        for pid in (trade.requested_props or []):
            db_prop = Property.query.get(pid)
            if db_prop:
                db_prop.owner_id = trade.initiator_id

        trade.status = "accepted"
        trade.resolved_at = datetime.utcnow()
        db.session.commit()

        gs = attach_deals_snapshot(gs, match_id)

        activated_deals_suffix = ""
        if created_deals:
            count = len(created_deals)
            activated_deals_suffix = f" and activated {count} bundled deal{'s' if count != 1 else ''}"

        gs = log_and_broadcast(
            gs, "trade_completed",
            f"Trade accepted between {initiator.get('username')} and {receiver.get('username')}{activated_deals_suffix}",
            match_id, redis_client, socketio,
        )
        for payer_id, entries in ((trade.initiator_id, (pledge_results or {}).get("initiator", [])), (trade.receiver_id, (pledge_results or {}).get("receiver", []))):
            payer = next((player for player in gs.get("players", []) if player.get("id") == payer_id), None)
            for entry in entries:
                gs = log_and_broadcast(
                    gs,
                    "lobby_pending",
                    f"{payer.get('username', 'Player')} committed {entry['amount']:.2f} to '{entry['policy'].get('policy_name', 'Policy')}' as part of a trade.",
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
        persist_game_state(gs, match_id, redis_client)
        broadcast_game_state_snapshot(socketio, match_id, gs)
        return jsonify({"trade": trade.to_dict()}), 200

    elif action == "reject":
        if mp.id not in (trade.receiver_id, trade.initiator_id):
            return jsonify({"error": "Not involved in this trade."}), 403
        trade.status = "rejected"
        trade.resolved_at = datetime.utcnow()
        db.session.commit()

        log_and_broadcast(gs, "trade_rejected", "A trade was rejected.", match_id, redis_client, socketio)
        socketio.emit("trade_resolved", {"trade": trade.to_dict(), "accepted": False}, room=str(match_id))
        return jsonify({"trade": trade.to_dict()}), 200

    elif action == "cancel":
        if mp.id != trade.initiator_id:
            return jsonify({"error": "Only the initiator can cancel."}), 403
        trade.status = "cancelled"
        trade.resolved_at = datetime.utcnow()
        db.session.commit()
        socketio.emit("trade_resolved", {"trade": trade.to_dict(), "accepted": False}, room=str(match_id))
        return jsonify({"trade": trade.to_dict()}), 200

    elif action == "counter":
        if mp.id != trade.receiver_id:
            return jsonify({"error": "Only the receiver can counter."}), 403

        # Create reverse trade
        counter_data = data.get("counter", {})
        payload, error = normalize_trade_request_payload(match_id, mp.id, gs, counter_data)
        if error:
            return jsonify({"error": error}), 400

        error = validate_trade_proposal(gs, mp.id, payload)
        if error:
            return jsonify({"error": error}), 400

        trade.status = "countered"
        trade.resolved_at = datetime.utcnow()
        db.session.commit()

        new_trade = Trade(
            match_id=match_id,
            initiator_id=trade.receiver_id,
            receiver_id=trade.initiator_id,
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
        db.session.add(new_trade)
        db.session.commit()

        socketio.emit("trade_proposed", new_trade.to_dict(), room=str(match_id))
        return jsonify({"trade": new_trade.to_dict()}), 201


# ---------------------------------------------------------------------------
# POST /api/game/<match_id>/lobby — submit lobbying contribution
# ---------------------------------------------------------------------------

@game_bp.route("/<int:match_id>/lobby", methods=["POST"])
def submit_lobby(match_id):
    user_id, mp, match, err = _require_active_player(match_id)
    if err:
        return err

    gs = load_game_state(match_id, redis_client)
    settings = gs.get("settings", {})

    if not settings.get("lobbying_enabled", True):
        return jsonify({"error": "Lobbying is disabled."}), 403

    econ = gs.get("econ", {})
    gov_type = normalize_government_type(
        econ.get("gov_type") or econ.get("government_type") or settings.get("government_type", "liberal_democracy")
    )
    if gov_type == "minarchism":
        return jsonify({"error": "Lobbying is not available under Minarchism."}), 403

    data = request.get_json(silent=True) or {}
    requested_contributions = data.get("contributions")
    if not isinstance(requested_contributions, list):
        requested_contributions = [data]

    normalized_contributions = []
    grouped_contributions = {}
    for item in requested_contributions:
        if not isinstance(item, dict):
            continue

        request_identifiers = extract_lobbying_request_identifiers(item)

        raw_contribution = item.get("contribution", item.get("amount", 0))
        try:
            contribution = round(float(raw_contribution), 2)
        except (TypeError, ValueError):
            contribution = 0.0

        if contribution <= 0:
            continue

        policy, policy_error = resolve_lobbying_policy(
            match_id,
            government_type=gov_type,
            policy_id=request_identifiers["policy_id"],
            axis=request_identifiers["axis"],
            direction=request_identifiers["direction"],
            target=request_identifiers["target"],
            target_stat=request_identifiers["target_stat"],
        )
        if policy_error:
            return jsonify({"error": policy_error}), 400

        grouped = grouped_contributions.get(policy.id)
        if grouped is None:
            grouped = {
                "policy": policy,
                "contribution": 0.0,
                "axis": request_identifiers["axis"],
                "direction": request_identifiers["direction"],
            }
            grouped_contributions[policy.id] = grouped
        grouped["contribution"] = round(grouped["contribution"] + contribution, 2)
        grouped["axis"] = grouped.get("axis") or request_identifiers["axis"]
        grouped["direction"] = grouped.get("direction") or request_identifiers["direction"]

    normalized_contributions = list(grouped_contributions.values())
    if not normalized_contributions:
        return jsonify({"error": "A positive contribution is required."}), 400

    player = next((p for p in gs["players"] if p["id"] == mp.id), None)
    total_contribution = round(sum(item["contribution"] for item in normalized_contributions), 2)
    if float(player["balance"]) < total_contribution:
        return jsonify({"error": "Insufficient funds."}), 400

    updated_players = []
    updated_player = None
    for state_player in gs["players"]:
        state_player = dict(state_player)
        if state_player["id"] == mp.id:
            state_player["balance"] = round(float(state_player["balance"]) - total_contribution, 2)
            updated_player = state_player
        updated_players.append(state_player)

    gs = dict(gs)
    gs["players"] = updated_players

    response_contributions = []
    mp.balance = round(float(mp.balance) - total_contribution, 2)
    player_identity = updated_player or player

    for item in normalized_contributions:
        policy = item["policy"]
        contribution = item["contribution"]

        entry = LobbyContribution.query.filter_by(
            match_id=match_id,
            policy_id=policy.id,
            player_id=mp.id,
        ).first()
        if entry:
            entry.contribution = round(float(entry.contribution or 0) + contribution, 2)
        else:
            db.session.add(
                LobbyContribution(
                    match_id=match_id,
                    policy_id=policy.id,
                    player_id=mp.id,
                    contribution=contribution,
                )
            )

    db.session.commit()

    for item in normalized_contributions:
        policy = item["policy"]
        contribution = item["contribution"]
        policy_entries = LobbyContribution.query.filter_by(match_id=match_id, policy_id=policy.id).all()
        policy_pool_total = round(sum(float(pool_entry.contribution or 0) for pool_entry in policy_entries), 2)
        contributor_count = len({pool_entry.player_id for pool_entry in policy_entries})
        estimated_success_chance = calculate_lobbying_success_chance(
            target_stat=policy.target_stat,
            government_type=gov_type,
            total_contribution=policy_pool_total,
            contributor_count=contributor_count,
        )
        policy_data = policy.to_dict(government_type=gov_type)
        gs = record_lobbying_contribution(gs, player_identity, policy, contribution, policy_entries)
        gs = log_and_broadcast(
            gs,
            "lobby_pending",
            (
                f"{player.get('username')} committed ${contribution:.2f} to '{policy.policy_name}'. "
                f"Current pool: ${policy_pool_total:.2f}."
            ),
            match_id, redis_client, socketio, player_id=mp.id,
        )
        response_contributions.append({
            "axis": policy_data.get("axis") or item.get("axis"),
            "direction": policy_data.get("direction") or item.get("direction"),
            "contribution": contribution,
            "policy_pool_total": policy_pool_total,
            "estimated_success_chance": round(estimated_success_chance * 100, 1),
            "policy": policy_data,
        })

    persist_game_state(gs, match_id, redis_client)
    broadcast_game_state_snapshot(socketio, match_id, gs)

    first_result = response_contributions[0]

    return jsonify({
        "message": "Lobbying contribution submitted. Results resolve at the end of the round.",
        "total_contribution": total_contribution,
        "contribution": first_result["contribution"],
        "policy_pool_total": first_result["policy_pool_total"],
        "estimated_success_chance": first_result["estimated_success_chance"],
        "remaining_balance": updated_player.get("balance") if updated_player else None,
        "policy": first_result["policy"],
        "contributions": response_contributions,
    }), 201


# ---------------------------------------------------------------------------
# POST /api/game/<match_id>/negotiate — fund local concessions
# ---------------------------------------------------------------------------

@game_bp.route("/<int:match_id>/negotiate", methods=["POST"])
def submit_negotiation(match_id):
    user_id, mp, match, err = _require_active_player(match_id)
    if err:
        return err

    gs = load_game_state(match_id, redis_client)
    data = request.get_json(silent=True) or {}
    property_id = data.get("property_id")
    amount = data.get("contribution", data.get("amount", 0))

    try:
        property_id = int(property_id)
        amount = float(amount)
    except (TypeError, ValueError):
        return jsonify({"error": "A valid property_id and contribution are required."}), 400

    try:
        gs, result = submit_negotiation_contribution(
            gs,
            property_id=property_id,
            player_id=mp.id,
            amount=amount,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    persist_game_state(gs, match_id, redis_client)
    broadcast_game_state_snapshot(socketio, match_id, gs)
    socketio.emit(
        "negotiation_updated",
        {"match_id": match_id, **result, "social": gs.get("social", {})},
        room=str(match_id),
    )
    return jsonify({"state": gs, "result": result}), 201


# ---------------------------------------------------------------------------
# POST /api/game/<match_id>/emergency-reform — Minarchist emergency action
# ---------------------------------------------------------------------------

@game_bp.route("/<int:match_id>/emergency-reform", methods=["POST"])
def apply_emergency_reform(match_id):
    user_id, mp, match, err = _require_active_player(match_id)
    if err:
        return err

    gs = load_game_state(match_id, redis_client)
    data = request.get_json(silent=True) or {}
    reform_type = (data.get("reform_type") or "").strip()
    property_id = data.get("property_id")
    target_region = data.get("target_region")

    try:
        property_id = int(property_id) if property_id is not None else None
    except (TypeError, ValueError):
        property_id = None

    try:
        gs, effect = submit_minarchist_emergency_reform(
            gs,
            player_id=mp.id,
            reform_type=reform_type,
            property_id=property_id,
            target_region=target_region,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    persist_game_state(gs, match_id, redis_client)
    broadcast_game_state_snapshot(socketio, match_id, gs)
    socketio.emit(
        "emergency_reform_applied",
        {"match_id": match_id, "effect": effect, "social": gs.get("social", {})},
        room=str(match_id),
    )
    return jsonify({"state": gs, "effect": effect}), 201


# ---------------------------------------------------------------------------
# GET /api/game/<match_id>/deals
# ---------------------------------------------------------------------------

@game_bp.route("/<int:match_id>/deals", methods=["GET"])
def list_deals(match_id):
    user_id, mp, match, err = _require_active_player(match_id)
    if err:
        return err

    gs = load_game_state(match_id, redis_client)
    gs = attach_deals_snapshot(gs, match_id)
    return jsonify({"deals": gs.get("deals", [])}), 200


# ---------------------------------------------------------------------------
# POST /api/game/<match_id>/deals
# ---------------------------------------------------------------------------

@game_bp.route("/<int:match_id>/deals", methods=["POST"])
def propose_deal(match_id):
    user_id, mp, match, err = _require_active_player(match_id)
    if err:
        return err

    gs = load_game_state(match_id, redis_client)
    payload, error = normalize_deal_request_payload(match_id, mp.id, gs, request.get_json(silent=True) or {})
    if error:
        return jsonify({"error": error}), 400

    deal = create_deal(match_id, mp.id, payload)
    if deal is None:
        return jsonify({"error": "Failed to create the deal."}), 500

    gs = attach_deals_snapshot(gs, match_id)
    player_lookup = {player.get("id"): player for player in gs.get("players", [])}
    deal_payload = serialize_deal(deal, player_lookup)
    socketio.emit("deal_proposed", deal_payload, room=str(match_id))
    gs = log_and_broadcast(
        gs,
        "deal_proposed",
        f"{player_lookup.get(mp.id, {}).get('username', 'Player')} proposed a deal to {deal_payload.get('counterparty_name', 'another player')}",
        match_id,
        redis_client,
        socketio,
        player_id=mp.id,
    )
    persist_game_state(gs, match_id, redis_client)
    broadcast_game_state_snapshot(socketio, match_id, gs)
    return jsonify({"deal": deal_payload, "state": gs}), 201


# ---------------------------------------------------------------------------
# PATCH /api/game/<match_id>/deals/<deal_id>
# ---------------------------------------------------------------------------

@game_bp.route("/<int:match_id>/deals/<int:deal_id>", methods=["PATCH"])
def respond_to_deal(match_id, deal_id):
    user_id, mp, match, err = _require_active_player(match_id)
    if err:
        return err

    deal = Deal.query.get(deal_id)
    if not deal or deal.match_id != match_id:
        return jsonify({"error": "Deal not found."}), 404

    data = request.get_json(silent=True) or {}
    action = str(data.get("action") or "").strip().lower()
    if action not in {"accept", "reject", "cancel", "expire"}:
        return jsonify({"error": "action must be accept, reject, cancel, or expire."}), 400

    gs = load_game_state(match_id, redis_client)
    player_lookup = {player.get("id"): player for player in gs.get("players", [])}

    if action == "accept":
        if mp.id != deal.counterparty_id:
            return jsonify({"error": "Only the counterparty can accept."}), 403
        gs, error = accept_deal(deal, gs)
        if error:
            return jsonify({"error": error}), 400
        deal_payload = serialize_deal(deal, player_lookup)
        gs = log_and_broadcast(
            gs,
            "deal_accepted",
            f"Deal accepted between {deal_payload.get('proposer_name', 'Player')} and {deal_payload.get('counterparty_name', 'Player')}",
            match_id,
            redis_client,
            socketio,
            player_id=mp.id,
        )
        persist_game_state(gs, match_id, redis_client)
        socketio.emit("deal_accepted", deal_payload, room=str(match_id))
        broadcast_game_state_snapshot(socketio, match_id, gs)
        return jsonify({"deal": deal_payload, "state": gs}), 200

    if action == "reject":
        if mp.id not in {deal.proposer_id, deal.counterparty_id}:
            return jsonify({"error": "You are not involved in this deal."}), 403
        if not reject_deal(deal):
            return jsonify({"error": "Failed to reject the deal."}), 500
        gs = attach_deals_snapshot(gs, match_id)
        deal_payload = serialize_deal(deal, player_lookup)
        log_and_broadcast(
            gs,
            "deal_rejected",
            f"Deal rejected between {deal_payload.get('proposer_name', 'Player')} and {deal_payload.get('counterparty_name', 'Player')}",
            match_id,
            redis_client,
            socketio,
            player_id=mp.id,
        )
        socketio.emit("deal_rejected", deal_payload, room=str(match_id))
        return jsonify({"deal": deal_payload}), 200

    if action == "cancel":
        if deal.status == "proposed" and mp.id != deal.proposer_id:
            return jsonify({"error": "Only the proposer can cancel a pending deal."}), 403
        if deal.status == "accepted" and mp.id not in {deal.proposer_id, deal.counterparty_id}:
            return jsonify({"error": "Only deal participants can cancel an active deal."}), 403
        if deal.status == "accepted":
            gs, termination_status, error = request_deal_termination(deal, mp.id, gs)
            if error:
                return jsonify({"error": error}), 400
            player_lookup = {player.get("id"): player for player in gs.get("players", [])}
            deal_payload = serialize_deal(deal, player_lookup)
            if termination_status == "pending":
                return jsonify({
                    "deal": deal_payload,
                    "state": gs,
                    "termination_status": termination_status,
                    "message": "Termination is already awaiting the other party.",
                }), 200

            if termination_status == "requested":
                gs = log_and_broadcast(
                    gs,
                    "deal_termination_requested",
                    f"{player_lookup.get(mp.id, {}).get('username', 'Player')} requested to terminate the deal with {deal_payload.get('counterparty_name', 'Player') if mp.id == deal.proposer_id else deal_payload.get('proposer_name', 'Player')}",
                    match_id,
                    redis_client,
                    socketio,
                    player_id=mp.id,
                )
            else:
                gs = log_and_broadcast(
                    gs,
                    "deal_cancelled",
                    f"Deal cancelled by mutual agreement between {deal_payload.get('proposer_name', 'Player')} and {deal_payload.get('counterparty_name', 'Player')}",
                    match_id,
                    redis_client,
                    socketio,
                    player_id=mp.id,
                )
            persist_game_state(gs, match_id, redis_client)
            socketio.emit("deal_updated", deal_payload, room=str(match_id))
            broadcast_game_state_snapshot(socketio, match_id, gs)
            return jsonify({"deal": deal_payload, "state": gs, "termination_status": termination_status}), 200

        gs, _ = cancel_deal(deal, gs)
        player_lookup = {player.get("id"): player for player in gs.get("players", [])}
        deal_payload = serialize_deal(deal, player_lookup)
        gs = log_and_broadcast(
            gs,
            "deal_cancelled",
            f"Deal cancelled between {deal_payload.get('proposer_name', 'Player')} and {deal_payload.get('counterparty_name', 'Player')}",
            match_id,
            redis_client,
            socketio,
            player_id=mp.id,
        )
        persist_game_state(gs, match_id, redis_client)
        socketio.emit("deal_updated", deal_payload, room=str(match_id))
        broadcast_game_state_snapshot(socketio, match_id, gs)
        return jsonify({"deal": deal_payload, "state": gs}), 200

    if mp.id not in {deal.proposer_id, deal.counterparty_id}:
        return jsonify({"error": "Only deal participants can expire a deal."}), 403
    gs = terminate_deal(deal, gs, status="expired")
    deal_payload = serialize_deal(deal, player_lookup)
    gs = log_and_broadcast(
        gs,
        "deal_expired",
        f"Deal expired between {deal_payload.get('proposer_name', 'Player')} and {deal_payload.get('counterparty_name', 'Player')}",
        match_id,
        redis_client,
        socketio,
        player_id=mp.id,
    )
    persist_game_state(gs, match_id, redis_client)
    socketio.emit("deal_expired", deal_payload, room=str(match_id))
    broadcast_game_state_snapshot(socketio, match_id, gs)
    return jsonify({"deal": deal_payload, "state": gs}), 200


# ---------------------------------------------------------------------------
# POST /api/game/<match_id>/deals/<deal_id>/counter
# ---------------------------------------------------------------------------

@game_bp.route("/<int:match_id>/deals/<int:deal_id>/counter", methods=["POST"])
def counter_deal(match_id, deal_id):
    user_id, mp, match, err = _require_active_player(match_id)
    if err:
        return err

    original = Deal.query.get(deal_id)
    if not original or original.match_id != match_id:
        return jsonify({"error": "Deal not found."}), 404
    if original.status != "proposed":
        return jsonify({"error": "Only pending deals can be countered."}), 400
    if mp.id != original.counterparty_id:
        return jsonify({"error": "Only the counterparty can counter a deal."}), 403

    gs = load_game_state(match_id, redis_client)
    payload, error = normalize_deal_request_payload(match_id, mp.id, gs, request.get_json(silent=True) or {})
    if error:
        return jsonify({"error": error}), 400

    original.status = "countered"
    original.responded_at = datetime.utcnow()
    original.last_updated_at = datetime.utcnow()
    db.session.commit()

    new_deal = create_deal(match_id, mp.id, payload, counter_of_deal_id=deal_id)
    if new_deal is None:
        return jsonify({"error": "Failed to create the counteroffer."}), 500

    gs = attach_deals_snapshot(gs, match_id)
    player_lookup = {player.get("id"): player for player in gs.get("players", [])}
    original_payload = serialize_deal(original, player_lookup)
    new_payload = serialize_deal(new_deal, player_lookup)
    gs = log_and_broadcast(
        gs,
        "deal_countered",
        f"{player_lookup.get(mp.id, {}).get('username', 'Player')} countered a deal from {original_payload.get('proposer_name', 'Player')}",
        match_id,
        redis_client,
        socketio,
        player_id=mp.id,
    )
    persist_game_state(gs, match_id, redis_client)
    socketio.emit("deal_updated", original_payload, room=str(match_id))
    socketio.emit("deal_proposed", new_payload, room=str(match_id))
    broadcast_game_state_snapshot(socketio, match_id, gs)
    return jsonify({"deal": new_payload, "original": original_payload, "state": gs}), 201


# ---------------------------------------------------------------------------
# DELETE /api/game/<match_id>/deals/<deal_id>
# ---------------------------------------------------------------------------

@game_bp.route("/<int:match_id>/deals/<int:deal_id>", methods=["DELETE"])
def delete_deal(match_id, deal_id):
    user_id, mp, match, err = _require_active_player(match_id)
    if err:
        return err

    deal = Deal.query.get(deal_id)
    if not deal or deal.match_id != match_id:
        return jsonify({"error": "Deal not found."}), 404

    gs = load_game_state(match_id, redis_client)
    if deal.status == "proposed":
        if mp.id != deal.proposer_id:
            return jsonify({"error": "Only the proposer can cancel a pending deal."}), 403
        gs, _ = cancel_deal(deal, gs)
        player_lookup = {player.get("id"): player for player in gs.get("players", [])}
        deal_payload = serialize_deal(deal, player_lookup)
        gs = log_and_broadcast(
            gs,
            "deal_cancelled",
            f"Deal cancelled between {deal_payload.get('proposer_name', 'Player')} and {deal_payload.get('counterparty_name', 'Player')}",
            match_id,
            redis_client,
            socketio,
            player_id=mp.id,
        )
        persist_game_state(gs, match_id, redis_client)
        socketio.emit("deal_updated", deal_payload, room=str(match_id))
        broadcast_game_state_snapshot(socketio, match_id, gs)
        return jsonify({"deal": deal_payload, "state": gs, "termination_status": "cancelled"}), 200

    if deal.status != "accepted":
        return jsonify({"error": "Only pending or accepted deals can be deleted."}), 400
    if mp.id not in {deal.proposer_id, deal.counterparty_id}:
        return jsonify({"error": "Only deal participants can cancel an active deal."}), 403

    gs, termination_status, error = request_deal_termination(deal, mp.id, gs)
    if error:
        return jsonify({"error": error}), 400
    player_lookup = {player.get("id"): player for player in gs.get("players", [])}
    deal_payload = serialize_deal(deal, player_lookup)
    if termination_status == "pending":
        return jsonify({
            "deal": deal_payload,
            "state": gs,
            "termination_status": termination_status,
            "message": "Termination is already awaiting the other party.",
        }), 200

    if termination_status == "requested":
        gs = log_and_broadcast(
            gs,
            "deal_termination_requested",
            f"{player_lookup.get(mp.id, {}).get('username', 'Player')} requested to terminate the deal with {deal_payload.get('counterparty_name', 'Player') if mp.id == deal.proposer_id else deal_payload.get('proposer_name', 'Player')}",
            match_id,
            redis_client,
            socketio,
            player_id=mp.id,
        )
    else:
        gs = log_and_broadcast(
            gs,
            "deal_cancelled",
            f"Deal cancelled by mutual agreement between {deal_payload.get('proposer_name', 'Player')} and {deal_payload.get('counterparty_name', 'Player')}",
            match_id,
            redis_client,
            socketio,
            player_id=mp.id,
        )
    persist_game_state(gs, match_id, redis_client)
    socketio.emit("deal_updated", deal_payload, room=str(match_id))
    broadcast_game_state_snapshot(socketio, match_id, gs)
    return jsonify({"deal": deal_payload, "state": gs, "termination_status": termination_status}), 200


# ---------------------------------------------------------------------------
# POST /api/game/<match_id>/team/create
# ---------------------------------------------------------------------------

@game_bp.route("/<int:match_id>/team/create", methods=["POST"])
def create_team(match_id):
    return jsonify({
        "error": "The team system has been replaced by Deals. Use /api/game/<match_id>/deals instead.",
    }), 410


# ---------------------------------------------------------------------------
# POST /api/game/<match_id>/team/invite
# ---------------------------------------------------------------------------

@game_bp.route("/<int:match_id>/team/invite", methods=["POST"])
def invite_to_team(match_id):
    return jsonify({
        "error": "The team system has been replaced by Deals. Submit a deal proposal instead.",
    }), 410


# ---------------------------------------------------------------------------
# PATCH /api/game/<match_id>/team/respond
# ---------------------------------------------------------------------------

@game_bp.route("/<int:match_id>/team/respond", methods=["PATCH"])
def respond_team_invite(match_id):
    return jsonify({
        "error": "The team system has been replaced by Deals. Respond through the deals endpoints instead.",
    }), 410


# ---------------------------------------------------------------------------
# DELETE /api/game/<match_id>/team
# ---------------------------------------------------------------------------

@game_bp.route("/<int:match_id>/team", methods=["DELETE"])
def dissolve_team(match_id):
    return jsonify({
        "error": "The team system has been replaced by Deals. Cancel or expire the relevant deals instead.",
    }), 410


# ---------------------------------------------------------------------------
# GET /api/game/<match_id>/log
# ---------------------------------------------------------------------------

@game_bp.route("/<int:match_id>/log", methods=["GET"])
def get_log(match_id):
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not authenticated."}), 401

    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 50))
    offset = (page - 1) * per_page

    entries = (
        GameLog.query
        .filter_by(match_id=match_id)
        .order_by(GameLog.timestamp.asc())
        .offset(offset)
        .limit(per_page)
        .all()
    )
    total = GameLog.query.filter_by(match_id=match_id).count()

    return jsonify({
        "log": [e.to_dict() for e in entries],
        "page": page,
        "per_page": per_page,
        "total": total,
    }), 200


# ---------------------------------------------------------------------------
# POST /api/game/<match_id>/jail/pay
# ---------------------------------------------------------------------------

@game_bp.route("/<int:match_id>/jail/pay", methods=["POST"])
def pay_jail_bail(match_id):
    user_id, mp, match, err = _require_active_player(match_id)
    if err:
        return err

    gs = load_game_state(match_id, redis_client)
    settings = gs.get("settings", {})
    if not settings.get("jail_enabled", True):
        return jsonify({"error": "Jail is disabled."}), 403

    player = next((p for p in gs["players"] if p["id"] == mp.id), None)
    if not player or not player.get("is_jailed", False):
        return jsonify({"error": "You are not in jail."}), 400

    bail = 50.0  # standard bail amount
    if float(player["balance"]) < bail:
        return jsonify({"error": f"Insufficient funds. Bail is ${bail:.2f}."}), 400

    gs, released_player = release_player_from_jail(gs, mp.id, bail_amount=bail)
    mp.balance = float(mp.balance) - bail
    mp.is_jailed = False
    mp.jail_turns_remaining = 0
    db.session.commit()

    log_and_broadcast(
        gs, "jail_released",
        f"{player.get('username')} paid ${bail:.2f} bail and may roll immediately.",
        match_id, redis_client, socketio, player_id=mp.id,
    )
    persist_game_state(gs, match_id, redis_client)
    return jsonify({"state": gs, "player": released_player}), 200


# ---------------------------------------------------------------------------
# POST /api/game/<match_id>/jail/card
# ---------------------------------------------------------------------------

@game_bp.route("/<int:match_id>/jail/card", methods=["POST"])
def use_jail_card(match_id):
    user_id, mp, match, err = _require_active_player(match_id)
    if err:
        return err

    gs = load_game_state(match_id, redis_client)
    player = next((p for p in gs["players"] if p["id"] == mp.id), None)

    if not player or not player.get("is_jailed", False):
        return jsonify({"error": "You are not in jail."}), 400

    if not player.get("has_jail_card", False):
        return jsonify({"error": "You do not have a Get Out of Jail Free card."}), 400

    gs, released_player = release_player_from_jail(gs, mp.id, consume_card=True)

    mp.is_jailed = False
    mp.jail_turns_remaining = 0
    mp.has_jail_card = False
    db.session.commit()

    log_and_broadcast(
        gs, "jail_released",
        f"{player.get('username')} used a Get Out of Jail Free card and may roll immediately.",
        match_id, redis_client, socketio, player_id=mp.id,
    )
    persist_game_state(gs, match_id, redis_client)
    return jsonify({"state": gs, "player": released_player}), 200
