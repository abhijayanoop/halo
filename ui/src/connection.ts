// Talking to the Python core: the event WebSocket, and replay of a recorded run.
import type { HaloEvent } from "./types/generated/HaloEvent";

export interface Params {
  token: string | null;
  mock: string | null;
  speed: number;
}

/** Launch parameters come from the query string or the hash (`?token=…&mock=…`). */
export function readParams(search: string, hash: string): Params {
  const query = new URLSearchParams(search);
  const fragment = new URLSearchParams(hash.replace(/^#/, ""));
  const get = (key: string) => query.get(key) ?? fragment.get(key);
  const speed = Number(get("speed"));
  return {
    token: get("token"),
    mock: get("mock"),
    speed: Number.isFinite(speed) && speed > 0 ? speed : 1,
  };
}

export function buildWsUrl(origin: string, token: string | null): string {
  const base = origin.replace(/^http/, "ws");
  return token
    ? `${base}/events?token=${encodeURIComponent(token)}`
    : `${base}/events`;
}

export type ConnectionStatus = "connecting" | "open" | "closed";

export interface ConnectOptions {
  url: string;
  onEvent: (event: HaloEvent) => void;
  onStatus?: (status: ConnectionStatus) => void;
  socketFactory?: (url: string) => WebSocket;
}

const RECONNECT_BASE_MS = 500;
const RECONNECT_MAX_MS = 10_000;

function isEvent(value: unknown): value is HaloEvent {
  const e = value as Partial<HaloEvent> | null;
  return (
    !!e &&
    typeof e.id === "string" &&
    typeof e.run_id === "string" &&
    typeof e.type === "string"
  );
}

/** Keep one WebSocket to the core open, reconnecting with a growing delay.
 *  Returns a function that stops it for good. */
export function connect(options: ConnectOptions): () => void {
  const make = options.socketFactory ?? ((url: string) => new WebSocket(url));
  let stopped = false;
  let failures = 0;
  let socket: WebSocket | null = null;
  let timer: ReturnType<typeof setTimeout> | undefined;

  const open = () => {
    options.onStatus?.("connecting");
    const ws = make(options.url);
    socket = ws;
    ws.onopen = () => {
      failures = 0;
      options.onStatus?.("open");
    };
    ws.onmessage = (message: MessageEvent<string>) => {
      let parsed: unknown;
      try {
        parsed = JSON.parse(message.data);
      } catch {
        return;
      }
      if (isEvent(parsed)) options.onEvent(parsed);
    };
    ws.onclose = () => {
      if (stopped) return;
      options.onStatus?.("closed");
      const delay = Math.min(
        RECONNECT_BASE_MS * 4 ** failures,
        RECONNECT_MAX_MS,
      );
      failures += 1;
      timer = setTimeout(open, delay);
    };
  };

  open();
  return () => {
    stopped = true;
    clearTimeout(timer);
    socket?.close();
  };
}

export interface ReplayOptions {
  speed?: number;
  maxGapMs?: number;
}

/** Play recorded events back through `onEvent` with their original gaps
 *  (divided by `speed`, each capped at `maxGapMs`). Returns a stop function. */
export function replay(
  events: HaloEvent[],
  onEvent: (event: HaloEvent) => void,
  { speed = 1, maxGapMs = 1500 }: ReplayOptions = {},
): () => void {
  let stopped = false;
  let timer: ReturnType<typeof setTimeout> | undefined;

  const play = (index: number) => {
    if (stopped || index >= events.length) return;
    onEvent(events[index]);
    const next = events[index + 1];
    if (!next) return;
    const gap = Date.parse(next.ts) - Date.parse(events[index].ts);
    const wait = Math.min(Math.max(gap, 0) / speed, maxGapMs);
    timer = setTimeout(() => play(index + 1), wait);
  };

  play(0);
  return () => {
    stopped = true;
    clearTimeout(timer);
  };
}
