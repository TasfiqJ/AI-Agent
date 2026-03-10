import React from "react";
import { Text, Box } from "ink";

export interface LogEntry {
  type: "tool_call" | "llm" | "state" | "info" | "error";
  message: string;
  timestamp?: string;
}

interface LogStreamProps {
  entries: LogEntry[];
  maxVisible?: number;
}

const ICONS: Record<string, string> = {
  tool_call: ">",
  llm: "*",
  state: "#",
  info: "-",
  error: "!",
};

const COLORS: Record<string, string> = {
  tool_call: "cyan",
  llm: "magenta",
  state: "yellow",
  info: "white",
  error: "red",
};

export function LogStream({ entries, maxVisible = 15 }: LogStreamProps) {
  const visible = entries.slice(-maxVisible);

  return (
    <Box flexDirection="column">
      <Box marginBottom={0}>
        <Text bold underline>
          Activity Log
        </Text>
      </Box>
      {visible.length === 0 && (
        <Text dimColor>  Waiting for activity...</Text>
      )}
      {visible.map((entry, i) => (
        <Box key={i}>
          <Text color={COLORS[entry.type] || "white"}>
            {"  "}{ICONS[entry.type] || "-"}{" "}
          </Text>
          <Text color={entry.type === "error" ? "red" : undefined}>
            {entry.message}
          </Text>
        </Box>
      ))}
    </Box>
  );
}
