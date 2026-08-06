"""Contact-sheet rendering tests (golden + layout + real-collection invariants)."""

from __future__ import annotations

import json
import math
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from icons import (  # noqa: E402
    COLLECTIONS,
    COLUMNS,
    ICONS_PER_SHEET,
    ICON_VIEW_H,
    ICON_VIEW_W,
    LABEL_MAX_CHARS,
    SCHEMA_VERSION,
    SHEETS_REL,
    SVG_NS,
    CollectionSpec,
    IconValidationError,
    _LayoutIcon,
    chunk,
    format_layout_number,
    group_key,
    layout_sheet,
    prepare_artifacts,
    render_icon_entry_line,
    render_sheet_svg,
    sheet_height,
    sheet_href,
    sheet_name,
    truncate_label,
    write_if_changed,
    write_sheets,
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
) -> None:
    data: dict = {
        "prefix": prefix,
        "info": {
            "name": prefix.upper(),
            "author": {"name": "Test", "url": "https://example.com"},
            "license": {
                "title": "CC0",
                "spdx": "CC0-1.0",
                "url": "https://example.com/license",
            },
        },
        "lastModified": 1700000000,
        "icons": icons,
    }
    if width is not None:
        data["width"] = width
    if height is not None:
        data["height"] = height
    if aliases is not None:
        data["aliases"] = aliases
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8", newline="\n")


def _fixture_root(tmp_path: Path) -> tuple[Path, tuple[CollectionSpec, ...]]:
    """Eight-icon (+alias) fixture covering full dims, defaults, offsets, nonstandard key."""
    pack = tmp_path / "docs" / "assets" / "mermaid-icons" / "demo.json"
    _write_pack(
        pack,
        prefix="demo",
        width=48,
        height=48,
        icons={
            "full-dims": {
                "body": '<path d="M0 0h16v16H0z" fill="#111"/>',
                "width": 16,
                "height": 16,
            },
            "collection-default": {
                "body": '<circle cx="24" cy="24" r="20" fill="#222"/>',
            },
            "with-offsets": {
                "body": '<rect width="100" height="40" fill="#333"/>',
                "width": 100,
                "height": 40,
                "left": 0.1,
                "top": 31.4,
            },
            "weird-&-key": {
                "body": '<path d="M1 1h8v8H1z" fill="#444"/>',
            },
            "parent-icon": {
                "body": '<ellipse cx="8" cy="8" rx="8" ry="8" fill="#555"/>',
                "width": 16,
                "height": 16,
            },
            "hidden-one": {
                "body": '<path d="M0 0h4v4H0z"/>',
                "hidden": True,
            },
            "mixed-dims": {
                "body": '<path d="M0 0h32v48H0z"/>',
                "width": 32,
            },
            "float-left": {
                "body": '<path d="M0 0h10v10H0z"/>',
                "width": 10,
                "height": 10,
                "left": 0.1,
            },
        },
        aliases={"alias-of-parent": {"parent": "parent-icon"}},
    )
    (tmp_path / "docs" / "assets" / "mermaid-icons" / "sources.json").write_text(
        "{}", encoding="utf-8", newline="\n"
    )
    specs = (CollectionSpec("demo", "docs/assets/mermaid-icons/demo.json"),)
    return tmp_path, specs


def _layout(
    key: str,
    *,
    width: float,
    height: float,
    left: float = 0,
    top: float = 0,
    body: str = '<path d="M0 0h1v1H0z"/>',
) -> _LayoutIcon:
    return _LayoutIcon(
        key=key,
        slug=f"demo:{key}",
        width=width,
        height=height,
        left=left,
        top=top,
        body=body,
    )


def _plan_for(icons: list[_LayoutIcon], **kwargs) -> object:
    defaults = dict(
        collection_id="demo",
        collection_name="DEMO",
        source_json="docs/assets/mermaid-icons/demo.json",
        group=None,
        index=1,
        range_start=1,
        range_total=len(icons),
    )
    defaults.update(kwargs)
    return layout_sheet(icons, **defaults)


