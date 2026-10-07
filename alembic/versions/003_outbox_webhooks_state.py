"""Outbox, webhook receipts, and state transition audit tables."""

import sqlalchemy as sa
from alembic import op

revision = "003_outbox_webhooks_state"
down_revision = "002_acquisition_state"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from core.db import Base
    import core.models  # noqa: F401

    bind = op.get_bind()
    for table in ("outbox", "webhook_receipts", "state_transitions"):
        Base.metadata.tables[table].create(bind, checkfirst=True)


def downgrade() -> None:
    from core.db import Base
    import core.models  # noqa: F401

    bind = op.get_bind()
    for table in ("state_transitions", "webhook_receipts", "outbox"):
        Base.metadata.tables[table].drop(bind, checkfirst=True)
