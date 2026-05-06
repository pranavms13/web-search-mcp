#!/usr/bin/env python3
"""
MCP Web Search Server
A Model Context Protocol server that provides web search functionality using a headless browser
to scrape search results from multiple search engines with fallback support.
"""

import asyncio
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote_plus, urljoin, urlparse

from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager
from webdriver_manager.microsoft import EdgeChromiumDriverManager
from bs4 import BeautifulSoup, Tag
import requests

from fastmcp import FastMCP

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize MCP server
mcp = FastMCP("Web Search MCP")

SUPPORTED_BROWSERS = ("chrome", "edge", "firefox")
BROWSER_USER_AGENTS = {
    "chrome": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "edge": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    "firefox": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
}

class WebSearcher:
    """Web search functionality using Selenium browsers with fallback support."""
    
    def __init__(self, browser: str = "chrome"):
        self.browser = self._normalize_browser(browser)
        self.driver: Optional[webdriver.Remote] = None
        self.driver_initialized = False
        # Define search engines in order of preference
        self.search_engines = [
            {'name': 'google', 'method': self._search_google},
            {'name': 'duckduckgo', 'method': self._search_duckduckgo},
            {'name': 'bing', 'method': self._search_bing}
        ]
        self.blocked_engines = set()  # Track which engines are blocked/failing

    @staticmethod
    def _normalize_browser(browser: str) -> str:
        """Validate and normalize the browser name."""
        normalized = (browser or "chrome").strip().lower()
        if normalized not in SUPPORTED_BROWSERS:
            supported = ", ".join(SUPPORTED_BROWSERS)
            raise ValueError(f"Unsupported browser '{browser}'. Supported browsers are: {supported}")
        return normalized

    def _configure_chromium_options(self, options: ChromeOptions | EdgeOptions, user_agent: str) -> None:
        """Apply shared Chromium options for Chrome and Edge."""
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument(f"--user-agent={user_agent}")

    def _configure_firefox_options(self, options: FirefoxOptions, user_agent: str) -> None:
        """Apply Firefox-specific options."""
        options.add_argument("--headless")
        options.add_argument("--width=1920")
        options.add_argument("--height=1080")
        options.set_preference("general.useragent.override", user_agent)
    
    def _setup_driver(self):
        """Set up the configured Selenium browser driver."""
        try:
            if self.browser == "chrome":
                browser_options = ChromeOptions()
                self._configure_chromium_options(browser_options, BROWSER_USER_AGENTS["chrome"])
                service = ChromeService(ChromeDriverManager().install())
                self.driver = webdriver.Chrome(service=service, options=browser_options)
            elif self.browser == "edge":
                browser_options = EdgeOptions()
                self._configure_chromium_options(browser_options, BROWSER_USER_AGENTS["edge"])
                service = EdgeService(EdgeChromiumDriverManager().install())
                self.driver = webdriver.Edge(service=service, options=browser_options)
            else:
                browser_options = FirefoxOptions()
                self._configure_firefox_options(browser_options, BROWSER_USER_AGENTS["firefox"])
                service = FirefoxService(GeckoDriverManager().install())
                self.driver = webdriver.Firefox(service=service, options=browser_options)

            self.driver_initialized = True
            logger.info("%s driver initialized successfully", self.browser.capitalize())
        except Exception as e:
            logger.error("Failed to initialize %s driver: %s", self.browser, e)
            raise
    
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
        if not self.driver_initialized or self.driver is None:
            self._setup_driver()
        
        if self.driver is None:
            logger.error("Failed to initialize %s driver", self.browser)
            return [], "none"
        
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
        """Search Google (original implementation)."""
        if self.driver is None:
            raise Exception("Driver not initialized")
            
        try:
            # Construct Google search URL
            search_url = f"https://www.google.com/search?q={quote_plus(query)}&num={min(max_results, 100)}"
            
            self.driver.get(search_url)
            
            # Wait for results to load
            time.sleep(2)
            wait = WebDriverWait(self.driver, 15)
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div#search, div#rso")))
            
            # Check if we're blocked (captcha, unusual traffic page, etc.)
            if self._is_google_blocked():
                raise Exception("Google has blocked this IP/session")
            
            return self._parse_google_results(max_results, include_snippets)
            
        except Exception as e:
            logger.error(f"Google search failed: {e}")
            raise
    
    def _search_duckduckgo(self, query: str, max_results: int, include_snippets: bool) -> List[Dict[str, Any]]:
        """Search DuckDuckGo as fallback."""
        if self.driver is None:
            raise Exception("Driver not initialized")
            
        try:
            # DuckDuckGo search URL
            search_url = f"https://duckduckgo.com/?q={quote_plus(query)}"
            
            self.driver.get(search_url)
            time.sleep(3)  # DuckDuckGo needs a bit more time to load
            
            return self._parse_duckduckgo_results(max_results, include_snippets)
            
        except Exception as e:
            logger.error(f"DuckDuckGo search failed: {e}")
            raise
    
    def _search_bing(self, query: str, max_results: int, include_snippets: bool) -> List[Dict[str, Any]]:
        """Search Bing as fallback."""
        if self.driver is None:
            raise Exception("Driver not initialized")
            
        try:
            # Bing search URL
            search_url = f"https://www.bing.com/search?q={quote_plus(query)}"
            
            self.driver.get(search_url)
            time.sleep(2)
            
            return self._parse_bing_results(max_results, include_snippets)
            
        except Exception as e:
            logger.error(f"Bing search failed: {e}")
            raise
    
    def _is_google_blocked(self) -> bool:
        """Check if Google has blocked us with captcha or unusual traffic page."""
        if self.driver is None:
            return True
        try:
            page_source = self.driver.page_source.lower()
            blocked_indicators = [
                "unusual traffic",
                "captcha",
                "blocked",
                "verify you're not a robot",
                "our systems have detected unusual traffic"
            ]
            return any(indicator in page_source for indicator in blocked_indicators)
        except:
            return False
    
    def _parse_google_results(self, max_results: int, include_snippets: bool) -> List[Dict[str, Any]]:
        """Parse Google search results (original implementation)."""
        results = []
        
        if self.driver is None:
            return results
        
        try:
            result_containers = self.driver.find_elements(By.XPATH, "//div[@class='g' or contains(@class, 'g ')]")
            
            for i, container in enumerate(result_containers[:max_results]):
                try:
                    title_elements = container.find_elements(By.XPATH, ".//h3")
                    if not title_elements:
                        continue
                    
                    title = title_elements[0].text.strip()
                    if not title:
                        continue
                    
                    link_elements = container.find_elements(By.XPATH, ".//h3/parent::a | .//h3/ancestor::a")
                    if not link_elements:
                        link_elements = container.find_elements(By.XPATH, ".//a[@href]")
                    
                    if not link_elements:
                        continue
                    
                    url = link_elements[0].get_attribute('href')
                    if not url or url.startswith('/search') or url.startswith('#'):
                        continue
                    
                    if url.startswith('/url?q='):
                        url = url.split('/url?q=')[1].split('&')[0]
                    
                    snippet = ""
                    if include_snippets:
                        snippet_xpaths = [
                            ".//span[contains(@class, 'aCOpRe')]",
                            ".//div[contains(@class, 'VwiC3b')]",
                            ".//span[contains(@class, 'st')]",
                            ".//div[contains(@class, 's')]//span",
                            ".//div//span[not(ancestor::h3)]"
                        ]
                        
                        for xpath in snippet_xpaths:
                            snippet_elements = container.find_elements(By.XPATH, xpath)
                            if snippet_elements:
                                snippet_text = snippet_elements[0].text.strip()
                                if len(snippet_text) > 20:
                                    snippet = snippet_text
                                    break
                    
                    domain = urlparse(url).netloc
                    
                    results.append({
                        "title": title,
                        "url": url,
                        "domain": domain,
                        "snippet": snippet,
                        "rank": i + 1,
                        "source_engine": "google"
                    })
                    
                except Exception as e:
                    logger.warning(f"Error parsing Google result {i}: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"Error parsing Google results: {e}")
        
        return results
    
    def _parse_duckduckgo_results(self, max_results: int, include_snippets: bool) -> List[Dict[str, Any]]:
        """Parse DuckDuckGo search results."""
        results = []
        
        if self.driver is None:
            return results
        
        try:
            # DuckDuckGo uses different selectors
            result_containers = self.driver.find_elements(By.CSS_SELECTOR, "article[data-testid='result'], div[data-testid='result']")
            
            for i, container in enumerate(result_containers[:max_results]):
                try:
                    # Title
                    title_elements = container.find_elements(By.CSS_SELECTOR, "h2 a, h3 a")
                    if not title_elements:
                        continue
                    
                    title = title_elements[0].text.strip()
                    url = title_elements[0].get_attribute('href')
                    
                    if not title or not url:
                        continue
                    
                    # Snippet
                    snippet = ""
                    if include_snippets:
                        snippet_elements = container.find_elements(By.CSS_SELECTOR, "[data-result='snippet'], .result__snippet")
                        if snippet_elements:
                            snippet = snippet_elements[0].text.strip()
                    
                    domain = urlparse(url).netloc
                    
                    results.append({
                        "title": title,
                        "url": url,
                        "domain": domain,
                        "snippet": snippet,
                        "rank": i + 1,
                        "source_engine": "duckduckgo"
                    })
                    
                except Exception as e:
                    logger.warning(f"Error parsing DuckDuckGo result {i}: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"Error parsing DuckDuckGo results: {e}")
        
        return results
    
    def _parse_bing_results(self, max_results: int, include_snippets: bool) -> List[Dict[str, Any]]:
        """Parse Bing search results."""
        results = []
        
        if self.driver is None:
            return results
        
        try:
            # Bing result selectors
            result_containers = self.driver.find_elements(By.CSS_SELECTOR, ".b_algo")
            
            for i, container in enumerate(result_containers[:max_results]):
                try:
                    # Title and URL
                    title_elements = container.find_elements(By.CSS_SELECTOR, "h2 a")
                    if not title_elements:
                        continue
                    
                    title = title_elements[0].text.strip()
                    url = title_elements[0].get_attribute('href')
                    
                    if not title or not url:
                        continue
                    
                    # Snippet
                    snippet = ""
                    if include_snippets:
                        snippet_elements = container.find_elements(By.CSS_SELECTOR, ".b_caption p")
                        if snippet_elements:
                            snippet = snippet_elements[0].text.strip()
                    
                    domain = urlparse(url).netloc
                    
                    results.append({
                        "title": title,
                        "url": url,
                        "domain": domain,
                        "snippet": snippet,
                        "rank": i + 1,
                        "source_engine": "bing"
                    })
                    
                except Exception as e:
                    logger.warning(f"Error parsing Bing result {i}: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"Error parsing Bing results: {e}")
        
        return results

    # Keep the old method for backward compatibility
    def search_google(self, query: str, max_results: int = 10, include_snippets: bool = True) -> List[Dict[str, Any]]:
        """Legacy method - now uses fallback search."""
        results, engine_used = self.search_with_fallback(query, max_results, include_snippets)
        return results

    def _parse_search_results_xpath(self, max_results: int, include_snippets: bool) -> List[Dict[str, Any]]:
        """Legacy method - redirects to Google parser."""
        return self._parse_google_results(max_results, include_snippets)
    
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
            if not self.driver_initialized or self.driver is None:
                self._setup_driver()
            
            if self.driver is None:
                raise Exception(f"Failed to initialize {self.browser} driver")
            
            logger.info(f"Fetching content from: {url}")
            self.driver.get(url)
            
            # Wait for page to load
            time.sleep(2)
            
            # Get page title
            title = self.driver.title
            
            # Get page content
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style", "nav", "header", "footer"]):
                script.decompose()
            
            # Extract text content
            text = soup.get_text()
            
            # Clean up text
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk)
            
            # Truncate if too long
            if len(text) > max_length:
                text = text[:max_length] + "..."
            
            return {
                "url": url,
                "title": title,
                "content": text,
                "length": len(text)
            }
            
        except Exception as e:
            logger.error(f"Error fetching page content: {e}")
            return {
                "url": url,
                "title": "",
                "content": f"Error fetching content: {str(e)}",
                "length": 0
            }
    
    def reset_blocked_engines(self):
        """Reset the list of blocked engines (useful for testing or recovery)."""
        self.blocked_engines.clear()
        logger.info("Reset blocked engines list")
    
    def get_engine_status(self) -> Dict[str, str]:
        """Get the status of all search engines."""
        status = {}
        for engine in self.search_engines:
            name = engine['name']
            status[name] = "blocked" if name in self.blocked_engines else "available"
        return status
    
    def close(self):
        """Close the browser driver."""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("%s driver closed", self.browser.capitalize())
            except Exception as e:
                logger.error(f"Error closing driver: {e}")

# Global searchers by browser (initialized lazily)
searchers: Dict[str, WebSearcher] = {}

def get_searcher(browser: str = "chrome"):
    """Get or create a global searcher instance for the requested browser."""
    normalized_browser = WebSearcher._normalize_browser(browser)
    if normalized_browser not in searchers:
        searchers[normalized_browser] = WebSearcher(browser=normalized_browser)
    return searchers[normalized_browser]

@mcp.tool()
def search_web(query: str, max_results: int = 10, include_snippets: bool = True, browser: str = "chrome") -> List[Dict[str, Any]]:
    """
    Search the web using multiple search engines with automatic fallback.
    
    Args:
        query: The search query string
        max_results: Maximum number of results to return (default: 10, max: 100)
        include_snippets: Whether to include text snippets from search results (default: True)
        browser: Browser to use for Selenium (default: chrome; supported: chrome, edge, firefox)
    
    Returns:
        List of search results, each containing title, URL, domain, snippet, rank, and source_engine
    """
    max_results = min(max_results, 100)  # Cap at 100 results
    results, engine_used = get_searcher(browser).search_with_fallback(query, max_results, include_snippets)
    
    # Add metadata about which engine was used
    if results:
        logger.info("Search completed using %s engine on %s", engine_used, browser)
    
    return results

@mcp.tool()
def get_search_engine_status(browser: str = "chrome") -> Dict[str, str]:
    """
    Get the current status of all search engines (available/blocked).

    Args:
        browser: Browser searcher instance to inspect (default: chrome)
    
    Returns:
        Dictionary with engine names as keys and their status as values
    """
    return get_searcher(browser).get_engine_status()

@mcp.tool()
def reset_search_engines(browser: str = "chrome") -> str:
    """
    Reset the blocked search engines list (useful if engines recover from blocks).

    Args:
        browser: Browser searcher instance to reset (default: chrome)
    
    Returns:
        Status message
    """
    get_searcher(browser).reset_blocked_engines()
    return f"All search engines have been reset to available status for browser '{browser}'"

@mcp.tool()
def get_webpage_content(url: str, max_length: int = 5000, browser: str = "chrome") -> Dict[str, Any]:
    """
    Fetch and return the text content of a webpage.
    
    Args:
        url: The URL of the webpage to fetch
        max_length: Maximum length of content to return (default: 5000)
        browser: Browser to use for Selenium (default: chrome; supported: chrome, edge, firefox)
    
    Returns:
        Dictionary containing the webpage's title, content, URL, and content length
    """
    max_length = min(max_length, 20000)  # Cap at 20k characters
    return get_searcher(browser).get_page_content(url, max_length)

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
        for searcher in searchers.values():
            searcher.close()
        logger.info("Server shutdown complete")

if __name__ == "__main__":
    main()
