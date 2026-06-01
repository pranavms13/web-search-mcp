#!/usr/bin/env python3
"""
MCP Web Search Server
A Model Context Protocol server that provides web search functionality using a headless browser
to scrape search results from multiple search engines with fallback support.

Two interchangeable browser backends are supported:
  - "selenium": Selenium + headless Chrome (default)
  - "obscura":  Obscura headless browser via its CLI (https://github.com/h4ckf0r0day/obscura)

Select the backend with the BROWSER_BACKEND environment variable. If "obscura" is
requested but the binary is not found on PATH (or at OBSCURA_BIN), the server logs a
warning and falls back to Selenium.
"""

import logging
import os
import shutil
import subprocess
import time
from typing import Any, Dict, List, Optional, Tuple
import base64
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup, Tag

from fastmcp import FastMCP

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize MCP server
mcp = FastMCP("Web Search MCP")


class BrowserBackend:
    """Abstract browser backend that renders a URL and returns its HTML + title."""

    name = "abstract"

    def fetch_html(self, url: str, wait_until: str = "networkidle0", timeout: int = 20) -> Tuple[str, str]:
        """Render `url` and return a (html, title) tuple."""
        raise NotImplementedError

    def close(self) -> None:
        """Release any resources held by the backend."""
        pass


class SeleniumBackend(BrowserBackend):
    """Renders pages with a lazily-initialized headless Chrome driver."""

    name = "selenium"

    def __init__(self) -> None:
        self.driver: Optional[webdriver.Chrome] = None

    def _ensure_driver(self) -> webdriver.Chrome:
        if self.driver is not None:
            return self.driver
        chrome_options = Options()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)
        chrome_options.add_argument(
            "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        logger.info("Chrome driver initialized successfully")
        return self.driver

    def fetch_html(self, url: str, wait_until: str = "networkidle0", timeout: int = 20) -> Tuple[str, str]:
        driver = self._ensure_driver()
        driver.get(url)
        # Give JS-rendered pages a moment, then wait for the body to be present.
        time.sleep(2)
        try:
            WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
        except Exception:
            pass
        return driver.page_source, driver.title or ""

    def close(self) -> None:
        if self.driver is not None:
            try:
                self.driver.quit()
                logger.info("Chrome driver closed")
            except Exception as e:
                logger.error(f"Error closing driver: {e}")
            finally:
                self.driver = None


class ObscuraBackend(BrowserBackend):
    """Renders pages by shelling out to the Obscura CLI.

    See https://github.com/h4ckf0r0day/obscura. We use:
        obscura fetch <url> --dump html [--wait-until <state>] [--timeout <s>]
    which returns the fully JS-rendered HTML on stdout.
    """

    name = "obscura"

    def __init__(self, binary: str) -> None:
        self.binary = binary

    def fetch_html(self, url: str, wait_until: str = "networkidle0", timeout: int = 20) -> Tuple[str, str]:
        cmd = [self.binary, "fetch", url, "--dump", "html"]
        if wait_until:
            cmd += ["--wait-until", wait_until]
        if timeout:
            cmd += ["--timeout", str(timeout)]

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout + 15,
            )
        except subprocess.TimeoutExpired as e:
            raise Exception(f"Obscura timed out fetching {url}") from e

        if proc.returncode != 0:
            err = (proc.stderr or "").strip()
            raise Exception(f"Obscura fetch failed ({proc.returncode}): {err}")

        html = proc.stdout or ""
        title = ""
        title_tag = BeautifulSoup(html, "html.parser").title
        if title_tag and title_tag.string:
            title = title_tag.string.strip()
        return html, title


def _build_backend() -> BrowserBackend:
    """Choose a backend from BROWSER_BACKEND, falling back to Selenium when needed."""
    requested = os.getenv("BROWSER_BACKEND", "selenium").strip().lower()
    if requested == "obscura":
        binary = os.getenv("OBSCURA_BIN") or shutil.which("obscura")
        if binary:
            logger.info(f"Using Obscura backend ({binary})")
            return ObscuraBackend(binary)
        logger.warning(
            "BROWSER_BACKEND=obscura but the 'obscura' binary was not found "
            "(set OBSCURA_BIN or add it to PATH). Falling back to Selenium."
        )
    return SeleniumBackend()


