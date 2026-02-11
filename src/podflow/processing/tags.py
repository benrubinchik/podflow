"""ID3 tagging for MP3 files via mutagen."""

from __future__ import annotations

from pathlib import Path

from mutagen.id3 import (
    APIC,
    TALB,
    TCON,
    TDRC,
    TIT2,
    TPE1,
    TRCK,
    COMM,
)
from mutagen.mp3 import MP3

from podflow.metadata.models import EpisodeMetadata
from podflow.utils.logging import get_logger

log = get_logger(__name__)


def apply_id3_tags(
    mp3_path: Path,
    metadata: EpisodeMetadata,
    podcast_title: str = "",
    author: str = "",
    episode_number: int | None = None,
    year: str | None = None,
    artwork_path: Path | None = None,
) -> None:
    """Apply ID3v2.4 tags to an MP3 file."""
    mp3_path = Path(mp3_path)
    audio = MP3(str(mp3_path))

    # Ensure ID3 tags exist
    if audio.tags is None:
        audio.add_tags()

    tags = audio.tags
    tags.add(TIT2(encoding=3, text=[metadata.title]))

    if author:
        tags.add(TPE1(encoding=3, text=[author]))

    if podcast_title:
        tags.add(TALB(encoding=3, text=[podcast_title]))

    if episode_number is not None:
        tags.add(TRCK(encoding=3, text=[str(episode_number)]))

    if year:
        tags.add(TDRC(encoding=3, text=[year]))

    if metadata.tags:
        tags.add(TCON(encoding=3, text=[", ".join(metadata.tags[:5])]))

    if metadata.description:
        tags.add(COMM(encoding=3, lang="eng", desc="", text=[metadata.description]))

    if artwork_path and artwork_path.exists():
        mime = "image/jpeg"
        if artwork_path.suffix.lower() == ".png":
            mime = "image/png"
        with open(artwork_path, "rb") as f:
            tags.add(APIC(encoding=3, mime=mime, type=3, desc="Cover", data=f.read()))

    audio.save()
    log.info("ID3 tags applied to %s", mp3_path.name)
