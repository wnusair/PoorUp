from datetime import datetime

from app import db


class Deal(db.Model):
    __tablename__ = "deals"

    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.Integer, db.ForeignKey("matches.id"), nullable=False)
    proposer_id = db.Column(db.Integer, db.ForeignKey("match_players.id"), nullable=False)
    counterparty_id = db.Column(db.Integer, db.ForeignKey("match_players.id"), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="proposed")
    title = db.Column(db.String(80), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    responded_at = db.Column(db.DateTime, nullable=True)
    accepted_at = db.Column(db.DateTime, nullable=True)
    cancelled_at = db.Column(db.DateTime, nullable=True)
    last_updated_at = db.Column(db.DateTime, default=datetime.utcnow)
    proposal_version = db.Column(db.Integer, default=1)
    counter_of_deal_id = db.Column(db.Integer, db.ForeignKey("deals.id"), nullable=True)

    match = db.relationship("Match", back_populates="deals")
    proposer = db.relationship("MatchPlayer", foreign_keys=[proposer_id])
    counterparty = db.relationship("MatchPlayer", foreign_keys=[counterparty_id])
    clauses = db.relationship("DealClause", back_populates="deal", cascade="all, delete-orphan")
    counter_of = db.relationship("Deal", remote_side=[id], foreign_keys=[counter_of_deal_id])

    def to_dict(self):
        return {
            "id": self.id,
            "match_id": self.match_id,
            "proposer_id": self.proposer_id,
            "counterparty_id": self.counterparty_id,
            "status": self.status,
            "title": self.title,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "responded_at": self.responded_at.isoformat() if self.responded_at else None,
            "accepted_at": self.accepted_at.isoformat() if self.accepted_at else None,
            "cancelled_at": self.cancelled_at.isoformat() if self.cancelled_at else None,
            "last_updated_at": self.last_updated_at.isoformat() if self.last_updated_at else None,
            "proposal_version": self.proposal_version,
            "counter_of_deal_id": self.counter_of_deal_id,
            "clauses": [clause.to_dict() for clause in (self.clauses or [])],
        }


class DealClause(db.Model):
    __tablename__ = "deal_clauses"

    id = db.Column(db.Integer, primary_key=True)
    deal_id = db.Column(db.Integer, db.ForeignKey("deals.id"), nullable=False)
    clause_type = db.Column(db.String(30), nullable=False)
    grantor_id = db.Column(db.Integer, db.ForeignKey("match_players.id"), nullable=False)
    beneficiary_id = db.Column(db.Integer, db.ForeignKey("match_players.id"), nullable=False)
    scope_json = db.Column(db.JSON, nullable=False, default=dict)
    config_json = db.Column(db.JSON, nullable=False, default=dict)
    deadline_json = db.Column(db.JSON, nullable=False, default=dict)
    state_json = db.Column(db.JSON, nullable=False, default=dict)
    status = db.Column(db.String(20), nullable=False, default="pending")
    activated_at = db.Column(db.DateTime, nullable=True)
    expired_at = db.Column(db.DateTime, nullable=True)

    deal = db.relationship("Deal", back_populates="clauses")
    grantor = db.relationship("MatchPlayer", foreign_keys=[grantor_id])
    beneficiary = db.relationship("MatchPlayer", foreign_keys=[beneficiary_id])
    investment_tranches = db.relationship(
        "DealInvestmentTranche",
        back_populates="clause",
        cascade="all, delete-orphan",
    )

    def to_dict(self):
        return {
            "id": self.id,
            "deal_id": self.deal_id,
            "clause_type": self.clause_type,
            "grantor_id": self.grantor_id,
            "beneficiary_id": self.beneficiary_id,
            "scope_json": self.scope_json or {},
            "config_json": self.config_json or {},
            "deadline_json": self.deadline_json or {},
            "state_json": self.state_json or {},
            "status": self.status,
            "activated_at": self.activated_at.isoformat() if self.activated_at else None,
            "expired_at": self.expired_at.isoformat() if self.expired_at else None,
            "investment_tranches": [tranche.to_dict() for tranche in (self.investment_tranches or [])],
        }


class DealInvestmentTranche(db.Model):
    __tablename__ = "deal_investment_tranches"

    id = db.Column(db.Integer, primary_key=True)
    deal_clause_id = db.Column(db.Integer, db.ForeignKey("deal_clauses.id"), nullable=False)
    property_id = db.Column(db.Integer, db.ForeignKey("properties.id"), nullable=False)
    investor_id = db.Column(db.Integer, db.ForeignKey("match_players.id"), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey("match_players.id"), nullable=False)
    funded_cost = db.Column(db.Numeric(10, 2), nullable=False)
    baseline_dev_level = db.Column(db.Integer, nullable=False)
    funded_dev_level = db.Column(db.Integer, nullable=False)
    baseline_rent = db.Column(db.Numeric(10, 2), nullable=False)
    funded_rent = db.Column(db.Numeric(10, 2), nullable=False)
    profit_share_percent = db.Column(db.Numeric(5, 4), nullable=False)
    max_payout = db.Column(db.Numeric(10, 2), nullable=False)
    payout_to_date = db.Column(db.Numeric(10, 2), default=0)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    clause = db.relationship("DealClause", back_populates="investment_tranches")
    property = db.relationship("Property")
    investor = db.relationship("MatchPlayer", foreign_keys=[investor_id])
    recipient = db.relationship("MatchPlayer", foreign_keys=[recipient_id])

    def to_dict(self):
        return {
            "id": self.id,
            "deal_clause_id": self.deal_clause_id,
            "property_id": self.property_id,
            "investor_id": self.investor_id,
            "recipient_id": self.recipient_id,
            "funded_cost": float(self.funded_cost) if self.funded_cost is not None else 0.0,
            "baseline_dev_level": self.baseline_dev_level,
            "funded_dev_level": self.funded_dev_level,
            "baseline_rent": float(self.baseline_rent) if self.baseline_rent is not None else 0.0,
            "funded_rent": float(self.funded_rent) if self.funded_rent is not None else 0.0,
            "profit_share_percent": float(self.profit_share_percent) if self.profit_share_percent is not None else 0.0,
            "max_payout": float(self.max_payout) if self.max_payout is not None else 0.0,
            "payout_to_date": float(self.payout_to_date) if self.payout_to_date is not None else 0.0,
            "active": bool(self.active),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }