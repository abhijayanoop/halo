import { afterEach, describe, expect, it, vi } from "vitest";
import { createApi } from "./api";

afterEach(() => vi.restoreAllMocks());

function fakeFetch(status = 200, body: unknown = { ok: true }) {
  return vi.fn(async () => new Response(JSON.stringify(body), { status }));
}

describe("api", () => {
  it("sends a run with the token header", async () => {
    const fetchFn = fakeFetch(200, { run_id: "R1" });
    const api = createApi(
      "http://h",
      "tok",
      fetchFn as unknown as typeof fetch,
    );

    await expect(api.run("open Notepad")).resolves.toEqual({ runId: "R1" });

    const [url, init] = fetchFn.mock.calls[0] as unknown as [
      string,
      RequestInit,
    ];
    expect(url).toBe("http://h/run");
    expect(init.method).toBe("POST");
    expect((init.headers as Record<string, string>)["X-Halo-Token"]).toBe(
      "tok",
    );
    expect(JSON.parse(init.body as string)).toEqual({
      request: "open Notepad",
    });
  });

  it("approves with the approval id the card was showing", async () => {
    const fetchFn = fakeFetch();
    const api = createApi(
      "http://h",
      "tok",
      fetchFn as unknown as typeof fetch,
    );

    await api.approve({ runId: "R1", approvalId: "A1", grant: "allow_once" });

    const [url, init] = fetchFn.mock.calls[0] as unknown as [
      string,
      RequestInit,
    ];
    expect(url).toBe("http://h/approve");
    expect(JSON.parse(init.body as string)).toEqual({
      run_id: "R1",
      approval_id: "A1",
      grant: "allow_once",
    });
  });

  it("omits the token header when there is none", async () => {
    const fetchFn = fakeFetch();
    await createApi(
      "http://h",
      null,
      fetchFn as unknown as typeof fetch,
    ).approve({
      runId: "R",
      approvalId: "A",
      grant: "deny",
    });
    const [, init] = fetchFn.mock.calls[0] as unknown as [string, RequestInit];
    expect(init.headers as Record<string, string>).not.toHaveProperty(
      "X-Halo-Token",
    );
  });

  it("turns a refusal into an error that says what happened", async () => {
    const api = createApi(
      "http://h",
      "tok",
      fakeFetch(409, { detail: "stale" }) as unknown as typeof fetch,
    );
    await expect(
      api.approve({ runId: "R", approvalId: "A", grant: "deny" }),
    ).rejects.toMatchObject({ status: 409 });
  });
});
