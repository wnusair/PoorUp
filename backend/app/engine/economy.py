"""
Economy engine — all financial formulas for PoorUp.
All functions operate on plain dict game-state (loaded from Redis).
"""
import random
from typing import Any

from app.engine.taxation import build_welfare_distribution
from app.utils.settings import normalize_government_type

STANDARD_RENT_MULTIPLIERS = {0: 1.0, 1: 5.0, 2: 10.0, 3: 20.0, 4: 30.0, 5: 50.0}
STANDARD_MAX_DEVELOPMENT_LEVEL = 5
MINARCHISM_BASE_HOUSE_LEVEL = 4
MINARCHISM_EXTRA_RENT_INCREMENT = 8.0
MINARCHISM_PROGRESSIVE_COST_STEP = 0.35


def resolve_government_type(
    game_state: dict | None = None,
    econ: dict | None = None,
    settings: dict | None = None,
) -> str:
    state = game_state or {}
    economy = econ or state.get("econ") or {}
    config = settings or state.get("settings") or {}
    raw_value = (
        economy.get("gov_type")
        or economy.get("government_type")
        or config.get("government_type")
    )
    return normalize_government_type(raw_value)


def get_development_cap(
    game_state: dict | None = None,
    econ: dict | None = None,
    settings: dict | None = None,
) -> int | None:
    if resolve_government_type(game_state, econ, settings) == "minarchism":
        return None
    return STANDARD_MAX_DEVELOPMENT_LEVEL


def property_is_fully_developed(
    prop: dict,
    game_state: dict | None = None,
    econ: dict | None = None,
    settings: dict | None = None,
) -> bool:
    cap = get_development_cap(game_state, econ, settings)
    if cap is None:
        return False
    return int(prop.get("dev_level", 0) or 0) >= cap


def get_rent_multiplier(
    dev_level: int | float | None,
    game_state: dict | None = None,
    econ: dict | None = None,
    settings: dict | None = None,
) -> float:
    level = max(0, int(dev_level or 0))
    government_type = resolve_government_type(game_state, econ, settings)
    if government_type != "minarchism":
        return float(
            STANDARD_RENT_MULTIPLIERS.get(
                level,
                STANDARD_RENT_MULTIPLIERS[STANDARD_MAX_DEVELOPMENT_LEVEL],
            )
        )

    if level <= MINARCHISM_BASE_HOUSE_LEVEL:
        return float(STANDARD_RENT_MULTIPLIERS.get(level, 1.0))

    extra_houses = level - MINARCHISM_BASE_HOUSE_LEVEL
    return float(STANDARD_RENT_MULTIPLIERS[MINARCHISM_BASE_HOUSE_LEVEL]) + (
        extra_houses * MINARCHISM_EXTRA_RENT_INCREMENT
    )


def calculate_development_cost(
    base_price: int | float | None,
    target_level: int | float | None,
    game_state: dict | None = None,
    econ: dict | None = None,
    settings: dict | None = None,
) -> float:
    base_cost = round(float(base_price or 0) * 0.5, 2)
    level = max(1, int(target_level or 1))
    government_type = resolve_government_type(game_state, econ, settings)

    if government_type != "minarchism" or level <= MINARCHISM_BASE_HOUSE_LEVEL:
        return base_cost

    extra_houses = level - MINARCHISM_BASE_HOUSE_LEVEL
    progressive_factor = extra_houses * (extra_houses + 1) / 2
    cost_multiplier = 1.0 + (MINARCHISM_PROGRESSIVE_COST_STEP * progressive_factor)
    return round(base_cost * cost_multiplier, 2)


def calculate_development_refund(
    base_price: int | float | None,
    current_level: int | float | None,
    game_state: dict | None = None,
    econ: dict | None = None,
    settings: dict | None = None,
) -> float:
    level = int(current_level or 0)
    if level <= 0:
        return 0.0
    return round(
        calculate_development_cost(base_price, level, game_state, econ, settings) * 0.5,
        2,
    )


def split_development_for_repairs(
    dev_level: int | float | None,
    game_state: dict | None = None,
    econ: dict | None = None,
    settings: dict | None = None,
) -> tuple[int, int]:
    level = max(0, int(dev_level or 0))
    government_type = resolve_government_type(game_state, econ, settings)
    if government_type == "minarchism":
        return level, 0
    if level >= STANDARD_MAX_DEVELOPMENT_LEVEL:
        return 0, 1
    return level, 0


