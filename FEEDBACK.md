# Feedback log

Required part of the submission, and it has its own prize. One entry per friction
point, written as it happens: what I tried, what happened, what I expected, and how
I worked around it. Covers Nebius Token Factory and every NVIDIA model or service used.

## Nebius Token Factory

- **2026-10-11 - Getting access.** Registered for the hackathon and for Token Factory;
  waiting on the API key and credits before any call can be made. Impact: Day 1's live
  checks (tool-calling spike, router eval, first real run) were blocked for 2-3 days, so
  development continued against Nemotron served by NVIDIA's hosted API instead.
  _Update this entry with how long approval took and what would have made it faster._

## NVIDIA models and services

- **2026-10-12 - Catalogue lists models the account cannot call.** `GET /v1/models` on
  `integrate.api.nvidia.com` returned 80 models including `nvidia/nemotron-nano-3-30b-a3b`, but a
  chat call to it returned HTTP 404 "Function ... Not found for account". Four older/other
  Nemotron ids 404'd the same way (`llama-3.1-nemotron-ultra-253b-v1`, `-70b-instruct`,
  `-51b-instruct`); Super, Ultra, Omni and `nemotron-3.5-lightning-30b-a3b` worked. Cost: 1 wasted
  call plus a probe to find out which ids were usable. Expected: the model list to show only
  models the key can invoke, or flag the others. Workaround: `spikes/check_models.py` sends one
  8-token call per candidate; used the Lightning 30B-A3B model as the Nano stand-in.
