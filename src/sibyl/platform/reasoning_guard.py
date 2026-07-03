import asyncio
from collections.abc import Awaitable, Callable

from sibyl.platform.observability import get_logger

logger = get_logger(__name__)


class TokenBudgetExceededError(Exception):
    pass


async def guarded_llm_call[ResultT](
    call: Callable[[], Awaitable[ResultT]],
    fallback: Callable[[], ResultT],
    timeout_seconds: float,
    budget_exceeded: bool = False,
) -> ResultT:
    if budget_exceeded:
        logger.warning("llm.budget_exceeded")
        return fallback()

    try:
        return await asyncio.wait_for(call(), timeout=timeout_seconds)
    except TimeoutError:
        logger.warning("llm.timeout")
        return fallback()
    except Exception:
        logger.warning("llm.provider_error", exc_info=True)
        return fallback()
