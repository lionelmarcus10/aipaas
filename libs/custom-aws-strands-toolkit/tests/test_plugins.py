"""Test plugins helpers."""

import tempfile
from pathlib import Path

from cast.plugins import skills_from_md_dir
from strands.vended_plugins.skills import AgentSkills


def test_skills_from_md_dir():
    with tempfile.TemporaryDirectory() as d:
        Path(d, "youtuber.md").write_text("# YouTuber\nYou are a YouTuber expert.")
        Path(d, "coder.md").write_text("# Coder\nYou are a coding expert.")
        plugin = skills_from_md_dir(d)
        assert isinstance(plugin, AgentSkills)


def test_skills_from_md_dir_empty():
    plugin = skills_from_md_dir("/nonexistent")
    assert isinstance(plugin, AgentSkills)
