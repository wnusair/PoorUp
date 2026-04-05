from __future__ import annotations

from copy import deepcopy
from typing import Any


BOT_DIFFICULTIES = {
    "easy": {
        "key": "easy",
        "label": "Cautious",
        "summary": "Under-exploits systems, preserves larger buffers, and makes readable mistakes.",
        "allowed_capabilities": {
            "welfare_abuse": False,
            "bailout_abuse": False,
            "negative_exposure": False,
            "policy_lookahead": False,
        },
        "skill": {
            "planning_horizon": 2,
            "valuation_noise": 0.16,
            "leverage_confidence": 0.14,
            "trade_precision": 0.42,
        },
        "style": {
            "reserve_multiplier": 1.18,
            "aggression_bonus": -0.08,
            "liquidity_bonus": 0.1,
            "lobby_share_multiplier": 0.7,
            "denial_multiplier": 0.68,
        },
    },
    "normal": {
        "key": "normal",
        "label": "Standard",
        "summary": "Competent default bot that understands welfare timing but avoids bailout abuse.",
        "allowed_capabilities": {
            "welfare_abuse": True,
            "bailout_abuse": False,
            "negative_exposure": False,
            "policy_lookahead": True,
        },
        "skill": {
            "planning_horizon": 4,
            "valuation_noise": 0.1,
            "leverage_confidence": 0.42,
            "trade_precision": 0.67,
        },
        "style": {
            "reserve_multiplier": 1.0,
            "aggression_bonus": 0.0,
            "liquidity_bonus": 0.0,
            "lobby_share_multiplier": 1.0,
            "denial_multiplier": 1.0,
        },
    },
    "hard": {
        "key": "hard",
        "label": "Aggressive",
        "summary": "Pushes leverage, stages policy lines, and uses bailout plus welfare support when justified.",
        "allowed_capabilities": {
            "welfare_abuse": True,
            "bailout_abuse": True,
            "negative_exposure": True,
            "policy_lookahead": True,
        },
        "skill": {
            "planning_horizon": 5,
            "valuation_noise": 0.06,
            "leverage_confidence": 0.74,
            "trade_precision": 0.84,
        },
        "style": {
            "reserve_multiplier": 0.84,
            "aggression_bonus": 0.08,
            "liquidity_bonus": -0.04,
            "lobby_share_multiplier": 1.18,
            "denial_multiplier": 1.18,
        },
    },
    "expert": {
        "key": "expert",
        "label": "Exploitative",
        "summary": "Treats the economy as a system and deliberately exploits public protection when the line is coherent.",
        "allowed_capabilities": {
            "welfare_abuse": True,
            "bailout_abuse": True,
            "negative_exposure": True,
            "policy_lookahead": True,
        },
        "skill": {
            "planning_horizon": 6,
            "valuation_noise": 0.03,
            "leverage_confidence": 0.9,
            "trade_precision": 0.92,
        },
        "style": {
            "reserve_multiplier": 0.72,
            "aggression_bonus": 0.12,
            "liquidity_bonus": -0.08,
            "lobby_share_multiplier": 1.32,
            "denial_multiplier": 1.28,
        },
    },
}


