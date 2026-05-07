"""
Lobby routes: create, join, view, update color/ready, update settings, start game.
"""
import json
from flask import Blueprint, request, jsonify, session

from app import db
from app.models.player import Match, MatchPlayer, User
from app.engine.bots import create_bot_for_lobby, remove_bot_from_lobby, update_bot_for_lobby
from app.engine.game_loop import (
    generate_room_code,
    initialize_game_state,
    DEFAULT_SETTINGS,
    BOARD,
)
from app.utils.color_utils import (
    PLAYER_COLOR_PALETTE,
    get_available_player_colors,
    is_valid_color,
)
from app.utils.bot_registry import get_public_bot_catalog
from app.utils.settings import normalize_government_type, normalize_settings_payload

lobby_bp = Blueprint("lobby", __name__)


def _require_auth():
    user_id = session.get("user_id")
    if not user_id:
        return None, jsonify({"error": "Authentication required."}), 401
    user = User.query.get(user_id)
    if not user:
        return None, jsonify({"error": "User not found."}), 404
    return user, None, None


def _all_players_ready(players) -> bool:
    return len(players) >= 2 and all(player.is_ready for player in players)


def _coerce_bool(value, default=True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


@lobby_bp.route("/create", methods=["POST"])
def create_lobby():
    user, err_resp, err_code = _require_auth()
    if err_resp:
        return err_resp, err_code

    data = request.get_json(silent=True) or {}
    provided_settings = normalize_settings_payload(
        data.get("settings", {}),
        set(DEFAULT_SETTINGS.keys()),
    )
    gov_type = normalize_government_type(
        data.get(
            "government_type",
            provided_settings.get("government_type", DEFAULT_SETTINGS["government_type"]),
        )
    )

    # Merge provided settings with defaults
    settings = {**DEFAULT_SETTINGS, **provided_settings, "government_type": gov_type}

    # Generate unique room code
    for _ in range(10):
        code = generate_room_code()
        if not Match.query.filter_by(room_code=code).first():
            break

    match = Match(
        room_code=code,
        host_user_id=user.id,
        government_type=gov_type,
        status="lobby",
        settings_json=settings,
        current_round=0,
    )
    db.session.add(match)
    db.session.flush()

    # Add host as first player with first available color
    color = PLAYER_COLOR_PALETTE[0]
    mp = MatchPlayer(
        match_id=match.id,
        user_id=user.id,
        color_hex=color,
        balance=0,
        is_ready=False,
    )
    db.session.add(mp)
    db.session.commit()

    return jsonify({
        "message": "Lobby created.",
        "match": match.to_dict(),
        "player": mp.to_dict(),
    }), 201


@lobby_bp.route("/join", methods=["POST"])
def join_lobby():
    user, err_resp, err_code = _require_auth()
    if err_resp:
        return err_resp, err_code

    data = request.get_json(silent=True) or {}
    room_code = (data.get("room_code") or "").strip().upper()

    if not room_code:
        return jsonify({"error": "Room code is required."}), 400

    match = Match.query.filter_by(room_code=room_code).first()
    if not match:
        return jsonify({"error": "Room not found."}), 404

    if match.status != "lobby":
        return jsonify({"error": "Game has already started or finished."}), 403

    settings = match.settings_json or DEFAULT_SETTINGS
    max_players = settings.get("max_players", 6)
    current_count = MatchPlayer.query.filter_by(match_id=match.id).count()

    if current_count >= max_players:
        return jsonify({"error": "Lobby is full."}), 403

    # Check not already in this match
    existing = MatchPlayer.query.filter_by(match_id=match.id, user_id=user.id).first()
    if existing:
        return jsonify({"message": "Already in lobby.", "player": existing.to_dict()}), 200

    # Assign available color
    taken_colors = [mp.color_hex for mp in MatchPlayer.query.filter_by(match_id=match.id).all()]
    available = get_available_player_colors(taken_colors)
    if not available:
        return jsonify({"error": "No colors available."}), 403

    color = available[0]
    mp = MatchPlayer(
        match_id=match.id,
        user_id=user.id,
        color_hex=color,
        balance=0,
        is_ready=False,
    )
    db.session.add(mp)
    db.session.commit()

    # Notify lobby via socket
    from app import socketio
    socketio.emit("lobby_update", _lobby_state(match), room=room_code)

    return jsonify({"message": "Joined lobby.", "player": mp.to_dict()}), 200


@lobby_bp.route("/<room_code>", methods=["GET"])
def get_lobby(room_code):
    user, err_resp, err_code = _require_auth()
    if err_resp:
        return err_resp, err_code

    match = Match.query.filter_by(room_code=room_code.upper()).first()
    if not match:
        return jsonify({"error": "Room not found."}), 404

    return jsonify(_lobby_state(match)), 200


@lobby_bp.route("/<room_code>/color", methods=["PATCH"])
def update_color(room_code):
    user, err_resp, err_code = _require_auth()
    if err_resp:
        return err_resp, err_code

    match = Match.query.filter_by(room_code=room_code.upper()).first()
    if not match:
        return jsonify({"error": "Room not found."}), 404

    if match.status != "lobby":
        return jsonify({"error": "Colors can only change before the game starts."}), 403

    data = request.get_json(silent=True) or {}
    color_hex = data.get("color_hex", "")
    if not is_valid_color(color_hex, PLAYER_COLOR_PALETTE):
        return jsonify({"error": "Invalid color."}), 400

    players = MatchPlayer.query.filter_by(match_id=match.id).all()
    taken_colors = [player.color_hex for player in players if player.user_id != user.id]
    if color_hex in taken_colors:
        return jsonify({"error": "That color is already taken."}), 409

    mp = next((player for player in players if player.user_id == user.id), None)
    if not mp:
        return jsonify({"error": "Player not found in lobby."}), 404

    mp.color_hex = color_hex
    db.session.commit()

    from app import socketio

    socketio.emit(
        "color_taken",
        {"color_hex": color_hex, "player_id": mp.id},
        room=room_code.upper(),
    )

    lobby_state = _lobby_state(match)
    socketio.emit("lobby_update", lobby_state, room=room_code.upper())

    return jsonify({
        "message": "Color updated.",
        "color_hex": color_hex,
        "lobby": lobby_state,
    }), 200


@lobby_bp.route("/<room_code>/ready", methods=["PATCH"])
def update_ready(room_code):
    user, err_resp, err_code = _require_auth()
    if err_resp:
        return err_resp, err_code

    match = Match.query.filter_by(room_code=room_code.upper()).first()
    if not match:
        return jsonify({"error": "Room not found."}), 404

    if match.status != "lobby":
        return jsonify({"error": "Ready state can only change before the game starts."}), 403

    data = request.get_json(silent=True) or {}
    ready = _coerce_bool(data.get("ready"), default=True)

    mp = MatchPlayer.query.filter_by(match_id=match.id, user_id=user.id).first()
    if not mp:
        return jsonify({"error": "Player not found in lobby."}), 404

    mp.is_ready = ready
    db.session.commit()

    from app import socketio

    lobby_state = _lobby_state(match)
    socketio.emit("lobby_update", lobby_state, room=room_code.upper())

    return jsonify({
        "message": "Ready state updated.",
        "ready": ready,
        "lobby": lobby_state,
    }), 200


@lobby_bp.route("/<room_code>/settings", methods=["PATCH"])
def update_settings(room_code):
    user, err_resp, err_code = _require_auth()
    if err_resp:
        return err_resp, err_code

    match = Match.query.filter_by(room_code=room_code.upper()).first()
    if not match:
        return jsonify({"error": "Room not found."}), 404

    if match.host_user_id != user.id:
        return jsonify({"error": "Only the host can change settings."}), 403

    if match.status != "lobby":
        return jsonify({"error": "Settings are immutable once the game is active."}), 403

    data = request.get_json(silent=True) or {}
    payload = data.get("settings", data)
    current_settings = dict(match.settings_json or DEFAULT_SETTINGS)

    # Whitelist allowed settings keys
    allowed_keys = set(DEFAULT_SETTINGS.keys())
    normalized_settings = normalize_settings_payload(payload, allowed_keys)
    for k, v in normalized_settings.items():
        if k in allowed_keys:
            current_settings[k] = v

    # Validate government_type if changed
    if "government_type" in normalized_settings:
        gov = normalized_settings["government_type"]
        match.government_type = gov
        current_settings["government_type"] = gov

    match.settings_json = current_settings
    db.session.commit()

    from app import socketio
    lobby_state = _lobby_state(match)
    socketio.emit("lobby_update", lobby_state, room=room_code.upper())

    return jsonify({"message": "Settings updated.", "settings": current_settings, "lobby": lobby_state}), 200


@lobby_bp.route("/<room_code>/start", methods=["POST"])
def start_game(room_code):
    user, err_resp, err_code = _require_auth()
    if err_resp:
        return err_resp, err_code

    match = Match.query.filter_by(room_code=room_code.upper()).first()
    if not match:
        return jsonify({"error": "Room not found."}), 404

    if match.host_user_id != user.id:
        return jsonify({"error": "Only the host can start the game."}), 403

    if match.status != "lobby":
        return jsonify({"error": "Game already started or completed."}), 403

    match_players = MatchPlayer.query.filter_by(match_id=match.id).all()
    if len(match_players) < 2:
        return jsonify({"error": "Need at least 2 players to start."}), 400

    if not _all_players_ready(match_players):
        return jsonify({"error": "All players must be ready to start."}), 400

    from app import redis_client, socketio
    from app.engine.bots import queue_bot_state_evaluation

    game_state = initialize_game_state(match, match_players, redis_client, socketio)

    socketio.emit("game_start", {
        "match_id": match.id,
        "room_code": match.room_code,
        "state": game_state,
        "turn_order": game_state["turn_order"],
        "first_player_id": game_state["current_player_id"],
    }, room=room_code.upper())

    socketio.emit(
        "game_state_snapshot",
        {"state": game_state},
        room=str(match.id),
    )
    queue_bot_state_evaluation(match.id, game_state, reason="game_start_rest")

    return jsonify({
        "message": "Game started.",
        "match_id": match.id,
        "state": game_state,
    }), 200


@lobby_bp.route("/<room_code>/bots", methods=["POST"])
def add_bot(room_code):
    user, err_resp, err_code = _require_auth()
    if err_resp:
        return err_resp, err_code

    match = Match.query.filter_by(room_code=room_code.upper()).first()
    if not match:
        return jsonify({"error": "Room not found."}), 404

    if match.host_user_id != user.id:
        return jsonify({"error": "Only the host can add bots."}), 403

    if match.status != "lobby":
        return jsonify({"error": "Bots can only be added before the game starts."}), 403

    data = request.get_json(silent=True) or {}
    try:
        count = max(1, int(data.get("count", 1) or 1))
    except (TypeError, ValueError):
        return jsonify({"error": "Count must be a positive integer."}), 400

    settings = {**DEFAULT_SETTINGS, **(match.settings_json or {})}
    max_players = int(settings.get("max_players", DEFAULT_SETTINGS["max_players"]))
    current_count = MatchPlayer.query.filter_by(match_id=match.id).count()
    if current_count + count > max_players:
        return jsonify({"error": "Not enough open seats for that many bots."}), 400

    created_players = []
    try:
        for _ in range(count):
            created_players.append(
                create_bot_for_lobby(
                    match,
                    difficulty=data.get("difficulty"),
                    persona=data.get("persona"),
                    archetype=data.get("archetype"),
                )
            )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    from app import socketio
    lobby_state = _lobby_state(match)
    socketio.emit("lobby_update", lobby_state, room=room_code.upper())

    return jsonify({
        "message": "Bot added." if count == 1 else f"{count} bots added.",
        "player": created_players[0].to_dict(),
        "players": [player.to_dict() for player in created_players],
        "lobby": lobby_state,
    }), 201


@lobby_bp.route("/<room_code>/bots/<int:player_id>", methods=["PATCH"])
def patch_bot(room_code, player_id):
    user, err_resp, err_code = _require_auth()
    if err_resp:
        return err_resp, err_code

    match = Match.query.filter_by(room_code=room_code.upper()).first()
    if not match:
        return jsonify({"error": "Room not found."}), 404

    if match.host_user_id != user.id:
        return jsonify({"error": "Only the host can edit bots."}), 403

    if match.status != "lobby":
        return jsonify({"error": "Bots can only be edited before the game starts."}), 403

    data = request.get_json(silent=True) or {}

    try:
        bot_player = update_bot_for_lobby(
            match,
            player_id,
            difficulty=data.get("difficulty"),
            persona=data.get("persona"),
            archetype=data.get("archetype"),
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    if bot_player is None:
        return jsonify({"error": "Bot not found."}), 404

    from app import socketio
    lobby_state = _lobby_state(match)
    socketio.emit("lobby_update", lobby_state, room=room_code.upper())

    return jsonify({"message": "Bot updated.", "player": bot_player.to_dict(), "lobby": lobby_state}), 200


@lobby_bp.route("/<room_code>/bots/<int:player_id>", methods=["DELETE"])
def delete_bot(room_code, player_id):
    user, err_resp, err_code = _require_auth()
    if err_resp:
        return err_resp, err_code

    match = Match.query.filter_by(room_code=room_code.upper()).first()
    if not match:
        return jsonify({"error": "Room not found."}), 404

    if match.host_user_id != user.id:
        return jsonify({"error": "Only the host can remove bots."}), 403

    if match.status != "lobby":
        return jsonify({"error": "Bots can only be removed before the game starts."}), 403

    removed = remove_bot_from_lobby(match, player_id)
    if removed is None:
        return jsonify({"error": "Bot not found."}), 404

    from app import socketio
    lobby_state = _lobby_state(match)
    socketio.emit("lobby_update", lobby_state, room=room_code.upper())

    return jsonify({"message": "Bot removed.", "lobby": lobby_state}), 200


def _lobby_state(match: Match) -> dict:
    players = MatchPlayer.query.filter_by(match_id=match.id).all()
    settings = {
        **DEFAULT_SETTINGS,
        **normalize_settings_payload(match.settings_json or {}, set(DEFAULT_SETTINGS.keys())),
    }
    settings["government_type"] = normalize_government_type(
        settings.get("government_type", match.government_type)
    )

    return {
        "match": match.to_dict(),
        "players": [p.to_dict() for p in players],
        "settings": settings,
        "taken_colors": [player.color_hex for player in players if player.color_hex],
        "bot_setup": get_public_bot_catalog(),
    }
