"""Plugin helpers — auto-discover skills and create native AgentSkills plugin.

Native Strands v1.53.0 provides:
  - AgentSkills(skills=[paths_or_Skill_instances])
  - Skill(name, description, instructions)

This helper auto-discovers a skills directory and creates the plugin.
"""

from pathlib import Path
from typing import Any

from strands.vended_plugins.skills import AgentSkills, Skill


def skills_from_dir(skills_dir: str) -> AgentSkills:
    """Create an AgentSkills plugin from a directory of SKILL.md files.

    The directory should contain subdirectories, each with a SKILL.md:
        skills/
        ├── youtuber/SKILL.md
        ├── code-reviewer/SKILL.md
        └── auditor/SKILL.md

    Use md_to_skill_dirs() to convert flat .md files to this structure first.

    Args:
        skills_dir: Directory containing skill subdirectories with SKILL.md.
    """
    return AgentSkills(skills=[skills_dir])


def skills_from_md_dir(md_dir: str) -> AgentSkills:
    """Create an AgentSkills plugin from flat .md files (auto-converts).

    Reads each .md file in the directory and creates a Skill instance.
    No need to create SKILL.md directory structure — this does it in-memory.

    Args:
        md_dir: Directory containing flat .md skill files.
    """
    src = Path(md_dir)
    if not src.is_dir():
        return AgentSkills(skills=[])

    skills = []
    for md_file in sorted(src.glob("*.md")):
        content = md_file.read_text(encoding="utf-8").strip()
        # First line or first paragraph as description
        first_line = content.split("\n")[0].lstrip("# ").strip()
        skills.append(Skill(
            name=md_file.stem,
            description=first_line[:200],
            instructions=content,
        ))
    return AgentSkills(skills=skills)
