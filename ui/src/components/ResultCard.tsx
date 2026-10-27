import { motion } from "framer-motion";
import { useCallback, useEffect, useRef, useState } from "react";
import type { Api, CodeAction } from "../api";
import { HaloMascot } from "../character/HaloMascot";
import type { PendingApproval } from "../state/reducer";

const WORKER_STATUS: Record<string, string> = {
  done: "Claude Code finished.",
  max_turns: "Claude Code stopped: it reached its turn limit.",
  budget: "Claude Code stopped: it reached its cost limit.",
  timeout: "Claude Code stopped: it ran out of time.",
  error: "Claude Code stopped unexpectedly.",
};

/** The result of a coding task. What Halo found out itself (its own test run, the
 *  review against the brief) is what the card shows; the worker's own words are only
 *  the summary line. Merge and Discard are clicks only: no key answers this card. */
export function ResultCard({
  approval,
  api,
}: {
  approval: PendingApproval;
  api: Api;
}) {
  const result = approval.result;
  const [error, setError] = useState(false);
  const [iterating, setIterating] = useState(false);
  const [feedback, setFeedback] = useState("");
  const sending = useRef(false);

  useEffect(() => {
    sending.current = false;
    setError(false);
    setIterating(false);
    setFeedback("");
  }, [approval.approvalId]);

  const send = useCallback(
    async (action: CodeAction, text?: string) => {
      if (sending.current) return;
      sending.current = true;
      setError(false);
      try {
        if (!api.codeDecide) throw new Error("no codeDecide");
        await api.codeDecide({
          runId: approval.runId,
          approvalId: approval.approvalId,
          action,
          ...(text !== undefined ? { feedback: text } : {}),
        });
      } catch {
        sending.current = false;
        setError(true);
      }
    },
    [api, approval.runId, approval.approvalId],
  );

  if (!result) return null;
  const { tests, review } = result;
  const testsLabel = tests.timedOut
    ? "Tests timed out"
    : tests.passed
      ? "Tests passed"
      : "Tests failed";
  const testsColor = tests.passed ? "#3ddc97" : "#ff4d5e";

  return (
    <motion.section
      aria-label="Coding result"
      data-risk="high"
      initial={{ opacity: 0, y: -4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: "spring", stiffness: 420, damping: 32 }}
      className="plate relative flex h-[560px] w-[500px] flex-col gap-3 overflow-hidden rounded-2xl p-4 text-ink"
    >
      <header className="flex items-center gap-2.5">
        <HaloMascot mood="asking" size={36} />
        <div className="min-w-0 flex-1">
          <div className="text-[13px] font-semibold">
            Review the result{" "}
            <span className="font-normal text-ink-dim">
              (round {result.iteration})
            </span>
          </div>
          <div
            data-testid="result-status"
            className="truncate text-[11px] text-ink-dim"
          >
            {WORKER_STATUS[result.status] ?? "Claude Code stopped."}
          </div>
        </div>
        <span
          data-testid="result-cost"
          className="shrink-0 text-[11px] text-ink-dim"
        >
          ₹{result.costInr}
        </span>
      </header>

      {result.notice && (
        <p
          role="status"
          className="rounded-lg border border-amber-400/40 bg-amber-400/10 px-2.5 py-1.5 text-[11px] text-amber-200"
        >
          {result.notice}
        </p>
      )}

      <div className="flex min-h-0 flex-1 flex-col gap-2.5 overflow-y-auto pr-1 text-[12px]">
        <p className="break-words text-ink-dim">{result.summary}</p>

        <section data-testid="result-tests">
          <div
            className="text-[11px] font-semibold uppercase tracking-wider"
            style={{ color: testsColor }}
          >
            {testsLabel}
          </div>
          {tests.tail && (
            <pre className="tile mt-1 max-h-24 overflow-auto whitespace-pre-wrap break-words rounded-lg px-2.5 py-1.5 font-mono text-[11px] text-ink-dim">
              {tests.tail}
            </pre>
          )}
        </section>

        <section data-testid="result-review">
          <div
            className={`text-[11px] font-semibold uppercase tracking-wider ${
              review?.result === "concerns" ? "text-amber-300" : "text-ink-dim"
            }`}
          >
            {review === null
              ? "Review unavailable"
              : review.result === "pass"
                ? "Review: matches the brief"
                : "Review: concerns"}
          </div>
          {review && (
            <>
              <p className="mt-0.5 break-words">{review.summary}</p>
              {review.issues.length > 0 && (
                <ul className="mt-1 list-disc pl-4">
                  {review.issues.map((issue) => (
                    <li key={issue} className="break-words">
                      {issue}
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
        </section>

        <section data-testid="result-diff">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-ink-dim">
            Changes
          </div>
          <pre className="overflow-x-auto whitespace-pre font-mono text-[11px] text-ink-dim">
            {result.diffStat || "No changes"}
          </pre>
          <div className="mt-1 font-mono text-[11px]">
            {result.changedFiles.map((file) => (
              <div key={file} className="truncate" title={file}>
                {file}
              </div>
            ))}
          </div>
          <div className="mt-1 break-all text-[11px] text-ink-dim">
            on branch {result.branch}, your checkout is untouched
          </div>
        </section>

        {iterating && (
          <label className="flex flex-col gap-1">
            <span className="text-[11px] font-medium text-ink-dim">
              What should change?
            </span>
            <textarea
              value={feedback}
              onChange={(e) => setFeedback(e.target.value)}
              rows={3}
              maxLength={2000}
              placeholder="For example: also add a test for the 429 case"
              className="tile resize-none rounded-lg px-2.5 py-1.5 text-[12px] text-ink outline-none placeholder:text-ink-dim/60 focus:ring-1 focus:ring-ink/50"
            />
          </label>
        )}
      </div>

      {error && (
        <p role="alert" className="text-[11px] text-red-300">
          That answer didn't go through. Try again.
        </p>
      )}

      <footer className="flex items-center gap-2.5 border-t border-line pt-3">
        {iterating ? (
          <>
            <button
              type="button"
              disabled={feedback.trim().length === 0}
              onClick={() => void send("iterate", feedback.trim())}
              className="rounded-md bg-ink px-3 py-1 text-[11px] font-semibold text-bg transition hover:bg-white active:scale-95 disabled:opacity-40"
            >
              Send feedback
            </button>
            <button
              type="button"
              onClick={() => setIterating(false)}
              className="rounded-md border border-line px-3 py-1 text-[11px] font-medium text-ink transition hover:bg-raised-2 active:scale-95"
            >
              Back
            </button>
          </>
        ) : (
          <>
            <button
              type="button"
              onClick={() => void send("merge")}
              className={
                tests.passed
                  ? "rounded-md bg-ink px-3 py-1 text-[11px] font-semibold text-bg transition hover:bg-white active:scale-95"
                  : "rounded-md border border-red-400/60 px-3 py-1 text-[11px] font-semibold text-red-300 transition hover:bg-red-400/10 active:scale-95"
              }
            >
              {tests.passed ? "Merge" : "Merge anyway"}
            </button>
            {result.canIterate && (
              <button
                type="button"
                onClick={() => setIterating(true)}
                className="rounded-md border border-line px-3 py-1 text-[11px] font-medium text-ink transition hover:bg-raised-2 active:scale-95"
              >
                Iterate
              </button>
            )}
            <button
              type="button"
              onClick={() => void send("discard")}
              className="ml-auto rounded-md px-2 py-1 text-[11px] text-ink-dim transition hover:text-red-300 focus-visible:ring-1 focus-visible:ring-red-300/60"
            >
              Discard
            </button>
          </>
        )}
      </footer>
    </motion.section>
  );
}
