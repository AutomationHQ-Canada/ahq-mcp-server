"""
Serves the plugin's skills as MCP prompts, so hosted/remote clients (which can't install the
Claude Code plugin) still get the curated workflows over the wire. Clients surface these as
slash-command-like entries (VS Code: /mcp.ahq.<name>, Claude Desktop: the "+" menu).
"""

from mcp.types import GetPromptResult, Prompt, PromptMessage, TextContent

from src.config.ahq_services import REPO_ROOT

# extract_requirements reads a file off the SERVER's disk, which is meaningless/blocked when
# hosted — the one skill whose workflow needs a hosted adaptation note.
_HOSTED_NOTE = {
    "ahq-gen-from-requirements": (
        "\n\n> Note (hosted server): the `extract_requirements` tool is unavailable here — "
        "it reads local files. Ask the user to paste the requirements text directly instead."
    ),
}


def parse_skill_md(text: str) -> tuple[dict, str]:
    """
    Splits a SKILL.md into (frontmatter meta, markdown body). The frontmatter is strictly
    `key: value` scalars plus an indented `tools:` list (verified across all 7 skills) — a
    15-line hand parser beats adding a pyyaml dependency for this. Indented lines (list items)
    and unknown shapes are simply skipped.
    """
    meta: dict[str, str] = {}
    if not text.startswith("---"):
        return meta, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return meta, text
    for line in parts[1].splitlines():
        if not line or line.startswith((" ", "\t", "-")):
            continue
        key, sep, value = line.partition(":")
        if sep and value.strip():
            meta[key.strip()] = value.strip()
    return meta, parts[2].strip()


def load_skill_prompts() -> dict[str, dict]:
    """name -> {"description": ..., "body": ...}; empty if skills/ is absent (pip-install edge)."""
    prompts: dict[str, dict] = {}
    skills_dir = REPO_ROOT / "skills"
    if not skills_dir.is_dir():
        return prompts
    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        try:
            meta, body = parse_skill_md(skill_md.read_text(encoding="utf-8"))
        except OSError:
            continue
        name = meta.get("name") or skill_md.parent.name
        prompts[name] = {"description": meta.get("description", ""), "body": body}
    return prompts


SKILL_PROMPTS = load_skill_prompts()


def list_skill_prompts() -> list[Prompt]:
    return [
        Prompt(name=name, description=entry["description"], arguments=[])
        for name, entry in SKILL_PROMPTS.items()
    ]


def get_skill_prompt(name: str, hosted: bool = False) -> GetPromptResult:
    entry = SKILL_PROMPTS.get(name)
    if entry is None:
        raise ValueError(f"Unknown prompt: {name}")
    body = entry["body"]
    if hosted and name in _HOSTED_NOTE:
        body += _HOSTED_NOTE[name]
    return GetPromptResult(
        description=entry["description"],
        messages=[PromptMessage(role="user", content=TextContent(type="text", text=body))],
    )
