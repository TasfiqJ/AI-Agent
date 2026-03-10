import React, { useState, useEffect, useCallback } from "react";
import { Text, Box } from "ink";
import { Spinner } from "../components/Spinner.js";
import { LogStream, type LogEntry } from "../components/LogStream.js";
import { ApprovalGate, type ApprovalAction } from "../components/ApprovalGate.js";
import { startRun, healthCheck, type SSEEvent } from "../api.js";

interface RunCommandProps {
  trust: boolean;
  model?: string;
}

type RunPhase = "connecting" | "running" | "approval" | "complete" | "failed" | "offline";

export function RunCommand({ trust, model }: RunCommandProps) {
  const [phase, setPhase] = useState<RunPhase>("connecting");
  const [runId, setRunId] = useState("");
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);

  const addLog = useCallback((entry: LogEntry) => {
    setLogs((prev) => [...prev, entry]);
  }, []);

  const handleEvent = useCallback(
    (event: SSEEvent) => {
      switch (event.type) {
        case "run_start":
          setRunId(event.data.run_id as string);
          addLog({
            type: "state",
            message: `Run started: ${event.data.run_id}`,
          });
          break;
        case "run_complete":
          setResult(event.data);
          setPhase(
            event.data.termination_reason === "SUCCESS" ? "complete" : "failed"
          );
          addLog({
            type: "state",
            message: `Run finished: ${event.data.termination_reason}`,
          });
          break;
        case "error":
          addLog({
            type: "error",
            message: `Error: ${event.data.error}`,
          });
          setPhase("failed");
          break;
        default:
          addLog({
            type: "info",
            message: JSON.stringify(event.data).slice(0, 120),
          });
      }
    },
    [addLog]
  );

  useEffect(() => {
    async function run() {
      const alive = await healthCheck();
      if (!alive) {
        setPhase("offline");
        return;
      }

      setPhase("running");
      addLog({ type: "info", message: "Connecting to agent backend..." });

      try {
        await startRun(
          {
            repoPath: process.cwd(),
            permissionMode: trust ? "trust" : "default",
            model: model || "qwen2.5-coder:7b",
          },
          handleEvent
        );
      } catch (err) {
        addLog({ type: "error", message: String(err) });
        setPhase("failed");
      }
    }
    run();
  }, [trust, model, addLog, handleEvent]);

  if (phase === "offline") {
    return (
      <Box flexDirection="column" padding={1}>
        <Text color="yellow">
          Agent backend not running. Start it with:
        </Text>
        <Text dimColor>
          cd agent && uvicorn guardian.server:app --reload
        </Text>
      </Box>
    );
  }

  return (
    <Box flexDirection="column" padding={1}>
      {/* Header */}
      {trust && (
        <Box marginBottom={1}>
          <Text bold color="yellow">
            [WARNING] Trust mode — changes will be auto-approved.
          </Text>
        </Box>
      )}

      <Box marginBottom={1}>
        <Text bold color="magenta">
          [RUN]
        </Text>
        <Text> Plan → Act → Verify</Text>
        {runId && <Text dimColor> ({runId})</Text>}
      </Box>

      {/* Activity log */}
      <LogStream entries={logs} />

      {/* Status */}
      {phase === "running" && (
        <Box marginTop={1}>
          <Spinner label="Agent working..." />
        </Box>
      )}

      {phase === "complete" && (
        <Box marginTop={1} flexDirection="column">
          <Text bold color="green">
            All tests passed!
          </Text>
          {result && (
            <>
              <Text>
                Iterations: {String(result.iterations)} | Files:{" "}
                {(result.files_changed as string[])?.length || 0}
              </Text>
              {!trust && (
                <Box marginTop={1}>
                  <ApprovalGate
                    onAction={(action: ApprovalAction) => {
                      if (action === "reject") {
                        addLog({
                          type: "state",
                          message: "Changes rejected. Run `test-guardian revert` to undo.",
                        });
                      } else {
                        addLog({
                          type: "state",
                          message: "Changes applied!",
                        });
                      }
                    }}
                  />
                </Box>
              )}
            </>
          )}
        </Box>
      )}

      {phase === "failed" && (
        <Box marginTop={1}>
          <Text bold color="red">
            Run failed.
          </Text>
          {result?.termination_reason && (
            <Text> Reason: {String(result.termination_reason)}</Text>
          )}
        </Box>
      )}
    </Box>
  );
}
