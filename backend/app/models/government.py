from app import db


class Government(db.Model):
    __tablename__ = "governments"

    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.Integer, db.ForeignKey("matches.id"), unique=True, nullable=False)
    gov_type = db.Column(db.String(30))
    stability = db.Column(db.Numeric(5, 2))
    treasury_balance = db.Column(db.Numeric(14, 2))
    welfare_payout = db.Column(db.Numeric(10, 2))
    tax_multiplier = db.Column(db.Numeric(5, 3))
    inflation_rate = db.Column(db.Numeric(5, 4))
    interest_rate = db.Column(db.Numeric(5, 4))

    match = db.relationship("Match", back_populates="government")

    def to_dict(self):
        return {
            "id": self.id,
            "match_id": self.match_id,
            "gov_type": self.gov_type,
            "stability": float(self.stability) if self.stability is not None else 0.0,
            "treasury_balance": float(self.treasury_balance) if self.treasury_balance is not None else 0.0,
            "welfare_payout": float(self.welfare_payout) if self.welfare_payout is not None else 0.0,
            "tax_multiplier": float(self.tax_multiplier) if self.tax_multiplier is not None else 0.0,
            "inflation_rate": float(self.inflation_rate) if self.inflation_rate is not None else 0.0,
            "interest_rate": float(self.interest_rate) if self.interest_rate is not None else 0.0,
        }
