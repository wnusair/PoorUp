"""
Socket.IO event handlers for PoorUp.
All game events are validated server-side before any state mutation.
"""
import json
from datetime import datetime
from flask import current_app, request, session
from flask_socketio import join_room, leave_room, emit

from app import socketio, redis_client, db
from app.models.player import Match, MatchPlayer
from app.engine.game_loop import (
    broadcast_game_state_snapshot,
    check_bankruptcy,
    declare_player_bankruptcy,
    end_turn,
    finalize_turn_resolution,
    load_game_state,
    persist_game_state,
    process_turn,
    log_and_broadcast,
    handle_player_bankrupt,
    check_win_condition,
)
from app.engine.events import reset_auction_timer, start_auction, resolve_auction
from app.engine.debt import (
    credit_player_with_debt_settlement,
    has_pending_player_debt,
    spend_player_balance,
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
    serialize_deal,
    spend_investment_escrow,
    terminate_deal,
)
from app.engine.trading import (
    apply_trade_acceptance,
    normalize_trade_request_payload,
    validate_trade_proposal,
)
from app.engine.economy import (
    calculate_development_cost,
    calculate_development_refund,
    property_is_fully_developed,
)
from app.utils.color_utils import PLAYER_COLOR_PALETTE, is_valid_color
from app.utils.settings import normalize_settings_payload
from app.engine.bots import has_active_auction, queue_bot_auction_reactions, queue_bot_state_evaluation, queue_bot_trade_responses


# ---------------------------------------------------------------------------
# Connection / Room management
# ---------------------------------------------------------------------------

@socketio.on("connect")
def handle_connect(auth=None):
    """Called when a client connects. We defer room-joining to explicit events."""
    user_id = session.get("user_id")
    if not user_id:
        # Allow connection but they won't be in any room until they join
        pass


@socketio.on("disconnect")
def handle_disconnect():
    """Handle player disconnect. Mark them as disconnected in game state."""
    user_id = session.get("user_id")
    if not user_id:
        return

    # Find which active match this player is in
    mp = MatchPlayer.query.filter_by(user_id=user_id, is_bankrupt=False).join(
        Match, Match.id == MatchPlayer.match_id
    ).filter(Match.status == "active").first()

    if not mp:
        return

    mp.is_connected = False
    db.session.commit()

    gs = load_game_state(mp.match_id, redis_client)
    if gs:
        # Mark in state
        updated_players = []
        for p in gs.get("players", []):
            p = dict(p)
            if p["id"] == mp.id:
                p["is_connected"] = False
            updated_players.append(p)
        gs = dict(gs)
        gs["players"] = updated_players

        # Record disconnect round for influence decay
        redis_client.set(
            f"player:{mp.id}:disconnected_at_round",
            str(gs.get("current_round", 0))
        )

        log_and_broadcast(
            gs, "move",
            f"{mp.user.username} disconnected.",
            mp.match_id, redis_client, socketio, player_id=mp.id,
        )
        persist_game_state(gs, mp.match_id, redis_client)

    socketio.emit(
        "player_disconnected",
        {"player_id": mp.id, "username": mp.user.username},
        room=str(mp.match_id),
    )

    # If it's this player's turn, schedule auto-resolve after 30 seconds
    if gs and gs.get("current_player_id") == mp.id:
        # Eventlet-based delayed auto-resolve
        import eventlet
        eventlet.spawn_after(
            30,
            _auto_resolve_turn,
            current_app._get_current_object(),
            mp.match_id,
            mp.id,
        )


def _auto_resolve_turn(app, match_id: int, player_id: int):
    """Auto-resolve a turn for a disconnected player after 30 seconds."""
    with app.app_context():
        gs = load_game_state(match_id, redis_client)
        if not gs:
            return

        # Only proceed if it's still this player's turn
        if gs.get("current_player_id") != player_id:
            return

        player = next((p for p in gs["players"] if p["id"] == player_id), None)
        if not player or player.get("is_connected", True):
            return

        # Execute turn with minimal actions
        try:
            gs = process_turn(
                match_id=match_id,
                player_id=player_id,
                game_state=gs,
                redis_client=redis_client,
                socketio_instance=socketio,
            )
            persist_game_state(gs, match_id, redis_client)
        except Exception as e:
            print(f"[AutoTurn] Error auto-resolving turn for player {player_id}: {e}")


def _resolve_property_reference(game_state: dict, data: dict):
    property_id = data.get("property_id")
    if property_id is not None:
        try:
            property_id = int(property_id)
        except (TypeError, ValueError):
            property_id = None
    if property_id is not None:
        return next((p for p in game_state.get("properties", []) if p.get("id") == property_id), None)

    position = data.get("position")
    if position is not None:
        try:
            position = int(position)
        except (TypeError, ValueError):
            position = None
    if position is not None:
        return next((p for p in game_state.get("properties", []) if p.get("board_position") == position), None)

    return None


def _require_current_turn(game_state: dict, player_id: int, message: str = "It is not your turn.") -> bool:
    if not game_state or game_state.get("current_player_id") != player_id:
        emit("error", {"message": message})
        return False
    return True


def _require_property_management_access(game_state: dict, prop: dict, action_message: str) -> bool:
    if property_private_actions_locked(game_state, prop.get("id")):
        emit("error", {"message": action_message})
        return False
    return True


# ---------------------------------------------------------------------------
# Lobby events
# ---------------------------------------------------------------------------

@socketio.on("join_room")
def handle_join_room(data):
    """Player joins a Socket.IO room (lobby or game)."""
    room_code = (data.get("room_code") or "").upper()
    match_id = data.get("match_id")

    if room_code:
        join_room(room_code)

    if match_id:
        join_room(str(match_id))

    user_id = session.get("user_id")
    if user_id:
        mp = MatchPlayer.query.filter_by(user_id=user_id).join(
            Match, Match.id == MatchPlayer.match_id
        ).filter(
            Match.room_code == room_code if room_code else Match.id == match_id
        ).first()

        if mp:
            mp.is_connected = True
            db.session.commit()

            # If reconnecting to active game, send full state
            match = Match.query.get(mp.match_id)
            if match and match.status == "active":
                gs = load_game_state(mp.match_id, redis_client)
                if gs:
                    emit("game_state_snapshot", {
                        "state": gs,
                        "your_player_id": mp.id,
                    })

                    # Update connection status in game state
                    updated_players = []
                    for p in gs.get("players", []):
                        p = dict(p)
                        if p["id"] == mp.id:
                            p["is_connected"] = True
                        updated_players.append(p)
                    gs = dict(gs)
                    gs["players"] = updated_players
                    persist_game_state(gs, mp.match_id, redis_client)
            elif match and match.status == "lobby":
                from app.routes.lobby import _lobby_state
                emit("lobby_update", _lobby_state(match))


@socketio.on("leave_room")
def handle_leave_room(data):
    room_code = (data.get("room_code") or "").upper()
    room = room_code or str(data.get("match_id", ""))
    if room:
        leave_room(room)


@socketio.on("select_color")
def handle_select_color(data):
    """Player selects a color in the lobby — enforced server-side."""
    user_id = session.get("user_id")
    if not user_id:
        return

    room_code = data.get("room_code", "")
    color_hex = data.get("color_hex", "")

    match = Match.query.filter_by(room_code=room_code.upper()).first()
    if not match or match.status != "lobby":
        return

    if not is_valid_color(color_hex, PLAYER_COLOR_PALETTE):
        emit("color_error", {"error": "Invalid color."})
        return

    # Check race condition — is color already taken?
    taken = [
        mp.color_hex
        for mp in MatchPlayer.query.filter_by(match_id=match.id).all()
        if mp.user_id != user_id
    ]
    if color_hex in taken:
        emit("color_taken", {"color_hex": color_hex, "taken": True})
        return

    mp = MatchPlayer.query.filter_by(match_id=match.id, user_id=user_id).first()
    if not mp:
        return

    mp.color_hex = color_hex
    db.session.commit()

    socketio.emit("color_taken", {"color_hex": color_hex, "player_id": mp.id}, room=room_code.upper())

    from app.routes.lobby import _lobby_state

    socketio.emit(
        "lobby_update",
        _lobby_state(match),
        room=room_code.upper(),
    )


@socketio.on("player_ready")
def handle_player_ready(data):
    """Player toggles ready state in lobby."""
    user_id = session.get("user_id")
    if not user_id:
        return

    room_code = data.get("room_code", "")
    ready = data.get("ready", True)

    match = Match.query.filter_by(room_code=room_code.upper()).first()
    if not match or match.status != "lobby":
        return

    mp = MatchPlayer.query.filter_by(match_id=match.id, user_id=user_id).first()
    if not mp:
        return

    mp.is_ready = ready
    db.session.commit()

    from app.routes.lobby import _lobby_state

    socketio.emit(
        "lobby_update",
        _lobby_state(match),
        room=room_code.upper(),
    )


@socketio.on("update_settings")
def handle_update_settings(data):
    """Host updates lobby settings."""
    user_id = session.get("user_id")
    if not user_id:
        return

    room_code = data.get("room_code", "")
    settings = data.get("settings", {})

    match = Match.query.filter_by(room_code=room_code.upper()).first()
    if not match or match.status != "lobby":
        return

    if match.host_user_id != user_id:
        return

    from app.engine.game_loop import DEFAULT_SETTINGS
    current = dict(match.settings_json or DEFAULT_SETTINGS)
    allowed = set(DEFAULT_SETTINGS.keys())
    normalized_settings = normalize_settings_payload(settings, allowed)
    for k, v in normalized_settings.items():
        if k in allowed:
            current[k] = v

    if "government_type" in normalized_settings:
        gov = normalized_settings["government_type"]
        match.government_type = gov
        current["government_type"] = gov

    match.settings_json = current
    db.session.commit()

    from app.routes.lobby import _lobby_state

    socketio.emit(
        "lobby_update",
        _lobby_state(match),
        room=room_code.upper(),
    )


@socketio.on("start_game")
def handle_start_game(data):
    """Host starts the game via Socket.IO (alternative to REST endpoint)."""
    user_id = session.get("user_id")
    if not user_id:
        return

    room_code = data.get("room_code", "")
    match = Match.query.filter_by(room_code=room_code.upper()).first()
    if not match or match.status != "lobby":
        return

    if match.host_user_id != user_id:
        return

    match_players = MatchPlayer.query.filter_by(match_id=match.id).all()
    if len(match_players) < 2:
        emit("error", {"message": "Need at least 2 players to start."})
        return

    if not all(player.is_ready for player in match_players):
        emit("error", {"message": "All players must be ready to start."})
        return

    from app.engine.game_loop import initialize_game_state
    gs = initialize_game_state(match, match_players, redis_client, socketio)

    socketio.emit(
        "game_start",
        {
            "match_id": match.id,
            "room_code": match.room_code,
            "state": gs,
            "turn_order": gs["turn_order"],
            "first_player_id": gs["current_player_id"],
        },
        room=room_code.upper(),
    )
    queue_bot_state_evaluation(match.id, gs, reason="game_start_socket")


# ---------------------------------------------------------------------------
# In-game action events
# ---------------------------------------------------------------------------

@socketio.on("roll_dice")
def handle_roll_dice(data):
    """Player emits roll_dice — validates turn, executes full turn."""
    user_id = session.get("user_id")
    if not user_id:
        return

    match_id = data.get("match_id")
    if not match_id:
        return

    match = Match.query.get(int(match_id))
    if not match or match.status != "active":
        return

    mp = MatchPlayer.query.filter_by(match_id=int(match_id), user_id=user_id).first()
    if not mp or mp.is_bankrupt:
        return

    gs = load_game_state(int(match_id), redis_client)
    if not gs:
        return

    if gs.get("current_player_id") != mp.id:
        emit("error", {"message": "Not your turn."})
        return

    if gs.get("awaiting_end_turn_player_id") == mp.id:
        emit("error", {"message": "End your turn before rolling again."})
        return

    if gs.get("dice_rolled_this_turn", False):
        emit("error", {"message": "Already rolled this turn."})
        return

    process_turn(
        match_id=int(match_id),
        player_id=mp.id,
        game_state=gs,
        redis_client=redis_client,
        socketio_instance=socketio,
    )


@socketio.on("end_turn")
def handle_end_turn(data):
    """Advance to the next player's turn after the active player confirms they are done."""
    user_id = session.get("user_id")
    if not user_id:
        return

    match_id = int(data.get("match_id", 0))
    gs = load_game_state(match_id, redis_client)
    if not gs:
        return

    mp = MatchPlayer.query.filter_by(match_id=match_id, user_id=user_id).first()
    if not mp or mp.is_bankrupt:
        return

    if not _require_current_turn(gs, mp.id, "Only the active player can end the turn."):
        return

    if gs.get("awaiting_end_turn_player_id") != mp.id:
        emit("error", {"message": "There is no turn ready to end yet."})
        return

    gs = check_bankruptcy(gs, match_id, redis_client, socketio, player_id=mp.id)
    active_player = next((player for player in gs.get("players", []) if player.get("id") == mp.id), None)
    if active_player and (
        float(active_player.get("balance", 0) or 0) < 0
        or has_pending_player_debt(gs, mp.id)
    ):
        emit("error", {"message": "You cannot end your turn while your balance is negative."})
        return

    gs = end_turn(
        gs,
        mp.id,
        {"is_doubles": False},
        match_id,
        redis_client,
        socketio,
        gs.get("settings", {}),
        gs.get("econ", {}),
        gs.get("current_round", 1),
    )
    persist_game_state(gs, match_id, redis_client)
    broadcast_game_state_snapshot(socketio, match_id, gs)


@socketio.on("buy_property")
def handle_buy_property(data):
    """Player buys the property they landed on."""
    user_id = session.get("user_id")
    if not user_id:
        return

    match_id = int(data.get("match_id", 0))
    gs = load_game_state(match_id, redis_client)
    if not gs:
        return

    mp = MatchPlayer.query.filter_by(match_id=match_id, user_id=user_id).first()
    if not mp or mp.is_bankrupt:
        return

    pending_action = gs.get("pending_action") or {}
    if pending_action.get("type") != "buy_property" or pending_action.get("player_id") != mp.id:
        emit("error", {"message": "There is no property awaiting your decision."})
        return

    pending_turn = gs.get("pending_turn_context") or {}
    dice_result = pending_turn.get("dice_result")
    if not dice_result:
        emit("error", {"message": "Turn context expired. Please refresh the game state."})
        return

    player = next((p for p in gs["players"] if p["id"] == mp.id), None)
    if not player:
        return

    prop = _resolve_property_reference(gs, pending_action)
    position = prop.get("board_position") if prop else player["current_position"]

    if not prop or prop.get("owner_id") is not None:
        emit("error", {"message": "Cannot buy this property."})
        return

    price = float(prop.get("current_value") or prop.get("base_price", 0))
    if float(player["balance"]) < price:
        emit("error", {"message": "Insufficient funds."})
        return

    # Update state
    updated_props = [
        {**p, "owner_id": mp.id} if p.get("board_position") == position else p
        for p in gs["properties"]
    ]
    updated_players = [
        {**p, "balance": round(float(p["balance"]) - price, 2)} if p["id"] == mp.id else p
        for p in gs["players"]
    ]

    gs = {**gs, "properties": updated_props, "players": updated_players}

    # DB persist
    from app.models.property import Property
    db_prop = Property.query.filter_by(match_id=match_id, board_position=position).first()
    if db_prop:
        db_prop.owner_id = mp.id
    mp.balance = float(mp.balance) - price
    db.session.commit()

    updated_player = next((p for p in updated_players if p["id"] == mp.id), player)

    gs = log_and_broadcast(
        gs, "property_purchased",
        f"{player.get('username')} bought {prop['name']} for ${price:.2f}",
        match_id, redis_client, socketio, player_id=mp.id,
    )
    socketio.emit(
        "property_purchased",
        {
            "player_id": mp.id,
            "player_name": player.get("username", "Player"),
            "player_balance": updated_player.get("balance"),
            "property_id": prop["id"],
            "position": position,
            "price": price,
            "property_name": prop["name"],
        },
        room=str(match_id),
    )
    finalize_turn_resolution(gs, mp.id, dice_result, match_id, redis_client, socketio)


@socketio.on("decline_property")
def handle_decline_property(data):
    """Player declines to buy — start auction if enabled."""
    user_id = session.get("user_id")
    if not user_id:
        return

    match_id = int(data.get("match_id", 0))
    gs = load_game_state(match_id, redis_client)
    if not gs:
        return

    settings = gs.get("settings", {})
    mp = MatchPlayer.query.filter_by(match_id=match_id, user_id=user_id).first()
    if not mp:
        return

    pending_action = gs.get("pending_action") or {}
    if pending_action.get("type") != "buy_property" or pending_action.get("player_id") != mp.id:
        emit("error", {"message": "There is no property awaiting your decision."})
        return

    pending_turn = gs.get("pending_turn_context") or {}
    dice_result = pending_turn.get("dice_result")
    if not dice_result:
        emit("error", {"message": "Turn context expired. Please refresh the game state."})
        return

    player = next((p for p in gs["players"] if p["id"] == mp.id), None)
    if not player:
        return

    prop = _resolve_property_reference(gs, pending_action)

    if not prop:
        return

    if settings.get("auction_enabled", True):
        start_auction(prop, gs, redis_client, socketio, match_id)

    gs = log_and_broadcast(
        gs,
        "move",
        f"{player.get('username')} declined {prop['name']}",
        match_id,
        redis_client,
        socketio,
        player_id=mp.id,
    )
    finalize_turn_resolution(gs, mp.id, dice_result, match_id, redis_client, socketio)


@socketio.on("auction_bid")
def handle_auction_bid(data):
    """Player places a bid in an active auction."""
    user_id = session.get("user_id")
    if not user_id:
        return

    match_id = int(data.get("match_id", 0))
    prop_id = int(data.get("property_id", 0))
    amount = float(data.get("amount", 0))

    if amount <= 0:
        return

    active_key = f"game:{match_id}:auction:{prop_id}:active"
    if not redis_client.get(active_key):
        emit("error", {"message": "Auction is not active."})
        return

    current_bid = float(redis_client.get(f"game:{match_id}:auction:{prop_id}:current_bid") or 0)
    if amount <= current_bid:
        emit("error", {"message": f"Bid must exceed current bid of ${current_bid:.2f}."})
        return

    gs = load_game_state(match_id, redis_client)
    if not gs:
        return

    mp = MatchPlayer.query.filter_by(match_id=match_id, user_id=user_id).first()
    if not mp or mp.is_bankrupt:
        return

    player = next((p for p in gs["players"] if p["id"] == mp.id), None)
    if float(player.get("balance", 0)) < amount:
        emit("error", {"message": "Insufficient funds for this bid."})
        return

    # Record bid
    redis_client.set(f"game:{match_id}:auction:{prop_id}:current_bid", str(amount))
    redis_client.set(f"game:{match_id}:auction:{prop_id}:current_bidder", str(mp.id))
    redis_client.rpush(
        f"game:{match_id}:auction:{prop_id}:bids",
        json.dumps({"player_id": mp.id, "amount": amount}),
    )

    prop = next((p for p in gs["properties"] if p["id"] == prop_id), None)
    socketio.emit(
        "auction_bid",
        {
            "player_id": mp.id,
            "player_name": player.get("username"),
            "amount": amount,
            "property_id": prop_id,
            "property_name": prop["name"] if prop else "",
            "countdown_seconds": 5,
        },
        room=str(match_id),
    )
    reset_auction_timer(match_id, prop_id, redis_client, socketio)
    queue_bot_auction_reactions(match_id, game_state=gs, reason="human_auction_bid")


