from flask import render_template

from CTFd.admin import admin
from CTFd.utils.config import is_teams_mode, is_hybrid_mode
from CTFd.utils.decorators import admins_only
from CTFd.utils.scores import get_standings, get_user_standings, get_hybrid_individual_standings, get_hybrid_team_standings


@admin.route("/admin/scoreboard")
@admins_only
def scoreboard_listing():
    if is_hybrid_mode():
        # In hybrid mode, get both individual and team standings
        individual_standings = get_hybrid_individual_standings(admin=True)
        team_standings = get_hybrid_team_standings(admin=True)
        return render_template(
            "admin/scoreboard.html", 
            individual_standings=individual_standings,
            team_standings=team_standings,
            is_hybrid=True
        )
    else:
        # Standard mode (users or teams)
        standings = get_standings(admin=True)
        user_standings = get_user_standings(admin=True) if is_teams_mode() else None
        return render_template(
            "admin/scoreboard.html", 
            standings=standings, 
            user_standings=user_standings,
            is_hybrid=False
        )
