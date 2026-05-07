"""Liberal Democracy economy helpers for PoorUp."""

from __future__ import annotations

import random
from typing import Any

_ENEMIES = ["Russia", "China", "Iran", "North Korea", "Venezuela", "Cuba", "Syria", "Belarus"]
_PARTY_PREFIXES_LEFT = ["People's", "Workers'", "Democratic Socialist", "Progressive", "Labor", "Green", "Social Democratic"]
_PARTY_PREFIXES_RIGHT = ["National", "Conservative", "Freedom", "America First", "Liberty", "Patriot", "Traditional Values"]
_PARTY_SUFFIXES_LEFT = ["Party", "Alliance", "Front", "Movement", "Coalition", "Bloc"]
_PARTY_SUFFIXES_RIGHT = ["Party", "Alliance", "Front", "Union", "Assembly", "Guard"]

GOVERNMENT_EVENT_TEMPLATES = [
    {
        "category": "war",
        "generate": lambda rng: {
            "title": f"War declared on {rng.choice(_ENEMIES)}",
            "description": f"The government has declared war on {rng.choice(_ENEMIES)}, citing national security threats. Defense spending surges.",
            "effects": {"inflation_rate": +0.04, "stability": -0.06, "treasury_balance": -300},
            "plain_text": "Inflation goes up. Government loses money. Things get less stable.",
        },
    },
    {
        "category": "tax_cut",
        "generate": lambda rng: {
            "title": "Conservative government cuts top income tax",
            "description": "A fiscally conservative coalition has taken power and slashed taxes for high earners, claiming it will benefit everyone through job creation.",
            "effects": {"tax_bracket_top_rate_delta": -0.02, "inflation_rate": +0.01, "market_policy_bias": +0.03},
            "plain_text": "Top tax bracket rate drops 2%. Prices go up slightly. Stock market gets a small boost.",
        },
    },
    {
        "category": "stimulus",
        "generate": lambda rng: {
            "title": "Emergency stimulus package passed",
            "description": "The government has printed and distributed money to fight a slowdown. Every player receives a small cash injection.",
            "effects": {"inflation_rate": +0.03, "welfare_payout": +5, "player_cash_bonus": 150},
            "plain_text": "Everyone gets $150. Prices go up a bit.",
        },
    },
    {
        "category": "austerity",
        "generate": lambda rng: {
            "title": "Austerity measures enacted",
            "description": "Facing a budget crisis, the government has cut welfare and public spending to reduce debt.",
            "effects": {"welfare_payout": -8, "inflation_rate": -0.02, "stability": -0.04},
            "plain_text": "Welfare payments drop. Prices fall slightly. People are unhappy.",
        },
    },
    {
        "category": "central_bank",
        "generate": lambda rng: {
            "title": "Central bank raises interest rates",
            "description": "To cool rising prices, the central bank has raised interest rates. Borrowing costs more.",
            "effects": {"interest_rate": +0.02, "inflation_rate": -0.025, "market_policy_bias": -0.03},
            "plain_text": "Loans cost more. Prices drop a little. Stocks get a small hit.",
        },
    },
    {
        "category": "rate_cut",
        "generate": lambda rng: {
            "title": "Central bank slashes interest rates",
            "description": "To stimulate the economy, the central bank has cut interest rates. Borrowing is cheap.",
            "effects": {"interest_rate": -0.015, "inflation_rate": +0.02, "market_policy_bias": +0.04},
            "plain_text": "Loans are cheaper. Prices go up slightly. Stocks get a boost.",
        },
    },
    {
        "category": "strike",
        "generate": lambda rng: {
            "title": "General strike shuts down major industries",
            "description": "Workers across the country have walked off the job demanding better pay. Companies lose income.",
            "effects": {"stability": -0.05, "inflation_rate": +0.015},
            "plain_text": "Companies earn less. Things get less stable. Prices nudge up.",
        },
    },
    {
        "category": "boom",
        "generate": lambda rng: {
            "title": "Tech boom drives economic growth",
            "description": "A wave of innovation has boosted productivity and investor confidence across all sectors.",
            "effects": {"market_policy_bias": +0.05, "stability": +0.04},
            "plain_text": "Stocks go up. Things get more stable.",
        },
    },
    {
        "category": "crash",
        "generate": lambda rng: {
            "title": "Financial crash rocks the markets",
            "description": "A chain of bad bets and overleveraged banks has triggered a market collapse. Panic selling is everywhere.",
            "effects": {"market_policy_bias": -0.07, "stability": -0.08, "inflation_rate": -0.01},
            "plain_text": "Stocks take a big hit. Things get very unstable.",
        },
    },
    {
        "category": "election",
        "generate": lambda rng: {
            "title": "Snap election called",
            "description": "Political instability has forced a snap election. The outcome is uncertain, creating market volatility.",
            "effects": {"stability": -0.03, "market_policy_bias": rng.uniform(-0.04, 0.04)},
            "plain_text": "Markets wobble. Stability drops briefly during the election.",
        },
    },
]


def _generate_party_name(spectrum: float, rng: random.Random) -> str:
    """Generate a plausible-sounding party name based on the political spectrum position."""
    if spectrum <= -0.6:
        prefix = rng.choice(["Revolutionary", "Workers'", "Socialist", "People's", "Radical Left", "Communist"])
        suffix = rng.choice(["Front", "Vanguard", "Movement", "Bloc", "Coalition"])
    elif spectrum <= -0.2:
        prefix = rng.choice(_PARTY_PREFIXES_LEFT)
        suffix = rng.choice(_PARTY_SUFFIXES_LEFT)
    elif spectrum <= 0.2:
        prefix = rng.choice(["Centrist", "Moderate", "United", "Reform", "Progressive Conservative", "National Democratic"])
        suffix = rng.choice(["Party", "Alliance", "Union", "Coalition"])
    elif spectrum <= 0.6:
        prefix = rng.choice(_PARTY_PREFIXES_RIGHT)
        suffix = rng.choice(_PARTY_SUFFIXES_RIGHT)
    else:
        prefix = rng.choice(["National", "Patriot", "America First", "Alternative for America", "New Nationalist", "Sovereign"])
        suffix = rng.choice(["Party", "Guard", "Front", "Movement", "Union"])
    return f"{prefix} {suffix}"


def update_political_parties(game_state: dict[str, Any]) -> dict[str, Any]:
    """Shift the political spectrum based on social unrest and update party names."""
    next_state = dict(game_state)
    econ = dict(next_state.get("econ") or {})
    social = next_state.get("social") or {}
    politics = dict(econ.get("politics") or {})
    spectrum = _clamp(float(politics.get("spectrum", 0.0) or 0.0), -1.0, 1.0)

    stability = float(econ.get("stability", 0.7) or 0.7)
    protests = int(social.get("total_incidents", {}).get("protest", 0) or 0) if isinstance(social.get("total_incidents"), dict) else 0
    strikes = int(social.get("total_incidents", {}).get("strike", 0) or 0) if isinstance(social.get("total_incidents"), dict) else 0
    revolutions = int(social.get("total_incidents", {}).get("revolution", 0) or 0) if isinstance(social.get("total_incidents"), dict) else 0

    unrest_score = protests * 0.01 + strikes * 0.03 + revolutions * 0.08
    stability_effect = (stability - 0.5) * 0.04

    if unrest_score > 0.04:
        drift = -(unrest_score * 1.2 + stability_effect)
    elif unrest_score < 0.01 and stability > 0.75:
        drift = 0.02 + stability_effect
    else:
        drift = -unrest_score + stability_effect

    new_spectrum = _clamp(spectrum + drift + random.uniform(-0.02, 0.02), -1.0, 1.0)

    rng = random.Random(int(new_spectrum * 1000) + int(econ.get("round_number", 1) or 1))
    governing_party = _generate_party_name(new_spectrum, rng)
    opposition_party = _generate_party_name(-new_spectrum * 0.6, rng)

    if abs(new_spectrum) > 0.65:
        fringe_party = _generate_party_name(-new_spectrum, rng)
    else:
        fringe_party = None

    politics["spectrum"] = round(new_spectrum, 4)
    politics["governing_party"] = governing_party
    politics["opposition_party"] = opposition_party
    politics["fringe_party"] = fringe_party
    politics["label"] = (
        "Far Left" if new_spectrum <= -0.65
        else "Centre-Left" if new_spectrum <= -0.2
        else "Centre" if abs(new_spectrum) <= 0.2
        else "Centre-Right" if new_spectrum <= 0.65
        else "Far Right"
    )
    econ["politics"] = politics
    next_state["econ"] = econ
    return next_state


def generate_government_event(rng: random.Random | None = None) -> dict[str, Any]:
    rng = rng or random.Random()
    template = rng.choice(GOVERNMENT_EVENT_TEMPLATES)
    return template["generate"](rng)


