"""Export DevToolkit and DevSpotlight SVG logos and icons extracted from the UI."""

import os
from pathlib import Path
import xml.etree.ElementTree as ET

def generate_svg_assets():
    root = Path(__file__).resolve().parent.parent
    design_dir = root / "design"
    design_dir.mkdir(parents=True, exist_ok=True)

    # =========================================================================
    # 1. DevToolkit Icon (512x512 Master App / UI Mark)
    # =========================================================================
    tk_icon = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">
  <defs>
    <!-- Background Card 3D Depth Gradient (Cyber Emerald Obsidian) -->
    <linearGradient id="tkCardGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#11261c"/>
      <stop offset="45%" stop-color="#0c1a14"/>
      <stop offset="100%" stop-color="#060e0a"/>
    </linearGradient>

    <!-- Outer Squircle 3D Border Gradient -->
    <linearGradient id="tkBorderGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#34d399" stop-opacity="0.75"/>
      <stop offset="50%" stop-color="#10b981" stop-opacity="0.25"/>
      <stop offset="100%" stop-color="#059669" stop-opacity="0.55"/>
    </linearGradient>

    <!-- 3D Lightning Bolt Main Gradient -->
    <linearGradient id="tkBoltGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#6ee7b7"/>
      <stop offset="45%" stop-color="#10b981"/>
      <stop offset="100%" stop-color="#047857"/>
    </linearGradient>

    <!-- 3D Inner Highlight Facet Gradient -->
    <linearGradient id="tkInnerGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#ecfdf5" stop-opacity="0.9"/>
      <stop offset="50%" stop-color="#a7f3d0" stop-opacity="0.65"/>
      <stop offset="100%" stop-color="#34d399" stop-opacity="0.3"/>
    </linearGradient>

    <!-- Code Chevrons Gradient -->
    <linearGradient id="tkChevronGrad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#a7f3d0"/>
      <stop offset="45%" stop-color="#34d399"/>
      <stop offset="100%" stop-color="#059669"/>
    </linearGradient>

    <filter id="tkBoltGlow" x="-30%" y="-30%" width="160%" height="160%">
      <feDropShadow dx="0" dy="0" stdDeviation="16" flood-color="#10b981" flood-opacity="0.65"/>
    </filter>

    <filter id="tkChevronGlow" x="-30%" y="-30%" width="160%" height="160%">
      <feDropShadow dx="0" dy="2" stdDeviation="4" flood-color="#000000" flood-opacity="0.5"/>
      <feDropShadow dx="0" dy="0" stdDeviation="8" flood-color="#10b981" flood-opacity="0.4"/>
    </filter>

    <clipPath id="tkSquircleClip">
      <rect x="46" y="46" width="420" height="420" rx="96"/>
    </clipPath>
  </defs>

  <!-- Centered Icon Mark Container Tile (Standalone Squircle) -->
  <g filter="url(#tkGlow)">
    <rect x="46" y="46" width="420" height="420" rx="96" fill="url(#tkCardGrad)" stroke="url(#tkBorderGrad)" stroke-width="4"/>
    <!-- Subtle Inner Border Highlight -->
    <rect x="48" y="48" width="416" height="416" rx="94" fill="none" stroke="#34d399" stroke-width="1.5" stroke-opacity="0.28"/>
  </g>

  <!-- Clipped Interior Accents -->
  <g clip-path="url(#tkSquircleClip)">
    <!-- Top-Left Ambient Light Beam -->
    <path d="M46 46 L260 46 L380 466 L46 466 Z" fill="#10b981" fill-opacity="0.035"/>

    <!-- Subtle Developer Precision Crosshairs / Grid -->
    <line x1="46" y1="256" x2="466" y2="256" stroke="#10b981" stroke-opacity="0.08" stroke-width="1.5" stroke-dasharray="6 6"/>
    <line x1="256" y1="46" x2="256" y2="466" stroke="#10b981" stroke-opacity="0.08" stroke-width="1.5" stroke-dasharray="6 6"/>

    <!-- Concentric Workstation Diagnostics Rings -->
    <circle cx="256" cy="256" r="168" fill="none" stroke="#10b981" stroke-opacity="0.09" stroke-width="1.5" stroke-dasharray="8 8"/>
    <circle cx="256" cy="256" r="118" fill="none" stroke="#10b981" stroke-opacity="0.06" stroke-width="1"/>

    <!-- Left Code Chevron with 3D Bevel -->
    <g filter="url(#tkChevronGlow)">
      <path d="M172 192 L114 256 L172 320" fill="none" stroke="url(#tkChevronGrad)" stroke-width="20" stroke-linecap="round" stroke-linejoin="round"/>
    </g>

    <!-- Right Code Chevron with 3D Bevel -->
    <g filter="url(#tkChevronGlow)">
      <path d="M340 192 L398 256 L340 320" fill="none" stroke="url(#tkChevronGrad)" stroke-width="20" stroke-linecap="round" stroke-linejoin="round"/>
    </g>

    <!-- Original DevToolkit Central Lightning Bolt in 3D -->
    <g filter="url(#tkBoltGlow)">
      <!-- Main Bolt Body -->
      <path d="M282 108 L190 256 L256 256 L224 404 L330 250 L264 250 Z" fill="url(#tkBoltGrad)"/>
      <!-- 3D Bevel / Top-Facet Highlight -->
      <path d="M272 130 L204 248 L250 248 L232 362 L308 254 L262 254 Z" fill="url(#tkInnerGrad)"/>
    </g>
  </g>