# ---------------------------------------------------------------------------
# Gini coefficient
# ---------------------------------------------------------------------------

def compute_gini_coefficient(players: list[dict]) -> float:
    balances = sorted(
        [float(p["balance"]) for p in players if not p.get("is_bankrupt", False)]
    )
    n = len(balances)
    if n == 0:
        return 0.0
    total = sum(balances)
    if total == 0:
        return 0.0
    gini_sum = sum((2 * (i + 1) - n - 1) * b for i, b in enumerate(balances))
    return gini_sum / (n * total)


# ---------------------------------------------------------------------------
# Net worth
# ---------------------------------------------------------------------------

def get_player_properties(player_id: int, game_state: dict) -> list[dict]:
    return [
        p for p in game_state.get("properties", [])
        if p.get("owner_id") == player_id
    ]


def calculate_net_worth(player: dict, game_state: dict) -> float:
    balance = float(player.get("balance", 0))
    props = get_player_properties(player["id"], game_state)
    prop_value = sum(
        float(p["current_value"]) + p.get("dev_level", 0) * 50
        for p in props
        if not p.get("is_mortgaged", False)
    )
    mortgage_debt = sum(
        float(p["base_price"]) * 0.5
        for p in props
        if p.get("is_mortgaged", False)
    )
    return round(balance + prop_value - mortgage_debt, 2)


# ---------------------------------------------------------------------------
# Monopoly helpers
# ---------------------------------------------------------------------------

def has_full_monopoly(prop: dict, game_state: dict) -> bool:
    """Return True if the owner of *prop* owns all properties in the same color group."""
    owner_id = prop.get("owner_id")
    if owner_id is None:
        return False
    group_color = prop.get("group_color")
    if not group_color:
        return False

    group_props = [
        p for p in game_state.get("properties", [])
        if p.get("group_color") == group_color and p.get("property_type") == "property"
    ]
    return all(p.get("owner_id") == owner_id for p in group_props)


def count_transits_owned_by(owner_id: int, game_state: dict) -> int:
    return sum(
        1 for p in game_state.get("properties", [])
        if p.get("owner_id") == owner_id and p.get("property_type") == "transit"
    )


def _active_social_effects(game_state: dict | None) -> list[dict]:
    social = (game_state or {}).get("social") or {}
    return [effect for effect in (social.get("active_effects") or []) if isinstance(effect, dict)]


def _territory_key_for_property(prop: dict) -> str | None:
    owner_id = prop.get("owner_id")
    region = prop.get("region")
    if owner_id is None or region is None:
        return None
    return f"{owner_id}|{region}"


def _territory_rent_control_active(prop: dict, game_state: dict | None) -> bool:
    current_round = int((game_state or {}).get("current_round", 1) or 1)
    territory_key = _territory_key_for_property(prop)
    region = prop.get("region")
    for effect in _active_social_effects(game_state):
        if effect.get("effect_type") != "territory_rent_control":
            continue
        if int(effect.get("expires_round", 0) or 0) < current_round:
            continue
        target_territory_key = effect.get("target_territory_key")
        if target_territory_key and territory_key and target_territory_key == territory_key:
            return True
        if not target_territory_key and effect.get("target_region") == region:
            return True
    return False


def _inflation_drift_is_halved(game_state: dict | None, current_round: int) -> bool:
    for effect in _active_social_effects(game_state):
        if effect.get("effect_type") != "inflation_drift_halved":
            continue
        if int(effect.get("expires_round", 0) or 0) >= current_round:
            return True
    return False


# ---------------------------------------------------------------------------
# Rent
# ---------------------------------------------------------------------------

def calculate_rent_with_dev(prop: dict, econ: dict, game_state: dict) -> float:
    """Calculate rent for a regular property."""
    base_rent = float(prop["base_price"]) * 0.1
    dev_level = prop.get("dev_level", 0)
    multiplier = get_rent_multiplier(dev_level, game_state, econ)
    inflation_adj = 1 + float(econ.get("inflation_rate", 0))

    rent = base_rent * multiplier * inflation_adj

    # Double rent if full monopoly with no development
    if dev_level == 0 and has_full_monopoly(prop, game_state):
        rent *= 2

    # Rent control can be global or limited to a specific owner-region territory.
    if econ.get("rent_control_active", False) or _territory_rent_control_active(prop, game_state):
        rent = min(rent, base_rent * multiplier * inflation_adj * 0.80)

    return round(rent, 2)


