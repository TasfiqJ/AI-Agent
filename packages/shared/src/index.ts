// ============================================================
// test-guardian shared types
// ============================================================

/** Agent loop states */
export type AgentState =
  | "IDLE"
  | "PLANNING"
  | "ACTING"
  | "VERIFYING"
  | "COMPLETE"
  | "FAILED"
  | "REVERTED";

/** Termination reasons */
export type TerminationReason =
  | "SUCCESS"
  | "PARTIAL"
  | "BUDGET_EXCEEDED"
  | "REJECTED"
  | "ERROR";

/** Permission modes */
export type PermissionMode = "plan" | "default" | "trust";

/** Detected API framework */
export type Framework = "flask" | "fastapi" | "express" | "unknown";

/** HTTP methods */
export type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

/** A detected API endpoint */
export interface Endpoint {
  method: HttpMethod;
  path: string;
  handler: string;
  file: string;
  line: number;
  params?: Record<string, string>;
  responseSchema?: Record<string, unknown>;
}

/** A step in the agent's plan */
export interface PlanStep {
  id: number;
  description: string;
  toolCalls: string[];
  outputFile?: string;
}

/** The structured plan output from the PLAN phase */
export interface AgentPlan {
  framework: Framework;
  endpoints: Endpoint[];
  steps: PlanStep[];
  testFiles: string[];
  successCriteria: string[];
  estimatedToolCalls: number;
}

/** A request to call a tool */
export interface ToolCallRequest {
  tool: string;
  params: Record<string, unknown>;
}

/** A unified diff patch */
export interface FileDiff {
  path: string;
  diff: string;
  isNew: boolean;
}

/** A fix to apply after test failure */
export interface TestFix {
  file: string;
  diff: string;
  reason: string;
}

/** Result of a single test */
export interface TestResult {
  name: string;
  passed: boolean;
  duration?: number;
  error?: string;
  stdout?: string;
  stderr?: string;
}

/** Result of a sandbox execution */
export interface SandboxResult {
  command: string;
  exitCode: number;
  stdout: string;
  stderr: string;
  timedOut: boolean;
  durationMs: number;
}

/** A trace log entry */
export interface TraceEntry {
  timestamp: string;
  runId: string;
  step: number;
  type: "tool_call" | "llm_request" | "llm_response" | "decision" | "error";
  data: Record<string, unknown>;
}

/** Agent run configuration */
export interface RunConfig {
  repoPath: string;
  permissionMode: PermissionMode;
  maxToolCalls: number;
  maxIterations: number;
  sandboxTimeout: number;
  ollamaModel: string;
}

/** Agent run status */
export interface RunStatus {
  runId: string;
  state: AgentState;
  phase: "plan" | "act" | "verify";
  iteration: number;
  toolCallsUsed: number;
  toolCallsBudget: number;
  testsTotal: number;
  testsPassed: number;
  testsFailed: number;
  filesChanged: string[];
  terminationReason?: TerminationReason;
}
