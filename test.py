#!/usr/bin/env python3
"""
Test suite for Web Search MCP Server
Tests backend selection (Selenium / Obscura), search engines, parsing, and fallback.
"""

import subprocess
import pytest
from unittest.mock import MagicMock, patch
from urllib.parse import quote_plus

from main import (
    WebSearcher,
    SeleniumBackend,
    ObscuraBackend,
    _build_backend,
)


# ---------------------------------------------------------------------------
# Sample rendered HTML for each engine (mirrors the real result markup)
# ---------------------------------------------------------------------------

GOOGLE_HTML = """
<html><body>
  <div class="g">
    <a href="https://example.com/1"><h3>Test Result 1</h3></a>
    <div class="VwiC3b">First test result snippet</div>
  </div>
  <div class="g">
    <a href="https://example.org/2"><h3>Test Result 2</h3></a>
    <div class="VwiC3b">Second test result snippet</div>
  </div>
</body></html>
"""

# DuckDuckGo wraps results in //duckduckgo.com/l/?uddg=<real-url>
DDG_HTML = """
<html><body>
  <div class="result results_links web-result">
    <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2F1&rut=x">DDG Result 1</a>
    <a class="result__snippet">DDG snippet</a>
  </div>
</body></html>
"""

# Bing wraps results in /ck/a?...&u=a1<base64url real-url>; here a1...== decodes to https://example.com/1
BING_HTML = """
<html><body>
  <li class="b_algo">
    <h2><a href="https://www.bing.com/ck/a?!&p=z&u=a1aHR0cHM6Ly9leGFtcGxlLmNvbS8x&ntb=1">Bing Result 1</a></h2>
    <div class="b_caption"><p>Bing snippet</p></div>
  </li>
</body></html>
"""


def make_backend(html: str = "", title: str = "Test Page") -> MagicMock:
    """A mock BrowserBackend whose fetch_html returns canned (html, title)."""
    backend = MagicMock()
    backend.name = "mock"
    backend.fetch_html.return_value = (html, title)
    return backend


# ---------------------------------------------------------------------------
# Backend selection
# ---------------------------------------------------------------------------

class TestBackendSelection:
    """Test _build_backend honoring BROWSER_BACKEND / OBSCURA_BIN."""

    def test_default_is_selenium(self):
        with patch.dict("os.environ", {}, clear=True):
            backend = _build_backend()
        assert isinstance(backend, SeleniumBackend)
        assert backend.name == "selenium"

    def test_explicit_selenium(self):
        with patch.dict("os.environ", {"BROWSER_BACKEND": "selenium"}, clear=True):
            backend = _build_backend()
        assert isinstance(backend, SeleniumBackend)

    def test_obscura_with_explicit_binary(self):
        with patch.dict("os.environ", {"BROWSER_BACKEND": "obscura", "OBSCURA_BIN": "/usr/bin/obscura"}, clear=True):
            backend = _build_backend()
        assert isinstance(backend, ObscuraBackend)
        assert backend.binary == "/usr/bin/obscura"

    def test_obscura_found_on_path(self):
        with patch.dict("os.environ", {"BROWSER_BACKEND": "obscura"}, clear=True):
            with patch("main.shutil.which", return_value="/opt/obscura"):
                backend = _build_backend()
        assert isinstance(backend, ObscuraBackend)
        assert backend.binary == "/opt/obscura"

    def test_obscura_missing_falls_back_to_selenium(self):
        with patch.dict("os.environ", {"BROWSER_BACKEND": "obscura"}, clear=True):
            with patch("main.shutil.which", return_value=None):
                backend = _build_backend()
        assert isinstance(backend, SeleniumBackend)


# ---------------------------------------------------------------------------
# Obscura backend
# ---------------------------------------------------------------------------

