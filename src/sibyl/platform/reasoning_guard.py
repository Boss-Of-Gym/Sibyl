import asyncio
import time
from collections.abc import Awaitable, Callable

from pydantic import ValidationError

from sibyl.platform.observability import get_logger, get_meter, get_tracer

logger = get_logger(__name__)
tracer = get_tracer(__name__)
meter = get_meter(__name__)

_budget_exceeded_total = meter.create_counter("llm.budget_exceeded_total")
_timeout_total = meter.create_counter("llm.timeout_total")
_provider_error_total = meter.create_counter("llm.provider_error_total")
_schema_validation_failed_total = meter.create_counter("llm.schema_validation_failed_total")
_success_total = meter.create_counter("llm.success_total")
_latency_ms = meter.create_histogram("llm.latency_ms", unit="ms")


class TokenBudgetExceededError(Exception):
    pass


def _elapsed_ms(start: float) -> int:
    return int((time.monotonic() - start) * 1000)


async def guarded_llm_call[ResultT](
    call: Callable[[], Awaitable[ResultT]],
    fallback: Callable[[], ResultT],
    timeout_seconds: float,
    budget_exceeded: bool = False,
) -> tuple[ResultT, int]:
    with tracer.start_as_current_span("llm.call") as span:
        start = time.monotonic()

        if budget_exceeded:
            logger.warning("llm.budget_exceeded")
            _budget_exceeded_total.add(1)
            span.set_attribute("llm.outcome", "budget_exceeded")
            return fallback(), 0

        try:
            result = await asyncio.wait_for(call(), timeout=timeout_seconds)
            latency_ms = _elapsed_ms(start)
            _success_total.add(1)
            _latency_ms.record(latency_ms)
            span.set_attribute("llm.outcome", "success")
            return result, latency_ms
        except TimeoutError:
            logger.warning("llm.timeout")
            _timeout_total.add(1)
            span.set_attribute("llm.outcome", "timeout")
            return fallback(), _elapsed_ms(start)
        except ValidationError:
            logger.error("llm.schema_validation_failed", exc_info=True)
            _schema_validation_failed_total.add(1)
            span.set_attribute("llm.outcome", "schema_validation_failed")
            return fallback(), _elapsed_ms(start)
        except Exception:
            logger.error("llm.provider_error", exc_info=True)
            _provider_error_total.add(1)
            span.set_attribute("llm.outcome", "provider_error")
            return fallback(), _elapsed_ms(start)
