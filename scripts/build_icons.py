"""Generate high-resolution PNG and multi-resolution ICO from devspotlight-icon.svg."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
from PIL import Image


def generate_spotlight_icons() -> None:
    root = Path(__file__).resolve().parent.parent
    design_dir = root / "design"
    assets_dir = root / "assets"
    spotlight_ui_dir = root / "clients" / "spotlight" / "ui"

    svg_path = design_dir / "devspotlight-icon.svg"
    if not svg_path.is_file():
        raise FileNotFoundError(f"SVG file not found: {svg_path}")

    # 1. Locate Edge executable
    edge_exe = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    if not os.path.exists(edge_exe):
        edge_exe = r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
    if not os.path.exists(edge_exe):
        raise FileNotFoundError("Microsoft Edge executable not found for headless rendering.")

    # 2. Create rendering HTML wrapper
    temp_html = design_dir / "_temp_icon_render.html"
    svg_uri = svg_path.as_uri()
    html_content = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  html, body {{
    margin: 0;
    padding: 0;
    background: transparent !important;
    width: 512px;
    height: 512px;
    overflow: hidden;
  }}
  img {{
    width: 512px;
    height: 512px;
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

    # 3. Render 512x512 transparent PNG
    master_png = assets_dir / "devspotlight.png"
    cmd = [
        edge_exe,
        "--headless",
        "--disable-gpu",
        "--default-background-color=00000000",
        "--hide-scrollbars",
        f"--screenshot={master_png}",
        "--window-size=512,512",
        str(temp_html.resolve())
    ]
    subprocess.run(cmd, check=True)
    if temp_html.exists():
        temp_html.unlink()

    print(f"[+] Master PNG generated: {master_png} ({master_png.stat().st_size} bytes)")

    # 4. Generate multi-resolution .ico using Pillow
    img = Image.open(master_png).convert("RGBA")
    
    # Target standard Windows icon resolutions
    icon_sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    
    master_ico = assets_dir / "devspotlight.ico"
    img.save(
        master_ico,
        format="ICO",
        sizes=icon_sizes
    )
    print(f"[+] Multi-resolution ICO generated: {master_ico} ({master_ico.stat().st_size} bytes)")

    # 5. Also copy/save into clients/spotlight/ui/ for runtime bundling
    spotlight_ui_dir.mkdir(parents=True, exist_ok=True)
    ui_ico = spotlight_ui_dir / "devspotlight.ico"
    ui_png = spotlight_ui_dir / "devspotlight.png"

    img.save(ui_ico, format="ICO", sizes=icon_sizes)
    img.save(ui_png, format="PNG")
    print(f"[+] Bundled to UI directory: {ui_ico} and {ui_png}")


if __name__ == "__main__":
    generate_spotlight_icons()
