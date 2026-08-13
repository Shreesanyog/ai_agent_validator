"""A tiny dependency-free async retry helper.

Used around outbound HTTP calls (LLM providers, target agent endpoint) so a
single flaky request doesn't fail an entire validation run.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable, TypeVar

T = TypeVar("T")

logger = logging.getLogger(__name__)


async def retry_async(
    fn: Callable[[], Awaitable[T]],
    *,
    attempts: int = 3,
    base_delay_seconds: float = 0.5,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
) -> T:
    last_exc: BaseException | None = None
    for attempt in range(1, attempts + 1):
        try:
            return await fn()
        except exceptions as exc:  # noqa: BLE001 - intentional broad retry boundary
            last_exc = exc
            logger.warning("attempt %s/%s failed: %s", attempt, attempts, exc)
            if attempt < attempts:
                await asyncio.sleep(base_delay_seconds * attempt)
    assert last_exc is not None
    raise last_exc