# --- truncate / group / chunk / naming ----------------------------------------


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        ("a" * 22, "a" * 22),
        ("a" * 23, "a" * 21 + "…"),
        ("short", "short"),
    ],
)
def test_truncate_label_boundary(key: str, expected: str) -> None:
    assert LABEL_MAX_CHARS == 22
    assert truncate_label(key) == expected


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        ("adobe-dreamweaver", "a"),
        ("zeta", "z"),
        ("100tb", "0"),
        ("6px", "0"),
        ("", "0"),
    ],
)
def test_group_key(key: str, expected: str) -> None:
    assert group_key(key) == expected


def test_chunk_boundaries() -> None:
    items = list(range(160))
    chunks = chunk(items, ICONS_PER_SHEET)
    assert ICONS_PER_SHEET == 80
    assert [len(c) for c in chunks] == [80, 80]
    assert chunk(list(range(81)), 80) == [list(range(80)), [80]]
    assert chunk(list(range(80)), 80) == [list(range(80))]


def test_sheet_name_zero_padding() -> None:
    assert sheet_name("aws", None, 1) == "aws-001.svg"
    assert sheet_name("aws", None, 11) == "aws-011.svg"
    assert sheet_name("logos", "a", 3) == "logos-a-003.svg"
    with pytest.raises(ValueError):
        sheet_name("aws", None, 0)


def test_sheet_height_shrinks_for_partial_grid() -> None:
    assert sheet_height(80) == sheet_height(ICONS_PER_SHEET)
    assert sheet_height(3) < sheet_height(80)
    assert sheet_height(3) == sheet_height(8)  # one row
    assert sheet_height(9) > sheet_height(8)


# --- layout / scale / centre --------------------------------------------------


@pytest.mark.parametrize(
    ("width", "height", "left", "top"),
    [
        (48, 48, 0, 0),  # square
        (512, 105, 0, 0),  # wide
        (64, 200, 0, 0),  # tall
        (16, 16, 0, 0),  # tiny
        (100, 40, 0.1, 31.4),  # offsets
    ],
)
def test_layout_scale_and_centre(
    width: float, height: float, left: float, top: float
) -> None:
    icon = _layout("sample", width=width, height=height, left=left, top=top)
    plan = _plan_for([icon])
    cell = plan.cells[0]
    assert cell.row == 0 and cell.column == 0 and cell.sheet_index == 1
    assert cell.cell == "r0c0"

    scale = min(ICON_VIEW_W / width, ICON_VIEW_H / height)
    # Recompute placement the same way as render_sheet_svg and assert numbers round.
    cell_x = 16 + cell.column * 150
    cell_y = 16 + 56 + cell.row * 132
    tx = cell_x + 8 + (ICON_VIEW_W - width * scale) / 2 - left * scale
    ty = cell_y + 8 + (ICON_VIEW_H - height * scale) / 2 - top * scale
    svg = render_sheet_svg(plan)
    assert (
        f'translate({format_layout_number(tx)} {format_layout_number(ty)}) '
        f'scale({format_layout_number(scale)})'
    ) in svg
    assert scale > 0
    # upscaling allowed for tiny icons
    if width <= 16 and height <= 16:
        assert scale >= 1


def test_render_sheet_svg_shape_and_cell_count() -> None:
    icons = [_layout(f"k{i}", width=16, height=16) for i in range(5)]
    plan = _plan_for(icons)
    text = render_sheet_svg(plan)
    assert text.startswith(
        "<!-- Generated by scripts/icons.py. Do not edit. "
        "Source: docs/assets/mermaid-icons/demo.json -->\n"
    )
    assert 'xmlns="http://www.w3.org/2000/svg"' in text
    assert 'xmlns:xlink="http://www.w3.org/1999/xlink"' in text
    assert f'width="1232" height="{sheet_height(5)}"' in text
    assert text.endswith("</svg>\n")
    assert "\r" not in text

    payload = text.split("\n", 1)[1]
    root = ET.fromstring(payload)
    assert root.tag == f"{{{SVG_NS}}}svg"
    # placement groups are direct children of the root (bodies may nest further <g>)
    groups = [
        el
        for el in list(root)
        if el.tag == f"{{{SVG_NS}}}g" and (el.get("transform") or "").startswith("translate(")
    ]
    assert len(groups) == 5


