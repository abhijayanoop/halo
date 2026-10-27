import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Api } from "../api";
import type { BriefData, PendingApproval, ResultData } from "../state/reducer";
import { BriefCard } from "./BriefCard";
import { ResultCard } from "./ResultCard";

const brief: BriefData = {
  goal: "Add rate limiting",
  acceptanceCriteria: ["Over-limit requests get 429", "Existing tests pass"],
  likelyFiles: ["src/webhook.py"],
  testCmd: "uv run pytest -q",
  constraints: ["No new dependencies"],
  outOfScope: ["Auth"],
};

const result: ResultData = {
  project: "halo",
  status: "done",
  summary: "Added the limiter",
  tests: { passed: true, exitCode: 0, timedOut: false, tail: "12 passed" },
  review: { result: "pass", summary: "Meets the criteria", issues: [] },
  diffStat: "1 file changed, 9 insertions(+)",
  changedFiles: ["src/webhook.py"],
  costInr: "11.40",
  branch: "halo/add-rate-limiting-ab12cd",
  worktree: "C:/x/wt",
  iteration: 1,
  canIterate: true,
  notice: "",
};

const approval = (extra: Partial<PendingApproval>): PendingApproval => ({
  approvalId: "AP1",
  runId: "R1",
  action: "x",
  detail: "",
  risk: "medium",
  stepIndex: 0,
  requestedAt: "2026-10-27T10:00:00.000Z",
  ...extra,
});

const briefApproval = () =>
  approval({ kind: "code.brief", brief, project: "halo" });
const resultApproval = (r: Partial<ResultData> = {}) =>
  approval({
    kind: "code.result",
    risk: "high",
    result: { ...result, ...r },
    project: "halo",
  });

let api: Api;
let decide: ReturnType<typeof vi.fn>;
beforeEach(() => {
  decide = vi.fn(async () => {});
  api = {
    run: vi.fn(),
    approve: vi.fn(),
    codeDecide: decide,
  } as unknown as Api;
});

describe("BriefCard", () => {
  it("shows the goal, the criteria, the files and the test command Halo will run", () => {
    render(<BriefCard approval={briefApproval()} api={api} />);
    expect(screen.getByLabelText(/goal/i)).toHaveValue("Add rate limiting");
    expect(screen.getByLabelText(/acceptance criteria/i)).toHaveValue(
      "Over-limit requests get 429\nExisting tests pass",
    );
    expect(screen.getByText("src/webhook.py")).toBeInTheDocument();
    expect(screen.getByTestId("brief-test-cmd")).toHaveTextContent(
      "uv run pytest -q",
    );
    expect(screen.getByTestId("brief-project")).toHaveTextContent("halo");
  });

  it("the test command cannot be edited on the card", () => {
    render(<BriefCard approval={briefApproval()} api={api} />);
    expect(screen.queryByLabelText(/test command/i)).toBeNull();
  });

  it("Start approves the brief as it came, without resending it", async () => {
    render(<BriefCard approval={briefApproval()} api={api} />);
    await userEvent.click(screen.getByRole("button", { name: /start/i }));
    expect(decide).toHaveBeenCalledWith({
      runId: "R1",
      approvalId: "AP1",
      action: "approve",
    });
  });

  it("an edited goal and criteria go with the approval", async () => {
    render(<BriefCard approval={briefApproval()} api={api} />);
    const goal = screen.getByLabelText(/goal/i);
    await userEvent.clear(goal);
    await userEvent.type(goal, "Add rate limiting, per user");
    const criteria = screen.getByLabelText(/acceptance criteria/i);
    await userEvent.clear(criteria);
    await userEvent.type(criteria, "429 over the limit{Enter}A test covers it");
    await userEvent.click(screen.getByRole("button", { name: /start/i }));
    expect(decide).toHaveBeenCalledWith({
      runId: "R1",
      approvalId: "AP1",
      action: "approve",
      brief: {
        ...brief,
        goal: "Add rate limiting, per user",
        acceptanceCriteria: ["429 over the limit", "A test covers it"],
      },
    });
  });

  it("cannot start with no goal or no criteria", async () => {
    render(<BriefCard approval={briefApproval()} api={api} />);
    await userEvent.clear(screen.getByLabelText(/goal/i));
    expect(screen.getByRole("button", { name: /start/i })).toBeDisabled();
    await userEvent.type(screen.getByLabelText(/goal/i), "x");
    await userEvent.clear(screen.getByLabelText(/acceptance criteria/i));
    expect(screen.getByRole("button", { name: /start/i })).toBeDisabled();
  });

  it("Not now and Escape both deny", async () => {
    const { unmount } = render(
      <BriefCard approval={briefApproval()} api={api} />,
    );
    await userEvent.click(screen.getByRole("button", { name: /not now/i }));
    expect(decide).toHaveBeenLastCalledWith(
      expect.objectContaining({ action: "deny" }),
    );
    unmount();
    render(<BriefCard approval={briefApproval()} api={api} />);
    await userEvent.keyboard("{Escape}");
    expect(decide).toHaveBeenLastCalledWith(
      expect.objectContaining({ action: "deny" }),
    );
  });

  it("Enter while typing in a field does not approve", async () => {
    render(<BriefCard approval={briefApproval()} api={api} />);
    await userEvent.type(screen.getByLabelText(/goal/i), "{Enter}");
    await userEvent.type(
      screen.getByLabelText(/acceptance criteria/i),
      "{Enter}",
    );
    expect(decide).not.toHaveBeenCalled();
  });

  it("answers only once even when clicked twice", async () => {
    render(<BriefCard approval={briefApproval()} api={api} />);
    await userEvent.dblClick(screen.getByRole("button", { name: /start/i }));
    expect(decide).toHaveBeenCalledTimes(1);
  });

  it("says so when the answer did not go through, and lets the user try again", async () => {
    decide.mockRejectedValueOnce(new Error("nope"));
    render(<BriefCard approval={briefApproval()} api={api} />);
    await userEvent.click(screen.getByRole("button", { name: /start/i }));
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /start/i }));
    await waitFor(() => expect(decide).toHaveBeenCalledTimes(2));
  });
});

