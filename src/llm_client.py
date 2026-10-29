"""Local Ollama client with normalized usage accounting."""
from __future__ import annotations
import os
from pathlib import Path
from typing import Any
import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

class LLMClient:
    def __init__(self) -> None:
        backend = os.environ.get("LLM_BACKEND", "ollama").strip().lower()
        if backend != "ollama":
            raise ValueError("This benchmark is intentionally local-only. Set LLM_BACKEND=ollama.")
        self.backend = backend
        self.host = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
        self.model = os.environ.get("OLLAMA_MODEL", "qwen2.5:3b").strip()
        if not self.model:
            raise RuntimeError("OLLAMA_MODEL is not set.")
        self.last_usage: dict[str, Any] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "model_time_ms": 0.0}

    def chat(self, messages: list[dict[str, str]], temperature: float = 0.0) -> str:
        response = requests.post(
            f"{self.host}/api/chat",
            json={"model": self.model, "messages": messages, "stream": False, "options": {"temperature": temperature}},
            timeout=180,
        )
        if not response.ok:
            raise RuntimeError(f"Ollama error {response.status_code}: {response.text}")
        payload = response.json()
        prompt = payload.get("prompt_eval_count", 0) or 0
        completion = payload.get("eval_count", 0) or 0
        self.last_usage = {
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "total_tokens": prompt + completion,
            "model_time_ms": (payload.get("total_duration", 0) or 0) / 1_000_000,
        }
        return payload["message"]["content"]
