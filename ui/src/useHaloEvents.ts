import { useEffect } from "react";
import { buildWsUrl, connect, readParams, replay } from "./connection";
import { parseJsonl } from "./state/reducer";
import { useStore } from "./state/store";

/** Where `?mock=` files are read from: a URL as is, or a local path via Vite's /@fs. */
export function mockUrl(mock: string): string {
  if (/^(https?:)?\/\//.test(mock) || mock.startsWith("/@fs/")) return mock;
  return `/@fs/${mock.replace(/\\/g, "/").replace(/^\/+/, "")}`;
}

/** Feed the store from the live event stream, or from a recorded run (`?mock=`). */
export function useHaloEvents(): void {
  useEffect(() => {
    const { apply, setConnection, reset } = useStore.getState();
    const params = readParams(window.location.search, window.location.hash);

    if (params.mock) {
      const controller = new AbortController();
      let stop = () => {};
      reset();
      fetch(mockUrl(params.mock), { signal: controller.signal })
        .then((r) => r.text())
        .then((text) => {
          setConnection("open");
          stop = replay(parseJsonl(text), apply, { speed: params.speed });
        })
        .catch((error: unknown) => {
          if (!controller.signal.aborted)
            console.error("mock replay failed", error);
        });
      return () => {
        controller.abort();
        stop();
      };
    }

    return connect({
      url: buildWsUrl(window.location.origin, params.token),
      onEvent: apply,
      onStatus: setConnection,
    });
  }, []);
}
