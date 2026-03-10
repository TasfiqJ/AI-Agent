import React from "react";
import { Text, Box } from "ink";
import type { Endpoint, PlanStep } from "@test-guardian/shared";

interface PlanViewProps {
  framework: string;
  endpoints: Endpoint[];
  steps: PlanStep[];
}

export function PlanView({ framework, endpoints, steps }: PlanViewProps) {
  return (
    <Box flexDirection="column">
      {/* Header */}
      <Box marginBottom={1}>
        <Text bold color="blue">
          [PLAN]
        </Text>
        <Text>
          {" "}
          Framework: <Text bold>{framework}</Text> | Endpoints:{" "}
          <Text bold>{endpoints.length}</Text> | Steps:{" "}
          <Text bold>{steps.length}</Text>
        </Text>
      </Box>

      {/* Endpoint table */}
      <Box flexDirection="column" marginBottom={1}>
        <Text bold underline>
          Detected Endpoints
        </Text>
        <Box marginTop={0}>
          <Text dimColor>
            {"  METHOD   PATH                              HANDLER          FILE"}
          </Text>
        </Box>
        {endpoints.map((ep, i) => (
          <Box key={i}>
            <Text>{"  "}</Text>
            <MethodBadge method={ep.method} />
            <Text>{"  "}</Text>
            <Text>{ep.path.padEnd(32)}</Text>
            <Text dimColor>{(ep.handler || "").padEnd(16)} </Text>
            <Text dimColor>
              {ep.file}:{ep.line}
            </Text>
          </Box>
        ))}
      </Box>

      {/* Steps */}
      <Box flexDirection="column">
        <Text bold underline>
          Plan Steps
        </Text>
        {steps.map((step) => (
          <Box key={step.id}>
            <Text dimColor>  {step.id}. </Text>
            <Text>{step.description}</Text>
            {step.outputFile && (
              <Text dimColor> → {step.outputFile}</Text>
            )}
          </Box>
        ))}
      </Box>
    </Box>
  );
}

function MethodBadge({ method }: { method: string }) {
  const colors: Record<string, string> = {
    GET: "green",
    POST: "yellow",
    PUT: "blue",
    PATCH: "cyan",
    DELETE: "red",
  };
  const color = colors[method] || "white";
  return <Text color={color} bold>{method.padEnd(6)}</Text>;
}
