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
app.add_typer(config_app, name="config")
console = Console()


@app.callback(invoke_without_command=True)
def default_callback(
    ctx: typer.Context,
    port: int = typer.Option(4321, "--port", "-p", help="Local server port when launching UI."),
    web: bool = typer.Option(False, "--web", help="Open in default browser instead of native desktop window."),
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


if __name__ == "__main__":
    app()
