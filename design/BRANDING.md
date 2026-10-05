# DevToolkit Ecosystem Brand & Visual Identity System

This specification defines the universal design architecture, color systems, and asset pipelines for all applications and utilities across the **DevToolkit** suite.

---

## 1. Visual Hierarchy & The "Asset Triple"

Every standalone application or modular utility in the ecosystem must provide a standard **Asset Triple** within the [`design/`](file:///D:/UtilitySoftware/design) directory:

```
design/
  ├── {app}-icon.svg         # 1. Master Application Icon (512×512 Squircle)
  ├── {app}-logo.svg         # 2. Horizontal Brand Lockup (Vector Logo)
  └── {app}-ui-badge.svg     # 3. In-App Micro Badge (32×32 or 40×40)
assets/
  ├── {app}.png              # Rendered 512×512 Master Transparent PNG
  └── {app}.ico              # Multi-resolution Windows Icon (16 to 256px)
```

### Purpose & Placement of Each Asset

| Asset Type | File Spec | ViewBox | Target Usage |
|---|---|---|---|
| **Master Icon** | `{app}-icon.svg` | `0 0 512 512` | Desktop shortcuts, OS application launcher, Windows PE executable resource (`--icon`), task switcher (Alt+Tab), GitHub repositories. |
| **Brand Logo** | `{app}-logo.svg` | `0 0 460-480 110` | Splash screens, documentation headers, README heroes, "About" dialogs, and marketing banners. |
| **UI Micro Badge** | `{app}-ui-badge.svg` | `0 0 32 32` or `40 40` | In-app view headers, sidebar navigation pills, breadcrumbs, and taskbar / system tray icon fallbacks. |
| **Multi-Res ICO** | `{app}.ico` | 16, 24, 32, 48, 64, 128, 256px | Native Windows Explorer icon, Win32 executable compilation, and system notification area tray icon. |

---

## 2. Product Registry & Signature Colors

Each tool has **one distinct signature accent color** that anchors its visual identity:

### App 1: DevToolkit
* **Product Role**: Workstation Developer Suite, Diagnostics Engine & Local HTTP Dashboard
* **Signature Color**: **Cyber Emerald** (`#10B981`)
* **Color Tokens**:
  - Primary Accent: `#10B981` (RGB: `16, 185, 129`)
  - Accent Gradient: `#34D399` (0%) → `#10B981` (50%) → `#059669` (100%)
  - Glow Shadow: `rgba(16, 185, 129, 0.20)`
  - Card Slate Base: `#181C26` → `#141721` → `#0E1015`
  - Border Highlight: `#1F2430` / `#2E3446`
* **Icon Motifs**:
  - Code chevron brackets (`<` `>`) flanking a central energetic lightning bolt.
  - Precision hairline workstation grid lines.
* **Tagline Meta**: `WORKSTATION SUITE`

### App 2: DevSpotlight
* **Product Role**: Floating Command Palette, Rapid Workspace Launcher & Tactical Socket Inspector
* **Signature Color**: **Obsidian Sky / Cyan** (`#38BDF8`)
* **Color Tokens**:
  - Primary Accent: `#38BDF8` (RGB: `56, 189, 248`)
  - Accent Gradient: `#7DD3FC` (0%) → `#38BDF8` (45%) → `#0284C7` (100%)
  - Glow Shadow: `rgba(56, 189, 248, 0.25)`
  - Card Slate Base: `#16273D` → `#0E1522` → `#080B11`
  - Border Highlight: `#38BDF8` (opacity 0.65 to 0.25)
* **Icon Motifs**:
  - Radial aperture / radar guide rings and 45° conical light beam.
  - Cyber-cut lightning bolt mark with 3D top-face facet highlight (`#E0F2FE`).
* **Tagline Meta**: `COMMAND PALETTE`

---

## 3. Design Geometry & Standardization Rules

To ensure aesthetic consistency across all future utilities:

1. **Squircle Outer Container (512×512 Tile)**:
   - Outer tile size: `width="420" height="420"` placed at `x="46" y="46"`.
   - Corner radius: `rx="96"` (produces the modern Windows 11 / iOS squircle curve).
   - Inner highlight stroke: `x="48" y="48" width="416" height="416" rx="94" stroke-width="1.5"` with low-opacity accent color.
2. **Gradient Angle**:
   - Background card: Diagonal top-left to bottom-right (`x1="0%" y1="0%" x2="100%" y2="100%"`).
   - Accent mark: Matches container diagonal or top-to-bottom.
3. **Typography Standards (for Logos)**:
   - Primary wordmark font: `'Geist', 'Segoe UI Variable', system-ui, sans-serif` (weight: 700, size: 34px).
   - Prefix: `Dev` in `#F3F4F6` (White).
   - Suffix: `{AppName}` in product signature accent color.
   - Metadata / Subtitle: `'JetBrains Mono', 'Consolas', monospace` (size: 10.5px, weight: 600, letter-spacing: 2.5px, fill: `#94A3B8`).

---

## 4. Brand Asset Generation Pipeline

All icons and binary assets are generated through the centralized pipeline:

```bash
# Export all SVGs, render 512x512 PNGs, and build multi-res Windows ICOs:
python scripts/build_brand_assets.py

# Preview the unified gallery in headless Edge:
python scripts/render_preview.py
```

### Output Matrix:
* `design/preview.png` — Real-time visual audit sheet showing all icons, logos, and badges side-by-side.
* `assets/devtoolkit.ico` & `assets/icon.ico` — Compiled into `dist/DevToolkit.exe` binary.
### Output Matrix:
* `design/preview.png` — Visual audit sheet showing all icons, logos, and badges side-by-side.
* `assets/devtoolkit.ico` — Multi-resolution ICO compiled into `dist/DevToolkit.exe` binary and used by workstation daemon tray.
* `assets/devspotlight.ico` — Multi-resolution ICO compiled into `dist/DevToolkitSpotlight.exe` and used for DevSpotlight tray/window.
* `assets/devtoolkit.png` & `assets/devspotlight.png` — 512×512 Master transparent PNGs.

---

## 5. Zero-Duplication Architecture & Directory Map

To prevent asset drift, stale files, and redundant maintenance, **every asset exists in exactly ONE place in the entire codebase**:

```
D:\UtilitySoftware\
│
├── design/                     <-- ALL SVGs LIVE ONLY HERE (Source of Truth)
│   ├── devtoolkit-icon.svg     # 512×512 Master App Mark (Cyber Emerald #10B981)
│   ├── devtoolkit-logo.svg     # Horizontal Brand Lockup (Mark + Typography)
│   ├── devtoolkit-ui-badge.svg # 40×40 Micro Squircle UI Badge
│   ├── devspotlight-icon.svg   # 512×512 Master App Mark (Obsidian Sky #38BDF8)
│   ├── devspotlight-logo.svg   # Horizontal Brand Lockup (Mark + Typography)
│   ├── devspotlight-ui-badge.svg # 40×40 Micro Squircle UI Badge
│   ├── BRANDING.md             # Brand specifications & architecture documentation
│   ├── preview.html            # Visual audit gallery
│   └── preview.png             # Rendered audit sheet (1200×820)
│
├── assets/                     <-- ALL COMPILED BINARIES LIVE ONLY HERE
│   ├── devtoolkit.ico          # Multi-resolution ICO (16, 24, 32, 48, 64, 128, 256px)
│   ├── devtoolkit.png          # 512×512 Master Transparent PNG
│   ├── devspotlight.ico        # Multi-resolution ICO for Spotlight client binary & tray
│   └── devspotlight.png        # 512×512 Master Transparent PNG
│
├── clients/spotlight/ui/       <-- ONLY CLIENT UI MARKUP
│   └── spotlight.html          # Clean HTML, references central assets directly
│
└── devtoolkit/server/static/   <-- ONLY SERVER WEB MARKUP & STYLES
    ├── index.html              # Clean HTML, references /design/*.svg and /favicon.ico
    ├── styles.css              # Master stylesheet
    └── app.js                  # Client SPA controller
```

---

## 6. How Zero-Duplication Works at Runtime & Build Time

1. **FastAPI Web Routing (`/design` & `/favicon.ico`)**:
   - `app.mount("/design", StaticFiles(directory=DESIGN_DIR))` serves SVGs directly from `design/`.
   - `@app.get("/favicon.ico")` returns `assets/devtoolkit.ico` directly.
   - No copies of SVGs or ICOs in `devtoolkit/server/static/`.

2. **HTML Markup Reference**:
   - `index.html` references canonical paths directly:
     ```html
     <link rel="icon" type="image/x-icon" href="/favicon.ico">
     <link rel="icon" type="image/svg+xml" href="/design/devtoolkit-ui-badge.svg">
     <img src="/design/devtoolkit-ui-badge.svg" class="w-8 h-8 rounded-lg select-none" alt="DevToolkit">
     <img src="/design/devspotlight-ui-badge.svg" class="w-10 h-10 rounded-lg select-none" alt="DevSpotlight">
     ```
   - Editing an SVG in `design/` updates the UI immediately without rebuilding or copying.

3. **PyInstaller Standalone Packaging**:
   - `build_standalone.ps1` bundles `--add-data "design;design"` and `--add-data "assets;assets"`.
   - `build_spotlight.ps1` bundles `--add-data "assets;assets"` and uses `--icon "assets/devspotlight.ico"`.
   - Single-file binaries remain self-contained with zero runtime dependencies.

4. **Streamlined Pipeline**:
   - `python scripts/build_brand_assets.py` renders master PNGs and ICOs into `assets/` and captures `design/preview.png`. No files are duplicated across subdirectories.


