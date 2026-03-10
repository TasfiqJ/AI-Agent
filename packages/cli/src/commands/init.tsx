import React, { useState, useEffect } from "react";
import { Text, Box } from "ink";
import nodePath from "node:path";
import { Spinner } from "../components/Spinner.js";
import { PlanView } from "../components/PlanView.js";
import { initRepo, healthCheck } from "../api.js";
import type { Endpoint, PlanStep } from "@test-guardian/shared";

interface InitCommandProps {
  path?: string;
}

type InitState = "checking" | "connecting" | "detecting" | "done" | "error" | "offline";

export function InitCommand({ path }: InitCommandProps) {
  const [state, setState] = useState<InitState>("checking");
  const [framework, setFramework] = useState("");
  const [endpoints, setEndpoints] = useState<Endpoint[]>([]);
  const [error, setError] = useState("");

  if (!path) {
    return (
      <Box padding={1}>
        <Text color="red">Error: </Text>
        <Text>Please provide a path: test-guardian init {"<path>"}</Text>
      </Box>
    );
  }

  useEffect(() => {
    async function run() {
      // Check if backend is running
      setState("connecting");
      const alive = await healthCheck();
      if (!alive) {
        setState("offline");
        return;
      }

      // Detect framework and endpoints
      setState("detecting");
      try {
        const absPath = nodePath.resolve(path!);
        const result = await initRepo(absPath);
        setFramework(result.framework);

        const eps: Endpoint[] = result.endpoints.map((e) => ({
          method: e.method as Endpoint["method"],
          path: e.path,
          handler: e.handler,
          file: e.file,
          line: e.line,
        }));
        setEndpoints(eps);
        setState("done");
      } catch (err) {
        setError(String(err));
        setState("error");
      }
    }
    run();
  }, [path]);

  if (state === "connecting" || state === "checking") {
    return (
      <Box padding={1}>
        <Spinner label="Connecting to agent backend..." />
      </Box>
    );
  }

  if (state === "offline") {
    return (
      <Box flexDirection="column" padding={1}>
        <Box marginBottom={1}>
          <Text bold color="yellow">[INIT] </Text>
          <Text>Agent backend not running. Starting offline analysis...</Text>
        </Box>
        <Text dimColor>
          Start the backend: cd agent && uvicorn guardian.server:app
        </Text>
      </Box>
    );
  }

  if (state === "detecting") {
    return (
      <Box padding={1}>
        <Spinner label={`Analyzing ${path}...`} />
      </Box>
    );
  }

  if (state === "error") {
    return (
      <Box padding={1}>
        <Text color="red">Error: {error}</Text>
      </Box>
    );
  }

  // Done — show results
  const steps: PlanStep[] = endpoints.length > 0
    ? [{
        id: 1,
        description: `Generate API tests for ${endpoints.length} endpoints`,
        toolCalls: ["file_write"],
        outputFile: "tests/test_api.py",
      }]
    : [];

  return (
    <Box flexDirection="column" padding={1}>
      <Box marginBottom={1}>
        <Text bold color="green">[INIT] </Text>
        <Text>Repository initialized successfully</Text>
      </Box>
      <PlanView
        framework={framework}
        endpoints={endpoints}
        steps={steps}
      />
      <Box marginTop={1}>
        <Text dimColor>
          Run `test-guardian run` to generate tests.
        </Text>
      </Box>
    </Box>
  );
}