def test_render_deterministic() -> None:
    icons = [
        _layout("wide", width=512, height=105),
        _layout("tiny", width=16, height=16),
        _layout("offset", width=100, height=40, left=0.1, top=31.4),
    ]
    plan = _plan_for(icons)
    assert render_sheet_svg(plan) == render_sheet_svg(plan)


# --- safety / well-formedness -------------------------------------------------


def test_script_body_rejected(tmp_path: Path) -> None:
    pack = tmp_path / "docs" / "assets" / "mermaid-icons" / "demo.json"
    _write_pack(
        pack,
        prefix="demo",
        icons={
            "evil": {
                "body": '<script>alert(1)</script><path d="M0 0h1v1H0z"/>'
            }
        },
    )
    with pytest.raises(IconValidationError) as exc:
        prepare_artifacts(
            root=tmp_path,
            collections=(
                CollectionSpec("demo", "docs/assets/mermaid-icons/demo.json"),
            ),
        )
    assert any("safety scan" in e for e in exc.value.errors)


@pytest.mark.parametrize(
    "body",
    [
        '<foreignObject width="1" height="1"></foreignObject>',
        "<!DOCTYPE svg>",
        '<!ENTITY x "y"><path/>',
        '<rect width="1" height="1" onclick="x()"/>',
        '<path onload = "x()" d="M0 0"/>',
        '<image href="https://evil.example/x.png"/>',
        '<a href="https://evil.example">x</a>',
        '<use href="https://evil.example/x.svg#i"/>',
        '<animate attributeName="x" values="0;1"/>',
        '<path href="https://evil.example"/>',
    ],
)
def test_unsafe_bodies_rejected(tmp_path: Path, body: str) -> None:
    pack = tmp_path / "docs" / "assets" / "mermaid-icons" / "demo.json"
    _write_pack(pack, prefix="demo", icons={"bad": {"body": body}})
    with pytest.raises(IconValidationError) as exc:
        prepare_artifacts(
            root=tmp_path,
            collections=(
                CollectionSpec("demo", "docs/assets/mermaid-icons/demo.json"),
            ),
        )
    joined = " ".join(exc.value.errors)
    assert (
        "safety scan" in joined
        or "disallowed" in joined
        or "non-fragment" in joined
        or "not well-formed" in joined
    )


def test_malformed_body_rejected(tmp_path: Path) -> None:
    pack = tmp_path / "docs" / "assets" / "mermaid-icons" / "demo.json"
    _write_pack(
        pack,
        prefix="demo",
        icons={"broken": {"body": "<path d='M0 0'"}},  # unclosed
    )
    with pytest.raises(IconValidationError) as exc:
        prepare_artifacts(
            root=tmp_path,
            collections=(
                CollectionSpec("demo", "docs/assets/mermaid-icons/demo.json"),
            ),
        )
    assert any("well-formed" in e for e in exc.value.errors)


# --- golden sheet -------------------------------------------------------------


def test_golden_sheet(tmp_path: Path, update_goldens: bool) -> None:
    root, specs = _fixture_root(tmp_path)
    _, plans = prepare_artifacts(root=root, collections=specs)
    assert len(plans) == 1
    rendered = render_sheet_svg(plans[0])
    golden_path = GOLDEN / "demo-sheet.svg"
    if update_goldens:
        golden_path.write_text(rendered, encoding="utf-8", newline="\n")
    expected = golden_path.read_text(encoding="utf-8").replace("\r\n", "\n")
    assert rendered == expected
    assert len(plans[0].cells) == 9  # 8 icons + 1 alias


# --- write / sheets flag ------------------------------------------------------


