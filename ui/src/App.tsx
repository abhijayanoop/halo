import { useEffect, useMemo } from "react";
import { createApi } from "./api";
import { CollapsedBar } from "./components/CollapsedBar";
import { MoodsPage } from "./components/MoodsPage";
import { Panel } from "./components/Panel";
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
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setExpanded(false);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [setExpanded]);

  if (view === "panel")
    return (
      <Panel halo={halo} api={api} onCollapse={() => setExpanded(false)} />
    );
  if (view === "card") return <div data-testid="permission-card-slot" />;
  return <CollapsedBar halo={halo} onExpand={() => setExpanded(true)} />;
}
