import React, { useState, useEffect } from "react";
import { Text, Box } from "ink";
import { Spinner } from "../components/Spinner.js";
import { PlanView } from "../components/PlanView.js";
import { initRepo, healthCheck } from "../api.js";
import type { Endpoint, PlanStep } from "@test-guardian/shared";

type Phase = "loading" | "done" | "offline" | "error";

export function PlanCommand() {
  const [phase, setPhase] = useState<Phase>("loading");
  const [framework, setFramework] = useState("");
  const [endpoints, setEndpoints] = useState<Endpoint[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    async function run() {
      const alive = await healthCheck();
      if (!alive) {
        setPhase("offline");
        return;
      }

      try {
        const result = await initRepo(process.cwd());
        setFramework(result.framework);

        const eps: Endpoint[] = result.endpoints.map((e) => ({
          method: e.method as Endpoint["method"],
          path: e.path,
          handler: e.handler,
          file: e.file,
          line: e.line,
        }));
        setEndpoints(eps);
        setPhase("done");
      } catch (err) {
        setError(String(err));
        setPhase("error");
      }
    }
    run();
  }, []);

  if (phase === "loading") {
    return (
      <Box padding={1}>
        <Spinner label="Analyzing repository (read-only)..." />
      </Box>
    );
  }

  if (phase === "offline") {
    return (
      <Box flexDirection="column" padding={1}>
        <Text bold color="blue">[PLAN] </Text>
        <Text color="yellow">
          Agent backend not running. Start it with:
        </Text>
        <Text dimColor>
          cd agent && uvicorn guardian.server:app --reload
        </Text>
      </Box>
    );
  }

  if (phase === "error") {
    return (
      <Box padding={1}>
        <Text color="red">Error: {error}</Text>
      </Box>
    );
  }

  const steps: PlanStep[] = endpoints.length > 0
    ? [
        {
          id: 1,
          description: "Detect API framework and extract endpoints",
          toolCalls: ["detect_framework", "extract_endpoints"],
        },
        {
          id: 2,
          description: `Generate test file for ${endpoints.length} endpoints`,
          toolCalls: ["file_write"],
          outputFile: "tests/test_api.py",
        },
        {
          id: 3,
          description: "Run tests in sandbox and verify results",
          toolCalls: ["run_in_sandbox"],
        },
      ]
    : [];

  return (
    <Box flexDirection="column" padding={1}>
      <Box marginBottom={1}>
        <Text bold color="blue">[PLAN] </Text>
        <Text>Read-only analysis complete</Text>
      </Box>
      <PlanView
        framework={framework}
        endpoints={endpoints}
        steps={steps}
      />
    </Box>
  );
}
