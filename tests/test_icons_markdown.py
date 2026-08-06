"""Markdown reference and THIRD_PARTY_NOTICES generation tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from icons import (  # noqa: E402
    COLLECTIONS,
    ICONS_DIR_REL,
    ICONS_README_REL,
    MARKDOWN_MAX_BYTES,
    MD_TARGET_RE,
    NOTICES_REL,
    REGENERATE_CMD,
    CollectionSpec,
    IconValidationError,
    build_manifest,
    build_markdown_outputs,
    render_collection_hub,
    render_collection_index,
    render_group_index,
    render_icon_entry_line,
    render_icons_readme,
    render_third_party_notices,
    sheet_href,
)

GOLDEN = Path(__file__).resolve().parent / "golden"


def _write_pack(
    path: Path,
    *,
    prefix: str,
    icons: dict,
    width: int | None = 48,
    height: int | None = 48,
    aliases: dict | None = None,
    categories: dict | None = None,
    info: dict | None = None,
    last_modified: int = 1700000000,
) -> None:
    data: dict = {
        "prefix": prefix,
        "info": info
        or {
            "name": prefix.upper(),
            "author": {"name": "Test", "url": "https://example.com"},
            "license": {
                "title": "CC0",
                "spdx": "CC0-1.0",
                "url": "https://example.com/license",
            },
        },
        "lastModified": last_modified,
        "icons": icons,
    }
    if width is not None:
        data["width"] = width
    if height is not None:
        data["height"] = height
    if aliases is not None:
        data["aliases"] = aliases
    if categories is not None:
        data["categories"] = categories
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8", newline="\n")


def _fixture_root(tmp_path: Path) -> tuple[Path, tuple[CollectionSpec, ...]]:
    pack = tmp_path / "docs" / "assets" / "mermaid-icons" / "demo.json"
    _write_pack(
        pack,
        prefix="demo",
        width=48,
        height=48,
        icons={
            "alpha": {"body": '<path d="M0 0h1v1H0z"/>', "width": 16, "height": 16},
            "bravo": {"body": '<path d="M0 0h1v1H0z"/>'},
            "hidden-one": {
                "body": '<path d="M0 0h1v1H0z"/>',
                "hidden": True,
            },
            "weird-&-key": {"body": '<path d="M0 0h1v1H0z"/>'},
            "parent-icon": {
                "body": '<path d="M0 0h1v1H0z"/>',
                "width": 16,
                "height": 16,
            },
            "zeta": {"body": '<path d="M0 0h1v1H0z"/>'},
        },
        aliases={"alias-of-parent": {"parent": "parent-icon"}},
        categories={
            "First Group": ["bravo", "alpha"],
            "Second Group": ["weird-&-key", "parent-icon"],
        },
        info={
            "name": "Demo Pack",
            "version": "1.0",
            "author": {"name": "Fixture Author", "url": "https://example.com/author"},
            "license": {
                "title": "CC0",
                "spdx": "CC0-1.0",
                "url": "https://example.com/license",
            },
        },
    )
    sources = tmp_path / "docs" / "assets" / "mermaid-icons" / "sources.json"
    sources.write_text(
        json.dumps(
            {
                "demo": {
                    "obtained_from": "TODO-MAINTAINER",
                    "retrieved": "2024-01-01",
                    "notes": None,
                }
            }
        ),
        encoding="utf-8",
        newline="\n",
    )
    specs = (CollectionSpec("demo", "docs/assets/mermaid-icons/demo.json"),)
    return tmp_path, specs


def _grouped_fixture_root(
    tmp_path: Path,
) -> tuple[Path, tuple[CollectionSpec, ...]]:
    pack = tmp_path / "docs" / "assets" / "mermaid-icons" / "demo.json"
    _write_pack(
        pack,
        prefix="demo",
        icons={
            "alpha": {"body": '<path d="M0 0h1v1H0z"/>'},
            "azure": {"body": '<path d="M0 0h1v1H0z"/>'},
            "beta": {"body": '<path d="M0 0h1v1H0z"/>'},
            "100tb": {"body": '<path d="M0 0h1v1H0z"/>'},
        },
        info={
            "name": "Demo Pack",
            "author": {"name": "Fixture Author", "url": "https://example.com/author"},
            "license": {
                "title": "CC0",
                "spdx": "CC0-1.0",
                "url": "https://example.com/license",
            },
        },
    )
    sources = tmp_path / "docs" / "assets" / "mermaid-icons" / "sources.json"
    sources.write_text("{}", encoding="utf-8", newline="\n")
    specs = (
        CollectionSpec(
            "demo",
            "docs/assets/mermaid-icons/demo.json",
            group_by_initial=True,
        ),
    )
    return tmp_path, specs


def _planned_sheet_names(manifest: dict) -> set[str]:
    return {
        Path(sheet["file"]).name
        for coll in manifest["collections"]
        for sheet in coll.get("sheets") or []
    }


def _local_md_targets(content: str) -> list[str]:
    targets: list[str] = []
    for match in MD_TARGET_RE.finditer(content):
        target = match.group(1)
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        targets.append(target)
    return targets


# --- entry line / sheet href --------------------------------------------------


def test_sheet_href_depths() -> None:
    assert sheet_href("reference/icons/sheets/aws-001.svg", depth=0) == "sheets/aws-001.svg"
    assert (
        sheet_href("reference/icons/sheets/logos-a-001.svg", depth=1)
        == "../sheets/logos-a-001.svg"
    )


def test_entry_line_contains_slug_name_sheet_cell_usage(tmp_path: Path) -> None:
    root, specs = _fixture_root(tmp_path)
    manifest = build_manifest(root=root, collections=specs)
    by_slug = {e["slug"]: e for e in manifest["icons"]}
    alpha = by_slug["demo:alpha"]
    href = sheet_href(alpha["sheet"], depth=0)
    line = render_icon_entry_line(alpha, href=href)
    assert line.startswith("- `demo:alpha` — Alpha — ")
    assert "[demo-001.svg](sheets/demo-001.svg)" in line
    assert f" {alpha['cell']} — " in line
    assert "`service example(demo:alpha)[Alpha]`" in line


def test_collection_index_sheet_sections(tmp_path: Path) -> None:
    root, specs = _fixture_root(tmp_path)
    manifest = build_manifest(root=root, collections=specs)
    page = render_collection_index(manifest, "demo")
    assert "## demo-001" in page
    assert "![demo-001](sheets/demo-001.svg)" in page
    assert "`demo:alpha`" in page
    assert "`demo:hidden-one`" in page  # listed; still on the sheet
    assert "Nonstandard keys" in page
    assert REGENERATE_CMD in page


def test_hub_and_group_indexes(tmp_path: Path) -> None:
    root, specs = _grouped_fixture_root(tmp_path)
    manifest = build_manifest(root=root, collections=specs)
    hub = render_collection_hub(manifest, "demo")
    assert "`demo:alpha`" not in hub
    assert "| `a` |" in hub
    assert "| `0` |" in hub
    assert "[a.md](demo/a.md)" in hub
    assert "sheets/demo-a-001.svg" in hub

    group_a = render_group_index(manifest, "demo", "a")
    assert "## demo-a-001" in group_a
    assert "![demo-a-001](../sheets/demo-a-001.svg)" in group_a
    assert "`demo:alpha`" in group_a
    assert "`demo:azure`" in group_a
    assert "`demo:beta`" not in group_a
    assert "[Demo Pack hub](../demo.md)" in group_a


def test_regeneration_command_in_readme(tmp_path: Path) -> None:
    root, specs = _fixture_root(tmp_path)
    manifest = build_manifest(root=root, collections=specs)
    readme = render_icons_readme(manifest)
    assert REGENERATE_CMD in readme
    assert f"`{REGENERATE_CMD}`" in readme
    assert "**Generated file — do not edit." in readme
    assert "contact sheets" in readme.lower() or "Contact sheets" in readme


def test_notices_contact_sheets_wording(tmp_path: Path) -> None:
    root, specs = _fixture_root(tmp_path)
    manifest = build_manifest(root=root, collections=specs)
    notices = render_third_party_notices(manifest)
    assert "TODO-MAINTAINER" in notices
    assert "`notes`: null" in notices
    assert "reference/icons/sheets/" in notices
    assert "contact sheets" in notices
    assert "previews/" not in notices
    assert "composing AWS" in notices
    assert "not create a separate grant of rights" in notices
    assert "Demo Pack" in notices
    assert "`demo`" in notices
    assert "docs/assets/mermaid-icons/demo.json" in notices


def test_size_guard_triggers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, specs = _fixture_root(tmp_path)
    manifest = build_manifest(root=root, collections=specs)
    monkeypatch.setattr("icons.MARKDOWN_MAX_BYTES", 200)
    with pytest.raises(IconValidationError) as exc:
        build_markdown_outputs(manifest, root=root, collections=specs)
    assert any("Shard this collection page" in e for e in exc.value.errors)
    assert any("bytes" in e for e in exc.value.errors)


def test_golden_collection_markdown(
    tmp_path: Path, update_goldens: bool
) -> None:
    root, specs = _fixture_root(tmp_path)
    manifest = build_manifest(root=root, collections=specs)
    outputs = build_markdown_outputs(manifest, root=root, collections=specs)
    page = outputs["reference/icons/demo.md"]
    golden_path = GOLDEN / "demo-index.md"
    if update_goldens:
        golden_path.write_text(page, encoding="utf-8", newline="\n")
    expected = golden_path.read_text(encoding="utf-8").replace("\r\n", "\n")
    assert page == expected


def test_markdown_link_targets_are_planned(tmp_path: Path) -> None:
    root, specs = _fixture_root(tmp_path)
    manifest = build_manifest(root=root, collections=specs)
    outputs = build_markdown_outputs(manifest, root=root, collections=specs)
    planned_md = {rel for rel in outputs if rel.endswith(".md") and rel != NOTICES_REL}
    planned_sheets = _planned_sheet_names(manifest)

    for rel, content in outputs.items():
        if rel == NOTICES_REL:
            continue
        page_dir = Path(rel).parent
        for target in _local_md_targets(content):
            if target.startswith("../../"):
                continue  # THIRD_PARTY_NOTICES from README
            resolved = (page_dir / target).as_posix()
            if target.endswith(".svg") or "/sheets/" in target or target.startswith("sheets/"):
                assert Path(target).name in planned_sheets, f"{rel}: unplanned {target}"
            elif target.endswith(".md"):
                # normalize to repo-relative under reference/icons
                if resolved.startswith("reference/icons/"):
                    assert resolved in planned_md or resolved == ICONS_README_REL, (
                        f"{rel}: unplanned md {resolved}"
                    )
                else:
                    # relative like demo/a.md from hub — join under ICONS_DIR_REL
                    joined = f"{ICONS_DIR_REL}/{target}".replace("\\", "/")
                    # collapse ../
                    parts: list[str] = []
                    for part in joined.split("/"):
                        if part == "..":
                            if parts:
                                parts.pop()
                        elif part and part != ".":
                            parts.append(part)
                    normalized = "/".join(parts)
                    assert normalized in planned_md or normalized == ICONS_README_REL, (
                        f"{rel}: unplanned md {target} -> {normalized}"
                    )


# --- real collections ---------------------------------------------------------


@pytest.fixture(scope="module")
def real_manifest_and_md() -> tuple[dict, dict[str, str]]:
    manifest = build_manifest(root=ROOT, collections=COLLECTIONS)
    outputs = build_markdown_outputs(manifest, root=ROOT, collections=COLLECTIONS)
    return manifest, outputs


def test_real_markdown_under_size_limit(real_manifest_and_md: tuple) -> None:
    _, outputs = real_manifest_and_md
    for rel, content in outputs.items():
        size = len(content.encode("utf-8"))
        assert size <= MARKDOWN_MAX_BYTES, f"{rel} is {size} bytes"


def test_real_link_targets_planned(real_manifest_and_md: tuple) -> None:
    manifest, outputs = real_manifest_and_md
    planned_sheets = _planned_sheet_names(manifest)
    planned_md = {rel for rel in outputs if rel.endswith(".md")}

    for rel, content in outputs.items():
        if rel == NOTICES_REL:
            continue
        page_dir = Path(rel).parent
        for target in _local_md_targets(content):
            if target.startswith(("http://", "https://")):
                continue
            if "THIRD_PARTY_NOTICES" in target:
                continue
            name = Path(target).name
            if name.endswith(".svg"):
                assert name in planned_sheets, f"{rel}: unplanned sheet {target}"
            elif name.endswith(".md"):
                parts: list[str] = []
                for part in (page_dir / target).as_posix().split("/"):
                    if part == "..":
                        if parts:
                            parts.pop()
                    elif part and part != ".":
                        parts.append(part)
                # page_dir is relative like reference/icons or reference/icons/logos
                # rebuild from rel's parent + target
                joined_parts: list[str] = []
                for part in Path(rel).parent.parts + Path(target).parts:
                    if part == "..":
                        if joined_parts:
                            joined_parts.pop()
                    elif part != ".":
                        joined_parts.append(part)
                normalized = Path(*joined_parts).as_posix()
                assert normalized in planned_md, f"{rel}: unplanned md {target} -> {normalized}"


def test_real_aws_sheet_sections(real_manifest_and_md: tuple) -> None:
    _, outputs = real_manifest_and_md
    aws = outputs["reference/icons/aws.md"]
    assert "## aws-001" in aws
    assert "![aws-001](sheets/aws-001.svg)" in aws
    assert "`aws:cloudfront`" in aws
    assert "- `aws:" in aws
    assert REGENERATE_CMD in outputs[ICONS_README_REL]


def test_real_logos_hub_and_letter_pages(real_manifest_and_md: tuple) -> None:
    _, outputs = real_manifest_and_md
    hub = outputs["reference/icons/logos.md"]
    assert "`logos:6px`" not in hub  # hub has no icon entries
    assert "| `a` |" in hub
    assert "[a.md](logos/a.md)" in hub
    assert "reference/icons/logos/a.md" in outputs
    letter_a = outputs["reference/icons/logos/a.md"]
    assert "## logos-a-001" in letter_a
    assert "../sheets/logos-a-001.svg" in letter_a
    assert "`logos:adobe-dreamweaver`" in letter_a


def test_real_readme_links_collections(real_manifest_and_md: tuple) -> None:
    _, outputs = real_manifest_and_md
    readme = outputs[ICONS_README_REL]
    assert "[AWS Icons](aws.md)" in readme
    assert "[SVG Logos](logos.md)" in readme
    assert "THIRD_PARTY_NOTICES.md" in readme
    assert "Sheet gallery" in readme
    assert "sheets/aws-001.svg" in readme
