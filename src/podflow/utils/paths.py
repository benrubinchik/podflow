"""Path utilities for episode output management."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path


def sanitize_filename(name: str) -> str:
    """Remove or replace characters that are unsafe for filenames."""
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    name = re.sub(r"\s+", "_", name)
    name = name.strip("._")
    return name[:200]


def episode_id_from_file(input_file: Path) -> str:
    """Generate a stable episode ID from the input filename."""
    stem = input_file.stem
    safe = sanitize_filename(stem)
    short_hash = hashlib.sha256(str(input_file.resolve()).encode()).hexdigest()[:8]
    return f"{safe}_{short_hash}"


def episode_output_dir(base_output_dir: Path, episode_id: str) -> Path:
    """Get or create the output directory for an episode."""
    out = base_output_dir / episode_id
    out.mkdir(parents=True, exist_ok=True)
    return out


def output_audio_path(episode_dir: Path, episode_id: str) -> Path:
    return episode_dir / f"{episode_id}.mp3"


def output_video_path(episode_dir: Path, episode_id: str) -> Path:
    return episode_dir / f"{episode_id}.mp4"


def output_transcript_path(episode_dir: Path, episode_id: str) -> Path:
    return episode_dir / f"{episode_id}_transcript.json"


def output_metadata_path(episode_dir: Path, episode_id: str) -> Path:
    return episode_dir / f"{episode_id}_metadata.json"
