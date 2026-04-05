from app import db


class Property(db.Model):
    __tablename__ = "properties"

    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.Integer, db.ForeignKey("matches.id"), nullable=False)
    name = db.Column(db.String(60), nullable=False)
    region = db.Column(db.String(40))
    group_color = db.Column(db.String(7))
    board_position = db.Column(db.Integer, nullable=False)
    base_price = db.Column(db.Numeric(10, 2))
    current_value = db.Column(db.Numeric(10, 2))
    dev_level = db.Column(db.Integer, default=0)
    owner_id = db.Column(db.Integer, db.ForeignKey("match_players.id"), nullable=True)
    is_mortgaged = db.Column(db.Boolean, default=False)
    property_type = db.Column(db.String(20), default="property")

    match = db.relationship("Match", back_populates="properties")
    owner = db.relationship("MatchPlayer", back_populates="owned_properties")

    def to_dict(self):
        return {
            "id": self.id,
            "match_id": self.match_id,
            "name": self.name,
            "region": self.region,
            "group_color": self.group_color,
            "board_position": self.board_position,
            "base_price": float(self.base_price) if self.base_price is not None else None,
            "current_value": float(self.current_value) if self.current_value is not None else None,
            "dev_level": self.dev_level,
            "owner_id": self.owner_id,
            "is_mortgaged": self.is_mortgaged,
            "property_type": self.property_type,
        }
