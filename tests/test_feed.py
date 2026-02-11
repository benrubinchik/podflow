"""Tests for feed generation and validation."""

import tempfile
from datetime import datetime, timezone
from pathlib import Path

from podflow.config import FeedConfig
from podflow.feed.generator import create_feed, generate_feed_xml
from podflow.feed.validator import validate_feed
from podflow.metadata.models import EpisodeInfo, EpisodeMetadata


def _make_episode(num: int) -> EpisodeInfo:
    return EpisodeInfo(
        episode_number=num,
        input_file=f"ep{num}.wav",
        audio_url=f"https://cdn.example.com/episodes/ep{num}.mp3",
        audio_size_bytes=50_000_000,
        audio_duration_seconds=1800.0,
        publish_date=datetime(2024, 1, num, tzinfo=timezone.utc),
        metadata=EpisodeMetadata(
            title=f"Episode {num}: Test Title",
            description=f"Description for episode {num}.",
            summary=f"Summary for episode {num}.",
            tags=["tech", "podcast"],
        ),
    )


def test_create_feed():
    config = FeedConfig(
        title="Test Podcast",
        author="Tester",
        email="test@example.com",
        image_url="https://example.com/art.jpg",
    )
    fg = create_feed(config)
    xml = fg.rss_str(pretty=True)
    assert b"Test Podcast" in xml
    assert b"Tester" in xml


def test_generate_feed_xml():
    config = FeedConfig(
        title="Test Podcast",
        author="Tester",
        email="test@example.com",
    )
    episodes = [_make_episode(1), _make_episode(2)]

    with tempfile.TemporaryDirectory() as tmpdir:
        feed_path = Path(tmpdir) / "feed.xml"
        generate_feed_xml(config, episodes, feed_path)

        assert feed_path.exists()
        content = feed_path.read_text(encoding="utf-8")
        assert "Episode 1" in content
        assert "Episode 2" in content
        assert "https://cdn.example.com/episodes/ep1.mp3" in content


def test_validate_feed_valid():
    config = FeedConfig(
        title="Test Podcast",
        author="Tester",
        email="test@example.com",
        image_url="https://example.com/art.jpg",
    )
    episodes = [_make_episode(1)]

    with tempfile.TemporaryDirectory() as tmpdir:
        feed_path = Path(tmpdir) / "feed.xml"
        generate_feed_xml(config, episodes, feed_path)
        result = validate_feed(feed_path)

        # Should pass validation (may have warnings but no errors)
        assert result.is_valid, result.summary()


def test_validate_feed_missing_file():
    result = validate_feed(Path("/nonexistent/feed.xml"))
    assert not result.is_valid
    assert "not found" in result.errors[0]