def apply_government_event(game_state: dict[str, Any], event: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    next_state = dict(game_state)
    econ = dict(next_state.get("econ") or {})
    effects = event.get("effects") or {}

    for key, delta in effects.items():
        if key == "player_cash_bonus":
            updated_players = []
            for player in next_state.get("players", []):
                if not player.get("is_bankrupt"):
                    updated_players.append({**dict(player), "balance": round(float(player.get("balance", 0) or 0) + float(delta or 0), 2)})
                else:
                    updated_players.append(player)
            next_state["players"] = updated_players
        elif key == "tax_bracket_top_rate_delta":
            # Directly adjust the top bracket rate
            next_econ_temp = ensure_liberal_democracy_econ(econ)
            tax_brackets = _default_tax_brackets(next_econ_temp.get("tax_brackets"))
            brackets = list(tax_brackets.get("brackets") or [])
            if brackets:
                top = dict(brackets[-1])
                top["rate"] = round(_clamp(float(top.get("rate", 0) or 0) + float(delta or 0), 0.0, 0.35), 4)
                brackets[-1] = top
                tax_brackets["brackets"] = brackets
                tax_brackets["last_adjustment"] = f"National event: {top['label']} rate changed to {top['rate'] * 100:.1f}%."
                next_econ_temp["tax_brackets"] = tax_brackets
                econ = _sync_legacy_summary_fields(next_econ_temp)
        elif key in econ:
            current = float(econ.get(key, 0) or 0)
            econ[key] = round(current + float(delta or 0), 4)
        else:
            econ[key] = round(float(delta or 0), 4)

    next_state["econ"] = econ
    next_state["last_government_event"] = event
    return next_state, event


AIRPORT_ABBREVIATIONS = {
    "Mumbai Airport": "BOM",
    "Dubai Airport": "DXB",
    "London Heathrow": "LHR",
    "JFK Airport": "JFK",
}

REGION_OVERRIDES = {
    "#06B6D4": "Oceania",
    "#16A34A": "Americas",
}

CORPORATION_NAME_POOL = [
    ("Atlas Capital", "ATLC", "#f97316"),
    ("Northstar Equity", "NSEQ", "#8b5cf6"),
    ("Transit Horizon", "TRNH", "#06b6d4"),
    ("Cinder & Co", "CNDR", "#ef4444"),
    ("Harbor Growth", "HGRW", "#10b981"),
    ("Aurora Holdings", "AUHO", "#f59e0b"),
    ("Vantage Realty", "VNTR", "#ec4899"),
    ("Meridian Trust", "MRDT", "#3b82f6"),
]

CRYPTO_DEFAULTS = {
    "BTC": {
        "name": "Bitcoin",
        "kind": "crypto",
        "price": 82.0,
        "volatility": 0.14,
    },
    "ETH": {
        "name": "Ethereum",
        "kind": "crypto",
        "price": 56.0,
        "volatility": 0.18,
    },
}

DEFAULT_TAX_BRACKETS = (
    {"label": "Tier 1", "min_net_worth": 0, "max_net_worth": 1999, "rate": 0.00},
    {"label": "Tier 2", "min_net_worth": 2000, "max_net_worth": 3999, "rate": 0.04},
    {"label": "Tier 3", "min_net_worth": 4000, "max_net_worth": 6999, "rate": 0.07},
    {"label": "Tier 4", "min_net_worth": 7000, "max_net_worth": 9999, "rate": 0.10},
    {"label": "Tier 5", "min_net_worth": 10000, "max_net_worth": None, "rate": 0.13},
)

SALARY_BANDS = (180.0, 240.0, 320.0, 420.0)
TOTAL_CORPORATE_SHARES = 1000
MAX_MARKET_HISTORY_POINTS = 24


def _round(value: float | int | None, digits: int = 2) -> float:
    return round(float(value or 0), digits)


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, float(value)))


def _history_entry(round_number: int, price: float, change: float = 0.0) -> dict[str, Any]:
    return {
        "round": max(1, int(round_number or 1)),
        "price": _round(price, 2),
        "change": round(float(change or 0), 4),
    }


def _append_price_history(asset: dict[str, Any], round_number: int, change: float | None = None) -> dict[str, Any]:
    next_asset = dict(asset or {})
    history = [dict(entry) for entry in (next_asset.get("history") or []) if isinstance(entry, dict)]
    price = _round(next_asset.get("price", 0), 2)
    change_value = float(change if change is not None else next_asset.get("price_change_last_round", 0) or 0)
    if history and int(history[-1].get("round", 0) or 0) == int(round_number or 1):
        history[-1] = _history_entry(round_number, price, change_value)
    else:
        history.append(_history_entry(round_number, price, change_value))
    next_asset["history"] = history[-MAX_MARKET_HISTORY_POINTS:]
    return next_asset


def _append_market_history(market: dict[str, Any], round_number: int) -> dict[str, Any]:
    next_market = dict(market or {})
    assets = dict(next_market.get("assets") or {})
    asset_prices = [
        float((asset or {}).get("price", 0) or 0)
        for asset in assets.values()
        if float((asset or {}).get("price", 0) or 0) > 0
    ]
    average_price = sum(asset_prices) / max(1, len(asset_prices)) if asset_prices else 0.0
    history = [dict(entry) for entry in (next_market.get("history") or []) if isinstance(entry, dict)]
    entry = {
        "round": max(1, int(round_number or 1)),
        "sentiment": _round(next_market.get("sentiment", 0), 2),
        "average_price": _round(average_price, 2),
    }
    if history and int(history[-1].get("round", 0) or 0) == entry["round"]:
        history[-1] = entry
    else:
        history.append(entry)
    next_market["history"] = history[-MAX_MARKET_HISTORY_POINTS:]
    return next_market


def _market_policy_pressure(econ: dict[str, Any]) -> float:
    inflation = float(econ.get("inflation_rate", 0.03) or 0.03)
    interest = float(econ.get("interest_rate", 0.06) or 0.06)
    welfare = float(econ.get("welfare_payout", 18.0) or 18.0)
    stability = float(econ.get("stability", 0.70) or 0.70)
    treasury = float(econ.get("treasury_balance", 0) or 0)
    active_count = max(1, int(econ.get("active_player_count", 4) or 4))
    treasury_floor = active_count * 220.0

    pressure = 0.0
    pressure -= max(0.0, inflation - 0.045) * 1.65
    pressure -= max(0.0, interest - 0.075) * 0.85
    pressure -= max(0.0, welfare - 30.0) * 0.0009
    pressure += max(0.0, stability - 0.62) * 0.045
    pressure -= max(0.0, 1.0 - (treasury / treasury_floor)) * 0.026
    pressure += max(-0.035, min(0.035, float(econ.get("market_policy_bias", 0) or 0)))
    return _clamp(pressure, -0.075, 0.065)


def _update_market_cycle(market: dict[str, Any], econ: dict[str, Any], current_round: int) -> tuple[dict[str, Any], float]:
    next_market = dict(market or {})
    cycle = dict(next_market.get("cycle") or {})
    phase = str(cycle.get("phase") or "growth")
    rounds_remaining = int(cycle.get("rounds_remaining", 0) or 0)
    policy_pressure = _market_policy_pressure(econ)
    sentiment = float(next_market.get("sentiment", 72.0) or 72.0)

    if rounds_remaining <= 0 or policy_pressure <= -0.04 or policy_pressure >= 0.035:
        if policy_pressure <= -0.025 or sentiment >= 86.0:
            phase = "decay"
            rounds_remaining = 2 + (int(current_round or 1) % 2)
        elif policy_pressure >= 0.02 or sentiment <= 55.0:
            phase = "growth"
            rounds_remaining = 2 + (int(current_round or 1) % 3)
        else:
            phase = "growth" if phase == "decay" else "decay"
            rounds_remaining = 2

    cycle_bias = 0.018 if phase == "growth" else -0.022
    cycle["phase"] = phase
    cycle["rounds_remaining"] = max(0, rounds_remaining - 1)
    cycle["policy_pressure"] = round(policy_pressure, 4)
    cycle["bias"] = round(cycle_bias + policy_pressure, 4)
    next_market["cycle"] = cycle
    return next_market, cycle["bias"]


def liberal_democracy_corporation_count(player_count: int) -> int:
    seat_count = max(2, int(player_count or 0))
    if seat_count <= 3:
        return 3
    if seat_count <= 5:
        return 4
    if seat_count <= 7:
        return 5
    return 6


def normalize_property_region_name(prop: dict[str, Any]) -> str | None:
    region = prop.get("region")
    if prop.get("property_type") == "transit":
        return "Transit"
    override = REGION_OVERRIDES.get(str(prop.get("group_color") or ""))
    if override:
        return override
    return str(region) if region else None


