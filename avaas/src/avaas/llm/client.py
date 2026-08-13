"""Unified LLM client with automatic fallback.

Provider selection (LLM_PROVIDER env var):
  * "mock"   - no network calls at all. Deterministic heuristic text/score
               generation. This is the default so the whole platform is
               runnable with zero external services or API keys.
  * "ollama" - calls a local Ollama server (OLLAMA_BASE_URL/OLLAMA_MODEL).
  * "gemini" - calls the Gemini API (GEMINI_API_KEY/GEMINI_MODEL).

Every call goes through `LLMClient.generate()` / `LLMClient.score()`. Both
methods NEVER raise for provider-availability reasons: if the configured
provider is unreachable (no Ollama running, bad/missing Gemini key, network
error) they transparently fall back to the mock heuristic implementation and
log a warning. This is what lets `LLM_PROVIDER=mock` (or a misconfigured
provider) still produce a complete, useful validation run end-to-end - the
LLM is used to *enhance* test generation and scoring, never as a hard
dependency for the pipeline to function.
"""
from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass

import httpx

from ..config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class LLMResult:
    text: str
    provider_used: str


class LLMClient:
    def __init__(self) -> None:
        self.settings = get_settings()

    # ---------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------
    async def generate(self, prompt: str, system: str = "") -> LLMResult:
        provider = self.settings.llm_provider.lower()
        try:
            if provider == "ollama":
                text = await self._call_ollama(prompt, system)
                return LLMResult(text=text, provider_used="ollama")
            if provider == "gemini":
                text = await self._call_gemini(prompt, system)
                return LLMResult(text=text, provider_used="gemini")
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM provider '%s' failed (%s); falling back to mock.", provider, exc)

        return LLMResult(text=self._mock_generate(prompt, system), provider_used="mock")

    async def score(self, response_text: str, rubric: str) -> tuple[float, str]:
        """Return (score 0-100, rationale) for `response_text` against `rubric`."""
        result = await self.generate(
            prompt=(
                f"Rubric:\n{rubric}\n\n"
                f"Agent response to evaluate:\n{response_text}\n\n"
                "Score the response from 0 to 100 on how well it satisfies the rubric. "
                "Reply in the exact format: SCORE=<int 0-100> RATIONALE=<one short sentence>"
            ),
            system="You are a strict, consistent QA judge for AI agent responses.",
        )
        score, rationale = self._parse_score(result.text)
        return score, rationale

    # ---------------------------------------------------------------
    # Providers
    # ---------------------------------------------------------------
    async def _call_ollama(self, prompt: str, system: str) -> str:
        url = f"{self.settings.ollama_base_url.rstrip('/')}/api/generate"
        payload = {
            "model": self.settings.ollama_model,
            "prompt": f"{system}\n\n{prompt}" if system else prompt,
            "stream": False,
        }
        async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data.get("response", "")

    async def _call_gemini(self, prompt: str, system: str) -> str:
        if not self.settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is not set")
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.settings.gemini_model}:generateContent?key={self.settings.gemini_api_key}"
        )
        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        payload = {"contents": [{"parts": [{"text": full_prompt}]}]}
        async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                return ""
            parts = candidates[0].get("content", {}).get("parts", [])
            return "".join(p.get("text", "") for p in parts)

    # ---------------------------------------------------------------
    # Mock / heuristic fallback (also used directly when LLM_PROVIDER=mock)
    # ---------------------------------------------------------------
    def _mock_generate(self, prompt: str, system: str) -> str:
        """Deterministic, dependency-free stand-in for a real LLM call.

        Not meant to be clever - just stable and useful enough that the
        pipeline (test generation enrichment, judge scoring) always has
        something sensible to work with when no real model is configured.
        """
        digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        pseudo_score = 55 + (int(digest[:4], 16) % 40)  # deterministic 55-94 range
        return f"SCORE={pseudo_score} RATIONALE=heuristic mock evaluation (no LLM provider configured)"

    @staticmethod
    def _parse_score(text: str) -> tuple[float, str]:
        score_match = re.search(r"SCORE\s*=\s*(-?\d+(?:\.\d+)?)", text)
        rationale_match = re.search(r"RATIONALE\s*=\s*(.+)", text)
        score = float(score_match.group(1)) if score_match else 50.0
        score = max(0.0, min(100.0, score))
        rationale = rationale_match.group(1).strip() if rationale_match else text.strip()[:200]
        return score, rationale
