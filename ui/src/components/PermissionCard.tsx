import { useCallback, useEffect, useRef, useState } from "react";
import type { Api, Grant } from "../api";
import type { PendingApproval, Risk } from "../state/reducer";

const RISK_STYLE: Record<Risk, string> = {
  low: "bg-emerald-400/20 text-emerald-200",
  medium: "bg-amber-400/20 text-amber-200",
  high: "bg-red-400/25 text-red-200",
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

  return (
    <section
      aria-label="Permission request"
      className="flex h-[140px] w-[380px] flex-col gap-1.5 rounded-2xl border border-amber-300/40 bg-slate-900/90 p-3 text-slate-100 shadow-xl backdrop-blur"
    >
      <div className="flex items-center gap-2">
        <span
          data-testid="card-action"
          className="truncate text-sm font-medium"
        >
          {approval.action}
        </span>
        <span
          data-testid="card-risk"
          className={`rounded px-1.5 py-0.5 text-[10px] uppercase tracking-wide ${RISK_STYLE[approval.risk]}`}
        >
          {approval.risk} risk
        </span>
        {total > 1 && (
          <span
            data-testid="card-count"
            className="ml-auto text-[11px] text-slate-400"
          >
            1 of {total}
          </span>
        )}
      </div>

      <code
        data-testid="card-detail"
        className="line-clamp-2 flex-1 break-all rounded bg-black/30 px-2 py-1 text-[12px] text-slate-200"
      >
        {approval.detail}
      </code>

      {error && (
        <p role="alert" className="text-[11px] text-red-300">
          That answer didn't go through. Try again.
        </p>
      )}

      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => void answer("allow_once")}
          className="rounded-md bg-amber-400 px-3 py-1 text-xs font-medium text-slate-900 hover:bg-amber-300"
        >
          Allow once <kbd className="opacity-60">↵</kbd>
        </button>
        <button
          type="button"
          onClick={() => void answer("deny")}
          className="rounded-md bg-white/10 px-3 py-1 text-xs hover:bg-white/20"
        >
          Deny <kbd className="opacity-60">Esc</kbd>
        </button>
        {approval.risk !== "high" && (
          <button
            type="button"
            onClick={() => void answer("always_for_task")}
            className="ml-auto rounded-md px-2 py-1 text-xs text-slate-400 hover:text-slate-200"
          >
            Always for this task
          </button>
        )}
      </div>
    </section>
  );
}
