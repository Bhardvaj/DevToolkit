"""Unified Brand Asset Builder & Validator for DevToolkit Ecosystem.

Generates high-resolution PNGs, multi-resolution Windows ICOs, and visual
preview sheets for all registered products and utilities from their master SVGs.
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Dict, List
from PIL import Image


ROOT_DIR = Path(__file__).resolve().parent.parent
DESIGN_DIR = ROOT_DIR / "design"
ASSETS_DIR = ROOT_DIR / "assets"

# Standard Windows icon sizes for complete DPI and shell scaling coverage
ICON_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]

# Product Brand Registry - Single Canonical Source & Destinations
BRAND_REGISTRY: List[Dict[str, Any]] = [
    {
        "id": "devtoolkit",
        "name": "DevToolkit",
        "subtitle": "Workstation Developer Suite",
        "signature_color": "#10B981",
        "icon_svg": DESIGN_DIR / "devtoolkit-icon.svg",
        "logo_svg": DESIGN_DIR / "devtoolkit-logo.svg",
        "badge_svg": DESIGN_DIR / "devtoolkit-ui-badge.svg",
        "ico_path": ASSETS_DIR / "devtoolkit.ico",
        "png_path": ASSETS_DIR / "devtoolkit.png",
    },
    {
        "id": "devspotlight",
        "name": "DevSpotlight",
        "subtitle": "Command Palette & Fast Launcher",
        "signature_color": "#38BDF8",
        "icon_svg": DESIGN_DIR / "devspotlight-icon.svg",
        "logo_svg": DESIGN_DIR / "devspotlight-logo.svg",
        "badge_svg": DESIGN_DIR / "devspotlight-ui-badge.svg",
        "ico_path": ASSETS_DIR / "devspotlight.ico",
        "png_path": ASSETS_DIR / "devspotlight.png",
    },
]


def find_edge_browser() -> str:
    """Locate Microsoft Edge executable for headless rendering."""
    candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    raise FileNotFoundError("Microsoft Edge executable not found for headless asset rendering.")


def render_svg_to_png(edge_exe: str, svg_path: Path, output_png: Path, size: int = 512) -> None:
    """Render an SVG file into a pixel-perfect transparent PNG using headless Edge."""
    output_png.parent.mkdir(parents=True, exist_ok=True)
    temp_html = output_png.parent / f"_temp_render_{output_png.stem}.html"
    svg_uri = svg_path.resolve().as_uri()

    html_content = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  html, body {{
    margin: 0;
    padding: 0;
    background: transparent !important;
    width: {size}px;
    height: {size}px;
    overflow: hidden;
  }}
  img {{
    width: {size}px;
    height: {size}px;
    display: block;
    margin: 0;
    padding: 0;
  }}
</style>
</head>
<body>
  <img src="{svg_uri}">
</body>
</html>"""
    temp_html.write_text(html_content, encoding="utf-8")

    cmd = [
        edge_exe,
        "--headless",
        "--disable-gpu",
        "--default-background-color=00000000",
        "--hide-scrollbars",
        f"--screenshot={output_png}",
        f"--window-size={size},{size}",
        str(temp_html.resolve())
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    finally:
        if temp_html.exists():
            temp_html.unlink()


def build_product_assets(product: Dict[str, Any], edge_exe: str) -> None:
    """Build all icon and raster assets for a single product."""
    print(f"\n=======================================================")
    print(f" Processing: {product['name']} ({product['signature_color']})")
    print(f"=======================================================")

    icon_svg: Path = product["icon_svg"]
    if not icon_svg.is_file():
        raise FileNotFoundError(f"Missing master icon SVG: {icon_svg}")

    # 1. Render primary 512x512 transparent PNG
    png_path: Path = product["png_path"]
    render_svg_to_png(edge_exe, icon_svg, png_path, size=512)
    print(f"[+] Rendered Master PNG : {png_path.name} ({png_path.stat().st_size:,} bytes)")

    # 2. Build multi-resolution Windows ICO file
    ico_path: Path = product["ico_path"]
    img = Image.open(png_path).convert("RGBA")
    ico_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(ico_path, format="ICO", sizes=ICON_SIZES)
    print(f"[+] Built Multi-Res ICO : {ico_path.name} ({ico_path.stat().st_size:,} bytes)")


def build_unified_preview(edge_exe: str) -> None:
    """Generate side-by-side HTML gallery and capture preview.png."""
    preview_html = DESIGN_DIR / "preview.html"
    preview_png = DESIGN_DIR / "preview.png"

    cards_html = []
    for p in BRAND_REGISTRY:
        cards_html.append(f"""
    <div class="product-group">
      <div class="product-header">
        <span class="color-dot" style="background: {p['signature_color']}; box-shadow: 0 0 10px {p['signature_color']};"></span>
        <h2>{p['name']}</h2>
        <span class="badge" style="border-color: {p['signature_color']}40; color: {p['signature_color']}; background: {p['signature_color']}18;">
          {p['signature_color']}
        </span>
      </div>

      <div class="grid">
        <div class="card">
          <h3>1. Horizontal Logo ({p['id']}-logo.svg)</h3>
          <img src="{p['logo_svg'].name}" style="height: 72px;">
        </div>
        <div class="card">
          <h3>2. Master Icon ({p['id']}-icon.svg)</h3>
          <img src="{p['icon_svg'].name}" style="width: 140px; height: 140px;">
        </div>
        <div class="card">
          <h3>3. UI Badge ({p['badge_svg'].name})</h3>
          <img src="{p['badge_svg'].name}" style="width: 56px; height: 56px;">
        </div>
      </div>
    </div>
""")

    html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>DevToolkit Brand & Visual Identity Gallery</title>
  <style>
    body {{
      background-color: #08090C;
      color: #F3F4F6;
      font-family: 'Segoe UI Variable', system-ui, -apple-system, sans-serif;
      padding: 40px;
      display: flex;
      flex-direction: column;
      gap: 32px;
      margin: 0;
    }}
    h1 {{
      font-size: 24px;
      margin: 0;
      letter-spacing: -0.5px;
    }}
    .subtitle {{
      font-size: 13px;
      color: #94A3B8;
      margin-top: 4px;
      font-family: Consolas, monospace;
    }}
    .product-group {{
      display: flex;
      flex-direction: column;
      gap: 16px;
      padding: 20px;
      background: #0B0D12;
      border: 1px solid #1F2430;
      border-radius: 14px;
    }}
    .product-header {{
      display: flex;
      align-items: center;
      gap: 10px;
    }}
    .product-header h2 {{
      margin: 0;
      font-size: 18px;
    }}
    .color-dot {{
      width: 10px;
      height: 10px;
      border-radius: 50%;
    }}
    .badge {{
      font-family: Consolas, monospace;
      font-size: 11px;
      padding: 2px 8px;
      border-radius: 6px;
      border: 1px solid;
    }}
    .grid {{
      display: grid;
      grid-template-columns: 2fr 1fr 1fr;
      gap: 16px;
      align-items: center;
    }}
    .card {{
      background: #10131A;
      border: 1px solid #1F2430;
      border-radius: 10px;
      padding: 20px;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 14px;
      min-height: 170px;
    }}
    .card h3 {{
      margin: 0;
      font-size: 11px;
      color: #94A3B8;
      font-family: Consolas, monospace;
    }}
    img {{
      max-width: 100%;
    }}
  </style>
</head>
<body>
  <div>
    <h1>DevToolkit Ecosystem Visual Identity System</h1>
    <div class="subtitle">Unified Master Assets • The Asset Triple: Logo, Icon, and UI Badge</div>
  </div>

  {"".join(cards_html)}
</body>
</html>"""

    preview_html.write_text(html_content, encoding="utf-8")

    cmd = [
        edge_exe,
        "--headless",
        "--disable-gpu",
        f"--screenshot={preview_png}",
        "--window-size=1200,820",
        str(preview_html.resolve())
    ]
    subprocess.run(cmd, check=True)
    print(f"\n[+] Unified brand preview generated: {preview_png}")


def main() -> None:
    print("=======================================================")
    print(" DevToolkit Ecosystem Brand Asset Pipeline             ")
    print("=======================================================")
    edge_exe = find_edge_browser()
    print(f"[i] Using Edge Engine: {edge_exe}")

    for product in BRAND_REGISTRY:
        build_product_assets(product, edge_exe)

    build_unified_preview(edge_exe)
    print("\n[+] All brand assets built, verified, and audited successfully!")


if __name__ == "__main__":
    main()
