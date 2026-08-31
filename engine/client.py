from __future__ import annotations

import hashlib
import json
import os
import re
from typing import Any

import httpx
from pydantic import ValidationError

from engine.prompt import JSON_INSTRUCTION
from engine.schema import ModelJudgement
from engine.version import DEFAULT_MODEL, MODEL_FAMILY

DEFAULT_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")


class OllamaError(RuntimeError):
    pass


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        raise OllamaError("Model did not return JSON. Re-run the analysis.")
    data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise OllamaError("Model JSON was not an object.")
    return data


async def list_models(host: str = DEFAULT_HOST) -> list[str]:
    async with httpx.AsyncClient(timeout=8.0) as client:
        try:
            r = await client.get(f"{host.rstrip('/')}/api/tags")
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise OllamaError(
                "Cannot reach Ollama. Start the Ollama app, then pull nebulatech/rasa-analyst."
            ) from e
        names = [m.get("name", "") for m in r.json().get("models", [])]
        return [n for n in names if n]


def rasa_model_present(names: list[str]) -> bool:
    return any(MODEL_FAMILY in n for n in names)


def content_seed(text: str) -> int:
    digest = hashlib.sha256(text.strip().encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % (2**31 - 1)


async def analyze_content(
    content: str,
    model: str = DEFAULT_MODEL,
    host: str = DEFAULT_HOST,
) -> tuple[ModelJudgement, int]:
    text = content.strip()
    prompt = JSON_INSTRUCTION + text
    seed = content_seed(text)
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0,
            "top_p": 1,
            "seed": seed,
            "num_ctx": 8192,
            "repeat_penalty": 1.05,
        },
    }
    last_err: Exception | None = None
    async with httpx.AsyncClient(timeout=240.0) as client:
        for _ in range(2):
            try:
                r = await client.post(f"{host.rstrip('/')}/api/generate", json=payload)
                r.raise_for_status()
                raw = r.json().get("response", "")
                data = _extract_json(raw)
                if data.get("priority_fix") is None:
                    data["priority_fix"] = "None"
                if data.get("failure_modes") is None:
                    data["failure_modes"] = []
                judgement = ModelJudgement.model_validate(data)
                return judgement, seed
            except (httpx.HTTPError, json.JSONDecodeError, ValidationError, OllamaError) as e:
                last_err = e
                # Same prompt and seed — do not mutate the request or scores drift.
    raise OllamaError(f"Scoring failed after retry: {last_err}")
