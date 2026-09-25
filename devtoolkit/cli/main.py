"""Typer CLI interface for DevToolkit."""

import sys
from pathlib import Path
from typing import List, Optional
import typer
from rich.console import Console
from rich.markup import escape

# Ensure UTF-8 output on Windows streams
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from devtoolkit.core.config import add_search_path, get_config_path, load_config, remove_search_path
from devtoolkit.core.registry import PluginRegistry
from devtoolkit.formatters.json_fmt import render_json
from devtoolkit.formatters.table import render_doctor, render_ports_table, render_project_audit, render_table
from devtoolkit.formatters.yaml_fmt import render_yaml
from devtoolkit.modules.utilities.ports import PortManager
from devtoolkit.modules.utilities.project_auditor import ProjectAuditor

from devtoolkit.daemon import get_daemon_status, start_daemon, stop_daemon
from devtoolkit.daemon.server import run_daemon_server

app = typer.Typer(
    name="devtoolkit",
    help="Extensible developer environment auditor and workstation utility.",
    add_completion=False,
    invoke_without_command=True,
)
config_app = typer.Typer(
    name="config",
    help="Manage DevToolkit user preferences and custom search paths.",
    add_completion=False,
)
daemon_app = typer.Typer(
    name="daemon",
    help="Manage the DevToolkit background daemon service.",
    add_completion=False,
)
app.add_typer(config_app, name="config")
app.add_typer(daemon_app, name="daemon")
console = Console()


def version_callback(value: bool) -> None:
    if value:
        from devtoolkit import __version__
        print(f"DevToolkit v{__version__}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def default_callback(
    ctx: typer.Context,
    port: int = typer.Option(4321, "--port", "-p", help="Local server port when launching UI."),
    web: bool = typer.Option(False, "--web", help="Open in default browser instead of native desktop window."),
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        help="Show application version and exit.",
        callback=version_callback,
        is_eager=True,
    ),
) -> None:
    """DevToolkit: Extensible developer environment auditor and workstation utility."""
    if ctx.invoked_subcommand is None:
        from devtoolkit.server.app import launch_ui
        launch_ui(port=port, web_only=web)






@app.command(name="inspect", help="Audit installed SDKs, runtimes, and development CLIs.")
def inspect_cmd(
    category: Optional[List[str]] = typer.Option(
        None,
        "--category",
        "-c",
        help="Filter tools by category (e.g., runtime, vcs, mobile, container).",
    ),
    tool: Optional[List[str]] = typer.Option(
        None,
        "--tool",
        "-t",
        help="Audit specific tools by ID (e.g., node, python, docker, git).",
    ),
    format: str = typer.Option(
        "table",
        "--format",
        "-f",
        help="Output format: table (default), json, yaml.",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Save the audit result to a specified file.",
    ),
) -> None:
    """Audit system development environment and report resolved paths, versions, and health."""
    registry = PluginRegistry()

    with console.status("[bold cyan]Auditing developer workstation environment...[/bold cyan]"):
        summary = registry.run_audit(categories=category, tool_ids=tool)

    fmt = format.lower()
    if fmt == "json":
        result = render_json(summary)
        if output:
            output.write_text(result, encoding="utf-8")
            console.print(f"[green]Audit saved to {output}[/green]")
        else:
            print(result)
    elif fmt == "yaml":
        result = render_yaml(summary)
        if output:
            output.write_text(result, encoding="utf-8")
            console.print(f"[green]Audit saved to {output}[/green]")
        else:
            print(result)
    else:
        render_table(summary)
        if output:
            output.write_text(render_json(summary), encoding="utf-8")
            console.print(f"\n[green]Audit JSON copy saved to {output}[/green]")


@app.command(name="doctor", help="Run health diagnostics and display recommended fixes.")
def doctor_cmd() -> None:
    """Check workstation environment for misconfigurations, missing SDK paths, or broken tools."""
    registry = PluginRegistry()

    with console.status("[bold yellow]Running environment health diagnostics...[/bold yellow]"):
        summary = registry.run_audit()

    render_doctor(summary)


