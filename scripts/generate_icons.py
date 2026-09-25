"""Generate multi-resolution Windows ICO and PNG assets from design/Icon_design/screen.png."""

from pathlib import Path
from PIL import Image

def generate_icons():
    root = Path(__file__).resolve().parent.parent
    source_png = root / "design" / "Icon_design" / "screen.png"
    if not source_png.exists():
        raise FileNotFoundError(f"Source icon not found: {source_png}")

    assets_dir = root / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    static_dir = root / "devtoolkit" / "server" / "static"
    static_dir.mkdir(parents=True, exist_ok=True)

    img = Image.open(source_png).convert("RGBA")
    w, h = img.size

    # Place on square transparent canvas (size = max(w, h))
    max_dim = max(w, h)
    square_img = Image.new("RGBA", (max_dim, max_dim), (0, 0, 0, 0))
    offset_x = (max_dim - w) // 2
    offset_y = (max_dim - h) // 2
    square_img.paste(img, (offset_x, offset_y), img)

    # High-res 512x512 PNG
    icon_512 = square_img.resize((512, 512), Image.Resampling.LANCZOS)
    icon_512.save(assets_dir / "icon.png", format="PNG")
    icon_512.save(static_dir / "icon.png", format="PNG")
    print(f"Generated: {assets_dir / 'icon.png'}")

    # Standard Windows ICO sizes (using bitmap_format='bmp' for Windows Explorer shell compatibility)
    ico_sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    icon_ico_path = assets_dir / "icon.ico"
    square_img.save(
        icon_ico_path,
        format="ICO",
        sizes=ico_sizes,
        bitmap_format="bmp",
    )
    print(f"Generated: {icon_ico_path}")

    # Also save favicon for web dashboard
    square_img.save(
        static_dir / "favicon.ico",
        format="ICO",
        sizes=[(16, 16), (32, 32), (48, 48)],
        bitmap_format="bmp",
    )
    print(f"Generated: {static_dir / 'favicon.ico'}")

if __name__ == "__main__":
    generate_icons()

