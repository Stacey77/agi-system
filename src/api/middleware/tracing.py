"""OpenTelemetry tracing — optional, graceful fallback when OTEL not installed."""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Any, Generator, Optional

logger = logging.getLogger(__name__)

try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.resources import Resource
    _OTEL_AVAILABLE = True
except ImportError:
    _OTEL_AVAILABLE = False

_tracer: Optional[Any] = None


def setup_tracing(service_name: str = "agi-system") -> None:
    """Configure the global OpenTelemetry tracer provider."""
    global _tracer
    if not _OTEL_AVAILABLE:
        logger.info("opentelemetry-sdk not installed — tracing disabled")
        return

    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)

    if endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter  # type: ignore
            provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
            logger.info("OTLP tracing enabled → %s", endpoint)
        except ImportError:
            logger.warning("opentelemetry-exporter-otlp not installed — traces will not be exported")

    trace.set_tracer_provider(provider)
    _tracer = trace.get_tracer(service_name)
    logger.info("OpenTelemetry tracing initialised for service '%s'", service_name)


@contextmanager
def span(name: str, attributes: Optional[dict] = None) -> Generator[Any, None, None]:
    """Context manager that creates a tracing span, or no-ops if tracing unavailable."""
    if _tracer is None or not _OTEL_AVAILABLE:
        yield None
        return
    with _tracer.start_as_current_span(name) as s:
        if attributes:
            for k, v in attributes.items():
                s.set_attribute(k, str(v))
        yield s
