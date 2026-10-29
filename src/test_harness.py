"""Deterministic sanity checks for the benchmark; no LLM/network required."""
from __future__ import annotations
import json
from pathlib import Path
from agent import run_episode
from grader import check_answer, grade
from memory_store import MemoryStore
from tools import build_tool_registry, load_knowledge

ROOT = Path(__file__).resolve().parent.parent


class FakeLLM:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.last_usage = {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2, "model_time_ms": 1.0}

    def chat(self, messages):
        return next(self.replies)


def check(label, condition):
    print(f"[{'PASS' if condition else 'FAIL'}] {label}")
    assert condition, label


def test_data_parity():
    tasks = json.loads((ROOT / "data" / "tasks_seed.json").read_text(encoding="utf-8"))["tasks"]
    check("benchmark contains 12 tasks", len(tasks) == 12)
    for task in tasks:
        info = task["information"]
        check(f"{task['task_id']} has direct context", bool(info["context"]))
        check(f"{task['task_id']} has memory payload", bool(info["memory_content"]))
        check(f"{task['task_id']} has source id", bool(info["id"]))


def test_tool_and_memory_access():
    knowledge = load_knowledge()
    memory = MemoryStore()
    tool_registry = build_tool_registry("tool", knowledge, memory)
    memory_registry = build_tool_registry("memory", knowledge, memory)
    baseline_registry = build_tool_registry("baseline", knowledge, memory)
    check("baseline exposes no tools", baseline_registry == {})
    check("tool exposes only knowledge tools", set(tool_registry) == {"search_knowledge", "get_knowledge"})
    check("memory exposes only note search", set(memory_registry) == {"search_notes"})
    check("tool retrieves P09", "P09" in tool_registry["get_knowledge"](id="P09"))
    memory.save_note("P09 reward shaping", "P09 — Cuts training steps to convergence by 55%.")
    check("memory retrieves seeded note", "55%" in memory_registry["search_notes"]("P09 reward shaping"))


def test_agent_execution_semantics():
    tools = build_tool_registry("tool", load_knowledge(), MemoryStore())
    fake = FakeLLM([
        '{"tool":"get_knowledge","args":{"id":"P09"}}',
        '{"final_answer":"P09 cuts training steps by 55%."}'
    ])
    episode = run_episode("What happened in P09?", tools, fake)
    check("tool call executes", len(episode["executed_tool_calls"]) == 1)
    check("tool call is recorded", episode["executed_tool_calls"][0]["tool"] == "get_knowledge")
    check("final answer returned", "55%" in episode["final_answer"])


def test_answer_grading_variants():
    # These alternatives were added before the final benchmark run and are explicit,
    # deterministic phrase rules rather than an LLM-based subjective judge.
    cases = [
        (
            "Ablation condition means a specific set of components removed to isolate the contribution of one factor.",
            {"mode": "contains_all", "values": ["specific set of components removed", "isolate one factor's contribution"]},
            True,
            "accepts grammatical equivalent for K-02",
        ),
        (
            "Accuracy is used rather than F1 for classification papers.",
            {"mode": "contains_all", "values": ["Accuracy", "not F1"]},
            True,
            "accepts rather-than wording for K-09",
        ),
        (
            "Exclude any paper based only on synthetic or simulated data without real-world validation.",
            {"mode": "contains_all", "values": ["Exclude any paper", "synthetic/simulated data", "no real-world validation"]},
            True,
            "accepts slash and preposition variants for K-10",
        ),
        (
            "The paper used synthetic data and had no real-world validation.",
            {"mode": "contains_all", "values": ["synthetic/simulated data", "no real-world validation"]},
            True,
            "accepts natural synthetic-data phrasing",
        ),
        (
            "Accuracy is the primary metric for classification papers.",
            {"mode": "contains_all", "values": ["Accuracy", "not F1"]},
            False,
            "does not infer an unstated F1 contrast",
        ),
        (
            "P09 reports a 55% reduction in training steps.",
            {"mode": "contains_all", "values": ["55%", "training steps"]},
            True,
            "preserves numeric and unit checking",
        ),
    ]
    for answer, rule, expected, label in cases:
        passed, issues = check_answer(answer, rule)
        check(label, passed is expected)
        if expected:
            check(f"{label}: no grading issues", not issues)


def test_retrieval_grading():
    memory_retrieval = grade(
        answer="P09 reports a 55% reduction in training steps.",
        answer_check={"mode": "contains_all", "values": ["55%", "training steps"]},
        executed_tool_calls=[{"tool": "search_notes", "args": {"query": "study on hierarchical reward shaping for sparse-feedback RL"}}],
        expected_tool_calls=[{"tool": "search_notes", "args": {"query": "P09 reward shaping"}}],
    )
    check("memory retrieval tolerates different search wording", memory_retrieval["retrieval_success"])

    tool_retrieval = grade(
        answer="P09 reports a 55% reduction in training steps.",
        answer_check={"mode": "contains_all", "values": ["55%", "training steps"]},
        executed_tool_calls=[
            {"tool": "search_knowledge", "args": {"query": "hierarchical reward shaping sparse-feedback RL"}},
            {"tool": "get_knowledge", "args": {"id": "P09"}},
        ],
        expected_tool_calls=[
            {"tool": "search_knowledge", "args": {"query": "a different search phrase"}, "match": "name_only"},
            {"tool": "get_knowledge", "args": {"id": "P09"}},
        ],
    )
    check("knowledge retrieval ignores search wording but checks record ID", tool_retrieval["retrieval_success"])

    wrong_record = grade(
        answer="P09 reports a 55% reduction in training steps.",
        answer_check={"mode": "contains_all", "values": ["55%", "training steps"]},
        executed_tool_calls=[{"tool": "get_knowledge", "args": {"id": "P08"}}],
        expected_tool_calls=[{"tool": "get_knowledge", "args": {"id": "P09"}}],
    )
    check("knowledge retrieval rejects the wrong record ID", not wrong_record["retrieval_success"])

    refusal = grade(
        answer="Insufficient information to answer.",
        answer_check={"mode": "contains_all", "values": ["82%", "34%", "48 percentage points"]},
        executed_tool_calls=[],
        expected_tool_calls=[],
    )
    check("insufficient-information response does not pass", not refusal["answer_correct"])


def main():
    print("=" * 60)
    print("CONTROLLED BENCHMARK SANITY CHECKS")
    print("=" * 60)
    test_data_parity()
    test_tool_and_memory_access()
    test_agent_execution_semantics()
    test_answer_grading_variants()
    test_retrieval_grading()
    print("\nAll sanity checks passed.")


if __name__ == "__main__":
    main()
