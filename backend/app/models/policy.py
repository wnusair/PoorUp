from app import db



LOBBYING_AXES = {
    "tax_multiplier": {
        "axis": "tax_multiplier",
        "label": "Tax Multiplier",
        "description": "Push taxes lower for relief or higher to refill the treasury.",
        "order": 10,
        "directions": {
            "decrease": {"label": "Decrease", "target": "tax_multiplier_decrease"},
            "increase": {"label": "Increase", "target": "tax_multiplier_increase"},
        },
    },
    "welfare_rate": {
        "axis": "welfare_rate",
        "label": "Welfare Rate",
        "description": "Reduce welfare drag or increase recovery support for low-cash players.",
        "order": 20,
        "directions": {
            "decrease": {"label": "Decrease", "target": "welfare_decrease"},
            "increase": {"label": "Increase", "target": "welfare_increase"},
        },
    },
    "bailouts": {
        "axis": "bailouts",
        "label": "Bailouts",
        "description": "Turn treasury-backed rescues off or on.",
        "order": 30,
        "directions": {
            "disable": {"label": "Disable", "target": "bailout_disable"},
            "enable": {"label": "Enable", "target": "bailout_enable"},
        },
    },
    "housing_regulation": {
        "axis": "housing_regulation",
        "label": "Housing Regulation",
        "description": "Tighten rent regulation or loosen it for development upside.",
        "order": 40,
        "directions": {
            "tighten": {"label": "Tighten", "target": "rent_control"},
            "loosen": {"label": "Loosen", "target": "deregulate_housing"},
        },
    },
    "treasury_posture": {
        "axis": "treasury_posture",
        "label": "Treasury Posture",
        "description": "Rebuild the treasury or spend it on direct stimulus.",
        "order": 50,
        "directions": {
            "rebuild": {"label": "Rebuild", "target": "stabilization_fund"},
            "stimulate": {"label": "Stimulate", "target": "economic_stimulus"},
        },
    },
}


DEFAULT_LOBBYING_POLICIES = {
    "tax_multiplier_decrease": {
        "policy_name": "Tax Relief",
        "target_stat": "tax_multiplier_decrease",
        "axis": "tax_multiplier",
        "axis_label": "Tax Multiplier",
        "direction": "decrease",
        "direction_label": "Decrease",
        "effect_value": -0.08,
        "cost_hint": 200,
        "description": "Cut the tax multiplier by a meaningful amount. Bigger lobbying pools push the cut further.",
    },
    "welfare_increase": {
        "policy_name": "Welfare Increase",
        "target_stat": "welfare_increase",
        "axis": "welfare_rate",
        "axis_label": "Welfare Rate",
        "direction": "increase",
        "direction_label": "Increase",
        "effect_value": 12.5,
        "cost_hint": 250,
        "description": "Raise the welfare rate so low-cash players recover faster toward the welfare target.",
    },
    "welfare_decrease": {
        "policy_name": "Welfare Cuts",
        "target_stat": "welfare_decrease",
        "axis": "welfare_rate",
        "axis_label": "Welfare Rate",
        "direction": "decrease",
        "direction_label": "Decrease",
        "effect_value": -12.5,
        "cost_hint": 220,
        "description": "Reduce the welfare rate. Bigger pooled lobbying makes the cut deeper.",
    },
    "tax_multiplier_increase": {
        "policy_name": "Tax Hike",
        "target_stat": "tax_multiplier_increase",
        "axis": "tax_multiplier",
        "axis_label": "Tax Multiplier",
        "direction": "increase",
        "direction_label": "Increase",
        "effect_value": 0.08,
        "cost_hint": 240,
        "description": "Raise taxes sharply when the lobby pool is large enough.",
    },
    "rent_control": {
        "policy_name": "Rent Control",
        "target_stat": "rent_control",
        "axis": "housing_regulation",
        "axis_label": "Housing Regulation",
        "direction": "tighten",
        "direction_label": "Tighten",
        "effect_value": 0,
        "cost_hint": 300,
        "description": "Cap rents and calm the economy with a small stability boost.",
    },
    "deregulate_housing": {
        "policy_name": "Housing Deregulation",
        "target_stat": "deregulate_housing",
        "axis": "housing_regulation",
        "axis_label": "Housing Regulation",
        "direction": "loosen",
        "direction_label": "Loosen",
        "effect_value": 0.15,
        "cost_hint": 400,
        "description": "Lift rent control and increase development upside for landlords.",
    },
    "stabilization_fund": {
        "policy_name": "Stabilization Fund",
        "target_stat": "stabilization_fund",
        "axis": "treasury_posture",
        "axis_label": "Treasury Posture",
        "direction": "rebuild",
        "direction_label": "Rebuild",
        "effect_value": 400,
        "cost_hint": 250,
        "description": "Inject cash into the treasury and improve stability.",
    },
    "economic_stimulus": {
        "policy_name": "Economic Stimulus",
        "target_stat": "economic_stimulus",
        "axis": "treasury_posture",
        "axis_label": "Treasury Posture",
        "direction": "stimulate",
        "direction_label": "Stimulate",
        "effect_value": 125,
        "cost_hint": 450,
        "description": "Pay every active player a sizable treasury-funded stimulus.",
    },
    "bailout_enable": {
        "policy_name": "Enable Bailouts",
        "target_stat": "bailout_enable",
        "axis": "bailouts",
        "axis_label": "Bailouts",
        "direction": "enable",
        "direction_label": "Enable",
        "effect_value": 1,
        "cost_hint": 260,
        "description": "Turn on government bailouts so debt spirals can be covered by the treasury when funds exist.",
    },
    "bailout_disable": {
        "policy_name": "Disable Bailouts",
        "target_stat": "bailout_disable",
        "axis": "bailouts",
        "axis_label": "Bailouts",
        "direction": "disable",
        "direction_label": "Disable",
        "effect_value": 1,
        "cost_hint": 260,
        "description": "Turn off government bailouts so the treasury stops rescuing debtors.",
    },
}

