"""Environment Diagnostics View for DevToolkit Python Native UI."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Any, Dict, List, Optional

from devtoolkit.client.api import DevToolkitClient
from devtoolkit.client.dialogs.tool_inspector import ToolInspectorModal
from devtoolkit.client.state import ClientState
from devtoolkit.client.theme import Colors, Fonts

logger = logging.getLogger(__name__)


class EnvironmentView(ttk.Frame):
    """Workstation Environment Diagnostics view with tool categorization, filtering, and deep inspection."""

    def __init__(
        self,
        parent: ttk.Frame,
        client: DevToolkitClient,
        state: ClientState,
    ):
        super().__init__(parent, style="Main.TFrame")
        self.client = client
        self.state = state

        self._filter_category = "all"
        self._filter_query = ""

        self._build_header()
        self._build_metrics_cards()
        self._build_filters_bar()
        self._build_tools_table()
        self._build_table_actions()

        # Subscribe to State Changes
        self._unsub_tools = self.state.subscribe("tools_updated", self._on_tools_updated)
        self._populate_table()

    def destroy(self) -> None:
        """Unsubscribe from state events when view is destroyed."""
        if hasattr(self, "_unsub_tools") and self._unsub_tools:
            self._unsub_tools()
        super().destroy()

    # -------------------------------------------------------------------------
    # Layout Builders
    # -------------------------------------------------------------------------

    def _build_header(self) -> None:
        """Top view header."""
        header_row = ttk.Frame(self, style="Main.TFrame")
        header_row.pack(fill="x", pady=(0, 16))

        title = ttk.Label(header_row, text="Workstation Environment Diagnostics", style="Header.TLabel")
        title.pack(side="left")

        rescan_btn = ttk.Button(
            header_row,
            text="🔄 Re-scan Environment",
            style="Primary.TButton",
            command=self._trigger_audit,
        )
        rescan_btn.pack(side="right")

    def _build_metrics_cards(self) -> None:
        """Summary cards showing total tools, installed, missing, and health score."""
        self.metrics_frame = ttk.Frame(self, style="Main.TFrame")
        self.metrics_frame.pack(fill="x", pady=(0, 16))

        self.metric_labels: Dict[str, ttk.Label] = {}

        metrics_def = [
            ("total", "Total Tools", "--", "CardTitle.TLabel"),
            ("installed", "Installed", "--", "BadgeSuccess.TLabel"),
            ("missing", "Missing", "--", "BadgeError.TLabel"),
            ("health", "Health Score", "--", "BadgeSuccess.TLabel"),
        ]

        for col, (key, title_text, val_text, badge_style) in enumerate(metrics_def):
            card = ttk.Frame(self.metrics_frame, style="Card.TFrame", padding=(16, 12))
            card.grid(row=0, column=col, sticky="nsew", padx=6 if col > 0 else 0)
            self.metrics_frame.columnconfigure(col, weight=1)

            t_lbl = ttk.Label(card, text=title_text, style="CardMuted.TLabel")
            t_lbl.pack(anchor="w")

            v_lbl = ttk.Label(card, text=val_text, style=badge_style)
            v_lbl.pack(anchor="w", pady=(4, 0))
            self.metric_labels[key] = v_lbl

        self._update_metrics()

    def _build_filters_bar(self) -> None:
        """Search and category filter controls."""
        filters_frame = ttk.Frame(self, style="Main.TFrame")
        filters_frame.pack(fill="x", pady=(0, 12))

        # Search Box
        search_frame = ttk.Frame(filters_frame, style="Main.TFrame")
        search_frame.pack(side="left", fill="x", expand=True, padx=(0, 12))

        ttk.Label(search_frame, text="🔍 Filter Tools:", style="CardMuted.TLabel").pack(side="left", padx=(0, 8))

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *args: self._on_filter_changed())
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var)
        search_entry.pack(side="left", fill="x", expand=True)

        # Category Combobox
        cat_frame = ttk.Frame(filters_frame, style="Main.TFrame")
        cat_frame.pack(side="right")

        ttk.Label(cat_frame, text="Category:", style="CardMuted.TLabel").pack(side="left", padx=(0, 8))

        self.category_var = tk.StringVar(value="All Categories")
        self.category_cb = ttk.Combobox(
            cat_frame,
            textvariable=self.category_var,
            state="readonly",
            width=20,
            values=["All Categories", "runtimes", "compilers", "build", "vcs", "cloud", "general"],
        )
        self.category_cb.pack(side="left")
        self.category_cb.bind("<<ComboboxSelected>>", lambda e: self._on_filter_changed())

    def _build_tools_table(self) -> None:
        """Tools data treeview table."""
        table_frame = ttk.Frame(self, style="Card.TFrame", padding=1)
        table_frame.pack(fill="both", expand=True)

        columns = ("id", "name", "category", "version", "status", "path")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")

        self.tree.heading("id", text="ID")
        self.tree.heading("name", text="Tool Name")
        self.tree.heading("category", text="Category")
        self.tree.heading("version", text="Resolved Version")
        self.tree.heading("status", text="Health Status")
        self.tree.heading("path", text="Executable Path")

        self.tree.column("id", width=110)
        self.tree.column("name", width=160)
        self.tree.column("category", width=120)
        self.tree.column("version", width=140)
        self.tree.column("status", width=110)
        self.tree.column("path", width=300)

        # Double-click to open deep inspector
        self.tree.bind("<Double-1>", lambda e: self._inspect_selected_tool())
        self.tree.bind("<Return>", lambda e: self._inspect_selected_tool())

        self.tree.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

    def _build_table_actions(self) -> None:
        """Bottom action bar under tools table."""
        actions_bar = ttk.Frame(self, style="Main.TFrame", padding=(0, 8, 0, 0))
        actions_bar.pack(fill="x")

        hint_lbl = ttk.Label(
            actions_bar,
            text="Tip: Double-click any tool to launch the Deep Domain Inspector modal.",
            style="CardMuted.TLabel",
        )
        hint_lbl.pack(side="left")

        inspect_btn = ttk.Button(
            actions_bar,
            text="⚡ Deep Inspect Tool",
            style="Primary.TButton",
            command=self._inspect_selected_tool,
        )
        inspect_btn.pack(side="right")

    # -------------------------------------------------------------------------
    # Data & Event Handlers
    # -------------------------------------------------------------------------

    def _on_tools_updated(self, tools: List[Dict[str, Any]]) -> None:
        """Handle state update when tools list refreshes."""
        self.after(0, self._populate_table)

    def _on_filter_changed(self) -> None:
        """Filter table data when search query or category combobox changes."""
        self._filter_query = self.search_var.get().strip().lower()
        selected_cat = self.category_var.get()
        self._filter_category = "all" if selected_cat == "All Categories" else selected_cat.lower()
        self._populate_table()

    def _update_metrics(self) -> None:
        """Update metrics card values from state."""
        tools = self.state.tools or []
        total_count = len(tools)
        installed_count = sum(1 for t in tools if t.get("status") == "healthy" or t.get("installed"))
        missing_count = max(0, total_count - installed_count)
        health_pct = round((installed_count / total_count * 100), 1) if total_count else 0.0

        if "total" in self.metric_labels:
            self.metric_labels["total"].configure(text=str(total_count) if total_count else "--")
            self.metric_labels["installed"].configure(text=str(installed_count) if total_count else "--")
            self.metric_labels["missing"].configure(text=str(missing_count) if total_count else "--")
            self.metric_labels["health"].configure(text=f"{health_pct}%" if total_count else "--")

    def _populate_table(self) -> None:
        """Filter and populate tools in treeview."""
        self._update_metrics()

        for item in self.tree.get_children():
            self.tree.delete(item)

        tools = self.state.tools or []

        # Update categories combobox dynamically if needed
        cats = sorted({t.get("category", "general") for t in tools if t.get("category")})
        current_values = list(self.category_cb["values"])
        expected_values = ["All Categories"] + cats
        if current_values != expected_values and cats:
            self.category_cb["values"] = expected_values

        for t in tools:
            tool_id = t.get("id", "")
            name = t.get("name", tool_id)
            cat = t.get("category", "general")
            version = t.get("version") or "Not found"
            path = t.get("binary_path") or "--"
            installed = t.get("installed", False) or t.get("status") == "healthy"

            # Filter by Category
            if self._filter_category != "all" and cat.lower() != self._filter_category:
                continue

            # Filter by Search Query
            if self._filter_query:
                haystack = f"{tool_id} {name} {cat} {version} {path}".lower()
                if self._filter_query not in haystack:
                    continue

            status_display = "✓ Healthy" if installed else "✗ Missing"

            self.tree.insert(
                "",
                "end",
                iid=tool_id,
                values=(
                    tool_id,
                    name,
                    cat,
                    version,
                    status_display,
                    path,
                ),
            )

    def _inspect_selected_tool(self) -> None:
        """Launch the ToolInspectorModal for the selected tool."""
        selected = self.tree.selection()
        if not selected:
            return

        tool_id = selected[0]
        base_tool = next((t for t in self.state.tools if t.get("id") == tool_id), {"id": tool_id})

        ToolInspectorModal(
            parent=self,
            client=self.client,
            tool_id=tool_id,
            base_tool=base_tool,
        )

    def _trigger_audit(self) -> None:
        """Trigger workstation re-scan asynchronously."""
        def _task():
            return self.client.run_audit()

        def _on_success(summary: Dict[str, Any]):
            tools = summary.get("reports", [])
            self.after(0, lambda: self.state.set_tools(tools))
            self.after(0, lambda: self.state.set_audit_report(summary))

        self.client.run_async(_task, callback=_on_success)
