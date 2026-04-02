from __future__ import annotations

import logging

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine

from financeops.config import Settings

log = logging.getLogger(__name__)
_TRACING_CONFIGURED = False


def configure_telemetry(
    *,
    app: FastAPI,
    engine: AsyncEngine,
    settings: Settings,
) -> None:
    """
    Configure OpenTelemetry instrumentation for HTTP, DB, and Redis/Celery surfaces.
    Additive and safe: failures degrade to warnings.
    """
    global _TRACING_CONFIGURED
    if _TRACING_CONFIGURED:
        return

    endpoint = str(settings.OTEL_EXPORTER_OTLP_ENDPOINT or "").strip()
    if not endpoint:
        log.info("OpenTelemetry disabled (OTEL_EXPORTER_OTLP_ENDPOINT not set)")
        return

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.celery import CeleryInstrumentor
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.redis import RedisInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        resource = Resource.create(
            {
                "service.name": settings.APP_NAME.lower().replace(" ", "-"),
                "service.version": settings.APP_RELEASE,
                "deployment.environment": settings.APP_ENVIRONMENT,
            }
        )
        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)

        FastAPIInstrumentor.instrument_app(app)
        SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)
        RedisInstrumentor().instrument()
        CeleryInstrumentor().instrument()

        _TRACING_CONFIGURED = True
        log.info("OpenTelemetry instrumentation enabled", extra={"event": "otel_enabled"})
    except Exception as exc:
        log.warning(
            "OpenTelemetry instrumentation failed: %s",
            exc,
            extra={"event": "otel_enable_failed", "error_type": exc.__class__.__name__},
        )
