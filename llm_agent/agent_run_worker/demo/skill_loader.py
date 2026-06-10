from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
from typing import Protocol


@dataclass(frozen=True)
class DemoSkill:
    name: str
    description: str
    content: str


class DemoSkillLoader(Protocol):
    def load_skills(self) -> list[DemoSkill]: ...


class PackageDemoSkillLoader(DemoSkillLoader):
    _SKILL_PACKAGES = (
        "agent_run_worker.demo.skills.reservation_demo_workflow",
        "agent_run_worker.demo.skills.observability_demo",
    )

    def load_skills(self) -> list[DemoSkill]:
        skills: list[DemoSkill] = []

        for skill_package in self._SKILL_PACKAGES:
            content = resources.files(skill_package).joinpath("SKILL.md").read_text(encoding="utf-8")
            skills.append(parse_skill_markdown(content))

        return skills


class DemoSkillFormatError(ValueError):
    pass


def parse_skill_markdown(content: str) -> DemoSkill:
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        raise DemoSkillFormatError("Skill file must start with YAML frontmatter")

    try:
        closing_index = next(index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---")
    except StopIteration as exc:
        raise DemoSkillFormatError("Skill file frontmatter is not closed") from exc

    metadata = _parse_frontmatter(lines[1:closing_index])
    body = "\n".join(lines[closing_index + 1 :]).strip()
    if not body:
        raise DemoSkillFormatError("Skill file body must not be empty")

    name = metadata.get("name")
    description = metadata.get("description")
    if not name or not description:
        raise DemoSkillFormatError("Skill frontmatter requires name and description")

    unexpected_fields = set(metadata) - {"name", "description"}
    if unexpected_fields:
        fields = ", ".join(sorted(unexpected_fields))
        raise DemoSkillFormatError(f"Skill frontmatter has unsupported fields: {fields}")

    return DemoSkill(name=name, description=description, content=body)


def _parse_frontmatter(lines: list[str]) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        key, separator, value = stripped.partition(":")
        if separator != ":" or not key.strip() or not value.strip():
            raise DemoSkillFormatError(f"Unsupported skill frontmatter line: {line}")
        metadata[key.strip()] = value.strip().strip('"').strip("'")
    return metadata
