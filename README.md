# Web Search MCP
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/pranavms13/web-search-mcp)

A Model Context Protocol (MCP) server that provides web search functionality using a headless Chrome browser to scrape Google, DuckDuckGo and Bing search results.

[![Install MCP Server](https://cursor.com/deeplink/mcp-install-dark.svg)](https://cursor.com/en/install-mcp?name=web-search-mcp&config=eyJjb21tYW5kIjoidXZ4IGdpdCtodHRwczovL2dpdGh1Yi5jb20vcHJhbmF2bXMxMy93ZWItc2VhcmNoLW1jcCIsImVudiI6e319)

## Features

- **Google Search**: Search Google and get structured results with titles, URLs, snippets, and rankings
- **Web Page Content**: Fetch and extract text content from any webpage
- **Headless Browser**: Uses Selenium with Chrome WebDriver for reliable scraping
- **MCP Compatible**: Fully compatible with Claude Desktop and other MCP clients

## Tools Available

### `search_web`
Search the web using Google and return structured results.

**Parameters:**
- `query` (string): The search query string
- `max_results` (int, optional): Maximum number of results to return (default: 10, max: 100)
- `include_snippets` (bool, optional): Whether to include text snippets (default: true)

**Returns:**
- List of search results with:
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

**Returns:**
- Dictionary with:
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

2. **Install Chrome browser** (required for Selenium):
   - On macOS: `brew install --cask google-chrome`
   - On Ubuntu: `sudo apt-get install google-chrome-stable`
   - On Windows: Download from Google Chrome website

3. **ChromeDriver** will be automatically downloaded and managed by webdriver-manager.

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
    "web-search": {
      "command": "python",
      "args": ["/path/to/your/web-search-mcp/main.py"]
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

## Error Handling

The tool includes comprehensive error handling for:
- Network timeouts
- WebDriver failures
- Page parsing errors
- Invalid URLs

Errors are logged and graceful fallbacks are provided.

## Requirements

- Python 3.10+
- Chrome browser
- Internet connection

## Dependencies

- `fastmcp`: MCP server framework
- `selenium`: Web browser automation
- `beautifulsoup4`: HTML parsing
- `webdriver-manager`: Chrome driver management
- `requests`: HTTP requests
- `lxml`: XML/HTML parser

## Limitations

- Respects Google's rate limiting
- Results may vary based on location and Google's algorithms
- Some websites may block automated access
- Chrome browser required for headless operation

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


