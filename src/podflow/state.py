"""Per-episode state tracking for resumable pipeline runs."""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class StageStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class StageState(BaseModel):
    status: StageStatus = StageStatus.PENDING
    error: str | None = None
    outputs: dict[str, Any] = Field(default_factory=dict)


PIPELINE_STAGES = [
    "process_audio",
    "process_video",
    "transcribe",
    "generate_metadata",
    "upload_youtube",
    "host_audio",
    "update_feed",
]


class PipelineState(BaseModel):
    episode_id: str = ""
    input_file: str = ""
    stages: dict[str, StageState] = Field(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        for stage in PIPELINE_STAGES:
            if stage not in self.stages:
                self.stages[stage] = StageState()

    def get_stage(self, name: str) -> StageState:
        return self.stages[name]

    def set_running(self, name: str) -> None:
        self.stages[name].status = StageStatus.RUNNING
        self.stages[name].error = None

    def set_completed(self, name: str, outputs: dict[str, Any] | None = None) -> None:
        self.stages[name].status = StageStatus.COMPLETED
        self.stages[name].error = None
        if outputs:
            self.stages[name].outputs = outputs

    def set_failed(self, name: str, error: str) -> None:
        self.stages[name].status = StageStatus.FAILED
        self.stages[name].error = error

    def set_skipped(self, name: str) -> None:
        self.stages[name].status = StageStatus.SKIPPED

    def is_completed(self, name: str) -> bool:
        return self.stages[name].status == StageStatus.COMPLETED

    def first_incomplete_stage(self) -> str | None:
        for stage in PIPELINE_STAGES:
            if self.stages[stage].status not in (
                StageStatus.COMPLETED,
                StageStatus.SKIPPED,
            ):
                return stage
        return None


def state_file_path(output_dir: Path, episode_id: str) -> Path:
    return output_dir / f".podflow_state_{episode_id}.json"


def load_state(output_dir: Path, episode_id: str) -> PipelineState:
    path = state_file_path(output_dir, episode_id)
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        return PipelineState(**data)
    return PipelineState(episode_id=episode_id)


def save_state(state: PipelineState, output_dir: Path) -> None:
    path = state_file_path(output_dir, state.episode_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        state.model_dump_json(indent=2),
        encoding="utf-8",
    )
