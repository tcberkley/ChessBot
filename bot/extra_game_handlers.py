"""Functions for the user to implement when the config file is not adequate to express bot requirements."""
from lib import model
from lib.types import OPTIONS_TYPE


def game_specific_options(game: model.Game) -> OPTIONS_TYPE:
    """
    Return a dictionary of engine options based on game aspects.

    By default, an empty dict is returned so that the options in the configuration file are used.
    """
    return {}


def is_supported_extra(challenge: model.Challenge) -> bool:
    """
    Determine whether to accept a challenge.

    Humans are accepted at any rating. Bots must play rated games and be within
    ±300 rating points in the challenged time control (bullet, blitz, rapid, classical).
    """
    if challenge.challenger.is_bot:
        # Bots may only play rated games
        if not challenge.rated:
            return False
        # Rating proximity check (bots only): within ±300 in the specific game mode
        my_rating = challenge.my_perfs.get(challenge.speed, {}).get("rating", 0)
        challenger_rating = challenge.challenger.rating or 0
        if my_rating > 0 and challenger_rating > 0:
            if abs(challenger_rating - my_rating) > 300:
                return False

    return True
