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
from devtoolkit.client.views import (
    EnvironmentView,
    PortManagerView,
    ProjectAuditorView,
    SearchView,
    SettingsView,
)

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

        # Track navigation buttons and active frame
        self._nav_buttons: Dict[str, ttk.Button] = {}
        self._content_container: Optional[ttk.Frame] = None
        self._active_view_frame: Optional[ttk.Frame] = None

        # Build Main Frame Hierarchy
        self._build_header()
        self._build_main_layout()
        self._build_footer()

        # Keyboard Navigation Shortcuts
        self._bind_shortcuts()

        # Subscribe to State Changes
        self.state.subscribe("view_changed", self._on_view_changed)
        self.state.subscribe("daemon_status", self._on_daemon_status)

        # Hook Window Close Interception
        self.root.protocol("WM_DELETE_WINDOW", self._on_window_closing)

        # Initial View and Background Sync
        self._switch_view("environment")
        self._start_background_sync()

    # -------------------------------------------------------------------------
    # Keyboard Shortcuts
    # -------------------------------------------------------------------------

    def _bind_shortcuts(self) -> None:
        """Bind productivity hotkeys across application."""
        self.root.bind("<Control-Key-1>", lambda e: self.state.set_active_view("environment"))
        self.root.bind("<Control-Key-2>", lambda e: self.state.set_active_view("ports"))
        self.root.bind("<Control-Key-3>", lambda e: self.state.set_active_view("projects"))
        self.root.bind("<Control-Key-4>", lambda e: self.state.set_active_view("search"))
        self.root.bind("<Control-Key-5>", lambda e: self.state.set_active_view("settings"))
        self.root.bind("<Control-f>", lambda e: self.state.set_active_view("search"))
        self.root.bind("<Control-r>", lambda e: self._trigger_rescan())
        self.root.bind("<F5>", lambda e: self._refresh_active_view())

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

        if view_name == "environment":
            self._active_view_frame = EnvironmentView(
                self._content_container, client=self.client, state=self.state
            )
        elif view_name == "ports":
            self._active_view_frame = PortManagerView(
                self._content_container, client=self.client, state=self.state
            )
        elif view_name == "projects":
            self._active_view_frame = ProjectAuditorView(
                self._content_container, client=self.client, state=self.state
            )
        elif view_name == "search":
            self._active_view_frame = SearchView(
                self._content_container, client=self.client, state=self.state
            )
        elif view_name == "settings":
            self._active_view_frame = SettingsView(
                self._content_container, client=self.client, state=self.state
            )
        else:
            self._active_view_frame = EnvironmentView(
                self._content_container, client=self.client, state=self.state
            )

        self._active_view_frame.pack(fill="both", expand=True)

    def _on_view_changed(self, view_name: str) -> None:
        """Callback on reactive active_view change."""
        self.root.after(0, lambda: self._switch_view(view_name))

    # -------------------------------------------------------------------------
    # Actions & Synchronizations
    # -------------------------------------------------------------------------

    def _trigger_rescan(self) -> None:
        """Trigger background workstation audit scan."""
        def _task():
            return self.client.run_audit()

        def _on_success(summary: Dict[str, Any]):
            tools = summary.get("reports", [])
            self.state.set_tools(tools)
            self.state.set_audit_report(summary)

        self.client.run_async(_task, callback=_on_success)

    def _refresh_active_view(self) -> None:
        """Refresh active view data."""
        current = self.state.active_view
        if current == "ports" and hasattr(self._active_view_frame, "_refresh_ports"):
            self._active_view_frame._refresh_ports()
        elif current == "environment":
            self._trigger_rescan()
        elif current == "settings" and hasattr(self._active_view_frame, "_load_config"):
            self._active_view_frame._load_config()

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
