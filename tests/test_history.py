import time

import pytest

from portwatch.history import (
    Event,
    append_events,
    diff_listeners,
    filter_events,
    parse_since,
    read_events,
    record_from_listener,
)
from portwatch.scanner import Listener


def _L(port, pid=100, name="x", proto="tcp"):
    return Listener(port, proto, pid, name, name, "root", f"0.0.0.0:{port}")


def test_history_roundtrip(tmp_path):
    path = tmp_path / "h.jsonl"
    evs = [record_from_listener(_L(80), "open"), record_from_listener(_L(80), "close")]
    n = append_events(evs, path)
    assert n == 2
    back = read_events(path)
    assert len(back) == 2
    assert back[0].port == 80
    assert back[0].action == "open"
    assert back[1].action == "close"


def test_read_events_missing_file(tmp_path):
    assert read_events(tmp_path / "nope.jsonl") == []


def test_diff_listeners():
    prev = [_L(80), _L(443)]
    curr = [_L(443), _L(8080)]
    added, removed = diff_listeners(prev, curr)
    assert {l.port for l in added} == {8080}
    assert {l.port for l in removed} == {80}


def test_parse_since_valid():
    now = time.time()
    assert parse_since("1h") <= now - 3500
    assert parse_since("30m") <= now - 1700
    assert parse_since("2d") <= now - 86400 * 2 + 10


def test_parse_since_invalid():
    with pytest.raises(ValueError):
        parse_since("forever")


def test_filter_events(tmp_path):
    now = time.time()
    events = [
        Event(ts=now - 7200, action="open", port=80, proto="tcp", pid=1, name="a", user="r", laddr="x"),
        Event(ts=now - 60, action="close", port=80, proto="tcp", pid=1, name="a", user="r", laddr="x"),
        Event(ts=now - 30, action="open", port=443, proto="tcp", pid=2, name="b", user="r", laddr="y"),
    ]
    filt = filter_events(events, port=80, since=now - 3600)
    assert len(filt) == 1
    assert filt[0].action == "close"
    assert len(filter_events(events, port=443)) == 1
