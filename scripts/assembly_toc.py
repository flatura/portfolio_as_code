"""Generate the Contents section for assembled project pages.

Simulates the assembled page: page Contents h2, then each included file with
heading-offset=1, using Python-Markdown slug rules (including global _N
fallbacks for non-ASCII headings).

Usage:
  python scripts/assembly_toc.py docs/en/projects/ai_oip
  python scripts/assembly_toc.py docs/ru/projects/ai_oip
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from markdown.extensions.toc import slugify

SUMMARY = "summary.md"

COMPACT_MODULES = [
    "01-overview.md",
    "02-context-and-problem.md",
    "03-goals-requirements-and-constraints.md",
    "04-role-and-responsibilities.md",
    "05-system-model.md",
    "06-architecture-and-integrations.md",
    "07-security-quality-and-operations.md",
    "08-decisions-trade-offs-and-risks.md",
    "09-roadmap-and-demonstration.md",
]

ALL_IN_ONE_MODULES = [SUMMARY, *COMPACT_MODULES]

INCLUDE_LEAF_FILES = frozenset(ALL_IN_ONE_MODULES)
ASSEMBLY_FILES = frozenset(
    {
        "index.md",
        "all-in-one.md",
        "architecture-review.md",
        "srs-pack.md",
        "demo-pack.md",
    }
)


def assert_include_leaves(modules: list[str], context: str) -> None:
    bad = [m for m in modules if m not in INCLUDE_LEAF_FILES]
    if bad:
        raise ValueError(f"{context}: non-leaf include targets: {bad}")

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
ADR_LABEL = "Architecture Decision Records"
ADR_ANCHOR = "architecture-decision-records"
HEADING_OFFSET = 1


def parse_headings(text: str) -> list[tuple[int, str]]:
    headings: list[tuple[int, str]] = []
    for line in text.splitlines():
        match = HEADING_RE.match(line)
        if match:
            level = len(match.group(1))
            title = match.group(2).strip()
            headings.append((level, title))
    return headings


class AnchorRegistry:
    def __init__(self) -> None:
        self._counts: dict[str, int] = {}
        self._numeric = 0

    def assign(self, title: str) -> str:
        base = slugify(title, "-")
        if not base:
            self._numeric += 1
            anchor = f"_{self._numeric}"
            self._counts[anchor] = 1
            return anchor
        if base not in self._counts:
            self._counts[base] = 0
        self._counts[base] += 1
        if self._counts[base] == 1:
            return base
        return f"{base}_{self._counts[base] - 1}"


def module_entry_anchors(project_dir: Path, modules: list[str], lang: str) -> list[tuple[str, str]]:
    registry = AnchorRegistry()
    entries: list[tuple[str, str]] = []

    registry.assign("Contents" if lang == "en" else "Содержание")

    for name in modules:
        path = project_dir / name
        if not path.is_file():
            raise FileNotFoundError(f"Missing module for TOC: {path}")
        headings = parse_headings(path.read_text(encoding="utf-8"))
        if not headings:
            raise ValueError(f"No headings in {name}")
        module_title = headings[0][1]
        module_anchor: str | None = None

        for level, title in headings:
            adjusted = level + HEADING_OFFSET
            anchor = registry.assign(title)
            if adjusted == 2 and title == module_title and module_anchor is None:
                module_anchor = anchor

        if module_anchor is None:
            raise ValueError(f"Could not resolve module anchor for {name}")
        entries.append((module_title, module_anchor))

    return entries


def contents_section(
    lang: str,
    project_dir: Path,
    modules: list[str] | None = None,
    *,
    include_adr: bool = False,
) -> str:
    if modules is None:
        modules = ALL_IN_ONE_MODULES
    heading = "## Contents" if lang == "en" else "## Содержание"
    lines = [heading, ""]
    for title, anchor in module_entry_anchors(project_dir, modules, lang):
        lines.append(f"- [{title}](#{anchor})")
    if include_adr:
        lines.append(f"- [{ADR_LABEL}](#{ADR_ANCHOR})")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    project_dir = Path(sys.argv[1])
    lang = "ru" if "ru" in project_dir.parts else "en"
    print(contents_section(lang, project_dir, include_adr=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
