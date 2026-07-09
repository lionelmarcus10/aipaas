"""Test skills module — md_to_skill_dirs and PromptLoader."""

import tempfile
from pathlib import Path

from cast.skills import PromptLoader, md_to_skill_dirs


def test_md_to_skill_dirs():
    with tempfile.TemporaryDirectory() as src:
        Path(src, "youtuber.md").write_text("You are a YouTuber.")
        Path(src, "coder.md").write_text("You are a coder.")
        with tempfile.TemporaryDirectory() as out:
            created = md_to_skill_dirs(src, out)
            assert len(created) == 2
            assert Path(created[0], "SKILL.md").exists()
            assert Path(created[1], "SKILL.md").exists()


def test_md_to_skill_dirs_empty():
    with tempfile.TemporaryDirectory() as src:
        with tempfile.TemporaryDirectory() as out:
            created = md_to_skill_dirs(src, out)
            assert created == []


def test_md_to_skill_dirs_nonexistent():
    created = md_to_skill_dirs("/nonexistent", "/tmp")
    assert created == []


def test_prompt_loader_list():
    with tempfile.TemporaryDirectory() as d:
        Path(d, "assistant.md").write_text("You are helpful.")
        Path(d, "auditor.md").write_text("You audit invoices.")
        loader = PromptLoader(d)
        assert sorted(loader.list_prompts()) == ["assistant", "auditor"]


def test_prompt_loader_get():
    with tempfile.TemporaryDirectory() as d:
        Path(d, "assistant.md").write_text("You are helpful.")
        loader = PromptLoader(d)
        assert loader.get_prompt("assistant") == "You are helpful."


def test_prompt_loader_not_found():
    with tempfile.TemporaryDirectory() as d:
        loader = PromptLoader(d)
        try:
            loader.get_prompt("nonexistent")
            assert False
        except FileNotFoundError:
            pass


def test_prompt_loader_to_dict():
    with tempfile.TemporaryDirectory() as d:
        Path(d, "assistant.md").write_text("You are helpful.")
        loader = PromptLoader(d)
        result = loader.to_dict()
        assert "assistant" in result
