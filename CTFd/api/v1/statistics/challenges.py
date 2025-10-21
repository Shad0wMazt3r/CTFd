from flask import request
from flask_restx import Resource
from sqlalchemy import Integer, func
from sqlalchemy.sql import and_
from sqlalchemy.sql.expression import cast

from CTFd.api.v1.statistics import statistics_namespace
from CTFd.models import Challenges, Solves, Users, Teams, db
from CTFd.utils import get_config
from CTFd.utils.decorators import admins_only
from CTFd.utils.modes import get_model


@statistics_namespace.route("/challenges/<column>")
class ChallengePropertyCounts(Resource):
    @admins_only
    def get(self, column):
        # TODO: Probably rename this function in CTFd 4.0 as it can be used to do more than just counts now
        funcs = {
            "count": func.count,
            "sum": func.sum,
        }
        aggregate_func = funcs[request.args.get("function", "count")]
        if column in Challenges.__table__.columns.keys():
            c1 = getattr(Challenges, column)
            c2 = getattr(
                Challenges, request.args.get("target", "category"), Challenges.category
            )
            # We cast this to Integer to deal with cases where SQLAlchemy will give us a Decimal instead
            data = (
                Challenges.query.with_entities(c1, cast(aggregate_func(c2), Integer))
                .group_by(c1)
                .all()
            )
            return {"success": True, "data": dict(data)}
        else:
            response = {"message": "That could not be found"}, 404
            return response


@statistics_namespace.route("/challenges/solves")
class ChallengeSolveStatistics(Resource):
    @admins_only
    def get(self):
        chals = (
            Challenges.query.filter(
                and_(Challenges.state != "hidden", Challenges.state != "locked")
            )
            .order_by(Challenges.value)
            .all()
        )

        Model = get_model()
        user_mode = get_config("user_mode")

        if user_mode == "hybrid":
            # For hybrid mode, union individual user solves and team solves
            user_solves_sub = (
                db.session.query(
                    Solves.challenge_id, db.func.count(Solves.challenge_id).label("solves")
                )
                .join(Users, Solves.account_id == Users.id)
                .filter(
                    Users.banned == False, 
                    Users.hidden == False,
                    Users.user_type == "individual",
                    Solves.user_id.isnot(None),
                    Solves.team_id.is_(None),
                )
                .group_by(Solves.challenge_id)
            )
            
            team_solves_sub = (
                db.session.query(
                    Solves.challenge_id, db.func.count(Solves.challenge_id).label("solves")
                )
                .join(Teams, Solves.account_id == Teams.id)
                .filter(
                    Teams.banned == False, 
                    Teams.hidden == False,
                    Teams.user_type == "team",
                    Solves.team_id.isnot(None),
                    Solves.user_id.is_(None),
                )
                .group_by(Solves.challenge_id)
            )
            
            solves_sub = user_solves_sub.union_all(team_solves_sub).subquery()
        else:
            # Standard mode (users or teams)
            solves_sub = (
                db.session.query(
                    Solves.challenge_id, db.func.count(Solves.challenge_id).label("solves")
                )
                .join(Model, Solves.account_id == Model.id)
                .filter(Model.banned == False, Model.hidden == False)
                .group_by(Solves.challenge_id)
                .subquery()
            )

        solves = (
            db.session.query(
                solves_sub.columns.challenge_id,
                solves_sub.columns.solves,
                Challenges.name,
            )
            .join(Challenges, solves_sub.columns.challenge_id == Challenges.id)
            .all()
        )

        response = []
        has_solves = []

        for challenge_id, count, name in solves:
            challenge = {"id": challenge_id, "name": name, "solves": count}
            response.append(challenge)
            has_solves.append(challenge_id)
        for c in chals:
            if c.id not in has_solves:
                challenge = {"id": c.id, "name": c.name, "solves": 0}
                response.append(challenge)

        db.session.close()
        return {"success": True, "data": response}


@statistics_namespace.route("/challenges/solves/percentages")
class ChallengeSolvePercentages(Resource):
    @admins_only
    def get(self):
        challenges = (
            Challenges.query.add_columns(
                Challenges.id,
                Challenges.name,
                Challenges.state,
                Challenges.max_attempts,
            )
            .order_by(Challenges.value)
            .all()
        )

        Model = get_model()
        user_mode = get_config("user_mode")

        if user_mode == "hybrid":
            # For hybrid mode, count individual users and teams separately
            individual_accounts_with_points = (
                db.session.query(Solves.account_id)
                .join(Users, Solves.account_id == Users.id)
                .filter(
                    Users.banned == False, 
                    Users.hidden == False,
                    Users.user_type == "individual",
                    Solves.user_id.isnot(None),
                    Solves.team_id.is_(None),
                )
                .group_by(Solves.account_id)
                .count()
            )
            
            team_accounts_with_points = (
                db.session.query(Solves.account_id)
                .join(Teams, Solves.account_id == Teams.id)
                .filter(
                    Teams.banned == False, 
                    Teams.hidden == False,
                    Teams.user_type == "team",
                    Solves.team_id.isnot(None),
                    Solves.user_id.is_(None),
                )
                .group_by(Solves.account_id)
                .count()
            )
            
            teams_with_points = individual_accounts_with_points + team_accounts_with_points
        else:
            # Standard mode (users or teams)
            teams_with_points = (
                db.session.query(Solves.account_id)
                .join(Model)
                .filter(Model.banned == False, Model.hidden == False)
                .group_by(Solves.account_id)
                .count()
            )

        percentage_data = []
        for challenge in challenges:
            if user_mode == "hybrid":
                # For hybrid mode, count individual and team solves separately
                individual_solve_count = (
                    Solves.query.join(Users, Solves.account_id == Users.id)
                    .filter(
                        Solves.challenge_id == challenge.id,
                        Users.banned == False,
                        Users.hidden == False,
                        Users.user_type == "individual",
                        Solves.user_id.isnot(None),
                        Solves.team_id.is_(None),
                    )
                    .count()
                )
                
                team_solve_count = (
                    Solves.query.join(Teams, Solves.account_id == Teams.id)
                    .filter(
                        Solves.challenge_id == challenge.id,
                        Teams.banned == False,
                        Teams.hidden == False,
                        Teams.user_type == "team",
                        Solves.team_id.isnot(None),
                        Solves.user_id.is_(None),
                    )
                    .count()
                )
                
                solve_count = individual_solve_count + team_solve_count
            else:
                # Standard mode (users or teams)
                solve_count = (
                    Solves.query.join(Model, Solves.account_id == Model.id)
                    .filter(
                        Solves.challenge_id == challenge.id,
                        Model.banned == False,
                        Model.hidden == False,
                    )
                    .count()
                )

            if teams_with_points > 0:
                percentage = float(solve_count) / float(teams_with_points)
            else:
                percentage = 0.0

            percentage_data.append(
                {"id": challenge.id, "name": challenge.name, "percentage": percentage}
            )

        response = sorted(percentage_data, key=lambda x: x["percentage"], reverse=True)
        return {"success": True, "data": response}
