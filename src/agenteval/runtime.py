"""Shared provider wiring for the API and worker entry points."""

import os
from contextlib import asynccontextmanager

from agenteval.providers import FakeProvider


async def connection_timeout_bounds(request):
    # Public HTTPX request hook: the SDK supplies per-request read/write timeout,
    # while connection establishment and pool acquisition have separate bounds.
    timing = request.extensions.setdefault("timeout", {})
    for phase in ("connect", "pool"):
        configured = timing.get(phase)
        timing[phase] = min(5.0, configured) if configured is not None else 5.0


@asynccontextmanager
async def provider_context(provided=None, timeout_seconds=30, judge_prompt_version=None):
    if os.getenv("AGENTEVAL_PRIVATE_SERVER") == "1":
        simulated = (
            provided.simulated
            if provided is not None
            else os.getenv("AGENTEVAL_PROVIDER", "fake") == "fake"
        )
        if not simulated:
            raise RuntimeError(
                "Private server profile requires a simulated provider until shared live-request controls are configured"
            )
    client = None
    selected = provided
    if selected is None:
        mode = os.getenv("AGENTEVAL_PROVIDER", "fake")
        if mode == "fake":
            selected = FakeProvider()
        elif mode == "gemini":
            key, model = os.getenv("GEMINI_API_KEY"), os.getenv("AGENTEVAL_MODEL")
            if not key or not model:
                raise RuntimeError("Gemini requires GEMINI_API_KEY and AGENTEVAL_MODEL")
            from google import genai
            from google.genai import types

            from agenteval.gemini import GeminiProvider

            client = genai.Client(
                api_key=key,
                http_options=types.HttpOptions(
                    timeout=int(timeout_seconds * 1000),
                    async_client_args={"event_hooks": {"request": [connection_timeout_bounds]}},
                    retry_options=types.HttpRetryOptions(attempts=1),
                ),
            )
            version = (
                judge_prompt_version
                if judge_prompt_version is not None
                else os.getenv("AGENTEVAL_JUDGE_PROMPT", "candidate-v2")
            )
            selected = GeminiProvider(client, model, judge_prompt_version=version)
        else:
            raise RuntimeError("AGENTEVAL_PROVIDER must be fake or gemini")
    try:
        yield selected
    finally:
        if client:
            await client.aio.aclose()
