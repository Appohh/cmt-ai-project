"""C4 LLMProviderComponent: pluggable local TF-IDF, Ollama, Gemini, and OpenAI providers."""

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

VALID_AI_PROVIDERS = ("local", "ollama", "gemini", "openai")

_RUNTIME_AI_CONFIG: dict[str, str] = {}

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in", "into",
    "is", "it", "of", "on", "or", "our", "that", "the", "their", "this", "to",
    "using", "we", "with", "across", "based", "study", "paper", "evaluate",
    "propose", "approach", "method", "system", "results", "clear", "strong",
}

_DOMAIN_PHRASES = [
    ("neural machine translation", "Neural MT"),
    ("machine translation", "Machine Translation"),
    ("low-resource", "Low-Resource NLP"),
    ("differential privacy", "Differential Privacy"),
    ("privacy-preserving", "Privacy-Preserving AI"),
    ("double-blind", "Double-Blind Security"),
    ("software security", "Software Security"),
    ("transformer", "Transformers"),
    ("attention", "Attention Mechanisms"),
    ("terminology", "Terminology"),
    ("quality estimation", "Quality Estimation"),
    ("comet", "MT Evaluation"),
    ("evaluation", "Evaluation"),
    ("multilingual", "Multilingual NLP"),
    ("federated", "Federated Learning"),
    ("corpus alignment", "Corpus Alignment"),
    ("domain-adapted", "Domain Adaptation"),
    ("adapter", "Adapters"),
    ("beam search", "Decoding"),
    ("nlp", "NLP"),
    ("privacy", "Privacy"),
    ("security", "Security"),
    ("peer-review", "Peer Review"),
    ("peer review", "Peer Review"),
    ("compliance", "Compliance"),
    ("computer vision", "Computer Vision"),
    ("databases", "Databases"),
]


def get_runtime_ai_settings() -> dict[str, Any]:
    """Return active AI provider settings combining runtime overrides with env vars."""
    provider = _RUNTIME_AI_CONFIG.get("provider") or get_ai_provider()
    if provider not in VALID_AI_PROVIDERS:
        provider = "local"
    ollama_base_url = (
        _RUNTIME_AI_CONFIG.get("ollama_base_url")
        or os.getenv("OLLAMA_BASE_URL")
        or "http://localhost:11434"
    ).rstrip("/")
    ollama_model = (
        _RUNTIME_AI_CONFIG.get("ollama_model")
        or os.getenv("OLLAMA_MODEL")
        or "llama3.2"
    )
    gemini_api_key = (
        _RUNTIME_AI_CONFIG.get("gemini_api_key")
        or os.getenv("GEMINI_API_KEY")
        or ""
    ).strip()
    gemini_model = (
        _RUNTIME_AI_CONFIG.get("gemini_model")
        or os.getenv("GEMINI_MODEL")
        or "gemini-3-flash-preview"
    )
    openai_api_key = (
        _RUNTIME_AI_CONFIG.get("openai_api_key")
        or os.getenv("OPENAI_API_KEY")
        or ""
    ).strip()
    openai_base_url = (
        _RUNTIME_AI_CONFIG.get("openai_base_url")
        or os.getenv("OPENAI_BASE_URL")
        or "https://api.openai.com/v1"
    ).rstrip("/")
    openai_model = (
        _RUNTIME_AI_CONFIG.get("openai_model")
        or os.getenv("OPENAI_MODEL")
        or "gpt-4o-mini"
    )
    return {
        "provider": provider,
        "ollama_base_url": ollama_base_url,
        "ollama_model": ollama_model,
        "gemini_api_key": gemini_api_key,
        "gemini_model": gemini_model,
        "gemini_configured": bool(gemini_api_key),
        "openai_api_key": openai_api_key,
        "openai_base_url": openai_base_url,
        "openai_model": openai_model,
        "openai_configured": bool(openai_api_key),
    }


