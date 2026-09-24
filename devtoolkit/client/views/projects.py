"""Project Environment Auditor View for DevToolkit Python Native UI."""

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


class ProjectAuditorView(ttk.Frame):
    """Project Auditor view for verifying workspace dependencies, runtimes, and build prerequisites."""

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
        self._build_selector_card()
        self._build_results_panel()

        # Subscribe to State Changes
        self._unsub_project = self.state.subscribe("project_updated", self._on_project_updated)

        # Restore existing project report if available
        if self.state.project_report:
            self._render_report(self.state.project_report)

    def destroy(self) -> None:
        """Unsubscribe from state events when destroyed."""
        if hasattr(self, "_unsub_project") and self._unsub_project:
            self._unsub_project()
        super().destroy()

    # -------------------------------------------------------------------------
    # Layout Builders
    # -------------------------------------------------------------------------

    def _build_header(self) -> None:
        """Top view header."""
        header_row = ttk.Frame(self, style="Main.TFrame")
        header_row.pack(fill="x", pady=(0, 16))

        title = ttk.Label(header_row, text="Project Environment Auditor", style="Header.TLabel")
        title.pack(side="left")

    def _build_selector_card(self) -> None:
        """Directory selection and audit execution card."""
        card = ttk.Frame(self, style="Card.TFrame", padding=(16, 16))
        card.pack(fill="x", pady=(0, 16))

        prompt_lbl = ttk.Label(
            card,
            text="Audit local workspace projects against workstation toolchains, runtimes, and SDKs:",
            style="CardText.TLabel",
        )
        prompt_lbl.pack(anchor="w", pady=(0, 10))

        input_row = ttk.Frame(card, style="Card.TFrame")
        input_row.pack(fill="x")

        initial_path = self.state.project_path or os.getcwd()
        self.path_var = tk.StringVar(value=initial_path)

        entry = ttk.Entry(input_row, textvariable=self.path_var)
        entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        entry.bind("<Return>", lambda e: self._trigger_audit())

        browse_btn = ttk.Button(
            input_row,
            text="📁 Browse...",
            style="TButton",
            command=self._browse_directory,
        )
        browse_btn.pack(side="left", padx=(0, 8))

        self.audit_btn = ttk.Button(
            input_row,
            text="🔍 Audit Project",
            style="Primary.TButton",
            command=self._trigger_audit,
        )
        self.audit_btn.pack(side="right")

    def _build_results_panel(self) -> None:
        """Dynamic container where audit results are displayed."""
        self.results_container = ttk.Frame(self, style="Main.TFrame")
        self.results_container.pack(fill="both", expand=True)

        self.empty_card = ttk.Frame(self.results_container, style="Card.TFrame", padding=(24, 32))
        self.empty_card.pack(fill="x")

        ttk.Label(
            self.empty_card,
            text="No project audit performed yet.",
            style="CardTitle.TLabel",
        ).pack(anchor="center")

        ttk.Label(
            self.empty_card,
            text="Select a project folder above and click 'Audit Project' to verify prerequisites.",
            style="CardMuted.TLabel",
        ).pack(anchor="center", pady=(6, 0))

    # -------------------------------------------------------------------------
    # Actions & Async Audit
    # -------------------------------------------------------------------------

    def _browse_directory(self) -> None:
        """Open native directory chooser dialog."""
        initial = self.path_var.get().strip() or os.getcwd()
        selected_dir = filedialog.askdirectory(
            initialdir=initial if os.path.isdir(initial) else os.getcwd(),
            title="Select Project Directory to Audit",
            parent=self.winfo_toplevel(),
        )
        if selected_dir:
            self.path_var.set(os.path.normpath(selected_dir))
            self._trigger_audit()

    def _trigger_audit(self) -> None:
        """Execute project audit asynchronously."""
        target_path = self.path_var.get().strip()
        if not target_path:
            messagebox.showwarning("Audit Notice", "Please enter a valid directory path.", parent=self.winfo_toplevel())
            return

        self.state.project_path = target_path
        self.audit_btn.configure(text="⏳ Auditing...", state="disabled")

        def _task():
            return self.client.run_project_audit(target_path)

        def _on_success(report: Dict[str, Any]):
            self.after(0, lambda: self.state.set_project_report(report))
            self.after(0, lambda: self.audit_btn.configure(text="🔍 Audit Project", state="normal"))

        def _on_error(err: Exception):
            logger.debug(f"Project audit failed: {err}")
            def _ui_err():
                messagebox.showerror(
                    "Audit Error",
                    f"Failed to audit project directory:\n{err}",
                    parent=self.winfo_toplevel(),
                )
                self.audit_btn.configure(text="🔍 Audit Project", state="normal")
            self.after(0, _ui_err)

        self.client.run_async(_task, callback=_on_success, errback=_on_error)

    def _on_project_updated(self, payload: Dict[str, Any]) -> None:
        """Callback when state project report updates."""
        report = payload.get("report")
        if report:
            self.after(0, lambda: self._render_report(report))

    # -------------------------------------------------------------------------
    # Report Rendering
    # -------------------------------------------------------------------------

    def _render_report(self, report: Dict[str, Any]) -> None:
        """Render complete project audit report."""
        # Clear existing container
        for child in self.results_container.winfo_children():
            child.destroy()

        proj_name = report.get("project_name", "Unknown Project")
        proj_path = report.get("project_path", "")
        ready = report.get("ready_to_build", False)
        detected_types: List[str] = report.get("detected_types", [])
        checks: List[Dict[str, Any]] = report.get("checks", [])
        actions: List[str] = report.get("suggested_actions", [])

        # Top Summary Card
        sum_card = ttk.Frame(self.results_container, style="Card.TFrame", padding=(16, 14))
        sum_card.pack(fill="x", pady=(0, 12))

        left_side = ttk.Frame(sum_card, style="Card.TFrame")
        left_side.pack(side="left", fill="x", expand=True)

        ttk.Label(left_side, text=proj_name, style="Header.TLabel").pack(anchor="w")
        ttk.Label(left_side, text=proj_path, style="CardMuted.TLabel").pack(anchor="w", pady=(2, 6))

        # Detected Types Tags
        tags_frame = ttk.Frame(left_side, style="Card.TFrame")
        tags_frame.pack(anchor="w")

        if detected_types:
            for t in detected_types:
                tag = ttk.Label(tags_frame, text=f"📦 {t}", style="BadgeWarning.TLabel", padding=(6, 2))
                tag.pack(side="left", padx=(0, 6))
        else:
            ttk.Label(tags_frame, text="Generic Workspace", style="CardMuted.TLabel").pack(side="left")

        # Readiness Badge
        right_side = ttk.Frame(sum_card, style="Card.TFrame")
        right_side.pack(side="right")

        readiness_badge = ttk.Label(
            right_side,
            text="✓ Ready to Build" if ready else "⚠️ Action Required",
            style="BadgeSuccess.TLabel" if ready else "BadgeError.TLabel",
            padding=(12, 6),
        )
        readiness_badge.pack(side="right")

        # Prerequisites Table
        table_frame = ttk.Frame(self.results_container, style="Card.TFrame", padding=1)
        table_frame.pack(fill="both", expand=True, pady=(0, 12))

        columns = ("status", "name", "required", "detected", "message")
        tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")

        tree.heading("status", text="Status")
        tree.heading("name", text="Prerequisite")
        tree.heading("required", text="Required Version")
        tree.heading("detected", text="Detected On Machine")
        tree.heading("message", text="Diagnostic Details")

        tree.column("status", width=90, anchor="center")
        tree.column("name", width=160)
        tree.column("required", width=140)
        tree.column("detected", width=160)
        tree.column("message", width=300)

        for c in checks:
            satisfied = c.get("satisfied", False)
            status_text = "✓ OK" if satisfied else "✗ Missing"
            tree.insert(
                "",
                "end",
                values=(
                    status_text,
                    c.get("name", ""),
                    c.get("required", ""),
                    c.get("detected") or "Not found",
                    c.get("message", ""),
                ),
            )

        tree.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")

        # Suggested Actions Card (if any)
        if actions:
            action_card = ttk.Frame(self.results_container, style="Card.TFrame", padding=(16, 12))
            action_card.pack(fill="x")

            ttk.Label(action_card, text="ACTIONABLE RECOMMENDATIONS", style="SidebarHeader.TLabel").pack(
                anchor="w", pady=(0, 6)
            )

            for act in actions:
                row = ttk.Frame(action_card, style="Card.TFrame")
                row.pack(fill="x", pady=2)
                ttk.Label(row, text="•", style="BadgeWarning.TLabel").pack(side="left", padx=(0, 6))
                ttk.Label(row, text=act, style="CardText.TLabel").pack(side="left")
