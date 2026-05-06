# Web Search MCP

[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/pranavms13/web-search-mcp)
[![Install MCP Server](https://cursor.com/deeplink/mcp-install-dark.svg)](https://cursor.com/en/install-mcp?name=web-search-mcp&config=eyJjb21tYW5kIjoidXZ4IGdpdCtodHRwczovL2dpdGh1Yi5jb20vcHJhbmF2bXMxMy93ZWItc2VhcmNoLW1jcCIsImVudiI6e319)

Production-ready MCP server for web search and webpage extraction using Selenium.

It queries multiple engines with fallback support:

1. Google
2. DuckDuckGo
3. Bing

Supported browsers: `chrome` (default), `edge`, `firefox`.

---

## Why this project exists

Many MCP workflows need fresh web data but run into brittle scraping scripts.

This server provides:

- A stable MCP interface
- Structured results (`title`, `url`, `domain`, `snippet`, `rank`)
- Engine fallback when one provider is blocked or rate-limited
- Browser selection per request

---

## Quick start (5 minutes)

### 1) Prerequisites

- Python `3.10+`
- At least one installed browser: Chrome, Edge, or Firefox
- Internet access

### 2) Install dependencies

Using `uv` (recommended):

```bash
uv sync
```

Using `pip`:

```bash
pip install -e .
```

### 3) Run the MCP server

```bash
python main.py
```

Alternative entrypoint:

```bash
web-search-mcp
```

Expected startup log includes:

`Starting MCP server 'Web Search MCP' with transport 'stdio'`

---

## Tools exposed

### `search_web`

Searches the web with automatic engine fallback.

#### Parameters (`search_web`)

- `query` (`str`, required): search query
- `max_results` (`int`, optional): default `10`, max `100`
- `include_snippets` (`bool`, optional): default `true`
- `browser` (`str`, optional): `chrome | edge | firefox`, default `chrome`

#### Returns (`search_web`)

List of objects with:

- `title`
- `url`
- `domain`
- `snippet` (if enabled)
- `rank`
- `source_engine`

---

### `get_webpage_content`

Fetches and extracts text from a webpage.

#### Parameters (`get_webpage_content`)

- `url` (`str`, required)
- `max_length` (`int`, optional): default `5000`, max `20000`
- `browser` (`str`, optional): `chrome | edge | firefox`, default `chrome`

#### Returns

- `url`
- `title`
- `content`
- `length`

---

### `get_search_engine_status`

Returns whether each engine is currently considered `available` or `blocked`
for the current searcher session.

#### Parameters (`get_search_engine_status`)

- `browser` (`str`, optional): `chrome | edge | firefox`, default `chrome`

---

### `reset_search_engines`

Clears blocked-engine state for a given browser session.

#### Parameters (`reset_search_engines`)

- `browser` (`str`, optional): `chrome | edge | firefox`, default `chrome`

---

## Configure in MCP clients

### Claude Desktop (local checkout)

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

Windows example path:

`d:\\trabajo\\web-search`

### Run directly from GitHub via `uvx`

```json
{
  "mcpServers": {
    "web-search-mcp": {
      "command": "uvx",
      "args": ["git+https://github.com/naml14/web-search"]
    }
  }
}
```

### Run via `uvx` with local EdgeDriver (optional)

If your environment blocks driver downloads, provide a local `msedgedriver` path:

```json
{
  "mcpServers": {
    "web-search-mcp": {
      "command": "uvx",
      "args": ["git+https://github.com/naml14/web-search"],
      "env": {
        "MSEDGEDRIVER_PATH": "C:\\tools\\edgedriver\\msedgedriver.exe"
      }
    }
  }
}
```

Alternative key:

```json
{
  "mcpServers": {
    "web-search-mcp": {
      "command": "uvx",
      "args": ["git+https://github.com/naml14/web-search"],
      "env": {
        "WEBDRIVER_EDGE_DRIVER": "C:\\tools\\edgedriver\\msedgedriver.exe"
      }
    }
  }
}
```

---

## Usage examples (natural language in MCP client)

- `Search for "python web scraping tutorials" and show top 5 results.`
- `Search for "latest AI safety papers" using Firefox.`
- `Get webpage content from https://example.com/article.`

---

## Smoke test (real call from Python client)

If you want to validate tool calls outside Claude/Desktop, use `fastmcp.client`:

```python
import asyncio
from fastmcp.client import Client, PythonStdioTransport

async def main():
    transport = PythonStdioTransport(script_path="main.py")
    async with Client(transport, timeout=120) as client:
        status = await client.call_tool("get_search_engine_status", {"browser": "edge"})
        print(status)

asyncio.run(main())
```

---

## Browser notes

- `chrome` and `edge` use Chromium-like flags
- `firefox` uses Firefox-specific options and UA override
- `chrome` and `firefox` drivers are managed via `webdriver-manager`
- `edge` now prefers a local `msedgedriver` binary, and otherwise downloads from `https://msedgedriver.microsoft.com`

---

## Troubleshooting

### `Could not reach host. Are you offline?`

Root cause is usually connectivity (DNS, proxy, firewall, or temporary outage).

Check:

- Internet connectivity from host
- Corporate proxy/VPN restrictions
- Whether outbound traffic to search engines is blocked

### Browser/driver startup failures

Check:

- Browser is installed locally
- Browser can launch manually
- Antivirus or policy is not blocking WebDriver startup

Try switching browser parameter:

- `edge` → `chrome` → `firefox`

#### Microsoft Edge WebDriver matching strategy

For Edge, this project follows Microsoft guidance:

- Detect installed Edge version (for example `147.0.3912.98`).
  - On Windows, version is read from the Edge registry (`BLBeacon`) first.
  - CLI `msedge --version` is used only as a fallback.
- Try matching EdgeDriver version first.
- If exact match is unavailable, resolve a compatible release with same `major.minor.build`.
- Download the platform ZIP from `https://msedgedriver.microsoft.com/{version}/...`.

Examples:

- Windows x64: `https://msedgedriver.microsoft.com/147.0.3912.98/edgedriver_win64.zip`
- Windows x86: `https://msedgedriver.microsoft.com/147.0.3912.98/edgedriver_win32.zip`
- Windows ARM64: `https://msedgedriver.microsoft.com/147.0.3912.98/edgedriver_arm64.zip`
- macOS Intel: `https://msedgedriver.microsoft.com/147.0.3912.98/edgedriver_mac64.zip`
- macOS Apple Silicon: `https://msedgedriver.microsoft.com/147.0.3912.98/edgedriver_mac64_m1.zip`
- Linux x64: `https://msedgedriver.microsoft.com/147.0.3912.98/edgedriver_linux64.zip`

#### Edge local driver fallback (recommended)

Resolution order for Edge driver:

1. `MSEDGEDRIVER_PATH`
2. `WEBDRIVER_EDGE_DRIVER`
3. `msedgedriver` in `PATH`
4. Download from `msedgedriver.microsoft.com`

Downloaded drivers are cached under `~/.wdm/drivers/msedgedriver/<version>/`.

### Empty or inconsistent results

Expected in scraping ecosystems due to:

- Search engine anti-bot behavior
- Geographic/result personalization
- Rate limiting

Use lower request frequency and retries where needed.

---

## Limitations

- Subject to engine rate limits and anti-automation behavior
- Results vary by location/time/account context
- Some target websites may block automated browsers

---

## Development workflow

1. Clone repository
2. Install dependencies (`uv sync` or `pip install -e .`)
3. Run server (`python main.py`)
4. Validate with MCP client or FastMCP client script

---

## Tech stack

- `fastmcp`
- `selenium`
- `webdriver-manager`
- `beautifulsoup4`
- `requests`
- `lxml`

---

## License

MIT — see [LICENSE](./LICENSE).

## Contributing

Pull requests are welcome. Please include a clear description, reproducible steps,
and (when relevant) sample tool-call output.
