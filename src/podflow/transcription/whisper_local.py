"""Local Whisper model transcription."""

from __future__ import annotations

from pathlib import Path

from podflow.config import TranscriptionConfig
from podflow.metadata.models import Transcript, TranscriptSegment
from podflow.transcription.base import Transcriber
from podflow.utils.logging import get_logger

log = get_logger(__name__)


class WhisperLocalTranscriber(Transcriber):
    """Transcribe using locally-installed openai-whisper."""

    def __init__(self, config: TranscriptionConfig) -> None:
        self.config = config
        self._model = None

    @property
    def name(self) -> str:
        return f"whisper-local ({self.config.model})"

    def _load_model(self):
        if self._model is not None:
            return self._model
        try:
            import whisper
        except ImportError:
            raise ImportError(
                "openai-whisper is not installed. "
                "Install it with: pip install 'podflow[whisper-local]'"
            )
        log.info("Loading Whisper model: %s", self.config.model)
        self._model = whisper.load_model(self.config.model)
        return self._model

    def transcribe(self, audio_path: Path) -> Transcript:
        model = self._load_model()
        log.info("Transcribing %s with local Whisper (%s)", audio_path.name, self.config.model)

        options = {}
        if self.config.language:
            options["language"] = self.config.language
        if self.config.prompt:
            options["initial_prompt"] = self.config.prompt

        result = model.transcribe(str(audio_path), **options)

        segments = []
        for seg in result.get("segments", []):
            segments.append(
                TranscriptSegment(
                    start=seg["start"],
                    end=seg["end"],
                    text=seg["text"].strip(),
                )
            )

        full_text = result.get("text", "").strip()
        language = result.get("language", self.config.language or "en")

        transcript = Transcript(
            segments=segments,
            language=language,
            full_text=full_text,
        )

        log.info(
            "Transcription complete: %d segments, %d characters",
            len(segments), len(full_text),
        )
        return transcript
