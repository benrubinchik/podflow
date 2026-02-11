"""Abstract transcriber interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from podflow.metadata.models import Transcript


class Transcriber(ABC):
    """Base class for all transcription backends."""

    @abstractmethod
    def transcribe(self, audio_path: Path) -> Transcript:
        """Transcribe an audio file and return a Transcript."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name for this backend."""
        ...
