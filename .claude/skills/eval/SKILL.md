---
name: eval
description: Run Halo's eval suite and summarise changes against the previous report.
disable-model-invocation: true
---
1. Copy evals/report.md to evals/report.prev.md if it exists.
2. Run `uv run python evals/run_evals.py $ARGUMENTS`. It costs Token Factory credits: ask me first if
   more than 25 live tasks will run.
3. Summarise: overall golden-task success, per-category change vs report.prev.md, attack success with
   defences off and on, cascade table changes, and the cost of this run.
4. For each regression: the task, the failing check, and the most likely cause among commits since the
   previous report.