@socketio.on("auction_close")
def handle_auction_close(data):
    match_id = int(data.get("match_id", 0))
    prop_id = int(data.get("property_id", 0))
    if not match_id or not prop_id:
        return

    active_key = f"game:{match_id}:auction:{prop_id}:active"
    if not redis_client.get(active_key):
        return

    gs = load_game_state(match_id, redis_client)
    if not gs:
        return

    econ = gs.get("econ", {})
    gs, econ, _ = resolve_auction(prop_id, gs, econ, redis_client, socketio, match_id)
    gs = dict(gs)
    gs["econ"] = econ
    persist_game_state(gs, match_id, redis_client)
    broadcast_game_state_snapshot(socketio, match_id, gs)


@socketio.on("submit_trade")
def handle_submit_trade(data):
    """Player submits a trade proposal (socket path — mirrors REST)."""
    user_id = session.get("user_id")
    if not user_id:
        return

    match_id = int(data.get("match_id", 0))
    gs = load_game_state(match_id, redis_client)
    if not gs:
        return

    settings = gs.get("settings", {})
    if not settings.get("trading_enabled", True):
        emit("error", {"message": "Trading is disabled."})
        return

    mp = MatchPlayer.query.filter_by(match_id=match_id, user_id=user_id).first()
    if not mp or mp.is_bankrupt:
        return

    if has_active_auction(match_id):
        emit("error", {"message": "Trading is unavailable while an auction is active."})
        return

    from app.models.trade import Trade
    from datetime import datetime

    payload, error = normalize_trade_request_payload(match_id, data)
    if error:
        emit("error", {"message": error})
        return

    error = validate_trade_proposal(gs, mp.id, payload)
    if error:
        emit("error", {"message": error})
        return

    trade = Trade(
        match_id=match_id,
        initiator_id=mp.id,
        receiver_id=payload["receiver_id"],
        offered_money=payload["offered_money"],
        requested_money=payload["requested_money"],
        offered_props=payload["offered_props"],
        requested_props=payload["requested_props"],
        offered_lobby_pledges=payload["offered_lobby_pledges"],
        requested_lobby_pledges=payload["requested_lobby_pledges"],
        status="pending",
        created_at=datetime.utcnow(),
    )
    db.session.add(trade)
    db.session.commit()

    player = next((p for p in gs["players"] if p["id"] == mp.id), None)
    receiver = next((p for p in gs["players"] if p["id"] == payload["receiver_id"]), None)
    trade_data = trade.to_dict()
    trade_data["initiator_username"] = player.get("username") if player else ""
    trade_data["receiver_username"] = receiver.get("username") if receiver else ""
    pledge_suffix = " including lobbying pledges" if payload["offered_lobby_pledges"] or payload["requested_lobby_pledges"] else ""

    socketio.emit("trade_proposed", trade_data, room=str(match_id))
    log_and_broadcast(
        gs, "trade_proposed",
        f"{player.get('username')} proposed a trade{pledge_suffix}.",
        match_id, redis_client, socketio, player_id=mp.id,
    )
    queue_bot_trade_responses(match_id)


@socketio.on("respond_trade")
def handle_respond_trade(data):
    """Accept or reject a trade."""
    user_id = session.get("user_id")
    if not user_id:
        return

    match_id = int(data.get("match_id", 0))
    trade_id = int(data.get("trade_id", 0))
    accept = data.get("accept", False)

    from app.models.trade import Trade
    from app.models.property import Property
    from datetime import datetime

    trade = Trade.query.get(trade_id)
    if not trade or trade.match_id != match_id or trade.status != "pending":
        return

    mp = MatchPlayer.query.filter_by(match_id=match_id, user_id=user_id).first()
    if not mp or mp.id != trade.receiver_id:
        return

    gs = load_game_state(match_id, redis_client)
    if not gs:
        return

    if has_active_auction(match_id):
        emit("error", {"message": "Trading is unavailable while an auction is active."})
        return

    if accept:
        gs, pledge_results, error = apply_trade_acceptance(gs, trade, match_id)
        if error:
            emit("error", {"message": error})
            return

        initiator = next((p for p in gs["players"] if p["id"] == trade.initiator_id), None)
        receiver = next((p for p in gs["players"] if p["id"] == trade.receiver_id), None)

        # DB
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

        gs = log_and_broadcast(
            gs, "trade_completed",
            "A trade was accepted.",
            match_id, redis_client, socketio,
        )
        for payer_id, entries in ((trade.initiator_id, (pledge_results or {}).get("initiator", [])), (trade.receiver_id, (pledge_results or {}).get("receiver", []))):
            payer = next((player for player in gs.get("players", []) if player.get("id") == payer_id), None)
            for entry in entries:
                gs = log_and_broadcast(
                    gs,
                    "lobby_pending",
                    f"{payer.get('username', 'Player')} committed ${entry['amount']:.2f} to '{entry['policy'].get('policy_name', 'Policy')}' as part of a trade.",
                    match_id,
                    redis_client,
                    socketio,
                    player_id=payer_id,
                )
        persist_game_state(gs, match_id, redis_client)
    else:
        trade.status = "rejected"
        trade.resolved_at = datetime.utcnow()
        db.session.commit()
        log_and_broadcast(gs, "trade_rejected", "A trade was rejected.", match_id, redis_client, socketio)

    socketio.emit("trade_resolved", {"trade": trade.to_dict(), "accepted": accept}, room=str(match_id))

    if accept:
        broadcast_game_state_snapshot(socketio, match_id, gs)


