import React, { useState } from "react";
import { Text, Box, useInput } from "ink";

export type ApprovalAction = "apply" | "reject" | "edit" | "iterate";

interface ApprovalGateProps {
  onAction: (action: ApprovalAction) => void;
  prompt?: string;
}

export function ApprovalGate({
  onAction,
  prompt = "Review the changes above:",
}: ApprovalGateProps) {
  const [selected, setSelected] = useState<ApprovalAction | null>(null);

  useInput((input) => {
    switch (input.toLowerCase()) {
      case "a":
        setSelected("apply");
        onAction("apply");
        break;
      case "r":
        setSelected("reject");
        onAction("reject");
        break;
      case "e":
        setSelected("edit");
        onAction("edit");
        break;
      case "i":
        setSelected("iterate");
        onAction("iterate");
        break;
    }
  });

  if (selected) {
    return (
      <Box>
        <Text color="green">
          Selected: <Text bold>{selected}</Text>
        </Text>
      </Box>
    );
  }

  return (
    <Box flexDirection="column">
      <Text>{prompt}</Text>
      <Box marginTop={0} gap={2}>
        <Text>
          <Text color="green" bold>[a]</Text>
          <Text>pply</Text>
        </Text>
        <Text>
          <Text color="red" bold>[r]</Text>
          <Text>eject</Text>
        </Text>
        <Text>
          <Text color="yellow" bold>[e]</Text>
          <Text>dit</Text>
        </Text>
        <Text>
          <Text color="blue" bold>[i]</Text>
          <Text>terate</Text>
        </Text>
      </Box>
    </Box>
  );
}
