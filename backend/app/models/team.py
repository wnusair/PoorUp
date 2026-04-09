from app import db


class Team(db.Model):
    __tablename__ = "teams"

    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.Integer, db.ForeignKey("matches.id"), nullable=False)
    team_name = db.Column(db.String(30), nullable=False)
    team_color = db.Column(db.String(7))
    created_by = db.Column(db.Integer, db.ForeignKey("match_players.id"))

    match = db.relationship("Match", back_populates="teams")
    creator = db.relationship("MatchPlayer", foreign_keys=[created_by])
    members = db.relationship(
        "MatchPlayer",
        foreign_keys="MatchPlayer.team_id",
        back_populates="team",
    )

    def to_dict(self):
        return {
            "id": self.id,
            "match_id": self.match_id,
            "team_name": self.team_name,
            "team_color": self.team_color,
            "created_by": self.created_by,
            "member_ids": [m.id for m in self.members] if self.members else [],
        }
