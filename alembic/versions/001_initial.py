"""Initial schema for the YouTube channel engine."""

from alembic import op

revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    from core.db import Base
    import core.models  # noqa: F401
    import youtube.models  # noqa: F401

    bind = op.get_bind()
    Base.metadata.create_all(bind)


def downgrade() -> None:
    from core.db import Base
    import core.models  # noqa: F401
    import youtube.models  # noqa: F401

    bind = op.get_bind()
    Base.metadata.drop_all(bind)
