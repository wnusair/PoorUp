"""
Admin/host controls for PoorUp.
Host-only actions: kick player, force-end game, reset auction timer, seed debug states.
"""
from flask import Blueprint, current_app, request, jsonify, session

from app import db, redis_client, socketio
from app.models.player import Match, MatchPlayer
from app.engine.game_loop import broadcast_game_state_snapshot, load_game_state, persist_game_state, log_and_broadcast
from app.engine.plot import seed_debug_communist_plot_state

admin_bp = Blueprint("admin", __name__)


def _require_host(match_id: int):
    user_id = session.get("user_id")
    if not user_id:
        return None, None, (jsonify({"error": "Not authenticated."}), 401)
    match = Match.query.get(match_id)
    if not match:
        return None, None, (jsonify({"error": "Match not found."}), 404)
    if match.host_user_id != user_id:
        return None, None, (jsonify({"error": "Host only."}), 403)
    return user_id, match, None


# ---------------------------------------------------------------------------
# POST /api/admin/<match_id>/kick
# ---------------------------------------------------------------------------

@admin_bp.route("/<int:match_id>/kick", methods=["POST"])
def kick_player(match_id):
    user_id, match, err = _require_host(match_id)
    if err:
        return err

    data = request.get_json(silent=True) or {}
    target_player_id = data.get("player_id")
    if not target_player_id:
        return jsonify({"error": "player_id required."}), 400

    mp = MatchPlayer.query.filter_by(match_id=match_id, id=int(target_player_id)).first()
    if not mp:
        return jsonify({"error": "Player not found in match."}), 404

    if mp.user_id == match.host_user_id:
        return jsonify({"error": "Cannot kick the host."}), 400

    if match.status == "active":
        # Mark bankrupt in live game
        gs = load_game_state(match_id, redis_client)
        from app.engine.game_loop import handle_player_bankrupt
        gs = handle_player_bankrupt(gs, mp.id, None, match_id, socketio)
        persist_game_state(gs, match_id, redis_client)
    else:
        db.session.delete(mp)
        db.session.commit()

    socketio.emit("player_disconnected", {"player_id": target_player_id, "kicked": True}, room=str(match_id))
    return jsonify({"message": f"Player {target_player_id} kicked."}), 200


# ---------------------------------------------------------------------------
# POST /api/admin/<match_id>/end
# ---------------------------------------------------------------------------

@admin_bp.route("/<int:match_id>/end", methods=["POST"])
def force_end_game(match_id):
    user_id, match, err = _require_host(match_id)
    if err:
        return err

    match.status = "completed"
    db.session.commit()

    socketio.emit("game_over", {"match_id": match_id, "reason": "host_ended"}, room=str(match_id))
    return jsonify({"message": "Game ended by host."}), 200


# ---------------------------------------------------------------------------
# POST /api/admin/<match_id>/auction/resolve
# ---------------------------------------------------------------------------

@admin_bp.route("/<int:match_id>/auction/resolve", methods=["POST"])
def force_resolve_auction(match_id):
    user_id, match, err = _require_host(match_id)
    if err:
        return err

    data = request.get_json(silent=True) or {}
    prop_id = data.get("property_id")
    if not prop_id:
        return jsonify({"error": "property_id required."}), 400

    from app.engine.events import resolve_auction
    gs = load_game_state(match_id, redis_client)
    econ = gs.get("econ", {})
    gs, econ, logs = resolve_auction(int(prop_id), gs, econ, redis_client, socketio, match_id)
    gs["econ"] = econ
    persist_game_state(gs, match_id, redis_client)
    return jsonify({"logs": logs}), 200


# ---------------------------------------------------------------------------
# GET /api/admin/<match_id>/state  — full raw state for host debugging
# ---------------------------------------------------------------------------

@admin_bp.route("/<int:match_id>/state", methods=["GET"])
def admin_game_state(match_id):
    user_id, match, err = _require_host(match_id)
    if err:
        return err

    gs = load_game_state(match_id, redis_client)
    return jsonify({"state": gs}), 200


# ---------------------------------------------------------------------------
# POST /api/admin/<match_id>/plot/debug-seed
# ---------------------------------------------------------------------------

@admin_bp.route("/<int:match_id>/plot/debug-seed", methods=["POST"])
def admin_seed_plot_debug_state(match_id):
    user_id, match, err = _require_host(match_id)
    if err:
        return err
    if not current_app.config.get("ENABLE_HOST_DEBUG_TOOLS", False):
        return jsonify({"error": "Host debug tools are disabled."}), 403
    if match.status != "active":
        return jsonify({"error": "The communist plot debug seed is only available during an active match."}), 400

    host_player = MatchPlayer.query.filter_by(match_id=match_id, user_id=user_id).first()
    if not host_player:
        return jsonify({"error": "The host does not have an active player slot in this match."}), 400

    gs = load_game_state(match_id, redis_client)
    try:
        gs, result = seed_debug_communist_plot_state(gs, revolutionary_player_id=host_player.id)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    persist_game_state(gs, match_id, redis_client)
    log_and_broadcast(
        gs,
        "plot_debug_seeded",
        result.get("summary") or "Host seeded a communist plot debug scenario.",
        match_id,
        redis_client,
        socketio,
        player_id=host_player.id,
    )
    broadcast_game_state_snapshot(socketio, match_id, gs)
    socketio.emit("plot_updated", {"match_id": match_id, "plot": gs.get("social", {}).get("plot", {})}, room=str(match_id))
    return jsonify({"message": result.get("summary"), "plot": gs.get("social", {}).get("plot", {})}), 200
