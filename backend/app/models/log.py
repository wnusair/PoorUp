from datetime import datetime
from app import db


class GameLog(db.Model):
    __tablename__ = "game_log"

    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.Integer, db.ForeignKey("matches.id"), nullable=False)
    round = db.Column(db.Integer)
    turn = db.Column(db.Integer)
    player_id = db.Column(db.Integer, db.ForeignKey("match_players.id"), nullable=True)
    event_type = db.Column(db.String(40))
    description = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    match = db.relationship("Match", back_populates="logs")
    player = db.relationship("MatchPlayer")

    def to_dict(self):
        return {
            "id": self.id,
            "match_id": self.match_id,
            "round": self.round,
            "turn": self.turn,
            "player_id": self.player_id,
            "event_type": self.event_type,
            "description": self.description,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }
