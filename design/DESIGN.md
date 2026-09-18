---
name: DevToolkit Pro
colors:
  surface: '#121316'
  surface-dim: '#121316'
  surface-bright: '#38393d'
  surface-container-lowest: '#0d0e11'
  surface-container-low: '#1b1b1f'
  surface-container: '#1f1f23'
  surface-container-high: '#292a2d'
  surface-container-highest: '#343538'
  on-surface: '#e3e2e6'
  on-surface-variant: '#bbcabf'
  inverse-surface: '#e3e2e6'
  inverse-on-surface: '#2f3034'
  outline: '#86948a'
  outline-variant: '#3c4a42'
  surface-tint: '#4edea3'
  primary: '#4edea3'
  on-primary: '#003824'
  primary-container: '#10b981'
  on-primary-container: '#00422b'
  inverse-primary: '#006c49'
  secondary: '#4cd7f6'
  on-secondary: '#003640'
  secondary-container: '#03b5d3'
  on-secondary-container: '#00424e'
  tertiary: '#d0bcff'
  on-tertiary: '#3c0091'
  tertiary-container: '#b090ff'
  on-tertiary-container: '#4600a7'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#6ffbbe'
  primary-fixed-dim: '#4edea3'
  on-primary-fixed: '#002113'
  on-primary-fixed-variant: '#005236'
  secondary-fixed: '#acedff'
  secondary-fixed-dim: '#4cd7f6'
  on-secondary-fixed: '#001f26'
  on-secondary-fixed-variant: '#004e5c'
  tertiary-fixed: '#e9ddff'
  tertiary-fixed-dim: '#d0bcff'
  on-tertiary-fixed: '#23005c'
  on-tertiary-fixed-variant: '#5516be'
  background: '#121316'
  on-background: '#e3e2e6'
  surface-variant: '#343538'
typography:
  headline-lg:
    fontFamily: Geist
    fontSize: 28px
    fontWeight: '600'
    lineHeight: 36px
    letterSpacing: -0.02em
  headline-lg-mobile:
    fontFamily: Geist
    fontSize: 22px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: -0.015em
  headline-md:
    fontFamily: Geist
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: -0.015em
  headline-sm:
    fontFamily: Geist
    fontSize: 15px
    fontWeight: '600'
    lineHeight: 20px
    letterSpacing: -0.01em
  body-lg:
    fontFamily: Geist
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-md:
    fontFamily: Geist
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
  body-sm:
    fontFamily: Geist
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
  code-lg:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '500'
    lineHeight: 18px
  code-md:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
  code-sm:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '400'
    lineHeight: 14px
  label-md:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '600'
    lineHeight: 14px
    letterSpacing: 0.04em
  label-sm:
    fontFamily: JetBrains Mono
    fontSize: 10px
    fontWeight: '600'
    lineHeight: 12px
    letterSpacing: 0.05em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  gutter: 0.75rem
  gutter-desktop: 1rem
  margin: 0.75rem
  margin-desktop: 1.25rem
  space-xs: 0.25rem
  space-sm: 0.375rem
  space-md: 0.75rem
  space-lg: 1rem
  space-xl: 1.5rem
---

## Brand & Style

This design system establishes a high-density, pro-grade utility interface tailored for engineers, devops specialists, and technical leads. Drawing inspiration from modern engineering suites like Linear, Vercel, and Raycast, the experience feels immediate, keyboard-centric, and distraction-free.

The visual style blends **technical minimalism** with **precise micro-borders** and subtle surface depth. Information density is treated as a core feature rather than a compromise: screen real estate is optimized for rapid telemetry scanning, terminal parity, and inline debugging. The UI prioritizes visual quietness by default, relying on razor-thin dividers and strict contrast hierarchy rather than heavy container blocks, allowing execution state and semantic diagnostics to stand out immediately.

## Colors

The palette is engineered around deep obsidian and slate foundations, eliminating screen glare during sustained technical operations while maintaining AAA contrast for monospace telemetry and code fragments.

### Palette Architecture
- **Canvas Base (`#08090C`)**: Deep obsidian base for the overall window background and outermost application shells.
- **Surface Elevation 1 (`#0E1015`)**: Default panel, drawer, and split-pane background.
- **Surface Elevation 2 (`#141721`)**: Elevated cards, toolbars, dropdown popovers, and contextual modals.
- **Border Subtle (`#1F2430`)**: Micro-borders separating high-density data tables, splitters, and unselected states.
- **Border Strong (`#2E3446`)**: Focus rings, active partition boundaries, and hover stroke states.
- **Primary / Emerald (`#10B981`)**: Signals healthy states, passing builds, runtime activations, and positive commit signatures.
- **Secondary / Cyan (`#06B6D4`)**: Used for telemetry readouts, environment scopes (`production`, `edge`), and proxy connections.
- **Tertiary / Violet (`#8B5CF6`)**: Distinguishes pro badges, staging environments, release tags, and deep-inspection triggers.
- **Warning / Amber (`#F59E0B`)**: Non-blocking diagnostics, path warnings, and resource pressure indicators.
- **Critical / Crimson (`#EF4444`)**: Uncaught exceptions, broken pipelines, merge conflicts, and destructive kill commands.
- **Text High-Contrast (`#F3F4F6`)**: Primary terminal outputs, system headers, and critical tokens.
- **Text Muted (`#94A3B8`)**: Secondary metrics, table column descriptors, and timestamps.
- **Text Dim (`#475569`)**: Inactive hotkeys, line numbers, and tree guide connectors.

## Typography

Typography balances typographic speed and mechanical clarity. **Geist** serves as the structural core for navigation, command titles, and analytical labels, providing tight optical kerning that excels at high data density. **JetBrains Mono** is strictly implemented for machine-readable strings: system paths, Git hashes, CLI arguments, environment keys, status indicators, and keyboard shortcut chips.

All monospace tokens use tabular lining numbers by default (`tnum`) to maintain exact horizontal alignment across tabular metrics and resource usage counters. Headers feature subtle negative tracking to preserve structural tension without decreasing legibility.

## Layout & Spacing

The layout model is anchored on a **fluid, pane-oriented workbench** rather than standard marketing grid systems. Desktop viewports prioritize multi-column, resize-capable split panels (e.g., File Tree `240px`, Center Workarea `flex-1`, Telemetry Sidebar `320px`). 

### Spatial Density
- Base increments scale on a compact 4px base (`0.25rem`), enabling compact tables and command palettes.
- Workstation layouts snap to strict structural gutters of `0.75rem` (12px) on mobile/tablet viewports and `1rem` (16px) on wide displays.
- Outer canvas margins remain compact (`1.25rem` / 20px) to maximize workable terminal output.

### Responsive Behaviors
- **Mobile (< 768px)**: Collapses multi-pane splitters into stacked bottom sheets or full-screen overlays with swipe-to-dismiss command bars. Font scale drops smoothly, while monospace line heights remain fixed to avoid multi-line hash breakage.
- **Tablet (768px - 1024px)**: Secondary inspection panels become slide-over drawers triggered via hotkey or edge toggle.
- **Desktop (> 1024px)**: Full multi-pane parity with persistent tool strips, inline split-screen diffs, and sticky status feet.

## Elevation & Depth

Visual depth is achieved through **tonal stacking and micro-borders** rather than heavy drop shadows.

- **Level 0 (App Canvas)**: Solid `#08090C`, non-interactive base plane.
- **Level 1 (Docked Surfaces & Panels)**: `#0E1015` framed by a 1px solid border of `#1F2430`.
- **Level 2 (Floating Popovers, Command Palettes, Menus)**: `#141721` with a 1px solid `#2E3446` stroke, accompanied by a targeted ambient shadow: `0 12px 32px -4px rgba(0, 0, 0, 0.65), 0 0 0 1px rgba(255, 255, 255, 0.04) inset`.
- **Level 3 (Modal Dialogs & Critical Kill-Switches)**: Stacked above a `#00000080` backdrop blur (8px) with high-contrast `#2E3446` outline containment.

