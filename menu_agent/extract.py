"""Turn a saved page into numbered text lines.

The agent and the baseline both read pages only through this module, so a
difference between them comes from what they do with the lines, not from
reading the page differently (method §7 rule 1).

- HTML: visible and hidden text alike (tabbed menus keep every panel in the
  page), scripts and styles dropped, block elements become line breaks.
  Images are listed (file name and alt text) but never read.
- PDF: the text layer, page by page. A page with no text layer yields no
  lines, and the capture reports it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urljoin

from .text import clean_line

BLOCK_TAGS = {
    "address", "article", "aside", "blockquote", "body", "caption", "dd", "details",
    "dialog", "div", "dl", "dt", "fieldset", "figcaption", "figure", "footer", "form",
    "h1", "h2", "h3", "h4", "h5", "h6", "header", "hr", "li", "main", "nav", "ol",
    "p", "pre", "section", "summary", "table", "tbody", "td", "tfoot", "th", "thead",
    "tr", "ul", "button", "label", "option", "select",
}
DROP_TAGS = {"script", "style", "noscript", "template", "svg", "canvas", "iframe", "head"}
_SPACE_BEFORE_PUNCT = re.compile(r"\s+([,.;:!?)\]])")
_SPACE_AFTER_OPEN = re.compile(r"([(\[])\s+")


@dataclass
class Extracted:
    lines: list[str]
    line_pages: list[int] = field(default_factory=list)   # PDF page per line (1-based); empty for HTML
    title: str = ""
    images: list[dict] = field(default_factory=list)       # {"src", "alt"}
    links: list[dict] = field(default_factory=list)        # {"text", "url"}
    pages: int = 1
    pages_without_text: list[int] = field(default_factory=list)


def _tidy(line: str) -> str:
    line = clean_line(line)
    line = _SPACE_BEFORE_PUNCT.sub(r"\1", line)
    line = _SPACE_AFTER_OPEN.sub(r"\1", line)
    return line


def html_to_lines(html: str, base_url: str = "") -> Extracted:
    from bs4 import BeautifulSoup, NavigableString

    soup = BeautifulSoup(html, "html.parser")
    title = clean_line(soup.title.get_text()) if soup.title else ""
    images = [
        {"src": urljoin(base_url, im.get("src", "")), "alt": clean_line(im.get("alt", ""))}
        for im in soup.find_all("img")
    ]
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        links.append({"text": clean_line(a.get_text(" ")), "url": urljoin(base_url, href)})
    for t in soup.find_all(list(DROP_TAGS)):
        t.decompose()
    for br in soup.find_all("br"):
        br.replace_with(NavigableString("\n"))
    for t in soup.find_all(list(BLOCK_TAGS)):
        t.insert_before(NavigableString("\n"))
        t.insert_after(NavigableString("\n"))
    root = soup.body or soup
    raw = root.get_text(" ")
    lines = [_tidy(x) for x in raw.split("\n")]
    return Extracted(lines=[x for x in lines if x], title=title, images=images, links=links)


def pdf_to_lines(path: str) -> Extracted:
    import pdfplumber

    lines: list[str] = []
    pages: list[int] = []
    empty: list[int] = []
    with pdfplumber.open(path) as pdf:
        n = len(pdf.pages)
        for pi, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            page_lines = [_tidy(x) for x in text.split("\n")]
            page_lines = [x for x in page_lines if x]
            if not page_lines:
                empty.append(pi)
            lines += page_lines
            pages += [pi] * len(page_lines)
        title = clean_line((pdf.metadata or {}).get("Title", "") or "")
    return Extracted(lines=lines, line_pages=pages, title=title, pages=n, pages_without_text=empty)
