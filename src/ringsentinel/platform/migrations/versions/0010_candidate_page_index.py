"""Index range scans for owner-authorized candidate pages."""
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index("ix_result_sections_page", "result_sections", ["run_id", "kind", "ordinal"])


def downgrade():
    op.drop_index("ix_result_sections_page", table_name="result_sections")
