"""Shared provider wiring for the API and worker entry points."""

import os
from contextlib import asynccontextmanager

from agenteval.providers import FakeProvider


@asynccontextmanager
async def provider_context(provided=None, timeout_seconds=30):
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
                    retry_options=types.HttpRetryOptions(attempts=1),
                ),
            )
            selected = GeminiProvider(client, model)
        else:
            raise RuntimeError("AGENTEVAL_PROVIDER must be fake or gemini")
    try:
        yield selected
    finally:
        if client:
            await client.aio.aclose()
