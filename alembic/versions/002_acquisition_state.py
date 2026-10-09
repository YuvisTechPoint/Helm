"""Historical migration — retained for revision chain (acquisition engine removed)."""

from alembic import op

revision = "002_acquisition_state"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
