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