@app.command(name="ui", help="Launch the modern DevToolkit desktop UI or local web dashboard.")
def ui_cmd(
    port: int = typer.Option(4321, "--port", "-p", help="Local server port."),
    web_only: bool = typer.Option(False, "--web", help="Open in browser instead of native desktop window."),
    dev: bool = typer.Option(False, "--dev", help="Run in frontend development mode."),
) -> None:
    """Launch the DevToolkit graphical interface."""
    from devtoolkit.server.app import launch_ui
    launch_ui(port=port, web_only=web_only, dev=dev)


@config_app.command(name="list", help="Display active configuration and custom search paths.")
def config_list_cmd() -> None:
    cfg = load_config()
    cfg_file = get_config_path()
    console.print(f"[bold cyan]DevToolkit Config File:[/] {cfg_file}")
    if cfg.search_paths:
        console.print("\n[bold]Custom Search Directories:[/]")
        for sp in cfg.search_paths:
            console.print(f"  • [green]{escape(sp)}[/green]")
    else:
        console.print("\n[dim]No custom search paths configured. Using standard OS & ecosystem discovery.[/dim]")


@config_app.command(name="add-path", help="Add a custom search root directory to monitor for SDKs.")
def config_add_path_cmd(
    path: Path = typer.Argument(..., help="Path to custom directory containing SDKs or tools"),
) -> None:
    p = path.expanduser().resolve()
    if not p.exists() or not p.is_dir():
        console.print(f"[bold red]Error:[/] '{path}' is not an existing directory.")
        raise typer.Exit(code=1)

    added = add_search_path(str(p))
    if added:
        console.print(f"[bold green]✓ Added custom search path:[/] {escape(str(p))}")
    else:
        console.print(f"[yellow]Path is already configured:[/] {escape(str(p))}")


@config_app.command(name="remove-path", help="Remove a custom search root directory from monitoring.")
def config_remove_path_cmd(
    path: str = typer.Argument(..., help="Path or index to remove from configuration"),
) -> None:
    removed = remove_search_path(path)
    if removed:
        console.print(f"[bold green]✓ Removed custom search path:[/] {escape(path)}")
    else:
        console.print(f"[bold yellow]Path not found in configuration:[/] {escape(path)}")


# Ports Sub-Typer
ports_app = typer.Typer(
    name="ports",
    help="Inspect active listening TCP sockets and safely terminate lingering processes.",
    invoke_without_command=True,
    add_completion=False,
)
app.add_typer(ports_app, name="ports")


@ports_app.callback(invoke_without_command=True)
def ports_default(
    ctx: typer.Context,
    dev_only: bool = typer.Option(
        False,
        "--dev-only",
        "-d",
        help="Filter to common developer ports (3000, 5173, 8080, 27017, etc.).",
    ),
    kill: Optional[int] = typer.Option(
        None,
        "--kill",
        "-k",
        help="Quick kill: terminate process on this port.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Force kill even if process is flagged system critical.",
    ),
) -> None:
    """List active listening ports or terminate a process."""
    if ctx.invoked_subcommand is None:
        pm = PortManager()
        if kill is not None:
            with console.status(f"[bold red]Terminating process on port {kill}...[/bold red]"):
                res = pm.kill_port(kill, force=force)
            if res.success:
                console.print(f"[bold green]✓[/] {res.message}")
            else:
                console.print(f"[bold red]✗[/] {res.message}")
                raise typer.Exit(code=1)
            return

        with console.status("[bold cyan]Scanning listening sockets...[/bold cyan]"):
            ports = pm.list_ports(dev_only=dev_only)

        if not ports:
            if dev_only:
                console.print("[yellow]No active developer ports currently in use.[/yellow]")
            else:
                console.print("[dim]No active listening TCP ports detected.[/dim]")
            return

        render_ports_table(ports, dev_only=dev_only)


@ports_app.command(name="kill", help="Safely kill the process occupying a specific port.")
def ports_kill_cmd(
    port: int = typer.Argument(..., help="Port number of the process to terminate"),
    force: bool = typer.Option(False, "--force", "-f", help="Force kill system critical processes."),
) -> None:
    """Terminate the process listening on a port."""
    pm = PortManager()
    with console.status(f"[bold red]Terminating process on port {port}...[/bold red]"):
        res = pm.kill_port(port, force=force)
    if res.success:
        console.print(f"[bold green]✓[/] {res.message}")
    else:
        console.print(f"[bold red]✗[/] {res.message}")
        raise typer.Exit(code=1)


