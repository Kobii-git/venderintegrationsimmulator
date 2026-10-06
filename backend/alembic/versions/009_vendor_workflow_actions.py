"""Add vendor workflow action metadata to event history."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "009_vendor_workflow_actions"
down_revision: Union[str, None] = "008_materialized_pull_datasets"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("event_instances") as batch:
        batch.add_column(
            sa.Column("event_kind", sa.String(length=32), nullable=False, server_default="scenario")
        )
        batch.add_column(sa.Column("action_id", sa.String(length=64), nullable=True))
        batch.create_index("ix_event_instances_action_id", ["action_id"])


def downgrade() -> None:
    with op.batch_alter_table("event_instances") as batch:
        batch.drop_index("ix_event_instances_action_id")
        batch.drop_column("action_id")
        batch.drop_column("event_kind")
