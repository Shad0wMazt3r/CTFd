#!/usr/bin/env python
# Check user and team data

from CTFd import create_app
from CTFd.models import Users, Teams, Solves, db
from CTFd.utils import get_config

app = create_app()

with app.app_context():
    # Check configuration
    user_mode = get_config("user_mode")
    print(f"User mode: {user_mode}")
    
    # Get all users
    users = Users.query.all()
    print(f"\nUsers ({len(users)}):")
    for user in users:
        team = Teams.query.filter_by(id=user.team_id).first() if user.team_id else None
        print(f"  ID: {user.id}, Name: {user.name}, Team ID: {user.team_id}, User Type: {user.user_type}")
        if team:
            print(f"    Team: {team.name}")
    
    # Get all teams
    teams = Teams.query.all()
    print(f"\nTeams ({len(teams)}):")
    for team in teams:
        members = Users.query.filter_by(team_id=team.id).all()
        print(f"  ID: {team.id}, Name: {team.name}, Members: {len(members)}")
        for member in members:
            print(f"    Member: {member.name} (ID: {member.id}, Type: {member.user_type})")
    
    # Get all solves
    solves = Solves.query.all()
    print(f"\nSolves ({len(solves)}):")
    for solve in solves:
        print(f"  ID: {solve.id}, Challenge: {solve.challenge_id}, User ID: {solve.user_id}, Team ID: {solve.team_id}")