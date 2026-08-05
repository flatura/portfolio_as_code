"""Portfolio tooling: regenerate assemblies, scaffold projects, personalize demo.

Subcommands:
  assemblies [--check]   Regenerate all-in-one / packs / index link blocks
  new-project <slug>     Copy project-docs templates and run assemblies
  init                   Replace demo name, site_url, and repo_url
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from assembly_toc import SUMMARY, ALL_IN_ONE_MODULES, assert_include_leaves, contents_section

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
LOCALES = ("en", "ru")

TEMPLATE_CANDIDATES = (
    ROOT / "templates" / "project-docs",
    ROOT / "architecture-docs-template",
)

DEMO_NAME_EN = "John Smith"
DEMO_NAME_RU = "Василий Иванов"
DEMO_SITE_URL = "https://example-user.github.io/portfolio-as-code/"
DEMO_REPO_URL = "https://github.com/example-user/portfolio-as-code"

INCLUDES_ALL_IN_ONE = "\n".join(
    f'{{% include-markdown "./{name}" heading-offset=1 %}}' for name in ALL_IN_ONE_MODULES
)

EN_ALL_IN_ONE_INTRO = (
    "This page is assembled from compact project documentation sections. "
    "Individual section files remain the source of truth; this page is for sequential reading, "
    "review, and PDF-style export."
)
RU_ALL_IN_ONE_INTRO = (
    "Эта страница собирается из компактных разделов проектной документации. "
    "Отдельные файлы разделов остаются источником истины; эта страница предназначена "
    "для последовательного чтения, ревью и экспорта в стиле PDF."
)

PACKS = {
    "architecture-review": {
        "modules": [
            SUMMARY,
            "03-goals-requirements-and-constraints.md",
            "05-system-model.md",
            "06-architecture-and-integrations.md",
            "07-security-quality-and-operations.md",
            "08-decisions-trade-offs-and-risks.md",
        ],
        "en": {
            "suffix": "architecture review",
            "intro": (
                "This page assembles sections relevant to architecture review: "
                "goals, requirements, and constraints; system model; architecture and integrations; "
                "security, quality, and operations; and decisions, trade-offs, and risks."
            ),
            "index_desc": "goals through decisions for architecture review sessions",
        },
        "ru": {
            "suffix": "архитектурное ревью",
            "intro": (
                "Эта страница собирает разделы для архитектурного ревью: "
                "цели, требования и ограничения; модель системы; архитектура и интеграции; "
                "безопасность, качество и эксплуатация; решения, компромиссы и риски."
            ),
            "index_desc": "от целей до решений для сессий архитектурного ревью",
        },
    },
    "srs-pack": {
        "modules": [
            SUMMARY,
            "02-context-and-problem.md",
            "03-goals-requirements-and-constraints.md",
            "04-role-and-responsibilities.md",
            "05-system-model.md",
            "06-architecture-and-integrations.md",
            "07-security-quality-and-operations.md",
        ],
        "en": {
            "suffix": "SRS pack",
            "intro": (
                "This page assembles sections relevant to a software requirements specification: "
                "context and problem through security, quality, and operations."
            ),
            "index_desc": "context through operations for SRS-style review",
        },
        "ru": {
            "suffix": "SRS-сборка",
            "intro": (
                "Эта страница собирает разделы для спецификации требований к ПО: "
                "от контекста и проблемы до безопасности, качества и эксплуатации."
            ),
            "index_desc": "от контекста до эксплуатации для ревью в формате SRS",
        },
    },
    "demo-pack": {
        "modules": [
            SUMMARY,
            "01-overview.md",
            "04-role-and-responsibilities.md",
            "06-architecture-and-integrations.md",
            "08-decisions-trade-offs-and-risks.md",
            "09-roadmap-and-demonstration.md",
        ],
        "en": {
            "suffix": "demo pack",
            "intro": (
                "This page assembles sections relevant to demos and stakeholder presentations: "
                "overview, role, architecture, decisions, roadmap, and demonstration."
            ),
            "index_desc": "overview, role, architecture, decisions, roadmap, and demonstration",
        },
        "ru": {
            "suffix": "демо-сборка",
            "intro": (
                "Эта страница собирает разделы для демо: "
                "обзор, роль, архитектура, решения, дорожная карта и демонстрация."
            ),
            "index_desc": "обзор, роль, архитектура, решения, дорожная карта и демонстрация",
        },
    },
}

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def discover_projects() -> list[Path]:
    """Return project dirs that have docs/<locale>/projects/<slug>/summary.md."""
    found: list[Path] = []
    for lang in LOCALES:
        projects_root = DOCS / lang / "projects"
        if not projects_root.is_dir():
            continue
        for summary in sorted(projects_root.glob("*/summary.md")):
            found.append(summary.parent)
    return found


def project_title(project_dir: Path) -> str:
    index = (project_dir / "index.md").read_text(encoding="utf-8")
    match = re.search(r"^#\s+(.+?)\s*$", index, re.MULTILINE)
    if not match:
        raise ValueError(f"No H1 in {project_dir / 'index.md'}")
    return match.group(1).strip()


def lang_of(project_dir: Path) -> str:
    return "ru" if "ru" in project_dir.parts else "en"


def render_all_in_one(project_dir: Path) -> str:
    assert_include_leaves(ALL_IN_ONE_MODULES, str(project_dir / "all-in-one.md"))
    lang = lang_of(project_dir)
    title = project_title(project_dir)
    suffix = "всё вместе" if lang == "ru" else "all-in-one"
    intro = RU_ALL_IN_ONE_INTRO if lang == "ru" else EN_ALL_IN_ONE_INTRO
    toc = contents_section(lang, project_dir, include_adr=True)
    adr_footer = (
        "## Architecture Decision Records\n\n"
        + ("См. " if lang == "ru" else "See ")
        + "[Architecture Decision Records](adr/index.md).\n"
    )
    return (
        f"# {title} — {suffix}\n\n"
        f"{intro}\n\n"
        f"{toc}\n"
        f"{INCLUDES_ALL_IN_ONE}\n\n"
        f"{adr_footer}"
    )


def pack_body(modules: list[str]) -> str:
    lines = [f'{{% include-markdown "./{name}" heading-offset=1 %}}' for name in modules]
    lines.append("")
    return "\n".join(lines)


def render_pack(project_dir: Path, lang: str, pack_name: str, meta: dict) -> str:
    assert_include_leaves(meta["modules"], f"{project_dir}/{pack_name}.md")
    pack_meta = meta[lang]
    title = project_title(project_dir)
    return "\n".join(
        [
            f"# {title} — {pack_meta['suffix']}",
            "",
            pack_meta["intro"],
            "",
            contents_section(lang, project_dir, meta["modules"]),
            pack_body(meta["modules"]),
        ]
    )


def render_index(project_dir: Path, lang: str) -> str:
    index_path = project_dir / "index.md"
    text = index_path.read_text(encoding="utf-8")
    section = "## Document assemblies" if lang == "en" else "## Документные сборки"
    if section not in text:
        raise ValueError(f"Missing section in {index_path}")

    if lang == "en":
        pack_lines = [
            "- [All-in-one](all-in-one.md) - all sections assembled for sequential reading and export",
            f"- [Architecture review](architecture-review.md) - {PACKS['architecture-review']['en']['index_desc']}",
            f"- [SRS pack](srs-pack.md) - {PACKS['srs-pack']['en']['index_desc']}",
            f"- [Demo pack](demo-pack.md) - {PACKS['demo-pack']['en']['index_desc']}",
        ]
    else:
        pack_lines = [
            "- [Всё вместе](all-in-one.md) - все разделы собраны для последовательного чтения и экспорта",
            f"- [Архитектурное ревью](architecture-review.md) - {PACKS['architecture-review']['ru']['index_desc']}",
            f"- [SRS-сборка](srs-pack.md) - {PACKS['srs-pack']['ru']['index_desc']}",
            f"- [Демо-сборка](demo-pack.md) - {PACKS['demo-pack']['ru']['index_desc']}",
        ]

    block = section + "\n\n" + "\n".join(pack_lines) + "\n"
    updated, n = re.subn(
        rf"{re.escape(section)}\n\n(?:- .+\n)+",
        block,
        text,
        count=1,
    )
    if n != 1:
        raise ValueError(f"Could not update assemblies block in {index_path}")
    return updated


def planned_outputs(project_dir: Path) -> dict[Path, str]:
    lang = lang_of(project_dir)
    outputs: dict[Path, str] = {
        project_dir / "all-in-one.md": render_all_in_one(project_dir),
        project_dir / "index.md": render_index(project_dir, lang),
    }
    for pack_name, meta in PACKS.items():
        outputs[project_dir / f"{pack_name}.md"] = render_pack(
            project_dir, lang, pack_name, meta
        )
    return outputs


def write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8", newline="\n")


def cmd_assemblies(check: bool) -> int:
    projects = discover_projects()
    if not projects:
        print("No projects discovered (expected docs/<locale>/projects/*/summary.md)", file=sys.stderr)
        return 1

    drift = False
    for project_dir in projects:
        rel = project_dir.relative_to(ROOT)
        for path, content in planned_outputs(project_dir).items():
            if check:
                if not path.is_file():
                    print(f"MISSING {path.relative_to(ROOT)}", file=sys.stderr)
                    drift = True
                    continue
                existing = path.read_text(encoding="utf-8")
                if existing.replace("\r\n", "\n") != content:
                    print(f"DRIFT {path.relative_to(ROOT)}", file=sys.stderr)
                    drift = True
            else:
                write_text(path, content)
        print(f"{'check' if check else 'ok'} {rel.as_posix()}")

    if check and drift:
        print("Assembly drift detected. Run: python scripts/portfolio.py assemblies", file=sys.stderr)
        return 1
    return 0


def resolve_templates() -> Path:
    for candidate in TEMPLATE_CANDIDATES:
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError(
        "No project template found. Expected templates/project-docs or architecture-docs-template."
    )


def cmd_new_project(slug: str) -> int:
    if not SLUG_RE.fullmatch(slug):
        print(
            f"Invalid slug {slug!r}: use lowercase letters, digits, and hyphens "
            "(e.g. orchid-cloud).",
            file=sys.stderr,
        )
        return 2

    templates = resolve_templates()
    targets: list[Path] = []
    for lang in LOCALES:
        src = templates / lang
        if not src.is_dir():
            print(f"Missing template locale: {src}", file=sys.stderr)
            return 1
        dest = DOCS / lang / "projects" / slug
        if dest.exists():
            print(f"Already exists: {dest.relative_to(ROOT)}", file=sys.stderr)
            return 1
        targets.append(dest)

    for lang, dest in zip(LOCALES, targets, strict=True):
        shutil.copytree(templates / lang, dest)
        print(f"Created {dest.relative_to(ROOT).as_posix()}")

    return cmd_assemblies(check=False)


def _prompt(label: str, default: str) -> str:
    raw = input(f"{label} [{default}]: ").strip()
    return raw or default


def _replace_all(text: str, old: str, new: str) -> tuple[str, int]:
    if not old or old == new:
        return text, 0
    count = text.count(old)
    return text.replace(old, new), count


def cmd_init(name: str | None, name_ru: str | None, site_url: str | None, repo_url: str | None) -> int:
    if name is None:
        name = _prompt("Display name (EN)", DEMO_NAME_EN)
    if name_ru is None:
        name_ru = _prompt("Display name (RU)", name if name != DEMO_NAME_EN else DEMO_NAME_RU)
    if site_url is None:
        site_url = _prompt("site_url", DEMO_SITE_URL)
    if repo_url is None:
        repo_url = _prompt("repo_url", DEMO_REPO_URL)

    if not site_url.endswith("/"):
        site_url += "/"

    replacements_by_file: dict[Path, list[tuple[str, str]]] = {
        ROOT / "mkdocs.yml": [
            (DEMO_NAME_EN, name),
            (DEMO_NAME_RU, name_ru),
            (DEMO_SITE_URL, site_url),
            (DEMO_REPO_URL, repo_url),
        ],
        DOCS / "en" / "index.md": [
            (DEMO_NAME_EN, name),
        ],
        DOCS / "ru" / "index.md": [
            (DEMO_NAME_RU, name_ru),
            (DEMO_NAME_EN, name),
        ],
    }

    total = 0
    for path, pairs in replacements_by_file.items():
        if not path.is_file():
            print(f"skip missing {path.relative_to(ROOT)}", file=sys.stderr)
            continue
        text = path.read_text(encoding="utf-8")
        file_hits = 0
        for old, new in pairs:
            text, n = _replace_all(text, old, new)
            file_hits += n
        if file_hits:
            write_text(path, text)
            print(f"updated {path.relative_to(ROOT).as_posix()} ({file_hits} replacements)")
        else:
            print(f"unchanged {path.relative_to(ROOT).as_posix()} (demo strings not found)")
        total += file_hits

    if total == 0:
        print(
            "No demo placeholders were replaced. Ensure mkdocs.yml / index.md still use "
            f"{DEMO_NAME_EN!r}, {DEMO_SITE_URL!r}, and {DEMO_REPO_URL!r}.",
            file=sys.stderr,
        )
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Portfolio-as-code maintenance CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    assemblies = sub.add_parser("assemblies", help="Regenerate assembled project pages")
    assemblies.add_argument(
        "--check",
        action="store_true",
        help="Fail if committed assemblies differ from regenerated output",
    )

    new_project = sub.add_parser("new-project", help="Scaffold a project from templates")
    new_project.add_argument("slug", help="Project directory slug (e.g. orchid-cloud)")

    init = sub.add_parser("init", help="Personalize demo name, site_url, and repo_url")
    init.add_argument("--name", help="Display name (EN)")
    init.add_argument("--name-ru", help="Display name (RU)")
    init.add_argument("--site-url", help="MkDocs site_url")
    init.add_argument("--repo-url", help="MkDocs repo_url")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "assemblies":
        return cmd_assemblies(check=args.check)
    if args.command == "new-project":
        return cmd_new_project(args.slug)
    if args.command == "init":
        return cmd_init(args.name, args.name_ru, args.site_url, args.repo_url)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
