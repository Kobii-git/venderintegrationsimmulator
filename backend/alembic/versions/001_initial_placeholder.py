"""Core persistence tables for simulations, events, and delivery attempts."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "simulations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("product_id", sa.String(length=64), nullable=False),
        sa.Column("scenario_id", sa.String(length=64), nullable=False),
        sa.Column("simulation_mode", sa.String(length=64), nullable=False),
        sa.Column("fidelity_mode", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("destination", sa.JSON(), nullable=False),
        sa.Column("auth_config", sa.JSON(), nullable=False),
        sa.Column("scenario_overrides", sa.JSON(), nullable=False),
        sa.Column("schedule", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_simulations_product_id", "simulations", ["product_id"])
    op.create_index("ix_simulations_status", "simulations", ["status"])

    op.create_table(
        "event_instances",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("simulation_id", sa.String(length=36), nullable=False),
        sa.Column("product_id", sa.String(length=64), nullable=False),
        sa.Column("scenario_id", sa.String(length=64), nullable=False),
        sa.Column("fidelity_mode", sa.String(length=32), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("correlation_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["simulation_id"], ["simulations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_event_instances_simulation_id", "event_instances", ["simulation_id"])
    op.create_index("ix_event_instances_product_id", "event_instances", ["product_id"])
    op.create_index("ix_event_instances_correlation_id", "event_instances", ["correlation_id"])
    op.create_index("ix_event_instances_status", "event_instances", ["status"])

    op.create_table(
        "delivery_attempts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("event_instance_id", sa.String(length=36), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("transport_id", sa.String(length=64), nullable=False),
        sa.Column("destination_summary", sa.String(length=512), nullable=False),
        sa.Column("request_method", sa.String(length=16), nullable=True),
        sa.Column("request_headers_redacted", sa.JSON(), nullable=False),
        sa.Column("request_body", sa.Text(), nullable=True),
        sa.Column("response_status_code", sa.Integer(), nullable=True),
        sa.Column("response_headers_redacted", sa.JSON(), nullable=False),
        sa.Column("response_body", sa.Text(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("error_category", sa.String(length=32), nullable=True),
        sa.ForeignKeyConstraint(["event_instance_id"], ["event_instances.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_delivery_attempts_event_instance_id", "delivery_attempts", ["event_instance_id"])


def downgrade() -> None:
    op.drop_index("ix_delivery_attempts_event_instance_id", table_name="delivery_attempts")
    op.drop_table("delivery_attempts")
    op.drop_index("ix_event_instances_status", table_name="event_instances")
    op.drop_index("ix_event_instances_correlation_id", table_name="event_instances")
    op.drop_index("ix_event_instances_product_id", table_name="event_instances")
    op.drop_index("ix_event_instances_simulation_id", table_name="event_instances")
    op.drop_table("event_instances")
    op.drop_index("ix_simulations_status", table_name="simulations")
    op.drop_index("ix_simulations_product_id", table_name="simulations")
    op.drop_table("simulations")
