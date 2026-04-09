import re
from better_profanity import profanity

profanity.load_censor_words()

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{1,12}$")


def is_clean_username(username: str) -> bool:
    """Return True if the username does not contain profanity."""
    return not profanity.contains_profanity(username)


def validate_username(username: str) -> tuple[bool, str]:
    """
    Validate a username against all rules.

    Returns (is_valid: bool, error_message: str).
    Error message is empty string on success.
    """
    if not username:
        return False, "Username cannot be empty."

    if len(username) > 12:
        return False, "Username must be 12 characters or fewer."

    if not USERNAME_RE.match(username):
        return False, "Username may only contain letters, digits, and underscores."

    if not is_clean_username(username):
        return False, "Username contains inappropriate content."

    return True, ""
