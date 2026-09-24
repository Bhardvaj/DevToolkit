"""DevToolkit Python Native UI Desktop Application Shell."""

from __future__ import annotations

import logging
import os
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Dict, List, Optional

from devtoolkit import __version__
from devtoolkit.client.api import DevToolkitClient
from devtoolkit.client.state import ClientState
from devtoolkit.client.theme import Colors, Fonts, apply_theme

logger = logging.getLogger(__name__)

WINDOW_TITLE = "DevToolkit ⚡ Native Workstation Inspector"


class DevToolkitApp:
    """Main desktop application window shell for DevToolkit Python Native UI."""

    def __init__(
        self,
        root: tk.Tk,
        client: Optional[DevToolkitClient] = None,
        state: Optional[ClientState] = None,
    ):
        self.root = root
        self.client = client or DevToolkitClient()
        self.state = state or ClientState()

        self.root.title(WINDOW_TITLE)
        self.root.geometry("1140x780")
        self.root.minsize(880, 600)

        # Apply dark modern theme
        self.style = apply_theme(self.root)

        # Track navigation buttons
        self._nav_buttons: Dict[str, ttk.Button] = {}
        self._content_container: Optional[ttk.Frame] = None
        self._active_view_frame: Optional[ttk.Frame] = None

        # Build Main Frame Hierarchy
        self._build_header()
        self._build_main_layout()
        self._build_footer()

        # Subscribe to State Changes
        self.state.subscribe("view_changed", self._on_view_changed)
        self.state.subscribe("daemon_status", self._on_daemon_status)

        # Hook Window Close Interception
        self.root.protocol("WM_DELETE_WINDOW", self._on_window_closing)

        # Initial View and Background Sync
        self._switch_view("environment")
        self._start_background_sync()

    # -------------------------------------------------------------------------
    # UI Layout Construction
    # -------------------------------------------------------------------------

    def _build_header(self) -> None:
        """Construct top application header bar."""
        header_frame = ttk.Frame(self.root, style="Header.TFrame", padding=(20, 16, 20, 12))
        header_frame.pack(side="top", fill="x")

        # Left Branding
        brand_frame = ttk.Frame(header_frame, style="Header.TFrame")
        brand_frame.pack(side="left")

        title_lbl = ttk.Label(brand_frame, text="DevToolkit ⚡", style="Header.TLabel")
        title_lbl.pack(side="left")

        sub_lbl = ttk.Label(
            brand_frame,
            text=" Workstation Inspector",
            style="Subheader.TLabel",
        )
        sub_lbl.pack(side="left", padx=(4, 0))

        # Right Action & Status
        actions_frame = ttk.Frame(header_frame, style="Header.TFrame")
        actions_frame.pack(side="right")

        self.status_badge = ttk.Label(
            actions_frame,
            text="● Connecting...",
            style="BadgeWarning.TLabel",
            padding=(10, 4),
        )
        self.status_badge.pack(side="left", padx=(0, 12))

        rescan_btn = ttk.Button(
            actions_frame,
            text="🔄 Re-scan",
            style="Primary.TButton",
            command=self._trigger_rescan,
        )
        rescan_btn.pack(side="left", padx=(0, 8))

        browser_btn = ttk.Button(
            actions_frame,
            text="🌐 Web View",
            style="TButton",
            command=lambda: self.client.open_folder(self.client.base_url)
            if hasattr(self.client, "open_folder")
            else None,
        )
        browser_btn.pack(side="left")

    def _build_main_layout(self) -> None:
        """Construct split layout containing sidebar navigation and dynamic content panel."""
        self.main_split = ttk.Frame(self.root, style="Main.TFrame")
        self.main_split.pack(side="top", fill="both", expand=True)

        # Sidebar Frame
        self.sidebar = ttk.Frame(self.main_split, style="Sidebar.TFrame", width=220, padding=(12, 16))
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        sidebar_title = ttk.Label(self.sidebar, text="NAVIGATION", style="SidebarHeader.TLabel")
        sidebar_title.pack(anchor="w", padx=8, pady=(0, 12))

        # Nav Items
        nav_items = [
            ("environment", "⚡ Environment"),
            ("ports", "🔌 Port Manager"),
            ("projects", "📁 Project Auditor"),
            ("search", "🔍 Fast File Search"),
            ("settings", "⚙️ Configuration"),
        ]

        for view_key, label in nav_items:
            btn = ttk.Button(
                self.sidebar,
                text=label,
                style="Nav.TButton",
                command=lambda vk=view_key: self.state.set_active_view(vk),
            )
            btn.pack(fill="x", pady=2)
            self._nav_buttons[view_key] = btn

        # Sidebar Footer Badge
        ver_lbl = ttk.Label(
            self.sidebar,
            text=f"DevToolkit v{__version__}",
            style="CardMuted.TLabel",
        )
        ver_lbl.pack(side="bottom", anchor="w", padx=8, pady=8)

        # Content Area
        self._content_container = ttk.Frame(self.main_split, style="Main.TFrame", padding=(24, 16))
        self._content_container.pack(side="right", fill="both", expand=True)

    def _build_footer(self) -> None:
        """Construct bottom status and system diagnostics footer."""
        self.footer = ttk.Frame(self.root, style="Footer.TFrame", padding=(20, 8))
        self.footer.pack(side="bottom", fill="x")

        self.footer_info = ttk.Label(
            self.footer,
            text=f"Daemon: {self.client.base_url} | Architecture: {sys.platform} | Python: {sys.version.split()[0]}",
            style="CardMuted.TLabel",
        )
        self.footer_info.pack(side="left")

    # -------------------------------------------------------------------------
    # View Switching & Routing
    # -------------------------------------------------------------------------

    def _switch_view(self, view_name: str) -> None:
        """Render the selected view frame inside the content container."""
        # Update Nav Button Styles
        for vk, btn in self._nav_buttons.items():
            if vk == view_name:
                btn.configure(style="ActiveNav.TButton")
            else:
                btn.configure(style="Nav.TButton")

        # Destroy old view frame
        if self._active_view_frame:
            self._active_view_frame.destroy()

        self._active_view_frame = ttk.Frame(self._content_container, style="Main.TFrame")
        self._active_view_frame.pack(fill="both", expand=True)

        if view_name == "environment":
            self._render_environment_view(self._active_view_frame)
        elif view_name == "ports":
            self._render_ports_view(self._active_view_frame)
        elif view_name == "projects":
            self._render_projects_view(self._active_view_frame)
        elif view_name == "search":
            self._render_search_view(self._active_view_frame)
        elif view_name == "settings":
            self._render_settings_view(self._active_view_frame)

    def _on_view_changed(self, view_name: str) -> None:
        """Callback on reactive active_view change."""
        self.root.after(0, lambda: self._switch_view(view_name))

    # -------------------------------------------------------------------------
    # View Renderers
    # -------------------------------------------------------------------------

    def _render_environment_view(self, parent: ttk.Frame) -> None:
        """Render Environment Diagnostics dashboard cards and tool list."""
        header_row = ttk.Frame(parent, style="Main.TFrame")
        header_row.pack(fill="x", pady=(0, 16))

        title = ttk.Label(header_row, text="Workstation Environment Diagnostics", style="Header.TLabel")
        title.pack(side="left")

        # Summary Metrics Frame
        metrics_frame = ttk.Frame(parent, style="Main.TFrame")
        metrics_frame.pack(fill="x", pady=(0, 16))

        # Metric Cards
        tools = self.state.tools or []
        installed_count = sum(1 for t in tools if t.get("status") == "healthy" or t.get("installed"))
        total_count = len(tools)
        health_pct = round((installed_count / total_count * 100), 1) if total_count else 0.0

        for col, (title_text, val_text, badge_style) in enumerate([
            ("Total Tools", str(total_count or "--"), "CardTitle.TLabel"),
            ("Installed", str(installed_count or "--"), "BadgeSuccess.TLabel"),
            ("Missing", str(max(0, total_count - installed_count) if total_count else "--"), "BadgeError.TLabel"),
            ("Health Score", f"{health_pct}%" if total_count else "--", "BadgeSuccess.TLabel"),
        ]):
            card = ttk.Frame(metrics_frame, style="Card.TFrame", padding=(16, 12))
            card.grid(row=0, column=col, sticky="nsew", padx=6 if col > 0 else 0)
            metrics_frame.columnconfigure(col, weight=1)

            t_lbl = ttk.Label(card, text=title_text, style="CardMuted.TLabel")
            t_lbl.pack(anchor="w")
            v_lbl = ttk.Label(card, text=val_text, style=badge_style)
            v_lbl.pack(anchor="w", pady=(4, 0))

        # Tool Table
        table_frame = ttk.Frame(parent, style="Card.TFrame", padding=1)
        table_frame.pack(fill="both", expand=True)

        columns = ("id", "name", "category", "version", "status")
        tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")

        tree.heading("id", text="ID")
        tree.heading("name", text="Tool Name")
        tree.heading("category", text="Category")
        tree.heading("version", text="Resolved Version")
        tree.heading("status", text="Health Status")

        tree.column("id", width=120)
        tree.column("name", width=180)
        tree.column("category", width=140)
        tree.column("version", width=160)
        tree.column("status", width=120)

        for t in tools:
            status_display = "✓ Healthy" if t.get("status") == "healthy" or t.get("installed") else "✗ Missing"
            tree.insert(
                "",
                "end",
                values=(
                    t.get("id", ""),
                    t.get("name", t.get("id", "")),
                    t.get("category", ""),
                    t.get("version", "Not found"),
                    status_display,
                ),
            )

        tree.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

    def _render_ports_view(self, parent: ttk.Frame) -> None:
        """Render Port Manager view."""
        header_row = ttk.Frame(parent, style="Main.TFrame")
        header_row.pack(fill="x", pady=(0, 16))

        title = ttk.Label(header_row, text="Active Network Ports & Sockets", style="Header.TLabel")
        title.pack(side="left")

        refresh_btn = ttk.Button(
            header_row,
            text="🔄 Refresh Ports",
            style="TButton",
            command=self._refresh_ports,
        )
        refresh_btn.pack(side="right")

        # Table
        table_frame = ttk.Frame(parent, style="Card.TFrame", padding=1)
        table_frame.pack(fill="both", expand=True)

        columns = ("port", "protocol", "pid", "process", "address")
        tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")

        tree.heading("port", text="Port")
        tree.heading("protocol", text="Protocol")
        tree.heading("pid", text="PID")
        tree.heading("process", text="Process Name")
        tree.heading("address", text="Local Address")

        for p in self.state.ports or []:
            tree.insert(
                "",
                "end",
                values=(
                    p.get("port", ""),
                    p.get("protocol", "TCP"),
                    p.get("pid", ""),
                    p.get("process_name", ""),
                    p.get("address", "127.0.0.1"),
                ),
            )

        tree.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

    def _render_projects_view(self, parent: ttk.Frame) -> None:
        """Render Project Hygiene Auditor view."""
        header_row = ttk.Frame(parent, style="Main.TFrame")
        header_row.pack(fill="x", pady=(0, 16))

        title = ttk.Label(header_row, text="Project Environment Auditor", style="Header.TLabel")
        title.pack(side="left")

        # Selector Frame
        card = ttk.Frame(parent, style="Card.TFrame", padding=(16, 16))
        card.pack(fill="x", pady=(0, 16))

        prompt_lbl = ttk.Label(
            card,
            text="Select a project directory to audit framework hygiene, dependencies, and environment health:",
            style="CardText.TLabel",
        )
        prompt_lbl.pack(anchor="w", pady=(0, 12))

        input_row = ttk.Frame(card, style="Card.TFrame")
        input_row.pack(fill="x")

        self.project_path_var = tk.StringVar(value=os.getcwd())
        entry = ttk.Entry(input_row, textvariable=self.project_path_var)
        entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        audit_btn = ttk.Button(
            input_row,
            text="🔍 Audit Project",
            style="Primary.TButton",
            command=self._trigger_project_audit,
        )
        audit_btn.pack(side="right")

    def _render_search_view(self, parent: ttk.Frame) -> None:
        """Render Fast Filesystem Search view."""
        header_row = ttk.Frame(parent, style="Main.TFrame")
        header_row.pack(fill="x", pady=(0, 16))

        title = ttk.Label(header_row, text="Fast Multi-Root File Search", style="Header.TLabel")
        title.pack(side="left")

        # Search Card
        card = ttk.Frame(parent, style="Card.TFrame", padding=(16, 16))
        card.pack(fill="x", pady=(0, 16))

        self.search_var = tk.StringVar()
        entry = ttk.Entry(card, textvariable=self.search_var)
        entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        entry.bind("<Return>", lambda e: self._trigger_search())

        search_btn = ttk.Button(card, text="Search", style="Primary.TButton", command=self._trigger_search)
        search_btn.pack(side="right")

        # Results Table
        table_frame = ttk.Frame(parent, style="Card.TFrame", padding=1)
        table_frame.pack(fill="both", expand=True)

        columns = ("name", "path", "size")
        tree = ttk.Treeview(table_frame, columns=columns, show="headings")
        tree.heading("name", text="File Name")
        tree.heading("path", text="Directory Path")
        tree.heading("size", text="Size")
        tree.column("name", width=220)
        tree.column("path", width=500)
        tree.column("size", width=100)

        for res in self.state.search_results or []:
            tree.insert(
                "",
                "end",
                values=(
                    res.get("filename", ""),
                    res.get("path", ""),
                    f"{res.get('size_bytes', 0) // 1024} KB",
                ),
            )

        tree.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

    def _render_settings_view(self, parent: ttk.Frame) -> None:
        """Render Configuration and Settings view."""
        header_row = ttk.Frame(parent, style="Main.TFrame")
        header_row.pack(fill="x", pady=(0, 16))

        title = ttk.Label(header_row, text="DevToolkit Preferences & Settings", style="Header.TLabel")
        title.pack(side="left")

        # Close Action Preference Card
        card = ttk.Frame(parent, style="Card.TFrame", padding=(16, 16))
        card.pack(fill="x", pady=(0, 16))

        card_title = ttk.Label(card, text="Window Close Behavior", style="CardTitle.TLabel")
        card_title.pack(anchor="w", pady=(0, 8))

        desc = ttk.Label(
            card,
            text="Choose what happens when the workstation inspector window is closed:",
            style="CardText.TLabel",
        )
        desc.pack(anchor="w", pady=(0, 12))

        current_action = (self.state.config or {}).get("close_action", "ask")
        self.close_action_var = tk.StringVar(value=current_action)

        for val, label_text in [
            ("ask", "Ask every time (Prompt between Minimize to System Tray and Exit Completely)"),
            ("minimize", "Always minimize to System Tray in background"),
            ("exit", "Always exit completely and shut down all background services"),
        ]:
            rb = ttk.Radiobutton(
                card,
                text=label_text,
                value=val,
                variable=self.close_action_var,
                command=self._update_close_action,
            )
            rb.pack(anchor="w", pady=4)

    # -------------------------------------------------------------------------
    # Action & Background Handlers
    # -------------------------------------------------------------------------

    def _trigger_rescan(self) -> None:
        """Trigger background environment audit rescan."""
        self.client.run_async(
            self.client.run_audit,
            callback=lambda res: self.root.after(0, lambda: self._on_audit_finished(res)),
        )

    def _on_audit_finished(self, audit_res: Dict[str, Any]) -> None:
        self.state.set_audit_report(audit_res)
        # Refresh tools
        self.client.run_async(
            self.client.get_tools,
            callback=lambda tools: self.root.after(0, lambda: self.state.set_tools(tools)),
        )

    def _refresh_ports(self) -> None:
        """Fetch active ports in background."""
        self.client.run_async(
            self.client.get_ports,
            callback=lambda ports: self.root.after(0, lambda: self.state.set_ports(ports)),
        )

    def _trigger_project_audit(self) -> None:
        """Run project audit on chosen directory."""
        path = self.project_path_var.get()
        if not path:
            return
        self.client.run_async(
            self.client.run_project_audit,
            path,
            callback=lambda report: self.root.after(0, lambda: self.state.set_project_report(report)),
        )

    def _trigger_search(self) -> None:
        """Run fast filesystem query."""
        q = self.search_var.get()
        self.client.run_async(
            self.client.search_query,
            q,
            callback=lambda data: self.root.after(
                0, lambda: self.state.set_search_results(data.get("results", []), query=q)
            ),
        )

    def _update_close_action(self) -> None:
        """Persist close_action selection to daemon config."""
        action = self.close_action_var.get()
        self.client.run_async(self.client.set_close_action, action)

    def _on_daemon_status(self, payload: Dict[str, Any]) -> None:
        """Update status badge based on daemon telemetry."""
        connected = payload.get("connected", False)

        def _update():
            if connected:
                self.status_badge.configure(
                    text=f"● Daemon Active ({self.client.port})",
                    style="BadgeSuccess.TLabel",
                )
            else:
                self.status_badge.configure(
                    text="● Daemon Disconnected",
                    style="BadgeError.TLabel",
                )

        self.root.after(0, _update)

    def _start_background_sync(self) -> None:
        """Background daemon polling worker to discover services and sync state."""

        def _poller():
            while True:
                try:
                    alive = self.client.is_alive()
                    self.state.set_daemon_status(connected=alive)
                    if alive:
                        # Initial data fetch if not yet loaded
                        if not self.state.system_info:
                            sys_info = self.client.get_system()
                            self.root.after(0, lambda: self.state.set_system_info(sys_info))
                        if not self.state.tools:
                            tools = self.client.get_tools()
                            self.root.after(0, lambda: self.state.set_tools(tools))
                        if not self.state.config:
                            cfg = self.client.get_config()
                            self.root.after(0, lambda: self.state.set_config(cfg))
                        if not self.state.ports:
                            ports = self.client.get_ports()
                            self.root.after(0, lambda: self.state.set_ports(ports))
                except Exception as e:
                    logger.debug(f"Sync polling exception: {e}")
                time.sleep(4.0)

        t = threading.Thread(target=_poller, daemon=True, name="DevToolkit-ClientPoller")
        t.start()

    # -------------------------------------------------------------------------
    # Window Close Interception
    # -------------------------------------------------------------------------

    def _on_window_closing(self) -> None:
        """Intercept native window close according to user preference."""
        action = (self.state.config or {}).get("close_action", "ask")

        if action == "minimize":
            self.root.withdraw()
            self.client.send_notification("DevToolkit", "Minimized to tray. Background services remain active.")
            return

        if action == "exit":
            self.root.destroy()
            return

        # action == "ask": show confirmation prompt
        res = messagebox.askyesnocancel(
            "DevToolkit",
            "DevToolkit background daemon is currently active.\n\n"
            "Would you like to minimize to the System Tray to keep services running in the background, "
            "or exit completely?\n\n"
            "• [Yes]: Minimize to System Tray\n"
            "• [No]: Exit Completely\n"
            "• [Cancel]: Stay in DevToolkit",
        )

        if res is True:  # Yes -> Minimize
            self.root.withdraw()
            self.client.send_notification("DevToolkit", "Minimized to tray. Background services remain active.")
        elif res is False:  # No -> Exit
            self.root.destroy()


def launch_native_ui(port: int = 4321, host: str = "127.0.0.1") -> None:
    """Launch the Python Native UI desktop application."""
    from devtoolkit.daemon.manager import is_daemon_alive, start_daemon

    if not is_daemon_alive(host=host, port=port):
        try:
            start_daemon(port=port, host=host)
        except Exception as e:
            logger.warning(f"Could not auto-start daemon: {e}")

    root = tk.Tk()
    client = DevToolkitClient(host=host, port=port)
    state = ClientState()
    app = DevToolkitApp(root=root, client=client, state=state)
    root.mainloop()