</svg>"""

    # =========================================================================
    # 2. DevSpotlight Icon (512x512 Master App / UI Mark)
    # =========================================================================
    sp_icon = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">
  <defs>
    <linearGradient id="spCardGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#16273d"/>
      <stop offset="45%" stop-color="#0e1522"/>
      <stop offset="100%" stop-color="#080b11"/>
    </linearGradient>
    <linearGradient id="spBoltGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#7dd3fc"/>
      <stop offset="45%" stop-color="#38bdf8"/>
      <stop offset="100%" stop-color="#0284c7"/>
    </linearGradient>
    <linearGradient id="spBorderGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#38bdf8" stop-opacity="0.65"/>
      <stop offset="50%" stop-color="#38bdf8" stop-opacity="0.25"/>
      <stop offset="100%" stop-color="#0284c7" stop-opacity="0.45"/>
    </linearGradient>
    <filter id="spGlow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="12" stdDeviation="18" flood-color="#000000" flood-opacity="0.65"/>
      <feDropShadow dx="0" dy="0" stdDeviation="24" flood-color="#38bdf8" flood-opacity="0.25"/>
    </filter>
    <filter id="spBoltGlow" x="-30%" y="-30%" width="160%" height="160%">
      <feDropShadow dx="0" dy="0" stdDeviation="16" flood-color="#38bdf8" flood-opacity="0.65"/>
    </filter>
    <clipPath id="spSquircleClip">
      <rect x="46" y="46" width="420" height="420" rx="96"/>
    </clipPath>
  </defs>

  <!-- Centered Icon Mark Container Tile (Standalone Squircle) -->
  <g filter="url(#spGlow)">
    <rect x="46" y="46" width="420" height="420" rx="96" fill="url(#spCardGrad)" stroke="url(#spBorderGrad)" stroke-width="4"/>
    <!-- Subtle Inner Border Highlight -->
    <rect x="48" y="48" width="416" height="416" rx="94" fill="none" stroke="#38bdf8" stroke-width="1.5" stroke-opacity="0.25"/>
  </g>

  <!-- Clipped Interior Accents -->
  <g clip-path="url(#spSquircleClip)">
    <!-- Spotlight Conical / Aperture Light Beam Accent from top-left -->
    <path d="M46 46 L260 46 L380 466 L46 466 Z" fill="#38bdf8" fill-opacity="0.035"/>

    <!-- Concentric Aperture / Spotlight Guide Rings -->
    <circle cx="256" cy="256" r="172" fill="none" stroke="#38bdf8" stroke-opacity="0.12" stroke-width="2" stroke-dasharray="10 10"/>
    <circle cx="256" cy="256" r="126" fill="none" stroke="#38bdf8" stroke-opacity="0.08" stroke-width="1.5"/>
    <circle cx="256" cy="256" r="70" fill="none" stroke="#38bdf8" stroke-opacity="0.05" stroke-width="1.5"/>
  </g>

  <!-- Central DevSpotlight Lightning Bolt with Glow -->
  <g filter="url(#spBoltGlow)" transform="translate(148, 108) scale(0.565)">
    <path d="M0 256L28.5 28c2-16 15.6-28 31.8-28H228.9c15 0 27.1 12.1 27.1 27.1c0 3.2-.6 6.5-1.7 9.5L208 160H347.3c20.2 0 36.7 16.4 36.7 36.7c0 7.4-2.2 14.6-6.4 20.7l-192.2 281c-5.9 8.6-15.6 13.7-25.9 13.7h-2.9c-15.7 0-28.5-12.8-28.5-28.5c0-2.3 .3-4.6 .9-6.9L176 288H32c-17.7 0-32-14.3-32-32z" fill="url(#spBoltGrad)"/>
    <!-- Top Face Highlight Accent -->
    <path d="M28.5 28c2-16 15.6-28 31.8-28H228.9c15 0 27.1 12.1 27.1 27.1c0 3.2-.6 6.5-1.7 9.5L208 160H347.3c14 0 24 7 30 16L185 282L206 166L48 166L28.5 28z" fill="#e0f2fe" opacity="0.28"/>
  </g>
</svg>"""

    # =========================================================================
    # 3. DevToolkit Logo (Horizontal Brand Lockup: Mark + Typography)
    # =========================================================================
    tk_logo = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 460 110" width="460" height="110">
  <defs>
    <!-- Background Card 3D Depth Gradient -->
    <linearGradient id="tkLogoCardGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#11261c"/>
      <stop offset="50%" stop-color="#0c1a14"/>
      <stop offset="100%" stop-color="#060e0a"/>
    </linearGradient>

    <!-- 3D Lightning Bolt Gradient -->
    <linearGradient id="tkLogoBoltGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#6ee7b7"/>
      <stop offset="45%" stop-color="#10b981"/>
      <stop offset="100%" stop-color="#047857"/>
    </linearGradient>

    <!-- 3D Inner Highlight Facet Gradient -->
    <linearGradient id="tkLogoInnerGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#ecfdf5" stop-opacity="0.9"/>
      <stop offset="50%" stop-color="#a7f3d0" stop-opacity="0.65"/>
      <stop offset="100%" stop-color="#34d399" stop-opacity="0.3"/>
    </linearGradient>

    <!-- Code Chevrons Gradient -->
    <linearGradient id="tkLogoChevronGrad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#a7f3d0"/>
      <stop offset="45%" stop-color="#34d399"/>
      <stop offset="100%" stop-color="#059669"/>
    </linearGradient>

    <filter id="tkLogoBoltGlow" x="-30%" y="-30%" width="160%" height="160%">
      <feDropShadow dx="0" dy="0" stdDeviation="5" flood-color="#10b981" flood-opacity="0.6"/>
    </filter>

    <filter id="tkLogoChevronGlow" x="-30%" y="-30%" width="160%" height="160%">
      <feDropShadow dx="0" dy="1" stdDeviation="2" flood-color="#000000" flood-opacity="0.4"/>
      <feDropShadow dx="0" dy="0" stdDeviation="3" flood-color="#10b981" flood-opacity="0.3"/>
    </filter>

    <!-- Ambient Shadow & Glow -->
    <filter id="tkLogoGlow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="4" stdDeviation="8" flood-color="#000000" flood-opacity="0.5"/>
      <feDropShadow dx="0" dy="0" stdDeviation="10" flood-color="#10b981" flood-opacity="0.3"/>
    </filter>
  </defs>

  <!-- Icon Badge (Left) -->
  <g transform="translate(14, 14)">
    <g filter="url(#tkLogoGlow)">
      <rect x="0" y="0" width="82" height="82" rx="18" fill="url(#tkLogoCardGrad)" stroke="#10b981" stroke-opacity="0.45" stroke-width="1.5"/>
      <rect x="1" y="1" width="80" height="80" rx="17" fill="none" stroke="#34d399" stroke-width="1" stroke-opacity="0.22"/>
    </g>

    <!-- Concentric Guide Rings -->
    <circle cx="41" cy="41" r="28" fill="none" stroke="#10b981" stroke-opacity="0.12" stroke-width="1" stroke-dasharray="3 3"/>
    <circle cx="41" cy="41" r="18" fill="none" stroke="#10b981" stroke-opacity="0.08" stroke-width="1"/>

    <!-- Left Code Chevron with 3D Bevel -->
    <g filter="url(#tkLogoChevronGlow)">
      <path d="M27 31 L18 41 L27 51" fill="none" stroke="url(#tkLogoChevronGrad)" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"/>
    </g>

    <!-- Right Code Chevron with 3D Bevel -->
    <g filter="url(#tkLogoChevronGlow)">
      <path d="M55 31 L64 41 L55 51" fill="none" stroke="url(#tkLogoChevronGrad)" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"/>
    </g>

    <!-- Original DevToolkit Lightning Bolt in 3D -->
    <g filter="url(#tkLogoBoltGlow)">
      <path d="M45 17 L30 41 L41 41 L36 65 L53 40 L42 40 Z" fill="url(#tkLogoBoltGrad)"/>
      <path d="M43 21 L33 39 L40 39 L37 57 L50 41 L42 41 Z" fill="url(#tkLogoInnerGrad)"/>
    </g>
  </g>

  <!-- Brand Typography (Right) -->
  <g transform="translate(116, 0)">
    <!-- Main Title -->
    <text x="0" y="52" font-family="'Geist', 'Segoe UI Variable', system-ui, -apple-system, sans-serif" font-size="34" font-weight="700" letter-spacing="-0.5">
      <tspan fill="#F3F4F6">Dev</tspan><tspan fill="#10B981">Toolkit</tspan>
    </text>

    <!-- Version Badge Pill aligned right after title -->
    <g transform="translate(196, 32)">
      <rect x="0" y="0" width="46" height="20" rx="5" fill="#10B981" fill-opacity="0.12" stroke="#10B981" stroke-opacity="0.35" stroke-width="1"/>
      <text x="23" y="14" font-family="'JetBrains Mono', 'Consolas', monospace" font-size="10.5" font-weight="600" fill="#10B981" text-anchor="middle">v0.5.1</text>
    </g>

    <!-- Subtitle Meta -->
    <text x="1" y="77" font-family="'JetBrains Mono', 'Consolas', monospace" font-size="10.5" font-weight="600" fill="#94A3B8" letter-spacing="2.5">WORKSTATION SUITE</text>
  </g>
