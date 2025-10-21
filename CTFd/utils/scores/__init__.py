from sqlalchemy.sql.expression import union_all

from CTFd.cache import cache
from CTFd.models import Awards, Brackets, Challenges, Solves, Teams, Users, db
from CTFd.utils import get_config
from CTFd.utils.dates import unix_time_to_utc
from CTFd.utils.modes import get_model


class IndividualStanding:
    def __init__(self, individual):
        self.account_id = individual.user_id
        self.name = individual.name
        self.score = individual.score
        self.bracket_id = individual.bracket_id
        self.bracket_name = individual.bracket_name


class TeamStanding:
    def __init__(self, team):
        self.account_id = team.team_id
        self.name = team.name
        self.score = team.score
        self.bracket_id = team.bracket_id
        self.bracket_name = team.bracket_name


@cache.memoize(timeout=60)
def get_standings(count=None, bracket_id=None, admin=False, fields=None):
    """
    Get standings as a list of tuples containing account_id, name, and score e.g. [(account_id, team_name, score)].

    Ties are broken by who reached a given score first based on the solve ID. Two users can have the same score but one
    user will have a solve ID that is before the others. That user will be considered the tie-winner.

    Challenges & Awards with a value of zero are filtered out of the calculations to avoid incorrect tie breaks.
    """
    from CTFd.utils.modes import HYBRID_MODE

    # Handle hybrid mode with separate individual and team standings
    if get_config("user_mode") == HYBRID_MODE:
        individual_standings = get_hybrid_individual_standings(count=count, bracket_id=bracket_id, admin=admin, fields=fields)
        team_standings = get_hybrid_team_standings(count=count, bracket_id=bracket_id, admin=admin, fields=fields)

        combined_standings = []
        for individual in individual_standings:
            combined_standings.append(IndividualStanding(individual))

        for team in team_standings:
            combined_standings.append(TeamStanding(team))

        # Sort combined standings by score (descending) and then by date (ascending)
        combined_standings.sort(key=lambda x: (x.score, x.account_id), reverse=True)
        return combined_standings

    if fields is None:
        fields = []
    Model = get_model()

    scores = (
        db.session.query(
            Solves.account_id.label("account_id"),
            db.func.sum(Challenges.value).label("score"),
            db.func.max(Solves.id).label("id"),
            db.func.max(Solves.date).label("date"),
        )
        .join(Challenges)
        .filter(Challenges.value != 0)
        .group_by(Solves.account_id)
    )

    awards = (
        db.session.query(
            Awards.account_id.label("account_id"),
            db.func.sum(Awards.value).label("score"),
            db.func.max(Awards.id).label("id"),
            db.func.max(Awards.date).label("date"),
        )
        .filter(Awards.value != 0)
        .group_by(Awards.account_id)
    )

    """
    Filter out solves and awards that are before a specific time point.
    """
    freeze = get_config("freeze")
    if not admin and freeze:
        scores = scores.filter(Solves.date < unix_time_to_utc(freeze))
        awards = awards.filter(Awards.date < unix_time_to_utc(freeze))

    """
    Combine awards and solves with a union. They should have the same amount of columns
    """
    results = union_all(scores, awards).alias("results")

    """
    Sum each of the results by the team id to get their score.
    """
    sumscores = (
        db.session.query(
            results.columns.account_id,
            db.func.sum(results.columns.score).label("score"),
            db.func.max(results.columns.id).label("id"),
            db.func.max(results.columns.date).label("date"),
        )
        .group_by(results.columns.account_id)
        .subquery()
    )

    """
    Admins can see scores for all users but the public cannot see banned users.

    Filters out banned users.
    Properly resolves value ties by ID.

    Different databases treat time precision differently so resolve by the row ID instead.
    """
    if admin:
        standings_query = (
            db.session.query(
                Model.id.label("account_id"),
                Model.oauth_id.label("oauth_id"),
                Model.name.label("name"),
                Model.bracket_id.label("bracket_id"),
                Brackets.name.label("bracket_name"),
                Model.hidden,
                Model.banned,
                sumscores.columns.score,
                *fields,
            )
            .join(sumscores, Model.id == sumscores.columns.account_id)
            .join(Brackets, isouter=True)
            .order_by(
                sumscores.columns.score.desc(),
                sumscores.columns.date.asc(),
                sumscores.columns.id.asc(),
            )
        )
    else:
        standings_query = (
            db.session.query(
                Model.id.label("account_id"),
                Model.oauth_id.label("oauth_id"),
                Model.name.label("name"),
                Model.bracket_id.label("bracket_id"),
                Brackets.name.label("bracket_name"),
                sumscores.columns.score,
                *fields,
            )
            .join(sumscores, Model.id == sumscores.columns.account_id)
            .join(Brackets, isouter=True)
            .filter(Model.banned == False, Model.hidden == False)
            .order_by(
                sumscores.columns.score.desc(),
                sumscores.columns.date.asc(),
                sumscores.columns.id.asc(),
            )
        )

    # Filter on a bracket if asked
    if bracket_id is not None:
        standings_query = standings_query.filter(Model.bracket_id == bracket_id)

    # Only select a certain amount of users if asked.
    if count is None:
        standings = standings_query.all()
    else:
        standings = standings_query.limit(count).all()

    return standings


