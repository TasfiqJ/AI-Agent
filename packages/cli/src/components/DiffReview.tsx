import React from "react";
import { Text, Box } from "ink";

interface DiffReviewProps {
  filePath: string;
  diff: string;
  isNew: boolean;
}

export function DiffReview({ filePath, diff, isNew }: DiffReviewProps) {
  const lines = diff.split("\n");

  return (
    <Box flexDirection="column">
      <Box marginBottom={0}>
        <Text bold>
          {isNew ? "[NEW] " : "[MOD] "}
        </Text>
        <Text bold color="cyan">
          {filePath}
        </Text>
      </Box>
      <Box flexDirection="column" marginLeft={2}>
        {lines.map((line, i) => (
          <DiffLine key={i} line={line} />
        ))}
      </Box>
    </Box>
  );
}

function DiffLine({ line }: { line: string }) {
  if (line.startsWith("+")) {
    return <Text color="green">{line}</Text>;
  }
  if (line.startsWith("-")) {
    return <Text color="red">{line}</Text>;
  }
  if (line.startsWith("@@")) {
    return <Text color="cyan">{line}</Text>;
  }
  return <Text dimColor>{line}</Text>;
}
