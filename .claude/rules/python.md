---
paths:
  - "src/halo/**/*.py"
  - "evals/**/*.py"
---
# Python rules
- Type hints on every function; data crossing module boundaries is a Pydantic v2 model.
- Network and file I/O are async; wrap blocking calls in asyncio.to_thread.
- Config comes from halo/config.py (pydantic-settings), not scattered os.environ reads.
- Use the module logger (logging.getLogger(__name__)); no print().
- Raise specific exceptions; never a bare except.
- subprocess calls take a list of args; never shell=True.