Interactive rows and items rely on subtle luminance shifts (hovering to `#141721` from `#0E1015`) rather than high-contrast fill swaps, avoiding visual fatigue during rapid cursor movement.

## Shapes

The interface embraces a **disciplined, soft-rectilinear geometry** (`roundedness: 1`). Radii stay tight to mirror professional desktop OS engineering tools:

- **Base Components (Inputs, Buttons, Badges, Table Rows)**: `4px` (`0.25rem`) corner radius.
- **Floating Containers (Flyouts, Command Palettes, Cards)**: `6px` (`rounded-lg`) to `8px` (`rounded-xl`).
- **Pills and Badges**: Retain a strict `4px` subtle radius—full pill radii (`9999px`) are prohibited to avoid playful, non-technical visual cues.

## Components

### Buttons
- **Primary**: Emerald fill (`#10B981`) with rich dark obsidian typography (`#08090C`, font weight 600) for instant identification of the singular primary action. Hover: `#059669`.
- **Secondary (Default)**: Background `#141721`, border 1px `#1F2430`, text `#F3F4F6`. Hover: border `#2E3446`, text `#FFFFFF`.
- **Ghost / Tool**: Transparent background, text `#94A3B8`. Hover: background `#141721`, text `#F3F4F6`.
- **Destructive**: Background `#EF444415`, border 1px `#EF444440`, text `#EF4444`. Hover: background `#EF4444`, text `#FFFFFF`.
- All buttons include an inline shortcut badge right-aligned when applicable (e.g., `⌘K`, `↵`).

### Command Palette & Inputs
- **Inputs**: Background `#0E1015`, border 1px `#1F2430`, text `#F3F4F6`, placeholder `#475569`. Focus state transitions border to `#10B981` with a `0 0 0 1px #10B981` glow outline.
- **Command Palette**: Centered modal with fixed width (`640px`), containing an inline search header, quick-action chips, categorized row items, and sticky footer displaying active keyboard navigators (`↑↓ to navigate`, `esc to close`).

### Chips, Tags & Status Pills
- Compact padding (`2px 6px`), rendered strictly with `label-sm` or `code-sm` typography.
- **Health Indicators**: Preceded by a 6px circular indicator dot with a soft pulsing ping animation when active (`#10B981`).
- **Semantic Scopes**:
  - Stable/Active: Emerald tint (`#10B9811A`), border `#10B98140`, text `#10B981`.
  - Staging/Edge: Cyan tint (`#06B6D41A`), border `#06B6D440`, text `#06B6D4`.
  - Pro/Experimental: Violet tint (`#8B5CF61A`), border `#8B5CF640`, text `#8B5CF6`.
  - Deprecation/Warning: Amber tint (`#F59E0B1A`), border `#F59E0B40`, text `#F59E0B`.

### Lists & Data Tables
- High-density row height (`32px` for compact, `40px` standard).
- Alternating zebra backgrounds are avoided; row borders use 1px solid `#1F2430`.
- Hover highlights row with `#141721`.
- Monospace alignment for memory offsets, latency stats, and Git hashes.

### Checkboxes & Radios
- Size `14px` by `14px`, corner radius `3px`.
- Unchecked: `#0E1015` base with `#2E3446` border.
- Checked: `#10B981` base with obsidian icon tick, crisp alignment with monospace data rows.

### Cards & Panels
- Flat `#0E1015` surface enclosed in `#1F2430` micro-border.
- Header regions feature `space-md` padding with integrated actions (refresh, split, copy JSON) and an absolute bottom separator line of 1px `#1F2430`.