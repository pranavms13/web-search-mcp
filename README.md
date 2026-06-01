# Web Search MCP
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/pranavms13/web-search-mcp)

A Model Context Protocol (MCP) server that provides web search functionality by scraping Google, DuckDuckGo, and Bing search results through a headless browser.

[![Install MCP Server](https://cursor.com/deeplink/mcp-install-dark.svg)](https://cursor.com/en/install-mcp?name=web-search-mcp&config=eyJjb21tYW5kIjoidXZ4IGdpdCtodHRwczovL2dpdGh1Yi5jb20vcHJhbmF2bXMxMy93ZWItc2VhcmNoLW1jcCIsImVudiI6e319)

## Features

- **Multi-Engine Search**: Searches Google, DuckDuckGo, and Bing with automatic fallback when an engine is blocked or returns nothing
- **Structured Results**: Titles, URLs, domains, snippets, and rankings — with redirect URLs unwrapped to their real destinations
- **Web Page Content**: Fetch and extract text content from any webpage
- **Pluggable Browser Backends**: Selenium + headless Chrome (default) or the lightweight [Obscura](https://github.com/h4ckf0r0day/obscura) headless browser, selected via an environment variable
- **MCP Compatible**: Fully compatible with Claude Desktop and other MCP clients

## Tools Available

### `search_web`
Search the web across multiple engines (Google → DuckDuckGo → Bing) with automatic fallback and return structured results.

**Parameters:**
- `query` (string): The search query string
- `max_results` (int, optional): Maximum number of results to return (default: 10, max: 100)
- `include_snippets` (bool, optional): Whether to include text snippets (default: true)

**Returns:**
- List of search results with:
  - `title`: Page title
  - `url`: Full URL (redirect wrappers resolved to the real destination)
  - `domain`: Domain name
  - `snippet`: Text snippet (if enabled)
  - `rank`: Search result ranking
  - `source_engine`: Which engine produced the result (`google`, `duckduckgo`, or `bing`)

### `get_webpage_content`
Fetch and return the text content of a webpage.

**Parameters:**
- `url` (string): The URL of the webpage to fetch
- `max_length` (int, optional): Maximum content length (default: 5000, max: 20000)

**Returns:**
- Dictionary with:
  - `url`: The requested URL
  - `title`: Page title
  - `content`: Extracted text content
  - `length`: Content length in characters

### `get_search_engine_status`
Report the active browser backend and the availability of each search engine.

**Returns:**
- Dictionary with a `backend` key (`selenium` or `obscura`) plus each engine name mapped to `available` or `blocked`.

### `reset_search_engines`
Clear the list of engines marked as blocked during the session (useful if an engine recovers).

**Returns:**
- A status message string.

## Installation

1. **Install dependencies:**
   ```bash
   # Using uv (recommended)
   uv sync
   
   # Or using pip
   pip install -e .
   ```

2. **Install a browser backend** (pick one):

   - **Selenium (default)** — requires Chrome:
     - On macOS: `brew install --cask google-chrome`
     - On Ubuntu: `sudo apt-get install google-chrome-stable`
     - On Windows: Download from the Google Chrome website

     ChromeDriver is downloaded and managed automatically by webdriver-manager.

   - **Obscura** — no Chrome required. See the [Browser Backends](#browser-backends) section below.

## Usage

### Running the MCP Server

```bash
# Run directly
python main.py

# Or using the installed script
web-search-mcp
```

The server will start and listen for MCP connections.

### Using with Claude Desktop

Add this configuration to your Claude Desktop MCP settings:

```json
{
  "mcpServers": {
    "web-search-mcp": {
      "command": "uvx",
      "args": ["git+https://github.com/pranavms13/web-search-mcp"]
    }
  }
}
```

### Example Usage in Claude

Once connected, you can use the tools like this:

```
Search for "python web scraping tutorials" and show me the top 5 results.

Get the content from this webpage: https://example.com/article
```

## Configuration

The web searcher uses these Chrome options by default:
- Headless mode (no visible browser window)
- Window size: 1920x1080
- User agent: Modern Chrome browser
- Security flags for running in containers

## Browser Backends

The server can render pages with one of two interchangeable backends, selected via the `BROWSER_BACKEND` environment variable:

| Backend    | Value                | Notes                                                              |
|------------|----------------------|-------------------------------------------------------------------|
| Selenium   | `selenium` (default) | Headless Chrome via Selenium + webdriver-manager.                 |
| Obscura    | `obscura`            | [Obscura](https://github.com/h4ckf0r0day/obscura) headless browser via its CLI. Lightweight, stealthy, no Chrome needed. |

Both backends produce fully JS-rendered HTML, which is then parsed with BeautifulSoup, so search results are identical in shape regardless of backend.

### Using Obscura

1. Install the Obscura binary (see its [releases](https://github.com/h4ckf0r0day/obscura/releases)), e.g. on macOS:

   ```bash
   curl -LO https://github.com/h4ckf0r0day/obscura/releases/latest/download/obscura-x86_64-macos.tar.gz
   tar xzf obscura-x86_64-macos.tar.gz
   ```

2. Run the server with Obscura selected:

   ```bash
   BROWSER_BACKEND=obscura web-search-mcp
   ```

If `obscura` is not on your `PATH`, point to it explicitly with `OBSCURA_BIN=/full/path/to/obscura`. When the binary cannot be found, the server logs a warning and falls back to the Selenium backend automatically.

The active backend is reported by the `get_search_engine_status` tool under the `backend` key.

## Error Handling

The tool includes comprehensive error handling for:
- Network timeouts
- WebDriver failures
- Page parsing errors
- Invalid URLs

Errors are logged and graceful fallbacks are provided.

## Requirements

- Python 3.10+
- A browser backend: Chrome (Selenium) **or** the Obscura binary
- Internet connection

## Dependencies

- `fastmcp`: MCP server framework
- `selenium`: Web browser automation (Selenium backend)
- `beautifulsoup4`: HTML parsing
- `webdriver-manager`: Chrome driver management (Selenium backend)
- `lxml`: XML/HTML parser

The Obscura backend has no Python dependency — it is invoked as an external CLI binary.

## Limitations

- Search engines may rate-limit or block automated access; the multi-engine fallback mitigates but does not eliminate this
- Google in particular often blocks non-stealth headless traffic — DuckDuckGo and Bing typically remain available as fallbacks
- Results may vary based on location and each engine's ranking
- The Selenium backend requires Chrome; the Obscura backend requires the Obscura binary

## Development

To modify or extend the functionality:

1. Clone the repository
2. Install in development mode: `uv sync` or `pip install -e .`
3. Make your changes
4. Run the test suite: `uv run pytest test.py -q`
5. Smoke-test the server: `python main.py` (or `BROWSER_BACKEND=obscura OBSCURA_BIN=/path/to/obscura python main.py`)

## License

This project is licensed under MIT License. You can check it out at - [LICENSE](/LICENSE)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.


