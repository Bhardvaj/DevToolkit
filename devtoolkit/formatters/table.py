"""Rich console table and diagnostic formatters."""

import sys
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from devtoolkit.core.models import AuditSummary, DiagnosticLevel, HealthStatus, ToolReport

# Ensure UTF-8 output on Windows streams
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

console = Console()


def get_status_badge(status: HealthStatus) -> Text:
    if status == HealthStatus.HEALTHY:
        return Text("[OK] Healthy", style="bold green")
    elif status == HealthStatus.WARNING:
        return Text("[!] Warning", style="bold yellow")
    elif status == HealthStatus.ERROR:
        return Text("[X] Error", style="bold red")
    else:
        return Text("[-] Not Found", style="dim")


def render_table(summary: AuditSummary) -> None:
    """Render a comprehensive Rich table of the environment audit."""
    sys_info = summary.system
    header_text = (
        f"[bold cyan]DevToolkit Workstation Audit[/bold cyan]  "
        f"[dim]|[/dim]  OS: [bold]{sys_info.os_name} {sys_info.os_release}[/bold] ({sys_info.arch})  "
        f"[dim]|[/dim]  Host: [bold]{sys_info.hostname}[/bold]"
    )
    console.print(Panel(header_text, border_style="cyan", padding=(0, 1)))

    table = Table(
        title="Detected SDKs, Runtimes & CLIs",
        title_style="bold white",
        border_style="bright_black",
        header_style="bold cyan",
        show_lines=True,
    )

    table.add_column("Status", width=16, justify="left")
    table.add_column("Tool", width=16, style="bold")
    table.add_column("Category", width=12, style="dim")
    table.add_column("Version", width=18, style="green")
    table.add_column("Resolved Path", min_width=25, style="cyan", overflow="fold")
    table.add_column("Companions & Diagnostics", min_width=28, overflow="fold")

    for r in summary.reports:
        badge = get_status_badge(r.status)
        ver_text = r.version or "[dim]-[/dim]"
        path_text = r.binary_path or (f"[dim]Home: {r.home_path}[/dim]" if r.home_path else "[dim]-[/dim]")

        # Format companions
        comp_parts = []
        for c in r.companions:
            if c.installed:
                v_str = f" ({c.version})" if c.version else ""
                comp_parts.append(f"[green]+[/green] {c.name}{v_str}")
            else:
                comp_parts.append(f"[dim]- {c.name}[/dim]")

        diag_parts = []
        for d in r.diagnostics:
            color = "yellow" if d.level == DiagnosticLevel.WARNING else ("red" if d.level == DiagnosticLevel.ERROR else "blue")
            diag_parts.append(f"[{color}]* {d.message}[/{color}]")

        notes = []
        if comp_parts:
            notes.append(" ".join(comp_parts))
        if diag_parts:
            notes.append("\n".join(diag_parts))

        companion_summary = "\n".join(notes) if notes else "[dim]-[/dim]"

        table.add_row(badge, r.name, r.category.capitalize(), ver_text, path_text, companion_summary)

    console.print(table)

    # Summary metric footer
    summary_text = (
        f"[bold]Total Audited:[/] {summary.total_tools}   "
        f"[bold green]Installed:[/] {summary.installed_count}   "
        f"[bold green]Healthy:[/] {summary.healthy_count}   "
        f"[bold yellow]Warnings:[/] {summary.warning_count}   "
        f"[bold red]Errors:[/] {summary.error_count}   "
        f"[dim]Not Found:[/] {summary.not_found_count}"
    )
    console.print(Panel(summary_text, border_style="green" if summary.error_count == 0 else "yellow", padding=(0, 1)))


