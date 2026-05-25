"""Web search via DuckDuckGo HTML (no API key)."""
from __future__ import annotations

import json
import re
import threading
import time
from html.parser import HTMLParser
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

DDG_HTML_URL = "https://html.duckduckgo.com/html/"
_DDG_LOCK = threading.Lock()
_DDG_LAST_REQUEST = 0.0
_DDG_MIN_INTERVAL = 2.0
_CAPTCHA_MARKERS = ("challenge-form", "cc=botnet", "anomaly-modal", "Please try again")
_MAX_RETRIES = 3
_RETRY_BACKOFF = 3.0
_USER_AGENT = "macro-maintainer/1.0"


class _DuckDuckGoParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.results: list[dict[str, str]] = []
        self._current: dict[str, str] = {}
        self._capture: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_dict = dict(attrs)
        cls = attr_dict.get("class", "") or ""
        if tag == "a" and "result__a" in cls:
            self._flush()
            href = attr_dict.get("href", "")
            if href:
                self._current["url"] = href
            self._capture = "title"
            self._current.setdefault("title", "")
        if tag == "a" and "result__snippet" in cls:
            self._capture = "snippet"
            self._current.setdefault("snippet", "")

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._capture in ("title", "snippet"):
            self._capture = None

    def handle_data(self, data: str) -> None:
        if self._capture == "title":
            self._current["title"] = self._current.get("title", "") + data
        elif self._capture == "snippet":
            self._current["snippet"] = self._current.get("snippet", "") + data

    def _flush(self) -> None:
        if self._current.get("url") and self._current.get("title"):
            self.results.append(self._current)
        self._current = {}

    def close(self) -> None:
        self._flush()
        super().close()


def _parse_ddg_results(html: str) -> list[dict[str, str]]:
    parser = _DuckDuckGoParser()
    parser.feed(html)
    parser.close()
    if parser.results:
        return parser.results
    results: list[dict[str, str]] = []
    for match in re.finditer(
        r'class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
        html,
        re.DOTALL,
    ):
        url, title_html = match.group(1), match.group(2)
        title = re.sub(r"<[^>]+>", "", title_html).strip()
        if url and title:
            results.append({"url": url, "title": title, "snippet": ""})
    for i, match in enumerate(
        re.finditer(
            r'class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</a>',
            html,
            re.DOTALL,
        )
    ):
        snippet = re.sub(r"<[^>]+>", "", match.group(1)).strip()
        if i < len(results):
            results[i]["snippet"] = snippet
    return results


def _is_captcha(html: str) -> bool:
    for marker in _CAPTCHA_MARKERS:
        if marker in html:
            return True
    if len(html) < 2000 and "result__a" not in html:
        return True
    return False


def _fetch_ddg_html(query: str) -> str:
    global _DDG_LAST_REQUEST  # noqa: PLW0603
    last_error: Exception | None = None
    for attempt in range(1, _MAX_RETRIES + 1):
        with _DDG_LOCK:
            now = time.monotonic()
            wait = _DDG_MIN_INTERVAL - (now - _DDG_LAST_REQUEST)
            if wait > 0:
                time.sleep(wait)
            _DDG_LAST_REQUEST = time.monotonic()
        form_data = urlencode({"q": query}).encode("utf-8")
        req = Request(
            DDG_HTML_URL,
            data=form_data,
            headers={
                "User-Agent": _USER_AGENT,
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "text/html",
                "Accept-Language": "en-US,en;q=0.9",
            },
            method="POST",
        )
        try:
            with urlopen(req, timeout=20.0) as resp:
                charset = resp.headers.get_content_charset() or "utf-8"
                html = resp.read().decode(charset, errors="replace")
        except (HTTPError, URLError, TimeoutError) as exc:
            last_error = exc
            if attempt >= _MAX_RETRIES:
                break
            time.sleep(_RETRY_BACKOFF * attempt)
            continue
        if _is_captcha(html):
            if attempt >= _MAX_RETRIES:
                raise RuntimeError(f"DDG CAPTCHA or block after {_MAX_RETRIES} retries")
            time.sleep(_RETRY_BACKOFF * attempt)
            continue
        return html
    raise RuntimeError(f"DuckDuckGo search failed: {last_error}")


def search_web(query: str, count: int = 10, offset: int = 0) -> list[dict[str, str]]:
    query = (query or "").strip()
    if not query:
        return []
    html = _fetch_ddg_html(query)
    parsed = _parse_ddg_results(html)
    end = offset + max(1, min(count, 20))
    return parsed[offset:end]


def format_results_text(query: str, results: list[dict[str, str]]) -> str:
    if not results:
        return "No results found."
    formatted = []
    for i, item in enumerate(results, 1):
        title = item.get("title", "No title")
        url = item.get("url", "")
        description = item.get("snippet", "")
        formatted.append(f"{i}. {title}\n   URL: {url}\n   Description: {description}")
    header = f"Search results for '{query}' ({len(results)} results):\n\n"
    return header + "\n\n".join(formatted)


def format_results_json(results: list[dict[str, str]]) -> str:
    return json.dumps(results, ensure_ascii=False, indent=2)
