"""Video re-encoding for YouTube compatibility."""

from __future__ import annotations

from pathlib import Path

import ffmpeg

from podflow.config import VideoConfig
from podflow.utils.logging import get_logger

log = get_logger(__name__)


def probe_video(input_path: Path) -> dict:
    """Probe a video file for stream information."""
    return ffmpeg.probe(str(input_path))


def needs_reencode(input_path: Path, config: VideoConfig) -> bool:
    """Check if a video needs re-encoding for YouTube."""
    try:
        probe = probe_video(input_path)
    except ffmpeg.Error:
        return True

    video_streams = [
        s for s in probe.get("streams", [])
        if s["codec_type"] == "video"
    ]
    if not video_streams:
        return False

    vs = video_streams[0]
    codec = vs.get("codec_name", "")
    width = int(vs.get("width", 0))
    height = int(vs.get("height", 0))

    if codec != "h264":
        return True
    if width > config.max_width or height > config.max_height:
        return True
    return False


def process_video(
    input_path: Path,
    output_path: Path,
    config: VideoConfig,
) -> Path:
    """Re-encode video for YouTube compatibility (H.264 + AAC)."""
    input_path = Path(input_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not needs_reencode(input_path, config):
        log.info("Video already compatible, copying: %s", input_path.name)
        stream = (
            ffmpeg
            .input(str(input_path))
            .output(str(output_path), c="copy")
            .overwrite_output()
        )
        stream.run(quiet=True)
        return output_path

    log.info(
        "Re-encoding video %s → %s (H.264 crf=%d, %s)",
        input_path.name, output_path.name, config.crf, config.preset,
    )

    probe = probe_video(input_path)
    video_streams = [
        s for s in probe.get("streams", [])
        if s["codec_type"] == "video"
    ]

    output_kwargs = {
        "vcodec": config.codec,
        "preset": config.preset,
        "crf": config.crf,
        "acodec": config.audio_codec,
        "audio_bitrate": config.audio_bitrate,
        "movflags": "+faststart",
        "pix_fmt": "yuv420p",
    }

    # Scale down if needed while preserving aspect ratio
    if video_streams:
        width = int(video_streams[0].get("width", 0))
        height = int(video_streams[0].get("height", 0))
        if width > config.max_width or height > config.max_height:
            output_kwargs["vf"] = (
                f"scale='min({config.max_width},iw)':min'({config.max_height},ih)'"
                f":force_original_aspect_ratio=decrease,"
                f"pad=ceil(iw/2)*2:ceil(ih/2)*2"
            )

    stream = (
        ffmpeg
        .input(str(input_path))
        .output(str(output_path), **output_kwargs)
        .overwrite_output()
    )
    stream.run(quiet=True)

    log.info("Video processing complete: %s", output_path.name)
    return output_path
