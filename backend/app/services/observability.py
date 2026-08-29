from __future__ import annotations

import contextlib
import logging
import time
import uuid
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Iterator

from ..core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class Span:
    name: str
    backend: str
    native: Any = None
    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    attributes: dict[str, Any] = field(default_factory=dict)
    started: float = field(default_factory=time.perf_counter)

    def set(self, key: str, value: Any) -> None:
        self.attributes[key] = value
        if self.native is not None:
            try:
                self.native.set_attribute(key, str(value))
            except Exception:
                logger.debug("Native span rejected attribute", exc_info=True)


class ObservabilityRouter:
    """Langfuse + OpenTelemetry primary, LangSmith operational fallback.

    Provider failures never fail a validation run. They are logged without
    secrets, and local evidence remains persisted in AVaaS.
    """

    def __init__(self) -> None:
        self.config = settings()
        self.backend, self.client = self._select()

    def _select(self) -> tuple[str, Any]:
        s = self.config
        if s.langfuse_enabled and s.langfuse_public_key and s.langfuse_secret_key:
            try:
                from langfuse import Langfuse
                return "langfuse", Langfuse(
                    public_key=s.langfuse_public_key,
                    secret_key=s.langfuse_secret_key.get_secret_value(),
                    host=s.langfuse_host,
                )
            except Exception:
                logger.warning("Langfuse initialization failed; trying OpenTelemetry", exc_info=True)
        if s.otel_enabled and s.otel_exporter_otlp_endpoint:
            try:
                from opentelemetry import trace
                from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
                from opentelemetry.sdk.resources import Resource
                from opentelemetry.sdk.trace import TracerProvider
                from opentelemetry.sdk.trace.export import BatchSpanProcessor
                provider = TracerProvider(resource=Resource.create({"service.name": s.otel_service_name}))
                provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=s.otel_exporter_otlp_endpoint)))
                trace.set_tracer_provider(provider)
                return "opentelemetry", trace.get_tracer(s.otel_service_name)
            except Exception:
                logger.warning("OpenTelemetry initialization failed; trying LangSmith", exc_info=True)
        if s.langsmith_enabled and s.langsmith_api_key:
            try:
                from langsmith import Client
                return "langsmith", Client(api_key=s.langsmith_api_key.get_secret_value())
            except Exception:
                logger.warning("LangSmith initialization failed; using local evidence", exc_info=True)
        return "local", None

    @contextlib.contextmanager
    def span(self, name: str, **attributes: Any) -> Iterator[Span]:
        if self.backend == "opentelemetry":
            with self.client.start_as_current_span(name) as native:
                span = Span(name, self.backend, native=native)
                for key, value in attributes.items():
                    span.set(key, value)
                yield span
            return
        span = Span(name, self.backend)
        for key, value in attributes.items():
            span.set(key, value)
        try:
            yield span
        finally:
            span.set("duration_ms", round((time.perf_counter() - span.started) * 1000, 2))
            self._emit(span)

    def _emit(self, span: Span) -> None:
        try:
            if self.backend == "langfuse":
                self.client.start_observation(name=span.name, as_type="span", metadata=span.attributes).end()
            elif self.backend == "langsmith":
                self.client.create_run(
                    name=span.name,
                    run_type="chain",
                    inputs={},
                    outputs=span.attributes,
                    project_name=self.config.langsmith_project,
                )
        except Exception:
            logger.warning("Trace export failed; AVaaS local evidence was preserved", exc_info=True)


@lru_cache
def observability() -> ObservabilityRouter:
    return ObservabilityRouter()
