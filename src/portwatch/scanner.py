"""Enumerate listening TCP/UDP ports via psutil."""

from __future__ import annotations

import socket
from dataclasses import asdict, dataclass
from typing import Iterable

import psutil


@dataclass(frozen=True)
class Listener:
    port: int
    proto: str
    pid: int | None
    name: str
    cmdline: str
    user: str
    laddr: str

    def key(self) -> tuple[str, int, int | None]:
        return (self.proto, self.port, self.pid)

    def to_dict(self) -> dict:
        return asdict(self)


_PROTO_MAP = {
    socket.SOCK_STREAM: "tcp",
    socket.SOCK_DGRAM: "udp",
}


def _proc_info(pid: int | None) -> tuple[str, str, str]:
    if pid is None:
        return ("-", "", "-")
    try:
        p = psutil.Process(pid)
        with p.oneshot():
            name = p.name()
            try:
                cmd = " ".join(p.cmdline()) or name
            except (psutil.AccessDenied, psutil.ZombieProcess):
                cmd = name
            try:
                user = p.username()
            except (psutil.AccessDenied, KeyError):
                user = "-"
        return (name, cmd, user)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return ("?", "", "-")


def _iter_connections_unprivileged() -> list:
    """Fallback: iterate per-process connections (works without root on macOS).

    Per-process psutil conns are pconn tuples without a pid field, so wrap them
    into a minimal shim that matches the sconn-style attributes we use.
    """
    from types import SimpleNamespace

    conns = []
    for p in psutil.process_iter(["pid"]):
        pid = p.info["pid"]
        try:
            for c in p.net_connections(kind="inet"):
                conns.append(
                    SimpleNamespace(
                        type=c.type,
                        status=c.status,
                        laddr=c.laddr,
                        raddr=c.raddr,
                        pid=pid,
                        family=c.family,
                    )
                )
        except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
            continue
    return conns


def list_listeners() -> list[Listener]:
    """Return currently listening sockets (TCP LISTEN + UDP bound)."""
    out: list[Listener] = []
    try:
        conns = psutil.net_connections(kind="inet")
    except (psutil.AccessDenied, PermissionError):
        conns = _iter_connections_unprivileged()

    for c in conns:
        proto = _PROTO_MAP.get(c.type)
        if proto is None:
            continue
        if proto == "tcp" and c.status != psutil.CONN_LISTEN:
            continue
        if not c.laddr:
            continue
        laddr = c.laddr
        try:
            ip = laddr.ip
            port = laddr.port
        except AttributeError:
            continue
        name, cmd, user = _proc_info(c.pid)
        out.append(
            Listener(
                port=port,
                proto=proto,
                pid=c.pid,
                name=name,
                cmdline=cmd,
                user=user,
                laddr=f"{ip}:{port}",
            )
        )
    # de-duplicate (same proto/port/pid can appear on dual-stack)
    seen: set[tuple[str, int, int | None, str]] = set()
    deduped: list[Listener] = []
    for l in out:
        k = (l.proto, l.port, l.pid, l.laddr)
        if k in seen:
            continue
        seen.add(k)
        deduped.append(l)
    deduped.sort(key=lambda l: (l.port, l.proto))
    return deduped


def find_by_port(port: int, listeners: Iterable[Listener] | None = None) -> list[Listener]:
    listeners = list(listeners) if listeners is not None else list_listeners()
    return [l for l in listeners if l.port == port]
