"""Apify Actor entry point for quote-normalizer.

Reads `quotes` from the Actor input, validates first (invalid input must fail
without charging), pushes one result record, and charges that same delivery.

Charging uses a single path: push_data(..., charged_event_name=...).
Do not also call Actor.charge for the same delivery.
"""

from __future__ import annotations

import sys
import pathlib

from apify import Actor

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from quote_norm import InvalidInput, normalize  # noqa: E402


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}
        quotes = actor_input.get("quotes", [])

        try:
            result = normalize(quotes)
        except InvalidInput as error:
            # Fail loudly and do not charge: invalid input is not a delivery.
            raise ValueError(str(error)) from error

        await Actor.push_data(result, charged_event_name="result")
