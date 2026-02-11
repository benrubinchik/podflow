"""Path utilities for episode output management."""

from __future__ import annotations

import glob as _glob
import hashlib
import os
import re
import shutil
from pathlib import Path

_ffmpeg_path: str | None = None


def find_ffmpeg() -> str:
    """Find the ffmpeg executable, checking PATH and common install locations."""
    global _ffmpeg_path
    if _ffmpeg_path is not None:
        return _ffmpeg_path

    # Check PATH first
    found = shutil.which("ffmpeg")
    if found:
        _ffmpeg_path = found
        return found

    # Check common winget install location on Windows
    if os.name == "nt":
        winget_pattern = os.path.expanduser(
            "~/AppData/Local/Microsoft/WinGet/Packages/Gyan.FFmpeg*/ffmpeg-*-full_build/bin/ffmpeg.exe"
        )
        matches = _glob.glob(winget_pattern)
        if matches:
            _ffmpeg_path = matches[0]
            return matches[0]

    raise FileNotFoundError(
        "ffmpeg not found. Install it with: winget install ffmpeg"
    )


def find_ffprobe() -> str:
    """Find the ffprobe executable next to ffmpeg."""
    ffmpeg = find_ffmpeg()
    ffprobe = str(Path(ffmpeg).parent / ("ffprobe.exe" if os.name == "nt" else "ffprobe"))
    if os.path.exists(ffprobe):
        return ffprobe
    # Fallback: check PATH
    found = shutil.which("ffprobe")
    if found:
        return found
    raise FileNotFoundError("ffprobe not found")


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