@socketio.on("submit_deal")
def handle_submit_deal(data):
    user_id = session.get("user_id")
    if not user_id:
        return {"ok": False, "error": "You must be signed in to submit a deal."}

    match_id = int(data.get("match_id", 0))
    gs = load_game_state(match_id, redis_client)
    if not gs:
        return {"ok": False, "error": "Game state not found."}

    mp = MatchPlayer.query.filter_by(match_id=match_id, user_id=user_id).first()
    if not mp or mp.is_bankrupt:
        return {"ok": False, "error": "You cannot submit a deal in this match."}

    payload, error = normalize_deal_request_payload(match_id, mp.id, gs, data)
    if error:
        emit("error", {"message": error})
        return {"ok": False, "error": error}

    deal = create_deal(match_id, mp.id, payload)
    if deal is None:
        emit("error", {"message": "Failed to create the deal."})
        return {"ok": False, "error": "Failed to create the deal."}

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
    return {"ok": True, "deal": deal_payload}


@socketio.on("respond_deal")
def handle_respond_deal(data):
    user_id = session.get("user_id")
    if not user_id:
        return

    match_id = int(data.get("match_id", 0))
    deal_id = int(data.get("deal_id", 0))
    action = str(data.get("action") or ("accept" if data.get("accept") else "reject")).strip().lower()

    from app.models.deal import Deal

    deal = Deal.query.get(deal_id)
    if not deal or deal.match_id != match_id:
        emit("error", {"message": "Deal not found."})
        return

    mp = MatchPlayer.query.filter_by(match_id=match_id, user_id=user_id).first()
    if not mp or mp.is_bankrupt:
        return

    gs = load_game_state(match_id, redis_client)
    if not gs:
        return
    player_lookup = {player.get("id"): player for player in gs.get("players", [])}

    if action == "accept":
        if mp.id != deal.counterparty_id:
            emit("error", {"message": "Only the counterparty can accept."})
            return
        gs, error = accept_deal(deal, gs)
        if error:
            emit("error", {"message": error})
            return
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
        return

    if action == "reject":
        if mp.id not in {deal.proposer_id, deal.counterparty_id}:
            emit("error", {"message": "You are not involved in this deal."})
            return
        if not reject_deal(deal):
            emit("error", {"message": "Failed to reject the deal."})
            return
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
        return

    if action == "cancel":
        if deal.status == "proposed" and mp.id != deal.proposer_id:
            emit("error", {"message": "Only the proposer can cancel a pending deal."})
            return
        gs, _ = cancel_deal(deal, gs)
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
        return

    if mp.id not in {deal.proposer_id, deal.counterparty_id}:
        emit("error", {"message": "Only deal participants can expire a deal."})
        return

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


@socketio.on("counter_deal")
def handle_counter_deal(data):
    user_id = session.get("user_id")
    if not user_id:
        return {"ok": False, "error": "You must be signed in to counter a deal."}

    match_id = int(data.get("match_id", 0))
    deal_id = int(data.get("deal_id", 0))

    from app.models.deal import Deal

    original = Deal.query.get(deal_id)
    if not original or original.match_id != match_id or original.status != "proposed":
        emit("error", {"message": "Only pending deals can be countered."})
        return {"ok": False, "error": "Only pending deals can be countered."}

    mp = MatchPlayer.query.filter_by(match_id=match_id, user_id=user_id).first()
    if not mp or mp.is_bankrupt or mp.id != original.counterparty_id:
        emit("error", {"message": "Only the counterparty can counter this deal."})
        return {"ok": False, "error": "Only the counterparty can counter this deal."}

    gs = load_game_state(match_id, redis_client)
    if not gs:
        return {"ok": False, "error": "Game state not found."}

    payload, error = normalize_deal_request_payload(match_id, mp.id, gs, data)
    if error:
        emit("error", {"message": error})
        return {"ok": False, "error": error}

    original.status = "countered"
    original.responded_at = datetime.utcnow()
    original.last_updated_at = datetime.utcnow()
    db.session.commit()

    new_deal = create_deal(match_id, mp.id, payload, counter_of_deal_id=deal_id)
    if new_deal is None:
        emit("error", {"message": "Failed to create the counteroffer."})
        return {"ok": False, "error": "Failed to create the counteroffer."}

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
    return {"ok": True, "deal": new_payload, "original": original_payload}


@socketio.on("cancel_deal")
def handle_cancel_deal(data):
    user_id = session.get("user_id")
    if not user_id:
        return

    match_id = int(data.get("match_id", 0))
    deal_id = int(data.get("deal_id", 0))

    from app.models.deal import Deal

    deal = Deal.query.get(deal_id)
    if not deal or deal.match_id != match_id:
        emit("error", {"message": "Deal not found."})
        return

    mp = MatchPlayer.query.filter_by(match_id=match_id, user_id=user_id).first()
    if not mp or mp.is_bankrupt:
        return

    gs = load_game_state(match_id, redis_client)
    if not gs:
        return

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


@socketio.on("submit_lobby")
def handle_submit_lobby(data):
    """Player submits a lobbying contribution via socket."""
    user_id = session.get("user_id")
    if not user_id:
        return

    match_id = int(data.get("match_id", 0))
    target = (data.get("target") or "").strip()

    policy_id = data.get("policy_id")
    try:
        policy_id = int(policy_id) if policy_id is not None else 0
    except (TypeError, ValueError):
        policy_id = 0

    raw_contribution = data.get("contribution", data.get("amount", 0))
    try:
        contribution = float(raw_contribution)
    except (TypeError, ValueError):
        contribution = 0.0

    if contribution <= 0:
        emit("error", {"message": "Contribution must be positive."})
        return

    gs = load_game_state(match_id, redis_client)
    if not gs:
        return

    econ = gs.get("econ", {})
    if econ.get("gov_type") == "minarchism":
        emit("error", {"message": "Lobbying unavailable under Minarchism."})
        return

    mp = MatchPlayer.query.filter_by(match_id=match_id, user_id=user_id).first()
    if not mp or mp.is_bankrupt:
        return

    if not _require_current_turn(gs, mp.id, "Lobbying is only available on your turn."):
        return

    from app.models.policy import Policy, Lobbying as LobbyContribution, ensure_match_lobbying_policy

    policy = None
    if policy_id:
        policy = Policy.query.filter_by(id=policy_id, match_id=match_id).first()
    elif target:
        policy = ensure_match_lobbying_policy(match_id, target)

    if not policy:
        emit("error", {"message": "Select a valid lobbying target."})
        return

    player = next((p for p in gs["players"] if p["id"] == mp.id), None)
    if float(player.get("balance", 0)) < contribution:
        emit("error", {"message": "Insufficient funds."})
        return

    entry = LobbyContribution(
        match_id=match_id,
        policy_id=policy.id,
        player_id=mp.id,
        contribution=contribution,
    )
    db.session.add(entry)
    db.session.commit()

    log_and_broadcast(
        gs, "lobby_success",
        f"{player.get('username')} contributed ${contribution:.2f} to '{policy.policy_name}'",
        match_id, redis_client, socketio, player_id=mp.id,
    )


