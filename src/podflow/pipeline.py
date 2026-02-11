"""Stage orchestrator with resume logic."""

from __future__ import annotations

import json
from pathlib import Path

from podflow.config import PodflowConfig
from podflow.metadata.models import EpisodeInfo, EpisodeMetadata, Transcript
from podflow.state import PipelineState, load_state, save_state
from podflow.utils.logging import get_logger
from podflow.utils.paths import (
    episode_id_from_file,
    episode_output_dir,
    find_ffprobe,
    output_audio_path,
    output_metadata_path,
    output_transcript_path,
    output_video_path,
)

log = get_logger(__name__)


def _has_video_stream(input_path: Path) -> bool:
    """Check if the input file contains a video stream."""
    try:
        import ffmpeg
        probe = ffmpeg.probe(str(input_path), cmd=find_ffprobe())
        return any(
            s["codec_type"] == "video"
            for s in probe.get("streams", [])
        )
    except Exception:
        return False


def run_pipeline(
    input_path: Path,
    config: PodflowConfig,
    resume: bool = False,
    dry_run: bool = False,
    episode_number: int | None = None,
    privacy: str | None = None,
) -> EpisodeInfo:
    """Run the full podcast pipeline with stage tracking and resume support."""
    input_path = Path(input_path).resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    base_output = Path(config.output.base_dir)
    episode_id = episode_id_from_file(input_path)
    ep_dir = episode_output_dir(base_output, episode_id)

    # Load or create state
    state = load_state(base_output, episode_id) if resume else PipelineState(episode_id=episode_id)
    state.input_file = str(input_path)

    has_video = _has_video_stream(input_path)

    episode = EpisodeInfo(
        episode_number=episode_number,
        input_file=str(input_path),
        privacy=privacy or config.youtube.default_privacy,
    )

    stages = [
        ("process_audio", lambda: _stage_process_audio(input_path, ep_dir, episode_id, config, episode)),
        ("process_video", lambda: _stage_process_video(input_path, ep_dir, episode_id, config, episode, has_video)),
        ("transcribe", lambda: _stage_transcribe(ep_dir, episode_id, config, episode)),
        ("generate_metadata", lambda: _stage_generate_metadata(ep_dir, episode_id, config, episode)),
        ("upload_youtube", lambda: _stage_upload_youtube(ep_dir, episode_id, config, episode, has_video)),
        ("host_audio", lambda: _stage_host_audio(ep_dir, episode_id, config, episode)),
        ("update_feed", lambda: _stage_update_feed(config, episode)),
    ]

    if dry_run:
        log.info("=== DRY RUN — Pipeline Plan ===")
        log.info("Input: %s", input_path)
        log.info("Episode ID: %s", episode_id)
        log.info("Output dir: %s", ep_dir)
        log.info("Has video: %s", has_video)
        for stage_name, _ in stages:
            status = state.get_stage(stage_name).status.value
            skip = "(skip)" if state.is_completed(stage_name) and resume else ""
            log.info("  Stage: %-20s [%s] %s", stage_name, status, skip)
        return episode

    for stage_name, stage_fn in stages:
        if resume and state.is_completed(stage_name):
            log.info("Skipping completed stage: %s", stage_name)
            # Restore outputs from state
            _restore_from_state(state, stage_name, episode)
            continue

        log.info("=== Running stage: %s ===", stage_name)
        state.set_running(stage_name)
        save_state(state, base_output)

        try:
            outputs = stage_fn()
            state.set_completed(stage_name, outputs or {})
            save_state(state, base_output)
            log.info("Stage %s completed", stage_name)
        except Exception as e:
            state.set_failed(stage_name, str(e))
            save_state(state, base_output)
            log.error("Stage %s failed: %s", stage_name, e)
            raise

    log.info("=== Pipeline complete for %s ===", episode_id)
    return episode


def _restore_from_state(state: PipelineState, stage_name: str, episode: EpisodeInfo) -> None:
    """Restore episode info from saved state outputs."""
    outputs = state.get_stage(stage_name).outputs
    if stage_name == "process_audio" and "audio_file" in outputs:
        episode.audio_file = outputs["audio_file"]
        episode.audio_duration_seconds = outputs.get("audio_duration_seconds")
    elif stage_name == "process_video" and "video_file" in outputs:
        episode.video_file = outputs["video_file"]
    elif stage_name == "transcribe" and "transcript_file" in outputs:
        episode.transcript_file = outputs["transcript_file"]
        path = Path(outputs["transcript_file"])
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            episode.transcript = Transcript(**data)
    elif stage_name == "generate_metadata" and "metadata_file" in outputs:
        episode.metadata_file = outputs["metadata_file"]
        path = Path(outputs["metadata_file"])
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            episode.metadata = EpisodeMetadata(**data)
    elif stage_name == "upload_youtube":
        episode.youtube_video_id = outputs.get("youtube_video_id")
        episode.youtube_url = outputs.get("youtube_url")
    elif stage_name == "host_audio":
        episode.audio_url = outputs.get("audio_url")
        episode.audio_size_bytes = outputs.get("audio_size_bytes")


