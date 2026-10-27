import { useEffect, useMemo } from "react";
import { createApi } from "./api";
import { BriefCard } from "./components/BriefCard";
import { CollapsedBar } from "./components/CollapsedBar";
import { MoodsPage } from "./components/MoodsPage";
import { Panel } from "./components/Panel";
import { PermissionCard } from "./components/PermissionCard";
import { ResultCard } from "./components/ResultCard";
import { readParams } from "./connection";
import { useStore } from "./state/store";
import { useHaloEvents } from "./useHaloEvents";
import { SIZES, selectView } from "./view";
import { resizeWindow } from "./windowBridge";

export default function App() {
  if (import.meta.env.DEV && window.location.pathname === "/moods")
    return <MoodsPage />;
  return <Hud />;
}

function Hud() {
  useHaloEvents();
  const halo = useStore((s) => s.halo);
  const expanded = useStore((s) => s.expanded);
  const setExpanded = useStore((s) => s.setExpanded);
  const view = selectView(halo, expanded);
  const api = useMemo(
    () =>
      createApi(
        window.location.origin,
        readParams(window.location.search, window.location.hash).token,
      ),
    [],
  );

  // The window follows the view: bar, permission card, or panel.
  useEffect(() => {
    resizeWindow(...SIZES[view]);
  }, [view]);

  useEffect(() => {
    // On the permission card Escape means Deny (the card handles it), not collapse.
    if (view === "card" || view === "brief" || view === "result") return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setExpanded(false);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [setExpanded, view]);

  if (view === "brief")
    return <BriefCard approval={halo.pendingApprovals[0]} api={api} />;
  if (view === "result")
    return <ResultCard approval={halo.pendingApprovals[0]} api={api} />;
  if (view === "card") {
    return (
      <PermissionCard
        approval={halo.pendingApprovals[0]}
        total={halo.pendingApprovals.length}
        api={api}
      />
    );
  }
  if (view === "panel")
    return (
      <Panel halo={halo} api={api} onCollapse={() => setExpanded(false)} />
    );
  return <CollapsedBar halo={halo} onExpand={() => setExpanded(true)} />;
}
