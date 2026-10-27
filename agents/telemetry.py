"""Tracing in Microsoft Foundry."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Iterator

log = logging.getLogger("halfspace.telemetry")


async def enable_foundry_tracing(client: Any, sensitive: bool = False) -> bool:
    """Connect Agent Framework's spans to the Foundry project's Application Insights."""
    configure = getattr(client, "configure_azure_monitor", None)
    if configure is None:
        log.warning("Tracing needs a Foundry chat client; skipped.")
        return False
    try:
        await configure(enable_sensitive_data=sensitive)
        return True
    except ImportError:
        print('Tracing needs azure-monitor-opentelemetry: uv add "azure-monitor-opentelemetry>=1.8.10,<2"')
    except Exception as e:  # no Application Insights connected, no permission...
        print(f"Tracing not enabled ({type(e).__name__}: {str(e)[:160]}). Connect Application Insights "
              "on the Foundry project's Tracing page, then try again.")
    return False


@contextmanager
def span(name: str, **attrs: Any) -> Iterator[None]:
    """A parent span (e.g. one per Ask question) so the agent's own spans nest under it."""
    try:
        from opentelemetry import trace
    except ImportError:          # pragma: no cover
        yield
        return
    with trace.get_tracer("halfspace").start_as_current_span(name):
        annotate(**attrs)
        yield


def annotate(**attrs: Any) -> None:
    """Add halfspace.* attributes to the current span (no-op when nothing is recording)."""
    try:
        from opentelemetry import trace
    except ImportError:          # pragma: no cover
        return
    span = trace.get_current_span()
    if not span or not span.is_recording():
        return
    for k, v in attrs.items():
        if v is None:
            continue
        if isinstance(v, (list, tuple)):
            v = [str(x) for x in v]
        elif not isinstance(v, (str, bool, int, float)):
            v = str(v)
        span.set_attribute(f"halfspace.{k}", v)