</svg>"""

    # =========================================================================
    # 4. DevSpotlight Logo (Horizontal Brand Lockup: Mark + Typography)
    # =========================================================================
    sp_logo = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 480 110" width="480" height="110">
  <defs>
    <linearGradient id="spLogoCardGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#16273d"/>
      <stop offset="50%" stop-color="#0e1522"/>
      <stop offset="100%" stop-color="#080b11"/>
    </linearGradient>
    <linearGradient id="spLogoBoltGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#7dd3fc"/>
      <stop offset="45%" stop-color="#38bdf8"/>
      <stop offset="100%" stop-color="#0284c7"/>
    </linearGradient>
    <filter id="spLogoGlow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="4" stdDeviation="8" flood-color="#000000" flood-opacity="0.5"/>
      <feDropShadow dx="0" dy="0" stdDeviation="10" flood-color="#38bdf8" flood-opacity="0.3"/>
    </filter>
  </defs>

  <!-- Icon Badge (Left) -->
  <g transform="translate(14, 14)">
    <g filter="url(#spLogoGlow)">
      <rect x="0" y="0" width="82" height="82" rx="18" fill="url(#spLogoCardGrad)" stroke="#38bdf8" stroke-opacity="0.4" stroke-width="1.5"/>
      <rect x="1" y="1" width="80" height="80" rx="17" fill="none" stroke="#38bdf8" stroke-width="1" stroke-opacity="0.2"/>
    </g>

    <!-- Concentric Spotlight Rings -->
    <circle cx="41" cy="41" r="28" fill="none" stroke="#38bdf8" stroke-opacity="0.12" stroke-width="1" stroke-dasharray="3 3"/>
    <circle cx="41" cy="41" r="18" fill="none" stroke="#38bdf8" stroke-opacity="0.08" stroke-width="1"/>

    <!-- Cyan Lightning Bolt (FontAwesome bolt-lightning geometry scaled cleanly) -->
    <g transform="translate(23, 17) scale(0.095)">
      <path d="M0 256L28.5 28c2-16 15.6-28 31.8-28H228.9c15 0 27.1 12.1 27.1 27.1c0 3.2-.6 6.5-1.7 9.5L208 160H347.3c20.2 0 36.7 16.4 36.7 36.7c0 7.4-2.2 14.6-6.4 20.7l-192.2 281c-5.9 8.6-15.6 13.7-25.9 13.7h-2.9c-15.7 0-28.5-12.8-28.5-28.5c0-2.3 .3-4.6 .9-6.9L176 288H32c-17.7 0-32-14.3-32-32z" fill="url(#spLogoBoltGrad)"/>
      <path d="M28.5 28c2-16 15.6-28 31.8-28H228.9c15 0 27.1 12.1 27.1 27.1c0 3.2-.6 6.5-1.7 9.5L208 160H347.3c14 0 24 7 30 16L185 282L206 166L48 166L28.5 28z" fill="#e0f2fe" opacity="0.35"/>
    </g>
  </g>

  <!-- Brand Typography (Right) -->
  <g transform="translate(116, 0)">
    <!-- Main Title -->
    <text x="0" y="52" font-family="'Geist', 'Segoe UI Variable', system-ui, -apple-system, sans-serif" font-size="34" font-weight="700" letter-spacing="-0.5">
      <tspan fill="#F3F4F6">Dev</tspan><tspan fill="#38BDF8">Spotlight</tspan>
    </text>

    <!-- Version Badge Pill aligned right after title -->
    <g transform="translate(222, 32)">
      <rect x="0" y="0" width="46" height="20" rx="5" fill="#38BDF8" fill-opacity="0.12" stroke="#38BDF8" stroke-opacity="0.35" stroke-width="1"/>
      <text x="23" y="14" font-family="'JetBrains Mono', 'Consolas', monospace" font-size="10.5" font-weight="600" fill="#38BDF8" text-anchor="middle">v0.6.0</text>
    </g>

    <!-- Subtitle Meta -->
    <text x="1" y="77" font-family="'JetBrains Mono', 'Consolas', monospace" font-size="10.5" font-weight="600" fill="#94A3B8" letter-spacing="2.5">COMMAND PALETTE</text>
  </g>
</svg>"""

    # =========================================================================
    # 5. UI Badges (40x40 Micro Badges - Consistent with Icon and Logo):
    # =========================================================================
    # devtoolkit-ui-badge.svg (40x40 3D micro badge with chevrons + bolt)
    tk_ui_badge = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40" width="40" height="40">
  <defs>
    <!-- Background Card 3D Depth Gradient (Exact Match with Icon & Logo) -->
    <linearGradient id="uiTkCardGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#11261c"/>
      <stop offset="50%" stop-color="#0c1a14"/>
      <stop offset="100%" stop-color="#060e0a"/>
    </linearGradient>

    <!-- Outer 3D Border Gradient (Exact Match with Icon & Logo) -->
    <!-- <linearGradient id="uiTkBorderGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#34d399" stop-opacity="0.75"/>
      <stop offset="50%" stop-color="#10b981" stop-opacity="0.3"/>
      <stop offset="100%" stop-color="#059669" stop-opacity="0.55"/>
    </linearGradient> -->

    <!-- 3D Lightning Bolt Main Gradient -->
    <linearGradient id="uiTkBoltGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#6ee7b7"/>
      <stop offset="45%" stop-color="#10b981"/>
      <stop offset="100%" stop-color="#047857"/>
    </linearGradient>

    <!-- 3D Inner Highlight Facet Gradient -->
    <linearGradient id="uiTkInnerGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#ecfdf5" stop-opacity="0.9"/>
      <stop offset="50%" stop-color="#a7f3d0" stop-opacity="0.65"/>
      <stop offset="100%" stop-color="#34d399" stop-opacity="0.3"/>
    </linearGradient>

    <!-- Code Chevrons Gradient -->
    <linearGradient id="uiTkChevronGrad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#a7f3d0"/>
      <stop offset="45%" stop-color="#34d399"/>
      <stop offset="100%" stop-color="#059669"/>
    </linearGradient>
  </defs>

  <!-- Card Squircle with matching 3D border -->
  <rect x="0.5" y="0.5" width="39" height="39" rx="8" fill="url(#uiTkCardGrad)" stroke="url(#uiTkBorderGrad)" stroke-width="1.2" filter="url(#uiTkShadow)"/>
  <rect x="0.5" y="0.5" width="39" height="39" rx="8" fill="none" stroke="#34d399" stroke-width="0.8" stroke-opacity="0.22"/>

  <!-- Left Code Chevron with breathing room -->
  <g filter="url(#uiTkChevronGlow)">
    <path d="M12.5 15 L7.5 20 L12.5 25" fill="none" stroke="url(#uiTkChevronGrad)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
  </g>

  <!-- Right Code Chevron with breathing room -->
  <g filter="url(#uiTkChevronGlow)">
    <path d="M27.5 15 L32.5 20 L27.5 25" fill="none" stroke="url(#uiTkChevronGrad)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
  </g>

  <!-- Central DevToolkit Lightning Bolt -->
  <g filter="url(#uiTkBoltGlow)">
    <path d="M22 8 L14.5 20 L20 20 L17.5 32 L26 19.5 L20.5 19.5 Z" fill="url(#uiTkBoltGrad)"/>
    <path d="M21 10 L16 19 L19.5 19 L18 28 L24.5 20 L20.5 20 Z" fill="url(#uiTkInnerGrad)"/>
  </g>