class WebSearcher:
    """Web search functionality with pluggable browser backends and engine fallback."""

    def __init__(self) -> None:
        self.backend: Optional[BrowserBackend] = None
        # Define search engines in order of preference
        self.search_engines = [
            {'name': 'google', 'method': self._search_google},
            {'name': 'duckduckgo', 'method': self._search_duckduckgo},
            {'name': 'bing', 'method': self._search_bing},
        ]
        self.blocked_engines = set()  # Track which engines are blocked/failing

    def _get_backend(self) -> BrowserBackend:
        if self.backend is None:
            self.backend = _build_backend()
        return self.backend

    @property
    def backend_name(self) -> str:
        return self._get_backend().name

    def search_with_fallback(self, query: str, max_results: int = 10, include_snippets: bool = True) -> Tuple[List[Dict[str, Any]], str]:
        """
        Search using multiple search engines with fallback support.

        Args:
            query: Search query string
            max_results: Maximum number of results to return
            include_snippets: Whether to include text snippets from search results

        Returns:
            Tuple of (search results list, engine name used)
        """
        # Try each search engine until one works
        for engine in self.search_engines:
            engine_name = engine['name']

            # Skip if this engine is known to be blocked
            if engine_name in self.blocked_engines:
                logger.info(f"Skipping {engine_name} (previously blocked)")
                continue

            try:
                logger.info(f"Trying search with {engine_name}")
                results = engine['method'](query, max_results, include_snippets)

                if results:  # If we got results, success!
                    logger.info(f"Successfully searched with {engine_name}, got {len(results)} results")
                    # Remove from blocked list if it was there (in case it recovered)
                    self.blocked_engines.discard(engine_name)
                    return results, engine_name
                else:
                    logger.warning(f"No results from {engine_name}")

            except Exception as e:
                logger.error(f"Error with {engine_name}: {e}")
                # Add to blocked list for this session
                self.blocked_engines.add(engine_name)
                continue

        logger.error("All search engines failed or are blocked")
        return [], "none"

    def _search_google(self, query: str, max_results: int, include_snippets: bool) -> List[Dict[str, Any]]:
        """Search Google and parse the rendered results."""
        search_url = f"https://www.google.com/search?q={quote_plus(query)}&num={min(max_results, 100)}"
        html, _ = self._get_backend().fetch_html(search_url)

        if self._is_google_blocked(html):
            raise Exception("Google has blocked this IP/session")

        return self._parse_google_results(html, max_results, include_snippets)

    def _search_duckduckgo(self, query: str, max_results: int, include_snippets: bool) -> List[Dict[str, Any]]:
        """Search DuckDuckGo as fallback."""
        search_url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
        html, _ = self._get_backend().fetch_html(search_url)
        return self._parse_duckduckgo_results(html, max_results, include_snippets)

    def _search_bing(self, query: str, max_results: int, include_snippets: bool) -> List[Dict[str, Any]]:
        """Search Bing as fallback."""
        search_url = f"https://www.bing.com/search?q={quote_plus(query)}"
        html, _ = self._get_backend().fetch_html(search_url)
        return self._parse_bing_results(html, max_results, include_snippets)

    @staticmethod
    def _is_google_blocked(html: str) -> bool:
        """Check if Google has blocked us with captcha or unusual traffic page."""
        page = html.lower()
        blocked_indicators = [
            "unusual traffic",
            "captcha",
            "verify you're not a robot",
            "our systems have detected unusual traffic",
        ]
        return any(indicator in page for indicator in blocked_indicators)

    @staticmethod
    def _normalize_url(url: Optional[str]) -> Optional[str]:
        """Resolve a result href to the real destination URL.

        Search engines wrap results in redirect URLs:
          - Google:     /url?q=<real>&...
          - DuckDuckGo: //duckduckgo.com/l/?uddg=<url-encoded real>
          - Bing:       https://www.bing.com/ck/a?...&u=a1<base64url real>
        """
        if not url or url.startswith('#'):
            return None

        # Protocol-relative (e.g. DuckDuckGo redirects) -> give it a scheme.
        if url.startswith('//'):
            url = 'https:' + url

        # Google legacy redirect wrapper.
        if url.startswith('/url?q='):
            url = unquote(url.split('/url?q=')[1].split('&')[0])

        parsed = urlparse(url)
        host = parsed.netloc.lower()
        query = parse_qs(parsed.query)

        # DuckDuckGo redirect.
        if 'duckduckgo.com' in host and parsed.path.startswith('/l/') and 'uddg' in query:
            url = query['uddg'][0]
        # Bing redirect: the real URL is base64url-encoded in the `u` param after an "a1" marker.
        elif 'bing.com' in host and parsed.path.startswith('/ck/') and 'u' in query:
            raw = query['u'][0]
            if raw.startswith('a1'):
                raw = raw[2:]
            raw += '=' * (-len(raw) % 4)
            try:
                url = base64.urlsafe_b64decode(raw).decode('utf-8', 'replace')
            except Exception:
                pass

        # Reject internal/relative links we couldn't resolve.
        if url.startswith('/') or not urlparse(url).scheme:
            return None
        return url

    def _parse_google_results(self, html: str, max_results: int, include_snippets: bool) -> List[Dict[str, Any]]:
        """Parse Google search results from rendered HTML."""
        results: List[Dict[str, Any]] = []
        soup = BeautifulSoup(html, "html.parser")

        for i, container in enumerate(soup.select("div.g")):
            if len(results) >= max_results:
                break
            try:
                h3 = container.find("h3")
                if not isinstance(h3, Tag):
                    continue
                title = h3.get_text(strip=True)
                if not title:
                    continue

                anchor = h3.find_parent("a")
                if not isinstance(anchor, Tag):
                    anchor = container.find("a", href=True)
                if not isinstance(anchor, Tag):
                    continue

                url = self._normalize_url(anchor.get("href"))
                if not url:
                    continue

                snippet = ""
                if include_snippets:
                    snippet_el = container.select_one(".VwiC3b, .aCOpRe, span.st")
                    if snippet_el:
                        snippet = snippet_el.get_text(" ", strip=True)

                results.append({
                    "title": title,
                    "url": url,
                    "domain": urlparse(url).netloc,
                    "snippet": snippet,
                    "rank": len(results) + 1,
                    "source_engine": "google",
                })
            except Exception as e:
                logger.warning(f"Error parsing Google result {i}: {e}")
                continue

        return results

    def _parse_duckduckgo_results(self, html: str, max_results: int, include_snippets: bool) -> List[Dict[str, Any]]:
        """Parse DuckDuckGo search results from rendered HTML."""
        results: List[Dict[str, Any]] = []
        soup = BeautifulSoup(html, "html.parser")

        containers = soup.select(
            "article[data-testid='result'], div[data-testid='result'], div.result, div.web-result"
        )
        for i, container in enumerate(containers):
            if len(results) >= max_results:
                break
            try:
                anchor = container.select_one("h2 a, h3 a, a.result__a")
                if not isinstance(anchor, Tag):
                    continue
                title = anchor.get_text(strip=True)
                url = self._normalize_url(anchor.get("href"))
                if not title or not url:
                    continue

                snippet = ""
                if include_snippets:
                    snippet_el = container.select_one("[data-result='snippet'], .result__snippet")
                    if snippet_el:
                        snippet = snippet_el.get_text(" ", strip=True)

                results.append({
                    "title": title,
                    "url": url,
                    "domain": urlparse(url).netloc,
                    "snippet": snippet,
                    "rank": len(results) + 1,
                    "source_engine": "duckduckgo",
                })
            except Exception as e:
                logger.warning(f"Error parsing DuckDuckGo result {i}: {e}")
                continue

        return results

    def _parse_bing_results(self, html: str, max_results: int, include_snippets: bool) -> List[Dict[str, Any]]:
        """Parse Bing search results from rendered HTML."""
        results: List[Dict[str, Any]] = []
        soup = BeautifulSoup(html, "html.parser")

        for i, container in enumerate(soup.select("li.b_algo, .b_algo")):
            if len(results) >= max_results:
                break
            try:
                anchor = container.select_one("h2 a")
                if not isinstance(anchor, Tag):
                    continue
                title = anchor.get_text(strip=True)
                url = self._normalize_url(anchor.get("href"))
                if not title or not url:
                    continue

                snippet = ""
                if include_snippets:
                    snippet_el = container.select_one(".b_caption p, p")
                    if snippet_el:
                        snippet = snippet_el.get_text(" ", strip=True)

                results.append({
                    "title": title,
                    "url": url,
                    "domain": urlparse(url).netloc,
                    "snippet": snippet,
                    "rank": len(results) + 1,
                    "source_engine": "bing",
                })
            except Exception as e:
                logger.warning(f"Error parsing Bing result {i}: {e}")
                continue

        return results

    # Keep the old method for backward compatibility
    def search_google(self, query: str, max_results: int = 10, include_snippets: bool = True) -> List[Dict[str, Any]]:
        """Legacy method - now uses fallback search."""
        results, _ = self.search_with_fallback(query, max_results, include_snippets)
        return results

    def get_page_content(self, url: str, max_length: int = 5000) -> Dict[str, Any]:
        """
        Fetch and return content from a web page.

        Args:
            url: URL to fetch
            max_length: Maximum length of content to return

        Returns:
            Dictionary with page content and metadata
        """
        try:
            logger.info(f"Fetching content from: {url}")
            html, title = self._get_backend().fetch_html(url)

            soup = BeautifulSoup(html, "html.parser")

            # Remove non-content elements
            for element in soup(["script", "style", "nav", "header", "footer"]):
                element.decompose()

            text = soup.get_text()

            # Clean up whitespace
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk)

            if len(text) > max_length:
                text = text[:max_length] + "..."

            return {
                "url": url,
                "title": title,
                "content": text,
                "length": len(text),
            }

        except Exception as e:
            logger.error(f"Error fetching page content: {e}")
            return {
                "url": url,
                "title": "",
                "content": f"Error fetching content: {str(e)}",
                "length": 0,
            }

    def reset_blocked_engines(self):
        """Reset the list of blocked engines (useful for testing or recovery)."""
        self.blocked_engines.clear()
        logger.info("Reset blocked engines list")

    def get_engine_status(self) -> Dict[str, str]:
        """Get the status of all search engines plus the active browser backend."""
        status = {"backend": self.backend_name}
        for engine in self.search_engines:
            name = engine['name']
            status[name] = "blocked" if name in self.blocked_engines else "available"
        return status

    def close(self):
        """Close the active browser backend."""
        if self.backend is not None:
            self.backend.close()


