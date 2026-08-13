"""Pluggable trace & metrics backend.

Per the tech-stack requirement, this module implements a fallback chain:

    Langfuse (OSS, primary)
        -> OpenTelemetry OTLP exporter (OSS, primary)
        -> LangSmith (commercial fallback)
        -> console/log fallback (always available, zero setup)

Selection is automatic based on which credentials are present in Settings,
checked in that order. Every backend integration is imported lazily inside
a try/except so that NONE of langfuse/opentelemetry/langsmith need to be
installed for AVaaS to run — the console fallback always works and is the
default in this repo's `.env.example`.

Usage:

    tracer = get_tracer()
    with tracer.start_span("test_case_execution", test_case_id=tc.id) as span:
        ... do the work ...
        span.set_attribute("latency_ms", 123.4)

`start_span` always returns a context manager with the same minimal
interface (`set_attribute`, and `.trace_id` once exited), regardless of
which backend is actually active, so calling code never needs to know which
one is in effect.
"""
from __future__ import annotations

import contextlib
import logging
import time
import uuid
from functools import lru_cache
from typing import Any, Iterator

from ..config import get_settings

logger = logging.getLogger(__name__)


class _Span:
    def __init__(self, name: str, backend: str, native_span: Any = None):
        self.name = name
        self.backend = backend
        self.native_span = native_span
        self.trace_id = f"{backend}_{uuid.uuid4().hex[:12]}"
        self.attributes: dict[str, Any] = {}
        self._start = time.perf_counter()

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value
        if self.native_span is not None:
            try:
                self.native_span.set_attribute(key, value)  # OTel-style API
            except Exception:  # noqa: BLE001
                pass


class Tracer:
    """Selects and wraps exactly one backend for the process lifetime."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.backend, self._impl = self._select_backend()
        logger.info("Tracer initialized with backend: %s", self.backend)

    def _select_backend(self) -> tuple[str, Any]:
        s = self.settings

        if s.langfuse_public_key and s.langfuse_secret_key:
            try:
                from langfuse import Langfuse  # type: ignore

                client = Langfuse(
                    public_key=s.langfuse_public_key,
                    secret_key=s.langfuse_secret_key,
                    host=s.langfuse_host,
                )
                return "langfuse", client
            except Exception as exc:  # noqa: BLE001
                logger.warning("Langfuse configured but unavailable (%s); trying next backend.", exc)

        if s.otel_exporter_otlp_endpoint:
            try:
                from opentelemetry import trace  # type: ignore
                from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (  # type: ignore
                    OTLPSpanExporter,
                )
                from opentelemetry.sdk.resources import Resource  # type: ignore
                from opentelemetry.sdk.trace import TracerProvider  # type: ignore
                from opentelemetry.sdk.trace.export import BatchSpanProcessor  # type: ignore

                resource = Resource(attributes={"service.name": s.otel_service_name})
                provider = TracerProvider(resource=resource)
                exporter = OTLPSpanExporter(endpoint=s.otel_exporter_otlp_endpoint)
                provider.add_span_processor(BatchSpanProcessor(exporter))
                trace.set_tracer_provider(provider)
                return "otel", trace.get_tracer(s.otel_service_name)
            except Exception as exc:  # noqa: BLE001
                logger.warning("OpenTelemetry configured but unavailable (%s); trying next backend.", exc)

        if s.langsmith_api_key:
            try:
                from langsmith import Client  # type: ignore

                client = Client(api_key=s.langsmith_api_key)
                return "langsmith", client
            except Exception as exc:  # noqa: BLE001
                logger.warning("LangSmith configured but unavailable (%s); falling back to console.", exc)

        return "console", None

    @contextlib.contextmanager
    def start_span(self, name: str, **attributes: Any) -> Iterator[_Span]:
        if self.backend == "otel":
            with self._impl.start_as_current_span(name) as native_span:
                span = _Span(name, self.backend, native_span)
                for k, v in attributes.items():
                    span.set_attribute(k, v)
                yield span
            return

        # langfuse / langsmith / console all use the same lightweight local
        # span object; langfuse/langsmith event emission happens on exit
        # below rather than via a native context manager, so every backend
        # that isn't otel shares this simpler path.
        span = _Span(name, self.backend)
        for k, v in attributes.items():
            span.set_attribute(k, v)
        try:
            yield span
        finally:
            duration_ms = (time.perf_counter() - span._start) * 1000
            span.set_attribute("duration_ms", duration_ms)
            self._emit(span)

    def _emit(self, span: _Span) -> None:
        if self.backend == "langfuse" and self._impl is not None:
            try:
                self._impl.trace(name=span.name, metadata=span.attributes, id=span.trace_id)
                return
            except Exception as exc:  # noqa: BLE001
                logger.warning("Langfuse emit failed (%s); logging to console instead.", exc)
        elif self.backend == "langsmith" and self._impl is not None:
            try:
                self._impl.create_run(
                    name=span.name,
                    run_type="chain",
                    inputs={},
                    outputs=span.attributes,
                    project_name=self.settings.langsmith_project,
                )
                return
            except Exception as exc:  # noqa: BLE001
                logger.warning("LangSmith emit failed (%s); logging to console instead.", exc)

        logger.debug("trace[%s] %s %s", span.trace_id, span.name, span.attributes)


@lru_cache
def get_tracer() -> Tracer:
    return Tracer()
