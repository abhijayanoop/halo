# LangGraph notes (verified 2026-10-11)

Versions installed: langgraph 1.2.14, langgraph-checkpoint 4.2.0,
langgraph-checkpoint-sqlite 3.1.1, Python 3.12. Docs: https://docs.langchain.com/oss/python/langgraph/

What we rely on, and how it was checked (a probe script, not just the docs):

- **Async SQLite checkpointer on a file works.** `AsyncSqliteSaver(conn, serde=...)` over an
  `aiosqlite` connection, `thread_id` = run id. Use only async calls (`ainvoke`) with it.
- **Interrupt and resume.** `interrupt(payload)` pauses; `ainvoke` returns a dict with
  `"__interrupt__"` whose first item has `.value`. `astream` yields a chunk
  `{"__interrupt__": (...)}`. Resume with `ainvoke(Command(resume=value), config)` on the same
  thread. The paused node re-runs from its top on resume, so nothing observable (events, writes)
  may happen before `interrupt()` in that node.
- **Failed runs resume.** If a node raises, state up to the previous node is checkpointed.
  `ainvoke(None, config)` on the same thread continues at the failed node and does not re-run
  earlier ones. (Not stated in the docs; confirmed by the probe and by tests/core/test_graph_runner.py.)
- **Pydantic models in state round-trip** (`Intent`, `Plan`, ...) but the default serializer logs
  "Deserializing unregistered type ... will be blocked in a future version". Fix: pass
  `JsonPlusSerializer(allowed_msgpack_modules=[("halo.core.contracts", "Intent"), ...])`.
  A test fails if that warning ever returns.
- **Dependencies** (model client, registry, emit) are passed by closure in `build_graph(deps, ...)`.
  `context_schema`/`Runtime` also works but was not needed.
- **Pitfall:** `AsyncSqliteSaver.from_conn_string` takes no serializer, so build the saver from a
  connection directly (see `open_checkpointer` in `src/halo/core/graph.py`).