def update_runtime_ai_settings(
    provider: str | None = None,
    ollama_base_url: str | None = None,
    ollama_model: str | None = None,
    gemini_api_key: str | None = None,
    gemini_model: str | None = None,
    openai_api_key: str | None = None,
    openai_model: str | None = None,
) -> dict[str, Any]:
    """Update runtime AI provider preferences (in-memory for interactive switching)."""
    if provider is not None:
        clean = provider.strip().lower()
        if clean not in VALID_AI_PROVIDERS:
            raise ValueError(f"Unsupported AI provider '{provider}'. Choose from {VALID_AI_PROVIDERS}.")
        _RUNTIME_AI_CONFIG["provider"] = clean
    if ollama_base_url is not None and ollama_base_url.strip():
        _RUNTIME_AI_CONFIG["ollama_base_url"] = ollama_base_url.strip().rstrip("/")
    if ollama_model is not None and ollama_model.strip():
        _RUNTIME_AI_CONFIG["ollama_model"] = ollama_model.strip()
    if gemini_api_key is not None and gemini_api_key.strip():
        _RUNTIME_AI_CONFIG["gemini_api_key"] = gemini_api_key.strip()
    if gemini_model is not None and gemini_model.strip():
        _RUNTIME_AI_CONFIG["gemini_model"] = gemini_model.strip()
    if openai_api_key is not None and openai_api_key.strip():
        _RUNTIME_AI_CONFIG["openai_api_key"] = openai_api_key.strip()
    if openai_model is not None and openai_model.strip():
        _RUNTIME_AI_CONFIG["openai_model"] = openai_model.strip()
    return get_runtime_ai_settings()


def check_ollama_reachable(base_url: str) -> bool:
    """Return True if a local Ollama server responds to /api/tags."""
    try:
        resp = httpx.get(f"{base_url.rstrip('/')}/api/tags", timeout=1.5)
        return resp.status_code == 200
    except Exception:
        return False


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


def _normalize_tags(raw_tags: list[str], max_tags: int = 4) -> list[str]:
    seen: set[str] = set()
    cleaned: list[str] = []
    for tag in raw_tags:
        t = re.sub(r"\s+", " ", str(tag).strip()).strip("#,.;:")
        if not t or len(t) > 40:
            continue
        key = t.lower()
        if key not in seen:
            seen.add(key)
            cleaned.append(t)
        if len(cleaned) >= max_tags:
            break
    return cleaned


