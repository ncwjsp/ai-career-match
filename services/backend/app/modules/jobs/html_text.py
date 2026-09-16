"""Stdlib-only HTML text extraction for fetched job postings. Owner: M2 (B-02).

No BeautifulSoup/lxml: promoting either to a runtime dependency needs M3
coordination (see docs/job-sources/REGISTER.md's note on `fetch.py` for the
same rule applied to `httpx`), and a bounded single-purpose parser is enough
for two narrow jobs -- strip markup down to visible text, and pull out a
schema.org `JobPosting` block from an `application/ld+json` tag when the host
embeds one. Most ATS-hosted boards do, including Greenhouse.
"""

from __future__ import annotations

import json
import re
from html.parser import HTMLParser

_SKIP_TAGS = frozenset({"script", "style", "noscript", "template"})


class _PageTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._in_title = False
        self.body_chunks: list[str] = []
        self.title_chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
        elif tag == "title":
            self._in_title = True
        elif tag in ("br", "p", "div", "li", "tr"):
            self.body_chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._in_title:
            self.title_chunks.append(data)
        else:
            self.body_chunks.append(data)


def extract_visible_text(html: str) -> str:
    """Strip tags/scripts/styles; collapse runs of whitespace."""
    parser = _PageTextParser()
    parser.feed(html)
    parser.close()
    text = "".join(parser.body_chunks)
    text = re.sub(r"[ \t\f\v]+", " ", text)
    text = re.sub(r" *\n[ \n]*", "\n", text)
    return text.strip()


def extract_title_tag(html: str) -> str | None:
    """The document's `<title>` text, or None if there isn't one."""
    parser = _PageTextParser()
    parser.feed(html)
    parser.close()
    title = "".join(parser.title_chunks).strip()
    return title or None


_JSON_LD_BLOCK_RE = re.compile(
    r'<script[^>]*\btype\s*=\s*["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)


def extract_json_ld_jobposting(html: str) -> dict | None:
    """The first schema.org `JobPosting` object in an `application/ld+json` tag.

    Handles a bare object, a list of objects, and a `@graph` wrapper -- the
    three shapes JSON-LD producers commonly use. Returns None if no block
    parses as JSON or none of its nodes declare `"@type": "JobPosting"`.
    """
    for raw_block in _JSON_LD_BLOCK_RE.findall(html):
        try:
            data = json.loads(raw_block.strip())
        except (json.JSONDecodeError, ValueError):
            continue
        for node in _flatten_json_ld(data):
            if _is_job_posting(node):
                return node
    return None


def _flatten_json_ld(data):
    if isinstance(data, list):
        for item in data:
            yield from _flatten_json_ld(item)
    elif isinstance(data, dict):
        yield data
        graph = data.get("@graph")
        if isinstance(graph, list):
            yield from _flatten_json_ld(graph)


def _is_job_posting(node: dict) -> bool:
    node_type = node.get("@type")
    if isinstance(node_type, list):
        return "JobPosting" in node_type
    return node_type == "JobPosting"
