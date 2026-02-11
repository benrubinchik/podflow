"""Tests for Pydantic models."""

from podflow.metadata.models import (
    Chapter,
    EpisodeInfo,
    EpisodeMetadata,
    Transcript,
    TranscriptSegment,
)


def test_transcript_to_timestamped_text():
    t = Transcript(
        segments=[
            TranscriptSegment(start=0.0, end=5.0, text="Hello world"),
            TranscriptSegment(start=5.0, end=10.0, text="This is a test"),
            TranscriptSegment(start=3661.0, end=3670.0, text="Over an hour in"),
        ],
        language="en",
        full_text="Hello world This is a test Over an hour in",
    )
    text = t.to_timestamped_text()
    assert "[00:00] Hello world" in text
    assert "[00:05] This is a test" in text
    assert "[01:01:01] Over an hour in" in text


def test_episode_metadata_defaults():
    m = EpisodeMetadata()
    assert m.title == ""
    assert m.tags == []
    assert m.chapters == []


def test_episode_metadata_with_chapters():
    m = EpisodeMetadata(
        title="Test Episode",
        chapters=[
            Chapter(start_time=0, title="Intro"),
            Chapter(start_time=300, title="Main Topic"),
        ],
    )
    assert len(m.chapters) == 2
    assert m.chapters[1].title == "Main Topic"


def test_episode_info_defaults():
    ep = EpisodeInfo()
    assert ep.episode_number is None
    assert ep.privacy == "unlisted"
    assert ep.feed_updated is False