def calculate_transit_rent(owner_id: int, game_state: dict) -> float:
    owned = count_transits_owned_by(owner_id, game_state)
    return float({1: 25, 2: 50, 3: 100, 4: 200}.get(owned, 25))


# ---------------------------------------------------------------------------
# Tax helpers
# ---------------------------------------------------------------------------

TURN_TAX_RATE_SHARE = 0.05
LUXURY_TAX_RATE_SHARE = 0.50
SUPER_TAX_RATE_SHARE = 1.00


def get_effective_tax_rate(econ: dict) -> float:
    """
    Convert the live tax multiplier into a bounded cash-tax rate.

    Income, turn, luxury, and super taxes all use this effective rate so they
    remain percentage-based and cannot charge more cash than a player has.
    Property tax stays asset-based and may still push a player into debt.
    """
    tax_mult = max(0.0, float((econ or {}).get("tax_multiplier", 0.15) or 0.15))
    return tax_mult / (1.0 + tax_mult)


def _apply_cash_percentage_tax(player: dict, rate: float) -> tuple[float, float]:
    raw_balance = float(player.get("balance", 0) or 0)
    taxable_cash = max(0.0, raw_balance)
    safe_rate = max(0.0, min(1.0, float(rate or 0)))
    amount = round(min(taxable_cash, taxable_cash * safe_rate), 2)
    new_balance = round(raw_balance - amount, 2)
    return amount, new_balance

def apply_income_tax(player: dict, econ: dict, settings: dict) -> tuple[float, float]:
    """
    Deduct income tax from a player's current cash.
    Returns (amount_paid, new_balance).
    """
    return _apply_cash_percentage_tax(player, get_effective_tax_rate(econ))


def apply_property_tax(player: dict, props: list[dict], econ: dict) -> tuple[float, float]:
    """
    Deduct periodic property tax from player.
    Returns (total_tax, new_balance).
    """
    tax_mult = max(0.0, float(econ.get("tax_multiplier", 0.15) or 0.15))
    total = sum(
        float(p["current_value"]) * 0.01 * tax_mult
        for p in props
        if not p.get("is_mortgaged", False)
    )
    total = round(total, 2)
    new_balance = round(float(player["balance"]) - total, 2)
    return total, new_balance


def apply_per_turn_tax(player: dict, econ: dict) -> tuple[float, float]:
    """Deduct a capped percentage of current cash. Returns (amount, new_balance)."""
    return _apply_cash_percentage_tax(player, get_effective_tax_rate(econ) * TURN_TAX_RATE_SHARE)


def apply_luxury_tax(player: dict, econ: dict, free_parking_pot: float = 0.0) -> tuple[float, float, float]:
    """
    Luxury Tax (pos 39): percentage of current cash.
    Returns (amount, new_balance, updated_pot).
    """
    amount, new_balance = _apply_cash_percentage_tax(
        player,
        get_effective_tax_rate(econ) * LUXURY_TAX_RATE_SHARE,
    )
    new_pot = free_parking_pot + amount
    return amount, new_balance, new_pot


def apply_super_tax(player: dict, econ: dict, free_parking_pot: float = 0.0) -> tuple[float, float, float]:
    """
    Super Tax (pos 47): percentage of current cash.
    Returns (amount, new_balance, updated_pot).
    """
    amount, new_balance = _apply_cash_percentage_tax(
        player,
        get_effective_tax_rate(econ) * SUPER_TAX_RATE_SHARE,
    )
    new_pot = free_parking_pot + amount
    return amount, new_balance, new_pot


# ---------------------------------------------------------------------------
# Welfare
# ---------------------------------------------------------------------------

