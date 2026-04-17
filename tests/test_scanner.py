import socket
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import psutil

from portwatch import scanner
from portwatch.scanner import Listener, find_by_port, list_listeners


def _mk_conn(port, pid, proto=socket.SOCK_STREAM, status=psutil.CONN_LISTEN, ip="0.0.0.0"):
    laddr = SimpleNamespace(ip=ip, port=port)
    return SimpleNamespace(
        type=proto, status=status, laddr=laddr, raddr=(), pid=pid, family=socket.AF_INET
    )


def _mock_process(name="nginx", cmd=None, user="root"):
    p = MagicMock()
    p.name.return_value = name
    p.cmdline.return_value = cmd if cmd is not None else [name, "-g", "daemon off;"]
    p.username.return_value = user
    p.oneshot.return_value.__enter__ = lambda s: None
    p.oneshot.return_value.__exit__ = lambda s, *a: None
    return p


def test_list_listeners_basic():
    conns = [_mk_conn(80, 100), _mk_conn(53, 200, proto=socket.SOCK_DGRAM, status="NONE")]
    with patch.object(scanner.psutil, "net_connections", return_value=conns), patch.object(
        scanner.psutil, "Process", return_value=_mock_process()
    ):
        result = list_listeners()
    assert len(result) == 2
    ports = sorted(l.port for l in result)
    assert ports == [53, 80]
    protos = {l.proto for l in result}
    assert protos == {"tcp", "udp"}


def test_list_listeners_skips_non_listen_tcp():
    conns = [_mk_conn(80, 100, status=psutil.CONN_ESTABLISHED)]
    with patch.object(scanner.psutil, "net_connections", return_value=conns):
        result = list_listeners()
    assert result == []


def test_list_listeners_handles_missing_process():
    conns = [_mk_conn(80, 999)]
    with patch.object(scanner.psutil, "net_connections", return_value=conns), patch.object(
        scanner.psutil, "Process", side_effect=psutil.NoSuchProcess(999)
    ):
        result = list_listeners()
    assert len(result) == 1
    assert result[0].name == "?"
    assert result[0].user == "-"


def test_list_listeners_access_denied_on_enum():
    with patch.object(scanner.psutil, "net_connections", side_effect=psutil.AccessDenied()), patch.object(
        scanner, "_iter_connections_unprivileged", return_value=[]
    ):
        assert list_listeners() == []


def test_find_by_port_filters():
    listeners = [
        Listener(80, "tcp", 1, "a", "a", "r", "0:80"),
        Listener(443, "tcp", 2, "b", "b", "r", "0:443"),
    ]
    assert len(find_by_port(80, listeners)) == 1
    assert find_by_port(22, listeners) == []


def test_listener_to_dict():
    l = Listener(80, "tcp", 1, "a", "a -x", "root", "0:80")
    d = l.to_dict()
    assert d["port"] == 80
    assert d["proto"] == "tcp"
    assert d["cmdline"] == "a -x"
