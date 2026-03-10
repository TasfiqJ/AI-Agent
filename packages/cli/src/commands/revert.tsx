import React, { useState, useEffect } from "react";
import { Text, Box } from "ink";
import { Spinner } from "../components/Spinner.js";
import { revertRun, healthCheck } from "../api.js";

type Phase = "confirming" | "reverting" | "done" | "offline";

export function RevertCommand() {
  const [phase, setPhase] = useState<Phase>("reverting");
  const [revertedFiles, setRevertedFiles] = useState<string[]>([]);
  const [message, setMessage] = useState("");

  useEffect(() => {
    async function run() {
      const alive = await healthCheck();
      if (!alive) {
        setPhase("offline");
        return;
      }

      setPhase("reverting");
      const result = await revertRun();
      setRevertedFiles(result.reverted_files);
      setMessage(result.message);
      setPhase("done");
    }
    run();
  }, []);

  if (phase === "offline") {
    return (
      <Box padding={1}>
        <Text color="yellow">Agent backend not running.</Text>
      </Box>
    );
  }

  if (phase === "reverting") {
    return (
      <Box padding={1}>
        <Spinner label="Reverting changes..." />
      </Box>
    );
  }

  return (
    <Box flexDirection="column" padding={1}>
      <Box marginBottom={1}>
        <Text bold color="red">[REVERT] </Text>
        <Text>{message}</Text>
      </Box>

      {revertedFiles.length > 0 && (
        <Box flexDirection="column" marginLeft={2}>
          {revertedFiles.map((f, i) => (
            <Text key={i} dimColor>
              Restored: {f}
            </Text>
          ))}
        </Box>
      )}

      {revertedFiles.length === 0 && (
        <Text dimColor>  No files to revert.</Text>
      )}
    </Box>
  );
}