def test_unchanged_sheet_not_rewritten(tmp_path: Path) -> None:
    root, specs = _fixture_root(tmp_path)
    _, plans = prepare_artifacts(root=root, collections=specs)
    written1, unchanged1 = write_sheets(plans, root=root)
    assert written1 == len(plans) and unchanged1 == 0

    path = root / plans[0].rel_path
    mtime_before = path.stat().st_mtime_ns
    time.sleep(0.02)
    written2, unchanged2 = write_sheets(plans, root=root)
    assert written2 == 0 and unchanged2 == len(plans)
    assert path.stat().st_mtime_ns == mtime_before


def test_write_if_changed_skips_identical(tmp_path: Path) -> None:
    path = tmp_path / "a.svg"
    assert write_if_changed(path, "hello\n") is True
    assert write_if_changed(path, "hello\n") is False
    assert write_if_changed(path, "hello\r\n") is False
    assert write_if_changed(path, "other\n") is True


def test_sheets_false_emits_no_plans(tmp_path: Path) -> None:
    pack = tmp_path / "docs" / "assets" / "mermaid-icons" / "demo.json"
    _write_pack(pack, prefix="demo", icons={"a": {"body": "<path/>"}})
    manifest, plans = prepare_artifacts(
        root=tmp_path,
        collections=(
            CollectionSpec(
                "demo",
                "docs/assets/mermaid-icons/demo.json",
                sheets=False,
            ),
        ),
    )
    assert plans == []
    assert manifest["icons"][0]["sheet"].startswith(f"{SHEETS_REL}/")


# --- integration fixture ------------------------------------------------------


def test_integration_manifest_sheet_and_index(tmp_path: Path) -> None:
    long_key = "a" * 40
    pack = tmp_path / "docs" / "assets" / "mermaid-icons" / "demo.json"
    _write_pack(
        pack,
        prefix="demo",
        width=48,
        height=48,
        icons={
            "cloudfront": {
                "body": '<path d="M0 0h16v16H0z"/>',
                "width": 64,
                "height": 64,
            },
            "glue-databrew": {"body": '<path d="M0 0h16v16H0z"/>'},
            "glue-data-catalog": {"body": '<path d="M0 0h16v16H0z"/>'},
            "kinesis": {"body": '<path d="M0 0h16v16H0z"/>'},
            "adobe-dreamweaver": {
                "body": '<path d="M0 0h16v16H0z"/>',
                "width": 256,
                "height": 250,
            },
            "missing-width-only": {
                "body": '<path d="M0 0h16v16H0z"/>',
                "height": 32,
            },
            long_key: {"body": '<path d="M0 0h16v16H0z"/>'},
            "100tb": {"body": '<path d="M0 0h16v16H0z"/>'},
            "weird-&-key": {"body": '<path d="M0 0h16v16H0z"/>'},
        },
    )
    (tmp_path / "docs" / "assets" / "mermaid-icons" / "sources.json").write_text(
        "{}", encoding="utf-8", newline="\n"
    )
    specs = (CollectionSpec("demo", "docs/assets/mermaid-icons/demo.json"),)
    manifest, plans = prepare_artifacts(root=tmp_path, collections=specs)

    assert manifest["schema_version"] == SCHEMA_VERSION == 2
    by_key = {e["key"]: e for e in manifest["icons"]}
    assert by_key["cloudfront"]["name"] == "Cloudfront"
    assert by_key["glue-databrew"]["name"] == "Glue Databrew"
    assert by_key["glue-data-catalog"]["name"] == "Glue Data Catalog"
    assert by_key["kinesis"]["name"] == "Kinesis"
    assert by_key["adobe-dreamweaver"]["name"] == "Adobe Dreamweaver"
    assert by_key["missing-width-only"]["dimensions_source"] == "mixed"
    assert by_key["missing-width-only"]["width"] == 48
    assert by_key["missing-width-only"]["height"] == 32
    assert by_key["weird-&-key"]["flags"] == ["nonstandard-key"]
    assert "filename-sanitized" not in by_key["weird-&-key"].get("flags", [])
    assert "preview" not in by_key["cloudfront"]

    # sorted key order → placement
    keys = sorted(by_key)
    assert [e["key"] for e in manifest["icons"]] == keys
    for i, key in enumerate(keys):
        entry = by_key[key]
        assert entry["sheet_index"] == i + 1
        assert entry["row"] == i // COLUMNS
        assert entry["column"] == i % COLUMNS
        assert entry["cell"] == f"r{entry['row']}c{entry['column']}"
        assert entry["sheet"] == plans[0].rel_path

    svg = render_sheet_svg(plans[0])
    assert truncate_label(long_key) in svg
    assert long_key not in svg  # truncated in the label text
    assert "weird-&amp;-key" in svg  # XML-escaped label

    entry = by_key["adobe-dreamweaver"]
    line = render_icon_entry_line(
        entry, href=sheet_href(entry["sheet"], depth=0)
    )
    assert "`demo:adobe-dreamweaver`" in line
    assert "Adobe Dreamweaver" in line
    assert "demo-001.svg" in line
    assert entry["cell"] in line
    assert entry["usage_example"] in line