BOT_PERSONALITIES = {
    "steady_collector": {
        "key": "steady_collector",
        "label": "Steady Collector",
        "allowed_difficulties": ["easy"],
        "short_description": "Buys obvious value, protects cash, and develops only with a healthy buffer.",
        "example_behaviors": [
            "Buys a good standalone property if post-purchase cash is still comfortable.",
            "Waits too long before building on a monopoly.",
            "Avoids risky lobbying even when it might be correct.",
        ],
        "preferred_doctrines": ["liquidity_preservation", "development_snowball"],
        "style": {
            "aggression": 0.36,
            "liquidity_bias": 0.78,
            "macro_focus": 0.24,
            "trade_focus": 0.34,
            "auction_focus": 0.4,
            "development_focus": 0.46,
            "denial_focus": 0.16,
            "patience": 0.78,
            "lobby_focus": 0.18,
            "set_focus": 0.36,
        },
    },
    "rule_follower": {
        "key": "rule_follower",
        "label": "Rule Follower",
        "allowed_difficulties": ["easy"],
        "short_description": "Plays by visible board logic and does not exploit welfare or public-finance edge cases.",
        "example_behaviors": [
            "Prefers straightforward purchases and safe builds.",
            "Mortgages earlier than a stronger player would.",
            "Rarely stages multi-round policy plans.",
        ],
        "preferred_doctrines": ["liquidity_preservation", "monopoly_rush"],
        "style": {
            "aggression": 0.42,
            "liquidity_bias": 0.74,
            "macro_focus": 0.18,
            "trade_focus": 0.3,
            "auction_focus": 0.42,
            "development_focus": 0.42,
            "denial_focus": 0.12,
            "patience": 0.82,
            "lobby_focus": 0.14,
            "set_focus": 0.34,
        },
    },
    "balanced_operator": {
        "key": "balanced_operator",
        "label": "Balanced Operator",
        "allowed_difficulties": ["normal"],
        "short_description": "Plays a solid all-around game with moderate development and reasonable trades.",
        "example_behaviors": [
            "Completes sets when the price is fair.",
            "Uses welfare timing to stay efficient.",
            "Avoids deliberate rescue dependence.",
        ],
        "preferred_doctrines": ["monopoly_rush", "development_snowball"],
        "style": {
            "aggression": 0.58,
            "liquidity_bias": 0.56,
            "macro_focus": 0.46,
            "trade_focus": 0.5,
            "auction_focus": 0.52,
            "development_focus": 0.64,
            "denial_focus": 0.36,
            "patience": 0.58,
            "lobby_focus": 0.46,
            "set_focus": 0.58,
        },
    },
    "welfare_optimizer": {
        "key": "welfare_optimizer",
        "label": "Welfare Optimizer",
        "allowed_difficulties": ["normal"],
        "short_description": "Understands welfare cushions low-cash states and spends more aggressively when recovery is favorable.",
        "example_behaviors": [
            "Spends down into a welfare-eligible position if the board upgrade is strong.",
            "Pushes welfare increases more often than average.",
            "Still preserves enough cash to avoid deliberate bailout dependence.",
        ],
        "preferred_doctrines": ["development_snowball", "policy_shaping"],
        "style": {
            "aggression": 0.62,
            "liquidity_bias": 0.48,
            "macro_focus": 0.58,
            "trade_focus": 0.46,
            "auction_focus": 0.48,
            "development_focus": 0.68,
            "denial_focus": 0.3,
            "patience": 0.52,
            "lobby_focus": 0.6,
            "set_focus": 0.52,
        },
    },
    "set_hunter": {
        "key": "set_hunter",
        "label": "Set Hunter",
        "allowed_difficulties": ["normal"],
        "short_description": "Prioritizes color-group completion and straightforward development pressure.",
        "example_behaviors": [
            "Trades aggressively for the last piece of a set.",
            "Builds as soon as the monopoly is stable.",
            "Uses lobbying mainly to support the board plan, not reshape the full economy.",
        ],
        "preferred_doctrines": ["monopoly_rush", "development_snowball"],
        "style": {
            "aggression": 0.66,
            "liquidity_bias": 0.44,
            "macro_focus": 0.34,
            "trade_focus": 0.68,
            "auction_focus": 0.54,
            "development_focus": 0.74,
            "denial_focus": 0.4,
            "patience": 0.5,
            "lobby_focus": 0.34,
            "set_focus": 0.86,
        },
    },
    "expansionist": {
        "key": "expansionist",
        "label": "Expansionist",
        "allowed_difficulties": ["hard"],
        "short_description": "Pushes hard for monopoly completion, development tempo, and board pressure.",
        "example_behaviors": [
            "Overpays slightly for a monopoly finisher if the rent engine is worth it.",
            "Builds into a thin-cash state when protections make it rational.",
            "Rebuilds public protection before levering again.",
        ],
        "preferred_doctrines": ["monopoly_rush", "development_snowball", "social_democracy_leverage"],
        "style": {
            "aggression": 0.8,
            "liquidity_bias": 0.34,
            "macro_focus": 0.48,
            "trade_focus": 0.62,
            "auction_focus": 0.62,
            "development_focus": 0.88,
            "denial_focus": 0.5,
            "patience": 0.42,
            "lobby_focus": 0.52,
            "set_focus": 0.84,
        },
    },
    "policy_shaper": {
        "key": "policy_shaper",
        "label": "Policy Shaper",
        "allowed_difficulties": ["hard"],
        "short_description": "Treats lobbying as a first-class weapon and sequences policy to unlock future turns.",
        "example_behaviors": [
            "Pushes bailout enable before maximum leverage.",
            "Uses welfare or tax changes to support a chosen doctrine.",
            "Adds only enough money to near-passing pools instead of overspending.",
        ],
        "preferred_doctrines": ["policy_shaping", "treasury_rebuild_then_leverage", "social_democracy_leverage"],
        "style": {
            "aggression": 0.68,
            "liquidity_bias": 0.44,
            "macro_focus": 0.84,
            "trade_focus": 0.54,
            "auction_focus": 0.44,
            "development_focus": 0.58,
            "denial_focus": 0.56,
            "patience": 0.62,
            "lobby_focus": 0.9,
            "set_focus": 0.46,
        },
    },
    "denialist": {
        "key": "denialist",
        "label": "Denialist",
        "allowed_difficulties": ["hard"],
        "short_description": "Spends and trades to stop opponents from becoming unstoppable even when the immediate gain is only moderate.",
        "example_behaviors": [
            "Buys awkward properties to break a rival's near-monopoly.",
            "Refuses trades that help a rival complete a premium engine.",
            "Chooses policy directions that weaken the strongest opponent's line.",
        ],
        "preferred_doctrines": ["policy_shaping", "development_snowball", "distress_recovery"],
        "style": {
            "aggression": 0.66,
            "liquidity_bias": 0.48,
            "macro_focus": 0.56,
            "trade_focus": 0.64,
            "auction_focus": 0.58,
            "development_focus": 0.62,
            "denial_focus": 0.9,
            "patience": 0.48,
            "lobby_focus": 0.58,
            "set_focus": 0.5,
        },
    },
    "leverage_architect": {
        "key": "leverage_architect",
        "label": "Leverage Architect",
        "allowed_difficulties": ["expert"],
        "short_description": "Builds around public protection, treasury capacity, and policy timing to maximize development pressure.",
        "example_behaviors": [
            "Calculates whether welfare plus bailout justify a near-all-in build sequence.",
            "Intentionally goes mildly negative when rescue is highly likely and the rent engine justifies it.",
            "Rebuilds the treasury politically before levering again.",
        ],
        "preferred_doctrines": ["social_democracy_leverage", "treasury_rebuild_then_leverage", "development_snowball"],
        "style": {
            "aggression": 0.86,
            "liquidity_bias": 0.26,
            "macro_focus": 0.78,
            "trade_focus": 0.6,
            "auction_focus": 0.6,
            "development_focus": 0.92,
            "denial_focus": 0.56,
            "patience": 0.38,
            "lobby_focus": 0.72,
            "set_focus": 0.8,
        },
    },
    "treasury_predator": {
        "key": "treasury_predator",
        "label": "Treasury Predator",
        "allowed_difficulties": ["expert"],
        "short_description": "Treats the public treasury as a strategic battlefield and manages who gets to benefit from it.",
        "example_behaviors": [
            "Pushes tax hikes before taking rescue-heavy lines.",
            "Opposes welfare or bailout directions when rivals benefit more than it does.",
            "Uses pledge trades to buy policy support as well as assets.",
        ],
        "preferred_doctrines": ["treasury_rebuild_then_leverage", "policy_shaping", "social_democracy_leverage"],
        "style": {
            "aggression": 0.74,
            "liquidity_bias": 0.38,
            "macro_focus": 0.96,
            "trade_focus": 0.7,
            "auction_focus": 0.42,
            "development_focus": 0.58,
            "denial_focus": 0.72,
            "patience": 0.6,
            "lobby_focus": 0.94,
            "set_focus": 0.42,
        },
    },
    "board_strangler": {
        "key": "board_strangler",
        "label": "Board Strangler",
        "allowed_difficulties": ["expert"],
        "short_description": "Focuses on choking the board with denial, concentrated high-rent zones, and hostile policy maintenance.",
        "example_behaviors": [
            "Trades and buys primarily to deny rival engines.",
            "Builds where traffic and downside asymmetry are strongest.",
            "Uses lobbying to preserve a hostile environment once ahead.",
        ],
        "preferred_doctrines": ["development_snowball", "policy_shaping", "distress_recovery"],
        "style": {
            "aggression": 0.76,
            "liquidity_bias": 0.36,
            "macro_focus": 0.62,
            "trade_focus": 0.76,
            "auction_focus": 0.62,
            "development_focus": 0.82,
            "denial_focus": 0.96,
            "patience": 0.42,
            "lobby_focus": 0.68,
            "set_focus": 0.58,
        },
    },
}