@socketio.on("submit_negotiation")
def handle_submit_negotiation(data):
    user_id = session.get("user_id")
    if not user_id:
        return

    match_id = int(data.get("match_id", 0))
    property_id = data.get("property_id")
    amount = data.get("contribution", data.get("amount", 0))

    try:
        property_id = int(property_id)
        amount = float(amount)
    except (TypeError, ValueError):
        emit("error", {"message": "A valid property and contribution are required."})
        return

    gs = load_game_state(match_id, redis_client)
    if not gs:
        return

    mp = MatchPlayer.query.filter_by(match_id=match_id, user_id=user_id).first()
    if not mp or mp.is_bankrupt:
        return

    try:
        gs, result = submit_negotiation_contribution(
            gs,
            property_id=property_id,
            player_id=mp.id,
            amount=amount,
        )
    except ValueError as exc:
        emit("error", {"message": str(exc)})
        return

    persist_game_state(gs, match_id, redis_client)
    broadcast_game_state_snapshot(socketio, match_id, gs)
    socketio.emit(
        "negotiation_updated",
        {"match_id": match_id, **result, "social": gs.get("social", {})},
        room=str(match_id),
    )


@socketio.on("apply_emergency_reform")
def handle_apply_emergency_reform(data):
    user_id = session.get("user_id")
    if not user_id:
        return

    match_id = int(data.get("match_id", 0))
    gs = load_game_state(match_id, redis_client)
    if not gs:
        return

    mp = MatchPlayer.query.filter_by(match_id=match_id, user_id=user_id).first()
    if not mp or mp.is_bankrupt:
        return

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
        emit("error", {"message": str(exc)})
        return

    persist_game_state(gs, match_id, redis_client)
    broadcast_game_state_snapshot(socketio, match_id, gs)
    socketio.emit(
        "emergency_reform_applied",
        {"match_id": match_id, "effect": effect, "social": gs.get("social", {})},
        room=str(match_id),
    )


@socketio.on("develop_property")
def handle_develop_property(data):
    """Player develops a property via socket."""
    user_id = session.get("user_id")
    if not user_id:
        return

    match_id = int(data.get("match_id", 0))
    prop_id = int(data.get("property_id", 0))

    gs = load_game_state(match_id, redis_client)
    if not gs:
        return

    from app.engine.economy import has_full_monopoly
    from app.models.property import Property

    mp = MatchPlayer.query.filter_by(match_id=match_id, user_id=user_id).first()
    if not mp:
        return

    if not _require_current_turn(gs, mp.id, "Property management is only available on your turn."):
        return

    prop = _resolve_property_reference(gs, data)
    if not prop or prop.get("owner_id") != mp.id:
        emit("error", {"message": "Cannot develop this property."})
        return

    if not _require_property_management_access(gs, prop, "Unionized properties cannot be developed."):
        return

    prop_id = prop["id"]

    if not has_full_monopoly(prop, gs):
        emit("error", {"message": "Must own full group to develop."})
        return

    if property_is_fully_developed(prop, gs, gs.get("econ", {}), gs.get("settings", {})):
        emit("error", {"message": "This property is fully developed."})
        return

    # Check even development
    group_props = [
        p for p in gs["properties"]
        if p.get("group_color") == prop["group_color"] and p.get("property_type") == "property"
    ]
    for gp in group_props:
        if gp["id"] != prop["id"] and gp.get("dev_level", 0) < prop.get("dev_level", 0):
            emit("error", {"message": "Development must be even across the group."})
            return

    player = next((p for p in gs["players"] if p["id"] == mp.id), None)
    new_level = prop.get("dev_level", 0) + 1
    cost = calculate_development_cost(
        prop.get("base_price"),
        new_level,
        gs,
        gs.get("econ", {}),
        gs.get("settings", {}),
    )
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
            property_id=prop_id,
            property_snapshot=prop,
            build_cost=cost,
            next_dev_level=new_level,
            econ=gs.get("econ", {}),
            selected_clause_id=selected_clause_id or None,
        )
        player = next((p for p in gs["players"] if p["id"] == mp.id), player)

    personal_cost = round(max(0.0, cost - float((escrow_result or {}).get("escrow_used", 0) or 0)), 2)
    if float(player.get("balance", 0)) < personal_cost:
        emit("error", {"message": f"Need ${personal_cost:.2f} to develop."})
        return

    updated_props = [
        {**p, "dev_level": new_level} if p["id"] == prop_id else p
        for p in gs["properties"]
    ]
    updated_players = [
        {**p, "balance": round(float(p["balance"]) - personal_cost, 2)} if p["id"] == mp.id else p
        for p in gs["players"]
    ]
    gs = {**gs, "properties": updated_props, "players": updated_players}

    db_prop = Property.query.get(prop_id)
    if db_prop:
        db_prop.dev_level = new_level
    final_player = next((p for p in updated_players if p["id"] == mp.id), player)
    mp.balance = float(final_player.get("balance", mp.balance))
    db.session.commit()

    gs = log_and_broadcast(
        gs, "property_purchased",
        f"{player.get('username')} developed {prop['name']} to level {new_level} for ${personal_cost:.2f}{' plus deal escrow' if escrow_result else ''}",
        match_id, redis_client, socketio, player_id=mp.id,
    )
    if escrow_result:
        gs = log_and_broadcast(
            gs,
            "deal_investment_spent",
            f"{player.get('username')} used ${escrow_result['escrow_used']:.2f} of deal escrow to develop {prop['name']}",
            match_id,
            redis_client,
            socketio,
            player_id=mp.id,
        )
        socketio.emit(
            "deal_investment_spent",
            {
                "match_id": match_id,
                "property_id": prop_id,
                "property_name": prop["name"],
                **escrow_result,
            },
            room=str(match_id),
        )
    persist_game_state(gs, match_id, redis_client)
    broadcast_game_state_snapshot(socketio, match_id, gs)