TARGET_STAT_TO_POLICY_KEY = {
    definition["target_stat"]: target
    for target, definition in DEFAULT_LOBBYING_POLICIES.items()
}

LOBBYING_BASE_SUCCESS_CHANCE = 0.18
LOBBYING_MAX_SUCCESS_CHANCE = 0.97
LOBBYING_MAX_EFFECT_MULTIPLIER = 2.5

TARGET_TO_AXIS_DIRECTION = {
    target: {
        "axis": definition["axis"],
        "direction": definition["direction"],
        "axis_label": definition["axis_label"],
        "direction_label": definition["direction_label"],
    }
    for target, definition in DEFAULT_LOBBYING_POLICIES.items()
}


class Policy(db.Model):
    __tablename__ = "policies"

    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.Integer, db.ForeignKey("matches.id"), nullable=False)
    policy_name = db.Column(db.String(80), nullable=False)
    target_stat = db.Column(db.String(40))
    effect_value = db.Column(db.Numeric(8, 4))
    is_active = db.Column(db.Boolean, default=False)

    match = db.relationship("Match", back_populates="policies")
    lobbying_entries = db.relationship("Lobbying", back_populates="policy", cascade="all, delete-orphan")

    def to_dict(self):
        definition = get_lobbying_policy_definition(target_stat=self.target_stat)
        return {
            "id": self.id,
            "match_id": self.match_id,
            "policy_name": self.policy_name,
            "target_stat": self.target_stat,
            "axis": definition.get("axis") if definition else None,
            "axis_label": definition.get("axis_label") if definition else None,
            "direction": definition.get("direction") if definition else None,
            "direction_label": definition.get("direction_label") if definition else None,
            "effect_value": float(self.effect_value) if self.effect_value is not None else None,
            "is_active": self.is_active,
            "cost_hint": int(definition.get("cost_hint", 0)) if definition else 0,
            "description": definition.get("description", "") if definition else "",
        }


class Lobbying(db.Model):
    __tablename__ = "lobbies"

    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.Integer, db.ForeignKey("matches.id"), nullable=False)
    policy_id = db.Column(db.Integer, db.ForeignKey("policies.id"), nullable=False)
    player_id = db.Column(db.Integer, db.ForeignKey("match_players.id"), nullable=False)
    contribution = db.Column(db.Numeric(10, 2), default=0)

    policy = db.relationship("Policy", back_populates="lobbying_entries")
    player = db.relationship("MatchPlayer")

    def to_dict(self):
        return {
            "id": self.id,
            "match_id": self.match_id,
            "policy_id": self.policy_id,
            "player_id": self.player_id,
            "contribution": float(self.contribution) if self.contribution is not None else 0.0,
        }


def get_default_lobbying_policies() -> list[dict]:
    return [
        {"target": target, **definition}
        for target, definition in DEFAULT_LOBBYING_POLICIES.items()
    ]


def get_lobbying_axes() -> list[dict]:
    axes = []
    for axis_key, definition in sorted(LOBBYING_AXES.items(), key=lambda item: item[1]["order"]):
        axes.append({
            "axis": axis_key,
            "label": definition["label"],
            "description": definition["description"],
            "order": definition["order"],
            "directions": [
                {
                    "key": direction_key,
                    "label": direction_definition["label"],
                    "target": direction_definition["target"],
                }
                for direction_key, direction_definition in definition["directions"].items()
            ],
        })
    return axes


