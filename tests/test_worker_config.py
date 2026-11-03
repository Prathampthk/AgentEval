import asyncio

import pytest

from agenteval.worker import serve, validate_pool


@pytest.mark.parametrize("concurrency", [0, 17, True, 1.5, "16"])
def test_invalid_concurrency_rejected(concurrency):
    with pytest.raises(ValueError, match="concurrency"):
        validate_pool(concurrency, 1, 50, 60, 15)


@pytest.mark.parametrize("timing", [0, -1, float("nan"), float("inf")])
def test_invalid_timing_rejected(timing):
    with pytest.raises(ValueError, match="timing"):
        validate_pool(1, timing, 50, 60, 15)


async def test_invalid_pool_does_not_start_tasks():
    before = set(asyncio.all_tasks())
    with pytest.raises(ValueError):
        await serve(asyncio.Event(), None, None, "invalid", concurrency=17)
    assert set(asyncio.all_tasks()) == before
