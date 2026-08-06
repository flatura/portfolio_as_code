"""Unit tests for scripts/icons.py (generator core / manifest)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from icons import (  # noqa: E402
    COLLECTIONS,
    SCHEMA_VERSION,
    CollectionSpec,
    IconValidationError,
    RawIcon,
    build_manifest,
    format_number,
    humanize,
    load_collection,
    load_sources,
    render_manifest_json,
    resolve_dimensions,
    validate_key,
    write_manifest,
)


def _write_pack(
    path: Path,
    *,
    prefix: str,
    icons: dict,
    width: int | None = 48,
    height: int | None = 48,
    aliases: dict | None = None,
    last_modified: int = 1700000000,
    info: dict | None = None,
) -> None:
    data: dict = {
        "prefix": prefix,
        "info": info
        or {
            "name": prefix.upper(),
            "author": {"name": "Test", "url": "https://example.com"},
            "license": {"title": "CC0", "spdx": "CC0-1.0", "url": "https://example.com/license"},
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
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8", newline="\n")


# --- humanize -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        ("cloudfront", "Cloudfront"),
        ("glue-databrew", "Glue Databrew"),
        ("glue-data-catalog", "Glue Data Catalog"),
        ("kinesis", "Kinesis"),
        ("ec2", "Ec2"),
        ("adobe-dreamweaver", "Adobe Dreamweaver"),
        ("6px", "6Px"),
        ("redshift-query-editor-v2.0", "Redshift Query Editor V2.0"),
    ],
)
def test_humanize(key: str, expected: str) -> None:
    assert humanize(key) == expected


# --- validate_key -------------------------------------------------------------


@pytest.mark.parametrize(
    ("key", "flags"),
    [
        ("cloudfront", []),
        ("redshift-query-editor-v2.0", ["nonstandard-key"]),
        ("ec2-aws-microservice-extractor-for-.net", ["nonstandard-key"]),
        ("elemental-appliances-&-software", ["nonstandard-key"]),
        ("---", []),
        ("con", []),
    ],
)
def test_validate_key_flags(key: str, flags: list[str]) -> None:
    assert validate_key(key) == flags


@pytest.mark.parametrize(
    "key",
    [
        "",
        "../evil",
        "evil/../x",
        "a/b",
        "a\\b",
        "has\x00null",
    ],
)
def test_validate_key_rejects(key: str) -> None:
    with pytest.raises(ValueError):
        validate_key(key)


def test_validate_key_rejects_non_string() -> None:
    with pytest.raises(ValueError):
        validate_key(None)  # type: ignore[arg-type]


# --- format_number / resolve_dimensions --------------------------------------


def test_format_number_integers_and_floats() -> None:
    assert format_number(0) == "0"
    assert format_number(0.0) == "0"
    assert format_number(64) == "64"
    assert format_number(0.1) == "0.1"
    assert format_number(31.4) == "31.4"
    assert format_number(244.5) == "244.5"


def test_resolve_dimensions_matrix() -> None:
    both = resolve_dimensions(RawIcon("a", width=64, height=64), 48, 48)
    assert (both.width, both.height, both.dimensions_source) == (64, 64, None)

    only_w = resolve_dimensions(RawIcon("a", width=100), 48, 48)
    assert (only_w.width, only_w.height, only_w.dimensions_source) == (100, 48, "mixed")

    only_h = resolve_dimensions(RawIcon("a", height=200), 48, 48)
    assert (only_h.width, only_h.height, only_h.dimensions_source) == (48, 200, "mixed")

    neither = resolve_dimensions(RawIcon("a"), 48, 48)
    assert (neither.width, neither.height, neither.dimensions_source) == (
        48,
        48,
        "collection-default",
    )

    library = resolve_dimensions(RawIcon("a"), None, None)
    assert (library.width, library.height, library.dimensions_source) == (
        16,
        16,
        "library-default",
    )


def test_resolve_dimensions_left_top_defaults_and_floats() -> None:
    defaults = resolve_dimensions(RawIcon("a", width=1, height=1), None, None)
    assert defaults.left == 0 and defaults.top == 0

    offsets = resolve_dimensions(
        RawIcon("a", width=512, height=105, left=0.1, top=31.4),
        256,
        256,
    )
    assert offsets.left == 0.1
    assert offsets.top == 31.4
    assert format_number(offsets.left) == "0.1"
    assert format_number(offsets.top) == "31.4"


# --- load_collection validation ----------------------------------------------


def test_load_prefix_mismatch(tmp_path: Path) -> None:
    path = tmp_path / "pack.json"
    _write_pack(path, prefix="other", icons={"a": {"body": "<path/>"}})
    coll, errors, _ = load_collection(path, "aws", source_json="pack.json")
    assert coll is None
    assert any("prefix" in e for e in errors)


def test_load_missing_body(tmp_path: Path) -> None:
    path = tmp_path / "pack.json"
    _write_pack(
        path,
        prefix="aws",
        icons={
            "ok": {"body": "<path/>"},
            "bad": {"width": 16},
            "empty": {"body": ""},
            "nonstring": {"body": 1},
        },
    )
    coll, errors, _ = load_collection(path, "aws", source_json="pack.json")
    assert coll is None
    body_errors = [e for e in errors if "body" in e]
    assert len(body_errors) == 3


def test_load_bad_dimensions(tmp_path: Path) -> None:
    path = tmp_path / "pack.json"
    _write_pack(
        path,
        prefix="aws",
        icons={
            "str-w": {"body": "<path/>", "width": "64"},
            "zero-h": {"body": "<path/>", "height": 0},
        },
    )
    coll, errors, _ = load_collection(path, "aws", source_json="pack.json")
    assert coll is None
    assert any("width" in e for e in errors)
    assert any("height" in e for e in errors)


def test_load_non_object_root(tmp_path: Path) -> None:
    path = tmp_path / "pack.json"
    path.write_text("[]", encoding="utf-8")
    coll, errors, _ = load_collection(path, "aws", source_json="pack.json")
    assert coll is None
    assert any("object" in e for e in errors)


def test_load_missing_icons(tmp_path: Path) -> None:
    path = tmp_path / "pack.json"
    path.write_text(json.dumps({"prefix": "aws"}), encoding="utf-8")
    coll, errors, _ = load_collection(path, "aws", source_json="pack.json")
    assert coll is None
    assert any("icons" in e for e in errors)


# --- aliases ------------------------------------------------------------------


def test_alias_expansion_and_transform_skip(tmp_path: Path) -> None:
    root = tmp_path
    pack = root / "docs" / "assets" / "mermaid-icons" / "logos.json"
    _write_pack(
        pack,
        prefix="logos",
        width=256,
        height=256,
        icons={
            "linux-tux": {"body": "<circle/>", "width": 256, "height": 256},
            "plain": {"body": "<rect/>"},
        },
        aliases={
            "tux": {"parent": "linux-tux"},
            "rotated": {"parent": "linux-tux", "rotate": 1},
        },
    )
    (root / "docs" / "assets" / "mermaid-icons" / "sources.json").write_text(
        "{}", encoding="utf-8"
    )

    specs = (CollectionSpec("logos", "docs/assets/mermaid-icons/logos.json"),)
    manifest = build_manifest(root=root, collections=specs)
    slugs = {i["slug"]: i for i in manifest["icons"]}
    assert "logos:tux" in slugs
    assert slugs["logos:tux"]["alias_of"] == "logos:linux-tux"
    assert slugs["logos:tux"]["source"].endswith("#/aliases/tux")
    assert "logos:rotated" not in slugs
    assert manifest["collections"][0]["icon_count"] == 3  # linux-tux, plain, tux


def test_alias_key_collision_with_icon(tmp_path: Path) -> None:
    path = tmp_path / "pack.json"
    _write_pack(
        path,
        prefix="logos",
        icons={"tux": {"body": "<circle/>"}},
        aliases={"tux": {"parent": "tux"}},
    )
    coll, errors, _ = load_collection(path, "logos", source_json="pack.json")
    assert coll is None
    assert any("collides" in e for e in errors)


# --- collisions / sources / determinism ---------------------------------------


def test_nonstandard_keys_coexist_without_filename_collision(tmp_path: Path) -> None:
    """Keys that once shared a sanitised stem are distinct sheet cells now."""
    root = tmp_path
    pack = root / "docs" / "assets" / "mermaid-icons" / "aws.json"
    _write_pack(
        pack,
        prefix="aws",
        icons={
            "foo.bar": {"body": "<path/>"},
            "foo-bar": {"body": "<path/>"},
        },
    )
    specs = (CollectionSpec("aws", "docs/assets/mermaid-icons/aws.json"),)
    manifest = build_manifest(root=root, collections=specs)
    assert manifest["schema_version"] == SCHEMA_VERSION == 2
    by_key = {i["key"]: i for i in manifest["icons"]}
    assert by_key["foo.bar"]["flags"] == ["nonstandard-key"]
    assert "flags" not in by_key["foo-bar"]
    assert by_key["foo.bar"]["sheet"] == by_key["foo-bar"]["sheet"]
    assert by_key["foo.bar"]["cell"] != by_key["foo-bar"]["cell"]


def test_missing_sources_degrades_to_null(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    pack = tmp_path / "docs" / "assets" / "mermaid-icons" / "aws.json"
    _write_pack(pack, prefix="aws", icons={"a": {"body": "<path/>"}})
    sources, warnings = load_sources(tmp_path)
    assert sources is None
    assert warnings and "missing" in warnings[0]

    manifest = build_manifest(
        root=tmp_path,
        collections=(CollectionSpec("aws", "docs/assets/mermaid-icons/aws.json"),),
    )
    assert manifest["collections"][0]["provenance"] is None
    err = capsys.readouterr().err
    assert "sources.json" in err


def test_manifest_deterministic_and_ordered(tmp_path: Path) -> None:
    root = tmp_path
    pack = root / "docs" / "assets" / "mermaid-icons" / "aws.json"
    _write_pack(
        pack,
        prefix="aws",
        icons={
            "b-key": {"body": "<path/>", "width": 10, "height": 10},
            "a-key": {"body": "<path/>"},
            "A-upper": {"body": "<path/>"},  # code-point: 'A' < 'a' < 'b' after... keys as-is
        },
    )
    # use keys that sort by code point: 'A-upper' (65), 'a-key' (97), 'b-key' (98)
    # actually Iconify keys are lowercase; still assert sorted(key) order
    sources = root / "docs" / "assets" / "mermaid-icons" / "sources.json"
    sources.write_text(
        json.dumps(
            {
                "aws": {
                    "obtained_from": "TODO-MAINTAINER",
                    "retrieved": "TODO-MAINTAINER",
                    "notes": "TODO-MAINTAINER",
                }
            }
        ),
        encoding="utf-8",
    )
    specs = (CollectionSpec("aws", "docs/assets/mermaid-icons/aws.json"),)
    m1 = build_manifest(root=root, collections=specs)
    m2 = build_manifest(root=root, collections=specs)
    assert render_manifest_json(m1) == render_manifest_json(m2)
    keys = [i["key"] for i in m1["icons"]]
    assert keys == sorted(keys)
    # collection-default only when neither axis on icon
    by_key = {i["key"]: i for i in m1["icons"]}
    assert by_key["a-key"]["dimensions_source"] == "collection-default"
    assert "dimensions_source" not in by_key["b-key"]
    assert m1["collections"][0]["provenance"]["obtained_from"] == "TODO-MAINTAINER"


def test_write_manifest_trailing_newline_lf(tmp_path: Path) -> None:
    pack = tmp_path / "docs" / "assets" / "mermaid-icons" / "aws.json"
    _write_pack(pack, prefix="aws", icons={"z": {"body": "<path/>"}})
    manifest = build_manifest(
        root=tmp_path,
        collections=(CollectionSpec("aws", "docs/assets/mermaid-icons/aws.json"),),
    )
    out = write_manifest(manifest, root=tmp_path, path=tmp_path / "manifest.json")
    raw = out.read_bytes()
    assert raw.endswith(b"\n")
    assert b"\r" not in raw


def test_hidden_flag_passthrough(tmp_path: Path) -> None:
    pack = tmp_path / "docs" / "assets" / "mermaid-icons" / "logos.json"
    _write_pack(
        pack,
        prefix="logos",
        icons={"6px": {"body": "<path/>", "height": 265, "hidden": True}},
        width=256,
        height=256,
    )
    manifest = build_manifest(
        root=tmp_path,
        collections=(CollectionSpec("logos", "docs/assets/mermaid-icons/logos.json"),),
    )
    entry = manifest["icons"][0]
    assert entry["hidden"] is True
    assert entry["dimensions_source"] == "mixed"
    assert entry["name"] == "6Px"


def test_nonstandard_key_flags_and_sheet_coords(tmp_path: Path) -> None:
    pack = tmp_path / "docs" / "assets" / "mermaid-icons" / "aws.json"
    _write_pack(
        pack,
        prefix="aws",
        icons={"elemental-appliances-&-software": {"body": "<path/>"}},
    )
    manifest = build_manifest(
        root=tmp_path,
        collections=(CollectionSpec("aws", "docs/assets/mermaid-icons/aws.json"),),
    )
    entry = manifest["icons"][0]
    assert entry["flags"] == ["nonstandard-key"]
    assert "preview" not in entry
    assert entry["sheet"] == "reference/icons/sheets/aws-001.svg"
    assert entry["sheet_index"] == 1
    assert entry["row"] == 0
    assert entry["column"] == 0
    assert entry["cell"] == "r0c0"
    assert manifest["schema_version"] == 2
    assert manifest["collections"][0]["grouped_by_initial"] is False
    assert len(manifest["collections"][0]["sheets"]) == 1


def test_registry_order_and_ids() -> None:
    ids = [c.id for c in COLLECTIONS]
    assert ids == sorted(ids)
    assert ids == ["aws", "logos"]
    assert COLLECTIONS[0].group_by_initial is False
    assert COLLECTIONS[1].group_by_initial is True
    assert SCHEMA_VERSION == 2
