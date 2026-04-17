"""portwatch CLI."""

from __future__ import annotations

import os
import signal
import sys
import time
from pathlib import Path

import click
import psutil
from rich.console import Console

from . import __version__
from .formatters import events_table, listeners_json, listeners_table
from .history import (
    DEFAULT_HISTORY_PATH,
    append_events,
    diff_listeners,
    filter_events,
    parse_since,
    read_events,
    record_from_listener,
)
from .scanner import find_by_port, list_listeners
from .watch import run_watch


console = Console()


@click.group()
@click.version_option(__version__, prog_name="portwatch")
def main() -> None:
    """Track which processes hold which TCP/UDP ports."""


@main.command("list")
@click.option("--json", "as_json", is_flag=True, help="Output JSON.")
@click.option("--record", is_flag=True, help="Record a snapshot diff against last run to history.")
@click.option(
    "--history-path",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Override history file path.",
)
def list_cmd(as_json: bool, record: bool, history_path: Path | None) -> None:
    """Show current listeners."""
    listeners = list_listeners()
    if record:
        # Record all as "open" events (opportunistic snapshot)
        try:
            append_events(
                [record_from_listener(l, "open") for l in listeners],
                history_path,
            )
        except OSError as e:
            click.echo(f"warning: failed to record history: {e}", err=True)
    if as_json:
        click.echo(listeners_json(listeners))
    else:
        console.print(listeners_table(listeners, title=f"listeners ({len(listeners)})"))


@main.command("who")
@click.argument("port", type=int)
@click.option("--json", "as_json", is_flag=True)
def who_cmd(port: int, as_json: bool) -> None:
    """Show what's holding PORT. Exit 3 if free."""
    matches = find_by_port(port)
    if not matches:
        click.echo(f"port {port}: free", err=False)
        sys.exit(3)
    if as_json:
        click.echo(listeners_json(matches))
    else:
        console.print(listeners_table(matches, title=f"port {port}"))
    sys.exit(0)


def _current_shell_pid() -> int | None:
    try:
        p = psutil.Process(os.getpid())
        parent = p.parent()
        return parent.pid if parent else None
    except psutil.Error:
        return None


@main.command("kill")
@click.argument("port", type=int)
@click.option("--force", is_flag=True, help="Use SIGKILL instead of SIGTERM.")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt.")
def kill_cmd(port: int, force: bool, yes: bool) -> None:
    """Kill process holding PORT."""
    matches = find_by_port(port)
    if not matches:
        click.echo(f"port {port}: free", err=True)
        sys.exit(3)

    shell_pid = _current_shell_pid()
    sig = signal.SIGKILL if force else signal.SIGTERM

    rc = 0
    for l in matches:
        if l.pid is None:
            click.echo(f"port {port}: no pid available", err=True)
            rc = 1
            continue
        if l.pid == 1:
            click.echo(f"refusing to kill PID 1 ({l.name})", err=True)
            rc = 1
            continue
        warn_shell = shell_pid is not None and l.pid == shell_pid
        if warn_shell and not yes:
            click.echo(
                f"refusing to kill your own shell PID {l.pid} ({l.name}); use --yes to override",
                err=True,
            )
            rc = 1
            continue
        if not yes:
            if not click.confirm(
                f"kill {sig.name} pid={l.pid} ({l.name}) on {l.proto}/{l.port}?",
                default=False,
            ):
                click.echo("aborted", err=True)
                rc = 1
                continue
        try:
            os.kill(l.pid, sig)
            click.echo(f"sent {sig.name} to pid {l.pid} ({l.name}) on {l.proto}/{l.port}")
        except ProcessLookupError:
            click.echo(f"pid {l.pid} no longer exists", err=True)
            rc = 1
        except PermissionError:
            click.echo(f"permission denied killing pid {l.pid}", err=True)
            rc = 1
    sys.exit(rc)


@main.command("watch")
@click.option("--interval", default=2.0, type=float, help="Refresh interval seconds.")
@click.option("--record", is_flag=True, help="Append diffs to history.")
@click.option(
    "--history-path",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
)
def watch_cmd(interval: float, record: bool, history_path: Path | None) -> None:
    """Live refreshing view."""
    try:
        run_watch(interval=interval, record=record, history_path=history_path, console=console)
    except KeyboardInterrupt:
        pass


@main.command("record")
@click.option("--daemon", is_flag=True, help="Run continuously, recording diffs.")
@click.option("--interval", default=5.0, type=float)
@click.option(
    "--history-path",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
)
def record_cmd(daemon: bool, interval: float, history_path: Path | None) -> None:
    """Record open/close events to history."""
    if not daemon:
        listeners = list_listeners()
        n = append_events(
            [record_from_listener(l, "open") for l in listeners],
            history_path,
        )
        click.echo(f"recorded {n} snapshot events")
        return
    click.echo(f"recording diffs every {interval}s to {history_path or DEFAULT_HISTORY_PATH} (Ctrl-C to stop)")
    prev = list_listeners()
    try:
        while True:
            time.sleep(interval)
            curr = list_listeners()
            added, removed = diff_listeners(prev, curr)
            if added or removed:
                events = [record_from_listener(l, "open") for l in added] + [
                    record_from_listener(l, "close") for l in removed
                ]
                append_events(events, history_path)
                click.echo(f"+{len(added)} -{len(removed)}")
            prev = curr
    except KeyboardInterrupt:
        click.echo("stopped")


@main.command("history")
@click.option("--port", type=int, default=None, help="Filter by port.")
@click.option("--since", type=str, default=None, help="e.g. 30m, 1h, 2d")
@click.option("--limit", type=int, default=100, help="Max events to show.")
@click.option(
    "--history-path",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
)
def history_cmd(port: int | None, since: str | None, limit: int, history_path: Path | None) -> None:
    """Show recorded open/close events."""
    events = read_events(history_path)
    cutoff = parse_since(since) if since else None
    events = filter_events(events, port=port, since=cutoff)
    events = events[-limit:]
    if not events:
        click.echo("no events")
        return
    console.print(events_table(events))


if __name__ == "__main__":
    main()
