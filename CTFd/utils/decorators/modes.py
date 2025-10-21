import functools

from flask import abort

from CTFd.utils import get_config
from CTFd.utils.modes import TEAMS_MODE, USERS_MODE, HYBRID_MODE


def require_team_mode(f):
    @functools.wraps(f)
    def _require_team_mode(*args, **kwargs):
        if get_config("user_mode") == USERS_MODE:
            abort(404)
        return f(*args, **kwargs)

    return _require_team_mode


def require_user_mode(f):
    @functools.wraps(f)
    def _require_user_mode(*args, **kwargs):
        if get_config("user_mode") == TEAMS_MODE:
            abort(404)
        return f(*args, **kwargs)

    return _require_user_mode


def require_hybrid_mode(f):
    @functools.wraps(f)
    def _require_hybrid_mode(*args, **kwargs):
        if get_config("user_mode") != HYBRID_MODE:
            abort(404)
        return f(*args, **kwargs)

    return _require_hybrid_mode


def allow_hybrid_mode(f):
    @functools.wraps(f)
    def _allow_hybrid_mode(*args, **kwargs):
        mode = get_config("user_mode")
        if mode not in [TEAMS_MODE, HYBRID_MODE]:
            abort(404)
        return f(*args, **kwargs)

    return _allow_hybrid_mode
