import { motion } from "framer-motion";
import {
  type CSSProperties,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import type { Api, Grant } from "../api";
import type { PendingApproval, Risk } from "../state/reducer";

const RISK_STYLE: Record<Risk, string> = {
  low: "bg-emerald-400/20 text-emerald-200",
  medium: "bg-amber-400/20 text-amber-200",
  high: "bg-red-400/25 text-red-200",
};

// The card takes the colour of the risk, so a high-risk ask looks different at a glance.
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
      initial={{ opacity: 0, scale: 0.96 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ type: "spring", stiffness: 420, damping: 28 }}
      style={{ "--ring": color } as CSSProperties}
      className="glass flex h-[140px] w-[380px] flex-col gap-1.5 rounded-2xl p-3 text-ink"
    >
      <div className="flex items-center gap-2">
        <span
          aria-hidden
          className="h-2 w-2 shrink-0 animate-pulse rounded-full"
          style={{ background: color }}
        />
        <span
          data-testid="card-action"
          className="truncate text-sm font-semibold"
        >
          {approval.action}
        </span>
        <span
          data-testid="card-risk"
          className={`rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide ${RISK_STYLE[approval.risk]}`}
        >
          {approval.risk} risk
        </span>
        {total > 1 && (
          <span
            data-testid="card-count"
            className="ml-auto text-[11px] text-ink-dim"
          >
            1 of {total}
          </span>
        )}
      </div>

      <code
        data-testid="card-detail"
        className="line-clamp-2 flex-1 break-all rounded-lg bg-black/35 px-2.5 py-1.5 font-mono text-[11.5px] leading-snug text-ink"
      >
        {approval.detail}
      </code>

      {error && (
        <p role="alert" className="text-[11px] text-red-300">
          That answer didn't go through. Try again.
        </p>
      )}

      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => void answer("allow_once")}
          className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold text-slate-900 transition hover:brightness-110 active:scale-95"
          style={{ background: color }}
        >
          Allow once{" "}
          <kbd className="keycap !border-black/20 !bg-black/15">↵</kbd>
        </button>
        <button
          type="button"
          onClick={() => void answer("deny")}
          className="flex items-center gap-1.5 rounded-lg bg-white/10 px-3 py-1.5 text-xs font-medium transition hover:bg-white/20 active:scale-95"
        >
          Deny <kbd className="keycap">Esc</kbd>
        </button>
        {approval.risk !== "high" && (
          <button
            type="button"
            onClick={() => void answer("always_for_task")}
            className="ml-auto rounded-lg px-2 py-1.5 text-xs text-ink-dim transition hover:text-ink"
          >
            Always for this task
          </button>
        )}
      </div>
    </motion.section>
  );
}
