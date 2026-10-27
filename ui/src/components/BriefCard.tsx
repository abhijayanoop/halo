import { motion } from "framer-motion";
import { useCallback, useEffect, useRef, useState } from "react";
import type { Api } from "../api";
import { HaloMascot } from "../character/HaloMascot";
import type { PendingApproval } from "../state/reducer";

const lines = (text: string) =>
  text
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);

const isField = (target: EventTarget | null) =>
  target instanceof HTMLTextAreaElement || target instanceof HTMLInputElement;

/** The brief of a coding task: the contract the worker builds against. The user can
 *  fix the goal and the criteria; the files and the test command come from Halo. */
export function BriefCard({
  approval,
  api,
}: {
  approval: PendingApproval;
  api: Api;
}) {
  const brief = approval.brief;
  const [goal, setGoal] = useState(brief?.goal ?? "");
  const [criteria, setCriteria] = useState(
    (brief?.acceptanceCriteria ?? []).join("\n"),
  );
  const [error, setError] = useState(false);
  // One answer per card, set the moment it is sent (a ref, so a second click in the
  // same tick cannot slip through) and cleared when the card changes or the send fails.
  const sending = useRef(false);

  useEffect(() => {
    sending.current = false;
    setError(false);
    setGoal(brief?.goal ?? "");
    setCriteria((brief?.acceptanceCriteria ?? []).join("\n"));
  }, [approval.approvalId]);

  const parsed = lines(criteria);
  const valid = goal.trim().length > 0 && parsed.length > 0;

  const send = useCallback(
    async (action: "approve" | "deny") => {
      if (sending.current || !brief) return;
      sending.current = true;
      setError(false);
      const edited =
        action === "approve" &&
        (goal.trim() !== brief.goal ||
          parsed.join("\n") !== brief.acceptanceCriteria.join("\n"));
      try {
        if (!api.codeDecide) throw new Error("no codeDecide");
        await api.codeDecide({
          runId: approval.runId,
          approvalId: approval.approvalId,
          action,
          ...(edited
            ? {
                brief: {
                  ...brief,
                  goal: goal.trim(),
                  acceptanceCriteria: parsed,
                },
              }
            : {}),
        });
      } catch {
        sending.current = false;
        setError(true);
      }
    },
    [api, approval.runId, approval.approvalId, brief, goal, parsed],
  );

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.repeat) return;
      if (event.key === "Escape" && !isField(event.target)) {
        event.preventDefault();
        void send("deny");
      } else if (
        event.key === "Enter" &&
        (event.ctrlKey || event.metaKey) &&
        valid
      ) {
        event.preventDefault();
        void send("approve");
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [send, valid]);

  if (!brief) return null;
  const list = (items: string[]) =>
    items.length === 0 ? (
      <span className="text-ink-dim">none</span>
    ) : (
      <ul className="list-disc pl-4">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    );

  return (
    <motion.section
      aria-label="Task brief"
      data-risk={approval.risk}
      initial={{ opacity: 0, y: -4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: "spring", stiffness: 420, damping: 32 }}
      className="plate relative flex h-[480px] w-[460px] flex-col gap-3 overflow-hidden rounded-2xl p-4 text-ink"
    >
      <header className="flex items-center gap-2.5">
        <HaloMascot mood="asking" size={36} />
        <div className="min-w-0 flex-1">
          <div className="text-[13px] font-semibold">Review the task brief</div>
          <div className="text-[11px] text-ink-dim">
            Nothing starts until you say so. Project:{" "}
            <span data-testid="brief-project" className="text-ink">
              {approval.project}
            </span>
          </div>
        </div>
      </header>

      <div className="flex min-h-0 flex-1 flex-col gap-2.5 overflow-y-auto pr-1 text-[12px]">
        <label className="flex flex-col gap-1">
          <span className="text-[11px] font-medium text-ink-dim">Goal</span>
          <input
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
            className="tile rounded-lg px-2.5 py-1.5 text-[12px] text-ink outline-none focus:ring-1 focus:ring-ink/50"
          />
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-[11px] font-medium text-ink-dim">
            Acceptance criteria (one per line)
          </span>
          <textarea
            value={criteria}
            onChange={(e) => setCriteria(e.target.value)}
            rows={4}
            className="tile resize-none rounded-lg px-2.5 py-1.5 text-[12px] leading-snug text-ink outline-none focus:ring-1 focus:ring-ink/50"
          />
        </label>

        <section>
          <div className="mb-0.5 text-[11px] font-medium text-ink-dim">
            Likely files
          </div>
          <div className="font-mono text-[11px]">
            {brief.likelyFiles.length === 0
              ? list([])
              : brief.likelyFiles.map((file) => (
                  <div key={file} className="truncate">
                    {file}
                  </div>
                ))}
          </div>
        </section>

        <div className="grid grid-cols-2 gap-3">
          <section>
            <div className="mb-0.5 text-[11px] font-medium text-ink-dim">
              Constraints
            </div>
            {list(brief.constraints)}
          </section>
          <section>
            <div className="mb-0.5 text-[11px] font-medium text-ink-dim">
              Out of scope
            </div>
            {list(brief.outOfScope)}
          </section>
        </div>

        <section>
          <div className="mb-0.5 text-[11px] font-medium text-ink-dim">
            Halo will run this itself (from your project note)
          </div>
          <code
            data-testid="brief-test-cmd"
            className="tile block break-words rounded-lg px-2.5 py-1.5 font-mono text-[11px] text-ink-dim"
          >
            {brief.testCmd}
          </code>
        </section>
      </div>

      {error && (
        <p role="alert" className="text-[11px] text-red-300">
          That answer didn't go through. Try again.
        </p>
      )}

      <footer className="flex items-center gap-2.5 border-t border-line pt-3">
        <button
          type="button"
          disabled={!valid}
          onClick={() => void send("approve")}
          className="flex items-center gap-1.5 rounded-md bg-ink px-3 py-1 text-[11px] font-semibold text-bg transition hover:bg-white active:scale-95 disabled:opacity-40"
        >
          Start{" "}
          <kbd className="keycap !border-black/20 !bg-black/10 !text-bg">
            Ctrl ↵
          </kbd>
        </button>
        <button
          type="button"
          onClick={() => void send("deny")}
          className="flex items-center gap-1.5 rounded-md border border-line px-3 py-1 text-[11px] font-medium text-ink transition hover:bg-raised-2 active:scale-95"
        >
          Not now <kbd className="keycap">Esc</kbd>
        </button>
      </footer>
    </motion.section>
  );
}
