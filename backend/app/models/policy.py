from app import db
from app.utils.settings import normalize_government_type



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
        "government_types": ["liberal_democracy", "social_democracy"],
        "directions": {
            "disable": {"label": "Disable", "target": "bailout_disable"},
            "enable": {"label": "Enable", "target": "bailout_enable"},
        },
    },
    "tax_brackets": {
        "axis": "tax_brackets",
        "label": "Tax Brackets",
        "description": "Move the net-worth pyramid or change one bracket rate at a time.",
        "order": 35,
        "government_types": ["liberal_democracy"],
        "directions": {
            "raise_boundary": {"label": "Raise Boundary", "target": "tax_bracket_boundary_up"},
            "lower_boundary": {"label": "Lower Boundary", "target": "tax_bracket_boundary_down"},
            "raise_rate": {"label": "Raise Rate", "target": "tax_bracket_rate_up"},
            "lower_rate": {"label": "Lower Rate", "target": "tax_bracket_rate_down"},
        },
    },
    "treasury_transfers": {
        "axis": "treasury_transfers",
        "label": "Treasury Transfers",
        "description": "Send treasury help to players or refill the treasury for later fights.",
        "order": 36,
        "government_types": ["liberal_democracy"],
        "directions": {
            "toward_players": {"label": "Toward Players", "target": "treasury_transfer_players"},
            "toward_treasury": {"label": "Toward Treasury", "target": "treasury_transfer_treasury"},
        },
    },
    "money_supply": {
        "axis": "money_supply",
        "label": "Money Supply",
        "description": "Expand money creation for relief or contract it to cool inflation.",
        "order": 37,
        "government_types": ["liberal_democracy"],
        "directions": {
            "expand": {"label": "Expand", "target": "money_supply_expand"},
            "contract": {"label": "Contract", "target": "money_supply_contract"},
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
        "policy_name": "Decrease Tax Rate",
        "target_stat": "tax_multiplier_decrease",
        "axis": "tax_multiplier",
        "axis_label": "Tax Multiplier",
        "direction": "decrease",
        "direction_label": "Decrease",
        "effect_value": -0.08,
        "cost_hint": 200,
        "description": "Cut the tax multiplier by a meaningful amount. Bigger lobbying pools push the cut further.",
        "government_cost_multipliers": {"liberal_democracy": 0.85},
        "government_effect_multipliers": {"liberal_democracy": 1.1},
    },
    "welfare_increase": {
        "policy_name": "Increase Welfare Rate",
        "target_stat": "welfare_increase",
        "axis": "welfare_rate",
        "axis_label": "Welfare Rate",
        "direction": "increase",
        "direction_label": "Increase",
        "effect_value": 12.5,
        "cost_hint": 250,
        "description": "Raise the welfare rate so low-cash players recover faster toward the welfare target.",
        "government_cost_multipliers": {"liberal_democracy": 1.25},
        "government_effect_multipliers": {"liberal_democracy": 0.9},
    },
    "welfare_decrease": {
        "policy_name": "Decrease Welfare Rate",
        "target_stat": "welfare_decrease",
        "axis": "welfare_rate",
        "axis_label": "Welfare Rate",
        "direction": "decrease",
        "direction_label": "Decrease",
        "effect_value": -12.5,
        "cost_hint": 220,
        "description": "Reduce the welfare rate. Bigger pooled lobbying makes the cut deeper.",
        "government_cost_multipliers": {"liberal_democracy": 0.9},
        "government_effect_multipliers": {"liberal_democracy": 1.05},
    },
    "tax_multiplier_increase": {
        "policy_name": "Increase Tax Rate",
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
        "policy_name": "Tighten Housing Rules",
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
        "policy_name": "Loosen Housing Rules",
        "target_stat": "deregulate_housing",
        "axis": "housing_regulation",
        "axis_label": "Housing Regulation",
        "direction": "loosen",
        "direction_label": "Loosen",
        "effect_value": 0.15,
        "cost_hint": 400,
        "description": "Lift rent control and increase development upside for landlords.",
        "government_cost_multipliers": {"liberal_democracy": 0.9},
        "government_effect_multipliers": {"liberal_democracy": 1.1},
    },
    "stabilization_fund": {
        "policy_name": "Rebuild Treasury",
        "target_stat": "stabilization_fund",
        "axis": "treasury_posture",
        "axis_label": "Treasury Posture",
        "direction": "rebuild",
        "direction_label": "Rebuild",
        "effect_value": 400,
        "cost_hint": 250,
        "description": "Inject cash into the treasury and improve stability.",
        "government_cost_multipliers": {"liberal_democracy": 1.1},
    },
    "economic_stimulus": {
        "policy_name": "Fund Economic Stimulus",
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
        "government_types": ["liberal_democracy", "social_democracy"],
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
        "government_types": ["liberal_democracy", "social_democracy"],
    },
    "tax_bracket_boundary_up": {
        "policy_name": "Raise Tax Boundary",
        "target_stat": "tax_bracket_boundary_up",
        "axis": "tax_brackets",
        "axis_label": "Tax Brackets",
        "direction": "raise_boundary",
        "direction_label": "Raise Boundary",
        "effect_value": 500,
        "cost_hint": 270,
        "description": "Move one tier boundary upward by $500, easing pressure on the next bracket.",
        "government_types": ["liberal_democracy"],
    },
    "tax_bracket_boundary_down": {
        "policy_name": "Lower Tax Boundary",
        "target_stat": "tax_bracket_boundary_down",
        "axis": "tax_brackets",
        "axis_label": "Tax Brackets",
        "direction": "lower_boundary",
        "direction_label": "Lower Boundary",
        "effect_value": 500,
        "cost_hint": 270,
        "description": "Move one tier boundary downward by $500, exposing more wealth to the higher bracket.",
        "government_types": ["liberal_democracy"],
    },
    "tax_bracket_rate_up": {
        "policy_name": "Raise Bracket Rate",
        "target_stat": "tax_bracket_rate_up",
        "axis": "tax_brackets",
        "axis_label": "Tax Brackets",
        "direction": "raise_rate",
        "direction_label": "Raise Rate",
        "effect_value": 0.02,
        "cost_hint": 240,
        "description": "Increase one bracket tax rate by 2 percentage points.",
        "government_types": ["liberal_democracy"],
    },
    "tax_bracket_rate_down": {
        "policy_name": "Lower Bracket Rate",
        "target_stat": "tax_bracket_rate_down",
        "axis": "tax_brackets",
        "axis_label": "Tax Brackets",
        "direction": "lower_rate",
        "direction_label": "Lower Rate",
        "effect_value": 0.02,
        "cost_hint": 240,
        "description": "Lower one bracket tax rate by 2 percentage points.",
        "government_types": ["liberal_democracy"],
    },
    "treasury_transfer_players": {
        "policy_name": "Transfer Treasury To Players",
        "target_stat": "treasury_transfer_players",
        "axis": "treasury_transfers",
        "axis_label": "Treasury Transfers",
        "direction": "toward_players",
        "direction_label": "Toward Players",
        "effect_value": 90,
        "cost_hint": 300,
        "description": "Send treasury support directly to active players.",
        "government_types": ["liberal_democracy"],
    },
    "treasury_transfer_treasury": {
        "policy_name": "Transfer Lobby Gains To Treasury",
        "target_stat": "treasury_transfer_treasury",
        "axis": "treasury_transfers",
        "axis_label": "Treasury Transfers",
        "direction": "toward_treasury",
        "direction_label": "Toward Treasury",
        "effect_value": 320,
        "cost_hint": 250,
        "description": "Refill the treasury and improve fiscal breathing room.",
        "government_types": ["liberal_democracy"],
    },
    "money_supply_expand": {
        "policy_name": "Expand Money Supply",
        "target_stat": "money_supply_expand",
        "axis": "money_supply",
        "axis_label": "Money Supply",
        "direction": "expand",
        "direction_label": "Expand",
        "effect_value": 1,
        "cost_hint": 260,
        "description": "Increase market liquidity, lower rates slightly, and raise inflation pressure.",
        "government_types": ["liberal_democracy"],
    },
    "money_supply_contract": {
        "policy_name": "Contract Money Supply",
        "target_stat": "money_supply_contract",
        "axis": "money_supply",
        "axis_label": "Money Supply",
        "direction": "contract",
        "direction_label": "Contract",
        "effect_value": 1,
        "cost_hint": 260,
        "description": "Cool inflation, tighten rates, and steady the market.",
        "government_types": ["liberal_democracy"],
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


def _normalize_lobbying_token(value: str | None) -> str | None:
    raw_value = str(value or "").strip().lower()
    if not raw_value:
        return None
    return "_".join(raw_value.replace("-", " ").split())


NORMALIZED_POLICY_KEYS = {
    _normalize_lobbying_token(target): target
    for target in DEFAULT_LOBBYING_POLICIES
}

NORMALIZED_TARGET_STAT_TO_POLICY_KEY = {
    _normalize_lobbying_token(target_stat): target
    for target_stat, target in TARGET_STAT_TO_POLICY_KEY.items()
}

NORMALIZED_POLICY_NAME_TO_POLICY_KEY = {
    _normalize_lobbying_token(definition.get("policy_name")): target
    for target, definition in DEFAULT_LOBBYING_POLICIES.items()
    if definition.get("policy_name")
}


def extract_lobbying_request_identifiers(payload: dict | None) -> dict:
    data = payload if isinstance(payload, dict) else {}
    policy_data = data.get("policy") if isinstance(data.get("policy"), dict) else {}

    policy_id = data.get("policy_id")
    if policy_id in (None, ""):
        policy_id = policy_data.get("policy_id", policy_data.get("id"))

    return {
        "policy_id": policy_id,
        "axis": data.get("axis") or data.get("axis_label") or policy_data.get("axis") or policy_data.get("axis_label"),
        "direction": data.get("direction") or data.get("direction_label") or policy_data.get("direction") or policy_data.get("direction_label"),
        "target": data.get("target") or data.get("policy_name") or policy_data.get("target") or policy_data.get("policy_name"),
        "target_stat": data.get("target_stat") or policy_data.get("target_stat"),
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

    def to_dict(self, government_type: str | None = None):
        definition = get_lobbying_policy_definition(target_stat=self.target_stat, government_type=government_type)
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


def get_default_lobbying_policies(government_type: str | None = None) -> list[dict]:
    policies = []
    for target, definition in DEFAULT_LOBBYING_POLICIES.items():
        adjusted_definition = get_lobbying_policy_definition(target=target, government_type=government_type)
        if government_type and adjusted_definition is None:
            continue
        policies.append({"target": target, **(adjusted_definition or dict(definition))})
    return policies


def _policy_available_for_government(definition: dict, government_type: str | None) -> bool:
    allowed_government_types = definition.get("government_types") or []
    if not allowed_government_types or not government_type:
        return True

    normalized_government_type = normalize_government_type(government_type)
    return normalized_government_type in {
        normalize_government_type(candidate)
        for candidate in allowed_government_types
    }


def _apply_government_modifiers(definition: dict, government_type: str | None) -> dict | None:
    next_definition = dict(definition)
    if not government_type:
        return next_definition

    normalized_government_type = normalize_government_type(government_type)
    if not _policy_available_for_government(next_definition, normalized_government_type):
        return None

    cost_multiplier = float(
        (next_definition.get("government_cost_multipliers") or {}).get(normalized_government_type, 1.0)
        or 1.0
    )
    effect_multiplier = float(
        (next_definition.get("government_effect_multipliers") or {}).get(normalized_government_type, 1.0)
        or 1.0
    )

    if next_definition.get("cost_hint") is not None:
        next_definition["cost_hint"] = int(round(float(next_definition.get("cost_hint", 0) or 0) * max(0.1, cost_multiplier)))

    if next_definition.get("effect_value") is not None:
        next_definition["effect_value"] = round(float(next_definition.get("effect_value", 0) or 0) * effect_multiplier, 4)

    next_definition["government_type"] = normalized_government_type
    return next_definition


def get_lobbying_axes(government_type: str | None = None) -> list[dict]:
    axes = []
    for axis_key, definition in sorted(LOBBYING_AXES.items(), key=lambda item: item[1]["order"]):
        if not _policy_available_for_government(definition, government_type):
            continue

        directions = []
        for direction_key, direction_definition in definition["directions"].items():
            if get_lobbying_policy_definition(target=direction_definition["target"], government_type=government_type) is None:
                continue
            directions.append({
                "key": direction_key,
                "label": direction_definition["label"],
                "target": direction_definition["target"],
            })

        if not directions:
            continue

        axes.append({
            "axis": axis_key,
            "label": definition["label"],
            "description": definition["description"],
            "order": definition["order"],
            "directions": directions,
        })
    return axes


def get_lobbying_policy_key(target: str | None = None, target_stat: str | None = None) -> str | None:
    normalized_target = _normalize_lobbying_token(target)
    if normalized_target:
        direct_target = NORMALIZED_POLICY_KEYS.get(normalized_target)
        if direct_target:
            return direct_target

        target_stat_match = NORMALIZED_TARGET_STAT_TO_POLICY_KEY.get(normalized_target)
        if target_stat_match:
            return target_stat_match

        policy_name_match = NORMALIZED_POLICY_NAME_TO_POLICY_KEY.get(normalized_target)
        if policy_name_match:
            return policy_name_match

    normalized_target_stat = _normalize_lobbying_token(target_stat)
    if normalized_target_stat:
        return NORMALIZED_TARGET_STAT_TO_POLICY_KEY.get(normalized_target_stat)

    return None


def get_lobbying_policy_definition(
    target: str | None = None,
    target_stat: str | None = None,
    government_type: str | None = None,
) -> dict | None:
    if target:
        target_key = get_lobbying_policy_key(target=target)
        if target_key:
            return _apply_government_modifiers(dict(DEFAULT_LOBBYING_POLICIES[target_key]), government_type)

    if target_stat:
        target_key = get_lobbying_policy_key(target_stat=target_stat)
        if target_key:
            return _apply_government_modifiers(dict(DEFAULT_LOBBYING_POLICIES[target_key]), government_type)

    return None


def resolve_lobbying_target(
    *,
    axis: str | None = None,
    direction: str | None = None,
    target: str | None = None,
    target_stat: str | None = None,
) -> str | None:
    if axis and direction:
        axis_key = _normalize_lobbying_token(axis)
        direction_key = _normalize_lobbying_token(direction)
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
    government_type: str | None = None,
    total_contribution: float = 0.0,
    contributor_count: int = 1,
) -> float:
    definition = get_lobbying_policy_definition(
        target=target,
        target_stat=target_stat,
        government_type=government_type,
    ) or {}
    cost_hint = max(1.0, float(definition.get("cost_hint", 250) or 250))
    contribution_ratio = max(0.0, float(total_contribution or 0) / cost_hint)
    money_bonus = min(0.62, contribution_ratio * 0.47)
    contributor_bonus = min(0.15, max(0, int(contributor_count) - 1) * 0.05)
    chance = LOBBYING_BASE_SUCCESS_CHANCE + money_bonus + contributor_bonus
    return round(min(LOBBYING_MAX_SUCCESS_CHANCE, chance), 4)


def calculate_lobbying_effect_multiplier(
    target: str | None = None,
    target_stat: str | None = None,
    government_type: str | None = None,
    total_contribution: float = 0.0,
    contributor_count: int = 1,
) -> float:
    definition = get_lobbying_policy_definition(
        target=target,
        target_stat=target_stat,
        government_type=government_type,
    ) or {}
    cost_hint = max(1.0, float(definition.get("cost_hint", 250) or 250))
    contribution_ratio = max(0.0, float(total_contribution or 0) / cost_hint)
    contributor_bonus = min(0.30, max(0, int(contributor_count) - 1) * 0.05)
    multiplier = 0.75 + (contribution_ratio * 0.75) + contributor_bonus
    return round(min(LOBBYING_MAX_EFFECT_MULTIPLIER, max(0.75, multiplier)), 4)


def resolve_lobbying_policy(
    match_id: int,
    *,
    government_type: str | None = None,
    policy_id: int | str | None = None,
    axis: str | None = None,
    direction: str | None = None,
    target: str | None = None,
    target_stat: str | None = None,
) -> tuple[Policy | None, str | None]:
    policy = None

    try:
        resolved_policy_id = int(policy_id) if policy_id is not None else 0
    except (TypeError, ValueError):
        resolved_policy_id = 0

    if resolved_policy_id > 0:
        policy = Policy.query.filter_by(id=resolved_policy_id, match_id=match_id).first()

    if policy is None:
        resolved_target = resolve_lobbying_target(
            axis=axis,
            direction=direction,
            target=target,
            target_stat=target_stat,
        )
        if not resolved_target:
            return None, "Select a valid lobbying target."

        if get_lobbying_policy_definition(target=resolved_target, government_type=government_type) is None:
            return None, "That lobbying target is not available for the current government."

        policy = ensure_match_lobbying_policy(match_id, resolved_target)

    if policy is None:
        return None, "Select a valid lobbying target."

    if get_lobbying_policy_definition(target_stat=policy.target_stat, government_type=government_type) is None:
        return None, "That lobbying target is not available for the current government."

    return policy, None


def ensure_match_lobbying_policy(match_id: int, target: str):
    target_key = get_lobbying_policy_key(target=target)
    definition = DEFAULT_LOBBYING_POLICIES.get(target_key)
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


def seed_default_lobbying_policies(match_id: int, government_type: str | None = None) -> list[Policy]:
    policies = []
    for definition in get_default_lobbying_policies(government_type=government_type):
        target = definition["target"]
        policy = ensure_match_lobbying_policy(match_id, target)
        if policy is not None:
            policies.append(policy)
    return policies
