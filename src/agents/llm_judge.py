"""
LLM-as-judge: score model recommendation + explanation on faithfulness, relevance,
consistency, and optionally correctness vs ground truth.

Uses the same LiteLLM proxy as the analyst (OpenAI-compatible client).
"""

import json
import os
import re
from typing import Any, Optional

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from openai import OpenAI
    from openai import AsyncOpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

from .prompt_builder import build_judge_system_prompt, build_judge_user_prompt

# Same as MCP server
LITELLM_BASE_URL = os.environ.get("LITELLM_BASE_URL", "http://localhost:4000")
LITELLM_API_KEY = os.environ.get("LITELLM_MASTER_KEY", "sk-ds288r")
JUDGE_MODEL = os.environ.get("LITELLM_JUDGE_MODEL", "gpt-5.2-chat")


def _parse_judge_response(text: str) -> dict[str, Any]:
    """Extract JSON from judge LLM response (may be wrapped in markdown)."""
    text = (text or "").strip()
    # Try raw JSON
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Strip markdown code block
    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass
    # Find first { ... }
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return {"raw": text, "parse_error": True}


def judge_sync(
    context_summary: str,
    model_output: str,
    ground_truth_target: Optional[str] = None,
    model: Optional[str] = None,
) -> dict[str, Any]:
    """
    Call judge LLM synchronously. Returns dict with:
    - faithfulness, relevance, consistency, correctness (1-5 or null)
    - justification (str)
    - parse_error (bool) if JSON could not be parsed
    """
    model = model or JUDGE_MODEL
    out: dict[str, Any] = {
        "faithfulness": None,
        "relevance": None,
        "consistency": None,
        "correctness": None,
        "justification": "",
        "parse_error": False,
    }
    if not HAS_OPENAI:
        out["parse_error"] = True
        out["justification"] = "openai not installed"
        return out
    user_prompt = build_judge_user_prompt(context_summary, model_output, ground_truth_target)
    try:
        client = OpenAI(base_url=LITELLM_BASE_URL, api_key=LITELLM_API_KEY)
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": build_judge_system_prompt()},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=500,
        )
        content = (resp.choices[0].message.content or "").strip()
        parsed = _parse_judge_response(content)
        if parsed.get("parse_error"):
            out["parse_error"] = True
            out["justification"] = content[:500]
            return out
        out["faithfulness"] = parsed.get("faithfulness")
        out["relevance"] = parsed.get("relevance")
        out["consistency"] = parsed.get("consistency")
        out["correctness"] = parsed.get("correctness")
        out["justification"] = parsed.get("justification", "") or ""
        return out
    except Exception as e:
        out["parse_error"] = True
        out["justification"] = str(e)
        return out


async def judge_async(
    context_summary: str,
    model_output: str,
    ground_truth_target: Optional[str] = None,
    model: Optional[str] = None,
) -> dict[str, Any]:
    """Async version of judge_sync for use from MCP server."""
    model = model or JUDGE_MODEL
    out: dict[str, Any] = {
        "faithfulness": None,
        "relevance": None,
        "consistency": None,
        "correctness": None,
        "justification": "",
        "parse_error": False,
    }
    if not HAS_OPENAI:
        out["parse_error"] = True
        out["justification"] = "openai not installed"
        return out
    user_prompt = build_judge_user_prompt(context_summary, model_output, ground_truth_target)
    try:
        client = AsyncOpenAI(base_url=LITELLM_BASE_URL, api_key=LITELLM_API_KEY)
        resp = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": build_judge_system_prompt()},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=500,
        )
        content = (resp.choices[0].message.content or "").strip()
        parsed = _parse_judge_response(content)
        if parsed.get("parse_error"):
            out["parse_error"] = True
            out["justification"] = content[:500]
            return out
        out["faithfulness"] = parsed.get("faithfulness")
        out["relevance"] = parsed.get("relevance")
        out["consistency"] = parsed.get("consistency")
        out["correctness"] = parsed.get("correctness")
        out["justification"] = parsed.get("justification", "") or ""
        return out
    except Exception as e:
        out["parse_error"] = True
        out["justification"] = str(e)
        return out
