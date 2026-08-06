"""Temporary smoke test for icons check; delete after run."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))

from icons import CollectionSpec, check, generate  # noqa: E402

root = Path(tempfile.mkdtemp(prefix="icons-check-"))
try:
    pack = root / "docs/assets/mermaid-icons/demo.json"
    pack.parent.mkdir(parents=True)
    pack.write_text(
        json.dumps(
            {
                "prefix": "demo",
                "width": 48,
                "height": 48,
                "info": {
                    "name": "Demo",
                    "author": {"name": "T", "url": "https://e.com"},
                    "license": {
                        "title": "CC0",
                        "spdx": "CC0-1.0",
                        "url": "https://e.com",
                    },
                },
                "lastModified": 1700000000,
                "icons": {
                    "alpha": {"body": '<path d="M0 0h48v48H0z"/>'},
                    "bravo": {"body": '<path d="M0 0h48v48H0z"/>'},
                },
            }
        ),
        encoding="utf-8",
        newline="\n",
    )
    specs = (CollectionSpec("demo", "docs/assets/mermaid-icons/demo.json"),)
    generate(root=root, collections=specs)

    problems = check(root=root, collections=specs)
    assert problems == [], problems

    sheet = next((root / "reference/icons/sheets").glob("*.svg"))
    sheet.write_text(sheet.read_text(encoding="utf-8") + " ", encoding="utf-8", newline="\n")
    problems = check(root=root, collections=specs)
    assert any(p.startswith("DRIFT ") for p in problems), problems
    generate(root=root, collections=specs)

    sheet = next((root / "reference/icons/sheets").glob("*.svg"))
    rel = sheet.relative_to(root).as_posix()
    sheet.unlink()
    problems = check(root=root, collections=specs)
    assert f"MISSING {rel}" in problems, problems
    generate(root=root, collections=specs)

    stale = root / "reference/icons/sheets/zzz.svg"
    stale.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg"/>',
        encoding="utf-8",
        newline="\n",
    )
    problems = check(root=root, collections=specs)
    assert "STALE reference/icons/sheets/zzz.svg" in problems, problems
    generate(root=root, collections=specs)

    docs = root / "docs/en/x.md"
    docs.parent.mkdir(parents=True)
    docs.write_text(
        "# t\n"
        "```mermaid\n"
        "architecture-beta\n"
        "    service a(demo:nope)[X]\n"
        "    service b(demo:alpha)[Y]\n"
        "```\n",
        encoding="utf-8",
        newline="\n",
    )
    problems = check(root=root, collections=specs)
    assert any("UNKNOWN SLUG docs/en/x.md:4 demo:nope" in p for p in problems), problems
    assert not any(p.startswith("UNKNOWN SLUG reference/") for p in problems), problems

    generate(root=root, collections=specs)
    for path in (root / "reference/icons").rglob("*"):
        if path.is_file():
            text = path.read_text(encoding="utf-8").replace("\n", "\r\n")
            path.write_bytes(text.encode("utf-8"))
    notices = root / "THIRD_PARTY_NOTICES.md"
    if notices.is_file():
        text = notices.read_text(encoding="utf-8").replace("\n", "\r\n")
        notices.write_bytes(text.encode("utf-8"))
    docs.unlink()
    problems = check(root=root, collections=specs)
    assert problems == [], problems

    print("fixture check ok")
finally:
    shutil.rmtree(root, ignore_errors=True)