class BaseMatchingProvider(Protocol):
    """Protocol implemented by all AI matching and tagging providers."""

    def score_candidates(
        self,
        submission: dict[str, Any],
        candidates: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        ...

    def generate_tags(self, text: str, max_tags: int = 4) -> list[str]:
        ...

    def generate_bulk_tags(
        self,
        items: list[dict[str, str]],
        max_tags: int = 4,
    ) -> dict[str, list[str]]:
        ...


class LocalTFIDFProvider:
    """Zero-config deterministic TF-IDF matcher and domain keyword tag extractor."""

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

    def generate_tags(self, text: str, max_tags: int = 4) -> list[str]:
        lower = text.lower()
        tags: list[str] = []
        for phrase, label in _DOMAIN_PHRASES:
            if phrase in lower and label not in tags:
                tags.append(label)
            if len(tags) >= max_tags:
                break

        if len(tags) < max_tags:
            counts = Counter(_tokenize(text))
            for tok, _ in counts.most_common(12):
                if len(tok) < 3:
                    continue
                label = tok.upper() if len(tok) <= 3 else tok.replace("-", " ").title()
                if label.lower() not in {t.lower() for t in tags}:
                    tags.append(label)
                if len(tags) >= max_tags:
                    break

        return _normalize_tags(tags, max_tags=max_tags)

    def generate_bulk_tags(
        self,
        items: list[dict[str, str]],
        max_tags: int = 4,
    ) -> dict[str, list[str]]:
        return {
            item["id"]: self.generate_tags(item["text"], max_tags=max_tags)
            for item in items
        }


def _extract_json_block(raw_text: str) -> Any:
    stripped = raw_text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    return json.loads(stripped)


def _parse_llm_scores(raw_text: str, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    data = _extract_json_block(raw_text)
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


def _parse_llm_tags(raw_text: str, max_tags: int = 4) -> list[str]:
    data = _extract_json_block(raw_text)
    items = data.get("tags", data) if isinstance(data, dict) else data
    if not isinstance(items, list):
        raise ValueError("LLM response is not a list of tags")
    tags = _normalize_tags([str(item) for item in items], max_tags=max_tags)
    if not tags:
        raise ValueError("LLM returned no valid tags")
    return tags


def _parse_llm_bulk_tags(
    raw_text: str,
    items: list[dict[str, str]],
    max_tags: int = 4,
) -> dict[str, list[str]]:
    data = _extract_json_block(raw_text)
    entries = data.get("items", data) if isinstance(data, dict) else data
    mapping: dict[str, list[str]] = {}
    if isinstance(entries, dict):
        for k, v in entries.items():
            if isinstance(v, list):
                mapping[str(k)] = _normalize_tags([str(x) for x in v], max_tags=max_tags)
    elif isinstance(entries, list):
        for entry in entries:
            if isinstance(entry, dict) and "id" in entry and isinstance(entry.get("tags"), list):
                mapping[str(entry["id"])] = _normalize_tags(
                    [str(x) for x in entry["tags"]], max_tags=max_tags
                )
    if not mapping:
        raise ValueError("LLM bulk tag response contained no valid entries")

    local_fallback = LocalTFIDFProvider()
    return {
        item["id"]: mapping.get(item["id"]) or local_fallback.generate_tags(item["text"], max_tags=max_tags)
        for item in items
    }


class OllamaMatchingProvider:
    """On-premise Ollama LLM adapter for reviewer matching and topic tagging (PII-free)."""

    def __init__(self, base_url: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model

    def _generate(self, prompt: str) -> str:
        resp = httpx.post(
            f"{self.base_url}/api/generate",
            json={"model": self.model, "prompt": prompt, "format": "json", "stream": False},
            timeout=15.0,
        )
        resp.raise_for_status()
        return str(resp.json().get("response", "{}"))

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
        return _parse_llm_scores(self._generate(prompt), candidates)

    def generate_tags(self, text: str, max_tags: int = 4) -> list[str]:
        prompt = (
            f"Extract {max_tags} short academic research topic tags (1-3 words each) for this text. "
            "Do not include any personal names, emails, or universities. "
            "Return JSON: {\"tags\": [\"Tag 1\", \"Tag 2\"]}.\n"
            f"Text: {text}"
        )
        return _parse_llm_tags(self._generate(prompt), max_tags=max_tags)

    def generate_bulk_tags(
        self,
        items: list[dict[str, str]],
        max_tags: int = 4,
    ) -> dict[str, list[str]]:
        if not items:
            return {}
        prompt = (
            f"For each item below, extract up to {max_tags} concise academic research topic tags "
            "(1-3 words each). Never include personal names, emails, or affiliations. "
            "Return JSON: {\"items\": [{\"id\": \"...\", \"tags\": [\"Tag 1\", \"Tag 2\"]}]}.\n"
            f"Items: {json.dumps(items)}"
        )
        return _parse_llm_bulk_tags(self._generate(prompt), items, max_tags=max_tags)


class GeminiMatchingProvider:
    """Google Gemini Cloud LLM adapter for reviewer matching and topic tagging (PII-free)."""

    _SECONDARY_MODELS = ("gemini-3-flash-preview", "gemini-flash-lite-latest")

    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model

    def _call_model(self, model_name: str, prompt: str) -> str:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model_name}:generateContent"
        )
        resp = httpx.post(
            url,
            headers={"x-goog-api-key": self.api_key},
            json={
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"responseMimeType": "application/json"},
            },
            timeout=25.0,
        )
        resp.raise_for_status()
        body = resp.json()
        candidates = body.get("candidates", [])
        if not candidates:
            raise ValueError("Gemini returned empty candidates")
        parts = candidates[0].get("content", {}).get("parts", [])
        return "".join(str(p.get("text", "")) for p in parts)

    def _generate(self, prompt: str) -> str:
        models_to_try = [self.model] + [m for m in self._SECONDARY_MODELS if m != self.model]
        last_exc: Exception | None = None
        for idx, model_name in enumerate(models_to_try):
            try:
                return self._call_model(model_name, prompt)
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                if exc.response.status_code in (404, 503) and idx < len(models_to_try) - 1:
                    continue
                raise
        assert last_exc is not None
        raise last_exc

    def score_candidates(
        self,
        submission: dict[str, Any],
        candidates: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        prompt = (
            "Score how well each academic reviewer matches the paper based ONLY on title, abstract, "
            "and expertise. Return JSON: {\"recommendations\": [{\"reviewer_id\": ..., \"score\": 0.0..1.0}]}.\n"
            f"Paper: {json.dumps(submission)}\n"
            f"Candidates: {json.dumps(candidates)}"
        )
        return _parse_llm_scores(self._generate(prompt), candidates)

    def generate_tags(self, text: str, max_tags: int = 4) -> list[str]:
        prompt = (
            f"Extract {max_tags} concise academic research topic tags (1-3 words each) for this text. "
            "Never include personal names, emails, or affiliations. "
            "Return JSON: {\"tags\": [\"Tag 1\", \"Tag 2\"]}.\n"
            f"Text: {text}"
        )
        return _parse_llm_tags(self._generate(prompt), max_tags=max_tags)

    def generate_bulk_tags(
        self,
        items: list[dict[str, str]],
        max_tags: int = 4,
    ) -> dict[str, list[str]]:
        if not items:
            return {}
        prompt = (
            f"For each item below, extract up to {max_tags} concise academic research topic tags "
            "(1-3 words each). Never include personal names, emails, or affiliations. "
            "Return JSON: {\"items\": [{\"id\": \"...\", \"tags\": [\"Tag 1\", \"Tag 2\"]}]}.\n"
            f"Items: {json.dumps(items)}"
        )
        return _parse_llm_bulk_tags(self._generate(prompt), items, max_tags=max_tags)


class OpenAICompatibleProvider:
    """Cloud OpenAI-compatible LLM adapter (PII-free payload)."""

    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    def _generate(self, prompt: str) -> str:
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
            timeout=15.0,
        )
        resp.raise_for_status()
        return str(resp.json()["choices"][0]["message"]["content"])

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
        return _parse_llm_scores(self._generate(prompt), candidates)

    def generate_tags(self, text: str, max_tags: int = 4) -> list[str]:
        prompt = (
            f"Extract {max_tags} concise academic research topic tags (1-3 words each). "
            "Return JSON: {\"tags\": [\"Tag 1\", \"Tag 2\"]}.\n"
            f"Text: {text}"
        )
        return _parse_llm_tags(self._generate(prompt), max_tags=max_tags)

    def generate_bulk_tags(
        self,
        items: list[dict[str, str]],
        max_tags: int = 4,
    ) -> dict[str, list[str]]:
        if not items:
            return {}
        prompt = (
            f"For each item below, extract up to {max_tags} concise academic research topic tags "
            "(1-3 words each). Return JSON: {\"items\": [{\"id\": \"...\", \"tags\": [\"Tag 1\"]}]}.\n"
            f"Items: {json.dumps(items)}"
        )
        return _parse_llm_bulk_tags(self._generate(prompt), items, max_tags=max_tags)


