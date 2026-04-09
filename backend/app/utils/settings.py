GOVERNMENT_TYPE_ALIASES = {
    "minarchism": "minarchism",
    "minarchy": "minarchism",
    "liberal_democracy": "liberal_democracy",
    "liberal-democracy": "liberal_democracy",
    "liberal democracy": "liberal_democracy",
    "liberaldemocracy": "liberal_democracy",
    "democracy": "liberal_democracy",
    "democratic": "liberal_democracy",
    "social_democracy": "social_democracy",
    "social-democracy": "social_democracy",
    "social democracy": "social_democracy",
    "socialdemocracy": "social_democracy",
    "socialism": "social_democracy",
}


GAME_MODE_ALIASES = {
    "standard": "standard",
    "speed": "speed",
    "chaos": "chaos",
    "cooperative": "cooperative",
    "co-op": "cooperative",
    "coop": "cooperative",
    "team": "cooperative",
    "teams": "cooperative",
}


SETTINGS_KEY_ALIASES = {
    "allow_auctions": "auction_enabled",
    "allow_trading": "trading_enabled",
    "allow_lobbying": "lobbying_enabled",
    "allow_teams": "deals_enabled",
    "teams_enabled": "deals_enabled",
    "free_parking_jackpot": "free_parking_pot_enabled",
    "double_go_salary": "double_on_go",
}


def normalize_government_type(raw_value) -> str:
    if raw_value is None:
        return "liberal_democracy"

    value = str(raw_value).strip().lower()
    if not value:
        return "liberal_democracy"

    normalized = GOVERNMENT_TYPE_ALIASES.get(value)
    if normalized is not None:
        return normalized

    collapsed = value.replace("-", "_").replace(" ", "_")
    return GOVERNMENT_TYPE_ALIASES.get(collapsed, "liberal_democracy")


def normalize_game_mode(raw_value) -> str:
    if raw_value is None:
        return "standard"

    value = str(raw_value).strip().lower()
    if not value:
        return "standard"

    normalized = GAME_MODE_ALIASES.get(value)
    if normalized is not None:
        return normalized

    collapsed = value.replace("-", "_").replace(" ", "_")
    return GAME_MODE_ALIASES.get(collapsed, "standard")


def normalize_settings_payload(settings: dict | None, allowed_keys: set[str] | None = None) -> dict:
    normalized = {}
    if not settings:
        return normalized

    for key, value in settings.items():
        canonical_key = SETTINGS_KEY_ALIASES.get(key, key)
        if allowed_keys is not None and canonical_key not in allowed_keys:
            continue
        if canonical_key == "government_type":
            value = normalize_government_type(value)
        elif canonical_key == "game_mode":
            value = normalize_game_mode(value)
        normalized[canonical_key] = value

    return normalized