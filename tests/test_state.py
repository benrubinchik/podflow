"""Tests for pipeline state tracking."""

import tempfile
from pathlib import Path

from podflow.state import (
    PIPELINE_STAGES,
    PipelineState,
    StageStatus,
    load_state,
    save_state,
)


def test_initial_state():
    state = PipelineState(episode_id="test_ep")
    assert state.episode_id == "test_ep"
    for stage in PIPELINE_STAGES:
        assert state.get_stage(stage).status == StageStatus.PENDING


def test_stage_transitions():
    state = PipelineState(episode_id="test")
    state.set_running("process_audio")
    assert state.get_stage("process_audio").status == StageStatus.RUNNING

    state.set_completed("process_audio", {"audio_file": "/out/test.mp3"})
    assert state.is_completed("process_audio")
    assert state.get_stage("process_audio").outputs["audio_file"] == "/out/test.mp3"


def test_set_failed():
    state = PipelineState(episode_id="test")
    state.set_failed("transcribe", "API timeout")
    assert state.get_stage("transcribe").status == StageStatus.FAILED
    assert state.get_stage("transcribe").error == "API timeout"


def test_first_incomplete_stage():
    state = PipelineState(episode_id="test")
    assert state.first_incomplete_stage() == "process_audio"

    state.set_completed("process_audio")
    state.set_completed("process_video")
    assert state.first_incomplete_stage() == "transcribe"


def test_all_complete():
    state = PipelineState(episode_id="test")
    for stage in PIPELINE_STAGES:
        state.set_completed(stage)
    assert state.first_incomplete_stage() is None


def test_save_and_load_state():
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        state = PipelineState(episode_id="ep123")
        state.input_file = "/input/test.wav"
        state.set_completed("process_audio", {"audio_file": "/out/ep.mp3"})
        state.set_failed("transcribe", "timeout")

        save_state(state, output_dir)

        loaded = load_state(output_dir, "ep123")
        assert loaded.episode_id == "ep123"
        assert loaded.input_file == "/input/test.wav"
        assert loaded.is_completed("process_audio")
        assert loaded.get_stage("transcribe").status == StageStatus.FAILED
        assert loaded.get_stage("transcribe").error == "timeout"
