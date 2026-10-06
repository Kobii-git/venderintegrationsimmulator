"""Secure configuration storage and repair relational integrity."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "007_secure_configuration_and_integrity"
down_revision: Union[str, None] = "006_oauth2_client_credentials"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Remove rows that cannot be made valid before foreign-key enforcement is enabled.
    op.execute(
        "DELETE FROM delivery_attempts "
        "WHERE event_instance_id NOT IN (SELECT id FROM event_instances)"
    )
    op.execute(
        "DELETE FROM inbound_request_logs "
        "WHERE simulation_id NOT IN (SELECT id FROM simulations)"
    )
    op.execute(
        "DELETE FROM oauth_access_tokens "
        "WHERE simulation_id NOT IN (SELECT id FROM simulations)"
    )

    with op.batch_alter_table("simulations") as batch_op:
        batch_op.add_column(
            sa.Column("configuration_version", sa.Integer(), nullable=False, server_default="1")
        )
        batch_op.add_column(
            sa.Column(
                "destination_secret_values", sa.JSON(), nullable=False, server_default="{}"
            )
        )

    with op.batch_alter_table("delivery_attempts") as batch_op:
        batch_op.add_column(
            sa.Column("request_url_redacted", sa.String(length=2048), nullable=True)
        )

    with op.batch_alter_table("inbound_request_logs") as batch_op:
        batch_op.alter_column(
            "simulation_id",
            existing_type=sa.String(length=36),
            nullable=True,
        )

    op.create_index(
        "ix_delivery_attempts_event_order",
        "delivery_attempts",
        ["event_instance_id", "attempt_number", "started_at", "id"],
    )
    op.create_index(
        "ix_inbound_request_logs_request_kind",
        "inbound_request_logs",
        ["request_kind"],
    )
    op.create_index(
        "ix_inbound_request_logs_response_status_code",
        "inbound_request_logs",
        ["response_status_code"],
    )


def downgrade() -> None:
    raise RuntimeError("007_secure_configuration is a forward-only migration")
