"""YAML serialization formatter."""

import yaml
from devtoolkit.core.models import AuditSummary


def render_yaml(summary: AuditSummary) -> str:
    """Return YAML string representation of the audit summary."""
    data = summary.model_dump(mode="json")
    return yaml.dump(data, sort_keys=False, default_flow_style=False)

