"""Initial production schema.

Revision ID: 20260704_0001
"""

from alembic import op
import sqlalchemy as sa

revision = "20260704_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("salt", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False, server_default="farmer"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_table(
        "user_settings",
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("weather_api_key", sa.Text()),
        sa.Column("default_location", sa.Text(), server_default="Delhi,IN"),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_table(
        "analysis_logs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id")),
        sa.Column("image_name", sa.Text()),
        sa.Column("disease", sa.Text()),
        sa.Column("confidence", sa.Float()),
        sa.Column("severity", sa.Text()),
        sa.Column("immediate_action", sa.Text()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_analysis_logs_user_created", "analysis_logs", ["user_id", "created_at"])
    op.create_table(
        "weather_logs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id")),
        sa.Column("location", sa.Text()),
        sa.Column("temperature", sa.Float()),
        sa.Column("humidity", sa.Float()),
        sa.Column("wind_speed", sa.Float()),
        sa.Column("description", sa.Text()),
        sa.Column("source", sa.Text()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_table(
        "chat_logs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id")),
        sa.Column("role", sa.Text()),
        sa.Column("message", sa.Text()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    for table_name in ("refresh_tokens", "password_reset_tokens"):
        op.create_table(
            table_name,
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("token_hash", sa.Text(), nullable=False, unique=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("revoked" if table_name == "refresh_tokens" else "used", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("revoked_at" if table_name == "refresh_tokens" else "used_at", sa.DateTime()),
        )
    op.create_table(
        "prediction_feedback",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("analysis_id", sa.BigInteger(), sa.ForeignKey("analysis_logs.id"), nullable=False),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("is_correct", sa.Integer(), nullable=False),
        sa.Column("corrected_disease", sa.Text()),
        sa.Column("notes", sa.Text()),
        sa.Column("review_status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("reviewed_by", sa.BigInteger(), sa.ForeignKey("users.id")),
        sa.Column("reviewed_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("analysis_id", "user_id"),
    )
    op.create_table(
        "agronomist_review_queue",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("analysis_id", sa.BigInteger(), sa.ForeignKey("analysis_logs.id"), nullable=False, unique=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("crop_stage", sa.Text()),
        sa.Column("symptom_notes", sa.Text()),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("reviewer_notes", sa.Text()),
        sa.Column("reviewed_by", sa.BigInteger(), sa.ForeignKey("users.id")),
        sa.Column("reviewed_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    for table_name in (
        "agronomist_review_queue",
        "prediction_feedback",
        "password_reset_tokens",
        "refresh_tokens",
        "chat_logs",
        "weather_logs",
        "analysis_logs",
        "user_settings",
        "users",
    ):
        op.drop_table(table_name)
