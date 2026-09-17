"""Tests for Project Workstation Auditor."""

import json
from pathlib import Path
from devtoolkit.modules.utilities.project_auditor import ProjectAuditor, ProjectAuditReport


def test_audit_nonexistent_directory(tmp_path):
    auditor = ProjectAuditor()
    fake_path = tmp_path / "does_not_exist"
    report = auditor.audit_project(fake_path)
    assert isinstance(report, ProjectAuditReport)
    assert report.ready_to_build is False
    assert any(c.name == "Project Directory" and not c.satisfied for c in report.checks)


def test_audit_generic_directory(tmp_path):
    auditor = ProjectAuditor()
    report = auditor.audit_project(tmp_path)
    assert isinstance(report, ProjectAuditReport)
    assert "Generic Workspace" in [c.name for c in report.checks]


def test_audit_python_project(tmp_path):
    pyproj = tmp_path / "pyproject.toml"
    pyproj.write_text('[project]\nname = "test"\nrequires-python = ">=3.11"', encoding="utf-8")
    
    # Also simulate a .venv
    venv_dir = tmp_path / ".venv"
    venv_dir.mkdir()

    auditor = ProjectAuditor()
    report = auditor.audit_project(tmp_path)
    assert "Python" in report.detected_types
    check_names = {c.name for c in report.checks}
    assert "Python Interpreter" in check_names
    assert "Project Virtual Environment" in check_names
    venv_check = next(c for c in report.checks if c.name == "Project Virtual Environment")
    assert venv_check.satisfied is True


def test_audit_node_project(tmp_path):
    pkg_json = tmp_path / "package.json"
    pkg_json.write_text(
        json.dumps({
            "name": "test-web",
            "version": "1.0.0",
            "engines": {"node": ">=18.0.0"},
            "packageManager": "pnpm@9.0.0"
        }),
        encoding="utf-8"
    )

    auditor = ProjectAuditor()
    report = auditor.audit_project(tmp_path)
    assert "Node.js / Frontend" in report.detected_types
    check_names = {c.name for c in report.checks}
    assert "Node.js Runtime" in check_names
    assert "Node.js Version Engine" in check_names


def test_audit_docker_project(tmp_path):
    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text("FROM alpine:latest\nCMD echo hello", encoding="utf-8")

    auditor = ProjectAuditor()
    report = auditor.audit_project(tmp_path)
    assert "Docker" in report.detected_types
    check_names = {c.name for c in report.checks}
    assert "Docker Engine" in check_names
