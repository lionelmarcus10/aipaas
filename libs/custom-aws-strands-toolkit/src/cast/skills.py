"""Prompt loader and skill converter.

Skills: use native Strands AgentSkills plugin (reads SKILL.md from dirs).
  This module provides a converter: flat .md files → SKILL.md directory structure.

Prompts: no native equivalent. PromptLoader loads .md files by name.
"""

from pathlib import Path


def _read_md(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def md_to_skill_dirs(md_dir: str, output_dir: str) -> list[str]:
    """Convert flat .md files to SKILL.md directory structure for native AgentSkills.

    youtuber.md → output_dir/youtuber/SKILL.md
    code-reviewer.md → output_dir/code-reviewer/SKILL.md

    After conversion, use with native Strands:
        from strands.vended_plugins.skills import AgentSkills
        plugin = AgentSkills(skills=[output_dir])
        agent = Agent(plugins=[plugin])

    Args:
        md_dir: Directory containing flat .md skill files.
        output_dir: Where to create skill subdirectories with SKILL.md.

    Returns:
        List of created skill directory paths.
    """
    src = Path(md_dir)
    out = Path(output_dir)
    if not src.is_dir():
        return []

    created = []
    for md_file in sorted(src.glob("*.md")):
        skill_dir = out / md_file.stem
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(_read_md(md_file), encoding="utf-8")
        created.append(str(skill_dir))
    return created


class PromptLoader:
    """Load system prompts from markdown files.

    Each .md file becomes a named prompt.
    (e.g. prompts/auditor.md → prompt "auditor")

    No native Strands equivalent — this fills a genuine gap.

    Args:
        prompts_dir: Directory containing prompt .md files.
    """

    def __init__(self, prompts_dir: str) -> None:
        self.prompts_dir = Path(prompts_dir)

    def list_prompts(self) -> list[str]:
        if not self.prompts_dir.is_dir():
            return []
        return sorted(p.stem for p in self.prompts_dir.glob("*.md"))

    def get_prompt(self, name: str) -> str:
        """Get a system prompt by name."""
        path = self.prompts_dir / f"{name}.md"
        if not path.exists():
            raise FileNotFoundError(f"Prompt not found: {name} (looked for {path})")
        return _read_md(path)

    def to_dict(self) -> dict[str, str]:
        """Return {prompt_name: prompt_text} for all prompts."""
        return {name: self.get_prompt(name) for name in self.list_prompts()}
