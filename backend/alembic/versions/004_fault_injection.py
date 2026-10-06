"""Add fault_config to simulations for controlled fault injection."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004_fault_injection"
down_revision: Union[str, None] = "003_event_troubleshooting"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("simulations") as batch_op:
        batch_op.add_column(
            sa.Column("fault_config", sa.JSON(), nullable=False, server_default="{}")
        )


def downgrade() -> None:
    with op.batch_alter_table("simulations") as batch_op:
        batch_op.drop_column("fault_config")
