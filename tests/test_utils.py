"""Tests for utility modules."""

from pathlib import Path

from podflow.utils.paths import episode_id_from_file, sanitize_filename
from podflow.utils.time_format import (
    format_duration_human,
    hms_to_seconds,
    seconds_to_hms,
    seconds_to_ms,
)


class TestTimeFormat:
    def test_seconds_to_hms(self):
        assert seconds_to_hms(0) == "00:00:00"
        assert seconds_to_hms(65) == "00:01:05"
        assert seconds_to_hms(3661) == "01:01:01"

    def test_seconds_to_ms(self):
        assert seconds_to_ms(0) == "00:00"
        assert seconds_to_ms(65) == "01:05"
        assert seconds_to_ms(600) == "10:00"

    def test_hms_to_seconds(self):
        assert hms_to_seconds("01:01:01") == 3661.0
        assert hms_to_seconds("01:05") == 65.0
        assert hms_to_seconds("30") == 30.0

    def test_format_duration_human(self):
        assert format_duration_human(30) == "30s"
        assert format_duration_human(90) == "1m 30s"
        assert format_duration_human(3720) == "1h 2m"


class TestPaths:
    def test_sanitize_filename(self):
        assert sanitize_filename("hello world") == "hello_world"
        assert sanitize_filename('a<b>c:d"e') == "a_b_c_d_e"
        assert sanitize_filename("...leading") == "leading"

    def test_episode_id_from_file(self):
        eid = episode_id_from_file(Path("recording_2024.wav"))
        assert "recording_2024" in eid
        # Stable: same input gives same output
        eid2 = episode_id_from_file(Path("recording_2024.wav"))
        assert eid == eid2

    def test_episode_id_different_files(self):
        eid1 = episode_id_from_file(Path("/a/recording.wav"))
        eid2 = episode_id_from_file(Path("/b/recording.wav"))
        assert eid1 != eid2