DEFAULT_PERSONALITY_BY_DIFFICULTY = {
    "easy": "steady_collector",
    "normal": "balanced_operator",
    "hard": "expansionist",
    "expert": "leverage_architect",
}

LEGACY_PERSONALITY_MAP = {
    "balance_sheet": "balanced_operator",
    "expansionist": "expansionist",
    "macro_hawk": "policy_shaper",
    "rail_baron": "set_hunter",
    "liquidity_guard": "steady_collector",
    "policy_shaper": "policy_shaper",
}

LEGACY_DIFFICULTY_BY_PERSONALITY = {
    "steady_collector": "easy",
    "rule_follower": "easy",
    "balanced_operator": "normal",
    "welfare_optimizer": "normal",
    "set_hunter": "normal",
    "expansionist": "hard",
    "policy_shaper": "hard",
    "denialist": "hard",
    "leverage_architect": "expert",
    "treasury_predator": "expert",
    "board_strangler": "expert",
}

DIFFICULTY_ALIASES = {
    "easy": "easy",
    "cautious": "easy",
    "normal": "normal",
    "standard": "normal",
    "hard": "hard",
    "aggressive": "hard",
    "expert": "expert",
    "exploitative": "expert",
}


def _normalize_key(raw_value: Any) -> str:
    return str(raw_value or "").strip().lower().replace("-", "_").replace(" ", "_")


