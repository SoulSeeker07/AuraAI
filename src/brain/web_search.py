from __future__ import annotations

import html
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from urllib.parse import parse_qs, quote_plus, urlencode, urlparse
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class WebSearchResult:
    title: str
    url: str
    snippet: str


class WebSearchClient:
    def __init__(
        self,
        timeout_seconds: float = 8.0,
        google_api_key: str = "",
        google_search_engine_id: str = "",
    ):
        self.timeout_seconds = timeout_seconds
        self.google_api_key = google_api_key
        self.google_search_engine_id = google_search_engine_id

    def search(self, query: str, limit: int = 5) -> list[WebSearchResult]:
        import logging

        logger = logging.getLogger(__name__)
        logger.info(f"[WebSearch] Search called for: '{query}' with limit={limit}")
        logger.info(
            f"[WebSearch] Google API configured: {bool(self.google_api_key and self.google_search_engine_id)}"
        )

        if self.google_api_key and self.google_search_engine_id:
            logger.info("[WebSearch] Attempting Google Custom Search")
            google_results = self._search_google_custom(query, limit)
            if google_results:
                logger.info(
                    f"[WebSearch] Google search returned {len(google_results)} results"
                )
                return google_results
            else:
                logger.info("[WebSearch] Google search returned no results")

        try:
            logger.info("[WebSearch] Attempting Google News Search")
            news_results = self._search_google_news(query, limit)
            if news_results:
                logger.info(
                    f"[WebSearch] Google news search returned {len(news_results)} results"
                )
                return news_results
            else:
                logger.info("[WebSearch] Google news search returned no results")
        except Exception as exc:
            logger.warning(f"[WebSearch] Google news search failed: {exc}")

        logger.info("[WebSearch] Attempting DuckDuckGo search")
        urls = (
            f"https://html.duckduckgo.com/html/?q={quote_plus(query)}",
            f"https://duckduckgo.com/html/?q={quote_plus(query)}",
        )
        headers = {
            "User-Agent": "Mozilla/5.0 AuraAI/0.1",
            "Accept": "text/html",
        }

        last_error: Exception | None = None
        for url in urls:
            try:
                logger.info(f"[WebSearch] Attempting DuckDuckGo URL: {url}")
                request = Request(url, headers=headers)
                with urlopen(request, timeout=self.timeout_seconds) as response:
                    body = response.read().decode("utf-8", errors="replace")
                results = self._parse_results(body, limit)
                if results:
                    logger.info(
                        f"[WebSearch] DuckDuckGo search returned {len(results)} results"
                    )
                    return results
                else:
                    logger.info("[WebSearch] DuckDuckGo search returned no results")
            except Exception as exc:
                last_error = exc
                logger.warning(f"[WebSearch] DuckDuckGo search failed: {exc}")

        if last_error is not None:
            logger.error(f"[WebSearch] All search methods failed: {last_error}")
            raise last_error
        logger.info("[WebSearch] No results returned from any search method")
        return []

    def _search_google_custom(self, query: str, limit: int) -> list[WebSearchResult]:
        params = urlencode(
            {
                "key": self.google_api_key,
                "cx": self.google_search_engine_id,
                "q": query,
                "num": max(1, min(limit, 10)),
            }
        )
        url = f"https://www.googleapis.com/customsearch/v1?{params}"
        headers = {
            "User-Agent": "AuraAI/0.1",
            "Accept": "application/json",
        }

        request = Request(url, headers=headers)
        with urlopen(request, timeout=self.timeout_seconds) as response:
            body = response.read().decode("utf-8", errors="replace")

        payload = json.loads(body)
        results: list[WebSearchResult] = []
        for item in payload.get("items", []):
            title = str(item.get("title", "")).strip()
            link = str(item.get("link", "")).strip()
            snippet = str(item.get("snippet", "")).strip()
            if title and link:
                results.append(WebSearchResult(title=title, url=link, snippet=snippet))
            if len(results) >= limit:
                break

        return results

    def _search_google_news(self, query: str, limit: int) -> list[WebSearchResult]:
        url = f"https://news.google.com/rss/search?q={quote_plus(query)}&hl=en-US&gl=US&ceid=US:en"
        headers = {
            "User-Agent": "Mozilla/5.0 AuraAI/0.1",
            "Accept": "application/rss+xml, application/xml, text/xml",
        }

        request = Request(url, headers=headers)
        with urlopen(request, timeout=self.timeout_seconds) as response:
            body = response.read().decode("utf-8", errors="replace")

        root = ET.fromstring(body)
        results: list[WebSearchResult] = []
        for item in root.findall("./channel/item"):
            title = self._clean_html(item.findtext("title", default=""))
            link = self._clean_google_news_url(item.findtext("link", default=""))
            description = self._clean_html(item.findtext("description", default=""))
            published = item.findtext("pubDate", default="").strip()
            snippet = f"{description} Published: {published}".strip()
            if title and link:
                results.append(WebSearchResult(title=title, url=link, snippet=snippet))
            if len(results) >= limit:
                break

        return results

    def _parse_results(self, body: str, limit: int) -> list[WebSearchResult]:
        results: list[WebSearchResult] = []
        block_pattern = re.compile(
            r'<div class="result(?: results_links.*?)?".*?</div>\s*</div>', re.DOTALL
        )
        title_pattern = re.compile(
            r'<a[^>]*class="result__a"[^>]*href="(?P<url>.*?)"[^>]*>(?P<title>.*?)</a>',
            re.DOTALL,
        )
        snippet_pattern = re.compile(
            r'<a[^>]*class="result__snippet"[^>]*>(?P<snippet>.*?)</a>', re.DOTALL
        )

        for block in block_pattern.findall(body):
            title_match = title_pattern.search(block)
            if not title_match:
                continue

            snippet_match = snippet_pattern.search(block)
            title = self._clean_html(title_match.group("title"))
            url = self._clean_url(html.unescape(title_match.group("url")))
            snippet = (
                self._clean_html(snippet_match.group("snippet"))
                if snippet_match
                else ""
            )
            if title and url:
                results.append(WebSearchResult(title=title, url=url, snippet=snippet))
            if len(results) >= limit:
                break

        if results:
            return results

        fallback_pattern = re.compile(
            r'<a[^>]*class="result__a"[^>]*href="(?P<url>.*?)"[^>]*>(?P<title>.*?)</a>',
            re.DOTALL,
        )
        for match in fallback_pattern.finditer(body):
            title = self._clean_html(match.group("title"))
            url = self._clean_url(html.unescape(match.group("url")))
            if title and url:
                results.append(WebSearchResult(title=title, url=url, snippet=""))
            if len(results) >= limit:
                break

        return results

    def _clean_html(self, text: str) -> str:
        text = re.sub(r"<.*?>", "", text)
        return html.unescape(text).strip()

    def _clean_url(self, url: str) -> str:
        parsed = urlparse(url)
        if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
            target = parse_qs(parsed.query).get("uddg", [""])[0]
            return target or url
        return url

    def _clean_google_news_url(self, url: str) -> str:
        parsed = urlparse(url)
        if "news.google.com" not in parsed.netloc:
            return url

        target = parse_qs(parsed.query).get("url", [""])[0]
        return target or url
