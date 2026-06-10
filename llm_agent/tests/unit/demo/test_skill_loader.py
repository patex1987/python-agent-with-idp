import pytest

from agent_run_worker.demo.skill_loader import DemoSkillFormatError, PackageDemoSkillLoader, parse_skill_markdown


def test_loads_packaged_demo_skills():
    skills = PackageDemoSkillLoader().load_skills()

    skill_names = {skill.name for skill in skills}

    assert skill_names == {"reservation-demo-workflow", "observability-demo"}
    assert all(skill.description.strip() for skill in skills)
    assert all(skill.content.strip() for skill in skills)
    assert all(not skill.content.startswith("---") for skill in skills)


def test_parse_skill_markdown_requires_frontmatter():
    with pytest.raises(DemoSkillFormatError):
        parse_skill_markdown("# Missing frontmatter")


def test_parse_skill_markdown_extracts_metadata_and_body():
    skill = parse_skill_markdown(
        """---
name: demo-skill
description: Demo skill description.
---

# Demo Skill

Use the demo skill.
"""
    )

    assert skill.name == "demo-skill"
    assert skill.description == "Demo skill description."
    assert skill.content == "# Demo Skill\n\nUse the demo skill."
