"""Acquisition learning-state table and consent audit fields."""

import sqlalchemy as sa
from alembic import op

revision = "002_acquisition_state"
down_revision = "001_initial"
branch_labels = None
depends_on = None

CONSENT_COLUMNS = (
    ("source", sa.String(64)),
    ("evidence", sa.Text()),
    ("recorded_at", sa.String(40)),
    ("withdrawn_at", sa.String(40)),
)


def upgrade() -> None:
    from core.db import Base
    import acquisition.models  # noqa: F401

    bind = op.get_bind()
    Base.metadata.tables["acq_state"].create(bind, checkfirst=True)
    existing = {column["name"] for column in sa.inspect(bind).get_columns("consents")}
    for name, column_type in CONSENT_COLUMNS:
        if name not in existing:
            op.add_column("consents", sa.Column(name, column_type, nullable=True))


def downgrade() -> None:
    from core.db import Base
    import acquisition.models  # noqa: F401

    bind = op.get_bind()
    existing = {column["name"] for column in sa.inspect(bind).get_columns("consents")}
    for name, _ in CONSENT_COLUMNS:
        if name in existing:
            op.drop_column("consents", name)
    Base.metadata.tables["acq_state"].drop(bind, checkfirst=True)
