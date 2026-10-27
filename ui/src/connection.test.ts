import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { buildWsUrl, connect, readParams, replay } from "./connection";
import type { HaloEvent } from "./types/generated/HaloEvent";

class FakeSocket {
  static instances: FakeSocket[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  closed = false;
  constructor(public url: string) {
    FakeSocket.instances.push(this);
  }
  close() {
    this.closed = true;
  }
}

const event = (id: string, ts = "2026-10-12T10:00:00.000Z"): HaloEvent => ({
  id,
  run_id: "R",
  ts,
  type: "run.started",
  title: id,
  payload: {},
});

describe("readParams", () => {
  it("reads the token and mock from the query string or the hash", () => {
    expect(readParams("?token=abc&mock=/x.jsonl", "")).toMatchObject({
      token: "abc",
      mock: "/x.jsonl",
    });
    expect(readParams("", "#token=def")).toMatchObject({ token: "def" });
  });

  it("defaults to no token, no mock", () => {
    expect(readParams("", "")).toEqual({ token: null, mock: null, speed: 1 });
  });

  it("treats a bad speed as 1", () => {
    expect(readParams("?speed=nope", "").speed).toBe(1);
    expect(readParams("?speed=4", "").speed).toBe(4);
  });
});

describe("buildWsUrl", () => {
  it("turns http into ws and puts the token in the query", () => {
    expect(buildWsUrl("http://127.0.0.1:8765", "t0k")).toBe(
      "ws://127.0.0.1:8765/events?token=t0k",
    );
    expect(buildWsUrl("https://h", null)).toBe("wss://h/events");
  });

  it("escapes the token", () => {
    expect(buildWsUrl("http://h", "a b&c")).toBe(
      "ws://h/events?token=a%20b%26c",
    );
  });
});

describe("connect", () => {
  beforeEach(() => {
    FakeSocket.instances = [];
    vi.useFakeTimers();
  });
  afterEach(() => vi.useRealTimers());

  it("delivers every event the server sends", () => {
    const got: string[] = [];
    const status: string[] = [];
    connect({
      url: "ws://x/events",
      onEvent: (e) => got.push(e.id),
      onStatus: (s) => status.push(s),
      socketFactory: (u) => new FakeSocket(u) as unknown as WebSocket,
    });
    const socket = FakeSocket.instances[0];
    socket.onopen?.();
    socket.onmessage?.({ data: JSON.stringify(event("a")) });
    socket.onmessage?.({ data: JSON.stringify(event("b")) });
    expect(got).toEqual(["a", "b"]);
    expect(status).toEqual(["connecting", "open"]);
  });

  it("ignores a message that is not a HaloEvent", () => {
    const got: string[] = [];
    connect({
      url: "ws://x",
      onEvent: (e) => got.push(e.id),
      socketFactory: (u) => new FakeSocket(u) as unknown as WebSocket,
    });
    const socket = FakeSocket.instances[0];
    socket.onmessage?.({ data: "garbage" });
    socket.onmessage?.({ data: '{"hello":1}' });
    expect(got).toEqual([]);
  });

  it("reconnects with a growing delay after the socket closes", () => {
    connect({
      url: "ws://x",
      onEvent: () => {},
      socketFactory: (u) => new FakeSocket(u) as unknown as WebSocket,
    });
    FakeSocket.instances[0].onclose?.();
    vi.advanceTimersByTime(500);
    expect(FakeSocket.instances).toHaveLength(2);
    FakeSocket.instances[1].onclose?.();
    vi.advanceTimersByTime(500);
    expect(FakeSocket.instances).toHaveLength(2); // second wait is longer
    vi.advanceTimersByTime(1500);
    expect(FakeSocket.instances).toHaveLength(3);
  });

  it("a successful open resets the reconnect delay", () => {
    connect({
      url: "ws://x",
      onEvent: () => {},
      socketFactory: (u) => new FakeSocket(u) as unknown as WebSocket,
    });
    FakeSocket.instances[0].onclose?.();
    vi.advanceTimersByTime(500);
    FakeSocket.instances[1].onopen?.();
    FakeSocket.instances[1].onclose?.();
    vi.advanceTimersByTime(500);
    expect(FakeSocket.instances).toHaveLength(3);
  });

  it("stops for good once disconnected", () => {
    const stop = connect({
      url: "ws://x",
      onEvent: () => {},
      socketFactory: (u) => new FakeSocket(u) as unknown as WebSocket,
    });
    stop();
    expect(FakeSocket.instances[0].closed).toBe(true);
    FakeSocket.instances[0].onclose?.();
    vi.advanceTimersByTime(60_000);
    expect(FakeSocket.instances).toHaveLength(1);
  });
});

describe("replay", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  const events = [
    event("a", "2026-10-12T10:00:00.000Z"),
    event("b", "2026-10-12T10:00:01.000Z"),
    event("c", "2026-10-12T10:00:30.000Z"),
  ];

  it("plays events in order with their original gaps", () => {
    const got: string[] = [];
    replay(events, (e) => got.push(e.id), { speed: 1 });
    expect(got).toEqual(["a"]);
    vi.advanceTimersByTime(999);
    expect(got).toEqual(["a"]);
    vi.advanceTimersByTime(1);
    expect(got).toEqual(["a", "b"]);
  });

  it("caps a long gap so a replay never stalls", () => {
    const got: string[] = [];
    replay(events, (e) => got.push(e.id), { speed: 1, maxGapMs: 2000 });
    vi.advanceTimersByTime(1000 + 2000);
    expect(got).toEqual(["a", "b", "c"]);
  });

  it("speed divides the gaps", () => {
    const got: string[] = [];
    replay(events, (e) => got.push(e.id), { speed: 4 });
    vi.advanceTimersByTime(250);
    expect(got).toEqual(["a", "b"]);
  });

  it("can be stopped", () => {
    const got: string[] = [];
    const stop = replay(events, (e) => got.push(e.id), { speed: 1 });
    stop();
    vi.advanceTimersByTime(60_000);
    expect(got).toEqual(["a"]);
  });
});
