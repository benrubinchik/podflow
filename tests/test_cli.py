"""Tests for the CLI commands."""

import tempfile
from pathlib import Path

import yaml
from click.testing import CliRunner

from podflow.cli import cli


def test_version():
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "podflow" in result.output
    assert "0.1.0" in result.output


def test_init_creates_config():
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = str(Path(tmpdir) / "test_config.yaml")
        result = runner.invoke(cli, ["init", "-o", out_path])
        assert result.exit_code == 0
        assert Path(out_path).exists()

        data = yaml.safe_load(Path(out_path).read_text(encoding="utf-8"))
        assert "audio" in data
        assert "feed" in data
        assert data["audio"]["bitrate"] == "128k"


def test_validate_feed_missing():
    runner = CliRunner()
    result = runner.invoke(cli, ["validate-feed", "/nonexistent/feed.xml"])
    # Should fail because the file doesn't exist
    assert result.exit_code != 0
