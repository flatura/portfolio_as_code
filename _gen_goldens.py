"""One-shot helper to write tests/golden/*.svg; delete after use."""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, "scripts")
from icons import CollectionSpec, prepare_artifacts, render_preview_svg

tmp = Path("_tmp_golden_fixture")
pack = tmp / "docs/assets/mermaid-icons/demo.json"
pack.parent.mkdir(parents=True, exist_ok=True)
data = {
    "prefix": "demo",
    "info": {
        "name": "DEMO",
        "author": {"name": "Test", "url": "https://example.com"},
        "license": {"title": "CC0", "spdx": "CC0-1.0", "url": "https://example.com/license"},
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
pack.write_text(json.dumps(data), encoding="utf-8", newline="\n")
_, jobs = prepare_artifacts(
    root=tmp,
    collections=(CollectionSpec("demo", "docs/assets/mermaid-icons/demo.json"),),
)
golden = Path("tests/golden")
golden.mkdir(parents=True, exist_ok=True)
mapping = {
    "full-dims": "full-dims.svg",
    "collection-default": "collection-default.svg",
    "with-offsets": "offsets.svg",
    "weird-&-key": "sanitized-filename.svg",
}
for key, name in mapping.items():
    job = next(j for j in jobs if j.slug == f"demo:{key}")
    (golden / name).write_text(render_preview_svg(job), encoding="utf-8", newline="\n")
    print("wrote", name)
shutil.rmtree(tmp)
