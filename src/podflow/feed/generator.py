"""RSS 2.0 + iTunes feed generation using python-feedgen."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from feedgen.feed import FeedGenerator

from podflow.config import FeedConfig, HostingConfig
from podflow.metadata.models import EpisodeInfo
from podflow.utils.logging import get_logger
from podflow.utils.time_format import seconds_to_hms

log = get_logger(__name__)


def create_feed(config: FeedConfig) -> FeedGenerator:
    """Create a new podcast RSS feed with iTunes extensions."""
    fg = FeedGenerator()
    fg.load_extension("podcast")

    fg.title(config.title)
    fg.link(href=config.link, rel="alternate")
    fg.description(config.description)
    fg.language(config.language)
    fg.generator("PodFlow")

    # iTunes-specific extensions
    fg.podcast.itunes_author(config.author)
    fg.podcast.itunes_owner(name=config.author, email=config.email)
    fg.podcast.itunes_explicit("yes" if config.explicit else "no")

    if config.category:
        fg.podcast.itunes_category(config.category)

    if config.image_url:
        fg.podcast.itunes_image(config.image_url)
        fg.image(url=config.image_url, title=config.title, link=config.link)

    return fg


def add_episode_to_feed(
    fg: FeedGenerator,
    episode: EpisodeInfo,
) -> None:
    """Add a single episode entry to the feed."""
    if not episode.metadata:
        log.warning("No metadata for episode, skipping feed entry")
        return

    fe = fg.add_entry()
    meta = episode.metadata

    episode_id = episode.audio_url or episode.input_file
    fe.id(episode_id)
    fe.title(meta.title)
    fe.description(meta.description)

    pub_date = episode.publish_date or datetime.now(timezone.utc)
    fe.published(pub_date)

    if meta.show_notes:
        fe.content(content=meta.show_notes, type="html")

    if episode.audio_url:
        fe.enclosure(
            url=episode.audio_url,
            length=str(episode.audio_size_bytes or 0),
            type="audio/mpeg",
        )

    # iTunes episode extensions
    fe.podcast.itunes_summary(meta.summary or meta.description)

    if episode.audio_duration_seconds:
        fe.podcast.itunes_duration(seconds_to_hms(episode.audio_duration_seconds))

    if episode.episode_number:
        fe.podcast.itunes_episode(episode.episode_number)

    if episode.youtube_url:
        fe.link(href=episode.youtube_url, rel="related", title="Watch on YouTube")

    if meta.tags:
        for tag in meta.tags:
            fe.category(term=tag)


def generate_feed_xml(
    config: FeedConfig,
    episodes: list[EpisodeInfo],
    output_path: Path,
) -> Path:
    """Generate the full RSS feed XML file."""
    fg = create_feed(config)

    # Sort episodes by publish date (newest first)
    sorted_episodes = sorted(
        episodes,
        key=lambda e: e.publish_date or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )

    for ep in sorted_episodes:
        add_episode_to_feed(fg, ep)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fg.rss_file(str(output_path), pretty=True)

    log.info("Feed written to %s (%d episodes)", output_path, len(sorted_episodes))
    return output_path


def load_episodes_from_dir(output_base_dir: Path) -> list[EpisodeInfo]:
    """Scan the output directory for completed episodes with metadata."""
    episodes = []
    if not output_base_dir.exists():
        return episodes

    for episode_dir in output_base_dir.iterdir():
        if not episode_dir.is_dir():
            continue
        meta_files = list(episode_dir.glob("*_metadata.json"))
        if not meta_files:
            continue

        meta_path = meta_files[0]
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
            # Look for corresponding state file
            state_files = list(output_base_dir.glob(f".podflow_state_{episode_dir.name}.json"))
            ep_info = EpisodeInfo(
                input_file=episode_dir.name,
                metadata_file=str(meta_path),
            )
            from podflow.metadata.models import EpisodeMetadata
            ep_info.metadata = EpisodeMetadata(**data)

            # Try to find audio info from state
            if state_files:
                state_data = json.loads(state_files[0].read_text(encoding="utf-8"))
                host_outputs = state_data.get("stages", {}).get("host_audio", {}).get("outputs", {})
                ep_info.audio_url = host_outputs.get("audio_url")
                ep_info.audio_size_bytes = host_outputs.get("audio_size_bytes")
                ep_info.audio_duration_seconds = host_outputs.get("audio_duration_seconds")
                yt_outputs = state_data.get("stages", {}).get("upload_youtube", {}).get("outputs", {})
                ep_info.youtube_url = yt_outputs.get("youtube_url")

            episodes.append(ep_info)
        except (json.JSONDecodeError, KeyError) as e:
            log.warning("Skipping %s: %s", episode_dir.name, e)
            continue

    return episodes
