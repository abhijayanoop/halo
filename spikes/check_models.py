"""Spike helper: which listed models can this account actually call?

The catalogue (`list_models.py`) shows every model, but some return 404
"Function not found for account" when called. This sends ONE tiny request
(max 8 output tokens) per candidate, no retries, and reports ok / not callable.

Run:  uv run python spikes/check_models.py --yes
      uv run python spikes/check_models.py --yes nvidia/some-model other/model
The key is never printed.
"""

import argparse
import asyncio
import os
import sys

import openai
from openai import AsyncOpenAI

from halo.config import load_config, load_env

DEFAULT_CANDIDATES = [
    "nvidia/nemotron-nano-3-30b-a3b",
    "nvidia/nemotron-3.5-lightning-30b-a3b",
    "nvidia/nemotron-3-super-120b-a12b",
    "nvidia/nemotron-3-ultra-550b-a55b",
    "nvidia/llama-3.1-nemotron-ultra-253b-v1",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
    "nvidia/llama-3.1-nemotron-70b-instruct",
    "nvidia/llama-3.1-nemotron-51b-instruct",
]


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "models", nargs="*", help="model ids (default: the Nemotron candidates)"
    )
    parser.add_argument(
        "--yes", action="store_true", help="confirm: one tiny call per model"
    )
    args = parser.parse_args()
    candidates = args.models or DEFAULT_CANDIDATES

    load_env()
    config = load_config()
    key = os.environ.get(config.api.key_env)
    if not key or config.api.base_url.startswith("UNSET"):
        print(
            f"Set {config.api.key_env} and a real base_url first (profile: {config.profile})."
        )
        return 2
    if not args.yes:
        print(
            f"{len(candidates)} tiny calls (max 8 tokens each) on profile '{config.profile}'. Re-run with --yes."
        )
        return 1

    client = AsyncOpenAI(
        base_url=config.api.base_url, api_key=key, max_retries=0, timeout=60
    )
    print(f"profile={config.profile}")
    for model in candidates:
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Say OK."}],
                max_tokens=8,
            )
            usage = response.usage
            tokens = (
                f"{usage.prompt_tokens}+{usage.completion_tokens} tok" if usage else "?"
            )
            print(f"  OK       {model}  ({tokens})")
        except openai.APIStatusError as exc:
            print(f"  HTTP {exc.status_code}  {model}")
        except openai.APIConnectionError as exc:
            print(f"  ERROR    {model}  ({type(exc).__name__})")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
