"""Live watching of listeners with rich.Live diff highlighting."""

from __future__ import annotations

import time
from pathlib import Path

from rich.console import Console
from rich.live import Live

from .formatters import listeners_table
from .history import append_events, diff_listeners, record_from_listener
from .scanner import list_listeners


def run_watch(
    interval: float = 2.0,
    record: bool = False,
    history_path: Path | None = None,
    console: Console | None = None,
) -> None:
    console = console or Console()
    prev = list_listeners()
    added_keys: set = set()
    removed_prev: list = []

    def render():
        title = f"portwatch  |  {len(prev)} listeners  |  interval {interval}s  (Ctrl-C to exit)"
        return listeners_table(
            prev,
            added=added_keys,
            removed=removed_prev,
            title=title,
        )

    try:
        with Live(render(), console=console, refresh_per_second=4, screen=False) as live:
            while True:
                try:
                    time.sleep(interval)
                except KeyboardInterrupt:
                    break
                curr = list_listeners()
                added, removed = diff_listeners(prev, curr)
                if record and (added or removed):
                    events = [record_from_listener(l, "open") for l in added] + [
                        record_from_listener(l, "close") for l in removed
                    ]
                    try:
                        append_events(events, history_path)
                    except OSError:
                        pass
                added_keys = {l.key() for l in added}
                removed_prev = removed
                prev = curr
                try:
                    live.update(render())
                except Exception:
                    # terminal resize or other transient
                    pass
    except KeyboardInterrupt:
        pass
