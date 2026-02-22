"""
Build analyst and judge prompts using real data from Neo4j and data folder.

- Analyst prompt: Neo4j context (profile, earnings, news, peers, recommendation) + optional
  market row (close, next_day_return, target) so the LLM is grounded in real numbers.
- Judge prompt: context summary + model output + optional ground truth for LLM-as-judge scoring.
"""

import json
from typing import Any, Optional


def build_analyst_prompt(
    neo4j_context: dict[str, Any],
    data_row: Optional[dict[str, Any]] = None,
    include_ground_truth_in_prompt: bool = False,
) -> str:
    """
    Build the user prompt for the analyst LLM using real Neo4j context and optional
    market data row from data/processed (or data folder).
    """
    parts = [
        "You are a financial analyst. Base your answer ONLY on the following structured context.",
        "Give one recommendation: BUY, HOLD, or SELL, then in 2–4 sentences explain why, citing specific facts from the context (earnings, news, sector, peers, and any market data below).",
        "",
        "--- CONTEXT FROM KNOWLEDGE GRAPH (Neo4j) ---",
        json.dumps({
            "name": neo4j_context.get("name"),
            "sector": neo4j_context.get("sector"),
            "industry": neo4j_context.get("industry"),
            "market_cap": neo4j_context.get("market_cap"),
            "earnings": neo4j_context.get("earnings", []),
            "news_headlines": neo4j_context.get("news_headlines", []),
            "peers": neo4j_context.get("peers", []),
            "analyst_recommendation_summary": neo4j_context.get("recommendation"),
        }, indent=2),
    ]
    if data_row:
        market_block: dict[str, Any] = {
            "ticker": data_row.get("ticker"),
            "date": data_row.get("date"),
            "close": data_row.get("close"),
            "next_day_return_pct": round(data_row.get("next_day_return", 0) * 100, 2) if data_row.get("next_day_return") is not None else None,
            "news_count_that_day": data_row.get("news_count"),
        }
        if include_ground_truth_in_prompt and data_row.get("target"):
            market_block["ground_truth_label"] = data_row.get("target")  # for debugging; usually omit for analyst
        if data_row.get("news_text_snippet"):
            market_block["news_text_snippet"] = data_row["news_text_snippet"][:800] + "..." if len(data_row.get("news_text_snippet", "")) > 800 else data_row.get("news_text_snippet")
        parts.append("")
        parts.append("--- MARKET DATA (from data folder, same ticker/date) ---")
        parts.append(json.dumps(market_block, indent=2))
    parts.append("")
    parts.append("--- INSTRUCTIONS ---")
    parts.append("Reply with exactly two lines:")
    parts.append("RECOMMENDATION: <BUY|HOLD|SELL>")
    parts.append("EXPLANATION: <your short explanation citing the context above>")
    return "\n".join(parts)


PROMPT_VARIANTS = ("standard", "earnings_focus", "news_focus")


def build_analyst_prompt_variant(
    neo4j_context: dict[str, Any],
    data_row: Optional[dict[str, Any]] = None,
    variant: str = "standard",
    include_ground_truth_in_prompt: bool = False,
) -> str:
    """
    Build analyst prompt with a specific explainability variant.
    variant: standard (default), earnings_focus (emphasize earnings), news_focus (emphasize news).
    """
    if variant == "standard":
        return build_analyst_prompt(neo4j_context, data_row, include_ground_truth_in_prompt)
    base = build_analyst_prompt(neo4j_context, data_row, include_ground_truth_in_prompt)
    if variant == "earnings_focus":
        focus = (
            "\nFocus your explanation on earnings (actual vs estimate, surprise), "
            "sector comparables, and how they support your recommendation."
        )
    elif variant == "news_focus":
        focus = (
            "\nFocus your explanation on recent news headlines and sentiment, "
            "and how they support your recommendation."
        )
    else:
        focus = ""
    # Insert focus instruction before "--- INSTRUCTIONS ---"
    if focus and "--- INSTRUCTIONS ---" in base:
        base = base.replace(
            "--- INSTRUCTIONS ---",
            "--- ADDITIONAL GUIDANCE ---" + focus + "\n\n--- INSTRUCTIONS ---",
        )
    return base


def build_judge_system_prompt() -> str:
    """System prompt for the LLM judge."""
    return (
        "You are an expert evaluator for financial analysis systems. Your task is to score "
        "the quality of a model's stock recommendation and explanation given the same context the model saw. "
        "Be strict but fair. Output valid JSON only, no markdown or extra text."
    )


def build_judge_user_prompt(
    context_summary: str,
    model_output: str,
    ground_truth_target: Optional[str] = None,
) -> str:
    """
    Build the user prompt for the LLM judge. context_summary should be a short summary of
    what the model was given (Neo4j + market data). model_output is the analyst's
    RECOMMENDATION + EXPLANATION. If ground_truth_target is provided (buy/hold/sell),
    the judge can also score correctness.
    """
    parts = [
        "Evaluate the following model output for a stock recommendation task.",
        "",
        "CONTEXT THAT THE MODEL SAW (summary):",
        context_summary[:3000] + "..." if len(context_summary) > 3000 else context_summary,
        "",
        "MODEL OUTPUT:",
        model_output,
        "",
    ]
    if ground_truth_target:
        parts.append(f"GROUND TRUTH LABEL (actual outcome class): {ground_truth_target.upper()}")
        parts.append("")
    parts.append(
        "Score the following on 1–5 (1=poor, 5=excellent). Reply with JSON only, e.g.:"
    )
    parts.append(
        '{"faithfulness": N, "relevance": N, "consistency": N, "correctness": N, "justification": "one short paragraph"}'
    )
    parts.append(
        "- faithfulness: Does the explanation cite only facts present in the context? (no hallucination)"
    )
    parts.append(
        "- relevance: Are the cited facts relevant to the recommendation?"
    )
    parts.append(
        "- consistency: Does the explanation logically support the stated recommendation?"
    )
    parts.append(
        "- correctness: Does the recommendation match the ground truth label? (only if provided)"
    )
    if not ground_truth_target:
        parts.append("(Omit correctness or set to null if no ground truth.)")
    return "\n".join(parts)


def context_summary_for_judge(neo4j_context: dict[str, Any], data_row: Optional[dict[str, Any]] = None) -> str:
    """Produce a short text summary of context for the judge prompt."""
    parts = [
        f"Ticker: {neo4j_context.get('ticker')}; Name: {neo4j_context.get('name')}; Sector: {neo4j_context.get('sector')}.",
        f"Earnings: {len(neo4j_context.get('earnings') or [])} periods; News headlines: {len(neo4j_context.get('news_headlines') or [])}; Peers: {neo4j_context.get('peers', [])}.",
    ]
    if data_row:
        parts.append(
            f"Market data: date={data_row.get('date')}, close={data_row.get('close')}, "
            f"next_day_return_pct={round((data_row.get('next_day_return') or 0) * 100, 2)}%."
        )
    return " ".join(parts)
