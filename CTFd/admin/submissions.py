from flask import render_template, request, url_for

from CTFd.admin import admin
from CTFd.models import Challenges, Submissions, Users, Teams
from CTFd.utils.decorators import admins_only
from CTFd.utils.helpers.models import build_model_filters
from CTFd.utils.modes import get_model
from CTFd.utils.config import is_hybrid_mode


@admin.route("/admin/submissions", defaults={"submission_type": None})
@admin.route("/admin/submissions/<submission_type>")
@admins_only
def submissions_listing(submission_type):
    filters_by = {}
    if submission_type:
        filters_by["type"] = submission_type
    filters = []

    q = request.args.get("q")
    field = request.args.get("field")
    page = abs(request.args.get("page", 1, type=int))

    filters = build_model_filters(
        model=Submissions,
        query=q,
        field=field,
        extra_columns={
            "challenge_name": Challenges.name,
            "account_id": Submissions.account_id,
        },
    )

    Model = get_model()

    if is_hybrid_mode():
        # In hybrid mode, we need to handle both users and teams
        # Use outerjoin to get submissions from both individual users and teams
        submissions = (
            Submissions.query.filter_by(**filters_by)
            .filter(*filters)
            .join(Challenges)
            .outerjoin(Users, Submissions.user_id == Users.id)
            .outerjoin(Teams, Submissions.team_id == Teams.id)
            .order_by(Submissions.date.desc())
            .paginate(page=page, per_page=50, error_out=False)
        )
    else:
        if Model:
            submissions = (
                Submissions.query.filter_by(**filters_by)
                .filter(*filters)
                .join(Challenges)
                .join(Model)
                .order_by(Submissions.date.desc())
                .paginate(page=page, per_page=50, error_out=False)
            )
        else:
            # Fallback for cases where Model is None (shouldn't happen in non-hybrid modes)
            submissions = (
                Submissions.query.filter_by(**filters_by)
                .filter(*filters)
                .join(Challenges)
                .order_by(Submissions.date.desc())
                .paginate(page=page, per_page=50, error_out=False)
            )

    args = dict(request.args)
    args.pop("page", 1)

    return render_template(
        "admin/submissions.html",
        submissions=submissions,
        prev_page=url_for(
            request.endpoint,
            submission_type=submission_type,
            page=submissions.prev_num,
            **args
        ),
        next_page=url_for(
            request.endpoint,
            submission_type=submission_type,
            page=submissions.next_num,
            **args
        ),
        type=submission_type,
        q=q,
        field=field,
    )
