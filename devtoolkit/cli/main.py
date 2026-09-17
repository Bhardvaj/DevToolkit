"""Typer CLI interface for DevToolkit."""

import sys
from pathlib import Path
from typing import List, Optional
import typer
from rich.console import Console

# Ensure UTF-8 output on Windows streams
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from devtoolkit.core.registry import PluginRegistry
from devtoolkit.formatters.json_fmt import render_json
from devtoolkit.formatters.table import render_doctor, render_table
from devtoolkit.formatters.yaml_fmt import render_yaml

app = typer.Typer(
    name="devtoolkit",
    help="Extensible developer environment auditor and workstation utility.",
    add_completion=False,
)
console = Console()


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


if __name__ == "__main__":
    app()
