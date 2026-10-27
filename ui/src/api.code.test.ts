import { describe, expect, it, vi } from "vitest";
import { createApi } from "./api";

describe("api.codeDecide", () => {
  it("posts the decision with the token and the card's own id", async () => {
    const fetchFn = vi.fn(async () => new Response("{}", { status: 200 }));
    const api = createApi(
      "http://h",
      "tok",
      fetchFn as unknown as typeof fetch,
    );
    await api.codeDecide?.({
      runId: "R1",
      approvalId: "X1",
      action: "iterate",
      feedback: "add a test",
    });
    const [url, init] = fetchFn.mock.calls[0] as unknown as [
      string,
      RequestInit,
    ];
    expect(url).toBe("http://h/code/decision");
    expect((init.headers as Record<string, string>)["X-Halo-Token"]).toBe(
      "tok",
    );
    expect(JSON.parse(init.body as string)).toEqual({
      run_id: "R1",
      approval_id: "X1",
      action: "iterate",
      feedback: "add a test",
    });
  });

  it("sends an edited brief in the server's field names", async () => {
    const fetchFn = vi.fn(async () => new Response("{}", { status: 200 }));
    const api = createApi("http://h", null, fetchFn as unknown as typeof fetch);
    await api.codeDecide?.({
      runId: "R1",
      approvalId: "B1",
      action: "approve",
      brief: {
        goal: "g",
        acceptanceCriteria: ["c"],
        likelyFiles: ["a.py"],
        testCmd: "t",
        constraints: [],
        outOfScope: [],
      },
    });
    const [, init] = fetchFn.mock.calls[0] as unknown as [string, RequestInit];
    expect(JSON.parse(init.body as string).brief).toEqual({
      goal: "g",
      acceptance_criteria: ["c"],
      likely_files: ["a.py"],
      test_cmd: "t",
      constraints: [],
      out_of_scope: [],
    });
  });

  it("rejects when the server refuses", async () => {
    const fetchFn = vi.fn(async () => new Response("{}", { status: 409 }));
    const api = createApi("http://h", null, fetchFn as unknown as typeof fetch);
    await expect(
      api.codeDecide?.({ runId: "R1", approvalId: "X", action: "discard" }),
    ).rejects.toThrow();
  });
});