@cache.memoize(timeout=60)
def get_hybrid_individual_standings(count=None, bracket_id=None, admin=False, fields=None):
    """
    Get individual user standings for hybrid mode.
    Only includes users with user_type = 'individual' and no team_id.
    """
    if fields is None:
        fields = []

    scores = (
        db.session.query(
            Users.id.label("user_id"),
            db.func.sum(Challenges.value).label("score"),
            db.func.max(Solves.id).label("id"),
            db.func.max(Solves.date).label("date"),
        )
        .join(Solves, Users.id == Solves.user_id)  # Join on user_id directly for individual users
        .join(Challenges, Solves.challenge_id == Challenges.id)
        .filter(
            Challenges.value != 0,
            Users.user_type == 'individual',
            Users.team_id.is_(None),    # Only individual users, not team members
            Solves.user_id.isnot(None), # Only individual user solves
            Solves.team_id.is_(None),
        )
        .group_by(Users.id)
    )

    awards = (
        db.session.query(
            Users.id.label("user_id"),
            db.func.sum(Awards.value).label("score"),
            db.func.max(Awards.id).label("id"),
            db.func.max(Awards.date).label("date"),
        )
        .join(Awards, Users.id == Awards.user_id)  # Join on user_id directly for individual users
        .filter(
            Awards.value != 0,
            Users.user_type == 'individual',
            Users.team_id.is_(None),    # Only individual users, not team members
            Awards.user_id.isnot(None), # Only individual user awards
            Awards.team_id.is_(None),
        )
        .group_by(Users.id)
    )

    freeze = get_config("freeze")
    if not admin and freeze:
        scores = scores.filter(Solves.date < unix_time_to_utc(freeze))
        awards = awards.filter(Awards.date < unix_time_to_utc(freeze))

    results = union_all(scores, awards).alias("results")

    sumscores = (
        db.session.query(
            results.columns.user_id,
            db.func.sum(results.columns.score).label("score"),
            db.func.max(results.columns.id).label("id"),
            db.func.max(results.columns.date).label("date"),
        )
        .group_by(results.columns.user_id)
        .subquery()
    )

    if admin:
        standings_query = (
            db.session.query(
                Users.id.label("user_id"),
                Users.oauth_id.label("oauth_id"),
                Users.name.label("name"),
                Users.team_id.label("team_id"),
                Users.bracket_id.label("bracket_id"),
                Brackets.name.label("bracket_name"),
                Users.hidden,
                Users.banned,
                sumscores.columns.score,
                *fields,
            )
            .join(sumscores, Users.id == sumscores.columns.user_id)
            .join(Brackets, isouter=True)
            .order_by(
                sumscores.columns.score.desc(),
                sumscores.columns.date.asc(),
                sumscores.columns.id.asc(),
            )
        )
    else:
        standings_query = (
            db.session.query(
                Users.id.label("user_id"),
                Users.oauth_id.label("oauth_id"),
                Users.name.label("name"),
                Users.team_id.label("team_id"),
                Users.bracket_id.label("bracket_id"),
                Brackets.name.label("bracket_name"),
                sumscores.columns.score,
                *fields,
            )
            .join(sumscores, Users.id == sumscores.columns.user_id)
            .join(Brackets, isouter=True)
            .filter(Users.banned == False, Users.hidden == False)
            .filter(Users.user_type == 'individual')
            .filter(Users.team_id.is_(None))  # Only individual users, not team members
            .order_by(
                sumscores.columns.score.desc(),
                sumscores.columns.date.asc(),
                sumscores.columns.id.asc(),
            )
        )

    if bracket_id is not None:
        standings_query = standings_query.filter(Users.bracket_id == bracket_id)

    if count is None:
        standings = standings_query.all()
    else:
        standings = standings_query.limit(count).all()

    return standings


