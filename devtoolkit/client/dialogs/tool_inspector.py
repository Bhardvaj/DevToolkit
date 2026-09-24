"""Deep Tool Inspection Modal Dialog for DevToolkit Python Native UI."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Any, Dict, List, Optional

from devtoolkit.client.api import DevToolkitClient
from devtoolkit.client.theme import Colors, Fonts

logger = logging.getLogger(__name__)


class ToolInspectorModal(tk.Toplevel):
    """Modal dialog displaying deep domain telemetry and environment diagnostics for a tool."""

    def __init__(
        self,
        parent: tk.Misc,
        client: DevToolkitClient,
        tool_id: str,
        base_tool: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(parent)
        self.client = client
        self.tool_id = tool_id
        self.base_tool = base_tool or {}
        self.deep_data: Optional[Dict[str, Any]] = None

        tool_name = self.base_tool.get("name", self.tool_id.title())
        self.title(f"DevToolkit Inspector ⚡ {tool_name}")
        self.geometry("860x650")
        self.minsize(720, 500)
        self.configure(bg=Colors.BG_MAIN)

        # Make modal window behavior
        self.transient(parent.winfo_toplevel())
        self.grab_set()

        # Keyboard shortcuts
        self.bind("<Escape>", lambda e: self.destroy())

        # Build UI Structure
        self._build_header()
        self._build_notebook()
        self._build_footer()

        # Load Deep Telemetry Asynchronously
        self._load_telemetry()

    def _build_header(self) -> None:
        """Construct top modal header with tool identity and status badges."""
        self.header_frame = ttk.Frame(self, style="Header.TFrame", padding=(20, 16, 20, 14))
        self.header_frame.pack(side="top", fill="x")

        # Identity
        id_frame = ttk.Frame(self.header_frame, style="Header.TFrame")
        id_frame.pack(side="left")

        tool_name = self.base_tool.get("name", self.tool_id.title())
        title_lbl = ttk.Label(id_frame, text=tool_name, style="Header.TLabel")
        title_lbl.pack(anchor="w")

        sub_text = f"Tool ID: {self.tool_id} | Category: {self.base_tool.get('category', 'general').capitalize()}"
        sub_lbl = ttk.Label(id_frame, text=sub_text, style="CardMuted.TLabel")
        sub_lbl.pack(anchor="w", pady=(2, 0))

        # Status Badges
        self.badge_frame = ttk.Frame(self.header_frame, style="Header.TFrame")
        self.badge_frame.pack(side="right")

        installed = self.base_tool.get("installed", False)
        status_text = "✓ Healthy" if installed else "✗ Missing"
        status_style = "BadgeSuccess.TLabel" if installed else "BadgeError.TLabel"

        self.status_badge = ttk.Label(
            self.badge_frame,
            text=status_text,
            style=status_style,
            padding=(10, 4),
        )
        self.status_badge.pack(side="left", padx=(0, 8))

        self.latency_badge = ttk.Label(
            self.badge_frame,
            text="⚡ Loading...",
            style="BadgeWarning.TLabel",
            padding=(8, 4),
        )
        self.latency_badge.pack(side="left")

    def _build_notebook(self) -> None:
        """Construct tabbed notebook for different telemetry facets."""
        container = ttk.Frame(self, style="Main.TFrame", padding=(20, 12, 20, 12))
        container.pack(side="top", fill="both", expand=True)

        self.notebook = ttk.Notebook(container)
        self.notebook.pack(fill="both", expand=True)

        # Tab 1: Overview & Executable Paths
        self.tab_overview = ttk.Frame(self.notebook, style="Card.TFrame", padding=(16, 16))
        self.notebook.add(self.tab_overview, text="  Overview & Binaries  ")
        self._build_overview_tab()

        # Tab 2: Environment Variables
        self.tab_env = ttk.Frame(self.notebook, style="Card.TFrame", padding=(16, 16))
        self.notebook.add(self.tab_env, text="  Environment Variables  ")
        self._build_env_tab()

        # Tab 3: Domain Telemetry Details
        self.tab_telemetry = ttk.Frame(self.notebook, style="Card.TFrame", padding=(16, 16))
        self.notebook.add(self.tab_telemetry, text="  Telemetry & SDKs  ")
        self._build_telemetry_tab()

        # Tab 4: Raw CLI Output & Discovery Trace
        self.tab_raw = ttk.Frame(self.notebook, style="Card.TFrame", padding=(16, 16))
        self.notebook.add(self.tab_raw, text="  Raw Output & Logs  ")
        self._build_raw_tab()

    def _build_overview_tab(self) -> None:
        """Overview tab: Primary binary, home directory, and discovered instances."""
        # Primary Binary Section
        bin_card = ttk.Frame(self.tab_overview, style="Card.TFrame")
        bin_card.pack(fill="x", pady=(0, 12))

        ttk.Label(bin_card, text="PRIMARY EXECUTABLE", style="SidebarHeader.TLabel").pack(anchor="w")

        path_row = ttk.Frame(bin_card, style="Card.TFrame")
        path_row.pack(fill="x", pady=(4, 0))

        self.primary_path_var = tk.StringVar(value=self.base_tool.get("binary_path") or "Not found")
        path_entry = ttk.Entry(path_row, textvariable=self.primary_path_var, state="readonly")
        path_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        copy_btn = ttk.Button(
            path_row,
            text="📋 Copy Path",
            style="TButton",
            command=lambda: self._copy_to_clipboard(self.primary_path_var.get()),
        )
        copy_btn.pack(side="left", padx=(0, 6))

        reveal_btn = ttk.Button(
            path_row,
            text="📁 Reveal",
            style="TButton",
            command=lambda: self._reveal_path(self.primary_path_var.get()),
        )
        reveal_btn.pack(side="left")

        # Home Path Section
        home_card = ttk.Frame(self.tab_overview, style="Card.TFrame")
        home_card.pack(fill="x", pady=(0, 16))

        ttk.Label(home_card, text="HOME / SDK DIRECTORY", style="SidebarHeader.TLabel").pack(anchor="w")

        home_row = ttk.Frame(home_card, style="Card.TFrame")
        home_row.pack(fill="x", pady=(4, 0))

        self.home_path_var = tk.StringVar(value=self.base_tool.get("home_path") or "Not configured")
        home_entry = ttk.Entry(home_row, textvariable=self.home_path_var, state="readonly")
        home_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        copy_home_btn = ttk.Button(
            home_row,
            text="📋 Copy Path",
            style="TButton",
            command=lambda: self._copy_to_clipboard(self.home_path_var.get()),
        )
        copy_home_btn.pack(side="left")

        # Alternative Discovered Instances Table
        ttk.Label(self.tab_overview, text="ALL DISCOVERED INSTANCES", style="SidebarHeader.TLabel").pack(
            anchor="w", pady=(8, 4)
        )

        inst_frame = ttk.Frame(self.tab_overview, style="Card.TFrame")
        inst_frame.pack(fill="both", expand=True)

        cols = ("active", "version", "path", "details")
        self.inst_tree = ttk.Treeview(inst_frame, columns=cols, show="headings", selectmode="browse")
        self.inst_tree.heading("active", text="Active")
        self.inst_tree.heading("version", text="Version")
        self.inst_tree.heading("path", text="Executable Path")
        self.inst_tree.heading("details", text="Details")

        self.inst_tree.column("active", width=70, anchor="center")
        self.inst_tree.column("version", width=120)
        self.inst_tree.column("path", width=340)
        self.inst_tree.column("details", width=160)

        self.inst_tree.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(inst_frame, orient="vertical", command=self.inst_tree.yview)
        self.inst_tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")

    def _build_env_tab(self) -> None:
        """Environment variables table."""
        ttk.Label(
            self.tab_env,
            text="MONITORED ENVIRONMENT VARIABLES",
            style="SidebarHeader.TLabel",
        ).pack(anchor="w", pady=(0, 8))

        env_frame = ttk.Frame(self.tab_env, style="Card.TFrame")
        env_frame.pack(fill="both", expand=True)

        cols = ("name", "status", "value", "message")
        self.env_tree = ttk.Treeview(env_frame, columns=cols, show="headings", selectmode="browse")
        self.env_tree.heading("name", text="Variable Name")
        self.env_tree.heading("status", text="Status")
        self.env_tree.heading("value", text="Resolved Value")
        self.env_tree.heading("message", text="Diagnostics / Details")

        self.env_tree.column("name", width=160)
        self.env_tree.column("status", width=100)
        self.env_tree.column("value", width=280)
        self.env_tree.column("message", width=200)

        self.env_tree.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(env_frame, orient="vertical", command=self.env_tree.yview)
        self.env_tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")

    def _build_telemetry_tab(self) -> None:
        """Deep domain key-value details."""
        ttk.Label(
            self.tab_telemetry,
            text="DOMAIN TELEMETRY & SUB-COMPONENTS",
            style="SidebarHeader.TLabel",
        ).pack(anchor="w", pady=(0, 8))

        telem_frame = ttk.Frame(self.tab_telemetry, style="Card.TFrame")
        telem_frame.pack(fill="both", expand=True)

        cols = ("property", "value")
        self.telem_tree = ttk.Treeview(telem_frame, columns=cols, show="headings", selectmode="browse")
        self.telem_tree.heading("property", text="Telemetry Property")
        self.telem_tree.heading("value", text="Value / Setting")

        self.telem_tree.column("property", width=220)
        self.telem_tree.column("value", width=520)

        self.telem_tree.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(telem_frame, orient="vertical", command=self.telem_tree.yview)
        self.telem_tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")

    def _build_raw_tab(self) -> None:
        """Raw CLI dump and discovery logs."""
        ttk.Label(
            self.tab_raw,
            text="COMMAND EXECUTION DUMPS & DISCOVERY LOGS",
            style="SidebarHeader.TLabel",
        ).pack(anchor="w", pady=(0, 8))

        text_frame = ttk.Frame(self.tab_raw, style="Card.TFrame")
        text_frame.pack(fill="both", expand=True)

        self.raw_text = tk.Text(
            text_frame,
            wrap="word",
            bg=Colors.BG_CARD,
            fg=Colors.TEXT_PRIMARY,
            insertbackground=Colors.TEXT_PRIMARY,
            font=Fonts.CODE,
            relief="flat",
            padx=12,
            pady=12,
        )
        self.raw_text.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(text_frame, orient="vertical", command=self.raw_text.yview)
        self.raw_text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")

    def _build_footer(self) -> None:
        """Bottom action bar with Close button."""
        footer = ttk.Frame(self, style="Footer.TFrame", padding=(20, 10))
        footer.pack(side="bottom", fill="x")

        close_btn = ttk.Button(footer, text="Close", style="TButton", command=self.destroy)
        close_btn.pack(side="right")

    # -------------------------------------------------------------------------
    # Asynchronous Data Loading
    # -------------------------------------------------------------------------

    def _load_telemetry(self) -> None:
        """Fetch deep telemetry data from daemon via non-blocking async thread."""

        def _fetch():
            return self.client.get_tool_deep(self.tool_id)

        def _on_success(data: Dict[str, Any]):
            self.after(0, lambda: self._apply_telemetry(data))

        def _on_error(err: Exception):
            logger.debug(f"Deep inspection fetch failed for {self.tool_id}: {err}")
            self.after(0, lambda: self._apply_error(str(err)))

        self.client.run_async(_fetch, callback=_on_success, errback=_on_error)

    def _apply_telemetry(self, data: Dict[str, Any]) -> None:
        """Update UI components with loaded deep telemetry data."""
        self.deep_data = data

        # Latency Badge
        latency_ms = data.get("probe_latency_ms", 0)
        self.latency_badge.configure(
            text=f"⚡ {latency_ms}ms",
            style="BadgeSuccess.TLabel" if latency_ms < 50 else "BadgeWarning.TLabel",
        )

        # Instances
        instances: List[Dict[str, Any]] = data.get("instances", [])
        for item in self.inst_tree.get_children():
            self.inst_tree.delete(item)

        if instances:
            for inst in instances:
                active_str = "● Active" if inst.get("is_active") else "○"
                self.inst_tree.insert(
                    "",
                    "end",
                    values=(
                        active_str,
                        inst.get("version", "Unknown"),
                        inst.get("path", ""),
                        inst.get("details", ""),
                    ),
                )
        elif self.base_tool.get("binary_path"):
            self.inst_tree.insert(
                "",
                "end",
                values=(
                    "● Active",
                    self.base_tool.get("version", "Unknown"),
                    self.base_tool.get("binary_path", ""),
                    "Detected in PATH",
                ),
            )

        # Environment Variables
        env_vars: List[Dict[str, Any]] = data.get("env_vars", [])
        for item in self.env_tree.get_children():
            self.env_tree.delete(item)

        for ev in env_vars:
            status_val = ev.get("status", "aligned")
            status_display = {
                "aligned": "✓ Aligned",
                "divergent": "⚠️ Divergent",
                "missing": "✗ Missing",
            }.get(status_val, status_val)

            self.env_tree.insert(
                "",
                "end",
                values=(
                    ev.get("name", ""),
                    status_display,
                    ev.get("value") or "--",
                    ev.get("message") or ev.get("target_path") or "",
                ),
            )

        # Telemetry Details
        telemetry: Dict[str, Any] = data.get("telemetry", {})
        for item in self.telem_tree.get_children():
            self.telem_tree.delete(item)

        def _flatten_telemetry(prefix: str, val: Any) -> None:
            if isinstance(val, dict):
                for k, v in val.items():
                    _flatten_telemetry(f"{prefix}.{k}" if prefix else str(k), v)
            elif isinstance(val, list):
                self.telem_tree.insert("", "end", values=(prefix, f"[{len(val)} items] " + ", ".join(str(x) for x in val[:5])))
            else:
                self.telem_tree.insert("", "end", values=(prefix, str(val)))

        for k, v in telemetry.items():
            _flatten_telemetry(k, v)

        # Raw Output
        self.raw_text.delete("1.0", tk.END)
        raw_dumps: Dict[str, str] = data.get("raw_dumps", {})
        trace: List[str] = data.get("discovery_trace", [])

        output_lines = []
        if trace:
            output_lines.append("=== DISCOVERY TRACE ===")
            output_lines.extend(trace)
            output_lines.append("")

        if raw_dumps:
            for dump_key, dump_val in raw_dumps.items():
                output_lines.append(f"=== CLI DUMP: {dump_key} ===")
                output_lines.append(dump_val.strip())
                output_lines.append("")

        if not output_lines:
            output_lines.append("No raw CLI dumps or discovery traces captured.")

        self.raw_text.insert(tk.END, "\n".join(output_lines))

    def _apply_error(self, err_msg: str) -> None:
        """Handle telemetry load failure gracefully."""
        self.latency_badge.configure(text="⚠️ Probe Failed", style="BadgeError.TLabel")
        self.raw_text.delete("1.0", tk.END)
        self.raw_text.insert(tk.END, f"Failed to probe deep tool telemetry:\n\n{err_msg}")

    # -------------------------------------------------------------------------
    # Helper Actions
    # -------------------------------------------------------------------------

    def _copy_to_clipboard(self, text: str) -> None:
        """Copy path or text to clipboard."""
        if text and text != "Not found" and text != "Not configured":
            self.clipboard_clear()
            self.clipboard_append(text)

    def _reveal_path(self, path: str) -> None:
        """Reveal file or directory in Windows Explorer / OS file manager."""
        if path and path != "Not found" and path != "Not configured":
            self.client.run_async(self.client.reveal_file, path)
