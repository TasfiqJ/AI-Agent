/**
 * HTTP client for communicating with the test-guardian Python backend.
 */

const BASE_URL = process.env.GUARDIAN_API_URL || "http://localhost:8000";

export interface InitResult {
  framework: string;
  endpoints_detected: number;
  endpoints: Array<{
    method: string;
    path: string;
    handler: string;
    file: string;
    line: number;
  }>;
  message: string;
}

export interface StatusResult {
  run_id: string | null;
  state: string;
  termination_reason: string | null;
  iteration: number;
  tool_calls_used: number;
  tool_calls_budget: number;
  files_changed: string[];
  test_results: Array<{
    iteration: number;
    all_pass: boolean;
    raw_output: string;
  }>;
}

export interface RevertResult {
  reverted_files: string[];
  message: string;
}

export interface SSEEvent {
  type: string;
  data: Record<string, unknown>;
}

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${BASE_URL}${path}`;
  const res = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });

  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API error ${res.status}: ${body}`);
  }

  return res.json() as Promise<T>;
}

export async function healthCheck(): Promise<boolean> {
  try {
    await request("/health");
    return true;
  } catch {
    return false;
  }
}

export async function initRepo(repoPath: string): Promise<InitResult> {
  return request<InitResult>("/init", {
    method: "POST",
    body: JSON.stringify({ repo_path: repoPath }),
  });
}

export async function getStatus(): Promise<StatusResult> {
  return request<StatusResult>("/status");
}

export async function revertRun(runId?: string): Promise<RevertResult> {
  return request<RevertResult>("/revert", {
    method: "POST",
    body: JSON.stringify({ run_id: runId }),
  });
}

/**
 * Start an agent run with SSE streaming.
 * Calls onEvent for each SSE event received.
 */
export async function startRun(
  options: {
    repoPath: string;
    permissionMode?: string;
    maxIterations?: number;
    model?: string;
  },
  onEvent: (event: SSEEvent) => void
): Promise<void> {
  const url = `${BASE_URL}/run`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      repo_path: options.repoPath,
      permission_mode: options.permissionMode || "default",
      max_iterations: options.maxIterations || 3,
      model: options.model || "qwen2.5-coder:7b",
    }),
  });

  if (!res.ok || !res.body) {
    throw new Error(`Run failed: ${res.status}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    // Parse SSE events from buffer
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    let currentEvent = "";
    let currentData = "";

    for (const line of lines) {
      if (line.startsWith("event: ")) {
        currentEvent = line.slice(7);
      } else if (line.startsWith("data: ")) {
        currentData = line.slice(6);
      } else if (line === "" && currentEvent && currentData) {
        try {
          onEvent({
            type: currentEvent,
            data: JSON.parse(currentData),
          });
        } catch {
          // skip malformed events
        }
        currentEvent = "";
        currentData = "";
      }
    }
  }
}
