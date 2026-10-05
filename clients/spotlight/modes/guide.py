"""Interactive cheatsheet and command reference for DevToolkit Spotlight."""

from __future__ import annotations

from typing import Any, Dict, List


def get_command_guide() -> List[Dict[str, Any]]:
    """Return structured command cheatsheet and guide entries."""
    return [
        {
            "id": "guide_default",
            "title": "Default Search: Files & Apps (with Acronyms)",
            "subtitle": "Type filename, folder, or app acronym (e.g. 'vsc' -> VS Code, 'wt' -> Windows Terminal)",
            "type": "guide",
            "badge": "SEARCH",
            "action": "none",
        },
        {
            "id": "guide_port",
            "title": "port: / port:<num> / port:dev / port:<num> kill",
            "subtitle": "Inspect listening ports, drill down with Enter, or kill with Ctrl+K / port:<num> kill",
            "type": "guide",
            "badge": "PORT",
            "action": "none",
        },
        {
            "id": "guide_tool",
            "title": "tool: / tool:<name> (or t:)",
            "subtitle": "Audit 22 developer compilers and runtimes. Enter opens deep diagnostic telemetry drawer",
            "type": "guide",
            "badge": "TOOL",
            "action": "none",
        },
        {
            "id": "guide_project",
            "title": "proj:<path> / project:<path>",
            "subtitle": "Audit repositories for git status, virtualenvs, cleanable caches. Enter opens terminal, Shift+Enter Explorer",
            "type": "guide",
            "badge": "PROJECT",
            "action": "none",
        },
        {
            "id": "guide_window",
            "title": "w: / window: (Window Walker)",
            "subtitle": "Search and switch to running desktop windows. Enter switches to window, Ctrl+K closes it",
            "type": "guide",
            "badge": "WINDOW",
            "action": "none",
        },
        {
            "id": "guide_actions",
            "title": "> or / (Command Palette)",
            "subtitle": "Type '>' to list all actions: > settings, > config, > dashboard, > reindex, > rescan, > logs, > quit",
            "type": "guide",
            "badge": "COMMAND",
            "action": "none",
        },
        {
            "id": "guide_calc",
            "title": "= <math | uuid | epoch | hex>",
            "subtitle": "Inline calculations (1024*16), conversions (0xFF in dec), '= uuid', or '= epoch'. Enter copies result",
            "type": "guide",
            "badge": "CALC",
            "action": "none",
        },
        {
            "id": "guide_keys",
            "title": "Keyboard Shortcuts Cheatsheet",
            "subtitle": "↵ Open/Drilldown • Ctrl+Shift+↵ Run as Admin • Ctrl+K Kill Port/Window • Shift+↵ Explorer • Esc Dismiss",
            "type": "guide",
            "badge": "KEYS",
            "action": "none",
        },
    ]