@socketio.on("mortgage_property")
def handle_mortgage_property(data):
    """Player mortgages a property via socket."""
    user_id = session.get("user_id")
    if not user_id:
        return

    match_id = int(data.get("match_id", 0))
    prop_id = int(data.get("property_id", 0))

    gs = load_game_state(match_id, redis_client)
    if not gs:
        return

    mp = MatchPlayer.query.filter_by(match_id=match_id, user_id=user_id).first()
    if not mp:
        return

    if not _require_current_turn(gs, mp.id, "Property management is only available on your turn."):
        return

    prop = _resolve_property_reference(gs, data)
    if not prop or prop.get("owner_id") != mp.id:
        emit("error", {"message": "Cannot mortgage this property."})
        return

    if not _require_property_management_access(gs, prop, "Unionized properties cannot be mortgaged."):
        return

    prop_id = prop["id"]

    if prop.get("is_mortgaged"):
        emit("error", {"message": "Already mortgaged."})
        return

    if prop.get("dev_level", 0) > 0:
        emit("error", {"message": "Remove developments before mortgaging."})
        return

    mortgage_value = round(float(prop["base_price"]) * 0.5, 2)

    updated_props = [
        {**p, "is_mortgaged": True} if p["id"] == prop_id else p
        for p in gs["properties"]
    ]
    gs = {**gs, "properties": updated_props}
    gs, credit_result = credit_player_with_debt_settlement(gs, mp.id, mortgage_value)

    from app.models.property import Property
    db_prop = Property.query.get(prop_id)
    if db_prop:
        db_prop.is_mortgaged = True
    player = next((p for p in gs["players"] if p["id"] == mp.id), None)
    if player:
        mp.balance = player.get("balance", mp.balance)
    db.session.commit()

    debt_suffix = ""
    if credit_result.get("settled_amount", 0) > 0:
        debt_suffix = f" and paid down ${credit_result['settled_amount']:.2f} in outstanding debt"

    gs = log_and_broadcast(
        gs, "mortgage",
        f"{player.get('username')} mortgaged {prop['name']} for ${mortgage_value:.2f}{debt_suffix}",
        match_id, redis_client, socketio, player_id=mp.id,
    )
    persist_game_state(gs, match_id, redis_client)
    broadcast_game_state_snapshot(socketio, match_id, gs)


@socketio.on("sell_house")
def handle_sell_house(data):
    """Player sells one development level from a property via socket."""
    user_id = session.get("user_id")
    if not user_id:
        return

    match_id = int(data.get("match_id", 0))
    gs = load_game_state(match_id, redis_client)
    if not gs:
        return

    mp = MatchPlayer.query.filter_by(match_id=match_id, user_id=user_id).first()
    if not mp:
        return

    if not _require_current_turn(gs, mp.id, "Property management is only available on your turn."):
        return

    prop = _resolve_property_reference(gs, data)
    if not prop or prop.get("owner_id") != mp.id or prop.get("property_type") != "property":
        emit("error", {"message": "Cannot sell houses on this property."})
        return

    if not _require_property_management_access(gs, prop, "Unionized properties cannot sell houses."):
        return

    prop_id = prop["id"]
    current_level = int(prop.get("dev_level", 0) or 0)
    if current_level <= 0:
        emit("error", {"message": "There are no houses to sell here."})
        return

    group_props = [
        group_prop for group_prop in gs.get("properties", [])
        if group_prop.get("group_color") == prop.get("group_color") and group_prop.get("property_type") == "property"
    ]
    max_level = max((int(group_prop.get("dev_level", 0) or 0) for group_prop in group_props), default=0)
    if current_level < max_level:
        emit("error", {"message": "Sell evenly across the set before removing a house here."})
        return

    new_level = current_level - 1
    refund = calculate_development_refund(
        prop.get("base_price"),
        current_level,
        gs,
        gs.get("econ", {}),
        gs.get("settings", {}),
    )

    updated_props = [
        {**entry, "dev_level": new_level} if entry["id"] == prop_id else entry
        for entry in gs["properties"]
    ]
    gs = {**gs, "properties": updated_props}
    gs, credit_result = credit_player_with_debt_settlement(gs, mp.id, refund)

    from app.models.property import Property
    db_prop = Property.query.get(prop_id)
    if db_prop:
        db_prop.dev_level = new_level

    player = next((entry for entry in gs["players"] if entry["id"] == mp.id), None)
    if player:
        mp.balance = player.get("balance", mp.balance)
    db.session.commit()

    debt_suffix = ""
    if credit_result.get("settled_amount", 0) > 0:
        debt_suffix = f" and paid down ${credit_result['settled_amount']:.2f} in outstanding debt"

    gs = log_and_broadcast(
        gs,
        "property_purchased",
        f"{player.get('username')} sold one house on {prop['name']} for ${refund:.2f}{debt_suffix}",
        match_id,
        redis_client,
        socketio,
        player_id=mp.id,
    )
    persist_game_state(gs, match_id, redis_client)
    broadcast_game_state_snapshot(socketio, match_id, gs)


@socketio.on("unmortgage_property")
def handle_unmortgage_property(data):
    """Player unmortgages a property via socket."""
    user_id = session.get("user_id")
    if not user_id:
        return

    match_id = int(data.get("match_id", 0))
    prop_id = int(data.get("property_id", 0))

    gs = load_game_state(match_id, redis_client)
    if not gs:
        return

    mp = MatchPlayer.query.filter_by(match_id=match_id, user_id=user_id).first()
    if not mp:
        return

    if not _require_current_turn(gs, mp.id, "Property management is only available on your turn."):
        return

    prop = _resolve_property_reference(gs, data)
    if not prop or prop.get("owner_id") != mp.id or not prop.get("is_mortgaged"):
        emit("error", {"message": "Cannot unmortgage this property."})
        return

    if not _require_property_management_access(gs, prop, "Unionized properties cannot be unmortgaged."):
        return

    prop_id = prop["id"]

    unmortgage_cost = round(float(prop["base_price"]) * 0.55, 2)  # 0.5 * 1.1
    player = next((p for p in gs["players"] if p["id"] == mp.id), None)

    if float(player.get("balance", 0)) < unmortgage_cost:
        emit("error", {"message": f"Need ${unmortgage_cost:.2f} to unmortgage."})
        return

    updated_props = [
        {**p, "is_mortgaged": False} if p["id"] == prop_id else p
        for p in gs["properties"]
    ]
    updated_players = [
        {**p, "balance": round(float(p["balance"]) - unmortgage_cost, 2)} if p["id"] == mp.id else p
        for p in gs["players"]
    ]
    gs = {**gs, "properties": updated_props, "players": updated_players}

    from app.models.property import Property
    db_prop = Property.query.get(prop_id)
    if db_prop:
        db_prop.is_mortgaged = False
    mp.balance = float(mp.balance) - unmortgage_cost
    db.session.commit()

    gs = log_and_broadcast(
        gs, "unmortgage",
        f"{player.get('username')} unmortgaged {prop['name']} for ${unmortgage_cost:.2f}",
        match_id, redis_client, socketio, player_id=mp.id,
    )
    persist_game_state(gs, match_id, redis_client)
    broadcast_game_state_snapshot(socketio, match_id, gs)