def normalize_bot_difficulty(raw_value: Any, *, fallback: str = "normal") -> str:
    key = _normalize_key(raw_value)
    normalized = DIFFICULTY_ALIASES.get(key)
    if normalized:
        return normalized
    return fallback


def infer_legacy_difficulty(raw_personality: Any) -> str:
    normalized = normalize_bot_personality(raw_personality, fallback_persona=False)
    if normalized:
        return LEGACY_DIFFICULTY_BY_PERSONALITY.get(normalized, "normal")
    return "normal"


def normalize_bot_personality(
    raw_value: Any,
    *,
    difficulty: str | None = None,
    fallback_persona: bool = True,
) -> str | None:
    key = _normalize_key(raw_value)
    if not key:
        if not fallback_persona:
            return None
        normalized_difficulty = normalize_bot_difficulty(difficulty or "normal")
        return DEFAULT_PERSONALITY_BY_DIFFICULTY[normalized_difficulty]

    mapped_key = LEGACY_PERSONALITY_MAP.get(key, key)
    if mapped_key in BOT_PERSONALITIES:
        if difficulty and not is_personality_allowed_for_difficulty(mapped_key, difficulty):
            if fallback_persona:
                normalized_difficulty = normalize_bot_difficulty(difficulty)
                return choose_default_personality(normalized_difficulty)
            return None
        return mapped_key

    if not fallback_persona:
        return None

    normalized_difficulty = normalize_bot_difficulty(difficulty or "normal")
    return DEFAULT_PERSONALITY_BY_DIFFICULTY[normalized_difficulty]


def get_difficulty_metadata(difficulty: str) -> dict[str, Any]:
    normalized = normalize_bot_difficulty(difficulty)
    return deepcopy(BOT_DIFFICULTIES[normalized])


