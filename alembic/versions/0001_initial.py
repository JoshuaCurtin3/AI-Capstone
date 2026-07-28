"""Initial schema: users, analysis_results, triggered_rules.

Revision ID: 0001
Revises:
Create Date: 2026-07-27

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=256), nullable=False),
        sa.Column("display_name", sa.String(length=256), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("username", name="uq_users_username"),
    )
    op.create_index("ix_users_username", "users", ["username"])

    op.create_table(
        "analysis_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "submitted_by_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("subject", sa.String(length=998), nullable=True),
        sa.Column("from_address", sa.String(length=998), nullable=True),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("classification", sa.String(length=16), nullable=False),
        sa.Column("total_findings", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_analysis_results_submitted_by_id", "analysis_results", ["submitted_by_id"])

    op.create_table(
        "triggered_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "analysis_result_id",
            sa.Integer(),
            sa.ForeignKey("analysis_results.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("rule_id", sa.String(length=64), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
    )
    op.create_index(
        "ix_triggered_rules_analysis_result_id", "triggered_rules", ["analysis_result_id"]
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_triggered_rules_analysis_result_id", table_name="triggered_rules")
    op.drop_table("triggered_rules")
    op.drop_index("ix_analysis_results_submitted_by_id", table_name="analysis_results")
    op.drop_table("analysis_results")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")
