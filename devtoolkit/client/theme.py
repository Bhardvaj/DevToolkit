"""Modern dark theme design tokens and ttk styling for DevToolkit Native UI."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Dict


class Colors:
    """Color palette matching DevToolkit dark glassmorphic interface."""

    BG_MAIN = "#0B0F19"
    BG_SIDEBAR = "#070A10"
    BG_CARD = "#131B2E"
    BG_CARD_HOVER = "#1E293B"
    BG_INPUT = "#0F172A"

    BORDER = "#1E293B"
    BORDER_LIGHT = "#334155"

    TEXT_PRIMARY = "#F8FAFC"
    TEXT_SECONDARY = "#94A3B8"
    TEXT_MUTED = "#64748B"

    ACCENT = "#0EA5E9"
    ACCENT_HOVER = "#38BDF8"
    ACCENT_LIGHT = "rgba(14, 165, 233, 0.15)"

    SUCCESS = "#10B981"
    WARNING = "#F59E0B"
    ERROR = "#EF4444"
    INFO = "#6366F1"


class Fonts:
    """Typography scales using native system fonts."""

    TITLE = ("Segoe UI", 16, "bold")
    SUBTITLE = ("Segoe UI", 12, "bold")
    SECTION = ("Segoe UI", 11, "bold")
    BODY = ("Segoe UI", 10)
    BODY_BOLD = ("Segoe UI", 10, "bold")
    SMALL = ("Segoe UI", 9)
    SMALL_BOLD = ("Segoe UI", 9, "bold")
    CODE = ("Consolas", 9)
    CODE_BOLD = ("Consolas", 9, "bold")


def apply_theme(root: tk.Tk) -> ttk.Style:
    """Apply modern dark glassmorphic styling across all ttk widgets."""
    style = ttk.Style(root)

    # Use 'clam' as cross-platform baseline theme
    available = style.theme_names()
    if "clam" in available:
        style.theme_use("clam")

    # Configure root background
    root.configure(bg=Colors.BG_MAIN)

    # Base Frame Styles
    style.configure("TFrame", background=Colors.BG_MAIN)
    style.configure("Main.TFrame", background=Colors.BG_MAIN)
    style.configure("Sidebar.TFrame", background=Colors.BG_SIDEBAR)
    style.configure("Card.TFrame", background=Colors.BG_CARD)
    style.configure("Header.TFrame", background=Colors.BG_MAIN)
    style.configure("Footer.TFrame", background=Colors.BG_SIDEBAR)

    # Label Styles
    style.configure(
        "TLabel",
        background=Colors.BG_MAIN,
        foreground=Colors.TEXT_PRIMARY,
        font=Fonts.BODY,
    )
    style.configure(
        "Header.TLabel",
        background=Colors.BG_MAIN,
        foreground=Colors.TEXT_PRIMARY,
        font=Fonts.TITLE,
    )
    style.configure(
        "Subheader.TLabel",
        background=Colors.BG_MAIN,
        foreground=Colors.TEXT_SECONDARY,
        font=Fonts.BODY,
    )
    style.configure(
        "SidebarHeader.TLabel",
        background=Colors.BG_SIDEBAR,
        foreground=Colors.TEXT_PRIMARY,
        font=Fonts.SUBTITLE,
    )
    style.configure(
        "CardTitle.TLabel",
        background=Colors.BG_CARD,
        foreground=Colors.TEXT_PRIMARY,
        font=Fonts.SECTION,
    )
    style.configure(
        "CardText.TLabel",
        background=Colors.BG_CARD,
        foreground=Colors.TEXT_SECONDARY,
        font=Fonts.BODY,
    )
    style.configure(
        "CardMuted.TLabel",
        background=Colors.BG_CARD,
        foreground=Colors.TEXT_MUTED,
        font=Fonts.SMALL,
    )
    style.configure(
        "BadgeSuccess.TLabel",
        background=Colors.BG_CARD,
        foreground=Colors.SUCCESS,
        font=Fonts.SMALL_BOLD,
    )
    style.configure(
        "BadgeWarning.TLabel",
        background=Colors.BG_CARD,
        foreground=Colors.WARNING,
        font=Fonts.SMALL_BOLD,
    )
    style.configure(
        "BadgeError.TLabel",
        background=Colors.BG_CARD,
        foreground=Colors.ERROR,
        font=Fonts.SMALL_BOLD,
    )

    # Button Styles
    style.configure(
        "TButton",
        background=Colors.BG_CARD,
        foreground=Colors.TEXT_PRIMARY,
        font=Fonts.BODY_BOLD,
        borderwidth=0,
        focusthickness=0,
        padding=(12, 6),
    )
    style.map(
        "TButton",
        background=[("active", Colors.BG_CARD_HOVER), ("pressed", Colors.BORDER)],
        foreground=[("active", Colors.TEXT_PRIMARY)],
    )

    style.configure(
        "Primary.TButton",
        background=Colors.ACCENT,
        foreground="#FFFFFF",
        font=Fonts.BODY_BOLD,
        borderwidth=0,
        padding=(14, 7),
    )
    style.map(
        "Primary.TButton",
        background=[("active", Colors.ACCENT_HOVER), ("pressed", Colors.ACCENT)],
    )

    style.configure(
        "Nav.TButton",
        background=Colors.BG_SIDEBAR,
        foreground=Colors.TEXT_SECONDARY,
        font=Fonts.BODY,
        anchor="w",
        padding=(12, 10),
        borderwidth=0,
    )
    style.map(
        "Nav.TButton",
        background=[("active", Colors.BG_CARD), ("pressed", Colors.BG_CARD_HOVER)],
        foreground=[("active", Colors.TEXT_PRIMARY)],
    )

    style.configure(
        "ActiveNav.TButton",
        background=Colors.BG_CARD,
        foreground=Colors.ACCENT,
        font=Fonts.BODY_BOLD,
        anchor="w",
        padding=(12, 10),
        borderwidth=0,
    )

    # Entry & Input Styles
    style.configure(
        "TEntry",
        fieldbackground=Colors.BG_INPUT,
        foreground=Colors.TEXT_PRIMARY,
        insertcolor=Colors.TEXT_PRIMARY,
        padding=6,
    )

    # Treeview / Table Styles
    style.configure(
        "Treeview",
        background=Colors.BG_CARD,
        fieldbackground=Colors.BG_CARD,
        foreground=Colors.TEXT_PRIMARY,
        font=Fonts.BODY,
        rowheight=28,
        borderwidth=0,
    )
    style.configure(
        "Treeview.Heading",
        background=Colors.BG_SIDEBAR,
        foreground=Colors.TEXT_SECONDARY,
        font=Fonts.SMALL_BOLD,
        padding=(8, 6),
        borderwidth=0,
    )
    style.map(
        "Treeview",
        background=[("selected", Colors.ACCENT)],
        foreground=[("selected", "#FFFFFF")],
    )

    # Scrollbar
    style.configure(
        "Vertical.TScrollbar",
        background=Colors.BG_CARD,
        troughcolor=Colors.BG_MAIN,
        borderwidth=0,
        arrowsize=12,
    )

    return style
