"""Phase 2: Async Execution + trace collection.

Sends each generated TestCase to the target agent's HTTP endpoint with a
bounded concurrency pool, and records a TraceRecord for every call
(response body, tool calls the agent reported, latency, and any error).
Every call is wrapped in a tracing span (`tracing/tracer.py`) — Langfuse +
OpenTelemetry primary, LangSmith commercial fallback, console fallback —
so trace/tool-call/latency data is exportable to real observability tooling
without any code here needing to know which backend is active.

Wire protocol expected from the target agent endpoint (see
scripts/demo_target_agent.py for a working reference implementation):

  POST <endpoint_url>
  { "message": "<latest user turn>", "history": [{"role": "...", "content": "..."}, ...] }

  -> 200 OK
  {
    "response": "<agent's natural-language reply>",
    "tool_calls": [ {"name": "...", "arguments": {...}}, ... ]   # optional
  }

If the target agent returns a different shape, the raw JSON (or raw text)
is still captured in `raw_response` / `response_text` so evaluation can
degrade gracefully instead of crashing the whole run.
"""
from __future__ import annotations

import asyncio
import logging
import time

import httpx

from ..config import get_settings
from ..models.schemas import AgentSpec, TestCase, ToolCallRecord, TraceRecord
from ..tracing.tracer import get_tracer

logger = logging.getLogger(__name__)


async def run_test_cases(agent: AgentSpec, test_cases: list[TestCase]) -> list[TraceRecord]:
    settings = get_settings()
    semaphore = asyncio.Semaphore(settings.max_concurrency)

    async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
        tasks = [_run_one(client, semaphore, agent, tc) for tc in test_cases]
        traces = await asyncio.gather(*tasks)
    return list(traces)


async def _run_one(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    agent: AgentSpec,
    test_case: TestCase,
) -> TraceRecord:
    tracer = get_tracer()
    history: list[dict] = []
    last_response_text = ""
    last_tool_calls: list[ToolCallRecord] = []
    last_raw: dict | None = None
    total_latency_ms = 0.0
    error: str | None = None

    headers = {"Content-Type": "application/json"}
    if agent.auth_header:
        headers["Authorization"] = agent.auth_header

    with tracer.start_span(
        "test_case_execution", test_case_id=test_case.id, agent_id=agent.id, test_case_type=test_case.type.value
    ) as span:
        async with semaphore:
            for turn in test_case.turns:
                history.append({"role": turn.role, "content": turn.content})
                payload = {
                    "message": turn.content,
                    "history": history[:-1],
                    "system_prompt": agent.system_prompt,
                }
                start = time.perf_counter()
                try:
                    resp = await client.post(str(agent.endpoint_url), json=payload, headers=headers)
                    total_latency_ms += (time.perf_counter() - start) * 1000
                    resp.raise_for_status()
                    data = _safe_json(resp)
                    last_raw = data if isinstance(data, dict) else {"raw_text": str(data)}
                    last_response_text = _extract_response_text(data)
                    last_tool_calls = _extract_tool_calls(data)
                    history.append({"role": "assistant", "content": last_response_text})
                except Exception as exc:  # noqa: BLE001
                    total_latency_ms += (time.perf_counter() - start) * 1000
                    error = f"{type(exc).__name__}: {exc}"
                    logger.warning("Request failed for test case %s: %s", test_case.id, error)
                    break

        span.set_attribute("latency_ms", total_latency_ms)
        span.set_attribute("tool_calls", [c.name for c in last_tool_calls])
        span.set_attribute("error", error)
        trace_id = span.trace_id
        trace_backend = tracer.backend

    return TraceRecord(
        test_case_id=test_case.id,
        request_payload={"turns": [t.model_dump() for t in test_case.turns]},
        response_text=last_response_text,
        tool_calls=last_tool_calls,
        latency_ms=total_latency_ms,
        tokens_estimated=_estimate_tokens(last_response_text),
        error=error,
        raw_response=last_raw,
        trace_id=trace_id,
        trace_backend=trace_backend,
    )


def _safe_json(resp: httpx.Response):
    try:
        return resp.json()
    except Exception:  # noqa: BLE001
        return {"response": resp.text}


def _extract_response_text(data) -> str:
    if isinstance(data, dict):
        for key in ("response", "message", "reply", "output", "text"):
            if key in data and isinstance(data[key], str):
                return data[key]
        return str(data)
    return str(data)


def _extract_tool_calls(data) -> list[ToolCallRecord]:
    if not isinstance(data, dict):
        return []
    raw_calls = data.get("tool_calls") or data.get("tools_called") or []
    calls: list[ToolCallRecord] = []
    for rc in raw_calls:
        if isinstance(rc, dict) and "name" in rc:
            calls.append(ToolCallRecord(name=rc["name"], arguments=rc.get("arguments", {}) or {}))
    return calls


def _estimate_tokens(text: str) -> int:
    # Cheap, dependency-free approximation (~4 chars/token, English-ish text).
    return max(0, len(text) // 4)