@cache.memoize(timeout=60)
def get_hybrid_team_standings(count=None, bracket_id=None, admin=False, fields=None):
    """
    Get team standings for hybrid mode.
    Only includes teams and their members' aggregated scores.
    """
    if fields is None:
        fields = []

    # Get scores from team solves (solves attributed directly to teams)
    scores = (
        db.session.query(
            Teams.id.label("team_id"),
            db.func.sum(Challenges.value).label("score"),
            db.func.max(Solves.id).label("id"),
            db.func.max(Solves.date).label("date"),
        )
        .join(Solves, Teams.id == Solves.team_id)  # Join on team_id directly for team solves
        .join(Challenges, Solves.challenge_id == Challenges.id)
        .filter(
            Challenges.value != 0,
            Teams.user_type == 'team',
            Solves.team_id.isnot(None),  # Only team solves
            Solves.user_id.is_(None),
        )
        .group_by(Teams.id)
    )

    awards = (
        db.session.query(
            Teams.id.label("team_id"),
            db.func.sum(Awards.value).label("score"),
            db.func.max(Awards.id).label("id"),
            db.func.max(Awards.date).label("date"),
        )
        .join(Awards, Teams.id == Awards.team_id)  # Join on team_id directly for team awards
        .filter(
            Awards.value != 0,
            Teams.user_type == 'team',
            Awards.team_id.isnot(None),  # Only team awards
            Awards.user_id.is_(None),
        )
        .group_by(Teams.id)
    )

    freeze = get_config("freeze")
    if not admin and freeze:
        scores = scores.filter(Solves.date < unix_time_to_utc(freeze))
        awards = awards.filter(Awards.date < unix_time_to_utc(freeze))

    results = union_all(scores, awards).alias("results")

    sumscores = (
        db.session.query(
            results.columns.team_id,
            db.func.sum(results.columns.score).label("score"),
            db.func.max(results.columns.id).label("id"),
            db.func.max(results.columns.date).label("date"),
        )
        .group_by(results.columns.team_id)
        .subquery()
    )

    if admin:
        standings_query = (
            db.session.query(
                Teams.id.label("team_id"),
                Teams.oauth_id.label("oauth_id"),
                Teams.name.label("name"),
                Teams.bracket_id.label("bracket_id"),
                Brackets.name.label("bracket_name"),
                Teams.hidden,
                Teams.banned,
                sumscores.columns.score,
                *fields,
            )
            .join(sumscores, Teams.id == sumscores.columns.team_id)
            .join(Brackets, isouter=True)
            .order_by(
                sumscores.columns.score.desc(),
                sumscores.columns.date.asc(),
                sumscores.columns.id.asc(),
            )
        )
    else:
        standings_query = (
            db.session.query(
                Teams.id.label("team_id"),
                Teams.oauth_id.label("oauth_id"),
                Teams.name.label("name"),
                Teams.bracket_id.label("bracket_id"),
                Brackets.name.label("bracket_name"),
                sumscores.columns.score,
                *fields,
            )
            .join(sumscores, Teams.id == sumscores.columns.team_id)
            .join(Brackets, isouter=True)
            .filter(Teams.banned == False)
            .filter(Teams.hidden == False)
            .order_by(
                sumscores.columns.score.desc(),
                sumscores.columns.date.asc(),
                sumscores.columns.id.asc(),
            )
        )

    if bracket_id is not None:
        standings_query = standings_query.filter(Teams.bracket_id == bracket_id)

    if count is None:
        standings = standings_query.all()
    else:
        standings = standings_query.limit(count).all()

    return standings


