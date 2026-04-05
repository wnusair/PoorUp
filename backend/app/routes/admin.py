"""
Admin/host controls for PoorUp.
Host-only actions: kick player, force-end game, reset auction timer.
"""
from flask import Blueprint, request, jsonify, session

from app import db, redis_client, socketio
from app.models.player import Match, MatchPlayer
from app.engine.game_loop import load_game_state, persist_game_state, log_and_broadcast

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
