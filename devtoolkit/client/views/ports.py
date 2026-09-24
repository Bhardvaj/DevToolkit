"""Port Manager View for DevToolkit Python Native UI."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Dict, List, Optional

from devtoolkit.client.api import DevToolkitClient
from devtoolkit.client.state import ClientState
from devtoolkit.client.theme import Colors, Fonts

logger = logging.getLogger(__name__)


class PortManagerView(ttk.Frame):
    """Port Manager view with active socket inspection and interactive process termination."""

    def __init__(
        self,
        parent: ttk.Frame,
        client: DevToolkitClient,
        state: ClientState,
    ):
        super().__init__(parent, style="Main.TFrame")
        self.client = client
        self.state = state

        self._filter_query = ""

        self._build_header()
        self._build_filter_bar()
        self._build_table()
        self._build_action_bar()

        # Subscribe to State Changes
        self._unsub_ports = self.state.subscribe("ports_updated", self._on_ports_updated)

        # Initial Load
        self._refresh_ports()

    def destroy(self) -> None:
        """Unsubscribe from state events when destroyed."""
        if hasattr(self, "_unsub_ports") and self._unsub_ports:
            self._unsub_ports()
        super().destroy()

    # -------------------------------------------------------------------------
    # UI Construction
    # -------------------------------------------------------------------------

    def _build_header(self) -> None:
        """Top view header."""
        header_row = ttk.Frame(self, style="Main.TFrame")
        header_row.pack(fill="x", pady=(0, 16))

        title = ttk.Label(header_row, text="Active Network Ports & Sockets", style="Header.TLabel")
        title.pack(side="left")

        self.refresh_btn = ttk.Button(
            header_row,
            text="🔄 Refresh Ports",
            style="Primary.TButton",
            command=self._refresh_ports,
        )
        self.refresh_btn.pack(side="right")

    def _build_filter_bar(self) -> None:
        """Filter input bar."""
        filter_frame = ttk.Frame(self, style="Main.TFrame")
        filter_frame.pack(fill="x", pady=(0, 12))

        ttk.Label(filter_frame, text="🔍 Filter Ports / Processes:", style="CardMuted.TLabel").pack(
            side="left", padx=(0, 8)
        )

        self.filter_var = tk.StringVar()
        self.filter_var.trace_add("write", lambda *args: self._on_filter_changed())
        entry = ttk.Entry(filter_frame, textvariable=self.filter_var)
        entry.pack(side="left", fill="x", expand=True, padx=(0, 12))

        self.port_count_lbl = ttk.Label(filter_frame, text="Active Ports: 0", style="CardMuted.TLabel")
        self.port_count_lbl.pack(side="right")

    def _build_table(self) -> None:
        """Ports data table."""
        table_frame = ttk.Frame(self, style="Card.TFrame", padding=1)
        table_frame.pack(fill="both", expand=True)

        columns = ("port", "protocol", "pid", "process", "address")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")

        self.tree.heading("port", text="Port")
        self.tree.heading("protocol", text="Protocol")
        self.tree.heading("pid", text="PID")
        self.tree.heading("process", text="Process Name")
        self.tree.heading("address", text="Local Address")

        self.tree.column("port", width=90, anchor="center")
        self.tree.column("protocol", width=90, anchor="center")
        self.tree.column("pid", width=100, anchor="center")
        self.tree.column("process", width=260)
        self.tree.column("address", width=220)

        # Selection change event
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._on_select_row())
        self.tree.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

    def _build_action_bar(self) -> None:
        """Bottom action bar with Kill Process action."""
        actions_frame = ttk.Frame(self, style="Main.TFrame", padding=(0, 10, 0, 0))
        actions_frame.pack(fill="x")

        self.selected_info_lbl = ttk.Label(
            actions_frame,
            text="Select a port to terminate the listening process.",
            style="CardMuted.TLabel",
        )
        self.selected_info_lbl.pack(side="left")

        self.kill_btn = ttk.Button(
            actions_frame,
            text="🛑 Terminate Process / Free Port",
            style="Danger.TButton",
            state="disabled",
            command=self._confirm_and_kill_port,
        )
        self.kill_btn.pack(side="right")

    # -------------------------------------------------------------------------
    # Event Handlers & State Sync
    # -------------------------------------------------------------------------

    def _on_ports_updated(self, ports: List[Dict[str, Any]]) -> None:
        """State subscriber callback."""
        self.after(0, self._populate_table)

    def _on_filter_changed(self) -> None:
        """Filter table rows."""
        self._filter_query = self.filter_var.get().strip().lower()
        self._populate_table()

    def _on_select_row(self) -> None:
        """Update action bar state based on row selection."""
        selected = self.tree.selection()
        if not selected:
            self.kill_btn.configure(state="disabled")
            self.selected_info_lbl.configure(text="Select a port to terminate the listening process.")
            return

        item = self.tree.item(selected[0])
        vals = item.get("values", [])
        if len(vals) >= 5:
            port, proto, pid, proc, addr = vals[0], vals[1], vals[2], vals[3], vals[4]
            self.kill_btn.configure(state="normal")
            self.selected_info_lbl.configure(
                text=f"Selected: Port {port} ({proto}) | Process: {proc} (PID: {pid})"
            )

    def _populate_table(self) -> None:
        """Filter and render ports in treeview."""
        for item in self.tree.get_children():
            self.tree.delete(item)

        ports = self.state.ports or []
        visible_count = 0

        for p in ports:
            port_num = str(p.get("port", ""))
            proto = p.get("protocol", "TCP")
            pid = str(p.get("pid", ""))
            proc = p.get("process_name", "")
            addr = p.get("address", "127.0.0.1")

            if self._filter_query:
                haystack = f"{port_num} {proto} {pid} {proc} {addr}".lower()
                if self._filter_query not in haystack:
                    continue

            visible_count += 1
            item_id = f"port_{port_num}_{pid}"
            self.tree.insert(
                "",
                "end",
                iid=item_id,
                values=(port_num, proto, pid, proc, addr),
            )

        self.port_count_lbl.configure(text=f"Active Ports: {visible_count} (Total: {len(ports)})")
        self._on_select_row()

    # -------------------------------------------------------------------------
    # Port Actions
    # -------------------------------------------------------------------------

    def _refresh_ports(self) -> None:
        """Fetch active ports from background daemon asynchronously."""
        self.refresh_btn.configure(text="⏳ Refreshing...", state="disabled")

        def _task():
            return self.client.get_ports()

        def _on_success(ports: List[Dict[str, Any]]):
            try:
                if self.winfo_exists():
                    self.after(0, lambda: self.state.set_ports(ports))
                    self.after(0, lambda: self.refresh_btn.configure(text="🔄 Refresh Ports", state="normal"))
            except Exception:
                pass

        def _on_error(err: Exception):
            logger.debug(f"Failed to fetch ports: {err}")
            try:
                if self.winfo_exists():
                    self.after(0, lambda: self.refresh_btn.configure(text="🔄 Refresh Ports", state="normal"))
            except Exception:
                pass

        self.client.run_async(_task, callback=_on_success, errback=_on_error)

    def _confirm_and_kill_port(self) -> None:
        """Show confirmation dialog and terminate selected listening process."""
        selected = self.tree.selection()
        if not selected:
            return

        item = self.tree.item(selected[0])
        vals = item.get("values", [])
        if len(vals) < 4:
            return

        port_val = vals[0]
        pid_val = vals[2]
        proc_name = vals[3]

        try:
            port_int = int(port_val)
        except ValueError:
            return

        confirmed = messagebox.askyesno(
            "Confirm Process Termination",
            f"Are you sure you want to terminate '{proc_name}' (PID {pid_val}) listening on Port {port_val}?\n\n"
            "This will forcibly close the socket and terminate the target process.",
            parent=self.winfo_toplevel(),
        )

        if not confirmed:
            return

        self.kill_btn.configure(text="⏳ Terminating...", state="disabled")

        def _task():
            return self.client.kill_port(port=port_int, force=True)

        def _on_success(res: Dict[str, Any]):
            killed = res.get("killed", False)
            msg = res.get("message", "Port freed.")

            def _ui():
                if killed:
                    messagebox.showinfo(
                        "Process Terminated",
                        f"Successfully terminated process on Port {port_int}.\n{msg}",
                        parent=self.winfo_toplevel(),
                    )
                else:
                    messagebox.showwarning(
                        "Port Action Notice",
                        f"Could not terminate process on Port {port_int}:\n{msg}",
                        parent=self.winfo_toplevel(),
                    )
                self._refresh_ports()

            self.after(0, _ui)

        def _on_error(err: Exception):
            def _ui_err():
                messagebox.showerror(
                    "Termination Error",
                    f"Failed to terminate process on Port {port_int}:\n{err}",
                    parent=self.winfo_toplevel(),
                )
                self.kill_btn.configure(text="🛑 Terminate Process / Free Port", state="normal")

            self.after(0, _ui_err)

        self.client.run_async(_task, callback=_on_success, errback=_on_error)
