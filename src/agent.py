"""Model-agnostic agent loop for the controlled benchmark."""
from __future__ import annotations
import json
import re
import time
from typing import Any
from llm_client import LLMClient

MAX_TURNS = 6

SYSTEM_TEMPLATE = """You are a research-review assistant participating in a controlled benchmark.

Return exactly one JSON object and nothing else.
To use a tool:
{{"tool": "<tool_name>", "args": {{...}}}}
To finish:
{{"final_answer": "<answer>"}}

Available tools:
{tool_list}

Important:
- Use only the tools listed above.
- If the available tools are (none), do not make a tool call. Answer using the relevant context in the user message.
- Do not invent information that is not present in the conversation or returned by a tool.
- Answer every requested part of the question; do not omit important contrasts, identifiers, numbers, or units.
- If search_knowledge is available, its results contain only record IDs and titles, not the full facts. After every useful search, call get_knowledge with the relevant record ID before answering. For questions requiring multiple records or a comparison, retrieve every relevant record. Do not answer from titles alone.
- If search_notes is available, call search_notes with a non-empty, concise query string. Use the returned note contents to answer every part of the question. Never call search_notes with empty arguments.
- After a tool observation, either make the next necessary tool call or provide the final answer. Do not return a tool-call JSON object as the final answer.
- When you have enough information to answer every part, finish with a concise, direct answer.
"""

TOOL_DESCRIPTIONS = {
    "search_knowledge": "search_knowledge(query: str) -- search the fixed knowledge base",
    "get_knowledge": "get_knowledge(id: str) -- retrieve one knowledge record",
    "search_notes": "search_notes(query: str) -- retrieve relevant persistent notes",
}


def _describe_tools(names: list[str]) -> str:
    if not names:
        return "(none)"
    return "\n".join(f"- {TOOL_DESCRIPTIONS[name]}" for name in names)


def _extract_json(text: str) -> dict[str, Any] | None:
    text = text.strip()
    try:
        value = json.loads(text)
        return value if isinstance(value, dict) else None
    except json.JSONDecodeError:
        pass
    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", text):
        try:
            value, _ = decoder.raw_decode(text[match.start():])
            return value if isinstance(value, dict) else None
        except json.JSONDecodeError:
            continue
    return None


def _result(answer, attempted, executed, rejected, turns, started, usage):
    return {
        "final_answer": answer,
        "attempted_tool_calls": attempted,
        "executed_tool_calls": executed,
        "rejected_tool_calls": rejected,
        "raw_turns": turns,
        "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        "usage": usage,
    }


def run_episode(prompt: str, tools: dict[str, Any], llm: LLMClient) -> dict[str, Any]:
    system = SYSTEM_TEMPLATE.format(tool_list=_describe_tools(list(tools)))
    messages = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
    attempted, executed, rejected = [], [], []
    usage_total = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "model_time_ms": 0.0}
    started = time.perf_counter()

    for turn in range(1, MAX_TURNS + 1):
        reply = llm.chat(messages)
        for key in usage_total:
            usage_total[key] += llm.last_usage.get(key, 0) or 0
        parsed = _extract_json(reply)
        if parsed is None:
            messages.append({"role": "assistant", "content": reply})
            messages.append({"role": "user", "content": "Return ONLY one valid JSON object using tool or final_answer."})
            continue

        if "final_answer" in parsed:
            return _result(str(parsed["final_answer"]), attempted, executed, rejected, turn, started, usage_total)

        if "tool" in parsed:
            name = parsed.get("tool")
            args = parsed.get("args", {})
            if not isinstance(name, str) or not isinstance(args, dict):
                messages.append({"role": "user", "content": "Invalid tool request. Return valid JSON."})
                continue
            call = {"tool": name, "args": args}
            attempted.append(call)
            if name not in tools:
                rejected.append({**call, "reason": "tool_not_available"})
                observation = f"Tool '{name}' is not available in this condition."
            else:
                try:
                    observation = str(tools[name](**args))
                    executed.append(call)
                except Exception as exc:
                    rejected.append({**call, "reason": "tool_execution_error", "error": str(exc)})
                    observation = f"Tool execution failed: {exc}"
            messages.append({"role": "assistant", "content": reply})
            messages.append({"role": "user", "content": f"Tool observation:\n{observation}\nNow continue or return final_answer."})
            continue

        messages.append({"role": "user", "content": "Return either a tool call or final_answer as JSON."})

    return _result("(no final answer within turn limit)", attempted, executed, rejected, MAX_TURNS, started, usage_total)
