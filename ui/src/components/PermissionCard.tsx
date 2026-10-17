import { motion } from "framer-motion";
import {
  type CSSProperties,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import type { Api, Grant } from "../api";
import { HaloMascot } from "../character/HaloMascot";
import type { PendingApproval, Risk } from "../state/reducer";

// The card takes the colour of the risk on its left edge and its label, so a
// high-risk ask looks different at a glance. Nothing else on it is coloured.
const RISK_COLOR: Record<Risk, string> = {
  low: "#3ddc97",
  medium: "#ffb020",
  high: "#ff4d5e",
};

export function PermissionCard({
  approval,
  total,
  api,
}: {
  approval: PendingApproval;
  total: number;
  api: Api;
}) {
  const [error, setError] = useState(false);
  // One answer per card: set the moment an answer is sent, cleared when the card changes
  // or the send fails. A ref, so a second key press in the same tick cannot slip through.
  const sending = useRef(false);

  useEffect(() => {
    sending.current = false;
    setError(false);
  }, [approval.approvalId]);

  const answer = useCallback(
    async (grant: Grant) => {
      if (sending.current) return;
      sending.current = true;
      setError(false);
      try {
        await api.approve({
          runId: approval.runId,
          approvalId: approval.approvalId,
          grant,
        });
      } catch {
        sending.current = false;
        setError(true);
      }
    },
    [api, approval.runId, approval.approvalId],
  );

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.repeat) return; // a held-down key must not answer twice
      // Enter on a focused button presses that button, whichever it is: the card's
      // own shortcut must never turn Enter-on-Deny into an allow.
      if (event.key === "Enter" && event.target instanceof HTMLButtonElement)
        return;
      if (event.key === "Enter") {
        event.preventDefault();
        void answer("allow_once");
      } else if (event.key === "Escape") {
        event.preventDefault();
        void answer("deny");
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [answer]);

  const color = RISK_COLOR[approval.risk];

  return (
    <motion.section
      aria-label="Permission request"
      data-risk={approval.risk}
      initial={{ opacity: 0, y: -4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: "spring", stiffness: 420, damping: 32 }}
      style={{ "--ring": color } as CSSProperties}
      className="plate relative flex h-[140px] w-[380px] gap-2.5 overflow-hidden rounded-2xl py-3 pl-4 pr-3 text-ink"
    >
      <span
        aria-hidden
        className="absolute inset-y-0 left-0 w-[3px]"
        style={{ background: color }}
      />
      <div className="shrink-0 pt-1">
        <HaloMascot mood="asking" size={40} />
      </div>

      <div className="flex min-w-0 flex-1 flex-col gap-1.5">
        <div className="flex items-baseline gap-2">
          <span
            data-testid="card-action"
            className="truncate text-[13px] font-semibold"
          >
            {approval.action}
          </span>
          <span
            data-testid="card-risk"
            className="shrink-0 text-[10px] font-semibold uppercase tracking-wider"
            style={{ color }}
          >
            {approval.risk} risk
          </span>
          {total > 1 && (
            <span
              data-testid="card-count"
              className="ml-auto shrink-0 text-[11px] text-ink-dim"
            >
              1 of {total}
            </span>
          )}
        </div>

        <code
          data-testid="card-detail"
          className="tile line-clamp-2 flex-1 break-words rounded-lg px-2.5 py-1.5 font-mono text-[11px] leading-snug text-ink-dim"
        >
          {approval.detail}
        </code>

        {error && (
          <p role="alert" className="text-[11px] text-red-300">
            That answer didn't go through. Try again.
          </p>
        )}

        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={() => void answer("allow_once")}
            className="flex items-center gap-1.5 rounded-md bg-ink px-2.5 py-1 text-[11px] font-semibold text-bg transition hover:bg-white active:scale-95"
          >
            Allow once{" "}
            <kbd className="keycap !border-black/20 !bg-black/10 !text-bg">
              ↵
            </kbd>
          </button>
          <button
            type="button"
            onClick={() => void answer("deny")}
            className="flex items-center gap-1.5 rounded-md border border-line px-2.5 py-1 text-[11px] font-medium text-ink transition hover:bg-raised-2 active:scale-95"
          >
            Deny <kbd className="keycap">Esc</kbd>
          </button>
          {approval.risk !== "high" && (
            <button
              type="button"
              onClick={() => void answer("always_for_task")}
              className="ml-auto rounded-md px-1.5 py-1 text-[11px] text-ink-dim transition hover:text-ink"
            >
              Always for this task
            </button>
          )}
        </div>
      </div>
    </motion.section>
  );
}