def get_personality_metadata(personality: str) -> dict[str, Any]:
    normalized = normalize_bot_personality(personality, fallback_persona=True)
    return deepcopy(BOT_PERSONALITIES[normalized])


def is_personality_allowed_for_difficulty(personality: str, difficulty: str) -> bool:
    normalized_personality = normalize_bot_personality(personality, fallback_persona=False)
    if normalized_personality is None:
        return False
    normalized_difficulty = normalize_bot_difficulty(difficulty)
    return normalized_difficulty in BOT_PERSONALITIES[normalized_personality]["allowed_difficulties"]


def choose_default_personality(difficulty: str = "normal", seat_index: int = 0) -> str:
    normalized_difficulty = normalize_bot_difficulty(difficulty)
    allowed = [
        key
        for key, metadata in BOT_PERSONALITIES.items()
        if normalized_difficulty in metadata["allowed_difficulties"]
    ]
    if not allowed:
        return DEFAULT_PERSONALITY_BY_DIFFICULTY[normalized_difficulty]
    return allowed[max(0, seat_index) % len(allowed)]


def validate_bot_configuration(difficulty: Any, personality: Any) -> tuple[str, str]:
    normalized_difficulty = normalize_bot_difficulty(difficulty)
    normalized_personality = normalize_bot_personality(
        personality,
        difficulty=normalized_difficulty,
        fallback_persona=False,
    )
    if normalized_personality is None:
        raise ValueError("Select a valid bot personality.")
    if not is_personality_allowed_for_difficulty(normalized_personality, normalized_difficulty):
        raise ValueError(
            f"{normalized_personality.replace('_', ' ').title()} is not available for {normalized_difficulty} difficulty."
        )
    return normalized_difficulty, normalized_personality


def get_public_difficulty_options() -> list[dict[str, Any]]:
    return [
        {
            "key": difficulty["key"],
            "label": difficulty["label"],
            "summary": difficulty["summary"],
            "allowed_capabilities": dict(difficulty["allowed_capabilities"]),
        }
        for difficulty in BOT_DIFFICULTIES.values()
    ]


def get_public_personality_options(*, difficulty: str | None = None) -> list[dict[str, Any]]:
    normalized_difficulty = normalize_bot_difficulty(difficulty or "normal") if difficulty else None
    options = []
    for metadata in BOT_PERSONALITIES.values():
        if normalized_difficulty and normalized_difficulty not in metadata["allowed_difficulties"]:
            continue
        options.append({
            "key": metadata["key"],
            "label": metadata["label"],
            "allowed_difficulties": list(metadata["allowed_difficulties"]),
            "short_description": metadata["short_description"],
            "example_behaviors": list(metadata["example_behaviors"]),
            "preferred_doctrines": list(metadata["preferred_doctrines"]),
        })
    return options


def get_public_bot_catalog() -> dict[str, Any]:
    return {
        "difficulties": get_public_difficulty_options(),
        "personalities": get_public_personality_options(),
        "defaults": {
            "difficulty": "normal",
            "personality_by_difficulty": {
                difficulty: choose_default_personality(difficulty)
                for difficulty in BOT_DIFFICULTIES
            },
        },
    }


def build_public_bot_metadata(bot_profile: dict[str, Any] | None) -> dict[str, Any]:
    profile = dict(bot_profile or {})
    difficulty = normalize_bot_difficulty(profile.get("difficulty") or infer_legacy_difficulty(profile.get("persona")))
    personality = normalize_bot_personality(
        profile.get("persona"),
        difficulty=difficulty,
        fallback_persona=True,
    )
    difficulty_meta = BOT_DIFFICULTIES[difficulty]
    personality_meta = BOT_PERSONALITIES[personality]
    doctrine = profile.get("doctrine") or personality_meta["preferred_doctrines"][0]
    return {
        "bot_difficulty": difficulty,
        "bot_difficulty_label": difficulty_meta["label"],
        "bot_persona": personality,
        "bot_persona_label": personality_meta["label"],
        "bot_persona_description": personality_meta["short_description"],
        "bot_doctrine": doctrine,
    }
