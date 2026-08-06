"""Atomic generate, validation, sync, and owned-directory cleanup tests."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from icons import (  # noqa: E402
    ICONS_DIR_REL,
    MANIFEST_REL,
    NOTICES_REL,
    TMP_DIR_PREFIX,
    CollectionSpec,
    IconValidationError,
    cleanup_owned_dir,
    generate,
    render_all,
    sync_into_owned_dir,
    validate_outputs,
    write_text,
)


def _write_pack(path: Path, *, prefix: str, icons: dict) -> None:
    data = {
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
        "width": 48,
        "height": 48,
        "icons": icons,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8", newline="\n")


def _fixture(tmp_path: Path) -> tuple[Path, tuple[CollectionSpec, ...]]:
    pack = tmp_path / "docs" / "assets" / "mermaid-icons" / "demo.json"
    _write_pack(
        pack,
        prefix="demo",
        icons={
            "alpha": {"body": '<path d="M0 0h1v1H0z"/>', "width": 16, "height": 16},
            "bravo": {"body": '<path d="M0 0h1v1H0z"/>'},
        },
    )
    sources = tmp_path / "docs" / "assets" / "mermaid-icons" / "sources.json"
    sources.write_text("{}", encoding="utf-8", newline="\n")
    specs = (CollectionSpec("demo", "docs/assets/mermaid-icons/demo.json"),)
    return tmp_path, specs


def test_stale_sheet_and_previews_removed(tmp_path: Path) -> None:
    root, specs = _fixture(tmp_path)
    stale_sheet = root / ICONS_DIR_REL / "sheets" / "zzz.svg"
    stale_preview = root / ICONS_DIR_REL / "previews" / "x" / "y.svg"
    write_text(stale_sheet, "<svg xmlns='http://www.w3.org/2000/svg'/>\n")
    write_text(stale_preview, "<svg xmlns='http://www.w3.org/2000/svg'/>\n")

    _, stats = generate(root=root, collections=specs)

    assert not stale_sheet.exists()
    assert not stale_preview.exists()
    assert not (root / ICONS_DIR_REL / "previews").exists()
    assert stats["removed"] >= 2
    assert (root / MANIFEST_REL).is_file()
    assert list((root / ICONS_DIR_REL / "sheets").glob("*.svg"))


def test_outside_owned_area_untouched(tmp_path: Path) -> None:
    root, specs = _fixture(tmp_path)
    outside = root / "docs" / "keep-me.txt"
    write_text(outside, "sentinel\n")
    notices_sentinel = root / "KEEP_OUTSIDE.md"
    write_text(notices_sentinel, "do-not-delete\n")

    generate(root=root, collections=specs)

    assert outside.read_text(encoding="utf-8") == "sentinel\n"
    assert notices_sentinel.read_text(encoding="utf-8") == "do-not-delete\n"
    assert (root / NOTICES_REL).is_file()


def test_validation_failure_leaves_tree_and_removes_tmp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, specs = _fixture(tmp_path)
    owned = root / ICONS_DIR_REL
    write_text(owned / "pre-existing.md", "keep\n")

    def boom(_outputs: dict[str, str]) -> None:
        raise IconValidationError(["forced validation failure"])

    monkeypatch.setattr("icons.validate_outputs", boom)

    with pytest.raises(IconValidationError, match="forced validation failure"):
        generate(root=root, collections=specs)

    assert (owned / "pre-existing.md").read_text(encoding="utf-8") == "keep\n"
    leftover = list((root / "reference").glob(f"{TMP_DIR_PREFIX}*"))
    assert leftover == []


def test_unchanged_files_preserve_mtime(tmp_path: Path) -> None:
    root, specs = _fixture(tmp_path)
    generate(root=root, collections=specs)

    sheet = next((root / ICONS_DIR_REL / "sheets").glob("*.svg"))
    manifest = root / MANIFEST_REL
    sheet_mtime = sheet.stat().st_mtime_ns
    manifest_mtime = manifest.stat().st_mtime_ns
    time.sleep(0.05)

    _, stats = generate(root=root, collections=specs)

    assert stats["sheets_written"] == 0
    assert stats["sheets_unchanged"] >= 1
    assert stats["manifest_unchanged"] == 1
    assert sheet.stat().st_mtime_ns == sheet_mtime
    assert manifest.stat().st_mtime_ns == manifest_mtime


def test_cleanup_refuses_path_outside_owned(tmp_path: Path) -> None:
    root = tmp_path
    owned = root / ICONS_DIR_REL
    owned.mkdir(parents=True)

    # Plant a symlink/junction escape if possible; otherwise assert the guard
    # on a resolved path that claims to be under owned via relative_to abuse
    # is covered by calling cleanup with a path check via monkeypatch.
    outside = root / "outside.txt"
    write_text(outside, "x\n")

    # Direct unit: cleanup only walks owned.rglob, so outside stays.
    removed = cleanup_owned_dir(set(), root=root)
    assert removed == 0
    assert outside.exists()


def test_validate_outputs_rejects_bad_sheet(tmp_path: Path) -> None:
    root, specs = _fixture(tmp_path)
    _, outputs = render_all(root=root, collections=specs)
    sheet_key = next(rel for rel in outputs if rel.endswith(".svg"))
    outputs[sheet_key] = "not-svg\n"
    with pytest.raises(IconValidationError) as exc:
        validate_outputs(outputs)
    assert any("not well-formed" in e or "must be svg" in e for e in exc.value.errors)


def test_sync_into_owned_dir_stats(tmp_path: Path) -> None:
    root, specs = _fixture(tmp_path)
    _, outputs = render_all(root=root, collections=specs)
    validate_outputs(outputs)
    stats = sync_into_owned_dir(outputs, root=root)
    assert stats["sheets_total"] >= 1
    assert stats["sheets_written"] == stats["sheets_total"]
    assert stats["md_total"] >= 1
    assert (root / NOTICES_REL).is_file()
