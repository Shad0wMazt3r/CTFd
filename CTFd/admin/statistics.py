from flask import render_template

from CTFd.admin import admin
from CTFd.models import Challenges, Fails, Solves, Teams, Tracking, Users, db
from sqlalchemy import func as sa_func
from CTFd.utils.config import get_config
from CTFd.utils.decorators import admins_only
from CTFd.utils.modes import get_model
from CTFd.utils.scores import get_standings
from CTFd.utils.updates import update_check


@admin.route("/admin/statistics", methods=["GET"])
@admins_only
def statistics():
    update_check()

    user_mode = get_config("user_mode")

    teams_registered = Teams.query.count()
    users_registered = Users.query.count()

    if user_mode == "users":
        wrong_count = (
            Fails.query.join(Users, Fails.account_id == Users.id)
            .filter(Users.banned == False, Users.hidden == False)
            .count()
        )
    elif user_mode == "teams":
        wrong_count = (
            Fails.query.join(Teams, Fails.account_id == Teams.id)
            .filter(Teams.banned == False, Teams.hidden == False)
            .count()
        )
    elif user_mode == "hybrid":
        user_wrong_count = (
            Fails.query.join(Users, Fails.account_id == Users.id)
            .filter(
                Users.banned == False, 
                Users.hidden == False, 
                Users.user_type == "individual",
                Fails.user_id.isnot(None),  # Only individual user fails
                Fails.team_id.is_(None),
            )
            .count()
        )
        team_wrong_count = (
            Fails.query.join(Teams, Fails.account_id == Teams.id)
            .filter(
                Teams.banned == False, 
                Teams.hidden == False, 
                Teams.user_type == "team",
                Fails.team_id.isnot(None),  # Only team fails
                Fails.user_id.is_(None),
            )
            .count()
        )
        wrong_count = user_wrong_count + team_wrong_count
    else:
        wrong_count = 0 # Fallback


    if user_mode == "users":
        solve_count = (
            Solves.query.join(Users, Solves.account_id == Users.id)
            .filter(Users.banned == False, Users.hidden == False)
            .count()
        )
    elif user_mode == "teams":
        solve_count = (
            Solves.query.join(Teams, Solves.account_id == Teams.id)
            .filter(Teams.banned == False, Teams.hidden == False)
            .count()
        )
    elif user_mode == "hybrid":
        user_solve_count = (
            Solves.query.join(Users, Solves.account_id == Users.id)
            .filter(
                Users.banned == False, 
                Users.hidden == False, 
                Users.user_type == "individual",
                Solves.user_id.isnot(None),  # Only individual user solves
                Solves.team_id.is_(None),
            )
            .count()
        )
        team_solve_count = (
            Solves.query.join(Teams, Solves.account_id == Teams.id)
            .filter(
                Teams.banned == False, 
                Teams.hidden == False, 
                Teams.user_type == "team",
                Solves.team_id.isnot(None),  # Only team solves
                Solves.user_id.is_(None),
            )
            .count()
        )
        solve_count = user_solve_count + team_solve_count
    else:
        solve_count = 0 # Fallback


    challenge_count = Challenges.query.count()

    total_points = (
        Challenges.query.with_entities(db.func.sum(Challenges.value).label("sum"))
        .filter_by(state="visible")
        .first()
        .sum
    ) or 0

    ip_count = Tracking.query.with_entities(Tracking.ip).distinct().count()

    if user_mode == "users":
        solves_sub = (
            db.session.query(
                Solves.challenge_id, db.func.count(Solves.challenge_id).label("solves_cnt")
            )
            .join(Users, Solves.account_id == Users.id)
            .filter(Users.banned == False, Users.hidden == False)
            .group_by(Solves.challenge_id)
            .subquery()
        )
    elif user_mode == "teams":
        solves_sub = (
            db.session.query(
                Solves.challenge_id, db.func.count(Solves.challenge_id).label("solves_cnt")
            )
            .join(Teams, Solves.account_id == Teams.id)
            .filter(Teams.banned == False, Teams.hidden == False)
            .group_by(Solves.challenge_id)
            .subquery()
        )
    elif user_mode == "hybrid":
        # For hybrid mode, individual users' solves
        user_solves_sub = (
            db.session.query(
                Solves.challenge_id.label("challenge_id"),
                sa_func.count(Solves.challenge_id).label("solves_cnt"),
            )
            .join(Users, Solves.account_id == Users.id)
            .filter(
                Users.banned == False,
                Users.hidden == False,
                Users.user_type == "individual",
                Solves.user_id.isnot(None),  # Only individual user solves
                Solves.team_id.is_(None),
            )
            .group_by(Solves.challenge_id)
        )
        
        # For hybrid mode, team solves
        team_solves_sub = (
            db.session.query(
                Solves.challenge_id.label("challenge_id"),
                sa_func.count(Solves.challenge_id).label("solves_cnt"),
            )
            .join(Teams, Solves.account_id == Teams.id)
            .filter(
                Teams.banned == False,
                Teams.hidden == False,
                Teams.user_type == "team",
                Solves.team_id.isnot(None),  # Only team solves
                Solves.user_id.is_(None),
            )
            .group_by(Solves.challenge_id)
        )
        
        # Union both queries and make it a subquery
        solves_sub = user_solves_sub.union_all(team_solves_sub).subquery()
    else:
        solves_sub = db.session.query().subquery() # Fallback


    solves = (
        db.session.query(
            solves_sub.columns.challenge_id,
            solves_sub.columns.solves_cnt,
            Challenges.name,
        )
        .join(Challenges, solves_sub.columns.challenge_id == Challenges.id)
        .all()
    )

    solve_data = {}
    for _chal, count, name in solves:
        solve_data[name] = count

    most_solved = None
    least_solved = None
    if len(solve_data):
        most_solved = max(solve_data, key=solve_data.get)
        least_solved = min(solve_data, key=solve_data.get)

    account_scores_raw = get_standings(count=100, admin=True)

    if user_mode == "hybrid":
        # In hybrid mode, get_standings() already returns the combined list
        account_scores = account_scores_raw
    else:
        account_scores = account_scores_raw

    # Get all challenges ordered by category and value
    all_challenges = (
        Challenges.query.filter(Challenges.state == "visible")
        .order_by(Challenges.value.asc(), Challenges.category)
        .all()
    )

    # Get solve matrix data for top 100 accounts
    top_account_ids = [account.account_id for account in account_scores]

    if top_account_ids:
        if user_mode == "users":
            solve_matrix_data = (
                db.session.query(
                    Solves.account_id,
                    Solves.challenge_id,
                    Challenges.name.label("challenge_name"),
                )
                .join(Challenges, Challenges.id == Solves.challenge_id)
                .join(Users, Users.id == Solves.account_id)
                .filter(
                    Solves.account_id.in_(top_account_ids),
                    Users.banned == False,
                    Users.hidden == False,
                    Challenges.state == "visible",
                )
                .all()
            )
        elif user_mode == "teams":
            solve_matrix_data = (
                db.session.query(
                    Solves.account_id,
                    Solves.challenge_id,
                    Challenges.name.label("challenge_name"),
                )
                .join(Challenges, Challenges.id == Solves.challenge_id)
                .join(Teams, Teams.id == Solves.account_id)
                .filter(
                    Solves.account_id.in_(top_account_ids),
                    Teams.banned == False,
                    Teams.hidden == False,
                    Challenges.state == "visible",
                )
                .all()
            )
        elif user_mode == "hybrid":
            user_solve_matrix_data = (
                db.session.query(
                    Solves.account_id,
                    Solves.challenge_id,
                    Challenges.name.label("challenge_name"),
                )
                .join(Challenges, Challenges.id == Solves.challenge_id)
                .join(Users, Users.id == Solves.account_id)
                .filter(
                    Solves.account_id.in_(top_account_ids),
                    Users.banned == False,
                    Users.hidden == False,
                    Users.user_type == "individual",
                    Challenges.state == "visible",
                    Solves.user_id.isnot(None),  # Only individual user solves
                    Solves.team_id.is_(None),
                )
                .all()
            )
            team_solve_matrix_data = (
                db.session.query(
                    Solves.account_id,
                    Solves.challenge_id,
                    Challenges.name.label("challenge_name"),
                )
                .join(Challenges, Challenges.id == Solves.challenge_id)
                .join(Teams, Teams.id == Solves.account_id)
                .filter(
                    Solves.account_id.in_(top_account_ids),
                    Teams.banned == False,
                    Teams.hidden == False,
                    Teams.user_type == "team",
                    Challenges.state == "visible",
                    Solves.team_id.isnot(None),  # Only team solves
                    Solves.user_id.is_(None),
                )
                .all()
            )
            solve_matrix_data = user_solve_matrix_data + team_solve_matrix_data
        else:
            solve_matrix_data = [] # Fallback


        # Get attempt matrix data (fails) for top 100 accounts
        if user_mode == "users":
            attempt_matrix_data = (
                db.session.query(
                    Fails.account_id,
                    Fails.challenge_id,
                    Challenges.name.label("challenge_name"),
                )
                .join(Challenges, Challenges.id == Fails.challenge_id)
                .join(Users, Users.id == Fails.account_id)
                .filter(
                    Fails.account_id.in_(top_account_ids),
                    Users.banned == False,
                    Users.hidden == False,
                    Challenges.state == "visible",
                )
                .all()
            )
        elif user_mode == "teams":
            attempt_matrix_data = (
                db.session.query(
                    Fails.account_id,
                    Fails.challenge_id,
                    Challenges.name.label("challenge_name"),
                )
                .join(Challenges, Challenges.id == Fails.challenge_id)
                .join(Teams, Teams.id == Fails.account_id)
                .filter(
                    Fails.account_id.in_(top_account_ids),
                    Teams.banned == False,
                    Teams.hidden == False,
                    Challenges.state == "visible",
                )
                .all()
            )
        elif user_mode == "hybrid":
            user_attempt_matrix_data = (
                db.session.query(
                    Fails.account_id,
                    Fails.challenge_id,
                    Challenges.name.label("challenge_name"),
                )
                .join(Challenges, Challenges.id == Fails.challenge_id)
                .join(Users, Users.id == Fails.account_id)
                .filter(
                    Fails.account_id.in_(top_account_ids),
                    Users.banned == False,
                    Users.hidden == False,
                    Users.user_type == "individual",
                    Challenges.state == "visible",
                    Fails.user_id.isnot(None),  # Only individual user fails
                    Fails.team_id.is_(None),
                )
                .all()
            )
            team_attempt_matrix_data = (
                db.session.query(
                    Fails.account_id,
                    Fails.challenge_id,
                    Challenges.name.label("challenge_name"),
                )
                .join(Challenges, Challenges.id == Fails.challenge_id)
                .join(Teams, Teams.id == Fails.account_id)
                .filter(
                    Fails.account_id.in_(top_account_ids),
                    Teams.banned == False,
                    Teams.hidden == False,
                    Teams.user_type == "team",
                    Challenges.state == "visible",
                    Fails.team_id.isnot(None),  # Only team fails
                    Fails.user_id.is_(None),
                )
                .all()
            )
            attempt_matrix_data = user_attempt_matrix_data + team_attempt_matrix_data
        else:
            attempt_matrix_data = [] # Fallback


        # Get challenge opens matrix data for top 100 accounts
        # Need to handle mapping from user_id (in Tracking) to account_id (user or team)
        if user_mode == "teams":
            # In teams mode, map user_id to team_id (account_id)
            opens_matrix_data = (
                db.session.query(
                    Teams.id.label("account_id"),
                    Tracking.target.label("challenge_id"),
                )
                .join(Users, Users.id == Tracking.user_id)
                .join(Teams, Teams.id == Users.team_id)
                .join(Challenges, Challenges.id == Tracking.target)
                .filter(
                    Teams.id.in_(top_account_ids),
                    Users.banned == False,
                    Users.hidden == False,
                    Teams.banned == False,
                    Teams.hidden == False,
                    Challenges.state == "visible",
                    Tracking.target.isnot(None),  # Ensure target is not null
                    Tracking.type == "challenges.open",  # Only track challenge opens
                )
                .distinct()  # Remove duplicates if user opened same challenge multiple times
                .all()
            )
        elif user_mode == "users":
            # In users mode, user_id maps directly to account_id
            opens_matrix_data = (
                db.session.query(
                    Tracking.user_id.label("account_id"),
                    Tracking.target.label("challenge_id"),
                )
                .join(Users, Users.id == Tracking.user_id)
                .join(Challenges, Challenges.id == Tracking.target)
                .filter(
                    Tracking.user_id.in_(top_account_ids),
                    Users.banned == False,
                    Users.hidden == False,
                    Challenges.state == "visible",
                    Tracking.target.isnot(None),  # Ensure target is not null
                    Tracking.type == "challenges.open",  # Only track challenge opens
                )
                .distinct()  # Remove duplicates if user opened same challenge multiple times
                .all()
            )
        elif user_mode == "hybrid":
            # In hybrid mode, we need to consider both users and teams
            user_opens_matrix_data = (
                db.session.query(
                    Tracking.user_id.label("account_id"),
                    Tracking.target.label("challenge_id"),
                )
                .join(Users, Users.id == Tracking.user_id)
                .join(Challenges, Challenges.id == Tracking.target)
                .filter(
                    Tracking.user_id.in_(top_account_ids),
                    Users.banned == False,
                    Users.hidden == False,
                    Users.user_type == "individual",
                    Challenges.state == "visible",
                    Tracking.target.isnot(None),
                    Tracking.type == "challenges.open",
                )
                .distinct()
                .all()
            )
            team_opens_matrix_data = (
                db.session.query(
                    Teams.id.label("account_id"),
                    Tracking.target.label("challenge_id"),
                )
                .join(Users, Users.id == Tracking.user_id)
                .join(Teams, Teams.id == Users.team_id)
                .join(Challenges, Challenges.id == Tracking.target)
                .filter(
                    Teams.id.in_(top_account_ids),
                    Users.banned == False,
                    Users.hidden == False,
                    Teams.banned == False,
                    Teams.hidden == False,
                    Teams.user_type == "team",
                    Challenges.state == "visible",
                    Tracking.target.isnot(None),
                    Tracking.type == "challenges.open",
                )
                .distinct()
                .all()
            )
            opens_matrix_data = user_opens_matrix_data + team_opens_matrix_data
        else:
            opens_matrix_data = [] # Fallback


        # Build matrix data structure
        account_solves = {}
        for account in account_scores:
            account_solves[account.account_id] = {
                "name": account.name,
                "score": account.score,
                "solved_challenges": set(),
                "attempted_challenges": set(),
                "opened_challenges": set(),
            }

        for solve in solve_matrix_data:
            if solve.account_id in account_solves:
                account_solves[solve.account_id]["solved_challenges"].add(
                    solve.challenge_id
                )

        for attempt in attempt_matrix_data:
            if attempt.account_id in account_solves:
                account_solves[attempt.account_id]["attempted_challenges"].add(
                    attempt.challenge_id
                )

        for opens in opens_matrix_data:
            if opens.account_id in account_solves:
                account_solves[opens.account_id]["opened_challenges"].add(
                    opens.challenge_id
                )
    else:
        account_solves = {}

    db.session.close()

    return render_template(
        "admin/statistics.html",
        user_count=users_registered,
        team_count=teams_registered,
        ip_count=ip_count,
        wrong_count=wrong_count,
        solve_count=solve_count,
        challenge_count=challenge_count,
        total_points=total_points,
        solve_data=solve_data,
        most_solved=most_solved,
        least_solved=least_solved,
        top_users=account_scores,
        all_challenges=all_challenges,
        account_solves=account_solves,
    )
