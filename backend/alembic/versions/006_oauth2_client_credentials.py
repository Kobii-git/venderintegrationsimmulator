"""Add OAuth2 access tokens and inbound request kind metadata."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006_oauth2_client_credentials"
down_revision: Union[str, None] = "005_inbound_mock_api"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "oauth_access_tokens",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "simulation_id",
            sa.String(length=36),
            sa.ForeignKey("simulations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("client_id", sa.String(length=255), nullable=False),
        sa.Column("scope", sa.String(length=512), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default="0"),
    )
    op.create_index("ix_oauth_access_tokens_simulation_id", "oauth_access_tokens", ["simulation_id"])
    op.create_index("ix_oauth_access_tokens_token_hash", "oauth_access_tokens", ["token_hash"], unique=True)
    op.create_index("ix_oauth_access_tokens_expires_at", "oauth_access_tokens", ["expires_at"])

    with op.batch_alter_table("inbound_request_logs") as batch_op:
        batch_op.add_column(
            sa.Column("request_kind", sa.String(length=16), nullable=False, server_default="api")
        )
        batch_op.add_column(sa.Column("token_metadata", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("inbound_request_logs") as batch_op:
        batch_op.drop_column("token_metadata")
        batch_op.drop_column("request_kind")

    op.drop_index("ix_oauth_access_tokens_expires_at", table_name="oauth_access_tokens")
    op.drop_index("ix_oauth_access_tokens_token_hash", table_name="oauth_access_tokens")
    op.drop_index("ix_oauth_access_tokens_simulation_id", table_name="oauth_access_tokens")
    op.drop_table("oauth_access_tokens")
