# portwatch

A small CLI that tracks which processes hold which TCP/UDP ports on macOS and Linux.

Built on `psutil`, rendered with `rich`, driven by `click`.

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Requires Python 3.10+.

## Usage

```bash
# Show current listeners as a pretty table
portwatch list

# JSON output (for piping to jq etc.)
portwatch list --json

# Who is holding port 8080? (exit 3 if free)
portwatch who 8080

# Kill the process on a port (prompts unless --yes)
portwatch kill 8080
portwatch kill 8080 --force --yes     # SIGKILL, no prompt

# Live view with highlighted diffs (green=new, red=gone)
portwatch watch --interval 2

# Record open/close events to ~/.portwatch/history.jsonl
portwatch record --daemon --interval 5
portwatch list --record               # opportunistic snapshot
portwatch watch --record              # record diffs while watching

# Read recent history
portwatch history --since 1h
portwatch history --port 5432 --since 2d
```

## Safety

- Will refuse to kill PID 1.
- Will refuse to kill your current shell unless `--yes` is given.
- History is append-only JSONL at `~/.portwatch/history.jsonl`.

## Demo

```bash
# Start something that listens, then watch it appear live
python3 -m http.server 8000 &
portwatch who 8000
portwatch kill 8000 --yes
```

## Development

```bash
make install
make test
```

## License

MIT. (c) 2026 farkhad.
