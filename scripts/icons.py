"""Icon pack loader, normaliser, manifest, contact-sheet, and reference generator.

Canonical inputs:
  docs/assets/mermaid-icons/{aws-icons,logos}.json
  docs/assets/mermaid-icons/sources.json  (optional provenance sidecar)

Generated output (this module):
  reference/icons/manifest.json
  reference/icons/sheets/*.svg
  reference/icons/{README,aws,logos}.md
  THIRD_PARTY_NOTICES.md
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence, TypeVar

ROOT = Path(__file__).resolve().parents[1]

SCHEMA_VERSION = 2
GENERATOR = "scripts/icons.py"
LIBRARY_DEFAULT = 16
SOURCES_REL = "docs/assets/mermaid-icons/sources.json"
MANIFEST_REL = "reference/icons/manifest.json"
SHEETS_REL = "reference/icons/sheets"
ICONS_DIR_REL = "reference/icons"
ICONS_README_REL = "reference/icons/README.md"
NOTICES_REL = "THIRD_PARTY_NOTICES.md"
REGENERATE_CMD = "python scripts/portfolio.py icons generate"
MARKDOWN_MAX_BYTES = 400_000
SHEET_MAX_BYTES = 2_000_000
TMP_DIR_PREFIX = ".icons-tmp-"
MD_TARGET_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
FENCE_RE = re.compile(r"^(`{3,})(.*)$")
MERMAID_ICON_STMT_RE = re.compile(
    r"^\s*(?:service|group|junction)\s+\w+\(([^)]+)\)"
)
CHECK_REMEDIATE = (
    "Generated icon reference is out of date.\n"
    "\n"
    "Run:\n"
    f"{REGENERATE_CMD}\n"
    "\n"
    "Then commit the updated manifest, SVG sheets, and Markdown reference."
)

# Contact-sheet grid. logos aspect ratios range from ~512×105 (marko) to near-square;
# aws icons are 48–74 px squares. The cell uses a wide, short icon viewport (134×76,
# ratio 1.76) that letterboxes both extremes without cropping. 8×10 keeps the sheet
# at 1232 px — under the ~1400 px GitHub blob viewport — so sheets display near 1:1.
COLUMNS = 8
ROWS = 10
ICONS_PER_SHEET = COLUMNS * ROWS  # 80
MARGIN = 16
HEADER_H = 56
CELL_W = 150
CELL_H = 132
CELL_PAD = 8
ICON_VIEW_W = CELL_W - 2 * CELL_PAD  # 134
ICON_VIEW_H = 76
LABEL_BASELINE = CELL_PAD + ICON_VIEW_H + 22
LABEL_FONT_PX = 9
LABEL_MAX_CHARS = 22
SHEET_W = 2 * MARGIN + COLUMNS * CELL_W  # 1232
SHEET_H_FULL = MARGIN + HEADER_H + ROWS * CELL_H + MARGIN  # 1408
LABEL_FONT_FAMILY = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"
HEADER_FONT_FAMILY = "ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif"

# Bodies are Iconify SVG fragments; reject active content before writing sheets.
UNSAFE_BODY_RE = re.compile(
    r"<script|<foreignObject|<!DOCTYPE|<!ENTITY|\bon[a-z]+\s*=",
    re.IGNORECASE,
)
IMAGE_TAG_RE = re.compile(r"<image\b", re.IGNORECASE)
ANCHOR_TAG_RE = re.compile(r"<a\s", re.IGNORECASE)
ANIMATE_TAG_RE = re.compile(r"<(?:animate|set)\b", re.IGNORECASE)
HREF_ATTR_RE = re.compile(
    r"(?:xlink:)?href\s*=\s*(['\"])(.*?)\1",
    re.IGNORECASE | re.DOTALL,
)
SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"

COLLECTION_ID_RE = re.compile(r"^[a-z][a-z0-9-]*$")
STANDARD_KEY_RE = re.compile(r"^[a-z0-9-]+$")
ALIAS_TRANSFORM_KEYS = ("rotate", "hFlip", "vFlip")

T = TypeVar("T")


@dataclass(frozen=True)
class CollectionSpec:
    id: str
    json_path: str  # repo-relative POSIX path
    group_by_initial: bool = False
    sheets: bool = True  # set False to skip SVG emission (e.g. licensing gate)


COLLECTIONS: tuple[CollectionSpec, ...] = (
    CollectionSpec("aws", "docs/assets/mermaid-icons/aws-icons.json", group_by_initial=False),
    CollectionSpec("logos", "docs/assets/mermaid-icons/logos.json", group_by_initial=True),
)


@dataclass(frozen=True)
class SheetCell:
    """One icon cell inside a contact sheet."""

    key: str
    slug: str
    width: int | float
    height: int | float
    left: int | float
    top: int | float
    body: str
    row: int  # 0-based
    column: int  # 0-based
    sheet_index: int  # 1-based within the sheet
    cell: str  # e.g. r0c0


@dataclass(frozen=True)
class SheetPlan:
    """One contact-sheet SVG to emit under ``reference/icons/sheets/``."""

    rel_path: str  # repo-relative POSIX path
    collection_id: str
    collection_name: str
    source_json: str
    group: str | None
    index: int  # 1-based within the group
    range_start: int  # 1-based inclusive, within group/collection scope
    range_end: int
    range_total: int
    first_key: str
    last_key: str
    sheet_w: int
    sheet_h: int
    cells: tuple[SheetCell, ...]


@dataclass
class RawIcon:
    key: str
    body: str | None = None
    width: int | float | None = None
    height: int | float | None = None
    left: int | float | None = None
    top: int | float | None = None
    hidden: bool = False
    is_alias: bool = False
    alias_parent: str | None = None
    skipped_transform: bool = False


@dataclass
class RawCollection:
    id: str
    prefix: str
    source_json: str
    name: str | None = None
    upstream_version: str | None = None
    snapshot: str | None = None
    author: dict[str, Any] | None = None
    license: dict[str, Any] | None = None
    default_width: int | float | None = None
    default_height: int | float | None = None
    icons: dict[str, RawIcon] = field(default_factory=dict)
    aliases: dict[str, RawIcon] = field(default_factory=dict)
    categories: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class ResolvedDimensions:
    width: int | float
    height: int | float
    left: int | float
    top: int | float
    dimensions_source: str | None  # None means fully from icon (omit in manifest)


class IconValidationError(Exception):
    """One or more validation problems; ``errors`` holds every message."""

    def __init__(self, errors: Sequence[str]) -> None:
        self.errors = list(errors)
        super().__init__("\n".join(self.errors))


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def write_if_changed(path: Path, content: str) -> bool:
    """Write ``content`` only when it differs. Returns True if the file was written."""
    normalized = content.replace("\r\n", "\n")
    if path.is_file():
        existing = path.read_text(encoding="utf-8").replace("\r\n", "\n")
        if existing == normalized:
            return False
    write_text(path, normalized)
    return True


def scan_svg_body(body: str, identity: str) -> list[str]:
    """Return hard-error messages if ``body`` contains disallowed SVG content."""
    errors: list[str] = []
    if UNSAFE_BODY_RE.search(body):
        errors.append(
            f"{identity}: SVG body failed safety scan "
            "(script/foreignObject/DOCTYPE/ENTITY/on* attribute)"
        )
    if IMAGE_TAG_RE.search(body):
        errors.append(f"{identity}: SVG body contains disallowed <image> element")
    if ANCHOR_TAG_RE.search(body):
        errors.append(f"{identity}: SVG body contains disallowed <a> element")
    if ANIMATE_TAG_RE.search(body):
        errors.append(f"{identity}: SVG body contains disallowed <animate>/<set> element")
    for match in HREF_ATTR_RE.finditer(body):
        href = match.group(2)
        if not href.startswith("#"):
            errors.append(
                f"{identity}: SVG body has non-fragment href/xlink:href {href!r}"
            )
    return errors


def format_layout_number(value: int | float) -> str:
    """Format a layout coordinate/scale, rounded to 4 decimals for cross-platform stability."""
    return format_number(round(float(value), 4))


def escape_xml_text(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def truncate_label(key: str, max_chars: int = LABEL_MAX_CHARS) -> str:
    if len(key) <= max_chars:
        return key
    return key[: max_chars - 1] + "…"


def group_key(key: str) -> str:
    """Initial-character group: ``a``–``z``, else ``0`` (digits/symbols)."""
    if not key:
        return "0"
    ch = key[0].lower()
    if "a" <= ch <= "z":
        return ch
    return "0"


def chunk(items: Sequence[T], size: int) -> list[list[T]]:
    if size <= 0:
        raise ValueError(f"chunk size must be > 0, got {size}")
    return [list(items[i : i + size]) for i in range(0, len(items), size)]


def sheet_name(collection_id: str, group: str | None, index: int) -> str:
    if index < 1:
        raise ValueError(f"sheet index must be >= 1, got {index}")
    if group is None:
        return f"{collection_id}-{index:03d}.svg"
    return f"{collection_id}-{group}-{index:03d}.svg"


def sheet_height(icon_count: int) -> int:
    """Sheet height shrinks with the last (partial) row; never padded to a full grid."""
    if icon_count <= 0:
        rows_used = 0
    else:
        rows_used = math.ceil(icon_count / COLUMNS)
    return MARGIN + HEADER_H + rows_used * CELL_H + MARGIN


def validate_sheet_svg(svg_text: str, identity: str) -> list[str]:
    """Parse the sheet document; root must be an ``svg`` element."""
    payload = svg_text.split("\n", 1)[1] if svg_text.startswith("<!--") else svg_text
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        return [f"{identity}: sheet SVG is not well-formed: {exc}"]
    tag = root.tag
    local = tag.rsplit("}", 1)[-1] if isinstance(tag, str) else tag
    if local != "svg":
        return [f"{identity}: sheet root element must be svg, got {tag!r}"]
    return []


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def format_number(value: int | float) -> str:
    """Render viewBox/attr numbers without float noise (0 not 0.0; 31.4 not 31.400…002)."""
    if not is_number(value):
        raise TypeError(f"expected number, got {type(value).__name__}")
    as_float = float(value)
    if as_float.is_integer():
        return repr(int(as_float))
    # shortest round-trip that prefers decimal form over binary noise
    text = format(as_float, ".15g")
    return text


def _cap_token(token: str) -> str:
    """Uppercase the first alphabetic character (so ``6px`` → ``6Px``, ``ec2`` → ``Ec2``)."""
    for i, ch in enumerate(token):
        if ch.isalpha():
            return token[:i] + ch.upper() + token[i + 1 :]
    return token


def humanize(key: str) -> str:
    return " ".join(_cap_token(token) for token in key.split("-") if token)


def validate_key(key: Any) -> list[str]:
    """Validate an upstream icon key.

    Raises ``ValueError`` for non-string, empty, path separators, or control characters.
    Returns flag names (currently only ``nonstandard-key``).
    """
    if not isinstance(key, str):
        raise ValueError(f"icon key must be a string, got {type(key).__name__}")
    if key == "" or "/" in key or "\\" in key:
        raise ValueError(f"invalid icon key: {key!r}")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in key):
        raise ValueError(f"icon key contains control characters: {key!r}")
    flags: list[str] = []
    if not STANDARD_KEY_RE.match(key):
        flags.append("nonstandard-key")
    return flags


@dataclass(frozen=True)
class _LayoutIcon:
    """Icon fields needed to lay out one sheet cell (internal)."""

    key: str
    slug: str
    width: int | float
    height: int | float
    left: int | float
    top: int | float
    body: str


def layout_sheet(
    icons: Sequence[_LayoutIcon],
    *,
    collection_id: str,
    collection_name: str,
    source_json: str,
    group: str | None,
    index: int,
    range_start: int,
    range_total: int,
) -> SheetPlan:
    """Place ``icons`` on a contact-sheet grid and return a ``SheetPlan``."""
    if not icons:
        raise ValueError(f"{collection_id}: cannot layout an empty sheet")
    if len(icons) > ICONS_PER_SHEET:
        raise ValueError(
            f"{collection_id}: sheet has {len(icons)} icons "
            f"(max {ICONS_PER_SHEET})"
        )

    cells: list[SheetCell] = []
    for i, icon in enumerate(icons):
        sheet_index = i + 1
        row = i // COLUMNS
        column = i % COLUMNS
        cells.append(
            SheetCell(
                key=icon.key,
                slug=icon.slug,
                width=icon.width,
                height=icon.height,
                left=icon.left,
                top=icon.top,
                body=icon.body,
                row=row,
                column=column,
                sheet_index=sheet_index,
                cell=f"r{row}c{column}",
            )
        )

    filename = sheet_name(collection_id, group, index)
    return SheetPlan(
        rel_path=f"{SHEETS_REL}/{filename}",
        collection_id=collection_id,
        collection_name=collection_name,
        source_json=source_json,
        group=group,
        index=index,
        range_start=range_start,
        range_end=range_start + len(icons) - 1,
        range_total=range_total,
        first_key=icons[0].key,
        last_key=icons[-1].key,
        sheet_w=SHEET_W,
        sheet_h=sheet_height(len(icons)),
        cells=tuple(cells),
    )


def render_sheet_svg(plan: SheetPlan) -> str:
    """Render a deterministic contact-sheet SVG (LF, UTF-8, no XML declaration)."""
    w = format_layout_number(plan.sheet_w)
    h = format_layout_number(plan.sheet_h)
    stem = Path(plan.rel_path).stem
    title = (
        f"{plan.collection_name} — {stem} — "
        f"icons {plan.range_start}-{plan.range_end} of {plan.range_total}"
    )
    comment = (
        f"<!-- Generated by {GENERATOR}. Do not edit. "
        f"Source: {plan.source_json} -->"
    )

    parts: list[str] = [
        comment,
        (
            f'<svg xmlns="{SVG_NS}" xmlns:xlink="{XLINK_NS}" '
            f'width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
        ),
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        (
            f'<text x="{MARGIN}" y="{MARGIN + 36}" '
            f'font-family="{HEADER_FONT_FAMILY}" font-size="18" '
            f'fill="#24292f">{escape_xml_text(title)}</text>'
        ),
    ]

    for cell in plan.cells:
        cell_x = MARGIN + cell.column * CELL_W
        cell_y = MARGIN + HEADER_H + cell.row * CELL_H
        scale = min(ICON_VIEW_W / cell.width, ICON_VIEW_H / cell.height)
        tx = (
            cell_x
            + CELL_PAD
            + (ICON_VIEW_W - cell.width * scale) / 2
            - cell.left * scale
        )
        ty = (
            cell_y
            + CELL_PAD
            + (ICON_VIEW_H - cell.height * scale) / 2
            - cell.top * scale
        )
        label = escape_xml_text(truncate_label(cell.key))
        label_x = cell_x + CELL_W / 2
        label_y = cell_y + LABEL_BASELINE

        parts.append(
            f'<rect x="{format_layout_number(cell_x)}" '
            f'y="{format_layout_number(cell_y)}" '
            f'width="{format_layout_number(CELL_W)}" '
            f'height="{format_layout_number(CELL_H)}" '
            f'fill="#f6f8fa" stroke="#d0d7de" stroke-width="1"/>'
        )
        parts.append(
            f'<rect x="{format_layout_number(cell_x + CELL_PAD)}" '
            f'y="{format_layout_number(cell_y + CELL_PAD)}" '
            f'width="{format_layout_number(ICON_VIEW_W)}" '
            f'height="{format_layout_number(ICON_VIEW_H)}" '
            f'fill="#ffffff"/>'
        )
        parts.append(
            f'<g transform="translate({format_layout_number(tx)} '
            f'{format_layout_number(ty)}) '
            f'scale({format_layout_number(scale)})">{cell.body}</g>'
        )
        parts.append(
            f'<text x="{format_layout_number(label_x)}" '
            f'y="{format_layout_number(label_y)}" '
            f'font-family="{LABEL_FONT_FAMILY}" '
            f'font-size="{LABEL_FONT_PX}" fill="#24292f" '
            f'text-anchor="middle">{label}</text>'
        )

    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def resolve_dimensions(
    icon: RawIcon,
    collection_width: int | float | None,
    collection_height: int | float | None,
) -> ResolvedDimensions:
    if icon.width is not None:
        width: int | float = icon.width
        w_src = "icon"
    elif collection_width is not None:
        width = collection_width
        w_src = "collection"
    else:
        width = LIBRARY_DEFAULT
        w_src = "library"

    if icon.height is not None:
        height: int | float = icon.height
        h_src = "icon"
    elif collection_height is not None:
        height = collection_height
        h_src = "collection"
    else:
        height = LIBRARY_DEFAULT
        h_src = "library"

    left: int | float = 0 if icon.left is None else icon.left
    top: int | float = 0 if icon.top is None else icon.top

    if w_src == "icon" and h_src == "icon":
        dimensions_source: str | None = None
    elif w_src == "collection" and h_src == "collection":
        dimensions_source = "collection-default"
    elif w_src == "library" and h_src == "library":
        dimensions_source = "library-default"
    else:
        dimensions_source = "mixed"

    return ResolvedDimensions(width, height, left, top, dimensions_source)


def _validate_dim_field(
    errors: list[str],
    collection_id: str,
    key: str,
    field_name: str,
    value: Any,
    *,
    positive: bool,
) -> int | float | None:
    if value is None:
        return None
    if not is_number(value):
        errors.append(
            f"{collection_id}:{key}: {field_name} must be a number, got {type(value).__name__}"
        )
        return None
    if positive and value <= 0:
        errors.append(f"{collection_id}:{key}: {field_name} must be > 0, got {value!r}")
        return None
    return value


def _parse_icon_record(
    collection_id: str,
    key: str,
    record: Any,
    errors: list[str],
) -> RawIcon | None:
    if not isinstance(record, dict):
        errors.append(f"{collection_id}:{key}: icon record must be an object")
        return None

    body = record.get("body")
    if body is None or body == "" or not isinstance(body, str):
        errors.append(f"{collection_id}:{key}: missing or non-string body")
        # still collect other field errors
        body_ok = False
        body_val: str | None = None
    else:
        body_ok = True
        body_val = body

    width = _validate_dim_field(errors, collection_id, key, "width", record.get("width"), positive=True)
    height = _validate_dim_field(errors, collection_id, key, "height", record.get("height"), positive=True)
    left = _validate_dim_field(errors, collection_id, key, "left", record.get("left"), positive=False)
    top = _validate_dim_field(errors, collection_id, key, "top", record.get("top"), positive=False)

    hidden = bool(record.get("hidden", False))

    if not body_ok:
        return None
    return RawIcon(
        key=key,
        body=body_val,
        width=width,
        height=height,
        left=left,
        top=top,
        hidden=hidden,
    )


def _parse_alias_record(
    collection_id: str,
    key: str,
    record: Any,
    errors: list[str],
    warnings_out: list[str],
) -> RawIcon | None:
    if not isinstance(record, dict):
        errors.append(f"{collection_id}:{key}: alias record must be an object")
        return None

    parent = record.get("parent")
    if not isinstance(parent, str) or not parent:
        errors.append(f"{collection_id}:{key}: alias missing string parent")
        return None

    if any(k in record for k in ALIAS_TRANSFORM_KEYS):
        warnings_out.append(
            f"{collection_id}:{key}: alias has transform fields; skipped (not expanded)"
        )
        return RawIcon(key=key, is_alias=True, alias_parent=parent, skipped_transform=True)

    return RawIcon(key=key, is_alias=True, alias_parent=parent)


def load_collection(
    path: Path,
    collection_id: str,
    *,
    source_json: str | None = None,
) -> tuple[RawCollection | None, list[str], list[str]]:
    """Load and structurally validate one IconifyJSON file.

    Returns ``(collection_or_None, errors, warnings)``.
    """
    errors: list[str] = []
    warn: list[str] = []

    if not COLLECTION_ID_RE.match(collection_id):
        errors.append(f"invalid collection id: {collection_id!r}")
        return None, errors, warn

    rel = source_json or path.as_posix()
    if not path.is_file():
        errors.append(f"{collection_id}: source JSON not found: {rel}")
        return None, errors, warn

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"{collection_id}: invalid JSON in {rel}: {exc}")
        return None, errors, warn

    if not isinstance(data, dict):
        errors.append(f"{collection_id}: top-level JSON must be an object")
        return None, errors, warn

    prefix = data.get("prefix")
    if prefix != collection_id:
        errors.append(
            f"{collection_id}: prefix {prefix!r} does not match registry id {collection_id!r}"
        )

    icons_obj = data.get("icons")
    if not isinstance(icons_obj, dict):
        errors.append(f"{collection_id}: missing or non-object 'icons'")
        icons_obj = {}

    default_width = data.get("width")
    default_height = data.get("height")
    if default_width is not None and not is_number(default_width):
        errors.append(f"{collection_id}: collection width must be a number")
        default_width = None
    elif default_width is not None and default_width <= 0:
        errors.append(f"{collection_id}: collection width must be > 0")
        default_width = None
    if default_height is not None and not is_number(default_height):
        errors.append(f"{collection_id}: collection height must be a number")
        default_height = None
    elif default_height is not None and default_height <= 0:
        errors.append(f"{collection_id}: collection height must be > 0")
        default_height = None

    info = data.get("info") if isinstance(data.get("info"), dict) else {}
    name = info.get("name") if isinstance(info.get("name"), str) else None
    version = info.get("version")
    upstream_version = version if isinstance(version, str) else None

    author_raw = info.get("author") if isinstance(info.get("author"), dict) else None
    author = None
    if author_raw is not None:
        author = {
            "name": author_raw.get("name"),
            "url": author_raw.get("url"),
        }

    license_raw = info.get("license") if isinstance(info.get("license"), dict) else None
    license_info = None
    if license_raw is not None:
        license_info = {
            "title": license_raw.get("title"),
            "spdx": license_raw.get("spdx"),
            "url": license_raw.get("url"),
        }

    snapshot = None
    last_modified = data.get("lastModified")
    if is_number(last_modified):
        snapshot = datetime.fromtimestamp(float(last_modified), tz=timezone.utc).isoformat()

    icons: dict[str, RawIcon] = {}
    for key, record in icons_obj.items():
        if not isinstance(key, str):
            errors.append(f"{collection_id}: non-string icon key {key!r}")
            continue
        parsed = _parse_icon_record(collection_id, key, record, errors)
        if parsed is not None:
            icons[key] = parsed

    aliases: dict[str, RawIcon] = {}
    aliases_obj = data.get("aliases")
    if aliases_obj is None:
        aliases_obj = {}
    elif not isinstance(aliases_obj, dict):
        errors.append(f"{collection_id}: 'aliases' must be an object when present")
        aliases_obj = {}

    for key, record in aliases_obj.items():
        if not isinstance(key, str):
            errors.append(f"{collection_id}: non-string alias key {key!r}")
            continue
        if key in icons:
            errors.append(f"{collection_id}:{key}: alias key collides with icon key")
            continue
        parsed_alias = _parse_alias_record(collection_id, key, record, errors, warn)
        if parsed_alias is not None and not parsed_alias.skipped_transform:
            aliases[key] = parsed_alias

    categories: dict[str, list[str]] = {}
    cats = data.get("categories")
    if isinstance(cats, dict):
        for cat_name, members in cats.items():
            if isinstance(cat_name, str) and isinstance(members, list):
                categories[cat_name] = [m for m in members if isinstance(m, str)]

    if errors:
        return None, errors, warn

    return (
        RawCollection(
            id=collection_id,
            prefix=str(prefix),
            source_json=rel.replace("\\", "/"),
            name=name,
            upstream_version=upstream_version,
            snapshot=snapshot,
            author=author,
            license=license_info,
            default_width=default_width,
            default_height=default_height,
            icons=icons,
            aliases=aliases,
            categories=categories,
        ),
        errors,
        warn,
    )


def load_sources(root: Path) -> tuple[dict[str, dict[str, Any]] | None, list[str]]:
    """Load provenance sidecar. Missing file → ``(None, [warning])``."""
    path = root / SOURCES_REL
    if not path.is_file():
        return None, [f"warning: {SOURCES_REL} missing; provenance will be null"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, [f"warning: {SOURCES_REL} is invalid JSON ({exc}); provenance will be null"]
    if not isinstance(data, dict):
        return None, [f"warning: {SOURCES_REL} root must be an object; provenance will be null"]
    out: dict[str, dict[str, Any]] = {}
    for key, value in data.items():
        if isinstance(key, str) and isinstance(value, dict):
            out[key] = value
    return out, []


def _provenance_for(
    collection_id: str,
    sources: dict[str, dict[str, Any]] | None,
) -> dict[str, Any] | None:
    if sources is None:
        return None
    entry = sources.get(collection_id)
    if entry is None:
        return None
    return {
        "obtained_from": entry.get("obtained_from"),
        "retrieved": entry.get("retrieved"),
        "notes": entry.get("notes"),
    }


def _manifest_icon_entry(
    collection: RawCollection,
    key: str,
    icon: RawIcon,
    *,
    dims_icon: RawIcon,
    sheet: str,
    sheet_index: int,
    row: int,
    column: int,
    alias_of: str | None = None,
    source_kind: str = "icons",
) -> dict[str, Any]:
    flags = validate_key(key)
    dims = resolve_dimensions(dims_icon, collection.default_width, collection.default_height)
    name = humanize(key)
    slug = f"{collection.id}:{key}"
    entry: dict[str, Any] = {
        "collection": collection.id,
        "key": key,
        "slug": slug,
        "name": name,
        "width": dims.width,
        "height": dims.height,
        "left": dims.left,
        "top": dims.top,
    }
    if dims.dimensions_source is not None:
        entry["dimensions_source"] = dims.dimensions_source
    entry["source"] = f"{collection.source_json}#/{source_kind}/{key}"
    if alias_of is not None:
        entry["alias_of"] = alias_of
    if icon.hidden or dims_icon.hidden:
        entry["hidden"] = True
    entry["sheet"] = sheet
    entry["sheet_index"] = sheet_index
    entry["row"] = row
    entry["column"] = column
    entry["cell"] = f"r{row}c{column}"
    entry["usage"] = slug
    entry["usage_example"] = f"service example({slug})[{name}]"
    if flags:
        entry["flags"] = flags
    return entry


@dataclass
class _PendingIcon:
    key: str
    icon: RawIcon
    dims_icon: RawIcon
    body: str
    alias_of: str | None = None
    source_kind: str = "icons"


def prepare_artifacts(
    root: Path | None = None,
    collections: Sequence[CollectionSpec] | None = None,
) -> tuple[dict[str, Any], list[SheetPlan]]:
    """Build the manifest and sheet plans. Raises ``IconValidationError`` on hard errors."""
    root = ROOT if root is None else root
    specs = COLLECTIONS if collections is None else tuple(collections)
    spec_by_id = {s.id: s for s in specs}
    errors: list[str] = []
    warn: list[str] = []

    sources, source_warnings = load_sources(root)
    warn.extend(source_warnings)

    loaded: list[RawCollection] = []
    for spec in specs:
        coll, coll_errors, coll_warnings = load_collection(
            root / spec.json_path,
            spec.id,
            source_json=spec.json_path,
        )
        errors.extend(coll_errors)
        warn.extend(coll_warnings)
        if coll is not None:
            loaded.append(coll)

    if errors:
        raise IconValidationError(errors)

    collection_entries: list[dict[str, Any]] = []
    icon_entries: list[dict[str, Any]] = []
    sheet_plans: list[SheetPlan] = []
    slugs: dict[str, str] = {}
    sheet_paths: dict[str, str] = {}

    for coll in loaded:
        spec = spec_by_id[coll.id]
        pending: list[_PendingIcon] = []

        for key, icon in coll.icons.items():
            assert icon.body is not None
            try:
                validate_key(key)
            except ValueError as exc:
                errors.append(f"{coll.id}:{key}: {exc}")
                continue
            pending.append(
                _PendingIcon(key=key, icon=icon, dims_icon=icon, body=icon.body)
            )

        for key, alias in coll.aliases.items():
            parent_key = alias.alias_parent
            assert parent_key is not None
            parent = coll.icons.get(parent_key)
            if parent is None:
                errors.append(
                    f"{coll.id}:{key}: alias parent {parent_key!r} not found in icons"
                )
                continue
            assert parent.body is not None
            try:
                validate_key(key)
            except ValueError as exc:
                errors.append(f"{coll.id}:{key}: {exc}")
                continue
            pending.append(
                _PendingIcon(
                    key=key,
                    icon=alias,
                    dims_icon=parent,
                    body=parent.body,
                    alias_of=f"{coll.id}:{parent_key}",
                    source_kind="aliases",
                )
            )

        pending.sort(key=lambda item: item.key)
        collection_name = coll.name or coll.id

        if spec.group_by_initial:
            grouped: dict[str, list[_PendingIcon]] = {}
            for item in pending:
                grouped.setdefault(group_key(item.key), []).append(item)
            group_seq: list[tuple[str | None, list[_PendingIcon]]] = [
                (g, grouped[g]) for g in sorted(grouped)
            ]
        else:
            group_seq = [(None, pending)]

        sheets_meta: list[dict[str, Any]] = []

        for group, group_items in group_seq:
            range_total = len(group_items)
            for sheet_i, sheet_items in enumerate(
                chunk(group_items, ICONS_PER_SHEET), start=1
            ):
                layout_icons: list[_LayoutIcon] = []
                for item in sheet_items:
                    dims = resolve_dimensions(
                        item.dims_icon, coll.default_width, coll.default_height
                    )
                    layout_icons.append(
                        _LayoutIcon(
                            key=item.key,
                            slug=f"{coll.id}:{item.key}",
                            width=dims.width,
                            height=dims.height,
                            left=dims.left,
                            top=dims.top,
                            body=item.body,
                        )
                    )

                range_start = (sheet_i - 1) * ICONS_PER_SHEET + 1
                plan = layout_sheet(
                    layout_icons,
                    collection_id=coll.id,
                    collection_name=collection_name,
                    source_json=coll.source_json,
                    group=group,
                    index=sheet_i,
                    range_start=range_start,
                    range_total=range_total,
                )

                if plan.rel_path in sheet_paths:
                    errors.append(
                        f"duplicate sheet filename {plan.rel_path!r}: "
                        f"{sheet_paths[plan.rel_path]} and {coll.id}"
                    )
                else:
                    sheet_paths[plan.rel_path] = coll.id

                sheets_meta.append(
                    {
                        "file": plan.rel_path,
                        "group": group,
                        "index": plan.index,
                        "icon_count": len(plan.cells),
                        "first_key": plan.first_key,
                        "last_key": plan.last_key,
                    }
                )

                for item, cell in zip(sheet_items, plan.cells, strict=True):
                    identity = f"{coll.id}:{item.key}"
                    slug = f"{coll.id}:{item.key}"
                    if slug in slugs:
                        errors.append(
                            f"duplicate slug {slug!r}: {slugs[slug]} and {identity}"
                        )
                    else:
                        slugs[slug] = identity

                    try:
                        entry = _manifest_icon_entry(
                            coll,
                            item.key,
                            item.icon,
                            dims_icon=item.dims_icon,
                            sheet=plan.rel_path,
                            sheet_index=cell.sheet_index,
                            row=cell.row,
                            column=cell.column,
                            alias_of=item.alias_of,
                            source_kind=item.source_kind,
                        )
                    except ValueError as exc:
                        errors.append(f"{identity}: {exc}")
                        continue

                    icon_entries.append(entry)
                    errors.extend(scan_svg_body(item.body, identity))

                if spec.sheets:
                    sheet_plans.append(plan)

        collection_entries.append(
            {
                "id": coll.id,
                "prefix": coll.prefix,
                "name": coll.name,
                "source_json": coll.source_json,
                "upstream_version": coll.upstream_version,
                "snapshot": coll.snapshot,
                "author": coll.author,
                "license": coll.license,
                "provenance": _provenance_for(coll.id, sources),
                "default_width": coll.default_width,
                "default_height": coll.default_height,
                "icon_count": len(pending),
                "grouped_by_initial": spec.group_by_initial,
                "sheets": sheets_meta,
            }
        )

    coll_index = {c.id: i for i, c in enumerate(loaded)}
    icon_entries.sort(key=lambda e: (coll_index[e["collection"]], e["key"]))
    sheet_plans.sort(
        key=lambda p: (
            coll_index[p.collection_id],
            "" if p.group is None else p.group,
            p.index,
        )
    )

    for plan in sheet_plans:
        svg_text = render_sheet_svg(plan)
        errors.extend(validate_sheet_svg(svg_text, plan.rel_path))

    if errors:
        raise IconValidationError(errors)

    for message in warn:
        print(message, file=sys.stderr)

    return (
        {
            "schema_version": SCHEMA_VERSION,
            "generator": GENERATOR,
            "collections": collection_entries,
            "icons": icon_entries,
        },
        sheet_plans,
    )


def build_manifest(
    root: Path | None = None,
    collections: Sequence[CollectionSpec] | None = None,
) -> dict[str, Any]:
    """Build the full manifest dict. Raises ``IconValidationError`` on hard errors."""
    manifest, _ = prepare_artifacts(root=root, collections=collections)
    return manifest


def write_sheets(
    plans: Sequence[SheetPlan],
    root: Path | None = None,
) -> tuple[int, int]:
    """Write contact-sheet SVGs. Returns ``(written, unchanged)`` counts."""
    root = ROOT if root is None else root
    written = 0
    unchanged = 0
    for plan in plans:
        content = render_sheet_svg(plan)
        path = root / plan.rel_path
        if write_if_changed(path, content):
            written += 1
        else:
            unchanged += 1
    return written, unchanged


def render_manifest_json(manifest: dict[str, Any]) -> str:
    return json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"


def write_manifest(
    manifest: dict[str, Any],
    root: Path | None = None,
    path: Path | None = None,
) -> Path:
    root = ROOT if root is None else root
    out = path if path is not None else root / MANIFEST_REL
    write_text(out, render_manifest_json(manifest))
    return out


def generated_file_warning() -> str:
    return f"**Generated file — do not edit. Run `{REGENERATE_CMD}`.**\n"


def _ensure_trailing_newline(text: str) -> str:
    return text if text.endswith("\n") else text + "\n"


def sheet_href(sheet_rel: str, *, depth: int = 0) -> str:
    """Relative href from a page under ``reference/icons/`` to a sheet SVG.

    ``depth=0`` for pages in ``reference/icons/``; ``depth=1`` for ``logos/<g>.md``.
    """
    name = Path(sheet_rel).name
    return f"{'../' * depth}sheets/{name}"


def render_icon_entry_line(entry: dict[str, Any], *, href: str) -> str:
    """One compact bullet index line for an icon."""
    sheet_file = Path(entry["sheet"]).name
    return (
        f"- `{entry['slug']}` — {entry['name']} — "
        f"[{sheet_file}]({href}) {entry['cell']} — "
        f"`{entry['usage_example']}`"
    )


def _collection_icons(
    manifest: dict[str, Any],
    collection_id: str,
) -> list[dict[str, Any]]:
    return [e for e in manifest["icons"] if e["collection"] == collection_id]


def _collection_meta(manifest: dict[str, Any], collection_id: str) -> dict[str, Any]:
    for coll in manifest["collections"]:
        if coll["id"] == collection_id:
            return coll
    raise KeyError(f"collection {collection_id!r} missing from manifest")


def _icons_by_sheet(
    entries: Sequence[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        grouped.setdefault(str(entry["sheet"]), []).append(entry)
    for sheet_entries in grouped.values():
        sheet_entries.sort(key=lambda e: e["sheet_index"])
    return grouped


def _render_sheet_sections(
    sheets: Sequence[dict[str, Any]],
    by_sheet: dict[str, list[dict[str, Any]]],
    *,
    depth: int,
) -> list[str]:
    lines: list[str] = []
    for sheet in sheets:
        sheet_rel = str(sheet["file"])
        entries = by_sheet.get(sheet_rel, [])
        if not entries:
            continue
        stem = Path(sheet_rel).stem
        href = sheet_href(sheet_rel, depth=depth)
        lines.append(f"## {stem}")
        lines.append("")
        lines.append(f"![{stem}]({href})")
        lines.append("")
        for entry in entries:
            lines.append(render_icon_entry_line(entry, href=href))
        lines.append("")
    return lines


def _nonstandard_callout(entries: Sequence[dict[str, Any]]) -> list[str]:
    if not any("nonstandard-key" in e.get("flags", []) for e in entries):
        return []
    return [
        "> **Nonstandard keys:** some upstream keys contain characters outside "
        "`[a-z0-9-]`. Slugs are reproduced verbatim and may need quoting or "
        "avoidance in Mermaid `architecture-beta` diagrams.",
        "",
    ]


def render_collection_index(manifest: dict[str, Any], collection_id: str) -> str:
    """Flat collection index (``aws.md``): one section per sheet with embedded image."""
    meta = _collection_meta(manifest, collection_id)
    icons = _collection_icons(manifest, collection_id)
    by_sheet = _icons_by_sheet(icons)
    name = meta.get("name") or collection_id

    n_sheets = len(meta.get("sheets") or [])
    sheet_word = "contact sheet" if n_sheets == 1 else "contact sheets"
    lines: list[str] = [
        generated_file_warning(),
        "",
        f"# {name}",
        "",
        f"Collection prefix: `{collection_id}`. {len(icons)} icons across "
        f"{n_sheets} {sheet_word}. "
        "Display names are approximate; copy the slug for Mermaid.",
        "",
    ]
    lines.extend(_nonstandard_callout(icons))
    lines.extend(
        _render_sheet_sections(meta.get("sheets") or [], by_sheet, depth=0)
    )
    return _ensure_trailing_newline("\n".join(lines))


def render_collection_hub(manifest: dict[str, Any], collection_id: str) -> str:
    """Hub page for a grouped collection (``logos.md``): TOC only, no icon entries."""
    meta = _collection_meta(manifest, collection_id)
    name = meta.get("name") or collection_id
    sheets = meta.get("sheets") or []

    groups: dict[str, list[dict[str, Any]]] = {}
    for sheet in sheets:
        g = sheet.get("group")
        if g is None:
            continue
        groups.setdefault(str(g), []).append(sheet)

    lines: list[str] = [
        generated_file_warning(),
        "",
        f"# {name}",
        "",
        f"Collection prefix: `{collection_id}`. {meta.get('icon_count', 0)} icons "
        f"grouped by initial character (`a`–`z`, or `0` for digits/symbols), "
        f"then chunked into {ICONS_PER_SHEET}-icon contact sheets. "
        "Open a letter index for slug bullets and embedded sheets.",
        "",
        "| Group | Icons | Sheets | Index |",
        "| --- | ---: | --- | --- |",
    ]

    for g in sorted(groups):
        group_sheets = groups[g]
        icon_count = sum(int(s.get("icon_count") or 0) for s in group_sheets)
        sheet_links = ", ".join(
            f"[{Path(s['file']).name}]({sheet_href(s['file'], depth=0)})"
            for s in group_sheets
        )
        lines.append(
            f"| `{g}` | {icon_count} | {sheet_links} | [{g}.md]({collection_id}/{g}.md) |"
        )

    lines.append("")
    return _ensure_trailing_newline("\n".join(lines))


def render_group_index(
    manifest: dict[str, Any],
    collection_id: str,
    group: str,
) -> str:
    """Per-letter index (``logos/<group>.md``): sheet sections with bullets."""
    meta = _collection_meta(manifest, collection_id)
    name = meta.get("name") or collection_id
    sheets = [s for s in (meta.get("sheets") or []) if s.get("group") == group]
    icons = [
        e
        for e in _collection_icons(manifest, collection_id)
        if group_key(str(e["key"])) == group
    ]
    by_sheet = _icons_by_sheet(icons)
    icon_count = sum(int(s.get("icon_count") or 0) for s in sheets)

    lines: list[str] = [
        generated_file_warning(),
        "",
        f"# {name} — `{group}`",
        "",
        f"[{name} hub](../{collection_id}.md). "
        f"{icon_count} icons in group `{group}` across {len(sheets)} "
        f"{'sheet' if len(sheets) == 1 else 'sheets'}. "
        "Display names are approximate; copy the slug for Mermaid.",
        "",
    ]
    lines.extend(_nonstandard_callout(icons))
    lines.extend(_render_sheet_sections(sheets, by_sheet, depth=1))
    return _ensure_trailing_newline("\n".join(lines))


def render_icons_readme(manifest: dict[str, Any]) -> str:
    n_icons = len(manifest["icons"])
    n_sheets = sum(len(c.get("sheets") or []) for c in manifest["collections"])

    lines: list[str] = [
        generated_file_warning(),
        "",
        "# Icon reference",
        "",
        "Browsable slug catalogue for Mermaid `architecture-beta` diagrams. "
        "This directory is repository-only documentation (outside `docs/`) and is "
        "**not** part of the MkDocs site.",
        "",
        f"Regenerate with `{REGENERATE_CMD}`.",
        "",
        "## Why these packs are vendored",
        "",
        "The Iconify JSON files under `docs/assets/mermaid-icons/` are committed "
        "snapshots so site builds stay deterministic and offline for icon assets: "
        "no CDN or API fetch at build or browse time for the packs themselves, "
        "usable on restricted networks, and immune to upstream removal of a key. "
        "Refreshing a pack is an explicit maintainer action, not an automatic sync.",
        "",
        "## Why contact sheets (not one file per icon)",
        "",
        f"Showing every icon without rasterising still needs the SVG bodies once. "
        f"Per-icon previews meant ~{n_icons} committed files; contact sheets keep "
        f"the same visual coverage in **{n_sheets}** SVG files ({ICONS_PER_SHEET} "
        "icons per full sheet). Byte volume is essentially unchanged — that is "
        "inherent to shipping all bodies. History still holds deleted preview blobs.",
        "",
        "## Collections",
        "",
    ]

    for coll in manifest["collections"]:
        cid = coll["id"]
        name = coll.get("name") or cid
        count = coll.get("icon_count", 0)
        version = coll.get("upstream_version")
        version_text = (
            f"upstream version `{version}`"
            if isinstance(version, str) and version
            else "upstream version not recorded"
        )
        snapshot = coll.get("snapshot") or "unknown"
        license_info = coll.get("license") or {}
        spdx = license_info.get("spdx") or "unknown"
        license_url = license_info.get("url") or ""
        license_bit = f"[{spdx}]({license_url})" if license_url else spdx
        lines.append(
            f"- [{name}]({cid}.md) (`{cid}`) — {count} icons; "
            f"{version_text}; snapshot `{snapshot}`; license {license_bit}"
        )

    lines.extend(
        [
            "",
            "## How sheets are grouped and chunked",
            "",
            f"- **`aws`:** all keys sorted, chunked into {ICONS_PER_SHEET}s → "
            "`sheets/aws-001.svg`, `aws-002.svg`, …",
            f"- **`logos`:** group by initial (`a`–`z`, else `0`), then chunk → "
            "`sheets/logos-<group>-<NNN>.svg`; letter indexes live under "
            "`logos/<group>.md`.",
            "",
            "## How to read a cell coordinate",
            "",
            "Each index bullet ends with a sheet link and a cell like `r5c1`: "
            "**0-based** `row` and `column` inside that sheet (`r0c0` is top-left). "
            "The full slug, display name, and Mermaid usage example are on the same "
            "line for `Ctrl+F` / GitHub code search.",
            "",
            "## Sheet gallery",
            "",
        ]
    )

    for coll in manifest["collections"]:
        cid = coll["id"]
        name = coll.get("name") or cid
        lines.append(f"### {name} (`{cid}`)")
        lines.append("")
        for sheet in coll.get("sheets") or []:
            sheet_rel = str(sheet["file"])
            stem = Path(sheet_rel).stem
            href = sheet_href(sheet_rel, depth=0)
            first = sheet.get("first_key") or ""
            last = sheet.get("last_key") or ""
            count = sheet.get("icon_count") or 0
            lines.append(
                f"- [![{stem}]({href})]({href}) — {count} icons "
                f"(`{first}` … `{last}`)"
            )
        lines.append("")

    lines.extend(
        [
            "## Display names",
            "",
            "Display names are a mechanical humanisation of the upstream key "
            "(split on `-`, capitalise tokens). They are approximate — acronyms and "
            "official product casing are often wrong (`Ec2`, `Cloudfront`). "
            "The slug and Mermaid usage example are authoritative.",
            "",
            "## How to use a slug",
            "",
            "Slug format is `<pack>:<icon-key>` (upstream key verbatim). Example:",
            "",
            "````markdown",
            "```mermaid",
            "architecture-beta",
            "    service api(aws:api-gateway)[API Gateway]",
            "    service fn(aws:lambda)[Lambda]",
            "    api:R --> L:fn",
            "```",
            "````",
            "",
            "Find slugs in the per-collection / per-letter pages linked above, or "
            "search this folder for `aws:` / `logos:` plus a keyword.",
            "",
            "## Licensing",
            "",
            "Repository source is MIT; vendored icon collections and generated "
            "contact sheets are third-party works under their own terms. "
            "See [`THIRD_PARTY_NOTICES.md`](../../THIRD_PARTY_NOTICES.md).",
            "",
            "## Deferred",
            "",
            "Upstream sync automation, curated official display names, alias/"
            "deprecated-slug registry, fuzzy suggestions, interactive search UI, "
            "MkDocs nav integration, per-icon luminance backgrounds, and trimming "
            "packs to only referenced icons are out of scope for this iteration.",
            "",
        ]
    )
    return _ensure_trailing_newline("\n".join(lines))


def render_third_party_notices(manifest: dict[str, Any]) -> str:
    lines: list[str] = [
        generated_file_warning(),
        "",
        "# Third-party notices",
        "",
        "Repository source code and documentation are licensed under the MIT License "
        "(see `LICENSE`). Bundled icon assets under `docs/assets/mermaid-icons/` are "
        "third-party works distributed under their own terms, summarised below. "
        "Generated SVG contact sheets under `reference/icons/sheets/` are mechanical "
        "compositions of the vendored Iconify icon bodies into grid layouts; "
        "they do not create a separate grant of rights.",
        "",
        "**Maintainer note:** whether composing AWS (`CC-BY-ND-2.0`) icon bodies into "
        "contact sheets is compatible with the NoDerivatives term and AWS "
        "trademark guidelines is not resolved by this repository and must be confirmed "
        "by the maintainer. This file states upstream terms without asserting "
        "compatibility conclusions.",
        "",
    ]

    for coll in manifest["collections"]:
        cid = coll["id"]
        name = coll.get("name") or cid
        lines.append(f"## {name} (`{cid}`)")
        lines.append("")
        lines.append(f"- **Prefix:** `{cid}`")
        lines.append(f"- **Icon count:** {coll.get('icon_count', 0)}")
        version = coll.get("upstream_version")
        if isinstance(version, str) and version:
            lines.append(f"- **Upstream version:** `{version}`")
        else:
            lines.append("- **Upstream version:** not recorded upstream")
        snapshot = coll.get("snapshot")
        lines.append(
            f"- **Snapshot (`lastModified`):** `{snapshot}`"
            if snapshot
            else "- **Snapshot (`lastModified`):** not recorded"
        )
        author = coll.get("author") or {}
        author_name = author.get("name") or "unknown"
        author_url = author.get("url")
        if author_url:
            lines.append(f"- **Author:** [{author_name}]({author_url})")
        else:
            lines.append(f"- **Author:** {author_name}")
        license_info = coll.get("license") or {}
        title = license_info.get("title") or "unknown"
        spdx = license_info.get("spdx") or "unknown"
        license_url = license_info.get("url")
        if license_url:
            lines.append(f"- **License:** {title} (`{spdx}`) — <{license_url}>")
        else:
            lines.append(f"- **License:** {title} (`{spdx}`)")
        lines.append(f"- **Source JSON:** `{coll.get('source_json')}`")
        provenance = coll.get("provenance")
        lines.append("- **Provenance** (`docs/assets/mermaid-icons/sources.json`):")
        if provenance is None:
            lines.append("  - *(not available — sources.json missing or incomplete)*")
        else:
            for key in ("obtained_from", "retrieved", "notes"):
                value = provenance.get(key)
                rendered = "null" if value is None else str(value)
                lines.append(f"  - `{key}`: {rendered}")
        lines.append("")

    return _ensure_trailing_newline("\n".join(lines))


def build_markdown_outputs(
    manifest: dict[str, Any],
    root: Path | None = None,
    collections: Sequence[CollectionSpec] | None = None,
) -> dict[str, str]:
    """Return repo-relative path → Markdown body for README, indexes, notices.

    Raises ``IconValidationError`` if any page exceeds ``MARKDOWN_MAX_BYTES``.
    """
    _ = root  # outputs are derived from the manifest alone
    specs = COLLECTIONS if collections is None else tuple(collections)
    grouped_by_id = {s.id: s.group_by_initial for s in specs}

    outputs: dict[str, str] = {
        ICONS_README_REL: render_icons_readme(manifest),
        NOTICES_REL: render_third_party_notices(manifest),
    }

    for coll in manifest["collections"]:
        cid = coll["id"]
        if grouped_by_id.get(cid, False):
            outputs[f"{ICONS_DIR_REL}/{cid}.md"] = render_collection_hub(manifest, cid)
            groups = sorted(
                {
                    str(s["group"])
                    for s in (coll.get("sheets") or [])
                    if s.get("group") is not None
                }
            )
            for group in groups:
                outputs[f"{ICONS_DIR_REL}/{cid}/{group}.md"] = render_group_index(
                    manifest, cid, group
                )
        else:
            outputs[f"{ICONS_DIR_REL}/{cid}.md"] = render_collection_index(
                manifest, cid
            )

    errors: list[str] = []
    for rel, content in outputs.items():
        size = len(content.encode("utf-8"))
        if size > MARKDOWN_MAX_BYTES:
            errors.append(
                f"{rel}: generated Markdown is {size} bytes "
                f"(limit {MARKDOWN_MAX_BYTES}). Shard this collection page."
            )
    if errors:
        raise IconValidationError(errors)
    return outputs


def write_markdown_outputs(
    outputs: dict[str, str],
    root: Path | None = None,
) -> tuple[int, int]:
    """Write Markdown/notices files. Returns ``(written, unchanged)``."""
    root = ROOT if root is None else root
    written = 0
    unchanged = 0
    for rel, content in sorted(outputs.items()):
        if write_if_changed(root / rel, content):
            written += 1
        else:
            unchanged += 1
    return written, unchanged


def _posix_normjoin(*parts: str) -> str:
    """Join POSIX path parts and collapse ``.`` / ``..`` (no filesystem access)."""
    stack: list[str] = []
    for part in parts:
        for segment in part.replace("\\", "/").split("/"):
            if segment == "" or segment == ".":
                continue
            if segment == "..":
                if stack:
                    stack.pop()
                continue
            stack.append(segment)
    return "/".join(stack)


def _is_under_owned(rel: str) -> bool:
    normalized = rel.replace("\\", "/")
    return normalized == ICONS_DIR_REL or normalized.startswith(f"{ICONS_DIR_REL}/")


def render_all(
    root: Path | None = None,
    collections: Sequence[CollectionSpec] | None = None,
) -> tuple[dict[str, Any], dict[str, str]]:
    """Build every generated output in memory. Returns ``(manifest, outputs)``."""
    root = ROOT if root is None else root
    specs = COLLECTIONS if collections is None else tuple(collections)
    manifest, plans = prepare_artifacts(root=root, collections=specs)
    outputs: dict[str, str] = {MANIFEST_REL: render_manifest_json(manifest)}
    for plan in plans:
        outputs[plan.rel_path] = render_sheet_svg(plan)
    outputs.update(build_markdown_outputs(manifest, root=root, collections=specs))
    return manifest, outputs


def validate_outputs(outputs: dict[str, str]) -> None:
    """Pre-write validation of the full planned output set.

    Raises ``IconValidationError`` on any problem. Does not touch the filesystem.
    """
    errors: list[str] = []

    if MANIFEST_REL not in outputs:
        raise IconValidationError([f"planned outputs missing {MANIFEST_REL}"])

    try:
        manifest = json.loads(outputs[MANIFEST_REL])
    except json.JSONDecodeError as exc:
        raise IconValidationError([f"{MANIFEST_REL}: invalid JSON: {exc}"]) from exc

    planned_sheets = {rel for rel in outputs if rel.endswith(".svg")}
    planned_all = set(outputs)

    for rel, content in sorted(outputs.items()):
        size = len(content.encode("utf-8"))
        if rel.endswith(".svg"):
            if size > SHEET_MAX_BYTES:
                errors.append(
                    f"{rel}: sheet is {size} bytes (limit {SHEET_MAX_BYTES})"
                )
            errors.extend(validate_sheet_svg(content, rel))
        elif rel.endswith(".md"):
            if size > MARKDOWN_MAX_BYTES:
                errors.append(
                    f"{rel}: generated Markdown is {size} bytes "
                    f"(limit {MARKDOWN_MAX_BYTES}). Shard this collection page."
                )

    slugs: dict[str, str] = {}
    sheet_coords: dict[tuple[str, int, int], str] = {}
    sheet_names: dict[str, str] = {}

    for coll in manifest.get("collections") or []:
        for sheet in coll.get("sheets") or []:
            sheet_file = str(sheet.get("file") or "")
            if not sheet_file:
                errors.append(f"collection {coll.get('id')!r}: sheet entry missing file")
                continue
            name = Path(sheet_file).name
            if name in sheet_names:
                errors.append(
                    f"duplicate sheet filename {name!r}: "
                    f"{sheet_names[name]} and {sheet_file}"
                )
            else:
                sheet_names[name] = sheet_file
            if sheet_file not in planned_sheets:
                errors.append(f"manifest sheet {sheet_file} is not a planned output")

    for entry in manifest.get("icons") or []:
        slug = str(entry.get("slug") or "")
        identity = slug or f"{entry.get('collection')}:{entry.get('key')}"
        if not slug:
            errors.append(f"{identity}: missing slug")
            continue
        if slug in slugs:
            errors.append(f"duplicate slug {slug!r}")
        else:
            slugs[slug] = identity

        sheet = str(entry.get("sheet") or "")
        if sheet not in planned_sheets:
            errors.append(f"{slug}: sheet {sheet!r} is not a planned output")

        try:
            row = int(entry["row"])
            column = int(entry["column"])
        except (KeyError, TypeError, ValueError):
            errors.append(f"{slug}: missing or invalid row/column")
            continue
        coord_key = (sheet, row, column)
        if coord_key in sheet_coords:
            errors.append(
                f"duplicate sheet coordinate {sheet} r{row}c{column}: "
                f"{sheet_coords[coord_key]} and {slug}"
            )
        else:
            sheet_coords[coord_key] = slug

    for rel, content in sorted(outputs.items()):
        if not rel.endswith(".md"):
            continue
        page_dir = Path(rel).parent.as_posix()
        for match in MD_TARGET_RE.finditer(content):
            target = match.group(1)
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            resolved = _posix_normjoin(page_dir, target)
            if resolved not in planned_all:
                errors.append(f"{rel}: Markdown link target {target!r} -> {resolved} is not planned")

    if errors:
        raise IconValidationError(errors)


def write_tree(outputs: dict[str, str], dest_root: Path) -> None:
    """Write every planned output under ``dest_root`` using repo-relative paths."""
    for rel, content in sorted(outputs.items()):
        write_text(dest_root / rel, content.replace("\r\n", "\n"))


def cleanup_owned_dir(planned: set[str], *, root: Path) -> int:
    """Delete files under ``reference/icons/`` that are not planned outputs.

    Refusal guard: every path must resolve under ``root/reference/icons/``.
    ``THIRD_PARTY_NOTICES.md`` is outside the owned area and is never deleted here.
    Returns the number of files removed.
    """
    root_resolved = root.resolve()
    owned = (root_resolved / ICONS_DIR_REL).resolve()
    if not owned.is_dir():
        return 0

    removed = 0
    # Deepest paths first so files go before their parent directories.
    paths = sorted(owned.rglob("*"), key=lambda p: len(p.parts), reverse=True)
    for path in paths:
        resolved = path.resolve()
        if not resolved.is_relative_to(owned):
            raise RuntimeError(
                f"refusing to touch path outside owned icon directory: {path}"
            )
        if path.is_file():
            rel = resolved.relative_to(root_resolved).as_posix()
            if rel not in planned:
                path.unlink()
                removed += 1
        elif path.is_dir() and resolved != owned:
            try:
                next(path.iterdir())
            except StopIteration:
                path.rmdir()
    return removed


def sync_into_owned_dir(
    outputs: dict[str, str],
    *,
    root: Path,
) -> dict[str, int]:
    """Content-aware sync into the repository, then scoped stale cleanup.

    Writes only changed files. Owned-area cleanup deletes every file under
    ``reference/icons/`` that is not a planned output. Notices are written but
    never subject to deletion.
    """
    root = root.resolve()
    owned_planned = {rel for rel in outputs if _is_under_owned(rel)}

    sheets_written = sheets_unchanged = 0
    md_written = md_unchanged = 0
    manifest_written = manifest_unchanged = 0
    notices_written = notices_unchanged = 0

    for rel, content in sorted(outputs.items()):
        changed = write_if_changed(root / rel, content)
        if rel == NOTICES_REL:
            if changed:
                notices_written = 1
            else:
                notices_unchanged = 1
        elif rel == MANIFEST_REL:
            if changed:
                manifest_written = 1
            else:
                manifest_unchanged = 1
        elif rel.endswith(".svg"):
            if changed:
                sheets_written += 1
            else:
                sheets_unchanged += 1
        elif rel.endswith(".md") and _is_under_owned(rel):
            if changed:
                md_written += 1
            else:
                md_unchanged += 1

    removed = cleanup_owned_dir(owned_planned, root=root)

    return {
        "sheets_written": sheets_written,
        "sheets_unchanged": sheets_unchanged,
        "sheets_total": sum(1 for rel in outputs if rel.endswith(".svg")),
        "md_written": md_written,
        "md_unchanged": md_unchanged,
        "md_total": sum(
            1 for rel in outputs if rel.endswith(".md") and _is_under_owned(rel)
        ),
        "notices_written": notices_written,
        "notices_unchanged": notices_unchanged,
        "manifest_written": manifest_written,
        "manifest_unchanged": manifest_unchanged,
        "removed": removed,
    }


def _validate_temp_sheets(outputs: dict[str, str], tmp: Path) -> None:
    """Write outputs to ``tmp`` and re-parse every sheet from disk."""
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True, exist_ok=True)
    write_tree(outputs, tmp)

    disk_errors: list[str] = []
    for rel in sorted(r for r in outputs if r.endswith(".svg")):
        disk_text = (tmp / rel).read_text(encoding="utf-8").replace("\r\n", "\n")
        disk_errors.extend(validate_sheet_svg(disk_text, rel))
        if disk_text != outputs[rel].replace("\r\n", "\n"):
            disk_errors.append(
                f"{rel}: temp-dir content differs from in-memory render"
            )
    if disk_errors:
        raise IconValidationError(disk_errors)


def generate(
    root: Path | None = None,
    collections: Sequence[CollectionSpec] | None = None,
) -> tuple[dict[str, Any], dict[str, int]]:
    """Atomically generate icon reference artifacts.

    Builds all outputs in memory, validates, writes to a temp directory under
    ``reference/``, re-parses sheets from disk, then content-aware syncs into
    ``reference/icons/`` (and writes notices). Stale files under the owned
    directory are removed. On any failure before sync the committed tree is
    left untouched; the temp directory is always removed.
    """
    root = (ROOT if root is None else root).resolve()
    specs = COLLECTIONS if collections is None else tuple(collections)
    manifest, outputs = render_all(root=root, collections=specs)
    validate_outputs(outputs)

    tmp = root / "reference" / f"{TMP_DIR_PREFIX}{os.getpid()}"
    try:
        _validate_temp_sheets(outputs, tmp)
        stats = sync_into_owned_dir(outputs, root=root)
    finally:
        if tmp.exists():
            shutil.rmtree(tmp, ignore_errors=True)

    return manifest, stats


def iter_usage_markdown(root: Path) -> list[Path]:
    """User-authored Markdown that may contain Mermaid icon slugs.

    Scans ``docs/**/*.md``, ``templates/**/*.md``, and ``README.md``.
    Skips anything under ``reference/``.
    """
    root = root.resolve()
    reference = (root / "reference").resolve()
    found: list[Path] = []

    for base_name in ("docs", "templates"):
        base = root / base_name
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.md")):
            resolved = path.resolve()
            if resolved.is_relative_to(reference):
                continue
            found.append(resolved)

    readme = root / "README.md"
    if readme.is_file():
        found.append(readme.resolve())

    return found


def extract_mermaid_icon_usages(text: str) -> list[tuple[int, str]]:
    """Return ``(1-based line, slug)`` for icon tokens in mermaid fences.

    Tracks fenced regions opened by `` ```mermaid `` (including examples nested
    inside a `` ```markdown `` wrapper, as in README). Tokens without ``:`` are
    ignored — Mermaid allows icon-less nodes.
    """
    usages: list[tuple[int, str]] = []
    mermaid_fence: int | None = None

    for line_no, line in enumerate(text.splitlines(), start=1):
        fence = FENCE_RE.match(line)
        if fence is not None:
            ticks = len(fence.group(1))
            info = fence.group(2).strip()
            if mermaid_fence is None:
                lang = info.split()[0] if info else ""
                if lang == "mermaid":
                    mermaid_fence = ticks
            elif not info and ticks >= mermaid_fence:
                mermaid_fence = None
            continue

        if mermaid_fence is None:
            continue

        match = MERMAID_ICON_STMT_RE.match(line)
        if match is None:
            continue
        token = match.group(1).strip()
        if ":" not in token:
            continue
        usages.append((line_no, token))

    return usages


def scan_icon_usage(
    root: Path,
    known_slugs: set[str],
) -> list[str]:
    """Report unknown icon slugs in user-authored Mermaid diagrams."""
    problems: list[str] = []
    for path in iter_usage_markdown(root):
        rel = path.relative_to(root.resolve()).as_posix()
        text = path.read_text(encoding="utf-8")
        for line_no, slug in extract_mermaid_icon_usages(text):
            if slug in known_slugs:
                continue
            namespace = slug.split(":", 1)[0]
            problems.append(
                f"UNKNOWN SLUG {rel}:{line_no} {slug} (namespace={namespace})"
            )
    return problems


def list_owned_files(root: Path) -> list[str]:
    """Repo-relative POSIX paths of every file under ``reference/icons/``."""
    root_resolved = root.resolve()
    owned = root_resolved / ICONS_DIR_REL
    if not owned.is_dir():
        return []
    rels: list[str] = []
    for path in sorted(owned.rglob("*")):
        if path.is_file():
            rels.append(path.resolve().relative_to(root_resolved).as_posix())
    return rels


def check(
    root: Path | None = None,
    collections: Sequence[CollectionSpec] | None = None,
) -> list[str]:
    """Regenerate into a temp directory and compare against the committed tree.

    Never writes into ``reference/icons/`` or ``THIRD_PARTY_NOTICES.md``.
    Returns problem lines (``MISSING`` / ``DRIFT`` / ``STALE`` / ``UNKNOWN SLUG``);
    an empty list means success. Raises ``IconValidationError`` on malformed
    canonical inputs or structurally invalid generated output.
    """
    root = (ROOT if root is None else root).resolve()
    specs = COLLECTIONS if collections is None else tuple(collections)
    manifest, outputs = render_all(root=root, collections=specs)
    validate_outputs(outputs)

    tmp = root / "reference" / f"{TMP_DIR_PREFIX}{os.getpid()}"
    try:
        _validate_temp_sheets(outputs, tmp)
    finally:
        if tmp.exists():
            shutil.rmtree(tmp, ignore_errors=True)

    problems: list[str] = []
    for rel, content in sorted(outputs.items()):
        path = root / rel
        expected = content.replace("\r\n", "\n")
        if not path.is_file():
            problems.append(f"MISSING {rel}")
            continue
        existing = path.read_text(encoding="utf-8").replace("\r\n", "\n")
        if existing != expected:
            problems.append(f"DRIFT {rel}")

    planned_owned = {rel for rel in outputs if _is_under_owned(rel)}
    for rel in list_owned_files(root):
        if rel not in planned_owned:
            problems.append(f"STALE {rel}")

    known_slugs = {
        str(entry["slug"])
        for entry in manifest.get("icons") or []
        if entry.get("slug")
    }
    problems.extend(scan_icon_usage(root, known_slugs))
    return problems


def _print_generate_summary(
    manifest: dict[str, Any],
    stats: dict[str, int],
) -> None:
    n_icons = len(manifest["icons"])
    n_collections = len(manifest["collections"])
    print(f"ok {MANIFEST_REL} ({n_collections} collections, {n_icons} icons)")
    print(
        f"ok {SHEETS_REL}/ "
        f"({stats['sheets_total']} sheets, "
        f"{stats['sheets_written']} written, "
        f"{stats['sheets_unchanged']} unchanged)"
    )
    print(
        f"ok {ICONS_DIR_REL}/*.md "
        f"({stats['md_total']} files, "
        f"{stats['md_written']} written, "
        f"{stats['md_unchanged']} unchanged)"
    )
    print(f"ok {NOTICES_REL}")
    print(f"removed {stats['removed']} stale files")


def cmd_generate(root: Path | None = None) -> int:
    """CLI entry: regenerate icon reference artifacts. Returns a process exit code."""
    try:
        manifest, stats = generate(root=root)
    except IconValidationError as exc:
        for line in exc.errors:
            print(line, file=sys.stderr)
        return 1
    _print_generate_summary(manifest, stats)
    return 0


def cmd_check(root: Path | None = None) -> int:
    """CLI entry: drift / stale / usage gate. Returns a process exit code."""
    try:
        problems = check(root=root)
    except IconValidationError as exc:
        for line in exc.errors:
            print(line, file=sys.stderr)
        return 1

    if problems:
        for line in problems:
            print(line, file=sys.stderr)
        print(CHECK_REMEDIATE, file=sys.stderr)
        return 1

    print("ok icons")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate icon pack manifest, SVG contact sheets, and Markdown reference."
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("generate", help="Regenerate manifest, SVG sheets, and Markdown reference")
    sub.add_parser(
        "check",
        help="Fail if committed icon artifacts drift or Markdown uses unknown slugs",
    )
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    if args.command == "generate":
        return cmd_generate()
    if args.command == "check":
        return cmd_check()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
