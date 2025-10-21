"""Add user_type fields for hybrid mode

Revision ID: a1b2c3d4e5f6
Revises: 67ebab6de598
Create Date: 2025-10-20 12:52:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "67ebab6de598"
branch_labels = None
depends_on = None

def upgrade():
    """Add user_type columns to users and teams tables for hybrid mode support."""

    # Add user_type column to users table
    # Values: 'individual' or 'team_member'
    op.add_column('users', sa.Column('user_type', sa.String(20), nullable=True, default='individual'))

    # Add user_type column to teams table
    # Values: 'team'
    op.add_column('teams', sa.Column('user_type', sa.String(20), nullable=True, default='team'))

    # Update existing users to have user_type based on current mode
    # In users mode: all users are 'individual'
    # In teams mode: users with team_id are 'team_member', others are 'individual'
    # In hybrid mode: will be set during user creation

    # Set default user_type for existing users
    # Users with team_id will be 'team_member', others 'individual'
    op.execute("UPDATE users SET user_type = CASE WHEN team_id IS NOT NULL THEN 'team_member' ELSE 'individual' END")

    # Set user_type for all teams to 'team'
    op.execute("UPDATE teams SET user_type = 'team'")

    # Make user_type NOT NULL after setting defaults
    op.alter_column('users', 'user_type', nullable=False)
    op.alter_column('teams', 'user_type', nullable=False)


def downgrade():
    """Remove user_type columns."""

    op.drop_column('teams', 'user_type')
    op.drop_column('users', 'user_type')