def pay_welfare(players: list[dict], econ: dict, settings: dict | None = None) -> tuple[list[dict], dict, dict]:
    """
    Pay welfare to eligible active players at start of round.
    Eligibility is governed by welfare balance cap in settings.
    If treasury can't cover all eligible players: stability -= 0.10, no payout.
    Returns (updated_players, updated_econ, distribution).
    """
    distribution = build_welfare_distribution(players, econ, settings or {})
    if not distribution.get("successful", False):
        econ = dict(econ)
        if distribution.get("reason") == "Treasury cannot cover the next welfare payment.":
            econ["stability"] = round(max(0.0, float(econ.get("stability", 0.5)) - 0.10), 4)
        return players, econ, distribution

    econ = dict(econ)
    player_amounts = {
        int(player_id): float(amount)
        for player_id, amount in (distribution.get("player_amounts") or {}).items()
    }
    total_cost = float(distribution.get("total_cost", 0))
    treasury = float(econ.get("treasury_balance", 0))
    econ["treasury_balance"] = round(treasury - total_cost, 2)
    updated = []
    for p in players:
        p = dict(p)
        welfare_amount = player_amounts.get(p["id"], 0.0)
        if welfare_amount > 0:
            p["balance"] = round(float(p["balance"]) + welfare_amount, 2)
        updated.append(p)
    distribution = dict(distribution)
    distribution["treasury_after"] = round(float(econ.get("treasury_balance", 0)), 2)
    return updated, econ, distribution


# ---------------------------------------------------------------------------
# Economy drift (per turn)
# ---------------------------------------------------------------------------

def drift_economy(
    econ: dict,
    players: list[dict],
    current_round: int,
    settings: dict,
    game_state: dict | None = None,
) -> dict:
    """
    Apply one tick of economic drift. Returns updated econ dict.
    """
    econ = dict(econ)
    gov_type = econ.get("gov_type", "liberal_democracy")

    # Inflation drift is softened temporarily when anti-inflation protest relief is active.
    inflation = float(econ.get("inflation_rate", 0.03))
    inflation_drift_span = 0.0025 if _inflation_drift_is_halved(game_state, current_round) else 0.005
    inflation += random.uniform(-inflation_drift_span, inflation_drift_span)
    inflation = round(max(0.005, min(0.25, inflation)), 4)
    econ["inflation_rate"] = inflation

    # Interest rate drift ±0.003, clamped [0.01, 0.20]
    interest = float(econ.get("interest_rate", 0.06))
    interest += random.uniform(-0.003, 0.003)
    interest = round(max(0.01, min(0.20, interest)), 4)
    econ["interest_rate"] = interest

    # Stability drift based on gov type, Gini, welfare
    gini = compute_gini_coefficient(players)
    stability = float(econ.get("stability", 0.70))
    welfare_rate = max(0.0, min(100.0, float(econ.get("welfare_payout", 0) or 0)))

    if gov_type == "minarchism":
        stability += random.uniform(-0.01, 0.004)
    elif gov_type == "liberal_democracy":
        stability += -gini * 0.04 + (welfare_rate / 100.0) * 0.06 + random.uniform(-0.018, 0.015)
    elif gov_type == "social_democracy":
        stability += -gini * 0.025 + (welfare_rate / 100.0) * 0.08 + random.uniform(-0.015, 0.015)

    econ["stability"] = round(max(0.0, min(1.0, stability)), 4)

    # Welfare drift (never under minarchism)
    if gov_type != "minarchism":
        welfare_rate += random.uniform(-3, 3)
        welfare_rate = round(max(0.0, min(100.0, welfare_rate)), 2)
        econ["welfare_payout"] = welfare_rate

    # Approval rating updates per gov type handled in game_loop
    return econ


# ---------------------------------------------------------------------------
# Hyper-inflation
# ---------------------------------------------------------------------------

def apply_hyper_inflation(econ: dict, properties: list[dict], current_round: int, settings: dict) -> tuple[dict, list[dict]]:
    """
    Apply hyper-inflation boost when current_round >= trigger_round.
    Modifies econ rates and property values.
    Returns (updated_econ, updated_properties).
    """
    trigger_round = settings.get("hyper_inflation_round", 50)
    if current_round < trigger_round:
        return econ, properties

    econ = dict(econ)
    rounds_past = current_round - trigger_round
    inflation_boost = 0.02 * rounds_past
    econ["inflation_rate"] = round(min(float(econ.get("inflation_rate", 0.03)) + inflation_boost, 2.0), 4)
    econ["tax_multiplier"] = round(min(float(econ.get("tax_multiplier", 0.15)) * 1.05, 2.0), 4)

    updated_props = []
    for p in properties:
        p = dict(p)
        if p.get("property_type") == "property" and p.get("current_value") is not None:
            spike = random.uniform(1.05, 1.20)
            p["current_value"] = round(float(p["current_value"]) * spike, 2)
        updated_props.append(p)

    return econ, updated_props
