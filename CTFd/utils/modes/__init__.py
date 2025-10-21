from flask import url_for
from flask_babel import ngettext

from CTFd.models import Teams, Users
from CTFd.utils import get_config

# TODO: Replace these constants with the UserModeTypes enum
USERS_MODE = "users"
TEAMS_MODE = "teams"
HYBRID_MODE = "hybrid"


def generate_account_url(account_id, admin=False):
    if get_config("user_mode") == USERS_MODE:
        if admin:
            return url_for("admin.users_detail", user_id=account_id)
        else:
            return url_for("users.public", user_id=account_id)
    elif get_config("user_mode") == TEAMS_MODE:
        if admin:
            return url_for("admin.teams_detail", team_id=account_id)
        else:
            return url_for("teams.public", team_id=account_id)
    elif get_config("user_mode") == HYBRID_MODE:
        # In hybrid mode, we need to determine if account_id refers to a user or team
        # First check if it's a team ID
        team = Teams.query.filter_by(id=account_id).first()
        if team:
            # It's a team ID
            if admin:
                return url_for("admin.teams_detail", team_id=account_id)
            else:
                return url_for("teams.public", team_id=account_id)
        
        # Otherwise, check if it's a user ID
        user = Users.query.filter_by(id=account_id).first()
        if user:
            # It's a user ID - redirect to user page
            if admin:
                return url_for("admin.users_detail", user_id=account_id)
            else:
                return url_for("users.public", user_id=account_id)
        
        # Fallback - assume it's a user ID if we can't find it
        if admin:
            return url_for("admin.users_detail", user_id=account_id)
        else:
            return url_for("users.public", user_id=account_id)


def get_model():
    if get_config("user_mode") == USERS_MODE:
        return Users
    elif get_config("user_mode") == TEAMS_MODE:
        return Teams
    elif get_config("user_mode") == HYBRID_MODE:
        # In hybrid mode, we need to handle both users and teams
        # Return None and let calling code handle the distinction
        return None


def get_mode_as_word(plural=False, capitalize=False):
    count = 2 if plural else 1
    if get_config("user_mode") == USERS_MODE:
        word = ngettext("user", "users", count)
    elif get_config("user_mode") == HYBRID_MODE:
        word = ngettext("participant", "participants", count)
    else:
        word = ngettext("team", "teams", count)

    if capitalize:
        word = word.title()
    return word
