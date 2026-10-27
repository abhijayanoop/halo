// The calls the HUD makes: start a run, answer an approval card, stop a run.
export type Grant = "allow_once" | "deny" | "always_for_task";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

export type CodeAction = "approve" | "deny" | "merge" | "iterate" | "discard";

export interface CodeBriefEdit {
  goal: string;
  acceptanceCriteria: string[];
  likelyFiles: string[];
  testCmd: string;
  constraints: string[];
  outOfScope: string[];
}

export interface Api {
  run(request: string): Promise<{ runId: string }>;
  approve(args: {
    runId: string;
    approvalId: string;
    grant: Grant;
  }): Promise<void>;
  /** Answer the brief card or the result card of a coding session. */
  codeDecide?(args: {
    runId: string;
    approvalId: string;
    action: CodeAction;
    brief?: CodeBriefEdit;
    feedback?: string;
  }): Promise<void>;
  /** End a run that is working or waiting on a card. */
  stop?(runId: string): Promise<void>;
  /** Write a proposed memory to a note (default: by its subject) and drop it from the inbox. */
  memoryApprove?(candidateId: string, note?: string): Promise<void>;
  /** Discard a proposed memory. */
  memoryReject?(candidateId: string): Promise<void>;
}

export function createApi(
  origin: string,
  token: string | null,
  fetchFn: typeof fetch = (...args) => fetch(...args),
): Api {
  const post = async (path: string, body: unknown) => {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    if (token) headers["X-Halo-Token"] = token;
    const response = await fetchFn(`${origin}${path}`, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      throw new ApiError(
        response.status,
        `${path} answered ${response.status}`,
      );
    }
    return response.json();
  };

  return {
    async run(request) {
      const { run_id } = await post("/run", { request });
      return { runId: run_id as string };
    },
    async approve({ runId, approvalId, grant }) {
      await post("/approve", { run_id: runId, approval_id: approvalId, grant });
    },
    async codeDecide({ runId, approvalId, action, brief, feedback }) {
      await post("/code/decision", {
        run_id: runId,
        approval_id: approvalId,
        action,
        ...(brief
          ? {
              brief: {
                goal: brief.goal,
                acceptance_criteria: brief.acceptanceCriteria,
                likely_files: brief.likelyFiles,
                test_cmd: brief.testCmd,
                constraints: brief.constraints,
                out_of_scope: brief.outOfScope,
              },
            }
          : {}),
        ...(feedback !== undefined ? { feedback } : {}),
      });
    },
    async stop(runId) {
      await post("/stop", { run_id: runId });
    },
    async memoryApprove(candidateId, note) {
      await post("/memory/approve", {
        candidate_id: candidateId,
        ...(note ? { note } : {}),
      });
    },
    async memoryReject(candidateId) {
      await post("/memory/reject", { candidate_id: candidateId });
    },
  };
}
