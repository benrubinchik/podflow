"""Click CLI entry point for PodFlow."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from podflow import __version__
from podflow.config import load_config
from podflow.utils.logging import console, setup_logging


@click.group()
@click.version_option(version=__version__, prog_name="podflow")
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose logging")
@click.option(
    "-c", "--config", "config_path",
    type=click.Path(exists=False),
    default=None,
    help="Path to podcast_config.yaml",
)
@click.pass_context
def cli(ctx: click.Context, verbose: bool, config_path: str | None) -> None:
    """PodFlow — Podcast Automation Pipeline."""
    setup_logging(verbose=verbose)
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    ctx.obj["config_path"] = config_path


@cli.command()
@click.option(
    "-o", "--output", "output_path",
    type=click.Path(),
    default="podcast_config.yaml",
    help="Output path for the config file",
)
def init(output_path: str) -> None:
    """Generate a starter podcast_config.yaml."""
    from podflow.config import PodflowConfig

    out = Path(output_path)
    if out.exists():
        if not click.confirm(f"{out} already exists. Overwrite?"):
            raise SystemExit(0)

    import yaml

    config = PodflowConfig()
    data = config.model_dump()
    out.write_text(
        yaml.dump(data, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )
    console.print(f"[green]Config written to {out}[/green]")
    console.print("Edit this file with your podcast details, then run:")
    console.print("  podflow run <input_file>")


@cli.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--resume", is_flag=True, help="Resume from last failed stage")
@click.option("--dry-run", is_flag=True, help="Show the plan without executing")
@click.option("--episode-number", "-n", type=int, default=None, help="Episode number")
@click.option(
    "--privacy",
    type=click.Choice(["public", "unlisted", "private"]),
    default=None,
    help="YouTube privacy status",
)
@click.pass_context
def run(
    ctx: click.Context,
    input_file: str,
    resume: bool,
    dry_run: bool,
    episode_number: int | None,
    privacy: str | None,
) -> None:
    """Run the full podcast pipeline on an input file."""
    from podflow.pipeline import run_pipeline

    config = load_config(ctx.obj["config_path"])
    try:
        episode = run_pipeline(
            input_path=Path(input_file),
            config=config,
            resume=resume,
            dry_run=dry_run,
            episode_number=episode_number,
            privacy=privacy,
        )
        if not dry_run:
            console.print("\n[green bold]Pipeline complete![/green bold]")
            if episode.audio_url:
                console.print(f"  Audio URL: {episode.audio_url}")
            if episode.youtube_url:
                console.print(f"  YouTube:   {episode.youtube_url}")
    except Exception as e:
        console.print(f"\n[red bold]Pipeline failed:[/red bold] {e}")
        console.print("Run with --resume to retry from the failed stage.")
        sys.exit(1)


@cli.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.pass_context
def process(ctx: click.Context, input_file: str) -> None:
    """Process audio (and video if present) only."""
    from podflow.processing.audio import process_audio
    from podflow.processing.video import process_video
    from podflow.utils.paths import (
        episode_id_from_file,
        episode_output_dir,
        output_audio_path,
        output_video_path,
    )

    config = load_config(ctx.obj["config_path"])
    input_path = Path(input_file).resolve()
    base_output = Path(config.output.base_dir)
    episode_id = episode_id_from_file(input_path)
    ep_dir = episode_output_dir(base_output, episode_id)

    # Audio
    audio_out = output_audio_path(ep_dir, episode_id)
    process_audio(input_path, audio_out, config.audio)
    console.print(f"[green]Audio:[/green] {audio_out}")

    # Video (if applicable)
    try:
        import ffmpeg
        from podflow.utils.paths import find_ffprobe
        probe = ffmpeg.probe(str(input_path), cmd=find_ffprobe())
        has_video = any(s["codec_type"] == "video" for s in probe.get("streams", []))
    except Exception:
        has_video = False

    if has_video:
        video_out = output_video_path(ep_dir, episode_id)
        process_video(input_path, video_out, config.video)
        console.print(f"[green]Video:[/green] {video_out}")


@cli.command()
@click.argument("audio_file", type=click.Path(exists=True))
@click.pass_context
def transcribe(ctx: click.Context, audio_file: str) -> None:
    """Transcribe an audio file to timestamped JSON."""
    from podflow.utils.paths import (
        episode_id_from_file,
        episode_output_dir,
        output_transcript_path,
    )

    config = load_config(ctx.obj["config_path"])
    audio_path = Path(audio_file).resolve()

    tc = config.transcription
    if tc.backend == "whisper_local":
        from podflow.transcription.whisper_local import WhisperLocalTranscriber
        transcriber = WhisperLocalTranscriber(tc)
    else:
        from podflow.transcription.whisper_api import WhisperAPITranscriber
        transcriber = WhisperAPITranscriber(tc)

    transcript = transcriber.transcribe(audio_path)

    base_output = Path(config.output.base_dir)
    episode_id = episode_id_from_file(audio_path)
    ep_dir = episode_output_dir(base_output, episode_id)
    out_path = output_transcript_path(ep_dir, episode_id)
    out_path.write_text(transcript.model_dump_json(indent=2), encoding="utf-8")

    console.print(f"[green]Transcript:[/green] {out_path}")
    console.print(f"  Segments: {len(transcript.segments)}")
    console.print(f"  Length:   {len(transcript.full_text)} characters")


@cli.command("generate-metadata")
@click.argument("transcript_file", type=click.Path(exists=True))
@click.pass_context
def generate_metadata(ctx: click.Context, transcript_file: str) -> None:
    """Generate AI metadata from a transcript JSON file."""
    from podflow.metadata.generator import (
        generate_metadata as gen_meta,
        load_transcript,
        save_metadata,
    )

    config = load_config(ctx.obj["config_path"])
    transcript = load_transcript(Path(transcript_file))

    metadata = gen_meta(transcript, config.metadata)

    out_path = Path(transcript_file).with_suffix(".metadata.json")
    save_metadata(metadata, out_path)

    console.print(f"[green]Metadata:[/green] {out_path}")
    console.print(f"  Title:    {metadata.title}")
    console.print(f"  Tags:     {', '.join(metadata.tags)}")
    console.print(f"  Chapters: {len(metadata.chapters)}")


@cli.command("upload-youtube")
@click.argument("video_file", type=click.Path(exists=True))
@click.option("--title", default=None, help="Override video title")
@click.option("--description", default=None, help="Override video description")
@click.option(
    "--privacy",
    type=click.Choice(["public", "unlisted", "private"]),
    default=None,
)
@click.pass_context
def upload_youtube(
    ctx: click.Context,
    video_file: str,
    title: str | None,
    description: str | None,
    privacy: str | None,
) -> None:
    """Upload a video file to YouTube."""
    from podflow.metadata.models import EpisodeMetadata
    from podflow.upload.youtube import upload_to_youtube

    config = load_config(ctx.obj["config_path"])

    metadata = EpisodeMetadata(
        title=title or Path(video_file).stem,
        description=description or "",
    )

    video_id = upload_to_youtube(
        video_path=Path(video_file),
        metadata=metadata,
        config=config.youtube,
        privacy=privacy,
    )
    url = f"https://www.youtube.com/watch?v={video_id}"
    console.print(f"[green]Uploaded:[/green] {url}")


@cli.command("update-feed")
@click.pass_context
def update_feed(ctx: click.Context) -> None:
    """Regenerate the RSS feed from all processed episodes."""
    from podflow.feed.generator import generate_feed_xml, load_episodes_from_dir

    config = load_config(ctx.obj["config_path"])
    base_output = Path(config.output.base_dir)

    episodes = load_episodes_from_dir(base_output)
    if not episodes:
        console.print("[yellow]No episodes found in output directory[/yellow]")
        return

    feed_path = base_output / config.feed.feed_filename
    generate_feed_xml(config.feed, episodes, feed_path)
    console.print(f"[green]Feed updated:[/green] {feed_path} ({len(episodes)} episodes)")


@cli.command("validate-feed")
@click.argument(
    "feed_file",
    type=click.Path(exists=True),
    required=False,
    default=None,
)
@click.pass_context
def validate_feed(ctx: click.Context, feed_file: str | None) -> None:
    """Validate a podcast RSS feed for Apple/Spotify compliance."""
    from podflow.feed.validator import validate_feed as do_validate

    config = load_config(ctx.obj["config_path"])

    if feed_file is None:
        feed_path = Path(config.output.base_dir) / config.feed.feed_filename
    else:
        feed_path = Path(feed_file)

    result = do_validate(feed_path)
    console.print(result.summary())

    if not result.is_valid:
        sys.exit(1)