describe("ResultCard", () => {
  it("shows Halo's own test result, the review, the diff and the cost", () => {
    render(<ResultCard approval={resultApproval()} api={api} />);
    expect(screen.getByTestId("result-tests")).toHaveTextContent(/passed/i);
    expect(screen.getByTestId("result-tests")).toHaveTextContent("12 passed");
    expect(screen.getByTestId("result-review")).toHaveTextContent(
      "Meets the criteria",
    );
    expect(screen.getByTestId("result-diff")).toHaveTextContent("9 insertions");
    expect(screen.getByText("src/webhook.py")).toBeInTheDocument();
    expect(screen.getByTestId("result-cost")).toHaveTextContent("11.40");
  });

  it("a failed test run is shown as failed, whatever the review says", () => {
    render(
      <ResultCard
        approval={resultApproval({
          tests: {
            passed: false,
            exitCode: 1,
            timedOut: false,
            tail: "1 failed",
          },
        })}
        api={api}
      />,
    );
    expect(screen.getByTestId("result-tests")).toHaveTextContent(/failed/i);
    expect(
      screen.getByRole("button", { name: /merge anyway/i }),
    ).toBeInTheDocument();
  });

  it("a timed-out test run says it timed out", () => {
    render(
      <ResultCard
        approval={resultApproval({
          tests: { passed: false, exitCode: null, timedOut: true, tail: "" },
        })}
        api={api}
      />,
    );
    expect(screen.getByTestId("result-tests")).toHaveTextContent(/timed out/i);
  });

  it("lists review issues and a worker that stopped early", () => {
    render(
      <ResultCard
        approval={resultApproval({
          status: "budget",
          review: {
            result: "concerns",
            summary: "Missing a test",
            issues: ["no 429 test"],
          },
        })}
        api={api}
      />,
    );
    expect(screen.getByText("no 429 test")).toBeInTheDocument();
    expect(screen.getByTestId("result-status")).toHaveTextContent(
      /cost limit|budget/i,
    );
  });

  it("shows a notice such as a refused merge", () => {
    render(
      <ResultCard
        approval={resultApproval({
          notice: "Could not merge: uncommitted changes",
        })}
        api={api}
      />,
    );
    expect(screen.getByRole("status")).toHaveTextContent("uncommitted changes");
  });

  it("Merge and Discard answer with the card's id", async () => {
    const { unmount } = render(
      <ResultCard approval={resultApproval()} api={api} />,
    );
    await userEvent.click(screen.getByRole("button", { name: /^merge/i }));
    expect(decide).toHaveBeenCalledWith({
      runId: "R1",
      approvalId: "AP1",
      action: "merge",
    });
    unmount();
    render(<ResultCard approval={resultApproval()} api={api} />);
    await userEvent.click(screen.getByRole("button", { name: /discard/i }));
    expect(decide).toHaveBeenLastCalledWith({
      runId: "R1",
      approvalId: "AP1",
      action: "discard",
    });
  });

  it("neither Enter nor Escape merges or discards", async () => {
    render(<ResultCard approval={resultApproval()} api={api} />);
    await userEvent.keyboard("{Enter}");
    await userEvent.keyboard("{Escape}");
    expect(decide).not.toHaveBeenCalled();
  });

  it("Iterate asks for feedback first and sends it", async () => {
    render(<ResultCard approval={resultApproval()} api={api} />);
    await userEvent.click(screen.getByRole("button", { name: /iterate/i }));
    const send = screen.getByRole("button", { name: /send feedback/i });
    expect(send).toBeDisabled();
    await userEvent.type(
      screen.getByLabelText(/what should change/i),
      "add a test",
    );
    await userEvent.click(send);
    expect(decide).toHaveBeenCalledWith({
      runId: "R1",
      approvalId: "AP1",
      action: "iterate",
      feedback: "add a test",
    });
  });

  it("offers no Iterate after the last round", () => {
    render(
      <ResultCard approval={resultApproval({ canIterate: false })} api={api} />,
    );
    expect(screen.queryByRole("button", { name: /iterate/i })).toBeNull();
  });

  it("answers only once even when Merge is clicked twice", async () => {
    render(<ResultCard approval={resultApproval()} api={api} />);
    await userEvent.dblClick(screen.getByRole("button", { name: /^merge/i }));
    expect(decide).toHaveBeenCalledTimes(1);
  });

  it("untrusted text is shown as text, never as markup", () => {
    const evil = '<img src=x onerror="alert(1)"><script>alert(2)</script>';
    const { container } = render(
      <ResultCard
        approval={resultApproval({
          summary: evil,
          tests: { passed: true, exitCode: 0, timedOut: false, tail: evil },
          review: { result: "pass", summary: evil, issues: [evil] },
        })}
        api={api}
      />,
    );
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("script")).toBeNull();
    expect(screen.getAllByText(evil, { exact: false }).length).toBeGreaterThan(
      0,
    );
  });
});
