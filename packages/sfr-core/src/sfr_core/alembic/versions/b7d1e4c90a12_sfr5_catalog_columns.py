"""SFR-5: поля стратификации, дедупликации и признака мегаколлаборации

Revision ID: b7d1e4c90a12
Revises: a2cb448fcbcf
Create Date: 2026-09-05 21:10:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7d1e4c90a12"
down_revision: str | None = "a2cb448fcbcf"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # SQLite не умеет ALTER для добавления FK — batch_alter_table пересоздаёт
    # таблицу; на PostgreSQL тот же код выполняется обычным ALTER.
    with op.batch_alter_table("authors") as batch:
        batch.add_column(sa.Column("primary_field", sa.String(length=128), nullable=True))
        batch.add_column(sa.Column("merged_into_id", sa.Integer(), nullable=True))
        batch.add_column(
            sa.Column("suspect_merge", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch.create_foreign_key(
            "fk_authors_merged_into_id_authors", "authors", ["merged_into_id"], ["id"]
        )
    op.create_index(op.f("ix_authors_primary_field"), "authors", ["primary_field"])
    op.create_index(op.f("ix_authors_merged_into_id"), "authors", ["merged_into_id"])
    op.create_index(op.f("ix_authors_suspect_merge"), "authors", ["suspect_merge"])

    with op.batch_alter_table("works") as batch:
        batch.add_column(sa.Column("institutions_distinct_count", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("works") as batch:
        batch.drop_column("institutions_distinct_count")
    op.drop_index(op.f("ix_authors_suspect_merge"), table_name="authors")
    op.drop_index(op.f("ix_authors_merged_into_id"), table_name="authors")
    op.drop_index(op.f("ix_authors_primary_field"), table_name="authors")
    with op.batch_alter_table("authors") as batch:
        batch.drop_constraint("fk_authors_merged_into_id_authors", type_="foreignkey")
        batch.drop_column("suspect_merge")
        batch.drop_column("merged_into_id")
        batch.drop_column("primary_field")
