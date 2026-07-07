import asyncio
import time
from collections.abc import Awaitable, Callable

from sibyl.platform.observability import get_logger

logger = get_logger(__name__)


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
    start = time.monotonic()

    if budget_exceeded:
        logger.warning("llm.budget_exceeded")
        return fallback(), 0

    try:
        result = await asyncio.wait_for(call(), timeout=timeout_seconds)
        return result, _elapsed_ms(start)
    except TimeoutError:
        logger.warning("llm.timeout")
        return fallback(), _elapsed_ms(start)
    except Exception:
        logger.warning("llm.provider_error", exc_info=True)
        return fallback(), _elapsed_ms(start)
