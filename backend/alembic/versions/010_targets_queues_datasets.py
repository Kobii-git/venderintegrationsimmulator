"""Independent collectors, durable queues and uploaded log datasets."""

import uuid

from alembic import op
import sqlalchemy as sa

revision = "010_targets_queues_datasets"
down_revision = "009_vendor_workflow_actions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "simulations", sa.Column("devices", sa.JSON(), nullable=False, server_default="[]")
    )
    op.add_column(
        "simulations", sa.Column("replay_config", sa.JSON(), nullable=False, server_default="{}")
    )
    op.add_column("delivery_attempts", sa.Column("target_id", sa.String(64), nullable=True))
    op.add_column(
        "delivery_attempts", sa.Column("delivery_confirmation", sa.String(32), nullable=True)
    )
    op.add_column("delivery_attempts", sa.Column("delivery_note", sa.Text(), nullable=True))
    op.create_index("ix_delivery_attempts_target_id", "delivery_attempts", ["target_id"])
    op.create_table(
        "simulation_targets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "simulation_id",
            sa.String(36),
            sa.ForeignKey("simulations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("target_id", sa.String(64), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("stats", sa.JSON(), nullable=False),
        sa.UniqueConstraint("simulation_id", "target_id"),
    )
    op.create_index("ix_simulation_targets_simulation_id", "simulation_targets", ["simulation_id"])
    op.create_table(
        "delivery_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "simulation_id",
            sa.String(36),
            sa.ForeignKey("simulations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "event_id",
            sa.String(36),
            sa.ForeignKey("event_instances.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("target_key", sa.String(128), nullable=False),
        sa.Column("target_id", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_delivery_jobs_status", "delivery_jobs", ["status"])
    op.create_index("ix_delivery_jobs_simulation_id", "delivery_jobs", ["simulation_id"])
    op.create_index("ix_delivery_jobs_event_id", "delivery_jobs", ["event_id"])
    op.create_index(
        "ix_jobs_target_status", "delivery_jobs", ["target_key", "status", "created_at"]
    )
    op.create_table(
        "uploaded_datasets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("format", sa.String(16), nullable=False),
        sa.Column("filename", sa.String(64), nullable=False, unique=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("record_count", sa.Integer(), nullable=False),
        sa.Column("timestamp_fields", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    # Current configuration migration already secured destination and auth columns.
    bind = op.get_bind()
    rows = bind.execute(
        sa.text("SELECT id, destination, destination_secret_values, auth_config FROM simulations")
    ).mappings()
    import json

    table = sa.table(
        "simulation_targets",
        sa.column("id"),
        sa.column("simulation_id"),
        sa.column("target_id"),
        sa.column("position"),
        sa.column("config", sa.JSON()),
        sa.column("stats", sa.JSON()),
    )
    for row in rows:
        target_id = str(uuid.uuid4())

        def decode(value):
            return json.loads(value) if isinstance(value, str) else value

        bind.execute(
            table.insert().values(
                id=str(uuid.uuid4()),
                simulation_id=row["id"],
                target_id=target_id,
                position=0,
                config={
                    "id": target_id,
                    "name": "Primary",
                    "enabled": True,
                    "payload_format": "default",
                    "device_ids": [],
                    "scenario_ids": [],
                    "queue_limit": 10000,
                    "destination": decode(row["destination"]),
                    "destination_secret_values": decode(row["destination_secret_values"]),
                    "auth_config": decode(row["auth_config"]),
                },
                stats={},
            )
        )
        bind.execute(
            sa.text(
                "UPDATE delivery_attempts SET target_id=:target WHERE event_instance_id IN (SELECT id FROM event_instances WHERE simulation_id=:sim)"
            ),
            {"target": target_id, "sim": row["id"]},
        )


def downgrade() -> None:
    op.drop_table("uploaded_datasets")
    op.drop_table("delivery_jobs")
    op.drop_table("simulation_targets")
    op.drop_index("ix_delivery_attempts_target_id", table_name="delivery_attempts")
    for column in ("target_id", "delivery_confirmation", "delivery_note"):
        op.drop_column("delivery_attempts", column)
    op.drop_column("simulations", "replay_config")
    op.drop_column("simulations", "devices")
