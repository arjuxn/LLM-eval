"""Run the controlled information-access benchmark."""
from __future__ import annotations
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent import run_episode
from grader import grade
from llm_client import LLMClient
from memory_store import MemoryStore
from tools import build_tool_registry, load_knowledge

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RESULTS_DIR = ROOT / "results"
CONDITIONS = ["baseline", "tool", "memory"]


def load_tasks() -> list[dict[str, Any]]:
    with open(DATA_DIR / "tasks_seed.json", encoding="utf-8") as f:
        return json.load(f)["tasks"]


def select_tasks(tasks: list[dict], ids: list[str] | None) -> list[dict]:
    if not ids:
        return sorted(tasks, key=lambda task: task["episode_index"])
    lookup = {task["task_id"]: task for task in tasks}
    missing = [task_id for task_id in ids if task_id not in lookup]
    if missing:
        raise ValueError("Unknown task ID(s): " + ", ".join(missing))
    return sorted((lookup[task_id] for task_id in ids), key=lambda task: task["episode_index"])


def condition_prompt(task: dict, condition: str) -> str:
    if condition == "baseline":
        return f"{task['prompt']}\n\nRelevant context available directly to you:\n{task['information']['context']}"
    return task["prompt"]


def seed_memory(memory: MemoryStore, tasks: list[dict]) -> None:
    for task in tasks:
        info = task["information"]
        memory.save_note(info["memory_topic"], info["memory_content"])


def run_condition(condition: str, tasks: list[dict], knowledge: list[dict], llm: LLMClient) -> list[dict]:
    memory = MemoryStore()
    if condition == "memory":
        seed_memory(memory, tasks)
    tools = build_tool_registry(condition, knowledge, memory)
    results = []
    for task in tasks:
        episode = run_episode(condition_prompt(task, condition), tools, llm)
        expected = task.get("expected_tool_calls", {}).get(condition, [])
        grading = grade(
            answer=episode["final_answer"],
            answer_check=task.get("answer_check", {}),
            executed_tool_calls=episode["executed_tool_calls"],
            expected_tool_calls=expected,
        )
        results.append({
            "task_id": task["task_id"],
            "category": task["category"],
            "episode_index": task["episode_index"],
            **grading,
            "agent_answer": episode["final_answer"],
            "attempted_tool_calls": episode["attempted_tool_calls"],
            "executed_tool_calls": episode["executed_tool_calls"],
            "rejected_tool_calls": episode["rejected_tool_calls"],
            "turns_used": episode["raw_turns"],
            "latency_ms": episode["latency_ms"],
            "usage": episode["usage"],
        })
    return results


def summarize(all_results: dict[str, list[dict]]) -> str:
    lines = ["", "=== CONTROLLED EVALUATION SUMMARY ===", ""]
    for condition, results in all_results.items():
        total = len(results)
        success = sum(bool(result["task_success"]) for result in results)
        answer_correct = sum(bool(result["answer_correct"]) for result in results)
        avg_turns = sum(result["turns_used"] for result in results) / total
        avg_latency = sum(result["latency_ms"] for result in results) / total
        avg_tokens = sum(result["usage"]["total_tokens"] for result in results) / total
        executed = sum(len(result["executed_tool_calls"]) for result in results)
        rejected = sum(len(result["rejected_tool_calls"]) for result in results)
        required = [result for result in results if result["retrieval_required"]]
        retrieval_passes = sum(bool(result["retrieval_success"]) for result in required)
        lines.append(f"{condition:>8}: {success}/{total} task success | {answer_correct}/{total} answer correct | avg turns {avg_turns:.2f} | avg latency {avg_latency:.0f} ms | avg tokens {avg_tokens:.1f} | executed calls {executed} | rejected calls {rejected}")
        if required:
            lines.append(f"          retrieval success: {retrieval_passes}/{len(required)} retrieval-required tasks")
        else:
            lines.append("          retrieval success: not applicable")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Controlled evaluation of LLM information-access mechanisms")
    parser.add_argument("--task", nargs="+", help="Task ID(s), e.g. K-01 K-02")
    parser.add_argument("--condition", choices=CONDITIONS, help="Run one condition only")
    args = parser.parse_args()
    tasks = select_tasks(load_tasks(), args.task)
    knowledge = load_knowledge()
    llm = LLMClient()
    conditions = [args.condition] if args.condition else CONDITIONS
    all_results = {}
    print("=" * 72)
    print("CONTROLLED LLM AGENT EVALUATION")
    print("Direct Context vs Tool Retrieval vs Persistent Memory")
    print("=" * 72)
    print(f"Model: {llm.model}\nTasks: {len(tasks)}")
    for condition in conditions:
        print(f"\nRunning condition: {condition}")
        all_results[condition] = run_condition(condition, tasks, knowledge, llm)
        for result in all_results[condition]:
            status = "PASS" if result["task_success"] else "FAIL"
            suffix = f" | retrieval={'PASS' if result['retrieval_success'] else 'FAIL'}" if result["retrieval_required"] else ""
            print(f"  {result['task_id']}: {status} | turns={result['turns_used']} | latency={result['latency_ms']:.0f}ms{suffix}")
    print(summarize(all_results))
    RESULTS_DIR.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    report = {
        "benchmark": "controlled-information-access-v1",
        "evaluation_version": "v2.3-final-grading-rules",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "backend": llm.backend,
        "model": llm.model,
        "conditions": conditions,
        "task_ids": [task["task_id"] for task in tasks],
        "research_question": "How do direct contextual access, external tool retrieval, and persistent memory affect the performance and efficiency of the same local LLM agent?",
        "primary_metric": "task_success = deterministic answer correctness",
        "secondary_metrics": ["retrieval success", "turns", "latency", "tokens", "executed tool calls", "rejected tool calls"],
        "results": all_results,
    }
    path = RESULTS_DIR / f"report_{stamp}.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nReport saved to: {path}")


if __name__ == "__main__":
    main()
