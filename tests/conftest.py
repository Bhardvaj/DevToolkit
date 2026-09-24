"""Global pytest fixtures and configuration for DevToolkit test suite."""

import tkinter as tk
import pytest


@pytest.fixture(scope="session")
def session_tk_root():
    """Create a persistent headless Tk root for the entire test session.

    Tcl 8.6 cannot be safely re-initialized in the same OS process once destroyed.
    Reusing a single hidden root across all GUI tests ensures zero TclError crashes.
    """
    try:
        root = tk.Tk()
        root.withdraw()
        yield root
        try:
            root.destroy()
        except Exception:
            pass
    except Exception:
        yield None


@pytest.fixture
def tk_root(session_tk_root):
    """Provide clean Tk root per test, clearing child widgets after each run."""
    yield session_tk_root
    if session_tk_root:
        for child in session_tk_root.winfo_children():
            try:
                child.destroy()
            except Exception:
                pass
