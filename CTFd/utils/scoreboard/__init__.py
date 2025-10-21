from collections import defaultdict

from CTFd.cache import cache
from CTFd.models import Awards, Solves
from CTFd.utils import get_config
from CTFd.utils.dates import isoformat, unix_time_to_utc
from CTFd.utils.modes import generate_account_url, HYBRID_MODE
from CTFd.utils.scores import get_standings


@cache.memoize(timeout=60)
def get_scoreboard_detail(count, bracket_id=None):
    response = {}

    standings_data = get_standings(count=count, bracket_id=bracket_id)

    standings = standings_data

    team_ids = [team.account_id for team in standings]

    user_mode = get_config("user_mode")

    if user_mode == "users":
        solves = Solves.query.filter(Solves.user_id.in_(team_ids))
    elif user_mode == "teams":
        solves = Solves.query.filter(Solves.team_id.in_(team_ids))
    elif user_mode == "hybrid":
        # In hybrid mode, team_ids contains both user_ids and team_ids
        # We need to filter Solves by user_id if the account is a user, and by team_id if the account is a team
        # This requires a more complex filter or separate queries
        user_solves = Solves.query.filter(Solves.user_id.in_(team_ids))
        team_solves = Solves.query.filter(Solves.team_id.in_(team_ids))
        solves = user_solves.union_all(team_solves)
    else:
        solves = Solves.query.filter(Solves.account_id.in_(team_ids))
    if user_mode == "users":
        awards = Awards.query.filter(Awards.user_id.in_(team_ids))
    elif user_mode == "teams":
        awards = Awards.query.filter(Awards.team_id.in_(team_ids))
    elif user_mode == "hybrid":
        user_awards = Awards.query.filter(Awards.user_id.in_(team_ids))
        team_awards = Awards.query.filter(Awards.team_id.in_(team_ids))
        awards = user_awards.union_all(team_awards)
    else:
        awards = Awards.query.filter(Awards.account_id.in_(team_ids))

    freeze = get_config("freeze")

    if freeze:
        solves = solves.filter(Solves.date < unix_time_to_utc(freeze))
        awards = awards.filter(Awards.date < unix_time_to_utc(freeze))

    solves = solves.all()
    awards = awards.all()

    # Build a mapping of accounts to their solves and awards
    solves_mapper = defaultdict(list)
    for solve in solves:
        solves_mapper[solve.account_id].append(
            {
                "challenge_id": solve.challenge_id,
                "account_id": solve.account_id,
                "team_id": solve.team_id,
                "user_id": solve.user_id,
                "value": solve.challenge.value,
                "date": isoformat(solve.date),
            }
        )

    for award in awards:
        solves_mapper[award.account_id].append(
            {
                "challenge_id": None,
                "account_id": award.account_id,
                "team_id": award.team_id,
                "user_id": award.user_id,
                "value": award.value,
                "date": isoformat(award.date),
            }
        )

    # Sort all solves by date
    for team_id in solves_mapper:
        solves_mapper[team_id] = sorted(solves_mapper[team_id], key=lambda k: k["date"])

    for i, x in enumerate(standings):
        response[i + 1] = {
            "id": x.account_id,
            "account_url": generate_account_url(account_id=x.account_id),
            "name": x.name,
            "score": int(x.score),
            "bracket_id": x.bracket_id,
            "bracket_name": x.bracket_name,
            "solves": solves_mapper.get(x.account_id, []),
        }

    return response