def render_doctor(summary: AuditSummary) -> None:
    """Render a focused doctor diagnostic view with actionable fixes."""
    console.print(Panel("[bold yellow]DevToolkit Environment Doctor[/bold yellow]", border_style="yellow"))

    issues_found = False
    for r in summary.reports:
        if r.diagnostics:
            issues_found = True
            console.print(f"\n[bold]{r.name}[/bold] ({r.category}):")
            for d in r.diagnostics:
                color = "yellow" if d.level == DiagnosticLevel.WARNING else ("red" if d.level == DiagnosticLevel.ERROR else "blue")
                console.print(f"  [{color}][{d.level.upper()}][/{color}] {d.message}")
                if d.suggested_fix:
                    console.print(f"    [bold green]Suggested Fix:[/] {d.suggested_fix}")

    if not issues_found:
        console.print("\n[bold green]+ All inspected tools and environment variables are in good health![/bold green]\n")


def render_ports_table(ports: list, dev_only: bool = False) -> None:
    """Render a clean Rich table of listening ports and occupying processes."""
    dev_count = sum(1 for p in ports if p.is_dev_port)
    header = (
        f"[bold cyan]DevToolkit Port Manager[/bold cyan]  "
        f"[dim]|[/dim]  Listening Sockets: [bold]{len(ports)}[/bold]  "
        f"[dim]|[/dim]  Dev Ports: [bold green]{dev_count}[/bold green]"
    )
    console.print(Panel(header, border_style="cyan", padding=(0, 1)))

    table = Table(
        title="Active Listening Sockets",
        title_style="bold white",
        border_style="bright_black",
        header_style="bold cyan",
        show_lines=False,
    )

    table.add_column("Port", width=9, style="bold cyan")
    table.add_column("Tag", width=12)
    table.add_column("Process Name", style="bold white", overflow="ellipsis")
    table.add_column("PID", width=8, justify="right", style="yellow")
    table.add_column("Address", width=14, style="dim", overflow="ellipsis")
    table.add_column("Status", width=18)

    for p in ports:
        tag = Text("[DEV PORT]", style="bold magenta") if p.is_dev_port else Text("[SERVICE]", style="dim")
        if p.is_system_critical:
            status = Text("[!] System Protected", style="bold red")
        else:
            status = Text("[OK] User Process", style="green")

        port_str = f":{p.port}"
        table.add_row(port_str, tag, p.process_name, str(p.pid), p.address, status)

    console.print(table)
    console.print(
        "[dim]Tip: Terminate an occupying process safely with:[/] [bold cyan]devtoolkit ports kill <port>[/]\n"
    )


def render_project_audit(report) -> None:
    """Render a comprehensive project audit report with readiness checklist."""
    types_str = ", ".join(report.detected_types) if report.detected_types else "Generic Project"
    status_text = "[bold green]READY TO BUILD[/]" if report.ready_to_build else "[bold red]ACTION REQUIRED[/]"
    
    header = (
        f"[bold cyan]DevToolkit Project Auditor[/bold cyan]  "
        f"[dim]|[/dim]  Project: [bold]{report.project_name}[/bold]  "
        f"[dim]|[/dim]  Ecosystems: [bold yellow]{types_str}[/bold yellow]  "
        f"[dim]|[/dim]  Status: {status_text}"
    )
    console.print(Panel(header, border_style="green" if report.ready_to_build else "red", padding=(0, 1)))

    table = Table(
        title="Workstation Prerequisites Checklist",
        title_style="bold white",
        border_style="bright_black",
        header_style="bold cyan",
        show_lines=True,
    )

    table.add_column("Status", width=14)
    table.add_column("Requirement", width=24, style="bold")
    table.add_column("Expected", width=18, style="dim")
    table.add_column("Detected", width=18, style="cyan")
    table.add_column("Details", min_width=30, overflow="fold")

    for c in report.checks:
        status = Text("[OK] Satisfied", style="bold green") if c.satisfied else Text("[X] Missing", style="bold red")
        table.add_row(status, c.name, c.required, c.detected or "[dim]None[/dim]", c.message)

    console.print(table)

    if report.suggested_actions:
        actions_panel = "\n".join(f"[bold cyan]•[/] {act}" for act in report.suggested_actions)
        console.print(Panel(actions_panel, title="[bold yellow]Recommended Setup Commands[/bold yellow]", border_style="yellow"))
    else:
        if report.ready_to_build:
            console.print("[bold green]+ Machine satisfies all detected project requirements![/bold green]\n")

