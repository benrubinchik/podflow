"""Audio transcoding and loudness normalization using ffmpeg."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import ffmpeg

from podflow.config import AudioConfig
from podflow.utils.logging import get_logger

log = get_logger(__name__)


def get_audio_duration(input_path: Path) -> float:
    """Get duration of an audio file in seconds."""
    probe = ffmpeg.probe(str(input_path))
    duration = float(probe["format"]["duration"])
    return duration


def measure_loudness(input_path: Path) -> dict:
    """Measure loudness using ffmpeg's loudnorm filter (first pass)."""
    cmd = [
        "ffmpeg", "-hide_banner", "-i", str(input_path),
        "-af", "loudnorm=print_format=json",
        "-f", "null", "-"
    ]
    result = subprocess.run(
        cmd, capture_output=True, text=True, check=True,
    )
    # loudnorm JSON is in stderr
    stderr = result.stderr
    # Find the JSON block in the output
    json_start = stderr.rfind("{")
    json_end = stderr.rfind("}") + 1
    if json_start == -1 or json_end == 0:
        raise RuntimeError("Could not parse loudnorm output from ffmpeg")
    loudness_data = json.loads(stderr[json_start:json_end])
    return loudness_data


def process_audio(
    input_path: Path,
    output_path: Path,
    config: AudioConfig,
) -> Path:
    """Transcode audio to MP3 with loudness normalization.

    Two-pass loudness normalization:
    1. Measure current loudness
    2. Apply correction to target LUFS
    """
    input_path = Path(input_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    log.info("Measuring loudness of %s", input_path.name)
    loudness = measure_loudness(input_path)

    measured_i = loudness.get("input_i", "-24.0")
    measured_tp = loudness.get("input_tp", "-2.0")
    measured_lra = loudness.get("input_lra", "7.0")
    measured_thresh = loudness.get("input_thresh", "-34.0")

    loudnorm_filter = (
        f"loudnorm=I={config.target_lufs}:TP=-1.5:LRA=11:"
        f"measured_I={measured_i}:"
        f"measured_TP={measured_tp}:"
        f"measured_LRA={measured_lra}:"
        f"measured_thresh={measured_thresh}:"
        f"print_format=summary"
    )

    log.info(
        "Transcoding %s → %s (mono %s, %s LUFS)",
        input_path.name, output_path.name, config.bitrate, config.target_lufs,
    )

    stream = (
        ffmpeg
        .input(str(input_path))
        .output(
            str(output_path),
            acodec=config.codec,
            audio_bitrate=config.bitrate,
            ac=config.channels,
            ar=config.sample_rate,
            af=loudnorm_filter,
        )
        .overwrite_output()
    )
    stream.run(quiet=True)

    log.info("Audio processing complete: %s", output_path.name)
    return output_path
