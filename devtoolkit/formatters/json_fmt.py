"""JSON serialization formatter."""

from devtoolkit.core.models import AuditSummary


def render_json(summary: AuditSummary) -> str:
    """Return JSON string representation of the audit summary."""
    return summary.model_dump_json(indent=2)
