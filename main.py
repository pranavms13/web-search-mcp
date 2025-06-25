#!/usr/bin/env python3
"""
MCP Web Search Server
A Model Context Protocol server that provides web search functionality using a headless browser
to scrape Google search results.
"""

import asyncio
import logging
import re
import time
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus, urljoin, urlparse

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup, Tag
import requests

from fastmcp import FastMCP

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize MCP server
mcp = FastMCP("Web Search MCP")

class WebSearcher:
    """Web search functionality using headless Chrome browser."""
    
    def __init__(self):
        self.driver: Optional[webdriver.Chrome] = None
        self.driver_initialized = False
    
    def _setup_driver(self):
        """Set up Chrome driver with headless options."""
        try:
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            chrome_options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver_initialized = True
            logger.info("Chrome driver initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Chrome driver: {e}")
            raise
    
    def search_google(self, query: str, max_results: int = 10, include_snippets: bool = True) -> List[Dict[str, Any]]:
        """
        Search Google and return results.
        
        Args:
            query: Search query string
            max_results: Maximum number of results to return
            include_snippets: Whether to include text snippets from search results
            
        Returns:
            List of search result dictionaries
        """
        if not self.driver_initialized or self.driver is None:
            self._setup_driver()
        
        if self.driver is None:
            logger.error("Failed to initialize Chrome driver")
            return []
        
        try:
            # Construct Google search URL
            search_url = f"https://www.google.com/search?q={quote_plus(query)}&num={min(max_results, 100)}"
            
            logger.info(f"Searching Google for: {query}")
            self.driver.get(search_url)
            
            # Wait for results to load with increased timeout
            time.sleep(2)  # Give the page time to load
            wait = WebDriverWait(self.driver, 15)
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div#search, div#rso")))
            
            # Parse results using XPath
            results = self._parse_search_results_xpath(max_results, include_snippets)
            
            logger.info(f"Found {len(results)} search results")
            return results
            
        except TimeoutException:
            logger.error("Timeout waiting for search results to load")
            return []
        except WebDriverException as e:
            logger.error(f"WebDriver error during search: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error during search: {e}")
            return []
    
    def _parse_search_results_xpath(self, max_results: int, include_snippets: bool) -> List[Dict[str, Any]]:
        """Parse Google search results using XPath selectors."""
        results = []
        
        if self.driver is None:
            logger.error("Driver is not initialized")
            return results
        
        try:
            # Find all search result containers using a more flexible XPath
            # Look for div elements with class 'g' which contain search results
            result_containers = self.driver.find_elements(By.XPATH, "//div[@class='g' or contains(@class, 'g ')]")
            
            for i, container in enumerate(result_containers[:max_results]):
                try:
                    # Extract title using XPath - look for h3 elements within the container
                    title_elements = container.find_elements(By.XPATH, ".//h3")
                    if not title_elements:
                        continue
                    
                    title = title_elements[0].text.strip()
                    if not title:
                        continue
                    
                    # Extract URL - look for the parent anchor tag of the h3
                    link_elements = container.find_elements(By.XPATH, ".//h3/parent::a | .//h3/ancestor::a")
                    if not link_elements:
                        # Try alternative: look for any anchor with href in the container
                        link_elements = container.find_elements(By.XPATH, ".//a[@href]")
                    
                    if not link_elements:
                        continue
                    
                    url = link_elements[0].get_attribute('href')
                    if not url or url.startswith('/search') or url.startswith('#'):
                        continue
                    
                    # Clean up URL (Google sometimes wraps URLs)
                    if url.startswith('/url?q='):
                        url = url.split('/url?q=')[1].split('&')[0]
                    
                    # Extract snippet if requested
                    snippet = ""
                    if include_snippets:
                        # Look for snippet text in various possible locations
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
                                if len(snippet_text) > 20:  # Only use if it's substantial text
                                    snippet = snippet_text
                                    break
                    
                    # Extract domain
                    domain = urlparse(url).netloc
                    
                    result_dict = {
                        "title": title,
                        "url": url,
                        "domain": domain,
                        "snippet": snippet,
                        "rank": i + 1
                    }
                    
                    results.append(result_dict)
                    
                except Exception as e:
                    logger.warning(f"Error parsing search result {i}: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"Error finding search results: {e}")
        
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
            if not self.driver_initialized or self.driver is None:
                self._setup_driver()
            
            if self.driver is None:
                raise Exception("Failed to initialize Chrome driver")
            
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
    
    def close(self):
        """Close the browser driver."""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("Chrome driver closed")
            except Exception as e:
                logger.error(f"Error closing driver: {e}")

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
    Search the web using Google and return results.
    
    Args:
        query: The search query string
        max_results: Maximum number of results to return (default: 10, max: 100)
        include_snippets: Whether to include text snippets from search results (default: True)
    
    Returns:
        List of search results, each containing title, URL, domain, snippet, and rank
    """
    max_results = min(max_results, 100)  # Cap at 100 results
    return get_searcher().search_google(query, max_results, include_snippets)

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
        logger.info("Starting Web Search MCP Server...")
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
