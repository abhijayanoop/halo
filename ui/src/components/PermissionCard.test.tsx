import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Api } from "../api";
import type { PendingApproval } from "../state/reducer";
import { PermissionCard } from "./PermissionCard";

const approval = (extra: Partial<PendingApproval> = {}): PendingApproval => ({
  approvalId: "AP1",
  runId: "R1",
  action: "app.open",
  detail: "{'app': 'Notepad'}",
  risk: "medium",
  stepIndex: 0,
  requestedAt: "2026-10-12T10:00:00.000Z",
  ...extra,
});

let api: Api;
beforeEach(() => {
  api = { run: vi.fn(), approve: vi.fn(async () => {}) };
});

describe("PermissionCard", () => {
  it("shows what Halo wants to do, the exact detail, and the risk", () => {
    render(<PermissionCard approval={approval()} total={1} api={api} />);
    expect(screen.getByTestId("card-action")).toHaveTextContent("app.open");
    expect(screen.getByTestId("card-detail")).toHaveTextContent(
      "{'app': 'Notepad'}",
    );
    expect(screen.getByTestId("card-risk")).toHaveTextContent(/medium/i);
  });

  it("offers Allow once, Deny and Always for this task", () => {
    render(<PermissionCard approval={approval()} total={1} api={api} />);
    expect(
      screen.getByRole("button", { name: /allow once/i }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /deny/i })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /always for this task/i }),
    ).toBeInTheDocument();
  });

  it("never offers an always-grant for a high-risk action", () => {
    render(
      <PermissionCard
        approval={approval({ risk: "high" })}
        total={1}
        api={api}
      />,
    );
    expect(
      screen.queryByRole("button", { name: /always for this task/i }),
    ).toBeNull();
  });

  it("answers with the approval id the card was showing", async () => {
    render(<PermissionCard approval={approval()} total={1} api={api} />);
    await userEvent.click(screen.getByRole("button", { name: /allow once/i }));
    expect(api.approve).toHaveBeenCalledWith({
      runId: "R1",
      approvalId: "AP1",
      grant: "allow_once",
    });
  });

  it("Enter allows once and Escape denies", async () => {
    const { unmount } = render(
      <PermissionCard approval={approval()} total={1} api={api} />,
    );
    await userEvent.keyboard("{Enter}");
    expect(api.approve).toHaveBeenLastCalledWith(
      expect.objectContaining({ grant: "allow_once" }),
    );
    unmount();

    render(
      <PermissionCard
        approval={approval({ approvalId: "AP2" })}
        total={1}
        api={api}
      />,
    );
    await userEvent.keyboard("{Escape}");
    expect(api.approve).toHaveBeenLastCalledWith(
      expect.objectContaining({ approvalId: "AP2", grant: "deny" }),
    );
  });

  it("sends one answer only, however many keys or clicks arrive", async () => {
    let finish: () => void = () => {};
    api.approve = vi.fn(
      () => new Promise<void>((resolve) => (finish = resolve)),
    );
    render(<PermissionCard approval={approval()} total={1} api={api} />);

    await userEvent.keyboard("{Enter}{Enter}{Escape}");
    await userEvent.click(screen.getByRole("button", { name: /allow once/i }));

    expect(api.approve).toHaveBeenCalledTimes(1);
    finish();
  });

  it("is ready for the next card when the approval changes", async () => {
    const { rerender } = render(
      <PermissionCard approval={approval()} total={1} api={api} />,
    );
    await userEvent.keyboard("{Enter}");
    rerender(
      <PermissionCard
        approval={approval({ approvalId: "AP2" })}
        total={1}
        api={api}
      />,
    );
    await userEvent.keyboard("{Enter}");
    expect(api.approve).toHaveBeenCalledTimes(2);
    expect(api.approve).toHaveBeenLastCalledWith(
      expect.objectContaining({ approvalId: "AP2" }),
    );
  });

  it("says so, and lets the user try again, when the answer did not get through", async () => {
    api.approve = vi
      .fn()
      .mockRejectedValueOnce(new Error("nope"))
      .mockResolvedValueOnce(undefined);
    render(<PermissionCard approval={approval()} total={1} api={api} />);

    await userEvent.keyboard("{Enter}");
    expect(await screen.findByRole("alert")).toHaveTextContent(
      /didn't go through/i,
    );

    await userEvent.keyboard("{Enter}");
    await waitFor(() => expect(api.approve).toHaveBeenCalledTimes(2));
  });

  it("says how many are waiting when there is more than one", () => {
    render(<PermissionCard approval={approval()} total={3} api={api} />);
    expect(screen.getByTestId("card-count")).toHaveTextContent("1 of 3");
  });

  it("shows no count for a single request", () => {
    render(<PermissionCard approval={approval()} total={1} api={api} />);
    expect(screen.queryByTestId("card-count")).toBeNull();
  });

  it("Enter on a focused Deny button denies; it never allows", async () => {
    render(<PermissionCard approval={approval()} total={1} api={api} />);
    screen.getByRole("button", { name: /deny/i }).focus();
    await userEvent.keyboard("{Enter}");
    expect(api.approve).toHaveBeenCalledTimes(1);
    expect(api.approve).toHaveBeenCalledWith(expect.objectContaining({ grant: "deny" }));
  });

  it("Enter on Always for this task grants that, not Allow once", async () => {
    render(<PermissionCard approval={approval()} total={1} api={api} />);
    screen.getByRole("button", { name: /always for this task/i }).focus();
    await userEvent.keyboard("{Enter}");
    expect(api.approve).toHaveBeenCalledTimes(1);
    expect(api.approve).toHaveBeenCalledWith(
      expect.objectContaining({ grant: "always_for_task" }),
    );
  });

  it("ignores a held-down key", async () => {
    render(<PermissionCard approval={approval()} total={1} api={api} />);
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", repeat: true }));
    expect(api.approve).not.toHaveBeenCalled();
  });
});
