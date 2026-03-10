import React, { useState, useEffect } from "react";
import { Text, Box } from "ink";
import { Spinner } from "../components/Spinner.js";
import { getStatus, healthCheck, type StatusResult } from "../api.js";

type Phase = "loading" | "done" | "offline";

export function StatusCommand() {
  const [phase, setPhase] = useState<Phase>("loading");
  const [status, setStatus] = useState<StatusResult | null>(null);

  useEffect(() => {
    async function load() {
      const alive = await healthCheck();
      if (!alive) {
        setPhase("offline");
        return;
      }

      const result = await getStatus();
      setStatus(result);
      setPhase("done");
    }
    load();
  }, []);

  if (phase === "loading") {
    return (
      <Box padding={1}>
        <Spinner label="Loading status..." />
      </Box>
    );
  }

  if (phase === "offline") {
    return (
      <Box flexDirection="column" padding={1}>
        <Text bold color="cyan">[STATUS] </Text>
        <Text color="yellow">Agent backend not running.</Text>
      </Box>
    );
  }

  if (!status || !status.run_id) {
    return (
      <Box flexDirection="column" padding={1}>
        <Box>
          <Text bold color="cyan">[STATUS] </Text>
          <Text>No runs found.</Text>
        </Box>
        <Text dimColor>
          Run `test-guardian init` followed by `test-guardian run` to get started.
        </Text>
      </Box>
    );
  }

  const stateColor =
    status.state === "COMPLETE"
      ? "green"
      : status.state === "FAILED"
        ? "red"
        : "yellow";

  return (
    <Box flexDirection="column" padding={1}>
      <Box marginBottom={1}>
        <Text bold color="cyan">[STATUS] </Text>
        <Text>Run: {status.run_id}</Text>
      </Box>

      <Box flexDirection="column" marginLeft={2}>
        <Box>
          <Text>State: </Text>
          <Text bold color={stateColor}>
            {status.state}
          </Text>
          {status.termination_reason && (
            <Text dimColor> ({status.termination_reason})</Text>
          )}
        </Box>

        <Box>
          <Text>Iteration: </Text>
          <Text bold>{status.iteration}</Text>
        </Box>

        <Box>
          <Text>Tool calls: </Text>
          <Text bold>
            {status.tool_calls_used}/{status.tool_calls_budget}
          </Text>
        </Box>

        {status.files_changed.length > 0 && (
          <Box flexDirection="column" marginTop={1}>
            <Text underline>Files changed:</Text>
            {status.files_changed.map((f, i) => (
              <Text key={i} dimColor>
                {"  "}{f}
              </Text>
            ))}
          </Box>
        )}

        {status.test_results.length > 0 && (
          <Box flexDirection="column" marginTop={1}>
            <Text underline>Test results:</Text>
            {status.test_results.map((r, i) => (
              <Box key={i}>
                <Text dimColor>{"  "}Iter {r.iteration}: </Text>
                <Text color={r.all_pass ? "green" : "red"}>
                  {r.all_pass ? "PASSED" : "FAILED"}
                </Text>
              </Box>
            ))}
          </Box>
        )}
      </Box>
    </Box>
  );
}
