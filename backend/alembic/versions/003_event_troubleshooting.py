"""Add troubleshooting fields for event history, replay, and delivery inspection."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003_event_troubleshooting"
down_revision: Union[str, None] = "002_simulation_runtime"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("event_instances") as batch_op:
        batch_op.add_column(
            sa.Column(
                "payload_source",
                sa.String(length=32),
                nullable=False,
                server_default="generated",
            )
        )
        batch_op.add_column(
            sa.Column("replayed_from_event_id", sa.String(length=36), nullable=True)
        )
        batch_op.add_column(
            sa.Column("simulator_metadata", sa.JSON(), nullable=False, server_default="{}")
        )

    with op.batch_alter_table("delivery_attempts") as batch_op:
        batch_op.add_column(
            sa.Column(
                "request_query_params_redacted",
                sa.JSON(),
                nullable=False,
                server_default="{}",
            )
        )

    op.create_index(
        "ix_event_instances_payload_source",
        "event_instances",
        ["payload_source"],
    )
    op.create_index(
        "ix_event_instances_replayed_from",
        "event_instances",
        ["replayed_from_event_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_event_instances_replayed_from", table_name="event_instances")
    op.drop_index("ix_event_instances_payload_source", table_name="event_instances")
    with op.batch_alter_table("delivery_attempts") as batch_op:
        batch_op.drop_column("request_query_params_redacted")
    with op.batch_alter_table("event_instances") as batch_op:
        batch_op.drop_column("simulator_metadata")
        batch_op.drop_column("replayed_from_event_id")
        batch_op.drop_column("payload_source")
