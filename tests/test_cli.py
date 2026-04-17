import json
from unittest.mock import patch

from click.testing import CliRunner

from portwatch.cli import main
from portwatch.scanner import Listener


def _L(port, pid=100, name="nginx", proto="tcp"):
    return Listener(port, proto, pid, name, f"{name} -g", "root", f"0.0.0.0:{port}")


def test_cli_list_text():
    runner = CliRunner()
    with patch("portwatch.cli.list_listeners", return_value=[_L(80), _L(443)]):
        result = runner.invoke(main, ["list"])
    assert result.exit_code == 0
    assert "80" in result.output
    assert "443" in result.output


def test_cli_list_json():
    runner = CliRunner()
    with patch("portwatch.cli.list_listeners", return_value=[_L(80)]):
        result = runner.invoke(main, ["list", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data[0]["port"] == 80
    assert data[0]["proto"] == "tcp"


def test_cli_who_found():
    runner = CliRunner()
    with patch("portwatch.cli.find_by_port", return_value=[_L(80)]):
        result = runner.invoke(main, ["who", "80"])
    assert result.exit_code == 0
    assert "80" in result.output


def test_cli_who_not_found():
    runner = CliRunner()
    with patch("portwatch.cli.find_by_port", return_value=[]):
        result = runner.invoke(main, ["who", "9999"])
    assert result.exit_code == 3


def test_cli_kill_refuses_pid1():
    runner = CliRunner()
    with patch("portwatch.cli.find_by_port", return_value=[_L(80, pid=1, name="launchd")]):
        result = runner.invoke(main, ["kill", "80", "--yes"])
    assert result.exit_code == 1
    assert "PID 1" in result.output or "pid 1" in result.output.lower()


def test_cli_kill_free_port():
    runner = CliRunner()
    with patch("portwatch.cli.find_by_port", return_value=[]):
        result = runner.invoke(main, ["kill", "9999", "--yes"])
    assert result.exit_code == 3


def test_cli_kill_sends_signal():
    runner = CliRunner()
    with patch("portwatch.cli.find_by_port", return_value=[_L(80, pid=12345)]), patch(
        "portwatch.cli._current_shell_pid", return_value=None
    ), patch("portwatch.cli.os.kill") as mock_kill:
        result = runner.invoke(main, ["kill", "80", "--yes"])
    assert result.exit_code == 0
    mock_kill.assert_called_once()


def test_cli_history_empty(tmp_path):
    runner = CliRunner()
    result = runner.invoke(main, ["history", "--history-path", str(tmp_path / "h.jsonl")])
    assert result.exit_code == 0
    assert "no events" in result.output


def test_cli_history_with_data(tmp_path):
    from portwatch.history import append_events, record_from_listener

    path = tmp_path / "h.jsonl"
    append_events([record_from_listener(_L(80), "open")], path)
    runner = CliRunner()
    result = runner.invoke(main, ["history", "--history-path", str(path)])
    assert result.exit_code == 0
    assert "open" in result.output
    assert "80" in result.output


def test_cli_record_snapshot(tmp_path):
    path = tmp_path / "h.jsonl"
    runner = CliRunner()
    with patch("portwatch.cli.list_listeners", return_value=[_L(80), _L(443)]):
        result = runner.invoke(main, ["record", "--history-path", str(path)])
    assert result.exit_code == 0
    assert "recorded 2" in result.output


def test_cli_version():
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "portwatch" in result.output
