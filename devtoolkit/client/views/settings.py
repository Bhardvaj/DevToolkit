"""Preferences and Configuration View for DevToolkit Python Native UI."""

from __future__ import annotations

import logging
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any, Dict, List, Optional

from devtoolkit.client.api import DevToolkitClient
from devtoolkit.client.state import ClientState
from devtoolkit.client.theme import Colors, Fonts

logger = logging.getLogger(__name__)


class SettingsView(ttk.Frame):
    """Configuration view for window behavior, search roots, and daemon connection diagnostics."""

    def __init__(
        self,
        parent: ttk.Frame,
        client: DevToolkitClient,
        state: ClientState,
    ):
        super().__init__(parent, style="Main.TFrame")
        self.client = client
        self.state = state

        self._build_header()
        self._build_close_behavior_card()
        self._build_search_roots_card()
        self._build_daemon_diagnostics_card()

        # Subscribe to State Changes
        self._unsub_config = self.state.subscribe("config_updated", self._on_config_updated)

        # Initial Load
        self._load_config()

    def destroy(self) -> None:
        """Unsubscribe from state events when destroyed."""
        if hasattr(self._unsub_config, "__call__"):
            self._unsub_config()
        super().destroy()

    # -------------------------------------------------------------------------
    # UI Construction
    # -------------------------------------------------------------------------

    def _build_header(self) -> None:
        """Top view header."""
        header_row = ttk.Frame(self, style="Main.TFrame")
        header_row.pack(fill="x", pady=(0, 16))

        title = ttk.Label(header_row, text="DevToolkit Preferences & Settings", style="Header.TLabel")
        title.pack(side="left")

    def _build_close_behavior_card(self) -> None:
        """Window close behavior radio selection card."""
        card = ttk.Frame(self, style="Card.TFrame", padding=(16, 16))
        card.pack(fill="x", pady=(0, 16))

        ttk.Label(card, text="WINDOW CLOSE INTERCEPTION", style="SidebarHeader.TLabel").pack(
            anchor="w", pady=(0, 6)
        )

        desc = ttk.Label(
            card,
            text="Choose what happens when the workstation inspector window is closed:",
            style="CardText.TLabel",
        )
        desc.pack(anchor="w", pady=(0, 10))

        current_action = (self.state.config or {}).get("close_action", "ask")
        self.close_action_var = tk.StringVar(value=current_action)

        options = [
            ("ask", "Ask every time (Prompt to Minimize to System Tray vs Exit Completely)"),
            ("minimize", "Always minimize to System Tray in background (Keep daemon active)"),
            ("exit", "Always exit completely (Stop background daemon and close all services)"),
        ]

        for val, label_text in options:
            rb = ttk.Radiobutton(
                card,
                text=label_text,
                value=val,
                variable=self.close_action_var,
                command=self._update_close_action,
            )
            rb.pack(anchor="w", pady=3)

    def _build_search_roots_card(self) -> None:
        """Monitored search directories manager card."""
        card = ttk.Frame(self, style="Card.TFrame", padding=(16, 16))
        card.pack(fill="x", pady=(0, 16))

        ttk.Label(card, text="MONITORED SEARCH ROOTS", style="SidebarHeader.TLabel").pack(
            anchor="w", pady=(0, 6)
        )

        desc = ttk.Label(
            card,
            text="Directories indexed for rapid workstation file and project searches:",
            style="CardText.TLabel",
        )
        desc.pack(anchor="w", pady=(0, 10))

        # Listbox Frame
        list_frame = ttk.Frame(card, style="Card.TFrame")
        list_frame.pack(fill="x", pady=(0, 10))

        self.roots_listbox = tk.Listbox(
            list_frame,
            height=4,
            bg=Colors.BG_MAIN,
            fg=Colors.TEXT_PRIMARY,
            selectbackground=Colors.ACCENT,
            selectforeground="#FFFFFF",
            font=Fonts.BODY,
            relief="flat",
        )
        self.roots_listbox.pack(side="left", fill="x", expand=True)

        sb = ttk.Scrollbar(list_frame, orient="vertical", command=self.roots_listbox.yview)
        self.roots_listbox.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")

        # Action Buttons
        btn_row = ttk.Frame(card, style="Card.TFrame")
        btn_row.pack(fill="x")

        add_btn = ttk.Button(
            btn_row,
            text="➕ Add Directory...",
            style="TButton",
            command=self._add_search_directory,
        )
        add_btn.pack(side="left", padx=(0, 8))

        del_btn = ttk.Button(
            btn_row,
            text="➖ Remove Selected",
            style="TButton",
            command=self._remove_search_directory,
        )
        del_btn.pack(side="left", padx=(0, 8))

        reindex_btn = ttk.Button(
            btn_row,
            text="🔄 Re-index All Roots",
            style="Primary.TButton",
            command=self._reindex_roots,
        )
        reindex_btn.pack(side="right")

    def _build_daemon_diagnostics_card(self) -> None:
        """Daemon service connection diagnostics card."""
        card = ttk.Frame(self, style="Card.TFrame", padding=(16, 16))
        card.pack(fill="x")

        ttk.Label(card, text="BACKGROUND DAEMON DIAGNOSTICS", style="SidebarHeader.TLabel").pack(
            anchor="w", pady=(0, 8)
        )

        grid_frame = ttk.Frame(card, style="Card.TFrame")
        grid_frame.pack(fill="x")

        diag_items = [
            ("Daemon URL:", self.client.base_url),
            ("Connection Status:", "Connected" if self.state.daemon_connected else "Disconnected"),
            ("Daemon Version:", self.state.daemon_version or "N/A"),
            ("Client Architecture:", f"{os.name} / {Colors.ACCENT}"),
        ]

        for row, (lbl, val) in enumerate(diag_items):
            ttk.Label(grid_frame, text=lbl, style="CardMuted.TLabel").grid(
                row=row, column=0, sticky="w", pady=2, padx=(0, 16)
            )
            ttk.Label(grid_frame, text=val, style="CardText.TLabel").grid(
                row=row, column=1, sticky="w", pady=2
            )

    # -------------------------------------------------------------------------
    # Actions & Handlers
    # -------------------------------------------------------------------------

    def _load_config(self) -> None:
        """Fetch config from daemon asynchronously."""
        def _task():
            return self.client.get_config()

        def _on_success(cfg: Dict[str, Any]):
            self.after(0, lambda: self.state.set_config(cfg))

        self.client.run_async(_task, callback=_on_success)

    def _on_config_updated(self, cfg: Dict[str, Any]) -> None:
        """State subscriber callback."""
        self.after(0, lambda: self._apply_config(cfg))

    def _apply_config(self, cfg: Dict[str, Any]) -> None:
        """Update widgets with config values."""
        close_action = cfg.get("close_action", "ask")
        self.close_action_var.set(close_action)

        search_paths: List[str] = cfg.get("search_paths", [])
        self.roots_listbox.delete(0, tk.END)
        for p in search_paths:
            self.roots_listbox.insert(tk.END, p)

    def _update_close_action(self) -> None:
        """Send close action preference update to daemon."""
        action = self.close_action_var.get()

        def _task():
            return self.client.set_close_action(action)

        def _on_success(res: Dict[str, Any]):
            def _ui():
                if self.state.config:
                    self.state.config["close_action"] = action
            self.after(0, _ui)

        self.client.run_async(_task, callback=_on_success)

    def _add_search_directory(self) -> None:
        """Prompt user for directory to add to search roots."""
        chosen = filedialog.askdirectory(
            title="Select Directory to Monitor and Index",
            parent=self.winfo_toplevel(),
        )
        if not chosen:
            return

        norm_path = os.path.normpath(chosen)

        def _task():
            return self.client.add_search_path(norm_path)

        def _on_success(cfg: Dict[str, Any]):
            self.after(0, lambda: self.state.set_config(cfg))

        self.client.run_async(_task, callback=_on_success)

    def _remove_search_directory(self) -> None:
        """Remove selected search root."""
        selected_indices = self.roots_listbox.curselection()
        if not selected_indices:
            return

        idx = selected_indices[0]
        path_to_remove = self.roots_listbox.get(idx)

        def _task():
            return self.client.remove_search_path(path=path_to_remove, index=idx)

        def _on_success(cfg: Dict[str, Any]):
            self.after(0, lambda: self.state.set_config(cfg))

        self.client.run_async(_task, callback=_on_success)

    def _reindex_roots(self) -> None:
        """Trigger search index rebuild."""
        self.client.run_async(self.client.trigger_reindex)
        messagebox.showinfo(
            "Re-index Triggered",
            "Filesystem search re-indexing has been initiated in the background.",
            parent=self.winfo_toplevel(),
        )