class FallbackProvider:
    """Wrap an external AI provider with automatic fallback to LocalTFIDFProvider (NFR-07)."""

    def __init__(self, primary: BaseMatchingProvider, fallback: LocalTFIDFProvider) -> None:
        self.primary = primary
        self.fallback = fallback
        self.last_fallback_used = False

    def score_candidates(
        self,
        submission: dict[str, Any],
        candidates: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        self.last_fallback_used = False
        try:
            return self.primary.score_candidates(submission, candidates)
        except Exception as exc:
            self.last_fallback_used = True
            log_action("ai.provider_fallback", details={"reason": str(exc)})
            return self.fallback.score_candidates(submission, candidates)

    def generate_tags(self, text: str, max_tags: int = 4) -> list[str]:
        self.last_fallback_used = False
        try:
            return self.primary.generate_tags(text, max_tags=max_tags)
        except Exception as exc:
            self.last_fallback_used = True
            log_action("ai.tag_provider_fallback", details={"reason": str(exc)})
            return self.fallback.generate_tags(text, max_tags=max_tags)

    def generate_bulk_tags(
        self,
        items: list[dict[str, str]],
        max_tags: int = 4,
    ) -> dict[str, list[str]]:
        self.last_fallback_used = False
        try:
            return self.primary.generate_bulk_tags(items, max_tags=max_tags)
        except Exception as exc:
            self.last_fallback_used = True
            log_action("ai.tag_provider_fallback", details={"reason": str(exc)})
            return self.fallback.generate_bulk_tags(items, max_tags=max_tags)


def get_matching_provider(
    override_provider: str | None = None,
) -> tuple[str, BaseMatchingProvider]:
    """Select the active LLMProviderComponent based on runtime/env configuration."""
    settings = get_runtime_ai_settings()
    mode = (override_provider or settings["provider"]).strip().lower()
    local = LocalTFIDFProvider()

    if mode == "ollama":
        return (
            "ollama",
            FallbackProvider(
                OllamaMatchingProvider(settings["ollama_base_url"], settings["ollama_model"]),
                local,
            ),
        )

    if mode == "gemini":
        if settings["gemini_api_key"]:
            return (
                "gemini",
                FallbackProvider(
                    GeminiMatchingProvider(settings["gemini_api_key"], settings["gemini_model"]),
                    local,
                ),
            )
        return "local (gemini key missing)", local

    if mode == "openai":
        if settings["openai_api_key"]:
            return (
                "openai",
                FallbackProvider(
                    OpenAICompatibleProvider(
                        settings["openai_api_key"],
                        settings["openai_base_url"],
                        settings["openai_model"],
                    ),
                    local,
                ),
            )
        return "local (openai key missing)", local

    return "local", local
