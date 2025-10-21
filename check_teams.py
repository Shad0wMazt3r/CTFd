from CTFd import create_app
app = create_app()
with app.app_context():
    from CTFd.models import Users, Teams, Solves, db
    from CTFd.utils.scores import get_hybrid_team_standings
    
    # Check existing users and teams
    users = Users.query.all()
    print('Users:')
    for user in users:
        print(f'  ID: {user.id}, Name: {user.name}, Type: {user.user_type}, Team ID: {user.team_id}')
    
    teams = Teams.query.all()
    print('\nTeams:')
    for team in teams:
        print(f'  ID: {team.id}, Name: {team.name}, Type: {team.user_type}')
    
    # Check existing solves
    solves = Solves.query.all()
    print('\nSolves:')
    for solve in solves:
        print(f'  User ID: {solve.user_id}, Team ID: {solve.team_id}, Challenge: {solve.challenge_id}')
    
    # Check team standings
    print('\nTeam standings:')
    try:
        team_standings = get_hybrid_team_standings()
        print(f'Count: {len(team_standings)}')
        for standing in team_standings:
            print(f'  Team: {standing.name}, Score: {standing.score}')
    except Exception as e:
        print(f'Error: {e}')