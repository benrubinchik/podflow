"""Audio file hosting — S3, SCP, or local."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from podflow.config import HostingConfig
from podflow.utils.logging import get_logger

log = get_logger(__name__)


class HostingResult:
    def __init__(self, public_url: str, size_bytes: int):
        self.public_url = public_url
        self.size_bytes = size_bytes


def upload_audio(
    audio_path: Path,
    config: HostingConfig,
    remote_filename: str | None = None,
) -> HostingResult:
    """Upload an audio file using the configured hosting method."""
    audio_path = Path(audio_path)
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    if remote_filename is None:
        remote_filename = audio_path.name

    size_bytes = audio_path.stat().st_size

    if config.method == "s3":
        url = _upload_s3(audio_path, remote_filename, config)
    elif config.method == "scp":
        url = _upload_scp(audio_path, remote_filename, config)
    elif config.method == "local":
        url = _upload_local(audio_path, remote_filename, config)
    else:
        raise ValueError(f"Unknown hosting method: {config.method}")

    log.info("Audio hosted at: %s (%d bytes)", url, size_bytes)
    return HostingResult(public_url=url, size_bytes=size_bytes)


def _upload_s3(audio_path: Path, remote_filename: str, config: HostingConfig) -> str:
    """Upload to S3-compatible storage (AWS S3, Cloudflare R2, etc.)."""
    import boto3

    session_kwargs: dict = {}
    client_kwargs: dict = {}

    if config.s3_endpoint_url:
        client_kwargs["endpoint_url"] = config.s3_endpoint_url
    if config.s3_region and config.s3_region != "auto":
        session_kwargs["region_name"] = config.s3_region

    session = boto3.Session(**session_kwargs)
    s3 = session.client("s3", **client_kwargs)

    key = f"{config.s3_prefix}{remote_filename}"
    log.info("Uploading %s to s3://%s/%s", audio_path.name, config.s3_bucket, key)

    s3.upload_file(
        str(audio_path),
        config.s3_bucket,
        key,
        ExtraArgs={"ContentType": "audio/mpeg", "ACL": "public-read"},
    )

    if config.s3_public_url_base:
        base = config.s3_public_url_base.rstrip("/")
        return f"{base}/{key}"
    return f"https://{config.s3_bucket}.s3.amazonaws.com/{key}"


def _upload_scp(audio_path: Path, remote_filename: str, config: HostingConfig) -> str:
    """Upload via SCP to a remote server."""
    remote_path = f"{config.scp_remote_path.rstrip('/')}/{remote_filename}"
    target = f"{config.scp_user}@{config.scp_host}:{remote_path}"

    log.info("Uploading %s via SCP to %s", audio_path.name, target)

    subprocess.run(
        ["scp", str(audio_path), target],
        check=True,
        capture_output=True,
    )

    base = config.scp_public_url_base.rstrip("/")
    return f"{base}/{remote_filename}"


def _upload_local(audio_path: Path, remote_filename: str, config: HostingConfig) -> str:
    """Copy to a local directory for serving by a web server."""
    dest_dir = Path(config.local_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / remote_filename

    log.info("Copying %s to %s", audio_path.name, dest_path)
    shutil.copy2(str(audio_path), str(dest_path))

    base = config.local_public_url_base.rstrip("/")
    return f"{base}/{remote_filename}"
