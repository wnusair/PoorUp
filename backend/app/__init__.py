import eventlet
eventlet.monkey_patch()

import redis as redis_lib
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_session import Session
from flask_cors import CORS
from flask_socketio import SocketIO
from sqlalchemy import text

from config import get_config

db = SQLAlchemy()
migrate = Migrate()
socketio = SocketIO()
sess = Session()

redis_client: redis_lib.Redis = None


def _ensure_runtime_schema(app: Flask) -> None:
    with app.app_context():
        if db.engine.dialect.name != "postgresql":
            return
        db.session.execute(text("ALTER TABLE match_players ADD COLUMN IF NOT EXISTS is_bot BOOLEAN DEFAULT FALSE"))
        db.session.execute(text("ALTER TABLE match_players ADD COLUMN IF NOT EXISTS bot_profile JSONB DEFAULT '{}'::jsonb"))
        db.session.execute(text("ALTER TABLE trades ADD COLUMN IF NOT EXISTS offered_lobby_pledges JSONB DEFAULT '[]'::jsonb"))
        db.session.execute(text("ALTER TABLE trades ADD COLUMN IF NOT EXISTS requested_lobby_pledges JSONB DEFAULT '[]'::jsonb"))
        db.session.execute(text("ALTER TABLE trades ADD COLUMN IF NOT EXISTS included_deal_drafts JSONB DEFAULT '[]'::jsonb"))
        db.session.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS deals (
                    id SERIAL PRIMARY KEY,
                    match_id INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
                    proposer_id INTEGER NOT NULL REFERENCES match_players(id) ON DELETE CASCADE,
                    counterparty_id INTEGER NOT NULL REFERENCES match_players(id) ON DELETE CASCADE,
                    status VARCHAR(20) NOT NULL DEFAULT 'proposed',
                    title VARCHAR(80),
                    created_at TIMESTAMP DEFAULT now(),
                    responded_at TIMESTAMP NULL,
                    accepted_at TIMESTAMP NULL,
                    cancelled_at TIMESTAMP NULL,
                    last_updated_at TIMESTAMP DEFAULT now(),
                    proposal_version INTEGER DEFAULT 1,
                    counter_of_deal_id INTEGER NULL REFERENCES deals(id),
                    termination_requested_by_id INTEGER NULL REFERENCES match_players(id) ON DELETE SET NULL,
                    termination_requested_at TIMESTAMP NULL
                )
                """
            )
        )
        db.session.execute(
            text(
                "ALTER TABLE deals ADD COLUMN IF NOT EXISTS termination_requested_by_id INTEGER REFERENCES match_players(id) ON DELETE SET NULL"
            )
        )
        db.session.execute(text("ALTER TABLE deals ADD COLUMN IF NOT EXISTS termination_requested_at TIMESTAMP NULL"))
        db.session.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS deal_clauses (
                    id SERIAL PRIMARY KEY,
                    deal_id INTEGER NOT NULL REFERENCES deals(id) ON DELETE CASCADE,
                    clause_type VARCHAR(30) NOT NULL,
                    grantor_id INTEGER NOT NULL REFERENCES match_players(id) ON DELETE CASCADE,
                    beneficiary_id INTEGER NOT NULL REFERENCES match_players(id) ON DELETE CASCADE,
                    scope_json JSONB NOT NULL DEFAULT '{}'::jsonb,
                    config_json JSONB NOT NULL DEFAULT '{}'::jsonb,
                    deadline_json JSONB NOT NULL DEFAULT '{}'::jsonb,
                    state_json JSONB NOT NULL DEFAULT '{}'::jsonb,
                    status VARCHAR(20) NOT NULL DEFAULT 'pending',
                    activated_at TIMESTAMP NULL,
                    expired_at TIMESTAMP NULL
                )
                """
            )
        )
        db.session.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS deal_investment_tranches (
                    id SERIAL PRIMARY KEY,
                    deal_clause_id INTEGER NOT NULL REFERENCES deal_clauses(id) ON DELETE CASCADE,
                    property_id INTEGER NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
                    investor_id INTEGER NOT NULL REFERENCES match_players(id) ON DELETE CASCADE,
                    recipient_id INTEGER NOT NULL REFERENCES match_players(id) ON DELETE CASCADE,
                    funded_cost NUMERIC(10,2) NOT NULL,
                    baseline_dev_level INTEGER NOT NULL,
                    funded_dev_level INTEGER NOT NULL,
                    baseline_rent NUMERIC(10,2) NOT NULL,
                    funded_rent NUMERIC(10,2) NOT NULL,
                    profit_share_percent NUMERIC(5,4) NOT NULL,
                    max_payout NUMERIC(10,2) NOT NULL,
                    payout_to_date NUMERIC(10,2) DEFAULT 0,
                    active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT now()
                )
                """
            )
        )
        db.session.commit()


def create_app(config_class=None):
    global redis_client

    app = Flask(__name__)

    cfg = config_class or get_config()
    app.config.from_object(cfg)

    # Redis client (shared, decode_responses=True for app use)
    redis_client = redis_lib.from_url(app.config["REDIS_URL"], decode_responses=True)
    # Flask-Session needs binary responses (msgpack), so a separate client without decode_responses
    app.config["SESSION_REDIS"] = redis_lib.from_url(app.config["REDIS_URL"], decode_responses=False)

    # Extensions
    db.init_app(app)
    migrate.init_app(app, db)
    sess.init_app(app)
    CORS(app, origins=app.config["CORS_ORIGINS"], supports_credentials=True)
    socketio.init_app(
        app,
        cors_allowed_origins=app.config["CORS_ORIGINS"],
        async_mode="eventlet",
        message_queue=app.config["REDIS_URL"],
        manage_session=False,
    )

    # Register blueprints
    from app.routes.auth import auth_bp
    from app.routes.lobby import lobby_bp
    from app.routes.game import game_bp
    from app.routes.admin import admin_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(lobby_bp, url_prefix="/api/lobby")
    app.register_blueprint(game_bp, url_prefix="/api/game")
    app.register_blueprint(admin_bp, url_prefix="/api/admin")

    # Register socket events
    from app.sockets import game_events  # noqa: F401

    # Import all models so SQLAlchemy knows about them
    from app.models import (  # noqa: F401
        player, property, government, policy, trade, deal, team, card, log
    )

    _ensure_runtime_schema(app)

    return app
