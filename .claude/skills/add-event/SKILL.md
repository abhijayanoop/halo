---
name: add-event
description: Change the frozen contracts safely - add or modify a HaloEvent type or shared model and update every consumer together.
disable-model-invocation: true
---
Requested change: $ARGUMENTS

Only continue if this session was started with HALO_CONTRACT_EDIT=1. If not, stop and tell me how to restart.

1. Explain the change and list every consumer (search for the type name in halo/, ui/src/, tests/, evals/).
2. Wait for my approval.
3. Update halo/core/contracts.py and docs/CONTRACTS.md.
4. Run `uv run python -m halo.core.export_schemas`, then `npm run gen:types` in ui/.
5. Update the reducer, the mood rules (if mood is affected) and the recorder as needed.
6. Update tests on both sides; run the full Python and UI suites and show the results.
7. Add a line to docs/DECISIONS.md.
