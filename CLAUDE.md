# Web Search MCP — Project Guide

MCP server exposing web search + page-content tools. It scrapes search engine
result pages through a headless browser and returns structured results.

## Commands

```bash
uv sync                              # install deps (dev group includes pytest)
uv run pytest test.py -q             # run the test suite
python main.py                       # run the MCP server (stdio transport)
web-search-mcp                       # same, via the installed console script

# Run against the Obscura backend instead of Selenium/Chrome:
BROWSER_BACKEND=obscura OBSCURA_BIN="$PWD/obscura-binaries/obscura" python main.py
```

## Architecture (`main.py`)

Two layers, kept deliberately decoupled:

1. **Browser backends** — render a URL and return `(html, title)`:
   - `BrowserBackend` — abstract interface (`fetch_html`, `close`).
   - `SeleniumBackend` — lazy headless-Chrome driver via webdriver-manager.
   - `ObscuraBackend` — shells out to the Obscura CLI
     (`obscura fetch <url> --dump html --wait-until networkidle0 --timeout N`).
   - `_build_backend()` — selects the backend from the `BROWSER_BACKEND` env var
     (default `selenium`). For `obscura`, it resolves the binary from `OBSCURA_BIN`
     or `PATH`; if not found it **logs a warning and falls back to Selenium**.

2. **`WebSearcher`** — engine-agnostic scraping/parsing on top of a backend:
   - Multi-engine fallback (`search_with_fallback`): Google → DuckDuckGo → Bing.
     A failing engine is added to `blocked_engines` for the session.
   - Per-engine parsers (`_parse_google/_duckduckgo/_bing_results`) work on the
     rendered HTML with **BeautifulSoup**, so they are identical across backends.
   - `_normalize_url` unwraps redirect wrappers to the real destination:
     Google `/url?q=`, DuckDuckGo `//duckduckgo.com/l/?uddg=`, Bing `/ck/a?...u=a1<base64url>`.

**MCP tools** (FastMCP, decorated with `@mcp.tool()`): `search_web`,
`get_webpage_content`, `get_search_engine_status`, `reset_search_engines`.
A single lazy global `WebSearcher` is created via `get_searcher()`.

## Conventions & gotchas

- **Backends only return HTML+title.** All result extraction is BeautifulSoup in
  `WebSearcher`; do not push engine-specific parsing into a backend.
- **Always route result hrefs through `_normalize_url`.** Raw hrefs are redirect
  wrappers — using them directly yields useless `bing.com`/`duckduckgo.com` URLs.
  This was a real bug; the parser tests use the wrapped-href markup to guard it.
- **DuckDuckGo uses the no-JS endpoint** `html.duckduckgo.com/html/`, which parses
  far more reliably than the JS SPA.
- **Google frequently blocks** non-stealth headless traffic; relying on the DDG/Bing
  fallback is expected behavior, not a failure.
- **The `obscura-binaries/` directory is gitignored** (~130 MB). Binaries are
  provided/downloaded out of band, not committed.

## Testing notes

Tests mock the backend (`make_backend`) and feed canned HTML fixtures that mirror
real result markup (including redirect-wrapped hrefs). Backend selection, the
Obscura subprocess wrapper, and URL normalization each have dedicated tests. Keep
new engine/selector changes covered by a realistic HTML fixture.