def normalize_property_runtime_fields(properties: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for prop in properties:
        next_prop = dict(prop)
        next_prop["name"] = AIRPORT_ABBREVIATIONS.get(str(next_prop.get("name") or ""), next_prop.get("name"))
        next_prop["region"] = normalize_property_region_name(next_prop)
        next_prop["corporate_owner_id"] = next_prop.get("corporate_owner_id")
        next_prop["corporate_listing_price"] = _round(next_prop.get("corporate_listing_price", 0), 2) if next_prop.get("corporate_listing_price") is not None else None
        next_prop["corporate_rent"] = _round(next_prop.get("corporate_rent", 0), 2) if next_prop.get("corporate_rent") is not None else None
        normalized.append(next_prop)
    return normalized


def _default_tax_brackets(existing: dict[str, Any] | None = None) -> dict[str, Any]:
    existing = dict(existing or {})
    brackets = []
    for index, definition in enumerate(existing.get("brackets") or DEFAULT_TAX_BRACKETS):
        template = DEFAULT_TAX_BRACKETS[min(index, len(DEFAULT_TAX_BRACKETS) - 1)]
        entry = {
            "label": definition.get("label") or template["label"],
            "min_net_worth": int(definition.get("min_net_worth", template["min_net_worth"]) or 0),
            "max_net_worth": definition.get("max_net_worth", template["max_net_worth"]),
            "rate": round(float(definition.get("rate", template["rate"]) or template["rate"]), 4),
        }
        if entry["max_net_worth"] is not None:
            entry["max_net_worth"] = int(entry["max_net_worth"])
        brackets.append(entry)
    return {
        "brackets": brackets,
        "next_boundary_index": int(existing.get("next_boundary_index", 1) or 1),
        "next_rate_index": int(existing.get("next_rate_index", 0) or 0),
        "last_adjustment": existing.get("last_adjustment"),
    }


def _sync_legacy_summary_fields(econ: dict[str, Any]) -> dict[str, Any]:
    next_econ = dict(econ)
    market = dict(next_econ.get("market") or {})
    corporations = dict((next_econ.get("corporations") or {}).get("by_id") or {})
    market_assets = dict(market.get("assets") or {})
    average_dividend_yield = 0.0
    if corporations:
        average_dividend_yield = sum(
            float(corp.get("dividend_yield", 0) or 0)
            for corp in corporations.values()
        ) / max(1, len(corporations))
    next_econ["market_confidence"] = round(float(market.get("sentiment", next_econ.get("market_confidence", 72.0)) or 72.0), 2)
    next_econ["capital_yield_rate"] = round(max(0.0, average_dividend_yield), 4)
    next_econ["capital_yield_cap_per_player"] = 0.0
    next_econ["capital_yield_reserve_floor"] = 0.0
    next_econ["capital_yield_last_round"] = round(float(market.get("last_dividends_paid", 0) or 0), 2)
    next_econ["private_equity_bonus_multiplier"] = 1.0
    market["assets"] = market_assets
    next_econ["market"] = market
    return next_econ


def ensure_liberal_democracy_econ(econ: dict[str, Any] | None, settings: dict[str, Any] | None = None) -> dict[str, Any]:
    settings = dict(settings or {})
    next_econ = dict(econ or {})
    market = dict(next_econ.get("market") or {})
    market.setdefault("assets", {})
    market["sentiment"] = round(float(market.get("sentiment", next_econ.get("market_confidence", 72.0)) or 72.0), 2)
    market["volatility_index"] = round(float(market.get("volatility_index", 0.18) or 0.18), 4)
    market["last_round_summary"] = list(market.get("last_round_summary") or [])
    market["last_dividends_paid"] = _round(market.get("last_dividends_paid", 0), 2)
    market["cycle"] = {
        **{"phase": "growth", "rounds_remaining": 2, "policy_pressure": 0.0, "bias": 0.018},
        **dict(market.get("cycle") or {}),
    }
    market["history"] = [dict(entry) for entry in (market.get("history") or []) if isinstance(entry, dict)][-MAX_MARKET_HISTORY_POINTS:]
    current_round = int(next_econ.get("round_number", 1) or next_econ.get("current_round", 1) or 1)
    market["assets"] = {
        str(asset_key): _append_price_history(dict(asset or {}), current_round)
        for asset_key, asset in (market.get("assets") or {}).items()
    }

    corporations = dict(next_econ.get("corporations") or {})
    corporations["active_ids"] = list(corporations.get("active_ids") or [])
    corporations["by_id"] = {
        str(corp_id): dict(value or {})
        for corp_id, value in (corporations.get("by_id") or {}).items()
    }

    bank = dict(next_econ.get("bank") or {})
    bank["players"] = {
        str(player_id): {
            "savings_balance": _round((entry or {}).get("savings_balance", 0), 2),
            "loan_principal": _round((entry or {}).get("loan_principal", 0), 2),
            "loan_interest_rate": round(float((entry or {}).get("loan_interest_rate", 0) or 0), 4),
            "missed_payments": max(0, int((entry or {}).get("missed_payments", 0) or 0)),
            "account_open": bool((entry or {}).get("account_open", True)),
        }
        for player_id, entry in (bank.get("players") or {}).items()
    }
    bank["savings_interest_rate"] = round(
        max(0.01, float(next_econ.get("interest_rate", 0.06) or 0.06) * 0.5),
        4,
    )
    bank["loan_payment_ratio"] = round(float(bank.get("loan_payment_ratio", 0.10) or 0.10), 4)
    bank["default_after_missed_payments"] = max(1, int(bank.get("default_after_missed_payments", 2) or 2))

    jobs = dict(next_econ.get("jobs") or {})
    jobs["players"] = {
        str(player_id): {
            "employment_status": str((entry or {}).get("employment_status", "employed") or "employed"),
            "employer_id": (entry or {}).get("employer_id"),
            "employer_name": (entry or {}).get("employer_name"),
            "salary": _round((entry or {}).get("salary", 0), 2),
            "salary_band": _round((entry or {}).get("salary_band", 0), 2),
            "unemployment_rounds_remaining": max(0, int((entry or {}).get("unemployment_rounds_remaining", 0) or 0)),
            "event_history": list((entry or {}).get("event_history") or []),
        }
        for player_id, entry in (jobs.get("players") or {}).items()
    }
    jobs["salary_bands"] = list(jobs.get("salary_bands") or SALARY_BANDS)

    tax_brackets = _default_tax_brackets(next_econ.get("tax_brackets"))

    next_econ["market"] = market
    next_econ["corporations"] = corporations
    next_econ["bank"] = bank
    next_econ["jobs"] = jobs
    next_econ["tax_brackets"] = tax_brackets
    return _sync_legacy_summary_fields(next_econ)


def _player_portfolio(player: dict[str, Any]) -> dict[str, Any]:
    portfolio = dict(player.get("portfolio") or {})
    portfolio["stocks"] = {
        str(asset_key): int(quantity or 0)
        for asset_key, quantity in (portfolio.get("stocks") or {}).items()
        if int(quantity or 0) > 0
    }
    portfolio["crypto"] = {
        str(asset_key): float(quantity or 0)
        for asset_key, quantity in (portfolio.get("crypto") or {}).items()
        if float(quantity or 0) > 0
    }
    portfolio["recent_orders"] = list(portfolio.get("recent_orders") or [])[-12:]
    return portfolio


def _corporation_symbol(index: int) -> str:
    entry = CORPORATION_NAME_POOL[index % len(CORPORATION_NAME_POOL)]
    return entry[1] if isinstance(entry, tuple) else f"CORP{index + 1}"


def _corporation_color(index: int) -> str:
    entry = CORPORATION_NAME_POOL[index % len(CORPORATION_NAME_POOL)]
    return entry[2] if isinstance(entry, tuple) and len(entry) > 2 else "#06b6d4"


def _base_stock_price(property_count: int, rng: random.Random) -> float:
    return round(max(14.0, 18.0 + (property_count * 1.8) + rng.uniform(-4.0, 6.0)), 2)


def _initial_corporation_payload(corp_id: str, name: str, symbol: str, color_hex: str, property_ids: list[int], rng: random.Random) -> dict[str, Any]:
    stock_price = _base_stock_price(len(property_ids), rng)
    pricing_modifier = round(_clamp(0.92 + rng.uniform(-0.08, 0.22), 0.75, 1.35), 4)
    return {
        "id": corp_id,
        "name": name,
        "stock_symbol": symbol,
        "asset_key": symbol,
        "color_hex": color_hex,
        "property_ids": sorted(property_ids),
        "pricing_modifier": pricing_modifier,
        "stock_price": stock_price,
        "cash_reserve": round(max(350.0, len(property_ids) * 120.0), 2),
        "shares_outstanding": TOTAL_CORPORATE_SHARES,
        "rent_income_last_round": 0.0,
        "salary_cost_last_round": 0.0,
        "profit_last_round": 0.0,
        "dividend_per_share_last_round": 0.0,
        "dividend_yield": 0.0,
        "price_change_last_round": 0.0,
    }


def _calculate_corporate_rent(prop: dict[str, Any], corporation: dict[str, Any]) -> float:
    base_price = float(prop.get("base_price", 0) or 0)
    pricing_modifier = float(corporation.get("pricing_modifier", 1.0) or 1.0)
    if prop.get("property_type") == "transit":
        base_rent = max(25.0, base_price * 0.18)
    else:
        development_level = max(0, int(prop.get("dev_level", 0) or 0))
        base_rent = max(18.0, (base_price * 0.16) + (development_level * base_price * 0.035))
    return round(base_rent * pricing_modifier, 2)


def _calculate_corporate_listing_price(prop: dict[str, Any], corporation: dict[str, Any]) -> float:
    base_price = float(prop.get("base_price", 0) or 0)
    pricing_modifier = float(corporation.get("pricing_modifier", 1.0) or 1.0)
    development_level = max(0, int(prop.get("dev_level", 0) or 0))
    return round((base_price * 2.5 * pricing_modifier) + (development_level * base_price * 0.25), 2)


def refresh_corporate_property_metrics(
    properties: list[dict[str, Any]],
    econ: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    next_econ = ensure_liberal_democracy_econ(econ)
    corporations = dict((next_econ.get("corporations") or {}).get("by_id") or {})
    updated_properties = []
    for prop in normalize_property_runtime_fields(properties):
        next_prop = dict(prop)
        corporate_owner_id = next_prop.get("corporate_owner_id")
        corporation = corporations.get(str(corporate_owner_id)) if corporate_owner_id else None
        if corporation is not None:
            next_prop["corporate_rent"] = _calculate_corporate_rent(next_prop, corporation)
            next_prop["corporate_listing_price"] = _calculate_corporate_listing_price(next_prop, corporation)
            next_prop["current_value"] = round(
                max(
                    float(next_prop.get("base_price", 0) or 0),
                    float(next_prop.get("base_price", 0) or 0) * float(corporation.get("pricing_modifier", 1.0) or 1.0),
                ),
                2,
            )
        else:
            next_prop["corporate_owner_id"] = None
            next_prop["corporate_rent"] = None
            next_prop["corporate_listing_price"] = None
        updated_properties.append(next_prop)
    return updated_properties, _sync_legacy_summary_fields(next_econ)


def _sync_player_econ_views(players: list[dict[str, Any]], econ: dict[str, Any]) -> dict[str, Any]:
    next_econ = ensure_liberal_democracy_econ(econ)
    bank_players = {}
    job_players = {}
    for player in players:
        player_id = str(int(player.get("id") or 0))
        bank_players[player_id] = {
            "savings_balance": _round(player.get("bank_savings_balance", 0), 2),
            "loan_principal": _round(player.get("bank_loan_principal", 0), 2),
            "loan_interest_rate": round(float(player.get("bank_loan_interest_rate", 0) or 0), 4),
            "missed_payments": max(0, int(player.get("bank_missed_payments", 0) or 0)),
            "account_open": bool(player.get("bank_account_open", True)),
        }
        job_players[player_id] = {
            "employment_status": str(player.get("employment_status", "employed") or "employed"),
            "employer_id": player.get("employer_id"),
            "employer_name": player.get("employer_name"),
            "salary": _round(player.get("salary", 0), 2),
            "salary_band": _round(player.get("salary_band", 0), 2),
            "unemployment_rounds_remaining": max(0, int(player.get("unemployment_rounds_remaining", 0) or 0)),
            "event_history": list(player.get("job_event_history") or [])[-10:],
        }
    next_econ["bank"] = {**dict(next_econ.get("bank") or {}), "players": bank_players}
    next_econ["jobs"] = {**dict(next_econ.get("jobs") or {}), "players": job_players}
    return _sync_legacy_summary_fields(next_econ)


def _credit_player_balance(game_state: dict[str, Any], player_id: int, amount: float) -> tuple[dict[str, Any], dict[str, Any] | None]:
    from app.engine.debt import credit_player_with_debt_settlement

    next_state, result = credit_player_with_debt_settlement(game_state, player_id, amount)
    return next_state, result.get("player")


def _spend_player_balance(game_state: dict[str, Any], player_id: int, amount: float) -> tuple[dict[str, Any], dict[str, Any] | None]:
    from app.engine.debt import spend_player_balance

    return spend_player_balance(game_state, player_id, amount)


def setup_liberal_democracy_state(
    players: list[dict[str, Any]],
    properties: list[dict[str, Any]],
    econ: dict[str, Any],
    settings: dict[str, Any] | None = None,
    *,
    rng: random.Random | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    rng = rng or random.Random()
    next_properties = normalize_property_runtime_fields(properties)
    ownable = [dict(prop) for prop in next_properties if prop.get("property_type") in {"property", "transit"}]
    shuffled_properties = [dict(prop) for prop in ownable]
    rng.shuffle(shuffled_properties)

    next_players: list[dict[str, Any]] = []
    initial_player_property_ids = set()
    for index, player in enumerate(players):
        next_player = dict(player)
        next_player["balance"] = round(rng.uniform(1000.0, 2000.0), 2)
        next_player["portfolio"] = {"stocks": {}, "crypto": {}, "recent_orders": []}
        next_player["bank_account_open"] = True
        next_player["bank_savings_balance"] = 0.0
        next_player["bank_loan_principal"] = 0.0
        next_player["bank_loan_interest_rate"] = 0.0
        next_player["bank_missed_payments"] = 0
        next_player["employment_status"] = "employed"
        next_player["salary_band"] = float(SALARY_BANDS[index % len(SALARY_BANDS)])
        next_player["salary"] = float(next_player["salary_band"])
        next_player["job_event_history"] = []
        next_player["unemployment_rounds_remaining"] = 0
        if shuffled_properties:
            starting_property = shuffled_properties.pop(0)
            initial_player_property_ids.add(int(starting_property.get("id") or 0))
            next_player["starting_property_id"] = int(starting_property.get("id") or 0)
        else:
            next_player["starting_property_id"] = None
        next_players.append(next_player)

    corporation_count = liberal_democracy_corporation_count(len(next_players))
    corporation_ids = [f"corp_{index + 1}" for index in range(corporation_count)]
    corporation_properties: dict[str, list[int]] = {corp_id: [] for corp_id in corporation_ids}
    remaining_property_ids = [
        int(prop.get("id") or 0)
        for prop in shuffled_properties
        if int(prop.get("id") or 0) not in initial_player_property_ids
    ]
    for index, property_id in enumerate(remaining_property_ids):
        corporation_properties[corporation_ids[index % len(corporation_ids)]].append(property_id)

    corporations = {}
    market_assets = dict((ensure_liberal_democracy_econ(econ).get("market") or {}).get("assets") or {})
    for index, corp_id in enumerate(corporation_ids):
        symbol = _corporation_symbol(index)
        color_hex = _corporation_color(index)
        pool_entry = CORPORATION_NAME_POOL[index % len(CORPORATION_NAME_POOL)]
        corp_name = pool_entry[0] if isinstance(pool_entry, tuple) else pool_entry
        corporation = _initial_corporation_payload(
            corp_id,
            corp_name,
            symbol,
            color_hex,
            corporation_properties.get(corp_id, []),
            rng,
        )
        corporations[corp_id] = corporation
        market_assets[symbol] = {
            "asset_key": symbol,
            "kind": "stock",
            "label": corporation["name"],
            "price": corporation["stock_price"],
            "volatility": round(0.05 + (index * 0.01), 4),
            "corporation_id": corp_id,
            "price_change_last_round": 0.0,
        }

    for asset_key, defaults in CRYPTO_DEFAULTS.items():
        current = dict(market_assets.get(asset_key) or {})
        market_assets[asset_key] = {
            "asset_key": asset_key,
            "kind": defaults["kind"],
            "label": defaults["name"],
            "price": round(float(current.get("price", defaults["price"]) or defaults["price"]), 2),
            "volatility": round(float(current.get("volatility", defaults["volatility"]) or defaults["volatility"]), 4),
            "price_change_last_round": round(float(current.get("price_change_last_round", 0) or 0), 4),
        }

    updated_properties = []
    player_by_starting_property = {
        int(player.get("starting_property_id") or 0): int(player.get("id") or 0)
        for player in next_players
        if player.get("starting_property_id") is not None
    }
    for prop in next_properties:
        next_prop = dict(prop)
        prop_id = int(next_prop.get("id") or 0)
        if prop_id in player_by_starting_property:
            next_prop["owner_id"] = player_by_starting_property[prop_id]
            next_prop["corporate_owner_id"] = None
        else:
            assigned_corp_id = next(
                (corp_id for corp_id, property_ids in corporation_properties.items() if prop_id in property_ids),
                None,
            )
            next_prop["owner_id"] = None
            next_prop["corporate_owner_id"] = assigned_corp_id
        updated_properties.append(next_prop)

    next_econ = ensure_liberal_democracy_econ(econ, settings)
    next_econ["market"] = {
        **dict(next_econ.get("market") or {}),
        "assets": market_assets,
        "sentiment": round(float((next_econ.get("market") or {}).get("sentiment", rng.uniform(66.0, 82.0)) or rng.uniform(66.0, 82.0)), 2),
        "volatility_index": round(float((next_econ.get("market") or {}).get("volatility_index", 0.18) or 0.18), 4),
        "last_round_summary": [],
        "last_dividends_paid": 0.0,
    }
    next_econ["market"]["assets"] = {
        asset_key: _append_price_history(asset, 1, 0.0)
        for asset_key, asset in next_econ["market"]["assets"].items()
    }
    next_econ["market"] = _append_market_history(next_econ["market"], 1)
    next_econ["corporations"] = {
        "active_ids": corporation_ids,
        "by_id": corporations,
    }

    for index, player in enumerate(next_players):
        employer_id = corporation_ids[index % len(corporation_ids)] if corporation_ids else None
        employer = corporations.get(str(employer_id)) or {}
        player["employer_id"] = employer_id
        player["employer_name"] = employer.get("name")
        player["job_event_history"] = [
            f"Started the match employed by {player['employer_name']} at ${player['salary']:.2f} per round."
        ] if employer_id else []

    next_econ = _sync_player_econ_views(next_players, next_econ)
    updated_properties, next_econ = refresh_corporate_property_metrics(updated_properties, next_econ)
    return next_players, updated_properties, next_econ


def get_liberal_democracy_go_salary(game_state: dict[str, Any], player_id: int, default_go_salary: float) -> float:
    player = next(
        (entry for entry in game_state.get("players", []) if int(entry.get("id") or 0) == int(player_id)),
        None,
    )
    if player is None:
        return round(float(default_go_salary or 0), 2)
    if str(player.get("employment_status") or "") == "unemployed":
        return round(float(default_go_salary or 0) * 0.5, 2)
    return round(float(default_go_salary or 0), 2)


def _find_tax_bracket(tax_brackets: dict[str, Any], net_worth: float) -> dict[str, Any]:
    for bracket in tax_brackets.get("brackets") or []:
        minimum = float(bracket.get("min_net_worth", 0) or 0)
        maximum = bracket.get("max_net_worth")
        if net_worth < minimum:
            continue
        if maximum is None or net_worth <= float(maximum):
            return dict(bracket)
    return dict((tax_brackets.get("brackets") or [DEFAULT_TAX_BRACKETS[-1]])[-1])


def portfolio_market_value(player: dict[str, Any], econ: dict[str, Any]) -> float:
    assets = dict(((econ.get("market") or {}).get("assets") or {}))
    portfolio = _player_portfolio(player)
    total_value = 0.0
    for asset_key, quantity in portfolio.get("stocks", {}).items():
        total_value += float(quantity or 0) * float((assets.get(asset_key) or {}).get("price", 0) or 0)
    for asset_key, quantity in portfolio.get("crypto", {}).items():
        total_value += float(quantity or 0) * float((assets.get(asset_key) or {}).get("price", 0) or 0)
    return round(total_value, 2)


def apply_tax_bracket_policy(econ: dict[str, Any], *, mode: str) -> dict[str, Any]:
    next_econ = ensure_liberal_democracy_econ(econ)
    tax_brackets = _default_tax_brackets(next_econ.get("tax_brackets"))
    brackets = list(tax_brackets.get("brackets") or [])
    if not brackets:
        return next_econ

    if mode in {"boundary_up", "boundary_down"} and len(brackets) >= 2:
        boundary_index = max(1, min(len(brackets) - 1, int(tax_brackets.get("next_boundary_index", 1) or 1)))
        pivot = dict(brackets[boundary_index - 1])
        follower = dict(brackets[boundary_index])
        delta = 500 if mode == "boundary_up" else -500
        if pivot.get("max_net_worth") is not None:
            next_boundary = max(int(pivot["min_net_worth"]) + 500, int(pivot["max_net_worth"]) + delta)
            pivot["max_net_worth"] = next_boundary
            follower["min_net_worth"] = next_boundary + 1
            brackets[boundary_index - 1] = pivot
            brackets[boundary_index] = follower
            tax_brackets["next_boundary_index"] = 1 if boundary_index >= len(brackets) - 1 else boundary_index + 1
            tax_brackets["last_adjustment"] = f"Moved the {follower['label']} threshold by ${abs(delta)}."
    elif mode in {"rate_up", "rate_down"}:
        if mode == "rate_down":
            # Start from the top bracket (where there's room to cut) and cycle downward
            top = len(brackets) - 1
            rate_index = max(0, min(top, int(tax_brackets.get("next_rate_down_index", top) or top)))
            delta = -0.02
            next_down = rate_index - 1 if rate_index > 0 else top
            tax_brackets["next_rate_down_index"] = next_down
        else:
            # Start from the bottom bracket and cycle upward
            rate_index = max(0, min(len(brackets) - 1, int(tax_brackets.get("next_rate_up_index", 0) or 0)))
            delta = 0.02
            tax_brackets["next_rate_up_index"] = 0 if rate_index >= len(brackets) - 1 else rate_index + 1
        bracket = dict(brackets[rate_index])
        bracket["rate"] = round(_clamp(float(bracket.get("rate", 0) or 0) + delta, 0.0, 0.25), 4)
        brackets[rate_index] = bracket
        tax_brackets["last_adjustment"] = f"Changed the {bracket['label']} rate by {abs(delta) * 100:.0f} percentage points."

    tax_brackets["brackets"] = brackets
    next_econ["tax_brackets"] = tax_brackets
    return _sync_legacy_summary_fields(next_econ)


def submit_market_order(game_state: dict[str, Any], *, player_id: int, asset_key: str, side: str, quantity: float) -> tuple[dict[str, Any], dict[str, Any]]:
    next_state = dict(game_state)
    next_state["econ"] = ensure_liberal_democracy_econ(next_state.get("econ"), next_state.get("settings"))
    current_round = int(next_state.get("current_round", next_state["econ"].get("round_number", 1)) or 1)
    assets = dict(((next_state["econ"].get("market") or {}).get("assets") or {}))
    asset = dict(assets.get(asset_key) or {})
    if not asset:
        raise ValueError("That market asset does not exist.")

    quantity = float(quantity or 0)
    if quantity <= 0:
        raise ValueError("Quantity must be positive.")

    player = next((entry for entry in next_state.get("players", []) if int(entry.get("id") or 0) == int(player_id)), None)
    if player is None or player.get("is_bankrupt"):
        raise ValueError("Only active players can submit market orders.")

    updated_players = []
    updated_player = None
    price = round(float(asset.get("price", 0) or 0), 2)
    cost = round(price * quantity, 2)
    for existing in next_state.get("players", []):
        next_player = dict(existing)
        if int(next_player.get("id") or 0) == int(player_id):
            portfolio = _player_portfolio(next_player)
            key = "crypto" if str(asset.get("kind") or "") == "crypto" else "stocks"
            holdings = dict(portfolio.get(key) or {})
            if side == "buy":
                if float(next_player.get("balance", 0) or 0) < cost:
                    raise ValueError("Insufficient cash for that market order.")
                next_player["balance"] = round(float(next_player.get("balance", 0) or 0) - cost, 2)
                if key == "stocks":
                    holdings[asset_key] = int(holdings.get(asset_key, 0) or 0) + int(quantity)
                else:
                    holdings[asset_key] = round(float(holdings.get(asset_key, 0) or 0) + quantity, 4)
            elif side == "sell":
                available = float(holdings.get(asset_key, 0) or 0)
                if available < quantity:
                    raise ValueError("That player does not own enough of the selected asset.")
                if key == "stocks":
                    next_amount = int(available - int(quantity))
                    if next_amount > 0:
                        holdings[asset_key] = next_amount
                    else:
                        holdings.pop(asset_key, None)
                else:
                    next_amount = round(available - quantity, 4)
                    if next_amount > 0:
                        holdings[asset_key] = next_amount
                    else:
                        holdings.pop(asset_key, None)
                next_player["balance"] = round(float(next_player.get("balance", 0) or 0) + cost, 2)
            else:
                raise ValueError("Market orders must be 'buy' or 'sell'.")
            portfolio[key] = holdings
            portfolio["recent_orders"] = [
                *list(portfolio.get("recent_orders") or []),
                {"asset_key": asset_key, "side": side, "quantity": quantity, "price": price},
            ][-12:]
            next_player["portfolio"] = portfolio
            updated_player = next_player
        updated_players.append(next_player)

    price_impact = 0.004 * max(1.0, quantity)
    if side == "sell":
        price_impact *= -1
    asset["price"] = round(max(1.0, float(asset.get("price", 0) or 0) * (1.0 + price_impact)), 2)
    asset["price_change_last_round"] = round(price_impact, 4)
    asset = _append_price_history(asset, current_round, price_impact)
    assets[asset_key] = asset
    market = {**dict(next_state["econ"].get("market") or {}), "assets": assets}
    market = _append_market_history(market, current_round)
    next_state["players"] = updated_players
    next_state["econ"] = {
        **dict(next_state["econ"]),
        "market": market,
    }
    next_state["econ"] = _sync_player_econ_views(next_state["players"], next_state["econ"])
    return next_state, {
        "player_id": player_id,
        "asset_key": asset_key,
        "side": side,
        "quantity": quantity,
        "price": price,
        "player": updated_player,
    }


def deposit_bank_funds(game_state: dict[str, Any], *, player_id: int, amount: float) -> tuple[dict[str, Any], dict[str, Any]]:
    amount = round(float(amount or 0), 2)
    if amount <= 0:
        raise ValueError("Deposit amount must be positive.")
    next_state = dict(game_state)
    updated_players = []
    updated_player = None
    for player in next_state.get("players", []):
        next_player = dict(player)
        if int(next_player.get("id") or 0) == int(player_id):
            if float(next_player.get("balance", 0) or 0) < amount:
                raise ValueError("That player does not have enough cash to deposit.")
            next_player["balance"] = round(float(next_player.get("balance", 0) or 0) - amount, 2)
            next_player["bank_savings_balance"] = round(float(next_player.get("bank_savings_balance", 0) or 0) + amount, 2)
            next_player["bank_account_open"] = True
            updated_player = next_player
        updated_players.append(next_player)
    next_state["players"] = updated_players
    next_state["econ"] = _sync_player_econ_views(updated_players, next_state.get("econ") or {})
    return next_state, {"player_id": player_id, "amount": amount, "player": updated_player}


def withdraw_bank_funds(game_state: dict[str, Any], *, player_id: int, amount: float) -> tuple[dict[str, Any], dict[str, Any]]:
    amount = round(float(amount or 0), 2)
    if amount <= 0:
        raise ValueError("Withdrawal amount must be positive.")
    next_state = dict(game_state)
    updated_players = []
    updated_player = None
    for player in next_state.get("players", []):
        next_player = dict(player)
        if int(next_player.get("id") or 0) == int(player_id):
            if float(next_player.get("bank_savings_balance", 0) or 0) < amount:
                raise ValueError("That player does not have enough in savings.")
            next_player["bank_savings_balance"] = round(float(next_player.get("bank_savings_balance", 0) or 0) - amount, 2)
            next_player["balance"] = round(float(next_player.get("balance", 0) or 0) + amount, 2)
            updated_player = next_player
        updated_players.append(next_player)
    next_state["players"] = updated_players
    next_state["econ"] = _sync_player_econ_views(updated_players, next_state.get("econ") or {})
    return next_state, {"player_id": player_id, "amount": amount, "player": updated_player}


def request_bank_loan(game_state: dict[str, Any], *, player_id: int, amount: float) -> tuple[dict[str, Any], dict[str, Any]]:
    amount = round(float(amount or 0), 2)
    if amount <= 0:
        raise ValueError("Loan amount must be positive.")
    next_state = dict(game_state)
    interest_rate = float((next_state.get("econ") or {}).get("interest_rate", 0.06) or 0.06)
    risk_spread = 0.03
    updated_players = []
    updated_player = None
    for player in next_state.get("players", []):
        next_player = dict(player)
        if int(next_player.get("id") or 0) == int(player_id):
            current_principal = float(next_player.get("bank_loan_principal", 0) or 0)
            max_loan = max(300.0, float(next_player.get("balance", 0) or 0) * 1.5 + float(next_player.get("bank_savings_balance", 0) or 0))
            if current_principal + amount > max_loan:
                raise ValueError("The bank will not extend that much leverage right now.")
            next_player["bank_loan_principal"] = round(current_principal + amount, 2)
            next_player["bank_loan_interest_rate"] = round(min(0.24, interest_rate + risk_spread), 4)
            next_player["bank_missed_payments"] = 0
            next_player["balance"] = round(float(next_player.get("balance", 0) or 0) + amount, 2)
            next_player["bank_account_open"] = True
            updated_player = next_player
        updated_players.append(next_player)
    next_state["players"] = updated_players
    next_state["econ"] = _sync_player_econ_views(updated_players, next_state.get("econ") or {})
    return next_state, {"player_id": player_id, "amount": amount, "player": updated_player}


def repay_bank_loan(game_state: dict[str, Any], *, player_id: int, amount: float) -> tuple[dict[str, Any], dict[str, Any]]:
    amount = round(float(amount or 0), 2)
    if amount <= 0:
        raise ValueError("Repayment amount must be positive.")
    next_state = dict(game_state)
    updated_players = []
    updated_player = None
    for player in next_state.get("players", []):
        next_player = dict(player)
        if int(next_player.get("id") or 0) == int(player_id):
            if float(next_player.get("balance", 0) or 0) < amount:
                raise ValueError("That player does not have enough cash to make the payment.")
            principal = float(next_player.get("bank_loan_principal", 0) or 0)
            if principal <= 0:
                raise ValueError("That player does not have an active bank loan.")
            payment = min(principal, amount)
            next_player["balance"] = round(float(next_player.get("balance", 0) or 0) - payment, 2)
            next_player["bank_loan_principal"] = round(max(0.0, principal - payment), 2)
            next_player["bank_missed_payments"] = 0
            if next_player["bank_loan_principal"] <= 0:
                next_player["bank_loan_interest_rate"] = 0.0
            updated_player = next_player
        updated_players.append(next_player)
    next_state["players"] = updated_players
    next_state["econ"] = _sync_player_econ_views(updated_players, next_state.get("econ") or {})
    return next_state, {"player_id": player_id, "amount": amount, "player": updated_player}


def buy_corporate_property(game_state: dict[str, Any], *, player_id: int, property_id: int) -> tuple[dict[str, Any], dict[str, Any]]:
    next_state = dict(game_state)
    next_state["econ"] = ensure_liberal_democracy_econ(next_state.get("econ"), next_state.get("settings"))
    current_round = int(next_state.get("current_round", next_state["econ"].get("round_number", 1)) or 1)
    properties = []
    target_property = None
    price = 0.0
    corp_id = None
    for prop in next_state.get("properties", []):
        next_prop = dict(prop)
        if int(next_prop.get("id") or 0) == int(property_id):
            target_property = next_prop
            corp_id = next_prop.get("corporate_owner_id")
            price = round(float(next_prop.get("corporate_listing_price") or 0), 2)
        properties.append(next_prop)
    if target_property is None or not corp_id:
        raise ValueError("That property is not available for corporate buyout.")

    updated_players = []
    updated_player = None
    for player in next_state.get("players", []):
        next_player = dict(player)
        if int(next_player.get("id") or 0) == int(player_id):
            if float(next_player.get("balance", 0) or 0) < price:
                raise ValueError("That player cannot afford the corporate buyout.")
            next_player["balance"] = round(float(next_player.get("balance", 0) or 0) - price, 2)
            updated_player = next_player
        updated_players.append(next_player)
    if updated_player is None:
        raise ValueError("Only active players can buy corporate property.")

    refreshed_properties = []
    for prop in properties:
        next_prop = dict(prop)
        if int(next_prop.get("id") or 0) == int(property_id):
            next_prop["owner_id"] = player_id
            next_prop["corporate_owner_id"] = None
            next_prop["corporate_listing_price"] = None
            next_prop["corporate_rent"] = None
        refreshed_properties.append(next_prop)

    corporations = dict(((next_state["econ"].get("corporations") or {}).get("by_id") or {}))
    corporation = dict(corporations.get(str(corp_id)) or {})
    corporation["property_ids"] = [
        candidate_id
        for candidate_id in corporation.get("property_ids") or []
        if int(candidate_id or 0) != int(property_id)
    ]
    corporation["cash_reserve"] = round(float(corporation.get("cash_reserve", 0) or 0) + price, 2)
    corporation["pricing_modifier"] = round(_clamp(float(corporation.get("pricing_modifier", 1.0) or 1.0) + 0.03, 0.75, 1.65), 4)
    corporation["stock_price"] = round(max(1.0, float(corporation.get("stock_price", 0) or 0) * 1.03), 2)
    corporation["price_change_last_round"] = 0.03
    corporations[str(corp_id)] = corporation

    market = dict(next_state["econ"].get("market") or {})
    assets = dict(market.get("assets") or {})
    asset_key = str(corporation.get("asset_key") or corporation.get("stock_symbol") or "")
    if asset_key in assets:
        asset = dict(assets.get(asset_key) or {})
        asset["price"] = corporation["stock_price"]
        asset["price_change_last_round"] = 0.03
        asset = _append_price_history(asset, current_round, 0.03)
        assets[asset_key] = asset
    market["assets"] = assets
    market = _append_market_history(market, current_round)

    next_state["players"] = updated_players
    next_state["properties"] = refreshed_properties
    next_state["econ"] = {
        **dict(next_state["econ"]),
        "corporations": {
            **dict(next_state["econ"].get("corporations") or {}),
            "by_id": corporations,
        },
        "market": market,
    }
    next_state["econ"] = _sync_player_econ_views(updated_players, next_state["econ"])
    return next_state, {
        "player_id": player_id,
        "property_id": property_id,
        "property_name": target_property.get("name"),
        "price": price,
        "player": updated_player,
    }


def _force_loan_liquidation(next_state: dict[str, Any], player: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], float]:
    player_id = int(player.get("id") or 0)
    liquidation_credit = 0.0
    updated_properties = []
    for prop in next_state.get("properties", []):
        next_prop = dict(prop)
        if int(next_prop.get("owner_id") or 0) == player_id:
            liquidation_credit += float(next_prop.get("base_price", 0) or 0) * 0.5
            liquidation_credit += max(0, int(next_prop.get("dev_level", 0) or 0)) * (float(next_prop.get("base_price", 0) or 0) * 0.25)
            next_prop["owner_id"] = None
            next_prop["dev_level"] = 0
            next_prop["is_mortgaged"] = False
            next_prop["current_value"] = next_prop.get("base_price")
        updated_properties.append(next_prop)
    next_state["properties"] = updated_properties
    updated_player = dict(player)
    updated_player["bank_savings_balance"] = 0.0
    updated_player["bank_missed_payments"] = 0
    return next_state, updated_player, round(liquidation_credit, 2)


def process_liberal_democracy_round(game_state: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    next_state = dict(game_state)
    next_state["econ"] = ensure_liberal_democracy_econ(next_state.get("econ"), next_state.get("settings"))
    current_round = int(next_state.get("current_round", 1) or 1)
    properties, next_econ = refresh_corporate_property_metrics(next_state.get("properties", []), next_state["econ"])
    next_state["properties"] = properties
    next_state["econ"] = next_econ
    corporations = {
        str(corp_id): dict(entry or {})
        for corp_id, entry in (((next_state["econ"].get("corporations") or {}).get("by_id") or {}).items())
    }
    market = dict(next_state["econ"].get("market") or {})
    assets = dict(market.get("assets") or {})
    tax_brackets = _default_tax_brackets(next_state["econ"].get("tax_brackets"))
    active_player_count = max(1, sum(1 for player in next_state.get("players", []) if not player.get("is_bankrupt")))
    market, cycle_bias = _update_market_cycle(
        market,
        {**dict(next_state["econ"]), "active_player_count": active_player_count},
        current_round,
    )
    logs: list[dict[str, Any]] = []

    # Reset round counters on corporations.
    for corporation in corporations.values():
        corporation["rent_income_last_round"] = 0.0
        corporation["salary_cost_last_round"] = 0.0
        corporation["profit_last_round"] = 0.0
        corporation["dividend_per_share_last_round"] = 0.0
        corporation["dividend_yield"] = 0.0
        corporation["price_change_last_round"] = 0.0

    updated_players = []
    for player in next_state.get("players", []):
        next_player = dict(player)
        if next_player.get("is_bankrupt"):
            updated_players.append(next_player)
            continue

        job_history = list(next_player.get("job_event_history") or [])
        status = str(next_player.get("employment_status", "employed") or "employed")
        employer_id = str(next_player.get("employer_id") or "") or None
        if status == "employed" and float(next_player.get("salary", 0) or 0) > 0:
            salary = round(float(next_player.get("salary", 0) or 0), 2)
            next_player["balance"] = round(float(next_player.get("balance", 0) or 0) + salary, 2)
            if employer_id and employer_id in corporations:
                corporations[employer_id]["salary_cost_last_round"] = round(
                    float(corporations[employer_id].get("salary_cost_last_round", 0) or 0) + salary,
                    2,
                )
            logs.append({
                "event_type": "salary_paid",
                "description": f"{next_player.get('username', 'Player')} earned ${salary:.2f} from {next_player.get('employer_name', 'their job')}.",
            })
            # Check how badly the employer's stock is doing — worsens layoff odds.
            employer_corp = corporations.get(str(employer_id or "")) if employer_id else None
            stock_dip = float(employer_corp.get("price_change_last_round", 0) or 0) if employer_corp else 0.0
            dip_penalty = max(0.0, -stock_dip * 1.8)  # e.g. -15% stock → +0.27 extra layoff chance
            pay_cut_threshold = 0.20 + min(0.20, dip_penalty * 0.6)
            layoff_threshold = pay_cut_threshold + 0.08 + min(0.20, dip_penalty * 0.8)

            roll = random.random()
            if roll < 0.10 and stock_dip >= -0.03:
                increase = round(_clamp(random.uniform(0.05, 0.12), 0.05, 0.12), 4)
                next_player["salary"] = round(float(next_player.get("salary", 0) or 0) * (1.0 + increase), 2)
                next_player["salary_band"] = next_player["salary"]
                job_history.append(f"Received a raise to ${next_player['salary']:.2f}.")
            elif roll < 0.18 and stock_dip >= -0.05:
                bonus = round(random.uniform(60.0, 180.0), 2)
                next_player["balance"] = round(float(next_player.get("balance", 0) or 0) + bonus, 2)
                job_history.append(f"Collected a ${bonus:.2f} performance bonus.")
            elif roll < pay_cut_threshold and stock_dip < -0.05:
                cut = round(_clamp(random.uniform(0.05, 0.15), 0.05, 0.15), 4)
                next_player["salary"] = round(max(float(SALARY_BANDS[0]), float(next_player.get("salary", 0) or 0) * (1.0 - cut)), 2)
                job_history.append(f"Pay cut to ${next_player['salary']:.2f} after the company's stock fell sharply.")
                logs.append({
                    "event_type": "job_event",
                    "description": f"{next_player.get('username', 'Player')} took a pay cut because their employer's stock fell.",
                })
            elif roll < layoff_threshold:
                next_player["employment_status"] = "unemployed"
                next_player["unemployment_rounds_remaining"] = random.randint(1, 3)
                reason = "after the company's stock crashed" if stock_dip < -0.08 else "and must find new work"
                job_history.append(f"Was laid off {reason}.")
                logs.append({
                    "event_type": "job_event",
                    "description": f"{next_player.get('username', 'Player')} was laid off{' after their employer''s stock crashed' if stock_dip < -0.08 else ''}.",
                })
        else:
            remaining = max(0, int(next_player.get("unemployment_rounds_remaining", 0) or 0) - 1)
            next_player["unemployment_rounds_remaining"] = remaining
            if remaining <= 0:
                employer_ids = [corp_id for corp_id in (next_state["econ"].get("corporations") or {}).get("active_ids") or [] if str(corp_id) in corporations]
                # Avoid re-hiring at the same company the player just left
                prev_employer = str(next_player.get("employer_id") or "")
                candidates = [c for c in employer_ids if str(c) != prev_employer] or employer_ids
                employer_id = random.choice(candidates) if candidates else None
                employer = corporations.get(str(employer_id)) or {}
                next_player["employment_status"] = "employed" if employer_id else "unemployed"
                next_player["employer_id"] = employer_id
                next_player["employer_name"] = employer.get("name")
                # Fresh salary at the new employer — use current band with a small random adjustment
                base_band = float(next_player.get("salary_band") or SALARY_BANDS[0])
                new_salary = round(base_band * random.uniform(0.88, 1.12), 2)
                next_player["salary"] = max(float(SALARY_BANDS[0]), new_salary)
                next_player["salary_band"] = next_player["salary"]
                if employer_id:
                    job_history.append(f"Found a new job at {next_player.get('employer_name')} earning ${float(next_player.get('salary', 0) or 0):.2f}.")

        savings = float(next_player.get("bank_savings_balance", 0) or 0)
        if savings > 0:
            savings_interest_rate = max(0.01, float((next_state["econ"].get("bank") or {}).get("savings_interest_rate", 0.01) or 0.01))
            interest_credit = round(savings * savings_interest_rate, 2)
            haircut = 0.0
            inflation_rate = float(next_state["econ"].get("inflation_rate", 0.03) or 0.03)
            if inflation_rate >= 0.08 and random.random() < min(0.18, 0.04 + inflation_rate):
                haircut = round(savings * min(0.18, inflation_rate * 0.6), 2)
            next_player["bank_savings_balance"] = round(max(0.0, savings + interest_credit - haircut), 2)
            if interest_credit > 0:
                logs.append({
                    "event_type": "bank_interest",
                    "description": f"{next_player.get('username', 'Player')} earned ${interest_credit:.2f} in bank interest.",
                })
            if haircut > 0:
                logs.append({
                    "event_type": "bank_haircut",
                    "description": f"{next_player.get('username', 'Player')} lost ${haircut:.2f} in a savings haircut.",
                })

        principal = float(next_player.get("bank_loan_principal", 0) or 0)
        if principal > 0:
            loan_rate = float(next_player.get("bank_loan_interest_rate", next_state["econ"].get("interest_rate", 0.06)) or next_state["econ"].get("interest_rate", 0.06))
            interest_due = round(principal * loan_rate, 2)
            principal_due = round(principal * float((next_state["econ"].get("bank") or {}).get("loan_payment_ratio", 0.10) or 0.10), 2)
            total_due = round(interest_due + principal_due, 2)
            payment = min(round(float(next_player.get("balance", 0) or 0), 2), total_due)
            next_player["balance"] = round(float(next_player.get("balance", 0) or 0) - payment, 2)
            remaining_interest = max(0.0, round(interest_due - payment, 2))
            principal_reduction = max(0.0, round(payment - interest_due, 2))
            next_principal = round(max(0.0, principal + remaining_interest - principal_reduction), 2)
            if payment + 0.01 < total_due:
                next_player["bank_missed_payments"] = int(next_player.get("bank_missed_payments", 0) or 0) + 1
            else:
                next_player["bank_missed_payments"] = 0
            if int(next_player.get("bank_missed_payments", 0) or 0) >= int((next_state["econ"].get("bank") or {}).get("default_after_missed_payments", 2) or 2):
                forced_state, reset_player, liquidation_credit = _force_loan_liquidation({**next_state, "players": updated_players + [next_player]}, next_player)
                next_state["properties"] = forced_state["properties"]
                next_player = reset_player
                next_principal = round(max(0.0, next_principal - float(next_player.get("bank_savings_balance", 0) or 0) - liquidation_credit), 2)
                next_player["balance"] = round(float(next_player.get("balance", 0) or 0) - next_principal, 2)
                next_player["bank_loan_principal"] = 0.0
                next_player["bank_loan_interest_rate"] = 0.0
                logs.append({
                    "event_type": "bank_default",
                    "description": f"{next_player.get('username', 'Player')} defaulted on a bank loan and was forced to liquidate assets.",
                })
            else:
                next_player["bank_loan_principal"] = next_principal
            logs.append({
                "event_type": "bank_payment",
                "description": f"{next_player.get('username', 'Player')} owed ${total_due:.2f} to the bank and paid ${payment:.2f}.",
            })

        next_player["job_event_history"] = job_history[-10:]

        # Wealth-tier taxation.
        net_worth = (
            float(next_player.get("balance", 0) or 0)
            + float(next_player.get("bank_savings_balance", 0) or 0)
            + portfolio_market_value(next_player, next_state["econ"])
            - float(next_player.get("bank_loan_principal", 0) or 0)
        )
        bracket = _find_tax_bracket(tax_brackets, net_worth)
        tax_due = round(max(0.0, net_worth * float(bracket.get("rate", 0) or 0) * 0.25), 2)
        if tax_due > 0:
            balance_payment = min(round(float(next_player.get("balance", 0) or 0), 2), tax_due)
            savings_payment = min(round(float(next_player.get("bank_savings_balance", 0) or 0), 2), max(0.0, tax_due - balance_payment))
            next_player["balance"] = round(float(next_player.get("balance", 0) or 0) - balance_payment, 2)
            next_player["bank_savings_balance"] = round(float(next_player.get("bank_savings_balance", 0) or 0) - savings_payment, 2)
            next_state["econ"]["treasury_balance"] = round(float(next_state["econ"].get("treasury_balance", 0) or 0) + balance_payment + savings_payment, 2)
            logs.append({
                "event_type": "wealth_tax",
                "description": f"{next_player.get('username', 'Player')} paid ${balance_payment + savings_payment:.2f} from {bracket.get('label', 'their tax bracket')}.",
            })

        updated_players.append(next_player)

    next_state["players"] = updated_players

    # Corporate updates and dividends.
    dividends_paid = 0.0
    for corporation_id, corporation in corporations.items():
        rent_income = 0.0
        for prop in next_state.get("properties", []):
            if str(prop.get("corporate_owner_id") or "") == corporation_id:
                rent_income += float(prop.get("corporate_rent", 0) or 0)
        salary_cost = float(corporation.get("salary_cost_last_round", 0) or 0)
        macro_drag = float(next_state["econ"].get("inflation_rate", 0.03) or 0.03) * 180.0
        random_shock = random.uniform(-45.0, 70.0)
        profit = round(rent_income - (salary_cost * 0.32) - macro_drag + random_shock, 2)
        price_delta = _clamp(
            (profit / max(300.0, len(corporation.get("property_ids") or []) * 110.0))
            + ((float(next_state["econ"].get("stability", 0.7) or 0.7) - 0.5) * 0.12)
            + ((float(market.get("sentiment", 72.0) or 72.0) - 70.0) / 400.0)
            + cycle_bias
            + random.uniform(-0.04, 0.05),
            -0.18,
            0.22,
        )
        corporation["rent_income_last_round"] = round(rent_income, 2)
        corporation["profit_last_round"] = profit
        corporation["cash_reserve"] = round(float(corporation.get("cash_reserve", 0) or 0) + profit, 2)
        corporation["pricing_modifier"] = round(_clamp(float(corporation.get("pricing_modifier", 1.0) or 1.0) + (price_delta * 0.45), 0.75, 1.65), 4)
        corporation["stock_price"] = round(max(8.0, float(corporation.get("stock_price", 0) or 0) * (1.0 + price_delta)), 2)
        corporation["price_change_last_round"] = round(price_delta, 4)
        if current_round % 3 == 0 and profit > 0:
            dividend_per_share = round(
                min(
                    max(0.0, profit * 0.18 / float(corporation.get("shares_outstanding", TOTAL_CORPORATE_SHARES) or TOTAL_CORPORATE_SHARES)),
                    float(corporation.get("stock_price", 0) or 0) * 0.05,
                ),
                4,
            )
            corporation["dividend_per_share_last_round"] = dividend_per_share
            corporation["dividend_yield"] = round(
                dividend_per_share / max(0.01, float(corporation.get("stock_price", 1) or 1)),
                4,
            )
            for index, player in enumerate(next_state.get("players", [])):
                portfolio = _player_portfolio(player)
                shares_held = int((portfolio.get("stocks") or {}).get(str(corporation.get("asset_key") or corporation.get("stock_symbol") or ""), 0) or 0)
                if shares_held <= 0:
                    continue
                dividend = round(dividend_per_share * shares_held, 2)
                next_state["players"][index]["balance"] = round(float(player.get("balance", 0) or 0) + dividend, 2)
                dividends_paid = round(dividends_paid + dividend, 2)
        else:
            corporation["dividend_yield"] = 0.0

        asset_key = str(corporation.get("asset_key") or corporation.get("stock_symbol") or "")
        if asset_key in assets:
            assets[asset_key] = {
                **dict(assets.get(asset_key) or {}),
                "price": corporation["stock_price"],
                "price_change_last_round": corporation["price_change_last_round"],
            }
            assets[asset_key] = _append_price_history(
                assets[asset_key],
                current_round,
                corporation["price_change_last_round"],
            )
        corporations[corporation_id] = corporation

    for asset_key, defaults in CRYPTO_DEFAULTS.items():
        asset = dict(assets.get(asset_key) or {})
        volatility = float(asset.get("volatility", defaults["volatility"]) or defaults["volatility"])
        crypto_delta = _clamp(
            ((float(market.get("sentiment", 72.0) or 72.0) - 70.0) / 350.0)
            + (cycle_bias * 1.35)
            + random.uniform(-volatility, volatility),
            -0.28,
            0.32,
        )
        asset["price"] = round(max(4.0, float(asset.get("price", defaults["price"]) or defaults["price"]) * (1.0 + crypto_delta)), 2)
        asset["price_change_last_round"] = round(crypto_delta, 4)
        asset = _append_price_history(asset, current_round, crypto_delta)
        assets[asset_key] = asset

    stock_moves = [
        float(corporation.get("price_change_last_round", 0) or 0)
        for corporation in corporations.values()
    ]
    average_stock_move = sum(stock_moves) / max(1, len(stock_moves)) if stock_moves else 0.0
    next_sentiment = _clamp(
        float(market.get("sentiment", 72.0) or 72.0)
        + (average_stock_move * 120.0)
        + (cycle_bias * 90.0)
        + ((float(next_state["econ"].get("stability", 0.7) or 0.7) - 0.5) * 6.0)
        - (float(next_state["econ"].get("inflation_rate", 0.03) or 0.03) * 28.0)
        + random.uniform(-1.2, 1.1),
        8.0,
        96.0,
    )
    market["assets"] = assets
    market["sentiment"] = round(next_sentiment, 2)
    market = _append_market_history(market, current_round)
    phase_label = "growth" if (market.get("cycle") or {}).get("phase") == "growth" else "decay"
    market["last_round_summary"] = [
        f"Market sentiment moved to {round(next_sentiment, 2):.1f}.",
        f"The market is in a {phase_label} phase.",
        f"Dividends paid this round: ${dividends_paid:.2f}.",
    ]
    market["last_dividends_paid"] = dividends_paid

    next_state["econ"] = {
        **dict(next_state["econ"]),
        "market_policy_bias": round(float(next_state["econ"].get("market_policy_bias", 0) or 0) * 0.45, 4),
        "market": market,
        "corporations": {
            **dict(next_state["econ"].get("corporations") or {}),
            "by_id": corporations,
        },
        "tax_brackets": tax_brackets,
    }
    next_state["players"] = [
        {**dict(player), "portfolio": _player_portfolio(player)}
        for player in next_state.get("players", [])
    ]
    next_state["econ"] = _sync_player_econ_views(next_state["players"], next_state["econ"])
    next_state["properties"], next_state["econ"] = refresh_corporate_property_metrics(next_state.get("properties", []), next_state["econ"])
    return next_state, logs


def tick_ld_market_per_turn(game_state: dict[str, Any]) -> dict[str, Any]:
    """Apply a small intra-round stock price nudge so charts update every player turn."""
    next_state = dict(game_state)
    econ = dict(next_state.get("econ") or {})
    market = dict(econ.get("market") or {})
    assets = dict(market.get("assets") or {})
    current_round = int(next_state.get("current_round", 1) or 1)
    corporations = {
        str(k): dict(v or {})
        for k, v in ((econ.get("corporations") or {}).get("by_id") or {}).items()
    }
    cycle_bias = float((market.get("cycle") or {}).get("bias", 0.018) or 0.018)

    for asset_key, asset in list(assets.items()):
        asset = dict(asset)
        volatility = float(asset.get("volatility", 0.06) or 0.06)
        nudge = _clamp(
            (cycle_bias * 0.4) + random.uniform(-volatility * 0.35, volatility * 0.35),
            -0.07,
            0.08,
        )
        old_price = float(asset.get("price", 1.0) or 1.0)
        new_price = round(max(4.0, old_price * (1.0 + nudge)), 2)
        asset["price"] = new_price
        asset["price_change_last_round"] = round(nudge, 4)
        asset["round"] = current_round
        asset = _append_price_history(asset, current_round, nudge)
        assets[asset_key] = asset
        corp_id = asset.get("corporation_id")
        if corp_id and corp_id in corporations:
            corporations[corp_id]["stock_price"] = new_price
            corporations[corp_id]["price_change_last_round"] = round(nudge, 4)

    market["assets"] = assets
    econ["market"] = market
    econ["corporations"] = {
        **dict(econ.get("corporations") or {}),
        "by_id": corporations,
    }
    next_state["econ"] = econ
    return next_state
