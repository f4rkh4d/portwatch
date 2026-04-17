"""Append-only JSONL history of port events."""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .scanner import Listener


DEFAULT_HISTORY_PATH = Path.home() / ".portwatch" / "history.jsonl"


@dataclass
class Event:
    ts: float
    action: str  # "open" | "close"
    port: int
    proto: str
    pid: int | None
    name: str
    user: str
    laddr: str

    def to_json(self) -> str:
        return json.dumps(
            {
                "ts": self.ts,
                "action": self.action,
                "port": self.port,
                "proto": self.proto,
                "pid": self.pid,
                "name": self.name,
                "user": self.user,
                "laddr": self.laddr,
            }
        )

    @classmethod
    def from_dict(cls, d: dict) -> "Event":
        return cls(
            ts=d["ts"],
            action=d["action"],
            port=d["port"],
            proto=d["proto"],
            pid=d.get("pid"),
            name=d.get("name", ""),
            user=d.get("user", ""),
            laddr=d.get("laddr", ""),
        )


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def append_events(events: Iterable[Event], path: Path | None = None) -> int:
    path = Path(path) if path else DEFAULT_HISTORY_PATH
    _ensure_parent(path)
    n = 0
    with open(path, "a", encoding="utf-8") as f:
        for e in events:
            f.write(e.to_json() + "\n")
            n += 1
    return n


def record_from_listener(l: Listener, action: str, ts: float | None = None) -> Event:
    return Event(
        ts=ts if ts is not None else time.time(),
        action=action,
        port=l.port,
        proto=l.proto,
        pid=l.pid,
        name=l.name,
        user=l.user,
        laddr=l.laddr,
    )


def diff_listeners(
    prev: list[Listener], curr: list[Listener]
) -> tuple[list[Listener], list[Listener]]:
    prev_keys = {l.key(): l for l in prev}
    curr_keys = {l.key(): l for l in curr}
    added = [curr_keys[k] for k in curr_keys.keys() - prev_keys.keys()]
    removed = [prev_keys[k] for k in prev_keys.keys() - curr_keys.keys()]
    return added, removed


def read_events(path: Path | None = None) -> list[Event]:
    path = Path(path) if path else DEFAULT_HISTORY_PATH
    if not path.exists():
        return []
    out: list[Event] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(Event.from_dict(json.loads(line)))
            except (json.JSONDecodeError, KeyError):
                continue
    return out


_DURATION_RE = re.compile(r"^(\d+)\s*([smhd])$")


def parse_since(since: str) -> float:
    """Parse '1h', '30m', '45s', '2d' into epoch seconds cutoff."""
    m = _DURATION_RE.match(since.strip().lower())
    if not m:
        raise ValueError(f"invalid --since value: {since!r} (use e.g. 30m, 1h, 2d)")
    n = int(m.group(1))
    unit = m.group(2)
    mult = {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit]
    return time.time() - n * mult


def filter_events(
    events: Iterable[Event],
    port: int | None = None,
    since: float | None = None,
) -> list[Event]:
    out = []
    for e in events:
        if port is not None and e.port != port:
            continue
        if since is not None and e.ts < since:
            continue
        out.append(e)
    return out
