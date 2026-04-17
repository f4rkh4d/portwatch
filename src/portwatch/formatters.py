"""Rich-based formatters for portwatch."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Iterable

from rich.table import Table

from .history import Event
from .scanner import Listener


def listeners_table(
    listeners: Iterable[Listener],
    *,
    added: set | None = None,
    removed: set | None = None,
    title: str | None = None,
) -> Table:
    table = Table(title=title, show_lines=False, header_style="bold")
    table.add_column("PORT", justify="right")
    table.add_column("PROTO")
    table.add_column("PID", justify="right")
    table.add_column("NAME")
    table.add_column("USER")
    table.add_column("LADDR")
    table.add_column("CMD", overflow="fold", no_wrap=False)

    listeners = list(listeners)
    if removed:
        # Render removed rows before current so users can see them
        for l in removed:
            _add_row(table, l, style="red strike")

    for l in listeners:
        style = None
        if added and l.key() in added:
            style = "green"
        _add_row(table, l, style=style)
    return table


def _add_row(table: Table, l: Listener, style: str | None = None) -> None:
    table.add_row(
        str(l.port),
        l.proto,
        "-" if l.pid is None else str(l.pid),
        l.name or "-",
        l.user or "-",
        l.laddr,
        (l.cmdline or "")[:200],
        style=style,
    )


def listeners_json(listeners: Iterable[Listener]) -> str:
    return json.dumps([l.to_dict() for l in listeners], indent=2)


def events_table(events: Iterable[Event]) -> Table:
    table = Table(show_lines=False, header_style="bold")
    table.add_column("TIME")
    table.add_column("ACTION")
    table.add_column("PORT", justify="right")
    table.add_column("PROTO")
    table.add_column("PID", justify="right")
    table.add_column("NAME")
    table.add_column("LADDR")
    for e in events:
        style = "green" if e.action == "open" else "red"
        ts = datetime.fromtimestamp(e.ts).strftime("%Y-%m-%d %H:%M:%S")
        table.add_row(
            ts,
            e.action,
            str(e.port),
            e.proto,
            "-" if e.pid is None else str(e.pid),
            e.name or "-",
            e.laddr,
            style=style,
        )
    return table
