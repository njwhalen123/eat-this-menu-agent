"""A restaurant's saved pages ("capture set").

Layout of one restaurant folder:

    manifest.json
    captures/<files>

manifest.json:

    {
      "restaurant_id": "P1",
      "display_name": "Quillfeather Tavern",      # optional; never sent anywhere
      "fictional": true,
      "menu_scope": "every food section",
      "captures": [
        {"capture_id": "P1-C1", "url": "https://quillfeather.example/menu/",
         "kind": "html" | "pdf", "path": "captures/menu.html",
         "sha256": "<hex>", "retrieved_at": "2026-11-25", "role": "menu"}
      ]
    }

The loader checks each file's hash against the manifest, so a run always
names exactly the bytes it read. The real captures store may use another
layout; an adapter maps it onto this one.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field

from .extract import Extracted, html_to_lines, pdf_to_lines
from .text import SearchableText


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class Capture:
    capture_id: str
    url: str
    kind: str
    path: str
    sha256: str
    retrieved_at: str
    role: str
    ex: Extracted
    _search: SearchableText | None = field(default=None, repr=False)

    @property
    def lines(self) -> list[str]:
        return self.ex.lines

    @property
    def search(self) -> SearchableText:
        if self._search is None:
            self._search = SearchableText(self.ex.lines)
        return self._search

    def line_label(self, n: int) -> str:
        """1-based line number as shown to readers, with the PDF page."""
        if self.ex.line_pages:
            return f"p{self.ex.line_pages[n - 1]} L{n:04d}"
        return f"L{n:04d}"


@dataclass
class CaptureSet:
    root: str
    restaurant_id: str
    menu_scope: str
    fictional: bool
    captures: dict[str, Capture]

    def by_url(self) -> dict[str, str]:
        return {c.url.rstrip("/"): cid for cid, c in self.captures.items()}


class CaptureError(Exception):
    pass


def load(root: str, verify: bool = True) -> CaptureSet:
    with open(os.path.join(root, "manifest.json"), encoding="utf-8") as f:
        m = json.load(f)
    caps: dict[str, Capture] = {}
    for c in m["captures"]:
        path = os.path.join(root, c["path"])
        if verify:
            got = sha256_file(path)
            if got != c["sha256"]:
                raise CaptureError(f"{c['capture_id']}: hash {got} does not match manifest {c['sha256']}")
        if c["kind"] == "html":
            with open(path, encoding="utf-8", errors="replace") as f:
                ex = html_to_lines(f.read(), base_url=c["url"])
        elif c["kind"] == "pdf":
            ex = pdf_to_lines(path)
        else:
            raise CaptureError(f"{c['capture_id']}: unknown kind {c['kind']!r}")
        caps[c["capture_id"]] = Capture(
            capture_id=c["capture_id"], url=c["url"], kind=c["kind"], path=c["path"],
            sha256=c["sha256"], retrieved_at=c.get("retrieved_at", ""), role=c.get("role", "menu"), ex=ex,
        )
    return CaptureSet(root=root, restaurant_id=m["restaurant_id"], menu_scope=m.get("menu_scope", ""),
                      fictional=bool(m.get("fictional", False)), captures=caps)