class TestObscuraBackend:
    """Test the Obscura CLI subprocess wrapper."""

    def test_fetch_html_success(self):
        backend = ObscuraBackend("/usr/bin/obscura")
        completed = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout="<html><head><title>Hello</title></head><body>hi</body></html>",
            stderr="",
        )
        with patch("main.subprocess.run", return_value=completed) as mock_run:
            html, title = backend.fetch_html("https://example.com", timeout=10)

        assert "Hello" in html
        assert title == "Hello"
        cmd = mock_run.call_args.args[0]
        assert cmd[:4] == ["/usr/bin/obscura", "fetch", "https://example.com", "--dump"]
        assert "html" in cmd
        assert "--wait-until" in cmd
        assert "--timeout" in cmd

    def test_fetch_html_nonzero_exit_raises(self):
        backend = ObscuraBackend("/usr/bin/obscura")
        completed = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="boom")
        with patch("main.subprocess.run", return_value=completed):
            with pytest.raises(Exception, match="Obscura fetch failed"):
                backend.fetch_html("https://example.com")

    def test_fetch_html_timeout_raises(self):
        backend = ObscuraBackend("/usr/bin/obscura")
        with patch("main.subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="obscura", timeout=5)):
            with pytest.raises(Exception, match="Obscura timed out"):
                backend.fetch_html("https://example.com")


# ---------------------------------------------------------------------------
# Selenium backend
# ---------------------------------------------------------------------------

class TestSeleniumBackend:
    """Test the Selenium backend driver lifecycle."""

    @patch("main.webdriver.Chrome")
    @patch("main.ChromeDriverManager")
    def test_driver_setup_success(self, mock_driver_manager, mock_chrome):
        mock_driver_manager.return_value.install.return_value = "/path/to/chromedriver"
        mock_instance = MagicMock()
        mock_instance.page_source = "<html><body>ok</body></html>"
        mock_instance.title = "OK"
        mock_chrome.return_value = mock_instance

        backend = SeleniumBackend()
        with patch("main.time.sleep"), patch("main.WebDriverWait"):
            html, title = backend.fetch_html("https://example.com")

        assert "ok" in html
        assert title == "OK"
        mock_instance.get.assert_called_once_with("https://example.com")
        mock_chrome.assert_called_once()

    def test_close_quits_driver(self):
        backend = SeleniumBackend()
        mock_driver = MagicMock()
        backend.driver = mock_driver
        backend.close()
        mock_driver.quit.assert_called_once()
        assert backend.driver is None


# ---------------------------------------------------------------------------
# Searcher init
# ---------------------------------------------------------------------------

class TestSearchEngineInitialization:

    @pytest.fixture
    def searcher(self):
        return WebSearcher()

    def test_searcher_initialization(self, searcher):
        assert searcher.backend is None
        assert len(searcher.search_engines) == 3
        assert searcher.blocked_engines == set()
        engine_names = [engine['name'] for engine in searcher.search_engines]
        assert {'google', 'duckduckgo', 'bing'} <= set(engine_names)


# ---------------------------------------------------------------------------
# Per-engine search + parsing
# ---------------------------------------------------------------------------

class TestGoogleSearch:

    @pytest.fixture
    def searcher(self):
        return WebSearcher()

    def test_search_google_success(self, searcher):
        searcher.backend = make_backend(GOOGLE_HTML)
        results = searcher._search_google("test query", 10, True)

        assert len(results) == 2
        assert results[0]['source_engine'] == 'google'
        assert results[0]['url'] == "https://example.com/1"
        assert results[0]['snippet'] == "First test result snippet"
        expected_url = f"https://www.google.com/search?q={quote_plus('test query')}&num=10"
        searcher.backend.fetch_html.assert_called_with(expected_url)

    def test_search_google_blocked(self, searcher):
        searcher.backend = make_backend("Our systems have detected unusual traffic")
        with pytest.raises(Exception, match="Google has blocked"):
            searcher._search_google("test query", 10, True)

    def test_is_google_blocked_detection(self):
        assert WebSearcher._is_google_blocked("unusual traffic from your computer") is True
        assert WebSearcher._is_google_blocked("Normal search results") is False

    def test_max_results_limits_output(self, searcher):
        searcher.backend = make_backend(GOOGLE_HTML)
        results = searcher._search_google("q", 1, True)
        assert len(results) == 1

    def test_backend_error_propagates(self, searcher):
        backend = MagicMock()
        backend.fetch_html.side_effect = Exception("network down")
        searcher.backend = backend
        with pytest.raises(Exception):
            searcher._search_google("q", 10, True)


class TestDuckDuckGoSearch:

    @pytest.fixture
    def searcher(self):
        return WebSearcher()

    def test_search_duckduckgo_success(self, searcher):
        searcher.backend = make_backend(DDG_HTML)
        results = searcher._search_duckduckgo("test query", 10, True)

        assert len(results) == 1
        assert results[0]['source_engine'] == 'duckduckgo'
        assert results[0]['url'] == "https://example.com/1"
        assert results[0]['snippet'] == "DDG snippet"
        expected_url = f"https://html.duckduckgo.com/html/?q={quote_plus('test query')}"
        searcher.backend.fetch_html.assert_called_with(expected_url)


class TestBingSearch:

    @pytest.fixture
    def searcher(self):
        return WebSearcher()

    def test_search_bing_success(self, searcher):
        searcher.backend = make_backend(BING_HTML)
        results = searcher._search_bing("test query", 10, True)

        assert len(results) == 1
        assert results[0]['source_engine'] == 'bing'
        assert results[0]['url'] == "https://example.com/1"
        assert results[0]['snippet'] == "Bing snippet"
        expected_url = f"https://www.bing.com/search?q={quote_plus('test query')}"
        searcher.backend.fetch_html.assert_called_with(expected_url)


# ---------------------------------------------------------------------------
# Fallback
# ---------------------------------------------------------------------------

class TestUrlNormalization:
    """Test redirect-URL unwrapping for each engine."""

    def test_google_url_wrapper(self):
        assert WebSearcher._normalize_url("/url?q=https%3A%2F%2Fexample.org%2Fa&sa=U") == "https://example.org/a"

    def test_duckduckgo_redirect(self):
        out = WebSearcher._normalize_url("//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2F1&rut=x")
        assert out == "https://example.com/1"

    def test_bing_redirect(self):
        out = WebSearcher._normalize_url("https://www.bing.com/ck/a?!&p=z&u=a1aHR0cHM6Ly9leGFtcGxlLmNvbS8x&ntb=1")
        assert out == "https://example.com/1"

    def test_plain_url_unchanged(self):
        assert WebSearcher._normalize_url("https://plain.example/x") == "https://plain.example/x"

    def test_rejects_relative_and_anchor(self):
        assert WebSearcher._normalize_url("/search?q=foo") is None
        assert WebSearcher._normalize_url("#section") is None
        assert WebSearcher._normalize_url(None) is None


class TestSearchFallback:

    @pytest.fixture
    def searcher(self):
        return WebSearcher()

    @pytest.fixture
    def sample_results(self):
        return [{
            "title": "R1", "url": "https://example.com/1", "domain": "example.com",
            "snippet": "s", "rank": 1, "source_engine": "google",
        }]

    def test_fallback_google_success(self, searcher, sample_results):
        searcher.search_engines[0]['method'] = MagicMock(return_value=sample_results)
        results, engine_used = searcher.search_with_fallback("test", 10, True)
        assert len(results) == 1
        assert engine_used == "google"

    def test_fallback_google_fails_ddg_succeeds(self, searcher, sample_results):
        ddg = [{**r, 'source_engine': 'duckduckgo'} for r in sample_results]
        searcher.search_engines[0]['method'] = MagicMock(side_effect=Exception("Google blocked"))
        searcher.search_engines[1]['method'] = MagicMock(return_value=ddg)
        results, engine_used = searcher.search_with_fallback("test", 10, True)
        assert engine_used == "duckduckgo"
        assert 'google' in searcher.blocked_engines

    def test_fallback_all_engines_blocked(self, searcher):
        searcher.blocked_engines.update({'google', 'duckduckgo', 'bing'})
        results, engine_used = searcher.search_with_fallback("test", 10, True)
        assert len(results) == 0
        assert engine_used == "none"


# ---------------------------------------------------------------------------
# Engine management & status
# ---------------------------------------------------------------------------

class TestEngineManagement:

    @pytest.fixture
    def searcher(self):
        return WebSearcher()

    def test_engine_status_includes_backend(self, searcher):
        searcher.backend = make_backend()
        searcher.backend.name = "obscura"
        status = searcher.get_engine_status()
        assert status['backend'] == "obscura"
        assert status['google'] == 'available'

    def test_engine_status_tracking(self, searcher):
        searcher.backend = make_backend()
        searcher.blocked_engines.add('google')
        status = searcher.get_engine_status()
        assert status['google'] == 'blocked'
        assert status['duckduckgo'] == 'available'

    def test_reset_blocked_engines(self, searcher):
        searcher.blocked_engines.update({'google', 'bing'})
        searcher.reset_blocked_engines()
        assert len(searcher.blocked_engines) == 0

    def test_close_delegates_to_backend(self, searcher):
        backend = make_backend()
        searcher.backend = backend
        searcher.close()
        backend.close.assert_called_once()


# ---------------------------------------------------------------------------
# Page content
# ---------------------------------------------------------------------------

class TestPageContent:

    @pytest.fixture
    def searcher(self):
        return WebSearcher()

    def test_get_page_content(self, searcher):
        html = "<html><head><title>My Page</title></head><body><script>x()</script><p>Hello world</p></body></html>"
        searcher.backend = make_backend(html, title="My Page")
        result = searcher.get_page_content("https://example.com", 5000)
        assert result['title'] == "My Page"
        assert "Hello world" in result['content']
        assert "x()" not in result['content']  # script stripped

    def test_get_page_content_handles_error(self, searcher):
        backend = MagicMock()
        backend.fetch_html.side_effect = Exception("boom")
        searcher.backend = backend
        result = searcher.get_page_content("https://example.com")
        assert result['length'] == 0
        assert "Error fetching content" in result['content']


# ---------------------------------------------------------------------------
# MCP tools
# ---------------------------------------------------------------------------

class TestMCPTools:

    @pytest.fixture
    def sample_results(self):
        return [{
            "title": "R1", "url": "https://example.com/1", "domain": "example.com",
            "snippet": "s", "rank": 1, "source_engine": "google",
        }]

    @patch('main.get_searcher')
    def test_search_functionality(self, mock_get_searcher, sample_results):
        mock_searcher = MagicMock()
        mock_searcher.search_with_fallback.return_value = (sample_results, 'google')
        mock_get_searcher.return_value = mock_searcher

        searcher = mock_get_searcher()
        results, engine_used = searcher.search_with_fallback("test query", 5, True)
        assert len(results) == 1
        assert engine_used == 'google'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
