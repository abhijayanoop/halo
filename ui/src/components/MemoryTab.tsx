import { motion } from "framer-motion";
import { useState } from "react";
import type { Api } from "../api";
import type { ProposedMemory } from "../state/reducer";

/** What Halo thinks is worth remembering. Nothing here is a memory until the
 *  user approves it; approving writes it to a note, rejecting discards it. */
export function MemoryTab({
  proposals,
  api,
}: {
  proposals: ProposedMemory[];
  api: Api;
}) {
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState(false);

  const decide = async (
    candidateId: string,
    call: ((id: string) => Promise<void>) | undefined,
  ) => {
    if (!call || busy) return;
    setBusy(candidateId);
    setError(false);
    try {
      await call(candidateId);
    } catch {
      setError(true);
    } finally {
      setBusy(null);
    }
  };

  if (proposals.length === 0)
    return (
      <div className="flex h-full flex-col items-center justify-center gap-1 p-6 text-center">
        <p className="text-sm text-ink">Nothing waiting.</p>
        <p className="text-xs text-ink-dim">
          When Halo notices something worth remembering, it will ask here first.
        </p>
      </div>
    );

  return (
    <div className="flex flex-col gap-2 p-3">
      {error && (
        <p role="alert" className="text-xs text-red-300">
          That answer didn't go through. Try again.
        </p>
      )}
      <ul aria-label="Proposed memories" className="flex flex-col gap-2">
        {proposals.map((p) => (
          <motion.li
            key={p.candidateId}
            data-testid="proposed-memory"
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.2 }}
            className="flex flex-col gap-2 tile rounded-xl p-3"
          >
            <p className="text-[13px] leading-snug text-ink">{p.fact}</p>
            <div className="flex flex-wrap items-center gap-1.5 text-[10px]">
              {p.subject && (
                <span className="rounded-full bg-raised-2 px-2 py-0.5 text-ink">
                  {p.subject}
                </span>
              )}
              <span className="rounded-full bg-raised-2 px-2 py-0.5 text-ink-dim">
                {p.source}
              </span>
              <span className="rounded-full bg-raised-2 px-2 py-0.5 text-ink-dim">
                {p.trust} trust
              </span>
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                disabled={busy !== null}
                onClick={() => void decide(p.candidateId, api.memoryApprove)}
                className="rounded-md bg-ink px-3 py-1 text-xs font-semibold text-bg transition hover:bg-white active:scale-95 disabled:opacity-40"
              >
                Approve
              </button>
              <button
                type="button"
                disabled={busy !== null}
                onClick={() => void decide(p.candidateId, api.memoryReject)}
                className="rounded-md border border-line px-3 py-1 text-xs font-medium transition hover:bg-raised-2 active:scale-95 disabled:opacity-40"
              >
                Reject
              </button>
            </div>
          </motion.li>
        ))}
      </ul>
    </div>
  );
}
