"""Spike helper: list the model ids the active profile's endpoint serves.

Listing models is a free metadata call (no inference credits). Use it to fill the
`id = "UNSET-..."` lines of the active profile in src/halo/config.default.toml.

Run:  uv run python spikes/list_models.py            (Nemotron models only)
      uv run python spikes/list_models.py --all
Pick the profile with HALO_PROFILE (for example in .env). The key is never printed.
"""

import argparse
import asyncio
import os
import sys

from openai import AsyncOpenAI

from halo.config import load_config, load_env


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--all", action="store_true", help="show every model, not just Nemotron"
    )
    args = parser.parse_args()

    load_env()
    config = load_config()
    key = os.environ.get(config.api.key_env)
    if not key:
        print(
            f"Set {config.api.key_env} in .env first (profile: {config.profile or 'none'})."
        )
        return 2
    if config.api.base_url.startswith("UNSET") or not config.api.base_url:
        print("This profile has no base_url yet; fill it in config.default.toml.")
        return 2

    client = AsyncOpenAI(base_url=config.api.base_url, api_key=key, max_retries=0)
    page = await client.models.list()
    ids = sorted(model.id for model in page.data)
    shown = ids if args.all else [i for i in ids if "nemotron" in i.lower()]
    print(
        f"profile={config.profile}  endpoint={config.api.base_url}  models={len(ids)}"
    )
    for model_id in shown:
        print(" ", model_id)
    if not shown:
        print("  (no Nemotron models matched; try --all)")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
