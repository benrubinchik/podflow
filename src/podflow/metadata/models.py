"""Pydantic models for transcripts, episodes, and metadata."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class TranscriptSegment(BaseModel):
    start: float
    end: float
    text: str


class Transcript(BaseModel):
    segments: list[TranscriptSegment] = Field(default_factory=list)
    language: str = "en"
    full_text: str = ""

    def to_timestamped_text(self) -> str:
        lines = []
        for seg in self.segments:
            ts = _format_timestamp(seg.start)
            lines.append(f"[{ts}] {seg.text}")
        return "\n".join(lines)


class Chapter(BaseModel):
    start_time: float
    title: str


class EpisodeMetadata(BaseModel):
    title: str = ""
    description: str = ""
    show_notes: str = ""
    tags: list[str] = Field(default_factory=list)
    chapters: list[Chapter] = Field(default_factory=list)
    summary: str = ""


class EpisodeInfo(BaseModel):
    """Full episode information combining all pipeline outputs."""
    episode_number: int | None = None
    input_file: str = ""
    audio_file: str | None = None
    video_file: str | None = None
    transcript_file: str | None = None
    metadata_file: str | None = None
    transcript: Transcript | None = None
    metadata: EpisodeMetadata | None = None
    audio_url: str | None = None
    audio_size_bytes: int | None = None
    audio_duration_seconds: float | None = None
    youtube_video_id: str | None = None
    youtube_url: str | None = None
    feed_updated: bool = False
    publish_date: Optional[datetime] = None
    guest: str | None = None
    privacy: str = "unlisted"


def _format_timestamp(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"
