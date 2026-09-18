"""UI Template Engine and Asset Resolver for DevToolkit."""

import sys
from pathlib import Path


def get_resource_text(filename: str) -> str:
    """Resolve and read text content from static UI assets across environments.
    
    Supports:
    1. Python package resource loading via importlib.resources
    2. PyInstaller single-file bundle extraction via sys._MEIPASS
    3. Direct local filesystem resolution relative to __file__
    """
    # 1. Try importlib.resources (standard in Python 3.9+)
    try:
        from importlib.resources import files
        res = files("devtoolkit.server.static").joinpath(filename)
        return res.read_text(encoding="utf-8")
    except Exception:
        pass

    # 2. PyInstaller temporary extraction directory
    if hasattr(sys, "_MEIPASS"):
        meipass_path = Path(sys._MEIPASS) / "devtoolkit" / "server" / "static" / filename
        if meipass_path.exists():
            return meipass_path.read_text(encoding="utf-8")

    # 3. Direct filesystem fallback
    local_path = Path(__file__).resolve().parent / "static" / filename
    if local_path.exists():
        return local_path.read_text(encoding="utf-8")

    raise FileNotFoundError(f"Could not locate static UI asset: {filename}")


def get_dashboard_html() -> str:
    """Build and return the complete, self-contained HTML dashboard string.
    
    Inlines styles.css and app.js into index.html for zero-latency,
    offline-capable, single-payload delivery.
    """
    html = get_resource_text("index.html")
    css = get_resource_text("styles.css")
    js = get_resource_text("app.js")

    # Inline styles and scripts into template placeholders
    html = html.replace("/* __INLINE_STYLES__ */", css)
    html = html.replace("/* __INLINE_SCRIPTS__ */", js)
    return html


# Cached / pre-built dashboard string for high-throughput serving
EMBEDDED_UI_HTML = get_dashboard_html()


def serve_dashboard() -> str:
    """FastAPI root route handler serving the desktop UI."""
    return get_dashboard_html()