@cache.memoize(timeout=60)
def get_team_standings(count=None, bracket_id=None, admin=False, fields=None):
    if fields is None:
        fields = []
    scores = (
        db.session.query(
            Solves.team_id.label("team_id"),
            db.func.sum(Challenges.value).label("score"),
            db.func.max(Solves.id).label("id"),
            db.func.max(Solves.date).label("date"),
        )
        .join(Challenges)
        .filter(Challenges.value != 0)
        .group_by(Solves.team_id)
    )

    awards = (
        db.session.query(
            Awards.team_id.label("team_id"),
            db.func.sum(Awards.value).label("score"),
            db.func.max(Awards.id).label("id"),
            db.func.max(Awards.date).label("date"),
        )
        .filter(Awards.value != 0)
        .group_by(Awards.team_id)
    )

    freeze = get_config("freeze")
    if not admin and freeze:
        scores = scores.filter(Solves.date < unix_time_to_utc(freeze))
        awards = awards.filter(Awards.date < unix_time_to_utc(freeze))

    results = union_all(scores, awards).alias("results")

    sumscores = (
        db.session.query(
            results.columns.team_id,
            db.func.sum(results.columns.score).label("score"),
            db.func.max(results.columns.id).label("id"),
            db.func.max(results.columns.date).label("date"),
        )
        .group_by(results.columns.team_id)
        .subquery()
    )

    if admin:
        standings_query = (
            db.session.query(
                Teams.id.label("team_id"),
                Teams.oauth_id.label("oauth_id"),
                Teams.name.label("name"),
                Teams.bracket_id.label("bracket_id"),
                Brackets.name.label("bracket_name"),
                Teams.hidden,
                Teams.banned,
                sumscores.columns.score,
                *fields,
            )
            .join(sumscores, Teams.id == sumscores.columns.team_id)
            .join(Brackets, isouter=True)
            .order_by(
                sumscores.columns.score.desc(),
                sumscores.columns.date.asc(),
                sumscores.columns.id.asc(),
            )
        )
    else:
        standings_query = (
            db.session.query(
                Teams.id.label("team_id"),
                Teams.oauth_id.label("oauth_id"),
                Teams.name.label("name"),
                Teams.bracket_id.label("bracket_id"),
                Brackets.name.label("bracket_name"),
                sumscores.columns.score,
                *fields,
            )
            .join(sumscores, Teams.id == sumscores.columns.team_id)
            .join(Brackets, isouter=True)
            .filter(Teams.banned == False)
            .filter(Teams.hidden == False)
            .order_by(
                sumscores.columns.score.desc(),
                sumscores.columns.date.asc(),
                sumscores.columns.id.asc(),
            )
        )

    if bracket_id is not None:
        standings_query = standings_query.filter(Teams.bracket_id == bracket_id)

    if count is None:
        standings = standings_query.all()
    else:
        standings = standings_query.limit(count).all()

    return standings


@cache.memoize(timeout=60)
def get_user_standings(count=None, bracket_id=None, admin=False, fields=None):
    if fields is None:
        fields = []
    scores = (
        db.session.query(
            Solves.user_id.label("user_id"),
            db.func.sum(Challenges.value).label("score"),
            db.func.max(Solves.id).label("id"),
            db.func.max(Solves.date).label("date"),
        )
        .join(Challenges)
        .filter(Challenges.value != 0)
        .group_by(Solves.user_id)
    )

    awards = (
        db.session.query(
            Awards.user_id.label("user_id"),
            db.func.sum(Awards.value).label("score"),
            db.func.max(Awards.id).label("id"),
            db.func.max(Awards.date).label("date"),
        )
        .filter(Awards.value != 0)
        .group_by(Awards.user_id)
    )

    freeze = get_config("freeze")
    if not admin and freeze:
        scores = scores.filter(Solves.date < unix_time_to_utc(freeze))
        awards = awards.filter(Awards.date < unix_time_to_utc(freeze))

    results = union_all(scores, awards).alias("results")

    sumscores = (
        db.session.query(
            results.columns.user_id,
            db.func.sum(results.columns.score).label("score"),
            db.func.max(results.columns.id).label("id"),
            db.func.max(results.columns.date).label("date"),
        )
        .group_by(results.columns.user_id)
        .subquery()
    )

    if admin:
        standings_query = (
            db.session.query(
                Users.id.label("user_id"),
                Users.oauth_id.label("oauth_id"),
                Users.name.label("name"),
                Users.team_id.label("team_id"),
                Users.bracket_id.label("bracket_id"),
                Brackets.name.label("bracket_name"),
                Users.hidden,
                Users.banned,
                sumscores.columns.score,
                *fields,
            )
            .join(sumscores, Users.id == sumscores.columns.user_id)
            .join(Brackets, isouter=True)
            .order_by(
                sumscores.columns.score.desc(),
                sumscores.columns.date.asc(),
                sumscores.columns.id.asc(),
            )
        )
    else:
        standings_query = (
            db.session.query(
                Users.id.label("user_id"),
                Users.oauth_id.label("oauth_id"),
                Users.name.label("name"),
                Users.team_id.label("team_id"),
                Users.bracket_id.label("bracket_id"),
                Brackets.name.label("bracket_name"),
                sumscores.columns.score,
                *fields,
            )
            .join(sumscores, Users.id == sumscores.columns.user_id)
            .join(Brackets, isouter=True)
            .filter(Users.banned == False, Users.hidden == False)
            .order_by(
                sumscores.columns.score.desc(),
                sumscores.columns.date.asc(),
                sumscores.columns.id.asc(),
            )
        )

    if bracket_id is not None:
        standings_query = standings_query.filter(Users.bracket_id == bracket_id)

    if count is None:
        standings = standings_query.all()
    else:
        standings = standings_query.limit(count).all()

    return standings
