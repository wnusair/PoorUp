from app.routes.auth import auth_bp
from app.routes.lobby import lobby_bp
from app.routes.game import game_bp
from app.routes.admin import admin_bp

__all__ = ["auth_bp", "lobby_bp", "game_bp", "admin_bp"]
