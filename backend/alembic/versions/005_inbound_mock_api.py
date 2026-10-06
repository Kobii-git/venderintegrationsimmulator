"""Add inbound_config and inbound_request_logs for pull-based mock API."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005_inbound_mock_api"
down_revision: Union[str, None] = "004_fault_injection"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("simulations") as batch_op:
        batch_op.add_column(
            sa.Column("inbound_config", sa.JSON(), nullable=False, server_default="{}")
        )

    op.create_table(
        "inbound_request_logs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("simulation_id", sa.String(length=36), sa.ForeignKey("simulations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", sa.String(length=64), nullable=False),
        sa.Column("route_id", sa.String(length=64), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("request_method", sa.String(length=16), nullable=False),
        sa.Column("request_path", sa.String(length=512), nullable=False),
        sa.Column("request_query_params", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("request_headers_redacted", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("request_body", sa.Text(), nullable=True),
        sa.Column("response_status_code", sa.Integer(), nullable=False),
        sa.Column("response_headers", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("response_body", sa.Text(), nullable=True),
        sa.Column("auth_method_id", sa.String(length=32), nullable=False, server_default="none"),
        sa.Column("auth_result", sa.String(length=32), nullable=False, server_default="skipped"),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("items_returned", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.create_index("ix_inbound_request_logs_simulation_id", "inbound_request_logs", ["simulation_id"])
    op.create_index("ix_inbound_request_logs_product_id", "inbound_request_logs", ["product_id"])
    op.create_index("ix_inbound_request_logs_received_at", "inbound_request_logs", ["received_at"])


def downgrade() -> None:
    op.drop_index("ix_inbound_request_logs_received_at", table_name="inbound_request_logs")
    op.drop_index("ix_inbound_request_logs_product_id", table_name="inbound_request_logs")
    op.drop_index("ix_inbound_request_logs_simulation_id", table_name="inbound_request_logs")
    op.drop_table("inbound_request_logs")
    with op.batch_alter_table("simulations") as batch_op:
        batch_op.drop_column("inbound_config")
