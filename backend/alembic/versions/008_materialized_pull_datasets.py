"""Add stable materialized datasets for pull simulations."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "008_materialized_pull_datasets"
down_revision: Union[str, None] = "007_secure_configuration_and_integrity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pull_dataset_activations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "simulation_id",
            sa.String(length=36),
            sa.ForeignKey("simulations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("item_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index(
        "ix_pull_dataset_activations_simulation_id",
        "pull_dataset_activations",
        ["simulation_id"],
    )

    op.create_table(
        "pull_dataset_items",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "activation_id",
            sa.String(length=36),
            sa.ForeignKey("pull_dataset_activations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "simulation_id",
            sa.String(length=36),
            sa.ForeignKey("simulations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("route_id", sa.String(length=64), nullable=False),
        sa.Column("scenario_id", sa.String(length=64), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.UniqueConstraint(
            "activation_id",
            "route_id",
            "sequence",
            name="uq_pull_dataset_route_sequence",
        ),
    )
    op.create_index(
        "ix_pull_dataset_items_activation_id", "pull_dataset_items", ["activation_id"]
    )
    op.create_index(
        "ix_pull_dataset_items_simulation_id", "pull_dataset_items", ["simulation_id"]
    )
    op.create_index("ix_pull_dataset_items_route_id", "pull_dataset_items", ["route_id"])
    op.create_index(
        "ix_pull_dataset_items_generated_at", "pull_dataset_items", ["generated_at"]
    )
    op.create_index(
        "ix_pull_dataset_items_route_time",
        "pull_dataset_items",
        ["activation_id", "route_id", "generated_at"],
    )


def downgrade() -> None:
    raise RuntimeError("008_materialized_pull_datasets is a forward-only migration")
