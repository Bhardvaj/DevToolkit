"""Render HTML preview of SVGs using Headless Edge."""

import os
from pathlib import Path
import subprocess

def render_preview():
    root = Path(__file__).resolve().parent.parent
    design_dir = root / "design"

    html_content = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Logo Preview</title>
  <style>
    body {
      background-color: #08090C;
      color: #F3F4F6;
      font-family: 'Segoe UI Variable', system-ui, sans-serif;
      padding: 40px;
      display: flex;
      flex-direction: column;
      gap: 30px;
      margin: 0;
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 24px;
    }
    .card {
      background: #0E1015;
      border: 1px solid #1F2430;
      border-radius: 12px;
      padding: 24px;
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 16px;
    }
    .card h3 {
      margin: 0;
      font-size: 13px;
      color: #94A3B8;
      font-family: Consolas, monospace;
    }
    img {
      max-width: 100%;
    }
  </style>
</head>
<body>
  <h1 style="font-size: 22px; margin: 0 0 10px 0;">DevToolkit &amp; DevSpotlight Extracted Vector Assets</h1>
  
  <div class="grid">
    <div class="card">
      <h3>design/devtoolkit-logo.svg</h3>
      <img src="devtoolkit-logo.svg" style="height: 80px;">
    </div>
    <div class="card">
      <h3>design/devspotlight-logo.svg</h3>
      <img src="devspotlight-logo.svg" style="height: 80px;">
    </div>
    <div class="card">
      <h3>design/devtoolkit-icon.svg</h3>
      <img src="devtoolkit-icon.svg" style="width: 160px; height: 160px;">
    </div>
    <div class="card">
      <h3>design/devspotlight-icon.svg</h3>
      <img src="devspotlight-icon.svg" style="width: 160px; height: 160px;">
    </div>
    <div class="card">
      <h3>design/devtoolkit-ui-badge.svg</h3>
      <img src="devtoolkit-ui-badge.svg" style="width: 64px; height: 64px;">
    </div>
    <div class="card">
      <h3>design/devspotlight-ui-badge.svg</h3>
      <img src="devspotlight-ui-badge.svg" style="width: 64px; height: 64px;">
    </div>
  </div>
</body>
</html>
"""
    preview_html = design_dir / "preview.html"
    preview_html.write_text(html_content, encoding="utf-8")

    edge_exe = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    if not os.path.exists(edge_exe):
        edge_exe = r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"

    screenshot_png = design_dir / "preview.png"
    cmd = [
        edge_exe,
        "--headless",
        "--disable-gpu",
        f"--screenshot={screenshot_png}",
        "--window-size=1200,900",
        str(preview_html.resolve())
    ]
    subprocess.run(cmd, check=True)
    print(f"Preview saved to {screenshot_png}")

if __name__ == "__main__":
    render_preview()

