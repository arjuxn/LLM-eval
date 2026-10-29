"""Fixed knowledge-base tools and condition-specific tool registries."""
from __future__ import annotations
import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def load_knowledge() -> list[dict]:
    with open(DATA_DIR / "knowledge.json", encoding="utf-8") as f:
        return json.load(f)["items"]


def load_papers() -> list[dict]:
    with open(DATA_DIR / "papers.json", encoding="utf-8") as f:
        return json.load(f)["papers"]


class KnowledgeTools:
    def __init__(self, items: list[dict]):
        self.items = items

    def search_knowledge(self, query: str) -> str:
        words = set(query.lower().split())
        ranked = []
        for item in self.items:
            haystack = " ".join([item["id"], item["term"], item["value"], " ".join(item.get("tags", []))]).lower()
            score = sum(1 for word in words if word in haystack)
            if score:
                ranked.append((score, item))
        ranked.sort(key=lambda x: (-x[0], x[1]["id"]))
        if not ranked:
            return "No matching knowledge found."
        return "Search results (IDs and titles only; call get_knowledge with the relevant ID to read the full facts):\n" + "\n".join(f"{item['id']}: {item['term']}" for _, item in ranked[:5])

    def get_knowledge(self, id: str) -> str:
        for item in self.items:
            if item["id"] == id:
                return f"{item['id']} ({item['type']}) - {item['term']}\n{item['value']}"
        return f"No knowledge item found with id '{id}'."


def build_tool_registry(condition: str, items: list[dict], memory) -> dict:
    if condition == "baseline":
        return {}
    if condition == "tool":
        tools = KnowledgeTools(items)
        return {"search_knowledge": tools.search_knowledge, "get_knowledge": tools.get_knowledge}
    if condition == "memory":
        return {"search_notes": memory.search_notes}
    raise ValueError(f"Unknown condition: {condition}")