def get_lobbying_policy_key(target: str | None = None, target_stat: str | None = None) -> str | None:
    if target and target in DEFAULT_LOBBYING_POLICIES:
        return target

    if target_stat:
        return TARGET_STAT_TO_POLICY_KEY.get(target_stat)

    return None


def get_lobbying_policy_definition(target: str | None = None, target_stat: str | None = None) -> dict | None:
    if target:
        definition = DEFAULT_LOBBYING_POLICIES.get(target)
        if definition is not None:
            return dict(definition)

    if target_stat:
        target_key = TARGET_STAT_TO_POLICY_KEY.get(target_stat)
        if target_key:
            return dict(DEFAULT_LOBBYING_POLICIES[target_key])

    return None


def resolve_lobbying_target(
    *,
    axis: str | None = None,
    direction: str | None = None,
    target: str | None = None,
    target_stat: str | None = None,
) -> str | None:
    if axis and direction:
        axis_key = str(axis).strip().lower().replace("-", "_").replace(" ", "_")
        direction_key = str(direction).strip().lower().replace("-", "_").replace(" ", "_")
        axis_definition = LOBBYING_AXES.get(axis_key)
        if axis_definition is not None:
            direction_definition = axis_definition["directions"].get(direction_key)
            if direction_definition is not None:
                return direction_definition["target"]

    return get_lobbying_policy_key(target=target, target_stat=target_stat)


def get_lobbying_axis_direction(
    *,
    axis: str | None = None,
    direction: str | None = None,
    target: str | None = None,
    target_stat: str | None = None,
) -> dict | None:
    target_key = resolve_lobbying_target(axis=axis, direction=direction, target=target, target_stat=target_stat)
    if not target_key:
        return None
    definition = TARGET_TO_AXIS_DIRECTION.get(target_key)
    if not definition:
        return None
    return dict(definition)


def calculate_lobbying_success_chance(
    target: str | None = None,
    target_stat: str | None = None,
    total_contribution: float = 0.0,
    contributor_count: int = 1,
) -> float:
    definition = get_lobbying_policy_definition(target=target, target_stat=target_stat) or {}
    cost_hint = max(1.0, float(definition.get("cost_hint", 250) or 250))
    contribution_ratio = max(0.0, float(total_contribution or 0) / cost_hint)
    money_bonus = min(0.62, contribution_ratio * 0.47)
    contributor_bonus = min(0.15, max(0, int(contributor_count) - 1) * 0.05)
    chance = LOBBYING_BASE_SUCCESS_CHANCE + money_bonus + contributor_bonus
    return round(min(LOBBYING_MAX_SUCCESS_CHANCE, chance), 4)


def calculate_lobbying_effect_multiplier(
    target: str | None = None,
    target_stat: str | None = None,
    total_contribution: float = 0.0,
    contributor_count: int = 1,
) -> float:
    definition = get_lobbying_policy_definition(target=target, target_stat=target_stat) or {}
    cost_hint = max(1.0, float(definition.get("cost_hint", 250) or 250))
    contribution_ratio = max(0.0, float(total_contribution or 0) / cost_hint)
    contributor_bonus = min(0.30, max(0, int(contributor_count) - 1) * 0.05)
    multiplier = 0.75 + (contribution_ratio * 0.75) + contributor_bonus
    return round(min(LOBBYING_MAX_EFFECT_MULTIPLIER, max(0.75, multiplier)), 4)


def ensure_match_lobbying_policy(match_id: int, target: str):
    definition = DEFAULT_LOBBYING_POLICIES.get(target)
    if definition is None:
        return None

    policy = Policy.query.filter_by(match_id=match_id, target_stat=definition["target_stat"]).first()
    if policy is not None:
        policy.policy_name = definition["policy_name"]
        policy.target_stat = definition["target_stat"]
        policy.effect_value = definition["effect_value"]
        return policy

    policy = Policy(
        match_id=match_id,
        policy_name=definition["policy_name"],
        target_stat=definition["target_stat"],
        effect_value=definition["effect_value"],
        is_active=False,
    )
    db.session.add(policy)
    db.session.flush()
    return policy


def seed_default_lobbying_policies(match_id: int) -> list[Policy]:
    policies = []
    for target in DEFAULT_LOBBYING_POLICIES:
        policy = ensure_match_lobbying_policy(match_id, target)
        if policy is not None:
            policies.append(policy)
    return policies
