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

from src.agents.graph_context import get_stock_context, get_news_for_ticker
from src.agents.data_context import get_row_for_ticker_date, sample_rows_for_judge
from src.agents.prompt_builder import build_analyst_prompt, context_summary_for_judge
from src.agents.llm_judge import judge_async
from src.evaluation.classification_eval import run_classification_eval, format_metrics_report

try:
    from openai import AsyncOpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

try:
    from mcp.server.stdio import stdio_server
    from mcp.server import Server
    from mcp import types
    HAS_MCP = True
except ImportError:
    HAS_MCP = False


# LiteLLM proxy (manage.py start litellm)
LITELLM_BASE_URL = os.environ.get("LITELLM_BASE_URL", "http://localhost:4000")
LITELLM_API_KEY = os.environ.get("LITELLM_MASTER_KEY", "sk-ds288r")
LITELLM_MODEL = os.environ.get("LITELLM_MODEL", "gpt-4o")


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
            types.Tool(
                name="evaluate_with_judge",
                description=(
                    "Run analyst LLM on real Neo4j + data-folder context, then LLM-as-judge scores "
                    "the output (faithfulness, relevance, consistency, correctness vs ground truth). "
                    "Provide ticker and optional date; or leave date empty to sample from validation split."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ticker": {"type": "string", "description": "Stock ticker symbol"},
                        "date": {"type": "string", "description": "Date YYYY-MM-DD (optional; if omitted a row is sampled from validation)"},
                        "split": {"type": "string", "enum": ["validation", "test"], "description": "Split to sample from when date not provided (default validation)"}
                    },
                    "required": ["ticker"]
                }
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict):
        if name == "evaluate_model":
            split = arguments.get("split", "validation")
            if split not in ("validation", "test"):
                split = "validation"
            try:
                result = run_classification_eval(split)
                report = format_metrics_report(result)
                return [types.TextContent(type="text", text=report)]
            except FileNotFoundError as e:
                return [types.TextContent(type="text", text=f"Evaluation error: {e}")]
            except Exception as e:
                return [types.TextContent(type="text", text=f"Evaluation error: {e}")]

        if name == "analyze_stock":
            ticker = (arguments.get("ticker") or "").strip().upper()
            date_arg = (arguments.get("date") or "").strip() or None
            if not ticker:
                return [types.TextContent(type="text", text="Error: ticker is required.")]
            try:
                ctx = get_stock_context(ticker, news_limit=5, earnings_limit=4)
                if not ctx.get("found"):
                    return [types.TextContent(
                        type="text",
                        text=f"No graph data found for {ticker}. Ensure Neo4j is populated (e.g. run fin_memory memorize --ticker {ticker})."
                    )]
                data_row = get_row_for_ticker_date(ticker, date_arg) if date_arg else None
                prompt = build_analyst_prompt(ctx, data_row, include_ground_truth_in_prompt=False)
                if HAS_OPENAI:
                    client = AsyncOpenAI(base_url=LITELLM_BASE_URL, api_key=LITELLM_API_KEY)
                    resp = await client.chat.completions.create(
                        model=LITELLM_MODEL,
                        messages=[{"role": "user", "content": prompt}],
                        max_tokens=500,
                    )
                    content = (resp.choices[0].message.content or "").strip()
                    return [types.TextContent(type="text", text=f"**{ticker}**" + (f" ({date_arg})" if date_arg else "") + f"\n\n{content}")]
                return [types.TextContent(
                    type="text",
                    text=f"LiteLLM client not available. Prompt built from Neo4j + data folder for {ticker}."
                )]
            except Exception as e:
                return [types.TextContent(type="text", text=f"analyze_stock error: {e}")]

        if name == "evaluate_with_judge":
            ticker = (arguments.get("ticker") or "").strip().upper()
            date_arg = (arguments.get("date") or "").strip() or None
            split = arguments.get("split", "validation")
            if split not in ("validation", "test"):
                split = "validation"
            if not ticker:
                return [types.TextContent(type="text", text="Error: ticker is required.")]
            try:
                ctx = get_stock_context(ticker, news_limit=5, earnings_limit=4)
                if not ctx.get("found"):
                    return [types.TextContent(
                        type="text",
                        text=f"No graph data for {ticker}. Populate Neo4j first."
                    )]
                if date_arg:
                    data_row = get_row_for_ticker_date(ticker, date_arg, split=split)
                else:
                    rows = sample_rows_for_judge(split=split, n=1, tickers=[ticker], seed=42)
                    data_row = rows[0] if rows else None
                if not data_row:
                    return [types.TextContent(
                        type="text",
                        text=f"No processed data row for {ticker}" + (f" on {date_arg}" if date_arg else f" in {split} split. Run pipeline and ensure ticker exists.")
                    )]
                prompt = build_analyst_prompt(ctx, data_row, include_ground_truth_in_prompt=False)
                ground_truth = (data_row.get("target") or "hold").lower()
                if ground_truth not in ("buy", "hold", "sell"):
                    ground_truth = "hold"
                if not HAS_OPENAI:
                    return [types.TextContent(type="text", text="OpenAI client not available.")]
                client = AsyncOpenAI(base_url=LITELLM_BASE_URL, api_key=LITELLM_API_KEY)
                resp = await client.chat.completions.create(
                    model=LITELLM_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=500,
                )
                model_output = (resp.choices[0].message.content or "").strip()
                summary = context_summary_for_judge(ctx, data_row)
                judge_result = await judge_async(summary, model_output, ground_truth_target=ground_truth)
                pred_line = next((l for l in model_output.splitlines() if l.strip().upper().startswith("RECOMMENDATION:")), "")
                pred = "hold"
                for c in ("BUY", "HOLD", "SELL"):
                    if c in pred_line.upper():
                        pred = c.lower()
                        break
                correct = 1 if pred == ground_truth else 0
                lines = [
                    f"**{ticker}** date={data_row.get('date')}",
                    f"Ground truth: {ground_truth.upper()}  |  Predicted: {pred.upper()}  |  Correct: {'Yes' if correct else 'No'}",
                    "",
                    "--- Model output ---",
                    model_output,
                    "",
                    "--- LLM Judge (gpt-5.2-chat) ---",
                    f"  Faithfulness: {judge_result.get('faithfulness')}  Relevance: {judge_result.get('relevance')}  Consistency: {judge_result.get('consistency')}  Correctness: {judge_result.get('correctness')}",
                    f"  Justification: {judge_result.get('justification', '')[:400]}",
                ]
                return [types.TextContent(type="text", text="\n".join(lines))]
            except Exception as e:
                return [types.TextContent(type="text", text=f"evaluate_with_judge error: {e}")]

        if name == "search_news":
            ticker = (arguments.get("ticker") or "").strip().upper()
            query = (arguments.get("query") or "").strip() or None
            limit = arguments.get("limit")
            if limit is None:
                limit = 5
            limit = max(1, min(50, int(limit)))
            if not ticker:
                return [types.TextContent(type="text", text="Error: ticker is required.")]
            try:
                articles = get_news_for_ticker(ticker, limit=limit, query=query)
                if not articles:
                    return [types.TextContent(
                        type="text",
                        text=f"No news found for {ticker}" + (f" matching '{query}'." if query else ".")
                    )]
                lines = [f"News for {ticker}" + (f" (query: {query})" if query else "") + "\n"]
                for i, a in enumerate(articles, 1):
                    lines.append(f"{i}. {a.get('headline') or 'N/A'}")
                    if a.get("source"):
                        lines.append(f"   Source: {a['source']}")
                    if a.get("summary"):
                        lines.append(f"   Summary: {a['summary'][:200]}...")
                    lines.append("")
                return [types.TextContent(type="text", text="\n".join(lines))]
            except Exception as e:
                return [types.TextContent(type="text", text=f"search_news error: {e}")]

        # Placeholders for other tools
        if name == "get_sentiment":
            return [types.TextContent(
                type="text",
                text=json.dumps({"status": "not_yet_implemented", "tool": name, "message": "Per-article sentiment pipeline coming in Phase 2."}, indent=2)
            )]
        if name == "technical_snapshot":
            return [types.TextContent(
                type="text",
                text=json.dumps({"status": "not_yet_implemented", "tool": name, "message": "Technical snapshot pipeline coming in Phase 2."}, indent=2)
            )]
        if name == "backtest":
            return [types.TextContent(
                type="text",
                text=json.dumps({"status": "not_yet_implemented", "tool": name, "message": "Backtest using model signals coming in Phase 2."}, indent=2)
            )]

        return [types.TextContent(
            type="text",
            text=json.dumps({"status": "unknown_tool", "tool": name, "args": arguments}, indent=2)
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
