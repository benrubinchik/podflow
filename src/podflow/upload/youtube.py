"""YouTube Data API v3 resumable upload with exponential backoff."""

from __future__ import annotations

import random
import time
from pathlib import Path

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from podflow.config import YouTubeConfig
from podflow.metadata.models import EpisodeMetadata
from podflow.upload.auth import get_authenticated_credentials
from podflow.utils.logging import get_logger

log = get_logger(__name__)

MAX_RETRIES = 5
RETRIABLE_STATUS_CODES = [500, 502, 503, 504]


def upload_to_youtube(
    video_path: Path,
    metadata: EpisodeMetadata,
    config: YouTubeConfig,
    privacy: str | None = None,
    episode_number: int | None = None,
) -> str:
    """Upload a video to YouTube with resumable upload and backoff.

    Returns the YouTube video ID.
    """
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    creds = get_authenticated_credentials(
        client_secrets_file=config.client_secrets_file,
        token_file=config.token_file,
    )
    youtube = build("youtube", "v3", credentials=creds)

    title = metadata.title
    if episode_number:
        title = f"Ep. {episode_number} — {title}"
    # YouTube title max is 100 characters
    title = title[:100]

    description = metadata.description
    if metadata.show_notes:
        description += f"\n\n{metadata.show_notes}"

    # Add chapter markers if available
    if metadata.chapters:
        description += "\n\nChapters:\n"
        for ch in metadata.chapters:
            m = int(ch.start_time // 60)
            s = int(ch.start_time % 60)
            description += f"{m:02d}:{s:02d} {ch.title}\n"

    # YouTube description max is 5000 characters
    description = description[:5000]

    tags = metadata.tags[:15]  # YouTube max 500 chars total for tags

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": config.default_category,
        },
        "status": {
            "privacyStatus": privacy or config.default_privacy,
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(
        str(video_path),
        mimetype="video/*",
        resumable=True,
        chunksize=10 * 1024 * 1024,  # 10MB chunks
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    log.info("Starting YouTube upload: %s (%s)", title, video_path.name)
    video_id = _resumable_upload(request)
    log.info("Upload complete — YouTube video ID: %s", video_id)
    return video_id


def _resumable_upload(request) -> str:
    """Execute a resumable upload with exponential backoff."""
    response = None
    retry = 0

    while response is None:
        try:
            status, response = request.next_chunk()
            if status:
                pct = int(status.progress() * 100)
                log.info("Upload progress: %d%%", pct)
        except HttpError as e:
            if e.resp.status in RETRIABLE_STATUS_CODES:
                retry += 1
                if retry > MAX_RETRIES:
                    raise RuntimeError(
                        f"YouTube upload failed after {MAX_RETRIES} retries"
                    ) from e
                wait = (2 ** retry) + random.random()
                log.warning(
                    "Retriable error %d, retrying in %.1fs (attempt %d/%d)",
                    e.resp.status, wait, retry, MAX_RETRIES,
                )
                time.sleep(wait)
            else:
                raise
        except ConnectionError:
            retry += 1
            if retry > MAX_RETRIES:
                raise RuntimeError(
                    f"YouTube upload failed after {MAX_RETRIES} retries (connection error)"
                )
            wait = (2 ** retry) + random.random()
            log.warning(
                "Connection error, retrying in %.1fs (attempt %d/%d)",
                wait, retry, MAX_RETRIES,
            )
            time.sleep(wait)

    return response["id"]