@app.command(name="project", help="Audit local workspace or repository against workstation runtimes.")
def project_cmd(
    path: Path = typer.Argument(
        Path("."),
        help="Path to project directory to audit (defaults to current working directory).",
    ),
    format: str = typer.Option(
        "table",
        "--format",
        "-f",
        help="Output format: table (default), json.",
    ),
) -> None:
    """Audit project dependencies and SDK requirements against workstation state."""
    auditor = ProjectAuditor()
    p = path.expanduser().resolve()

    with console.status(f"[bold cyan]Auditing project requirements at '{p}'...[/bold cyan]"):
        report = auditor.audit_project(p)

    if format.lower() == "json":
        print(report.model_dump_json(indent=2))
    else:
        render_project_audit(report)


@app.command(name="web", help="Open the DevToolkit Web Dashboard directly in default browser.")
def web_cmd(
    port: int = typer.Option(4321, "--port", "-p", help="Server port when launching web dashboard."),
) -> None:
    """Launch or attach to daemon and open web dashboard in default browser."""
    from devtoolkit.server.app import launch_ui
    launch_ui(port=port, web_only=True)




@daemon_app.command(name="start", help="Start the background daemon process.")
def daemon_start_cmd(
    port: int = typer.Option(4321, "--port", "-p", help="Server port to bind to."),
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Network host interface to bind to."),
) -> None:
    """Start the DevToolkit server in detached background daemon mode."""
    with console.status(f"[bold cyan]Starting DevToolkit daemon on {host}:{port}...[/bold cyan]"):
        try:
            state = start_daemon(port=port, host=host)
            console.print(
                f"[bold green]✓ DevToolkit daemon active[/] at [cyan]http://{state.host}:{state.port}[/] (PID: {state.pid})"
            )
        except Exception as e:
            console.print(f"[bold red]✗ Failed to start daemon:[/] {e}")
            raise typer.Exit(code=1)


@daemon_app.command(name="stop", help="Stop the running background daemon process.")
def daemon_stop_cmd() -> None:
    """Gracefully terminate the background DevToolkit daemon."""
    with console.status("[bold cyan]Stopping DevToolkit daemon...[/bold cyan]"):
        stopped = stop_daemon()
    if stopped:
        console.print("[bold green]✓ DevToolkit daemon stopped successfully.[/]")
    else:
        console.print("[yellow]DevToolkit daemon is not running.[/]")


@daemon_app.command(name="status", help="Check status and telemetry of background daemon.")
def daemon_status_cmd() -> None:
    """Inspect PID, uptime, port, and health of background daemon."""
    status = get_daemon_status()
    from rich.panel import Panel
    from rich.table import Table

    table = Table(box=None, show_header=False, pad_edge=False)
    table.add_column("Key", style="bold cyan", width=18)
    table.add_column("Value", style="white")

    if status.running:
        table.add_row("Status", "[bold green]● Running (Active)[/]")
        table.add_row("Process ID", str(status.pid))
        table.add_row("Server URL", f"http://{status.host}:{status.port}")
        table.add_row("Version", f"v{status.version}")
        if status.uptime_seconds is not None:
            mins, secs = divmod(int(status.uptime_seconds), 60)
            hours, mins = divmod(mins, 60)
            table.add_row("Uptime", f"{hours}h {mins}m {secs}s")
        if status.search_status:
            total_indexed = status.search_status.get("total_files", 0)
            table.add_row("Indexed Files", f"{total_indexed:,} files")
        table.add_row("State File", status.state_path or "")
        panel = Panel(table, title="[bold cyan]DevToolkit Daemon Status[/bold cyan]", border_style="green")
    else:
        table.add_row("Status", "[bold red]○ Stopped (Inactive)[/]")
        table.add_row("Message", status.message)
        if status.state_path:
            table.add_row("State File", status.state_path)
        panel = Panel(table, title="[bold cyan]DevToolkit Daemon Status[/bold cyan]", border_style="red")

    console.print(panel)


@daemon_app.command(name="run", hidden=True, help="Internal command to run daemon server in foreground.")
def daemon_run_cmd(
    port: int = typer.Option(4321, "--port", "-p", help="Server port to bind to."),
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Network host interface to bind to."),
) -> None:
    """Execute daemon server process in foreground (internal spawn target)."""
    run_daemon_server(host=host, port=port)


if __name__ == "__main__":
    app()

