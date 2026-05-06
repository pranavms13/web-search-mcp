# Web Search MCP

[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/pranavms13/web-search-mcp)

A Model Context Protocol (MCP) server that provides web search functionality using Selenium browsers to scrape Google, DuckDuckGo and Bing search results.

[![Install MCP Server](https://cursor.com/deeplink/mcp-install-dark.svg)](https://cursor.com/en/install-mcp?name=web-search-mcp&config=eyJjb21tYW5kIjoidXZ4IGdpdCtodHRwczovL2dpdGh1Yi5jb20vcHJhbmF2bXMxMy93ZWItc2VhcmNoLW1jcCIsImVudiI6e319)

## Features

- **Google Search**: Search Google and get structured results with titles, URLs, snippets, and rankings
- **Web Page Content**: Fetch and extract text content from any webpage
- **Multiple Browsers**: Supports `chrome` (default), `edge`, and `firefox`
- **Selenium-based**: Uses Selenium WebDriver with `webdriver-manager` for reliable scraping
- **MCP Compatible**: Fully compatible with Claude Desktop and other MCP clients

## Tools Available

### `search_web`

Search the web using Google with automatic fallback to DuckDuckGo and Bing, and return structured results.

**Parameters:**

- `query` (string): The search query string
- `max_results` (int, optional): Maximum number of results to return (default: 10, max: 100)
- `include_snippets` (bool, optional): Whether to include text snippets (default: true)
- `browser` (string, optional): Browser to use for Selenium. Supported values: `chrome`, `edge`, `firefox`. Default: `chrome`

**Returns:**

- `title`: Page title
- `url`: Full URL
- `domain`: Domain name
- `snippet`: Text snippet (if enabled)
- `rank`: Search result ranking

### `get_webpage_content`

Fetch and return the text content of a webpage.

**Parameters:**

- `url` (string): The URL of the webpage to fetch
- `max_length` (int, optional): Maximum content length (default: 5000, max: 20000)
- `browser` (string, optional): Browser to use for Selenium. Supported values: `chrome`, `edge`, `firefox`. Default: `chrome`

**Returns:**

- `url`: The requested URL
- `title`: Page title
- `content`: Extracted text content
- `length`: Content length in characters

## Installation

1. **Install dependencies:**

   ```bash
   # Using uv (recommended)
   uv sync

   # Or using pip
   pip install -e .
   ```

2. **Install at least one supported browser** (required for Selenium):
   - **Chrome**
     - macOS: `brew install --cask google-chrome`
     - Ubuntu: `sudo apt-get install google-chrome-stable`
     - Windows: Download from the Google Chrome website
   - **Edge**
     - macOS / Windows: Install Microsoft Edge from the Microsoft website
     - Ubuntu: Install Microsoft Edge from Microsoft's Linux packages
   - **Firefox**
     - macOS: `brew install --cask firefox`
     - Ubuntu: `sudo apt-get install firefox`
     - Windows: Download from the Mozilla Firefox website

3. **Driver binaries** are automatically downloaded and managed by `webdriver-manager` for the selected browser.

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

If you want Claude Desktop to use your current local checkout of this repository, point it at the cloned folder with `uv`:

```json
{
  "mcpServers": {
    "web-search-mcp": {
      "command": "uv",
      "args": [
        "--directory",
        "/absolute/path/to/web-search",
        "run",
        "web-search-mcp"
      ]
    }
  }
}
```

On Windows, replace `/absolute/path/to/web-search` with the path to your clone, for example `d:\\trabajo\\web-search`.

If you prefer to run the GitHub version of this current repository instead of your local checkout, you can use:

```json
{
  "mcpServers": {
    "web-search-mcp": {
      "command": "uvx",
      "args": ["git+https://github.com/naml14/web-search.git"]
    }
  }
}
```

### Example Usage in Claude

Once connected, you can use the tools like this:

```text
Search for "python web scraping tutorials" and show me the top 5 results.

Search for "python web scraping tutorials" using Firefox and show me the top 5 results.

Get the content from this webpage: https://example.com/article
```

## Configuration

The web searcher uses these browser settings by default:

- `chrome`: Chromium-style automation flags and Chrome user agent
- `edge`: Chromium-style automation flags and Edge user agent
- `firefox`: Firefox-specific user agent override and window sizing

Chrome remains the default browser when `browser` is omitted, so existing clients keep working unchanged.

## Error Handling

The tool includes comprehensive error handling for:

- Network timeouts
- WebDriver failures
- Page parsing errors
- Invalid URLs

Errors are logged and graceful fallbacks are provided.

## Requirements

- Python 3.10+
- One of: Chrome, Edge, or Firefox
- Internet connection

## Dependencies

- `fastmcp`: MCP server framework
- `selenium`: Web browser automation
- `beautifulsoup4`: HTML parsing
- `webdriver-manager`: Browser driver management for Chrome, Edge, and Firefox
- `requests`: HTTP requests
- `lxml`: XML/HTML parser

## Limitations

- Respects Google's rate limiting
- Results may vary based on location and Google's algorithms
- Some websites may block automated access
- The selected browser must be installed on the host machine

## Development

To modify or extend the functionality:

1. Clone the repository
2. Install in development mode: `uv sync` or `pip install -e .`
3. Make your changes
4. Test with `python main.py`

## License

This project is licensed under MIT License. You can check it out at - [LICENSE](/LICENSE)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
