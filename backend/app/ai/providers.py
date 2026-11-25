"""C4 LLMProviderComponent: pluggable local TF-IDF, Ollama, and Cloud LLM matching providers."""

from __future__ import annotations

import json
import math
import os
import re
from collections import Counter
from typing import Any, Protocol

import httpx

from app.core.config import get_ai_provider
from app.core.logging import log_action

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in", "into",
    "is", "it", "of", "on", "or", "that", "the", "this", "to", "using", "we", "with",
}


def _tokenize(text: str) -> list[str]:
    raw_tokens = re.findall(r"[a-z0-9][a-z0-9\-]*", text.lower())
    tokens: list[str] = []
    for tok in raw_tokens:
        if tok not in _STOPWORDS and len(tok) > 1:
            tokens.append(tok)
        if "-" in tok:
            for part in tok.split("-"):
                if part and part not in _STOPWORDS and len(part) > 1:
                    tokens.append(part)
    return tokens


def _extract_text_fragments(data: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("title", "abstract", "topics", "expertise", "past_topics"):
        value = data.get(key)
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, list):
            parts.extend(str(item) for item in value)
    return " ".join(parts)


class BaseMatchingProvider(Protocol):
    """Protocol implemented by all reviewer matching providers."""

    def score_candidates(
        self,
        submission: dict[str, Any],
        candidates: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        ...


class LocalTFIDFProvider:
    """Zero-config deterministic TF-IDF + keyword overlap matcher."""

    def score_candidates(
        self,
        submission: dict[str, Any],
        candidates: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if not candidates:
            return []

        sub_tokens = _tokenize(_extract_text_fragments(submission))
        cand_tokens_list = [_tokenize(_extract_text_fragments(c)) for c in candidates]
        docs = [sub_tokens, *cand_tokens_list]
        num_docs = len(docs)

        df: Counter[str] = Counter()
        for doc in docs:
            for term in set(doc):
                df[term] += 1

        def _tfidf_vec(doc: list[str]) -> dict[str, float]:
            if not doc:
                return {}
            tf = Counter(doc)
            total = len(doc)
            vec: dict[str, float] = {}
            for term, count in tf.items():
                idf = math.log((num_docs + 1) / (df[term] + 1)) + 1.0
                vec[term] = (count / total) * idf
            return vec

        sub_vec = _tfidf_vec(sub_tokens)
        sub_norm = math.sqrt(sum(v * v for v in sub_vec.values()))
        sub_set = set(sub_tokens)

        scored: list[dict[str, Any]] = []
        for candidate, c_tokens in zip(candidates, cand_tokens_list):
            c_vec = _tfidf_vec(c_tokens)
            c_norm = math.sqrt(sum(v * v for v in c_vec.values()))

            cosine = 0.0
            if sub_norm > 0 and c_norm > 0:
                dot = sum(sub_vec.get(term, 0.0) * val for term, val in c_vec.items())
                cosine = dot / (sub_norm * c_norm)

            overlap = 0.0
            if sub_set and c_tokens:
                overlap = len(sub_set.intersection(c_tokens)) / max(len(set(c_tokens)), 1)

            combined = min(1.0, max(0.0, 0.7 * cosine + 0.3 * overlap))
            scored.append(
                {
                    "reviewer_id": candidate["reviewer_id"],
                    "score": round(combined, 4),
                }
            )

        scored.sort(key=lambda item: item["score"], reverse=True)
        return scored


def _parse_llm_scores(raw_text: str, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    data = json.loads(raw_text)
    items = data.get("recommendations", data) if isinstance(data, dict) else data
    if not isinstance(items, list):
        raise ValueError("LLM response is not a list of scores")

    score_map: dict[str, float] = {}
    for entry in items:
        if isinstance(entry, dict) and "reviewer_id" in entry and "score" in entry:
            rid = str(entry["reviewer_id"])
            score = min(1.0, max(0.0, float(entry["score"])))
            score_map[rid] = round(score, 4)

    if not score_map:
        raise ValueError("LLM response returned no valid reviewer scores")

    results = [
        {
            "reviewer_id": c["reviewer_id"],
            "score": score_map.get(str(c["reviewer_id"]), 0.0),
        }
        for c in candidates
    ]
    results.sort(key=lambda item: item["score"], reverse=True)
    return results


class OllamaMatchingProvider:
    """On-premise Ollama LLM reviewer matching adapter (PII-free payload)."""

    def __init__(self, base_url: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model

    def score_candidates(
        self,
        submission: dict[str, Any],
        candidates: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        prompt = (
            "Score how well each reviewer matches the paper based ONLY on title, abstract, "
            "and expertise. Return JSON: {\"recommendations\": [{\"reviewer_id\": ..., \"score\": 0.0..1.0}]}.\n"
            f"Paper: {json.dumps(submission)}\n"
            f"Candidates: {json.dumps(candidates)}"
        )
        resp = httpx.post(
            f"{self.base_url}/api/generate",
            json={"model": self.model, "prompt": prompt, "format": "json", "stream": False},
            timeout=10.0,
        )
        resp.raise_for_status()
        body = resp.json()
        return _parse_llm_scores(body.get("response", "{}"), candidates)


class OpenAICompatibleProvider:
    """Cloud OpenAI-compatible LLM reviewer matching adapter (PII-free payload)."""

    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    def score_candidates(
        self,
        submission: dict[str, Any],
        candidates: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        prompt = (
            "Score how well each reviewer matches the paper based ONLY on title, abstract, "
            "and expertise. Return JSON: {\"recommendations\": [{\"reviewer_id\": ..., \"score\": 0.0..1.0}]}.\n"
            f"Paper: {json.dumps(submission)}\n"
            f"Candidates: {json.dumps(candidates)}"
        )
        resp = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": "You output valid JSON only."},
                    {"role": "user", "content": prompt},
                ],
            },
            timeout=10.0,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        return _parse_llm_scores(content, candidates)


class FallbackProvider:
    """Wrap an external AI provider with automatic fallback to LocalTFIDFProvider (NFR-07)."""

    def __init__(self, primary: BaseMatchingProvider, fallback: LocalTFIDFProvider) -> None:
        self.primary = primary
        self.fallback = fallback

    def score_candidates(
        self,
        submission: dict[str, Any],
        candidates: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        try:
            return self.primary.score_candidates(submission, candidates)
        except Exception as exc:
            log_action("ai.provider_fallback", details={"reason": str(exc)})
            return self.fallback.score_candidates(submission, candidates)


def get_matching_provider() -> tuple[str, BaseMatchingProvider]:
    """Select the active LLMProviderComponent based on environment configuration."""
    local = LocalTFIDFProvider()
    mode = get_ai_provider()

    if mode == "ollama":
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        model = os.getenv("OLLAMA_MODEL", "llama3.2")
        return "ollama", FallbackProvider(OllamaMatchingProvider(base_url, model), local)

    if mode == "openai":
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if api_key:
            base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
            model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
            return "openai", FallbackProvider(OpenAICompatibleProvider(api_key, base_url, model), local)

    return "local", local
