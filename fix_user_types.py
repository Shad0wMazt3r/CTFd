#!/usr/bin/env python
# Fix current user data by updating user_type for team members

from CTFd import create_app
from CTFd.models import Users, Teams, db
from CTFd.utils import get_config

app = create_app()

with app.app_context():
    user_mode = get_config("user_mode")
    print(f"User mode: {user_mode}")
    
    if user_mode == "hybrid":
        # Find all users who are team members but have incorrect user_type
        users_to_fix = Users.query.filter(
            Users.team_id.isnot(None),
            Users.user_type == "individual"
        ).all()
        
        print(f"\nFound {len(users_to_fix)} users with incorrect user_type:")
        for user in users_to_fix:
            team = Teams.query.filter_by(id=user.team_id).first()
            print(f"  User: {user.name} (ID: {user.id}) is in team {team.name} but user_type is '{user.user_type}'")
            user.user_type = "team_member"
            print(f"    Fixed user_type to 'team_member'")
        
        if users_to_fix:
            db.session.commit()
            print(f"\nFixed {len(users_to_fix)} users' user_type")
        else:
            print("\nNo users need fixing")
    else:
        print("Not in hybrid mode, no fixes needed")