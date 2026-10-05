"""Tests for PortManager utility."""

from devtoolkit.modules.utilities.ports import PortManager, PortInfo


def test_port_manager_list():
    pm = PortManager()
    ports = pm.list_ports()
    assert isinstance(ports, list)
    if ports:
        p = ports[0]
        assert isinstance(p, PortInfo)
        assert isinstance(p.port, int)
        assert p.port > 0
        assert p.pid >= 0


def test_port_manager_system_critical_protection():
    pm = PortManager()
    # Attempting to kill port with non-existent or system critical PID
    res = pm.kill_port(target_port=99999)
    assert res.success is False
    assert "No active process" in res.message


def test_port_categorization_and_dev_process():
    from devtoolkit.modules.utilities.ports import categorize_port, is_dev_process

    # Dev process patterns
    assert is_dev_process("node.exe") is True
    assert is_dev_process("python.exe") is True
    assert is_dev_process("uvicorn.exe") is True
    assert is_dev_process("vite.exe") is True
    assert is_dev_process("svchost.exe") is False
    assert is_dev_process("explorer.exe") is False

    # Categories
    assert categorize_port(5432, "postgres.exe", is_dev=True, is_crit=False) == "Database"
    assert categorize_port(3306, "mysqld.exe", is_dev=True, is_crit=False) == "Database"
    assert categorize_port(5037, "adb.exe", is_dev=True, is_crit=False) == "Debug"
    assert categorize_port(9229, "node.exe", is_dev=True, is_crit=False) == "Debug"
    assert categorize_port(3000, "node.exe", is_dev=True, is_crit=False) == "Dev"
    assert categorize_port(5173, "vite.exe", is_dev=True, is_crit=False) == "Dev"
    assert categorize_port(135, "svchost.exe", is_dev=False, is_crit=True) == "System"
    assert categorize_port(59100, "random.exe", is_dev=False, is_crit=False) == "Service"


def test_port_info_model_dev_fields():
    p = PortInfo(
        port=5173,
        protocol="TCP",
        pid=1234,
        process_name="vite.exe",
        is_dev_port=True,
        is_dev=True,
        category="Dev",
    )
    assert p.is_dev_port is True
    assert p.is_dev is True
    assert p.category == "Dev"
    data = p.model_dump()
    assert data["is_dev_port"] is True
    assert data["is_dev"] is True
    assert data["category"] == "Dev"


