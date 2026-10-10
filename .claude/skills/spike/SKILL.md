---
name: spike
description: Run a time-boxed technical experiment that answers one question with a number, and record the result.
---
Question: $ARGUMENTS

1. Restate the question, the number(s) that will answer it, and the decision each outcome leads to.
2. Write the smallest script that measures it in spikes/<short-name>.py. Load secrets with
   python-dotenv; never print them.
3. Run it. If it needs my hardware (microphone, screen), tell me exactly how to run it and wait for my output.
4. Append to spikes/RESULTS.md: date, question, method, result with numbers, decision.
5. Spike code is throwaway. Never import it from halo/.
