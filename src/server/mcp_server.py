"""
MCP Server for DSC288 Financial Decision Support System.
Exposes multi-agent financial analysis tools to Cursor IDE via MCP protocol.

Run:  python server/mcp_server.py
Then add to Cursor MCP settings:
  {
    "mcpServers": {
      "financial-analyst": {
        "command": "python",
        "args": ["server/mcp_server.py"],
        "cwd": "<repo-root>"
      }
    }
  }
"""

import json
import sys
import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

# Will be replaced with actual imports once agents are built
# from agents.orchestrator import run_analysis
# from agents.sentiment import quick_sentiment
# from agents.technical import technical_snapshot

try:
    from mcp.server.stdio import stdio_server
    from mcp.server import Server
    from mcp import types
    HAS_MCP = True
except ImportError:
    HAS_MCP = False


def load_api_key():
    key_file = BASE_DIR / ".key"
    if key_file.exists():
        key = key_file.read_text().strip()
        os.environ["OPENAI_API_KEY"] = key
        return key
    return os.environ.get("OPENAI_API_KEY", "")


def create_server():
    server = Server("financial-analyst")

    @server.list_tools()
    async def list_tools():
        return [
            types.Tool(
                name="analyze_stock",
                description=(
                    "Run full multi-agent analysis on a stock ticker. "
                    "Returns buy/hold/sell recommendation with explanation, "
                    "citing specific news articles and technical indicators."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ticker": {
                            "type": "string",
                            "description": "Stock ticker symbol (e.g. AAPL, MSFT)"
                        },
                        "date": {
                            "type": "string",
                            "description": "Analysis date in YYYY-MM-DD format (optional, defaults to latest)"
                        }
                    },
                    "required": ["ticker"]
                }
            ),
            types.Tool(
                name="get_sentiment",
                description=(
                    "Get sentiment analysis for a stock over a date range. "
                    "Returns per-article sentiment scores and aggregated sentiment trend."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ticker": {"type": "string", "description": "Stock ticker symbol"},
                        "start_date": {"type": "string", "description": "Start date YYYY-MM-DD"},
                        "end_date": {"type": "string", "description": "End date YYYY-MM-DD"}
                    },
                    "required": ["ticker"]
                }
            ),
            types.Tool(
                name="technical_snapshot",
                description=(
                    "Get technical analysis snapshot: SMA crossovers, momentum, "
                    "volatility regime, volume signals, and price-to-SMA ratios."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ticker": {"type": "string", "description": "Stock ticker symbol"},
                        "date": {"type": "string", "description": "Date YYYY-MM-DD (optional)"}
                    },
                    "required": ["ticker"]
                }
            ),
            types.Tool(
                name="search_news",
                description=(
                    "Search financial news articles for a ticker. "
                    "Returns matching articles with dates, sources, and full text."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ticker": {"type": "string", "description": "Stock ticker symbol"},
                        "query": {"type": "string", "description": "Search query (optional)"},
                        "limit": {"type": "integer", "description": "Max results (default 5)"}
                    },
                    "required": ["ticker"]
                }
            ),
            types.Tool(
                name="backtest",
                description=(
                    "Simulate trading using the model's buy/hold/sell signals "
                    "over a date range. Returns cumulative return, Sharpe ratio, "
                    "and comparison to buy-and-hold benchmark."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ticker": {"type": "string", "description": "Stock ticker symbol"},
                        "start_date": {"type": "string", "description": "Start date YYYY-MM-DD"},
                        "end_date": {"type": "string", "description": "End date YYYY-MM-DD"}
                    },
                    "required": ["ticker", "start_date", "end_date"]
                }
            ),
            types.Tool(
                name="evaluate_model",
                description=(
                    "Get model evaluation metrics: Macro F1, per-class precision/recall, "
                    "confusion matrix, and RAGAS explanation quality scores."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "split": {
                            "type": "string",
                            "enum": ["validation", "test"],
                            "description": "Which split to evaluate on"
                        }
                    },
                    "required": ["split"]
                }
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict):
        # Placeholder implementations — will be wired to actual agents
        if name == "analyze_stock":
            return [types.TextContent(
                type="text",
                text=json.dumps({
                    "status": "not_yet_implemented",
                    "message": f"Multi-agent analysis for {arguments['ticker']} will be available after Phase 2.",
                    "architecture": "Technical → Sentiment → Fundamental → Optimistic/Cautious debate → Synthesizer"
                }, indent=2)
            )]

        return [types.TextContent(
            type="text",
            text=json.dumps({"status": "not_yet_implemented", "tool": name, "args": arguments}, indent=2)
        )]

    return server


async def main():
    load_api_key()
    server = create_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    if not HAS_MCP:
        print("MCP SDK not installed. Run: pip install mcp")
        sys.exit(1)
    asyncio.run(main())