</svg>"""

    # devspotlight-ui-badge.svg (40x40 3D micro badge)
    sp_ui_badge = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40" width="40" height="40">
  <defs>
    <linearGradient id="uiSpGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#38BDF8" stop-opacity="0.18"/>
      <stop offset="100%" stop-color="#080B11"/>
    </linearGradient>
    <linearGradient id="uiSpBoltGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#7DD3FC"/>
      <stop offset="45%" stop-color="#38BDF8"/>
      <stop offset="100%" stop-color="#0284C7"/>
    </linearGradient>
    <filter id="uiSpShadow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="1" stdDeviation="2" flood-color="#000000" flood-opacity="0.4"/>
      <feDropShadow dx="0" dy="0" stdDeviation="3" flood-color="#38BDF8" flood-opacity="0.3"/>
    </filter>
  </defs>
  <rect x="0.5" y="0.5" width="39" height="39" rx="8" fill="url(#uiSpGrad)" stroke="#38BDF8" stroke-opacity="0.35" stroke-width="1" filter="url(#uiSpShadow)"/>
  <rect x="1.5" y="1.5" width="37" height="37" rx="7" fill="none" stroke="#7DD3FC" stroke-opacity="0.2" stroke-width="0.75"/>
  <!-- Central 3D Lightning Bolt -->
  <g transform="translate(12, 9) scale(0.043)">
    <path fill="url(#uiSpBoltGrad)" d="M0 256L28.5 28c2-16 15.6-28 31.8-28H228.9c15 0 27.1 12.1 27.1 27.1c0 3.2-.6 6.5-1.7 9.5L208 160H347.3c20.2 0 36.7 16.4 36.7 36.7c0 7.4-2.2 14.6-6.4 20.7l-192.2 281c-5.9 8.6-15.6 13.7-25.9 13.7h-2.9c-15.7 0-28.5-12.8-28.5-28.5c0-2.3 .3-4.6 .9-6.9L176 288H32c-17.7 0-32-14.3-32-32z"/>
    <path d="M28.5 28c2-16 15.6-28 31.8-28H228.9c15 0 27.1 12.1 27.1 27.1c0 3.2-.6 6.5-1.7 9.5L208 160H347.3c14 0 24 7 30 16L185 282L206 166L48 166L28.5 28z" fill="#E0F2FE" opacity="0.35"/>
  </g>
</svg>"""

    file_map = {
        "devtoolkit-icon.svg": tk_icon,
        "devspotlight-icon.svg": sp_icon,
        "devtoolkit-logo.svg": tk_logo,
        "devspotlight-logo.svg": sp_logo,
        "devtoolkit.svg": tk_logo,
        "devspotlight.svg": sp_logo,
        "devtoolkit-ui-badge.svg": tk_ui_badge,
        "devspotlight-ui-badge.svg": sp_ui_badge,
    }

    print(f"Target directory: {design_dir}")
    for name, content in file_map.items():
        ET.fromstring(content)
        path = design_dir / name
        path.write_text(content.strip(), encoding="utf-8")
        print(f"Exported: {name} ({len(content)} bytes)")

if __name__ == "__main__":
    generate_svg_assets()
