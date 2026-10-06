"""Add simulation runtime fields for Phase 6."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002_simulation_runtime"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("simulations") as batch_op:
        batch_op.add_column(
            sa.Column("scenario_ids", sa.JSON(), nullable=False, server_default="[]")
        )
        batch_op.add_column(sa.Column("random_seed", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column("runtime_state", sa.JSON(), nullable=False, server_default="{}")
        )

    op.execute(
        """
        UPDATE simulations
        SET scenario_ids = json_array(scenario_id)
        WHERE scenario_ids = '[]' OR scenario_ids IS NULL
        """
    )

    op.execute(
        """
        UPDATE simulations
        SET status = 'stopped'
        WHERE status IN ('draft', 'paused', 'archived', 'active', 'running')
        """
    )


def downgrade() -> None:
    with op.batch_alter_table("simulations") as batch_op:
        batch_op.drop_column("runtime_state")
        batch_op.drop_column("random_seed")
        batch_op.drop_column("scenario_ids")
