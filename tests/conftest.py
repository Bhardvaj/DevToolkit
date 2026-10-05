"""Global pytest fixtures and configuration for DevToolkit test suite."""

import json
import logging
import os
import tempfile
from pathlib import Path
import pytest

from devtoolkit.core.inventory import OSInventory
from devtoolkit.core.ecosystem import EcosystemResolvers


@pytest.fixture(autouse=True, scope="session")
def isolate_test_config():
    """Ensure test runs never inherit root drives from development devtoolkit.json."""
    tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    dummy_cfg = Path(tmp.name) / "devtoolkit.json"
    dummy_cfg.write_text(
        json.dumps({
            "search_paths": [],
            "enabled_categories": None,
            "custom_env": {},
            "realtime_search": False,
            "close_action": "ask",
        }, indent=2),
        encoding="utf-8",
    )
    old_val = os.environ.get("DEVTOOLKIT_CONFIG")
    os.environ["DEVTOOLKIT_CONFIG"] = str(dummy_cfg)
    yield
    if old_val is not None:
        os.environ["DEVTOOLKIT_CONFIG"] = old_val
    else:
        os.environ.pop("DEVTOOLKIT_CONFIG", None)

    logging.shutdown()
    try:
        tmp.cleanup()
    except Exception:
        pass
