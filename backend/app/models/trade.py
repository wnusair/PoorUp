from datetime import datetime
from app import db
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy import Integer


class Trade(db.Model):
    __tablename__ = "trades"

    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.Integer, db.ForeignKey("matches.id"), nullable=False)
    initiator_id = db.Column(db.Integer, db.ForeignKey("match_players.id"), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey("match_players.id"), nullable=False)
    offered_money = db.Column(db.Numeric(10, 2), default=0)
    requested_money = db.Column(db.Numeric(10, 2), default=0)
    offered_props = db.Column(ARRAY(Integer), default=[])
    requested_props = db.Column(ARRAY(Integer), default=[])
    offered_lobby_pledges = db.Column(db.JSON, default=list)
    requested_lobby_pledges = db.Column(db.JSON, default=list)
    status = db.Column(db.String(20), default="pending")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    resolved_at = db.Column(db.DateTime, nullable=True)

    match = db.relationship("Match", back_populates="trades")
    initiator = db.relationship("MatchPlayer", foreign_keys=[initiator_id])
    receiver = db.relationship("MatchPlayer", foreign_keys=[receiver_id])

    def to_dict(self):
        return {
            "id": self.id,
            "match_id": self.match_id,
            "initiator_id": self.initiator_id,
            "receiver_id": self.receiver_id,
            "offered_money": float(self.offered_money) if self.offered_money is not None else 0.0,
            "requested_money": float(self.requested_money) if self.requested_money is not None else 0.0,
            "offered_props": self.offered_props or [],
            "requested_props": self.requested_props or [],
            "offered_lobby_pledges": self.offered_lobby_pledges or [],
            "requested_lobby_pledges": self.requested_lobby_pledges or [],
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }
