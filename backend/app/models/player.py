from datetime import datetime
from app import db
from app.utils.bot_registry import build_public_bot_metadata


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(12), unique=True, nullable=False)
    password_hash = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    matches = db.relationship("MatchPlayer", back_populates="user")

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Match(db.Model):
    __tablename__ = "matches"

    id = db.Column(db.Integer, primary_key=True)
    room_code = db.Column(db.String(8), unique=True)
    host_user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    government_type = db.Column(db.String(30))
    status = db.Column(db.String(20), default="lobby")
    settings_json = db.Column(db.JSON, default=dict)
    current_round = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    host = db.relationship("User", foreign_keys=[host_user_id])
    players = db.relationship("MatchPlayer", back_populates="match", cascade="all, delete-orphan")
    properties = db.relationship("Property", back_populates="match", cascade="all, delete-orphan")
    government = db.relationship("Government", back_populates="match", uselist=False, cascade="all, delete-orphan")
    policies = db.relationship("Policy", back_populates="match", cascade="all, delete-orphan")
    trades = db.relationship("Trade", back_populates="match", cascade="all, delete-orphan")
    deals = db.relationship("Deal", back_populates="match", cascade="all, delete-orphan")
    teams = db.relationship("Team", back_populates="match", cascade="all, delete-orphan")
    logs = db.relationship("GameLog", back_populates="match", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "room_code": self.room_code,
            "host_user_id": self.host_user_id,
            "government_type": self.government_type,
            "status": self.status,
            "settings_json": self.settings_json,
            "current_round": self.current_round,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class MatchPlayer(db.Model):
    __tablename__ = "match_players"

    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.Integer, db.ForeignKey("matches.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    color_hex = db.Column(db.String(7))
    balance = db.Column(db.Numeric(14, 2), default=0)
    influence_score = db.Column(db.Numeric(8, 2), default=0)
    approval_rating = db.Column(db.Numeric(5, 2), default=50.0)
    current_position = db.Column(db.Integer, default=0)
    is_jailed = db.Column(db.Boolean, default=False)
    jail_turns_remaining = db.Column(db.Integer, default=0)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=True)
    is_bankrupt = db.Column(db.Boolean, default=False)
    is_connected = db.Column(db.Boolean, default=True)
    has_jail_card = db.Column(db.Boolean, default=False)
    consecutive_doubles = db.Column(db.Integer, default=0)
    is_ready = db.Column(db.Boolean, default=False)
    is_bot = db.Column(db.Boolean, default=False)
    bot_profile = db.Column(db.JSON, default=dict)

    match = db.relationship("Match", back_populates="players")
    user = db.relationship("User", back_populates="matches")
    team = db.relationship("Team", foreign_keys=[team_id], back_populates="members")
    owned_properties = db.relationship("Property", back_populates="owner")

    def to_dict(self):
        data = {
            "id": self.id,
            "match_id": self.match_id,
            "user_id": self.user_id,
            "username": self.user.username if self.user else None,
            "color_hex": self.color_hex,
            "balance": float(self.balance) if self.balance is not None else 0.0,
            "influence_score": float(self.influence_score) if self.influence_score is not None else 0.0,
            "approval_rating": float(self.approval_rating) if self.approval_rating is not None else 50.0,
            "current_position": self.current_position,
            "is_jailed": self.is_jailed,
            "jail_turns_remaining": self.jail_turns_remaining,
            "team_id": self.team_id,
            "is_bankrupt": self.is_bankrupt,
            "is_connected": self.is_connected,
            "has_jail_card": self.has_jail_card,
            "consecutive_doubles": self.consecutive_doubles,
            "is_ready": self.is_ready,
            "is_bot": self.is_bot,
        }
        if self.is_bot:
            data.update(build_public_bot_metadata(self.bot_profile))
        return data
