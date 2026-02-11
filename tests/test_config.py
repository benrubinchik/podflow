"""Tests for config loading and validation."""

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from podflow.config import PodflowConfig, load_config


def test_default_config():
    config = PodflowConfig()
    assert config.audio.bitrate == "128k"
    assert config.audio.channels == 1
    assert config.audio.target_lufs == -16.0
    assert config.transcription.backend == "whisper_api"
    assert config.metadata.provider == "anthropic"
    assert config.hosting.method == "local"


def test_load_config_from_yaml():
    data = {
        "audio": {"bitrate": "192k", "channels": 2},
        "feed": {"title": "Test Pod", "author": "Tester"},
    }
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False, encoding="utf-8"
    ) as f:
        yaml.dump(data, f)
        f.flush()
        config = load_config(f.name)

    os.unlink(f.name)
    assert config.audio.bitrate == "192k"
    assert config.audio.channels == 2
    assert config.feed.title == "Test Pod"
    # Defaults preserved for unset fields
    assert config.audio.target_lufs == -16.0
    assert config.video.codec == "libx264"


def test_load_config_missing_file():
    config = load_config("/nonexistent/path.yaml")
    assert config.audio.bitrate == "128k"  # Returns defaults


def test_load_config_empty_yaml():
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False, encoding="utf-8"
    ) as f:
        f.write("")
        f.flush()
        config = load_config(f.name)

    os.unlink(f.name)
    assert config == PodflowConfig()