@socketio.on("declare_bankruptcy")
def handle_declare_bankruptcy(data):
    """Player explicitly declares bankruptcy after failing to resolve a negative balance."""
    user_id = session.get("user_id")
    if not user_id:
        return

    match_id = int(data.get("match_id", 0))
    gs = load_game_state(match_id, redis_client)
    if not gs:
        return

    mp = MatchPlayer.query.filter_by(match_id=match_id, user_id=user_id).first()
    if not mp or mp.is_bankrupt:
        return

    if not _require_current_turn(gs, mp.id, "Only the active player can declare bankruptcy."):
        return

    player = next((entry for entry in gs.get("players", []) if entry.get("id") == mp.id), None)
    if not player or (float(player.get("balance", 0) or 0) >= 0 and not has_pending_player_debt(gs, mp.id)):
        emit("error", {"message": "You can only declare bankruptcy while you are in debt."})
        return

    gs, outcome = declare_player_bankruptcy(gs, mp.id, match_id, redis_client, socketio)

    if outcome.get("bankrupt"):
        settings = gs.get("settings", {})
        winner = check_win_condition(gs, settings)
        if winner:
            gs = dict(gs)
            gs["status"] = "completed"
            gs["winner"] = winner
            gs.pop("awaiting_end_turn_player_id", None)
            gs["dice_rolled_this_turn"] = False
            socketio.emit("game_over", {"match_id": match_id, "winner": winner}, room=str(match_id))
        elif gs.get("current_player_id") == mp.id:
            gs = end_turn(
                gs,
                mp.id,
                {"is_doubles": False},
                match_id,
                redis_client,
                socketio,
                settings,
                gs.get("econ", {}),
                gs.get("current_round", 1),
            )

    persist_game_state(gs, match_id, redis_client)
    broadcast_game_state_snapshot(socketio, match_id, gs)


@socketio.on("pay_jail_bail")
def handle_pay_jail_bail(data):
    """Player pays bail to leave jail."""
    user_id = session.get("user_id")
    if not user_id:
        return

    match_id = int(data.get("match_id", 0))
    gs = load_game_state(match_id, redis_client)
    if not gs:
        return

    mp = MatchPlayer.query.filter_by(match_id=match_id, user_id=user_id).first()
    if not mp:
        return

    if not _require_current_turn(gs, mp.id, "You can only leave jail on your turn."):
        return

    player = next((p for p in gs["players"] if p["id"] == mp.id), None)
    if not player or not player.get("is_jailed"):
        emit("error", {"message": "You are not in jail."})
        return

    bail = 50.0
    if float(player.get("balance", 0)) < bail:
        emit("error", {"message": f"Insufficient funds. Bail is ${bail:.2f}."})
        return

    updated_players = [
        {**p, "balance": round(float(p["balance"]) - bail, 2), "is_jailed": False, "jail_turns_remaining": 0}
        if p["id"] == mp.id else p
        for p in gs["players"]
    ]
    gs = {**gs, "players": updated_players}

    mp.balance = float(mp.balance) - bail
    mp.is_jailed = False
    mp.jail_turns_remaining = 0
    db.session.commit()

    gs = log_and_broadcast(
        gs, "jail_released",
        f"{player.get('username')} paid ${bail:.2f} bail.",
        match_id, redis_client, socketio, player_id=mp.id,
    )
    persist_game_state(gs, match_id, redis_client)
    broadcast_game_state_snapshot(socketio, match_id, gs)


@socketio.on("use_jail_card")
def handle_use_jail_card(data):
    """Player uses Get Out of Jail Free card."""
    user_id = session.get("user_id")
    if not user_id:
        return

    match_id = int(data.get("match_id", 0))
    gs = load_game_state(match_id, redis_client)
    if not gs:
        return

    mp = MatchPlayer.query.filter_by(match_id=match_id, user_id=user_id).first()
    if not mp:
        return

    if not _require_current_turn(gs, mp.id, "You can only leave jail on your turn."):
        return

    player = next((p for p in gs["players"] if p["id"] == mp.id), None)
    if not player or not player.get("is_jailed") or not player.get("has_jail_card"):
        emit("error", {"message": "Cannot use jail card."})
        return

    updated_players = [
        {**p, "is_jailed": False, "jail_turns_remaining": 0, "has_jail_card": False}
        if p["id"] == mp.id else p
        for p in gs["players"]
    ]
    gs = {**gs, "players": updated_players}

    mp.is_jailed = False
    mp.jail_turns_remaining = 0
    mp.has_jail_card = False
    db.session.commit()

    gs = log_and_broadcast(
        gs, "jail_released",
        f"{player.get('username')} used a Get Out of Jail Free card.",
        match_id, redis_client, socketio, player_id=mp.id,
    )
    persist_game_state(gs, match_id, redis_client)
    broadcast_game_state_snapshot(socketio, match_id, gs)


@socketio.on("create_team")
def handle_create_team(data):
    emit("error", {"message": "The team system has been replaced by Deals. Open the Deals Desk instead."})


@socketio.on("invite_team")
def handle_invite_team(data):
    emit("error", {"message": "The team system has been replaced by Deals. Send a deal proposal instead."})


@socketio.on("respond_team")
def handle_respond_team(data):
    emit("error", {"message": "The team system has been replaced by Deals. Respond through the deal actions instead."})
