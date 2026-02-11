"""OpenAI Whisper API transcription."""

from __future__ import annotations

from pathlib import Path

import openai

from podflow.config import TranscriptionConfig, get_api_key
from podflow.metadata.models import Transcript, TranscriptSegment
from podflow.transcription.base import Transcriber
from podflow.utils.logging import get_logger

log = get_logger(__name__)


class WhisperAPITranscriber(Transcriber):
    """Transcribe using the OpenAI Whisper API."""

    def __init__(self, config: TranscriptionConfig) -> None:
        self.config = config
        self._client: openai.OpenAI | None = None

    @property
    def name(self) -> str:
        return "whisper-api"

    def _get_client(self) -> openai.OpenAI:
        if self._client is None:
            api_key = get_api_key("OPENAI_API_KEY")
            self._client = openai.OpenAI(api_key=api_key)
        return self._client

    def transcribe(self, audio_path: Path) -> Transcript:
        client = self._get_client()
        log.info("Transcribing %s via Whisper API", audio_path.name)

        kwargs: dict = {
            "model": "whisper-1",
            "response_format": "verbose_json",
            "timestamp_granularities": ["segment"],
        }
        if self.config.language:
            kwargs["language"] = self.config.language
        if self.config.prompt:
            kwargs["prompt"] = self.config.prompt

        with open(audio_path, "rb") as f:
            kwargs["file"] = f
            response = client.audio.transcriptions.create(**kwargs)

        segments = []
        for seg in getattr(response, "segments", []) or []:
            segments.append(
                TranscriptSegment(
                    start=seg["start"],
                    end=seg["end"],
                    text=seg["text"].strip(),
                )
            )

        full_text = getattr(response, "text", "") or ""
        language = getattr(response, "language", self.config.language or "en")

        transcript = Transcript(
            segments=segments,
            language=language,
            full_text=full_text.strip(),
        )

        log.info(
            "Transcription complete: %d segments, %d characters",
            len(segments), len(full_text),
        )
        return transcript
