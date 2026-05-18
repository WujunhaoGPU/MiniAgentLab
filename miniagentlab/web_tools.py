from __future__ import annotations

import re
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote_plus, unquote, urljoin, urlparse
from urllib.request import Request, url2pathname, urlopen


_DEFAULT_SEARCH_URL = "https://duckduckgo.com/html/?q={query}"
_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]")
_SENTENCE_PATTERN = re.compile(r"[^.!?\n\u3002\uff01\uff1f]+[.!?\u3002\uff01\uff1f]?")
_STOPWORDS = {"a", "an", "and", "are", "as", "does", "do", "for", "in", "is", "of", "the", "to", "what"}


def search_web(query: str, max_results: int = 5, search_url: str | None = None) -> list[dict[str, Any]]:
    """Search the web and return lightweight result records."""
    if max_results < 1:
        raise ValueError("max_results must be at least 1")
    if not query.strip():
        raise ValueError("query must not be empty")

    resolved_search_url = search_url or _DEFAULT_SEARCH_URL.format(query=quote_plus(query))
    html = _read_url_or_file(resolved_search_url)
    parser = SearchResultParser(base_url=resolved_search_url)
    parser.feed(html)

    results = parser.results[:max_results]
    if not results:
        raise ValueError("No search results found")
    return results


def fetch_page(url: str, timeout: int = 10) -> dict[str, Any]:
    """Fetch a local or remote HTML page."""
    if timeout < 1:
        raise ValueError("timeout must be at least 1")

    html = _read_url_or_file(url, timeout=timeout)
    title = _extract_title(html)
    return {
        "url": url,
        "title": title,
        "html": html,
    }


def extract_text(page: dict[str, Any] | str) -> dict[str, Any]:
    """Extract readable text from an HTML page object or raw HTML string."""
    if isinstance(page, dict):
        html = str(page.get("html", ""))
        url = str(page.get("url", ""))
        title = str(page.get("title", "")) or _extract_title(html)
    else:
        html = page
        url = ""
        title = _extract_title(html)

    parser = ReadableTextParser()
    parser.feed(html)
    text = _normalize_space(" ".join(parser.text_parts))
    return {
        "url": url,
        "title": title,
        "text": text,
    }


def summarize_text(text: dict[str, Any] | str, query: str, max_sentences: int = 3) -> dict[str, Any]:
    """Summarize text by selecting query-relevant sentences."""
    if max_sentences < 1:
        raise ValueError("max_sentences must be at least 1")

    if isinstance(text, dict):
        content = str(text.get("text", ""))
        source = {
            "url": text.get("url", ""),
            "title": text.get("title", ""),
        }
    else:
        content = text
        source = {}

    query_terms = _meaningful_terms(query)
    ranked = _rank_sentences(content, query_terms)
    selected = [sentence for _, sentence in ranked[:max_sentences]]
    if not selected and content.strip():
        selected = [content.strip()[:500]]

    return {
        "summary": " ".join(selected).strip(),
        "source": source,
    }


class SearchResultParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.results: list[dict[str, Any]] = []
        self._in_link = False
        self._current_href = ""
        self._current_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        attrs_dict = {key: value or "" for key, value in attrs}
        href = attrs_dict.get("href", "")
        css_class = attrs_dict.get("class", "")
        if "result__a" not in css_class and not attrs_dict.get("data-result"):
            return
        self._in_link = True
        self._current_href = href
        self._current_text = []

    def handle_data(self, data: str) -> None:
        if self._in_link:
            self._current_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or not self._in_link:
            return
        title = _normalize_space(" ".join(self._current_text))
        url = _normalize_result_url(self._current_href, self.base_url)
        if title and url and not any(result["url"] == url for result in self.results):
            self.results.append({"title": title, "url": url})
        self._in_link = False
        self._current_href = ""
        self._current_text = []


class ReadableTextParser(HTMLParser):
    _SKIP_TAGS = {"script", "style", "noscript"}
    _BLOCK_TAGS = {"article", "div", "h1", "h2", "h3", "li", "main", "p", "section"}

    def __init__(self) -> None:
        super().__init__()
        self.text_parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in self._SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self._SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
        if tag.lower() in self._BLOCK_TAGS and not self._skip_depth:
            self.text_parts.append(".")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = _normalize_space(data)
        if text:
            self.text_parts.append(unescape(text))


def _read_url_or_file(location: str, timeout: int = 10) -> str:
    parsed = urlparse(location)
    if parsed.scheme in {"http", "https"}:
        request = Request(location, headers={"User-Agent": "MiniAgentLab/0.1"})
        with urlopen(request, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="replace")

    if parsed.scheme == "file":
        path = Path(url2pathname(unquote(parsed.path)))
    else:
        path = Path(location)

    if not path.exists():
        raise FileNotFoundError(f"Page not found: {location}")
    return path.read_text(encoding="utf-8")


def _extract_title(html: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
    if match is None:
        return ""
    return _normalize_space(unescape(match.group(1)))


def _normalize_result_url(href: str, base_url: str) -> str:
    href = unescape(href)
    if href.startswith("//"):
        return f"https:{href}"

    parsed = urlparse(href)
    if parsed.path == "/l/":
        query = parse_qs(parsed.query)
        if "uddg" in query and query["uddg"]:
            return query["uddg"][0]

    if parsed.scheme in {"http", "https", "file"}:
        return href
    return urljoin(base_url, href)


def _rank_sentences(text: str, query_terms: set[str]) -> list[tuple[float, str]]:
    ranked: list[tuple[float, str]] = []
    for match in _SENTENCE_PATTERN.finditer(text):
        sentence = _normalize_space(match.group(0))
        if not sentence:
            continue
        sentence_terms = set(_tokenize(sentence))
        if len(sentence_terms) < 3:
            continue
        shared_terms = sentence_terms & query_terms
        if not shared_terms:
            continue
        score = len(shared_terms) / max(len(sentence_terms), 1) ** 0.5
        ranked.append((score, sentence))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return ranked


def _tokenize(text: str) -> list[str]:
    return [_normalize_token(match.group(0)) for match in _TOKEN_PATTERN.finditer(text)]


def _normalize_token(token: str) -> str:
    lowered = token.lower()
    if lowered.isascii() and len(lowered) > 3 and lowered.endswith("s"):
        return lowered[:-1]
    return lowered


def _meaningful_terms(text: str) -> set[str]:
    terms = set(_tokenize(text))
    filtered = {term for term in terms if term not in _STOPWORDS}
    return filtered or terms


def _normalize_space(text: str) -> str:
    return " ".join(text.split())
