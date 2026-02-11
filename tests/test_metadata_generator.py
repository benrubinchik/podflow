"""Tests for metadata generation (with mocked LLM calls)."""

import json

import pytest

from podflow.metadata.generator import _parse_response
from podflow.metadata.models import EpisodeMetadata
from podflow.metadata.prompts import build_metadata_prompt


def test_build_metadata_prompt_with_chapters():
    prompt = build_metadata_prompt("Hello world transcript", max_tags=5, generate_chapters=True)
    assert "Hello world transcript" in prompt
    assert "5" in prompt
    assert "chapter markers" in prompt.lower()


def test_build_metadata_prompt_without_chapters():
    prompt = build_metadata_prompt("Test", generate_chapters=False)
    assert "empty list" in prompt.lower()


def test_parse_response_clean_json():
    raw = json.dumps({
        "title": "Great Episode",
        "description": "A great one.",
        "show_notes": "## Notes\n- Topic A",
        "tags": ["tech", "ai"],
        "chapters": [
            {"start_time": 0.0, "title": "Intro"},
            {"start_time": 120.5, "title": "Main"},
        ],
        "summary": "An episode about things.",
    })
    meta = _parse_response(raw)
    assert isinstance(meta, EpisodeMetadata)
    assert meta.title == "Great Episode"
    assert len(meta.tags) == 2
    assert len(meta.chapters) == 2
    assert meta.chapters[1].start_time == 120.5


def test_parse_response_with_code_fences():
    raw = '```json\n{"title": "Fenced", "description": "", "show_notes": "", "tags": [], "chapters": [], "summary": ""}\n```'
    meta = _parse_response(raw)
    assert meta.title == "Fenced"


def test_parse_response_invalid_json():
    with pytest.raises(json.JSONDecodeError):
        _parse_response("not json at all")
