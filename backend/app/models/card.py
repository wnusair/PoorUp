from app import db


class Card(db.Model):
    __tablename__ = "cards"

    id = db.Column(db.Integer, primary_key=True)
    deck_type = db.Column(db.String(20), nullable=False)  # 'chance' | 'community_chest'
    card_text = db.Column(db.Text, nullable=False)
    effect_type = db.Column(db.String(40), nullable=False)
    effect_value = db.Column(db.Numeric(10, 2), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "deck_type": self.deck_type,
            "card_text": self.card_text,
            "effect_type": self.effect_type,
            "effect_value": float(self.effect_value) if self.effect_value is not None else None,
        }
