"""YAML + Pydantic config loading."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field


class AudioConfig(BaseModel):
    bitrate: str = "128k"
    channels: int = 1
    sample_rate: int = 44100
    target_lufs: float = -16.0
    codec: str = "libmp3lame"


class VideoConfig(BaseModel):
    codec: str = "libx264"
    preset: str = "medium"
    crf: int = 23
    audio_codec: str = "aac"
    audio_bitrate: str = "192k"
    max_width: int = 1920
    max_height: int = 1080


class TranscriptionConfig(BaseModel):
    backend: Literal["whisper_local", "whisper_api"] = "whisper_api"
    model: str = "base"
    language: str | None = None
    prompt: str | None = None


class MetadataConfig(BaseModel):
    provider: Literal["anthropic", "openai"] = "anthropic"
    model: str = "claude-sonnet-4-5-20250929"
    max_tags: int = 10
    generate_chapters: bool = True


class YouTubeConfig(BaseModel):
    client_secrets_file: str = "client_secrets.json"
    token_file: str = ".youtube_token.json"
    default_category: str = "22"  # People & Blogs
    default_privacy: Literal["public", "unlisted", "private"] = "unlisted"


class HostingConfig(BaseModel):
    method: Literal["s3", "scp", "local"] = "local"
    # S3 settings
    s3_bucket: str = ""
    s3_prefix: str = "episodes/"
    s3_endpoint_url: str | None = None
    s3_region: str = "auto"
    s3_public_url_base: str = ""
    # SCP settings
    scp_host: str = ""
    scp_user: str = ""
    scp_remote_path: str = ""
    scp_public_url_base: str = ""
    # Local settings
    local_dir: str = "./output/hosted"
    local_public_url_base: str = "http://localhost:8000/"


class FeedConfig(BaseModel):
    title: str = "My Podcast"
    link: str = "https://example.com"
    description: str = "A podcast about things."
    author: str = "Podcast Author"
    email: str = "podcast@example.com"
    image_url: str = ""
    language: str = "en"
    category: str = "Technology"
    subcategory: str = ""
    explicit: bool = False
    feed_filename: str = "feed.xml"


class OutputConfig(BaseModel):
    base_dir: str = "./output"


class PodflowConfig(BaseModel):
    audio: AudioConfig = Field(default_factory=AudioConfig)
    video: VideoConfig = Field(default_factory=VideoConfig)
    transcription: TranscriptionConfig = Field(default_factory=TranscriptionConfig)
    metadata: MetadataConfig = Field(default_factory=MetadataConfig)
    youtube: YouTubeConfig = Field(default_factory=YouTubeConfig)
    hosting: HostingConfig = Field(default_factory=HostingConfig)
    feed: FeedConfig = Field(default_factory=FeedConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)


def find_config_file() -> Path | None:
    """Search for podcast_config.yaml in cwd and parent dirs."""
    current = Path.cwd()
    for directory in [current, *current.parents]:
        candidate = directory / "podcast_config.yaml"
        if candidate.exists():
            return candidate
    return None


def load_config(config_path: str | Path | None = None) -> PodflowConfig:
    """Load config from YAML file, falling back to defaults."""
    if config_path is None:
        found = find_config_file()
        if found is None:
            return PodflowConfig()
        config_path = found

    config_path = Path(config_path)
    if not config_path.exists():
        return PodflowConfig()

    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    return PodflowConfig(**raw)


def get_api_key(name: str) -> str:
    """Get an API key from environment variables."""
    value = os.environ.get(name, "")
    if not value:
        raise EnvironmentError(
            f"Required environment variable {name} is not set. "
            f"See .env.example for required variables."
        )
    return value