# --- real collections ---------------------------------------------------------


@pytest.fixture(scope="module")
def real_artifacts() -> tuple[dict, list]:
    return prepare_artifacts(root=ROOT, collections=COLLECTIONS)


def test_real_manifest_icon_count(real_artifacts: tuple) -> None:
    manifest, plans = real_artifacts
    assert manifest["schema_version"] == 2
    # 867 aws icons + 2091 logos icons + 7 logos aliases
    assert len(manifest["icons"]) == 867 + 2091 + 7
    by_coll = {c["id"]: c["icon_count"] for c in manifest["collections"]}
    assert by_coll["aws"] == 867
    assert by_coll["logos"] == 2098
    assert len(plans) == 51


def test_real_sheet_files_exist_and_parse(real_artifacts: tuple) -> None:
    manifest, plans = real_artifacts
    sheets_root = ROOT / SHEETS_REL
    assert sheets_root.is_dir()

    slugs: set[str] = set()
    coords: set[tuple[str, int, int]] = set()
    sheet_paths = {p.rel_path for p in plans}

    for entry in manifest["icons"]:
        slug = entry["slug"]
        assert slug not in slugs
        slugs.add(slug)
        coord = (entry["sheet"], entry["row"], entry["column"])
        assert coord not in coords
        coords.add(coord)
        assert entry["sheet"] in sheet_paths
        assert "preview" not in entry
        assert "\\" not in entry["sheet"]
        assert entry["sheet"].startswith(f"{SHEETS_REL}/")

    for plan in plans:
        path = ROOT / plan.rel_path
        assert path.is_file(), f"MISSING {plan.rel_path}"
        text = path.read_text(encoding="utf-8")
        assert "\r" not in text
        assert text.startswith("<!-- Generated by scripts/icons.py. Do not edit. ")
        payload = text.split("\n", 1)[1]
        root_el = ET.fromstring(payload)
        assert root_el.tag == f"{{{SVG_NS}}}svg"
        groups = [
            el
            for el in list(root_el)
            if el.tag == f"{{{SVG_NS}}}g"
            and (el.get("transform") or "").startswith("translate(")
        ]
        assert len(groups) == len(plan.cells)

    on_disk = {
        p.relative_to(ROOT).as_posix()
        for p in sheets_root.glob("*.svg")
        if p.is_file()
    }
    assert on_disk == sheet_paths


def test_real_aws_and_logos_sheet_naming(real_artifacts: tuple) -> None:
    _, plans = real_artifacts
    aws = [p for p in plans if p.collection_id == "aws"]
    logos = [p for p in plans if p.collection_id == "logos"]
    assert len(aws) == 11
    assert all(p.group is None for p in aws)
    assert aws[0].rel_path.endswith("aws-001.svg")
    assert aws[-1].rel_path.endswith("aws-011.svg")
    assert any(p.rel_path.endswith("logos-a-001.svg") for p in logos)
    assert any(p.rel_path.endswith("logos-0-001.svg") for p in logos)
    assert math.ceil(867 / ICONS_PER_SHEET) == 11
