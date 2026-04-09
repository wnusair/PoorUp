import random


def roll_single() -> int:
    """Roll a single standard six-sided die."""
    return random.randint(1, 6)


def roll_dice() -> dict:
    """
    Roll two six-sided dice.

    Returns a dict with:
      - die1: first die value
      - die2: second die value
      - total: sum of both dice
      - is_doubles: True if both dice show the same value
    """
    die1 = roll_single()
    die2 = roll_single()
    return {
        "die1": die1,
        "die2": die2,
        "total": die1 + die2,
        "is_doubles": die1 == die2,
    }
