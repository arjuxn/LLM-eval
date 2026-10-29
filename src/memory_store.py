"""Persistent note store used by the memory condition."""
from __future__ import annotations
from dataclasses import dataclass, field

@dataclass
class MemoryStore:
    notes: list[dict[str, str]] = field(default_factory=list)

    def save_note(self, topic: str, content: str) -> str:
        self.notes.append({"topic": topic, "content": content})
        return f"Saved note under '{topic}'."

    def search_notes(self, query: str) -> str:
        words = set(query.lower().split())
        ranked = []
        for note in self.notes:
            text = f"{note['topic']} {note['content']}".lower()
            score = sum(1 for word in words if word in text)
            if score:
                ranked.append((score, note))
        ranked.sort(key=lambda item: -item[0])
        if not ranked:
            return "No matching notes found."
        return "\n".join(
            f"[{note['topic']}] {note['content']}" for _, note in ranked[:3]
        )