def _stage_process_audio(
    input_path: Path, ep_dir: Path, episode_id: str,
    config: PodflowConfig, episode: EpisodeInfo,
) -> dict:
    from podflow.processing.audio import get_audio_duration, process_audio

    out_path = output_audio_path(ep_dir, episode_id)
    process_audio(input_path, out_path, config.audio)
    duration = get_audio_duration(out_path)

    episode.audio_file = str(out_path)
    episode.audio_duration_seconds = duration

    return {"audio_file": str(out_path), "audio_duration_seconds": duration}


def _stage_process_video(
    input_path: Path, ep_dir: Path, episode_id: str,
    config: PodflowConfig, episode: EpisodeInfo, has_video: bool,
) -> dict:
    if not has_video:
        log.info("No video stream detected, skipping video processing")
        return {}

    from podflow.processing.video import process_video

    out_path = output_video_path(ep_dir, episode_id)
    process_video(input_path, out_path, config.video)
    episode.video_file = str(out_path)
    return {"video_file": str(out_path)}


def _stage_transcribe(
    ep_dir: Path, episode_id: str,
    config: PodflowConfig, episode: EpisodeInfo,
) -> dict:
    audio_path = Path(episode.audio_file) if episode.audio_file else None
    if audio_path is None or not audio_path.exists():
        raise RuntimeError("Audio file not available for transcription")

    tc = config.transcription
    if tc.backend == "whisper_local":
        from podflow.transcription.whisper_local import WhisperLocalTranscriber
        transcriber = WhisperLocalTranscriber(tc)
    else:
        from podflow.transcription.whisper_api import WhisperAPITranscriber
        transcriber = WhisperAPITranscriber(tc)

    transcript = transcriber.transcribe(audio_path)
    out_path = output_transcript_path(ep_dir, episode_id)
    out_path.write_text(transcript.model_dump_json(indent=2), encoding="utf-8")

    episode.transcript = transcript
    episode.transcript_file = str(out_path)
    return {"transcript_file": str(out_path)}


def _stage_generate_metadata(
    ep_dir: Path, episode_id: str,
    config: PodflowConfig, episode: EpisodeInfo,
) -> dict:
    if episode.transcript is None:
        raise RuntimeError("Transcript not available for metadata generation")

    from podflow.metadata.generator import generate_metadata, save_metadata

    metadata = generate_metadata(episode.transcript, config.metadata)
    out_path = output_metadata_path(ep_dir, episode_id)
    save_metadata(metadata, out_path)

    episode.metadata = metadata
    episode.metadata_file = str(out_path)
    return {"metadata_file": str(out_path)}


def _stage_upload_youtube(
    ep_dir: Path, episode_id: str,
    config: PodflowConfig, episode: EpisodeInfo, has_video: bool,
) -> dict:
    if not has_video or not episode.video_file:
        log.info("No video file, skipping YouTube upload")
        return {}

    if not episode.metadata:
        raise RuntimeError("Metadata not available for YouTube upload")

    from podflow.upload.youtube import upload_to_youtube

    video_id = upload_to_youtube(
        video_path=Path(episode.video_file),
        metadata=episode.metadata,
        config=config.youtube,
        privacy=episode.privacy,
        episode_number=episode.episode_number,
    )
    episode.youtube_video_id = video_id
    episode.youtube_url = f"https://www.youtube.com/watch?v={video_id}"
    return {"youtube_video_id": video_id, "youtube_url": episode.youtube_url}


def _stage_host_audio(
    ep_dir: Path, episode_id: str,
    config: PodflowConfig, episode: EpisodeInfo,
) -> dict:
    if not episode.audio_file:
        raise RuntimeError("Audio file not available for hosting")

    from podflow.feed.hosting import upload_audio

    result = upload_audio(
        audio_path=Path(episode.audio_file),
        config=config.hosting,
    )
    episode.audio_url = result.public_url
    episode.audio_size_bytes = result.size_bytes
    return {
        "audio_url": result.public_url,
        "audio_size_bytes": result.size_bytes,
        "audio_duration_seconds": episode.audio_duration_seconds,
    }


def _stage_update_feed(
    config: PodflowConfig, episode: EpisodeInfo,
) -> dict:
    from podflow.feed.generator import generate_feed_xml, load_episodes_from_dir

    base_output = Path(config.output.base_dir)
    episodes = load_episodes_from_dir(base_output)

    # Add the current episode if not already in the list
    if episode.metadata and episode.audio_url:
        episodes.append(episode)

    feed_path = base_output / config.feed.feed_filename
    generate_feed_xml(config.feed, episodes, feed_path)

    # Also host the feed file if using S3 or SCP
    if config.hosting.method in ("s3", "scp"):
        from podflow.feed.hosting import upload_audio
        upload_audio(
            audio_path=feed_path,
            config=config.hosting,
            remote_filename=config.feed.feed_filename,
        )

    episode.feed_updated = True
    return {"feed_path": str(feed_path)}
