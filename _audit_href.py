import json
import re

p = "docs/assets/mermaid-icons/logos.json"
d = json.load(open(p, encoding="utf-8"))
href_re = re.compile(r"(?:xlink:)?href\s*=\s*(['\"])(.*?)\1", re.I)
use_re = re.compile(r"<use\b", re.I)
image_re = re.compile(r"<image\b", re.I)
a_re = re.compile(r"<a\s", re.I)
for label, cre in [("use", use_re), ("image", image_re), ("a", a_re)]:
    keys = [k for k, v in d["icons"].items() if cre.search(v.get("body", ""))]
    print(label, len(keys), keys[:5])
bad_href = []
frag_href = 0
for k, v in d["icons"].items():
    for m in href_re.finditer(v.get("body", "")):
        val = m.group(2)
        if val.startswith("#"):
            frag_href += 1
        else:
            bad_href.append((k, val))
print("frag_href attrs", frag_href, "bad", bad_href[:10], "badcount", len(bad_href))
