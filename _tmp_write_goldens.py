"""Temporary helper to write sheet/index goldens; deleted after use."""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, "scripts")
from icons import (  # noqa: E402
    CollectionSpec,
    build_manifest,
    build_markdown_outputs,
    prepare_artifacts,
    render_sheet_svg,
)

GOLDEN = Path("tests/golden")
GOLDEN.mkdir(parents=True, exist_ok=True)

tmp = Path("_tmp_golden_sheet")
pack = tmp / "docs/assets/mermaid-icons/demo.json"
pack.parent.mkdir(parents=True, exist_ok=True)
pack.write_text(
    json.dumps(
        {
            "prefix": "demo",
            "info": {
                "name": "DEMO",
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
            "icons": {
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
            "aliases": {"alias-of-parent": {"parent": "parent-icon"}},
        }
    ),
    encoding="utf-8",
    newline="\n",
)
(tmp / "docs/assets/mermaid-icons/sources.json").write_text(
    "{}", encoding="utf-8", newline="\n"
)
_, plans = prepare_artifacts(
    root=tmp,
    collections=(CollectionSpec("demo", "docs/assets/mermaid-icons/demo.json"),),
)
assert len(plans) == 1
(GOLDEN / "demo-sheet.svg").write_text(
    render_sheet_svg(plans[0]), encoding="utf-8", newline="\n"
)
print("wrote demo-sheet.svg", len(plans[0].cells), "cells")
shutil.rmtree(tmp)

tmp = Path("_tmp_golden_md")
pack = tmp / "docs/assets/mermaid-icons/demo.json"
pack.parent.mkdir(parents=True, exist_ok=True)
pack.write_text(
    json.dumps(
        {
            "prefix": "demo",
            "info": {
                "name": "Demo Pack",
                "version": "1.0",
                "author": {
                    "name": "Fixture Author",
                    "url": "https://example.com/author",
                },
                "license": {
                    "title": "CC0",
                    "spdx": "CC0-1.0",
                    "url": "https://example.com/license",
                },
            },
            "lastModified": 1700000000,
            "width": 48,
            "height": 48,
            "icons": {
                "alpha": {
                    "body": '<path d="M0 0h1v1H0z"/>',
                    "width": 16,
                    "height": 16,
                },
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
            "aliases": {"alias-of-parent": {"parent": "parent-icon"}},
            "categories": {
                "First Group": ["bravo", "alpha"],
                "Second Group": ["weird-&-key", "parent-icon"],
            },
        }
    ),
    encoding="utf-8",
    newline="\n",
)
(tmp / "docs/assets/mermaid-icons/sources.json").write_text(
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
manifest = build_manifest(root=tmp, collections=specs)
outputs = build_markdown_outputs(manifest, root=tmp, collections=specs)
(GOLDEN / "demo-index.md").write_text(
    outputs["reference/icons/demo.md"], encoding="utf-8", newline="\n"
)
print("wrote demo-index.md")
shutil.rmtree(tmp)
