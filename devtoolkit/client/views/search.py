"""Fast Filesystem Search View for DevToolkit Python Native UI."""

from __future__ import annotations

import logging
import os
import tkinter as tk
from tkinter import ttk
from typing import Any, Dict, List, Optional

from devtoolkit.client.api import DevToolkitClient
from devtoolkit.client.state import ClientState
from devtoolkit.client.theme import Colors, Fonts

logger = logging.getLogger(__name__)


class SearchView(ttk.Frame):
    """Fast multi-root filesystem search view with native system launch and explorer actions."""

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
        self._build_search_card()
        self._build_results_table()
        self._build_context_menu()

        # Subscribe to State Changes
        self._unsub_search = self.state.subscribe("search_updated", self._on_search_updated)

        # Restore existing search results if present
        if self.state.search_results:
            self._populate_results(self.state.search_results)

    def destroy(self) -> None:
        """Unsubscribe from state events when destroyed."""
        if hasattr(self._unsub_search, "__call__"):
            self._unsub_search()
        super().destroy()

    # -------------------------------------------------------------------------
    # Layout Builders
    # -------------------------------------------------------------------------

    def _build_header(self) -> None:
        """Top view header."""
        header_row = ttk.Frame(self, style="Main.TFrame")
        header_row.pack(fill="x", pady=(0, 16))

        title = ttk.Label(header_row, text="Fast Multi-Root File Search", style="Header.TLabel")
        title.pack(side="left")

        reindex_btn = ttk.Button(
            header_row,
            text="🔄 Re-index Filesystem",
            style="TButton",
            command=self._trigger_reindex,
        )
        reindex_btn.pack(side="right")

    def _build_search_card(self) -> None:
        """Search query input and filter flags card."""
        card = ttk.Frame(self, style="Card.TFrame", padding=(16, 16))
        card.pack(fill="x", pady=(0, 16))

        # Input Row
        input_row = ttk.Frame(card, style="Card.TFrame")
        input_row.pack(fill="x", pady=(0, 10))

        self.query_var = tk.StringVar(value=self.state.search_query_text)
        self.entry = ttk.Entry(input_row, textvariable=self.query_var)
        self.entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.entry.bind("<Return>", lambda e: self._trigger_search())

        self.search_btn = ttk.Button(
            input_row,
            text="🔍 Search",
            style="Primary.TButton",
            command=self._trigger_search,
        )
        self.search_btn.pack(side="right")

        # Options Row
        options_row = ttk.Frame(card, style="Card.TFrame")
        options_row.pack(fill="x")

        self.match_path_var = tk.BooleanVar(value=False)
        self.regex_var = tk.BooleanVar(value=False)
        self.case_var = tk.BooleanVar(value=False)

        ttk.Checkbutton(options_row, text="Match Full Path", variable=self.match_path_var).pack(
            side="left", padx=(0, 16)
        )
        ttk.Checkbutton(options_row, text="Regular Expression", variable=self.regex_var).pack(
            side="left", padx=(0, 16)
        )
        ttk.Checkbutton(options_row, text="Case Sensitive", variable=self.case_var).pack(
            side="left", padx=(0, 16)
        )

        self.stats_lbl = ttk.Label(options_row, text="", style="CardMuted.TLabel")
        self.stats_lbl.pack(side="right")

    def _build_results_table(self) -> None:
        """Search results treeview table."""
        table_frame = ttk.Frame(self, style="Card.TFrame", padding=1)
        table_frame.pack(fill="both", expand=True)

        columns = ("name", "path", "size")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")

        self.tree.heading("name", text="File Name")
        self.tree.heading("path", text="Directory Path")
        self.tree.heading("size", text="Size")

        self.tree.column("name", width=220)
        self.tree.column("path", width=540)
        self.tree.column("size", width=100, anchor="e")

        # Double-click to open file
        self.tree.bind("<Double-1>", lambda e: self._open_selected_file())
        self.tree.bind("<Return>", lambda e: self._open_selected_file())

        # Right-click context menu
        self.tree.bind("<Button-3>", self._show_context_menu)

        self.tree.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

    def _build_context_menu(self) -> None:
        """Right-click native popup menu for results."""
        self.context_menu = tk.Menu(self, tearoff=0, bg=Colors.BG_CARD, fg=Colors.TEXT_PRIMARY)
        self.context_menu.add_command(label="Open File", command=self._open_selected_file)
        self.context_menu.add_command(label="Show in File Explorer", command=self._reveal_selected_file)
        self.context_menu.add_command(label="Open Containing Folder", command=self._open_containing_folder)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Copy Full Path", command=self._copy_selected_path)

    # -------------------------------------------------------------------------
    # Search Execution
    # -------------------------------------------------------------------------

    def _trigger_search(self) -> None:
        """Execute filesystem search query asynchronously."""
        q = self.query_var.get().strip()
        if not q:
            return

        self.search_btn.configure(text="⏳ Searching...", state="disabled")

        def _task():
            return self.client.search_query(
                query=q,
                match_path=self.match_path_var.get(),
                is_regex=self.regex_var.get(),
                case_sensitive=self.case_var.get(),
            )

        def _on_success(res: Dict[str, Any]):
            results = res.get("results", [])
            total = res.get("total", len(results))
            took_ms = res.get("took_ms", 0)

            def _ui():
                self.state.set_search_results(results, query=q)
                self.stats_lbl.configure(text=f"Found {total} matches in {took_ms}ms")
                self.search_btn.configure(text="🔍 Search", state="normal")

            self.after(0, _ui)

        def _on_error(err: Exception):
            logger.debug(f"Search query error: {err}")

            def _ui_err():
                self.stats_lbl.configure(text="Search error occurred.")
                self.search_btn.configure(text="🔍 Search", state="normal")

            self.after(0, _ui_err)

        self.client.run_async(_task, callback=_on_success, errback=_on_error)

    def _on_search_updated(self, payload: Dict[str, Any]) -> None:
        """Callback on search results update in state."""
        results = payload.get("results", [])
        self.after(0, lambda: self._populate_results(results))

    def _populate_results(self, results: List[Dict[str, Any]]) -> None:
        """Populate treeview with search results."""
        for item in self.tree.get_children():
            self.tree.delete(item)

        for idx, res in enumerate(results):
            name = res.get("filename") or res.get("name", "")
            raw_path = res.get("path", "")
            size_bytes = res.get("size_bytes") or res.get("size", 0)

            # Format Size
            if size_bytes < 1024:
                size_str = f"{size_bytes} B"
            elif size_bytes < 1024 * 1024:
                size_str = f"{size_bytes // 1024} KB"
            else:
                size_str = f"{round(size_bytes / (1024 * 1024), 1)} MB"

            item_id = f"res_{idx}"
            self.tree.insert(
                "",
                "end",
                iid=item_id,
                values=(name, raw_path, size_str),
            )

    def _trigger_reindex(self) -> None:
        """Trigger background re-indexing of monitored roots."""
        self.client.run_async(self.client.trigger_reindex)

    # -------------------------------------------------------------------------
    # Context Actions & File Launches
    # -------------------------------------------------------------------------

    def _get_selected_path(self) -> Optional[str]:
        """Retrieve full path of selected item."""
        selected = self.tree.selection()
        if not selected:
            return None
        item = self.tree.item(selected[0])
        vals = item.get("values", [])
        if len(vals) >= 2:
            return str(vals[1])
        return None

    def _open_selected_file(self) -> None:
        """Open selected file in default OS application."""
        path = self._get_selected_path()
        if path:
            self.client.run_async(self.client.open_file, path)

    def _reveal_selected_file(self) -> None:
        """Reveal file in Explorer."""
        path = self._get_selected_path()
        if path:
            self.client.run_async(self.client.reveal_file, path)

    def _open_containing_folder(self) -> None:
        """Open containing directory."""
        path = self._get_selected_path()
        if path:
            self.client.run_async(self.client.open_folder, path)

    def _copy_selected_path(self) -> None:
        """Copy selected path to clipboard."""
        path = self._get_selected_path()
        if path:
            self.clipboard_clear()
            self.clipboard_append(path)

    def _show_context_menu(self, event: tk.Event) -> None:
        """Display right-click context menu."""
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.context_menu.post(event.x_root, event.y_root)