# Global searcher instance (initialized lazily)
searcher = None


def get_searcher():
    """Get or create the global searcher instance."""
    global searcher
    if searcher is None:
        searcher = WebSearcher()
    return searcher


@mcp.tool()
def search_web(query: str, max_results: int = 10, include_snippets: bool = True) -> List[Dict[str, Any]]:
    """
    Search the web using multiple search engines with automatic fallback.

    Args:
        query: The search query string
        max_results: Maximum number of results to return (default: 10, max: 100)
        include_snippets: Whether to include text snippets from search results (default: True)

    Returns:
        List of search results, each containing title, URL, domain, snippet, rank, and source_engine
    """
    max_results = min(max_results, 100)  # Cap at 100 results
    results, engine_used = get_searcher().search_with_fallback(query, max_results, include_snippets)

    if results:
        logger.info(f"Search completed using {engine_used} engine")

    return results


@mcp.tool()
def get_search_engine_status() -> Dict[str, str]:
    """
    Get the current status of all search engines (available/blocked) and the active browser backend.

    Returns:
        Dictionary with the active backend plus each engine name mapped to its status
    """
    return get_searcher().get_engine_status()


@mcp.tool()
def reset_search_engines() -> str:
    """
    Reset the blocked search engines list (useful if engines recover from blocks).

    Returns:
        Status message
    """
    get_searcher().reset_blocked_engines()
    return "All search engines have been reset to available status"


@mcp.tool()
def get_webpage_content(url: str, max_length: int = 5000) -> Dict[str, Any]:
    """
    Fetch and return the text content of a webpage.

    Args:
        url: The URL of the webpage to fetch
        max_length: Maximum length of content to return (default: 5000)

    Returns:
        Dictionary containing the webpage's title, content, URL, and content length
    """
    max_length = min(max_length, 20000)  # Cap at 20k characters
    return get_searcher().get_page_content(url, max_length)


def main():
    """Main entry point for the MCP server."""
    try:
        logger.info("Starting Web Search MCP Server with fallback support...")
        mcp.run(transport="stdio")
    except KeyboardInterrupt:
        logger.info("Server interrupted by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
    finally:
        # Clean up
        if searcher is not None:
            searcher.close()
        logger.info("Server shutdown complete")


if __name__ == "__main__":
    main()
