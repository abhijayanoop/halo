import { useStore } from "./state/store";
import { useHaloEvents } from "./useHaloEvents";

// Placeholder shell: shows what the reducer derived. Replaced by the mascot,
// bar and panel in the next stage.
export default function App() {
  useHaloEvents();
  const halo = useStore((s) => s.halo);
  const connection = useStore((s) => s.connection);
  return (
    <div className="p-2 text-sm">
      <div data-testid="mood">{halo.mood}</div>
      <div data-testid="status">{halo.statusLine}</div>
      <div data-testid="connection">{connection}</div>
    </div>
  );
}
