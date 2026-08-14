"""add conversation cleanup index

Revision ID: 56124e050600
Revises: a1c7f4e9b3d2
Create Date: 2026-08-14 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "56124e050600"
down_revision = "a1c7f4e9b3d2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        "conversation_is_deleted_updated_at_idx",
        "conversations",
        ["is_deleted", "updated_at"],
        unique=False,
        postgresql_where=sa.text("is_deleted IS true"),
    )


def downgrade():
    op.drop_index("conversation_is_deleted_updated_at_idx", table_name="conversations")
