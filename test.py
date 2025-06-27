#!/usr/bin/env python3
"""
Test suite for Web Search MCP Server
Tests for Google, DuckDuckGo, and Bing search functionality
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from urllib.parse import quote_plus
from selenium.common.exceptions import TimeoutException, WebDriverException

from main import WebSearcher


class TestWebSearcher:
    """Test cases for the WebSearcher class."""
    
    @pytest.fixture
    def searcher(self):
        """Create a WebSearcher instance for testing."""
        return WebSearcher()
    
    @pytest.fixture
    def mock_driver(self):
        """Create a mock Selenium WebDriver."""
        mock_driver = MagicMock()
        mock_driver.page_source = "<html><body>Test page</body></html>"
        mock_driver.title = "Test Page"
        return mock_driver
    
    @pytest.fixture
    def sample_results(self):
        """Sample search results for testing."""
        return [
            {
                "title": "Test Result 1",
                "url": "https://example.com/1",
                "domain": "example.com",
                "snippet": "First test result",
                "rank": 1,
                "source_engine": "google"
            },
            {
                "title": "Test Result 2", 
                "url": "https://example.org/2",
                "domain": "example.org",
                "snippet": "Second test result",
                "rank": 2,
                "source_engine": "google"
            }
        ]


class TestSearchEngineInitialization:
    """Test search engine initialization and setup."""
    
    @pytest.fixture
    def searcher(self):
        """Create a WebSearcher instance for testing."""
        return WebSearcher()
    
    def test_searcher_initialization(self, searcher):
        """Test WebSearcher initializes correctly."""
        assert searcher.driver is None
        assert not searcher.driver_initialized
        assert len(searcher.search_engines) == 3
        assert searcher.blocked_engines == set()
        
        # Check search engines are configured correctly
        engine_names = [engine['name'] for engine in searcher.search_engines]
        assert 'google' in engine_names
        assert 'duckduckgo' in engine_names
        assert 'bing' in engine_names
    
    @patch('main.webdriver.Chrome')
    @patch('main.ChromeDriverManager')
    def test_driver_setup_success(self, mock_driver_manager, mock_chrome, searcher):
        """Test successful Chrome driver setup."""
        mock_driver_manager.return_value.install.return_value = "/path/to/chromedriver"
        mock_driver_instance = MagicMock()
        mock_chrome.return_value = mock_driver_instance
        
        searcher._setup_driver()
        
        assert searcher.driver == mock_driver_instance
        assert searcher.driver_initialized is True
        mock_chrome.assert_called_once()
    
    @patch('main.webdriver.Chrome')
    @patch('main.ChromeDriverManager')
    def test_driver_setup_failure(self, mock_driver_manager, mock_chrome, searcher):
        """Test Chrome driver setup failure."""
        mock_chrome.side_effect = Exception("Driver setup failed")
        
        with pytest.raises(Exception, match="Driver setup failed"):
            searcher._setup_driver()
        
        assert searcher.driver is None
        assert not searcher.driver_initialized


class TestGoogleSearch:
    """Test Google search functionality."""
    
    @pytest.fixture
    def searcher(self):
        return WebSearcher()
    
    @pytest.fixture
    def mock_driver(self):
        mock_driver = MagicMock()
        mock_driver.page_source = "<html><body>Test page</body></html>"
        mock_driver.title = "Test Page"
        return mock_driver
    
    @pytest.fixture
    def sample_results(self):
        return [
            {
                "title": "Test Result 1",
                "url": "https://example.com/1",
                "domain": "example.com",
                "snippet": "First test result",
                "rank": 1,
                "source_engine": "google"
            }
        ]
    
    def test_search_google_success(self, searcher, mock_driver, sample_results):
        """Test successful Google search."""
        searcher.driver = mock_driver
        searcher.driver_initialized = True
        
        with patch.object(searcher, '_parse_google_results', return_value=sample_results):
            with patch.object(searcher, '_is_google_blocked', return_value=False):
                results = searcher._search_google("test query", 10, True)
        
        assert len(results) == 1
        assert results[0]['source_engine'] == 'google'
        expected_url = f"https://www.google.com/search?q={quote_plus('test query')}&num=10"
        mock_driver.get.assert_called_with(expected_url)
    
    def test_search_google_blocked(self, searcher, mock_driver):
        """Test Google search when blocked."""
        searcher.driver = mock_driver
        searcher.driver_initialized = True
        
        with patch.object(searcher, '_is_google_blocked', return_value=True):
            with pytest.raises(Exception, match="Google has blocked"):
                searcher._search_google("test query", 10, True)
    
    def test_is_google_blocked_detection(self, searcher, mock_driver):
        """Test Google blocking detection."""
        searcher.driver = mock_driver
        
        # Test blocked page
        mock_driver.page_source = "unusual traffic from your computer"
        assert searcher._is_google_blocked() is True
        
        # Test normal page
        mock_driver.page_source = "Normal search results"
        assert searcher._is_google_blocked() is False


class TestDuckDuckGoSearch:
    """Test DuckDuckGo search functionality."""
    
    @pytest.fixture
    def searcher(self):
        return WebSearcher()
    
    @pytest.fixture
    def mock_driver(self):
        mock_driver = MagicMock()
        return mock_driver
    
    @pytest.fixture
    def sample_results(self):
        return [
            {
                "title": "DDG Result 1",
                "url": "https://example.com/1",
                "domain": "example.com",
                "snippet": "DDG test result",
                "rank": 1,
                "source_engine": "duckduckgo"
            }
        ]
    
    def test_search_duckduckgo_success(self, searcher, mock_driver, sample_results):
        """Test successful DuckDuckGo search."""
        searcher.driver = mock_driver
        searcher.driver_initialized = True
        
        with patch.object(searcher, '_parse_duckduckgo_results', return_value=sample_results):
            results = searcher._search_duckduckgo("test query", 10, True)
        
        assert len(results) == 1
        assert results[0]['source_engine'] == 'duckduckgo'
        expected_url = f"https://duckduckgo.com/?q={quote_plus('test query')}"
        mock_driver.get.assert_called_with(expected_url)
    
    def test_search_duckduckgo_no_driver(self, searcher):
        """Test DuckDuckGo search without driver."""
        with pytest.raises(Exception, match="Driver not initialized"):
            searcher._search_duckduckgo("test query", 10, True)


class TestBingSearch:
    """Test Bing search functionality."""
    
    @pytest.fixture
    def searcher(self):
        return WebSearcher()
    
    @pytest.fixture
    def mock_driver(self):
        mock_driver = MagicMock()
        return mock_driver
    
    @pytest.fixture
    def sample_results(self):
        return [
            {
                "title": "Bing Result 1",
                "url": "https://example.com/1",
                "domain": "example.com",
                "snippet": "Bing test result",
                "rank": 1,
                "source_engine": "bing"
            }
        ]
    
    def test_search_bing_success(self, searcher, mock_driver, sample_results):
        """Test successful Bing search."""
        searcher.driver = mock_driver
        searcher.driver_initialized = True
        
        with patch.object(searcher, '_parse_bing_results', return_value=sample_results):
            results = searcher._search_bing("test query", 10, True)
        
        assert len(results) == 1
        assert results[0]['source_engine'] == 'bing'
        expected_url = f"https://www.bing.com/search?q={quote_plus('test query')}"
        mock_driver.get.assert_called_with(expected_url)
    
    def test_search_bing_no_driver(self, searcher):
        """Test Bing search without driver."""
        with pytest.raises(Exception, match="Driver not initialized"):
            searcher._search_bing("test query", 10, True)


class TestSearchFallback:
    """Test the search fallback mechanism."""
    
    @pytest.fixture
    def searcher(self):
        return WebSearcher()
    
    @pytest.fixture
    def sample_results(self):
        return [
            {
                "title": "Test Result 1",
                "url": "https://example.com/1", 
                "domain": "example.com",
                "snippet": "Test snippet",
                "rank": 1,
                "source_engine": "google"
            }
        ]
    
    def test_fallback_google_success(self, searcher, sample_results):
        """Test fallback when Google succeeds."""
        searcher.driver_initialized = True
        searcher.driver = MagicMock()
        
        # Mock the method in the search_engines dictionary
        mock_google_method = MagicMock(return_value=sample_results)
        searcher.search_engines[0]['method'] = mock_google_method
        
        results, engine_used = searcher.search_with_fallback("test", 10, True)
        
        assert len(results) == 1
        assert engine_used == "google"
        mock_google_method.assert_called_once_with("test", 10, True)
    
    def test_fallback_google_fails_ddg_succeeds(self, searcher, sample_results):
        """Test fallback when Google fails, DuckDuckGo succeeds."""
        searcher.driver_initialized = True
        searcher.driver = MagicMock()
        
        ddg_results = sample_results.copy()
        for result in ddg_results:
            result['source_engine'] = 'duckduckgo'
        
        # Mock the methods in the search_engines dictionary
        mock_google_method = MagicMock(side_effect=Exception("Google blocked"))
        mock_ddg_method = MagicMock(return_value=ddg_results)
        searcher.search_engines[0]['method'] = mock_google_method
        searcher.search_engines[1]['method'] = mock_ddg_method
        
        results, engine_used = searcher.search_with_fallback("test", 10, True)
        
        assert len(results) == 1
        assert engine_used == "duckduckgo"
        assert 'google' in searcher.blocked_engines
        mock_google_method.assert_called_once_with("test", 10, True)
        mock_ddg_method.assert_called_once_with("test", 10, True)
    
    def test_fallback_all_engines_blocked(self, searcher):
        """Test fallback when all engines are pre-blocked."""
        searcher.driver_initialized = True
        searcher.driver = MagicMock()
        
        # Pre-block all engines
        searcher.blocked_engines.add('google')
        searcher.blocked_engines.add('duckduckgo')
        searcher.blocked_engines.add('bing')
        
        results, engine_used = searcher.search_with_fallback("test", 10, True)
        
        assert len(results) == 0
        assert engine_used == "none"


class TestEngineManagement:
    """Test engine status and reset functionality."""
    
    @pytest.fixture
    def searcher(self):
        return WebSearcher()
    
    def test_engine_status_tracking(self, searcher):
        """Test engine status tracking."""
        # Initially all available
        status = searcher.get_engine_status()
        assert all(s == 'available' for s in status.values())
        
        # Block some engines
        searcher.blocked_engines.add('google')
        status = searcher.get_engine_status()
        assert status['google'] == 'blocked'
        assert status['duckduckgo'] == 'available'
    
    def test_reset_blocked_engines(self, searcher):
        """Test resetting blocked engines."""
        searcher.blocked_engines.add('google')
        searcher.blocked_engines.add('bing')
        
        searcher.reset_blocked_engines()
        
        assert len(searcher.blocked_engines) == 0


class TestMCPTools:
    """Test MCP tool functions."""
    
    @pytest.fixture
    def sample_results(self):
        return [
            {
                "title": "Test Result 1",
                "url": "https://example.com/1",
                "domain": "example.com", 
                "snippet": "Test snippet",
                "rank": 1,
                "source_engine": "google"
            }
        ]
    
    @patch('main.get_searcher')
    def test_search_functionality(self, mock_get_searcher, sample_results):
        """Test the core search functionality used by MCP tools."""
        mock_searcher = MagicMock()
        mock_searcher.search_with_fallback.return_value = (sample_results, 'google')
        mock_get_searcher.return_value = mock_searcher
        
        # Test the core search functionality
        searcher = mock_get_searcher()
        results, engine_used = searcher.search_with_fallback("test query", 5, True)
        
        assert len(results) == 1
        assert engine_used == 'google'
        mock_searcher.search_with_fallback.assert_called_once_with("test query", 5, True)
    
    @patch('main.get_searcher')
    def test_engine_status_functionality(self, mock_get_searcher):
        """Test the engine status functionality used by MCP tools."""
        mock_searcher = MagicMock()
        mock_searcher.get_engine_status.return_value = {
            'google': 'available',
            'duckduckgo': 'blocked',
            'bing': 'available'
        }
        mock_get_searcher.return_value = mock_searcher
        
        # Test the core engine status functionality
        searcher = mock_get_searcher()
        status = searcher.get_engine_status()
        
        assert status['google'] == 'available'
        assert status['duckduckgo'] == 'blocked'


class TestIntegration:
    """Integration tests for complete search workflows."""
    
    @pytest.fixture
    def sample_results(self):
        return [
            {
                "title": "Python Tutorial",
                "url": "https://python.org/tutorial",
                "domain": "python.org",
                "snippet": "Learn Python programming",
                "rank": 1,
                "source_engine": "google"
            }
        ]
    
    @patch('main.WebSearcher._setup_driver')
    def test_full_search_workflow_google_success(self, mock_setup, sample_results):
        """Test complete search workflow when Google succeeds."""
        searcher = WebSearcher()
        mock_driver = MagicMock()
        searcher.driver = mock_driver
        searcher.driver_initialized = True
        
        # Mock successful Google search
        with patch.object(searcher, '_parse_google_results', return_value=sample_results):
            with patch.object(searcher, '_is_google_blocked', return_value=False):
                results, engine_used = searcher.search_with_fallback("python programming", 5, True)
        
        assert len(results) == 1
        assert engine_used == "google"
        assert all(result['source_engine'] == 'google' for result in results)
        assert 'google' not in searcher.blocked_engines
    
    def test_manual_engine_blocking(self):
        """Test manual engine blocking and status."""
        searcher = WebSearcher()
        
        # Manually block engines
        searcher.blocked_engines.add('google')
        searcher.blocked_engines.add('duckduckgo')
        
        status = searcher.get_engine_status()
        assert status['google'] == 'blocked'
        assert status['duckduckgo'] == 'blocked' 
        assert status['bing'] == 'available'
        
        # Reset engines
        searcher.reset_blocked_engines()
        status = searcher.get_engine_status()
        assert all(s == 'available' for s in status.values())


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    @pytest.fixture
    def searcher(self):
        return WebSearcher()
    
    @pytest.fixture
    def mock_driver(self):
        return MagicMock()
    
    def test_empty_search_query(self, searcher, mock_driver):
        """Test search with empty query."""
        searcher.driver = mock_driver
        searcher.driver_initialized = True
        
        with patch.object(searcher, '_parse_google_results', return_value=[]):
            results = searcher._search_google("", 10, True)
        
        assert len(results) == 0
    
    def test_selenium_timeout_exception(self, searcher, mock_driver):
        """Test handling of Selenium timeout exceptions."""
        searcher.driver = mock_driver
        searcher.driver_initialized = True
        mock_driver.get.side_effect = TimeoutException("Page load timeout")
        
        with pytest.raises(Exception):
            searcher._search_google("test query", 10, True)
    
    def test_close_driver(self, searcher, mock_driver):
        """Test closing the driver."""
        searcher.driver = mock_driver
        
        searcher.close()
        
        mock_driver.quit.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 