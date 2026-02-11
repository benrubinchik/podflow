"""LLM-based metadata generation using Anthropic or OpenAI."""

from __future__ import annotations

import json
from pathlib import Path

from podflow.config import MetadataConfig, get_api_key
from podflow.metadata.models import Chapter, EpisodeMetadata, Transcript
from podflow.metadata.prompts import SYSTEM_PROMPT, build_metadata_prompt
from podflow.utils.logging import get_logger

log = get_logger(__name__)


def generate_metadata(
    transcript: Transcript,
    config: MetadataConfig,
) -> EpisodeMetadata:
    """Generate episode metadata from a transcript using an LLM."""
    transcript_text = transcript.to_timestamped_text()
    if not transcript_text:
        transcript_text = transcript.full_text

    # Truncate very long transcripts to avoid exceeding context limits
    max_chars = 100_000
    if len(transcript_text) > max_chars:
        log.warning("Transcript truncated from %d to %d characters", len(transcript_text), max_chars)
        transcript_text = transcript_text[:max_chars]

    prompt = build_metadata_prompt(
        transcript_text=transcript_text,
        max_tags=config.max_tags,
        generate_chapters=config.generate_chapters,
    )

    log.info("Generating metadata via %s (%s)", config.provider, config.model)

    if config.provider == "anthropic":
        raw = _call_anthropic(prompt, config)
    else:
        raw = _call_openai(prompt, config)

    return _parse_response(raw)


def _call_anthropic(prompt: str, config: MetadataConfig) -> str:
    import anthropic

    api_key = get_api_key("ANTHROPIC_API_KEY")
    client = anthropic.Anthropic(api_key=api_key)

    message = client.messages.create(
        model=config.model,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _call_openai(prompt: str, config: MetadataConfig) -> str:
    import openai

    api_key = get_api_key("OPENAI_API_KEY")
    client = openai.OpenAI(api_key=api_key)

    response = client.chat.completions.create(
        model=config.model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        max_tokens=4096,
        temperature=0.7,
    )
    return response.choices[0].message.content or ""


def _parse_response(raw: str) -> EpisodeMetadata:
    """Parse LLM JSON response into EpisodeMetadata."""
    # Strip markdown code fences if present
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]  # remove opening fence
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)

    data = json.loads(text)

    chapters = []
    for ch in data.get("chapters", []):
        chapters.append(
            Chapter(start_time=float(ch["start_time"]), title=ch["title"])
        )

    return EpisodeMetadata(
        title=data.get("title", "Untitled Episode"),
        description=data.get("description", ""),
        show_notes=data.get("show_notes", ""),
        tags=data.get("tags", []),
        chapters=chapters,
        summary=data.get("summary", ""),
    )


def load_transcript(path: Path) -> Transcript:
    """Load a transcript from a JSON file."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return Transcript(**data)


def save_metadata(metadata: EpisodeMetadata, path: Path) -> None:
    """Save metadata to a JSON file."""
    Path(path).write_text(
        metadata.model_dump_json(indent=2),
        encoding="utf-8",
    )
